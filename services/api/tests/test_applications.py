from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import psycopg
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
            },
            {
                "id": "score",
                "type": "number",
                "label": "Score",
                "required": True,
            },
            {
                "id": "class",
                "type": "select",
                "label": "Class",
                "required": True,
                "options": ["warrior", "mage"],
            },
            {
                "id": "roles",
                "type": "multi_select",
                "label": "Roles",
                "required": True,
                "options": ["tank", "healer"],
            },
            {"id": "ready", "type": "boolean", "label": "Ready"},
        ],
        "routing_rules": {
            "schema_version": 1,
            "queue": "chapter_officers",
            "review_scope": {"scope_kind": "chapter", "scope_id": "chapter-1"},
        },
    }


def _application_payload(applicant_id: str, *, client_id: str = "interaction-1") -> dict[str, Any]:
    return {
        "applicant_id": applicant_id,
        "scope": {"scope_kind": "chapter", "scope_id": "chapter-1"},
        "responses": {
            "nickname": "Ada",
            "score": 42,
            "class": "mage",
            "roles": ["healer"],
            "ready": True,
        },
        "client_application_id": client_id,
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


async def _submit(client: AsyncClient, applicant_id: str, *, client_id: str = "interaction-1"):
    return await client.post(
        APPLICATIONS_URL,
        json=_application_payload(applicant_id, client_id=client_id),
        headers=_headers(applicant_id),
    )


async def _claim_application(
    client: AsyncClient,
    *,
    application_id: str,
    etag: str,
    owner_id: str,
) -> tuple[dict[str, Any], str]:
    response = await client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": "claim"},
        headers=_headers(owner_id, **{"If-Match": etag}),
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json(), response.headers["etag"]


async def _move_application_to_waitlisted(
    client: AsyncClient,
    *,
    application_id: str,
    etag: str,
    owner_id: str,
) -> tuple[dict[str, Any], str]:
    claimed, claim_etag = await _claim_application(
        client,
        application_id=application_id,
        etag=etag,
        owner_id=owner_id,
    )
    review = await client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": "review", "notes": "needs later review"},
        headers=_headers(owner_id, **{"If-Match": claim_etag}),
    )
    assert review.status_code == HTTPStatus.OK, review.text
    waitlist = await client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": "waitlist", "reason": "come back later"},
        headers=_headers(owner_id, **{"If-Match": review.headers["etag"]}),
    )
    assert waitlist.status_code == HTTPStatus.OK, waitlist.text
    assert claimed["state"] == "claimed"
    return waitlist.json(), waitlist.headers["etag"]


@pytest.fixture
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


@pytest.mark.asyncio
async def test_submit_creates_queued_application_with_pinned_snapshot(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    await _publish_form(migrated_async_client, governance_db)
    applicant_id = _create_member(governance_db, "applicant-1")

    response = await _submit(migrated_async_client, applicant_id)

    assert response.status_code == HTTPStatus.CREATED, response.text
    body = response.json()
    assert body["state"] == "queued"
    assert body["version"] == 2
    assert response.headers["etag"] == '"2"'
    assert body["form_snapshot"]["form_version"] == 1
    assert body["queued_at"] is not None

    with psycopg.connect(governance_dsn) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM application_reviews WHERE application_id = %s AND action = 'route'",
            (UUID(body["id"]),),
        ).fetchone()[0]
    assert count == 1


@pytest.mark.asyncio
async def test_authenticated_submit_rejects_synthetic_applicant(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    synthetic_member_guard_member_factory,
) -> None:
    """Risk annotation: group=TG-2; named_risk=authenticated_submit_synthetic_applicant;
    level=component; source=.tmp/init-124/phase6/step6a-contract.md#C2.
    """
    await _publish_form(migrated_async_client, governance_db)
    synthetic = synthetic_member_guard_member_factory.synthetic()

    response = await _submit(
        migrated_async_client,
        str(synthetic.id),
        client_id=f"synthetic-auth-{uuid4().hex}",
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "applicant_synthetic_not_allowed"


@pytest.mark.asyncio
async def test_authenticated_submit_still_accepts_real_discord_member(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    synthetic_member_guard_member_factory,
) -> None:
    """Risk annotation: group=TG-2; named_risk=authenticated_submit_real_member_regression;
    level=component; source=.tmp/init-124/phase6/step6a-contract.md#C2.
    """
    await _publish_form(migrated_async_client, governance_db)
    real = synthetic_member_guard_member_factory.real()

    response = await _submit(
        migrated_async_client,
        str(real.id),
        client_id=f"real-auth-{uuid4().hex}",
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    assert response.json()["applicant_id"] == str(real.id)


@pytest.mark.asyncio
async def test_duplicate_client_application_id_returns_409_without_second_review(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    await _publish_form(migrated_async_client, governance_db)
    applicant_id = _create_member(governance_db, "applicant-1")
    first = await _submit(migrated_async_client, applicant_id)
    assert first.status_code == HTTPStatus.CREATED, first.text

    duplicate = await _submit(migrated_async_client, applicant_id)

    assert duplicate.status_code == HTTPStatus.CONFLICT
    assert duplicate.json()["code"] == "duplicate_application_create"
    assert duplicate.json()["application"]["id"] == first.json()["id"]
    with psycopg.connect(governance_dsn) as conn:
        count = conn.execute("SELECT COUNT(*) FROM application_reviews").fetchone()[0]
    assert count == 1


@pytest.mark.asyncio
async def test_submit_rejects_empty_required_short_and_multi_select(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    await _publish_form(migrated_async_client, governance_db)
    applicant_id = _create_member(governance_db, "applicant-1")
    body = _application_payload(applicant_id, client_id=f"interaction-{uuid4().hex}")
    body["responses"]["nickname"] = "   "
    body["responses"]["roles"] = []

    response = await migrated_async_client.post(
        APPLICATIONS_URL,
        json=body,
        headers=_headers(applicant_id),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["code"] == "invalid_application_response"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "responses",
    [
        {"score": 42, "class": "mage"},
        {"nickname": "Ada", "score": 42, "class": "mage", "unknown": "x"},
        {"nickname": "Ada", "score": True, "class": "mage"},
        {"nickname": "A" * 17, "score": 42, "class": "mage"},
        {"nickname": "Ada", "score": 42, "class": "rogue"},
        {"nickname": "Ada", "score": 42, "class": "mage", "roles": ["tank", "tank"]},
        {"nickname": "Ada", "score": 42, "class": "mage", "roles": [{}]},
    ],
)
async def test_submit_validates_responses_against_snapshot(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    responses: dict[str, Any],
) -> None:
    await _publish_form(migrated_async_client, governance_db)
    applicant_id = _create_member(governance_db, "applicant-1")
    body = _application_payload(applicant_id, client_id=f"interaction-{uuid4().hex}")
    body["responses"] = responses

    response = await migrated_async_client.post(
        APPLICATIONS_URL,
        json=body,
        headers=_headers(applicant_id),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_claim_conflict_maps_stale_claim_to_409(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    await _publish_form(migrated_async_client, governance_db)
    applicant_id = _create_member(governance_db, "applicant-1")
    reviewer_1 = _create_member(governance_db, "reviewer-1")
    reviewer_2 = _create_member(governance_db, "reviewer-2")
    _grant(governance_db, actor_id=reviewer_1, permissions=frozenset({"application.claim"}))
    _grant(governance_db, actor_id=reviewer_2, permissions=frozenset({"application.claim"}))
    created = await _submit(migrated_async_client, applicant_id)
    application_id = created.json()["id"]
    stale_etag = created.headers["etag"]

    first = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": "claim"},
        headers=_headers(reviewer_1, **{"If-Match": stale_etag}),
    )
    assert first.status_code == HTTPStatus.OK, first.text
    assert first.json()["owner_id"] == reviewer_1

    second = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": "claim"},
        headers=_headers(reviewer_2, **{"If-Match": stale_etag}),
    )
    assert second.status_code == HTTPStatus.CONFLICT
    assert second.json()["code"] == "application_already_claimed"


@pytest.mark.asyncio
async def test_claim_rejects_synthetic_owner_actor(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    synthetic_member_guard_member_factory,
) -> None:
    """Risk annotation: group=TG-3; named_risk=application_owner_synthetic_claim;
    level=component; source=.tmp/init-124/phase6/step6a-contract.md#C3.
    """
    await _publish_form(migrated_async_client, governance_db)
    applicant = synthetic_member_guard_member_factory.real()
    synthetic_owner = synthetic_member_guard_member_factory.synthetic()
    _grant(
        governance_db,
        actor_id=str(synthetic_owner.id),
        permissions=frozenset({"application.claim"}),
    )
    created = await _submit(migrated_async_client, str(applicant.id))

    response = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{created.json()['id']}/transitions",
        json={"action": "claim"},
        headers=_headers(str(synthetic_owner.id), **{"If-Match": created.headers["etag"]}),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "owner_synthetic_not_allowed"


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["reassign", "reactivate"])
async def test_owner_transition_rejects_synthetic_new_owner(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    synthetic_member_guard_member_factory,
    action: str,
) -> None:
    """Risk annotation: group=TG-3; named_risk=application_owner_synthetic_assignment;
    level=component; source=.tmp/init-124/phase6/step6a-contract.md#C3.
    """
    await _publish_form(migrated_async_client, governance_db)
    applicant = synthetic_member_guard_member_factory.real()
    owner = synthetic_member_guard_member_factory.real()
    synthetic_new_owner = synthetic_member_guard_member_factory.synthetic()
    manager = synthetic_member_guard_member_factory.real()
    _grant(
        governance_db,
        actor_id=str(owner.id),
        permissions=frozenset({"application.claim", "application.review", "application.waitlist"}),
    )
    _grant(
        governance_db,
        actor_id=str(manager.id),
        permissions=frozenset({"application.review", "application.reactivate"}),
    )
    created = await _submit(migrated_async_client, str(applicant.id))
    application_id = created.json()["id"]
    if action == "reactivate":
        _waitlisted, etag = await _move_application_to_waitlisted(
            migrated_async_client,
            application_id=application_id,
            etag=created.headers["etag"],
            owner_id=str(owner.id),
        )
    else:
        etag = created.headers["etag"]

    response = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": action, "new_owner_id": str(synthetic_new_owner.id), "reason": "handoff"},
        headers=_headers(str(manager.id), **{"If-Match": etag}),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["code"] == "owner_synthetic_not_allowed"


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["reassign", "reactivate"])
async def test_owner_transition_accepts_real_new_owner(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
    synthetic_member_guard_member_factory,
    action: str,
) -> None:
    """Risk annotation: group=TG-3; named_risk=application_owner_real_member_regression;
    level=component; source=.tmp/init-124/phase6/step6a-contract.md#C3.
    """
    await _publish_form(migrated_async_client, governance_db)
    applicant = synthetic_member_guard_member_factory.real()
    owner = synthetic_member_guard_member_factory.real()
    real_new_owner = synthetic_member_guard_member_factory.real()
    manager = synthetic_member_guard_member_factory.real()
    _grant(
        governance_db,
        actor_id=str(owner.id),
        permissions=frozenset({"application.claim", "application.review", "application.waitlist"}),
    )
    _grant(
        governance_db,
        actor_id=str(manager.id),
        permissions=frozenset({"application.review", "application.reactivate"}),
    )
    created = await _submit(migrated_async_client, str(applicant.id))
    application_id = created.json()["id"]
    if action == "reactivate":
        _waitlisted, etag = await _move_application_to_waitlisted(
            migrated_async_client,
            application_id=application_id,
            etag=created.headers["etag"],
            owner_id=str(owner.id),
        )
    else:
        etag = created.headers["etag"]

    response = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": action, "new_owner_id": str(real_new_owner.id), "reason": "handoff"},
        headers=_headers(str(manager.id), **{"If-Match": etag}),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["owner_id"] == str(real_new_owner.id)


@pytest.mark.asyncio
async def test_only_owner_can_review_approve_deny(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    await _publish_form(migrated_async_client, governance_db)
    applicant_id = _create_member(governance_db, "applicant-1")
    owner = _create_member(governance_db, "reviewer-1")
    other = _create_member(governance_db, "reviewer-2")
    _grant(
        governance_db,
        actor_id=owner,
        permissions=frozenset(
            {"application.claim", "application.review", "application.approve", "application.deny"}
        ),
    )
    _grant(
        governance_db,
        actor_id=other,
        permissions=frozenset(
            {"application.review", "application.approve", "application.deny"}
        ),
    )
    created = await _submit(migrated_async_client, applicant_id)
    application_id = created.json()["id"]

    claimed = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": "claim"},
        headers=_headers(owner, **{"If-Match": created.headers["etag"]}),
    )
    assert claimed.status_code == HTTPStatus.OK, claimed.text

    review = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": "review", "notes": "not your claim"},
        headers=_headers(other, **{"If-Match": claimed.headers["etag"]}),
    )
    assert review.status_code == HTTPStatus.CONFLICT
    assert review.json()["code"] == "application_not_owner"

    reviewed = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": "review", "notes": "owner review"},
        headers=_headers(owner, **{"If-Match": claimed.headers["etag"]}),
    )
    assert reviewed.status_code == HTTPStatus.OK, reviewed.text

    approve = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": "approve", "decision_reason": "not your claim"},
        headers=_headers(other, **{"If-Match": reviewed.headers["etag"]}),
    )
    assert approve.status_code == HTTPStatus.CONFLICT
    assert approve.json()["code"] == "application_not_owner"

    deny = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": "deny", "decision_reason": "not your claim"},
        headers=_headers(other, **{"If-Match": reviewed.headers["etag"]}),
    )
    assert deny.status_code == HTTPStatus.CONFLICT
    assert deny.json()["code"] == "application_not_owner"


@pytest.mark.asyncio
async def test_review_and_decisions_enforce_required_fields(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    await _publish_form(migrated_async_client, governance_db)
    applicant_id = _create_member(governance_db, "applicant-1")
    reviewer = _create_member(governance_db, "reviewer-1")
    _grant(
        governance_db,
        actor_id=reviewer,
        permissions=frozenset({"application.claim", "application.review", "application.approve"}),
    )
    created = await _submit(migrated_async_client, applicant_id)
    application_id = created.json()["id"]
    claimed = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": "claim"},
        headers=_headers(reviewer, **{"If-Match": created.headers["etag"]}),
    )
    assert claimed.status_code == HTTPStatus.OK, claimed.text

    missing_notes = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": "review"},
        headers=_headers(reviewer, **{"If-Match": claimed.headers["etag"]}),
    )
    assert missing_notes.status_code == HTTPStatus.CONFLICT
    assert missing_notes.json()["code"] == "application_review_notes_required"

    reviewed = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": "review", "notes": "looks good"},
        headers=_headers(reviewer, **{"If-Match": claimed.headers["etag"]}),
    )
    assert reviewed.status_code == HTTPStatus.OK, reviewed.text

    missing_reason = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": "approve"},
        headers=_headers(reviewer, **{"If-Match": reviewed.headers["etag"]}),
    )
    assert missing_reason.status_code == HTTPStatus.CONFLICT
    assert missing_reason.json()["code"] == "application_decision_reason_required"

    approved = await migrated_async_client.post(
        f"{APPLICATIONS_URL}/{application_id}/transitions",
        json={"action": "approve", "decision_reason": "accepted"},
        headers=_headers(reviewer, **{"If-Match": reviewed.headers["etag"]}),
    )
    assert approved.status_code == HTTPStatus.OK, approved.text
    assert approved.json()["state"] == "approved"
    assert approved.json()["decision_reason"] == "accepted"
