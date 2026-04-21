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
            template_family_id,
            version,
            name,
            schema_version,
            channel_structure,
            role_structure,
            default_permission_intents
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            row["id"],
            row["template_family_id"],
            row["version"],
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
            SELECT id, template_family_id, version, name, schema_version, channel_structure,
                   role_structure, default_permission_intents, created_at
            FROM chapter_templates
            WHERE id = %s
            """,
            (template_id,),
        ).fetchone()


def fetch_chapter_template_for_update(
    connection: Connection[Any],
    template_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT id, template_family_id, version, name, schema_version,
                   channel_structure, role_structure,
                   default_permission_intents, created_at
            FROM chapter_templates
            WHERE id = %s
            FOR UPDATE
            """,
            (template_id,),
        ).fetchone()


def fetch_current_template_family_version_for_update(
    connection: Connection[Any],
    template_family_id: UUID,
) -> int | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT id
            FROM chapter_templates
            WHERE template_family_id = %s
            FOR UPDATE
            """,
            (template_family_id,),
        ).fetchall()
        row = cursor.execute(
            """
            SELECT MAX(version) AS current_version
            FROM chapter_templates
            WHERE template_family_id = %s
            """,
            (template_family_id,),
        ).fetchone()
    if row is None or row["current_version"] is None:
        return None
    return int(row["current_version"])


def fetch_latest_template_family_version_for_update(
    connection: Connection[Any],
    template_family_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT id, template_family_id, version, name, schema_version,
                   channel_structure, role_structure,
                   default_permission_intents, created_at
            FROM chapter_templates
            WHERE template_family_id = %s
            ORDER BY version DESC
            LIMIT 1
            FOR UPDATE
            """,
            (template_family_id,),
        ).fetchone()


def insert_template_version(
    connection: Connection[Any],
    *,
    row: dict[str, Any],
) -> None:
    insert_chapter_template(connection, row=row)
