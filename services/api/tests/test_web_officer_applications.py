from __future__ import annotations

import inspect
from collections.abc import Iterable
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from httpx import AsyncClient

from app.repositories.db import PostgresDatabase

from .public_intake_fixtures import applicant_receipt_token
from .test_applications_list import (
    _claim_application,
    _create_application,
    _create_member,
    _grant,
)


OFFICER_APPLICATIONS_URL = "/api/v1/web/officer/applications"
APPLICATIONS_URL = "/api/v1/applications"


def _pomerium_headers(
    *,
    subject: str = "humility-officer-1",
    email: str = "officer@humility.local",
    display_name: str = "Humility Officer",
    groups: str | None = "officers",
    discord_user_id: str | None = "210987654321098765",
    **extra: str,
) -> dict[str, str]:
    headers = {
        "x-pomerium-claim-sub": subject,
        "x-pomerium-claim-email": email,
        "x-pomerium-claim-name": display_name,
        **extra,
    }
    if groups is not None:
        headers["x-pomerium-claim-groups"] = groups
    if discord_user_id is not None:
        headers["x-pomerium-claim-discord-user-id"] = discord_user_id
    return headers


def _officer_member_with_grants(
    db: PostgresDatabase,
    *,
    discord_user_id: str = "210987654321098765",
    permissions: frozenset[str] = frozenset({"application.review", "application.claim"}),
    scope_kind: str = "chapter",
    scope_id: str | None = "chapter-1",
) -> str:
    member_id = _create_member(db, discord_user_id)
    _grant(
        db,
        actor_id=member_id,
        permissions=permissions,
        scope_kind=scope_kind,
        scope_id=scope_id,
    )
    return member_id


async def _claim_via_officer_bridge(
    client: AsyncClient,
    *,
    application_id: str,
    etag: str | None,
    headers: dict[str, str],
) -> Any:
    request_headers = dict(headers)
    if etag is not None:
        request_headers["If-Match"] = etag
    return await client.post(
        f"{OFFICER_APPLICATIONS_URL}/{application_id}/claim",
        headers=request_headers,
    )


def _actor_headers(actor_id: str, **extra: str) -> dict[str, str]:
    return {"X-Actor-Kind": "user", "X-Actor-Id": actor_id, **extra}


async def _append_application_message_via_api(
    client: AsyncClient,
    *,
    application_id: str,
    author_actor_id: str,
    visibility: str,
    body_markdown: str,
) -> dict[str, Any]:
    response = await client.post(
        f"{APPLICATIONS_URL}/{application_id}/messages",
        json={
            "body_markdown": body_markdown,
            "visibility": visibility,
            "client_message_id": f"officer-transcript-{uuid4().hex}",
            "author_actor_kind": "user",
            "author_actor_id": author_actor_id,
        },
        headers=_actor_headers(author_actor_id),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


def _set_application_state(
    db: PostgresDatabase,
    *,
    application_id: str,
    state: str,
) -> None:
    with db.connection() as connection:
        connection.execute(
            """
            UPDATE applications
               SET state = %s,
                   queued_at = CASE WHEN %s = 'submitted' THEN NULL ELSE queued_at END
             WHERE id = %s
            """,
            (state, state, UUID(application_id)),
        )


def _member_id_for_discord_user(governance_dsn: str, discord_user_id: str) -> str | None:
    with psycopg.connect(governance_dsn) as connection:
        row = connection.execute(
            "SELECT id FROM members WHERE discord_user_id = %s",
            (discord_user_id,),
        ).fetchone()
    return str(row[0]) if row else None


def _latest_activity_action(
    governance_dsn: str,
    *,
    aggregate_type: str,
    aggregate_id: str,
    action_type: str | None = None,
) -> dict[str, Any] | None:
    sql = """
        SELECT actor_kind, actor_id, action_type, request_surface
          FROM activity_actions
         WHERE aggregate_type = %s AND aggregate_id = %s
    """
    params: list[Any] = [aggregate_type, aggregate_id]
    if action_type is not None:
        sql += " AND action_type = %s"
        params.append(action_type)
    sql += " ORDER BY recorded_at DESC LIMIT 1"
    with psycopg.connect(governance_dsn) as connection:
        row = connection.execute(sql, params).fetchone()
    if row is None:
        return None
    return {
        "actor_kind": row[0],
        "actor_id": row[1],
        "action_type": row[2],
        "request_surface": row[3],
    }


def _flatten_route_dependencies(route: APIRoute) -> Iterable[Any]:
    pending = list(route.dependant.dependencies)
    while pending:
        dependant = pending.pop()
        if dependant.call is not None:
            yield dependant.call
        pending.extend(dependant.dependencies)


def _error_code(response) -> str:
    assert response.json()["code"]
    return response.json()["code"]


@pytest.mark.asyncio
async def test_officer_list_requires_pomerium_identity(
    migrated_async_client: AsyncClient,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=identity_required;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    response = await migrated_async_client.get(OFFICER_APPLICATIONS_URL)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert _error_code(response) == "identity_missing"


@pytest.mark.asyncio
async def test_officer_list_requires_officers_group(
    migrated_async_client: AsyncClient,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=officer_group_required;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    response = await migrated_async_client.get(
        OFFICER_APPLICATIONS_URL,
        headers=_pomerium_headers(groups="applicants"),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert _error_code(response) == "officer_required"


@pytest.mark.asyncio
async def test_officer_list_groups_parsing_comma(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=groups_parsing;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    _officer_member_with_grants(governance_db, scope_kind="chapter", scope_id="chapter-1")

    response = await migrated_async_client.get(
        OFFICER_APPLICATIONS_URL,
        params={"scope_kind": "chapter", "scope_id": "chapter-1"},
        headers=_pomerium_headers(groups="officers, admins"),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert set(response.json()) == {"items", "next_after_id"}


@pytest.mark.asyncio
async def test_officer_list_groups_parsing_json(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=groups_parsing_version_tolerant;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    _officer_member_with_grants(governance_db, scope_kind="chapter", scope_id="chapter-1")

    response = await migrated_async_client.get(
        OFFICER_APPLICATIONS_URL,
        params={"scope_kind": "chapter", "scope_id": "chapter-1"},
        headers=_pomerium_headers(groups='["officers", "admins"]'),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert set(response.json()) == {"items", "next_after_id"}


@pytest.mark.asyncio
async def test_officer_list_requires_discord_claim(
    migrated_async_client: AsyncClient,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=discord_claim_required;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    response = await migrated_async_client.get(
        OFFICER_APPLICATIONS_URL,
        headers=_pomerium_headers(discord_user_id=None),
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert _error_code(response) == "officer_discord_identity_missing"


@pytest.mark.asyncio
async def test_officer_list_invalid_discord_claim(
    migrated_async_client: AsyncClient,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=discord_claim_shape;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    response = await migrated_async_client.get(
        OFFICER_APPLICATIONS_URL,
        headers=_pomerium_headers(discord_user_id="not-a-snowflake"),
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert _error_code(response) == "officer_discord_identity_invalid"


@pytest.mark.asyncio
async def test_officer_list_member_resolution_non_discord(
    migrated_async_client: AsyncClient,
    synthetic_member_guard_member_factory,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=member_resolution_non_discord;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    synthetic_member_guard_member_factory.create(
        discord_user_id="210987654321098765",
        kind="public_intake",
    )

    response = await migrated_async_client.get(
        OFFICER_APPLICATIONS_URL,
        headers=_pomerium_headers(),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _error_code(response) == "officer_discord_member_invalid"


@pytest.mark.asyncio
async def test_officer_list_returns_application_list_read(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=happy_path;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    _officer_member_with_grants(
        governance_db,
        permissions=frozenset({"application.review"}),
        scope_kind="chapter",
        scope_id="chapter-1",
    )
    application, _etag = await _create_application(migrated_async_client, governance_db)

    response = await migrated_async_client.get(
        OFFICER_APPLICATIONS_URL,
        params={"state": "queued", "scope_kind": "chapter", "scope_id": "chapter-1"},
        headers=_pomerium_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert set(body) == {"items", "next_after_id"}
    assert body["items"][0]["id"] == application["id"]
    assert body["items"][0]["state"] == "queued"
    assert body["next_after_id"] is None


@pytest.mark.asyncio
async def test_officer_list_authority_denied(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=authority_denied;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    _create_member(governance_db, "210987654321098765")

    response = await migrated_async_client.get(
        OFFICER_APPLICATIONS_URL,
        headers=_pomerium_headers(),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert _error_code(response) == "application_list_forbidden"


@pytest.mark.asyncio
async def test_officer_claim_requires_if_match(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=if_match_required;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    _officer_member_with_grants(governance_db)
    application, _etag = await _create_application(migrated_async_client, governance_db)

    response = await _claim_via_officer_bridge(
        migrated_async_client,
        application_id=application["id"],
        etag=None,
        headers=_pomerium_headers(),
    )

    assert response.status_code == HTTPStatus.PRECONDITION_REQUIRED
    assert _error_code(response) == "if_match_required"


@pytest.mark.asyncio
async def test_officer_claim_invalid_if_match(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=if_match_shape;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    _officer_member_with_grants(governance_db)
    application, _etag = await _create_application(migrated_async_client, governance_db)

    response = await _claim_via_officer_bridge(
        migrated_async_client,
        application_id=application["id"],
        etag="2",
        headers=_pomerium_headers(),
    )

    assert response.status_code == HTTPStatus.PRECONDITION_FAILED
    assert _error_code(response) == "invalid_if_match"


@pytest.mark.asyncio
async def test_officer_claim_stale_version(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=stale_version;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    officer_id = _officer_member_with_grants(governance_db)
    other_owner = _create_member(governance_db, "210987654321098766")
    application, stale_etag = await _create_application(migrated_async_client, governance_db)
    _grant(
        governance_db,
        actor_id=other_owner,
        permissions=frozenset({"application.claim"}),
        scope_kind=application["target_scope"]["scope_kind"],
        scope_id=application["target_scope"]["scope_id"],
    )
    assert officer_id != other_owner
    await _claim_application(
        migrated_async_client,
        governance_db,
        application=application,
        etag=stale_etag,
        owner_id=other_owner,
    )

    response = await _claim_via_officer_bridge(
        migrated_async_client,
        application_id=application["id"],
        etag=stale_etag,
        headers=_pomerium_headers(),
    )

    assert response.status_code == HTTPStatus.PRECONDITION_FAILED
    assert _error_code(response) == "stale_application_version"


@pytest.mark.asyncio
async def test_officer_claim_happy_path(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=claim_happy_path;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    officer_id = _officer_member_with_grants(governance_db)
    application, etag = await _create_application(migrated_async_client, governance_db)

    response = await _claim_via_officer_bridge(
        migrated_async_client,
        application_id=application["id"],
        etag=etag,
        headers=_pomerium_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["owner_id"] == officer_id
    assert body["state"] == "claimed"
    assert response.headers["etag"] == f'"{body["version"]}"'


@pytest.mark.asyncio
async def test_officer_claim_audit_request_surface(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=audit_request_surface;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    _officer_member_with_grants(governance_db)
    application, etag = await _create_application(migrated_async_client, governance_db)

    response = await _claim_via_officer_bridge(
        migrated_async_client,
        application_id=application["id"],
        etag=etag,
        headers=_pomerium_headers(),
    )
    assert response.status_code == HTTPStatus.OK, response.text

    action = _latest_activity_action(
        governance_dsn,
        aggregate_type="application",
        aggregate_id=application["id"],
        action_type="application.claim",
    )
    assert action is not None
    assert (
        action["request_surface"]
        == f"api:/api/v1/web/officer/applications/{application['id']}/claim"
    )


@pytest.mark.asyncio
async def test_officer_claim_authority_denied(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=claim_authority_denied;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    _officer_member_with_grants(
        governance_db,
        permissions=frozenset({"application.review"}),
    )
    application, etag = await _create_application(migrated_async_client, governance_db)

    response = await _claim_via_officer_bridge(
        migrated_async_client,
        application_id=application["id"],
        etag=etag,
        headers=_pomerium_headers(),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert _error_code(response) == "authority_decision_denied"


@pytest.mark.asyncio
async def test_officer_claim_already_claimed(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=already_claimed;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    _officer_member_with_grants(governance_db)
    other_owner = _create_member(governance_db, "210987654321098767")
    application, etag = await _create_application(migrated_async_client, governance_db)
    claimed, claimed_etag = await _claim_application(
        migrated_async_client,
        governance_db,
        application=application,
        etag=etag,
        owner_id=other_owner,
    )

    response = await _claim_via_officer_bridge(
        migrated_async_client,
        application_id=application["id"],
        etag=claimed_etag,
        headers=_pomerium_headers(),
    )

    assert claimed["owner_id"] == other_owner
    assert response.status_code == HTTPStatus.CONFLICT
    assert _error_code(response) == "application_already_claimed"


@pytest.mark.asyncio
async def test_officer_claim_invalid_transition(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=invalid_transition;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    _officer_member_with_grants(governance_db)
    application, etag = await _create_application(migrated_async_client, governance_db)
    _set_application_state(governance_db, application_id=application["id"], state="submitted")

    response = await _claim_via_officer_bridge(
        migrated_async_client,
        application_id=application["id"],
        etag=etag,
        headers=_pomerium_headers(),
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert _error_code(response) == "invalid_application_transition"


@pytest.mark.asyncio
async def test_officer_claim_not_found(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=not_found;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    _officer_member_with_grants(governance_db)

    response = await _claim_via_officer_bridge(
        migrated_async_client,
        application_id=str(uuid4()),
        etag='"1"',
        headers=_pomerium_headers(),
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert _error_code(response) == "application_not_found"


@pytest.mark.asyncio
async def test_officer_claim_first_login_creates_member(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=first_login_member_create;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    first_login_snowflake = "210987654321098768"
    application, etag = await _create_application(migrated_async_client, governance_db)
    assert _member_id_for_discord_user(governance_dsn, first_login_snowflake) is None

    response = await _claim_via_officer_bridge(
        migrated_async_client,
        application_id=application["id"],
        etag=etag,
        headers=_pomerium_headers(discord_user_id=first_login_snowflake),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert _error_code(response) == "authority_decision_denied"
    member_id = _member_id_for_discord_user(governance_dsn, first_login_snowflake)
    assert member_id is not None
    action = _latest_activity_action(
        governance_dsn,
        aggregate_type="member",
        aggregate_id=member_id,
    )
    assert action is not None
    assert action["actor_kind"] == "service"
    assert action["actor_id"] == "web-officer-bridge"
    assert action["request_surface"] == "api:/api/v1/web/officer/applications"


@pytest.mark.asyncio
async def test_officer_claim_ignores_x_actor_headers(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=x_actor_header_attack;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    officer_id = _officer_member_with_grants(governance_db)
    attacker_id = _create_member(governance_db, "210987654321098769")
    _grant(
        governance_db,
        actor_id=attacker_id,
        permissions=frozenset({"application.claim"}),
    )
    application, etag = await _create_application(migrated_async_client, governance_db)

    response = await _claim_via_officer_bridge(
        migrated_async_client,
        application_id=application["id"],
        etag=etag,
        headers=_pomerium_headers(
            **{
                "X-Actor-Kind": "user",
                "X-Actor-Id": attacker_id,
            }
        ),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["owner_id"] == officer_id
    assert response.json()["owner_id"] != attacker_id


@pytest.mark.asyncio
async def test_officer_claim_ignores_applicant_receipt(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=receipt_cookie_attack;
        level=api;
        source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-1
    """
    officer_id = _officer_member_with_grants(governance_db)
    receipt_member_id = _create_member(governance_db, "123456789012345678")
    application, etag = await _create_application(migrated_async_client, governance_db)

    response = await migrated_async_client.post(
        f"{OFFICER_APPLICATIONS_URL}/{application['id']}/claim",
        headers={**_pomerium_headers(), "If-Match": etag},
        cookies={"applicant_receipt": applicant_receipt_token()},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["owner_id"] == officer_id
    assert response.json()["owner_id"] != receipt_member_id


@pytest.mark.asyncio
async def test_officer_read_application_requires_pomerium_identity(
    migrated_async_client: AsyncClient,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=detail_actor_binding;
        level=api;
        source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-1
    """
    response = await migrated_async_client.get(f"{OFFICER_APPLICATIONS_URL}/{uuid4()}")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert _error_code(response) == "identity_missing"


@pytest.mark.asyncio
async def test_officer_read_application_requires_officers_group(
    migrated_async_client: AsyncClient,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=detail_actor_binding;
        level=api;
        source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-1
    """
    response = await migrated_async_client.get(
        f"{OFFICER_APPLICATIONS_URL}/{uuid4()}",
        headers=_pomerium_headers(groups="applicants"),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert _error_code(response) == "officer_required"


@pytest.mark.asyncio
async def test_officer_read_application_requires_discord_claim(
    migrated_async_client: AsyncClient,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=detail_actor_binding;
        level=api;
        source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-1
    """
    response = await migrated_async_client.get(
        f"{OFFICER_APPLICATIONS_URL}/{uuid4()}",
        headers=_pomerium_headers(discord_user_id=None),
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert _error_code(response) == "officer_discord_identity_missing"


@pytest.mark.asyncio
async def test_officer_read_application_returns_application_read(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=detail_contract_shape;
        level=api;
        source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-1
    """
    _officer_member_with_grants(
        governance_db,
        permissions=frozenset({"application.review"}),
    )
    application, _etag = await _create_application(migrated_async_client, governance_db)

    response = await migrated_async_client.get(
        f"{OFFICER_APPLICATIONS_URL}/{application['id']}",
        headers=_pomerium_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["id"] == application["id"]
    assert body["applicant_id"] == application["applicant_id"]
    assert body["target_scope"] == application["target_scope"]
    assert body["state"] == application["state"]
    assert body["owner_id"] == application["owner_id"]
    assert body["responses"] == {"nickname": "Ada", "class": "mage"}
    assert body["version"] == application["version"]
    assert body["submitted_at"]
    assert "form_snapshot" in body


@pytest.mark.asyncio
async def test_officer_read_application_authority_denied(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=detail_authority_denied;
        level=api;
        source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-1
    """
    _create_member(governance_db, "210987654321098765")
    application, _etag = await _create_application(migrated_async_client, governance_db)

    response = await migrated_async_client.get(
        f"{OFFICER_APPLICATIONS_URL}/{application['id']}",
        headers=_pomerium_headers(),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert _error_code(response) == "authority_decision_denied"


@pytest.mark.asyncio
async def test_officer_read_application_not_found(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=detail_not_found;
        level=api;
        source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-1
    """
    _officer_member_with_grants(
        governance_db,
        permissions=frozenset({"application.review"}),
        scope_kind="global",
        scope_id=None,
    )

    response = await migrated_async_client.get(
        f"{OFFICER_APPLICATIONS_URL}/{uuid4()}",
        headers=_pomerium_headers(),
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert _error_code(response) == "application_not_found"


@pytest.mark.asyncio
async def test_officer_read_application_ignores_x_actor_headers(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=detail_actor_spoofing;
        level=api;
        source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-1
    """
    _officer_member_with_grants(
        governance_db,
        permissions=frozenset({"application.review"}),
    )
    attacker_id = _create_member(governance_db, "210987654321098769")
    application, _etag = await _create_application(migrated_async_client, governance_db)

    response = await migrated_async_client.get(
        f"{OFFICER_APPLICATIONS_URL}/{application['id']}",
        headers=_pomerium_headers(
            **{
                "X-Actor-Kind": "user",
                "X-Actor-Id": attacker_id,
            }
        ),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["id"] == application["id"]


@pytest.mark.asyncio
async def test_officer_read_application_ignores_applicant_receipt(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=detail_receipt_spoofing;
        level=api;
        source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-1
    """
    _officer_member_with_grants(
        governance_db,
        permissions=frozenset({"application.review"}),
    )
    _create_member(governance_db, "123456789012345678")
    application, _etag = await _create_application(migrated_async_client, governance_db)

    response = await migrated_async_client.get(
        f"{OFFICER_APPLICATIONS_URL}/{application['id']}",
        headers=_pomerium_headers(),
        cookies={"applicant_receipt": applicant_receipt_token()},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["id"] == application["id"]


@pytest.mark.asyncio
async def test_officer_read_transcript_requires_pomerium_identity(
    migrated_async_client: AsyncClient,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=transcript_actor_binding;
        level=api;
        source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-1
    """
    response = await migrated_async_client.get(
        f"{OFFICER_APPLICATIONS_URL}/{uuid4()}/transcript"
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert _error_code(response) == "identity_missing"


@pytest.mark.asyncio
async def test_officer_read_transcript_returns_transcript_read(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=officer_transcript_visibility_regression;
        level=api;
        source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-1
    """
    officer_id = _officer_member_with_grants(
        governance_db,
        permissions=frozenset({"application.message"}),
    )
    application, _etag = await _create_application(migrated_async_client, governance_db)
    await _append_application_message_via_api(
        migrated_async_client,
        application_id=application["id"],
        author_actor_id=officer_id,
        visibility="applicant_visible",
        body_markdown="Officer transcript bridge note",
    )

    response = await migrated_async_client.get(
        f"{OFFICER_APPLICATIONS_URL}/{application['id']}/transcript",
        headers=_pomerium_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["application_id"] == application["id"]
    assert {entry["type"] for entry in body["entries"]} >= {"state_change", "message"}
    message_entries = [entry for entry in body["entries"] if entry["type"] == "message"]
    assert [entry["body_markdown"] for entry in message_entries] == [
        "Officer transcript bridge note"
    ]


@pytest.mark.asyncio
async def test_officer_read_transcript_visibility_filtered_for_officer_only_messages(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=officer_only_visibility_available_to_message_authority;
        level=api;
        source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-1
    """
    officer_id = _officer_member_with_grants(
        governance_db,
        permissions=frozenset({"application.message"}),
    )
    application, _etag = await _create_application(migrated_async_client, governance_db)
    await _append_application_message_via_api(
        migrated_async_client,
        application_id=application["id"],
        author_actor_id=application["applicant_id"],
        visibility="applicant_visible",
        body_markdown="Applicant-visible bridge note",
    )
    await _append_application_message_via_api(
        migrated_async_client,
        application_id=application["id"],
        author_actor_id=officer_id,
        visibility="officer_only",
        body_markdown="Officer-only bridge note",
    )

    response = await migrated_async_client.get(
        f"{OFFICER_APPLICATIONS_URL}/{application['id']}/transcript",
        headers=_pomerium_headers(),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    message_entries = [
        entry for entry in response.json()["entries"] if entry["type"] == "message"
    ]
    assert [entry["visibility"] for entry in message_entries] == [
        "applicant_visible",
        "officer_only",
    ]
    assert [entry["body_markdown"] for entry in message_entries] == [
        "Applicant-visible bridge note",
        "Officer-only bridge note",
    ]


@pytest.mark.asyncio
async def test_officer_read_transcript_authority_denied(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=transcript_authority_denied;
        level=api;
        source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-1
    """
    _officer_member_with_grants(
        governance_db,
        permissions=frozenset({"application.review"}),
    )
    application, _etag = await _create_application(migrated_async_client, governance_db)

    response = await migrated_async_client.get(
        f"{OFFICER_APPLICATIONS_URL}/{application['id']}/transcript",
        headers=_pomerium_headers(),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert _error_code(response) == "application_transcript_forbidden"


@pytest.mark.asyncio
async def test_officer_read_transcript_not_found(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=transcript_not_found;
        level=api;
        source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-1
    """
    _officer_member_with_grants(
        governance_db,
        permissions=frozenset({"application.message"}),
        scope_kind="global",
        scope_id=None,
    )

    response = await migrated_async_client.get(
        f"{OFFICER_APPLICATIONS_URL}/{uuid4()}/transcript",
        headers=_pomerium_headers(),
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert _error_code(response) == "application_not_found"


def test_officer_endpoints_have_locked_actor_construction(app: FastAPI) -> None:
    """
    Risk annotation: group=TG-1;
        named_risk=dep_tree_lock;
        level=api;
        source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-1
    """
    officer_routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path.startswith("/api/v1/web/officer/")
    ]

    assert {route.path for route in officer_routes} == {
        "/api/v1/web/officer/applications",
        "/api/v1/web/officer/applications/{application_id}",
        "/api/v1/web/officer/applications/{application_id}/claim",
        "/api/v1/web/officer/applications/{application_id}/transcript",
    }

    forbidden_callables = {
        "app.core.dependencies.get_current_actor",
        "app.core.context.get_current_actor",
        "app.services.applicant_discord_auth.verify_applicant_receipt",
    }
    for route in officer_routes:
        callables = [route.endpoint, *_flatten_route_dependencies(route)]
        for candidate in callables:
            qualified_name = f"{candidate.__module__}.{candidate.__name__}"
            assert qualified_name not in forbidden_callables
            try:
                source = inspect.getsource(candidate)
            except (OSError, TypeError):
                continue
            assert "CURRENT_ACTOR.get(" not in source
            assert "verify_applicant_receipt" not in source
            assert "applicant_receipt" not in source
