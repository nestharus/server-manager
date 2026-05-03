from __future__ import annotations

import logging
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from math import floor
from typing import Any
from uuid import uuid4

from psycopg import Connection

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.mutations import StaleMutationError
from app.contracts.notifications import NotificationEventDraft
from app.contracts.ticket_categories import TicketSlaConsequence, TicketSlaThreshold
from app.contracts.tickets import (
    SlaTriggerRead,
    TicketCategorySnapshotRead,
    TicketTransitionRequest,
)
from app.core.context import get_current_audit_context, use_audit_context
from app.repositories.ticket_sla import TicketSlaRepository
from app.services import notification_events
from app.services.ticket_categories import find_state_path
from app.services.tickets import TicketsService

logger = logging.getLogger(__name__)

SLA_WORKER_ID = "sla-worker"
SLA_NOTIFICATION_PAYLOAD_ALLOWLIST = frozenset(
    {
        "ticket_id",
        "rule_key",
        "threshold_seconds",
        "consequence",
        "target_state",
        "state",
        "state_entered_at",
        "elapsed_seconds",
        "owner_id",
        "routing_scope",
        "queue",
    }
)


@dataclass(frozen=True)
class SlaCandidateTicket:
    id: Any
    category_snapshot: TicketCategorySnapshotRead
    reporter_id: str
    subject_id: str | None
    state: str
    priority: str
    owner_id: str | None
    created_at: datetime
    updated_at: datetime
    version: int


@dataclass(frozen=True)
class EligibleThreshold:
    rule_key: str
    rule_index: int
    threshold_index: int
    threshold: TicketSlaThreshold
    state: str
    state_entered_at: datetime
    elapsed_seconds: int


def _root_audit_context() -> AuditContextRead:
    correlation_id = uuid4()
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=None,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=None,
        ),
    )


def _candidate_from_row(row: dict[str, Any]) -> SlaCandidateTicket:
    return SlaCandidateTicket(
        id=row["id"],
        category_snapshot=TicketCategorySnapshotRead.model_validate(
            row["category_snapshot"]
        ),
        reporter_id=row["reporter_id"],
        subject_id=row["subject_id"],
        state=row["state"],
        priority=row["priority"],
        owner_id=row["owner_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        version=int(row["version"]),
    )


def _trigger_from_row(row: dict[str, Any]) -> SlaTriggerRead:
    return SlaTriggerRead(
        id=row["id"],
        ticket_id=row["ticket_id"],
        rule_key=row["rule_key"],
        threshold_seconds=int(row["threshold_seconds"]),
        consequence=row["consequence"],
        target_state=row["target_state"],
        state=row["state"],
        state_entered_at=row["state_entered_at"],
        elapsed_seconds=int(row["elapsed_seconds"]),
        applied_at=row["applied_at"],
        effect_summary=row["effect_summary_json"],
    )


def _eligible_thresholds(
    ticket: SlaCandidateTicket,
    *,
    state_entered_at: datetime,
    now: datetime,
) -> list[EligibleThreshold]:
    elapsed_seconds = max(0, floor((now - state_entered_at).total_seconds()))
    thresholds: list[EligibleThreshold] = []
    for rule_index, rule in enumerate(ticket.category_snapshot.sla_rules.rules):
        if ticket.state not in rule.states:
            continue
        for threshold_index, threshold in enumerate(rule.thresholds):
            if elapsed_seconds < threshold.elapsed_seconds:
                continue
            thresholds.append(
                EligibleThreshold(
                    rule_key=rule.key,
                    rule_index=rule_index,
                    threshold_index=threshold_index,
                    threshold=threshold,
                    state=ticket.state,
                    state_entered_at=state_entered_at,
                    elapsed_seconds=elapsed_seconds,
                )
            )
    return sorted(
        thresholds,
        key=lambda item: (
            item.threshold.elapsed_seconds,
            item.rule_index,
            item.threshold_index,
        ),
    )


def _notification_payload(
    ticket: SlaCandidateTicket,
    threshold: EligibleThreshold,
    *,
    consequence: TicketSlaConsequence,
) -> dict[str, Any]:
    routing_scope = ticket.category_snapshot.routing_scope
    return {
        "ticket_id": str(ticket.id),
        "rule_key": threshold.rule_key,
        "threshold_seconds": threshold.threshold.elapsed_seconds,
        "consequence": consequence,
        "target_state": threshold.threshold.target_state,
        "state": threshold.state,
        "state_entered_at": threshold.state_entered_at.isoformat(),
        "elapsed_seconds": threshold.elapsed_seconds,
        "owner_id": ticket.owner_id,
        "routing_scope": routing_scope.model_dump(mode="json"),
        "queue": routing_scope.queue,
    }


class TicketSlaService:
    def __init__(
        self,
        ticket_sla_repo: TicketSlaRepository,
        tickets_service: TicketsService,
        notification_events_module,
    ) -> None:
        self.ticket_sla_repo = ticket_sla_repo
        self.tickets_service = tickets_service
        self.notification_events_module = notification_events_module

    def _derive_state_entered_at(
        self,
        connection: Connection[Any],
        ticket: SlaCandidateTicket,
    ) -> datetime:
        row = self.ticket_sla_repo._find_last_transition_to_state_on(
            connection,
            ticket_id=ticket.id,
            state=ticket.state,
        )
        if row is None:
            return ticket.created_at
        return row["recorded_at"]

    def _insert_trigger(
        self,
        connection: Connection[Any],
        ticket: SlaCandidateTicket,
        threshold: EligibleThreshold,
        *,
        consequence: TicketSlaConsequence,
        effect_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return self.ticket_sla_repo._insert_trigger_on(
            connection,
            row={
                "id": uuid4(),
                "ticket_id": ticket.id,
                "rule_key": threshold.rule_key,
                "threshold_seconds": threshold.threshold.elapsed_seconds,
                "consequence": consequence,
                "target_state": threshold.threshold.target_state,
                "state": threshold.state,
                "state_entered_at": threshold.state_entered_at,
                "elapsed_seconds": threshold.elapsed_seconds,
                "effect_summary_json": effect_summary or {},
            },
        )

    def _emit_review_notification(
        self,
        connection: Connection[Any],
        ticket: SlaCandidateTicket,
        threshold: EligibleThreshold,
        actor: ActorIdentity,
        *,
        trigger_consequence: TicketSlaConsequence,
        fallback_from: str | None = None,
        fallback_reason: str | None = None,
    ) -> SlaTriggerRead | None:
        summary = {"result": "flag_for_review"}
        if fallback_from is not None:
            summary["fallback_from"] = fallback_from
        if fallback_reason is not None:
            summary["fallback_reason"] = fallback_reason
        row = self._insert_trigger(
            connection,
            ticket,
            threshold,
            consequence=trigger_consequence,
            effect_summary=summary,
        )
        if row is None:
            return None

        routing_scope = ticket.category_snapshot.routing_scope
        event = self.notification_events_module.emit(
            self.ticket_sla_repo.db,
            event=NotificationEventDraft(
                event_type="ticket.sla.flag_for_review",
                scope_kind=routing_scope.scope_kind,
                scope_id=routing_scope.scope_id,
                payload_json=_notification_payload(
                    ticket,
                    threshold,
                    consequence=trigger_consequence,
                ),
            ),
            actor=actor,
            connection=connection,
            payload_allowlist=SLA_NOTIFICATION_PAYLOAD_ALLOWLIST,
        )
        updated_summary = {
            **summary,
            "notification_event_id": str(event.id),
        }
        return _trigger_from_row(
            self.ticket_sla_repo._update_trigger_effect_summary_on(
                connection,
                trigger_id=row["id"],
                effect_summary_json=updated_summary,
            )
        )

    def _emit_sla_notification(
        self,
        connection: Connection[Any],
        ticket: SlaCandidateTicket,
        threshold: EligibleThreshold,
        actor: ActorIdentity,
        *,
        consequence: TicketSlaConsequence,
        event_type: str,
    ) -> SlaTriggerRead | None:
        row = self._insert_trigger(
            connection,
            ticket,
            threshold,
            consequence=consequence,
            effect_summary={"result": "notification_claimed"},
        )
        if row is None:
            return None

        routing_scope = ticket.category_snapshot.routing_scope
        event = self.notification_events_module.emit(
            self.ticket_sla_repo.db,
            event=NotificationEventDraft(
                event_type=event_type,
                scope_kind=routing_scope.scope_kind,
                scope_id=routing_scope.scope_id,
                payload_json=_notification_payload(ticket, threshold, consequence=consequence),
            ),
            actor=actor,
            connection=connection,
            payload_allowlist=SLA_NOTIFICATION_PAYLOAD_ALLOWLIST,
        )
        return _trigger_from_row(
            self.ticket_sla_repo._update_trigger_effect_summary_on(
                connection,
                trigger_id=row["id"],
                effect_summary_json={
                    "result": "notification_emitted",
                    "notification_event_id": str(event.id),
                },
            )
        )

    def _handle_notify_owner(
        self,
        connection: Connection[Any],
        ticket: SlaCandidateTicket,
        threshold: EligibleThreshold,
        actor: ActorIdentity,
    ) -> SlaTriggerRead | None:
        if ticket.owner_id is None:
            return self._emit_review_notification(
                connection,
                ticket,
                threshold,
                actor,
                trigger_consequence="notify_owner",
                fallback_from="notify_owner",
                fallback_reason="missing_owner",
            )
        return self._emit_sla_notification(
            connection,
            ticket,
            threshold,
            actor,
            consequence="notify_owner",
            event_type="ticket.sla.notify_owner",
        )

    def _handle_notify_scope(
        self,
        connection: Connection[Any],
        ticket: SlaCandidateTicket,
        threshold: EligibleThreshold,
        actor: ActorIdentity,
    ) -> SlaTriggerRead | None:
        return self._emit_sla_notification(
            connection,
            ticket,
            threshold,
            actor,
            consequence="notify_scope",
            event_type="ticket.sla.notify_scope",
        )

    def _handle_flag_for_review(
        self,
        connection: Connection[Any],
        ticket: SlaCandidateTicket,
        threshold: EligibleThreshold,
        actor: ActorIdentity,
    ) -> SlaTriggerRead | None:
        return self._emit_review_notification(
            connection,
            ticket,
            threshold,
            actor,
            trigger_consequence="flag_for_review",
        )

    def _handle_auto_escalate(
        self,
        connection: Connection[Any],
        ticket: SlaCandidateTicket,
        threshold: EligibleThreshold,
        actor: ActorIdentity,
    ) -> SlaTriggerRead | None:
        target_state = threshold.threshold.target_state
        if target_state is None:
            return self._emit_review_notification(
                connection,
                ticket,
                threshold,
                actor,
                trigger_consequence="auto_escalate",
                fallback_from="auto_escalate",
                fallback_reason="missing_target_state",
            )

        path = find_state_path(
            ticket.category_snapshot.state_machine.model_dump(mode="json", by_alias=True),
            ticket.state,
            target_state,
        )
        if path is None or len(path) != 1:
            return self._emit_review_notification(
                connection,
                ticket,
                threshold,
                actor,
                trigger_consequence="auto_escalate",
                fallback_from="auto_escalate",
                fallback_reason="no_direct_edge",
            )
        edge = path[0]
        if edge.get("requires_resolution"):
            return self._emit_review_notification(
                connection,
                ticket,
                threshold,
                actor,
                trigger_consequence="auto_escalate",
                fallback_from="auto_escalate",
                fallback_reason="requires_resolution",
            )

        try:
            transitioned_ticket, _result = self.tickets_service._transition_ticket_on(
                connection,
                ticket.id,
                ticket.version,
                TicketTransitionRequest(
                    action=edge["action"],
                    to_state=target_state,
                    reason=(
                        f"SLA threshold {threshold.rule_key}/"
                        f"{threshold.threshold.elapsed_seconds} exceeded after "
                        f"{threshold.elapsed_seconds} seconds"
                    ),
                    resolution=None,
                    owner_id=None,
                    priority=None,
                    originating_actor_kind=actor.actor_kind,
                    originating_actor_id=actor.actor_id,
                ),
                actor,
            )
        except StaleMutationError:
            logger.info(
                "ticket SLA auto-escalate skipped stale ticket version",
                extra={
                    "ticket_id": str(ticket.id),
                    "rule_key": threshold.rule_key,
                    "threshold_seconds": threshold.threshold.elapsed_seconds,
                    "expected_version": ticket.version,
                },
            )
            return None

        row = self._insert_trigger(
            connection,
            ticket,
            threshold,
            consequence="auto_escalate",
            effect_summary={
                "result": "transitioned",
                "ticket_version": transitioned_ticket.version,
                "action": edge["action"],
                "to_state": target_state,
            },
        )
        if row is None:
            return None
        return _trigger_from_row(row)

    def _handle_threshold(
        self,
        connection: Connection[Any],
        ticket: SlaCandidateTicket,
        threshold: EligibleThreshold,
        actor: ActorIdentity,
    ) -> SlaTriggerRead | None:
        consequence = threshold.threshold.consequence
        if consequence == "notify_owner":
            return self._handle_notify_owner(connection, ticket, threshold, actor)
        if consequence == "notify_scope":
            return self._handle_notify_scope(connection, ticket, threshold, actor)
        if consequence == "flag_for_review":
            return self._handle_flag_for_review(connection, ticket, threshold, actor)
        if consequence == "auto_escalate":
            return self._handle_auto_escalate(connection, ticket, threshold, actor)
        raise ValueError(f"unsupported SLA consequence {consequence}")

    def evaluate_ticket_sla(
        self,
        *,
        now: datetime | None = None,
        limit: int = 100,
    ) -> list[SlaTriggerRead]:
        resolved_now = now or datetime.now(tz=UTC)
        actor = ActorIdentity(actor_kind="service", actor_id=SLA_WORKER_ID)
        existing_ctx = get_current_audit_context()
        context = (
            use_audit_context(_root_audit_context())
            if existing_ctx is None
            else nullcontext()
        )

        applied: list[SlaTriggerRead] = []
        with context:
            with self.ticket_sla_repo.db.transaction() as connection:
                rows = self.ticket_sla_repo._find_due_tickets_on(
                    connection,
                    now=resolved_now,
                    limit=limit,
                )
                for row in rows:
                    ticket = _candidate_from_row(row)
                    state_entered_at = self._derive_state_entered_at(connection, ticket)
                    thresholds = _eligible_thresholds(
                        ticket,
                        state_entered_at=state_entered_at,
                        now=resolved_now,
                    )
                    existing = {
                        (trigger["rule_key"], int(trigger["threshold_seconds"]))
                        for trigger in self.ticket_sla_repo._get_existing_triggers_on(
                            connection,
                            ticket_id=ticket.id,
                        )
                    }
                    for threshold in thresholds:
                        trigger_key = (
                            threshold.rule_key,
                            threshold.threshold.elapsed_seconds,
                        )
                        if trigger_key in existing:
                            continue
                        trigger = self._handle_threshold(
                            connection,
                            ticket,
                            threshold,
                            actor,
                        )
                        if trigger is None:
                            continue
                        existing.add(trigger_key)
                        applied.append(trigger)
                        if trigger.consequence == "auto_escalate":
                            break
        return applied


__all__ = [
    "SLA_NOTIFICATION_PAYLOAD_ALLOWLIST",
    "SLA_WORKER_ID",
    "TicketSlaService",
]
