from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from uuid import uuid4

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


@pytest.fixture
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


def _guild_role_payload(
    *,
    scope_kind: str = "global",
    scope_id: str | None = None,
    role_id: str = "role-1",
    permission_bits: str = "8",
) -> dict[str, object]:
    return {
        "kind": "guild_role",
        "scope_kind": scope_kind,
        "scope_id": scope_id,
        "role_id": role_id,
        "permission_bits": permission_bits,
        "reason": "test",
        "temporary": False,
        "expires_at": None,
    }


def _channel_role_payload(
    *,
    scope_kind: str = "chapter",
    scope_id: str | None = "chapter-1",
    role_id: str = "role-1",
    channel_id: str = "channel-1",
    allow_bits: str = "1",
    deny_bits: str = "0",
) -> dict[str, object]:
    return {
        "kind": "channel_role",
        "scope_kind": scope_kind,
        "scope_id": scope_id,
        "role_id": role_id,
        "channel_id": channel_id,
        "allow_bits": allow_bits,
        "deny_bits": deny_bits,
        "reason": "test",
        "temporary": False,
        "expires_at": None,
    }


@pytest.mark.asyncio
async def test_create_intent_persists_full_target_and_returns_etag(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: create intent persists target and returns strong ETag '1'."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {"permission_intent.write", "permission_intent.read"}
        ),
    )
    response = await migrated_async_client.post(
        INTENTS_URL,
        json=_guild_role_payload(),
        headers=_headers("operator"),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    body = response.json()
    assert body["kind"] == "guild_role"
    assert body["scope_kind"] == "global"
    assert body["role_id"] == "role-1"
    assert body["permission_bits"] == "8"
    assert response.headers["etag"] == '"1"'
    assert body["id"]


@pytest.mark.asyncio
async def test_patch_intent_with_matching_if_match_advances_version(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: PATCH with matching If-Match advances version and returns new ETag."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {"permission_intent.write", "permission_intent.read"}
        ),
    )
    created = await migrated_async_client.post(
        INTENTS_URL,
        json=_guild_role_payload(),
        headers=_headers("operator"),
    )
    intent_id = created.json()["id"]
    patched = await migrated_async_client.patch(
        f"{INTENTS_URL}/{intent_id}",
        json={"permission_bits": "16", "reason": "updated"},
        headers=_headers("operator", **{"If-Match": '"1"'}),
    )
    assert patched.status_code == HTTPStatus.OK, patched.text
    assert patched.json()["permission_bits"] == "16"
    assert patched.headers["etag"] == '"2"'


@pytest.mark.asyncio
async def test_patch_intent_with_stale_if_match_returns_412(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: PATCH with stale If-Match returns 412."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {"permission_intent.write", "permission_intent.read"}
        ),
    )
    created = await migrated_async_client.post(
        INTENTS_URL,
        json=_guild_role_payload(),
        headers=_headers("operator"),
    )
    intent_id = created.json()["id"]
    patched = await migrated_async_client.patch(
        f"{INTENTS_URL}/{intent_id}",
        json={"permission_bits": "16"},
        headers=_headers("operator", **{"If-Match": '"0"'}),
    )
    assert patched.status_code == HTTPStatus.PRECONDITION_FAILED, patched.text
    assert patched.json()["code"] == "stale_permission_version"


@pytest.mark.asyncio
async def test_create_intent_rejects_scope_kind_member(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1 (D1): scope_kind='member' is rejected at the contract layer."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_intent.write"}),
    )
    payload = _guild_role_payload()
    payload["scope_kind"] = "member"
    response = await migrated_async_client.post(
        INTENTS_URL,
        json=payload,
        headers=_headers("operator"),
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_create_guild_role_intent_rejects_allow_deny_fields(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: guild_role intent forbids allow/deny fields."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_intent.write"}),
    )
    payload = _guild_role_payload()
    payload["allow_bits"] = "1"
    response = await migrated_async_client.post(
        INTENTS_URL,
        json=payload,
        headers=_headers("operator"),
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_create_channel_role_intent_requires_channel_allow_deny(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: channel_role intent requires channel_id + allow_bits + deny_bits."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset({"permission_intent.write"}),
        scope_kind="chapter",
        scope_id=None,
    )
    response = await migrated_async_client.post(
        INTENTS_URL,
        json=_channel_role_payload(),
        headers=_headers("operator"),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    body = response.json()
    assert body["channel_id"] == "channel-1"
    assert body["allow_bits"] == "1"
    assert body["deny_bits"] == "0"


@pytest.mark.asyncio
async def test_list_intents_filters_by_scope_kind_scope_id(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: list filters by scope_kind/scope_id (D10)."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {"permission_intent.write", "permission_intent.read"}
        ),
    )
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {"permission_intent.write", "permission_intent.read"}
        ),
        scope_kind="chapter",
        scope_id=None,
    )
    # Create a global and a chapter intent.
    await migrated_async_client.post(
        INTENTS_URL,
        json=_guild_role_payload(role_id="g-1"),
        headers=_headers("operator"),
    )
    await migrated_async_client.post(
        INTENTS_URL,
        json=_guild_role_payload(
            scope_kind="chapter", scope_id="chapter-1", role_id="c-1",
        ),
        headers=_headers("operator"),
    )
    list_response = await migrated_async_client.get(
        INTENTS_URL,
        params={"scope_kind": "chapter", "scope_id": "chapter-1"},
        headers=_headers("operator"),
    )
    assert list_response.status_code == HTTPStatus.OK, list_response.text
    rows = list_response.json()
    assert len(rows) == 1
    assert rows[0]["role_id"] == "c-1"


@pytest.mark.asyncio
async def test_list_intents_excludes_expired_by_default(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: expired intents are excluded unless include_expired=true."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {"permission_intent.write", "permission_intent.read"}
        ),
    )
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    payload_past = _guild_role_payload(role_id="expired")
    payload_past["temporary"] = True
    payload_past["expires_at"] = past
    payload_future = _guild_role_payload(role_id="future")
    payload_future["temporary"] = True
    payload_future["expires_at"] = future
    await migrated_async_client.post(
        INTENTS_URL, json=payload_past, headers=_headers("operator"),
    )
    await migrated_async_client.post(
        INTENTS_URL, json=payload_future, headers=_headers("operator"),
    )

    default_list = await migrated_async_client.get(
        INTENTS_URL,
        params={"scope_kind": "global"},
        headers=_headers("operator"),
    )
    assert default_list.status_code == HTTPStatus.OK
    roles = {row["role_id"] for row in default_list.json()}
    assert "future" in roles
    assert "expired" not in roles

    included = await migrated_async_client.get(
        INTENTS_URL,
        params={"scope_kind": "global", "include_expired": True},
        headers=_headers("operator"),
    )
    assert included.status_code == HTTPStatus.OK
    assert {row["role_id"] for row in included.json()} == {"expired", "future"}


@pytest.mark.asyncio
async def test_list_intents_requires_permission_intent_read(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: listing requires permission_intent.read authority."""
    response = await migrated_async_client.get(
        INTENTS_URL,
        params={"scope_kind": "global"},
        headers=_headers("unprivileged"),
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_patch_intent_requires_permission_intent_write(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: PATCH requires permission_intent.write authority."""
    _grant(
        governance_db,
        actor_id="operator",
        permissions=frozenset(
            {"permission_intent.write", "permission_intent.read"}
        ),
    )
    created = await migrated_async_client.post(
        INTENTS_URL,
        json=_guild_role_payload(),
        headers=_headers("operator"),
    )
    intent_id = created.json()["id"]
    response = await migrated_async_client.patch(
        f"{INTENTS_URL}/{intent_id}",
        json={"permission_bits": "32"},
        headers=_headers("unprivileged", **{"If-Match": '"1"'}),
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
