from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

import psycopg
import pytest
from httpx import AsyncClient

from app.repositories.db import PostgresDatabase
from app.services.authority import grant_authority

from .authority_slice_helpers import (
    actor_headers,
    audit_context,
    create_member,
    grant_permission,
    seed_application,
)
from app.core.context import use_audit_context


def _application_owner(dsn: str, application_id: UUID) -> str | None:
    with psycopg.connect(dsn) as connection:
        row = connection.execute(
            "SELECT owner_id::text FROM applications WHERE id = %s",
            (application_id,),
        ).fetchone()
    assert row is not None
    return row[0]


def _predecessor_grant(db: PostgresDatabase, *, grantee_id: str) -> UUID:
    with use_audit_context(audit_context()):
        grant = grant_authority(
            db=db,
            grantee_id=grantee_id,
            scope_kind="chapter",
            scope_id="chapter-1",
            permissions=frozenset({"chapter.write"}),
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )
    return grant.id


@pytest.mark.asyncio
async def test_handoff_applications_transfers_pending_items_and_skips_already_owned(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC3: application handoff transfers predecessor-owned items and skips successor-owned ones."""

    predecessor_id = create_member(governance_db, discord_user_id="predecessor-1")
    successor_id = create_member(governance_db, discord_user_id="successor-1")
    operator_id = create_member(governance_db, discord_user_id="operator-1")
    grant_id = _predecessor_grant(governance_db, grantee_id=predecessor_id)
    grant_permission(
        governance_db,
        actor_id=operator_id,
        permission="leadership_handoff.execute",
        scope_kind="chapter",
        scope_id="chapter-1",
    )

    transferred_application = seed_application(
        governance_db,
        chapter_id="chapter-1",
        applicant_id=UUID(predecessor_id),
        owner_id=UUID(predecessor_id),
        state="queued",
    )
    already_owned_application = seed_application(
        governance_db,
        chapter_id="chapter-1",
        applicant_id=UUID(successor_id),
        owner_id=UUID(successor_id),
        state="queued",
    )

    response = await migrated_async_client.post(
        f"/api/v1/authority-grants/{grant_id}/handoff/applications",
        json={"successor_member_id": successor_id},
        headers=actor_headers(actor_id=operator_id),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["transferred"] == [str(transferred_application)]
    assert body["already_owned"] == [str(already_owned_application)]
    assert body["failed"] == []
    assert _application_owner(governance_dsn, transferred_application) == successor_id


@pytest.mark.asyncio
async def test_handoff_applications_is_idempotent_on_replay(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC3: replaying application handoff reports the item as already owned with no second transfer."""

    predecessor_id = create_member(governance_db, discord_user_id="predecessor-1")
    successor_id = create_member(governance_db, discord_user_id="successor-1")
    operator_id = create_member(governance_db, discord_user_id="operator-1")
    grant_id = _predecessor_grant(governance_db, grantee_id=predecessor_id)
    grant_permission(
        governance_db,
        actor_id=operator_id,
        permission="leadership_handoff.execute",
        scope_kind="chapter",
        scope_id="chapter-1",
    )
    application_id = seed_application(
        governance_db,
        chapter_id="chapter-1",
        applicant_id=UUID(predecessor_id),
        owner_id=UUID(predecessor_id),
        state="queued",
    )

    first = await migrated_async_client.post(
        f"/api/v1/authority-grants/{grant_id}/handoff/applications",
        json={"successor_member_id": successor_id},
        headers=actor_headers(actor_id=operator_id),
    )
    assert first.status_code == HTTPStatus.OK, first.text

    replay = await migrated_async_client.post(
        f"/api/v1/authority-grants/{grant_id}/handoff/applications",
        json={"successor_member_id": successor_id},
        headers=actor_headers(actor_id=operator_id),
    )

    assert replay.status_code == HTTPStatus.OK, replay.text
    assert replay.json()["transferred"] == []
    assert replay.json()["already_owned"] == [str(application_id)]
