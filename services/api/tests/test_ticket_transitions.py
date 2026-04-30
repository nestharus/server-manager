from __future__ import annotations

from collections.abc import Iterator
from http import HTTPStatus
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from httpx import AsyncClient
from psycopg.rows import dict_row

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.authority import grant_authority


CATEGORY_URL = "/api/v1/ticket-categories"
TICKETS_URL = "/api/v1/tickets"


def _audit_context() -> AuditContextRead:
    cid = uuid4()
    return AuditContextRead(
        correlation_id=cid,
        causation_id=None,
        headers=CorrelationHeadersRead(x_correlation_id=cid, x_causation_id=None),
    )


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
            db=db,
            grantee_id=actor_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            permissions=permissions,
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )


def _headers(kind: str, actor_id: str) -> dict[str, str]:
    return {"X-Actor-Kind": kind, "X-Actor-Id": actor_id}


def _state_machine() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "initial_state": "open",
        "states": [
            {"key": "open", "label": "Open", "terminal": False},
            {"key": "triaged", "label": "Triaged", "terminal": False},
            {"key": "closed", "label": "Closed", "terminal": True},
        ],
        "edges": [
            {
                "from": "open",
                "to": "triaged",
                "action": "triage",
                "requires_reason": False,
                "requires_resolution": False,
                "allow_owner_change": True,
                "allow_priority_change": True,
            },
            {
                "from": "triaged",
                "to": "closed",
                "action": "close",
                "requires_reason": True,
                "requires_resolution": True,
                "allow_owner_change": False,
                "allow_priority_change": False,
            },
        ],
    }


async def _create_category(client: AsyncClient, db: PostgresDatabase) -> dict[str, Any]:
    _grant(db, actor_id="operator", permissions=frozenset({"ticket_category.write"}))
    response = await client.post(
        CATEGORY_URL,
        json={
            "name": f"Category-{uuid4().hex[:8]}",
            "routing_scope": {
                "scope_kind": "chapter",
                "scope_id": "chapter-1",
                "queue": "officers",
            },
            "privacy_level": "reporter_staff",
            "state_machine": _state_machine(),
            "sla_rules": {"schema_version": 1, "rules": []},
        },
        headers=_headers("user", "operator"),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


async def _create_ticket(
    client: AsyncClient,
    db: PostgresDatabase,
) -> tuple[dict[str, Any], str]:
    _grant(
        db,
        actor_id="discord-ticket-bot",
        permissions=frozenset({"ticket.create", "ticket.message.append"}),
    )
    category = await _create_category(client, db)
    response = await client.post(
        TICKETS_URL,
        json={
            "category_id": category["id"],
            "reporter_id": "reporter-1",
            "subject_id": None,
            "priority": "normal",
            "client_ticket_id": f"interaction-{uuid4().hex[:8]}",
            "initial_message": {
                "body_markdown": "Initial",
                "visibility": "reporter_visible",
                "client_message_id": f"interaction-{uuid4().hex[:8]}",
                "author_actor_kind": "user",
                "author_actor_id": "reporter-1",
            },
            "originating_actor_kind": "user",
            "originating_actor_id": "reporter-1",
        },
        headers=_headers("service", "discord-ticket-bot"),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    _grant(
        db,
        actor_id="moderator-1",
        scope_kind="chapter",
        scope_id="chapter-1",
        permissions=frozenset({"ticket.transition", "ticket.read"}),
    )
    return response.json()["ticket"], response.headers["etag"]


def _latest_transition(dsn: str, ticket_id: str) -> dict[str, Any] | None:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT aggregate_seq, from_state, to_state, action
            FROM ticket_transitions
            WHERE ticket_id = %s
            ORDER BY aggregate_seq DESC
            LIMIT 1
            """,
            (ticket_id,),
        ).fetchone()


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


@pytest.mark.asyncio
async def test_transition_succeeds_and_inserts_transition_row_with_correct_seq(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    # AC3, D5, D12
    ticket, etag = await _create_ticket(migrated_async_client, governance_db)

    response = await migrated_async_client.post(
        f"{TICKETS_URL}/{ticket['id']}/transitions",
        json={
            "action": "triage",
            "to_state": "triaged",
            "reason": None,
            "resolution": None,
            "owner_id": "staff-1",
            "priority": "urgent",
            "originating_actor_kind": "user",
            "originating_actor_id": "moderator-1",
        },
        headers={**_headers("user", "moderator-1"), "If-Match": etag},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["state"] == "triaged"
    assert body["owner_id"] == "staff-1"
    assert body["priority"] == "urgent"
    assert response.headers["etag"] == '"2"'
    transition = _latest_transition(governance_dsn, ticket["id"])
    assert transition is not None
    assert int(transition["aggregate_seq"]) == 2
    assert transition["from_state"] == "open"
    assert transition["to_state"] == "triaged"


@pytest.mark.asyncio
async def test_transition_rejects_invalid_edge(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    # AC3, D12
    ticket, etag = await _create_ticket(migrated_async_client, governance_db)

    response = await migrated_async_client.post(
        f"{TICKETS_URL}/{ticket['id']}/transitions",
        json={
            "action": "close",
            "to_state": "closed",
            "reason": "bad edge",
            "resolution": "done",
            "originating_actor_kind": "user",
            "originating_actor_id": "moderator-1",
        },
        headers={**_headers("user", "moderator-1"), "If-Match": etag},
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["code"] == "invalid_ticket_transition"


@pytest.mark.asyncio
async def test_transition_requires_reason_when_edge_requires(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    # AC3, D12
    ticket, etag = await _create_ticket(migrated_async_client, governance_db)
    triaged = await migrated_async_client.post(
        f"{TICKETS_URL}/{ticket['id']}/transitions",
        json={
            "action": "triage",
            "to_state": "triaged",
            "owner_id": "staff-1",
            "priority": "urgent",
            "originating_actor_kind": "user",
            "originating_actor_id": "moderator-1",
        },
        headers={**_headers("user", "moderator-1"), "If-Match": etag},
    )
    assert triaged.status_code == HTTPStatus.OK, triaged.text

    response = await migrated_async_client.post(
        f"{TICKETS_URL}/{ticket['id']}/transitions",
        json={
            "action": "close",
            "to_state": "closed",
            "reason": "   ",
            "resolution": "resolved",
            "originating_actor_kind": "user",
            "originating_actor_id": "moderator-1",
        },
        headers={**_headers("user", "moderator-1"), "If-Match": triaged.headers["etag"]},
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["code"] == "ticket_transition_reason_required"


@pytest.mark.asyncio
async def test_transition_requires_resolution_when_edge_requires(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    # AC3, D12
    ticket, etag = await _create_ticket(migrated_async_client, governance_db)
    triaged = await migrated_async_client.post(
        f"{TICKETS_URL}/{ticket['id']}/transitions",
        json={
            "action": "triage",
            "to_state": "triaged",
            "owner_id": "staff-1",
            "priority": "urgent",
            "originating_actor_kind": "user",
            "originating_actor_id": "moderator-1",
        },
        headers={**_headers("user", "moderator-1"), "If-Match": etag},
    )
    assert triaged.status_code == HTTPStatus.OK, triaged.text

    response = await migrated_async_client.post(
        f"{TICKETS_URL}/{ticket['id']}/transitions",
        json={
            "action": "close",
            "to_state": "closed",
            "reason": "closing",
            "originating_actor_kind": "user",
            "originating_actor_id": "moderator-1",
        },
        headers={**_headers("user", "moderator-1"), "If-Match": triaged.headers["etag"]},
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["code"] == "ticket_transition_resolution_required"


@pytest.mark.asyncio
async def test_transition_stale_if_match_returns_412(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    # AC3, D10
    ticket, etag = await _create_ticket(migrated_async_client, governance_db)

    missing = await migrated_async_client.post(
        f"{TICKETS_URL}/{ticket['id']}/transitions",
        json={
            "action": "triage",
            "to_state": "triaged",
            "owner_id": "staff-1",
            "priority": "urgent",
            "originating_actor_kind": "user",
            "originating_actor_id": "moderator-1",
        },
        headers=_headers("user", "moderator-1"),
    )
    assert missing.status_code == HTTPStatus.PRECONDITION_REQUIRED

    first = await migrated_async_client.post(
        f"{TICKETS_URL}/{ticket['id']}/transitions",
        json={
            "action": "triage",
            "to_state": "triaged",
            "owner_id": "staff-1",
            "priority": "urgent",
            "originating_actor_kind": "user",
            "originating_actor_id": "moderator-1",
        },
        headers={**_headers("user", "moderator-1"), "If-Match": etag},
    )
    assert first.status_code == HTTPStatus.OK, first.text

    stale = await migrated_async_client.post(
        f"{TICKETS_URL}/{ticket['id']}/transitions",
        json={
            "action": "triage",
            "to_state": "triaged",
            "owner_id": "staff-1",
            "priority": "urgent",
            "originating_actor_kind": "user",
            "originating_actor_id": "moderator-1",
        },
        headers={**_headers("user", "moderator-1"), "If-Match": etag},
    )
    assert stale.status_code == HTTPStatus.PRECONDITION_FAILED
    assert stale.json()["code"] == "stale_ticket_version"


@pytest.mark.asyncio
async def test_transition_rejects_owner_or_priority_change_when_edge_disallows(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    # AC3, D12
    ticket, etag = await _create_ticket(migrated_async_client, governance_db)
    triaged = await migrated_async_client.post(
        f"{TICKETS_URL}/{ticket['id']}/transitions",
        json={
            "action": "triage",
            "to_state": "triaged",
            "owner_id": "staff-1",
            "priority": "urgent",
            "originating_actor_kind": "user",
            "originating_actor_id": "moderator-1",
        },
        headers={**_headers("user", "moderator-1"), "If-Match": etag},
    )
    assert triaged.status_code == HTTPStatus.OK, triaged.text

    owner_forbidden = await migrated_async_client.post(
        f"{TICKETS_URL}/{ticket['id']}/transitions",
        json={
            "action": "close",
            "to_state": "closed",
            "reason": "closing",
            "resolution": "resolved",
            "owner_id": "staff-2",
            "originating_actor_kind": "user",
            "originating_actor_id": "moderator-1",
        },
        headers={**_headers("user", "moderator-1"), "If-Match": triaged.headers["etag"]},
    )
    assert owner_forbidden.status_code == HTTPStatus.CONFLICT

    priority_forbidden = await migrated_async_client.post(
        f"{TICKETS_URL}/{ticket['id']}/transitions",
        json={
            "action": "close",
            "to_state": "closed",
            "reason": "closing",
            "resolution": "resolved",
            "priority": "low",
            "originating_actor_kind": "user",
            "originating_actor_id": "moderator-1",
        },
        headers={**_headers("user", "moderator-1"), "If-Match": triaged.headers["etag"]},
    )
    assert priority_forbidden.status_code == HTTPStatus.CONFLICT
