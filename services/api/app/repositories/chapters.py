from __future__ import annotations

from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


_CHAPTER_SELECT = """
    SELECT c.id, c.name, c.template_id, c.template_snapshot, c.configuration,
           c.state, c.discord_resources, c.created_at, h.current_seq AS version
    FROM chapters AS c
    JOIN aggregate_heads AS h
      ON h.aggregate_type = 'chapter'
     AND h.aggregate_id = c.id
"""


def insert_chapter(
    connection: Connection[Any],
    *,
    row: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO chapters (
            id,
            name,
            template_id,
            template_snapshot,
            configuration,
            state,
            discord_resources
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            row["id"],
            row["name"],
            row["template_id"],
            Jsonb(row["template_snapshot"]),
            Jsonb(row["configuration"]),
            row["state"],
            Jsonb(row["discord_resources"]),
        ),
    )


def fetch_chapter(
    connection: Connection[Any],
    chapter_id: str,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            _CHAPTER_SELECT + " WHERE c.id = %s",
            (chapter_id,),
        ).fetchone()


def fetch_chapter_for_update(
    connection: Connection[Any],
    chapter_id: str,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            _CHAPTER_SELECT + " WHERE c.id = %s FOR UPDATE OF c",
            (chapter_id,),
        ).fetchone()


def update_chapter_state(
    connection: Connection[Any],
    *,
    chapter_id: str,
    state: str,
) -> None:
    connection.execute(
        "UPDATE chapters SET state = %s WHERE id = %s",
        (state, chapter_id),
    )


def merge_chapter_discord_resources(
    connection: Connection[Any],
    *,
    chapter_id: str,
    resources: dict[str, Any],
) -> None:
    connection.execute(
        """
        UPDATE chapters
        SET discord_resources = %s
        WHERE id = %s
        """,
        (Jsonb(resources), chapter_id),
    )
