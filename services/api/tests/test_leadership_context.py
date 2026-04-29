from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import AsyncClient

from app.repositories.db import PostgresDatabase
from app.services.authority import grant_authority, revoke_authority

from .authority_slice_helpers import actor_headers, audit_context, grant_permission, seed_ticket
from app.core.context import use_audit_context

PREDECESSOR_ID = "100000000000000001"
SUCCESSOR_ID = "100000000000000002"


def _seed_inherited_grant(db: PostgresDatabase) -> tuple[str, str]:
    with use_audit_context(audit_context()):
        predecessor = grant_authority(
            db=db,
            grantee_id=PREDECESSOR_ID,
            scope_kind="chapter",
            scope_id="chapter-1",
            permissions=frozenset({"chapter.write"}),
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )
        successor = grant_authority(
            db=db,
            grantee_id=SUCCESSOR_ID,
            scope_kind="chapter",
            scope_id="chapter-1",
            permissions=frozenset({"chapter.write"}),
            expires_at=None,
            predecessor_grant_id=predecessor.id,
            actor=("user", "admin"),
        )
        revoke_authority(
            db=db,
            grant_id=predecessor.id,
            actor=("user", "admin"),
            revoked_by="admin",
            reason="succession_transfer",
        )
    return str(predecessor.id), str(successor.id)


@pytest.mark.asyncio
async def test_leadership_context_returns_empty_but_non_null_shape_for_member_without_grants(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC4: leadership context returns a populated empty shape rather than an empty response."""

    grant_permission(
        governance_db,
        actor_id="operator",
        permission="leadership_context.read",
        scope_kind="global",
        scope_id=None,
    )

    response = await migrated_async_client.get(
        "/api/v1/members/100000000000000009/leadership-context",
        headers=actor_headers(actor_id="operator"),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["member_id"] == "100000000000000009"
    assert body["active_grants"] == []
    assert body["inherited_from"] == []
    assert body["stale_handoff"] == []
    assert body["is_stale"] is False


@pytest.mark.asyncio
async def test_leadership_context_rejects_synthetic_member_alias_expansion(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    synthetic_member_guard_member_factory,
) -> None:
    """Risk annotation: group=TG-5; named_risk=leadership_alias_synthetic_member;
    level=component; source=.tmp/init-124/phase6/step6a-contract.md#C5.
    """
    synthetic = synthetic_member_guard_member_factory.synthetic()
    grant_permission(
        governance_db,
        actor_id="operator",
        permission="leadership_context.read",
        scope_kind="global",
        scope_id=None,
    )

    response = await migrated_async_client.get(
        f"/api/v1/members/{synthetic.id}/leadership-context",
        headers=actor_headers(actor_id="operator"),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "leadership_alias_synthetic_not_allowed"


@pytest.mark.asyncio
async def test_leadership_context_accepts_real_member_alias_expansion(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    synthetic_member_guard_member_factory,
) -> None:
    """Risk annotation: group=TG-5; named_risk=leadership_alias_real_member_regression;
    level=component; source=.tmp/init-124/phase6/step6a-contract.md#C5.
    """
    real = synthetic_member_guard_member_factory.real()
    grant_permission(
        governance_db,
        actor_id="operator",
        permission="leadership_context.read",
        scope_kind="global",
        scope_id=None,
    )

    response = await migrated_async_client.get(
        f"/api/v1/members/{real.id}/leadership-context",
        headers=actor_headers(actor_id="operator"),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["member_id"] == str(real.id)


@pytest.mark.asyncio
async def test_leadership_context_reports_stale_handoff_for_predecessor_owned_work(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC4: inherited grants expose stale handoff when predecessor still owns open work."""

    predecessor_grant_id, _successor_grant_id = _seed_inherited_grant(governance_db)
    seed_ticket(
        governance_db,
        chapter_id="chapter-1",
        owner_id=PREDECESSOR_ID,
    )
    grant_permission(
        governance_db,
        actor_id="operator",
        permission="leadership_context.read",
        scope_kind="global",
        scope_id=None,
    )

    response = await migrated_async_client.get(
        f"/api/v1/members/{SUCCESSOR_ID}/leadership-context",
        headers=actor_headers(actor_id="operator"),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert len(body["active_grants"]) == 1
    assert body["inherited_from"][0]["predecessor_grant_id"] == predecessor_grant_id
    assert body["stale_handoff"][0]["predecessor_grant_id"] == predecessor_grant_id
    assert body["is_stale"] is True
