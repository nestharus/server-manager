# Proposal 10 — INIT-131 / BL-019B: application_messages substrate

## Goal

Per-application reviewer↔applicant messaging with visibility
levels (applicant_visible / officer_only). Mirrors the shape of
`ticket_messages` (WU-025C) since the substrate semantics are
identical: a parent aggregate with sequenced messages, an
"author identity" check that splits into a "primary party"
(applicant ≡ ticket reporter) and a "staff" (officer ≡ ticket
staff) path, with an idempotent client_message_id.

Why a separate substrate (not `ticket_messages` re-use): ticket
lifecycle (categories, SLA, owner reassignment under separate
permissions) does not apply to applications and would pollute
ticket queries with applications. Cloning the pattern keeps the
two surfaces semantically clean.

## Q1..Q7 — locked decisions

**Q1.** Visibility values: `applicant_visible` and `officer_only`.
(Mirrors `reporter_visible` / `staff_only`.)

**Q2.** Authorization model:
- Applicant identity is `members.id` referenced by
  `applications.applicant_id` (post-INIT-128, always
  `kind='discord'`).
- Applicant can:
  - read `applicant_visible` messages
  - append messages with `visibility='applicant_visible'`
- Officer permission: a single `application.message` permission.
  An actor with `application.message` at the application's
  target_scope can:
  - read both `applicant_visible` AND `officer_only` messages
  - append messages with EITHER visibility
- All other actors: 403.

Officer chapter-scope isolation is inherited from existing
authority infrastructure (grant scope_kind='chapter', scope_id=X).
INIT-131 declares `application.message` as the canonical
permission name; chapter admins grant it via the existing
`POST /api/v1/authority-grants` endpoint.

**Q3.** Schema: new table `application_messages` mirroring
`ticket_messages`:
- `id UUID PK`
- `application_id UUID NOT NULL FK applications(id) ON DELETE RESTRICT`
- `message_seq BIGINT NOT NULL`
- `author_actor_kind TEXT NOT NULL`
- `author_actor_id TEXT NOT NULL`
- `visibility TEXT NOT NULL CHECK IN ('applicant_visible', 'officer_only')`
- `body_markdown TEXT NOT NULL`
- `client_message_id TEXT NULL`
- `correlation_id UUID NOT NULL`
- `causation_id UUID NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `UNIQUE (application_id, message_seq)`
- partial unique index on `(application_id, client_message_id)`
  WHERE `client_message_id IS NOT NULL`

**Q4.** Endpoints (mounted at existing applications router):
- `POST /api/v1/applications/{application_id}/messages` →
  201 with `ApplicationMessageRead`. Idempotent on
  client_message_id.
- `GET /api/v1/applications/{application_id}/messages` →
  200 with `ApplicationMessageListRead`. Visibility filtered
  per actor identity.

**Q5.** Audit/correlation: every append participates in the
existing `AuditContext` (correlation_id + causation_id from
request middleware); messages link to that chain. No new
activity_action rows needed — message creation IS the
state-change record. (Tickets follow the same convention.)

**Q6.** Notification fanout: out of scope for INIT-131. Future
INIT can subscribe to message inserts and emit notification
events; the substrate is ready for that.

**Q7.** Retention: out of scope. Append-only; ON DELETE RESTRICT
prevents accidental loss. Future retention/redaction policy
lands as a separate slice if compliance demands it.

## Scope

- migration `wu-044_application_messages.py` adding the table +
  constraints + indices.
- `services/api/app/contracts/application_messages.py` with
  `ApplicationMessageVisibility`, `ApplicationMessageAppendRequest`,
  `ApplicationMessageRead`, `ApplicationMessageListRead`,
  `ApplicationMessageAppendForbiddenError`,
  `ApplicationMessageVisibilityError`.
- `services/api/app/repositories/application_messages.py`
  (mirror of `repositories/ticket_messages.py`).
- `services/api/app/services/application_messages.py`
  (mirror of `services/ticket_messages.py`).
- `services/api/app/api/v1/endpoints/applications/messages.py`
  with POST + GET routes; mounted in
  `app/api/v1/endpoints/applications/_init__.py` (the existing
  applications router aggregator).
- Tests:
  - unit tests for visibility rules (applicant cannot append
    officer_only; non-applicant non-officer cannot append at all)
  - idempotency on client_message_id
  - chapter-scope officer permission isolation (officer at chapter
    A cannot append on application targeted at chapter B)
  - read-side visibility filtering for applicant vs officer

## Anti-scope

- No SPA UI. INIT-133 (BL-019D).
- No transcript merge with state changes. INIT-132 (BL-019C).
- No notification fanout. Future.
- No retention/redaction. Future.
- No real-time delivery. Future.
- No file attachments. Future.

## Net value

- Unblocks INIT-132 (transcript) which unblocks INIT-133 (SPA)
  which unblocks BL-009 (Discord embed posts) + BL-020 (DM
  materialization on submit).
- Replaces the legacy `interview_thread_id` Discord-thread field
  for new applications. (Existing rows keep their
  interview_thread_id for backwards compatibility; new flows
  point at `application_messages`.)

## Risk gates (self-review, all LOW)

### Audit (LOW)
No incident; this is greenfield substrate. Pattern is identical
to ticket_messages which has been live since WU-025C.

### Scope (LOW)
Bounded to one migration, one contract module, one repository,
one service, one endpoint module, and corresponding tests. No
edits to existing application service code; the lifecycle stays
unchanged.

### Shortcut (LOW)
- Not adding notification fanout: deferred explicitly. The schema
  preserves correlation_id so future fanout has the join key.
- Not adding retention: deferred explicitly. Append-only design +
  ON DELETE RESTRICT means no data loss occurs in the meantime.
- Reusing the `ticket_messages` pattern instead of building a
  generic "messages" abstraction: deliberate. Two consumers do
  not warrant abstraction.

### Supported-surface (LOW)
- HTTP: net-new routes; no existing route changes.
- DB: net-new table; no existing schema change.
- Permissions: net-new `application.message` permission. Chapter
  admins can already grant it via the existing authority flow.
- Existing `interview_thread_id` field unchanged.

## Diff budget

~600 lines net add (migration, contracts, repo, service,
endpoint, tests). No deletions.
