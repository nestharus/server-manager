from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from httpx import AsyncClient

from app.contracts.actor import ActorIdentity
from app.contracts.application_messages import (
    ApplicationMessageAppendForbiddenError,
    ApplicationMessageAppendRequest,
)
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.authority import DuplicateActiveGrantError
from app.contracts.members import MemberCreate
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.application_messages import append_application_message
from app.services.application_transcript import read_application_transcript
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
        "name": f"Application Transcript {uuid4().hex[:8]}",
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
    return {"body": response.json(), "etag": response.headers["etag"]}


async def _claim_application(
    client: AsyncClient,
    *,
    application_id: str,
    etag: str,
    officer_id: str,
) -> dict[str, Any]:
    response = await client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": "claim"},
        headers=_headers(officer_id, **{"If-Match": etag}),
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


def _append_request(
    *,
    author_actor_id: str,
    visibility: str,
    body_markdown: str,
    client_message_id: str,
) -> ApplicationMessageAppendRequest:
    return ApplicationMessageAppendRequest(
        body_markdown=body_markdown,
        visibility=visibility,  # type: ignore[arg-type]
        client_message_id=client_message_id,
        author_actor_kind="user",
        author_actor_id=author_actor_id,
    )


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
            request=_append_request(
                author_actor_id=author_actor_id,
                visibility=visibility,
                body_markdown=body_markdown,
                client_message_id=f"transcript-message-{uuid4().hex}",
            ),
        )


def _set_state_change_times(
    dsn: str,
    *,
    application_id: str,
    times_by_aggregate_seq: dict[int, datetime],
) -> None:
    with psycopg.connect(dsn, autocommit=True) as connection:
        for aggregate_seq, occurred_at in times_by_aggregate_seq.items():
            cursor = connection.execute(
                """
                UPDATE activity_state_changes
                SET recorded_at = %s
                WHERE aggregate_type = 'application'
                  AND aggregate_id = %s
                  AND aggregate_seq = %s
                """,
                (occurred_at, application_id, aggregate_seq),
            )
            assert cursor.rowcount == 1


def _set_message_times(
    dsn: str,
    *,
    application_id: str,
    times_by_message_seq: dict[int, datetime],
) -> None:
    with psycopg.connect(dsn, autocommit=True) as connection:
        for message_seq, occurred_at in times_by_message_seq.items():
            cursor = connection.execute(
                """
                UPDATE application_messages
                SET created_at = %s
                WHERE application_id = %s
                  AND message_seq = %s
                """,
                (occurred_at, UUID(application_id), message_seq),
            )
            assert cursor.rowcount == 1


async def _seed_claimed_application_with_messages(
    client: AsyncClient,
    db: PostgresDatabase,
    dsn: str,
) -> dict[str, str]:
    applicant_id = _create_member(db)
    officer_id = _create_member(db)
    stranger_id = _create_member(db)
    _grant(
        db,
        actor_id=officer_id,
        permissions=frozenset({"application.claim", "application.message"}),
    )
    created = await _create_application(client, db, applicant_id=applicant_id)
    application_id = created["body"]["id"]
    await _claim_application(
        client,
        application_id=application_id,
        etag=created["etag"],
        officer_id=officer_id,
    )
    _append_message(
        db,
        application_id=application_id,
        author_actor_id=applicant_id,
        visibility="applicant_visible",
        body_markdown="Applicant-visible transcript message",
    )
    _append_message(
        db,
        application_id=application_id,
        author_actor_id=officer_id,
        visibility="officer_only",
        body_markdown="Officer-only transcript message",
    )
    base = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    _set_state_change_times(
        dsn,
        application_id=application_id,
        times_by_aggregate_seq={
            1: base,
            2: base + timedelta(minutes=2),
            3: base + timedelta(minutes=4),
        },
    )
    _set_message_times(
        dsn,
        application_id=application_id,
        times_by_message_seq={
            1: base + timedelta(minutes=1),
            2: base + timedelta(minutes=3),
        },
    )
    return {
        "application_id": application_id,
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
async def test_applicant_transcript_includes_state_changes_and_applicant_visible_messages_only(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """Risk annotation: group=TG-1; named_risk=applicant_transcript_visibility_leak;
    level=service; source=.tmp/init-132/phase6/step6a-contract.md#TG-1 and
    planning/proposals/11-application-transcript.md#Q2.
    """
    seed = await _seed_claimed_application_with_messages(
        migrated_async_client,
        governance_db,
        governance_dsn,
    )

    transcript = read_application_transcript(
        governance_db,
        application_id=UUID(seed["application_id"]),
        viewer_actor_kind="user",
        viewer_actor_id=seed["applicant_id"],
    )

    assert str(transcript.application_id) == seed["application_id"]
    assert [entry.occurred_at for entry in transcript.entries] == sorted(
        entry.occurred_at for entry in transcript.entries
    )
    state_entries = [
        entry for entry in transcript.entries if entry.type == "state_change"
    ]
    message_entries = [entry for entry in transcript.entries if entry.type == "message"]
    assert [entry.aggregate_seq for entry in state_entries] == [1, 2, 3]
    assert [entry.message_seq for entry in message_entries] == [1]
    assert [entry.visibility for entry in message_entries] == ["applicant_visible"]
    assert [entry.body_markdown for entry in message_entries] == [
        "Applicant-visible transcript message"
    ]


@pytest.mark.asyncio
async def test_officer_transcript_includes_state_changes_and_both_message_visibilities(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """Risk annotation: group=TG-2; named_risk=officer_transcript_visibility_regression;
    level=service; source=.tmp/init-132/phase6/step6a-contract.md#TG-2 and
    planning/proposals/11-application-transcript.md#Q2.
    """
    seed = await _seed_claimed_application_with_messages(
        migrated_async_client,
        governance_db,
        governance_dsn,
    )

    transcript = read_application_transcript(
        governance_db,
        application_id=UUID(seed["application_id"]),
        viewer_actor_kind="user",
        viewer_actor_id=seed["officer_id"],
    )

    assert [entry.occurred_at for entry in transcript.entries] == sorted(
        entry.occurred_at for entry in transcript.entries
    )
    state_entries = [
        entry for entry in transcript.entries if entry.type == "state_change"
    ]
    message_entries = [entry for entry in transcript.entries if entry.type == "message"]
    assert [entry.aggregate_seq for entry in state_entries] == [1, 2, 3]
    assert [entry.message_seq for entry in message_entries] == [1, 2]
    assert [entry.visibility for entry in message_entries] == [
        "applicant_visible",
        "officer_only",
    ]


@pytest.mark.asyncio
async def test_stranger_transcript_reuses_application_message_forbidden_error(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """Risk annotation: group=TG-3; named_risk=stranger_transcript_authorization_bypass;
    level=service; source=.tmp/init-132/phase6/step6a-contract.md#TG-3 and
    planning/proposals/11-application-transcript.md#Q2.
    """
    seed = await _seed_claimed_application_with_messages(
        migrated_async_client,
        governance_db,
        governance_dsn,
    )

    with pytest.raises(ApplicationMessageAppendForbiddenError):
        read_application_transcript(
            governance_db,
            application_id=UUID(seed["application_id"]),
            viewer_actor_kind="user",
            viewer_actor_id=seed["stranger_id"],
        )


@pytest.mark.asyncio
async def test_transcript_chronologically_interleaves_state_changes_and_messages(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """Risk annotation: group=TG-4; named_risk=transcript_chronological_merge_drift;
    level=service; source=.tmp/init-132/phase6/step6a-contract.md#TG-4 and
    planning/proposals/11-application-transcript.md#Q1.
    """
    applicant_id = _create_member(governance_db)
    created = await _create_application(
        migrated_async_client,
        governance_db,
        applicant_id=applicant_id,
    )
    application_id = created["body"]["id"]
    _append_message(
        governance_db,
        application_id=application_id,
        author_actor_id=applicant_id,
        visibility="applicant_visible",
        body_markdown="Message B",
    )
    _append_message(
        governance_db,
        application_id=application_id,
        author_actor_id=applicant_id,
        visibility="applicant_visible",
        body_markdown="Message D",
    )
    base = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)
    _set_state_change_times(
        governance_dsn,
        application_id=application_id,
        times_by_aggregate_seq={
            1: base,
            2: base + timedelta(minutes=2),
        },
    )
    _set_message_times(
        governance_dsn,
        application_id=application_id,
        times_by_message_seq={
            1: base + timedelta(minutes=1),
            2: base + timedelta(minutes=3),
        },
    )

    transcript = read_application_transcript(
        governance_db,
        application_id=UUID(application_id),
        viewer_actor_kind="user",
        viewer_actor_id=applicant_id,
    )

    assert [
        (entry.type, getattr(entry, "aggregate_seq", getattr(entry, "message_seq", None)))
        for entry in transcript.entries
    ] == [
        ("state_change", 1),
        ("message", 1),
        ("state_change", 2),
        ("message", 2),
    ]
