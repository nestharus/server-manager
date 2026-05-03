from __future__ import annotations

from datetime import UTC, datetime
from http import HTTPStatus

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.repositories.db import PostgresDatabase
from app.services.compliance import compliance_evaluator_actor

from psycopg.types.json import Jsonb

from .compliance_helpers import (
    EVALUATIONS_URL,
    audit_context,
    create_roster_entry,
    create_rule_http,
    fetch_one,
    grant,
    grant_evaluator,
    seed_chapter_and_roles,
    seed_evidence,
)
from app.core.context import use_audit_context


pytestmark = pytest.mark.usefixtures("governance_dsn")


def _seed_pending_review_evaluation(
    client: TestClient,
    app: FastAPI,
    *,
    member_id: str = "member-1",
) -> dict:
    db: PostgresDatabase = app.state.db
    roles = seed_chapter_and_roles(db)
    grant(db, grantee_id="operator", permissions=frozenset({"roster.write", "roster.read", "roster.remove"}))
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_rule.write"}))
    create_roster_entry(client, roles["member"], member_id=member_id)
    rule, _rule_etag = create_rule_http(
        client,
        consequence_kind="under_review",
        consequence_params={"auto_apply": True, "require_review": True},
    )
    grant_evaluator(db)
    service = app.state.container.services.compliance()
    with use_audit_context(audit_context()):
        evaluations = service.run_scheduled_compliance_evaluations(
            now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC),
            actor=compliance_evaluator_actor(),
        )
    assert len(evaluations) == 1
    return {"rule": rule, "evaluation": evaluations[0]}


def test_get_evaluation_returns_read_model(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC4: reading a compliance evaluation returns the populated review model with an ETag."""
    db: PostgresDatabase = app.state.db
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_evaluation.read"}))
    seeded = _seed_pending_review_evaluation(client, app)

    response = client.get(
        f"{EVALUATIONS_URL}/{seeded['evaluation'].id}",
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator"},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["review_status"] == "pending"
    assert response.headers["etag"] == '"1"'


def test_review_approve_updates_reviewer_fields(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC4: approving a pending evaluation records the reviewer, reason, and approved status."""
    db: PostgresDatabase = app.state.db
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_evaluation.review"}))
    seeded = _seed_pending_review_evaluation(client, app)

    response = client.post(
        f"{EVALUATIONS_URL}/{seeded['evaluation'].id}/review",
        json={"action": "approve", "reviewer_reason": "looks correct"},
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator", "If-Match": '"1"'},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["review_status"] == "approved"
    assert response.json()["reviewer_id"] == "operator"
    assert response.json()["review_reason"] == "looks correct"


def test_review_override_to_violation_applies_under_review(
    client: TestClient,
    app: FastAPI,
    governance_dsn: str,
) -> None:
    """AC4: overriding a pending evaluation to violation can advance the consequence through the roster service path."""
    db: PostgresDatabase = app.state.db
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_evaluation.review"}))
    seeded = _seed_pending_review_evaluation(client, app)

    response = client.post(
        f"{EVALUATIONS_URL}/{seeded['evaluation'].id}/review",
        json={
            "action": "override",
            "override_result": "violation",
            "reviewer_reason": "manual review found violation",
        },
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator", "If-Match": '"1"'},
    )
    roster_row = fetch_one(
        governance_dsn,
        "SELECT status FROM roster_entries WHERE member_id = %s",
        ("member-1",),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["result"] == "violation"
    assert response.json()["consequence_applied"] == "under_review_applied"
    assert response.json()["review_status"] == "overridden"
    assert roster_row["status"] == "under_review"


def test_review_requires_current_etag(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC4: reviewing an evaluation rejects stale If-Match versions."""
    db: PostgresDatabase = app.state.db
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_evaluation.review"}))
    seeded = _seed_pending_review_evaluation(client, app)

    response = client.post(
        f"{EVALUATIONS_URL}/{seeded['evaluation'].id}/review",
        json={"action": "approve", "reviewer_reason": "looks correct"},
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator", "If-Match": '"999"'},
    )

    assert response.status_code == HTTPStatus.PRECONDITION_FAILED
    assert response.json()["code"] == "stale_compliance_version"


def test_review_requires_authority(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC4: review actions are denied without compliance_evaluation.review authority."""
    seeded = _seed_pending_review_evaluation(client, app)

    response = client.post(
        f"{EVALUATIONS_URL}/{seeded['evaluation'].id}/review",
        json={"action": "approve", "reviewer_reason": "looks correct"},
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator", "If-Match": '"1"'},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["code"] == "authority_decision_denied"


def _seed_pending_violation_under_review(
    client: TestClient,
    app: FastAPI,
    *,
    member_id: str = "member-1",
) -> dict:
    db: PostgresDatabase = app.state.db
    roles = seed_chapter_and_roles(db)
    grant(db, grantee_id="operator", permissions=frozenset({"roster.write", "roster.read", "roster.remove"}))
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_rule.write"}))
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_evidence.submit"}))
    create_roster_entry(client, roles["member"], member_id=member_id)
    rule, _rule_etag = create_rule_http(
        client,
        consequence_kind="under_review",
        consequence_params={"auto_apply": False, "require_review": True},
    )
    evidence = seed_evidence(app, rule_id=rule["id"], member_id=member_id)
    with db.connection() as connection:
        connection.execute(
            """
            UPDATE evidence_submissions
            SET raw_text = %s,
                extracted_fields = %s,
                extraction_status = 'completed',
                extraction_confidence = 0.95,
                submitted_at = %s,
                extraction_error = NULL
            WHERE id = %s
            """,
            (
                "ocr text",
                Jsonb({"attendance": False}),
                datetime(2026, 4, 18, 12, 0, tzinfo=UTC),
                evidence.id,
            ),
        )
    grant_evaluator(db)
    service = app.state.container.services.compliance()
    with use_audit_context(audit_context()):
        evaluations = service.run_scheduled_compliance_evaluations(
            now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC),
            actor=compliance_evaluator_actor(),
        )
    assert len(evaluations) == 1
    return {"rule": rule, "evaluation": evaluations[0]}


def test_review_approve_of_under_review_violation_applies_consequence(
    client: TestClient,
    app: FastAPI,
    governance_dsn: str,
) -> None:
    """Approving a pending under_review violation must resolve consequence to under_review_applied and transition roster."""
    db: PostgresDatabase = app.state.db
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_evaluation.review"}))
    seeded = _seed_pending_violation_under_review(client, app)

    assert seeded["evaluation"].result == "violation"
    assert seeded["evaluation"].consequence_applied == "none"
    assert seeded["evaluation"].review_status == "pending"

    response = client.post(
        f"{EVALUATIONS_URL}/{seeded['evaluation'].id}/review",
        json={"action": "approve", "reviewer_reason": "confirm violation"},
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator", "If-Match": '"1"'},
    )
    roster_row = fetch_one(
        governance_dsn,
        "SELECT status FROM roster_entries WHERE member_id = %s",
        ("member-1",),
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["result"] == "violation"
    assert response.json()["consequence_applied"] == "under_review_applied"
    assert response.json()["review_status"] == "approved"
    assert roster_row["status"] == "under_review"
