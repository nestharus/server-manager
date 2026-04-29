from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.members import MemberCreate
from app.core.context import use_audit_context
from app.repositories.application_messages import (
    find_application_message_by_client_message_id,
    insert_application_message,
    list_application_messages,
    next_application_message_seq,
)
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


def _headers(actor_id: str) -> dict[str, str]:
    return {"X-Actor-Kind": "user", "X-Actor-Id": actor_id}


def _grant(
    db: PostgresDatabase,
    *,
    actor_id: str,
    permissions: frozenset[str],
) -> None:
    with use_audit_context(_audit_context()):
        grant_authority(
            db=db,
            grantee_id=actor_id,
            scope_kind="global",
            scope_id=None,
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


async def _create_application(client: AsyncClient, db: PostgresDatabase) -> dict[str, Any]:
    _grant(
        db,
        actor_id="operator",
        permissions=frozenset({"application_form.publish"}),
    )
    form = await client.post(
        FORMS_URL,
        json={
            "name": f"Application Messages Repository {uuid4().hex[:8]}",
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
        },
        headers={**_headers("operator"), "If-Match": '"0"'},
    )
    assert form.status_code == HTTPStatus.CREATED, form.text
    applicant_id = _create_member(db)
    response = await client.post(
        APPLICATIONS_URL,
        json={
            "applicant_id": applicant_id,
            "scope": {"scope_kind": "chapter", "scope_id": "chapter-1"},
            "responses": {"nickname": "Ada"},
            "client_application_id": f"app-{uuid4().hex}",
        },
        headers=_headers(applicant_id),
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


def _row(
    *,
    application_id: str,
    message_seq: int,
    client_message_id: str | None = None,
    body_markdown: str | None = None,
) -> dict[str, Any]:
    return {
        "id": uuid4(),
        "application_id": UUID(application_id),
        "message_seq": message_seq,
        "author_actor_kind": "user",
        "author_actor_id": "author-1",
        "visibility": "applicant_visible",
        "body_markdown": body_markdown or f"Message {message_seq}",
        "client_message_id": client_message_id,
        "correlation_id": uuid4(),
        "causation_id": None,
    }


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


@pytest.mark.asyncio
async def test_next_application_message_seq_advances_after_insert(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-7; named_risk=message_sequence_assignment_drift;
    level=repository; source=.tmp/init-131/phase6/step6a-contract.md#C3.
    """
    application = await _create_application(migrated_async_client, governance_db)

    with governance_db.connection() as connection:
        assert next_application_message_seq(
            connection,
            application_id=UUID(application["id"]),
        ) == 1
        insert_application_message(
            connection,
            row=_row(application_id=application["id"], message_seq=1),
        )
        assert next_application_message_seq(
            connection,
            application_id=UUID(application["id"]),
        ) == 2


@pytest.mark.asyncio
async def test_find_application_message_by_client_message_id_returns_hit_or_none(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-7; named_risk=client_message_id_lookup_drift;
    level=repository; source=.tmp/init-131/phase6/step6a-contract.md#C3.
    """
    application = await _create_application(migrated_async_client, governance_db)

    with governance_db.connection() as connection:
        assert (
            find_application_message_by_client_message_id(
                connection,
                application_id=UUID(application["id"]),
                client_message_id="missing-client-message",
            )
            is None
        )
        insert_application_message(
            connection,
            row=_row(
                application_id=application["id"],
                message_seq=1,
                client_message_id="client-message-1",
            ),
        )
        found = find_application_message_by_client_message_id(
            connection,
            application_id=UUID(application["id"]),
            client_message_id="client-message-1",
        )

    assert found is not None
    assert found["client_message_id"] == "client-message-1"
    assert int(found["message_seq"]) == 1


@pytest.mark.asyncio
async def test_list_application_messages_orders_by_message_seq_ascending(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-7; named_risk=message_list_ordering_drift;
    level=repository; source=.tmp/init-131/phase6/step6a-contract.md#C3.
    """
    application = await _create_application(migrated_async_client, governance_db)

    with governance_db.connection() as connection:
        insert_application_message(
            connection,
            row=_row(
                application_id=application["id"],
                message_seq=2,
                body_markdown="Second message",
            ),
        )
        insert_application_message(
            connection,
            row=_row(
                application_id=application["id"],
                message_seq=1,
                body_markdown="First message",
            ),
        )
        rows = list_application_messages(
            connection,
            application_id=UUID(application["id"]),
        )

    assert [int(row["message_seq"]) for row in rows] == [1, 2]
    assert [row["body_markdown"] for row in rows] == [
        "First message",
        "Second message",
    ]
