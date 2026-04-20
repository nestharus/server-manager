from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def insert_chapter_template(
    connection: Connection[Any],
    *,
    row: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO chapter_templates (
            id,
            name,
            schema_version,
            channel_structure,
            role_structure,
            default_permission_intents
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            row["id"],
            row["name"],
            row["schema_version"],
            Jsonb(row["channel_structure"]),
            Jsonb(row["role_structure"]),
            Jsonb(row["default_permission_intents"]),
        ),
    )


def fetch_chapter_template(
    connection: Connection[Any],
    template_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT id, name, schema_version, channel_structure,
                   role_structure, default_permission_intents, created_at
            FROM chapter_templates
            WHERE id = %s
            """,
            (template_id,),
        ).fetchone()

