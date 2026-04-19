from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection

from app.contracts.notifications import NotificationEventDraft, NotificationEventRead
from app.core.context import MissingCorrelationContextError, get_current_audit_context
from app.repositories.db import PostgresDatabase
from app.repositories.notification_events import insert_notification_event, list_for_correlation


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
    connection: Connection[Any],
    draft: NotificationEventDraft,
    *,
    payload_allowlist: frozenset[str] | None = None,
) -> UUID:
    ctx = get_current_audit_context()
    if ctx is None:
        raise MissingCorrelationContextError()

    return insert_notification_event(
        connection,
        correlation_id=ctx.correlation_id,
        causation_id=ctx.causation_id,
        draft=draft,
        payload_json=_redact_payload(draft.payload_json, payload_allowlist),
    )


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
