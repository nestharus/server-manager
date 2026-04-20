from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row


def fetch_audit_entry(
    connection: Connection[Any],
    audit_entry_id: int,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT
                id,
                recorded_at,
                actor_kind,
                actor_id,
                action_type,
                aggregate_type,
                aggregate_id,
                status,
                correlation_id,
                causation_id,
                scope_kind,
                scope_id,
                request_surface,
                reason_text
            FROM activity_actions
            WHERE id = %s
            """,
            (audit_entry_id,),
        ).fetchone()


def list_audit_entries_by_correlation(
    connection: Connection[Any],
    *,
    correlation_id: UUID,
    limit: int,
) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        rows = cursor.execute(
            """
            SELECT
                id,
                recorded_at,
                actor_kind,
                actor_id,
                action_type,
                aggregate_type,
                aggregate_id,
                status,
                correlation_id,
                causation_id,
                scope_kind,
                scope_id,
                request_surface,
                reason_text
            FROM activity_actions
            WHERE correlation_id = %s
            ORDER BY recorded_at ASC, id ASC
            LIMIT %s
            """,
            (correlation_id, limit),
        ).fetchall()
    return list(rows)


def list_audit_entry_chain(
    connection: Connection[Any],
    *,
    entry_id: int,
    limit: int,
) -> list[dict[str, Any]]:
    row = fetch_audit_entry(connection, entry_id)
    if row is None:
        return []
    return list_audit_entries_by_correlation(
        connection,
        correlation_id=row["correlation_id"],
        limit=limit,
    )
