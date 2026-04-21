from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from psycopg import Connection

from app.contracts.actor import ActorIdentity
from app.contracts.notifications import NotificationEventDraft, NotificationEventRead
from app.contracts.scheduler import DeferredEffectCreate
from app.core.context import MissingCorrelationContextError, get_current_audit_context
from app.repositories.db import PostgresDatabase
from app.repositories.deferred_effects import enqueue_effect
from app.repositories.notification_events import insert_notification_event, list_for_correlation
from app.services.scheduler import DEFAULT_MAX_ATTEMPTS


def _redact_payload(
    payload_json: dict[str, Any],
    payload_allowlist: frozenset[str] | None,
) -> dict[str, Any]:
    if payload_allowlist is None:
        return {}
    return {
        key: value
        for key, value in payload_json.items()
        if key in payload_allowlist
    }


def emit(
    db: PostgresDatabase | None,
    *,
    event: NotificationEventDraft,
    actor: ActorIdentity,  # noqa: ARG001 - reserved for worker-attribution parity
    connection: Connection[Any] | None = None,
    payload_allowlist: frozenset[str] | None = None,
) -> NotificationEventRead:
    ctx = get_current_audit_context()
    if ctx is None:
        raise MissingCorrelationContextError()

    redacted_payload = _redact_payload(event.payload_json, payload_allowlist)

    def _emit(active_connection: Connection[Any]) -> NotificationEventRead:
        event_id = insert_notification_event(
            active_connection,
            correlation_id=ctx.correlation_id,
            causation_id=ctx.causation_id,
            draft=event,
            payload_json=redacted_payload,
        )
        enqueue_effect(
            active_connection,
            effect=DeferredEffectCreate(
                subsystem="notifications",
                effect_type="notifications_materialize",
                idempotency_key=f"notifications:materialize:{event_id}",
                payload_json={"event_id": str(event_id)},
                consequence_level="safe",
                correlation_id=ctx.correlation_id,
            ),
            correlation_id=ctx.correlation_id,
            max_attempts=DEFAULT_MAX_ATTEMPTS,
        )
        return NotificationEventRead(
            id=event_id,
            event_type=event.event_type,
            correlation_id=ctx.correlation_id,
            causation_id=ctx.causation_id,
            scope_kind=event.scope_kind,
            scope_id=event.scope_id,
            payload=redacted_payload,
            created_at=datetime.now(UTC),
        )

    if connection is not None:
        return _emit(connection)
    if db is None:
        raise ValueError("db is required when connection is not supplied")
    with db.transaction() as active_connection:
        return _emit(active_connection)


def replay(db: PostgresDatabase, correlation_id: UUID) -> list[NotificationEventRead]:
    with db.connection() as connection:
        rows = list_for_correlation(connection, correlation_id)
    return [
        NotificationEventRead(
            id=row["id"],
            event_type=row["event_type"],
            correlation_id=row["correlation_id"],
            causation_id=row["causation_id"],
            scope_kind=row["scope_kind"],
            scope_id=row["scope_id"],
            payload=row["payload_json"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
