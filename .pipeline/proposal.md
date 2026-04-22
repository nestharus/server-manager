# SLICE-022 Phase 3 Proposal: Compliance Rule Evaluation With Evidence

## Binding sources

- `.pipeline/synthesis.md` — D1–D15 (binding).
- `.pipeline/research.md` — Phase 1 evidence.
- `product-strategy/tickets/SLICE-022.md` — AC1–AC4, WU grid, Code Boundary.
- `AGENTS.md` — Live Server Principle, No Backwards Compatibility,
  Test/Code Agent separation, migration discipline.

This proposal is bound to D1–D15. Mechanics may vary inside those
boundaries; scope and shape may not. Migration head advances
`wu_038 → wu_039 → wu_040a → wu_041a` (D12). Consequence vocabulary is
`"review"` / `"under_review"` — no `probation` enum or column (D1).

---

## §1 — AC mapping

### AC1 — Authority-gated compliance rule CRUD with OCC (WU-039)

1. **Migration** `migrations/versions/wu-039_compliance_rules.py` — creates
   `compliance_rules` per D2 (see §2).
2. **Contracts** `services/api/app/contracts/compliance.py`:
   `ComplianceRuleCreate`, `ComplianceRuleUpdate`, `ComplianceRuleRead`,
   plus error classes `ComplianceRuleNotFoundError`,
   `DuplicateActiveComplianceRuleError` (see §3).
3. **Repository** `services/api/app/repositories/compliance.py`:
   `create_rule`, `update_rule`, `list_rules_by_chapter`, `get_rule`,
   `_fetch_rule_for_update` (see §4).
4. **Service** `services/api/app/services/compliance.py`:
   `create_rule(db, request, *, actor)`,
   `update_rule(db, rule_id, request, expected_version, *, actor)`
   (see §5). Authority: `compliance_rule.write` at chapter scope.
   Mutations flow through `mutate_entity` with
   `aggregate_type="compliance_rule"` and constants from §9.
5. **Endpoints** `services/api/app/api/v1/endpoints/compliance/rules.py`:
   `POST /api/v1/compliance/rules`, `PATCH /api/v1/compliance/rules/{id}`,
   `GET /api/v1/compliance/rules`. If-Match strong ETag on PATCH; 412 on
   stale OCC (see §8).
6. **Tests** `services/api/tests/test_compliance_rules.py` per D14 (see §10).

### AC2 — Evidence submission persists pending, extraction is separate (WU-040A + WU-040B-extract)

1. **Migration** `migrations/versions/wu-040a_compliance_evidence.py` —
   creates `evidence_submissions` per D3 (see §2).
2. **Contracts** `services/api/app/contracts/compliance.py`
   (`EvidenceSubmissionCreate`, `EvidenceSubmissionRead`); separate
   `services/api/app/contracts/compliance_extraction.py`
   (`EvidenceExtractionRead`) per ticket Code Boundary.
3. **Repository** (`services/api/app/repositories/compliance.py`):
   `create_evidence`, `get_evidence`, `update_evidence_after_extraction`.
4. **Services**:
   - `services/api/app/services/compliance.py` adds
     `submit_evidence(db, request, *, actor)` — authority
     `compliance_evidence.submit`, inserts row with
     `extraction_status='pending'` (actor is spoof-proof via
     `ActorIdentity`; `submitted_by_member_id` is populated from
     `actor.actor_id`, never from the request body).
   - `services/api/app/services/compliance_extraction.py` adds
     `trigger_extraction(db, evidence_id, *, actor, ocr_provider)` —
     authority `compliance_evidence.extract`, synchronously invokes the
     OCR provider (D5), persists result or failure.
   - OCR boundary `services/api/app/infrastructure/ocr.py` (see §6).
5. **Endpoints**:
   - `services/api/app/api/v1/endpoints/compliance/evidence.py` —
     `POST /api/v1/compliance/evidence`,
     `GET /api/v1/compliance/evidence/{id}`.
   - `services/api/app/api/v1/endpoints/compliance/evidence_extract.py` —
     `POST /api/v1/compliance/evidence/{id}/extract`.
6. **Tests** `services/api/tests/test_compliance_evidence.py` and
   `services/api/tests/test_compliance_ocr_extract.py` per D14 (§10).

### AC3 — Officer correction preserves originals with OCC (WU-040B-correct)

1. **Contracts** `services/api/app/contracts/compliance_corrections.py`:
   `OfficerCorrectionRequest`, `OfficerCorrectionRead`,
   `CorrectionNotPermittedStatusError` (see §3).
2. **Repository** (`services/api/app/repositories/compliance.py`):
   `update_evidence_correction` — writes overlay columns only; never
   touches `raw_text` or `attachment_ref`.
3. **Service** `services/api/app/services/compliance_corrections.py`:
   `correct_evidence(db, evidence_id, request, expected_version, *, actor)`
   — authority `compliance_evidence.correct`, guards
   `extraction_status IN ('completed','failed','corrected')` (409
   otherwise), OCC via `mutate_entity`, sets `extracted_fields_corrected`,
   `corrected_by_member_id = actor.actor_id` (spoof-proof),
   `corrected_at`, `correction_reason`, transitions status to
   `'corrected'` (see §5).
4. **Endpoint**
   `services/api/app/api/v1/endpoints/compliance/evidence_correct.py`:
   `POST /api/v1/compliance/evidence/{id}/correct`. If-Match required;
   412 on stale; 409 on `pending`/`running`; 422 on blank reason.
5. **Tests** `services/api/tests/test_compliance_ocr_correct.py` per D14.

### AC4 — Scheduled evaluation is idempotent; consequences route through roster (WU-041A + WU-041B)

1. **Migration** `migrations/versions/wu-041a_compliance_evaluations.py` —
   creates `compliance_evaluations` per D7 and seeds the
   `compliance-evaluator` service actor grant per D11 (see §2).
2. **Contracts** (`services/api/app/contracts/compliance.py`):
   `ComplianceEvaluationRead`, `ComplianceEvaluationReviewRequest`, plus
   error classes (see §3).
3. **Repository**:
   `create_evaluation` (with `ON CONFLICT DO NOTHING`),
   `get_evaluation`, `list_evaluations_by_rule_period`,
   `update_evaluation_review`.
4. **Services**:
   - `services/api/app/services/compliance_review.py`:
     `get_evaluation(db, evaluation_id, *, actor)` (authority
     `compliance_evaluation.read`),
     `review_evaluation(db, evaluation_id, request, expected_version,
     *, actor)` (authority `compliance_evaluation.review`, OCC).
   - `services/api/app/services/compliance.py`:
     `run_scheduled_compliance_evaluations(db, *, now, batch_size)` —
     enumerates active rules across chapters, computes periods (D9),
     inserts idempotent rows, evaluates on insert only, dispatches
     consequences through the roster service (D10).
5. **Worker** `services/api/app/tasks/compliance.py` wires
   `compliance_evaluation_worker_tick` with root audit context per
   SLICE-020 R2 (see §7).
6. **Endpoints**
   `services/api/app/api/v1/endpoints/compliance/evaluations.py`:
   `GET /api/v1/compliance/evaluations/{id}`,
   `POST /api/v1/compliance/evaluations/{id}/review`. Manual trigger
   `POST /api/v1/compliance/evaluations/run` lives in
   `services/api/app/api/v1/endpoints/compliance/evaluations_run.py`.
   Authority: the endpoint checks `compliance_evaluation.review`
   against the operator — the manual trigger is an operator surface,
   not an internal-substrate write (D11: `.write` is internal-only).
   Internal mutations executed by the invoked service use the
   `compliance-evaluator` service actor's `.write` grant. Operator
   attribution is preserved by threading the operator actor as
   `originating_actor` on the roster transition call (§5 / R4);
   audit trail records both (correlation_id shared between
   `compliance_evaluation.create` and `roster_entry.transition`).
   Intended for operator backfill / smoke tests.
7. **Tests** `services/api/tests/test_compliance_review_api.py` and
   `services/api/tests/test_compliance_evaluation_worker.py` per D14.

---

## §2 — Migration plan

Chain (D12, linear off `wu_038`):

```
wu_038_permission_intent_expiry
  → wu_039_compliance_rules
    → wu_040a_compliance_evidence
      → wu_041a_compliance_evaluations
```

File naming mirrors shipped convention: dashed filename, underscored
`revision` identifier (e.g., filename
`migrations/versions/wu-039_compliance_rules.py`, revision
`"wu_039_compliance_rules"`). Each downgrade is a `pass` no-op per the
Live Server Principle (matches `wu-038_permission_intent_expiry.py:76–79`).

### `wu-039_compliance_rules.py` — WU-039

```sql
CREATE TABLE compliance_rules (
    id UUID PRIMARY KEY,
    chapter_id TEXT NOT NULL,
    name TEXT NOT NULL,
    cadence_kind TEXT NOT NULL,
    cadence_params JSONB NOT NULL DEFAULT '{}'::jsonb,
    evaluation_window_days INTEGER NOT NULL,
    evidence_requirements JSONB NOT NULL,
    consequence_kind TEXT NOT NULL,
    consequence_params JSONB NOT NULL DEFAULT '{}'::jsonb,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    archived_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT compliance_rules_cadence_kind_valid
        CHECK (cadence_kind IN ('weekly','monthly','quarterly')),
    CONSTRAINT compliance_rules_consequence_kind_valid
        CHECK (consequence_kind IN ('review','under_review')),
    CONSTRAINT compliance_rules_evaluation_window_positive
        CHECK (evaluation_window_days > 0 AND evaluation_window_days <= 365),
    CONSTRAINT compliance_rules_evidence_requirements_is_array
        CHECK (jsonb_typeof(evidence_requirements) = 'array')
);

CREATE UNIQUE INDEX ux_compliance_rules__chapter_active_name
    ON compliance_rules (chapter_id, name)
    WHERE archived_at IS NULL;

CREATE INDEX ix_compliance_rules__chapter_active
    ON compliance_rules (chapter_id)
    WHERE active = TRUE AND archived_at IS NULL;
```

Versioning lives in `aggregate_heads` per D2; no dedicated `version`
column.

### `wu-040a_compliance_evidence.py` — WU-040A

```sql
CREATE TABLE evidence_submissions (
    id UUID PRIMARY KEY,
    rule_id UUID NOT NULL REFERENCES compliance_rules(id),
    member_id TEXT NOT NULL,
    chapter_id TEXT NOT NULL,
    attachment_ref TEXT NOT NULL,
    raw_text TEXT NULL,
    extracted_fields JSONB NULL,
    extracted_fields_corrected JSONB NULL,
    extraction_status TEXT NOT NULL,
    extraction_confidence NUMERIC(5,4) NULL,
    extraction_error TEXT NULL,
    submitted_by_member_id TEXT NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    corrected_by_member_id TEXT NULL,
    corrected_at TIMESTAMPTZ NULL,
    correction_reason TEXT NULL,
    CONSTRAINT evidence_submissions_attachment_ref_non_blank
        CHECK (char_length(attachment_ref) > 0),
    CONSTRAINT evidence_submissions_extraction_status_valid
        CHECK (extraction_status IN
            ('pending','running','completed','failed','corrected')),
    CONSTRAINT evidence_submissions_confidence_bounded
        CHECK (extraction_confidence IS NULL
               OR (extraction_confidence >= 0 AND extraction_confidence <= 1)),
    CONSTRAINT evidence_submissions_completed_requires_ocr
        CHECK (extraction_status <> 'completed'
               OR (raw_text IS NOT NULL AND extracted_fields IS NOT NULL)),
    CONSTRAINT evidence_submissions_failed_requires_error
        CHECK (extraction_status <> 'failed'
               OR extraction_error IS NOT NULL),
    CONSTRAINT evidence_submissions_corrected_requires_overlay
        CHECK (extraction_status <> 'corrected'
               OR (extracted_fields_corrected IS NOT NULL
                   AND corrected_by_member_id IS NOT NULL
                   AND correction_reason IS NOT NULL))
);

CREATE INDEX ix_evidence_submissions__rule_member
    ON evidence_submissions (rule_id, member_id, submitted_at DESC);

CREATE INDEX ix_evidence_submissions__chapter_period
    ON evidence_submissions (chapter_id, submitted_at);
```

### `wu-041a_compliance_evaluations.py` — WU-041A

```sql
CREATE TABLE compliance_evaluations (
    id UUID PRIMARY KEY,
    rule_id UUID NOT NULL REFERENCES compliance_rules(id),
    rule_version BIGINT NOT NULL,
    chapter_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    result TEXT NOT NULL,
    consequence_applied TEXT NOT NULL,
    review_status TEXT NOT NULL,
    reviewer_id TEXT NULL,
    review_reason TEXT NULL,
    reviewed_at TIMESTAMPTZ NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    CONSTRAINT compliance_evaluations_result_valid
        CHECK (result IN ('compliant','violation','insufficient_evidence')),
    CONSTRAINT compliance_evaluations_consequence_valid
        CHECK (consequence_applied IN
            ('none','review_queued','under_review_applied')),
    CONSTRAINT compliance_evaluations_review_status_valid
        CHECK (review_status IN
            ('pending','approved','overridden','not_required')),
    CONSTRAINT compliance_evaluations_period_ordered
        CHECK (period_end >= period_start),
    CONSTRAINT compliance_evaluations_rule_version_positive
        CHECK (rule_version >= 1)
);

CREATE UNIQUE INDEX ux_compliance_evaluations__member_rule_period
    ON compliance_evaluations (member_id, rule_id, period_start, period_end);

CREATE INDEX ix_compliance_evaluations__rule_period
    ON compliance_evaluations (rule_id, period_start);

CREATE INDEX ix_compliance_evaluations__review_pending
    ON compliance_evaluations (chapter_id, evaluated_at DESC)
    WHERE review_status = 'pending';
```

**Service-actor seed** (same migration, mirrors
`wu-038_permission_intent_expiry.py:36–73`):

```python
_EVALUATOR_PERMISSIONS = (
    '["compliance_rule.read",'
    '"compliance_evaluation.write",'
    '"roster.transition"]'
)

op.execute(
    f"""
    INSERT INTO authority_grants (
        id, grantee_id, scope_kind, scope_id, permissions,
        expires_at, revoked_at, revoked_by, revocation_reason,
        predecessor_grant_id
    )
    SELECT
        gen_random_uuid(),
        'compliance-evaluator',
        'global',
        NULL,
        '{_EVALUATOR_PERMISSIONS}'::jsonb,
        NULL, NULL, NULL, NULL, NULL
    WHERE NOT EXISTS (
        SELECT 1
        FROM authority_grants
        WHERE grantee_id = 'compliance-evaluator'
          AND scope_kind = 'global'
          AND scope_id IS NULL
          AND permissions @> '{_EVALUATOR_PERMISSIONS}'::jsonb
          AND permissions <@ '{_EVALUATOR_PERMISSIONS}'::jsonb
          AND revoked_at IS NULL
          AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
    )
    """
)
```

---

## §3 — Contracts

### `services/api/app/contracts/compliance.py` (new)

```python
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


CadenceKind = Literal["weekly", "monthly", "quarterly"]
ConsequenceKind = Literal["review", "under_review"]
ExtractionStatus = Literal[
    "pending", "running", "completed", "failed", "corrected"
]
EvaluationResult = Literal[
    "compliant", "violation", "insufficient_evidence"
]
ConsequenceApplied = Literal[
    "none", "review_queued", "under_review_applied"
]
ReviewStatus = Literal["pending", "approved", "overridden", "not_required"]


class _ComplianceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceRequirement(_ComplianceModel):
    type: str = Field(min_length=1)
    required: bool = True


class ComplianceRuleCreate(_ComplianceModel):
    chapter_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    cadence_kind: CadenceKind
    cadence_params: dict[str, Any] = Field(default_factory=dict)
    evaluation_window_days: int = Field(ge=1, le=365)
    evidence_requirements: list[EvidenceRequirement]
    consequence_kind: ConsequenceKind
    consequence_params: dict[str, Any] = Field(default_factory=dict)


class ComplianceRuleUpdate(_ComplianceModel):
    name: str | None = Field(default=None, min_length=1)
    cadence_kind: CadenceKind | None = None
    cadence_params: dict[str, Any] | None = None
    evaluation_window_days: int | None = Field(default=None, ge=1, le=365)
    evidence_requirements: list[EvidenceRequirement] | None = None
    consequence_kind: ConsequenceKind | None = None
    consequence_params: dict[str, Any] | None = None
    active: bool | None = None


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


# Constants-only audit dispatch (D13)

COMPLIANCE_RULE_CREATE_ACTION_TYPE = "compliance_rule.create"
COMPLIANCE_RULE_CREATE_CHANGE_TYPE = "compliance_rule.created"
COMPLIANCE_RULE_UPDATE_ACTION_TYPE = "compliance_rule.update"
COMPLIANCE_RULE_UPDATE_CHANGE_TYPE = "compliance_rule.updated"
COMPLIANCE_RULE_ARCHIVE_ACTION_TYPE = "compliance_rule.archive"
COMPLIANCE_RULE_ARCHIVE_CHANGE_TYPE = "compliance_rule.archived"

EVIDENCE_SUBMIT_ACTION_TYPE = "evidence_submission.submit"
EVIDENCE_SUBMIT_CHANGE_TYPE = "evidence_submission.submitted"
EVIDENCE_EXTRACT_ACTION_TYPE = "evidence_submission.extract"
EVIDENCE_EXTRACT_CHANGE_TYPE = "evidence_submission.extracted"
EVIDENCE_EXTRACTION_FAILED_CHANGE_TYPE = "evidence_submission.extraction_failed"
EVIDENCE_CORRECT_ACTION_TYPE = "evidence_submission.correct"
EVIDENCE_CORRECT_CHANGE_TYPE = "evidence_submission.corrected"

COMPLIANCE_EVALUATION_CREATE_ACTION_TYPE = "compliance_evaluation.create"
COMPLIANCE_EVALUATION_CREATE_CHANGE_TYPE = "compliance_evaluation.created"
COMPLIANCE_EVALUATION_REVIEW_ACTION_TYPE = "compliance_evaluation.review"
COMPLIANCE_EVALUATION_REVIEW_CHANGE_TYPE = "compliance_evaluation.reviewed"
COMPLIANCE_EVALUATION_OVERRIDE_ACTION_TYPE = "compliance_evaluation.override"
COMPLIANCE_EVALUATION_OVERRIDE_CHANGE_TYPE = "compliance_evaluation.overridden"
# Note (Revision 1, R3): no standalone `compliance_evaluation.consequence_applied`
# change_type — `consequence_applied` is an attribute of the evaluation,
# written inside the CREATE action's `mutate_projection` and captured in
# the CREATE state change's `payload_json`. The roster transition lives
# on its own audit chain (`roster_entry.transition`), threaded via
# correlation_id.

# Narrow payload allowlists per action
COMPLIANCE_RULE_CREATE_PAYLOAD_ALLOWLIST: frozenset[str] = frozenset({
    "chapter_id", "name", "cadence_kind", "cadence_params",
    "evaluation_window_days", "evidence_requirements",
    "consequence_kind", "consequence_params",
})
COMPLIANCE_RULE_UPDATE_PAYLOAD_ALLOWLIST: frozenset[str] = frozenset({
    "name", "cadence_kind", "cadence_params", "evaluation_window_days",
    "evidence_requirements", "consequence_kind", "consequence_params",
    "active",
})
EVIDENCE_SUBMIT_PAYLOAD_ALLOWLIST: frozenset[str] = frozenset({
    "rule_id", "member_id", "chapter_id", "attachment_ref",
    "submitted_by_member_id",
})
EVIDENCE_EXTRACT_PAYLOAD_ALLOWLIST: frozenset[str] = frozenset({
    "extraction_status", "extraction_confidence",
    "extraction_error", "raw_text_present",
})
EVIDENCE_CORRECT_PAYLOAD_ALLOWLIST: frozenset[str] = frozenset({
    "corrected_fields", "correction_reason", "corrected_by_member_id",
})
COMPLIANCE_EVALUATION_CREATE_PAYLOAD_ALLOWLIST: frozenset[str] = frozenset({
    "rule_id", "rule_version", "chapter_id", "member_id",
    "period_start", "period_end", "result", "consequence_applied",
    "evidence_ids",
})
COMPLIANCE_EVALUATION_REVIEW_PAYLOAD_ALLOWLIST: frozenset[str] = frozenset({
    "action", "override_result", "reviewer_reason",
})
# Revision 2 (R8 / audit L2): dedicated override allowlist so the override
# action dispatches with its own named allowlist rather than reusing the
# review one implicitly. Fields cover the evaluation target, the override
# result, and the reviewer justification.
COMPLIANCE_EVALUATION_OVERRIDE_PAYLOAD_ALLOWLIST: frozenset[str] = frozenset({
    "evaluation_id", "override_result", "reviewer_reason",
})


# Errors
class ComplianceRuleNotFoundError(Exception):
    def __init__(self, rule_id: UUID) -> None:
        self.rule_id = rule_id
        super().__init__(f"compliance rule {rule_id} was not found")


class DuplicateActiveComplianceRuleError(Exception):
    def __init__(self, chapter_id: str, name: str) -> None:
        self.chapter_id = chapter_id
        self.name = name
        super().__init__(
            f"compliance rule {name!r} already active in chapter {chapter_id}"
        )


class EvidenceSubmissionNotFoundError(Exception):
    def __init__(self, evidence_id: UUID) -> None:
        self.evidence_id = evidence_id
        super().__init__(f"evidence submission {evidence_id} was not found")


class ComplianceEvaluationNotFoundError(Exception):
    def __init__(self, evaluation_id: UUID) -> None:
        self.evaluation_id = evaluation_id
        super().__init__(
            f"compliance evaluation {evaluation_id} was not found"
        )


class InvalidEvaluationReviewActionError(Exception):
    """`override` requested without `override_result` (422)."""


class EvidenceChapterMismatchError(Exception):
    """Raised when submit_evidence's request.chapter_id does not match the
    rule's chapter_id (422). Authorization is always derived from the
    rule; this error exists so the caller discovers an inconsistent
    request rather than silently accepting the rule's chapter."""

    def __init__(
        self, *, rule_id: UUID, rule_chapter_id: str, request_chapter_id: str
    ) -> None:
        self.rule_id = rule_id
        self.rule_chapter_id = rule_chapter_id
        self.request_chapter_id = request_chapter_id
        super().__init__(
            f"request.chapter_id {request_chapter_id!r} does not match "
            f"rule {rule_id} chapter_id {rule_chapter_id!r}"
        )


class OcrProviderNotConfiguredError(Exception):
    """Raised by the stub provider; mapped to 503 in the endpoint layer."""
```

### `services/api/app/contracts/compliance_corrections.py` (new)

```python
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class _CorrectionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OfficerCorrectionRequest(_CorrectionModel):
    corrected_fields: dict[str, Any]
    correction_reason: str = Field(min_length=1)


class OfficerCorrectionRead(_CorrectionModel):
    evidence_id: UUID
    corrected_fields: dict[str, Any]
    corrected_by_member_id: str
    corrected_at: datetime
    correction_reason: str
    version: int = Field(ge=1)


class CorrectionNotPermittedStatusError(Exception):
    """Raised when correction is attempted in `pending` or `running` (409)."""

    def __init__(self, evidence_id: UUID, status: str) -> None:
        self.evidence_id = evidence_id
        self.status = status
        super().__init__(
            f"correction not permitted while evidence {evidence_id} "
            f"is in status {status!r}"
        )
```

### `services/api/app/contracts/compliance_extraction.py` (new)

```python
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class _ExtractionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceExtractionRead(_ExtractionModel):
    evidence_id: UUID
    extraction_status: str
    raw_text: str | None
    extracted_fields: dict[str, Any] | None
    extraction_confidence: Decimal | None
    extraction_error: str | None
    extraction_completed_at: datetime
    version: int
```

---

## §4 — Repository layer

### `services/api/app/repositories/compliance.py` (new)

All functions are thin SQL wrappers returning typed rows/dicts. No
business logic. All mutations go through `mutate_entity`; repository
helpers only run DML inside the projection callback.

```python
def create_rule(
    connection: Connection[Any], *, row: dict[str, Any]
) -> dict[str, Any]: ...

def update_rule(
    connection: Connection[Any], *, rule_id: UUID, updates: dict[str, Any]
) -> dict[str, Any]: ...

def _fetch_rule_for_update(
    connection: Connection[Any], rule_id: UUID
) -> dict[str, Any] | None: ...

def get_rule(
    connection: Connection[Any], rule_id: UUID
) -> dict[str, Any] | None: ...

def list_rules_by_chapter(
    connection: Connection[Any], chapter_id: str, *, active_only: bool
) -> list[dict[str, Any]]: ...

def list_active_rules(
    connection: Connection[Any]
) -> list[dict[str, Any]]: ...

def create_evidence(
    connection: Connection[Any], *, row: dict[str, Any]
) -> dict[str, Any]: ...

def get_evidence(
    connection: Connection[Any], evidence_id: UUID
) -> dict[str, Any] | None: ...

def _fetch_evidence_for_update(
    connection: Connection[Any], evidence_id: UUID
) -> dict[str, Any] | None: ...

def update_evidence_after_extraction(
    connection: Connection[Any], *, evidence_id: UUID,
    extraction_status: str, raw_text: str | None,
    extracted_fields: dict[str, Any] | None,
    extraction_confidence: Decimal | None,
    extraction_error: str | None,
) -> dict[str, Any]: ...

def update_evidence_correction(
    connection: Connection[Any], *, evidence_id: UUID,
    corrected_fields: dict[str, Any],
    corrected_by_member_id: str,
    correction_reason: str,
) -> dict[str, Any]:
    """UPDATE sets overlay + status='corrected'; never touches
    `raw_text`, `attachment_ref`, or `extracted_fields` (D3/AC3)."""

def list_evidence_for_rule_period(
    connection: Connection[Any], *, rule_id: UUID,
    period_start: date, period_end: date,
    member_id: str | None = None,
) -> list[dict[str, Any]]: ...

def insert_evaluation_if_absent(
    connection: Connection[Any], *, row: dict[str, Any]
) -> dict[str, Any] | None:
    """`INSERT ... ON CONFLICT (member_id, rule_id, period_start,
    period_end) DO NOTHING RETURNING *`. Returns the inserted row or
    None if a prior tick already created it (AC4 idempotency; mirrors
    `repositories/ticket_sla.py:135–136`).

    **Revision 1 (R2):** invoked only from inside
    `_evaluate_member_rule`'s `mutate_projection` callback — never as a
    naked DML step outside a `mutate_entity` call. The connection passed
    in is the one `mutate_entity` opened for the per-member transaction;
    if the audit projection raises, the ON CONFLICT insert rolls back
    atomically so the next tick can retry cleanly."""

def get_evaluation(
    connection: Connection[Any], evaluation_id: UUID
) -> dict[str, Any] | None: ...

def _fetch_evaluation_for_update(
    connection: Connection[Any], evaluation_id: UUID
) -> dict[str, Any] | None: ...

def update_evaluation_review(
    connection: Connection[Any], *, evaluation_id: UUID,
    review_status: str, reviewer_id: str,
    review_reason: str, result: str | None,
    consequence_applied: str | None,
) -> dict[str, Any]: ...
```

**Revision 1 (R3):** `mark_consequence_applied` is intentionally absent.
Consequence is recorded as an attribute of the evaluation in the CREATE
action's `mutate_projection` — no second repository helper, no second
mutation, no orphan change_type.

### Roster member enumeration + per-member entry read

`run_scheduled_compliance_evaluations` enumerates chapter members via
the existing roster repository (research §5, §6); a single new helper
`list_active_members_by_chapter(connection, chapter_id)` is added to
`services/api/app/repositories/roster.py` returning
`roster_entries` rows where `status = 'active'`. No new table is
introduced (D1/D15); there is no `chapter_members` relation.

**Revision 1 (R6)** — `_evaluate_member_rule` additionally calls the
shipped roster read helper `get_roster_entry(connection, *,
chapter_id, member_id)` (already in
`services/api/app/repositories/roster.py`; add the helper if not
present, returning `roster_entries` row + its `aggregate_heads`
version). The returned `id` and `version` drive the
`transition_roster_entry(..., entry_id=..., expected_version=...)`
call so OCC is explicit — no stale-version assumption. Also exposes
a service-layer alias `roster_service.get_roster_entry` if
compliance needs a service-contract view (used by the worker only,
SELECT-only, no authority check required — matches the repository
access pattern used by other workers).

---

## §5 — Service layer

All service functions take `actor: ActorIdentity` and perform an
authority check before any mutation (D11). Mutations flow through
`mutate_entity` (`services/api/app/services/mutations.py:58`) with the
constants from §9; payload allowlists are narrow per action. Originating
actor is derived from `actor.actor_id` / `actor.actor_kind` and never
from the request body.

**Revision 2 — Roster service signature extensions (backward-compatible):**
`services/api/app/services/roster.py::transition_roster_entry` and
`get_roster_entry` accept an optional `connection=` kwarg to support
caller-managed transactions. Omitting it preserves today's behaviour
(open a fresh tx); supplying it runs the roster work on the caller's
connection so the roster write commits or rolls back with the caller's
outer `mutate_entity`. Mirrors SLICE-020 R1's extension of
`grant_authority` / `revoke_authority`.

### Roster service signature extension (Revision 2 — R7)

`_evaluate_member_rule` (§5) threads its per-member `mutate_entity`
connection into `transition_roster_entry(..., connection=conn)` so the
evaluation insert and the roster transition commit atomically. The
shipped `transition_roster_entry` in
`services/api/app/services/roster.py:186-192` does **not** currently
accept a `connection=` kwarg; its internal `mutate_entity` call opens
its own `db.transaction()`. Without the extension, the
`transition_roster_entry(..., connection=conn)` call in §5 raises
`TypeError` at import time, and the atomicity guarantee R2 was built
to deliver collapses (evaluation + roster transition commit in
separate transactions; a crash between them leaves a
`consequence_applied='under_review_applied'` evaluation with no
matching `roster_entries.status='under_review'`).

Change — `services/api/app/services/roster.py`:

1. Extend `transition_roster_entry(db, entry_id, request, actor, *,
   expected_version, connection: Connection[Any] | None = None)` — add
   an optional `connection` kwarg. When provided, pass it through to
   the internal `mutate_entity(..., connection=connection)` call so the
   roster write runs on the caller's transaction. When `None`, open a
   fresh tx as today.
2. Extend `get_roster_entry(db, *, chapter_id, member_id,
   connection: Connection[Any] | None = None)` with the same shape —
   reading on the same connection the caller will write on ensures a
   consistent snapshot of `(id, version)` when the caller needs
   read-then-write inside one tx. Lookup-only callers (today's usage)
   keep the default `None` path and open their own read connection.
3. The signature is append-only and defaults to `None`, so every
   existing caller continues to work unchanged (no backwards-compat
   shim; the kwarg is genuinely optional per AGENTS.md).
4. Pattern precedent: SLICE-020 R1 extended `grant_authority` /
   `revoke_authority` with the same optional-`connection=` shape so
   the permission-intent worker could share a tx with its audit
   projection. R7 applies the same shape to roster for the same
   reason.

`services/api/app/services/mutations.py:70` already accepts
`connection=` on `mutate_entity`, so the threading is mechanical —
the extension is purely adding the kwarg to the roster service layer
and routing it into the existing `mutate_entity` call.

Test (in `services/api/tests/test_roster.py`, the roster service's
own test home, not a SLICE-022 file — so the signature change is
testable where it lives):

- `test_transition_roster_entry_accepts_shared_connection` — opens
  a caller-managed `db.transaction()`, invokes
  `transition_roster_entry(..., connection=conn)`, and asserts (a)
  the roster row + its audit projection are visible inside the same
  tx before commit, and (b) a rollback on the caller's connection
  rolls back the roster transition atomically (both commit or both
  roll back — no partial state). This verifies the shared-connection
  tx behavior rather than the signature alone.


### `services/api/app/services/compliance.py` (new)

```python
def create_rule(
    db: PostgresDatabase, request: ComplianceRuleCreate, *,
    actor: ActorIdentity,
) -> ComplianceRuleRead:
    _require_scoped_authority(
        "compliance_rule.write",
        scope_kind="chapter", scope_id=request.chapter_id,
        actor=actor, db=db,
    )
    rule_id = uuid4()

    def mutate_projection(conn: Connection[Any]) -> StateChangeDraft:
        try:
            row = create_rule_row(
                conn,
                row={
                    "id": rule_id,
                    "chapter_id": request.chapter_id,
                    "name": request.name,
                    "cadence_kind": request.cadence_kind,
                    "cadence_params": request.cadence_params,
                    "evaluation_window_days": request.evaluation_window_days,
                    "evidence_requirements":
                        [r.model_dump() for r in request.evidence_requirements],
                    "consequence_kind": request.consequence_kind,
                    "consequence_params": request.consequence_params,
                },
            )
        except errors.UniqueViolation as err:
            raise DuplicateActiveComplianceRuleError(
                request.chapter_id, request.name
            ) from err
        return StateChangeDraft(
            change_type=COMPLIANCE_RULE_CREATE_CHANGE_TYPE,
            payload_json={"rule_id": str(rule_id), ...},
            diff_json={},
        )

    result = mutate_entity(
        db=db,
        aggregate_type="compliance_rule",
        aggregate_id=str(rule_id),
        request=_make_request(
            expected_version=0, actor=actor,
            request_surface="api:/api/v1/compliance/rules",
        ),
        action_type=COMPLIANCE_RULE_CREATE_ACTION_TYPE,
        action_payload=request.model_dump(mode="json"),
        payload_allowlist=set(COMPLIANCE_RULE_CREATE_PAYLOAD_ALLOWLIST),
        mutate_projection=mutate_projection,
        scope_kind="chapter", scope_id=request.chapter_id,
    )
    return _rule_read_from_result(result)


def update_rule(
    db: PostgresDatabase, rule_id: UUID,
    request: ComplianceRuleUpdate, expected_version: int,
    *, actor: ActorIdentity,
) -> ComplianceRuleRead: ...
    # authority `compliance_rule.write` (chapter scope via loaded row);
    # mutate_entity with aggregate_type="compliance_rule",
    # COMPLIANCE_RULE_UPDATE_*; If-Match → expected_version drives OCC.


def submit_evidence(
    db: PostgresDatabase, request: EvidenceSubmissionCreate,
    *, actor: ActorIdentity,
) -> EvidenceSubmissionRead:
    # Revision 1 (R1): authorize against the rule's chapter, not the
    # request's chapter. The rule is the source of truth for scope; the
    # request's chapter_id is cross-checked and a mismatch returns 422.
    # Pattern applies to any endpoint that takes both `rule_id` and
    # `chapter_id`.
    with db.connection() as conn:
        rule = get_rule(conn, request.rule_id)
    if rule is None:
        raise ComplianceRuleNotFoundError(request.rule_id)
    if request.chapter_id != rule["chapter_id"]:
        raise EvidenceChapterMismatchError(
            rule_id=request.rule_id,
            rule_chapter_id=rule["chapter_id"],
            request_chapter_id=request.chapter_id,
        )

    _require_scoped_authority(
        "compliance_evidence.submit",
        scope_kind="chapter", scope_id=rule["chapter_id"],
        actor=actor, db=db,
    )
    # FK-validate rule_id; inserts with extraction_status='pending',
    # chapter_id=rule["chapter_id"] (derived, spoof-proof),
    # submitted_by_member_id=actor.actor_id (spoof-proof).
```

### `services/api/app/services/compliance_corrections.py` (new)

```python
def correct_evidence(
    db: PostgresDatabase, evidence_id: UUID,
    request: OfficerCorrectionRequest, expected_version: int,
    *, actor: ActorIdentity,
) -> OfficerCorrectionRead:
    with db.connection() as conn:
        current = get_evidence(conn, evidence_id)
    if current is None:
        raise EvidenceSubmissionNotFoundError(evidence_id)

    _require_scoped_authority(
        "compliance_evidence.correct",
        scope_kind="chapter", scope_id=current["chapter_id"],
        actor=actor, db=db,
    )

    if current["extraction_status"] in ("pending", "running"):
        raise CorrectionNotPermittedStatusError(
            evidence_id, current["extraction_status"]
        )

    def mutate_projection(conn: Connection[Any]) -> StateChangeDraft:
        row = _fetch_evidence_for_update(conn, evidence_id)
        if row is None:
            raise EvidenceSubmissionNotFoundError(evidence_id)
        if row["extraction_status"] in ("pending", "running"):
            raise CorrectionNotPermittedStatusError(
                evidence_id, row["extraction_status"]
            )
        update_evidence_correction(
            conn,
            evidence_id=evidence_id,
            corrected_fields=request.corrected_fields,
            corrected_by_member_id=actor.actor_id,
            correction_reason=request.correction_reason,
        )
        return StateChangeDraft(
            change_type=EVIDENCE_CORRECT_CHANGE_TYPE,
            payload_json={
                "evidence_id": str(evidence_id),
                "corrected_fields": request.corrected_fields,
                "corrected_by_member_id": actor.actor_id,
                "correction_reason": request.correction_reason,
            },
            # Revision 1 (R5): `extracted_fields_corrected` diff captures
            # the prior overlay (None on the first correction) and the new
            # overlay, so a second-correction row is self-describing
            # without walking backward across rows. `extracted_fields` is
            # the immutable OCR baseline — included for completeness so an
            # auditor inspecting a single state-change row sees
            # (baseline, prior overlay, new overlay) in one place.
            diff_json={
                "extraction_status": {
                    "old": row["extraction_status"], "new": "corrected",
                },
                "extracted_fields": row["extracted_fields"],
                "extracted_fields_corrected": {
                    "old": row["extracted_fields_corrected"],
                    "new": request.corrected_fields,
                },
            },
        )

    result = mutate_entity(
        db=db,
        aggregate_type="evidence_submission",
        aggregate_id=str(evidence_id),
        request=_make_request(
            expected_version=expected_version, actor=actor,
            request_surface=(
                f"api:/api/v1/compliance/evidence/{evidence_id}/correct"
            ),
            reason_text=request.correction_reason,
        ),
        action_type=EVIDENCE_CORRECT_ACTION_TYPE,
        action_payload={
            "corrected_fields": request.corrected_fields,
            "correction_reason": request.correction_reason,
            "corrected_by_member_id": actor.actor_id,
        },
        payload_allowlist=set(EVIDENCE_CORRECT_PAYLOAD_ALLOWLIST),
        mutate_projection=mutate_projection,
        scope_kind="chapter", scope_id=current["chapter_id"],
    )
    return _correction_read_from_result(result)
```

Raw text + attachment ref are never touched by this path (AC3 / D6).

### `services/api/app/services/compliance_extraction.py` (new)

Thin wrapper orchestrating OCR provider + persistence. The service
opens a single `db.transaction()` and runs provider invocation inside
a coroutine bridge:

```python
def trigger_extraction(
    db: PostgresDatabase, evidence_id: UUID,
    *, actor: ActorIdentity,
    ocr_provider: OcrProvider,
) -> EvidenceExtractionRead:
    with db.connection() as conn:
        current = get_evidence(conn, evidence_id)
    if current is None:
        raise EvidenceSubmissionNotFoundError(evidence_id)

    _require_scoped_authority(
        "compliance_evidence.extract",
        scope_kind="chapter", scope_id=current["chapter_id"],
        actor=actor, db=db,
    )

    # Run provider OUTSIDE the transaction so a slow OCR call doesn't
    # hold row locks. Persisting the result is OCC-safe via
    # mutate_entity (extraction is idempotent — repeated calls
    # overwrite with the latest provider result).
    try:
        extraction = asyncio.run(
            ocr_provider.extract(
                attachment_ref=current["attachment_ref"],
                rule_hint=None,
            )
        )
    except OcrProviderNotConfiguredError:
        raise  # bubbles to endpoint → 503
    except Exception as err:
        return _persist_extraction_failure(db, evidence_id, err, actor)

    return _persist_extraction_success(db, evidence_id, extraction, actor)
```

`_persist_extraction_success` / `_persist_extraction_failure` call
`mutate_entity` with `EVIDENCE_EXTRACT_ACTION_TYPE` and the success /
failed change type per D13. Extraction is idempotent: a second
successful extraction overwrites `raw_text` + `extracted_fields` and
leaves the `corrected` overlay untouched (status transitions
`completed → completed`).

### `services/api/app/services/compliance_review.py` (new)

```python
def get_evaluation(
    db: PostgresDatabase, evaluation_id: UUID,
    *, actor: ActorIdentity,
) -> ComplianceEvaluationRead:
    with db.connection() as conn:
        row = get_evaluation_row(conn, evaluation_id)
    if row is None:
        raise ComplianceEvaluationNotFoundError(evaluation_id)
    _require_scoped_authority(
        "compliance_evaluation.read",
        scope_kind="chapter", scope_id=row["chapter_id"],
        actor=actor, db=db,
    )
    return _evaluation_read_from_row(row)


def review_evaluation(
    db: PostgresDatabase, evaluation_id: UUID,
    request: ComplianceEvaluationReviewRequest,
    expected_version: int, *, actor: ActorIdentity,
) -> ComplianceEvaluationRead:
    if request.action == "override" and request.override_result is None:
        raise InvalidEvaluationReviewActionError(
            "override requires override_result"
        )
    # authority: compliance_evaluation.review (chapter scope from row)
    # mutate_entity with aggregate_type="compliance_evaluation";
    # OCC from expected_version.
    # Revision 2 (R8 / audit L2): pair the action_type with its dedicated
    # payload allowlist — review → COMPLIANCE_EVALUATION_REVIEW_*
    # + COMPLIANCE_EVALUATION_REVIEW_PAYLOAD_ALLOWLIST; override →
    # COMPLIANCE_EVALUATION_OVERRIDE_* + COMPLIANCE_EVALUATION_OVERRIDE_PAYLOAD_ALLOWLIST.
    # Both dispatches route through the same mutate_entity call with the
    # allowlist chosen per request.action; no f-strings, constants-only.
```

### `run_scheduled_compliance_evaluations` (WU-041B core logic)

Lives in `services/api/app/services/compliance.py` to keep worker +
API in one service module (ticket Code Boundary). Algorithm
(Revision 1 rewrites R2 + R4 + R6):

```python
def run_scheduled_compliance_evaluations(
    db: PostgresDatabase, *,
    now: datetime,
    batch_size: int = COMPLIANCE_EVIDENCE_BATCH_SIZE,
    actor: ActorIdentity,
    originating_actor: ActorIdentity | None = None,
) -> list[ComplianceEvaluationRead]:
    """Enumerate active rules + members, insert per-member evaluations
    idempotently, dispatch consequences through the roster service.

    Revision 1 (R4):
    - `actor` is the authority-bearing identity used for inner
      `mutate_entity` calls; the scheduled worker passes the
      `compliance-evaluator` service actor (which holds the internal
      `compliance_evaluation.write` + `roster.transition` grants).
    - `originating_actor` is the identity recorded as
      `originating_actor_kind` / `originating_actor_id` on the roster
      transition request, preserving operator attribution when the
      manual `/evaluations/run` endpoint triggers this path. Defaults
      to `actor` (so the scheduled worker naturally records the
      service actor as originating).
    """
    created: list[ComplianceEvaluationRead] = []
    effective_originating = originating_actor or actor

    with db.connection() as conn:
        rules = list_active_rules(conn)

    for rule in rules:
        try:
            period_start, period_end = _compute_period(
                cadence_kind=rule["cadence_kind"],
                cadence_params=rule["cadence_params"],
                evaluation_window_days=rule["evaluation_window_days"],
                now=now,
            )
            with db.connection() as conn:
                members = list_active_members_by_chapter(
                    conn, rule["chapter_id"]
                )
        except Exception:
            logger.exception(
                "compliance evaluation rule setup failed rule=%s",
                rule["id"],
            )
            continue

        # Revision 1 (R2 / F2): per-member isolation. A failure on one
        # member's evaluation tx does NOT abort the remaining members
        # of this rule. Mirrors SLICE-020 R1 `_expire_single_intent`
        # batch pattern.
        for member in members:
            try:
                inserted = _evaluate_member_rule(
                    db,
                    rule=rule,
                    member=member,
                    period_start=period_start,
                    period_end=period_end,
                    actor=actor,
                    originating_actor=effective_originating,
                )
                if inserted is not None:
                    created.append(inserted)
            except StaleMutationError:
                logger.debug(
                    "compliance evaluation OCC skip rule=%s member=%s",
                    rule["id"], member["member_id"],
                )
                continue
            except Exception:
                logger.exception(
                    "compliance evaluation failed rule=%s member=%s",
                    rule["id"], member["member_id"],
                )
                continue
    return created
```

`_evaluate_member_rule` (private helper) — **Revision 1 (R2, R3,
R6)** rewrites the body to a single per-member transaction that
atomically covers the idempotency insert, the audit projection, and
the consequence dispatch. Mirrors SLICE-020 R1
`_expire_single_intent` point-for-point.

```python
def _evaluate_member_rule(
    db: PostgresDatabase, *,
    rule: dict[str, Any],
    member: dict[str, Any],
    period_start: date,
    period_end: date,
    actor: ActorIdentity,
    originating_actor: ActorIdentity,
) -> ComplianceEvaluationRead | None:
    evaluation_id = uuid4()

    # (R6) Snapshot the roster entry's id + version BEFORE opening the
    # mutate_entity transaction, so the transition call has a concrete
    # `expected_version` to drive OCC. `list_active_members_by_chapter`
    # already returned the roster row; pull from there (roster row id +
    # its aggregate head version) via `get_roster_entry` to avoid a
    # stale version assumption.
    with db.connection() as conn:
        roster_entry = get_roster_entry(
            conn,
            chapter_id=rule["chapter_id"],
            member_id=member["member_id"],
        )
    if roster_entry is None:
        logger.debug(
            "compliance evaluation skipped; roster entry gone rule=%s "
            "member=%s", rule["id"], member["member_id"],
        )
        return None

    # (R6) Snapshot evidence outside the tx (read-only) to keep the
    # write-path transaction short.
    with db.connection() as conn:
        evidence_rows = list_evidence_for_rule_period(
            conn,
            rule_id=rule["id"],
            period_start=period_start,
            period_end=period_end,
            member_id=member["member_id"],
        )
    rule_version = _current_rule_version(db, rule_id=rule["id"])

    result, evidence_ids = _compute_rule_result(
        rule=rule, evidence_rows=evidence_rows
    )
    consequence_applied, review_status = _compute_consequence_shape(
        rule=rule, result=result
    )

    def mutate_projection(conn: Connection[Any]) -> StateChangeDraft:
        # (R2 / M1) The idempotency insert runs INSIDE mutate_projection,
        # so if any downstream step raises, the insert rolls back with
        # the audit row — no bare evaluation row persists.
        inserted = insert_evaluation_if_absent(
            conn,
            row={
                "id": evaluation_id,
                "rule_id": rule["id"],
                "rule_version": rule_version,
                "chapter_id": rule["chapter_id"],
                "member_id": member["member_id"],
                "period_start": period_start,
                "period_end": period_end,
                "result": result,
                "consequence_applied": consequence_applied,
                "review_status": review_status,
                "evidence_ids": [str(x) for x in evidence_ids],
            },
        )
        if inserted is None:
            # Another tick already evaluated this (member, rule, period).
            # Raise the well-known sentinel so mutate_entity aborts the
            # projection cleanly and the caller treats this member as a
            # no-op (no audit row written).
            raise _AlreadyEvaluatedSentinel()

        # (R3 / R6) Dispatch consequence inside the same connection so
        # the roster transition either commits alongside the evaluation
        # insert or both roll back together. `transition_roster_entry`
        # accepts `connection=` via mutate_entity so we thread ours in.
        # StaleMutationError / InvalidRosterStatusTransitionError
        # propagate out of mutate_projection → mutate_entity's
        # rollback covers the evaluation insert too. On the next tick
        # the ON CONFLICT skip will NOT fire (the insert rolled back),
        # so the whole member/period is retried cleanly — no retry
        # bookkeeping, no `deferred_occ_conflict` marker state.
        if consequence_applied == "under_review_applied":
            roster_service.transition_roster_entry(
                db,
                entry_id=roster_entry["id"],
                request=RosterEntryTransitionRequest(
                    to_status="under_review",
                    reason=f"compliance_violation:{rule['name']}",
                    originating_actor_kind=originating_actor.actor_kind,
                    originating_actor_id=originating_actor.actor_id,
                ),
                expected_version=roster_entry["version"],
                actor=actor,
                connection=conn,  # mutations.py:70 accepts this kwarg
            )

        return StateChangeDraft(
            change_type=COMPLIANCE_EVALUATION_CREATE_CHANGE_TYPE,
            payload_json={
                "rule_id": str(rule["id"]),
                "rule_version": rule_version,
                "chapter_id": rule["chapter_id"],
                "member_id": member["member_id"],
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "result": result,
                "consequence_applied": consequence_applied,
                "evidence_ids": [str(x) for x in evidence_ids],
            },
            diff_json={},
        )

    try:
        mutation_result = mutate_entity(
            db=db,
            aggregate_type="compliance_evaluation",
            aggregate_id=str(evaluation_id),
            request=_make_request(
                expected_version=0,
                actor=actor,
                request_surface="worker:compliance_evaluation",
            ),
            action_type=COMPLIANCE_EVALUATION_CREATE_ACTION_TYPE,
            action_payload={
                "rule_id": str(rule["id"]),
                "rule_version": rule_version,
                "chapter_id": rule["chapter_id"],
                "member_id": member["member_id"],
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "result": result,
                "consequence_applied": consequence_applied,
                "evidence_ids": [str(x) for x in evidence_ids],
            },
            payload_allowlist=set(
                COMPLIANCE_EVALUATION_CREATE_PAYLOAD_ALLOWLIST
            ),
            mutate_projection=mutate_projection,
            scope_kind="chapter", scope_id=rule["chapter_id"],
        )
    except _AlreadyEvaluatedSentinel:
        return None

    return _evaluation_read_from_result(mutation_result)


def _compute_consequence_shape(
    *, rule: dict[str, Any], result: str
) -> tuple[str, str]:
    """Map (consequence_kind, result) → (consequence_applied,
    review_status). D1/D10:
    - `consequence_kind='review'` → `(review_queued, pending)`
    - `consequence_kind='under_review'` + `result='violation'` +
      `consequence_params.auto_apply` (fail-safe default: must be
      explicitly True; absence → False) → `(under_review_applied,
      not_required)`
    - otherwise → `(none, not_required)` or `(none, pending)` per
      `consequence_params.require_review`."""
```

The private sentinel `_AlreadyEvaluatedSentinel` is a module-local
exception that carries no payload; it signals ON CONFLICT hit so the
caller does not treat the skip as an error.

**Revision 1 (R2) summary.** A mid-step failure rolls back the
entire (evaluation insert + audit projection + roster transition) as
one unit. On next tick the ON CONFLICT insert succeeds cleanly —
there is no bare evaluation row to heal, no orphan consequence state,
no retry bookkeeping. Per-member isolation is at the worker loop
level.

Period computation (D9):

```python
def _compute_period(
    *, cadence_kind, cadence_params, evaluation_window_days, now
) -> tuple[date, date]:
    anchor = now - timedelta(days=evaluation_window_days)
    offset = int(cadence_params.get("week_offset", 0))  # or month/quarter
    if cadence_kind == "weekly":
        # ISO week: Monday 00:00 UTC → Sunday 23:59:59 UTC
        ...
    elif cadence_kind == "monthly":
        # calendar month in UTC
        ...
    elif cadence_kind == "quarterly":
        # calendar quarter in UTC
        ...
```

---

## §6 — OCR infrastructure

### `services/api/app/infrastructure/ocr.py` (new)

```python
from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict


class OcrExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    raw_text: str
    extracted_fields: dict[str, Any]
    confidence: Decimal


class OcrProvider(Protocol):
    async def extract(
        self, attachment_ref: str, rule_hint: str | None = None
    ) -> OcrExtractionResult: ...


class StubOcrProvider:
    async def extract(
        self, attachment_ref: str, rule_hint: str | None = None
    ) -> OcrExtractionResult:
        from app.contracts.compliance import OcrProviderNotConfiguredError
        raise OcrProviderNotConfiguredError(
            "OCR provider not configured"
        )


def get_ocr_provider(settings) -> OcrProvider:
    # Operators wire a concrete provider via settings in a later slice;
    # SLICE-022 ships the stub only (D4, D15).
    return StubOcrProvider()
```

The endpoint layer maps `OcrProviderNotConfiguredError → 503` via
`_shared.py` (see §8). No third-party SDKs are added as dependencies.

---

## §7 — Scheduled worker (WU-041B)

### `services/api/app/tasks/compliance.py` (new)

Mirrors `services/api/app/tasks/permission_expiry.py` structurally:
module-level `_DB`, `configure_compliance(*, db)`, service-actor
helper, root audit context, tick function.

```python
from __future__ import annotations

import logging
from contextlib import nullcontext
from datetime import UTC, datetime
from uuid import uuid4

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.mutations import StaleMutationError
from app.core.context import get_current_audit_context, use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.compliance import (
    COMPLIANCE_EVIDENCE_BATCH_SIZE,
    run_scheduled_compliance_evaluations,
)

logger = logging.getLogger(__name__)

COMPLIANCE_EVALUATOR_ACTOR_ID = "compliance-evaluator"
_DB: PostgresDatabase | None = None


def configure_compliance(*, db: PostgresDatabase) -> None:
    global _DB
    _DB = db


def get_compliance_db() -> PostgresDatabase:
    global _DB
    if _DB is None:
        _DB = PostgresDatabase()
    return _DB


def _evaluator_service_actor() -> ActorIdentity:
    return ActorIdentity(
        actor_kind="service", actor_id=COMPLIANCE_EVALUATOR_ACTOR_ID
    )


def _root_audit_context() -> AuditContextRead:
    correlation_id = uuid4()
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=None,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=None,
        ),
    )


def compliance_evaluation_worker_tick(
    *,
    now: datetime | None = None,
    batch_size: int | None = None,
) -> list | None:
    existing_ctx = get_current_audit_context()
    ambient = (
        use_audit_context(_root_audit_context())
        if existing_ctx is None
        else nullcontext()
    )
    with ambient:
        try:
            return run_scheduled_compliance_evaluations(
                get_compliance_db(),
                actor=_evaluator_service_actor(),
                originating_actor=None,  # defaults to actor (service)
                now=now or datetime.now(tz=UTC),
                batch_size=batch_size or COMPLIANCE_EVIDENCE_BATCH_SIZE,
            )
        except StaleMutationError:
            logger.debug(
                "compliance evaluation: OCC conflict, retry next tick"
            )
            return None
        except Exception:
            logger.exception(
                "compliance evaluation worker tick failed"
            )
            return None
```

### Scheduler wiring

`services/api/app/services/scheduler.py`:

- Add module-level constant
  `COMPLIANCE_EVALUATION_INTERVAL_SECONDS = 3600` (near line 34).
- Add `self._last_compliance_evaluation_tick_at: datetime | None = None`
  to `SchedulerLoop.__init__` (near line 150).
- Add `await self._run_compliance_evaluation_if_due(now)` to `_tick`
  (after existing worker dispatches).
- Add the `_run_compliance_evaluation_if_due` method mirroring
  `_run_permission_expiry_if_due` (lines 256–273).
- Append `"COMPLIANCE_EVALUATION_INTERVAL_SECONDS"` to `__all__`.

`services/api/app/tasks/__init__.py`:

- Import `configure_compliance` from `app.tasks.compliance`.
- Call `configure_compliance(db=db)` inside `configure_task_runtime`.

No `scheduled_jobs` row is registered — compliance uses the in-loop
interval pattern (same as permission expiry, ticket SLA, archive, and
read-model workers).

---

## §8 — Endpoints

### Package layout

Under ticket Code Boundary the endpoints live in a new subpackage
`services/api/app/api/v1/endpoints/compliance/`, mirroring
`endpoints/permissions/`:

```
services/api/app/api/v1/endpoints/compliance/
├── __init__.py            # APIRouter aggregator
├── _shared.py             # get_db, parse_if_match_strong, exception mapper
├── rules.py               # POST, PATCH, GET /rules
├── evidence.py            # POST, GET /evidence
├── evidence_correct.py    # POST /evidence/{id}/correct
├── evidence_extract.py    # POST /evidence/{id}/extract
├── evaluations.py         # GET, POST /evaluations/{id}[/review]
└── evaluations_run.py     # POST /evaluations/run (manual trigger)
```

`services/api/app/api/v1/router.py` gains one line:

```python
from .endpoints import compliance
router.include_router(compliance.router, prefix="/compliance")
```

(The path prefix `/compliance` is applied at the aggregator; each
sub-router keeps relative paths like `/rules`.)

### `_shared.py`

Reused helpers adapted from
`services/api/app/api/v1/endpoints/permissions/_shared.py`:

- `get_db(request) -> PostgresDatabase`
- `parse_if_match_strong(request) -> int` (verbatim semantics;
  RFC 7232 strong ETag)
- `set_etag(response, etag)`
- `raise_known_compliance_error(error)` maps:
  - `ComplianceRuleNotFoundError`, `EvidenceSubmissionNotFoundError`,
    `ComplianceEvaluationNotFoundError`, `MissingAggregateError` → 404
  - `StaleMutationError` → 412 (with
    `expected_version` / `current_version` detail per permissions
    pattern)
  - `CorrectionNotPermittedStatusError` → 409
  - `DuplicateActiveComplianceRuleError` → 409
  - `InvalidEvaluationReviewActionError` → 422
  - `EvidenceChapterMismatchError` → 422 (Revision 1 / R1;
    `{"code": "evidence_chapter_mismatch"}` with
    `rule_id`, `rule_chapter_id`, `request_chapter_id` detail)
  - `OcrProviderNotConfiguredError` → 503 (`{"code":
    "ocr_provider_not_configured"}`)
  - `PermissionError` → 403
  - Pydantic `ValidationError` (blank `correction_reason` etc.) → 422

### Endpoint bodies

Each module follows the `endpoints/permissions/*` pattern: parse path /
body via Pydantic, resolve `actor = Depends(get_current_actor)`, call
the service (which runs the authority check internally per D11), map
known exceptions via `_shared.raise_known_compliance_error`. ETag is
set on any response that carries a versioned aggregate.

Status-code mapping:

| Path                                                       | 200 | 201 | 403 | 404 | 409                                | 412            | 422                          | 503                         |
|------------------------------------------------------------|-----|-----|-----|-----|------------------------------------|----------------|------------------------------|-----------------------------|
| `POST /compliance/rules`                                   | -   | Y   | authority | chapter n/a | duplicate_active_rule              | -              | validation                   | -                           |
| `PATCH /compliance/rules/{id}`                             | Y   | -   | authority | rule n/a    | -                                  | stale If-Match | validation                   | -                           |
| `GET /compliance/rules`                                    | Y   | -   | authority | -           | -                                  | -              | -                            | -                           |
| `POST /compliance/evidence`                                | -   | Y   | authority | rule n/a    | -                                  | -              | blank attachment_ref; chapter_id/rule mismatch (R1) | -              |
| `GET /compliance/evidence/{id}`                            | Y   | -   | authority | evidence n/a| -                                  | -              | -                            | -                           |
| `POST /compliance/evidence/{id}/correct`                   | Y   | -   | authority | evidence n/a| status not correctable             | stale If-Match | blank reason                 | -                           |
| `POST /compliance/evidence/{id}/extract`                   | Y   | -   | authority | evidence n/a| -                                  | -              | -                            | ocr_provider_not_configured |
| `GET /compliance/evaluations/{id}`                         | Y   | -   | authority | evaluation n/a | -                               | -              | -                            | -                           |
| `POST /compliance/evaluations/{id}/review`                 | Y   | -   | authority | evaluation n/a | -                               | stale If-Match | override without result      | -                           |
| `POST /compliance/evaluations/run`                         | Y   | -   | authority | -           | -                                  | -              | -                            | -                           |

---

## §9 — Constants (module-level, no f-strings)

All `action_type` / `change_type` / payload allowlist values live in
`services/api/app/contracts/compliance.py` (contracts-level, as
elsewhere in the codebase); imported by services and tests. No
f-string / dynamic vocabulary per D13 + AGENTS.md.

Additional module-level constants:

| Module                                    | Constant                                    | Value                     |
|-------------------------------------------|---------------------------------------------|---------------------------|
| `services/api/app/services/scheduler.py`  | `COMPLIANCE_EVALUATION_INTERVAL_SECONDS`    | `3600`                    |
| `services/api/app/services/compliance.py` | `COMPLIANCE_EVIDENCE_BATCH_SIZE`            | `50`                      |
| `services/api/app/tasks/compliance.py`    | `COMPLIANCE_EVALUATOR_ACTOR_ID`             | `"compliance-evaluator"`  |
| (implicit — D11, opaque strings)          | `compliance_rule.read`                      | authority permission      |
| (implicit — D11, opaque strings)          | `compliance_rule.write`                     | authority permission      |
| (implicit — D11, opaque strings)          | `compliance_evidence.submit`                | authority permission      |
| (implicit — D11, opaque strings)          | `compliance_evidence.correct`               | authority permission      |
| (implicit — D11, opaque strings)          | `compliance_evidence.extract`               | authority permission      |
| (implicit — D11, opaque strings)          | `compliance_evaluation.read`                | authority permission      |
| (implicit — D11, opaque strings)          | `compliance_evaluation.review`              | authority permission      |
| (implicit — D11, opaque strings)          | `compliance_evaluation.write`               | internal substrate perm   |
| (implicit — D11, opaque strings)          | `roster.transition`                         | reused shipped permission |

---

## §10 — Tests (per-WU, per-AC docstrings)

Tests follow D14 and AGENTS.md Test/Code separation: the test agent
sees contracts only; each test docstring names the AC or guardrail it
enforces. Tests hit a real DB fixture (`governance_db` style —
`services/api/tests/test_roster.py:34–40`). Approximately 40 tests
across six files.

### `services/api/tests/test_compliance_rules.py` (WU-039)

- `test_create_persists_cadence_requirements_and_consequence` — AC1.
- `test_create_emits_compliance_rule_create_action_with_constants` — D13.
- `test_create_requires_compliance_rule_write_authority` — D11: 403.
- `test_create_rejects_duplicate_active_name_in_chapter` — D2: 409.
- `test_create_rejects_invalid_cadence_kind` — D2: 422 CHECK
  proxy / Pydantic literal.
- `test_create_rejects_invalid_consequence_kind` — D1: 422.
- `test_update_advances_version_with_if_match` — AC1 OCC.
- `test_update_rejects_stale_if_match` — AC1: 412.
- `test_archive_allows_name_reuse` — D2: partial unique index.
- `test_list_rules_returns_chapter_scoped_results` — AC1.

### `services/api/tests/test_compliance_evidence.py` (WU-040A)

- `test_submit_creates_row_in_pending_state` — AC2.
- `test_submit_emits_evidence_submission_submit_action_with_constants` — D13.
- `test_submit_requires_compliance_evidence_submit_authority` — D11.
- `test_submit_enforces_rule_fk_integrity` — D3: 404 (rule missing) /
  FK violation surfaced.
- `test_submit_rejects_blank_attachment_ref` — D3: 422.
- `test_submitted_by_is_derived_from_actor_not_request_body` — D3 /
  spoof-proof: even if body carries a different `submitted_by`, row
  stores `actor.actor_id` (extra field is rejected by `extra="forbid"`).
- `test_submit_rejects_chapter_id_mismatch_with_rule` — Revision 1
  (R1): request carries `chapter_id` that differs from the rule's
  chapter; service raises `EvidenceChapterMismatchError` → HTTP 422.
- `test_submit_authorizes_against_rules_chapter_not_request_chapter`
  — Revision 1 (R1): actor holds `compliance_evidence.submit` only
  on the rule's chapter; request carries an unrelated `chapter_id`
  the actor also has authority on; service uses rule's chapter for
  the authority check (422 precedes authority, so mismatch is
  rejected before authority is consulted; an aligned matching request
  proceeds).
- `test_submit_persists_chapter_id_from_rule_not_request` —
  Revision 1 (R1): the evidence row's `chapter_id` column always
  equals the rule's chapter, regardless of what the body supplied
  (in the matching case).
- `test_get_returns_pending_state_and_version_etag` — AC2.

### `services/api/tests/test_compliance_ocr_correct.py` (WU-040B-correct)

- `test_correction_writes_overlay_with_actor_as_corrector` — AC3.
- `test_correction_preserves_raw_text_and_attachment_ref` — AC3.
- `test_correction_preserves_original_extracted_fields` — AC3 / D3.
- `test_correction_transitions_status_to_corrected` — AC3.
- `test_correction_rejects_stale_if_match` — AC3 OCC: 412.
- `test_correction_rejects_pending_status` — D6: 409.
- `test_correction_rejects_running_status` — D6: 409.
- `test_correction_rejects_blank_reason` — D6: 422.
- `test_correction_requires_compliance_evidence_correct_authority` — D11.
- `test_correction_emits_evidence_submission_correct_action_with_constants` — D13.
- `test_second_correction_overwrites_overlay_and_preserves_baseline` — D6.
- `test_correction_diff_json_records_prior_overlay_on_second_correction`
  — Revision 1 (R5) / audit M4: second correction's
  `activity_state_changes.diff_json` records
  `extracted_fields_corrected: {old: <overlay_1>, new: <overlay_2>}`
  and the immutable `extracted_fields` baseline. First correction's
  diff records `extracted_fields_corrected: {old: null, new: <overlay_1>}`.

### `services/api/tests/test_compliance_ocr_extract.py` (WU-040B-extract)

- `test_extract_invokes_provider_and_transitions_to_completed` — D4/D5.
- `test_extract_persists_raw_text_fields_and_confidence` — D3.
- `test_extract_failure_transitions_to_failed_with_error_populated` — D3.
- `test_extract_with_stub_provider_returns_503` — D4/D5.
- `test_extract_is_idempotent_on_repeat_invocation` — D5.
- `test_extract_requires_compliance_evidence_extract_authority` — D11.
- `test_extract_emits_evidence_submission_extract_action_with_constants` — D13.

### `services/api/tests/test_compliance_review_api.py` (WU-041A)

- `test_get_evaluation_returns_populated_read_model` — AC1/AC4.
- `test_review_approve_updates_review_status_and_reviewer` — AC1.
- `test_review_override_changes_result_and_advances_consequence` — AC1.
- `test_review_override_without_result_returns_422` — D7.
- `test_review_rejects_stale_if_match` — AC1 OCC: 412.
- `test_review_rejects_blank_reason` — 422.
- `test_review_requires_compliance_evaluation_review_authority` — D11.
- `test_review_emits_compliance_evaluation_review_action_with_constants` — D13.

### `services/api/tests/test_compliance_evaluation_worker.py` (WU-041B)

- `test_worker_inserts_evaluation_once_per_member_rule_period` — AC4.
- `test_worker_is_idempotent_across_multiple_ticks` — AC4 / D8.
- `test_worker_routes_under_review_consequence_through_roster_service` — AC4 / D10.
- `test_worker_records_review_queued_for_review_consequence_kind` — D1/D10.
- `test_worker_records_consequence_applied_under_review_on_success` — D10.
- `test_worker_tolerates_per_rule_failure_and_continues_batch` — D8.
- `test_worker_tolerates_occ_conflict_and_retries_next_tick` — D8.
- `test_period_computation_weekly_monthly_quarterly` — D9.
- `test_worker_records_insufficient_evidence_with_no_consequence` — D7/D14.
- `test_worker_installs_root_audit_context` — D8.
- `test_worker_respects_consequence_kind_under_review_only_on_violation` — D10.
- `test_worker_does_not_bypass_roster_service_with_raw_sql` — D10.
- `test_worker_member_failure_does_not_skip_remaining_members_of_rule`
  — Revision 1 (R2 / F2): a mid-rule member raising a non-OCC
  exception is caught at the per-member arm; remaining members of
  that rule are processed within the same tick.
- `test_worker_rolls_back_evaluation_insert_when_audit_projection_fails`
  — Revision 1 (R2 / M1): injected fault inside the audit projection
  raises; neither the `compliance_evaluations` row nor any
  `activity_actions` row persists; the next tick retries cleanly
  (no ON CONFLICT shadow row, no bare evaluation row).
- `test_worker_rolls_back_evaluation_insert_when_roster_transition_occ_fails`
  — Revision 1 (R6): roster transition raises
  `StaleMutationError` inside the projection; whole per-member tx
  rolls back; next tick retries and commits when version matches.
- `test_manual_run_preserves_operator_attribution_on_roster_transition`
  — Revision 1 (R4 / audit M3): HTTP operator triggers
  `POST /evaluations/run`; resulting `roster_entry.transition`
  action row records
  `originating_actor_kind=<operator.kind>`,
  `originating_actor_id=<operator.id>` (not
  `compliance-evaluator`). Scheduled worker tick in the same test
  fixture records the service actor as originating.
- `test_manual_run_requires_compliance_evaluation_review_authority`
  — Revision 1 (R4): operator without `compliance_evaluation.review`
  receives 403; the inner service-actor's `.write` grant is not
  consulted for authority purposes when the endpoint check fails.

HTTP-layer coverage: each endpoint has at least one HTTP-level test
exercising 403 (authority), 422 (validation), and the happy path.
Service-layer tests carry the per-AC behavioural assertions.

---

## §11 — Out of scope (explicit — D15)

The following are deferred; any PR adding one is out-of-bounds for this
slice and must split into a follow-up slice:

1. Real OCR engine implementation (Google Vision, Gemini, Tesseract,
   etc.) — pluggable Protocol + stub only (D4).
2. Async extraction queue — synchronous only (D5).
3. File upload endpoint / blob storage — `attachment_ref` is opaque.
4. Per-rule-type evidence validators or dispatch tables.
5. Multi-member / batch consequences — one consequence per evaluation
   row.
6. Evidence deletion / GDPR flows.
7. Discord-triggered evidence submission — HTTP intake only.
8. Trust-signal integration — compliance violations do not generate
   trust signals this slice.
9. Immutable corrections history table — history lives in
   `activity_state_changes` via the audit projection.
10. `probation` as a new roster state — the only roster consequence is
    existing `under_review` (D1).
11. Per-chapter timezone overrides on cadence windows — UTC only (D9).
12. Confidence-based auto-approval of extractions.
13. Cross-scope (global) compliance rules — chapter-scoped only.

---

## §12 — PR decomposition

Three candidate seams emerge from the synthesis:

- **PR A — Rule lifecycle.** WU-039 (migration + contracts + repo +
  service + endpoints + tests) and WU-041A review API (migration +
  review service + endpoints + tests). Clean read/write-gated
  substrate without any evidence flow.
- **PR B — Evidence flow.** WU-040A (migration + evidence contracts +
  service + endpoints + tests), WU-040B-correct (contracts + service
  + endpoints + tests), WU-040B-extract (contracts + infrastructure
  OCR + service + endpoints + tests). All three share the
  `evidence_submissions` row lifecycle.
- **PR C — Scheduled worker.** WU-041B only (worker module,
  scheduler wiring, period helper, roster-service consequence
  dispatch, tests). Depends on PR A + PR B being merged.

Alternative single-PR bundling (PR A+B+C): acceptable at multi-concern
review time if the reviewer prefers one coherent drop — the three
migrations can be chained in a single PR (still linear per D12). The
proposal recommends the three-PR split for review surface area; final
decomposition is subject to the multi-concern review gate and should
not exceed three PRs.

---

## Guardrails (binding across all WUs)

- D1–D15 are binding. Any apparent need to violate a decision escalates
  to synthesis revision rather than silent expansion.
- All mutations flow through `mutate_entity` with narrow payload
  allowlists; no direct INSERT/UPDATE on mutable aggregates
  (§5 / `services/api/app/services/mutations.py:58`).
- All `action_type` / `change_type` values are module-level constants
  (§9). No f-strings or inline concatenation when emitting audit
  events (D13).
- Authority checks run at the service layer via
  `_require_scoped_authority`; endpoints do not declare per-route
  FastAPI authority dependencies (matches SLICE-020 / permissions
  pattern).
- Originating actor is spoof-proof: derived from
  `Depends(get_current_actor)` / the ambient audit context, never
  from the request body.
- Roster consequences route only through
  `services/api/app/services/roster.py::transition_roster_entry` (D10).
  No raw `UPDATE roster_entries` in compliance code.
- Multi-aggregate service operations share one connection via
  `mutate_entity(connection=...)` — the kwarg exists at
  `services/api/app/services/mutations.py:70`.
- Worker installs root audit context (§7 — mirrors
  `services/api/app/tasks/permission_expiry.py:43–74`).
- Migration chain is linear off `wu_038` (D12); downgrades are
  no-ops.
- Roster state vocabulary is `under_review`, not `probation` (D1).
- Test/Code Agent separation (D14): test agent sees contracts only;
  code agent sees contracts + tests.

---

## Migration chain

- Current head: `wu_038_permission_intent_expiry`.
- SLICE-022 advances the head through three migrations in order:
  `wu_039_compliance_rules` → `wu_040a_compliance_evidence` →
  `wu_041a_compliance_evaluations`. New head after slice:
  `wu_041a_compliance_evaluations`.
- Filename convention (shipped): `wu-039_compliance_rules.py` (dash
  between number and title); internal `revision` identifier uses
  underscore: `"wu_039_compliance_rules"`.

---

## Revision log

### Revision 2 — audit re-run MEDIUM + LOW findings closed

Binding risk inputs (re-run): `plans/risk/slice-022-audit.md` (MEDIUM:
M5; LOW: L1 unchanged, L2 new), `plans/risk/slice-022-shortcut.md`
(LOW — no action).

- **R7 (audit M5 MEDIUM — roster-service `connection=` kwarg).**
  R6's atomicity guarantee (evaluation insert + roster transition
  share one `mutate_entity` transaction) depended on
  `transition_roster_entry(..., connection=conn)` threading the
  caller's connection. The shipped
  `services/api/app/services/roster.py::transition_roster_entry`
  does not accept a `connection=` kwarg today, so without an
  explicit signature extension the §5 call would raise `TypeError`
  at import and the evaluation + roster transition would commit in
  separate transactions — re-opening the exact atomicity failure R2
  was built to close. Revision 2 adds an explicit subsection to §5
  ("Roster service signature extension") documenting the
  backward-compatible extension of `transition_roster_entry` and
  `get_roster_entry` with an optional `connection=None` kwarg,
  mirroring SLICE-020 R1's same-shape extension of
  `grant_authority` / `revoke_authority`. Test:
  `test_transition_roster_entry_accepts_shared_connection` in
  `services/api/tests/test_roster.py` (roster's own test home — so
  the signature change is pinned where it lives, not smeared into
  SLICE-022 tests). File/line refs: §5 header + §5 "Roster service
  signature extension" subsection; §10 notes the cross-file test.

- **R8 (audit L2 LOW — override payload allowlist).** Added
  `COMPLIANCE_EVALUATION_OVERRIDE_PAYLOAD_ALLOWLIST = frozenset({
  "evaluation_id", "override_result", "reviewer_reason"})` alongside
  the review allowlist in §3. §5 `review_evaluation` selects the
  allowlist per `request.action`: review dispatches pair
  `COMPLIANCE_EVALUATION_REVIEW_ACTION_TYPE` with
  `COMPLIANCE_EVALUATION_REVIEW_PAYLOAD_ALLOWLIST`; override
  dispatches pair `COMPLIANCE_EVALUATION_OVERRIDE_ACTION_TYPE` with
  `COMPLIANCE_EVALUATION_OVERRIDE_PAYLOAD_ALLOWLIST`. Closes D13's
  "named allowlist per action" requirement at the naming layer
  (previously review and override implicitly shared one allowlist,
  which read correctly but scanned poorly). File/line refs: §3
  (new constant); §5 `review_evaluation` (selection comment).

- **Audit L1 (LOW) — unchanged.** Still documented-silent (no audit
  row on 503 path); accepted per Revision 1's deferral.

- **Shortcut LOW items — no action.** Shortcut re-run is LOW with no
  new findings; Revision 1's LOW deferrals stand.

### Revision 1 — audit/shortcut MEDIUM findings closed

Binding risk inputs: `plans/risk/slice-022-audit.md` (MEDIUM: M1, M2,
M3, M4; LOW: L1), `plans/risk/slice-022-shortcut.md` (MEDIUM: F1, F2,
F3; six LOW), `plans/risk/slice-022-scope.md` (LOW — no action).

- **R1 (shortcut F1 MEDIUM — chapter_id spoof).** `submit_evidence`
  loads the rule first via `get_rule(request.rule_id)` and authorizes
  against `rule["chapter_id"]`, not `request.chapter_id`. Mismatch
  raises `EvidenceChapterMismatchError` → HTTP 422. The evidence row
  persists `chapter_id = rule["chapter_id"]` — derived, spoof-proof.
  Same rule-first pattern documented for any future endpoint that
  accepts both `rule_id` and `chapter_id`. Tests:
  `test_submit_rejects_chapter_id_mismatch_with_rule`,
  `test_submit_authorizes_against_rules_chapter_not_request_chapter`,
  `test_submit_persists_chapter_id_from_rule_not_request`.
  File/line refs in this proposal: §3 `EvidenceChapterMismatchError`;
  §5 `submit_evidence`; §8 `_shared.py` + status table; §10
  `test_compliance_evidence.py`.

- **R2 (audit M1 MEDIUM + shortcut F2 MEDIUM — atomic evaluation +
  per-member isolation).** `_evaluate_member_rule` is now a single
  per-member transaction — `insert_evaluation_if_absent`, the audit
  projection, and the roster transition commit or roll back together
  (mirrors SLICE-020 R1 `_expire_single_intent`). On ON CONFLICT, a
  private `_AlreadyEvaluatedSentinel` raised from
  `mutate_projection` aborts the projection cleanly (no audit row,
  no duplicate). `run_scheduled_compliance_evaluations` wraps the
  member loop in a per-member `try / except StaleMutationError /
  except Exception` so one bad member does not abort the rule's
  remaining members. Tests:
  `test_worker_rolls_back_evaluation_insert_when_audit_projection_fails`,
  `test_worker_member_failure_does_not_skip_remaining_members_of_rule`.
  File/line refs: §4 `insert_evaluation_if_absent` docstring; §5
  `_evaluate_member_rule` rewrite.

- **R3 (audit M2 MEDIUM — consequence audit shape).** Picked option
  (a) per risk guidance: consequence is an attribute of the
  evaluation and is written inside the CREATE action's
  `mutate_projection`. The orphan
  `COMPLIANCE_EVALUATION_CONSEQUENCE_CHANGE_TYPE` constant is
  removed; the `mark_consequence_applied` repository helper is
  removed from §4. The roster transition is its own audit chain
  (`roster_entry.transition`) threaded via the shared
  `correlation_id`. File/line refs: §3 (constant removal);
  §4 (helper removal); §5 `_evaluate_member_rule.mutate_projection`.

- **R4 (audit M3 MEDIUM — operator attribution on manual /run).**
  `run_scheduled_compliance_evaluations` grows an explicit
  `originating_actor: ActorIdentity | None` parameter (defaulting
  to `actor`). The scheduled worker passes `None`, so the service
  actor is originating as before. The manual
  `POST /evaluations/run` endpoint authorizes the operator with
  `compliance_evaluation.review` (D11: `.write` is internal-only),
  then invokes the service with
  `actor=_evaluator_service_actor(), originating_actor=<operator>`.
  The resulting `roster_entry.transition` records operator kind +
  id; the `compliance_evaluation.create` row records the service
  actor (consistent with the scheduled path); correlation_id ties
  them together. This is a legitimate authority-escalation pattern
  (operator cannot self-write `.write` but can trigger the service
  actor for a backfill) and is documented in §1 AC4 and the
  Guardrails. Tests:
  `test_manual_run_preserves_operator_attribution_on_roster_transition`,
  `test_manual_run_requires_compliance_evaluation_review_authority`.
  File/line refs: §1 AC4 endpoints bullet; §5
  `run_scheduled_compliance_evaluations`; §7 worker tick (defaults
  `originating_actor=None`).

- **R5 (audit M4 MEDIUM — second-correction diff_json).**
  `correct_evidence.mutate_projection` now emits
  `diff_json = {extraction_status: {old, new},
  extracted_fields: <baseline>,
  extracted_fields_corrected: {old: <prior overlay>, new: <new
  overlay>}}`. First correction's `old` is `None`; subsequent
  corrections carry the prior overlay. A single state-change row is
  self-describing: baseline + prior overlay + new overlay. Test:
  `test_correction_diff_json_records_prior_overlay_on_second_correction`.
  File/line refs: §5 `correct_evidence.mutate_projection` diff_json.

- **R6 (shortcut F3 MEDIUM — roster call signature).** The worker
  now explicitly (a) fetches `roster_entry` via
  `get_roster_entry(connection, chapter_id=..., member_id=...)`
  before opening the mutate_entity transaction, and (b) passes
  `entry_id=roster_entry["id"]` and
  `expected_version=roster_entry["version"]` into
  `roster.transition_roster_entry`, which runs on the shared
  connection (`mutations.py:70` accepts `connection=`). On
  `StaleMutationError` the entire per-member transaction rolls back
  (R2), so the next tick retries naturally — no
  `deferred_occ_conflict` marker state, no `pending_consequence`
  intermediate, no second mutation. Observation 3 from the shortcut
  report (non-atomic consequence) is closed by the same tx boundary.
  `InvalidRosterStatusTransitionError` (member already
  `under_review`/`removed`) is mapped upstream by
  `_compute_consequence_shape` choosing `consequence_applied="none"`
  when the preconditions do not hold; there is no silent catch
  inside the write path. Test:
  `test_worker_rolls_back_evaluation_insert_when_roster_transition_occ_fails`.
  File/line refs: §4 "Roster member enumeration" expansion;
  §5 `_evaluate_member_rule` rewrite.

- **Audit L1 (LOW) — unchanged.** The 503 path remains
  documented-silent (no audit row). Raising this to a MEDIUM-action
  revision was not required; the proposal already documents the
  503 short-circuit in §5 and the tests pin the behavior. Deferred
  to a follow-up slice if operational visibility becomes a concern.

- **Scope findings — none.** `plans/risk/slice-022-scope.md` rated
  LOW with observations only; no action.

- **Shortcut LOW items (Obs 1–6) — not addressed in this revision.**
  Obs 1 (failed → corrected COALESCE rule), Obs 2 (rule_version
  snapshot mechanism), Obs 4 (unused `compliance_rule.read` on
  service actor), Obs 5 (`asyncio.run` endpoint declaration),
  Obs 6 (negative-test naming). These are hygiene items;
  implementation phase can absorb them inline without a revision
  cycle.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
