# Proposal 01: Humility Discord Daemon v1 Scope

## 1. Executive summary

Humility v1 remains a single always-on Discord daemon on Railway, backed
by Supabase Postgres, with Supabase Storage for durable screenshot
evidence. The validated shape does not change: Discord stays the primary
operator surface, `discord_cli.py` stays a sibling read-mostly
inspection tool, and the v1 problem areas remain applications, activity
tracking, tickets, and chapter provisioning.

This revision takes the scope cut the last review asked for. The design
keeps the four subsystems, but removes machinery that spends present-day
budget on future scale Humility does not have yet. V1 assumes one
trusted daemon process is the only database writer, visible Discord
mutations are funneled through audited operator commands, and immutable
history is enforced in the service layer plus CI/tests rather than by a
DB-trigger framework.

The major scope trims are:

- applications stay first-class, but Phase 1 ships exactly one applicant
  input surface chosen before implementation starts: either Discord
  components if the library supports the required controls, or a thin
  daemon-served web intake page if it does not
- activity tracking is explicitly split into Phase 2a and Phase 2b so
  OCR ingestion lands before trust, fallback, correction, and rule
  automation
- tickets ship only as `server_support`, with close-time transcript
  capture only and no ticket-to-application promotion
- provisioning stays in scope, but v1 uses a linear audited runner with
  explicit cleanup instead of `provisioning_steps`, resume logic, or
  saga-style rollback
- deployment uses one always-on production Railway compute service; all
  staging validation happens locally against a staging Discord guild and
  staging Supabase

The complexity budget stays where Humility actually needs it: durable
records, safe Discord mutations, parameterized SQL, secret scrubbing,
upload limits, and operator-visible auditability.

## 2. Architecture

```text
Discord Slash Commands / Buttons / Modals / Threads
                    |
                    v
        +-----------------------------+
        | Humility daemon             |
        | discord.py gateway client   |
        | workflow handlers           |
        | OCR orchestration           |
        | mutation safety wrapper     |
        | optional thin intake page   |
        +-------------+---------------+
                      | \
                      |  \
                      v   v
            Supabase Postgres   Supabase Storage
            system of record    screenshot evidence
                      |
                      v
      Google Cloud Vision primary OCR
      Gemini 3 Flash Preview fallback in Phase 2b only
```

Key architectural rules:

- one production compute surface: the Railway daemon process
- no second always-on API or staging service in v1
- if the web intake fallback is required, it is served by the same
  daemon process and uses the same Postgres records as the Discord path
- `discord_cli.py` is not a mutation surface in v1; it remains for
  inspection, audits, and diagnostics

Existing bot boundary stays explicit:

- Captcha.bot continues to own server-entry verification and the
  Guest-to-Member flow
- AmariBot continues to own Discord-side XP and leveling
- the Humility daemon owns chapter applications, chapter roster state,
  activity OCR, `server_support` tickets, and chapter provisioning
- the daemon does not take over existing verification or leveling roles
  unless a later proposal says so

## 3. Scope principles

1. Humility scale, not speculative scale. The proposal must fit one
   operator, one daemon writer, one guild, and low chapter volume.
2. Discord-first operator surface. Staff actions happen in Discord even
   if applicant input falls back to a thin web page.
3. Supabase Postgres is the system of record. No SQLite or local-first
   fallback path exists in v1.
4. YAML and JSON attachments may be import or operator input formats,
   but never the production source of truth after import.
5. No compatibility shims, dual-write paths, feature flags for old
   behavior, or transitional storage layers.
6. Immutable history matters, but the enforcement mechanism must match
   the actual risk model: single daemon writer plus audited operator
   commands.

## 4. Data model

V1 should keep the schema relational and specific to Humility's actual
workflows. It does not need a generic guild-wide mirror of every role,
channel, and user object. Durable Discord IDs and snapshots live on the
records that actually use them.

Current-state tables:

- `app.chapters`
  - one row per live or archived chapter
  - stores chapter slug, display name, game name, core Discord resource
    IDs, and the active application form version reference
- `app.chapter_roles`
  - one row per chapter with the six role IDs v1 actually needs
- `app.chapter_channels`
  - one row per chapter with the minimum channel IDs v1 uses:
    applications queue, officer lobby, and any activity review channel
- `app.chapter_members`
  - roster rows keyed by chapter plus Discord user ID
  - stores current in-game name, normalized in-game name, join/leave
    timestamps, and optional source application ID
- `app.applications`
  - stores one submitted application plus current status, answer
    snapshot, attachment snapshot, queue message ID, review thread ID,
    claimer, decision metadata, and soft-archive fields
- `app.application_blacklist`
  - current blacklist entries per chapter and user
- `app.tickets`
  - only `server_support` in v1
  - stores requester ID, current status, subject/body, queue message ID,
    thread ID, claimer, close metadata, and archive fields
- `app.activity_rules`
  - per-chapter threshold rules as proper columns, not YAML and not a
    free-form DSL
- `app.activity_uploads`
  - one row per uploaded screenshot with storage path, hash, status,
    captured date, provider payloads, and review metadata
- `app.activity_rows`
  - extracted `(player_name, score)` rows for one upload
  - `row_confidence` stays nullable until Phase 2b
- `app.activity_flags`
  - officer-review flags generated from activity rules
- `app.provisioning_runs`
  - one mutable row per provisioning attempt with imported spec,
    validation report, created resource IDs, cleanup report, run status,
    and failure text

Immutable history tables:

- `app.application_form_versions`
  - immutable form-version rows with `schema_json`
  - each chapter points at one active version; applications reference
    the exact version used at submit time
- `app.application_status_history`
  - append-only application transitions
- `app.ticket_messages`
  - normalized close-time transcript rows
- `audit.audit_events`
  - append-only logical audit events for visible Discord mutations and
    important workflow decisions

JSONB stays disciplined and document-shaped:

- `schema_json` for immutable form definitions
- `answers_json` and `attachments_json` for immutable submitted
  application snapshots
- OCR provider payloads for Google Vision and Gemini
- transcript `attachments_json` and `embeds_json`
- provisioning `spec_json`, `validation_report_json`,
  `created_resources_json`, and `cleanup_report_json`
- audit `request_json`, `before_json`, and `after_json`

Explicit schema cuts from the previous revision:

- no generic `discord_users`, `discord_roles`, or `discord_channels`
  mirror tables
- no `provisioning_steps`
- no ticket schema for deferred ticket types
- no schema dedicated to real-time transcript mirroring
- no fields whose only consumer was ticket-to-application promotion

Append-only enforcement in v1 is an application invariant:

- the daemon is the only DB writer
- repository code for `application_status_history`,
  `ticket_messages`, and `audit.audit_events` exposes insert-only
  operations
- service code appends history; it does not rewrite it
- CI/tests fail if update/delete queries are introduced for append-only
  tables
- corrections append new rows or supersede mutable current-state rows;
  they do not mutate historical records in place

All DB writes use parameterized SQL or equivalent bound parameters. No
user-controlled value is interpolated into raw SQL strings.

## 5. Applications subsystem

Applications stay first-class, but the v1 implementation is narrower
than the last draft.

### 5.1 Operator and applicant surfaces

Humility still needs chapter-specific application forms, officer review,
waitlists, approval, denial, and blacklist support. It does not need
two applicant input surfaces in production.

Before Phase 1 starts, hookpoint research must resolve exactly one v1
intake surface:

- `Discord-native`: if the chosen `discord.py` surface supports the
  required components cleanly
- `Thin web intake`: if it does not

The fallback is explicit and bounded:

- it is served by the same daemon process
- it covers applicant input only
- it does not create a reviewer dashboard
- it does not add a second always-on service
- it does not change the data model or Discord review workflow

In either case, staff review remains Discord-first.

### 5.2 Form model

Forms are versioned in Postgres, not YAML-backed in production. A form
change creates a new immutable `application_form_versions` row. The
chapter points at one active version. Old submissions keep their exact
version reference forever.

The simplest acceptable v1 editing path is import-based and admin-only:

- `/chapter form replace chapter:<chapter> spec:<attachment>`
- the attachment may be YAML or JSON
- import creates a new immutable form version row
- the attachment is an input artifact, not the source of truth after
  import

### 5.3 Submit and review flow

The public entry point is `/apply chapter:<chapter>`.

Pre-submit checks:

- chapter exists and is active
- applicant is not blacklisted for that chapter
- applicant has no active application for that chapter

To keep Phase 1 small, v1 does not persist abandoned drafts. The daemon
creates the `app.applications` row on final submit, not at form-open
time.

On submit the daemon:

1. writes the application row in `submitted`
2. appends `application_status_history`
3. posts a queue embed in the chapter applications channel
4. creates a private review thread
5. seeds thread membership with chapter officers, preserved central
   overrides, the bot, and the applicant where appropriate

Application state machine:

- `submitted -> claimed`
- `submitted -> interview`
- `submitted -> waitlist`
- `submitted -> approved`
- `submitted -> denied`
- `claimed -> interview`
- `claimed -> waitlist`
- `claimed -> approved`
- `claimed -> denied`
- `interview -> waitlist`
- `interview -> approved`
- `interview -> denied`
- `waitlist -> claimed`
- `waitlist -> approved`
- `waitlist -> denied`
- any active state -> `withdrawn`

Operational meaning:

- `interview` means an officer is actively working the case
- `waitlist` means the chapter is deferring a decision for capacity or
  timing reasons; it is not approval

Buttons remain:

- `Claim`
- `Interview`
- `Waitlist`
- `Approve`
- `Deny`

### 5.4 Approve and deny

`Approve` is one bounded service operation:

1. start DB transaction
2. append application status history
3. insert or update the roster row
4. commit DB changes
5. run visible Discord mutations through the mutation wrapper:
   add member role, remove applicant role, DM if possible, post terminal
   thread summary, archive thread

`Deny` requires a reason and supports an optional chapter blacklist
checkbox. Denial writes the application result, optionally inserts the
blacklist row, sends the DM if possible, posts the thread summary, and
archives the thread.

No ticket-to-application promotion exists in v1.

### 5.5 Manual bootstrap dependency

Humility has no live chapter infrastructure yet. One staging chapter,
and any first production seed chapter needed for rollout, must be
manually created before applications go live. Provisioning automation
comes later; it is not a hidden dependency for Phase 1.

## 6. Activity tracking subsystem

Activity tracking remains a peer subsystem, but the proposal now phases
it honestly.

### 6.1 Command surface and roster maintenance

The entry point is officer-only:

- `/activity upload chapter:<chapter> date:<yyyy-mm-dd> image:<file>`

Upload bounds are explicit in v1:

- PNG or JPEG only
- max 10 MB per image
- fixed per-officer and per-chapter throttles before storage or OCR
  dispatch

The OCR path is only useful if roster bindings exist. Phase 2a therefore
includes the smallest necessary roster maintenance commands:

- `/chapter roster link`
- `/chapter roster rename`

These are enough to make OCR results operational. `/chapter roster
remove` can land in Phase 2b, and CSV import is deferred out of v1.

### 6.2 Phase 2a: upload -> store -> OCR call -> basic extraction

Phase 2a delivers a complete, demoable ingestion loop:

1. accept the image
2. copy it to Supabase Storage
3. hash it and create the `activity_uploads` row
4. call Google Cloud Vision `DOCUMENT_TEXT_DETECTION`
5. persist the provider payload
6. run a conservative row parser
7. persist extracted rows
8. post an officer-visible extraction summary

Phase 2a does not claim calibrated trust. It exists to replace manual
copying with durable ingestion and a usable extraction draft.

### 6.3 Phase 2b: confidence -> fallback OCR/vision -> correction UI -> rules

Phase 2b adds the hard part explicitly instead of hiding it behind
"review later" language:

1. confidence scoring
2. roster-match quality checks
3. escalation rules
4. Gemini 3 Flash Preview fallback for ambiguous uploads only
5. grounded-validation rules for fallback output
6. officer correction actions
7. activity-rule evaluation and flag posting

Correction tools should stay small and Discord-native:

- `Link Member`
- `Edit Score`
- `Add Missing Row`
- `Reject Row`
- `Confirm Upload`

Corrections append new rows or supersede active rows. They do not erase
the original extraction evidence.

The rule model stays column-backed:

- metric
- operator
- threshold
- window length
- breach count
- evaluation mode

No auto-punishment exists in v1. Flags go to officers for review.

## 7. Tickets subsystem

Tickets remain in scope, but the v1 ticket system is intentionally thin.

V1 ships only:

- `server_support`

Deferred explicitly:

- `moderator`
- `chapter_support`
- `chapter_incident`

The user-facing entry point is one command:

- `/ticket open subject:<text> description:<text>`

The daemon:

1. writes the ticket row in `open`
2. posts the queue embed
3. creates the private thread

Staff actions:

- `Claim`
- `Close`

Ticket state machine:

- `open -> claimed`
- `open -> closed`
- `claimed -> closed`

Transcript capture is close-time only:

- on close, fetch full thread history
- paginate until complete
- normalize into `app.ticket_messages`
- mark the ticket closed
- post the terminal summary
- archive the thread

V1 does not do:

- real-time transcript mirroring
- transcript reconciliation jobs
- ticket-to-application promotion
- chapter-specific routing logic

At Humility's current volume, the point of tickets is to replace a dead
vendor dependency with a small durable case flow, not to build a large
support platform.

## 8. Chapter provisioning subsystem

Provisioning stays in v1, but it is now a linear audited runner rather
than a workflow engine.

### 8.1 Inputs and dependency

The one-time first-chapter bootstrap remains explicit. V1 does not hide
that dependency behind fake automation.

Automated provisioning is for subsequent chapters and uses:

- `/chapter provision spec:<attachment>`

The attachment can be YAML or JSON and contains only what v1 needs:

- slug
- display name
- game
- initial officers
- application form definition
- initial activity rules

### 8.2 Linear runner

Provisioning flow:

1. validate the spec
2. check Discord cap headroom
3. create `app.provisioning_runs` with the imported spec and validation
   report
4. show a preview and require explicit admin confirmation
5. execute sequentially
6. record created IDs after each successful step
7. stop on first failure and report the cleanup target set

Execution order:

1. create chapter roles
2. create chapter category
3. create minimum v1 channels
4. apply explicit overwrites
5. write `chapters`, `chapter_roles`, and `chapter_channels`
6. import the initial application form version
7. insert initial activity rules
8. post and pin the application panel

### 8.3 Failure handling

V1 explicitly removes:

- `provisioning_steps`
- automatic resume
- automatic rollback
- saga-style orchestration

Failure handling becomes:

- stop the run
- mark it failed
- show which step failed
- show which resource IDs were already created
- allow an explicit human-visible cleanup action that uses the recorded
  IDs

That is proportionate to Humility's expected chapter volume and keeps
auditability without inventing an orchestration subsystem.

## 9. Shared controls

### 9.1 Mutation safety

Every visible Discord mutation goes through one wrapper that:

1. writes a `planned` audit event with logical parameters only
2. executes one bounded Discord change
3. records a sanitized success or failure event

Bounded helper examples:

- `add_role(member_id, role_id)`
- `remove_role(member_id, role_id)`
- `create_private_thread(channel_id, name)`
- `set_channel_overwrite(channel_id, target_id, overwrite)`

Non-goals for v1 helpers:

- server-wide sync helpers
- bulk "fix everything" mutations
- hidden fan-out operations

### 9.2 Rate limits

Discord mutation handling must be rate-limit aware:

- honor `Retry-After`
- queue bursty multi-call flows such as provisioning
- do not rely on naive retries

### 9.3 Audit and append-only rules

Audit rows store logical mutation context only. They never store raw
HTTP payloads, raw headers, Discord REST bodies, or vendor request
bodies.

Secret handling stays as won in the last revision:

- `request_json` is logical-only
- `error_text` is sanitized before persistence
- structured logs use the same scrubber

Application-level immutable history rules:

- the daemon is the only writer
- append-only tables are insert-only in repository code
- current-state tables may update, but history tables do not
- CI/tests enforce the invariant
- no DB-trigger framework is introduced in v1

### 9.4 Transactions

Pure DB writes inside one logical decision happen in one Postgres
transaction. Discord API calls sit outside that boundary and are tracked
through audit events rather than pretending to be transactional.

### 9.5 Environment guard

The daemon should refuse to start if the declared environment label does
not match the configured guild and database targets. This is a small
guardrail against local misconfiguration, not a new deployment surface.

## 10. Deployment and operations

V1 production runtime:

- one always-on Railway compute service
- start command: `python -m daemon`
- release command: `alembic upgrade head`

Environment layout:

- one production Discord guild target and Supabase project
- one staging Discord guild target and Supabase project
- staging validation runs locally against those staging resources
- no second always-on staging Railway service in v1

Supabase usage:

- Postgres is the system of record
- Storage bucket holds screenshot evidence
- Alembic manages schema changes

Observability is trimmed to what one operator actually needs:

- structured JSON logs to stdout
- shared secret scrubber for logs and audit failures
- minimal `/healthz` only if Railway needs it
- Railway logs and crash visibility are the primary operational surface

V1 explicitly does not include a Prometheus-style metrics stack or a
second alerting subsystem.

## 11. Testing strategy

Unit tests should cover:

- application transitions
- ticket transitions
- append-only repository rules
- secret scrubbing
- mutation-wrapper behavior
- rate-limit-aware retry logic
- provisioning validation
- OCR parsing and fallback-routing rules
- activity-rule evaluation

Integration tests should cover:

- one full application approval path
- one denial with blacklist
- one Phase 2a activity upload
- one Phase 2b ambiguous upload with correction
- one `server_support` ticket close with full transcript fetch
- one failed provisioning run with explicit cleanup

Contract tests for append-only enforcement are required:

- history/audit tables can be inserted into
- service code never issues update/delete against them
- stale update paths fail when optimistic-locking or version checks are
  expected on mutable aggregates

## 12. Sequencing plan

### Phase 0: foundations

Definition of done:

- Railway daemon deploys
- Supabase schema exists
- Alembic is wired
- mutation wrapper writes sanitized audit rows
- environment guard works
- `/daemon-ping` works

### Phase 0.5: manual bootstrap

Definition of done:

- one staging chapter exists manually
- any first production seed chapter required for rollout exists manually
- chapter resource IDs are recorded in Postgres

### Phase 1: applications

Definition of done:

- one active chapter has one working form
- one intake surface is selected and implemented
- `/apply` submits successfully
- review embed and private thread are created
- officers can claim, interview, waitlist, approve, and deny
- approval updates roles and roster state

Important gate:

- hookpoint research must choose the applicant intake surface before
  Phase 1 starts

### Phase 2a: activity ingestion

Definition of done:

- officers can upload images within v1 bounds
- evidence lands in Supabase Storage
- Google Vision is called
- basic rows persist
- officers receive a usable extraction summary
- roster link and rename commands exist

Demo value:

- Phase 2a is independently useful even before correction and rules

### Phase 2b: activity trust and automation

Definition of done:

- confidence scoring exists
- Gemini fallback exists for ambiguous uploads only
- officer correction actions exist
- rule evaluation produces review flags
- roster remove exists if needed by the correction path

### Phase 3: tickets

Definition of done:

- `server_support` can be opened, claimed, closed, and transcripted

### Phase 4: provisioning

Definition of done:

- an admin can validate, confirm, run, and clean up a chapter
  provisioning attempt
- created resource IDs are recorded as the run proceeds

## 13. Anti-scope

- `moderator`, `chapter_support`, and `chapter_incident` ticket types
- ticket-to-application promotion
- real-time transcript mirroring or transcript reconciliation
- `provisioning_steps`, automatic resume, automatic rollback, or saga
  orchestration
- a second always-on staging compute service
- a general reviewer web dashboard
- CSV roster import
- SQLite or local-first fallback
- YAML as the production source of truth
- spreadsheet sync
- compatibility shims, dual behavior, or feature flags for old paths
- auto-punishment from activity rules
- speculative scale-out machinery for multi-daemon writers

## 14. Risks and mitigations

- Discord component support may still force the web intake fallback.
  Mitigation: choose exactly one intake surface before Phase 1 starts;
  if fallback is needed, keep it daemon-served and applicant-only.
- OCR accuracy will vary by game UI. Mitigation: Phase 2a and Phase 2b
  are separate; ambiguous rows escalate or wait for review instead of
  being silently trusted.
- Activity uploads could create cost spikes. Mitigation: fixed file
  bounds, upload throttles, and Gemini fallback only for ambiguous
  cases.
- Provisioning can still fail mid-run. Mitigation: linear execution,
  incremental created-ID recording, and explicit cleanup.
- The daemon has high Discord privilege. Mitigation: bounded mutation
  helpers, logical-only audit payloads, rate-limit-aware execution, and
  secret scrubbing.

## 15. Cost model

Assumptions:

- one always-on Railway production service
- one production Supabase project
- one staging Supabase project used from local development
- Google Vision on all Phase 2a uploads
- Gemini only on ambiguous Phase 2b uploads

Expected monthly cost:

- Railway: roughly `$5-10`
- Supabase production: roughly `$25`
- Google Vision at Humility MVP volume: near `$0`
- Gemini fallback at low ambiguous volume: low single digits

Recommended production budget: roughly `$30-40/month`.

That budget matches the trimmed scope: one live daemon, one durable
database, one evidence bucket, one OCR baseline, and one optional
fallback path. The cost driver is still hosting and storage, not the
thin ticket subsystem or the simplified provisioning runner.
