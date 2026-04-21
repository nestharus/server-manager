# SLICE-021 Phase 2 Synthesis: Binding Decisions

These decisions are binding for the SLICE-021 proposal, hookpoint research,
tests, and implementation. The proposal may choose implementation mechanics
inside these boundaries, but it must not add lifecycle scope, create a parallel
application review system, or introduce compatibility paths around old behavior.

## Inputs

- `.pipeline/research.md`
- `product-strategy/tickets/SLICE-021.md`
- Shipped SLICE-012 application aggregate: existing `ApplicationState`,
  `VALID_TRANSITIONS`, optimistic locking, review ownership checks, and
  application review/audit persistence.

## Acceptance Criteria Reference

- **AC1**: Requesting an interview is valid only from `in_review` and returns
  `interview` state.
- **AC2**: Waitlist is valid only from `in_review` or `interview`, and
  reactivation returns `claimed` state with optimistic-locking protection.
- **AC3**: Repeating an interview request for the same application reuses the
  recorded thread instead of creating a duplicate.
- **AC4**: API conflicts or validation failures do not duplicate Discord status
  messages or create thread-local state divergence.

## Resolved Existing State

- SLICE-012 shipped the application aggregate with states `submitted`,
  `queued`, `claimed`, `in_review`, `approved`, `denied`, and `withdrawn`.
- SLICE-012 shipped transition ownership checks for reviewer-owned decision
  actions. SLICE-021 extends that rule to interview and waitlist behavior.
- Application mutations already require strong ETags/`If-Match` through the
  API layer and serialize aggregate updates through the service/repository
  mutation path.
- Current Alembic head for this worktree is `wu_042_chapter_governance`.
  SLICE-021 migrations must chain from that head.

## Binding Decisions

- **D1 - BINDING: Extended `ApplicationState` enum.**
  Extend the existing application state enum in place by adding `interview` and
  `waitlisted`.

  The full state vocabulary after SLICE-021 is:
  `submitted`, `queued`, `claimed`, `in_review`, `interview`, `waitlisted`,
  `approved`, `denied`, and `withdrawn`.

  Do not create a separate interview, waitlist, or review-status enum.

- **D2 - BINDING: Extended `VALID_TRANSITIONS`.**
  Extend the existing state machine in place with these edges:

  - `in_review -> interview` via action `request_interview`; `reason` is
    optional and `owner_id` is retained.
  - `in_review -> waitlisted` via action `waitlist`; `reason` is required.
  - `interview -> waitlisted` via action `waitlist`; `reason` is required.
  - `interview -> approved` via existing action `approve`; decision reason
    behavior remains the same as the SLICE-012 approval path.
  - `interview -> denied` via existing action `deny`; decision reason behavior
    remains the same as the SLICE-012 denial path.
  - `waitlisted -> claimed` via action `reactivate`; `new_owner_id` is
    optional.
  - `interview -> withdrawn` via existing action `withdraw`.
  - `waitlisted -> withdrawn` via existing action `withdraw`.

  Preserve all existing SLICE-012 transitions. Do not add `interview ->
  interview` or `waitlisted -> waitlisted` self-transitions.

- **D3 - BINDING: Migration `wu-035_application_interview.py`.**
  Add migration `wu-035_application_interview.py` chained onto current head
  `wu_042_chapter_governance`.

  The migration must:

  - Add `applications.interview_thread_id TEXT NULL`.
  - Replace the applications state CHECK so it includes `interview` and
    `waitlisted`.
  - Preserve the existing allowed application states and existing columns.

  No new table is required for interview or waitlist state.

- **D4 - BINDING: Dedicated API endpoints with optimistic locking.**
  Add dedicated endpoints:

  - `POST /api/v1/applications/{application_id}/interview`
  - `POST /api/v1/applications/{application_id}/waitlist`
  - `POST /api/v1/applications/{application_id}/reactivate`

  All three require `If-Match`, use the existing strong ETag parser, and return
  `ApplicationRead` with a fresh ETag after a successful mutation or idempotent
  interview reuse.

  Do not rely on Discord-local state as the source of truth for these lifecycle
  changes.

- **D5 - BINDING: Interview thread idempotency.**
  Interview thread linkage is stored on `applications.interview_thread_id`.

  Idempotency rules:

  - If `interview_thread_id` is null and the request supplies `thread_id`,
    store it while transitioning to `interview`.
  - If `interview_thread_id` is already set and equals the requested
    `thread_id`, return `200` with the current application and do not create a
    second state transition.
  - If `interview_thread_id` is already set and differs from the requested
    `thread_id`, return `409 Conflict`.
  - If the application is already in `interview` with the same stored thread,
    treat the request as the same idempotent no-op, not as a state-machine
    self-transition.

  AC traceability: this is the required duplicate-thread guard for AC3 and AC4.

- **D6 - BINDING: Waitlist idempotency uses the state machine.**
  Waitlist has no special idempotent no-op behavior. If an application is
  already `waitlisted`, another waitlist request must fail as a `409` invalid
  transition.

  `waitlist` requires a non-blank reason for both source states:
  `in_review` and `interview`.

- **D7 - BINDING: Ownership and authority rules.**
  Interview and waitlist actions require the same owner check as review,
  approve, and deny:

  ```text
  actor.actor_id == current.owner_id
  ```

  Reactivation is an ownership handoff. It requires `application.reactivate` at
  the application target scope, but it does not require the actor to be the
  current owner.

  If `new_owner_id` is supplied during reactivation, set `owner_id` to that
  member. If it is omitted, retain the existing `owner_id`.

- **D8 - BINDING: Request contracts.**
  Add these contracts in `services/api/app/contracts/applications.py`:

  ```text
  ApplicationInterviewRequest
    thread_id: str | None = None
    reason: str | None = None

  ApplicationWaitlistRequest
    reason: str

  ApplicationReactivateRequest
    new_owner_id: UUID | None = None
  ```

  Reject blank `thread_id`, blank `reason`, and blank optional reason strings
  when present.

  Extend the transition/review action vocabulary with
  `request_interview`, `waitlist`, and `reactivate`. The public interview
  endpoint maps to transition action `request_interview`.

- **D9 - BINDING: Audit names and state-change payloads.**
  Add action types:

  - `application.interview`
  - `application.waitlist`
  - `application.reactivate`

  Continue recording accepted lifecycle changes as
  `application.transitioned` state changes with `diff_json`.

  Diff/audit payloads must include the changed lifecycle fields relevant to the
  action: `state`, `owner_id`, `interview_thread_id`, timestamps, and
  reason/decision notes when supplied.

- **D10 - BINDING: Discord work units.**
  WU-036a adds `/apply-interview`.

  Required flow:

  - Resolve the actor to a member.
  - GET the application and ETag.
  - Create or reuse the Discord interview thread.
  - POST `/interview` with `thread_id` and `If-Match`.
  - Only send Discord-visible outcome/status messages after API success.

  WU-036b adds `/apply-waitlist` and `/apply-reactivate`.

  Required flow:

  - Use the API as the source of truth for all lifecycle mutations.
  - Use `If-Match` for both commands.
  - Avoid duplicate Discord status messages on API conflicts or validation
    failures.

- **D11 - BINDING: Service extension shape.**
  Extend the existing `transition_application` service path rather than
  creating separate lifecycle services.

  The single handler may branch on action name for:

  - optional interview reason and thread handling;
  - required waitlist reason;
  - reactivate owner handoff;
  - owner-only checks for `request_interview` and `waitlist`.

  Keep transition validation centralized through `VALID_TRANSITIONS`.

- **D12 - BINDING: Repository and review action enum.**
  Extend `application_reviews` action constraints and repository behavior to
  include:

  - `request_interview`
  - `waitlist`
  - `reactivate`

  Persist these actions through the existing review table and expose them
  through existing review read contracts where applicable.

  Repository reads/writes for applications must include
  `interview_thread_id`, and `ApplicationRead` must expose the stored value so
  Discord can reuse a prior thread.

- **D13 - BINDING: Migration chain.**
  The SLICE-021 migration chain starts from current head
  `wu_042_chapter_governance`.

  Do not create a detached migration head. Do not rewrite prior shipped
  migrations.

## Proposal Constraints

- Keep interview and waitlist behavior inside the application aggregate.
- Do not introduce backwards-compatibility aliases for action names.
- Do not create Discord-only lifecycle state.
- Do not create a separate waitlist table, interview table, or review system in
  this slice.
- Do not make visible Discord mutations during API tests; Discord behavior
  belongs behind handler mocks/fixtures until explicitly executed by an
  approved runtime command.
