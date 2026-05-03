from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import UTC, datetime
from typing import Any, Callable

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.scheduler import (
    ScheduledJobCreate,
    ScheduledJobRead,
    SchedulerHandlerConflictError,
)
from app.core.context import resolve_register_correlation, use_audit_context
from app.repositories.db import PostgresDatabase
from app.repositories.scheduler import SchedulerRepository

LEASE_SECONDS = 300
POLL_INTERVAL_SECONDS = 5
DEFAULT_MAX_ATTEMPTS = 3
CLAIM_BATCH_SIZE = 10
TICKET_SLA_INTERVAL_SECONDS = 60
CHAPTER_ARCHIVE_INTERVAL_SECONDS = 60
READ_MODEL_TICK_INTERVAL_SECONDS = 10
PERMISSION_EXPIRY_INTERVAL_SECONDS = 60
COMPLIANCE_EVALUATION_INTERVAL_SECONDS = 3600

logger = logging.getLogger(__name__)

SchedulerHandler = Callable[..., Any]


def _scheduled_job_from_row(row: dict[str, Any]) -> ScheduledJobRead:
    return ScheduledJobRead(
        job_key=row["job_key"],
        subsystem=row["subsystem"],
        handler_name=row["handler_name"],
        next_run_at=row["next_run_at"],
        status=row["status"],
        attempts=int(row["attempts"]),
        max_attempts=int(row["max_attempts"]),
        correlation_id=row["correlation_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
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


class HandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, SchedulerHandler] = {}

    def register(
        self, handler_name: str, handler: SchedulerHandler
    ) -> SchedulerHandler:
        if handler_name in self._handlers:
            raise SchedulerHandlerConflictError(handler_name)
        self._handlers[handler_name] = handler
        return handler

    def lookup(self, handler_name: str) -> SchedulerHandler | None:
        return self._handlers.get(handler_name)


_HANDLER_REGISTRY = HandlerRegistry()


def register_scheduler_handler(
    handler_name: str,
) -> Callable[[SchedulerHandler], SchedulerHandler]:
    def decorator(handler: SchedulerHandler) -> SchedulerHandler:
        return _HANDLER_REGISTRY.register(handler_name, handler)

    return decorator


def _lookup_handler(handler_name: str) -> SchedulerHandler | None:
    return _HANDLER_REGISTRY.lookup(handler_name)


def _handler_accepts_db(handler: SchedulerHandler) -> bool:
    try:
        signature = inspect.signature(handler)
    except (TypeError, ValueError):
        return True
    return any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD or name == "db"
        for name, parameter in signature.parameters.items()
    )


def _invoke_handler_with_db(
    handler: SchedulerHandler,
    payload: Any,
    *,
    db: PostgresDatabase,
) -> Any:
    if _handler_accepts_db(handler):
        return handler(payload, db=db)
    return handler(payload)


class SchedulerService:
    def __init__(
        self,
        scheduler_repo: SchedulerRepository,
        db: PostgresDatabase,
        *,
        worker_id: str,
        lease_seconds: int = LEASE_SECONDS,
        poll_interval_seconds: int = POLL_INTERVAL_SECONDS,
        claim_batch_size: int = CLAIM_BATCH_SIZE,
    ) -> None:
        self._scheduler_repo = scheduler_repo
        self._db = db
        self._worker_id = worker_id
        self._lease_seconds = lease_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._claim_batch_size = claim_batch_size
        self._stop_event = asyncio.Event()
        self._is_running = False
        self._last_ticket_sla_tick_at: datetime | None = None
        self._last_archive_tick_at: datetime | None = None
        self._last_read_model_tick_at: datetime | None = None
        self._last_permission_expiry_tick_at: datetime | None = None
        self._last_compliance_evaluation_tick_at: datetime | None = None

    @property
    def is_running(self) -> bool:
        return self._is_running and not self._stop_event.is_set()

    async def stop(self) -> None:
        self._stop_event.set()

    def register_scheduled_job(self, request: ScheduledJobCreate) -> ScheduledJobRead:
        ctx = resolve_register_correlation(request.correlation_id, allow_new_root=True)
        row = self._scheduler_repo.register_scheduled_job(
            job=request,
            correlation_id=ctx.correlation_id,
        )
        return _scheduled_job_from_row(row)

    def read_scheduled_job(self, job_key: str) -> ScheduledJobRead | None:
        row = self._scheduler_repo.fetch_scheduled_job(job_key)
        if row is None:
            return None
        return _scheduled_job_from_row(row)

    def extend_lease(self, job_key: str, *, extra_seconds: int) -> None:
        self._scheduler_repo.extend_job_lease(
            job_key=job_key,
            extra_seconds=extra_seconds,
        )

    async def run(self) -> None:
        self._is_running = True
        try:
            while not self._stop_event.is_set():
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self._poll_interval_seconds,
                    )
                    break
                except TimeoutError:
                    try:
                        await self._tick()
                    except Exception:
                        logger.exception(
                            "scheduler tick failed for worker %s", self._worker_id
                        )
        finally:
            self._is_running = False

    async def _tick(self) -> None:
        now = datetime.now(tz=UTC)
        claimed_jobs = await asyncio.to_thread(self._claim_due_jobs, now)
        for job in claimed_jobs:
            await asyncio.to_thread(self._dispatch_claimed_job, job)

        await self._run_chapter_archive_if_due(now)
        from functools import partial

        from app.repositories.deferred_effects import DeferredEffectsRepository
        from app.services.deferred_effects import DeferredEffectsService
        from app.services.mutations import mutate_entity

        await asyncio.to_thread(
            DeferredEffectsService(
                deferred_effects_repo=DeferredEffectsRepository(db=self._db),
                mutations_callable=partial(mutate_entity, db=self._db),
            ).deferred_effect_worker_tick,
            worker_id=self._worker_id,
        )
        await self._run_ticket_sla_if_due(now)
        await self._run_read_model_tick_if_due(now)
        await self._run_permission_expiry_if_due(now)
        await self._run_compliance_evaluation_if_due(now)

    async def _run_chapter_archive_if_due(self, now: datetime) -> None:
        if (
            self._last_archive_tick_at is not None
            and (now - self._last_archive_tick_at).total_seconds()
            < CHAPTER_ARCHIVE_INTERVAL_SECONDS
        ):
            return

        from app.tasks.archive import archive_worker_tick

        self._last_archive_tick_at = now
        try:
            await asyncio.to_thread(archive_worker_tick, db=self._db)
        except Exception:
            logger.exception(
                "chapter archive worker tick failed for worker %s",
                self._worker_id,
            )

    async def _run_ticket_sla_if_due(self, now: datetime) -> None:
        if (
            self._last_ticket_sla_tick_at is not None
            and (now - self._last_ticket_sla_tick_at).total_seconds()
            < TICKET_SLA_INTERVAL_SECONDS
        ):
            return

        from app.tasks.ticket_sla import ticket_sla_worker_tick

        self._last_ticket_sla_tick_at = now
        try:
            await asyncio.to_thread(ticket_sla_worker_tick, db=self._db)
        except Exception:
            logger.exception(
                "ticket SLA worker tick failed for worker %s",
                self._worker_id,
            )

    async def _run_read_model_tick_if_due(self, now: datetime) -> None:
        if (
            self._last_read_model_tick_at is not None
            and (now - self._last_read_model_tick_at).total_seconds()
            < READ_MODEL_TICK_INTERVAL_SECONDS
        ):
            return

        from app.tasks.read_models import read_model_worker_tick

        self._last_read_model_tick_at = now
        try:
            await asyncio.to_thread(read_model_worker_tick, db=self._db, now=now)
        except Exception:
            logger.exception(
                "read-model worker tick failed for worker %s",
                self._worker_id,
            )

    async def _run_permission_expiry_if_due(self, now: datetime) -> None:
        if (
            self._last_permission_expiry_tick_at is not None
            and (now - self._last_permission_expiry_tick_at).total_seconds()
            < PERMISSION_EXPIRY_INTERVAL_SECONDS
        ):
            return

        from app.tasks.permission_expiry import permission_expiry_worker_tick

        self._last_permission_expiry_tick_at = now
        try:
            await asyncio.to_thread(
                permission_expiry_worker_tick,
                db=self._db,
                now=now,
            )
        except Exception:
            logger.exception(
                "permission-expiry worker tick failed for worker %s",
                self._worker_id,
            )

    async def _run_compliance_evaluation_if_due(self, now: datetime) -> None:
        if (
            self._last_compliance_evaluation_tick_at is not None
            and (now - self._last_compliance_evaluation_tick_at).total_seconds()
            < COMPLIANCE_EVALUATION_INTERVAL_SECONDS
        ):
            return

        from app.tasks.compliance import compliance_evaluation_worker_tick

        self._last_compliance_evaluation_tick_at = now
        try:
            await asyncio.to_thread(
                compliance_evaluation_worker_tick, db=self._db, now=now
            )
        except Exception:
            logger.exception(
                "compliance evaluation worker tick failed for worker %s",
                self._worker_id,
            )

    def _claim_due_jobs(self, now: datetime) -> list[ScheduledJobRead]:
        with self._db.connection() as connection:
            rows = self._scheduler_repo._claim_due_scheduled_jobs_on(
                connection,
                worker_id=self._worker_id,
                now=now,
                batch_size=self._claim_batch_size,
                lease_seconds=self._lease_seconds,
            )
        return [_scheduled_job_from_row(row) for row in rows]

    def _dispatch_claimed_job(self, job: ScheduledJobRead) -> None:
        handler = _lookup_handler(job.handler_name)
        if handler is None:
            with self._db.connection() as connection:
                self._scheduler_repo._mark_scheduled_job_abandoned_on(
                    connection,
                    job_key=job.job_key,
                    reason="handler_not_found",
                )
            return

        try:
            with use_audit_context(_reconstruct_audit_context(job.correlation_id)):
                result = _invoke_handler_with_db(handler, job, db=self._db)
                if inspect.isawaitable(result):
                    asyncio.run(result)
        except Exception as error:
            with self._db.connection() as connection:
                failed_row = self._scheduler_repo._mark_scheduled_job_failed_on(
                    connection,
                    job_key=job.job_key,
                    worker_id=self._worker_id,
                    error=error,
                )
                if failed_row is not None and int(failed_row["attempts"]) >= int(
                    failed_row["max_attempts"]
                ):
                    self._scheduler_repo._mark_scheduled_job_abandoned_on(
                        connection,
                        job_key=job.job_key,
                        reason="max_attempts_exhausted",
                    )
            return

        with self._db.connection() as connection:
            self._scheduler_repo._mark_scheduled_job_completed_on(
                connection,
                job_key=job.job_key,
                worker_id=self._worker_id,
            )


def build_scheduler_loop(
    db: PostgresDatabase,
    *,
    worker_id: str,
) -> SchedulerService:
    return SchedulerService(
        scheduler_repo=SchedulerRepository(db),
        db=db,
        worker_id=worker_id,
    )


__all__ = [
    "CLAIM_BATCH_SIZE",
    "CHAPTER_ARCHIVE_INTERVAL_SECONDS",
    "DEFAULT_MAX_ATTEMPTS",
    "COMPLIANCE_EVALUATION_INTERVAL_SECONDS",
    "HandlerRegistry",
    "LEASE_SECONDS",
    "PERMISSION_EXPIRY_INTERVAL_SECONDS",
    "POLL_INTERVAL_SECONDS",
    "READ_MODEL_TICK_INTERVAL_SECONDS",
    "SchedulerService",
    "TICKET_SLA_INTERVAL_SECONDS",
    "_lookup_handler",
    "build_scheduler_loop",
    "register_scheduler_handler",
]
