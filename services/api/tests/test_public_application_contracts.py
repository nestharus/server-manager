from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.contracts.applications import (
    PublicApplicationSubmission,
    PublicApplicationSubmissionReceipt,
)

from .public_intake_fixtures import assert_risk_annotation, public_application_payload


def test_public_application_submission_accepts_fixture_shape() -> None:
    """Risk annotation: group=TG-1; named_risk=public_contract_drift;
    level=unit; source=proposals/02-public-application-intake.md#§1 AS-1 AS-3.
    """
    assert_risk_annotation(
        group="TG-1",
        named_risk="public_contract_drift",
        level="unit",
        source="proposals/02-public-application-intake.md#§1",
    )

    submission = PublicApplicationSubmission.model_validate(
        public_application_payload(client_application_id="  browser-token-1  ")
    )

    assert submission.scope.scope_kind == "global"
    assert submission.scope.scope_id is None
    assert submission.responses == {
        "character_name": "Test Applicant",
        "application_text": "I want to join scheduled guild activities.",
    }
    assert submission.client_application_id == "browser-token-1"


@pytest.mark.parametrize(
    "invalid_payload",
    [
        {**public_application_payload(), "unexpected": True},
        {**public_application_payload(), "responses": {}},
        public_application_payload(client_application_id="   "),
    ],
)
def test_public_application_submission_rejects_drift_shapes(
    invalid_payload: dict,
) -> None:
    """Risk annotation: group=TG-1; named_risk=public_contract_drift;
    level=unit; source=proposals/02-public-application-intake.md#§1 AS-1 AS-3.
    """
    assert_risk_annotation(
        group="TG-1",
        named_risk="public_contract_drift",
        level="unit",
        source="proposals/02-public-application-intake.md#§1",
    )

    with pytest.raises(ValidationError):
        PublicApplicationSubmission.model_validate(invalid_payload)


def test_public_application_submission_receipt_is_minimal_envelope() -> None:
    """Risk annotation: group=TG-1; named_risk=public_contract_drift;
    level=unit; source=proposals/02-public-application-intake.md#§1.
    """
    assert_risk_annotation(
        group="TG-1",
        named_risk="public_contract_drift",
        level="unit",
        source="proposals/02-public-application-intake.md#§1",
    )
    application_id = uuid4()

    receipt = PublicApplicationSubmissionReceipt.model_validate(
        {"message": "Application received", "application_id": application_id}
    )

    dumped = receipt.model_dump()
    assert dumped == {
        "message": "Application received",
        "application_id": application_id,
    }
    assert isinstance(receipt.application_id, UUID)


@pytest.mark.parametrize("extra_key", ["applicant_id", "state", "version", "responses"])
def test_public_application_submission_receipt_rejects_application_read_fields(
    extra_key: str,
) -> None:
    """Risk annotation: group=TG-1; named_risk=public_contract_drift;
    level=unit; source=proposals/02-public-application-intake.md#§1.
    """
    assert_risk_annotation(
        group="TG-1",
        named_risk="public_contract_drift",
        level="unit",
        source="proposals/02-public-application-intake.md#§1",
    )
    payload = {
        "message": "Application received",
        "application_id": uuid4(),
        extra_key: "leaked",
    }

    with pytest.raises(ValidationError):
        PublicApplicationSubmissionReceipt.model_validate(payload)
