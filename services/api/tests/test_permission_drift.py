from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from httpx import AsyncClient
from psycopg.rows import dict_row

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.permissions import (
    GuildRolePermissionIntentCreate,
    PermissionDriftRead,
)
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.authority import grant_authority
from app.services.permissions import (
    DRIFT_RESOLUTION_CHANGE_TYPE,
    create_permission_drift,
    create_permission_intent,
)


DRIFT_URL = "/api/v1/permission-drift"


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


def _seed_intent(
    db: PostgresDatabase,
    *,
    actor_id: str = "intent-seeder",
    role_id: str = "role-1",
    scope_kind: str = "global",
    scope_id: str | None = None,
    permission_bits: str = "4",
) -> tuple[UUID, int]:
    _grant(
        db,
        actor_id=actor_id,
        permissions=frozenset({"permission_intent.write"}),
        scope_kind=scope_kind,
        scope_id=scope_id,
    )
    create_request = GuildRolePermissionIntentCreate(
        kind="guild_role",
        scope_kind=scope_kind,
        scope_id=scope_id,
        role_id=role_id,
        permission_bits=permission_bits,
        temporary=False,
        expires_at=None,
    )
    with use_audit_context(_audit_context()):
        intent, result = create_permission_intent(
            db,
            create_request,
            actor=ActorIdentity(actor_kind="user", actor_id=actor_id),
        )
    return intent.id, result.version


def _seed_drift(
    db: PostgresDatabase,
    *,
    actor_id: str = "operator",
    drift_id: UUID | None = None,
    scope_kind: str = "global",
    scope_id: str | None = None,
    role_id: str = "role-1",
    permission_intent_id: UUID | None = None,
    intent_version: int | None = None,
    actual_bits: str = "8",
    intended_bits: str = "4",
    kind: str = "guild_role",
    channel_id: str | None = None,
    actual_allow_bits: str | None = None,
    actual_deny_bits: str | None = None,
    intended_allow_bits: str | None = None,
    intended_deny_bits: str | None = None,
) -> UUID:
    new_id = drift_id or uuid4()
    model_kwargs: dict[str, Any] = {
        "id": new_id,
        "permission_intent_id": permission_intent_id,
        "intent_version": intent_version,
        "scope_kind": scope_kind,
        "scope_id": scope_id,
        "role_id": role_id,
        "channel_id": channel_id,
        "kind": kind,
        "reconciliation_run_id": None,
        "status": "detected",
        "detected_at": datetime.now(UTC),
    }
    if kind == "guild_role":
        model_kwargs["actual_bits"] = actual_bits
        model_kwargs["intended_bits"] = intended_bits
    else:
        model_kwargs["actual_allow_bits"] = actual_allow_bits
        model_kwargs["actual_deny_bits"] = actual_deny_bits
        model_kwargs["intended_allow_bits"] = intended_allow_bits
        model_kwargs["intended_deny_bits"] = intended_deny_bits

    drift = PermissionDriftRead.model_validate(model_kwargs)
    with use_audit_context(_audit_context()):
        create_permission_drift(
            db,
            request=drift,
            actor=ActorIdentity(actor_kind="service", actor_id=actor_id),
        )
    return new_id


def _fetch_state_change_types(
    dsn: str,
    *,
    drift_id: UUID,
) -> list[str]:
    with psycopg.connect(dsn) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                """
                SELECT change_type FROM activity_state_changes
                 WHERE aggregate_type = 'permission_drift'
                   AND aggregate_id = %s
                 ORDER BY aggregate_seq
                """,
                (str(drift_id),),
            ).fetchall()
    return [row["change_type"] for row in rows]


@pytest.fixture
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


@pytest.mark.asyncio
async def test_list_drift_returns_intent_linked_and_orphaned_rows(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC2 (D6): list returns both intent-linked and orphaned drift rows."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_drift.read"}),
    )
    linked_intent_id, linked_intent_version = _seed_intent(
        governance_db,
        role_id="linked-role",
    )
    _seed_drift(
        governance_db,
        permission_intent_id=linked_intent_id,
        intent_version=linked_intent_version,
        role_id="linked-role",
    )
    _seed_drift(governance_db, role_id="orphan-role")

    response = await migrated_async_client.get(
        DRIFT_URL,
        params={"scope_kind": "global"},
        headers=_headers("operator"),
    )
    assert response.status_code == HTTPStatus.OK, response.text
    rows = response.json()
    by_role = {row["role_id"]: row for row in rows}
    assert by_role["linked-role"]["permission_intent_id"] == str(linked_intent_id)
    assert by_role["orphan-role"]["permission_intent_id"] is None


@pytest.mark.asyncio
async def test_list_drift_requires_scope_kind_param(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """CodeRabbit CRITICAL 2: scope_kind is required — omitting it must
    return 422 so a caller with only global read cannot implicitly
    enumerate chapter drift."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_drift.read"}),
    )

    response = await migrated_async_client.get(
        DRIFT_URL,
        headers=_headers("operator"),
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.asyncio
async def test_list_drift_chapter_scope_requires_scope_id(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """CodeRabbit CRITICAL 2: chapter scope must include scope_id."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_drift.read"}),
    )

    response = await migrated_async_client.get(
        DRIFT_URL,
        params={"scope_kind": "chapter"},
        headers=_headers("operator"),
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.asyncio
async def test_list_drift_has_intent_filter(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC2: has_intent filter narrows the list."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_drift.read"}),
    )
    linked_intent_id, linked_intent_version = _seed_intent(
        governance_db,
        role_id="linked-role",
    )
    _seed_drift(
        governance_db,
        permission_intent_id=linked_intent_id,
        intent_version=linked_intent_version,
        role_id="linked-role",
    )
    _seed_drift(governance_db, role_id="orphan-role")

    response_with = await migrated_async_client.get(
        DRIFT_URL,
        params={"scope_kind": "global", "has_intent": "true"},
        headers=_headers("operator"),
    )
    assert response_with.status_code == HTTPStatus.OK, response_with.text
    roles_with = {row["role_id"] for row in response_with.json()}
    assert roles_with == {"linked-role"}

    response_without = await migrated_async_client.get(
        DRIFT_URL,
        params={"scope_kind": "global", "has_intent": "false"},
        headers=_headers("operator"),
    )
    assert response_without.status_code == HTTPStatus.OK, response_without.text
    roles_without = {row["role_id"] for row in response_without.json()}
    assert roles_without == {"orphan-role"}


@pytest.mark.asyncio
async def test_resolve_drift_detected_to_acknowledged_with_if_match(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC2 (D5): detected -> acknowledged advances version and records
    the operator who acknowledged (CodeRabbit MAJOR 1: acknowledge is a
    resolved state and carries full resolution metadata)."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {"permission_drift.read", "permission_drift.write"}
        ),
    )
    drift_id = _seed_drift(governance_db)

    response = await migrated_async_client.post(
        f"{DRIFT_URL}/{drift_id}/resolve",
        json={"action": "acknowledge", "reason": "reviewing"},
        headers=_headers("operator", **{"If-Match": '"1"'}),
    )
    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["status"] == "acknowledged"
    assert body["resolved_by_kind"] == "user"
    assert body["resolved_by_id"] == "operator"
    assert body["resolved_at"] is not None
    assert body["resolution_reason"] == "reviewing"
    assert response.headers["etag"] == '"2"'


@pytest.mark.asyncio
async def test_resolve_drift_returns_post_mutation_state(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """CodeRabbit CRITICAL 1: response body must reflect post-update status
    (status=reconciled, resolution metadata populated), not the pre-update
    snapshot (status=detected with nulls)."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {"permission_drift.read", "permission_drift.write"}
        ),
    )
    drift_id = _seed_drift(governance_db)

    response = await migrated_async_client.post(
        f"{DRIFT_URL}/{drift_id}/resolve",
        json={"action": "reconcile", "reason": "fixed"},
        headers=_headers("operator", **{"If-Match": '"1"'}),
    )
    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    # Pre-update status was 'detected' with all resolution fields null; the
    # response MUST reflect the post-update terminal state with populated
    # resolution metadata, and the ETag must match the new version.
    assert body["status"] == "reconciled"
    assert body["status"] != "detected"
    assert body["resolved_by_kind"] == "user"
    assert body["resolved_by_id"] == "operator"
    assert body["resolved_at"] is not None
    assert body["resolution_reason"] == "fixed"
    assert response.headers["etag"] == '"2"'


@pytest.mark.asyncio
async def test_resolve_drift_acknowledged_to_reconciled_populates_resolved_fields(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC2 (D5): terminal resolution populates resolved_by/resolved_at/reason."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {"permission_drift.read", "permission_drift.write"}
        ),
    )
    drift_id = _seed_drift(governance_db)
    ack = await migrated_async_client.post(
        f"{DRIFT_URL}/{drift_id}/resolve",
        json={"action": "acknowledge", "reason": "reviewing"},
        headers=_headers("operator", **{"If-Match": '"1"'}),
    )
    assert ack.status_code == HTTPStatus.OK

    response = await migrated_async_client.post(
        f"{DRIFT_URL}/{drift_id}/resolve",
        json={"action": "reconcile", "reason": "fixed the bits"},
        headers=_headers("operator", **{"If-Match": '"2"'}),
    )
    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["status"] == "reconciled"
    assert body["resolved_by_kind"] == "user"
    assert body["resolved_by_id"] == "operator"
    assert body["resolved_at"] is not None
    assert body["resolution_reason"] == "fixed the bits"
    assert response.headers["etag"] == '"3"'


@pytest.mark.asyncio
async def test_resolve_drift_detected_to_accepted_skips_acknowledged(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC2 (D5): detected -> accepted is a valid direct edge."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {"permission_drift.read", "permission_drift.write"}
        ),
    )
    drift_id = _seed_drift(governance_db)

    response = await migrated_async_client.post(
        f"{DRIFT_URL}/{drift_id}/resolve",
        json={"action": "accept", "reason": "tolerate the drift"},
        headers=_headers("operator", **{"If-Match": '"1"'}),
    )
    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["status"] == "accepted"
    assert body["resolved_by_kind"] == "user"
    assert body["resolved_by_id"] == "operator"
    assert body["resolution_reason"] == "tolerate the drift"


@pytest.mark.asyncio
async def test_resolve_drift_stale_if_match_returns_412(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC2: PATCH with stale If-Match returns 412."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {"permission_drift.read", "permission_drift.write"}
        ),
    )
    drift_id = _seed_drift(governance_db)

    response = await migrated_async_client.post(
        f"{DRIFT_URL}/{drift_id}/resolve",
        json={"action": "acknowledge", "reason": "stale"},
        headers=_headers("operator", **{"If-Match": '"0"'}),
    )
    assert response.status_code == HTTPStatus.PRECONDITION_FAILED, response.text
    assert response.json()["code"] == "stale_permission_version"


@pytest.mark.asyncio
async def test_resolve_drift_user_actor_cannot_spoof_resolved_by_fields(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC2 (D6): user actor cannot override resolved_by via the request body."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {"permission_drift.read", "permission_drift.write"}
        ),
    )
    drift_id = _seed_drift(governance_db)

    response = await migrated_async_client.post(
        f"{DRIFT_URL}/{drift_id}/resolve",
        json={
            "action": "reconcile",
            "reason": "force",
            "resolved_by_kind": "service",
            "resolved_by_id": "spoofed-service",
        },
        headers=_headers("operator", **{"If-Match": '"1"'}),
    )
    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["status"] == "reconciled"
    assert body["resolved_by_kind"] == "user"
    assert body["resolved_by_id"] == "operator"


@pytest.mark.asyncio
async def test_resolve_drift_service_actor_sets_resolved_by_from_body(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC2 (D6): service actor honors resolved_by_* from the body."""
    _grant(
        governance_db,
        actor_id="permission-reconciler",
        permissions=frozenset(
            {"permission_drift.read", "permission_drift.write"}
        ),
    )
    drift_id = _seed_drift(governance_db)

    response = await migrated_async_client.post(
        f"{DRIFT_URL}/{drift_id}/resolve",
        json={
            "action": "reconcile",
            "reason": "bot reconciled",
            "resolved_by_kind": "user",
            "resolved_by_id": "human-operator",
        },
        headers=_headers("permission-reconciler", kind="service", **{"If-Match": '"1"'}),
    )
    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["status"] == "reconciled"
    assert body["resolved_by_kind"] == "user"
    assert body["resolved_by_id"] == "human-operator"


@pytest.mark.asyncio
async def test_resolve_drift_terminal_status_returns_409(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC2 (D5): resolving a terminal drift returns 409 invalid_drift_transition."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {"permission_drift.read", "permission_drift.write"}
        ),
    )
    drift_id = _seed_drift(governance_db)
    first = await migrated_async_client.post(
        f"{DRIFT_URL}/{drift_id}/resolve",
        json={"action": "accept", "reason": "accepted"},
        headers=_headers("operator", **{"If-Match": '"1"'}),
    )
    assert first.status_code == HTTPStatus.OK

    second = await migrated_async_client.post(
        f"{DRIFT_URL}/{drift_id}/resolve",
        json={"action": "reconcile", "reason": "retry"},
        headers=_headers("operator", **{"If-Match": '"2"'}),
    )
    assert second.status_code == HTTPStatus.CONFLICT, second.text
    assert second.json()["code"] == "invalid_drift_transition"


@pytest.mark.asyncio
async def test_resolve_drift_invalid_transition_returns_409(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC2 (D5): acknowledge -> acknowledge is not a valid transition."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {"permission_drift.read", "permission_drift.write"}
        ),
    )
    drift_id = _seed_drift(governance_db)
    ack = await migrated_async_client.post(
        f"{DRIFT_URL}/{drift_id}/resolve",
        json={"action": "acknowledge", "reason": "first"},
        headers=_headers("operator", **{"If-Match": '"1"'}),
    )
    assert ack.status_code == HTTPStatus.OK

    duplicate = await migrated_async_client.post(
        f"{DRIFT_URL}/{drift_id}/resolve",
        json={"action": "acknowledge", "reason": "again"},
        headers=_headers("operator", **{"If-Match": '"2"'}),
    )
    assert duplicate.status_code == HTTPStatus.CONFLICT, duplicate.text
    assert duplicate.json()["code"] == "invalid_drift_transition"


@pytest.mark.parametrize(
    "action,expected_change_type",
    [
        ("acknowledge", DRIFT_RESOLUTION_CHANGE_TYPE["acknowledge"]),
        ("reconcile", DRIFT_RESOLUTION_CHANGE_TYPE["reconcile"]),
        ("accept", DRIFT_RESOLUTION_CHANGE_TYPE["accept"]),
    ],
)
@pytest.mark.asyncio
async def test_resolve_drift_accept_emits_correct_change_type(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
    action: str,
    expected_change_type: str,
) -> None:
    """AC2 (R1 / shortcut F1 regression guard).

    Resolving with each action writes an activity_state_changes row whose
    change_type is exactly the constant declared in
    DRIFT_RESOLUTION_CHANGE_TYPE — proving accept emits
    'permission_drift.accepted', not the f-string typo 'permission_drift.acceptd'.
    """
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {"permission_drift.read", "permission_drift.write"}
        ),
    )
    drift_id = _seed_drift(governance_db)
    response = await migrated_async_client.post(
        f"{DRIFT_URL}/{drift_id}/resolve",
        json={"action": action, "reason": f"via {action}"},
        headers=_headers("operator", **{"If-Match": '"1"'}),
    )
    assert response.status_code == HTTPStatus.OK, response.text

    change_types = _fetch_state_change_types(governance_dsn, drift_id=drift_id)
    assert expected_change_type in change_types
    # Shortcut F1 regression guard: the accept action must not write
    # 'permission_drift.acceptd' (f-string typo) in any branch.
    assert "permission_drift.acceptd" not in change_types


@pytest.mark.asyncio
async def test_resolve_drift_rejects_whitespace_only_reason(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """CodeRabbit MAJOR 1: whitespace-only reason returns 422 before the write."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {"permission_drift.read", "permission_drift.write"}
        ),
    )
    drift_id = _seed_drift(governance_db)

    response = await migrated_async_client.post(
        f"{DRIFT_URL}/{drift_id}/resolve",
        json={"action": "acknowledge", "reason": "   "},
        headers=_headers("operator", **{"If-Match": '"1"'}),
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.asyncio
async def test_resolve_drift_rejects_blank_resolved_by_id(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """CodeRabbit MAJOR 3: whitespace-only resolved_by_id returns 422."""
    _grant(
        governance_db,
        actor_id="reconciler",
        permissions=frozenset(
            {"permission_drift.read", "permission_drift.write"}
        ),
    )
    drift_id = _seed_drift(governance_db)

    response = await migrated_async_client.post(
        f"{DRIFT_URL}/{drift_id}/resolve",
        json={
            "action": "reconcile",
            "reason": "bot reconciled",
            "resolved_by_kind": "user",
            "resolved_by_id": "   ",
        },
        headers=_headers(
            "reconciler", kind="service", **{"If-Match": '"1"'}
        ),
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
