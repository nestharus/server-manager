from __future__ import annotations

from http import HTTPStatus

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.repositories.db import PostgresDatabase

from .compliance_helpers import EVIDENCE_URL, create_rule_http, grant, latest_action, submit_evidence_http


pytestmark = pytest.mark.usefixtures("governance_dsn")


def test_submit_creates_pending_evidence_row(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC2: submitting evidence stores the attachment first and returns a pending extraction state."""
    db: PostgresDatabase = app.state.container.core.db()
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_rule.write"}))
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_evidence.submit"}))

    rule, _etag = create_rule_http(client)
    evidence, evidence_etag = submit_evidence_http(client, rule_id=rule["id"])

    assert evidence["rule_id"] == rule["id"]
    assert evidence["chapter_id"] == "ch-1"
    assert evidence["extraction_status"] == "pending"
    assert evidence["submitted_by_member_id"] == "operator"
    assert evidence["version"] == 1
    assert evidence_etag == '"1"'


def test_submit_rejects_chapter_mismatch_with_rule(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC2: evidence.chapter_id must match the owning rule chapter instead of trusting the request body."""
    db: PostgresDatabase = app.state.container.core.db()
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_rule.write"}))
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_evidence.submit"}))

    rule, _etag = create_rule_http(client, chapter_id="ch-1")
    response = client.post(
        EVIDENCE_URL,
        json={
            "rule_id": rule["id"],
            "member_id": "member-1",
            "chapter_id": "ch-2",
            "attachment_ref": "s3://bucket/evidence.png",
        },
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator"},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["code"] == "evidence_chapter_mismatch"


def test_submit_requires_evidence_submit_authority(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC2: evidence submission is denied without compliance_evidence.submit authority."""
    db: PostgresDatabase = app.state.container.core.db()
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_rule.write"}))

    rule, _etag = create_rule_http(client)
    response = client.post(
        EVIDENCE_URL,
        json={
            "rule_id": rule["id"],
            "member_id": "member-1",
            "chapter_id": "ch-1",
            "attachment_ref": "s3://bucket/evidence.png",
        },
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator"},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["code"] == "authority_decision_denied"


def test_submit_audit_uses_actor_identity_not_request_body(
    client: TestClient,
    app: FastAPI,
    governance_dsn: str,
) -> None:
    """AC2: the audit/request payload derives submitted_by_member_id from the authenticated actor, not the body."""
    db: PostgresDatabase = app.state.container.core.db()
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_rule.write"}))
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_evidence.submit"}))

    rule, _etag = create_rule_http(client)
    submit_evidence_http(client, rule_id=rule["id"], actor_id="operator")
    action = latest_action(governance_dsn, action_type="evidence_submission.submit")

    assert action["request_json"]["submitted_by_member_id"] == "operator"
    assert set(action["request_json"]) == {
        "rule_id",
        "member_id",
        "chapter_id",
        "attachment_ref",
        "submitted_by_member_id",
    }


def test_get_evidence_returns_current_version_etag(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC2: reading evidence returns the current version as a strong ETag."""
    db: PostgresDatabase = app.state.container.core.db()
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_rule.write", "compliance_evidence.read"}))
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_evidence.submit"}))

    rule, _etag = create_rule_http(client)
    evidence, _evidence_etag = submit_evidence_http(client, rule_id=rule["id"])
    response = client.get(
        f"{EVIDENCE_URL}/{evidence['id']}",
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator"},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["id"] == evidence["id"]
    assert response.headers["etag"] == '"1"'


def test_staff_can_submit_evidence_on_behalf_of_member(
    client: TestClient,
    app: FastAPI,
) -> None:
    """Service actors may attribute a submission to a different member (staff-on-behalf)."""
    db: PostgresDatabase = app.state.container.core.db()
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_rule.write"}))
    grant(db, grantee_id="bot-ingester", permissions=frozenset({"compliance_evidence.submit"}))

    rule, _etag = create_rule_http(client)
    response = client.post(
        EVIDENCE_URL,
        json={
            "rule_id": rule["id"],
            "member_id": "member-1",
            "chapter_id": "ch-1",
            "attachment_ref": "s3://bucket/evidence.png",
            "submitted_by_member_id": "member-1",
        },
        headers={"X-Actor-Kind": "service", "X-Actor-Id": "bot-ingester"},
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    assert response.json()["submitted_by_member_id"] == "member-1"


def test_user_cannot_spoof_submitted_by_member_id(
    client: TestClient,
    app: FastAPI,
) -> None:
    """User actors cannot attribute submissions to a different member."""
    db: PostgresDatabase = app.state.container.core.db()
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_rule.write"}))
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_evidence.submit"}))

    rule, _etag = create_rule_http(client)
    response = client.post(
        EVIDENCE_URL,
        json={
            "rule_id": rule["id"],
            "member_id": "member-1",
            "chapter_id": "ch-1",
            "attachment_ref": "s3://bucket/evidence.png",
            "submitted_by_member_id": "someone-else",
        },
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator"},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["code"] == "submitted_by_mismatch"
