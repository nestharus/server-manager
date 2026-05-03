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
from app.repositories.deferred_effects import DeferredEffectsRepository
from app.services.scheduler import (
    CLAIM_BATCH_SIZE,
    DEFAULT_MAX_ATTEMPTS,
    LEASE_SECONDS,
    _lookup_handler,
)


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
        causation_id=row["causation_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _summary_from_row(row: dict[str, Any]) -> DegradedStateSummaryRead:
    return DegradedStateSummaryRead(
        subsystem=row["subsystem"],
        pending_effect_count=int(row["pending_effect_count"]),
        scheduled_job_count=int(row["scheduled_job_count"]),
        stuck_in_flight_envelopes=(
            int(row["stuck_in_flight_envelopes"])
            if row["subsystem"] == "notifications"
            and row.get("stuck_in_flight_envelopes") is not None
            else None
        ),
        oldest_pending_at=row["oldest_pending_at"],
    )


def _reconstruct_audit_context(
    correlation_id: Any,
    causation_id: Any | None,
) -> AuditContextRead:
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=causation_id,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=causation_id,
        ),
    )


class DeferredEffectsService:
    def __init__(
        self,
        deferred_effects_repo: DeferredEffectsRepository,
        mutations_callable,
    ) -> None:
        self._deferred_effects_repo = deferred_effects_repo
        self._mutations_callable = mutations_callable

    def enqueue_effect(self, request: DeferredEffectCreate) -> DeferredEffectRead:
        ctx = resolve_register_correlation(request.correlation_id, allow_new_root=True)
        persisted = request.model_copy(
            update={
                "correlation_id": ctx.correlation_id,
                "causation_id": request.causation_id or ctx.causation_id,
            }
        )
        row = self._deferred_effects_repo.enqueue_effect(
            effect=persisted,
            correlation_id=ctx.correlation_id,
            max_attempts=DEFAULT_MAX_ATTEMPTS,
        )
        return _deferred_effect_from_row(row)

    def read_deferred_effect(self, effect_id: UUID) -> DeferredEffectRead | None:
        row = self._deferred_effects_repo.fetch_deferred_effect(effect_id)
        if row is None:
            return None
        return _deferred_effect_from_row(row)

    def list_deferred_effects_by_subsystem(
        self,
        subsystem: str,
        *,
        status: str | None = None,
    ) -> list[DeferredEffectRead]:
        rows = self._deferred_effects_repo.list_deferred_effects_by_subsystem(
            subsystem=subsystem,
            status=status,
        )
        return [_deferred_effect_from_row(row) for row in rows]

    def read_degraded_state_summary(self) -> list[DegradedStateSummaryRead]:
        rows = self._deferred_effects_repo.query_degraded_state_summary(
            now=datetime.now(tz=UTC),
        )
        return [_summary_from_row(row) for row in rows]

    def mark_precondition_valid(self, effect_id: UUID) -> DeferredEffectRead:
        row = self._deferred_effects_repo.update_precondition_state(
            effect_id=effect_id,
            new_state="valid",
        )
        return _deferred_effect_from_row(row)

    def mark_precondition_invalid(self, effect_id: UUID) -> DeferredEffectRead:
        row = self._deferred_effects_repo.update_precondition_state(
            effect_id=effect_id,
            new_state="invalid",
        )
        return _deferred_effect_from_row(row)

    def deferred_effect_worker_tick(self, *, worker_id: str) -> None:
        db = self._deferred_effects_repo.db
        with db.transaction() as connection:
            claimed_rows = self._deferred_effects_repo._claim_due_deferred_effects_on(
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
                with db.transaction() as connection:
                    self._deferred_effects_repo._mark_deferred_effect_skipped_on(
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
                with db.transaction() as connection:
                    self._deferred_effects_repo._mark_deferred_effect_skipped_on(
                        connection,
                        effect_id=effect.id,
                        worker_id=worker_id,
                        reason="invalid_precondition",
                    )
                continue

            try:
                with use_audit_context(
                    _reconstruct_audit_context(
                        effect.correlation_id, effect.causation_id
                    )
                ):
                    result = handler(effect)
                    if inspect.isawaitable(result):
                        asyncio.run(result)
            except Exception as error:
                with db.transaction() as connection:
                    self._deferred_effects_repo._mark_deferred_effect_failed_on(
                        connection,
                        effect_id=effect.id,
                        worker_id=worker_id,
                        error=error,
                    )
                continue

            with db.transaction() as connection:
                self._deferred_effects_repo._mark_deferred_effect_completed_on(
                    connection,
                    effect_id=effect.id,
                    worker_id=worker_id,
                )


__all__ = ["DeferredEffectsService"]
