from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contracts.scheduler import ScheduledJobCreate
from app.repositories._claim import claim_due_rows

ERROR_MESSAGE_LIMIT = 500


def _error_payload(error: Exception | str) -> Jsonb:
    if isinstance(error, Exception):
        payload = {
            "error_type": error.__class__.__name__,
            "message": str(error)[:ERROR_MESSAGE_LIMIT],
        }
    else:
        payload = {"reason": error}
    return Jsonb(payload)


def register_scheduled_job(
    connection: Connection[Any],
    *,
    job: ScheduledJobCreate,
    correlation_id: Any,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    with connection.cursor(row_factory=dict_row) as cursor:
        row = cursor.execute(
            """
            INSERT INTO scheduled_jobs (
                job_key,
                subsystem,
                handler_name,
                next_run_at,
                status,
                claimed_by,
                claimed_at,
                lease_until,
                attempts,
                max_attempts,
                last_error_json,
                correlation_id,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, 'queued', NULL, NULL, NULL, 0, %s, NULL, %s, %s, %s)
            ON CONFLICT (job_key) DO NOTHING
            RETURNING job_key, subsystem, handler_name, next_run_at, status,
                      claimed_by, claimed_at, lease_until, attempts, max_attempts,
                      last_error_json, correlation_id, created_at, updated_at
            """,
            (
                job.job_key,
                job.subsystem,
                job.handler_name,
                job.next_run_at,
                job.max_attempts,
                correlation_id,
                now,
                now,
            ),
        ).fetchone()
        if row is not None:
            return row
        existing = cursor.execute(
            """
            SELECT job_key, subsystem, handler_name, next_run_at, status,
                   claimed_by, claimed_at, lease_until, attempts, max_attempts,
                   last_error_json, correlation_id, created_at, updated_at
            FROM scheduled_jobs
            WHERE job_key = %s
            """,
            (job.job_key,),
        ).fetchone()
    if existing is None:
        raise RuntimeError(f"failed to load scheduled job {job.job_key}")
    return existing


def fetch_scheduled_job(
    connection: Connection[Any],
    job_key: str,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT job_key, subsystem, handler_name, next_run_at, status,
                   claimed_by, claimed_at, lease_until, attempts, max_attempts,
                   last_error_json, correlation_id, created_at, updated_at
            FROM scheduled_jobs
            WHERE job_key = %s
            """,
            (job_key,),
        ).fetchone()


def claim_due_scheduled_jobs(
    connection: Connection[Any],
    *,
    worker_id: str,
    now: datetime,
    batch_size: int,
    lease_seconds: int,
) -> list[dict[str, Any]]:
    return claim_due_rows(
        connection,
        table="scheduled_jobs",
        primary_key="job_key",
        worker_id=worker_id,
        batch_size=batch_size,
        now=now,
        lease_seconds=lease_seconds,
        ready_predicate=(
            "next_run_at <= %s "
            "AND (status = 'queued' OR (status = 'claimed' AND lease_until < %s))"
        ),
        predicate_params=(now, now),
        order_by="next_run_at ASC, job_key ASC",
    )


def mark_scheduled_job_completed(
    connection: Connection[Any],
    *,
    job_key: str,
    worker_id: str,
) -> None:
    now = datetime.now(UTC)
    connection.execute(
        """
        UPDATE scheduled_jobs
        SET status = 'completed',
            claimed_by = NULL,
            claimed_at = NULL,
            lease_until = NULL,
            updated_at = %s
        WHERE job_key = %s
          AND claimed_by = %s
        """,
        (now, job_key, worker_id),
    )


def mark_scheduled_job_failed(
    connection: Connection[Any],
    *,
    job_key: str,
    worker_id: str,
    error: Exception,
) -> dict[str, Any] | None:
    now = datetime.now(UTC)
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            UPDATE scheduled_jobs
            SET attempts = attempts + 1,
                last_error_json = %s,
                status = CASE
                    WHEN attempts + 1 >= max_attempts THEN 'failed'
                    ELSE 'queued'
                END,
                claimed_by = NULL,
                claimed_at = NULL,
                lease_until = NULL,
                updated_at = %s
            WHERE job_key = %s
              AND claimed_by = %s
            RETURNING job_key, subsystem, handler_name, next_run_at, status,
                      claimed_by, claimed_at, lease_until, attempts, max_attempts,
                      last_error_json, correlation_id, created_at, updated_at
            """,
            (_error_payload(error), now, job_key, worker_id),
        ).fetchone()


def mark_scheduled_job_abandoned(
    connection: Connection[Any],
    *,
    job_key: str,
    reason: str,
) -> None:
    now = datetime.now(UTC)
    connection.execute(
        """
        UPDATE scheduled_jobs
        SET status = 'abandoned',
            claimed_by = NULL,
            claimed_at = NULL,
            lease_until = NULL,
            last_error_json = COALESCE(last_error_json, '{}'::jsonb) || %s,
            updated_at = %s
        WHERE job_key = %s
        """,
        (_error_payload(reason), now, job_key),
    )


def extend_job_lease(
    connection: Connection[Any],
    *,
    job_key: str,
    extra_seconds: int,
) -> None:
    now = datetime.now(UTC)
    floor = now + timedelta(seconds=extra_seconds)
    connection.execute(
        """
        UPDATE scheduled_jobs
        SET lease_until = GREATEST(COALESCE(lease_until, %s), %s),
            updated_at = %s
        WHERE job_key = %s
          AND status = 'claimed'
        """,
        (floor, floor, now, job_key),
    )
