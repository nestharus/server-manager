from __future__ import annotations

from collections.abc import Iterator
from http import HTTPStatus
from uuid import UUID, uuid4

import psycopg
import pytest
from httpx import AsyncClient

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from tests._authority_helpers import grant_authority


RUNS_URL = "/api/v1/permission-reconciliation/runs"
INTENTS_URL = "/api/v1/permission-intents"


def _audit_context() -> AuditContextRead:
    correlation_id = uuid4()
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=None,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=None,
        ),
    )


def _headers(actor_id: str, *, kind: str = "user", **extra: str) -> dict[str, str]:
    return {"X-Actor-Kind": kind, "X-Actor-Id": actor_id, **extra}


def _grant(
    db: PostgresDatabase,
    *,
    actor_id: str,
    permissions: frozenset[str],
    scope_kind: str = "global",
    scope_id: str | None = None,
) -> None:
    with use_audit_context(_audit_context()):
        grant_authority(
            db,
            grantee_id=actor_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            permissions=permissions,
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )


@pytest.fixture
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


async def _create_run(
    client: AsyncClient,
    *,
    actor_id: str = "operator",
    scope_kind: str = "global",
    scope_id: str | None = None,
    actor_kind: str = "user",
    originating_actor_kind: str | None = None,
    originating_actor_id: str | None = None,
) -> dict:
    payload = {
        "scope_kind": scope_kind,
        "scope_id": scope_id,
        "originating_actor_kind": originating_actor_kind,
        "originating_actor_id": originating_actor_id,
    }
    response = await client.post(
        RUNS_URL,
        json=payload,
        headers=_headers(actor_id, kind=actor_kind),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


async def _create_intent(
    client: AsyncClient,
    *,
    actor_id: str = "operator",
    role_id: str,
    permission_bits: str,
    scope_kind: str = "global",
    scope_id: str | None = None,
) -> dict:
    payload = {
        "kind": "guild_role",
        "scope_kind": scope_kind,
        "scope_id": scope_id,
        "role_id": role_id,
        "permission_bits": permission_bits,
        "reason": "seed",
        "temporary": False,
        "expires_at": None,
    }
    response = await client.post(
        INTENTS_URL,
        json=payload,
        headers=_headers(actor_id),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


@pytest.mark.asyncio
async def test_create_run_returns_201_and_etag_1(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC3: create run returns 201 with strong ETag '1'."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_reconciliation_run.write"}),
    )
    response = await migrated_async_client.post(
        RUNS_URL,
        json={"scope_kind": "global", "scope_id": None},
        headers=_headers("operator"),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    body = response.json()
    assert body["status"] == "requested"
    assert body["requested_by_kind"] == "user"
    assert body["requested_by_id"] == "operator"
    assert response.headers["etag"] == '"1"'


@pytest.mark.asyncio
async def test_create_run_requires_permission_reconciliation_run_write(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC3: creating a run without permission returns 403."""
    response = await migrated_async_client.post(
        RUNS_URL,
        json={"scope_kind": "global", "scope_id": None},
        headers=_headers("unprivileged"),
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_service_actor_create_run_uses_originating_actor_fields(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC3 (D12): service actor stamps requested_by from originating_actor_* body fields."""
    # The wu-028b migration seeds a grant for 'permission-reconciler', but
    # conftest.reset_governance_state truncates authority_grants between tests,
    # so re-grant here to assert the service-actor trust-headers behavior.
    _grant(
        governance_db,
        actor_id="permission-reconciler",
        permissions=frozenset({"permission_reconciliation_run.write"}),
    )
    response = await migrated_async_client.post(
        RUNS_URL,
        json={
            "scope_kind": "global",
            "scope_id": None,
            "originating_actor_kind": "user",
            "originating_actor_id": "moderator-3",
        },
        headers=_headers("permission-reconciler", kind="service"),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    body = response.json()
    assert body["requested_by_kind"] == "user"
    assert body["requested_by_id"] == "moderator-3"


@pytest.mark.asyncio
async def test_user_actor_create_run_ignores_originating_actor_fields(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC3 (D12): user actor keeps requested_by = actor headers even if body provides originating_*."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_reconciliation_run.write"}),
    )
    response = await migrated_async_client.post(
        RUNS_URL,
        json={
            "scope_kind": "global",
            "scope_id": None,
            "originating_actor_kind": "service",
            "originating_actor_id": "spoofed-bot",
        },
        headers=_headers("operator"),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    body = response.json()
    assert body["requested_by_kind"] == "user"
    assert body["requested_by_id"] == "operator"


@pytest.mark.asyncio
async def test_submit_snapshot_inserts_new_drift_and_advances_to_reconciled(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC3 (D4/D8): submitting a snapshot advances the run to reconciled and creates drift."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {
                "permission_intent.write",
                "permission_intent.read",
                "permission_reconciliation_run.write",
                "permission_drift.read",
            }
        ),
    )
    await _create_intent(
        migrated_async_client,
        role_id="role-1",
        permission_bits="8",
    )
    run = await _create_run(migrated_async_client)

    response = await migrated_async_client.post(
        f"{RUNS_URL}/{run['id']}/snapshots",
        json={
            "entries": [
                {
                    "kind": "guild_role",
                    "role_id": "role-1",
                    "permission_bits": "16",
                },
            ],
        },
        headers=_headers("operator"),
    )
    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["status"] == "reconciled"
    assert len(body["drift_ids"]) == 1
    # requested(1) -> snapshot_submitted(2) -> reconciled(3)
    assert response.headers["etag"] == '"3"'


@pytest.mark.asyncio
async def test_submit_snapshot_idempotent_on_duplicate_target(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC3 (D3): insert_permission_drift_batch dedupes by (run_id, role, kind, channel)."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {
                "permission_intent.write",
                "permission_intent.read",
                "permission_reconciliation_run.write",
                "permission_drift.read",
            }
        ),
    )
    await _create_intent(
        migrated_async_client, role_id="role-dup", permission_bits="8",
    )
    run = await _create_run(migrated_async_client)

    first = await migrated_async_client.post(
        f"{RUNS_URL}/{run['id']}/snapshots",
        json={
            "entries": [
                {
                    "kind": "guild_role",
                    "role_id": "role-dup",
                    "permission_bits": "16",
                },
            ],
        },
        headers=_headers("operator"),
    )
    assert first.status_code == HTTPStatus.OK, first.text
    drift_ids_first = first.json()["drift_ids"]
    assert len(drift_ids_first) == 1

    # Re-submitting against the same terminal run should replay the cached
    # result (see test_submit_snapshot_terminal_reconciled_replays_cached_result
    # for the dedicated assertion). Here, we assert the set of drift rows did
    # not grow.
    second = await migrated_async_client.post(
        f"{RUNS_URL}/{run['id']}/snapshots",
        json={
            "entries": [
                {
                    "kind": "guild_role",
                    "role_id": "role-dup",
                    "permission_bits": "16",
                },
            ],
        },
        headers=_headers("operator"),
    )
    assert second.status_code == HTTPStatus.OK, second.text
    assert second.json()["drift_ids"] == drift_ids_first


@pytest.mark.asyncio
async def test_submit_snapshot_terminal_reconciled_replays_cached_result(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC3 (D4): replaying against a reconciled run returns the cached read without mutating."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {
                "permission_intent.write",
                "permission_reconciliation_run.write",
                "permission_drift.read",
            }
        ),
    )
    await _create_intent(
        migrated_async_client, role_id="role-replay", permission_bits="8",
    )
    run = await _create_run(migrated_async_client)
    first = await migrated_async_client.post(
        f"{RUNS_URL}/{run['id']}/snapshots",
        json={
            "entries": [
                {
                    "kind": "guild_role",
                    "role_id": "role-replay",
                    "permission_bits": "16",
                },
            ],
        },
        headers=_headers("operator"),
    )
    assert first.status_code == HTTPStatus.OK
    first_etag = first.headers["etag"]

    second = await migrated_async_client.post(
        f"{RUNS_URL}/{run['id']}/snapshots",
        json={"entries": []},
        headers=_headers("operator"),
    )
    assert second.status_code == HTTPStatus.OK, second.text
    assert second.headers["etag"] == first_etag
    assert second.json()["status"] == "reconciled"


@pytest.mark.asyncio
async def test_submit_snapshot_failed_run_returns_409(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC3 (D4): re-submitting against a failed run returns 409."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {"permission_reconciliation_run.write", "permission_drift.read"}
        ),
    )
    run = await _create_run(migrated_async_client)
    # Manually mark the run failed at the projection layer. CodeRabbit
    # MAJOR 2: the tightened CHECK requires snapshot_submitted_at on
    # failed rows, so populate it alongside failed_at.
    with psycopg.connect(governance_dsn) as connection:
        connection.execute(
            """
            UPDATE permission_reconciliation_runs
               SET status = 'failed',
                   snapshot_submitted_at = CURRENT_TIMESTAMP,
                   failed_at = CURRENT_TIMESTAMP,
                   failure_reason = 'simulated failure'
             WHERE id = %s
            """,
            (run["id"],),
        )
        connection.commit()

    response = await migrated_async_client.post(
        f"{RUNS_URL}/{run['id']}/snapshots",
        json={"entries": []},
        headers=_headers("operator"),
    )
    assert response.status_code == HTTPStatus.CONFLICT, response.text
    assert response.json()["code"] == "reconciliation_run_conflict"


@pytest.mark.asyncio
async def test_submit_snapshot_not_requested_state_returns_409(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC3 (D4): a run in snapshot_submitted state returns 409 on re-submission."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {"permission_reconciliation_run.write", "permission_drift.read"}
        ),
    )
    run = await _create_run(migrated_async_client)
    with psycopg.connect(governance_dsn) as connection:
        connection.execute(
            """
            UPDATE permission_reconciliation_runs
               SET status = 'snapshot_submitted',
                   snapshot_submitted_at = CURRENT_TIMESTAMP
             WHERE id = %s
            """,
            (run["id"],),
        )
        connection.commit()

    response = await migrated_async_client.post(
        f"{RUNS_URL}/{run['id']}/snapshots",
        json={"entries": []},
        headers=_headers("operator"),
    )
    assert response.status_code == HTTPStatus.CONFLICT, response.text
    assert response.json()["code"] == "reconciliation_run_conflict"


@pytest.mark.asyncio
async def test_submit_snapshot_rejects_duplicate_snapshot_keys_422(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC3: duplicate (kind, role_id, channel_id) in the request body is rejected at 422."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_reconciliation_run.write"}),
    )
    run = await _create_run(migrated_async_client)
    response = await migrated_async_client.post(
        f"{RUNS_URL}/{run['id']}/snapshots",
        json={
            "entries": [
                {
                    "kind": "guild_role",
                    "role_id": "role-dup",
                    "permission_bits": "8",
                },
                {
                    "kind": "guild_role",
                    "role_id": "role-dup",
                    "permission_bits": "16",
                },
            ],
        },
        headers=_headers("operator"),
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.asyncio
async def test_submit_snapshot_records_run_failed_on_error(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3 (D4): if the diff/insert raises, the run is advanced to failed and the error bubbles."""
    from app.repositories.permissions import PermissionsRepository

    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {"permission_reconciliation_run.write", "permission_drift.read"}
        ),
    )
    run = await _create_run(migrated_async_client)

    def failing_batch(*args: object, **kwargs: object) -> list[UUID]:
        raise RuntimeError("forced diff failure")

    monkeypatch.setattr(
        PermissionsRepository, "_insert_permission_drift_batch_on", failing_batch,
    )

    # Starlette's ServerErrorMiddleware produces a 500 body but re-raises the
    # exception afterwards; httpx.ASGITransport (raise_app_exceptions=True by
    # default) surfaces that re-raise here. The behavior we care about is the
    # side effect: the run transitioned to 'failed' before the exception was
    # re-raised.
    with pytest.raises(RuntimeError, match="forced diff failure"):
        await migrated_async_client.post(
            f"{RUNS_URL}/{run['id']}/snapshots",
            json={"entries": []},
            headers=_headers("operator"),
        )

    with psycopg.connect(governance_dsn) as connection:
        row = connection.execute(
            "SELECT status FROM permission_reconciliation_runs WHERE id = %s",
            (run["id"],),
        ).fetchone()
    assert row is not None
    assert row[0] == "failed"


@pytest.mark.asyncio
async def test_submit_snapshot_diff_algorithm_handles_both_directions(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC3 (D8): diff algorithm emits drift for intent-only, entry-only, and mismatched pairs."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {
                "permission_intent.write",
                "permission_reconciliation_run.write",
                "permission_drift.read",
            }
        ),
    )
    # Two intents: role-mismatch (will differ), role-missing (entry omitted).
    await _create_intent(
        migrated_async_client, role_id="role-mismatch", permission_bits="8",
    )
    await _create_intent(
        migrated_async_client, role_id="role-missing", permission_bits="4",
    )
    run = await _create_run(migrated_async_client)

    response = await migrated_async_client.post(
        f"{RUNS_URL}/{run['id']}/snapshots",
        json={
            "entries": [
                {
                    "kind": "guild_role",
                    "role_id": "role-mismatch",
                    "permission_bits": "16",
                },
                {
                    "kind": "guild_role",
                    "role_id": "role-orphan",
                    "permission_bits": "32",
                },
            ],
        },
        headers=_headers("operator"),
    )
    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["status"] == "reconciled"

    with psycopg.connect(governance_dsn) as connection:
        rows = connection.execute(
            """
            SELECT role_id, permission_intent_id IS NOT NULL AS linked,
                   actual_bits, intended_bits
              FROM permission_drift
             WHERE reconciliation_run_id = %s
             ORDER BY role_id
            """,
            (run["id"],),
        ).fetchall()

    by_role = {row[0]: row for row in rows}
    assert set(by_role.keys()) == {"role-mismatch", "role-missing", "role-orphan"}
    # mismatched: linked, both masks populated
    mismatch = by_role["role-mismatch"]
    assert mismatch[1] is True
    assert int(mismatch[2]) == 16
    assert int(mismatch[3]) == 8
    # intent-only: linked, actual cleared to 0, intended carried from intent
    missing = by_role["role-missing"]
    assert missing[1] is True
    assert int(missing[2]) == 0
    assert int(missing[3]) == 4
    # entry-only: orphan, intended null, actual from entry
    orphan = by_role["role-orphan"]
    assert orphan[1] is False
    assert int(orphan[2]) == 32
    assert orphan[3] is None


@pytest.mark.asyncio
async def test_create_run_rejects_blank_originating_actor_kind(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """CodeRabbit MAJOR 4: whitespace-only originating_actor_kind returns 422."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_reconciliation_run.write"}),
    )
    response = await migrated_async_client.post(
        RUNS_URL,
        json={
            "scope_kind": "global",
            "scope_id": None,
            "originating_actor_kind": "   ",
            "originating_actor_id": "some-bot",
        },
        headers=_headers("operator"),
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.asyncio
async def test_create_run_rejects_mismatched_originating_actor_pair(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """CodeRabbit MAJOR 4: originating_actor_{kind,id} must be both-or-neither."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_reconciliation_run.write"}),
    )
    response = await migrated_async_client.post(
        RUNS_URL,
        json={
            "scope_kind": "global",
            "scope_id": None,
            "originating_actor_kind": "service",
            "originating_actor_id": None,
        },
        headers=_headers("operator"),
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
