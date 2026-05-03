from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row

from app.repositories.db import PostgresDatabase


class ChapterRolesRepository:
    def __init__(self, db: PostgresDatabase) -> None:
        self.db = db

    def insert_chapter_role(self, *, row: dict[str, Any]) -> None:
        with self.db.connection() as connection:
            self._insert_chapter_role_on(connection, row=row)

    def _insert_chapter_role_on(
        self,
        connection: Connection[Any],
        *,
        row: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO chapter_roles (
                id,
                chapter_id,
                template_id,
                name,
                ordinal,
                triggers_succession
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                row["id"],
                row["chapter_id"],
                row.get("template_id"),
                row["name"],
                row["ordinal"],
                row["triggers_succession"],
            ),
        )

    def fetch_chapter_role(self, role_id: UUID) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._fetch_chapter_role_on(connection, role_id)

    def _fetch_chapter_role_on(
        self,
        connection: Connection[Any],
        role_id: UUID,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                """
                SELECT id, chapter_id, template_id, name, ordinal,
                       triggers_succession, created_at
                FROM chapter_roles
                WHERE id = %s
                """,
                (role_id,),
            ).fetchone()

    def list_succession_triggering_roles(
        self,
        *,
        chapter_id: str,
    ) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._list_succession_triggering_roles_on(
                connection,
                chapter_id=chapter_id,
            )

    def _list_succession_triggering_roles_on(
        self,
        connection: Connection[Any],
        *,
        chapter_id: str,
    ) -> list[dict[str, Any]]:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                """
                SELECT id, chapter_id, template_id, name, ordinal,
                       triggers_succession, created_at
                FROM chapter_roles
                WHERE chapter_id = %s
                  AND triggers_succession = TRUE
                ORDER BY ordinal ASC, id ASC
                """,
                (chapter_id,),
            ).fetchall()


__all__ = ["ChapterRolesRepository"]
