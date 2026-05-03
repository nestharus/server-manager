"""Contract tests for SLICE-004 WU-008A: scheduler foundation (AC1).

Pins D1 (asyncio lifespan execution), D4 (lease/claim), D5 (explicit
subsystem column), D8 (scheduler-originated request_surface via restored
audit context), and D10 (Python-dict handler registry). Tests fail now;
pass once the scheduler service, repository, migration, and handler
registry land.

Worker behavior is exercised through ``SchedulerService._tick()`` — the
single-tick seam called by ``run()`` on each poll interval — instead of
spinning up the asyncio supervision loop.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.scheduler import (
    ScheduledJobCreate,
    ScheduledJobRead,
    SchedulerHandlerConflictError,
)
from app.core.context import resolve_register_correlation, use_audit_context
from app.repositories.db import PostgresDatabase
from app.repositories.scheduler import SchedulerRepository
from app.services.scheduler import (
    DEFAULT_MAX_ATTEMPTS,
    LEASE_SECONDS,
    POLL_INTERVAL_SECONDS,
    SchedulerService,
    register_scheduler_handler,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_audit_context(correlation_id: UUID | None = None) -> AuditContextRead:
    cid = correlation_id or uuid4()
    headers = CorrelationHeadersRead(x_correlation_id=cid, x_causation_id=None)
    return AuditContextRead(correlation_id=cid, causation_id=None, headers=headers)


def _unique_job_key(label: str) -> str:
    return f"test:{label}:{uuid4().hex}"


def _unique_handler_name(label: str) -> str:
    return f"test.handler.{label}.{uuid4().hex}"


def _fetch_job_row(database_url: str, job_key: str) -> dict[str, Any] | None:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT job_key, subsystem, handler_name, next_run_at, status,
                   claimed_by, claimed_at, lease_until, attempts, max_attempts,
                   correlation_id, created_at, updated_at
            FROM scheduled_jobs
            WHERE job_key = %s
            """,
            (job_key,),
        ).fetchone()
    return row


def _count_jobs(database_url: str, job_key: str) -> int:
    with psycopg.connect(database_url) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM scheduled_jobs WHERE job_key = %s",
            (job_key,),
        ).fetchone()
    assert row is not None
    return int(row[0])


def _set_job_claim(
    database_url: str,
    job_key: str,
    *,
    claimed_by: str,
    lease_until: datetime,
    status: str = "claimed",
) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(
            """
            UPDATE scheduled_jobs
            SET claimed_by = %s,
                claimed_at = NOW(),
                lease_until = %s,
                status = %s
            WHERE job_key = %s
            """,
            (claimed_by, lease_until, status, job_key),
        )


def _mark_job_completed_directly(database_url: str, job_key: str) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(
            """
            UPDATE scheduled_jobs
            SET status = 'completed',
                claimed_by = NULL,
                claimed_at = NULL,
                lease_until = NULL
            WHERE job_key = %s
            """,
            (job_key,),
        )


def _make_create(
    *,
    job_key: str | None = None,
    subsystem: str = "test-sub",
    handler_name: str = "test.handler",
    next_run_at: datetime | None = None,
    correlation_id: UUID | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> ScheduledJobCreate:
    kwargs: dict[str, Any] = {
        "job_key": job_key or _unique_job_key("job"),
        "subsystem": subsystem,
        "handler_name": handler_name,
        "next_run_at": next_run_at or datetime.now(tz=UTC),
        "max_attempts": max_attempts,
    }
    if correlation_id is not None:
        kwargs["correlation_id"] = correlation_id
    return ScheduledJobCreate.model_validate(kwargs)


def _scheduler_service(
    db: PostgresDatabase,
    *,
    worker_id: str = "test-scheduler",
) -> SchedulerService:
    return SchedulerService(
        scheduler_repo=SchedulerRepository(db),
        db=db,
        worker_id=worker_id,
    )


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Contract round-trip
# ---------------------------------------------------------------------------


def test_scheduled_job_round_trips_to_json() -> None:
    """``ScheduledJobRead`` must preserve every field documented by the
    proposal when serialized through canonical JSON (model_dump →
    model_validate)."""

    original = ScheduledJobRead(
        job_key=_unique_job_key("rt"),
        subsystem="subsystem-x",
        handler_name="test.roundtrip",
        next_run_at=datetime(2026, 4, 19, 12, 0, tzinfo=UTC),
        status="queued",
        attempts=0,
        max_attempts=3,
        correlation_id=uuid4(),
        created_at=datetime(2026, 4, 19, 11, 59, tzinfo=UTC),
        updated_at=datetime(2026, 4, 19, 11, 59, tzinfo=UTC),
    )

    restored = ScheduledJobRead.model_validate(original.model_dump())

    assert restored.job_key == original.job_key
    assert restored.subsystem == original.subsystem
    assert restored.handler_name == original.handler_name
    assert restored.next_run_at == original.next_run_at
    assert restored.status == original.status
    assert restored.attempts == original.attempts
    assert restored.max_attempts == original.max_attempts
    assert restored.correlation_id == original.correlation_id
    assert restored.created_at == original.created_at
    assert restored.updated_at == original.updated_at


# ---------------------------------------------------------------------------
# register_scheduled_job — persistence, idempotency, correlation resolution
# ---------------------------------------------------------------------------


def test_register_scheduled_job_persists_row(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """``register_scheduled_job`` must write a ``scheduled_jobs`` row that
    is visible via direct SQL — infrastructure rows flow through repository
    SQL (D2), not ``mutate_entity``."""

    job_key = _unique_job_key("persist")
    request = _make_create(job_key=job_key, subsystem="persist-sub")

    with use_audit_context(_make_audit_context()):
        read = _scheduler_service(governance_db).register_scheduled_job(request)

    assert isinstance(read, ScheduledJobRead)
    assert read.job_key == job_key
    assert read.subsystem == "persist-sub"

    row = _fetch_job_row(governance_dsn, job_key)
    assert row is not None
    assert row["job_key"] == job_key
    assert row["subsystem"] == "persist-sub"
    assert row["handler_name"] == request.handler_name
    assert row["status"] == "queued"


def test_register_scheduled_job_is_idempotent_by_job_key(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """``ON CONFLICT (job_key) DO NOTHING`` — registering the same
    ``job_key`` twice must not error and must leave exactly one row."""

    job_key = _unique_job_key("idempotent")
    first_request = _make_create(job_key=job_key)
    second_request = _make_create(
        job_key=job_key,
        next_run_at=datetime.now(tz=UTC) + timedelta(hours=1),
    )

    with use_audit_context(_make_audit_context()):
        first = _scheduler_service(governance_db).register_scheduled_job(first_request)
        second = _scheduler_service(governance_db).register_scheduled_job(second_request)

    assert first.job_key == second.job_key == job_key
    assert _count_jobs(governance_dsn, job_key) == 1


def test_register_scheduled_job_without_correlation_warns(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Without an active audit context and without an explicit
    ``correlation_id``, ``resolve_register_correlation(allow_new_root=True)``
    must WARN-log and invent a root correlation. The persisted row must
    still carry a valid UUID in ``correlation_id`` so the row remains
    debuggable."""

    job_key = _unique_job_key("warn")
    request = _make_create(job_key=job_key)

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="app.core.context"):
        read = _scheduler_service(governance_db).register_scheduled_job(request)

    assert any(
        record.levelno == logging.WARNING for record in caplog.records
    ), "expected a WARN log when correlation is fabricated"

    assert isinstance(read.correlation_id, UUID)

    row = _fetch_job_row(governance_dsn, job_key)
    assert row is not None
    # Valid UUID — accepts UUID objects or string-serialized UUIDs.
    assert UUID(str(row["correlation_id"])) == read.correlation_id


def test_register_scheduled_job_with_explicit_correlation_uses_it(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """An explicit ``correlation_id`` on ``ScheduledJobCreate`` must
    round-trip straight to the persisted row — ahead of any ambient
    context and ahead of the root-correlation fallback."""

    explicit = uuid4()
    job_key = _unique_job_key("explicit")
    request = _make_create(job_key=job_key, correlation_id=explicit)

    read = _scheduler_service(governance_db).register_scheduled_job(request)

    assert read.correlation_id == explicit

    row = _fetch_job_row(governance_dsn, job_key)
    assert row is not None
    assert UUID(str(row["correlation_id"])) == explicit


def test_register_scheduled_job_inherits_contextvar_correlation(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """``use_audit_context(X)`` around a register call with no explicit
    correlation must persist ``X.correlation_id``. Precedence is explicit
    > ContextVar > fabricated root."""

    ctx_correlation = uuid4()
    ctx = _make_audit_context(correlation_id=ctx_correlation)
    job_key = _unique_job_key("ctx")
    request = _make_create(job_key=job_key)

    with use_audit_context(ctx):
        read = _scheduler_service(governance_db).register_scheduled_job(request)

    assert read.correlation_id == ctx_correlation

    row = _fetch_job_row(governance_dsn, job_key)
    assert row is not None
    assert UUID(str(row["correlation_id"])) == ctx_correlation


# ---------------------------------------------------------------------------
# AC1: survives restart + stable identity across runs
# ---------------------------------------------------------------------------


def test_scheduled_job_survives_restart(governance_dsn: str) -> None:
    """AC1: register a job with a past ``next_run_at`` on one
    ``PostgresDatabase`` pool; close the pool; open a fresh pool at the
    same DSN; ``read_scheduled_job`` must still return the row."""

    job_key = _unique_job_key("restart")
    past = datetime.now(tz=UTC) - timedelta(minutes=5)
    request = _make_create(job_key=job_key, next_run_at=past)

    db = PostgresDatabase(dsn=governance_dsn)
    try:
        with use_audit_context(_make_audit_context()):
            _scheduler_service(db).register_scheduled_job(request)
    finally:
        db.close()

    # Simulate process restart: fresh pool, same DSN.
    fresh_db = PostgresDatabase(dsn=governance_dsn)
    try:
        reloaded = _scheduler_service(fresh_db).read_scheduled_job(job_key)
    finally:
        fresh_db.close()

    assert reloaded is not None
    assert reloaded.job_key == job_key
    assert reloaded.next_run_at == past


def test_scheduled_job_stable_identity_across_runs(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC1: stable identity means re-registering the same ``job_key``
    after a completed run reuses the existing row — NOT inserts a new
    row. The ``job_key`` is the durable identity; ``next_run_at`` is
    operational state."""

    job_key = _unique_job_key("stable")
    first_next = datetime.now(tz=UTC) + timedelta(minutes=10)
    first_request = _make_create(job_key=job_key, next_run_at=first_next)

    with use_audit_context(_make_audit_context()):
        first = _scheduler_service(governance_db).register_scheduled_job(first_request)

    # Simulate an execution that left the row in ``completed`` state.
    _mark_job_completed_directly(governance_dsn, job_key)

    second_next = datetime.now(tz=UTC) + timedelta(hours=1)
    second_request = _make_create(job_key=job_key, next_run_at=second_next)

    with use_audit_context(_make_audit_context()):
        second = _scheduler_service(governance_db).register_scheduled_job(second_request)

    # Same logical row, same identity.
    assert first.job_key == second.job_key
    assert _count_jobs(governance_dsn, job_key) == 1


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------


def test_register_scheduler_handler_decorator_registers_in_registry() -> None:
    """D10: handler discovery is a Python dict. The decorator must make
    the handler reachable via the internal ``_lookup_handler`` seam so
    the scheduler can dispatch by name."""

    from app.services.scheduler import _lookup_handler

    name = _unique_handler_name("lookup")
    calls: list[str] = []

    @register_scheduler_handler(name)
    def handler(job: Any) -> None:
        calls.append(name)

    resolved = _lookup_handler(name)
    assert resolved is handler


def test_register_scheduler_handler_conflict_raises() -> None:
    """Registering the same handler name twice must raise
    ``SchedulerHandlerConflictError`` — not silently clobber the prior
    callable."""

    name = _unique_handler_name("conflict")

    @register_scheduler_handler(name)
    def first(job: Any) -> None:  # pragma: no cover — body not invoked
        pass

    with pytest.raises(SchedulerHandlerConflictError):
        @register_scheduler_handler(name)
        def second(job: Any) -> None:  # pragma: no cover
            pass


def test_tasks_module_exposes_register_scheduler_handler() -> None:
    """``app.tasks`` is documented as the namespace entrypoint for later
    task slices. It must re-export ``register_scheduler_handler`` so
    slice authors do not reach across into ``app.services.scheduler``
    directly."""

    from app.tasks import register_scheduler_handler as reexport

    assert reexport is register_scheduler_handler


# ---------------------------------------------------------------------------
# Lease semantics
# ---------------------------------------------------------------------------


def test_extend_lease_pushes_lease_until_forward(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """``extend_lease`` must advance ``lease_until`` forward on a
    currently claimed job so long-running handlers can keep their
    claim."""

    job_key = _unique_job_key("lease")
    request = _make_create(job_key=job_key)
    with use_audit_context(_make_audit_context()):
        _scheduler_service(governance_db).register_scheduled_job(request)

    initial_lease = datetime.now(tz=UTC) + timedelta(seconds=10)
    _set_job_claim(
        governance_dsn,
        job_key,
        claimed_by="worker-1",
        lease_until=initial_lease,
    )

    _scheduler_service(governance_db).extend_lease(job_key, extra_seconds=300)

    row = _fetch_job_row(governance_dsn, job_key)
    assert row is not None
    assert row["lease_until"] is not None
    assert row["lease_until"] > initial_lease


def test_claim_due_scheduled_jobs_skips_leased_rows(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """D4: a scheduler tick must not re-claim a row whose lease is still
    live. Once the lease expires, the next tick lazily reclaims it — no
    boot sweep required."""

    job_key = _unique_job_key("leased")
    handler_name = _unique_handler_name("leased")
    calls: list[str] = []

    @register_scheduler_handler(handler_name)
    def handler(job: Any) -> None:
        calls.append(job_key)

    due = datetime.now(tz=UTC) - timedelta(seconds=1)
    with use_audit_context(_make_audit_context()):
        _scheduler_service(governance_db).register_scheduled_job(
            _make_create(
                job_key=job_key, handler_name=handler_name, next_run_at=due
            ),
        )

    # Simulate worker-1 holding a LIVE lease on the row.
    live_lease = datetime.now(tz=UTC) + timedelta(seconds=LEASE_SECONDS)
    _set_job_claim(
        governance_dsn,
        job_key,
        claimed_by="worker-1",
        lease_until=live_lease,
    )

    # worker-2 tick — must NOT execute a live-leased row.
    async def _run_worker_2() -> None:
        loop = _scheduler_service(governance_db, worker_id="worker-2")
        await loop._tick()

    asyncio.run(_run_worker_2())
    assert calls == []

    row = _fetch_job_row(governance_dsn, job_key)
    assert row is not None
    assert row["claimed_by"] == "worker-1"

    # Expire the lease: worker-2 can now reclaim lazily on its next tick.
    expired_lease = datetime.now(tz=UTC) - timedelta(seconds=1)
    _set_job_claim(
        governance_dsn,
        job_key,
        claimed_by="worker-1",
        lease_until=expired_lease,
    )

    asyncio.run(_run_worker_2())
    assert calls == [job_key]


# ---------------------------------------------------------------------------
# Module-level constants (sanity pins)
# ---------------------------------------------------------------------------


def test_scheduler_module_constants_are_module_level() -> None:
    """Phase 0 constants are intentionally module-level, not settings-
    owned (proposal §3 WU-008A and findings F-5)."""

    assert isinstance(LEASE_SECONDS, int) and LEASE_SECONDS > 0
    assert isinstance(POLL_INTERVAL_SECONDS, int) and POLL_INTERVAL_SECONDS > 0
    assert isinstance(DEFAULT_MAX_ATTEMPTS, int) and DEFAULT_MAX_ATTEMPTS > 0


# ---------------------------------------------------------------------------
# resolve_register_correlation is reachable (helper is on context module)
# ---------------------------------------------------------------------------


def test_resolve_register_correlation_is_importable_from_core_context() -> None:
    """The registration-time correlation helper must live beside
    ``use_audit_context`` in ``app.core.context`` — not inside the
    scheduler service (hookpoint §2)."""

    assert callable(resolve_register_correlation)
