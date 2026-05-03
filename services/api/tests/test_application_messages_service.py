from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from functools import partial
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from httpx import AsyncClient

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.authority import DuplicateActiveGrantError
from app.contracts.members import MemberCreate
from app.contracts.application_messages import (
    ApplicationMessageAppendForbiddenError,
    ApplicationMessageAppendRequest,
    ApplicationMessageVisibilityError,
)
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from tests._authority_helpers import grant_authority
from tests._authority_helpers import create_or_get_member
from app.services.mutations import mutate_entity


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
            # Idempotent for fixture re-use: the same grant
            # being requested twice in setup is fine.
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


def _form_payload(
    *,
    scope_kind: str = "chapter",
    scope_id: str | None = "chapter-1",
) -> dict[str, Any]:
    scope = {"scope_kind": scope_kind, "scope_id": scope_id}
    if scope_kind == "global":
        scope = {"scope_kind": "global", "scope_id": None}
    return {
        "name": f"Application Messages {uuid4().hex[:8]}",
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
    scope_kind: str = "chapter",
    scope_id: str | None = "chapter-1",
) -> dict[str, Any]:
    scope = {"scope_kind": scope_kind, "scope_id": scope_id}
    if scope_kind == "global":
        scope = {"scope_kind": "global", "scope_id": None}
    return {
        "applicant_id": applicant_id,
        "scope": scope,
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
        headers={**_headers("operator"), "If-Match": '"0"'},
    )
    assert response.status_code == HTTPStatus.CREATED, response.text


async def _create_application(
    client: AsyncClient,
    db: PostgresDatabase,
    *,
    applicant_id: str | None = None,
    scope_kind: str = "chapter",
    scope_id: str | None = "chapter-1",
) -> dict[str, Any]:
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
    return response.json()


def _append_request(
    *,
    author_actor_id: str,
    visibility: str,
    body_markdown: str = "Application message body",
    client_message_id: str | None = None,
) -> ApplicationMessageAppendRequest:
    return ApplicationMessageAppendRequest(
        body_markdown=body_markdown,
        visibility=visibility,  # type: ignore[arg-type]
        client_message_id=client_message_id,
        author_actor_kind="user",
        author_actor_id=author_actor_id,
    )


def _messages_service(db: PostgresDatabase):
    from app.repositories.applications import ApplicationsRepository
    from app.repositories.application_messages import ApplicationMessagesRepository
    from app.services.application_messages import ApplicationMessagesService

    return ApplicationMessagesService(
        applications_repo=ApplicationsRepository(db),
        application_messages_repo=ApplicationMessagesRepository(db),
        mutations_callable=partial(mutate_entity, db=db),
    )


def _append(
    db: PostgresDatabase,
    *,
    application_id: str,
    author_actor_id: str,
    visibility: str,
    body_markdown: str = "Application message body",
    client_message_id: str | None = None,
) -> tuple[Any, bool]:
    with use_audit_context(_audit_context()):
        return _messages_service(db).append_application_message(
            application_id=UUID(application_id),
            request=_append_request(
                author_actor_id=author_actor_id,
                visibility=visibility,
                body_markdown=body_markdown,
                client_message_id=client_message_id,
            ),
        )


def _message_count(dsn: str, application_id: str) -> int:
    with psycopg.connect(dsn) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM application_messages WHERE application_id = %s",
            (UUID(application_id),),
        ).fetchone()
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
async def test_applicant_can_append_applicant_visible_message(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-1; named_risk=applicant_visible_append_denied;
    level=component; source=.tmp/init-131/phase6/step6a-contract.md#TG-1.
    """
    applicant_id = _create_member(governance_db)
    application = await _create_application(
        migrated_async_client,
        governance_db,
        applicant_id=applicant_id,
    )

    message, created = _append(
        governance_db,
        application_id=application["id"],
        author_actor_id=applicant_id,
        visibility="applicant_visible",
    )

    assert created is True
    assert str(message.application_id) == application["id"]
    assert message.message_seq == 1
    assert message.visibility == "applicant_visible"
    assert message.author_actor_id == applicant_id


@pytest.mark.asyncio
async def test_applicant_cannot_append_officer_only_message(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-1; named_risk=applicant_officer_only_visibility_leak;
    level=component; source=.tmp/init-131/phase6/step6a-contract.md#TG-1.
    """
    applicant_id = _create_member(governance_db)
    application = await _create_application(
        migrated_async_client,
        governance_db,
        applicant_id=applicant_id,
    )

    with pytest.raises(ApplicationMessageVisibilityError):
        _append(
            governance_db,
            application_id=application["id"],
            author_actor_id=applicant_id,
            visibility="officer_only",
        )


@pytest.mark.asyncio
async def test_non_applicant_without_permission_cannot_append_message(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-1; named_risk=stranger_append_authorization_bypass;
    level=component; source=.tmp/init-131/phase6/step6a-contract.md#TG-1.
    """
    application = await _create_application(migrated_async_client, governance_db)
    stranger_id = _create_member(governance_db)

    with pytest.raises(ApplicationMessageAppendForbiddenError):
        _append(
            governance_db,
            application_id=application["id"],
            author_actor_id=stranger_id,
            visibility="applicant_visible",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("visibility", ["applicant_visible", "officer_only"])
async def test_officer_with_application_message_permission_can_append_either_visibility(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    visibility: str,
) -> None:
    """Risk annotation: group=TG-1; named_risk=officer_append_visibility_regression;
    level=component; source=.tmp/init-131/phase6/step6a-contract.md#TG-1.
    """
    officer_id = _create_member(governance_db)
    _grant(
        governance_db,
        actor_id=officer_id,
        permissions=frozenset({"application.message"}),
    )
    application = await _create_application(migrated_async_client, governance_db)

    message, created = _append(
        governance_db,
        application_id=application["id"],
        author_actor_id=officer_id,
        visibility=visibility,
    )

    assert created is True
    assert message.visibility == visibility
    assert message.author_actor_id == officer_id


@pytest.mark.asyncio
async def test_chapter_scoped_officer_can_append_only_within_matching_chapter(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-2; named_risk=chapter_scope_message_permission_bleed;
    level=component; source=.tmp/init-131/phase6/step6a-contract.md#TG-2.
    """
    officer_id = _create_member(governance_db)
    _grant(
        governance_db,
        actor_id=officer_id,
        permissions=frozenset({"application.message"}),
        scope_kind="chapter",
        scope_id="chapter-a",
    )
    chapter_a = await _create_application(
        migrated_async_client,
        governance_db,
        scope_kind="chapter",
        scope_id="chapter-a",
    )
    chapter_b = await _create_application(
        migrated_async_client,
        governance_db,
        scope_kind="chapter",
        scope_id="chapter-b",
    )

    message, created = _append(
        governance_db,
        application_id=chapter_a["id"],
        author_actor_id=officer_id,
        visibility="officer_only",
    )
    assert created is True
    assert str(message.application_id) == chapter_a["id"]

    with pytest.raises(ApplicationMessageAppendForbiddenError):
        _append(
            governance_db,
            application_id=chapter_b["id"],
            author_actor_id=officer_id,
            visibility="officer_only",
        )


@pytest.mark.asyncio
async def test_global_scoped_officer_can_append_on_global_targeted_application(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-2; named_risk=global_scope_message_permission_denied;
    level=component; source=.tmp/init-131/phase6/step6a-contract.md#TG-2.
    """
    officer_id = _create_member(governance_db)
    _grant(
        governance_db,
        actor_id=officer_id,
        permissions=frozenset({"application.message"}),
        scope_kind="global",
        scope_id=None,
    )
    application = await _create_application(
        migrated_async_client,
        governance_db,
        scope_kind="global",
        scope_id=None,
    )

    message, created = _append(
        governance_db,
        application_id=application["id"],
        author_actor_id=officer_id,
        visibility="officer_only",
    )

    assert created is True
    assert str(message.application_id) == application["id"]
    assert message.visibility == "officer_only"


@pytest.mark.asyncio
async def test_duplicate_client_message_id_returns_existing_without_second_row(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """Risk annotation: group=TG-3; named_risk=client_message_id_idempotency_regression;
    level=component; source=.tmp/init-131/phase6/step6a-contract.md#TG-3.
    """
    applicant_id = _create_member(governance_db)
    application = await _create_application(
        migrated_async_client,
        governance_db,
        applicant_id=applicant_id,
    )

    first, first_created = _append(
        governance_db,
        application_id=application["id"],
        author_actor_id=applicant_id,
        visibility="applicant_visible",
        client_message_id="client-message-1",
    )
    second, second_created = _append(
        governance_db,
        application_id=application["id"],
        author_actor_id=applicant_id,
        visibility="applicant_visible",
        client_message_id="client-message-1",
    )

    assert first_created is True
    assert second_created is False
    assert second.id == first.id
    assert _message_count(governance_dsn, application["id"]) == 1


@pytest.mark.asyncio
async def test_read_messages_filters_by_viewer_identity_and_officer_authority(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-4; named_risk=application_message_read_visibility_leak;
    level=component; source=.tmp/init-131/phase6/step6a-contract.md#TG-4.
    """
    applicant_id = _create_member(governance_db)
    officer_id = _create_member(governance_db)
    stranger_id = _create_member(governance_db)
    _grant(
        governance_db,
        actor_id=officer_id,
        permissions=frozenset({"application.message"}),
    )
    application = await _create_application(
        migrated_async_client,
        governance_db,
        applicant_id=applicant_id,
    )
    _append(
        governance_db,
        application_id=application["id"],
        author_actor_id=applicant_id,
        visibility="applicant_visible",
        body_markdown="Applicant-visible first",
    )
    _append(
        governance_db,
        application_id=application["id"],
        author_actor_id=officer_id,
        visibility="officer_only",
        body_markdown="Officer-only second",
    )
    _append(
        governance_db,
        application_id=application["id"],
        author_actor_id=officer_id,
        visibility="applicant_visible",
        body_markdown="Applicant-visible third",
    )

    service = _messages_service(governance_db)
    applicant_messages = service.read_application_messages(
        application_id=UUID(application["id"]),
        viewer_actor_kind="user",
        viewer_actor_id=applicant_id,
    )
    officer_messages = service.read_application_messages(
        application_id=UUID(application["id"]),
        viewer_actor_kind="user",
        viewer_actor_id=officer_id,
    )

    assert [message.visibility for message in applicant_messages] == [
        "applicant_visible",
        "applicant_visible",
    ]
    assert [message.message_seq for message in applicant_messages] == [1, 3]
    assert [message.visibility for message in officer_messages] == [
        "applicant_visible",
        "officer_only",
        "applicant_visible",
    ]
    assert [message.message_seq for message in officer_messages] == [1, 2, 3]
    with pytest.raises(ApplicationMessageAppendForbiddenError):
        service.read_application_messages(
            application_id=UUID(application["id"]),
            viewer_actor_kind="user",
            viewer_actor_id=stranger_id,
        )
