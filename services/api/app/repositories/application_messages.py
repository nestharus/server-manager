from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row

from app.repositories.db import PostgresDatabase


_APPLICATION_MESSAGE_SELECT = """
    SELECT id,
           application_id,
           message_seq,
           author_actor_kind,
           author_actor_id,
           visibility,
           body_markdown,
           client_message_id,
           correlation_id,
           causation_id,
           created_at
    FROM application_messages
"""


class ApplicationMessagesRepository:
    def __init__(self, db: PostgresDatabase) -> None:
        self.db = db

    def insert_application_message(self, *, row: dict[str, Any]) -> None:
        with self.db.connection() as connection:
            self._insert_application_message_on(connection, row=row)

    def _insert_application_message_on(
        self,
        connection: Connection[Any],
        *,
        row: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO application_messages (
                id,
                application_id,
                message_seq,
                author_actor_kind,
                author_actor_id,
                visibility,
                body_markdown,
                client_message_id,
                correlation_id,
                causation_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                row["id"],
                row["application_id"],
                row["message_seq"],
                row["author_actor_kind"],
                row["author_actor_id"],
                row["visibility"],
                row["body_markdown"],
                row.get("client_message_id"),
                row["correlation_id"],
                row.get("causation_id"),
            ),
        )

    def next_application_message_seq(self, *, application_id: UUID) -> int:
        with self.db.connection() as connection:
            return self._next_application_message_seq_on(
                connection,
                application_id=application_id,
            )

    def _next_application_message_seq_on(
        self,
        connection: Connection[Any],
        *,
        application_id: UUID,
    ) -> int:
        row = connection.execute(
            """
            SELECT COALESCE(MAX(message_seq), 0) + 1
            FROM application_messages
            WHERE application_id = %s
            """,
            (application_id,),
        ).fetchone()
        if row is None:
            return 1
        return int(row[0])

    def find_application_message_by_client_message_id(
        self,
        *,
        application_id: UUID,
        client_message_id: str,
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._find_application_message_by_client_message_id_on(
                connection,
                application_id=application_id,
                client_message_id=client_message_id,
            )

    def _find_application_message_by_client_message_id_on(
        self,
        connection: Connection[Any],
        *,
        application_id: UUID,
        client_message_id: str,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _APPLICATION_MESSAGE_SELECT
                + " WHERE application_id = %s AND client_message_id = %s",
                (application_id, client_message_id),
            ).fetchone()

    def get_application_message(self, message_id: UUID) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._get_application_message_on(connection, message_id)

    def _get_application_message_on(
        self,
        connection: Connection[Any],
        message_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _APPLICATION_MESSAGE_SELECT + " WHERE id = %s",
                (message_id,),
            ).fetchone()

    def list_application_messages(
        self,
        *,
        application_id: UUID,
    ) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._list_application_messages_on(
                connection,
                application_id=application_id,
            )

    def _list_application_messages_on(
        self,
        connection: Connection[Any],
        *,
        application_id: UUID,
    ) -> list[dict[str, Any]]:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _APPLICATION_MESSAGE_SELECT
                + " WHERE application_id = %s ORDER BY message_seq ASC",
                (application_id,),
            ).fetchall()
