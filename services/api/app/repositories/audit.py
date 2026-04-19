from __future__ import annotations

from typing import Any

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
