from __future__ import annotations

from http import HTTPStatus

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.infrastructure.ocr import StubOcrProvider
from app.repositories.db import PostgresDatabase

from .compliance_helpers import (
    EVIDENCE_URL,
    FailingOcrProvider,
    StaticOcrProvider,
    create_rule_http,
    grant,
    latest_action,
    set_ocr_provider,
    submit_evidence_http,
)


pytestmark = pytest.mark.usefixtures("governance_dsn")


def _seed_pending_evidence(client: TestClient, app: FastAPI) -> dict:
    db: PostgresDatabase = app.state.container.core.db()
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_rule.write"}))
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_evidence.submit", "compliance_evidence.extract"}))
    rule, _rule_etag = create_rule_http(client)
    evidence, _evidence_etag = submit_evidence_http(client, rule_id=rule["id"])
    return evidence


def test_extract_invokes_provider_and_marks_completed(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC2: extract uses the configured OCR provider and persists completed OCR output synchronously."""
    evidence = _seed_pending_evidence(client, app)
    set_ocr_provider(app, StaticOcrProvider(raw_text="parsed", extracted_fields={"attendance": True}))

    response = client.post(
        f"{EVIDENCE_URL}/{evidence['id']}/extract",
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator"},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["raw_text"] == "parsed"
    assert response.json()["extracted_fields"] == {"attendance": True}
    assert response.json()["extraction_status"] == "completed"


def test_extract_failure_marks_failed_status(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC2: provider failures persist a failed extraction state with a sanitized error message."""
    evidence = _seed_pending_evidence(client, app)
    set_ocr_provider(app, FailingOcrProvider("ocr blew up with secret=hunter2"))

    response = client.post(
        f"{EVIDENCE_URL}/{evidence['id']}/extract",
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator"},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["extraction_status"] == "failed"
    assert response.json()["extraction_error"] == "OCR extraction failed"
    assert "secret" not in response.json()["extraction_error"]


def test_extract_with_stub_provider_returns_503(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC2: the default stub OCR provider surfaces a 503 instead of pretending extraction succeeded."""
    evidence = _seed_pending_evidence(client, app)
    set_ocr_provider(app, StubOcrProvider())

    response = client.post(
        f"{EVIDENCE_URL}/{evidence['id']}/extract",
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator"},
    )

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()["code"] == "ocr_provider_not_configured"


def test_extract_is_repeatable_without_overwriting_correction_overlay(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC2: repeated extraction updates OCR output but keeps any officer correction overlay intact."""
    evidence = _seed_pending_evidence(client, app)
    db: PostgresDatabase = app.state.container.core.db()
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_evidence.correct"}))
    set_ocr_provider(app, StaticOcrProvider(raw_text="first", extracted_fields={"attendance": False}))
    first = client.post(
        f"{EVIDENCE_URL}/{evidence['id']}/extract",
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator"},
    )
    correct = client.post(
        f"{EVIDENCE_URL}/{evidence['id']}/correct",
        json={"corrected_fields": {"attendance": True}, "correction_reason": "manual"},
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator", "If-Match": first.headers["etag"]},
    )
    set_ocr_provider(app, StaticOcrProvider(raw_text="second", extracted_fields={"attendance": False, "count": 1}))
    second = client.post(
        f"{EVIDENCE_URL}/{evidence['id']}/extract",
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator"},
    )

    assert correct.status_code == HTTPStatus.OK, correct.text
    assert second.status_code == HTTPStatus.OK, second.text
    assert second.json()["raw_text"] == "second"
    assert second.json()["extracted_fields"] == {"attendance": False, "count": 1}
    assert second.json()["extracted_fields_corrected"] == {"attendance": True}


def test_extract_audit_uses_constants_payload(
    client: TestClient,
    app: FastAPI,
    governance_dsn: str,
) -> None:
    """AC2: extraction audit payload uses the compliance extract constant allowlist rather than raw request sprawl."""
    evidence = _seed_pending_evidence(client, app)
    set_ocr_provider(app, StaticOcrProvider())
    client.post(
        f"{EVIDENCE_URL}/{evidence['id']}/extract",
        headers={"X-Actor-Kind": "user", "X-Actor-Id": "operator"},
    )
    action = latest_action(governance_dsn, action_type="evidence_submission.extract")

    assert set(action["request_json"]) == {
        "attachment_ref",
        "rule_hint",
        "extraction_status",
        "raw_text_present",
    }
