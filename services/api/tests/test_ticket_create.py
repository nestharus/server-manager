from __future__ import annotations

from collections.abc import Iterator
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

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
    correlation_id = uuid4()
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=None,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=None,
        ),
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


def _operator_headers(actor_id: str = "operator") -> dict[str, str]:
    return {"X-Actor-Kind": "user", "X-Actor-Id": actor_id}


def _service_headers() -> dict[str, str]:
    return {"X-Actor-Kind": "service", "X-Actor-Id": "discord-ticket-bot"}


def _state_machine() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "initial_state": "open",
        "states": [
            {"key": "open", "label": "Open", "terminal": False},
            {"key": "assigned", "label": "Assigned", "terminal": False},
            {"key": "closed", "label": "Closed", "terminal": True},
        ],
        "edges": [
            {
                "from": "open",
                "to": "assigned",
                "action": "assign",
                "requires_reason": False,
                "requires_resolution": False,
                "allow_owner_change": True,
                "allow_priority_change": True,
            },
            {
                "from": "assigned",
                "to": "closed",
                "action": "close",
                "requires_reason": True,
                "requires_resolution": True,
                "allow_owner_change": False,
                "allow_priority_change": False,
            },
        ],
    }


def _category_payload() -> dict[str, Any]:
    return {
        "name": f"Category-{uuid4().hex[:8]}",
        "routing_scope": {
            "scope_kind": "chapter",
            "scope_id": "chapter-1",
            "queue": "officers",
        },
        "privacy_level": "reporter_staff",
        "state_machine": _state_machine(),
        "sla_rules": {"schema_version": 1, "rules": []},
    }


async def _create_category(
    client: AsyncClient,
    db: PostgresDatabase,
) -> dict[str, Any]:
    _grant(db, actor_id="operator", permissions=frozenset({"ticket_category.write"}))
    response = await client.post(
        CATEGORY_URL,
        json=_category_payload(),
        headers=_operator_headers(),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


def _ticket_payload(category_id: str, *, client_ticket_id: str | None = None) -> dict[str, Any]:
    nonce = client_ticket_id or f"interaction-{uuid4().hex[:10]}"
    return {
        "category_id": category_id,
        "reporter_id": "reporter-1",
        "subject_id": "subject-1",
        "priority": "high",
        "client_ticket_id": client_ticket_id,
        "initial_message": {
            "body_markdown": "Initial message",
            "visibility": "reporter_visible",
            "client_message_id": nonce,
            "author_actor_kind": "user",
            "author_actor_id": "reporter-1",
        },
        "originating_actor_kind": "user",
        "originating_actor_id": "reporter-1",
    }


def _count_tickets(dsn: str) -> int:
    with psycopg.connect(dsn) as conn:
        row = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()
    assert row is not None
    return int(row[0])


def _fetch_ticket_head(dsn: str, ticket_id: str | UUID) -> dict[str, Any] | None:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT current_seq
            FROM aggregate_heads
            WHERE aggregate_type = 'ticket'
              AND aggregate_id = %s
            """,
            (str(ticket_id),),
        ).fetchone()


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


@pytest.mark.asyncio
async def test_create_ticket_sets_initial_state_from_snapshot(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    # AC2, D2, D4, D11
    _grant(
        governance_db,
        actor_id="discord-ticket-bot",
        permissions=frozenset({"ticket.create", "ticket.message.append"}),
    )
    category = await _create_category(migrated_async_client, governance_db)

    response = await migrated_async_client.post(
        TICKETS_URL,
        json=_ticket_payload(category["id"]),
        headers=_service_headers(),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    body = response.json()
    assert body["ticket"]["state"] == category["state_machine"]["initial_state"]
    assert body["ticket"]["category_version"] == category["version"]
    assert body["ticket"]["category_snapshot"]["category_id"] == category["id"]
    assert body["ticket"]["category_snapshot"]["state_machine"] == category["state_machine"]
    assert body["initial_message"]["message_seq"] == 1


@pytest.mark.asyncio
async def test_create_ticket_with_duplicate_client_ticket_id_returns_409_existing(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    # AC2, AC4, D13
    _grant(
        governance_db,
        actor_id="discord-ticket-bot",
        permissions=frozenset({"ticket.create", "ticket.message.append"}),
    )
    category = await _create_category(migrated_async_client, governance_db)
    payload = _ticket_payload(category["id"], client_ticket_id="interaction-123")
    first = await migrated_async_client.post(
        TICKETS_URL,
        json=payload,
        headers=_service_headers(),
    )
    assert first.status_code == HTTPStatus.CREATED, first.text

    duplicate = await migrated_async_client.post(
        TICKETS_URL,
        json=payload,
        headers=_service_headers(),
    )

    assert duplicate.status_code == HTTPStatus.CONFLICT
    body = duplicate.json()
    assert body["code"] == "duplicate_ticket_create"
    assert body["ticket"]["id"] == first.json()["ticket"]["id"]
    assert body["initial_message"]["id"] == first.json()["initial_message"]["id"]
    assert duplicate.headers["etag"] == first.headers["etag"]
    assert _count_tickets(governance_dsn) == 1


@pytest.mark.asyncio
async def test_create_ticket_returns_etag_and_scope_snapshot(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    # AC2, D4, D10
    _grant(
        governance_db,
        actor_id="discord-ticket-bot",
        permissions=frozenset({"ticket.create", "ticket.message.append"}),
    )
    category = await _create_category(migrated_async_client, governance_db)

    response = await migrated_async_client.post(
        TICKETS_URL,
        json=_ticket_payload(category["id"]),
        headers=_service_headers(),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    body = response.json()
    assert response.headers["etag"] == '"1"'
    assert body["ticket"]["version"] == 1
    assert body["ticket"]["category_snapshot"]["routing_scope"] == category["routing_scope"]
    head = _fetch_ticket_head(governance_dsn, body["ticket"]["id"])
    assert head is not None
    assert body["ticket"]["version"] == int(head["current_seq"])
