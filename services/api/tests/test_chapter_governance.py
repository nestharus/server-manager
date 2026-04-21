from __future__ import annotations

from http import HTTPStatus

from fastapi.testclient import TestClient

from app.repositories.db import PostgresDatabase

from .chapter_governance_helpers import (
    ACTOR_HEADERS,
    CHAPTERS_URL,
    create_active_chapter,
    seed_operator_and_archiver_grants,
)


def test_governance_suspend_requires_reason_and_current_version(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: governance suspend requires If-Match and a non-empty reason."""
    seed_operator_and_archiver_grants(governance_db)
    chapter, etag = create_active_chapter(client)

    missing_reason = client.post(
        f"{CHAPTERS_URL}/{chapter['id']}/governance-transitions",
        json={
            "action": "suspend",
            "to_state": "probation",
            "reason": "",
            "originating_actor_kind": "user",
            "originating_actor_id": "1001",
        },
        headers={**ACTOR_HEADERS, "If-Match": etag},
    )
    assert missing_reason.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    missing_if_match = client.post(
        f"{CHAPTERS_URL}/{chapter['id']}/governance-transitions",
        json={
            "action": "suspend",
            "to_state": "probation",
            "reason": "probation required",
            "originating_actor_kind": "user",
            "originating_actor_id": "1001",
        },
        headers=ACTOR_HEADERS,
    )
    assert missing_if_match.status_code == HTTPStatus.PRECONDITION_REQUIRED

    response = client.post(
        f"{CHAPTERS_URL}/{chapter['id']}/governance-transitions",
        json={
            "action": "suspend",
            "to_state": "probation",
            "reason": "probation required",
            "originating_actor_kind": "user",
            "originating_actor_id": "1001",
        },
        headers={**ACTOR_HEADERS, "If-Match": etag},
    )
    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["state"] == "probation"
    assert response.headers["etag"] == '"5"'


def test_governance_invalid_transition_and_action_mismatch_return_409(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: invalid governance edges and action/state mismatches return 409."""
    seed_operator_and_archiver_grants(governance_db)
    chapter, etag = create_active_chapter(client)

    mismatch = client.post(
        f"{CHAPTERS_URL}/{chapter['id']}/governance-transitions",
        json={
            "action": "suspend",
            "to_state": "active",
            "reason": "bad mapping",
            "originating_actor_kind": "user",
            "originating_actor_id": "1001",
        },
        headers={**ACTOR_HEADERS, "If-Match": etag},
    )
    assert mismatch.status_code == HTTPStatus.CONFLICT
    assert mismatch.json()["code"] == "invalid_chapter_governance_transition"

    archived = client.post(
        f"{CHAPTERS_URL}/{chapter['id']}/governance-transitions",
        json={
            "action": "archive",
            "to_state": "archiving",
            "reason": "archive",
            "originating_actor_kind": "user",
            "originating_actor_id": "1001",
        },
        headers={**ACTOR_HEADERS, "If-Match": etag},
    )
    assert archived.status_code == HTTPStatus.OK, archived.text
    invalid_worker_edge = client.post(
        f"{CHAPTERS_URL}/{chapter['id']}/governance-transitions",
        json={
            "action": "restore",
            "to_state": "active",
            "reason": "restore",
            "originating_actor_kind": "user",
            "originating_actor_id": "1001",
        },
        headers={**ACTOR_HEADERS, "If-Match": archived.headers["etag"]},
    )
    assert invalid_worker_edge.status_code == HTTPStatus.CONFLICT


def test_governance_stale_version_returns_412(
    client: TestClient,
    governance_db: PostgresDatabase,
) -> None:
    """AC1: stale governance If-Match values return 412."""
    seed_operator_and_archiver_grants(governance_db)
    chapter, _etag = create_active_chapter(client)

    response = client.post(
        f"{CHAPTERS_URL}/{chapter['id']}/governance-transitions",
        json={
            "action": "suspend",
            "to_state": "probation",
            "reason": "probation required",
            "originating_actor_kind": "user",
            "originating_actor_id": "1001",
        },
        headers={**ACTOR_HEADERS, "If-Match": '"1"'},
    )
    assert response.status_code == HTTPStatus.PRECONDITION_FAILED
