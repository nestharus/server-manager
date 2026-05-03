from __future__ import annotations

from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from app.repositories.db import PostgresDatabase


PUBLIC_CHAPTERS_LIMIT = 200


class PublicChaptersRepository:
    def __init__(self, db: PostgresDatabase) -> None:
        self.db = db

    def list_public_active_chapters(self) -> list[dict[str, Any]]:
        with self.db.connection() as connection:
            return self._list_public_active_chapters_on(connection)

    def _list_public_active_chapters_on(
        self,
        connection: Connection[Any],
    ) -> list[dict[str, Any]]:
        with connection.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                """
                SELECT id, name
                FROM chapters
                WHERE state = 'active'
                ORDER BY name ASC
                LIMIT %s
                """,
                (PUBLIC_CHAPTERS_LIMIT,),
            ).fetchall()
        return list(rows)

    def fetch_active_public_chapter(
        self,
        chapter_id: str,
    ) -> dict[str, Any] | None:
        with self.db.connection() as connection:
            return self._fetch_active_public_chapter_on(connection, chapter_id)

    def _fetch_active_public_chapter_on(
        self,
        connection: Connection[Any],
        chapter_id: str,
    ) -> dict[str, Any] | None:
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                """
                SELECT id, name
                FROM chapters
                WHERE id = %s
                  AND state = 'active'
                """,
                (chapter_id,),
            ).fetchone()


__all__ = [
    "PUBLIC_CHAPTERS_LIMIT",
    "PublicChaptersRepository",
]
