from __future__ import annotations

from collections.abc import Iterator
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from httpx import AsyncClient
from psycopg.rows import dict_row

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.ticket_categories import (
    InvalidTicketSlaRulesError,
    InvalidTicketStateMachineError,
    TicketCategoryCreate,
    TicketCategoryPatch,
)
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.authority import grant_authority
from app.services.ticket_categories import create_ticket_category, update_ticket_category


BASE_URL = "/api/v1/ticket-categories"


def _actor_headers(
    *,
    actor_id: str = "operator",
    actor_kind: str = "user",
) -> dict[str, str]:
    return {"X-Actor-Kind": actor_kind, "X-Actor-Id": actor_id}


def _make_audit_context() -> AuditContextRead:
    correlation_id = uuid4()
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=None,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=None,
        ),
    )


def _actor() -> ActorIdentity:
    return ActorIdentity(actor_kind="user", actor_id="operator")


def _state_machine(*, cycle: bool = False) -> dict[str, Any]:
    edges: list[dict[str, Any]] = [
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
    ]
    if cycle:
        edges.insert(
            1,
            {
                "from": "triaged",
                "to": "open",
                "action": "reopen",
                "requires_reason": False,
                "requires_resolution": False,
                "allow_owner_change": False,
                "allow_priority_change": False,
            },
        )
    return {
        "schema_version": 1,
        "initial_state": "open",
        "states": [
            {"key": "open", "label": "Open", "terminal": False},
            {"key": "triaged", "label": "Triaged", "terminal": False},
            {"key": "closed", "label": "Closed", "terminal": True},
        ],
        "edges": edges,
    }


def _sla_rules(*, target_state: str = "closed") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "rules": [
            {
                "key": "time_to_resolution",
                "states": ["triaged"],
                "thresholds": [
                    {"elapsed_seconds": 3600, "consequence": "notify_owner"},
                    {
                        "elapsed_seconds": 7200,
                        "consequence": "auto_escalate",
                        "target_state": target_state,
                    },
                ],
            }
        ],
    }


def _category_payload() -> dict[str, Any]:
    return {
        "name": f"Appeals-{uuid4().hex[:8]}",
        "routing_scope": {
            "scope_kind": "chapter",
            "scope_id": "chapter-1",
            "queue": "officers",
        },
        "privacy_level": "reporter_staff",
        "state_machine": _state_machine(),
        "sla_rules": _sla_rules(),
    }


def _grant_permissions(
    db: PostgresDatabase,
    *,
    actor_id: str = "operator",
    scope_kind: str = "global",
    scope_id: str | None = None,
    permissions: frozenset[str],
) -> None:
    with use_audit_context(_make_audit_context()):
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


def _fetch_head(dsn: str, category_id: str | UUID) -> dict[str, Any] | None:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT current_seq
            FROM aggregate_heads
            WHERE aggregate_type = 'ticket_category'
              AND aggregate_id = %s
            """,
            (str(category_id),),
        ).fetchone()


@pytest.fixture
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


@pytest.mark.asyncio
async def test_create_category_persists_all_fields(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    # AC1, D1, D3, D7, D10
    _grant_permissions(
        governance_db,
        permissions=frozenset({"ticket_category.write"}),
    )
    payload = _category_payload()

    response = await migrated_async_client.post(
        BASE_URL,
        json=payload,
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    body = response.json()
    assert response.headers["etag"] == '"1"'
    assert body["routing_scope"] == payload["routing_scope"]
    assert body["privacy_level"] == payload["privacy_level"]
    assert body["state_machine"] == payload["state_machine"]
    assert body["sla_rules"]["schema_version"] == 1
    assert body["sla_rules"]["rules"][0]["key"] == "time_to_resolution"
    assert body["sla_rules"]["rules"][0]["thresholds"][-1]["target_state"] == "closed"
    assert body["version"] == 1

    head = _fetch_head(governance_dsn, body["id"])
    assert head is not None
    assert int(head["current_seq"]) == 1


@pytest.mark.asyncio
async def test_update_category_requires_if_match_and_412_on_stale(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    # AC1, D10
    _grant_permissions(
        governance_db,
        permissions=frozenset({"ticket_category.write"}),
    )
    created = await migrated_async_client.post(
        BASE_URL,
        json=_category_payload(),
        headers=_actor_headers(),
    )
    category = created.json()

    missing = await migrated_async_client.patch(
        f"{BASE_URL}/{category['id']}",
        json={"name": "Renamed"},
        headers=_actor_headers(),
    )
    assert missing.status_code == HTTPStatus.PRECONDITION_REQUIRED

    malformed = await migrated_async_client.patch(
        f"{BASE_URL}/{category['id']}",
        json={"name": "Renamed"},
        headers={**_actor_headers(), "If-Match": "W/1"},
    )
    assert malformed.status_code == HTTPStatus.PRECONDITION_FAILED

    updated = await migrated_async_client.patch(
        f"{BASE_URL}/{category['id']}",
        json={"name": "Renamed"},
        headers={**_actor_headers(), "If-Match": created.headers["etag"]},
    )
    assert updated.status_code == HTTPStatus.OK, updated.text
    assert updated.headers["etag"] == '"2"'

    stale = await migrated_async_client.patch(
        f"{BASE_URL}/{category['id']}",
        json={"name": "Renamed Again"},
        headers={**_actor_headers(), "If-Match": created.headers["etag"]},
    )
    assert stale.status_code == HTTPStatus.PRECONDITION_FAILED
    assert stale.json()["code"] == "stale_ticket_category_version"


@pytest.mark.asyncio
async def test_create_category_accepts_cycles_when_terminal_remains_reachable(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    # AC1, D3
    _grant_permissions(
        governance_db,
        permissions=frozenset({"ticket_category.write"}),
    )
    payload = _category_payload()
    payload["state_machine"] = _state_machine(cycle=True)

    response = await migrated_async_client.post(
        BASE_URL,
        json=payload,
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text


def test_create_category_rejects_unreachable_terminal(
    governance_db: PostgresDatabase,
) -> None:
    payload = _category_payload()
    payload["state_machine"]["edges"] = [
        {
            "from": "open",
            "to": "triaged",
            "action": "triage",
            "requires_reason": False,
            "requires_resolution": False,
            "allow_owner_change": False,
            "allow_priority_change": False,
        },
        {
            "from": "triaged",
            "to": "open",
            "action": "reopen",
            "requires_reason": False,
            "requires_resolution": False,
            "allow_owner_change": False,
            "allow_priority_change": False,
        },
    ]
    request = TicketCategoryCreate.model_validate(payload)

    with pytest.raises(InvalidTicketStateMachineError):
        create_ticket_category(governance_db, request, _actor())


@pytest.mark.asyncio
async def test_create_category_rejects_disconnected_state(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    # AC1, D3
    _grant_permissions(
        governance_db,
        permissions=frozenset({"ticket_category.write"}),
    )
    payload = _category_payload()
    payload["state_machine"]["states"].append(
        {"key": "orphan", "label": "Orphan", "terminal": False}
    )

    response = await migrated_async_client.post(
        BASE_URL,
        json=payload,
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["code"] == "invalid_state_machine"


@pytest.mark.asyncio
async def test_create_category_rejects_invalid_state_machine_no_reachable_terminal(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    # AC1, D3
    _grant_permissions(
        governance_db,
        permissions=frozenset({"ticket_category.write"}),
    )
    payload = _category_payload()
    payload["state_machine"]["edges"] = [
        {
            "from": "open",
            "to": "triaged",
            "action": "triage",
            "requires_reason": False,
            "requires_resolution": False,
            "allow_owner_change": False,
            "allow_priority_change": False,
        },
        {
            "from": "triaged",
            "to": "open",
            "action": "reopen",
            "requires_reason": False,
            "requires_resolution": False,
            "allow_owner_change": False,
            "allow_priority_change": False,
        },
    ]

    response = await migrated_async_client.post(
        BASE_URL,
        json=payload,
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["code"] == "invalid_state_machine"


@pytest.mark.asyncio
async def test_create_category_rejects_duplicate_edge(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    # AC1, D3
    _grant_permissions(
        governance_db,
        permissions=frozenset({"ticket_category.write"}),
    )
    payload = _category_payload()
    payload["state_machine"]["edges"].append(
        dict(payload["state_machine"]["edges"][0])
    )

    response = await migrated_async_client.post(
        BASE_URL,
        json=payload,
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["code"] == "invalid_state_machine"


@pytest.mark.asyncio
async def test_create_category_rejects_missing_initial_state(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    # AC1, D3
    _grant_permissions(
        governance_db,
        permissions=frozenset({"ticket_category.write"}),
    )
    payload = _category_payload()
    payload["state_machine"]["initial_state"] = "missing"

    response = await migrated_async_client.post(
        BASE_URL,
        json=payload,
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["code"] == "invalid_state_machine"


@pytest.mark.asyncio
async def test_create_category_rejects_sla_with_nonexistent_state(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    # AC1, D7
    _grant_permissions(
        governance_db,
        permissions=frozenset({"ticket_category.write"}),
    )
    payload = _category_payload()
    payload["sla_rules"]["rules"][0]["states"] = ["missing"]

    response = await migrated_async_client.post(
        BASE_URL,
        json=payload,
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["code"] == "invalid_sla_rules"


def test_patch_category_rejects_sla_with_nonexistent_state(
    governance_db: PostgresDatabase,
) -> None:
    with use_audit_context(_make_audit_context()):
        category, _result = create_ticket_category(
            governance_db,
            TicketCategoryCreate.model_validate(_category_payload()),
            _actor(),
        )
    request = TicketCategoryPatch.model_validate(
        {
            "sla_rules": {
                "schema_version": 1,
                "rules": [
                    {
                        "key": "bad_state",
                        "states": ["missing"],
                        "thresholds": [
                            {"elapsed_seconds": 60, "consequence": "notify_owner"},
                        ],
                    }
                ],
            }
        }
    )

    with pytest.raises(InvalidTicketSlaRulesError):
        update_ticket_category(
            governance_db,
            category.id,
            category.version,
            request,
            _actor(),
        )


@pytest.mark.asyncio
async def test_create_category_rejects_sla_non_monotonic_thresholds(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    # AC1, D7
    _grant_permissions(
        governance_db,
        permissions=frozenset({"ticket_category.write"}),
    )
    payload = _category_payload()
    payload["sla_rules"]["rules"][0]["thresholds"][1]["elapsed_seconds"] = 3599

    response = await migrated_async_client.post(
        BASE_URL,
        json=payload,
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_create_category_rejects_auto_escalate_target_state_without_reachability(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    # AC1, D7
    _grant_permissions(
        governance_db,
        permissions=frozenset({"ticket_category.write"}),
    )
    payload = _category_payload()
    payload["state_machine"]["states"].append(
        {"key": "escalated", "label": "Escalated", "terminal": False}
    )
    payload["sla_rules"] = _sla_rules(target_state="escalated")

    response = await migrated_async_client.post(
        BASE_URL,
        json=payload,
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_category_create_response_returns_version_from_aggregate_heads(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    # AC1, D1, D10
    _grant_permissions(
        governance_db,
        permissions=frozenset({"ticket_category.write"}),
    )
    response = await migrated_async_client.post(
        BASE_URL,
        json=_category_payload(),
        headers=_actor_headers(),
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    body = response.json()
    head = _fetch_head(governance_dsn, body["id"])
    assert head is not None
    assert body["version"] == int(head["current_seq"])
    assert response.headers["etag"] == f'"{body["version"]}"'
