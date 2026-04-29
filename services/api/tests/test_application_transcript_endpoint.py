from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from app.contracts.actor import ActorIdentity
from app.contracts.application_messages import ApplicationMessageAppendRequest
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.authority import DuplicateActiveGrantError
from app.contracts.members import MemberCreate
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.application_messages import append_application_message
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
            # Idempotent for fixture re-use: the same grant being requested
            # twice in setup is fine.
            pass


def _create_member(db: PostgresDatabase, discord_user_id: str | None = None) -> str:
    raw_discord_user_id = discord_user_id or str(10**17 + (uuid4().int % 10**17))
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


def _form_payload() -> dict[str, Any]:
    return {
        "name": f"Application Transcript Endpoint {uuid4().hex[:8]}",
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
        scope_kind="global",
        scope_id=None,
    )
    response = await client.post(
        FORMS_URL,
        json=_form_payload(),
        headers=_headers("operator", **{"If-Match": '"0"'}),
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


def _append_message(
    db: PostgresDatabase,
    *,
    application_id: str,
    author_actor_id: str,
    visibility: str,
    body_markdown: str,
) -> None:
    with use_audit_context(_audit_context()):
        append_application_message(
            db,
            application_id=UUID(application_id),
            request=ApplicationMessageAppendRequest(
                body_markdown=body_markdown,
                visibility=visibility,  # type: ignore[arg-type]
                client_message_id=f"transcript-endpoint-message-{uuid4().hex}",
                author_actor_kind="user",
                author_actor_id=author_actor_id,
            ),
        )


async def _seed_application_with_messages(
    client: AsyncClient,
    db: PostgresDatabase,
) -> dict[str, str]:
    applicant_id = _create_member(db)
    officer_id = _create_member(db)
    stranger_id = _create_member(db)
    _grant(
        db,
        actor_id=officer_id,
        permissions=frozenset({"application.message"}),
    )
    application = await _create_application(client, db, applicant_id=applicant_id)
    _append_message(
        db,
        application_id=application["id"],
        author_actor_id=applicant_id,
        visibility="applicant_visible",
        body_markdown="Endpoint applicant-visible message",
    )
    _append_message(
        db,
        application_id=application["id"],
        author_actor_id=officer_id,
        visibility="officer_only",
        body_markdown="Endpoint officer-only message",
    )
    return {
        "application_id": application["id"],
        "applicant_id": applicant_id,
        "officer_id": officer_id,
        "stranger_id": stranger_id,
    }


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


@pytest.mark.asyncio
async def test_get_transcript_as_applicant_returns_applicant_visible_messages_only(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-5; named_risk=applicant_endpoint_visibility_leak;
    level=endpoint; source=.tmp/init-132/phase6/step6a-contract.md#TG-5 and
    proposals/11-application-transcript.md#Q3.
    """
    seed = await _seed_application_with_messages(migrated_async_client, governance_db)

    response = await migrated_async_client.get(
        f"{APPLICATIONS_URL}/{seed['application_id']}/transcript",
        headers=_headers(seed["applicant_id"]),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["application_id"] == seed["application_id"]
    assert any(entry["type"] == "state_change" for entry in body["entries"])
    message_entries = [
        entry for entry in body["entries"] if entry["type"] == "message"
    ]
    assert [entry["visibility"] for entry in message_entries] == [
        "applicant_visible"
    ]
    assert [entry["body_markdown"] for entry in message_entries] == [
        "Endpoint applicant-visible message"
    ]


@pytest.mark.asyncio
async def test_get_transcript_as_officer_returns_both_message_visibilities(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-5; named_risk=officer_endpoint_visibility_regression;
    level=endpoint; source=.tmp/init-132/phase6/step6a-contract.md#TG-5 and
    proposals/11-application-transcript.md#Q3.
    """
    seed = await _seed_application_with_messages(migrated_async_client, governance_db)

    response = await migrated_async_client.get(
        f"{APPLICATIONS_URL}/{seed['application_id']}/transcript",
        headers=_headers(seed["officer_id"]),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    message_entries = [
        entry for entry in response.json()["entries"] if entry["type"] == "message"
    ]
    assert [entry["visibility"] for entry in message_entries] == [
        "applicant_visible",
        "officer_only",
    ]


@pytest.mark.asyncio
async def test_get_transcript_as_stranger_maps_to_application_transcript_forbidden(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-5; named_risk=stranger_endpoint_error_mapping_drift;
    level=endpoint; source=.tmp/init-132/phase6/step6a-contract.md#TG-5 and
    proposals/11-application-transcript.md#Q3.
    """
    seed = await _seed_application_with_messages(migrated_async_client, governance_db)

    response = await migrated_async_client.get(
        f"{APPLICATIONS_URL}/{seed['application_id']}/transcript",
        headers=_headers(seed["stranger_id"]),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    assert response.json()["code"] == "application_transcript_forbidden"


@pytest.mark.asyncio
async def test_get_transcript_for_missing_application_maps_to_application_not_found(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-5; named_risk=missing_application_error_mapping_drift;
    level=endpoint; source=.tmp/init-132/phase6/step6a-contract.md#TG-5 and
    proposals/11-application-transcript.md#Q3.
    """
    applicant_id = _create_member(governance_db)

    response = await migrated_async_client.get(
        f"{APPLICATIONS_URL}/{uuid4()}/transcript",
        headers=_headers(applicant_id),
    )

    assert response.status_code == HTTPStatus.NOT_FOUND, response.text
    assert response.json()["code"] == "application_not_found"
