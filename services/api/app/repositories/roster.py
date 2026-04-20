from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row


def insert_roster_entry(
    connection: Connection[Any],
    *,
    row: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO roster_entries (
            id,
            chapter_id,
            member_id,
            role_id,
            status
        )
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            row["id"],
            row["chapter_id"],
            row["member_id"],
            row["role_id"],
            row["status"],
        ),
    )


def fetch_roster_entry(
    connection: Connection[Any],
    entry_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT id, chapter_id, member_id, role_id, status, created_at
            FROM roster_entries
            WHERE id = %s
            """,
            (entry_id,),
        ).fetchone()


def update_roster_status(
    connection: Connection[Any],
    *,
    entry_id: UUID,
    status: str,
) -> int:
    cursor = connection.execute(
        """
        UPDATE roster_entries
        SET status = %s
        WHERE id = %s
        """,
        (status, entry_id),
    )
    return cursor.rowcount

