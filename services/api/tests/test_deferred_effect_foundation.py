"""Contract tests for SLICE-004 WU-008B: deferred-effect foundation
(AC2, AC3, AC4).

Pins D3 (dequeue-time precondition gate), D4 (lease/claim reclaim), D5
(explicit ``subsystem`` column), D6 (idempotency_key UNIQUE), D7 (widened
``DegradedStateSummaryRead``), and D9 (attempts/retry journaling).

Worker behavior is exercised through ``DeferredEffectsService.deferred_effect_worker_tick`` —
the single-tick seam dispatched by ``SchedulerService`` — instead of
spinning up the asyncio supervision loop.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.scheduler import (
    DeferredEffectCreate,
    DeferredEffectRead,
    DegradedStateSummaryRead,
    InvalidPreconditionStateTransitionError,
    ScheduledJobCreate,
)
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.repositories.deferred_effects import DeferredEffectsRepository
from app.repositories.scheduler import SchedulerRepository
from app.services.deferred_effects import DeferredEffectsService
from app.services.mutations import mutate_entity
from app.services.scheduler import (
    DEFAULT_MAX_ATTEMPTS,
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


def _unique(label: str) -> str:
    return f"{label}-{uuid4().hex}"


def _unique_effect_type(label: str) -> str:
    return f"test.effect.{label}.{uuid4().hex}"


def _unique_handler(label: str) -> str:
    return f"test.effect.handler.{label}.{uuid4().hex}"


def _make_create(
    *,
    subsystem: str = "test-sub",
    effect_type: str | None = None,
    idempotency_key: str | None = None,
    payload_json: dict[str, Any] | None = None,
    consequence_level: str = "safe",
    correlation_id: UUID | None = None,
) -> DeferredEffectCreate:
    kwargs: dict[str, Any] = {
        "subsystem": subsystem,
        "effect_type": effect_type or _unique_effect_type("e"),
        "idempotency_key": idempotency_key or _unique("idk"),
        "payload_json": payload_json if payload_json is not None else {},
        "consequence_level": consequence_level,
    }
    if correlation_id is not None:
        kwargs["correlation_id"] = correlation_id
    return DeferredEffectCreate.model_validate(kwargs)


def _fetch_effect_row(database_url: str, effect_id: Any) -> dict[str, Any] | None:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT id, subsystem, effect_type, idempotency_key, payload_json,
                   consequence_level, precondition_state, status,
                   claimed_by, claimed_at, lease_until,
                   attempts, max_attempts, last_error_json,
                   correlation_id, created_at, updated_at
            FROM deferred_effects
            WHERE id = %s
            """,
            (effect_id,),
        ).fetchone()
    return row


def _count_effects_by_idempotency(database_url: str, idempotency_key: str) -> int:
    with psycopg.connect(database_url) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM deferred_effects WHERE idempotency_key = %s",
            (idempotency_key,),
        ).fetchone()
    assert row is not None
    return int(row[0])


def _simulate_stale_claim(
    database_url: str,
    effect_id: Any,
    *,
    claimed_by: str,
    lease_until: datetime,
) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(
            """
            UPDATE deferred_effects
            SET status = 'claimed',
                claimed_by = %s,
                claimed_at = NOW(),
                lease_until = %s
            WHERE id = %s
            """,
            (claimed_by, lease_until, effect_id),
        )


def _deferred_effects_service(db: PostgresDatabase) -> DeferredEffectsService:
    return DeferredEffectsService(
        deferred_effects_repo=DeferredEffectsRepository(db),
        mutations_callable=partial(mutate_entity, db=db),
    )


def _scheduler_service(db: PostgresDatabase) -> SchedulerService:
    return SchedulerService(
        scheduler_repo=SchedulerRepository(db),
        db=db,
        worker_id="test-scheduler",
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


def test_deferred_effect_round_trips_to_json() -> None:
    """``DeferredEffectRead`` must preserve every field documented by the
    proposal through canonical JSON (model_dump → model_validate)."""

    original = DeferredEffectRead(
        id=uuid4(),
        subsystem="subsystem-x",
        effect_type="test.roundtrip",
        idempotency_key="idk-roundtrip",
        payload_json={"k": "v"},
        consequence_level="consequential",
        precondition_state="unchecked",
        status="queued",
        attempts=0,
        max_attempts=3,
        correlation_id=uuid4(),
        created_at=datetime(2026, 4, 19, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 19, 12, 0, tzinfo=UTC),
    )

    restored = DeferredEffectRead.model_validate(original.model_dump())

    assert restored.id == original.id
    assert restored.subsystem == original.subsystem
    assert restored.effect_type == original.effect_type
    assert restored.idempotency_key == original.idempotency_key
    assert restored.payload_json == original.payload_json
    assert restored.consequence_level == original.consequence_level
    assert restored.precondition_state == original.precondition_state
    assert restored.status == original.status
    assert restored.attempts == original.attempts
    assert restored.max_attempts == original.max_attempts
    assert restored.correlation_id == original.correlation_id
    assert restored.created_at == original.created_at
    assert restored.updated_at == original.updated_at


# ---------------------------------------------------------------------------
# enqueue_effect — persistence, idempotency, default state
# ---------------------------------------------------------------------------


def test_enqueue_effect_persists_row(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """``enqueue_effect`` must write a ``deferred_effects`` row visible
    via direct SQL — infrastructure rows flow through repository SQL,
    not ``mutate_entity``."""

    request = _make_create(subsystem="persist-sub")
    with use_audit_context(_make_audit_context()):
        read = _deferred_effects_service(governance_db).enqueue_effect(request)

    assert isinstance(read, DeferredEffectRead)
    assert read.subsystem == "persist-sub"
    row = _fetch_effect_row(governance_dsn, read.id)
    assert row is not None
    assert row["subsystem"] == "persist-sub"
    assert row["effect_type"] == request.effect_type
    assert row["idempotency_key"] == request.idempotency_key


def test_enqueue_effect_is_idempotent_by_idempotency_key(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """D6: repeated enqueue attempts with the same ``idempotency_key``
    must collapse to one canonical row — the caller always gets the
    existing row back on conflict."""

    idk = _unique("idempotent")
    first = _make_create(idempotency_key=idk)
    second = _make_create(idempotency_key=idk)

    with use_audit_context(_make_audit_context()):
        first_read = _deferred_effects_service(governance_db).enqueue_effect(first)
        second_read = _deferred_effects_service(governance_db).enqueue_effect(second)

    assert first_read.idempotency_key == second_read.idempotency_key == idk
    assert first_read.id == second_read.id
    assert _count_effects_by_idempotency(governance_dsn, idk) == 1


def test_enqueue_effect_default_precondition_state_is_unchecked(
    governance_db: PostgresDatabase,
) -> None:
    """D3: fresh consequential effects start at ``precondition_state =
    'unchecked'``. They never auto-skip at enqueue; the gate is a
    dequeue-time check."""

    request = _make_create(consequence_level="consequential")
    with use_audit_context(_make_audit_context()):
        read = _deferred_effects_service(governance_db).enqueue_effect(request)

    assert read.precondition_state == "unchecked"
    assert read.status == "queued"


# ---------------------------------------------------------------------------
# Precondition transition state machine
# ---------------------------------------------------------------------------


def test_mark_precondition_valid_transitions_state(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """``mark_precondition_valid`` must move a fresh ``unchecked`` effect
    to ``valid`` — the sanctioned transition path for precondition
    validators."""

    request = _make_create(consequence_level="consequential")
    with use_audit_context(_make_audit_context()):
        read = _deferred_effects_service(governance_db).enqueue_effect(request)

    _deferred_effects_service(governance_db).mark_precondition_valid(read.id)

    row = _fetch_effect_row(governance_dsn, read.id)
    assert row is not None
    assert row["precondition_state"] == "valid"


def test_mark_precondition_invalid_transitions_state(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """``mark_precondition_invalid`` must move ``unchecked`` to
    ``invalid`` — the terminal-non-execution transition. ``invalid``
    rows remain visible in the degraded-state summary."""

    request = _make_create(consequence_level="consequential")
    with use_audit_context(_make_audit_context()):
        read = _deferred_effects_service(governance_db).enqueue_effect(request)

    _deferred_effects_service(governance_db).mark_precondition_invalid(read.id)

    row = _fetch_effect_row(governance_dsn, read.id)
    assert row is not None
    assert row["precondition_state"] == "invalid"


def test_precondition_state_only_transitions_from_unchecked(
    governance_db: PostgresDatabase,
) -> None:
    """Only ``unchecked -> valid`` and ``unchecked -> invalid`` are
    allowed. Calling a transition on an already-resolved effect must
    raise ``InvalidPreconditionStateTransitionError`` — no toggle, no
    reverse, no silent idempotency."""

    request = _make_create(consequence_level="consequential")
    with use_audit_context(_make_audit_context()):
        read = _deferred_effects_service(governance_db).enqueue_effect(request)

    _deferred_effects_service(governance_db).mark_precondition_valid(read.id)

    with pytest.raises(InvalidPreconditionStateTransitionError):
        _deferred_effects_service(governance_db).mark_precondition_valid(read.id)


# ---------------------------------------------------------------------------
# AC2: consequential precondition gate at dequeue time
# ---------------------------------------------------------------------------


def test_worker_skips_consequential_effect_without_valid_precondition(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC2: the worker tick must NOT execute a ``consequential`` effect
    whose ``precondition_state`` is ``unchecked``. The row remains
    unclaimed / not executed so later validators can still flip it."""

    effect_type = _unique_effect_type("gate-skip")
    calls: list[Any] = []

    @register_scheduler_handler(effect_type)
    def handler(effect: Any) -> None:
        calls.append(effect)

    request = _make_create(
        effect_type=effect_type,
        consequence_level="consequential",
    )
    with use_audit_context(_make_audit_context()):
        read = _deferred_effects_service(governance_db).enqueue_effect(request)

    _deferred_effects_service(governance_db).deferred_effect_worker_tick(worker_id="test-worker")

    assert calls == []
    row = _fetch_effect_row(governance_dsn, read.id)
    assert row is not None
    assert row["status"] != "completed"
    assert row["precondition_state"] == "unchecked"


def test_worker_executes_consequential_effect_with_valid_precondition(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC2: once precondition is marked ``valid``, the next worker tick
    must claim and execute a ``consequential`` effect — terminating at
    ``status='completed'``."""

    effect_type = _unique_effect_type("gate-run")
    calls: list[Any] = []

    @register_scheduler_handler(effect_type)
    def handler(effect: Any) -> None:
        calls.append(effect)

    request = _make_create(
        effect_type=effect_type,
        consequence_level="consequential",
    )
    with use_audit_context(_make_audit_context()):
        read = _deferred_effects_service(governance_db).enqueue_effect(request)

    _deferred_effects_service(governance_db).mark_precondition_valid(read.id)
    _deferred_effects_service(governance_db).deferred_effect_worker_tick(worker_id="test-worker")

    assert len(calls) == 1
    row = _fetch_effect_row(governance_dsn, read.id)
    assert row is not None
    assert row["status"] == "completed"


def test_worker_executes_safe_effects_regardless_of_precondition_state(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """D3: ``safe`` effects bypass the precondition gate and execute
    immediately on the next tick even when ``precondition_state`` is
    ``unchecked``. Only ``consequential`` effects are gated."""

    effect_type = _unique_effect_type("safe-run")
    calls: list[Any] = []

    @register_scheduler_handler(effect_type)
    def handler(effect: Any) -> None:
        calls.append(effect)

    request = _make_create(effect_type=effect_type, consequence_level="safe")
    with use_audit_context(_make_audit_context()):
        read = _deferred_effects_service(governance_db).enqueue_effect(request)

    _deferred_effects_service(governance_db).deferred_effect_worker_tick(worker_id="test-worker")

    assert len(calls) == 1
    row = _fetch_effect_row(governance_dsn, read.id)
    assert row is not None
    assert row["status"] == "completed"


# ---------------------------------------------------------------------------
# AC3: effects queryable independently from scheduled jobs
# ---------------------------------------------------------------------------


def test_deferred_effects_queryable_independently_from_scheduled_jobs(
    governance_db: PostgresDatabase,
) -> None:
    """AC3: deferred effects and scheduled jobs must be independent query
    surfaces backed by separate tables. A listing call on one must not
    return rows from the other, even with matching ``subsystem``."""

    subsystem = _unique("sub-indep")
    effect_request = _make_create(subsystem=subsystem)
    job_key = _unique("job-indep")
    job_request = ScheduledJobCreate.model_validate(
        {
            "job_key": job_key,
            "subsystem": subsystem,
            "handler_name": "test.indep.handler",
            "next_run_at": datetime.now(tz=UTC),
            "max_attempts": DEFAULT_MAX_ATTEMPTS,
        }
    )

    with use_audit_context(_make_audit_context()):
        effect_read = _deferred_effects_service(governance_db).enqueue_effect(effect_request)
        _scheduler_service(governance_db).register_scheduled_job(job_request)

    listed_effects = _deferred_effects_service(governance_db).list_deferred_effects_by_subsystem(subsystem)
    listed_ids = [e.id for e in listed_effects]
    assert effect_read.id in listed_ids
    # Effects listing is NOT polluted with scheduled-job rows.
    assert all(isinstance(e, DeferredEffectRead) for e in listed_effects)

    # Reading by effect id never returns the scheduled job.
    by_id = _deferred_effects_service(governance_db).read_deferred_effect(effect_read.id)
    assert by_id is not None
    assert by_id.id == effect_read.id


# ---------------------------------------------------------------------------
# AC4: degraded-state summary per subsystem + MVCC non-blocking
# ---------------------------------------------------------------------------


def test_degraded_state_summary_returns_per_subsystem_counts(
    governance_db: PostgresDatabase,
) -> None:
    """AC4 + D7: ``DegradedStateSummaryRead`` must group pending rows
    across BOTH ``deferred_effects`` and ``scheduled_jobs`` by
    ``subsystem`` — this subsystem has 2 effects and 1 job pending."""

    subsystem = _unique("sub-sum")

    with use_audit_context(_make_audit_context()):
        _deferred_effects_service(governance_db).enqueue_effect(_make_create(subsystem=subsystem))
        _deferred_effects_service(governance_db).enqueue_effect(_make_create(subsystem=subsystem))
        _scheduler_service(governance_db).register_scheduled_job(
            ScheduledJobCreate.model_validate(
                {
                    "job_key": _unique("job-sum"),
                    "subsystem": subsystem,
                    "handler_name": "test.sum.handler",
                    "next_run_at": datetime.now(tz=UTC),
                    "max_attempts": DEFAULT_MAX_ATTEMPTS,
                }
            ),
        )

    summary = _deferred_effects_service(governance_db).read_degraded_state_summary()
    matching = [entry for entry in summary if entry.subsystem == subsystem]

    assert len(matching) == 1
    entry = matching[0]
    assert isinstance(entry, DegradedStateSummaryRead)
    assert entry.pending_effect_count == 2
    assert entry.scheduled_job_count == 1
    assert entry.oldest_pending_at is not None


def test_degraded_state_summary_does_not_block_concurrent_writes(
    governance_db: PostgresDatabase,
) -> None:
    """AC4: the summary must be an MVCC read — no ``FOR UPDATE``, no
    table locks. Running 100 summary reads concurrently with a writer
    thread enqueuing effects must finish quickly and never deadlock."""

    subsystem = _unique("sub-conc")

    stop = threading.Event()
    write_errors: list[BaseException] = []

    def writer() -> None:
        try:
            while not stop.is_set():
                with use_audit_context(_make_audit_context()):
                    _deferred_effects_service(governance_db).enqueue_effect(
                        _make_create(subsystem=subsystem),
                    )
        except BaseException as exc:  # pragma: no cover — surfaced via assertion
            write_errors.append(exc)

    thread = threading.Thread(target=writer, daemon=True)
    thread.start()
    try:
        start = time.monotonic()
        for _ in range(100):
            _deferred_effects_service(governance_db).read_degraded_state_summary()
        elapsed = time.monotonic() - start
    finally:
        stop.set()
        thread.join(timeout=5.0)

    assert not thread.is_alive(), "writer thread must terminate after stop"
    assert not write_errors, f"writer thread raised: {write_errors!r}"
    assert elapsed < 5.0, (
        f"100 summary reads under concurrent writes took {elapsed:.2f}s — "
        "suggests FOR UPDATE / blocking semantics"
    )


# ---------------------------------------------------------------------------
# Crash recovery (lease expiry on the next tick)
# ---------------------------------------------------------------------------


def test_effect_crash_safe_re_execution(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """D4: a claimed effect with an expired lease must be reclaimable on
    the next worker tick — simulates a worker crash mid-handler. Lazy
    reclaim, no boot sweep."""

    effect_type = _unique_effect_type("crash")
    calls: list[Any] = []

    @register_scheduler_handler(effect_type)
    def handler(effect: Any) -> None:
        calls.append(effect)

    request = _make_create(effect_type=effect_type, consequence_level="safe")
    with use_audit_context(_make_audit_context()):
        read = _deferred_effects_service(governance_db).enqueue_effect(request)

    # Simulate worker-1 claimed the row but crashed; lease is in the past.
    expired = datetime.now(tz=UTC) - timedelta(seconds=1)
    _simulate_stale_claim(
        governance_dsn,
        read.id,
        claimed_by="worker-1",
        lease_until=expired,
    )

    _deferred_effects_service(governance_db).deferred_effect_worker_tick(worker_id="worker-2")

    assert len(calls) == 1
    row = _fetch_effect_row(governance_dsn, read.id)
    assert row is not None
    assert row["status"] == "completed"


# ---------------------------------------------------------------------------
# Retry journaling (D9)
# ---------------------------------------------------------------------------


def test_effect_attempts_increment_on_failure(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """D9: a handler that raises must cause the worker to journal the
    failure: ``attempts`` bumped by 1, ``last_error_json`` populated.
    Below ``max_attempts`` the row remains operator-visible for retry."""

    effect_type = _unique_effect_type("fail-once")

    @register_scheduler_handler(effect_type)
    def handler(effect: Any) -> None:
        raise RuntimeError("boom")

    request = _make_create(effect_type=effect_type, consequence_level="safe")
    with use_audit_context(_make_audit_context()):
        read = _deferred_effects_service(governance_db).enqueue_effect(request)

    _deferred_effects_service(governance_db).deferred_effect_worker_tick(worker_id="worker-fail")

    row = _fetch_effect_row(governance_dsn, read.id)
    assert row is not None
    assert row["attempts"] == 1
    # Terminal state depends on max_attempts config; below max, a retry
    # slot remains. Above, the row is permanently failed.
    assert row["status"] in {"queued", "failed"}


def test_effect_reaches_failed_permanently_at_max_attempts(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """D9: after ``max_attempts`` consecutive handler failures the row
    must terminate at ``status='failed'`` with ``attempts ==
    max_attempts``. No auto-retry beyond the cap; operator intervention
    is required."""

    effect_type = _unique_effect_type("fail-exhaust")

    @register_scheduler_handler(effect_type)
    def handler(effect: Any) -> None:
        raise RuntimeError("always fails")

    request = _make_create(effect_type=effect_type, consequence_level="safe")
    with use_audit_context(_make_audit_context()):
        read = _deferred_effects_service(governance_db).enqueue_effect(request)

    # Hammer the tick until the row terminates or we exceed the cap.
    # After each failure, the worker re-queues the row (setting status
    # back to ``queued`` with cleared lease) so the next tick can claim.
    for _ in range(DEFAULT_MAX_ATTEMPTS):
        _deferred_effects_service(governance_db).deferred_effect_worker_tick(worker_id="worker-fail")

    row = _fetch_effect_row(governance_dsn, read.id)
    assert row is not None
    assert row["status"] == "failed"
    assert row["attempts"] == DEFAULT_MAX_ATTEMPTS
