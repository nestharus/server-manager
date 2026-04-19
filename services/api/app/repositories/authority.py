from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def insert_grant(
    connection: Connection[Any],
    *,
    grant_row: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO authority_grants (
            id,
            grantee_id,
            scope_kind,
            scope_id,
            permissions,
            expires_at,
            revoked_at,
            predecessor_grant_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            grant_row["id"],
            grant_row["grantee_id"],
            grant_row["scope_kind"],
            grant_row["scope_id"],
            Jsonb(sorted(grant_row["permissions"])),
            grant_row["expires_at"],
            grant_row["revoked_at"],
            grant_row["predecessor_grant_id"],
        ),
    )


def fetch_active_grants_for(
    connection: Connection[Any],
    *,
    grantee_id: str,
    at: datetime,
) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT id, grantee_id, scope_kind, scope_id, permissions,
                   expires_at, revoked_at, predecessor_grant_id
            FROM authority_grants
            WHERE grantee_id = %s
              AND revoked_at IS NULL
              AND (expires_at IS NULL OR expires_at > %s)
            ORDER BY created_at ASC, id ASC
            """,
            (grantee_id, at),
        ).fetchall()


def update_revoked_at(
    connection: Connection[Any],
    *,
    grant_id: UUID,
    revoked_at: datetime,
) -> int:
    cursor = connection.execute(
        """
        UPDATE authority_grants
        SET revoked_at = %s
        WHERE id = %s AND revoked_at IS NULL
        """,
        (revoked_at, grant_id),
    )
    return cursor.rowcount
