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
from app.contracts.members import MemberCreate
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from tests._authority_helpers import grant_authority
from tests._authority_helpers import create_or_get_member


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


def _headers(actor_id: str) -> dict[str, str]:
    return {"X-Actor-Kind": "user", "X-Actor-Id": actor_id}


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


def _create_member(db: PostgresDatabase) -> str:
    discord_user_id = str(10**17 + (uuid4().int % 10**17))
    with use_audit_context(_audit_context()):
        member, _result, _created = create_or_get_member(
            db,
            MemberCreate(
                discord_user_id=discord_user_id,
                joined_at=datetime.now(UTC),
                originating_actor_kind="user",
                originating_actor_id=discord_user_id,
            ),
            ActorIdentity(actor_kind="user", actor_id=discord_user_id),
        )
    return str(member.id)


def _form_payload() -> dict[str, Any]:
    return {
        "name": f"Application Messages Endpoint {uuid4().hex[:8]}",
        "target_type": "chapter_membership",
        "scope": {"scope_kind": "chapter", "scope_id": "chapter-1"},
        "fields": [
            {
                "id": "nickname",
                "type": "short",
                "label": "Nickname",
                "required": True,
                "max_length": 32,
            }
        ],
        "routing_rules": {
            "schema_version": 1,
            "queue": "chapter_officers",
            "review_scope": {"scope_kind": "chapter", "scope_id": "chapter-1"},
        },
    }


async def _publish_form(client: AsyncClient, db: PostgresDatabase) -> None:
    _grant(
        db,
        actor_id="operator",
        permissions=frozenset({"application_form.publish"}),
    )
    response = await client.post(
        FORMS_URL,
        json=_form_payload(),
        headers={**_headers("operator"), "If-Match": '"0"'},
    )
    assert response.status_code == HTTPStatus.CREATED, response.text


async def _create_application(
    client: AsyncClient,
    db: PostgresDatabase,
    *,
    applicant_id: str | None = None,
) -> dict[str, Any]:
    await _publish_form(client, db)
    resolved_applicant_id = applicant_id or _create_member(db)
    response = await client.post(
        APPLICATIONS_URL,
        json={
            "applicant_id": resolved_applicant_id,
            "scope": {"scope_kind": "chapter", "scope_id": "chapter-1"},
            "responses": {"nickname": "Ada"},
            "client_application_id": f"app-{uuid4().hex}",
        },
        headers=_headers(resolved_applicant_id),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


def _message_payload(
    *,
    author_actor_id: str,
    visibility: str = "applicant_visible",
    client_message_id: str | None = None,
) -> dict[str, Any]:
    return {
        "body_markdown": "Endpoint message body",
        "visibility": visibility,
        "client_message_id": client_message_id or f"message-{uuid4().hex}",
        "author_actor_kind": "user",
        "author_actor_id": author_actor_id,
    }


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


@pytest.mark.asyncio
async def test_post_then_get_application_messages_as_applicant(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-5; named_risk=endpoint_round_trip_contract_drift;
    level=component; source=.tmp/init-131/phase6/step6a-contract.md#TG-5.
    """
    applicant_id = _create_member(governance_db)
    application = await _create_application(
        migrated_async_client,
        governance_db,
        applicant_id=applicant_id,
    )

    posted = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application['id']}/messages",
        json=_message_payload(
            author_actor_id=applicant_id,
            visibility="applicant_visible",
            client_message_id="endpoint-message-1",
        ),
        headers=_headers(applicant_id),
    )
    fetched = await migrated_async_client.get(
        f"{APPLICATIONS_URL}/{application['id']}/messages",
        headers=_headers(applicant_id),
    )

    assert posted.status_code == HTTPStatus.CREATED, posted.text
    posted_body = posted.json()
    assert posted_body["application_id"] == application["id"]
    assert posted_body["message_seq"] == 1
    assert posted_body["visibility"] == "applicant_visible"
    assert posted_body["body_markdown"] == "Endpoint message body"
    assert posted_body["client_message_id"] == "endpoint-message-1"
    assert posted_body["author_actor_kind"] == "user"
    assert posted_body["author_actor_id"] == applicant_id
    assert posted_body["correlation_id"]
    assert posted_body["created_at"]

    assert fetched.status_code == HTTPStatus.OK, fetched.text
    items = fetched.json()["items"]
    assert [item["id"] for item in items] == [posted_body["id"]]


@pytest.mark.asyncio
async def test_post_and_get_missing_application_return_application_not_found(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-5; named_risk=missing_application_error_mapping_drift;
    level=component; source=.tmp/init-131/phase6/step6a-contract.md#TG-5.
    """
    applicant_id = _create_member(governance_db)
    missing_application_id = uuid4()

    posted = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{missing_application_id}/messages",
        json=_message_payload(author_actor_id=applicant_id),
        headers=_headers(applicant_id),
    )
    fetched = await migrated_async_client.get(
        f"{APPLICATIONS_URL}/{missing_application_id}/messages",
        headers=_headers(applicant_id),
    )

    assert posted.status_code == HTTPStatus.NOT_FOUND, posted.text
    assert posted.json()["code"] == "application_not_found"
    assert fetched.status_code == HTTPStatus.NOT_FOUND, fetched.text
    assert fetched.json()["code"] == "application_not_found"


@pytest.mark.asyncio
async def test_post_applicant_officer_only_maps_to_applicant_visibility_required(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-5; named_risk=applicant_visibility_error_mapping_drift;
    level=component; source=.tmp/init-131/phase6/step6a-contract.md#TG-5.
    """
    applicant_id = _create_member(governance_db)
    application = await _create_application(
        migrated_async_client,
        governance_db,
        applicant_id=applicant_id,
    )

    response = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application['id']}/messages",
        json=_message_payload(
            author_actor_id=applicant_id,
            visibility="officer_only",
        ),
        headers=_headers(applicant_id),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "applicant_visibility_required"


@pytest.mark.asyncio
async def test_post_stranger_maps_to_application_message_forbidden(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-5; named_risk=stranger_error_mapping_drift;
    level=component; source=.tmp/init-131/phase6/step6a-contract.md#TG-5.
    """
    application = await _create_application(migrated_async_client, governance_db)
    stranger_id = _create_member(governance_db)

    response = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application['id']}/messages",
        json=_message_payload(author_actor_id=stranger_id),
        headers=_headers(stranger_id),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    assert response.json()["code"] == "application_message_forbidden"
