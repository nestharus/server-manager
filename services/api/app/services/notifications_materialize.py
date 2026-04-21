from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
from string import Template
from typing import Any
from uuid import UUID, uuid4

from app.contracts.notifications import (
    NotificationEnvelopeRead,
    NotificationEventRead,
    NotificationMaterializationResult,
    NotificationRuleRead,
    TemplateRenderError,
)
from app.contracts.scheduler import DeferredEffectCreate
from app.repositories.db import PostgresDatabase
from app.repositories.deferred_effects import enqueue_effect
from app.repositories.notification_events import fetch_notification_event
from app.repositories.notifications import (
    insert_notification_envelope_on_conflict_do_nothing,
    list_enabled_rules_for_event,
)
from app.services.scheduler import DEFAULT_MAX_ATTEMPTS


def _event_from_row(row: dict[str, Any]) -> NotificationEventRead:
    return NotificationEventRead(
        id=row["id"],
        event_type=row["event_type"],
        correlation_id=row["correlation_id"],
        causation_id=row["causation_id"],
        scope_kind=row["scope_kind"],
        scope_id=row["scope_id"],
        payload=row["payload_json"],
        created_at=row["created_at"],
    )


def _rule_from_row(row: dict[str, Any]) -> NotificationRuleRead:
    return NotificationRuleRead(
        id=row["id"],
        trigger_json=row["trigger_json"],
        scope_kind=row["scope_kind"],
        scope_id=row["scope_id"],
        recipients_json=row["recipients_json"],
        channel=row["channel"],
        template_json=row["template_json"],
        actionable=row["actionable"],
        grouping=row["grouping"],
        enabled=row["enabled"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        version=int(row["version"]),
    )


def _trigger_matches(rule: NotificationRuleRead, event: NotificationEventRead) -> bool:
    event_type = rule.trigger_json.event_type
    if event_type.endswith(".*"):
        if not event.event_type.startswith(event_type[:-1]):
            return False
    elif event.event_type != event_type:
        return False
    filters = rule.trigger_json.payload_filters or {}
    return all(event.payload.get(key) == value for key, value in filters.items())


def _recipient_selector_key(recipients_json: dict[str, Any]) -> str:
    encoded = json.dumps(recipients_json, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
    return f"unresolved:{digest}"


def _resolve_recipients(rule: NotificationRuleRead) -> list[dict[str, Any]]:
    recipients = rule.recipients_json
    kind = recipients.get("kind")
    if kind == "discord_user":
        user_id = str(recipients.get("user_id", "")).strip()
        if not user_id:
            return [
                {
                    "recipient_key": _recipient_selector_key(recipients),
                    "recipient_discord_id": None,
                    "recipient_display": "unresolved recipient",
                    "reason": "recipient_unresolved",
                }
            ]
        return [
            {
                "recipient_key": f"discord_user:{user_id}",
                "recipient_discord_id": user_id,
                "recipient_display": user_id,
                "reason": None,
            }
        ]
    if kind == "discord_users":
        resolved: list[dict[str, Any]] = []
        for raw_user_id in recipients.get("user_ids", []):
            user_id = str(raw_user_id).strip()
            if not user_id:
                continue
            resolved.append(
                {
                    "recipient_key": f"discord_user:{user_id}",
                    "recipient_discord_id": user_id,
                    "recipient_display": user_id,
                    "reason": None,
                }
            )
        if resolved:
            return resolved
    return [
        {
            "recipient_key": _recipient_selector_key(recipients),
            "recipient_discord_id": None,
            "recipient_display": "unresolved recipient",
            "reason": "recipient_unresolved",
        }
    ]


def _resolve_destination(rule: NotificationRuleRead) -> tuple[str | None, str | None]:
    if rule.channel == "dm":
        return None, None
    if rule.channel == "designated_channel":
        destination = str(rule.recipients_json.get("designated_channel_id", "")).strip()
        if not destination:
            return None, "destination_missing"
        return destination, None
    return None, "thread_channel_out_of_scope"


def _template_context(event: NotificationEventRead, rule: NotificationRuleRead) -> dict[str, str]:
    context = {
        "event_id": str(event.id),
        "event_type": event.event_type,
        "correlation_id": str(event.correlation_id),
        "causation_id": "" if event.causation_id is None else str(event.causation_id),
        "scope_kind": "" if event.scope_kind is None else event.scope_kind,
        "scope_id": "" if event.scope_id is None else event.scope_id,
        "rule_id": str(rule.id),
    }
    for key, value in event.payload.items():
        context[f"payload_{key}"] = "" if value is None else str(value)
    return context


def _render_template(rule: NotificationRuleRead, event: NotificationEventRead) -> tuple[str, str]:
    context = _template_context(event, rule)
    title_template = str(rule.template_json.get("title", ""))
    body_template = str(rule.template_json.get("body", ""))
    try:
        return Template(title_template).substitute(context), Template(body_template).substitute(context)
    except KeyError as error:
        raise TemplateRenderError(str(error.args[0])) from error


def _envelope_from_row(row: dict[str, Any]) -> NotificationEnvelopeRead:
    return NotificationEnvelopeRead.model_validate(row)


def materialize_event(
    db: PostgresDatabase,
    event_id: UUID,
    *,
    worker_id: str = "notification-dispatcher",
) -> NotificationMaterializationResult:
    created_count = 0
    skipped_count = 0
    delivery_effect_count = 0
    envelope_ids: list[UUID] = []

    with db.transaction() as connection:
        event_row = fetch_notification_event(connection, event_id)
        if event_row is None:
            raise LookupError(f"notification event {event_id} was not found")
        event = _event_from_row(event_row)
        candidate_rules = [
            _rule_from_row(row)
            for row in list_enabled_rules_for_event(connection, event_row=event_row)
        ]
        for rule in candidate_rules:
            if not rule.enabled or not _trigger_matches(rule, event):
                continue
            rendered_title = ""
            rendered_body = ""
            render_error: str | None = None
            try:
                rendered_title, rendered_body = _render_template(rule, event)
            except TemplateRenderError:
                render_error = "template_missing_key"
            destination_channel_id, destination_error = _resolve_destination(rule)
            for recipient in _resolve_recipients(rule):
                reason = recipient["reason"] or destination_error or render_error
                status = "skipped" if reason is not None else "pending"
                now = datetime.now(UTC)
                inserted = insert_notification_envelope_on_conflict_do_nothing(
                    connection,
                    row={
                        "id": uuid4(),
                        "rule_id": rule.id,
                        "rule_version": rule.version,
                        "source_event_id": event.id,
                        "root_correlation_id": event.correlation_id,
                        "causation_id": event.causation_id,
                        "grouping": rule.grouping,
                        "recipient_key": recipient["recipient_key"],
                        "recipient_discord_id": recipient["recipient_discord_id"],
                        "recipient_display": recipient["recipient_display"],
                        "channel": rule.channel,
                        "destination_channel_id": destination_channel_id,
                        "template_snapshot_json": deepcopy(rule.template_json),
                        "rendered_title": rendered_title,
                        "rendered_body": rendered_body,
                        "actionable": rule.actionable,
                        "delivery_status": status,
                        "claimed_by": None,
                        "claimed_at": None,
                        "lease_until": None,
                        "attempts": 0,
                        "max_attempts": DEFAULT_MAX_ATTEMPTS,
                        "last_error_json": None if reason is None else {"reason": reason},
                        "discord_message_id": None,
                        "delivered_at": None,
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                if inserted is None:
                    continue
                created_count += 1
                envelope = _envelope_from_row(inserted)
                envelope_ids.append(envelope.id)
                if envelope.delivery_status == "skipped":
                    skipped_count += 1
                    continue
                enqueue_effect(
                    connection,
                    effect=DeferredEffectCreate(
                        subsystem="notifications",
                        effect_type="notifications_deliver",
                        idempotency_key=f"notifications:deliver:{envelope.id}",
                        payload_json={"envelope_id": str(envelope.id)},
                        consequence_level="safe",
                        correlation_id=event.correlation_id,
                        causation_id=event.causation_id,
                    ),
                    correlation_id=event.correlation_id,
                    max_attempts=DEFAULT_MAX_ATTEMPTS,
                )
                delivery_effect_count += 1

    return NotificationMaterializationResult(
        event_id=event_id,
        created_count=created_count,
        skipped_count=skipped_count,
        delivery_effect_count=delivery_effect_count,
        envelope_ids=envelope_ids,
    )
