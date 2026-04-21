from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


_ARCHIVE_RUN_SELECT = """
    SELECT id,
           chapter_id,
           correlation_id,
           causation_id,
           archive_reason,
           initiated_by_kind,
           initiated_by_id,
           initiated_at,
           completed_at,
           status,
           manual_review_items
    FROM chapter_archive_runs
"""


def insert_archive_run(
    connection: Connection[Any],
    *,
    row: dict[str, Any],
) -> dict[str, Any]:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            INSERT INTO chapter_archive_runs (
                id,
                chapter_id,
                correlation_id,
                causation_id,
                archive_reason,
                initiated_by_kind,
                initiated_by_id,
                status,
                manual_review_items
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'in_progress', %s)
            RETURNING id, chapter_id, correlation_id, causation_id, archive_reason,
                      initiated_by_kind, initiated_by_id, initiated_at, completed_at,
                      status, manual_review_items
            """,
            (
                row["id"],
                row["chapter_id"],
                row["correlation_id"],
                row["causation_id"],
                row["archive_reason"],
                row["initiated_by_kind"],
                row["initiated_by_id"],
                Jsonb(row.get("manual_review_items", [])),
            ),
        ).fetchone()


def fetch_in_progress_archive_run(
    connection: Connection[Any],
    *,
    chapter_id: str,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            _ARCHIVE_RUN_SELECT
            + """
            WHERE chapter_id = %s
              AND status = 'in_progress'
            ORDER BY initiated_at DESC, id DESC
            LIMIT 1
            """,
            (chapter_id,),
        ).fetchone()


def fetch_latest_archive_run(
    connection: Connection[Any],
    *,
    chapter_id: str,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            _ARCHIVE_RUN_SELECT
            + """
            WHERE chapter_id = %s
            ORDER BY initiated_at DESC, id DESC
            LIMIT 1
            """,
            (chapter_id,),
        ).fetchone()


def list_in_progress_archive_runs(
    connection: Connection[Any],
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            _ARCHIVE_RUN_SELECT
            + """
            WHERE status = 'in_progress'
            ORDER BY initiated_at ASC, id ASC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()


def fetch_archive_run_for_update(
    connection: Connection[Any],
    *,
    archive_run_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            _ARCHIVE_RUN_SELECT + " WHERE id = %s FOR UPDATE",
            (archive_run_id,),
        ).fetchone()


def update_archive_run_manual_review_items(
    connection: Connection[Any],
    *,
    archive_run_id: UUID,
    items: list[dict[str, Any]],
) -> None:
    connection.execute(
        """
        UPDATE chapter_archive_runs
        SET manual_review_items = %s
        WHERE id = %s
          AND status = 'in_progress'
        """,
        (Jsonb(items), archive_run_id),
    )


def mark_archive_run_completed(
    connection: Connection[Any],
    *,
    archive_run_id: UUID,
) -> None:
    connection.execute(
        """
        UPDATE chapter_archive_runs
        SET status = 'completed',
            completed_at = %s
        WHERE id = %s
          AND status = 'in_progress'
        """,
        (datetime.now(UTC), archive_run_id),
    )


__all__ = [
    "fetch_archive_run_for_update",
    "fetch_in_progress_archive_run",
    "fetch_latest_archive_run",
    "insert_archive_run",
    "list_in_progress_archive_runs",
    "mark_archive_run_completed",
    "update_archive_run_manual_review_items",
]
