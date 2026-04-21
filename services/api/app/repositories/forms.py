from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


_FORM_SELECT = """
    SELECT f.id,
           f.scope_kind,
           f.scope_id,
           f.version,
           f.name,
           f.target_type,
           f.fields,
           f.routing_rules,
           f.status,
           f.published_by_kind,
           f.published_by_id,
           f.published_at,
           f.archived_at,
           f.created_at,
           h.current_seq AS aggregate_version
    FROM form_definitions AS f
    JOIN aggregate_heads AS h
      ON h.aggregate_type = 'application_form'
     AND h.aggregate_id = 'application_form|' || f.scope_kind || '|' || COALESCE(f.scope_id, '')
"""


def insert_form(connection: Connection[Any], *, row: dict[str, Any]) -> dict[str, Any]:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            INSERT INTO form_definitions (
                id,
                scope_kind,
                scope_id,
                version,
                name,
                target_type,
                fields,
                routing_rules,
                status,
                published_by_kind,
                published_by_id,
                published_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                row["id"],
                row["scope_kind"],
                row.get("scope_id"),
                row["version"],
                row["name"],
                row["target_type"],
                Jsonb(row["fields"]),
                Jsonb(row["routing_rules"]),
                row["status"],
                row["published_by_kind"],
                row["published_by_id"],
                row["published_at"],
            ),
        ).fetchone()


def archive_current_form_for_scope(
    connection: Connection[Any],
    *,
    scope_kind: str,
    scope_id: str | None,
    archived_at: Any,
) -> None:
    connection.execute(
        """
        UPDATE form_definitions
        SET status = 'archived',
            archived_at = %s
        WHERE scope_kind = %s
          AND scope_id IS NOT DISTINCT FROM %s
          AND status = 'current'
        """,
        (archived_at, scope_kind, scope_id),
    )


def get_current_form_for_scope(
    connection: Connection[Any],
    *,
    scope_kind: str,
    scope_id: str | None,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            _FORM_SELECT
            + """
            WHERE f.scope_kind = %s
              AND f.scope_id IS NOT DISTINCT FROM %s
              AND f.status = 'current'
            """,
            (scope_kind, scope_id),
        ).fetchone()


def get_current_form_for_scope_for_update(
    connection: Connection[Any],
    *,
    scope_kind: str,
    scope_id: str | None,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            _FORM_SELECT
            + """
            WHERE f.scope_kind = %s
              AND f.scope_id IS NOT DISTINCT FROM %s
              AND f.status = 'current'
            FOR UPDATE OF f
            """,
            (scope_kind, scope_id),
        ).fetchone()


def list_form_versions(
    connection: Connection[Any],
    *,
    scope_kind: str,
    scope_id: str | None,
) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        return list(
            cursor.execute(
                _FORM_SELECT
                + """
                WHERE f.scope_kind = %s
                  AND f.scope_id IS NOT DISTINCT FROM %s
                ORDER BY f.version ASC
                """,
                (scope_kind, scope_id),
            ).fetchall()
        )


def get_form_by_id(
    connection: Connection[Any],
    *,
    form_definition_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            _FORM_SELECT + " WHERE f.id = %s",
            (form_definition_id,),
        ).fetchone()
