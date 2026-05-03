from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contracts.notifications import NotificationEventDraft
from app.repositories.db import PostgresDatabase


class NotificationEventsRepository:
    def __init__(self, db: PostgresDatabase) -> None:
        self.db = db

    def insert_notification_event(
        self,
        *,
        correlation_id: UUID,
        causation_id: UUID | None,
        draft: NotificationEventDraft,
        payload_json: dict[str, Any],
    ) -> tuple[UUID, datetime]:
        with self.db.connection() as connection:
            return self._insert_notification_event_on(
                connection,
                correlation_id=correlation_id,
                causation_id=causation_id,
                draft=draft,
                payload_json=payload_json,
            )

    def fetch_notification_event(self, event_id: UUID) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._fetch_notification_event_on(connection, event_id)

    def list_for_correlation(self, correlation_id: UUID) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._list_for_correlation_on(connection, correlation_id)

    def _insert_notification_event_on(
        self,
        connection: Connection[Any],
        *,
        correlation_id: UUID,
        causation_id: UUID | None,
        draft: NotificationEventDraft,
        payload_json: dict[str, Any],
    ) -> tuple[UUID, datetime]:
        event_id = uuid4()
        row = connection.execute(
            """
            INSERT INTO notification_events (
                id,
                event_type,
                correlation_id,
                causation_id,
                scope_kind,
                scope_id,
                payload_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
            """,
            (
                event_id,
                draft.event_type,
                correlation_id,
                causation_id,
                draft.scope_kind,
                draft.scope_id,
                Jsonb(payload_json),
            ),
        ).fetchone()
        if row is None:
            raise RuntimeError("failed to insert notification event")
        return UUID(str(row[0])), row[1]

    def _fetch_notification_event_on(
        self,
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

    def _list_for_correlation_on(
        self,
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


__all__ = ["NotificationEventsRepository"]
