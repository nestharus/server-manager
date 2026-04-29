from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row


_MEMBER_SELECT = """
    SELECT m.id,
           m.discord_user_id,
           m.kind,
           m.joined_at,
           m.status,
           m.created_at,
           m.updated_at,
           h.current_seq AS version
    FROM members AS m
    JOIN aggregate_heads AS h
      ON h.aggregate_type = 'member'
     AND h.aggregate_id = m.id::text
"""


def fetch_member_by_id(
    connection: Connection[Any],
    member_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            _MEMBER_SELECT + " WHERE m.id = %s",
            (member_id,),
        ).fetchone()


def fetch_member_by_discord_id(
    connection: Connection[Any],
    discord_user_id: str,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            _MEMBER_SELECT + " WHERE m.discord_user_id = %s",
            (discord_user_id,),
        ).fetchone()


def _fetch_member_by_id_for_update(
    connection: Connection[Any],
    member_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            _MEMBER_SELECT + " WHERE m.id = %s FOR UPDATE OF m",
            (member_id,),
        ).fetchone()


def _insert_member(
    connection: Connection[Any],
    *,
    row: dict[str, Any],
    _kind: str = "discord",
) -> None:
    connection.execute(
        """
        INSERT INTO members (
            id,
            discord_user_id,
            kind,
            joined_at,
            status
        )
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            row["id"],
            row["discord_user_id"],
            _kind,
            row["joined_at"],
            row["status"],
        ),
    )


def _update_member_status(
    connection: Connection[Any],
    *,
    member_id: UUID,
    status: str,
) -> None:
    connection.execute(
        """
        UPDATE members
        SET status = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (status, member_id),
    )


__all__ = [
    "_fetch_member_by_id_for_update",
    "_insert_member",
    "_update_member_status",
    "fetch_member_by_discord_id",
    "fetch_member_by_id",
]
