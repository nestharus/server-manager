from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row


def insert_chapter_role(
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


def fetch_chapter_role(
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

