from __future__ import annotations

import asyncio
import inspect
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.scheduler import (
    DeferredEffectCreate,
    DeferredEffectRead,
    DegradedStateSummaryRead,
)
from app.core.context import resolve_register_correlation, use_audit_context
from app.repositories.db import PostgresDatabase
from app.repositories.deferred_effects import (
    claim_due_deferred_effects,
    enqueue_effect as insert_effect,
    fetch_deferred_effect,
    list_deferred_effects_by_subsystem as list_effect_rows_by_subsystem,
    mark_deferred_effect_completed,
    mark_deferred_effect_failed,
    mark_deferred_effect_skipped,
    query_degraded_state_summary,
    update_precondition_state,
)
from app.services.scheduler import CLAIM_BATCH_SIZE, DEFAULT_MAX_ATTEMPTS, LEASE_SECONDS, _lookup_handler


def _deferred_effect_from_row(row: dict[str, Any]) -> DeferredEffectRead:
    return DeferredEffectRead(
        id=row["id"],
        subsystem=row["subsystem"],
        effect_type=row["effect_type"],
        idempotency_key=row["idempotency_key"],
        payload_json=row["payload_json"],
        consequence_level=row["consequence_level"],
        precondition_state=row["precondition_state"],
        status=row["status"],
        attempts=int(row["attempts"]),
        max_attempts=int(row["max_attempts"]),
        correlation_id=row["correlation_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _summary_from_row(row: dict[str, Any]) -> DegradedStateSummaryRead:
    return DegradedStateSummaryRead(
        subsystem=row["subsystem"],
        pending_effect_count=int(row["pending_effect_count"]),
        scheduled_job_count=int(row["scheduled_job_count"]),
        stuck_in_flight_envelopes=int(row.get("stuck_in_flight_envelopes", 0) or 0),
        oldest_pending_at=row["oldest_pending_at"],
    )


def _reconstruct_audit_context(correlation_id: Any) -> AuditContextRead:
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=None,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=None,
        ),
    )


def enqueue_effect(
    db: PostgresDatabase,
    request: DeferredEffectCreate,
) -> DeferredEffectRead:
    ctx = resolve_register_correlation(request.correlation_id, allow_new_root=True)
    with db.connection() as connection:
        row = insert_effect(
            connection,
            effect=request,
            correlation_id=ctx.correlation_id,
            max_attempts=DEFAULT_MAX_ATTEMPTS,
        )
    return _deferred_effect_from_row(row)


def read_deferred_effect(
    db: PostgresDatabase,
    effect_id: UUID,
) -> DeferredEffectRead | None:
    with db.connection() as connection:
        row = fetch_deferred_effect(connection, effect_id)
    if row is None:
        return None
    return _deferred_effect_from_row(row)


def list_deferred_effects_by_subsystem(
    db: PostgresDatabase,
    subsystem: str,
    *,
    status: str | None = None,
) -> list[DeferredEffectRead]:
    with db.connection() as connection:
        rows = list_effect_rows_by_subsystem(
            connection,
            subsystem=subsystem,
            status=status,
        )
    return [_deferred_effect_from_row(row) for row in rows]


def read_degraded_state_summary(
    db: PostgresDatabase,
) -> list[DegradedStateSummaryRead]:
    with db.connection() as connection:
        rows = query_degraded_state_summary(connection, now=datetime.now(tz=UTC))
    return [_summary_from_row(row) for row in rows]


def mark_precondition_valid(
    db: PostgresDatabase,
    effect_id: UUID,
) -> DeferredEffectRead:
    with db.connection() as connection:
        row = update_precondition_state(connection, effect_id=effect_id, new_state="valid")
    return _deferred_effect_from_row(row)


def mark_precondition_invalid(
    db: PostgresDatabase,
    effect_id: UUID,
) -> DeferredEffectRead:
    with db.connection() as connection:
        row = update_precondition_state(connection, effect_id=effect_id, new_state="invalid")
    return _deferred_effect_from_row(row)


def deferred_effect_worker_tick(
    db: PostgresDatabase,
    *,
    worker_id: str,
) -> None:
    with db.connection() as connection:
        claimed_rows = claim_due_deferred_effects(
            connection,
            worker_id=worker_id,
            now=datetime.now(tz=UTC),
            batch_size=CLAIM_BATCH_SIZE,
            lease_seconds=LEASE_SECONDS,
        )

    claimed_effects = [_deferred_effect_from_row(row) for row in claimed_rows]
    for effect in claimed_effects:
        handler = _lookup_handler(effect.effect_type)
        if handler is None:
            with db.connection() as connection:
                mark_deferred_effect_skipped(
                    connection,
                    effect_id=effect.id,
                    worker_id=worker_id,
                    reason="handler_not_found",
                )
            continue

        if (
            effect.consequence_level == "consequential"
            and effect.precondition_state == "invalid"
        ):
            with db.connection() as connection:
                mark_deferred_effect_skipped(
                    connection,
                    effect_id=effect.id,
                    worker_id=worker_id,
                    reason="invalid_precondition",
                )
            continue

        try:
            with use_audit_context(_reconstruct_audit_context(effect.correlation_id)):
                result = handler(effect)
                if inspect.isawaitable(result):
                    asyncio.run(result)
        except Exception as error:
            with db.connection() as connection:
                mark_deferred_effect_failed(
                    connection,
                    effect_id=effect.id,
                    worker_id=worker_id,
                    error=error,
                )
            continue

        with db.connection() as connection:
            mark_deferred_effect_completed(
                connection,
                effect_id=effect.id,
                worker_id=worker_id,
            )


__all__ = [
    "deferred_effect_worker_tick",
    "enqueue_effect",
    "list_deferred_effects_by_subsystem",
    "mark_precondition_invalid",
    "mark_precondition_valid",
    "read_deferred_effect",
    "read_degraded_state_summary",
]
