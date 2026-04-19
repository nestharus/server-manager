# SLICE-012: Structured application intake with reviewer ownership

## Parent

**Initiative:** INIT-004 — Structured Intake
**Phase:** Phase 2

## What Changes for the Operator

Operators can publish versioned application forms, accept submissions against the current form for a scope, and route each application into an exclusive reviewer-ownership flow with durable reasons on final decisions. Applicants and reviewers stop relying on shared dashboards or Discord-only coordination to know who is handling what.

## Justification Chain

**Market signal:** Application-tool research shows reviewer collision prevention is essentially absent and waitlists plus required decision reasons remain rare.
**Problem axis:** §2 — Structured Intake and Adjudication
**Proposal mechanism:** proposal.md, Intake and Adjudication; Operational Workflows -> Application Intake
**Philosophy principles:** Principle 1: Operator Clarity, Principle 9: Volunteer-Aware Design, Principle 10: Durable State over Ephemeral State

## Technical Specification

**Schema objects:**
- FormDefinition: `name`, `target_type`, `fields`, `routing_rules`, `version`, `status`
- Application: `applicant_id`, `form_definition_id`, `form_version`, `target_scope`, `responses`, lifecycle `state`, `decision_reason`, `version`
- ApplicationReview: `application_id`, `reviewer_id`, `action`, `notes`, `timestamp`

**API endpoints:**
- POST /api/v1/application-forms -> FormDefinitionRead
- GET /api/v1/application-forms/current?scope_kind={kind}&scope_id={id} -> FormDefinitionRead
- POST /api/v1/applications -> ApplicationRead
- POST /api/v1/applications/{application_id}/transitions -> ApplicationRead
- handler: submit_application(command: ApplicationSubmissionCommand) -> ApplicationSubmissionResult
- handler: review_application(command: ApplicationReviewCommand) -> ApplicationReviewResult

**Discord interactions:**
- application submission command forwards form responses to the API and returns the created application ID
- review commands forward claim/approve/deny actions and post one outcome summary after API success

**State transitions:**
- submitted -> queued -> claimed -> in_review -> approved/denied
- any pre-decision state -> withdrawn

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-021 | Form Definition Version API | `services/api/app/contracts/applications.py` | migrations/versions/wu-021_forms.py, services/api/app/contracts/applications.py, services/api/app/repositories/forms.py, services/api/app/services/forms.py, services/api/app/api/v1/endpoints/applications/forms.py, services/api/tests/test_forms.py |
| WU-022 | Application Submission And Reviewer Ownership API | `services/api/app/contracts/applications.py` | migrations/versions/wu-022_applications.py, services/api/app/contracts/applications.py, services/api/app/repositories/applications.py, services/api/app/services/applications.py, services/api/app/api/v1/endpoints/applications/lifecycle.py, services/api/tests/test_applications.py |
| WU-023a | Discord Application Submission Flow | `services/discord/app/contracts/application_submission.py` | services/discord/app/contracts/application_submission.py, services/discord/app/commands/application_submission.py, services/discord/app/handlers/application_submission.py, services/discord/tests/test_application_submission.py |
| WU-023b | Discord Application Review Flow | `services/discord/app/contracts/application_review.py` | services/discord/app/contracts/application_review.py, services/discord/app/commands/application_review.py, services/discord/app/handlers/application_review.py, services/discord/tests/test_application_review.py |

## Dependencies

**Upstream slices:** SLICE-007, SLICE-008, SLICE-009, SLICE-010
**Foundation dependencies:** SLICE-005, SLICE-006
**Parallelizable with:** SLICE-011, SLICE-013, SLICE-014, SLICE-015, SLICE-016

## Acceptance Criteria

- [ ] Publishing a form definition creates or advances the scope-local form version and current-form lookup returns the latest effective version.
- [ ] Submitting an application creates submitted state and routes it to queued automatically.
- [ ] Exactly one reviewer can claim a queued application; a concurrent second claim returns 409 Conflict.
- [ ] Discord submission and review flows remain API-backed and do not create duplicate review state or duplicate decision messages when API conflicts occur.

## Engineering Notes

**Effort:** VS-006 -> M-L (leans M)
**Prototyping:** VS-006 -> no
**Risk:** Medium — reviewer-collision correctness and form-version pinning matter directly for intake credibility and later appeal reconstruction.
**Existing code:** Preserved `forms/` material is hookpoint input only; the approved implementation surface is the API/Discord shell and Phase 1 governance substrate.
**Known challenges:** Keeping reviewer ownership single-writer safe while preserving thin Discord handlers and immutable form-version semantics.
