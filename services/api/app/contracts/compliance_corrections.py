from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator

from app.contracts.compliance import EvidenceSubmissionRead, _ComplianceModel


class OfficerCorrectionRequest(_ComplianceModel):
    corrected_fields: dict[str, Any] = Field(default_factory=dict)
    correction_reason: str = Field(min_length=1)

    @field_validator("correction_reason")
    @classmethod
    def _validate_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("correction_reason must be non-blank")
        return stripped


class OfficerCorrectionRead(EvidenceSubmissionRead):
    pass


class CorrectionNotPermittedStatusError(Exception):
    def __init__(self, *, evidence_id, extraction_status: str) -> None:
        self.evidence_id = evidence_id
        self.extraction_status = extraction_status
        super().__init__(
            f"evidence {evidence_id} cannot be corrected from status {extraction_status}"
        )


__all__ = [
    "CorrectionNotPermittedStatusError",
    "OfficerCorrectionRead",
    "OfficerCorrectionRequest",
]
