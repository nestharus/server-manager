from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contracts.notifications import NotificationEventDraft


def insert_notification_event(
    connection: Connection[Any],
    *,
    correlation_id: UUID,
    causation_id: UUID | None,
    draft: NotificationEventDraft,
    payload_json: dict[str, Any],
) -> UUID:
    event_id = uuid4()
    created_at = datetime.now(UTC)
    row = connection.execute(
        """
        INSERT INTO notification_events (
            id,
            event_type,
            correlation_id,
            causation_id,
            scope_kind,
            scope_id,
            payload_json,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            event_id,
            draft.event_type,
            correlation_id,
            causation_id,
            draft.scope_kind,
            draft.scope_id,
            Jsonb(payload_json),
            created_at,
        ),
    ).fetchone()
    if row is None:
        raise RuntimeError("failed to insert notification event")
    return UUID(str(row[0]))


def fetch_notification_event(
    connection: Connection[Any],
    event_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT id, event_type, correlation_id, causation_id,
                   scope_kind, scope_id, payload_json, created_at
            FROM notification_events
            WHERE id = %s
            """,
            (event_id,),
        ).fetchone()


def list_for_correlation(
    connection: Connection[Any],
    correlation_id: UUID,
) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT id, event_type, correlation_id, causation_id,
                   scope_kind, scope_id, payload_json, created_at
            FROM notification_events
            WHERE correlation_id = %s
            ORDER BY created_at ASC, id ASC
            """,
            (correlation_id,),
        ).fetchall()
