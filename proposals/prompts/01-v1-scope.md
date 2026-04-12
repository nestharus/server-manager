# Proposal prompt — v1 scope for the Humility Discord daemon

## Hard rules (read these first)

**YOU are the proposal-writing agent. YOU write the proposal yourself.
Do not launch, spawn, dispatch, or report on any other agent.** There
are no subprocesses. There is no orchestrator. This prompt is your
assignment. Your deliverable is a single markdown file:
`proposals/01-v1-scope.md`.

- **DO** read `research/01-problem-space.md`, `research/02-humility-needs.md`,
  `research/04-ocr-backends.md`, `DECISIONS.md`, `NOTES.md`, and
  `AGENTS.md` before writing. These are your source material.
- **DO** read `daemon/`, `forms/`, `docs/APPLICATIONS_SKETCH.md`, and
  `docs/DAEMON_DESIGN.md` with the understanding that these are
  **pre-research drafts** — they may contain useful shapes but they
  are NOT constraints on your proposal. You may keep ideas from them,
  but you must justify each kept idea.
- **DO** write the proposal to `proposals/01-v1-scope.md` using your
  Write tool.
- **DO NOT** write progress commentary to stdout or to any log file.
- **DO NOT** modify any files other than `proposals/01-v1-scope.md`.
- **DO NOT** describe what the proposal process will do — just do it.
- **DO NOT** write code. This is a proposal, not an implementation.
  Pseudocode, schema DDL, config YAML examples, and short illustrative
  snippets are fine. Full modules are not.
- **DO NOT** edit `research/00-INDEX.md`, `DECISIONS.md`, or any other
  coordination file.

Your job: synthesize the research and decisions into a concrete,
reviewable proposal that the next phase (risk assessment, three
parallel agents) can evaluate.

## Context — the situation

The Humility Discord server has an established but unpopulated
"chapter" system (multi-sub-community structure). Two external bots
the server depends on are failing: **Gather** (application forms) is
deprecated, and **ticketsbot.net v1** is dead with the tickets.bot v2
replacement proving to be un-automatable and not a great fit. On top
of replacing those, the owner spends daily time tracking in-game
player activity points by hand in a spreadsheet, and wants that
automated.

The v1 scope covers four subsystems:

1. **Applications** (per-chapter forms with a full review workflow)
2. **Tickets** (four categories, claim-based visibility)
3. **Chapter provisioning** (one-command chapter creation)
4. **Activity tracking** (screenshot → OCR → threshold flagging)

All of this runs on **Railway + Supabase (Postgres)** — cloud-hosted,
always-on. There is no local-only deployment path. There is no SQLite.

## Required reading (in order of priority)

1. `DECISIONS.md` — the full decision log (D1 through D6). D2 mandates
   Railway + Supabase, D4 captures the user's v1 scope answers, D5
   establishes activity tracking as a first-class requirement, D6
   locks the current-phase decisions including the OCR architecture
   (mixed, Google Cloud Vision classical + Gemini Flash LLM fallback).
2. `research/02-humility-needs.md` — the synthesis document. Ignore
   any content that has been superseded by `DECISIONS.md#D6`.
3. `research/01-problem-space.md` — evidence-led problem taxonomy and
   existing-solutions map.
4. `research/04-ocr-backends.md` — OCR backend evaluation.
5. `NOTES.md` — live Humility server audit (roles, channels, bots,
   integrations, current breakage).
6. `AGENTS.md` — workflow contract, including The Live Server
   Principle and Mutation Safety Workflow.
7. `daemon/`, `forms/dark-nemesis.yaml`, `docs/DAEMON_DESIGN.md`,
   `docs/APPLICATIONS_SKETCH.md` — pre-research drafts, not
   constraints.

## Non-negotiable constraints

The proposal must respect these without exception:

1. **Cloud-hosted**: runs on Railway, 24/7. No local-only mode.
2. **Postgres via Supabase**: not SQLite, not Railway-managed Postgres,
   not in-memory state. State lives in Supabase.
3. **No compatibility shims**: no feature flags for old behavior, no
   transitional code paths, no "phase this in over 3 releases."
4. **One daemon process** is the preferred architecture (discord.py
   gateway client with persistent connection). Justify if you propose
   otherwise.
5. **The CLI (`discord_cli.py`) survives** as a read-mostly inspection
   tool. It is not merged into the daemon.
6. **Mutation safety**: every tier-3 action (see `AGENTS.md`) is
   auditable and reversible where possible. Bounded mutation patterns
   required for role/channel operations.
7. **Full data retention**: applications, tickets, transcripts,
   activity logs, chapter membership history — all kept forever. Soft
   deletes only.
8. **Mixed OCR pipeline**: Google Cloud Vision `DOCUMENT_TEXT_DETECTION`
   primary, vision LLM fallback for low-confidence cases. Default LLM
   backend: Gemini 3 Flash Preview (paid tier). Escalation logic is
   a design decision you own.

## Deliverable: `proposals/01-v1-scope.md`

Structure the proposal with these sections. Target length: 4000–8000
words. Be specific — proposals get risk-assessed on concrete details,
not on vague gestures.

### 1. Executive summary

One page. What we're building, why, at what cost, over what sequence.

### 2. High-level architecture

A diagram (ASCII is fine) showing:
- Discord gateway → daemon process → Supabase Postgres
- Google Cloud Vision API + Gemini Vision API (for activity tracking only)
- `discord_cli.py` as a sibling inspection tool
- Secrets / env var flow from Railway to daemon
- Upstream/downstream boundaries

Explain each component in a short paragraph.

### 3. Data model

Complete DDL (not Python, SQL) for every table. Include:
- `chapters` (with soft-delete `archived_at`)
- `chapter_roles` (the 6 per-chapter role IDs as foreign references
  to Discord)
- `chapter_members` (roster, with `in_game_name` + discord user id)
- `application_forms` (form definitions — YAML-backed or DB-stored?)
- `applications` (submissions with full state machine including
  waitlist)
- `application_blacklist`
- `tickets` (all four types)
- `ticket_messages` (transcripts)
- `activity_rules` (per-chapter threshold configuration)
- `activity_log` (per-member daily rows with source image reference)
- `activity_flags` (derived from activity_log + rules)
- `audit_events` (durable audit trail — reminder: Discord's native
  audit log is only 45 days)
- any others you find necessary

Each table must have: columns, types, constraints, indexes,
foreign keys, and a one-line purpose note. Mark which columns are
nullable and why. Mark soft-delete columns explicitly.

### 4. Applications subsystem

Detailed design. Must cover:

- Form definition format (YAML in-repo vs DB-stored — pick one and
  justify)
- Slash command surface (`/apply <chapter>` with autocomplete)
- Modal rendering strategy — use the **corrected** modal capabilities
  (selects, file upload, radios allowed now, not just text inputs),
  not the pre-research split-flow design
- Blacklist check (where in the flow)
- Submission persistence
- Review message + embed shape
- Private thread creation and initial seeding (applicant + chapter
  officers)
- Review button actions: Claim, Interview, Waitlist, Approve, Deny
- Claim semantics (thread membership mutation)
- Waitlist semantics (pre-decision holding state per DECISIONS.md#D6)
- Interview state vs waitlist state (what's the difference in the
  state machine?)
- Approve: role mutations (add chapter-specific Member role, remove
  Applicant role, archive thread, DM applicant)
- Deny: reason capture, DM applicant, blacklist-by-policy flag,
  archive thread
- Data retention: soft-delete only, status history preserved
- Handling of form schema evolution (if a chapter updates its form
  questions, do old submissions display correctly? explain)

### 5. Tickets subsystem

Same level of detail. Must cover:

- Four ticket types (server-support, moderator, chapter-support,
  chapter-incident) with their routing rules
- Handler role mapping (Staff, Moderator + Trial Mod readonly, chapter
  officers)
- Slash command surface + button panels
- Thread creation with private-thread semantics (including the
  `SEND_MESSAGES_IN_THREADS` vs `SEND_MESSAGES` distinction for Trial
  Mod read-only)
- Claim mechanics (shared with applications)
- Transcript persistence (every message in a ticket thread stored to
  `ticket_messages` — but how? gateway events? poll on close?)
- Close + archive flow
- Handling of requester leaving the server mid-ticket
- Ticket-to-application promotion (if a staffer realizes a server
  ticket is really an application, can they convert it?)

### 6. Activity tracking subsystem

Detailed design with special attention to the OCR pipeline. Must
cover:

- Input surface: how officers upload screenshots (slash command?
  attach to specific channel? DM?)
- Per-chapter roster setup (linking in-game names to Discord user
  IDs) — one-time or ongoing?
- OCR pipeline:
  1. Receive image
  2. Optional preprocessing (crop, upscale, deskew)
  3. Call Google Cloud Vision `DOCUMENT_TEXT_DETECTION`
  4. Row parsing logic (how do you group text into rows?)
  5. Confidence scoring per row
  6. Decision: accept, flag for review, or escalate to vision LLM
  7. LLM fallback path with Gemini 3 Flash Preview (structured JSON
     output)
  8. Hallucination controls (quoted original text, second-pass
     validation, row-count check)
  9. Final persistence to `activity_log`
- Activity rule DSL: how does an officer define "flag anyone under
  50 points for 3 consecutive days"? YAML? DB rows? Simple table with
  (chapter, target, window)?
- Flagging output: where does the bot post flagged members (channel?
  DM? both?)
- Handling of mis-scanned rows: officer correction UI
- Handling of new players appearing in screenshots before they're in
  the roster
- Historical backfill: can officers upload old screenshots to backfill
  history?

### 7. Chapter provisioning subsystem

Detailed design. Must cover:

- Trigger: where does chapter creation actually start? CLI command?
  Slash command for admins?
- Inputs: chapter name, slug, game, form questions, activity rules,
  initial officers, any other config
- Sequence of mutations (each is tier-3 per `AGENTS.md`):
  1. Create chapter-specific roles (cloned from templates with prefix)
  2. Create chapter category with appropriate overwrites
  3. Create chapter channels (from template + extras for queues)
  4. Set channel-level overwrites (NOT relying on category
     inheritance — research flagged this trap)
  5. Write chapter row to Postgres
  6. Upload form definition (or write to DB)
  7. Write activity rule
  8. Post application panel in the chapter's applications channel
- Idempotency: if provisioning fails partway through, how does it
  recover? (transactional? rollback? resume?)
- Chapter archival (inverse flow, preserves data)
- Chapter role cap check (Discord's 250-role hard limit)
- Chapter category cap check (Discord's 50-category hard limit)
- Provisioning UX: does the officer see progress?

### 8. Shared infrastructure

- **Claim-visibility helper**: factored out so applications and
  tickets both use it. Describe the interface.
- **Mutation safety wrapper**: every tier-3 mutation goes through a
  helper that logs to `audit_events` before and after the operation.
  Explain the pattern.
- **Bounded mutation pattern**: e.g., role mutations always specify a
  target member + target role, never "add this role to everyone" by
  accident. Explain how the code prevents mass mutations.
- **Background jobs**: anything that needs to run on a schedule
  (daily activity flag computation? waitlist aging? chapter activity
  summaries?) — if so, how are they scheduled? (in-process scheduler?
  external cron? Railway cron job?)

### 9. Deployment

- Dockerfile sketch (layers, base image, dependency install, entry
  point)
- Railway service configuration: start command, health check,
  environment variables, region
- Supabase project layout: one prod project + one staging? schemas?
  row-level security?
- Secrets management: `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`,
  `SUPABASE_DB_URL`, `SUPABASE_SERVICE_KEY`, `GOOGLE_CLOUD_VISION_KEY`,
  `GEMINI_API_KEY` — where do they live?
- Migration tool selection and justification (Alembic recommended;
  justify if you pick differently)
- Monorepo layout: where does the daemon, CLI, migrations, and docs
  live relative to each other?

### 10. Observability

- Logs: where do they go? what level? structured JSON?
- Metrics: what do we care about? (command counts, error rates,
  OCR confidence distribution, active threads, etc.)
- Alerting: what wakes the owner up at 2am? (daemon process dying,
  Supabase connection lost, Google Vision quota exceeded, anything
  else?)
- Error handling: does a failure in the activity tracker cascade
  into other subsystems? explain the blast radius boundaries.

### 11. Testing strategy

- Unit tests (on what? the daemon has lots of Discord-API side
  effects)
- Integration tests: how do you test a Discord bot without a real
  Discord server? Options: mock the gateway, stand up a test guild,
  run locally against a private server...
- Staging environment: is there a separate staging Humility-like
  server, a sandbox category in Humility, or a mock-only path?
- Manual test checklist for first deploy
- OCR accuracy measurement: how do we know the activity tracker is
  working well enough to trust?

### 12. Sequencing plan (Option C)

Per `DECISIONS.md#D6`, the agreed sequencing is Option C: foundations
first, then parallel feature delivery. Lay out the sequence in detail:

- **Phase 0 (foundations)**: daemon skeleton on Railway, Supabase
  schema deployed, CI running, `/daemon-ping` live
- **Phase 1 (applications)**: single working chapter with working
  apply flow, end-to-end including DM notifications
- **Phase 2 (activity tracking)**: OCR pipeline live, can ingest
  screenshots and produce flags
- **Phase 3 (tickets)**: four ticket types live
- **Phase 4 (chapter provisioning automation)**: `chapters create`
  command working end to end

For each phase: definition of done, demoable outcome, and what the
next phase depends on. No time estimates — focus on sequencing.

### 13. Rollback plan

What does the rollback look like per phase? For the one-process
daemon, rollback is mostly redeploy-previous-image, but some
operations (role creation, channel creation) leave residue. How do
you undo a failed chapter provisioning?

### 14. Anti-scope (explicitly out of v1)

Copy the out-of-scope list from `research/02-humility-needs.md#6`
and add anything else you realize during writing. Each item gets a
one-line explanation of why it's out.

### 15. Risks and mitigations

At least 8 risks with mitigations. Must include:
- OCR accuracy risk
- Player → Discord identity mapping risk
- Supabase vendor dependency
- Gemini/Google Vision vendor dependency
- Role/category cap growth
- Permission drift over time
- Bounded-mutation bug (bot has Administrator)
- Waitlist state aging / UX friction
- Any others you discover

### 16. Open questions for hookpoint phase

Questions that hookpoint research (phase 5, `gpt-high`) needs to
answer before implementation can start. Examples:

- Which pre-research code (if any) should survive?
- Does `discord.py` have features that simplify this design we
  haven't exploited?
- Are there existing OSS reference implementations of claim-based
  Discord threads we should crib from?

### 17. Cost model

Back-of-envelope monthly cost at MVP volume:
- Railway service (~$5-10/month base)
- Supabase (free tier sufficient? paid tier?)
- Google Cloud Vision (~$0–$2/month)
- Gemini vision fallback (~$1/month)
- Total

Be explicit about free-tier assumptions.

## Anti-goals for the proposal

- **No code.** Schema DDL is OK. Short pseudocode snippets are OK.
  Full Python modules are not.
- **No picking winners on things the user should decide.** If a
  design decision has significant user-facing tradeoffs, present the
  options and flag it for the hookpoint phase or for user review.
- **No speculation.** If you don't know something, say so. List it
  as an open question.
- **No restating the research.** Reference it, don't duplicate it.
- **No vague hand-waving.** "A state machine handles the waitlist"
  is not a design. "States are `pending, claimed, interview,
  waitlist, approved, denied`; valid transitions are `pending→claimed,
  claimed→{interview, waitlist, approved, denied}, interview→{waitlist,
  approved, denied}, waitlist→{claimed, approved, denied}`; approvals
  require a reviewer_id; denials require a reason" is a design.
- **No markdown tables without actual data.** Don't write
  `| Column | Type | Purpose |` and then nothing useful.

## Output

Write the report to `proposals/01-v1-scope.md`. Do not modify any
other file. When you are done, stop. Do not print commentary. Do
not describe the file contents. Just write the file and exit.
