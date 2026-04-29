from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.authority import DuplicateActiveGrantError
from app.contracts.members import MemberCreate
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.authority import grant_authority
from app.services.members import create_or_get_member


FORMS_URL = "/api/v1/application-forms"
APPLICATIONS_URL = "/api/v1/applications"


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
    scope_kind: str = "chapter",
    scope_id: str | None = "chapter-1",
) -> None:
    with use_audit_context(_audit_context()):
        try:
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
        except DuplicateActiveGrantError:
            # Idempotent for fixture re-use: setup may grant the same
            # active authority more than once across helper calls.
            pass


def _create_member(db: PostgresDatabase, discord_user_id: str | None = None) -> str:
    raw_discord_user_id = discord_user_id or f"user-{uuid4().hex}"
    with use_audit_context(_audit_context()):
        member, _result, _created = create_or_get_member(
            db,
            MemberCreate(
                discord_user_id=raw_discord_user_id,
                joined_at=datetime.now(UTC),
                originating_actor_kind="user",
                originating_actor_id=raw_discord_user_id,
            ),
            ActorIdentity(actor_kind="user", actor_id=raw_discord_user_id),
        )
    return str(member.id)


def _scope(scope_kind: str, scope_id: str | None) -> dict[str, str | None]:
    if scope_kind == "global":
        return {"scope_kind": "global", "scope_id": None}
    return {"scope_kind": scope_kind, "scope_id": scope_id}


def _form_payload(*, scope_kind: str, scope_id: str | None) -> dict[str, Any]:
    scope = _scope(scope_kind, scope_id)
    return {
        "name": f"Application List {uuid4().hex[:8]}",
        "target_type": "chapter_membership",
        "scope": scope,
        "fields": [
            {
                "id": "nickname",
                "type": "short",
                "label": "Nickname",
                "required": True,
                "max_length": 32,
            },
            {
                "id": "class",
                "type": "select",
                "label": "Class",
                "required": True,
                "options": ["warrior", "mage"],
            },
        ],
        "routing_rules": {
            "schema_version": 1,
            "queue": "chapter_officers",
            "review_scope": scope,
        },
    }


def _application_payload(
    applicant_id: str,
    *,
    scope_kind: str,
    scope_id: str | None,
) -> dict[str, Any]:
    return {
        "applicant_id": applicant_id,
        "scope": _scope(scope_kind, scope_id),
        "responses": {"nickname": "Ada", "class": "mage"},
        "client_application_id": f"app-{uuid4().hex}",
    }


async def _publish_form(
    client: AsyncClient,
    db: PostgresDatabase,
    *,
    scope_kind: str = "chapter",
    scope_id: str | None = "chapter-1",
) -> None:
    _grant(
        db,
        actor_id="operator",
        permissions=frozenset({"application_form.publish"}),
        scope_kind="global",
        scope_id=None,
    )
    response = await client.post(
        FORMS_URL,
        json=_form_payload(scope_kind=scope_kind, scope_id=scope_id),
        headers=_headers("operator", **{"If-Match": '"0"'}),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text


async def _create_application(
    client: AsyncClient,
    db: PostgresDatabase,
    *,
    applicant_id: str | None = None,
    scope_kind: str = "chapter",
    scope_id: str | None = "chapter-1",
    publish_form: bool = True,
) -> tuple[dict[str, Any], str]:
    if publish_form:
        await _publish_form(client, db, scope_kind=scope_kind, scope_id=scope_id)
    resolved_applicant_id = applicant_id or _create_member(db)
    response = await client.post(
        APPLICATIONS_URL,
        json=_application_payload(
            resolved_applicant_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
        ),
        headers=_headers(resolved_applicant_id),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json(), response.headers["etag"]


async def _claim_application(
    client: AsyncClient,
    db: PostgresDatabase,
    *,
    application: dict[str, Any],
    etag: str,
    owner_id: str,
) -> tuple[dict[str, Any], str]:
    _grant(
        db,
        actor_id=owner_id,
        permissions=frozenset({"application.claim"}),
        scope_kind=application["target_scope"]["scope_kind"],
        scope_id=application["target_scope"]["scope_id"],
    )
    response = await client.post(
        f"{APPLICATIONS_URL}/{application['id']}/transitions",
        json={"action": "claim"},
        headers=_headers(owner_id, **{"If-Match": etag}),
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json(), response.headers["etag"]


async def _move_application_to_waitlisted(
    client: AsyncClient,
    db: PostgresDatabase,
    *,
    application: dict[str, Any],
    etag: str,
    owner_id: str,
) -> tuple[dict[str, Any], str]:
    _grant(
        db,
        actor_id=owner_id,
        permissions=frozenset(
            {"application.claim", "application.review", "application.waitlist"}
        ),
        scope_kind=application["target_scope"]["scope_kind"],
        scope_id=application["target_scope"]["scope_id"],
    )
    claimed, claim_etag = await _claim_application(
        client,
        db,
        application=application,
        etag=etag,
        owner_id=owner_id,
    )
    reviewed = await client.post(
        f"{APPLICATIONS_URL}/{application['id']}/transitions",
        json={"action": "review", "notes": "ready for waitlist"},
        headers=_headers(owner_id, **{"If-Match": claim_etag}),
    )
    assert reviewed.status_code == HTTPStatus.OK, reviewed.text
    waitlisted = await client.post(
        f"{APPLICATIONS_URL}/{application['id']}/transitions",
        json={"action": "waitlist", "reason": "capacity"},
        headers=_headers(owner_id, **{"If-Match": reviewed.headers["etag"]}),
    )
    assert waitlisted.status_code == HTTPStatus.OK, waitlisted.text
    assert claimed["state"] == "claimed"
    return waitlisted.json(), waitlisted.headers["etag"]


async def _list_applications(
    client: AsyncClient,
    *,
    actor_id: str,
    params: dict[str, str | int] | None = None,
):
    return await client.get(
        APPLICATIONS_URL,
        params=params or {},
        headers=_headers(actor_id),
    )


def _ids(body: dict[str, Any]) -> list[str]:
    return [item["id"] for item in body["items"]]


@pytest.fixture
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


@pytest.mark.asyncio
async def test_list_filters_by_single_and_multiple_states(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-1; named_risk=state_filter_leaks_wrong_state;
    level=component; source=.tmp/init-133a/phase6/step6a-contract.md#TG-1.
    """
    officer = _create_member(governance_db, "state-list-officer")
    owner = _create_member(governance_db, "state-list-owner")
    _grant(
        governance_db,
        actor_id=officer,
        permissions=frozenset({"application.review"}),
        scope_kind="global",
        scope_id=None,
    )
    await _publish_form(
        migrated_async_client,
        governance_db,
        scope_id="state-filter",
    )
    queued, _queued_etag = await _create_application(
        migrated_async_client,
        governance_db,
        scope_id="state-filter",
        publish_form=False,
    )
    claimed_created, claimed_etag = await _create_application(
        migrated_async_client,
        governance_db,
        scope_id="state-filter",
        publish_form=False,
    )
    claimed, _claimed_etag = await _claim_application(
        migrated_async_client,
        governance_db,
        application=claimed_created,
        etag=claimed_etag,
        owner_id=owner,
    )
    waitlisted_created, waitlisted_etag = await _create_application(
        migrated_async_client,
        governance_db,
        scope_id="state-filter",
        publish_form=False,
    )
    waitlisted, _waitlisted_etag = await _move_application_to_waitlisted(
        migrated_async_client,
        governance_db,
        application=waitlisted_created,
        etag=waitlisted_etag,
        owner_id=owner,
    )

    queued_response = await _list_applications(
        migrated_async_client,
        actor_id=officer,
        params={"state": "queued"},
    )
    assert queued_response.status_code == HTTPStatus.OK, queued_response.text
    assert _ids(queued_response.json()) == [queued["id"]]

    combined_response = await _list_applications(
        migrated_async_client,
        actor_id=officer,
        params={"state": "queued,claimed"},
    )
    assert combined_response.status_code == HTTPStatus.OK, combined_response.text
    assert set(_ids(combined_response.json())) == {queued["id"], claimed["id"]}
    assert waitlisted["id"] not in _ids(combined_response.json())

    invalid_response = await _list_applications(
        migrated_async_client,
        actor_id=officer,
        params={"state": "bogus"},
    )
    assert invalid_response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert invalid_response.json()["code"] == "invalid_application_state"


@pytest.mark.asyncio
async def test_list_filters_by_scope_and_requires_chapter_scope_id(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-2; named_risk=scope_filter_cross_scope_leak;
    level=component; source=.tmp/init-133a/phase6/step6a-contract.md#TG-2.
    """
    officer = _create_member(governance_db, "scope-list-officer")
    _grant(
        governance_db,
        actor_id=officer,
        permissions=frozenset({"application.review"}),
        scope_kind="global",
        scope_id=None,
    )
    app_a, _etag_a = await _create_application(
        migrated_async_client,
        governance_db,
        scope_id="A",
    )
    app_b, _etag_b = await _create_application(
        migrated_async_client,
        governance_db,
        scope_id="B",
    )
    global_app, _global_etag = await _create_application(
        migrated_async_client,
        governance_db,
        scope_kind="global",
        scope_id=None,
    )

    chapter_a_response = await _list_applications(
        migrated_async_client,
        actor_id=officer,
        params={"scope_kind": "chapter", "scope_id": "A"},
    )
    assert chapter_a_response.status_code == HTTPStatus.OK, chapter_a_response.text
    assert _ids(chapter_a_response.json()) == [app_a["id"]]
    assert app_b["id"] not in _ids(chapter_a_response.json())

    global_response = await _list_applications(
        migrated_async_client,
        actor_id=officer,
        params={"scope_kind": "global"},
    )
    assert global_response.status_code == HTTPStatus.OK, global_response.text
    assert _ids(global_response.json()) == [global_app["id"]]

    missing_scope_response = await _list_applications(
        migrated_async_client,
        actor_id=officer,
        params={"scope_kind": "chapter"},
    )
    assert missing_scope_response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_list_filters_by_owner_and_excludes_unowned_applications(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-3; named_risk=owner_filter_includes_unowned_or_other_owner;
    level=component; source=.tmp/init-133a/phase6/step6a-contract.md#TG-3.
    """
    officer = _create_member(governance_db, "owner-list-officer")
    owner_x = _create_member(governance_db, "owner-list-x")
    owner_y = _create_member(governance_db, "owner-list-y")
    _grant(
        governance_db,
        actor_id=officer,
        permissions=frozenset({"application.review"}),
        scope_kind="global",
        scope_id=None,
    )
    await _publish_form(
        migrated_async_client,
        governance_db,
        scope_id="owner-filter",
    )
    owned_x_created, owned_x_etag = await _create_application(
        migrated_async_client,
        governance_db,
        scope_id="owner-filter",
        publish_form=False,
    )
    owned_x, _owned_x_etag = await _claim_application(
        migrated_async_client,
        governance_db,
        application=owned_x_created,
        etag=owned_x_etag,
        owner_id=owner_x,
    )
    owned_y_created, owned_y_etag = await _create_application(
        migrated_async_client,
        governance_db,
        scope_id="owner-filter",
        publish_form=False,
    )
    owned_y, _owned_y_etag = await _claim_application(
        migrated_async_client,
        governance_db,
        application=owned_y_created,
        etag=owned_y_etag,
        owner_id=owner_y,
    )
    unowned, _unowned_etag = await _create_application(
        migrated_async_client,
        governance_db,
        scope_id="owner-filter",
        publish_form=False,
    )

    response = await _list_applications(
        migrated_async_client,
        actor_id=officer,
        params={"owner_id": owner_x},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert _ids(response.json()) == [owned_x["id"]]
    assert owned_y["id"] not in _ids(response.json())
    assert unowned["id"] not in _ids(response.json())


@pytest.mark.asyncio
async def test_list_uses_keyset_pagination_and_validates_limit(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-4; named_risk=pagination_cursor_duplicates_or_skips_items;
    level=component; source=.tmp/init-133a/phase6/step6a-contract.md#TG-4.
    """
    officer = _create_member(governance_db, "pagination-list-officer")
    scope_id = "pagination-filter"
    _grant(
        governance_db,
        actor_id=officer,
        permissions=frozenset({"application.review"}),
        scope_kind="chapter",
        scope_id=scope_id,
    )
    await _publish_form(migrated_async_client, governance_db, scope_id=scope_id)
    seeded_ids = []
    for _index in range(10):
        application, _etag = await _create_application(
            migrated_async_client,
            governance_db,
            scope_id=scope_id,
            publish_form=False,
        )
        seeded_ids.append(application["id"])

    first_page = await _list_applications(
        migrated_async_client,
        actor_id=officer,
        params={"scope_kind": "chapter", "scope_id": scope_id, "limit": 5},
    )
    assert first_page.status_code == HTTPStatus.OK, first_page.text
    first_body = first_page.json()
    assert len(first_body["items"]) == 5
    assert first_body["next_after_id"] is not None

    second_page = await _list_applications(
        migrated_async_client,
        actor_id=officer,
        params={
            "scope_kind": "chapter",
            "scope_id": scope_id,
            "limit": 5,
            "after_id": first_body["next_after_id"],
        },
    )
    assert second_page.status_code == HTTPStatus.OK, second_page.text
    second_body = second_page.json()
    assert len(second_body["items"]) == 5
    assert second_body["next_after_id"] is None
    assert set(_ids(first_body)).isdisjoint(_ids(second_body))
    assert set(_ids(first_body) + _ids(second_body)) == set(seeded_ids)

    zero_limit = await _list_applications(
        migrated_async_client,
        actor_id=officer,
        params={"scope_kind": "chapter", "scope_id": scope_id, "limit": 0},
    )
    assert zero_limit.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    too_large_limit = await _list_applications(
        migrated_async_client,
        actor_id=officer,
        params={"scope_kind": "chapter", "scope_id": scope_id, "limit": 201},
    )
    assert too_large_limit.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_list_authorizes_only_officer_scope_reads(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-5; named_risk=list_endpoint_allows_non_officer_or_wrong_scope;
    level=component; source=.tmp/init-133a/phase6/step6a-contract.md#TG-5.
    """
    stranger = _create_member(governance_db, "auth-list-stranger")
    applicant = _create_member(governance_db, "auth-list-applicant")
    chapter_a_officer = _create_member(governance_db, "auth-list-chapter-a-officer")
    global_officer = _create_member(governance_db, "auth-list-global-officer")
    _app_a, _etag_a = await _create_application(
        migrated_async_client,
        governance_db,
        applicant_id=applicant,
        scope_id="A",
    )
    _app_b, _etag_b = await _create_application(
        migrated_async_client,
        governance_db,
        scope_id="B",
    )
    _grant(
        governance_db,
        actor_id=chapter_a_officer,
        permissions=frozenset({"application.review"}),
        scope_kind="chapter",
        scope_id="A",
    )
    _grant(
        governance_db,
        actor_id=global_officer,
        permissions=frozenset({"application.review"}),
        scope_kind="global",
        scope_id=None,
    )

    stranger_response = await _list_applications(
        migrated_async_client,
        actor_id=stranger,
        params={"scope_kind": "chapter", "scope_id": "A"},
    )
    assert stranger_response.status_code == HTTPStatus.FORBIDDEN
    assert stranger_response.json()["code"] == "application_list_forbidden"

    applicant_response = await _list_applications(
        migrated_async_client,
        actor_id=applicant,
        params={"scope_kind": "chapter", "scope_id": "A"},
    )
    assert applicant_response.status_code == HTTPStatus.FORBIDDEN
    assert applicant_response.json()["code"] == "application_list_forbidden"
    assert "items" not in applicant_response.json()

    chapter_a_response = await _list_applications(
        migrated_async_client,
        actor_id=chapter_a_officer,
        params={"scope_kind": "chapter", "scope_id": "A"},
    )
    assert chapter_a_response.status_code == HTTPStatus.OK, chapter_a_response.text

    chapter_b_response = await _list_applications(
        migrated_async_client,
        actor_id=chapter_a_officer,
        params={"scope_kind": "chapter", "scope_id": "B"},
    )
    assert chapter_b_response.status_code == HTTPStatus.FORBIDDEN
    assert chapter_b_response.json()["code"] == "application_list_forbidden"

    global_response = await _list_applications(
        migrated_async_client,
        actor_id=global_officer,
        params={"scope_kind": "chapter", "scope_id": "B"},
    )
    assert global_response.status_code == HTTPStatus.OK, global_response.text


@pytest.mark.asyncio
async def test_list_returns_empty_page_when_no_applications_match(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-6; named_risk=empty_filter_returns_non_empty_or_bad_cursor;
    level=component; source=.tmp/init-133a/phase6/step6a-contract.md#TG-6.
    """
    officer = _create_member(governance_db, "empty-list-officer")
    _grant(
        governance_db,
        actor_id=officer,
        permissions=frozenset({"application.review"}),
        scope_kind="chapter",
        scope_id="empty-filter",
    )
    existing, _etag = await _create_application(
        migrated_async_client,
        governance_db,
        scope_id="empty-filter",
    )

    response = await _list_applications(
        migrated_async_client,
        actor_id=officer,
        params={
            "scope_kind": "chapter",
            "scope_id": "empty-filter",
            "state": "claimed",
        },
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert existing["state"] == "queued"
    assert response.json() == {"items": [], "next_after_id": None}
