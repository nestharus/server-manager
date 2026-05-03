"""SLICE-009 WU-016A — Audit Query API (AC1, AC2, AC3).

Exercises the three HTTP endpoints that ship in SLICE-009:

- ``GET /api/v1/audit/{entry_id}`` -> ``AuditEntryRead``
- ``GET /api/v1/audit?correlation_id={uuid}`` -> ``AuditEntryListRead``
- ``GET /api/v1/audit/{entry_id}/chain`` -> ``AuditEntryListRead``

All tests run against real Postgres via ``migrated_async_client`` and
seed the audit substrate by invoking ``mutate_entity()`` under a real
``use_audit_context(...)``. No mocking — audit rows are written through
the production substrate, then queried through the production routes.
"""

from __future__ import annotations

from collections.abc import Iterator
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio
from httpx import AsyncClient
from psycopg import Connection
from psycopg.rows import dict_row

from app.contracts.audit import (
    AuditContextRead,
    AuditEntryListRead,
    AuditEntryRead,
    CorrelationHeadersRead,
)
from app.contracts.mutations import MutationRequest, StateChangeDraft
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.audit_queries import (
    AuditChainTooLargeError,  # noqa: F401 — imported to pin error-contract name
    AuditQueriesService,  # noqa: F401 — imported to pin service symbol
)
from tests._authority_helpers import grant_authority
from app.services.mutations import mutate_entity


BASE_URL = "/api/v1/audit"
AGGREGATE_TYPE = "test_audit_api_aggregate"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _actor_headers(
    *,
    actor_id: str = "admin",
    actor_kind: str = "user",
) -> dict[str, str]:
    return {"X-Actor-Kind": actor_kind, "X-Actor-Id": actor_id}


def _make_audit_context(
    *,
    correlation_id: UUID | None = None,
    causation_id: UUID | None = None,
) -> AuditContextRead:
    cid = correlation_id if correlation_id is not None else uuid4()
    return AuditContextRead(
        correlation_id=cid,
        causation_id=causation_id,
        headers=CorrelationHeadersRead(
            x_correlation_id=cid,
            x_causation_id=causation_id,
        ),
    )


def _noop_projection(_connection: Connection[Any]) -> StateChangeDraft:
    return StateChangeDraft(
        change_type="test.audit.recorded",
        payload_json={"value": "ok"},
    )


def _grant_audit_permission(
    db: PostgresDatabase,
    *,
    actor_id: str = "admin",
    actor_kind: str = "user",
) -> None:
    """Grant the actor the global-scope ``audit.read`` permission required
    by the SLICE-009 authority guard."""

    with use_audit_context(_make_audit_context()):
        grant_authority(
            db=db,
            grantee_id=actor_id,
            scope_kind="global",
            scope_id=None,
            permissions=frozenset({"audit.read"}),
            expires_at=None,
            predecessor_grant_id=None,
            actor=(actor_kind, "root"),
        )


def _seed_mutation(
    db: PostgresDatabase,
    *,
    correlation_id: UUID,
    causation_id: UUID | None = None,
    aggregate_id: str = "test:audit-api:1",
    action_type: str = "test.audit.recorded",
) -> int:
    """Run a no-op ``mutate_entity`` under the given correlation context and
    return the freshly-created ``activity_actions.id`` value.

    The mutation always bootstraps its own aggregate head (expected_version=0),
    so the caller does not need to pre-seed ``aggregate_heads``.
    """

    request = MutationRequest(
        expected_version=0,
        actor_kind="user",
        actor_id="u1",
        reason_text=None,
        request_surface="service:test.audit-api",
    )
    with use_audit_context(
        _make_audit_context(
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
    ):
        mutate_entity(
            db=db,
            aggregate_type=AGGREGATE_TYPE,
            aggregate_id=aggregate_id,
            request=request,
            action_type=action_type,
            action_payload={},
            payload_allowlist=None,
            mutate_projection=_noop_projection,
            scope_kind="chapter",
            scope_id="ch-1",
        )

    # Look up the latest-accepted row for this correlation and aggregate to
    # return a deterministic id to the test. We fetch by correlation + scope
    # to avoid coupling to insertion order across concurrent seeds.
    with db.connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                """
                SELECT id FROM activity_actions
                WHERE correlation_id = %s
                  AND aggregate_id = %s
                  AND status = 'accepted'
                ORDER BY recorded_at DESC, id DESC
                LIMIT 1
                """,
                (str(correlation_id), aggregate_id),
            ).fetchone()
    assert row is not None, "mutate_entity did not persist an accepted row"
    return int(row["id"])


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


@pytest_asyncio.fixture()
async def audit_client(
    migrated_async_client: AsyncClient,
    governance_dsn: str,  # noqa: ARG001 — forces governance truncation
) -> AsyncClient:
    return migrated_async_client


# ---------------------------------------------------------------------------
# GET /api/v1/audit/{entry_id} — single-entry read (AC3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_audit_entry_requires_audit_read_permission(
    audit_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC3: without an ``audit.read`` grant the single-entry read returns 403.

    The endpoint must delegate to the existing ``RequireAuthority`` guard
    rather than short-circuit permission evaluation locally.
    """

    correlation_id = uuid4()
    entry_id = _seed_mutation(governance_db, correlation_id=correlation_id)

    response = await audit_client.get(
        f"{BASE_URL}/{entry_id}", headers=_actor_headers()
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text


@pytest.mark.asyncio
async def test_get_audit_entry_allows_with_global_audit_read_grant(
    audit_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC3: with the global ``audit.read`` grant, the endpoint returns 200
    and the response body parses cleanly into ``AuditEntryRead``."""

    correlation_id = uuid4()
    entry_id = _seed_mutation(governance_db, correlation_id=correlation_id)
    _grant_audit_permission(governance_db)

    response = await audit_client.get(
        f"{BASE_URL}/{entry_id}", headers=_actor_headers()
    )

    assert response.status_code == HTTPStatus.OK, response.text
    entry = AuditEntryRead.model_validate(response.json())
    assert entry.id == entry_id
    assert entry.correlation.correlation_id == correlation_id


@pytest.mark.asyncio
async def test_get_audit_entry_returns_404_for_unknown_id(
    audit_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Unknown entry_id -> 404 (after the authority guard has passed)."""

    _grant_audit_permission(governance_db)

    response = await audit_client.get(
        f"{BASE_URL}/999999999", headers=_actor_headers()
    )

    assert response.status_code == HTTPStatus.NOT_FOUND, response.text


@pytest.mark.asyncio
async def test_get_audit_entry_requires_actor_identity_header(
    audit_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC3: without X-Actor-* headers the guard must return 401
    (``actor_identity_missing``) before permission evaluation runs."""

    correlation_id = uuid4()
    entry_id = _seed_mutation(governance_db, correlation_id=correlation_id)
    # Even with the permission granted, absence of actor identity is 401.
    _grant_audit_permission(governance_db)

    response = await audit_client.get(f"{BASE_URL}/{entry_id}")

    assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text


# ---------------------------------------------------------------------------
# GET /api/v1/audit?correlation_id=... — correlation listing (AC1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_audit_by_correlation_returns_full_chain_ordered_ascending(
    audit_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: seeding three entries under the same correlation returns all
    three ordered chronologically (``recorded_at ASC, id ASC``), with
    ``total=3`` on the response envelope."""

    correlation_id = uuid4()
    ids = [
        _seed_mutation(
            governance_db,
            correlation_id=correlation_id,
            aggregate_id=f"test:audit-api:chain-{index}",
        )
        for index in range(3)
    ]
    _grant_audit_permission(governance_db)

    response = await audit_client.get(
        BASE_URL,
        params={"correlation_id": str(correlation_id)},
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = AuditEntryListRead.model_validate(response.json())
    assert body.total == 3
    assert [entry.id for entry in body.items] == ids
    for entry in body.items:
        assert entry.correlation.correlation_id == correlation_id


@pytest.mark.asyncio
async def test_list_audit_by_correlation_empty_returns_zero_items(
    audit_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """An unknown correlation_id returns 200 with ``items=[]`` and ``total=0``,
    not 404. Empty is a valid result, not an error."""

    _grant_audit_permission(governance_db)
    missing_correlation = uuid4()

    response = await audit_client.get(
        BASE_URL,
        params={"correlation_id": str(missing_correlation)},
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = AuditEntryListRead.model_validate(response.json())
    assert body.total == 0
    assert body.items == []


@pytest.mark.asyncio
async def test_list_audit_by_correlation_filters_to_exact_correlation(
    audit_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Two distinct correlations: the query must return only entries that
    match the exact requested correlation, never bleeding across."""

    correlation_a = uuid4()
    correlation_b = uuid4()
    id_a1 = _seed_mutation(
        governance_db, correlation_id=correlation_a,
        aggregate_id="test:audit-api:corr-a1",
    )
    id_a2 = _seed_mutation(
        governance_db, correlation_id=correlation_a,
        aggregate_id="test:audit-api:corr-a2",
    )
    id_b = _seed_mutation(
        governance_db, correlation_id=correlation_b,
        aggregate_id="test:audit-api:corr-b1",
    )
    _grant_audit_permission(governance_db)

    response = await audit_client.get(
        BASE_URL,
        params={"correlation_id": str(correlation_a)},
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = AuditEntryListRead.model_validate(response.json())
    returned_ids = {entry.id for entry in body.items}
    assert returned_ids == {id_a1, id_a2}
    assert id_b not in returned_ids
    assert body.total == 2


@pytest.mark.asyncio
async def test_list_audit_by_correlation_enforces_1000_row_cap(
    audit_client: AsyncClient,
    governance_dsn: str,
    governance_db: PostgresDatabase,
) -> None:
    """D5: a correlation trace that exceeds 1000 rows must respond with
    413 Payload Too Large. To avoid running 1001 ``mutate_entity`` calls
    in CI, bulk-insert 1001 minimal ``activity_actions`` rows sharing the
    same correlation, then query through the production endpoint."""

    correlation_id = uuid4()
    _grant_audit_permission(governance_db)

    with psycopg.connect(governance_dsn, autocommit=True) as conn:
        rows_payload = [
            (
                "accepted",
                AGGREGATE_TYPE,
                f"test:audit-api:cap:{index}",
                "user",
                "u1",
                "test.audit.cap",
                str(correlation_id),
                None,
                "chapter",
                "ch-1",
                "service:test.audit-api",
                None,
                "{}",
            )
            for index in range(1001)
        ]
        conn.cursor().executemany(
            """
            INSERT INTO activity_actions (
                status, aggregate_type, aggregate_id,
                actor_kind, actor_id, action_type,
                correlation_id, causation_id,
                scope_kind, scope_id, request_surface,
                reason_text, request_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            rows_payload,
        )

    response = await audit_client.get(
        BASE_URL,
        params={"correlation_id": str(correlation_id)},
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE, response.text


@pytest.mark.asyncio
async def test_list_audit_by_correlation_invalid_uuid_returns_400(
    audit_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """A ``correlation_id`` query param that is not a valid UUID returns
    400 Bad Request — the proposal explicitly binds invalid-UUID parsing
    to 400 rather than FastAPI's default 422 shape."""

    _grant_audit_permission(governance_db)

    response = await audit_client.get(
        BASE_URL,
        params={"correlation_id": "not-a-uuid"},
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST, response.text


# ---------------------------------------------------------------------------
# GET /api/v1/audit/{entry_id}/chain — entry-chain listing (AC2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_chain_returns_same_correlation_ordered_oldest_to_newest(
    audit_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC2 (Phase 1 semantics per synthesis D4): ``/chain`` returns the full
    correlation trace ordered oldest to newest. Given a chain of 5 entries
    sharing the same correlation, querying the middle entry's chain returns
    all 5 in ``recorded_at ASC, id ASC`` order."""

    correlation_id = uuid4()
    ids = [
        _seed_mutation(
            governance_db,
            correlation_id=correlation_id,
            aggregate_id=f"test:audit-api:link-{index}",
        )
        for index in range(5)
    ]
    _grant_audit_permission(governance_db)

    middle_entry_id = ids[2]

    response = await audit_client.get(
        f"{BASE_URL}/{middle_entry_id}/chain",
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = AuditEntryListRead.model_validate(response.json())
    assert body.total == 5
    assert [entry.id for entry in body.items] == ids


@pytest.mark.asyncio
async def test_audit_chain_includes_the_queried_entry(
    audit_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC2: the seed entry itself must appear inside its own chain result."""

    correlation_id = uuid4()
    ids = [
        _seed_mutation(
            governance_db,
            correlation_id=correlation_id,
            aggregate_id=f"test:audit-api:include-{index}",
        )
        for index in range(3)
    ]
    _grant_audit_permission(governance_db)

    target_entry_id = ids[1]

    response = await audit_client.get(
        f"{BASE_URL}/{target_entry_id}/chain",
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = AuditEntryListRead.model_validate(response.json())
    returned_ids = {entry.id for entry in body.items}
    assert target_entry_id in returned_ids


@pytest.mark.asyncio
async def test_audit_chain_404_for_unknown_entry(
    audit_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Unknown seed entry -> 404 (after the authority guard has passed)."""

    _grant_audit_permission(governance_db)

    response = await audit_client.get(
        f"{BASE_URL}/999999999/chain",
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.NOT_FOUND, response.text


@pytest.mark.asyncio
async def test_audit_chain_correlation_with_two_unrelated_entries_not_included(
    audit_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Entries belonging to a different correlation must never appear in the
    chain result of an entry from a separate correlation."""

    correlation_a = uuid4()
    correlation_b = uuid4()
    id_a = _seed_mutation(
        governance_db, correlation_id=correlation_a,
        aggregate_id="test:audit-api:unrelated-a",
    )
    id_b = _seed_mutation(
        governance_db, correlation_id=correlation_b,
        aggregate_id="test:audit-api:unrelated-b",
    )
    _grant_audit_permission(governance_db)

    response = await audit_client.get(
        f"{BASE_URL}/{id_a}/chain",
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = AuditEntryListRead.model_validate(response.json())
    returned_ids = {entry.id for entry in body.items}
    assert id_a in returned_ids
    assert id_b not in returned_ids
    for entry in body.items:
        assert entry.correlation.correlation_id == correlation_a
