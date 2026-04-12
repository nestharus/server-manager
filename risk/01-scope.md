# Scope risk assessment — proposals/01-v1-scope.md

Date: 2026-04-11
Assessor: claude-opus (scope)

## Verdict

**MEDIUM**

The four-subsystem scope matches the documented pain, but the
proposal is designed for a 10x-Humility target and spends its
one-person implementation budget on durability machinery that the
actual server — 84 members, 0 populated chapters, 3 test tickets in
four years — will not exercise for a long time. Applications and
activity tracking are cleanly justified and correctly sized.
Tickets, the provisioning saga, the append-only-trigger story, and
the full staging-parity environment are each individually
defensible but collectively push v1 past what one person plus an
agent will realistically stabilize before the next pain point
arrives. Nothing here is fundamentally wrong; several things need
rebalancing. The proposal should not be rewritten, but several
items should be cut or deferred and the schema should be trimmed
before implementation starts.

## Findings

### Finding 1 — Schema is designed for a 10x Humility

- **Severity**: MEDIUM
- **Direction**: TOO BIG
- **Section of proposal**: §3 (Data model), all sub-tables
- **Description**: The DDL prelude introduces nine enums and the
  schema lists roughly twenty tables, including
  `application_form_versions` (with `schema_hash`, immutable
  triggers, YAML source text stored per version), a full
  `application_status_history`, separate `application_messages` and
  `ticket_messages` transcript tables, a 13-value
  `chapter_channel_kind` enum, `provisioning_runs` +
  `provisioning_steps` as a saga substrate, and a dedicated
  `audit_events` table with `correlation_id` + `phase` state
  machine. Humility has 84 members, 0 populated chapters, and
  historically 3 test tickets in four years (`NOTES.md`).
- **Why it matters**: Schema surface is durable work. Every table
  is a migration, an access path, test coverage, backup bytes, and
  code that has to stay correct. Each enum value is a migration
  hazard. At current volume, the 20-table design buys almost no
  runtime value over a ~10-table subset. The research recommended
  designing for "50 members, recoverable by hand" scale
  (`research/01-problem-space.md` §1), not 500+.
- **Recommendation**: Before implementation, collapse the schema to
  the minimum that still passes the forever-retention requirement.
  Concretely: merge `application_messages` and `ticket_messages`
  into one `thread_messages` table keyed by thread + item, drop
  `application_form_versions` as a separate table for v1 (store
  `schema_json` + `schema_hash` inline on the application row —
  re-introduce the version table when a chapter actually revises a
  form), drop the `chapter_channel_kind` enum in favor of a
  `kind TEXT` column, and collapse `provisioning_runs` /
  `provisioning_steps` to a single table with a JSONB step log.
  The guarantees in §8 (append-only, history-preserving) can be
  kept with half the surface.

### Finding 2 — Provisioning automation is premium engineering for 1-3 chapter lifetime use

- **Severity**: MEDIUM
- **Direction**: TOO BIG
- **Section of proposal**: §7 (Chapter provisioning subsystem), §12
  Phase 4
- **Description**: The provisioning subsystem is the heaviest
  per-feature surface in the proposal. It includes a saga workflow
  with planned/running/failed/completed/rolled_back states, step
  rebinding on resume, preflight role/category/channel-cap checks,
  daemon-CLI job handoff, JSONB spec submission, rollback UX, and a
  non-destructive archival flow. Humility's scale is 0 live
  chapters today and plausibly 1-3 over the next year per
  `research/02-humility-needs.md`.
- **Why it matters**: Provisioning is the least-frequently-exercised
  and highest-blast-radius subsystem. Complexity is justified where
  either cost or frequency is high; here the frequency is near
  zero. A one-person implementation budget spent on saga
  infrastructure is a budget not spent on OCR calibration, which
  the user will touch every day. The proposal already accepts (§12
  Phase 0) that the **first** chapter is hand-built via a manual
  bootstrap checklist — which is the right call and evidence that
  automation is not on the critical path.
- **Recommendation**: Keep the subsystem, cut the sophistication.
  Drop the saga state machine in v1. Replace it with: a single
  Python script driven by the same CLI command, running under the
  existing mutation safety wrapper (§8), that walks the plan
  top-to-bottom inside one daemon process and writes one
  `audit_events` row per step. Keep dry-run. Drop the resume logic:
  on failure, manual cleanup + re-run is acceptable for something
  that will execute 1-3 times. If provisioning frequency rises,
  the full saga can be added as an additive refactor.

### Finding 3 — Tickets subsystem is premature relative to historical volume

- **Severity**: LOW
- **Direction**: TOO BIG
- **Section of proposal**: §5 (Tickets subsystem), §12 Phase 3
- **Description**: The proposal ships two ticket types in v1, which
  is already a correct cut from the synthesis's four. That part is
  good. But historical ticket volume is 3 test tickets in 4 years
  (`NOTES.md`), and the research did not surface ticket pain as
  actually felt, only as a broken integration that the user wants
  off their plate. v1 still invests in claim mechanics, transcript
  backfill, requester-left-guild handling, panel deployment,
  ticket-to-application promotion, and a separate `tickets` state
  machine.
- **Why it matters**: Tickets are in v1 to close the
  ticketsbot.net vendor dependency, not because tickets are
  operationally acute. That's a legitimate reason, but it means v1
  is paying full cost for a subsystem whose runtime exercise is
  approximately zero per week. At 84 members this is probably
  fine — it's just a signal that the proposal's overall cost
  center is heavy.
- **Recommendation**: Accept the subsystem, but cut
  ticket-to-application promotion (see Finding 4) and do NOT treat
  tickets as a priority-peer with applications and activity. Phase
  3 can legitimately slip or be cut for time, and the proposal's
  sequencing (applications → activity → tickets → provisioning) is
  already compatible with that reality. Consider explicitly marking
  Phase 3 as time-boxed: if it slips, the dead ticketsbot panel can
  be removed manually and the ticket surface left bare.

### Finding 4 — Ticket-to-application promotion is scope smuggled in at the gate

- **Severity**: LOW
- **Direction**: TOO BIG
- **Section of proposal**: §5, ticket-to-application promotion flow
- **Description**: D7 locked "ticket-to-application promotion: kept
  in v1 scope. Low marginal implementation cost, prevents data loss
  for users who accidentally use the wrong queue." The rationale
  does not survive Humility's actual ticket history of 3 test
  tickets. The data-loss scenario being prevented is at most a few
  users per year and is recoverable with a copy-paste.
- **Why it matters**: Promotion adds a cross-subsystem coupling
  (`tickets.promoted_to_application_id` FK, a `promoted` ticket
  state, a modal/DM roundtrip to collect missing form fields) for
  a scenario the server has never actually produced. Every
  cross-subsystem FK is a thing that can go wrong during migration.
- **Recommendation**: Defer promotion to post-v1. Remove the
  `promoted` state from `app.ticket_state`, drop
  `promoted_to_application_id`, and remove the flow from §5. A
  user who files the wrong thing can close and re-open. Re-evaluate
  if real ticket volume ever materializes.

### Finding 5 — Append-only DB enforcement is one-person overhead without a concrete attacker

- **Severity**: LOW
- **Direction**: TOO BIG
- **Section of proposal**: §3, §8 ("Append-only durability is a
  database requirement, not a code-style preference")
- **Description**: The proposal mandates that four tables
  (`audit_events`, `application_status_history`,
  `application_form_versions`, `provisioning_steps`) must enforce
  append-only at the database layer via either `BEFORE UPDATE OR
  DELETE` triggers or a dedicated daemon Postgres role with
  `SELECT`+`INSERT`-only grants.
- **Why it matters**: Append-only enforcement is a correct posture
  for systems with untrusted clients or multiple writers. The
  proposal explicitly says (§9) "the daemon is the only application
  client and uses a service credential." The only entity that could
  mutate history is the daemon itself — i.e., the same entity whose
  correctness is already the control plane. Triggers or a
  second-role setup means a second set of Alembic migrations, a
  second grant surface, test coverage on the trigger body, and
  failure modes where a legitimate schema change is blocked by a
  trigger nobody remembers writing.
- **Recommendation**: Downgrade to a code-level convention enforced
  by CI (the same pattern already used in §8 for mutation
  primitives: no module outside a whitelisted file imports raw
  UPDATE/DELETE against those tables). If a second writer ever
  appears, promote to DB enforcement at that point. This is
  exactly the "reconsider RLS if a second client appears" posture
  §9 already takes.

### Finding 6 — Full staging-parity environment risks becoming meta-scope that never lands

- **Severity**: MEDIUM
- **Direction**: TOO BIG
- **Section of proposal**: §11 (Testing strategy), §12 Phase 0,
  §17 (Cost model)
- **Description**: §11 mandates a separate staging Discord guild,
  a staging Supabase project, and a Railway staging service, and
  §12 Phase 0 folds a "staging-parity checklist" into the
  foundations phase. The staging guild has to be hand-created by
  the user.
- **Why it matters**: Setting up and maintaining a parallel guild
  costs real calendar time: bot invite, intents, Captcha.bot
  setup, baseline roles, template category, keeping Supabase
  staging schema in sync, deploying a Railway staging service.
  For a one-person project, this is the kind of meta-scope that
  gets built once, decays over two weeks, and then the "tests"
  silently happen in prod. The proposal is right that a sandbox
  category inside live Humility is insufficient; it is less
  obviously right that a full second environment will actually
  stay in parity.
- **Recommendation**: Keep the staging Discord guild — it is the
  only honest way to exercise role/overwrite paths without
  touching live members. Cut the staging **Railway service** and
  the staging-parity checklist as a Phase 0 gate. Run the daemon
  locally against the staging guild during development, and push
  directly to production after tests pass. Keep the staging
  Supabase project on free tier (the proposal already plans this).
  This trims the cost model and removes one moving part that will
  otherwise rot.

### Finding 7 — Schema commits the team to expensive-to-change shapes

- **Severity**: MEDIUM
- **Direction**: ENTANGLED
- **Section of proposal**: §3 (`application_form_versions`,
  `activity_log`, `chapter_members`, ticket FK coupling)
- **Description**: Several schema choices are hard to walk back:
  the form_version snapshot model couples applications to an
  immutable versions table and a `schema_hash` publish workflow
  (§4); the `activity_log` superseded-row correction model commits
  to append-only logical history for activity data;
  `chapter_members` uses a composite unique key with `joined_at`
  that locks in the historical roster model.
- **Why it matters**: Each of these is a reasonable design *if it
  matches real operating behavior*. For Humility, nothing is yet
  known about whether chapters will revise forms at all, whether
  officers will routinely correct OCR rows (vs. reject+re-upload),
  or whether rosters will have enough churn to justify a
  joined/left_at history. Committing now is fine; committing now
  with append-only DB enforcement (Finding 5) + immutable triggers
  makes walk-back a migration story, not a code change.
- **Recommendation**: Pair with Finding 1 and Finding 5. The
  schema should be trimmable and the invariants enforceable in
  code during v1, so that the first few months of real use can
  tell the team which of these models is load-bearing before they
  are cemented.

### Finding 8 — Critical-path sequencing is correct and the Phase 0 bootstrap is the right hedge

- **Severity**: LOW
- **Direction**: OTHER (validation, not a problem)
- **Section of proposal**: §12 Phase 0, Phase 1, Phase 4
- **Description**: Option C is the right sequencing. The subtle
  move in §12 Phase 0 — requiring a hand-bootstrapped chapter
  before any feature phase runs — correctly removes the circular
  dependency where applications (Phase 1) would otherwise need
  provisioning (Phase 4) to exist first. Phase 4 then validates
  its automation against a real already-working chapter rather
  than against an invented spec-only target. This is the strongest
  sequencing move in the proposal.
- **Why it matters**: This is often the thing that goes wrong in
  multi-subsystem v1s, and it is handled. No change recommended.
- **Recommendation**: Accept. Keep the manual bootstrap
  requirement. If anything, the bootstrap is an argument for
  Finding 2 (drop the saga): since the first chapter is already
  going to be hand-provisioned, the automation subsystem's real
  value isn't "first chapter" but "N-th chapter," which further
  weakens the case for saga-level infrastructure.

### Finding 9 — Cost model understates staging Railway and free-tier assumptions

- **Severity**: LOW
- **Direction**: OTHER (cost calibration)
- **Section of proposal**: §17 (Cost model)
- **Description**: The table shows staging Railway at ~$5 and
  staging Supabase at $0 (free tier, auto-pause accepted).
  Railway does not have a free always-on tier for long-running
  containers; a second always-on service is more like $5-10
  minimum, matching the production line. Supabase free-tier
  auto-pause is acknowledged but worth being explicit that
  re-waking a paused project is a manual step before a staging
  test run.
- **Why it matters**: The cost model is directionally right and
  modest enough that the miscalibration doesn't change the
  build-vs-buy decision. It does affect the Finding 6
  recommendation: if staging Railway is closer to $10 than $5,
  the case for cutting staging Railway entirely is a bit
  stronger.
- **Recommendation**: Revise §17 to reflect prod Railway $5-10 +
  staging Railway $5-10 if kept, or cut staging Railway per
  Finding 6. Either way, total stays well under $50/month. Not a
  deal breaker.

### Finding 10 — OCR gold-set acceptance harness is real implementation budget not called out as scope

- **Severity**: LOW
- **Direction**: TOO SMALL (of budgeting, not of scope)
- **Section of proposal**: §11, §12 Phase 2a exit gate
- **Description**: §11 describes a gold set of Humility-style
  screenshots with expected rows and scores, and §12 makes passing
  that gate a phase 2a exit condition. Building the gold set
  requires collecting real screenshots, transcribing them by
  hand, and running the measurement. The proposal treats this as
  part of phase 2a but does not call out the labor.
- **Why it matters**: It's not zero work, it's the user's own
  daily time multiplied by N samples. If that labor gets skipped,
  phase 2a ships against unmeasured thresholds and the starter
  values in §6 (median confidence 0.85, <10% unmatched, ≥80%
  parse) become production defaults by default.
- **Recommendation**: Explicitly name gold-set construction as a
  phase 2a task, cap it at something like 20 representative
  screenshots to bound the labor, and do not treat the starter
  thresholds as the acceptance gate. This is a budgeting note,
  not a scope cut.

## Overall assessment

The proposal correctly identifies four subsystems that map to
documented Humility pain, sequences them with foundations first,
and hedges the provisioning circular dependency with a hand-built
first chapter. Those are the hard calls and they are right.

The MEDIUM verdict is driven by a consistent pattern across
several findings (1, 2, 5, 6, 7): v1 is being built with
invariants, guarantees, and infrastructure that only pay off at a
scale Humility will not see in the near term. A one-person
implementation budget spent on saga execution, append-only trigger
enforcement, a full-parity staging environment, and a 20-table
schema with nine enums is budget not spent on getting applications,
OCR calibration, and the manual first-chapter bootstrap stable.
The research was explicit that at 50-member scale most workflows
are still "recoverable by hand"; the proposal is writing them as
if they are not.

The recommended cuts are not structural — the four-subsystem
shape stays, Option C sequencing stays, the mutation safety
wrapper stays, the YAML-forms-with-DB-snapshot choice stays. The
cuts are targeted at the over-engineered machinery underneath
those features.

## What a LOW verdict requires

Any of the following would move the verdict to LOW:

1. Findings 1, 2, and 5 are addressed in the proposal (schema
   trimmed, provisioning saga replaced by a linear runner,
   append-only enforced in code not DB triggers). Finding 4
   (drop ticket-to-application promotion) must also be addressed
   because it's the smallest and lowest-cost cut and leaving it
   in signals the team is not willing to cut at all.
2. Or, the proposal explicitly defers one of the four subsystems
   (most plausibly tickets) to post-v1, which reduces the total
   implementation budget enough that the remaining
   over-engineering becomes affordable.

The verdict is MEDIUM, not HIGH, because none of these findings
invalidate the proposal's core design. They are rebalancing notes
on a structurally sound plan. Re-risk after revision; a revised
proposal with the cuts above is very likely to come back LOW.
