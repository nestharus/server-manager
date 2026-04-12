# Scope risk assessment — proposals/01-v1-scope.md

Date: 2026-04-11
Assessor: claude-opus (scope)

## Verdict

**MEDIUM**

The proposal targets the right four pain points in the right order and
is not fundamentally wrong, but it builds subsystems sized for a
10x-larger org than Humility (84 members, 0 live chapters, 3 test
tickets in 4 years) and commits one person + agent to more durable
infrastructure than v1 needs. The scope needs trimming in three places
(moderator/incident ticket types, live gateway transcript streaming,
staging-environment sizing) and needs to make two implicit
dependencies explicit (phase 1 depends on a hand-provisioned chapter;
Captcha.bot role-hierarchy interaction). Everything else — the four
subsystems, Option C sequencing, forever-retention, YAML-authored
forms, saga-style provisioning — is proportionate. With the trims
below the project becomes credibly achievable by a single implementer;
without them, phase 2 and phase 3 risk stalling before v1 ships.

## Findings

### Finding 1 — Moderator and incident ticket types are premature

- **Severity**: MEDIUM
- **Direction**: TOO BIG
- **Section of proposal**: §5 Tickets subsystem, §3 `tickets`/`ticket_type` enum
- **Description**: v1 builds all four ticket types: `server_support`,
  `moderator`, `chapter_support`, `chapter_incident`. Per
  `research/02-humility-needs.md` §2, the `Moderator` role is empty
  today — zero mods exist. `chapter_incident` requires live chapters
  with officer rosters, and Humility has zero populated chapters.
  Historical ticket volume is "3 test tickets in 4 years" (§2). The
  proposal itself acknowledges at §5 that the moderator type has no
  handlers at all, yet builds the whole Trial-Mod read-only
  `SEND_MESSAGES_IN_THREADS` overwrite logic, private-thread
  narrowing with watcher semantics, and a separate ticket enum value
  for incidents.
- **Why it matters**: Building plumbing for users who do not yet
  exist is the textbook "building for hypothetical 10x" case the
  assessment prompt warns about (§7). Every route has its own
  overwrite story, panel, queue channel, tests, and staging
  permutations. Four ticket types with distinct permission models
  will double tickets-subsystem implementation time compared to one.
  It also leaks past the §14 anti-scope line "Moderation tooling: no
  active moderators and no research evidence that a full mod-case
  system is the pain today" — the proposal bans mod-case tooling
  then builds mod ticket routing.
- **Recommendation**: Ship `server_support` and `chapter_support`
  only in v1. Add `chapter_incident` when the first chapter is
  populated and officers ask for a separate queue. Add `moderator`
  only after the `Moderator` role is non-empty. Keep the enum but
  do not wire the routing, panels, or Trial-Mod overwrite logic.
  This saves real scope without closing the door on later additions.

### Finding 2 — Live gateway transcript streaming is over-engineered for Humility scale

- **Severity**: MEDIUM
- **Direction**: TOO BIG
- **Section of proposal**: §5 Tickets subsystem (transcript persistence), §3 `ticket_messages`, `application_messages`
- **Description**: The proposal subscribes to message create/edit/
  delete events across all tracked ticket and application threads
  and writes each message into `ticket_messages`/
  `application_messages` as it happens, with a reconcile-on-close
  backfill on top. This requires the daemon to track which threads
  are in-scope, handle missed events during restarts, maintain an
  ingest-source enum (`gateway_create`, `gateway_update`, etc.),
  and store embeds/components/attachments/reference-message JSONB
  per row.
- **Why it matters**: At 3 tickets in 4 years, a "fetch full
  history on close" approach would persist every message the
  project needs with dramatically less complexity and zero gateway
  bookkeeping. Live streaming only matters if you expect either
  high write volume or real-time dashboards during an open ticket,
  and v1 has neither. This is also an easy place for bugs to
  silently drop messages, which forces a reconciliation pass
  anyway — so the incremental value of the gateway path is small.
- **Recommendation**: Cut gateway ingestion for v1. On close (and
  on periodic retroactive refresh of still-open threads), fetch
  the thread history and persist it in one pass. Keep the
  `ingest_source` enum but only ship `close_reconcile` and
  `manual_backfill` in v1. This removes a whole class of edit/delete
  accounting work and simplifies restart handling. If operational
  need for real-time transcripts surfaces, add it in v2 — the
  schema does not need to change.

### Finding 3 — Phase 1 has a hidden dependency on phase 4

- **Severity**: MEDIUM
- **Direction**: ENTANGLED
- **Section of proposal**: §12 Sequencing plan, phases 1–4
- **Description**: Phase 1 (applications) definition of done says
  "one working chapter has an active form." Phase 4 is chapter
  provisioning automation. There is no documented path for how
  phase 1 gets its one chapter. Implicitly, the first chapter is
  hand-provisioned (manual role/channel creation + direct DB
  insert), but the proposal does not name this as a phase 0
  deliverable or a manual prerequisite. Option C was sold as
  "foundations first, then parallel features" but the proposal
  has chapter provisioning gated behind three other phases.
- **Why it matters**: If the chapter-bootstrap manual path is not
  planned, phase 1 slips waiting for phase 4. Alternatively, if
  the one-off manual path gets built ad hoc, it becomes the
  shortcut path and the saga provisioning in phase 4 never gets
  the chance to run against a real workload before v1 ends. Either
  way the sequencing is not actually Option C critical-path
  optimal — it reintroduces a serial dependency.
- **Recommendation**: Either (a) move chapter provisioning forward
  so phases 1–3 can be tested against a real provisioned chapter,
  or (b) explicitly scope a "manual chapter bootstrap" task as part
  of phase 0 — a documented script or SQL + Discord manual setup
  that creates one test chapter for phases 1–3 to run against.
  Option (b) is lighter and preserves the existing sequencing. The
  proposal must pick one and say so.

### Finding 4 — Staging Supabase on free tier contradicts the reason production uses Pro

- **Severity**: LOW
- **Direction**: OTHER
- **Section of proposal**: §9 Deployment, §17 Cost model
- **Description**: §17 says "free tier for staging; production
  Pro." Per `DECISIONS.md#D7`, production was moved to Pro
  specifically because free tier auto-pauses after one week of
  inactivity and has tight limits that "will bite live data."
  Staging is by definition used intermittently — probably less
  often than production — so the auto-pause trap is actually worse
  there. §17 also omits the staging Railway service from the cost
  table entirely despite §11 naming it as required.
- **Why it matters**: Either staging paused-pauses constantly and
  testing becomes "wake it up, wait, then test" friction that
  makes the staging guild get skipped (false economy: see
  Finding 5), or staging quietly also needs Pro, making the real
  monthly number ~$56 not ~$31. §17 is not load-bearing for the
  design but it should not understate reality.
- **Recommendation**: Fix §17 to (a) add a staging Railway line
  (~$5) and (b) either budget staging Supabase at Pro ~$25 or
  document an explicit "refresh staging on demand before test"
  workflow that accepts the auto-pause behavior. Do not leave the
  contradiction uncommented on.

### Finding 5 — Testing scope assumes a separate staging guild that may not get built

- **Severity**: LOW
- **Direction**: OTHER
- **Section of proposal**: §11 Testing strategy
- **Description**: §11 requires one separate staging Discord guild
  + one staging Supabase project + one Railway staging service,
  and argues that a live-Humility sandbox category is "not a
  sufficient replacement" because policy requires per-action care
  for live-server mutations. That is correct reasoning. The risk
  is not that staging is wrong, it is that setting up and
  maintaining a whole parallel guild for one-person+agent work is
  real overhead: invites, roles, template population, Captcha.bot
  re-setup (or skip it), and ongoing drift from production.
- **Why it matters**: If staging gets built and then falls out of
  date, phase-1 test runs will mysteriously not match production,
  and the implementer will start reaching for the live Humility
  sandbox category anyway. If staging doesn't get built at all,
  the permission, thread, and overwrite behaviors for §5 tickets
  and §4 applications are untested before they touch Humility.
- **Recommendation**: Accept §11 but add a concrete "staging parity"
  task to phase 0 — a script or checklist that creates the staging
  guild from the same provisioning spec that phase 4 eventually
  executes against production. That way staging is itself a first
  workload for the provisioning subsystem and does not drift. This
  is the smallest credible way to not let staging become meta-scope
  that never ships.

### Finding 6 — OCR fallback validator is a subsystem, not a helper

- **Severity**: LOW
- **Direction**: TOO BIG
- **Section of proposal**: §6 Activity tracking subsystem (steps 6–9)
- **Description**: The proposal builds (a) Vision OCR with row
  grouping by y-centroid + median token height tolerance,
  (b) weighted confidence scoring with four inputs, (c) accept/
  flag/escalate triage with explicit numeric thresholds, (d) LLM
  fallback with evidence-string quoting, (e) a second-pass
  validator that cross-checks LLM output against classical OCR
  text, row counts, and "sanity checks," and (f) a correction UI
  with superseding rows. This is ~6 independent pieces of logic,
  each a potential source of bugs.
- **Why it matters**: Activity tracking is the subsystem with the
  most technical unknowns (per research/02-humility-needs.md §7,
  risk 1 and research/04-ocr-backends.md). A one-person effort
  that tries to ship all six gates before measuring a single
  real screenshot is likely to spend the whole phase 2 budget on
  the OCR machinery and not reach the flags/correction flow. The
  proposal also proposes gold-set benchmarking (§11) without a
  budget for producing the gold set.
- **Recommendation**: Phase 2 should ship in two slices. Slice 2a:
  Vision-only ingestion with confidence-based accept/flag-for-
  review, manual correction via slash commands, and flags. No
  LLM fallback at all. Measure accuracy against a 20-screenshot
  gold set. Slice 2b: add Gemini fallback + validator only if 2a's
  measured accuracy is below a chosen bar. The schema
  (`raw_llm_response_json`, `fallback_ocr_engine`) already
  supports adding 2b later without a migration. This cuts roughly
  half of phase 2's risk without giving up the end state.

### Finding 7 — Integration with Captcha.bot and AmariBot is not described

- **Severity**: LOW
- **Direction**: OTHER
- **Section of proposal**: §5 Tickets, §7 Chapter provisioning, §15 Risks
- **Description**: Captcha.bot and AmariBot are explicit v1 keeps
  (research/02-humility-needs.md §3; DECISIONS.md#D4). The proposal
  gives the daemon `Administrator` and creates six chapter roles
  per provision. There is no mention of Captcha.bot's verified-
  role position in the hierarchy, no mention of whether the
  daemon's role must be above or below the verification role, and
  no mention of how approval's role mutation (§4 Applications,
  approval flow) interacts with a user who has not yet been
  verified by Captcha.bot. Finding 9 in §15 Risks lists "bot role
  hierarchy may block role management" but only for the daemon's
  own role — not for Captcha.bot collision.
- **Why it matters**: If the daemon's role is below Captcha.bot's
  verified role, or if approval fires for a member who has not
  been verified yet, the approval path will either fail with a
  hierarchy error or put an applicant into a chapter without
  having cleared the verification gate. Neither is catastrophic,
  but both are testable bugs that will appear on first real use
  and are avoidable with an explicit preflight check.
- **Recommendation**: Add a preflight check in §7 provisioning
  (before role creation) that the daemon's role position is
  above both Captcha.bot's managed role and every chapter role
  it will create. Add a check in the approval path that the
  applicant has cleared whatever Captcha.bot state Humility uses,
  and fail cleanly if not. Neither is new scope — both fit within
  existing preflight and approval helpers — but they need to be
  named.

### Finding 8 — Form wizard modal sequencing adds scope for an unlikely case

- **Severity**: LOW
- **Direction**: TOO BIG
- **Section of proposal**: §4 Applications subsystem (form rendering)
- **Description**: The proposal supports single-modal forms when
  forms fit the five-component cap and a multi-modal wizard
  (page 1, page 2, ..., with server-side interim answer storage
  and draft expiry) when they don't. Per
  research/02-humility-needs.md §3 and §4.1 this is a corrected
  platform constraint — modals now accept more input types — and
  §4.1 explicitly says "single-modal form where possible. Forms
  with ≤5 inputs fit in one Discord modal." The wizard is a
  fallback for the exception case.
- **Why it matters**: Server-side draft storage, abandoned-draft
  expiry, and multi-page form state reconciliation are a real
  chunk of phase 1 work for a case that probably never happens in
  v1 — Humility has zero chapters and the only form shape
  referenced anywhere in research is Dark Nemesis, which fit in
  one modal. Building the wizard is paying for a scenario that
  has no evidence of being needed.
- **Recommendation**: v1 supports single-modal forms only. If a
  chapter authors a YAML form that exceeds five components at
  publish time, the publish step fails with a clear error message
  and refuses to store the version. Add wizard support when a
  chapter actually needs it. The `application_forms` / versions
  schema already supports this with no change.

### Finding 9 — The daemon is right-sized except for activity-rule windowing

- **Severity**: LOW
- **Direction**: TOO BIG
- **Section of proposal**: §6 (activity rule evaluation), §3 `activity_rules`
- **Description**: `activity_rules` supports threshold, comparison
  operator, window days, minimum breach days, and
  consecutive-or-not semantics. §6 describes the daily flag job
  that evaluates these rules with "consecutive days" logic. This
  is a real engine.
- **Why it matters**: Humility has no live chapters and no prior
  activity-rule history to validate against. The research did not
  surface a specific shape of rule officers want — the only
  example is "flag under 50 points for 3 consecutive days." One
  example is not enough evidence to justify a rule engine with
  four tuning knobs. This is not severe because the schema is
  cheap, but §6's evaluation logic has to be implemented and
  tested against all four knobs.
- **Recommendation**: Keep the schema (it costs nothing). Ship
  rule evaluation in v1 with only two knobs: threshold and
  consecutive-days window. Leave the comparison operator enum
  (`lt`, `lte`) and `minimum_breach_days` in place but hard-code
  them behind `lt` and `window_days == minimum_breach_days`
  until an officer asks for something different. This trims the
  test matrix for phase 2 without closing options.

## Overall assessment

Findings 1, 2, and 3 are the three that together push the verdict
from LOW to MEDIUM. Finding 1 (moderator/incident ticket types) and
Finding 2 (live gateway transcript streaming) are overbuild for
Humility's actual scale and volume. Finding 3 (phase 1's hidden
dependency on phase 4) is a sequencing gap that is easy to fix but
not fixed in the current document. Findings 4, 5, 6, 7, 8, 9 are
individually small and do not block the proposal; they are listed
because several of them compound in the same direction (build for
a bigger org than exists) and because collectively they consume
enough implementer budget to matter.

The subsystems themselves are right. The schema shape is right.
Option C sequencing is right. Forever-retention is right at this
scale. YAML-authored forms with DB snapshots is right. Saga-style
provisioning is right. The bounded-mutation pattern and audit
events are not scope overruns — they are the price of holding
`Administrator`, and cutting them would trade scope risk for audit
risk. Those stay.

If the above trims are applied, a single implementer + agent can
credibly ship v1. If they are not applied, phase 2 is at serious
risk of consuming its entire budget on OCR machinery and phase 3
is at risk of building ticket plumbing that no user ever exercises.

## What a LOW verdict requires

The verdict is LOW if the scope is credibly achievable, proportionate
to the problem, and does not entangle or starve features.

The verdict is MEDIUM if the scope needs trimming or rebalancing but
is not fundamentally wrong.

The verdict is HIGH if the scope is so wrong (too ambitious or too
narrow) that the proposal should be rewritten before implementation.
