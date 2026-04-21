from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.contracts.actor import ActorIdentity
from app.contracts.applications import ApplicationTransitionRequest
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.mutations import StaleMutationError
from app.contracts.scheduler import DeferredEffectRead
from app.contracts.tickets import TicketTransitionRequest
from app.core.context import use_audit_context
from app.repositories.applications import get_application
from app.repositories.authority import fetch_grant
from app.repositories.db import PostgresDatabase
from app.repositories.deferred_effects import (
    fetch_deferred_effect,
    list_archive_effects,
    mark_unclaimed_deferred_effect_skipped,
    update_precondition_state,
)
from app.repositories.tickets import get_ticket
from app.services.applications import transition_application
from app.services.authority import current_time, revoke_authority
from app.services.chapters import (
    ARCHIVE_EFFECT_APPLICATION_WITHDRAW,
    ARCHIVE_EFFECT_AUTHORITY_REVOKE,
    ARCHIVE_EFFECT_DEFERRED_EFFECT_CANCEL,
    ARCHIVE_EFFECT_TICKET_CLOSE,
    AuthorityDenied,
    archive_status,
    enqueue_missing_archive_effects,
    ensure_actor_has,
    finalize_archive_run,
    list_active_archive_runs,
    record_archive_manual_review_items,
)
from app.services.scheduler import register_scheduler_handler
from app.services.tickets import transition_ticket


CHAPTER_ARCHIVER_ID = "chapter-archiver"
ARCHIVE_WORKER_ACTOR = ActorIdentity(
    actor_kind="service",
    actor_id=CHAPTER_ARCHIVER_ID,
)
ARCHIVE_TICK_INTERVAL_SECONDS = 60
_PENDING_APPLICATION_STATES = {"submitted", "queued", "claimed", "in_review"}

_DB: PostgresDatabase | None = None


def configure_archive_worker(*, db: PostgresDatabase) -> None:
    global _DB
    _DB = db


def get_archive_db() -> PostgresDatabase:
    global _DB
    if _DB is None:
        _DB = PostgresDatabase()
    return _DB


def _audit_context(row: dict[str, Any]) -> AuditContextRead:
    return AuditContextRead(
        correlation_id=row["correlation_id"],
        causation_id=row["causation_id"],
        headers=CorrelationHeadersRead(
            x_correlation_id=row["correlation_id"],
            x_causation_id=row["causation_id"],
        ),
    )


def _terminal_states(state_machine: dict[str, Any]) -> set[str]:
    return {str(state["key"]) for state in state_machine.get("states", []) if state.get("terminal")}


def _edge_value(edge: dict[str, Any], key: str) -> Any:
    if key == "from":
        return edge.get("from", edge.get("from_state"))
    if key == "to":
        return edge.get("to", edge.get("to_state"))
    return edge.get(key)


def _find_close_edge(ticket_row: dict[str, Any]) -> dict[str, Any] | None:
    state_machine = ticket_row["category_snapshot"]["state_machine"]
    terminals = _terminal_states(state_machine)
    edges = [
        edge
        for edge in state_machine.get("edges", [])
        if str(_edge_value(edge, "from")) == str(ticket_row["state"])
        and str(_edge_value(edge, "to")) in terminals
        and str(edge.get("action")) in {"auto_close", "close"}
    ]
    return next((edge for edge in edges if edge.get("action") == "auto_close"), None) or (
        edges[0] if edges else None
    )


def _manual_item(
    *,
    kind: str,
    item_id: str,
    reason: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "item_id": item_id,
        "reason": reason,
        "metadata": metadata or {},
    }


def _mark_valid(connection, effect_id: UUID) -> None:
    try:
        update_precondition_state(
            connection,
            effect_id=effect_id,
            new_state="valid",
        )
    except Exception:
        return


def _skip_effect(connection, effect_id: UUID, reason: str) -> None:
    mark_unclaimed_deferred_effect_skipped(
        connection,
        effect_id=effect_id,
        reason=reason,
    )


def _validate_archive_effects(db: PostgresDatabase, archive_run: dict[str, Any]) -> None:
    with db.transaction() as connection:
        effects = list_archive_effects(
            connection,
            archive_run_id=archive_run["id"],
            statuses={"queued", "failed"},
        )
        manual_items: list[dict[str, Any]] = []
        for effect in effects:
            payload = effect["payload_json"]
            target_kind = payload["target_kind"]
            target_id = payload["target_id"]
            expected_version = int(payload.get("expected_version") or 0)
            expected_state = payload.get("expected_state")

            if target_kind == "application":
                application = get_application(connection, application_id=UUID(target_id))
                if application is None or application["state"] not in _PENDING_APPLICATION_STATES:
                    _skip_effect(connection, effect["id"], "already_resolved")
                elif (
                    int(application["version"]) == expected_version
                    and application["state"] == expected_state
                ):
                    _mark_valid(connection, effect["id"])
                else:
                    _skip_effect(connection, effect["id"], "stale_precondition")
            elif target_kind == "ticket":
                ticket = get_ticket(connection, UUID(target_id))
                if ticket is None or ticket["terminal_at"] is not None:
                    _skip_effect(connection, effect["id"], "already_resolved")
                    continue
                if _find_close_edge(ticket) is None:
                    manual_items.append(
                        _manual_item(
                            kind="ticket",
                            item_id=target_id,
                            reason="ticket_requires_manual_review",
                            metadata={"state": ticket["state"]},
                        )
                    )
                    _skip_effect(connection, effect["id"], "manual_review_required")
                elif int(ticket["version"]) == expected_version and ticket["state"] == expected_state:
                    _mark_valid(connection, effect["id"])
                else:
                    _skip_effect(connection, effect["id"], "stale_precondition")
            elif target_kind == "authority_grant":
                grant = fetch_grant(connection, grant_id=UUID(target_id))
                if (
                    grant is None
                    or grant["revoked_at"] is not None
                    or (
                        grant["expires_at"] is not None
                        and grant["expires_at"] <= current_time()
                    )
                ):
                    _skip_effect(connection, effect["id"], "already_resolved")
                elif int(grant["current_seq"]) == expected_version:
                    _mark_valid(connection, effect["id"])
                else:
                    _skip_effect(connection, effect["id"], "stale_precondition")
            elif target_kind == "deferred_effect":
                target = fetch_deferred_effect(connection, UUID(target_id))
                if target is None or target["status"] in {"completed", "skipped"}:
                    _skip_effect(connection, effect["id"], "already_resolved")
                elif target["status"] in {"queued", "failed"} or (
                    target["status"] == "claimed"
                    and target["lease_until"] is not None
                    and target["lease_until"] < datetime.now(UTC)
                ):
                    _mark_valid(connection, effect["id"])
                else:
                    manual_items.append(
                        _manual_item(
                            kind="deferred_effect",
                            item_id=target_id,
                            reason="deferred_effect_in_flight",
                        )
                    )
                    _skip_effect(connection, effect["id"], "manual_review_required")
        if manual_items:
            record_archive_manual_review_items(
                db,
                archive_run_id=archive_run["id"],
                items=manual_items,
            )


def archive_worker_tick() -> list[Any]:
    db = get_archive_db()
    statuses = []
    for archive_run in list_active_archive_runs(db):
        try:
            with use_audit_context(_audit_context(archive_run)):
                enqueue_missing_archive_effects(db, archive_run=archive_run)
                _validate_archive_effects(db, archive_run)
                enqueue_missing_archive_effects(db, archive_run=archive_run)
                finalized = finalize_archive_run(
                    db,
                    archive_run=archive_run,
                    actor=ARCHIVE_WORKER_ACTOR,
                )
                statuses.append(
                    finalized
                    if finalized is not None
                    else archive_status(db, archive_run["chapter_id"], ARCHIVE_WORKER_ACTOR)
                )
        except StaleMutationError:
            continue
    return statuses


def _record_authority_denied(effect: DeferredEffectRead, permission: str) -> None:
    record_archive_manual_review_items(
        get_archive_db(),
        archive_run_id=UUID(str(effect.payload_json["archive_run_id"])),
        items=[
            _manual_item(
                kind=str(effect.payload_json["target_kind"]),
                item_id=str(effect.payload_json["target_id"]),
                reason="archive_worker_authority_denied",
                metadata={"permission": permission},
            )
        ],
    )


@register_scheduler_handler(ARCHIVE_EFFECT_APPLICATION_WITHDRAW)
def handle_archive_application_withdraw(effect: DeferredEffectRead) -> None:
    db = get_archive_db()
    payload = effect.payload_json
    permission = "application.withdraw"
    try:
        ensure_actor_has(
            db=db,
            permission=permission,
            scope_kind="chapter",
            scope_id=str(payload["chapter_id"]),
            actor=ARCHIVE_WORKER_ACTOR,
        )
    except AuthorityDenied:
        _record_authority_denied(effect, permission)
        return

    with db.connection() as connection:
        application = get_application(connection, application_id=UUID(str(payload["target_id"])))
    if application is None or application["state"] not in _PENDING_APPLICATION_STATES:
        return
    transition_application(
        db,
        UUID(str(payload["target_id"])),
        int(payload["expected_version"]),
        ApplicationTransitionRequest(
            action="withdraw",
            notes=f"chapter archived: {payload['archive_reason']}",
        ),
        ARCHIVE_WORKER_ACTOR,
    )


@register_scheduler_handler(ARCHIVE_EFFECT_TICKET_CLOSE)
def handle_archive_ticket_close(effect: DeferredEffectRead) -> None:
    db = get_archive_db()
    payload = effect.payload_json
    permission = "ticket.transition"
    try:
        ensure_actor_has(
            db=db,
            permission=permission,
            scope_kind="chapter",
            scope_id=str(payload["chapter_id"]),
            actor=ARCHIVE_WORKER_ACTOR,
        )
    except AuthorityDenied:
        _record_authority_denied(effect, permission)
        return

    with db.connection() as connection:
        ticket = get_ticket(connection, UUID(str(payload["target_id"])))
    if ticket is None or ticket["terminal_at"] is not None:
        return
    close_edge = _find_close_edge(ticket)
    if close_edge is None:
        record_archive_manual_review_items(
            db,
            archive_run_id=UUID(str(payload["archive_run_id"])),
            items=[
                _manual_item(
                    kind="ticket",
                    item_id=str(payload["target_id"]),
                    reason="ticket_requires_manual_review",
                    metadata={"state": ticket["state"]},
                )
            ],
        )
        return
    transition_ticket(
        db,
        UUID(str(payload["target_id"])),
        int(payload["expected_version"]),
        TicketTransitionRequest(
            action=str(close_edge["action"]),
            to_state=str(_edge_value(close_edge, "to")),
            reason=f"chapter archived: {payload['archive_reason']}",
            resolution="chapter_archived",
            originating_actor_kind="service",
            originating_actor_id=CHAPTER_ARCHIVER_ID,
        ),
        ARCHIVE_WORKER_ACTOR,
    )


@register_scheduler_handler(ARCHIVE_EFFECT_AUTHORITY_REVOKE)
def handle_archive_authority_revoke(effect: DeferredEffectRead) -> None:
    db = get_archive_db()
    payload = effect.payload_json
    permission = "authority.revoke"
    try:
        ensure_actor_has(
            db=db,
            permission=permission,
            scope_kind="chapter",
            scope_id=str(payload["chapter_id"]),
            actor=ARCHIVE_WORKER_ACTOR,
        )
    except AuthorityDenied:
        _record_authority_denied(effect, permission)
        return

    with db.connection() as connection:
        grant = fetch_grant(connection, grant_id=UUID(str(payload["target_id"])))
    if grant is None or grant["revoked_at"] is not None:
        return
    if grant["expires_at"] is not None and grant["expires_at"] <= current_time():
        return
    revoke_authority(
        db,
        grant_id=UUID(str(payload["target_id"])),
        actor=(ARCHIVE_WORKER_ACTOR.actor_kind, ARCHIVE_WORKER_ACTOR.actor_id),
        revoked_by=CHAPTER_ARCHIVER_ID,
        reason=f"chapter archived: {payload['archive_reason']}",
        expected_version=int(payload["expected_version"]),
    )


@register_scheduler_handler(ARCHIVE_EFFECT_DEFERRED_EFFECT_CANCEL)
def handle_archive_deferred_effect_cancel(effect: DeferredEffectRead) -> None:
    payload = effect.payload_json
    with get_archive_db().connection() as connection:
        mark_unclaimed_deferred_effect_skipped(
            connection,
            effect_id=UUID(str(payload["target_id"])),
            reason=f"chapter archived: {payload['archive_reason']}",
        )


__all__ = [
    "ARCHIVE_TICK_INTERVAL_SECONDS",
    "ARCHIVE_WORKER_ACTOR",
    "CHAPTER_ARCHIVER_ID",
    "archive_worker_tick",
    "configure_archive_worker",
    "get_archive_db",
]
