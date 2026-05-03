from __future__ import annotations

from collections.abc import Iterator
from http import HTTPStatus
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from dependency_injector import providers
from httpx import ASGITransport, AsyncClient
from psycopg.rows import dict_row

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.repositories.db import PostgresDatabase
from tests._authority_helpers import grant_authority


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
    from app.core.context import use_audit_context

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


def _ticket_payload(category_id: str) -> dict[str, Any]:
    return {
        "category_id": category_id,
        "reporter_id": "reporter-1",
        "subject_id": None,
        "priority": "normal",
        "client_ticket_id": "interaction-1",
        "initial_message": {
            "body_markdown": "Initial body",
            "visibility": "reporter_visible",
            "client_message_id": "interaction-1",
            "author_actor_kind": "user",
            "author_actor_id": "reporter-1",
        },
        "originating_actor_kind": "user",
        "originating_actor_id": "reporter-1",
    }


def _fetch_ticket_create_correlation(dsn: str, ticket_id: str) -> str | None:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT correlation_id
            FROM activity_actions
            WHERE aggregate_type = 'ticket'
              AND aggregate_id = %s
              AND action_type = 'ticket.create'
            ORDER BY id DESC
            LIMIT 1
            """,
            (ticket_id,),
        ).fetchone()
    return None if row is None else str(row["correlation_id"])


def _fetch_message_row(dsn: str, ticket_id: str) -> dict[str, Any] | None:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT id, ticket_id, correlation_id, message_seq
            FROM ticket_messages
            WHERE ticket_id = %s
            ORDER BY message_seq ASC
            LIMIT 1
            """,
            (ticket_id,),
        ).fetchone()


def _count_rows(dsn: str, table: str, *, where_sql: str = "TRUE") -> int:
    with psycopg.connect(dsn) as conn:
        row = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where_sql}").fetchone()
    assert row is not None
    return int(row[0])


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


@pytest.mark.asyncio
async def test_create_ticket_persists_initial_message_with_shared_correlation_id(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    # AC2, D6, D11
    _grant(
        governance_db,
        actor_id="discord-ticket-bot",
        permissions=frozenset({"ticket.create", "ticket.message.append"}),
    )
    category = await _create_category(migrated_async_client, governance_db)

    response = await migrated_async_client.post(
        TICKETS_URL,
        json=_ticket_payload(category["id"]),
        headers=_headers("service", "discord-ticket-bot"),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    body = response.json()
    message_row = _fetch_message_row(governance_dsn, body["ticket"]["id"])
    assert message_row is not None
    assert body["initial_message"]["message_seq"] == 1
    assert str(message_row["ticket_id"]) == body["ticket"]["id"]
    assert str(message_row["correlation_id"]) == _fetch_ticket_create_correlation(
        governance_dsn, body["ticket"]["id"]
    )


@pytest.mark.asyncio
async def test_initial_message_failure_rolls_back_ticket_create(
    governance_db: PostgresDatabase,
    governance_dsn: str,
    ticket_app_with_overrides: tuple[Any, Any],
) -> None:
    # AC2, D11
    _grant(
        governance_db,
        actor_id="discord-ticket-bot",
        permissions=frozenset({"ticket.create", "ticket.message.append"}),
    )

    class FakeMessagesService:
        def _boom(self, *_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError("forced append failure")

        def append_ticket_message(self, *_args: Any, **_kwargs: Any) -> Any:
            return self._boom(*_args, **_kwargs)

        def _append_ticket_message_on(self, *_args: Any, **_kwargs: Any) -> Any:
            return self._boom(*_args, **_kwargs)

    app, container = ticket_app_with_overrides
    container.services.ticket_messages.override(providers.Object(FakeMessagesService()))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        category = await _create_category(client, governance_db)

        with pytest.raises(RuntimeError, match="forced append failure"):
            await client.post(
                TICKETS_URL,
                json=_ticket_payload(category["id"]),
                headers=_headers("service", "discord-ticket-bot"),
            )

    assert _count_rows(governance_dsn, "tickets") == 0
    assert _count_rows(governance_dsn, "ticket_messages") == 0
    assert (
        _count_rows(
            governance_dsn,
            "aggregate_heads",
            where_sql="aggregate_type = 'ticket'",
        )
        == 0
    )
