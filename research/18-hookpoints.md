# Hookpoint Research: `daemon/applications.py`

Date: 2026-04-13

## Scope

This note maps the revised applications proposal in
`proposals/18-applications.md` onto the current repo.

It is hookpoint-only research:

- what `daemon/applications.py` can reuse directly
- what the module should call instead of re-implementing
- what must be added elsewhere first
- what current code or docs need to change

It does not include implementation code.

## 1. Config Hookpoints

### `DaemonConfig`

Direct hookpoint: `daemon/config.py:48-52`

- `DaemonConfig.chapters` is the main entry surface.
- `daemon.py:70-80` stores that object on `bot.config`, so
  `setup_applications(bot)` can chapter-lookup against the already-loaded
  config.
- `DaemonConfig.base_path` exists, but the revised proposal does not
  need it directly for the application flow.

Practical meaning:

- `/apply` needs `bot.config.chapters` to resolve the requested chapter.
- Review callbacks need the same chapter lookup to recover queue
  channel, form, and officer-role metadata from the submission row’s
  `chapter_slug`.

### `ChapterConfig`

Direct hookpoint: `daemon/config.py:54-67`

Fields the applications module directly needs:

- `slug` for chapter lookup and DB storage.
- `display_name` for modal titles, queue embeds, and thread naming.
- `officer_role_id` for the required per-callback authorization check.
- `applications_channel_id` for posting the review queue message and
  creating the private review thread in the correct channel.
- `form` as the handoff into the configured application form.

Fields that are adjacent but not clearly direct in this partition:

- `member_role_id`
- `applicant_role_id`

Those may matter for future approval side effects, but the revised
proposal explicitly avoids inventing a richer acceptance policy in this
partition. Current config has role IDs, but no `on_accept` policy
surface.

### `FormConfig`

Direct hookpoint: `daemon/config.py:69-76`

Fields the applications module directly needs:

- `id` for `submissions.form_id`.
- `title` for user-facing text and review rendering.
- `steps` for the runtime interaction sequence.
- `questions` for reconstructing the final stored answer order.

Fields not directly needed by the revised proposal:

- `source_path`

Important boundary:

- `proposals/18-applications.md:25-29` says `applications.py` must
  consume `FormConfig.steps` exactly as emitted by config and must not
  repack questions.
- The current planner in `daemon/config.py:514-531` groups all
  text/number questions into `modal` steps first, then all select
  questions into `followup_selects` steps. That planner already exists,
  so `applications.py` should treat it as input, not duplicate it.

### `FormStepConfig`

Direct hookpoint: `daemon/config.py:89-94`

Fields the applications module directly needs:

- `index` for session progress and stale-step rejection.
- `kind` to decide modal vs follow-up rendering.
- `questions` to render the actual components for that step.

This is the immediate input to:

- `ApplicationModal` for `kind == "modal"`
- `_ApplicationFollowupView` for `kind == "followup_selects"`

### `QuestionConfig`

Direct hookpoint: `daemon/config.py:78-86`

Fields the applications module directly needs:

- `id` for answer storage and normalization.
- `type` for choosing text input vs select handling and for validation.
- `label` for component labels and stored answer metadata.
- `required` for server-side validation.
- `max_length` for text/number modal inputs.
- `options` for select and multi-select validation/rendering.
- `source_index` for restoring authored question order when persisting
  the final answer payload.

Current reusable validation constraints already live in config:

- text/number questions require `max_length` and cap it at 4000
  (`daemon/config.py:331-348`, `daemon/config.py:470-477`)
- select questions require `options` and cap them at 25 entries
  (`daemon/config.py:349-366`, `daemon/config.py:480-511`)

## 2. DB Hookpoints

### Existing reusable surfaces

Schema hookpoint: `daemon/db.py:29-44`

The `submissions` table already has the fields the revised proposal
expects `applications.py` to persist and later re-read:

- identity and routing: `id`, `form_id`, `chapter_slug`, `applicant_id`
- lifecycle: `submitted_at`, `status`
- Discord refs: `queue_message_id`, `queue_channel_id`, `thread_id`
- review state: `claimer_id`, `decided_by`, `decided_at`,
  `decision_reason`
- finalized answers: `answers_json`

Blacklist hookpoint: `daemon/db.py:63-70`, `daemon/db.py:355-363`

- `get_blacklist_entry(...)` is already the direct pre-modal gate for
  `/apply`.

Submission lookup hookpoint: `daemon/db.py:245-246`

- `get_submission_by_id(...)` already fits the proposal’s rule that
  every review callback re-reads the row from SQLite instead of trusting
  view state.

Submission insert hookpoint: `daemon/db.py:178-243`

- `create_submission(...)` already centralizes row insertion.
- The current function writes the right columns, but it returns `None`.
- The revised proposal requires it to return the inserted row id so the
  queue message, thread, and persistent view can all key off a stable
  `submission_id`.

Connection ownership hookpoint: `daemon.py:95-110`

- The entry point opens one SQLite connection and stores it on
  `bot.conn` (`daemon.py:72-80`), which is the connection surface
  `applications.py` would use.

### Missing helpers the proposal now requires

These do not exist yet in `daemon/db.py` and are explicit new hookpoints
for this partition:

- `update_submission_refs(conn, submission_id, *, queue_message_id, queue_channel_id, thread_id) -> None`
- `transition_submission_status(conn, submission_id, from_status, to_status, **kwargs) -> bool`
- `load_active_submission_ids(conn) -> list[int]`
- `has_active_submission(conn, applicant_id, chapter_slug) -> bool`

Why each one matters:

- `update_submission_refs(...)`
  Needed after the queue message and private thread succeed so the row
  can persist those Discord object IDs without raw SQL in
  `applications.py`.
- `transition_submission_status(...)`
  Needed for atomic guarded review transitions such as
  `pending -> claimed` and terminal decisions. This is the proposal’s
  concurrency boundary.
- `load_active_submission_ids(...)`
  Needed during startup hydration so `setup_applications(bot)` can
  re-register `ApplicationReviewView(submission_id)` for restart-safe
  buttons.
- `has_active_submission(...)`
  Needed before opening the first modal to reject duplicate active
  submissions.

### Direct change needed to an existing helper

`daemon/db.py:178-243` must change, not be replaced:

- `create_submission(...)` should return `int`
- the insert body is reusable
- the return contract is not

### What applications should not duplicate

The revised proposal is explicit that `applications.py` should not grow
its own SQL layer. In current code that means:

- reuse the existing `submissions` schema in `daemon/db.py:29-44`
- reuse `get_blacklist_entry(...)` and `get_submission_by_id(...)`
- add the missing helpers in `daemon/db.py`
- do not issue raw `SELECT`, `INSERT`, or `UPDATE` statements from
  `daemon/applications.py`

## 3. Claim Hookpoints

Direct claim surfaces: `daemon/claim.py:40-71` and
`daemon/claim.py:74-139`

### `ensure_preclaim_visibility(...)`

Hookpoint: called immediately after the private review thread is created.

Existing contract:

- requires a private thread (`daemon/claim.py:142-151`)
- takes `requester`
- takes `handler_members`
- adds any missing explicit members to the thread

This is the exact handoff for the revised proposal’s queue/thread setup:

1. create queue message
2. create separate private thread in the applications channel
3. resolve the officer-role members for the chapter
4. call `ensure_preclaim_visibility(thread, requester, handler_members)`

### `execute_claim_visibility(...)`

Hookpoint: called only on the `Claim` review action.

Existing contract:

- requires a private thread
- takes `requester`
- takes `claimer`
- narrows explicit membership down to requester + claimer, while
  preserving admins and the bot when present

That makes the required application-side order:

1. re-read submission row from SQLite
2. verify `interaction.user` has the chapter officer role
3. perform guarded DB transition to claimed state
4. call `execute_claim_visibility(...)`
5. edit queue/thread presentation

The applications module should not call this for `Interview`,
`Approve`, or `Deny`; those actions are DB and Discord workflow changes,
not claim-membership reconciliation.

### `ClaimVisibilityResult`

Hookpoint: `daemon/claim.py:29-37`

- reusable for logging and diagnostics
- not a substitute for DB state

The revised proposal keeps SQLite authoritative for submission review
state, so `ClaimVisibilityResult` is an operational artifact, not the
source of truth.

## 4. Entry Point Hookpoints

### Bot-owned runtime state already exists

Hookpoint: `daemon.py:66-80`

`HumilityDaemonBot` already stores the exact shared state the
applications module needs on the bot instance:

- `guild_id`
- `config`
- `conn`
- `base_path`

For the revised proposal, the important ones are `guild_id`, `config`,
and `conn`.

### `setup_hook()` is the wire-in seam

Direct hookpoint: `daemon.py:82-90`

This is where the future `setup_applications(bot)` call belongs.

Current flow:

1. build `guild = discord.Object(id=self.guild_id)`
2. register `/ping`
3. `await self.tree.sync(guild=guild)`

Future applications-aware flow:

1. build `guild = discord.Object(id=self.guild_id)`
2. keep any boot-owned commands such as `/ping`
3. call `setup_applications(self)`
4. then `await self.tree.sync(guild=guild)`

Why this is the correct seam:

- `setup_applications(bot)` is the proposal’s only public registration
  hook (`proposals/18-applications.md:38`)
- slash commands must be registered before `tree.sync(...)`
- persistent review views must be added on the live bot instance during
  startup, not in `main()`

### `main()` stays orchestration-only

Hookpoint: `daemon.py:93-110`

`main()` already does the correct outer work:

- load runtime env
- load YAML config
- open the database
- construct the bot
- start the gateway
- always close the DB connection

That means the revised applications module does not need its own startup
entry path. Even if the project later moves boot code into
`daemon/__main__.py`, the important hookpoint still remains the bot’s
`setup_hook()`, not a second startup pipeline inside
`applications.py`.

## 5. Parallel Systems And Duplication

### What is already reusable instead of duplicated

There is no live `daemon/applications.py` yet, so this partition is
mostly additive. The duplication risks are against existing support
modules, not against an existing application workflow module.

Existing reusable systems are:

- config planning in `daemon/config.py:514-531`
- config dataclasses in `daemon/config.py:48-94`
- submission and blacklist persistence in `daemon/db.py:29-44`,
  `daemon/db.py:178-246`, and `daemon/db.py:355-363`
- private-thread membership reconciliation in `daemon/claim.py:40-139`
- daemon startup and guild command sync in `daemon.py:82-110`

### The three concrete duplication risks to avoid

1. Do not create a second form-step planner.
   `daemon/config.py:514-531` already decides how questions become
   `FormStepConfig` steps. The revised proposal explicitly says
   `applications.py` must consume `form.steps` as-is.

2. Do not create a raw-SQL application sublayer.
   `daemon/db.py` already owns schema and helpers. This partition adds
   missing DB helpers there; it does not justify SQL inside
   `applications.py`.

3. Do not create a second claim-membership path.
   `daemon/claim.py:40-139` already owns explicit member add/remove
   logic for private threads. `applications.py` should decide when to
   call it, not restate it.

### What is parallel, not duplicate

`docs/DAEMON_DESIGN.md:41-52` describes a shared queue-message plus
private-thread pattern for both applications and tickets. That means
`daemon/tickets.py` will eventually look parallel in shape, but there is
no live ticket module yet. The only shared runtime pieces that should be
generalized now are the ones that already exist:

- DB helpers
- claim visibility helpers
- bot startup wiring

The revised proposal is correct not to introduce a new generic workflow
engine in this partition.

## 6. Deletions And Required Changes

### No Python deletions are required

Nothing in the current runtime tree needs to be removed to make room for
`daemon/applications.py`.

There is:

- no existing applications module to replace
- no one-off submission script to retire
- no duplicate claim helper to delete

This is an additive partition with a few targeted edits to existing
support code.

### Python changes that are required

1. `daemon/db.py:178-243`
   Change `create_submission(...)` so it returns the inserted
   `submission_id`.

2. `daemon/db.py`
   Add the missing helper family for refs, transitions, active-id
   hydration, and duplicate-submission checks.

3. `daemon.py:82-90`
   Change `setup_hook()` so it calls `setup_applications(self)` before
   `tree.sync(guild=...)`.

### Docs that are now stale against the revised proposal

1. `docs/DAEMON_DESIGN.md:25-27` and `docs/DAEMON_DESIGN.md:45-47`
   The design doc still describes private threads as being created off
   the queue message. The revised proposal now requires a separate
   private thread created from the applications channel with
   `TextChannel.create_thread(message=None)` and `invitable=False`.

2. `docs/DAEMON_DESIGN.md:94-100`
   The design doc still speaks in terms of a generic `modal -> select ->
   modal` sequence. The live planner in `daemon/config.py:514-531` does
   not encode that; it currently groups all modal steps first and all
   follow-up selects afterward. The revised proposal explicitly says
   `applications.py` must follow config’s emitted steps rather than
   inventing a second planner.

### What should not change in this partition

- `daemon/config.py` should not be rewritten here.
- `daemon/claim.py` should not absorb DB state or queue-message logic.
- `main()` should not be burdened with application workflow setup beyond
  constructing the bot that owns `setup_hook()`.

## Conclusion

The revised proposal maps cleanly onto the current repo.

The direct hookpoints are already present:

- config dataclasses from `daemon/config.py`
- submission and blacklist storage from `daemon/db.py`
- claim visibility helpers from `daemon/claim.py`
- bot startup wiring through `HumilityDaemonBot.setup_hook()` in
  `daemon.py`

The main missing pieces are in `daemon/db.py`, not in config or claim:

- `create_submission(...)` must return `submission_id`
- active-submission and guarded-transition helpers must be added
- `setup_hook()` must call `setup_applications(self)` before guild sync

No current runtime code needs deletion. The required work is additive,
plus a small set of support-code and documentation updates.
