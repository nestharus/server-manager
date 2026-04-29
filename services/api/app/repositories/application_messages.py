from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row


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


def insert_application_message(connection: Connection[Any], *, row: dict[str, Any]) -> None:
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


def next_application_message_seq(
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


def get_application_message(
    connection: Connection[Any],
    message_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            _APPLICATION_MESSAGE_SELECT + " WHERE id = %s",
            (message_id,),
        ).fetchone()


def list_application_messages(
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
