from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

import psycopg
import pytest
from httpx import AsyncClient

from app.repositories.db import PostgresDatabase
from tests._authority_helpers import grant_authority

from .authority_slice_helpers import (
    actor_headers,
    audit_context,
    grant_permission,
    seed_ticket,
)
from app.core.context import use_audit_context


def _ticket_owner(dsn: str, ticket_id: UUID) -> str | None:
    with psycopg.connect(dsn) as connection:
        row = connection.execute(
            "SELECT owner_id FROM tickets WHERE id = %s",
            (ticket_id,),
        ).fetchone()
    assert row is not None
    return row[0]


PREDECESSOR_ID = "100000000000000001"
SUCCESSOR_ID = "100000000000000002"


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
async def test_handoff_tickets_transfers_open_items_and_skips_already_owned(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC3: ticket handoff transfers predecessor-owned open tickets and skips successor-owned ones."""

    grant_id = _predecessor_grant(governance_db, grantee_id=PREDECESSOR_ID)
    grant_permission(
        governance_db,
        actor_id="operator",
        permission="leadership_handoff.execute",
        scope_kind="chapter",
        scope_id="chapter-1",
    )
    transferred_ticket = seed_ticket(
        governance_db,
        chapter_id="chapter-1",
        owner_id=PREDECESSOR_ID,
    )
    already_owned_ticket = seed_ticket(
        governance_db,
        chapter_id="chapter-1",
        owner_id=SUCCESSOR_ID,
    )

    response = await migrated_async_client.post(
        f"/api/v1/authority-grants/{grant_id}/handoff/tickets",
        json={"successor_member_id": SUCCESSOR_ID},
        headers=actor_headers(actor_id="operator"),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["transferred"] == [str(transferred_ticket)]
    assert body["already_owned"] == [str(already_owned_ticket)]
    assert body["failed"] == []
    assert _ticket_owner(governance_dsn, transferred_ticket) == SUCCESSOR_ID


@pytest.mark.asyncio
async def test_handoff_tickets_is_idempotent_on_replay(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC3: replaying ticket handoff reports the ticket as already owned with no second transfer."""

    grant_id = _predecessor_grant(governance_db, grantee_id=PREDECESSOR_ID)
    grant_permission(
        governance_db,
        actor_id="operator",
        permission="leadership_handoff.execute",
        scope_kind="chapter",
        scope_id="chapter-1",
    )
    ticket_id = seed_ticket(
        governance_db,
        chapter_id="chapter-1",
        owner_id=PREDECESSOR_ID,
    )

    first = await migrated_async_client.post(
        f"/api/v1/authority-grants/{grant_id}/handoff/tickets",
        json={"successor_member_id": SUCCESSOR_ID},
        headers=actor_headers(actor_id="operator"),
    )
    assert first.status_code == HTTPStatus.OK, first.text

    replay = await migrated_async_client.post(
        f"/api/v1/authority-grants/{grant_id}/handoff/tickets",
        json={"successor_member_id": SUCCESSOR_ID},
        headers=actor_headers(actor_id="operator"),
    )

    assert replay.status_code == HTTPStatus.OK, replay.text
    assert replay.json()["transferred"] == []
    assert replay.json()["already_owned"] == [str(ticket_id)]
