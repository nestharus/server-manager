from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contracts.scheduler import (
    DeferredEffectCreate,
    InvalidPreconditionStateTransitionError,
)
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


def enqueue_effect(
    connection: Connection[Any],
    *,
    effect: DeferredEffectCreate,
    correlation_id: Any,
    max_attempts: int,
) -> dict[str, Any]:
    effect_id = uuid4()
    now = datetime.now(UTC)
    with connection.cursor(row_factory=dict_row) as cursor:
        row = cursor.execute(
            """
            INSERT INTO deferred_effects (
                id,
                subsystem,
                effect_type,
                idempotency_key,
                payload_json,
                consequence_level,
                precondition_state,
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
            VALUES (
                %s, %s, %s, %s, %s, %s, 'unchecked', 'queued',
                NULL, NULL, NULL, 0, %s, NULL, %s, %s, %s
            )
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id, subsystem, effect_type, idempotency_key, payload_json,
                      consequence_level, precondition_state, status,
                      claimed_by, claimed_at, lease_until, attempts, max_attempts,
                      last_error_json, correlation_id, created_at, updated_at
            """,
            (
                effect_id,
                effect.subsystem,
                effect.effect_type,
                effect.idempotency_key,
                Jsonb(effect.payload_json),
                effect.consequence_level,
                max_attempts,
                correlation_id,
                now,
                now,
            ),
        ).fetchone()
        if row is not None:
            return row
        existing = cursor.execute(
            """
            SELECT id, subsystem, effect_type, idempotency_key, payload_json,
                   consequence_level, precondition_state, status,
                   claimed_by, claimed_at, lease_until, attempts, max_attempts,
                   last_error_json, correlation_id, created_at, updated_at
            FROM deferred_effects
            WHERE idempotency_key = %s
            """,
            (effect.idempotency_key,),
        ).fetchone()
    if existing is None:
        raise RuntimeError(
            f"failed to load deferred effect for idempotency_key={effect.idempotency_key}"
        )
    return existing


def fetch_deferred_effect(
    connection: Connection[Any],
    effect_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT id, subsystem, effect_type, idempotency_key, payload_json,
                   consequence_level, precondition_state, status,
                   claimed_by, claimed_at, lease_until, attempts, max_attempts,
                   last_error_json, correlation_id, created_at, updated_at
            FROM deferred_effects
            WHERE id = %s
            """,
            (effect_id,),
        ).fetchone()


def list_deferred_effects_by_subsystem(
    connection: Connection[Any],
    *,
    subsystem: str,
    status: str | None = None,
) -> list[dict[str, Any]]:
    query = """
        SELECT id, subsystem, effect_type, idempotency_key, payload_json,
               consequence_level, precondition_state, status,
               claimed_by, claimed_at, lease_until, attempts, max_attempts,
               last_error_json, correlation_id, created_at, updated_at
        FROM deferred_effects
        WHERE subsystem = %s
    """
    params: tuple[Any, ...]
    if status is None:
        query += " ORDER BY created_at ASC, id ASC"
        params = (subsystem,)
    else:
        query += " AND status = %s ORDER BY created_at ASC, id ASC"
        params = (subsystem, status)
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(query, params).fetchall()


def claim_due_deferred_effects(
    connection: Connection[Any],
    *,
    worker_id: str,
    now: datetime,
    batch_size: int,
    lease_seconds: int,
) -> list[dict[str, Any]]:
    return claim_due_rows(
        connection,
        table="deferred_effects",
        primary_key="id",
        worker_id=worker_id,
        batch_size=batch_size,
        now=now,
        lease_seconds=lease_seconds,
        ready_predicate=(
            "(status = 'queued' OR (status = 'claimed' AND lease_until < %s)) "
            "AND (consequence_level = 'safe' OR precondition_state = 'valid')"
        ),
        predicate_params=(now,),
        order_by="created_at ASC, id ASC",
    )


def mark_deferred_effect_completed(
    connection: Connection[Any],
    *,
    effect_id: UUID,
    worker_id: str,
) -> None:
    now = datetime.now(UTC)
    connection.execute(
        """
        UPDATE deferred_effects
        SET status = 'completed',
            claimed_by = NULL,
            claimed_at = NULL,
            lease_until = NULL,
            updated_at = %s
        WHERE id = %s
          AND claimed_by = %s
        """,
        (now, effect_id, worker_id),
    )


def mark_deferred_effect_failed(
    connection: Connection[Any],
    *,
    effect_id: UUID,
    worker_id: str,
    error: Exception,
) -> dict[str, Any] | None:
    now = datetime.now(UTC)
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            UPDATE deferred_effects
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
            WHERE id = %s
              AND claimed_by = %s
            RETURNING id, subsystem, effect_type, idempotency_key, payload_json,
                      consequence_level, precondition_state, status,
                      claimed_by, claimed_at, lease_until, attempts, max_attempts,
                      last_error_json, correlation_id, created_at, updated_at
            """,
            (_error_payload(error), now, effect_id, worker_id),
        ).fetchone()


def mark_deferred_effect_skipped(
    connection: Connection[Any],
    *,
    effect_id: UUID,
    worker_id: str,
    reason: str,
) -> None:
    now = datetime.now(UTC)
    connection.execute(
        """
        UPDATE deferred_effects
        SET status = 'skipped',
            claimed_by = NULL,
            claimed_at = NULL,
            lease_until = NULL,
            last_error_json = COALESCE(last_error_json, '{}'::jsonb) || %s,
            updated_at = %s
        WHERE id = %s
          AND claimed_by = %s
        """,
        (_error_payload(reason), now, effect_id, worker_id),
    )


def update_precondition_state(
    connection: Connection[Any],
    *,
    effect_id: UUID,
    new_state: str,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    with connection.cursor(row_factory=dict_row) as cursor:
        row = cursor.execute(
            """
            UPDATE deferred_effects
            SET precondition_state = %s,
                updated_at = %s
            WHERE id = %s
              AND precondition_state = 'unchecked'
            RETURNING id, subsystem, effect_type, idempotency_key, payload_json,
                      consequence_level, precondition_state, status,
                      claimed_by, claimed_at, lease_until, attempts, max_attempts,
                      last_error_json, correlation_id, created_at, updated_at
            """,
            (new_state, now, effect_id),
        ).fetchone()
        if row is not None:
            return row
        current = cursor.execute(
            """
            SELECT precondition_state
            FROM deferred_effects
            WHERE id = %s
            """,
            (effect_id,),
        ).fetchone()
    if current is None:
        raise LookupError(f"deferred effect {effect_id} was not found")
    raise InvalidPreconditionStateTransitionError(effect_id, str(current["precondition_state"]))


def query_degraded_state_summary(
    connection: Connection[Any],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            WITH effect_summary AS (
                SELECT
                    subsystem,
                    COUNT(*)::int AS pending_effect_count,
                    MIN(created_at) AS oldest_effect_at
                FROM deferred_effects
                WHERE status <> 'completed'
                GROUP BY subsystem
            ),
            job_summary AS (
                SELECT
                    subsystem,
                    COUNT(*)::int AS scheduled_job_count,
                    MIN(next_run_at) AS oldest_job_at
                FROM scheduled_jobs
                WHERE (status = 'queued' AND next_run_at <= %s)
                   OR (status = 'claimed' AND lease_until < %s)
                GROUP BY subsystem
            ),
            envelope_summary AS (
                SELECT
                    'notifications'::text AS subsystem,
                    COUNT(*)::int AS stuck_in_flight_envelopes
                FROM notification_envelopes
                WHERE delivery_status = 'delivered_in_flight'
                  AND claimed_at < %s - INTERVAL '1 hour'
            ),
            subsystems AS (
                SELECT subsystem FROM effect_summary
                UNION
                SELECT subsystem FROM job_summary
                UNION
                SELECT subsystem FROM envelope_summary
            ),
            merged AS (
                SELECT
                    subsystems.subsystem AS subsystem,
                    COALESCE(effect_summary.pending_effect_count, 0) AS pending_effect_count,
                    COALESCE(job_summary.scheduled_job_count, 0) AS scheduled_job_count,
                    COALESCE(envelope_summary.stuck_in_flight_envelopes, 0) AS stuck_in_flight_envelopes,
                    effect_summary.oldest_effect_at,
                    job_summary.oldest_job_at
                FROM subsystems
                LEFT JOIN effect_summary
                  ON effect_summary.subsystem = subsystems.subsystem
                LEFT JOIN job_summary
                  ON job_summary.subsystem = subsystems.subsystem
                LEFT JOIN envelope_summary
                  ON envelope_summary.subsystem = subsystems.subsystem
            )
            SELECT
                subsystem,
                pending_effect_count,
                scheduled_job_count,
                stuck_in_flight_envelopes,
                CASE
                    WHEN oldest_effect_at IS NULL THEN oldest_job_at
                    WHEN oldest_job_at IS NULL THEN oldest_effect_at
                    ELSE LEAST(oldest_effect_at, oldest_job_at)
                END AS oldest_pending_at
            FROM merged
            ORDER BY subsystem ASC
            """,
            (now, now, now),
        ).fetchall()
