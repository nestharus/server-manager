from __future__ import annotations

import asyncio
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
from tests._authority_helpers import grant_authority


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
            {"key": "closed", "label": "Closed", "terminal": True},
        ],
        "edges": [
            {
                "from": "open",
                "to": "closed",
                "action": "close",
                "requires_reason": True,
                "requires_resolution": True,
                "allow_owner_change": False,
                "allow_priority_change": False,
            }
        ],
    }


async def _create_category(
    client: AsyncClient,
    db: PostgresDatabase,
    *,
    privacy_level: str = "reporter_staff",
) -> dict[str, Any]:
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
            "privacy_level": privacy_level,
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
    *,
    privacy_level: str = "reporter_staff",
) -> dict[str, Any]:
    _grant(
        db,
        actor_id="discord-ticket-bot",
        permissions=frozenset({"ticket.create", "ticket.message.append"}),
    )
    category = await _create_category(client, db, privacy_level=privacy_level)
    response = await client.post(
        TICKETS_URL,
        json={
            "category_id": category["id"],
            "reporter_id": "reporter-1",
            "subject_id": None,
            "priority": "normal",
            "client_ticket_id": f"interaction-{uuid4().hex[:8]}",
            "initial_message": {
                "body_markdown": "Initial reporter message",
                "visibility": "reporter_visible",
                "client_message_id": f"msg-{uuid4().hex[:8]}",
                "author_actor_kind": "user",
                "author_actor_id": "reporter-1",
            },
            "originating_actor_kind": "user",
            "originating_actor_id": "reporter-1",
        },
        headers=_headers("service", "discord-ticket-bot"),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()["ticket"]


def _message_rows(dsn: str, ticket_id: str) -> list[dict[str, Any]]:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT message_seq, visibility, client_message_id, author_actor_id
            FROM ticket_messages
            WHERE ticket_id = %s
            ORDER BY message_seq ASC
            """,
            (ticket_id,),
        ).fetchall()


@pytest.fixture
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


@pytest.mark.asyncio
async def test_append_message_with_duplicate_client_message_id_returns_existing(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    # AC2, D6, D13
    _grant(
        governance_db,
        actor_id="staff-1",
        scope_kind="chapter",
        scope_id="chapter-1",
        permissions=frozenset({"ticket.message.staff"}),
    )
    ticket = await _create_ticket(migrated_async_client, governance_db)
    payload = {
        "body_markdown": "Staff note",
        "visibility": "staff_only",
        "client_message_id": "staff-note-1",
        "author_actor_kind": "user",
        "author_actor_id": "staff-1",
    }

    first = await migrated_async_client.post(
        f"{TICKETS_URL}/{ticket['id']}/messages",
        json=payload,
        headers=_headers("service", "discord-ticket-bot"),
    )
    second = await migrated_async_client.post(
        f"{TICKETS_URL}/{ticket['id']}/messages",
        json=payload,
        headers=_headers("service", "discord-ticket-bot"),
    )

    assert first.status_code == HTTPStatus.CREATED, first.text
    assert second.status_code == HTTPStatus.OK, second.text
    assert second.json()["id"] == first.json()["id"]


@pytest.mark.asyncio
async def test_append_message_locks_ticket_for_seq_assignment(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    # AC2, D6
    _grant(
        governance_db,
        actor_id="staff-1",
        scope_kind="chapter",
        scope_id="chapter-1",
        permissions=frozenset({"ticket.message.staff"}),
    )
    ticket = await _create_ticket(migrated_async_client, governance_db)

    async def _append(index: int) -> None:
        response = await migrated_async_client.post(
            f"{TICKETS_URL}/{ticket['id']}/messages",
            json={
                "body_markdown": f"Staff note {index}",
                "visibility": "staff_only",
                "client_message_id": f"staff-note-{index}",
                "author_actor_kind": "user",
                "author_actor_id": "staff-1",
            },
            headers=_headers("service", "discord-ticket-bot"),
        )
        assert response.status_code == HTTPStatus.CREATED, response.text

    await asyncio.gather(_append(1), _append(2))

    rows = _message_rows(governance_dsn, ticket["id"])
    assert [int(row["message_seq"]) for row in rows] == [1, 2, 3]


@pytest.mark.asyncio
async def test_reporter_cannot_read_staff_only_messages(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    # AC2, D8
    _grant(
        governance_db,
        actor_id="staff-1",
        scope_kind="chapter",
        scope_id="chapter-1",
        permissions=frozenset({"ticket.message.staff"}),
    )
    ticket = await _create_ticket(migrated_async_client, governance_db)
    response = await migrated_async_client.post(
        f"{TICKETS_URL}/{ticket['id']}/messages",
        json={
            "body_markdown": "Staff-only note",
            "visibility": "staff_only",
            "client_message_id": "staff-only-1",
            "author_actor_kind": "user",
            "author_actor_id": "staff-1",
        },
        headers=_headers("service", "discord-ticket-bot"),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text

    messages = await migrated_async_client.get(
        f"{TICKETS_URL}/{ticket['id']}/messages",
        headers=_headers("user", "reporter-1"),
    )

    assert messages.status_code == HTTPStatus.OK, messages.text
    items = messages.json()["items"]
    assert len(items) == 1
    assert items[0]["visibility"] == "reporter_visible"


@pytest.mark.asyncio
async def test_reporter_with_ticket_read_authority_sees_staff_only_messages(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    _grant(
        governance_db,
        actor_id="staff-1",
        scope_kind="chapter",
        scope_id="chapter-1",
        permissions=frozenset({"ticket.message.staff"}),
    )
    _grant(
        governance_db,
        actor_id="reporter-1",
        scope_kind="chapter",
        scope_id="chapter-1",
        permissions=frozenset({"ticket.read"}),
    )
    ticket = await _create_ticket(migrated_async_client, governance_db)
    response = await migrated_async_client.post(
        f"{TICKETS_URL}/{ticket['id']}/messages",
        json={
            "body_markdown": "Staff-only note",
            "visibility": "staff_only",
            "client_message_id": "staff-only-1",
            "author_actor_kind": "user",
            "author_actor_id": "staff-1",
        },
        headers=_headers("service", "discord-ticket-bot"),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text

    messages = await migrated_async_client.get(
        f"{TICKETS_URL}/{ticket['id']}/messages",
        headers=_headers("user", "reporter-1"),
    )

    assert messages.status_code == HTTPStatus.OK, messages.text
    assert [item["visibility"] for item in messages.json()["items"]] == [
        "reporter_visible",
        "staff_only",
    ]


@pytest.mark.asyncio
async def test_staff_only_category_reporter_cannot_read(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    # AC2, D8
    ticket = await _create_ticket(
        migrated_async_client,
        governance_db,
        privacy_level="staff_only",
    )

    response = await migrated_async_client.get(
        f"{TICKETS_URL}/{ticket['id']}",
        headers=_headers("user", "reporter-1"),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_staff_only_append_requires_ticket_message_staff_authority(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    # AC2, D9
    ticket = await _create_ticket(migrated_async_client, governance_db)

    response = await migrated_async_client.post(
        f"{TICKETS_URL}/{ticket['id']}/messages",
        json={
            "body_markdown": "Staff-only note",
            "visibility": "staff_only",
            "client_message_id": "staff-only-1",
            "author_actor_kind": "user",
            "author_actor_id": "staff-1",
        },
        headers=_headers("service", "discord-ticket-bot"),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
