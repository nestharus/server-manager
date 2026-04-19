from __future__ import annotations

from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def fetch_latest_version(
    connection: Connection[Any],
    policy_type: str,
    scope_kind: str,
    scope_id: str | None,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT id, policy_type, scope_kind, scope_id,
                   version_number, content, effective_at
            FROM policy_versions
            WHERE policy_type = %s
              AND scope_kind = %s
              AND scope_id IS NOT DISTINCT FROM %s
            ORDER BY version_number DESC, effective_at DESC, id DESC
            LIMIT 1
            """,
            (policy_type, scope_kind, scope_id),
        ).fetchone()


def insert_policy_version(
    connection: Connection[Any],
    *,
    row: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO policy_versions (
            id,
            policy_type,
            scope_kind,
            scope_id,
            version_number,
            content,
            effective_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            row["id"],
            row["policy_type"],
            row["scope_kind"],
            row["scope_id"],
            row["version_number"],
            Jsonb(row["content"]),
            row["effective_at"],
        ),
    )
