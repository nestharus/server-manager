from __future__ import annotations

from datetime import datetime
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from app.contracts.mutations import StaleMutationError
from app.contracts.read_models import ReadModelCursorRead


def load_cursor(
    connection: Connection[Any],
    *,
    projection_name: str,
    for_update: bool = False,
) -> ReadModelCursorRead | None:
    query = """
        SELECT projection_name,
               last_processed_id,
               last_processed_at,
               version
        FROM read_model_cursors
        WHERE projection_name = %s
    """
    if for_update:
        query += " FOR UPDATE"
    with connection.cursor(row_factory=dict_row) as cursor:
        row = cursor.execute(query, (projection_name,)).fetchone()
    if row is None:
        return None
    return ReadModelCursorRead(
        projection_name=row["projection_name"],
        last_processed_id=int(row["last_processed_id"]),
        last_processed_at=row["last_processed_at"],
        version=int(row["version"]),
    )


def advance_cursor(
    connection: Connection[Any],
    *,
    projection_name: str,
    last_processed_id: int,
    last_processed_at: datetime,
    expected_version: int,
) -> dict[str, Any]:
    with connection.cursor(row_factory=dict_row) as cursor:
        row = cursor.execute(
            """
            UPDATE read_model_cursors
            SET last_processed_id = %s,
                last_processed_at = %s,
                version = version + 1
            WHERE projection_name = %s
              AND version = %s
            RETURNING projection_name,
                      last_processed_id,
                      last_processed_at,
                      version
            """,
            (
                last_processed_id,
                last_processed_at,
                projection_name,
                expected_version,
            ),
        ).fetchone()
        if row is not None:
            return row

        current = cursor.execute(
            """
            SELECT version
            FROM read_model_cursors
            WHERE projection_name = %s
            """,
            (projection_name,),
        ).fetchone()

    if current is None:
        raise RuntimeError(
            f"read_model_cursors missing row for projection {projection_name!r}"
        )

    raise StaleMutationError(
        aggregate_type="read_model_cursor",
        aggregate_id=projection_name,
        expected_version=expected_version,
        current_version=int(current["version"]),
    )


def max_event_id_settled(
    connection: Connection[Any],
    *,
    min_age_seconds: int,
) -> int:
    with connection.cursor() as cursor:
        row = cursor.execute(
            """
            SELECT COALESCE(MAX(id), 0)
            FROM activity_state_changes
            WHERE recorded_at <= CURRENT_TIMESTAMP - make_interval(secs => %s)
            """,
            (min_age_seconds,),
        ).fetchone()
    assert row is not None
    return int(row[0])


def count_open_applications(
    connection: Connection[Any],
    *,
    states: frozenset[str],
    scope_kind: str,
    scope_id: str | None,
) -> int:
    query = """
        SELECT COUNT(*)::int
        FROM applications
        WHERE state = ANY(%s)
    """
    params: list[Any] = [list(states)]
    if scope_kind == "chapter":
        query += " AND target_scope_kind = 'chapter' AND target_scope_id = %s"
        params.append(scope_id)
    with connection.cursor() as cursor:
        row = cursor.execute(query, params).fetchone()
    assert row is not None
    return int(row[0])


def count_open_tickets(
    connection: Connection[Any],
    *,
    scope_kind: str,
    scope_id: str | None,
) -> int:
    query = """
        SELECT COUNT(*)::int
        FROM tickets
        WHERE terminal_at IS NULL
    """
    params: list[Any] = []
    if scope_kind == "chapter":
        query += """
            AND category_snapshot #>> '{routing_scope,scope_kind}' = 'chapter'
            AND category_snapshot #>> '{routing_scope,scope_id}' = %s
        """
        params.append(scope_id)
    with connection.cursor() as cursor:
        row = cursor.execute(query, params).fetchone()
    assert row is not None
    return int(row[0])


def count_pending_deferred_effects(
    connection: Connection[Any],
    *,
    statuses: frozenset[str],
) -> int:
    with connection.cursor() as cursor:
        row = cursor.execute(
            """
            SELECT COUNT(*)::int
            FROM deferred_effects
            WHERE status = ANY(%s)
            """,
            (list(statuses),),
        ).fetchone()
    assert row is not None
    return int(row[0])


def count_active_drift(
    connection: Connection[Any],
    *,
    statuses: frozenset[str],
    scope_kind: str,
    scope_id: str | None,
) -> int:
    query = """
        SELECT COUNT(*)::int
        FROM permission_drift
        WHERE status = ANY(%s)
    """
    params: list[Any] = [list(statuses)]
    if scope_kind == "chapter":
        query += " AND scope_kind = 'chapter' AND scope_id = %s"
        params.append(scope_id)
    with connection.cursor() as cursor:
        row = cursor.execute(query, params).fetchone()
    assert row is not None
    return int(row[0])


__all__ = [
    "advance_cursor",
    "count_active_drift",
    "count_open_applications",
    "count_open_tickets",
    "count_pending_deferred_effects",
    "load_cursor",
    "max_event_id_settled",
]
