from __future__ import annotations

from http import HTTPStatus

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.repositories.db import PostgresDatabase

from .compliance_helpers import (
    EVIDENCE_URL,
    StaticOcrProvider,
    create_rule_http,
    fetch_all,
    grant,
    set_ocr_provider,
    submit_evidence_http,
)


pytestmark = pytest.mark.usefixtures("governance_dsn")


def _seed_completed_evidence(client: TestClient, app: FastAPI) -> tuple[dict, str]:
    db: PostgresDatabase = app.state.container.core.db()
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_rule.write"}))
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_evidence.submit", "compliance_evidence.extract", "compliance_evidence.correct"}))
    rule, _rule_etag = create_rule_http(client)
    evidence, _evidence_etag = submit_evidence_http(client, rule_id=rule["id"])
    set_ocr_provider(app, StaticOcrProvider(raw_text="baseline text", extracted_fields={"attendance": False}))
    extract = client.post(
        f"{EVIDENCE_URL}/{evidence['id']}/extract",
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator"},
    )
    assert extract.status_code == HTTPStatus.OK, extract.text
    return extract.json(), extract.headers["etag"]


def test_correction_writes_overlay_and_preserves_baseline(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC3: officer correction writes an overlay without overwriting OCR raw_text or extracted_fields."""
    extracted, etag = _seed_completed_evidence(client, app)

    response = client.post(
        f"{EVIDENCE_URL}/{extracted['id']}/correct",
        json={"corrected_fields": {"attendance": True}, "correction_reason": "verified manually"},
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator", "If-Match": etag},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["raw_text"] == "baseline text"
    assert response.json()["extracted_fields"] == {"attendance": False}
    assert response.json()["extracted_fields_corrected"] == {"attendance": True}
    assert response.json()["extraction_status"] == "corrected"
    assert response.json()["corrected_by_member_id"] == "operator"


def test_correction_rejects_pending_status(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC3: evidence cannot be corrected while extraction is still pending."""
    db: PostgresDatabase = app.state.container.core.db()
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_rule.write"}))
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_evidence.submit", "compliance_evidence.correct"}))
    rule, _rule_etag = create_rule_http(client)
    evidence, evidence_etag = submit_evidence_http(client, rule_id=rule["id"])

    response = client.post(
        f"{EVIDENCE_URL}/{evidence['id']}/correct",
        json={"corrected_fields": {"attendance": True}, "correction_reason": "verified manually"},
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator", "If-Match": evidence_etag},
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["code"] == "correction_not_permitted_status"


def test_correction_requires_strong_if_match(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC3: correction enforces optimistic locking through If-Match."""
    extracted, _etag = _seed_completed_evidence(client, app)

    response = client.post(
        f"{EVIDENCE_URL}/{extracted['id']}/correct",
        json={"corrected_fields": {"attendance": True}, "correction_reason": "verified manually"},
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator", "If-Match": '"999"'},
    )

    assert response.status_code == HTTPStatus.PRECONDITION_FAILED
    assert response.json()["code"] == "stale_compliance_version"


def test_correction_requires_authority(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC3: correction is denied without compliance_evidence.correct authority."""
    db: PostgresDatabase = app.state.container.core.db()
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_rule.write"}))
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_evidence.submit", "compliance_evidence.extract"}))
    rule, _rule_etag = create_rule_http(client)
    evidence, _evidence_etag = submit_evidence_http(client, rule_id=rule["id"])
    set_ocr_provider(app, StaticOcrProvider(extracted_fields={"attendance": False}))
    extract = client.post(
        f"{EVIDENCE_URL}/{evidence['id']}/extract",
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator"},
    )

    response = client.post(
        f"{EVIDENCE_URL}/{evidence['id']}/correct",
        json={"corrected_fields": {"attendance": True}, "correction_reason": "verified manually"},
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator", "If-Match": extract.headers["etag"]},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["code"] == "authority_decision_denied"


def test_second_correction_diff_preserves_prior_overlay(
    client: TestClient,
    app: FastAPI,
    governance_dsn: str,
) -> None:
    """AC3: a second correction records prior overlay, new overlay, and immutable OCR baseline in diff_json."""
    extracted, etag = _seed_completed_evidence(client, app)
    first = client.post(
        f"{EVIDENCE_URL}/{extracted['id']}/correct",
        json={"corrected_fields": {"attendance": True}, "correction_reason": "first pass"},
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator", "If-Match": etag},
    )
    second = client.post(
        f"{EVIDENCE_URL}/{extracted['id']}/correct",
        json={"corrected_fields": {"attendance": False, "notes": "late"}, "correction_reason": "second pass"},
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator", "If-Match": first.headers["etag"]},
    )

    changes = fetch_all(
        governance_dsn,
        """
        SELECT diff_json
        FROM activity_state_changes
        WHERE aggregate_type = 'evidence_submission'
          AND aggregate_id = %s
          AND change_type = 'evidence_submission.corrected'
        ORDER BY aggregate_seq ASC
        """,
        (extracted["id"],),
    )

    assert second.status_code == HTTPStatus.OK, second.text
    assert changes[0]["diff_json"]["from"]["extracted_fields_corrected"] is None
    assert changes[0]["diff_json"]["to"]["extracted_fields_corrected"] == {"attendance": True}
    assert changes[1]["diff_json"]["from"]["extracted_fields_corrected"] == {"attendance": True}
    assert changes[1]["diff_json"]["to"]["extracted_fields_corrected"] == {
        "attendance": False,
        "notes": "late",
    }
    assert changes[1]["diff_json"]["baseline"]["extracted_fields"] == {"attendance": False}
