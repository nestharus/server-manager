from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from httpx import AsyncClient
from psycopg.rows import dict_row

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.permissions import GuildRolePermissionIntentCreate
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.authority import grant_authority
from app.services.scheduler import SchedulerLoop
from app.tasks.permission_expiry import permission_expiry_worker_tick


DRIFT_URL = "/api/v1/permission-drift"
EXPIRE_URL = "/api/v1/permission-intents/expire/run"


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


def _grant_expirer(db: PostgresDatabase) -> None:
    _grant(
        db,
        actor_id="permission-expirer",
        permissions=frozenset({"permission_intent.write", "permission_drift.write"}),
    )


def _seed_temporary_intent(
    db: PostgresDatabase,
    app: Any,
    *,
    actor_id: str | None = None,
    scope_kind: str = "global",
    scope_id: str | None = None,
    role_id: str = "role-1",
    temporary: bool = True,
    expires_at: datetime | None = None,
) -> Any:
    resolved_actor_id = actor_id or f"intent-seeder:{role_id}"
    _grant(
        db,
        actor_id=resolved_actor_id,
        permissions=frozenset({"permission_intent.write"}),
        scope_kind=scope_kind,
        scope_id=scope_id,
    )
    request = GuildRolePermissionIntentCreate(
        kind="guild_role",
        scope_kind=scope_kind,
        scope_id=scope_id,
        role_id=role_id,
        permission_bits="4",
        reason="temporary access",
        temporary=temporary,
        expires_at=expires_at,
    )
    with use_audit_context(_audit_context()):
        from app.services.permissions import PermissionsService

        permissions_service = app.state.container.services.permissions()
        assert isinstance(permissions_service, PermissionsService)
        intent, _ = permissions_service.create_permission_intent(
            request,
            actor=ActorIdentity(actor_kind="user", actor_id=resolved_actor_id),
        )
    return intent


def _fetch_drift_count(governance_dsn: str) -> int:
    with psycopg.connect(governance_dsn) as conn:
        row = conn.execute("SELECT COUNT(*) FROM permission_drift").fetchone()
    assert row is not None
    return int(row[0])


def _fetch_latest_action(governance_dsn: str, *, action_type: str) -> dict[str, Any]:
    with psycopg.connect(governance_dsn, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT actor_kind, actor_id, request_json
            FROM activity_actions
            WHERE action_type = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (action_type,),
        ).fetchone()
    assert row is not None
    return row


def _fetch_change_types(governance_dsn: str, *, aggregate_id: str) -> list[str]:
    with psycopg.connect(governance_dsn, row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            SELECT change_type
            FROM activity_state_changes
            WHERE aggregate_type = 'permission_drift'
              AND aggregate_id = %s
            ORDER BY aggregate_seq
            """,
            (aggregate_id,),
        ).fetchall()
    return [row["change_type"] for row in rows]


def test_worker_creates_drift_sets_expired_at_and_installs_root_audit_context(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    app: Any,
) -> None:
    """AC3: worker stamps expired_at, emits one expiry drift, and succeeds without ambient audit context."""
    _grant_expirer(governance_db)
    now = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
    intent = _seed_temporary_intent(
        governance_db,
        app,
        scope_kind="chapter",
        scope_id="chapter-1",
        role_id="chapter-role",
        expires_at=now - timedelta(minutes=5),
    )

    result = permission_expiry_worker_tick(now=now)

    assert result is not None
    assert result.inspected_count == 1
    assert result.expired_count == 1
    assert result.errored_count == 0
    permissions_service = app.state.container.services.permissions()
    expired_intent = permissions_service.read_permission_intent(intent.id)
    assert expired_intent.expired_at == now

    drift = permissions_service.read_permission_drift(result.drift_ids[0])
    assert drift.permission_intent_id == intent.id
    assert drift.intent_version == 2
    assert drift.scope_kind == "chapter"
    assert drift.scope_id == "chapter-1"
    assert drift.intended_bits == "4"
    assert drift.actual_bits is None
    assert drift.actual_allow_bits is None
    assert drift.actual_deny_bits is None
    assert drift.reconciliation_run_id is None
    assert drift.status == "detected"
    assert _fetch_change_types(governance_dsn, aggregate_id=str(drift.id)) == [
        "permission_drift.detected_expired"
    ]

    expire_action = _fetch_latest_action(
        governance_dsn,
        action_type="permission_intent.expire",
    )
    assert expire_action["request_json"]["source"] == "worker_sweep"
    assert set(expire_action["request_json"]) == {"expired_at", "source"}

    drift_action = _fetch_latest_action(
        governance_dsn,
        action_type="permission_drift.detect_expired",
    )
    assert set(drift_action["request_json"]) == {
        "drift_id",
        "permission_intent_id",
        "intent_version",
        "scope_kind",
        "scope_id",
        "role_id",
        "channel_id",
        "kind",
        "status",
    }


def test_worker_rerun_is_idempotent(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    app: Any,
) -> None:
    """AC3: rerunning the worker after an expiry creates no duplicate drift rows."""
    _grant_expirer(governance_db)
    now = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
    _seed_temporary_intent(
        governance_db,
        app,
        role_id="idempotent-role",
        expires_at=now - timedelta(minutes=5),
    )

    first = permission_expiry_worker_tick(now=now)
    second = permission_expiry_worker_tick(now=now)

    assert first is not None
    assert second is not None
    assert first.expired_count == 1
    assert second.expired_count == 0
    assert _fetch_drift_count(governance_dsn) == 1


def test_worker_ignores_non_temporary_and_future_intents(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    app: Any,
) -> None:
    """AC3: worker ignores non-temporary intents and temporary intents whose expires_at is still in the future."""
    _grant_expirer(governance_db)
    now = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
    non_temporary = _seed_temporary_intent(
        governance_db,
        app,
        role_id="non-temp",
        temporary=False,
        expires_at=None,
    )
    future = _seed_temporary_intent(
        governance_db,
        app,
        role_id="future-temp",
        expires_at=now + timedelta(minutes=5),
    )

    result = permission_expiry_worker_tick(now=now)

    assert result is not None
    assert result.expired_count == 0
    assert result.drift_ids == []
    assert _fetch_drift_count(governance_dsn) == 0
    permissions_service = app.state.container.services.permissions()
    assert permissions_service.read_permission_intent(non_temporary.id).expired_at is None
    assert permissions_service.read_permission_intent(future.id).expired_at is None


@pytest.mark.asyncio
async def test_expiry_drift_is_discoverable_via_get_permission_drift(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    app: Any,
) -> None:
    """AC4: expiry-created drift is discoverable through GET /permission-drift."""
    _grant_expirer(governance_db)
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_drift.read"}),
    )
    now = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
    _seed_temporary_intent(
        governance_db,
        app,
        role_id="discoverable-role",
        expires_at=now - timedelta(minutes=5),
    )
    result = permission_expiry_worker_tick(now=now)
    assert result is not None

    response = await migrated_async_client.get(
        DRIFT_URL,
        params={"scope_kind": "global"},
        headers=_headers("operator"),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["id"] == str(result.drift_ids[0])
    assert rows[0]["permission_intent_id"] == str(result.expired_intent_ids[0])
    assert rows[0]["actual_bits"] is None
    assert rows[0]["intended_bits"] == "4"
    assert rows[0]["reconciliation_run_id"] is None


@pytest.mark.asyncio
async def test_manual_expire_run_returns_result_and_ignores_spoofed_body(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
    app: Any,
) -> None:
    """AC3: manual POST /expire/run returns the sweep result and cannot be used to spoof the recorded actor."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_intent.write", "permission_drift.read"}),
    )
    now = datetime.now(UTC)
    _seed_temporary_intent(
        governance_db,
        app,
        role_id="manual-role",
        expires_at=now - timedelta(minutes=5),
    )

    response = await migrated_async_client.post(
        EXPIRE_URL,
        json={
            "originating_actor_kind": "service",
            "originating_actor_id": "spoofed",
        },
        headers=_headers("operator"),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["expired_count"] == 1
    assert len(body["drift_ids"]) == 1

    expire_action = _fetch_latest_action(
        governance_dsn,
        action_type="permission_intent.expire",
    )
    assert expire_action["actor_kind"] == "user"
    assert expire_action["actor_id"] == "operator"
    assert expire_action["request_json"]["source"] == "manual_trigger"
    assert "originating_actor_kind" not in expire_action["request_json"]
    assert "originating_actor_id" not in expire_action["request_json"]


def test_expire_and_drift_are_atomic_when_drift_creation_fails(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    monkeypatch: pytest.MonkeyPatch,
    app: Any,
) -> None:
    """AC3: if drift creation fails, the worker rolls back the expired_at stamp and leaves no drift row behind."""
    from app.services.permissions import PermissionsService

    _grant_expirer(governance_db)
    now = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
    intent = _seed_temporary_intent(
        governance_db,
        app,
        role_id="atomic-role",
        expires_at=now - timedelta(minutes=5),
    )

    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(PermissionsService, "_create_expiry_drift_on", _boom)

    result = permission_expiry_worker_tick(now=now)

    assert result is not None
    assert result.expired_count == 0
    assert result.errored_count == 1
    permissions_service = app.state.container.services.permissions()
    assert permissions_service.read_permission_intent(intent.id).expired_at is None
    assert _fetch_drift_count(governance_dsn) == 0


def test_scheduler_invokes_permission_expiry_worker_on_interval(
    governance_db: PostgresDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: scheduler wiring runs the permission expiry worker when due and skips the immediate repeat."""
    calls: list[datetime] = []

    def _permission_expiry_tick(*, now: datetime, batch_size: int | None = None) -> None:
        assert batch_size is None
        calls.append(now)

    monkeypatch.setattr(
        "app.tasks.permission_expiry.permission_expiry_worker_tick",
        _permission_expiry_tick,
    )
    monkeypatch.setattr("app.tasks.archive.archive_worker_tick", lambda: None)
    monkeypatch.setattr(
        "app.services.deferred_effects.deferred_effect_worker_tick",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr("app.tasks.ticket_sla.ticket_sla_worker_tick", lambda: [])
    monkeypatch.setattr(
        "app.tasks.read_models.read_model_worker_tick",
        lambda *_args, **_kwargs: None,
    )

    async def _run() -> None:
        loop = SchedulerLoop(governance_db, worker_id="worker-expiry")
        first = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
        second = first + timedelta(seconds=5)
        third = first + timedelta(seconds=61)
        await loop._run_permission_expiry_if_due(first)
        await loop._run_permission_expiry_if_due(second)
        await loop._run_permission_expiry_if_due(third)

    asyncio.run(_run())

    assert calls == [
        datetime(2026, 4, 21, 12, 0, tzinfo=UTC),
        datetime(2026, 4, 21, 12, 1, 1, tzinfo=UTC),
    ]
