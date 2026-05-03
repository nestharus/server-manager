from __future__ import annotations

from typing import Any

from psycopg import Connection

from app.repositories.db import PostgresDatabase


class ChapterTransitionsRepository:
    def __init__(self, db: PostgresDatabase) -> None:
        self.db = db

    def insert_chapter_transition(self, *, row: dict[str, Any]) -> None:
        with self.db.connection() as connection:
            self._insert_chapter_transition_on(connection, row=row)

    def _insert_chapter_transition_on(
        self,
        connection: Connection[Any],
        *,
        row: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO chapter_transitions (
                id,
                chapter_id,
                aggregate_seq,
                from_state,
                to_state,
                actor_kind,
                actor_id,
                originating_actor_kind,
                originating_actor_id,
                reason
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                row["id"],
                row["chapter_id"],
                row["aggregate_seq"],
                row["from_state"],
                row["to_state"],
                row["actor_kind"],
                row["actor_id"],
                row["originating_actor_kind"],
                row["originating_actor_id"],
                row["reason"],
            ),
        )


__all__ = ["ChapterTransitionsRepository"]
