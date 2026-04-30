from __future__ import annotations

from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row


def list_public_active_chapters(connection: Connection[Any]) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        rows = cursor.execute(
            """
            SELECT id, name
            FROM chapters
            WHERE state = 'active'
            ORDER BY name ASC
            LIMIT 200
            """
        ).fetchall()
    return list(rows)


def fetch_active_public_chapter(
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


__all__ = ["fetch_active_public_chapter", "list_public_active_chapters"]
