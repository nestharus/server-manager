from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from psycopg import Connection, sql
from psycopg.rows import dict_row


def claim_due_rows(
    connection: Connection[Any],
    *,
    table: str,
    primary_key: str,
    worker_id: str,
    batch_size: int,
    now: datetime,
    lease_seconds: int,
    ready_predicate: str,
    predicate_params: tuple[Any, ...] = (),
    order_by: str,
) -> list[dict[str, Any]]:
    lease_until = now + timedelta(seconds=lease_seconds)
    query = sql.SQL(
        """
        WITH claimable AS (
            SELECT {primary_key}
            FROM {table}
            WHERE {ready_predicate}
            ORDER BY {order_by}
            FOR UPDATE SKIP LOCKED
            LIMIT %s
        )
        UPDATE {table} AS target
        SET status = 'claimed',
            claimed_by = %s,
            claimed_at = %s,
            lease_until = %s,
            updated_at = %s
        FROM claimable
        WHERE target.{primary_key} = claimable.{primary_key}
        RETURNING target.*
        """
    ).format(
        table=sql.Identifier(table),
        primary_key=sql.Identifier(primary_key),
        ready_predicate=sql.SQL(ready_predicate),
        order_by=sql.SQL(order_by),
    )
    params = (*predicate_params, batch_size, worker_id, now, lease_until, now)
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(query, params).fetchall()
