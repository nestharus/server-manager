from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row


@dataclass(frozen=True)
class CountAndSamples:
    count: int
    sample_ids: list[str]

    @property
    def has_more(self) -> bool:
        return len(self.sample_ids) < self.count


def _count_and_samples(
    connection: Connection[Any],
    *,
    count_sql: str,
    sample_sql: str,
    params: tuple[Any, ...],
    sample_limit: int,
) -> CountAndSamples:
    with connection.cursor(row_factory=dict_row) as cursor:
        count_row = cursor.execute(count_sql, params).fetchone()
        sample_rows = cursor.execute(sample_sql, (*params, sample_limit)).fetchall()
    return CountAndSamples(
        count=0 if count_row is None else int(count_row["count"]),
        sample_ids=[str(row["id"]) for row in sample_rows],
    )


def list_pending_applications_for_chapter(
    connection: Connection[Any],
    *,
    chapter_id: str,
    sample_limit: int,
) -> CountAndSamples:
    predicate = """
        FROM applications
        WHERE state IN ('submitted','queued','claimed','in_review')
          AND target_scope_kind = 'chapter'
          AND target_scope_id = %s
    """
    return _count_and_samples(
        connection,
        count_sql="SELECT COUNT(*)::int AS count " + predicate,
        sample_sql="SELECT id " + predicate + " ORDER BY created_at ASC, id ASC LIMIT %s",
        params=(chapter_id,),
        sample_limit=sample_limit,
    )


def list_open_tickets_for_chapter(
    connection: Connection[Any],
    *,
    chapter_id: str,
    sample_limit: int,
) -> CountAndSamples:
    predicate = """
        FROM tickets
        WHERE terminal_at IS NULL
          AND category_snapshot #>> '{routing_scope,scope_kind}' = 'chapter'
          AND category_snapshot #>> '{routing_scope,scope_id}' = %s
    """
    return _count_and_samples(
        connection,
        count_sql="SELECT COUNT(*)::int AS count " + predicate,
        sample_sql="SELECT id " + predicate + " ORDER BY created_at ASC, id ASC LIMIT %s",
        params=(chapter_id,),
        sample_limit=sample_limit,
    )


def list_active_authority_grants_for_chapter(
    connection: Connection[Any],
    *,
    chapter_id: str,
    sample_limit: int,
) -> CountAndSamples:
    predicate = """
        FROM authority_grants
        WHERE scope_kind = 'chapter'
          AND scope_id = %s
          AND revoked_at IS NULL
          AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
    """
    return _count_and_samples(
        connection,
        count_sql="SELECT COUNT(*)::int AS count " + predicate,
        sample_sql="SELECT id " + predicate + " ORDER BY created_at ASC, id ASC LIMIT %s",
        params=(chapter_id,),
        sample_limit=sample_limit,
    )


def list_unresolved_deferred_effects_for_chapter(
    connection: Connection[Any],
    *,
    chapter_id: str,
    sample_limit: int,
) -> CountAndSamples:
    predicate = """
        FROM deferred_effects
        WHERE status IN ('queued','claimed','failed')
          AND payload_json->>'chapter_id' = %s
    """
    return _count_and_samples(
        connection,
        count_sql="SELECT COUNT(*)::int AS count " + predicate,
        sample_sql="SELECT id " + predicate + " ORDER BY created_at ASC, id ASC LIMIT %s",
        params=(chapter_id,),
        sample_limit=sample_limit,
    )


def list_active_roster_entries_for_chapter(
    connection: Connection[Any],
    *,
    chapter_id: str,
    sample_limit: int,
) -> CountAndSamples:
    predicate = """
        FROM roster_entries
        WHERE chapter_id = %s
          AND status != 'removed'
    """
    return _count_and_samples(
        connection,
        count_sql="SELECT COUNT(*)::int AS count " + predicate,
        sample_sql="SELECT id " + predicate + " ORDER BY created_at ASC, id ASC LIMIT %s",
        params=(chapter_id,),
        sample_limit=sample_limit,
    )


def list_chapter_roles_for_plan(
    connection: Connection[Any],
    *,
    chapter_id: str,
    sample_limit: int,
) -> CountAndSamples:
    predicate = "FROM chapter_roles WHERE chapter_id = %s"
    return _count_and_samples(
        connection,
        count_sql="SELECT COUNT(*)::int AS count " + predicate,
        sample_sql="SELECT id " + predicate + " ORDER BY ordinal ASC, id ASC LIMIT %s",
        params=(chapter_id,),
        sample_limit=sample_limit,
    )


def iter_pending_applications_for_archive(
    connection: Connection[Any],
    *,
    chapter_id: str,
) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT a.id, a.state, h.current_seq AS version
            FROM applications AS a
            JOIN aggregate_heads AS h
              ON h.aggregate_type = 'application'
             AND h.aggregate_id = a.id::text
            WHERE a.state IN ('submitted','queued','claimed','in_review')
              AND a.target_scope_kind = 'chapter'
              AND a.target_scope_id = %s
            ORDER BY a.created_at ASC, a.id ASC
            """,
            (chapter_id,),
        ).fetchall()


def iter_open_tickets_for_archive(
    connection: Connection[Any],
    *,
    chapter_id: str,
) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT t.id, t.state, t.category_snapshot, h.current_seq AS version
            FROM tickets AS t
            JOIN aggregate_heads AS h
              ON h.aggregate_type = 'ticket'
             AND h.aggregate_id = t.id::text
            WHERE t.terminal_at IS NULL
              AND t.category_snapshot #>> '{routing_scope,scope_kind}' = 'chapter'
              AND t.category_snapshot #>> '{routing_scope,scope_id}' = %s
            ORDER BY t.created_at ASC, t.id ASC
            """,
            (chapter_id,),
        ).fetchall()


def iter_active_grants_for_archive(
    connection: Connection[Any],
    *,
    chapter_id: str,
) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT g.id, g.permissions, h.current_seq AS version
            FROM authority_grants AS g
            JOIN aggregate_heads AS h
              ON h.aggregate_type = 'authority_grant'
             AND h.aggregate_id = g.id::text
            WHERE g.scope_kind = 'chapter'
              AND g.scope_id = %s
              AND g.revoked_at IS NULL
              AND (g.expires_at IS NULL OR g.expires_at > CURRENT_TIMESTAMP)
            ORDER BY g.created_at ASC, g.id ASC
            """,
            (chapter_id,),
        ).fetchall()


def iter_unresolved_chapter_effects_for_archive(
    connection: Connection[Any],
    *,
    chapter_id: str,
    exclude_archive_run_id: str,
) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT id, status, precondition_state, attempts
            FROM deferred_effects
            WHERE status IN ('queued','claimed','failed')
              AND payload_json->>'chapter_id' = %s
              AND COALESCE(payload_json->>'archive_run_id', '') <> %s
            ORDER BY created_at ASC, id ASC
            """,
            (chapter_id, exclude_archive_run_id),
        ).fetchall()


__all__ = [
    "CountAndSamples",
    "iter_active_grants_for_archive",
    "iter_open_tickets_for_archive",
    "iter_pending_applications_for_archive",
    "iter_unresolved_chapter_effects_for_archive",
    "list_active_authority_grants_for_chapter",
    "list_active_roster_entries_for_chapter",
    "list_chapter_roles_for_plan",
    "list_open_tickets_for_chapter",
    "list_pending_applications_for_chapter",
    "list_unresolved_deferred_effects_for_chapter",
]
