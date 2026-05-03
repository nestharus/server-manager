from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import AsyncClient

from app.repositories.db import PostgresDatabase
from tests._authority_helpers import grant_authority

from .authority_slice_helpers import actor_headers, audit_context, create_member, grant_permission, seed_role_holder
from app.core.context import use_audit_context


@pytest.mark.asyncio
async def test_succession_plan_lists_departing_roles_and_affected_grants(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: the succession plan is queryable without a designated successor or writes."""

    member_id = create_member(governance_db, discord_user_id="holder-1")
    role_id = seed_role_holder(
        governance_db,
        chapter_id="chapter-1",
        member_id=member_id,
    )
    with use_audit_context(audit_context()):
        grant_authority(
            db=governance_db,
            grantee_id=member_id,
            scope_kind="chapter",
            scope_id="chapter-1",
            permissions=frozenset({"chapter.write"}),
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )
    grant_permission(
        governance_db,
        actor_id="operator",
        permission="succession_plan.read",
        scope_kind="chapter",
        scope_id="chapter-1",
    )

    response = await migrated_async_client.get(
        "/api/v1/chapters/chapter-1/succession-plan",
        headers=actor_headers(actor_id="operator"),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["chapter_id"] == "chapter-1"
    assert body["successor_designated"] is False
    assert body["successor_member_id"] is None
    assert body["departing_roles"][0]["role_id"] == str(role_id)
    assert body["departing_roles"][0]["holder_member_id"] == member_id
    assert body["affected_grants"][0]["grantee_id"] == member_id


@pytest.mark.asyncio
async def test_succession_plan_rejects_invalid_holder_ids_in_roster_rows(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: malformed holder ids raise 422 instead of being silently skipped."""

    seed_role_holder(
        governance_db,
        chapter_id="chapter-1",
        member_id="not-a-uuid-or-discord-id",
        status="removed",
    )
    grant_permission(
        governance_db,
        actor_id="operator",
        permission="succession_plan.read",
        scope_kind="chapter",
        scope_id="chapter-1",
    )

    response = await migrated_async_client.get(
        "/api/v1/chapters/chapter-1/succession-plan",
        headers=actor_headers(actor_id="operator"),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "invalid_holder_id"
