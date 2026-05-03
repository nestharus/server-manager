from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row

from app.repositories.db import PostgresDatabase


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


class MembersRepository:
    def __init__(self, db: PostgresDatabase) -> None:
        self.db = db

    def fetch_member_by_id(self, member_id: UUID) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._fetch_member_by_id_on(connection, member_id)

    def _fetch_member_by_id_on(
        self,
        connection: Connection[Any],
        member_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _MEMBER_SELECT + " WHERE m.id = %s",
                (member_id,),
            ).fetchone()

    def fetch_member_by_discord_id(
        self,
        discord_user_id: str,
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._fetch_member_by_discord_id_on(connection, discord_user_id)

    def _fetch_member_by_discord_id_on(
        self,
        connection: Connection[Any],
        discord_user_id: str,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _MEMBER_SELECT + " WHERE m.discord_user_id = %s",
                (discord_user_id,),
            ).fetchone()

    def fetch_member_by_id_for_update(
        self,
        member_id: UUID,
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._fetch_member_by_id_for_update_on(connection, member_id)

    def _fetch_member_by_id_for_update_on(
        self,
        connection: Connection[Any],
        member_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _MEMBER_SELECT + " WHERE m.id = %s FOR UPDATE OF m",
                (member_id,),
            ).fetchone()

    def insert_member(self, *, row: dict[str, Any]) -> None:
        with self.db.connection() as connection:
            self._insert_member_on(connection, row=row)

    def _insert_member_on(
        self,
        connection: Connection[Any],
        *,
        row: dict[str, Any],
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
            VALUES (%s, %s, 'discord', %s, %s)
            """,
            (
                row["id"],
                row["discord_user_id"],
                row["joined_at"],
                row["status"],
            ),
        )

    def insert_member_on_discord_conflict_do_nothing(
        self,
        *,
        row: dict[str, Any],
    ) -> bool:
        with self.db.connection() as connection:
            return self._insert_member_on_discord_conflict_do_nothing_on(
                connection,
                row=row,
            )

    def _insert_member_on_discord_conflict_do_nothing_on(
        self,
        connection: Connection[Any],
        *,
        row: dict[str, Any],
    ) -> bool:
        inserted = connection.execute(
            """
            INSERT INTO members (
                id,
                discord_user_id,
                kind,
                joined_at,
                status
            )
            VALUES (%s, %s, 'discord', %s, %s)
            ON CONFLICT (discord_user_id) DO NOTHING
            RETURNING id
            """,
            (
                row["id"],
                row["discord_user_id"],
                row["joined_at"],
                row["status"],
            ),
        ).fetchone()
        return inserted is not None

    def update_member_status(
        self,
        *,
        member_id: UUID,
        status: str,
    ) -> None:
        with self.db.connection() as connection:
            self._update_member_status_on(
                connection,
                member_id=member_id,
                status=status,
            )

    def _update_member_status_on(
        self,
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


__all__ = ["MembersRepository"]
