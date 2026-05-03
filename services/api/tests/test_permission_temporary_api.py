from __future__ import annotations

from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from uuid import UUID, uuid4

import psycopg
import pytest
from httpx import AsyncClient

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from tests._authority_helpers import grant_authority


INTENTS_URL = "/api/v1/permission-intents"


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


def _headers(actor_id: str, **extra: str) -> dict[str, str]:
    return {"X-Actor-Kind": "user", "X-Actor-Id": actor_id, **extra}


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


def _intent_payload(
    *,
    temporary: bool = True,
    expires_at: str | None = None,
    scope_kind: str = "global",
    scope_id: str | None = None,
    role_id: str = "role-1",
) -> dict[str, object]:
    return {
        "kind": "guild_role",
        "scope_kind": scope_kind,
        "scope_id": scope_id,
        "role_id": role_id,
        "permission_bits": "8",
        "reason": "temporary access",
        "temporary": temporary,
        "expires_at": expires_at,
    }


async def _create_intent(
    client: AsyncClient,
    *,
    actor_id: str,
    payload: dict[str, object],
) -> dict[str, object]:
    response = await client.post(
        INTENTS_URL,
        json=payload,
        headers=_headers(actor_id),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


def _set_expired_at(governance_dsn: str, *, intent_id: UUID, expired_at: datetime) -> None:
    with psycopg.connect(governance_dsn, autocommit=True) as conn:
        conn.execute(
            "UPDATE permission_intents SET expired_at = %s WHERE id = %s",
            (expired_at, intent_id),
        )


def _latest_action_request_json(
    governance_dsn: str,
    *,
    action_type: str,
) -> dict[str, object]:
    with psycopg.connect(governance_dsn) as conn:
        row = conn.execute(
            """
            SELECT request_json
            FROM activity_actions
            WHERE action_type = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (action_type,),
        ).fetchone()
    assert row is not None
    return row[0]


@pytest.mark.asyncio
async def test_renew_advances_expires_at_and_version(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC1: renew advances expires_at, clears no new lifecycle flags, and emits a new ETag."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_intent.write", "permission_intent.read"}),
    )
    original_expires = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    renewed_expires = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    created = await _create_intent(
        migrated_async_client,
        actor_id="operator",
        payload=_intent_payload(expires_at=original_expires),
    )

    response = await migrated_async_client.post(
        f"{INTENTS_URL}/{created['id']}/renew",
        json={"expires_at": renewed_expires, "reason": "extend review window"},
        headers=_headers("operator", **{"If-Match": '"1"'}),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00")) == datetime.fromisoformat(renewed_expires)
    assert body["expired_at"] is None
    assert response.headers["etag"] == '"2"'
    assert _latest_action_request_json(
        governance_dsn,
        action_type="permission_intent.renew",
    ) == {
        "new_expires_at": renewed_expires,
        "reason": "extend review window",
    }


@pytest.mark.asyncio
async def test_renew_with_stale_if_match_returns_412(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: stale If-Match on renew returns 412 Precondition Failed."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_intent.write", "permission_intent.read"}),
    )
    created = await _create_intent(
        migrated_async_client,
        actor_id="operator",
        payload=_intent_payload(
            expires_at=(datetime.now(UTC) + timedelta(days=1)).isoformat()
        ),
    )

    response = await migrated_async_client.post(
        f"{INTENTS_URL}/{created['id']}/renew",
        json={
            "expires_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "reason": "extend",
        },
        headers=_headers("operator", **{"If-Match": '"0"'}),
    )

    assert response.status_code == HTTPStatus.PRECONDITION_FAILED, response.text
    assert response.json()["code"] == "stale_permission_version"


@pytest.mark.asyncio
async def test_renew_rejects_non_temporary_intent(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC2: renew rejects non-temporary intents with 422 non_temporary_intent."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_intent.write", "permission_intent.read"}),
    )
    created = await _create_intent(
        migrated_async_client,
        actor_id="operator",
        payload=_intent_payload(temporary=False, expires_at=None),
    )

    response = await migrated_async_client.post(
        f"{INTENTS_URL}/{created['id']}/renew",
        json={
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "reason": "extend",
        },
        headers=_headers("operator", **{"If-Match": '"1"'}),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "non_temporary_intent"


@pytest.mark.asyncio
async def test_renew_rejects_intent_with_past_expires_at(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: renew rejects intents whose expires_at is already in the past."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_intent.write", "permission_intent.read"}),
    )
    created = await _create_intent(
        migrated_async_client,
        actor_id="operator",
        payload=_intent_payload(
            expires_at=(datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        ),
    )

    response = await migrated_async_client.post(
        f"{INTENTS_URL}/{created['id']}/renew",
        json={
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "reason": "extend",
        },
        headers=_headers("operator", **{"If-Match": '"1"'}),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "expired_intent"


@pytest.mark.asyncio
async def test_renew_rejects_intent_already_marked_expired(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC1: renew rejects intents whose expired_at stamp is already set."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_intent.write", "permission_intent.read"}),
    )
    created = await _create_intent(
        migrated_async_client,
        actor_id="operator",
        payload=_intent_payload(
            expires_at=(datetime.now(UTC) + timedelta(days=1)).isoformat()
        ),
    )
    created_expires_at = datetime.fromisoformat(
        str(created["expires_at"]).replace("Z", "+00:00")
    )
    _set_expired_at(
        governance_dsn,
        intent_id=UUID(str(created["id"])),
        expired_at=created_expires_at + timedelta(seconds=1),
    )

    response = await migrated_async_client.post(
        f"{INTENTS_URL}/{created['id']}/renew",
        json={
            "expires_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "reason": "extend",
        },
        headers=_headers("operator", **{"If-Match": '"1"'}),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "expired_intent"


@pytest.mark.asyncio
async def test_renew_rejects_past_expires_at_in_body(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: renew rejects request bodies whose expires_at is already in the past."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_intent.write", "permission_intent.read"}),
    )
    created = await _create_intent(
        migrated_async_client,
        actor_id="operator",
        payload=_intent_payload(
            expires_at=(datetime.now(UTC) + timedelta(days=1)).isoformat()
        ),
    )

    response = await migrated_async_client.post(
        f"{INTENTS_URL}/{created['id']}/renew",
        json={
            "expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
            "reason": "extend",
        },
        headers=_headers("operator", **{"If-Match": '"1"'}),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "renewal_expires_at_in_past"


@pytest.mark.asyncio
async def test_renew_blank_reason_returns_422(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: renew rejects blank reasons with 422 validation failure."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_intent.write", "permission_intent.read"}),
    )
    created = await _create_intent(
        migrated_async_client,
        actor_id="operator",
        payload=_intent_payload(
            expires_at=(datetime.now(UTC) + timedelta(days=1)).isoformat()
        ),
    )

    response = await migrated_async_client.post(
        f"{INTENTS_URL}/{created['id']}/renew",
        json={
            "expires_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "reason": "   ",
        },
        headers=_headers("operator", **{"If-Match": '"1"'}),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.asyncio
async def test_renew_requires_permission_intent_write(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: renew requires permission_intent.write at the intent scope."""
    _grant(
        governance_db,
        actor_id="creator",
        permissions=frozenset({"permission_intent.write", "permission_intent.read"}),
    )
    created = await _create_intent(
        migrated_async_client,
        actor_id="creator",
        payload=_intent_payload(
            expires_at=(datetime.now(UTC) + timedelta(days=1)).isoformat()
        ),
    )

    response = await migrated_async_client.post(
        f"{INTENTS_URL}/{created['id']}/renew",
        json={
            "expires_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "reason": "extend",
        },
        headers=_headers("unprivileged", **{"If-Match": '"1"'}),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    assert response.json()["code"] == "authority_decision_denied"
