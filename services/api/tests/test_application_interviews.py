from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from httpx import AsyncClient
from psycopg.rows import dict_row

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
            return


def _create_member(db: PostgresDatabase, discord_user_id: str) -> str:
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
        "name": "Chapter Application",
        "target_type": "chapter_membership",
        "scope": {"scope_kind": "chapter", "scope_id": "chapter-1"},
        "fields": [
            {
                "id": "nickname",
                "type": "short",
                "label": "Nickname",
                "required": True,
                "max_length": 16,
            }
        ],
        "routing_rules": {
            "schema_version": 1,
            "queue": "chapter_officers",
            "review_scope": {"scope_kind": "chapter", "scope_id": "chapter-1"},
        },
    }


def _application_payload(applicant_id: str) -> dict[str, Any]:
    return {
        "applicant_id": applicant_id,
        "scope": {"scope_kind": "chapter", "scope_id": "chapter-1"},
        "responses": {"nickname": "Ada"},
        "client_application_id": f"interaction-{uuid4().hex}",
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
    if (
        response.status_code == HTTPStatus.PRECONDITION_FAILED
        and response.json().get("code") == "stale_application_version"
    ):
        return
    assert response.status_code == HTTPStatus.CREATED, response.text


async def _submit(client: AsyncClient, applicant_id: str):
    return await client.post(
        APPLICATIONS_URL,
        json=_application_payload(applicant_id),
        headers=_headers(applicant_id),
    )


async def _claim(
    client: AsyncClient,
    *,
    application_id: str,
    owner_id: str,
    etag: str,
):
    return await client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": "claim"},
        headers=_headers(owner_id, **{"If-Match": etag}),
    )


async def _review(
    client: AsyncClient,
    *,
    application_id: str,
    owner_id: str,
    etag: str,
):
    return await client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": "review", "notes": "ready for next step"},
        headers=_headers(owner_id, **{"If-Match": etag}),
    )


async def _prepare_in_review(
    client: AsyncClient,
    db: PostgresDatabase,
    *,
    applicant_discord_id: str = "applicant-1",
    owner_discord_id: str = "reviewer-1",
) -> tuple[str, str, str, str]:
    await _publish_form(client, db)
    applicant_id = _create_member(db, applicant_discord_id)
    owner_id = _create_member(db, owner_discord_id)
    _grant(
        db,
        actor_id=owner_id,
        permissions=frozenset(
            {
                "application.claim",
                "application.review",
                "application.request_interview",
                "application.waitlist",
                "application.approve",
                "application.deny",
                "application.withdraw",
            }
        ),
    )
    created = await _submit(client, applicant_id)
    assert created.status_code == HTTPStatus.CREATED, created.text
    application_id = created.json()["id"]
    claimed = await _claim(
        client,
        application_id=application_id,
        owner_id=owner_id,
        etag=created.headers["etag"],
    )
    assert claimed.status_code == HTTPStatus.OK, claimed.text
    reviewed = await _review(
        client,
        application_id=application_id,
        owner_id=owner_id,
        etag=claimed.headers["etag"],
    )
    assert reviewed.status_code == HTTPStatus.OK, reviewed.text
    return application_id, owner_id, applicant_id, reviewed.headers["etag"]


@pytest.fixture
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


@pytest.mark.asyncio
async def test_request_interview_succeeds_only_from_in_review(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC1: request_interview only valid from in_review."""
    application_id, owner_id, _applicant_id, etag = await _prepare_in_review(
        migrated_async_client,
        governance_db,
    )

    response = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/interview",
        json={
            "thread_id": "thread-1",
            "reason": "voice check",
            "originating_actor_kind": "user",
            "originating_actor_id": owner_id,
        },
        headers=_headers(owner_id, **{"If-Match": etag}),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["state"] == "interview"
    assert response.json()["interview_thread_id"] == "thread-1"
    assert response.json()["version"] == 5
    with psycopg.connect(governance_dsn) as conn:
        action = conn.execute(
            """
            SELECT action
            FROM application_reviews
            WHERE application_id = %s
            ORDER BY aggregate_seq DESC
            LIMIT 1
            """,
            (UUID(application_id),),
        ).fetchone()[0]
    assert action == "request_interview"

    queued_applicant = _create_member(governance_db, "applicant-queued")
    queued_owner = _create_member(governance_db, "reviewer-queued")
    _grant(
        governance_db,
        actor_id=queued_owner,
        permissions=frozenset({"application.request_interview", "application.claim"}),
    )
    queued = await _submit(migrated_async_client, queued_applicant)
    claimed = await _claim(
        migrated_async_client,
        application_id=queued.json()["id"],
        owner_id=queued_owner,
        etag=queued.headers["etag"],
    )
    assert claimed.status_code == HTTPStatus.OK, claimed.text
    queued_invalid = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{queued.json()['id']}/interview",
        json={
            "thread_id": "thread-queued",
            "originating_actor_kind": "user",
            "originating_actor_id": queued_owner,
        },
        headers=_headers(queued_owner, **{"If-Match": queued.headers["etag"]}),
    )
    claimed_invalid = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{queued.json()['id']}/interview",
        json={
            "thread_id": "thread-claimed",
            "originating_actor_kind": "user",
            "originating_actor_id": queued_owner,
        },
        headers=_headers(queued_owner, **{"If-Match": claimed.headers["etag"]}),
    )
    assert queued_invalid.status_code == HTTPStatus.PRECONDITION_FAILED
    assert claimed_invalid.status_code == HTTPStatus.CONFLICT
    assert claimed_invalid.json()["code"] == "invalid_application_transition"


@pytest.mark.asyncio
async def test_interview_owner_enforcement(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: request_interview requires the current application owner."""
    application_id, _owner_id, _applicant_id, etag = await _prepare_in_review(
        migrated_async_client,
        governance_db,
    )
    other_id = _create_member(governance_db, "reviewer-other")
    _grant(
        governance_db,
        actor_id=other_id,
        permissions=frozenset({"application.request_interview"}),
    )

    response = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/interview",
        json={
            "thread_id": "thread-1",
            "originating_actor_kind": "user",
            "originating_actor_id": other_id,
        },
        headers=_headers(other_id, **{"If-Match": etag}),
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["code"] == "application_not_owner"


@pytest.mark.asyncio
async def test_interview_thread_idempotency_and_mismatch_precedence(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC3: repeated interview request reuses the recorded thread."""
    application_id, owner_id, _applicant_id, etag = await _prepare_in_review(
        migrated_async_client,
        governance_db,
    )
    first = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/interview",
        json={
            "thread_id": "thread-1",
            "originating_actor_kind": "user",
            "originating_actor_id": owner_id,
        },
        headers=_headers(owner_id, **{"If-Match": etag}),
    )
    assert first.status_code == HTTPStatus.OK, first.text

    repeat = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/interview",
        json={
            "thread_id": "thread-1",
            "originating_actor_kind": "user",
            "originating_actor_id": owner_id,
        },
        headers=_headers(owner_id, **{"If-Match": first.headers["etag"]}),
    )

    assert repeat.status_code == HTTPStatus.OK, repeat.text
    assert repeat.headers["etag"] == first.headers["etag"]
    assert repeat.json()["version"] == first.json()["version"]
    with psycopg.connect(governance_dsn) as conn:
        count = conn.execute(
            """
            SELECT COUNT(*)
            FROM application_reviews
            WHERE application_id = %s AND action = 'request_interview'
            """,
            (UUID(application_id),),
        ).fetchone()[0]
    assert count == 1

    mismatch = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/interview",
        json={
            "thread_id": "thread-2",
            "originating_actor_kind": "user",
            "originating_actor_id": owner_id,
        },
        headers=_headers(owner_id, **{"If-Match": first.headers["etag"]}),
    )
    assert mismatch.status_code == HTTPStatus.CONFLICT
    assert mismatch.json()["code"] == "application_interview_thread_mismatch"


@pytest.mark.asyncio
async def test_waitlist_from_in_review_and_interview_persists_reason(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC2: waitlist is valid from in_review and interview with reason."""
    in_review_id, in_review_owner, _applicant_id, in_review_etag = await _prepare_in_review(
        migrated_async_client,
        governance_db,
        applicant_discord_id="applicant-in-review",
        owner_discord_id="reviewer-in-review",
    )
    waitlisted = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{in_review_id}/waitlist",
        json={
            "reason": "waiting on schedule",
            "originating_actor_kind": "user",
            "originating_actor_id": in_review_owner,
        },
        headers=_headers(in_review_owner, **{"If-Match": in_review_etag}),
    )
    assert waitlisted.status_code == HTTPStatus.OK, waitlisted.text
    assert waitlisted.json()["state"] == "waitlisted"

    interview_id, interview_owner, _applicant_id, interview_etag = await _prepare_in_review(
        migrated_async_client,
        governance_db,
        applicant_discord_id="applicant-interview",
        owner_discord_id="reviewer-interview",
    )
    interview = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{interview_id}/interview",
        json={
            "thread_id": "thread-interview",
            "originating_actor_kind": "user",
            "originating_actor_id": interview_owner,
        },
        headers=_headers(interview_owner, **{"If-Match": interview_etag}),
    )
    from_interview = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{interview_id}/waitlist",
        json={
            "reason": "needs officer availability",
            "originating_actor_kind": "user",
            "originating_actor_id": interview_owner,
        },
        headers=_headers(interview_owner, **{"If-Match": interview.headers["etag"]}),
    )
    assert from_interview.status_code == HTTPStatus.OK, from_interview.text
    assert from_interview.json()["state"] == "waitlisted"

    with psycopg.connect(governance_dsn, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT ar.notes, ascg.diff_json, ascg.payload_json
            FROM application_reviews AS ar
            JOIN activity_state_changes AS ascg
              ON ascg.aggregate_id = ar.application_id::text
             AND ascg.aggregate_seq = ar.aggregate_seq
            WHERE ar.application_id = %s
              AND ar.action = 'waitlist'
            ORDER BY ar.aggregate_seq DESC
            LIMIT 1
            """,
            (UUID(interview_id),),
        ).fetchone()
    assert row["notes"] == "needs officer availability"
    assert row["diff_json"]["notes"]["new"] == "needs officer availability"
    assert row["payload_json"]["reason"] == "needs officer availability"


@pytest.mark.asyncio
async def test_waitlist_validation_and_owner_guard(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC2: waitlist rejects missing reason, repeat waitlist, and non-owner."""
    application_id, owner_id, _applicant_id, etag = await _prepare_in_review(
        migrated_async_client,
        governance_db,
    )
    missing_reason = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/waitlist",
        json={
            "originating_actor_kind": "user",
            "originating_actor_id": owner_id,
        },
        headers=_headers(owner_id, **{"If-Match": etag}),
    )
    assert missing_reason.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    other_id = _create_member(governance_db, "reviewer-other")
    _grant(governance_db, actor_id=other_id, permissions=frozenset({"application.waitlist"}))
    non_owner = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/waitlist",
        json={
            "reason": "not my application",
            "originating_actor_kind": "user",
            "originating_actor_id": other_id,
        },
        headers=_headers(other_id, **{"If-Match": etag}),
    )
    assert non_owner.status_code == HTTPStatus.CONFLICT
    assert non_owner.json()["code"] == "application_not_owner"

    waitlisted = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/waitlist",
        json={
            "reason": "waiting",
            "originating_actor_kind": "user",
            "originating_actor_id": owner_id,
        },
        headers=_headers(owner_id, **{"If-Match": etag}),
    )
    assert waitlisted.status_code == HTTPStatus.OK, waitlisted.text
    repeat = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/waitlist",
        json={
            "reason": "again",
            "originating_actor_kind": "user",
            "originating_actor_id": owner_id,
        },
        headers=_headers(owner_id, **{"If-Match": waitlisted.headers["etag"]}),
    )
    assert repeat.status_code == HTTPStatus.CONFLICT
    assert repeat.json()["code"] == "invalid_application_transition"


@pytest.mark.asyncio
async def test_user_actor_cannot_spoof_originating_actor(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """User-authenticated transitions record the authenticated actor as origin."""
    application_id, owner_id, _applicant_id, etag = await _prepare_in_review(
        migrated_async_client,
        governance_db,
        applicant_discord_id="applicant-origin",
        owner_discord_id="reviewer-origin",
    )

    response = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={
            "action": "waitlist",
            "reason": "waiting",
            "originating_actor_kind": "service",
            "originating_actor_id": "discord-ticket-bot",
        },
        headers=_headers(owner_id, **{"If-Match": etag}),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    with psycopg.connect(governance_dsn, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT request_json
            FROM activity_actions
            WHERE aggregate_id = %s
              AND action_type = 'application.waitlist'
              AND status = 'accepted'
            ORDER BY id DESC
            LIMIT 1
            """,
            (application_id,),
        ).fetchone()
    assert row is not None
    assert row["request_json"]["originating_actor_kind"] == "user"
    assert row["request_json"]["originating_actor_id"] == owner_id


@pytest.mark.asyncio
async def test_reactivate_from_waitlisted_uses_occ_and_handoff(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC2: reactivate returns claimed and enforces optimistic locking."""
    application_id, owner_id, _applicant_id, etag = await _prepare_in_review(
        migrated_async_client,
        governance_db,
    )
    waitlisted = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/waitlist",
        json={
            "reason": "waiting",
            "originating_actor_kind": "user",
            "originating_actor_id": owner_id,
        },
        headers=_headers(owner_id, **{"If-Match": etag}),
    )
    reactivator_id = _create_member(governance_db, "reviewer-reactivator")
    new_owner_id = _create_member(governance_db, "reviewer-new-owner")
    _grant(
        governance_db,
        actor_id=reactivator_id,
        permissions=frozenset({"application.reactivate"}),
    )

    stale = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/reactivate",
        json={
            "originating_actor_kind": "user",
            "originating_actor_id": reactivator_id,
        },
        headers=_headers(reactivator_id, **{"If-Match": etag}),
    )
    assert stale.status_code == HTTPStatus.PRECONDITION_FAILED
    assert stale.json()["code"] == "stale_application_version"

    retained = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/reactivate",
        json={
            "reason": "back in queue",
            "originating_actor_kind": "user",
            "originating_actor_id": reactivator_id,
        },
        headers=_headers(reactivator_id, **{"If-Match": waitlisted.headers["etag"]}),
    )
    assert retained.status_code == HTTPStatus.OK, retained.text
    assert retained.json()["state"] == "claimed"
    assert retained.json()["owner_id"] == owner_id

    second_id, second_owner, _applicant_id, second_etag = await _prepare_in_review(
        migrated_async_client,
        governance_db,
        applicant_discord_id="applicant-reactivate-2",
        owner_discord_id="reviewer-reactivate-owner-2",
    )
    second_waitlisted = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{second_id}/waitlist",
        json={
            "reason": "waiting",
            "originating_actor_kind": "user",
            "originating_actor_id": second_owner,
        },
        headers=_headers(second_owner, **{"If-Match": second_etag}),
    )
    changed = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{second_id}/reactivate",
        json={
            "new_owner_id": new_owner_id,
            "originating_actor_kind": "user",
            "originating_actor_id": reactivator_id,
        },
        headers=_headers(reactivator_id, **{"If-Match": second_waitlisted.headers["etag"]}),
    )
    assert changed.status_code == HTTPStatus.OK, changed.text
    assert changed.json()["state"] == "claimed"
    assert changed.json()["owner_id"] == new_owner_id


@pytest.mark.asyncio
async def test_interview_decisions_and_withdrawals_remain_valid(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: interview state still supports decision and withdrawal transitions."""
    application_id, owner_id, _applicant_id, etag = await _prepare_in_review(
        migrated_async_client,
        governance_db,
    )
    interview = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/interview",
        json={
            "thread_id": "thread-1",
            "originating_actor_kind": "user",
            "originating_actor_id": owner_id,
        },
        headers=_headers(owner_id, **{"If-Match": etag}),
    )
    approved = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": "approve", "decision_reason": "accepted"},
        headers=_headers(owner_id, **{"If-Match": interview.headers["etag"]}),
    )
    assert approved.status_code == HTTPStatus.OK, approved.text
    assert approved.json()["state"] == "approved"

    waitlist_id, waitlist_owner, _applicant_id, waitlist_etag = await _prepare_in_review(
        migrated_async_client,
        governance_db,
        applicant_discord_id="applicant-withdraw",
        owner_discord_id="reviewer-withdraw",
    )
    waitlisted = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{waitlist_id}/waitlist",
        json={
            "reason": "later",
            "originating_actor_kind": "user",
            "originating_actor_id": waitlist_owner,
        },
        headers=_headers(waitlist_owner, **{"If-Match": waitlist_etag}),
    )
    withdrawn = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{waitlist_id}/transitions",
        json={"action": "withdraw", "notes": "applicant withdrew"},
        headers=_headers(waitlist_owner, **{"If-Match": waitlisted.headers["etag"]}),
    )
    assert withdrawn.status_code == HTTPStatus.OK, withdrawn.text
    assert withdrawn.json()["state"] == "withdrawn"
