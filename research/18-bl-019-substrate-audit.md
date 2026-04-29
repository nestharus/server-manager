# BL-019 substrate audit + decomposition

## Goal (per user-confirmed product direction in BACKLOG BL-009)

In-product application review surface so officers can:
- claim/assign applications from a queue
- exchange messages with the applicant per-application (not Discord)
- read a persisted transcript of the conversation
- decide approve/deny with the existing transitions

This unblocks BL-009 (Discord embed posts a link back to the
in-product page).

## What already exists (corrected from initial Explore agent report)

### Application lifecycle — substantial; already shipped
- `services/api/app/contracts/applications.py` defines
  `ApplicationState` (submitted | queued | claimed | in_review |
  interview | waitlisted | approved | denied | withdrawn),
  `ApplicationTransitionAction`, and `ApplicationReviewRead`.
- `services/api/app/services/applications.py:VALID_TRANSITIONS`
  encodes the state machine. Includes claim, reassign, review,
  request_interview, waitlist, approve, deny, withdraw,
  reactivate.
- `ApplicationRead.owner_id: UUID | None` already tracks the
  assigned reviewer.
- `ApplicationRead.interview_thread_id: str | None` exists as a
  pre-existing Discord-thread-id field (legacy from the
  Discord-driven flow). For the in-product surface this gets
  superseded by a per-application messaging substrate.
- Endpoints in `services/api/app/api/v1/endpoints/applications/`
  (lifecycle.py, transitions.py) already cover claim/reassign/
  review/approve/deny via authority-checked routes.

### Authority / chapter scope — substantial; already shipped
- `services/api/app/services/authority.py` supports grants at
  `scope_kind` ∈ {`global`, `chapter`, `member`}.
- Existing applications submit code uses
  `_require_submit_authority` against
  `permission='application.submit'` at the form's target scope.
- Existing application review code uses
  `application.review` permission at the form's target scope.
- `chapters` table and `chapter_roles` table both exist (with
  templates, ordinals, and triggers_succession).

### Ticket-messaging substrate — usable as the template, NOT to reuse
- `services/api/app/contracts/ticket_messages.py` defines
  `TicketMessageAppendRequest` / `TicketMessageRead` /
  `TicketMessageListRead` with:
  - `visibility: Literal["reporter_visible", "staff_only"]`
  - `body_markdown: str`
  - `author_actor_kind`, `author_actor_id`
  - `client_message_id` for idempotency
  - `message_seq` for ordering
  - `correlation_id`, `causation_id` for audit chain
- `services/api/app/services/ticket_messages.py` implements
  append + list with visibility gates.

The shape is ideal for officer↔applicant messaging. **Decision:**
clone the pattern as `application_messages` rather than
overloading tickets — ticket lifecycle (SLA, categorization,
incident workflow) doesn't apply to applications, and conflating
would pollute ticket queries with applications.

### Audit / transcript foundation — already shipped
- `activity_actions` + `activity_state_changes` are append-only
  per aggregate with `aggregate_seq` versioning. Reading them
  for a given `aggregate_id='application'` already produces a
  chronological transcript of state transitions.
- Adding application_messages and joining on correlation chain
  yields a complete transcript without additional retention
  framework. Retention compliance can land later if/when
  needed.

## What must be built for BL-019

| Need | Status | Slice |
|---|---|---|
| Officer permission set + chapter-scoped grant flow | Partial — `application.review` exists; need formalized officer-grant endpoint + chapter-admin role | INIT-130 (BL-019A) |
| Endpoint guards verifying chapter-scoped review permissions | Exists per endpoint; needs audit + officer-role wiring | INIT-130 (BL-019A) |
| `application_messages` table + service + endpoints | Missing | INIT-131 (BL-019B) |
| Transcript read endpoint (state changes + messages joined) | Missing | INIT-132 (BL-019C) |
| SPA officer review surface (queue, claim, message, decide) | Missing | INIT-133 (BL-019D) |

## Decomposition

### INIT-130 — BL-019A: Officer role + chapter-scoped review authority
**Scope**
- Define canonical officer permission set in code (constants in
  `app/contracts/authority.py` or similar): `application.review.read`,
  `application.review.assign`, `application.review.message`,
  `application.review.transition`.
- Audit existing application endpoints; align permission strings
  with the new canonical set.
- Add a chapter-admin grant flow: an admin (or another chapter
  admin) can grant the officer role to a member via an existing
  authority-grant endpoint — confirm that path works for
  `scope_kind='chapter'`.
- Tests: officer at chapter X can claim/transition apps targeted
  at X; cannot at chapter Y; non-officer at X gets 403.

**Out of scope**
- Messaging — INIT-131.
- SPA surface — INIT-133.

### INIT-131 — BL-019B: Application messages substrate
**Scope**
- New table `application_messages` (mirror `ticket_messages`):
  `id`, `application_id`, `message_seq`, `author_actor_kind`,
  `author_actor_id`, `visibility`
  (`applicant_visible`|`officer_only`), `body_markdown`,
  `client_message_id`, `correlation_id`, `causation_id`,
  `created_at`.
- New service `services/api/app/services/application_messages.py`:
  `append_application_message`, `list_application_messages` with
  visibility filtering.
- New endpoints
  `POST /api/v1/applications/{id}/messages` and
  `GET /api/v1/applications/{id}/messages`.
- Authorization:
  - Applicant (member identified by `applications.applicant_id`):
    can read `applicant_visible`, can append `applicant_visible`.
  - Officer (chapter-scoped `application.review.message` permission
    at the application's target scope): can read both, can append
    either visibility.

**Out of scope**
- SPA — INIT-133.
- Real-time delivery (poll-based fine for v1; WebSocket if
  needed later).

### INIT-132 — BL-019C: Transcript read endpoint
**Scope**
- New endpoint `GET /api/v1/applications/{id}/transcript` returns
  chronological merge of state changes + messages with author
  attribution and visibility filtering for the caller.
- Reuses existing `activity_state_changes` rows for the
  transitions and the new `application_messages` rows.

### INIT-133 — BL-019D: SPA officer review surface
**Scope**
- Routes: `/applications/queue` (officer queue), `/applications/{id}`
  (review page).
- Components: claim button, assign-to-officer dropdown, message
  thread (with visibility toggle for officers), transcript view,
  decision form (approve / deny / waitlist with reason).
- Auth state: respects existing Discord OAuth identity from
  receipt; identifies whether viewer is applicant or officer.

**Out of scope**
- Real-time updates.
- File attachments (if needed, future slice).

## Risk / dependency graph

```
INIT-130 (perms)
       ↓
INIT-131 (messages) ──┐
       ↓               │
INIT-132 (transcript) ─┤
                       ↓
                  INIT-133 (SPA)
                       ↓
                  BL-009 (Discord fan-out)
                  BL-020 (DM materialization)
```

INIT-131 and INIT-132 can run in either order after 130.
INIT-130 can land independently.
