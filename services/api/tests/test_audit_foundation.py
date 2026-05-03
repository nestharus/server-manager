"""Contract tests for WU-003: audit + correlation context foundation.

These tests pin the public service surface without reaching into any
new repository, service, or migration module. Everything runs against
real Postgres via the shared testcontainers fixtures and exercises
``mutate_entity()`` end-to-end so the behavior under test is the
contract the code agent must satisfy.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import partial
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from httpx import AsyncClient
from psycopg import Connection
from psycopg.rows import dict_row

from app.contracts.audit import (
    AuditContextRead,
    AuditEntryRead,
    CorrelationHeadersRead,
)
from app.contracts.mutations import (
    MissingAggregateError,
    MissingCorrelationContextError,
    MutationRequest,
    StateChangeDraft,
)
from app.core.context import get_current_audit_context, use_audit_context
from app.repositories.audit import AuditRepository
from app.repositories.db import PostgresDatabase
from app.services.audit import AuditService
from app.services.mutations import mutate_entity


AGGREGATE_TYPE = "test_audit_aggregate"


def _make_audit_context(
    *,
    correlation_id: UUID | None = None,
    causation_id: UUID | None = None,
) -> AuditContextRead:
    cid = correlation_id or uuid4()
    headers = CorrelationHeadersRead(
        x_correlation_id=cid,
        x_causation_id=causation_id,
    )
    return AuditContextRead(
        correlation_id=cid,
        causation_id=causation_id,
        headers=headers,
    )


def _make_request(
    *,
    expected_version: int = 0,
    correlation_id: UUID | None = None,
    causation_id: UUID | None = None,
) -> MutationRequest:
    return MutationRequest(
        expected_version=expected_version,
        actor_kind="user",
        actor_id="u1",
        reason_text=None,
        request_surface="service:test.audit",
        correlation_id=correlation_id,
        causation_id=causation_id,
    )


def _noop_projection(_connection: Connection[Any]) -> StateChangeDraft:
    return StateChangeDraft(
        change_type="test.audit.recorded",
        payload_json={"value": "ok"},
    )


def _raising_projection(_connection: Connection[Any]) -> StateChangeDraft:
    raise RuntimeError("projection exploded")


def _fetch_actions(database_url: str) -> list[dict[str, Any]]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT id, aggregate_type, aggregate_id, actor_kind, actor_id,
                   status, correlation_id, causation_id, scope_kind, scope_id,
                   request_surface, reason_text, request_json, recorded_at
            FROM activity_actions
            ORDER BY id
            """
        ).fetchall()


def _fetch_head(database_url: str, *, aggregate_id: str) -> dict[str, Any] | None:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT aggregate_type, aggregate_id, current_seq, latest_change_id
            FROM aggregate_heads
            WHERE aggregate_type = %s AND aggregate_id = %s
            """,
            (AGGREGATE_TYPE, aggregate_id),
        ).fetchone()


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Middleware (AC1 — correlation propagation across HTTP boundary)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "header_value",
    [None, "not-a-uuid"],
    ids=["missing", "malformed"],
)
async def test_correlation_middleware_generates_root_correlation_for_missing_or_malformed_header(
    migrated_async_client: AsyncClient,
    header_value: str | None,
) -> None:
    """A missing or malformed ``X-Correlation-Id`` must not 5xx.

    The middleware generates a fresh UUID and surfaces it back on the
    response so tests (and downstream systems) can correlate.
    """

    headers = {"X-Correlation-Id": header_value} if header_value else {}
    response = await migrated_async_client.get(
        "/api/v1/system/migrations/current",
        headers=headers,
    )

    assert response.status_code == 200, response.text

    echoed = response.headers.get("x-correlation-id")
    assert echoed is not None, "middleware must echo X-Correlation-Id on response"
    # Must be a parseable UUID — middleware generated a root correlation.
    UUID(echoed)
    if header_value is not None:
        assert echoed != header_value


@pytest.mark.asyncio
async def test_correlation_middleware_preserves_valid_header(
    migrated_async_client: AsyncClient,
) -> None:
    """A valid UUID in ``X-Correlation-Id`` must pass through unchanged."""

    known = uuid4()
    response = await migrated_async_client.get(
        "/api/v1/system/migrations/current",
        headers={"X-Correlation-Id": str(known)},
    )

    assert response.status_code == 200, response.text
    echoed = response.headers.get("x-correlation-id")
    assert echoed is not None
    assert UUID(echoed) == known


# ---------------------------------------------------------------------------
# ContextVar helper (D3 — explicit per-call audit context)
# ---------------------------------------------------------------------------


def test_use_audit_context_restores_outer_context_on_exit() -> None:
    """Nested ``use_audit_context(...)`` must restore the outer value on exit.

    The helper uses the token-pair ``set/reset`` pattern; it never calls
    ``ContextVar.set(None)`` as a cleanup mechanism.
    """

    ctx_a = _make_audit_context()
    ctx_b = _make_audit_context()

    with use_audit_context(ctx_a):
        assert get_current_audit_context() == ctx_a

        with use_audit_context(ctx_b):
            assert get_current_audit_context() == ctx_b

        # Outer context must be restored after the inner exits.
        assert get_current_audit_context() == ctx_a

    # Outside every helper: back to the baseline (None for a clean test).
    assert get_current_audit_context() is None


# ---------------------------------------------------------------------------
# mutate_entity() correlation + bootstrap contracts
# ---------------------------------------------------------------------------


def test_mutate_entity_raises_missing_correlation_context_error_outside_request_lifecycle(
    governance_db: PostgresDatabase,
) -> None:
    """With no request-scope context and no explicit override, the primitive
    must raise ``MissingCorrelationContextError`` — it does NOT invent a
    correlation uuid (that is middleware's sole responsibility)."""

    # Sanity: no outer context active.
    assert get_current_audit_context() is None

    with pytest.raises(MissingCorrelationContextError):
        mutate_entity(
            db=governance_db,
            aggregate_type=AGGREGATE_TYPE,
            aggregate_id="test:no-ctx:1",
            request=_make_request(expected_version=0),
            action_type="test.noop",
            action_payload={},
            payload_allowlist=None,
            mutate_projection=_noop_projection,
        )


def test_mutate_entity_bootstraps_head_for_new_aggregate_at_expected_version_zero(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """First write against a brand-new aggregate must self-bootstrap.

    ``expected_version == 0`` + missing head row = create head, then mutate
    from 0 → 1. No pre-seeding required by callers.
    """

    aggregate_id = "test:bootstrap:1"

    assert _fetch_head(governance_dsn, aggregate_id=aggregate_id) is None

    ctx = _make_audit_context()
    with use_audit_context(ctx):
        result = mutate_entity(
            db=governance_db,
            aggregate_type=AGGREGATE_TYPE,
            aggregate_id=aggregate_id,
            request=_make_request(expected_version=0),
            action_type="test.bootstrap",
            action_payload={},
            payload_allowlist=None,
            mutate_projection=_noop_projection,
        )

    assert result.version == 1
    assert result.etag == '"1"'

    head = _fetch_head(governance_dsn, aggregate_id=aggregate_id)
    assert head is not None
    assert head["current_seq"] == 1


def test_mutate_entity_raises_missing_aggregate_error_for_new_id_at_nonzero_expected_version(
    governance_db: PostgresDatabase,
) -> None:
    """An ``expected_version >= 1`` call against a missing head must raise
    ``MissingAggregateError`` — it must not auto-bootstrap the head."""

    ctx = _make_audit_context()
    with use_audit_context(ctx):
        with pytest.raises(MissingAggregateError) as exc_info:
            mutate_entity(
                db=governance_db,
                aggregate_type=AGGREGATE_TYPE,
                aggregate_id="test:missing:1",
                request=_make_request(expected_version=5),
                action_type="test.missing",
                action_payload={},
                payload_allowlist=None,
                mutate_projection=_noop_projection,
            )

    assert exc_info.value.aggregate_type == AGGREGATE_TYPE
    assert exc_info.value.aggregate_id == "test:missing:1"


# ---------------------------------------------------------------------------
# Correlation/scope columns on activity_actions
# ---------------------------------------------------------------------------


def test_activity_actions_carries_correlation_and_scope_columns(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """After a mutate, the persisted ``activity_actions`` row must carry the
    exact correlation/causation/scope metadata the primitive resolved."""

    correlation_id = uuid4()
    causation_id = uuid4()

    with use_audit_context(_make_audit_context(correlation_id=correlation_id, causation_id=causation_id)):
        mutate_entity(
            db=governance_db,
            aggregate_type=AGGREGATE_TYPE,
            aggregate_id="test:scope:1",
            request=_make_request(expected_version=0),
            action_type="test.scope",
            action_payload={},
            payload_allowlist=None,
            mutate_projection=_noop_projection,
            scope_kind="chapter",
            scope_id="ch-1",
        )

    actions = _fetch_actions(governance_dsn)
    assert len(actions) == 1
    action = actions[0]

    assert action["status"] == "accepted"
    assert action["aggregate_type"] == AGGREGATE_TYPE
    assert action["aggregate_id"] == "test:scope:1"
    assert UUID(str(action["correlation_id"])) == correlation_id
    assert UUID(str(action["causation_id"])) == causation_id
    assert action["scope_kind"] == "chapter"
    assert action["scope_id"] == "ch-1"
    assert action["request_surface"] == "service:test.audit"


def test_failed_mutation_records_correlation_on_failure_audit(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC1 trace: when the projection callback raises, the ``failed`` audit row
    must still carry the resolved correlation/causation from the calling
    context — not a freshly invented uuid."""

    correlation_id = uuid4()
    causation_id = uuid4()

    with use_audit_context(_make_audit_context(correlation_id=correlation_id, causation_id=causation_id)):
        with pytest.raises(RuntimeError):
            mutate_entity(
                db=governance_db,
                aggregate_type=AGGREGATE_TYPE,
                aggregate_id="test:fail:1",
                request=_make_request(expected_version=0),
                action_type="test.fail",
                action_payload={},
                payload_allowlist=None,
                mutate_projection=_raising_projection,
            )

    actions = _fetch_actions(governance_dsn)
    failed = [a for a in actions if a["status"] == "failed"]
    assert len(failed) == 1, f"expected exactly one failed audit row, got {actions}"

    failure = failed[0]
    assert UUID(str(failure["correlation_id"])) == correlation_id
    assert UUID(str(failure["causation_id"])) == causation_id


# ---------------------------------------------------------------------------
# AuditEntryRead read projection (AC1)
# ---------------------------------------------------------------------------


def test_audit_entry_read_is_one_to_one_projection_of_activity_actions(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """``AuditService.get_audit_entry(id)`` must return an ``AuditEntryRead`` whose
    fields mirror the ``activity_actions`` row exactly. This pins the
    projection-vs-second-authority boundary from synthesis D1."""

    correlation_id = uuid4()
    with use_audit_context(_make_audit_context(correlation_id=correlation_id)):
        mutate_entity(
            db=governance_db,
            aggregate_type=AGGREGATE_TYPE,
            aggregate_id="test:project:1",
            request=_make_request(expected_version=0),
            action_type="test.project",
            action_payload={"safe": 1, "secret": "x"},
            payload_allowlist={"safe"},
            mutate_projection=_noop_projection,
            scope_kind="chapter",
            scope_id="ch-x",
        )

    actions = _fetch_actions(governance_dsn)
    assert len(actions) == 1
    raw = actions[0]

    service = AuditService(
        audit_repo=AuditRepository(governance_db),
        mutations_callable=partial(mutate_entity, db=governance_db),
    )
    entry = service.get_audit_entry(raw["id"])

    assert isinstance(entry, AuditEntryRead)
    assert entry.id == raw["id"]
    assert entry.action_type == "test.project"
    assert entry.aggregate_type == AGGREGATE_TYPE
    assert entry.aggregate_id == "test:project:1"
    assert entry.actor_kind == "user"
    assert entry.actor_id == "u1"
    assert entry.status == "accepted"
    assert entry.scope_kind == "chapter"
    assert entry.scope_id == "ch-x"
    assert entry.request_surface == "service:test.audit"
    assert entry.reason_text is None
    assert entry.correlation.correlation_id == correlation_id
