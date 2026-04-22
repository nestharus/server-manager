from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CadenceKind = Literal["weekly", "monthly", "quarterly"]
ConsequenceKind = Literal["review", "under_review"]
ExtractionStatus = Literal["pending", "running", "completed", "failed", "corrected"]
EvaluationResult = Literal["compliant", "violation", "insufficient_evidence"]
ConsequenceApplied = Literal["none", "review_queued", "under_review_applied"]
ReviewStatus = Literal["pending", "approved", "overridden", "not_required"]


class _ComplianceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceRequirement(_ComplianceModel):
    type: str = Field(min_length=1)
    required: bool = True

    @field_validator("type")
    @classmethod
    def _validate_type(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("type must be non-blank")
        return stripped


class ComplianceRuleCreate(_ComplianceModel):
    chapter_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    cadence_kind: CadenceKind
    cadence_params: dict[str, Any] = Field(default_factory=dict)
    evaluation_window_days: int = Field(ge=1, le=365)
    evidence_requirements: list[EvidenceRequirement]
    consequence_kind: ConsequenceKind
    consequence_params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("chapter_id", "name")
    @classmethod
    def _validate_non_blank_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must be non-blank")
        return stripped


class ComplianceRuleUpdate(_ComplianceModel):
    name: str | None = Field(default=None, min_length=1)
    cadence_kind: CadenceKind | None = None
    cadence_params: dict[str, Any] | None = None
    evaluation_window_days: int | None = Field(default=None, ge=1, le=365)
    evidence_requirements: list[EvidenceRequirement] | None = None
    consequence_kind: ConsequenceKind | None = None
    consequence_params: dict[str, Any] | None = None
    active: bool | None = None

    @field_validator("name")
    @classmethod
    def _validate_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must be non-blank")
        return stripped


class ComplianceRuleRead(_ComplianceModel):
    id: UUID
    chapter_id: str
    name: str
    cadence_kind: CadenceKind
    cadence_params: dict[str, Any]
    evaluation_window_days: int
    evidence_requirements: list[EvidenceRequirement]
    consequence_kind: ConsequenceKind
    consequence_params: dict[str, Any]
    active: bool
    archived_at: datetime | None
    created_at: datetime
    version: int = Field(ge=1)


class EvidenceSubmissionCreate(_ComplianceModel):
    rule_id: UUID
    member_id: str = Field(min_length=1)
    chapter_id: str = Field(min_length=1)
    attachment_ref: str = Field(min_length=1)

    @field_validator("member_id", "chapter_id", "attachment_ref")
    @classmethod
    def _validate_submission_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must be non-blank")
        return stripped


class EvidenceSubmissionRead(_ComplianceModel):
    id: UUID
    rule_id: UUID
    member_id: str
    chapter_id: str
    attachment_ref: str
    raw_text: str | None
    extracted_fields: dict[str, Any] | None
    extracted_fields_corrected: dict[str, Any] | None
    extraction_status: ExtractionStatus
    extraction_confidence: Decimal | None
    extraction_error: str | None
    submitted_by_member_id: str
    submitted_at: datetime
    corrected_by_member_id: str | None
    corrected_at: datetime | None
    correction_reason: str | None
    version: int = Field(ge=1)


class ComplianceEvaluationRead(_ComplianceModel):
    id: UUID
    rule_id: UUID
    rule_version: int = Field(ge=1)
    chapter_id: str
    member_id: str
    period_start: date
    period_end: date
    result: EvaluationResult
    consequence_applied: ConsequenceApplied
    review_status: ReviewStatus
    reviewer_id: str | None
    review_reason: str | None
    reviewed_at: datetime | None
    evaluated_at: datetime
    evidence_ids: list[UUID]
    version: int = Field(ge=1)


class ComplianceEvaluationReviewRequest(_ComplianceModel):
    action: Literal["approve", "override"]
    override_result: EvaluationResult | None = None
    reviewer_reason: str = Field(min_length=1)

    @field_validator("reviewer_reason")
    @classmethod
    def _validate_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reviewer_reason must be non-blank")
        return stripped

    @model_validator(mode="after")
    def _validate_override_shape(self) -> "ComplianceEvaluationReviewRequest":
        if self.action == "override" and self.override_result is None:
            raise ValueError("override_result is required for override actions")
        return self


class ComplianceRuleNotFoundError(Exception):
    def __init__(self, rule_id: UUID) -> None:
        self.rule_id = rule_id
        super().__init__(f"compliance rule {rule_id} was not found")


class DuplicateActiveComplianceRuleError(Exception):
    def __init__(self, chapter_id: str, name: str) -> None:
        self.chapter_id = chapter_id
        self.name = name
        super().__init__(f"active compliance rule already exists for {chapter_id}/{name}")


class ComplianceRulePatchEmptyError(Exception):
    def __init__(self) -> None:
        super().__init__("compliance rule patch must change at least one field")


class EvidenceSubmissionNotFoundError(Exception):
    def __init__(self, evidence_id: UUID) -> None:
        self.evidence_id = evidence_id
        super().__init__(f"evidence submission {evidence_id} was not found")


class EvidenceChapterMismatchError(Exception):
    def __init__(
        self,
        *,
        rule_id: UUID,
        rule_chapter_id: str,
        request_chapter_id: str,
    ) -> None:
        self.rule_id = rule_id
        self.rule_chapter_id = rule_chapter_id
        self.request_chapter_id = request_chapter_id
        super().__init__(
            "evidence chapter must match the owning rule chapter"
        )


class ComplianceEvaluationNotFoundError(Exception):
    def __init__(self, evaluation_id: UUID) -> None:
        self.evaluation_id = evaluation_id
        super().__init__(f"compliance evaluation {evaluation_id} was not found")


class EvaluationReviewNotPermittedError(Exception):
    def __init__(self, *, evaluation_id: UUID, review_status: str, action: str) -> None:
        self.evaluation_id = evaluation_id
        self.review_status = review_status
        self.action = action
        super().__init__(
            f"evaluation {evaluation_id} cannot {action} from review_status {review_status}"
        )


__all__ = [
    "CadenceKind",
    "ComplianceEvaluationNotFoundError",
    "ComplianceEvaluationRead",
    "ComplianceEvaluationReviewRequest",
    "ComplianceRuleCreate",
    "ComplianceRuleNotFoundError",
    "ComplianceRulePatchEmptyError",
    "ComplianceRuleRead",
    "ComplianceRuleUpdate",
    "ConsequenceApplied",
    "ConsequenceKind",
    "DuplicateActiveComplianceRuleError",
    "EvaluationResult",
    "EvaluationReviewNotPermittedError",
    "EvidenceChapterMismatchError",
    "EvidenceRequirement",
    "EvidenceSubmissionCreate",
    "EvidenceSubmissionNotFoundError",
    "EvidenceSubmissionRead",
    "ExtractionStatus",
    "ReviewStatus",
]
