from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.repositories.db import PostgresDatabase


_ROSTER_ENTRY_SELECT = """
    SELECT r.id,
           r.chapter_id,
           r.member_id,
           r.role_id,
           r.status,
           r.removal_metadata,
           r.created_at,
           r.updated_at,
           h.current_seq AS version
    FROM roster_entries AS r
    JOIN aggregate_heads AS h
      ON h.aggregate_type = 'roster_entry'
     AND h.aggregate_id = r.id::text
"""


class RosterRepository:
    def __init__(self, db: PostgresDatabase) -> None:
        self.db = db

    def _public_insert_roster_entry(self, *, row: dict[str, Any]) -> None:
        with self.db.connection() as connection:
            self._insert_roster_entry_on(connection, row=row)

    def _insert_roster_entry_on(
        self,
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
                status,
                removal_metadata
            )
            VALUES (%s, %s, %s, %s, 'active', %s)
            """,
            (
                row["id"],
                row["chapter_id"],
                row["member_id"],
                row["role_id"],
                Jsonb(row.get("removal_metadata", {})),
            ),
        )

    def _public_fetch_roster_entry(self, entry_id: UUID) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._fetch_roster_entry_on(connection, entry_id)

    def _fetch_roster_entry_on(
        self,
        connection: Connection[Any],
        entry_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _ROSTER_ENTRY_SELECT + " WHERE r.id = %s",
                (entry_id,),
            ).fetchone()

    def fetch_roster_entry_for_update(
        self,
        entry_id: UUID,
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._fetch_roster_entry_for_update_on(connection, entry_id)

    def _fetch_roster_entry_for_update_on(
        self,
        connection: Connection[Any],
        entry_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                _ROSTER_ENTRY_SELECT + " WHERE r.id = %s FOR UPDATE OF r",
                (entry_id,),
            ).fetchone()

    def fetch_chapter_role_for_update_or_validate(
        self,
        *,
        role_id: UUID,
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._fetch_chapter_role_for_update_or_validate_on(
                connection,
                role_id=role_id,
            )

    def _fetch_chapter_role_for_update_or_validate_on(
        self,
        connection: Connection[Any],
        *,
        role_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                """
                SELECT id, chapter_id, name, ordinal, triggers_succession, created_at
                FROM chapter_roles
                WHERE id = %s
                FOR UPDATE
                """,
                (role_id,),
            ).fetchone()

    def insert_roster_transition(self, *, row: dict[str, Any]) -> None:
        with self.db.connection() as connection:
            self._insert_roster_transition_on(connection, row=row)

    def _insert_roster_transition_on(
        self,
        connection: Connection[Any],
        *,
        row: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO roster_transitions (
                id,
                roster_entry_id,
                chapter_id,
                aggregate_seq,
                from_status,
                to_status,
                from_role_id,
                to_role_id,
                actor_kind,
                actor_id,
                originating_actor_kind,
                originating_actor_id,
                reason,
                removal_metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                row["id"],
                row["roster_entry_id"],
                row["chapter_id"],
                row["aggregate_seq"],
                row["from_status"],
                row["to_status"],
                row["from_role_id"],
                row["to_role_id"],
                row["actor_kind"],
                row["actor_id"],
                row["originating_actor_kind"],
                row["originating_actor_id"],
                row["reason"],
                Jsonb(row["removal_metadata"]),
            ),
        )

    def update_roster_entry(
        self,
        *,
        entry_id: UUID,
        status: str,
        role_id: UUID,
        removal_metadata: dict[str, Any],
    ) -> None:
        with self.db.connection() as connection:
            self._update_roster_entry_on(
                connection,
                entry_id=entry_id,
                status=status,
                role_id=role_id,
                removal_metadata=removal_metadata,
            )

    def _update_roster_entry_on(
        self,
        connection: Connection[Any],
        *,
        entry_id: UUID,
        status: str,
        role_id: UUID,
        removal_metadata: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            UPDATE roster_entries
            SET status = %s,
                role_id = %s,
                removal_metadata = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (status, role_id, Jsonb(removal_metadata), entry_id),
        )

    def touch_roster_entry(self, *, entry_id: UUID) -> None:
        with self.db.connection() as connection:
            self._touch_roster_entry_on(connection, entry_id=entry_id)

    def _touch_roster_entry_on(
        self,
        connection: Connection[Any],
        *,
        entry_id: UUID,
    ) -> None:
        connection.execute(
            "UPDATE roster_entries SET updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (entry_id,),
        )

    def list_latest_role_holders(
        self,
        *,
        chapter_id: str,
        role_ids: list[UUID],
    ) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._list_latest_role_holders_on(
                connection,
                chapter_id=chapter_id,
                role_ids=role_ids,
            )

    def _list_latest_role_holders_on(
        self,
        connection: Connection[Any],
        *,
        chapter_id: str,
        role_ids: list[UUID],
    ) -> list[dict[str, Any]]:
        if not role_ids:
            return []
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                """
                SELECT DISTINCT ON (r.role_id)
                       r.role_id,
                       r.member_id,
                       r.status,
                       r.updated_at,
                       r.id
                FROM roster_entries AS r
                WHERE r.chapter_id = %s
                  AND r.role_id = ANY(%s)
                ORDER BY r.role_id ASC, r.updated_at DESC, r.id DESC
                """,
                (chapter_id, role_ids),
            ).fetchall()


RosterRepository.insert_roster_entry = RosterRepository._public_insert_roster_entry
RosterRepository.fetch_roster_entry = RosterRepository._public_fetch_roster_entry


__all__ = ["RosterRepository"]
