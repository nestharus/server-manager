# INIT-133B-iii problem map — messages + non-claim transitions

Source: BL-019D-β-iii. Final slice in the BL-019D-β family.

## What we're building

After β-i (queue + claim) and β-ii (detail + transcript,
read-only), β-iii adds **action surfaces** to the detail page:

1. **Message thread** — append messages to an application,
   choose visibility (`applicant_visible | officer_only`),
   see the result reflected in the transcript.
2. **Non-claim transitions** — drive an application through
   the full review state machine (claim is in β-i):
   - `route` (submitted → queued) — only relevant if officers
     are authoring queue-routing decisions; out of scope if
     queue routing happens automatically.
   - `review` (claimed → in_review)
   - `request_interview` (in_review → interview)
   - `waitlist` (in_review | interview → waitlisted)
   - `approve` (in_review | interview → approved)
   - `deny` (in_review | interview → denied)
   - `reactivate` (waitlisted → claimed)
   - `withdraw` (multiple → withdrawn) — typically applicant
     action, but officers may force-withdraw.
   - `reassign` (multiple → same state, different owner) —
     out of scope unless we want officer-driven reassign UI.

## Backend prerequisites

All exist:

- `POST /api/v1/applications/{id}/messages` (INIT-131
  application_messages substrate). Visibility +
  client_message_id idempotency. Authorization via
  `application.message` permission.
- `POST /api/v1/applications/{id}/transitions` — single
  endpoint covering all transitions; body has
  `action: ApplicationTransitionAction`. Optimistic locking
  via `If-Match` header.
- `services/api/app/services/applications.py` —
  `VALID_TRANSITIONS` table covers every transition the slice
  needs.

## Officer bridge prerequisites

β-i added `_build_officer_actor`, claim endpoint. β-ii added
detail + transcript endpoints. β-iii needs:

- **POST `/api/v1/web/officer/applications/{id}/messages`** —
  bridge to message append; reuses
  `_build_officer_actor`. Forwards body + visibility +
  client_message_id.
- **POST `/api/v1/web/officer/applications/{id}/transitions`** —
  generic transition bridge; reuses claim's pattern (body
  `{ action }`, `If-Match` header forwarded). Each transition
  through this single bridge.

OR per-action bridge endpoints (one per transition). The
single-endpoint design matches the existing direct API and
is simpler.

## SPA prerequisites

β-i + β-ii landed:
- TanStack Solid Router as entry.
- `ApplicationDetailRoute` at `/applications/{id}` with
  metadata + transcript panels.
- `client.ts` ApiError, applicationReadSchema,
  applicationTranscriptReadSchema.

β-iii needs:
- Message composer in detail page (textarea + visibility
  toggle + send button).
- Transition action buttons in detail page (one per valid
  transition for the current state).
- API client functions: `appendOfficerApplicationMessage`,
  `transitionOfficerApplication`.

## Open questions for the proposal

### Q1. Single transition endpoint or per-action endpoints?

Lock: **single `POST /transitions`** mirroring the direct
API. Simpler; one bridge endpoint covers all 8 actions.

### Q2. Which transitions does the officer UI expose?

Lock: every action except `claim` (β-i). Specifically expose:
- `route`, `review`, `request_interview`, `waitlist`,
  `approve`, `deny`, `reactivate`, `withdraw`.

`reassign` is out of scope for v1 — requires an owner-picker
UI.

### Q3. Action button visibility (state machine)

Each button visible only when the current state allows that
transition (per `VALID_TRANSITIONS`). The officer detail
page reads `application.state` and shows the valid set.

### Q4. Message composer

Plain textarea + visibility toggle (`applicant_visible` /
`officer_only`) + Send button. After successful append:
- Refetch transcript to show the new message inline.
- Clear the textarea.
- Generate a fresh `client_message_id` (UUID v4) for the
  next compose; preserve idempotency on the same compose.

### Q5. Optimistic locking for transitions

Same as claim: bridge sends `If-Match: "<version>"` derived
from `ApplicationRead.version`. After successful transition,
optimistic update with returned `ApplicationRead`, then
refetch detail + transcript.

Stale version → 412 → notice + refetch. Already-claimed →
409 → notice + refetch.

### Q6. Authorization

Each transition checks its specific permission via existing
`require_transition_authority`:
- `application.review` for `review`
- `application.approve` for `approve`
- `application.deny` for `deny`
- `application.waitlist` for `waitlist` and
  `request_interview` (if not separate)
- `application.reactivate` for `reactivate`
- `application.withdraw` for `withdraw`
- `application.reassign` for `reassign` (out of scope v1)

Bridge forwards via `transition_application`; unauthorized →
403 `authority_decision_denied`.

### Q7. Pomerium / routing

No new Pomerium routes. β-ii's `prefix:/applications/`
already covers detail. The new bridge endpoints fall under
β-i's `prefix:/api/web/officer/`.

### Q8. Anti-scope

Out of scope for β-iii:
- `reassign` (needs owner-picker UI).
- Discord-visible side effects on transitions (BL-009).
- Applicant DM materialization (BL-020).
- Bulk actions (multi-select queue → batch transition).
- Message editing / deletion / threading.
- Message attachments (files, images).
- Real-time updates (SSE/WebSocket).

## What the proposal must lock

1. Q1 single bridge endpoint design.
2. Q2 transition action set.
3. Q3 state machine UI (valid actions per state).
4. Q4 message composer behavior + idempotency.
5. Q5 If-Match flow.
6. Q6 authorization mapping.
7. Q8 anti-scope.

## Dependencies + sequencing

- β-i + β-ii prerequisites. Done.
- β-iii is the final β-slice; closes BL-019D-β.
- BL-009 (Discord-visible side effects) and BL-020 (DM
  materialization) consume β-iii's transition events.

## Diff budget

Estimate ~+700 / -50 net lines:
- Bridge: ~+80 (two new POST endpoints; transition is the
  bigger one).
- SPA: ~+400 (message composer + 8 transition buttons + state
  machine UI).
- Tests: ~+220 (API bridge + Playwright + e2e).
