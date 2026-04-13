# Proposal: `daemon/applications.py`

Date: 2026-04-13

## Goal

Define the design for `daemon/applications.py` as the Humility daemon's
application-flow module.

This proposal is design only. It does not include implementation code.

## Summary

`daemon/applications.py` should own the Discord interaction surface for
chapter applications:

- register the guild-scoped `/apply` slash command
- render form steps from `daemon.config`
- collect answers across modal and follow-up interaction steps
- persist finalized submissions in SQLite
- post a review message in the chapter applications queue
- create a separate private review thread
- attach a persistent 4-button review view for staff actions

The module should consume `FormConfig.steps` exactly as provided by
`daemon.config`. It should not repack questions or rewrite step order.
That matters because the current planner groups modal steps first and
follow-up select steps after them, while future config work may change
that packing independently.

The module should treat SQLite as the source of truth for review state
and treat in-progress applicant sessions as ephemeral in-memory state.
Review actions must survive bot restarts; unfinished applicant drafts do
not.

## Design Rules

- `setup_applications(bot)` is the only public registration hook.
- `/apply` must be guild-scoped to Humility's configured guild.
- blacklist rejection happens before any modal is opened
- duplicate-submission rejection happens after blacklist check and
  before any modal is opened
- modal-opening interactions must do only cheap local work before
  calling `send_modal()` so the initial response stays within 3 seconds
- `ApplicationModal` must support up to 5 components and respect modal
  title and `custom_id` length limits
- follow-up interaction steps use ephemeral views, not persistent views
- review actions use persistent views with `timeout=None` and explicit
  `custom_id`s
- private review threads are created with
  `TextChannel.create_thread(message=None)`, not off the queue message
- `_create_review_thread(...)` must pass `invitable=False`
- every review callback re-reads the submission row from SQLite instead
  of trusting view instance state
- every review callback must verify that `interaction.user` has the
  chapter's `officer_role_id`; unauthorized attempts are rejected
  ephemerally and logged
- `daemon.claim` owns private-thread membership reconciliation; this
  module only decides when to call it
- applicant draft sessions use a 15-minute TTL and lazy eviction before
  new session creation

## Module Structure

`daemon/applications.py` should expose these public symbols.

### `ApplicationModal`

Subclass of `discord.ui.Modal`.

Responsibilities:

- render one `FormStepConfig` with `kind == "modal"`
- accept the step as configured rather than assuming text-only content
- build modal components from the step questions
- on submit, validate and normalize answers for that step
- advance the applicant session to the next step or finalize the
  submission

Recommended constructor shape:

- `bot`
- `chapter: ChapterConfig`
- `form: FormConfig`
- `session_id: str`
- `step_index: int`

Design notes:

- the constructor should fail fast if the requested step is not a modal
  step
- the modal title should use a deterministic short format such as
  `<chapter display> (<step>/<total>)`, truncated safely to 45 chars
- the modal `custom_id` should include a compact opaque session token
  and step index so stale submissions can be rejected cleanly while
  staying under the 100-character limit

### `ApplicationReviewView`

Subclass of `discord.ui.View`.

Constructor:

- `ApplicationReviewView(submission_id: int)`

Required behavior:

- `timeout=None`
- exactly 4 button children
- labels, order, and custom IDs:
  - `Claim` -> `app:claim:<id>`
  - `Interview` -> `app:interview:<id>`
  - `Approve` -> `app:approve:<id>`
  - `Deny` -> `app:deny:<id>`

Design notes:

- the view should stay stateless apart from `submission_id`
- button enabled/disabled state should not be trusted for correctness;
  callbacks must check the DB row each time
- keeping exactly 4 direct button children satisfies the smoke test and
  keeps restart hydration simple

### `setup_applications(bot)`

Responsibilities:

- register the guild-scoped `/apply` slash command
- register persistent review views during `setup_hook`
- attach any module-local runtime state needed for in-progress
  application sessions

Startup behavior:

1. Register `/apply`.
2. Query SQLite for active submissions whose review buttons should still
   work after restart.
3. Call `bot.add_view(ApplicationReviewView(submission_id=submission_id))`
   once per active submission ID.

Recommended active statuses:

- `pending`
- `claimed`
- `interview`

This per-submission hydration is acceptable for Humility's scale,
matches the required `ApplicationReviewView(submission_id)` API, and
should use `db.load_active_submission_ids(conn)` rather than
module-local SQL.

## Internal Types And Helpers

The module should keep the rest of its surface private.

### Internal dataclasses

`ApplicationSessionState`

- `session_id: str`
- `chapter_slug: str`
- `applicant_id: int`
- `current_step_index: int`
- `answers_by_question_id: dict[str, object]`
- `created_at` / `updated_at`

Purpose:

- hold in-progress answers between modal submits and follow-up steps
- invalidate stale component clicks by checking `session_id`
- allow one active draft per `(applicant_id, chapter_slug)` in memory
- support 15-minute TTL expiry using `updated_at`

### Internal views and modals

`_ApplicationFollowupView`

- ephemeral, non-persistent
- renders one `followup_selects` step as select menus plus a submit or
  continue button

`_ContinueApplicationView`

- ephemeral, non-persistent
- used when the next configured step is another modal, since a
  `MODAL_SUBMIT` interaction cannot directly respond with another modal

`_DecisionReasonModal`

- internal modal for denial reason capture
- opened from the `Deny` button, not from a modal submit

### Internal helpers

- `_find_chapter(bot, slug)`
- `_evict_expired_sessions(now)`
- `_begin_application_session(...)`
- `_get_session(session_id)`
- `_store_step_answers(...)`
- `_advance_session(...)`
- `_render_queue_embed(...)`
- `_create_review_thread(...)`
- `_fetch_handler_members(...)`
- `_user_has_officer_role(...)`
- `_edit_decided_queue_message(...)`
- `_notify_applicant(...)`

These remain private because they are workflow plumbing, not reusable
cross-module contracts.

### Required `db.py` helper contracts

`daemon/applications.py` should not issue raw SQL. It should call
`daemon.db` helpers for all submission writes and active-submission
lookups.

Required signatures:

- `create_submission(...) -> int`
- `update_submission_refs(conn, submission_id, *, queue_message_id, queue_channel_id, thread_id) -> None`
- `transition_submission_status(conn, submission_id, from_status, to_status, **kwargs) -> bool`
- `load_active_submission_ids(conn) -> list[int]`
- `has_active_submission(conn, applicant_id, chapter_slug) -> bool`

Contract notes:

- `create_submission(...)` returns the inserted submission row ID via
  `cursor.lastrowid`
- `transition_submission_status(...)` must perform a single atomic
  conditional `UPDATE ... WHERE id = ? AND status IN (...)` and return
  `True` only when `cursor.rowcount == 1`
- `has_active_submission(...)` checks for statuses
  `pending|claimed|interview`

## Interaction Flow

```text
Applicant
  |
  | /apply chapter:<slug>
  v
setup_applications-registered command
  |
  |-- chapter lookup from bot.config
  |-- blacklist lookup from SQLite
  |-- active-submission lookup from SQLite
  |-- if active exists -----------> ephemeral reject
  |-- begin in-memory session
  v
first step dispatch
  |
  |-- if step.kind == modal -----------> send ApplicationModal
  |-- if step.kind == followup_selects -> send ephemeral follow-up view
  v
step submit
  |
  |-- validate and store step answers
  |-- if more steps:
  |     |-- next is modal -----------> send ephemeral Continue button
  |     |-- next is followup_selects -> send ephemeral follow-up view
  |
  |-- if last step:
  |     |-- normalize answers back into form question order
  |     |-- insert submission row via db.create_submission() -> id
  |     |-- post queue review message with ApplicationReviewView
  |     |-- create private thread on applications channel
  |     |-- add requester + handler members via ensure_preclaim_visibility
  |     |-- update submission row with message/thread refs via db.update_submission_refs()
  |     '-- ephemeral applicant confirmation
  v
Review queue
  |
  |-- Claim -----> officer-role guard -> guarded DB transition -> execute_claim_visibility
  |-- Interview -> officer-role guard -> guarded DB transition -> queue/thread update
  |-- Approve ---> officer-role guard -> guarded DB transition -> queue cleanup -> notify applicant -> archive thread
  '-- Deny ------> officer-role guard -> open reason modal -> guarded DB transition -> queue cleanup -> notify applicant -> archive thread
```

## Data Flow

### 1. Config to interaction state

Input sources:

- `bot.config.chapters`
- `ChapterConfig.form`
- `FormConfig.steps`
- `FormConfig.questions`

The module should use `form.steps` to drive the applicant interaction
sequence, but use `form.questions` to reconstruct the final answer set
in original source order.

That distinction matters because the current step planner reorders
questions into grouped modal and follow-up-select steps. Staff should
review answers in the form's authored order, not the transport order.

### 2. Interaction state to normalized answers

Per-question normalization:

- `short`, `long`, `number` -> stored as strings after validation
- `select` -> stored as a single selected option string
- `multi_select` -> stored as an ordered list of selected option strings

Server-side validation should still run even when Discord components
already constrain input:

- required questions must have values
- `number` questions must parse as numeric
- selected values must exist in the configured options list

### 3. Normalized answers to SQLite

The finalized submission should be written before queue/thread side
effects so the application is not lost if Discord API work fails later.

Recommended stored shape for `answers_json`:

- a JSON object containing form metadata and a list of ordered answers
- each answer entry includes question `id`, `label`, `type`, and
  normalized `value`

Example shape:

```json
{
  "form_id": "dark-nemesis",
  "chapter_slug": "dark-nemesis",
  "answers": [
    {"id": "in_game_name", "label": "...", "type": "short", "value": "Nes"},
    {"id": "timezone", "label": "...", "type": "select", "value": "UTC-08:00"}
  ]
}
```

The applications module should extend `daemon.db` so submission writes
and lookups stay centralized there.

Required helper signatures:

- `create_submission(...) -> int`
- `update_submission_refs(conn, submission_id, *, queue_message_id, queue_channel_id, thread_id) -> None`
- `transition_submission_status(conn, submission_id, from_status, to_status, **kwargs) -> bool`
- `load_active_submission_ids(conn) -> list[int]`
- `has_active_submission(conn, applicant_id, chapter_slug) -> bool`

`create_submission(...)` returns the inserted row ID via
`cursor.lastrowid`, and the ref/status helpers write back queue and
review state after Discord resources exist. `applications.py` should
never perform submission SQL directly.

### 4. SQLite to review queue message

The queue message is the public staff-facing summary.

It should contain:

- applicant mention and ID
- chapter display name
- submission ID
- status
- ordered answers
- attached `ApplicationReviewView(submission_id)`

The message should be derivable from DB state plus config so it can be
rebuilt or reinterpreted after restart.

### 5. Queue message to private review thread

After the queue message posts:

1. Create a private thread from the applications queue channel with
   `message=None` and `invitable=False`.
2. Name it from chapter slug, applicant name, and submission ID using a
   compact deterministic format.
3. Call `ensure_preclaim_visibility(thread, requester, handler_members)`.
4. Persist `queue_message_id`, `queue_channel_id`, and `thread_id` via
   `db.update_submission_refs(...)`.

The queue message and the private thread are related through the
submission row, not through Discord's "thread off message" linkage.

### 6. Review actions back to DB and Discord

Each review button callback should:

1. Parse `submission_id` from `custom_id`.
2. Re-fetch the submission row.
3. Check that `interaction.user` has the chapter's `officer_role_id`.
4. Perform a guarded status transition in SQLite.
5. Apply Discord side effects only if the transition succeeded.
6. Acknowledge stale or already-processed actions ephemerally.

This keeps the DB authoritative when multiple reviewers click buttons at
nearly the same time or when the bot restarts between steps.

## Review State Machine

Recommended application states:

- `pending`
- `claimed`
- `interview`
- `approved`
- `denied`

Recommended transitions:

- `pending -> claimed`
- `pending -> interview`
- `claimed -> interview`
- `pending|claimed|interview -> approved`
- `pending|claimed|interview -> denied`

Rejected transitions should produce a short ephemeral response such as
"This submission has already been decided."

`Claim` should be concurrency-safe. The guarded update should only
succeed when the row is still claimable. This is more important than the
visual state of the button on the queue message.

Authorization should be defense in depth, not queue-channel-only. Each
review callback should reject users who do not hold the chapter's
`officer_role_id`, respond ephemerally, and log the failed attempt with
submission ID, chapter slug, and actor ID.

After `approved` or `denied`, the queue message should be edited to
reflect the terminal result:

- update the embed status/decision fields
- disable all 4 review buttons on the message
- keep the message in place as the canonical reviewer-facing record

## Error Handling Strategy

### Immediate-response paths

These interactions must answer immediately without deferring:

- `/apply` when opening the first modal
- a continue button when opening a later modal
- the `Deny` button when opening a denial-reason modal

Those code paths should do only:

- cheap config lookup
- cheap in-memory session lookup or eviction
- cheap SQLite blacklist or submission lookup
- `send_modal()`

### Deferred paths

These interactions should defer as soon as possible:

- modal submit that will not open another modal
- follow-up select submission
- `Claim`
- `Interview`
- `Approve`
- denial-reason modal submit

After deferral, the module can safely do DB writes, queue-message edits,
thread creation or archival, membership reconciliation, and applicant
notifications.

### Validation failures

Validation failures are user errors, not operator errors.

Behavior:

- respond ephemerally with the specific invalid field or stale-step
  problem
- keep the session alive when correction is possible
- require `/apply` restart only when the session token is stale or the
  bot restarted mid-flow
- reject duplicate active submissions ephemerally before opening the
  first modal

### Discord API failures

Operational Discord failures include:

- `discord.Forbidden`
- `discord.HTTPException`
- `discord.NotFound`

Handling policy:

- do not silently swallow them
- keep the already-written submission row when persistence succeeded
- respond to the applicant or reviewer with a short generic failure
  message
- leave enough DB state behind for manual recovery
- log unauthorized review-action attempts before rejecting them

### Partial-failure policy

The hardest failure mode is:

1. submission row inserted
2. queue message succeeds or partially succeeds
3. thread creation or later update fails

The module should prefer recoverable partial state over losing the
application entirely.

Concretely:

- insert first
- write message/thread references as each resource succeeds
- never delete the row just because the Discord handoff failed
- report the failure so staff can repair from the DB-backed submission

### Restart behavior

Supported after restart:

- review button callbacks on active submissions
- interpretation of stored answers
- queue message actions driven from DB state

Not supported after restart:

- applicant draft recovery for unfinished multi-step forms

If a restart interrupts an applicant mid-flow, the module should reject
stale session clicks and require the user to run `/apply` again.

Applicant sessions should expire after 15 minutes of inactivity, matching
the practical lifetime of Discord interaction tokens. The module should
evict expired sessions lazily before inserting a new session entry.

## Anti-scope

`daemon/applications.py` should not do these jobs.

- rewriting `daemon.config._build_steps()` or changing form packing
- persisting in-progress applicant drafts across restarts
- building a generic workflow engine for every future interaction flow
- chapter provisioning or queue-channel creation
- blacklist mutation commands
- analytics, reporting, or reviewer dashboards
- background retry workers for failed queue or thread handoff
- full permission-policy derivation outside normal Discord channel
  visibility
- message-thread linkage tricks that Discord does not support for
  private threads
- automatic approval side-effect policy beyond clearly defined existing
  chapter metadata

That last point matters because the current config surface does not yet
encode a rich `on_accept` policy. The module may reserve a small
internal hook for approval side effects, but it should not invent a new
configuration language in this partition.

## Tradeoffs And Alternatives

### Persistent view per active submission vs generic dynamic-item routing

Chosen:

- hydrate one `ApplicationReviewView(submission_id)` per active
  submission with `bot.add_view()`

Why:

- matches the required public API exactly
- keeps button construction simple and explicit
- Humility's expected active-submission count is small

Alternative:

- use `discord.ui.DynamicItem` or a custom router keyed only by
  `custom_id`

Why not now:

- more abstraction than the current scope needs
- does not help the smoke-test requirement around
  `ApplicationReviewView`

### In-memory applicant sessions vs DB-backed drafts

Chosen:

- in-memory sessions only

Why:

- simpler lifecycle
- no extra schema
- restart-safe review flow is more important than restart-safe drafts

Alternative:

- persist unfinished steps in SQLite

Why not now:

- adds schema, cleanup, expiry, and reconciliation work
- unnecessary for a low-volume guild flow

### Insert submission before Discord side effects vs after queue/thread creation

Chosen:

- insert first

Why:

- avoids losing an application when Discord API work fails
- gives a canonical `submission_id` for queue-button custom IDs

Alternative:

- create queue resources first, insert DB row last

Why not:

- risks losing the submission if the process dies mid-handoff
- makes it harder to build required review-button custom IDs

### Consume config steps as-is vs repack in applications.py

Chosen:

- consume `form.steps` exactly as emitted by `daemon.config`

Why:

- keeps responsibilities clean
- avoids duplicating or contradicting config-planner logic
- lets config evolve independently

Alternative:

- applications module reorders questions to pack selects into modals

Why not:

- violates the current boundary between config planning and interaction
  execution
- creates two competing planners

### Ambient channel permissions vs explicit reviewer-role checks in the module

Chosen:

- require both normal queue-channel visibility and an explicit
  `officer_role_id` check in every review callback

Why:

- keeps Discord permissions as the primary boundary
- adds cheap defense in depth against channel misconfiguration
- uses chapter metadata the bot already has locally

Alternative:

- rely only on ambient channel permissions

Why not now:

- it leaves review actions exposed if queue permissions drift
- the incremental code-level check is small and does not require a new
  policy model

## Decision

Design `daemon/applications.py` as the interaction and orchestration
boundary for chapter applications: start with `/apply`, collect answers
through configured steps, persist finalized submissions before Discord
handoff, create a queue message plus separate private review thread, and
drive restart-safe staff actions through `ApplicationReviewView`.

Keep review state authoritative in SQLite, keep applicant draft state
ephemeral, consume `FormConfig.steps` as-is, and avoid pulling planner,
provisioning, or broad approval-policy concerns into this module.

## Risk Revisions

This revision addresses all MEDIUM findings from the audit and shortcut
reviews without expanding scope.

- Private review threads now explicitly require
  `_create_review_thread(..., invitable=False)` so applicants cannot
  invite extra members into staff discussion.
- Review callbacks now require a chapter `officer_role_id` check in
  each action path, with ephemeral rejection and logging on failure, to
  add defense in depth beyond channel visibility.
- Submission persistence is now explicitly routed through `daemon.db`
  helper contracts, including `create_submission(...) -> int`,
  `update_submission_refs(...)`,
  `transition_submission_status(...) -> bool`,
  `load_active_submission_ids(...) -> list[int]`, and
  `has_active_submission(...) -> bool`, so `applications.py` does not
  grow an ad-hoc SQL layer.
- `/apply` now checks `has_active_submission(...)` after the blacklist
  lookup and rejects duplicate active applications before any modal is
  opened.
- In-memory applicant sessions now have a 15-minute TTL with lazy
  eviction before new session creation, bounding abandoned draft state.
- Terminal review actions now require queue-message cleanup: edit the
  embed to show the final decision result and disable all buttons so
  decided submissions no longer look actionable.
