# SLICE-021: Application interview and waitlist handling

## Parent

**Initiative:** INIT-004 — Structured Intake
**Phase:** Phase 3

## What Changes for the Operator

Operators can request an interview thread, waitlist an application, and later reactivate it without pushing the process into untracked DMs or ad hoc notes. Applicants see one durable application lifecycle rather than separate side-channel coordination.

## Justification Chain

**Market signal:** Application research explicitly calls out missing waitlists and structured interview handling across the reviewed market.
**Problem axis:** §2 — Structured Intake and Adjudication
**Proposal mechanism:** proposal.md, Intake and Adjudication -> Application state machine extensions
**Philosophy principles:** Principle 1: Operator Clarity, Principle 8: Platform-Native Interaction, Principle 9: Volunteer-Aware Design

## Technical Specification

**Schema objects:**
- Application: extended states `interview` and `waitlisted` plus thread linkage
- ApplicationReview: review actions extended with request_interview and waitlist semantics

**API endpoints:**
- POST /api/v1/applications/{application_id}/interview -> ApplicationRead
- POST /api/v1/applications/{application_id}/waitlist -> ApplicationRead
- POST /api/v1/applications/{application_id}/reactivate -> ApplicationRead
- handler: handle_interview(command: InterviewCommand) -> InterviewResultRead
- handler: handle_waitlist(command: WaitlistCommand) -> WaitlistResultRead

**Discord interactions:**
- interview command provisions or reuses a private Discord thread and sends the thread ID to the API
- waitlist command posts one applicant-facing status update and reuses the existing review thread on reactivation

**State transitions:**
- in_review -> interview
- in_review/interview -> waitlisted
- waitlisted -> claimed

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-035 | Application Interview And Waitlist API | `services/api/app/contracts/applications.py` | services/api/app/contracts/applications.py, services/api/app/services/applications.py, services/api/app/api/v1/endpoints/applications/interviews.py, services/api/tests/test_application_interviews.py |
| WU-036a | Discord Interview Thread Flow | `services/discord/app/contracts/application_interview.py` | services/discord/app/contracts/application_interview.py, services/discord/app/handlers/application_interview.py, services/discord/app/commands/application_interview.py, services/discord/tests/test_application_interview.py |
| WU-036b | Discord Waitlist Flow | `services/discord/app/contracts/application_waitlist.py` | services/discord/app/contracts/application_waitlist.py, services/discord/app/handlers/application_waitlist.py, services/discord/app/commands/application_waitlist.py, services/discord/tests/test_application_waitlist.py |

## Dependencies

**Upstream slices:** SLICE-012, SLICE-015
**Foundation dependencies:** SLICE-005, SLICE-006
**Parallelizable with:** SLICE-018, SLICE-019, SLICE-020

## Acceptance Criteria

- [ ] Requesting an interview is valid only from in_review and returns interview state.
- [ ] Waitlist is valid only from in_review or interview and reactivate_waitlist returns claimed state with optimistic-locking protection.
- [ ] Repeating an interview request for the same application reuses the recorded thread instead of creating a duplicate.
- [ ] API conflicts or validation failures do not duplicate Discord status messages or create thread-local state divergence.

## Engineering Notes

**Effort:** VS-012 -> M
**Prototyping:** VS-012 -> no
**Risk:** Medium — this is a lifecycle extension on top of the intake substrate, with most risk concentrated in duplicate thread/state handling.
**Existing code:** Extends the application lifecycle API and the Discord runtime shell; no approved interview/waitlist surface exists yet.
**Known challenges:** Keeping interview and waitlist behavior within the same application state machine rather than branching into separate review systems.
