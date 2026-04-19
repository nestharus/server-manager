# SLICE-022: Compliance rule evaluation with evidence

## Parent

**Initiative:** INIT-007 — Activity and Compliance
**Phase:** Phase 4

## What Changes for the Operator

Operators can define compliance rules, accept evidence before extraction completes, review OCR and corrections, and run scheduled evaluations that apply proportionate roster consequences instead of hand-maintaining spreadsheets and manual threshold checks.

## Justification Chain

**Market signal:** Activity/compliance research shows strong demand for attendance and analytics tooling, but a general-purpose evidence-backed compliance engine with dispute-grade audit remains absent.
**Problem axis:** §6 — Activity Tracking and Compliance Enforcement
**Proposal mechanism:** proposal.md, Activity and Compliance; Operational Workflows -> Compliance Evaluation; AI/ML Approaches -> Screenshot OCR for Compliance Evidence
**Philosophy principles:** Principle 9: Volunteer-Aware Design, Principle 13: Derived State Transparency, Principle 14: Graduated Consequence

## Technical Specification

**Schema objects:**
- ComplianceRule: `chapter_id`, `name`, cadence/parameters, consequence policy, `version`
- EvidenceSubmission: `member_id`, `chapter_id`, `rule_id`, attachment/raw/extracted data, extraction status/confidence, `version`
- ComplianceEvaluation: `member_id`, `chapter_id`, `rule_id`, `rule_version`, result, consequence_applied

**API endpoints:**
- POST /api/v1/compliance/rules -> ComplianceRuleRead
- PATCH /api/v1/compliance/rules/{rule_id} -> ComplianceRuleRead
- POST /api/v1/compliance/evidence -> EvidenceSubmissionRead
- GET /api/v1/compliance/evidence/{evidence_id} -> EvidenceSubmissionRead
- POST /api/v1/compliance/evidence/{evidence_id}/correct -> OfficerCorrectionRead
- POST /api/v1/compliance/evidence/{evidence_id}/extract -> EvidenceExtractionRead
- GET /api/v1/compliance/evaluations/{evaluation_id} -> ComplianceEvaluationRead
- POST /api/v1/compliance/evaluations/{evaluation_id}/review -> ComplianceEvaluationRead
- POST /api/v1/compliance/evaluations/run
- scheduled handler: run_compliance_evaluations() -> list[ComplianceEvaluationRead]

**Discord interactions:**
- none in this slice; evidence and evaluation surfaces are API- and worker-driven in the roadmap

**State transitions:**
- evidence pending -> complete/failed extraction
- evaluation compliant/violation/insufficient_evidence -> review action or roster consequence

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-039 | Compliance Rule Management API | `services/api/app/contracts/compliance.py` | migrations/versions/wu-039_compliance_rules.py, services/api/app/contracts/compliance.py, services/api/app/repositories/compliance.py, services/api/app/services/compliance.py, services/api/app/api/v1/endpoints/compliance/rules.py, services/api/tests/test_compliance_rules.py |
| WU-040A | Evidence Submission API | `services/api/app/contracts/compliance.py` | migrations/versions/wu-040a_compliance_evidence.py, services/api/app/contracts/compliance.py, services/api/app/repositories/compliance.py, services/api/app/services/compliance.py, services/api/app/api/v1/endpoints/compliance/evidence.py, services/api/tests/test_compliance_evidence.py |
| WU-040B-correct | Officer Correction API | `services/api/app/contracts/compliance_corrections.py` | services/api/app/contracts/compliance_corrections.py, services/api/app/services/compliance_corrections.py, services/api/app/api/v1/endpoints/compliance/evidence_correct.py, services/api/tests/test_compliance_ocr_correct.py |
| WU-040B-extract | OCR Extraction API | `services/api/app/contracts/compliance_extraction.py` | services/api/app/contracts/compliance_extraction.py, services/api/app/infrastructure/ocr.py, services/api/app/services/compliance_extraction.py, services/api/app/api/v1/endpoints/compliance/evidence_extract.py, services/api/tests/test_compliance_ocr_extract.py |
| WU-041A | Compliance Evaluation Review API | `services/api/app/contracts/compliance.py` | migrations/versions/wu-041a_compliance_review_api.py, services/api/app/contracts/compliance.py, services/api/app/repositories/compliance.py, services/api/app/services/compliance_review.py, services/api/app/api/v1/endpoints/compliance/evaluations.py, services/api/tests/test_compliance_review_api.py |
| WU-041B | Scheduled Compliance Evaluation Worker | `services/api/app/contracts/compliance.py` | services/api/app/tasks/compliance.py, services/api/app/services/compliance.py, services/api/tests/test_compliance_evaluation_worker.py |

## Dependencies

**Upstream slices:** SLICE-007, SLICE-008, SLICE-009, SLICE-010, SLICE-013, SLICE-015, SLICE-018
**Foundation dependencies:** SLICE-004, SLICE-006
**Parallelizable with:** SLICE-023

## Acceptance Criteria

- [ ] Compliance rule create/update persists cadence, evidence requirements, and consequence policy with optimistic locking on updates.
- [ ] Evidence submission stores the attachment reference before OCR extraction completes and returns pending extraction state.
- [ ] Officer correction updates extracted fields with optimistic locking and preserves the raw attachment and OCR text.
- [ ] Scheduled evaluation is idempotent for the same member/rule/period and routes review or probation consequences through the roster API path.

## Engineering Notes

**Effort:** VS-016 -> XL
**Prototyping:** VS-016 -> yes
**Risk:** High — this slice concentrates external evidence uncertainty, scheduled enforcement, and cross-subsystem consequence routing.
**Existing code:** Depends on the chapter and roster substrates plus the scheduler; there is no approved compliance engine in the current codebase.
**Known challenges:** Keeping evidence provenance intact while still making extraction/correction and scheduled evaluation fast enough to replace spreadsheet work.
