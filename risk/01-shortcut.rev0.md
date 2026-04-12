# Shortcut risk assessment — proposals/01-v1-scope.md

Date: 2026-04-11
Assessor: claude-opus (shortcut)

## Verdict

**MEDIUM**

The proposal avoids the obvious shortcuts its history predicts (SQLite,
hardcoded chapter IDs, split-by-question-type modals, shared Chapter*
roles) and explicitly rewrites those shapes. Shortcut risk is not in
those replaced areas. It is concentrated in three smaller places: a
ticket type whose handler role is known-empty, OCR acceptance
thresholds specified before the harness that is supposed to produce
them, and one undefined `JSONB` column on `chapters`. All three are
fixable with small edits to the proposal text and do not require a
redesign. The rest of the design pulls its weight — the saga-style
provisioner, the private-thread claim model, the snapshotting form
versions table, the bounded-mutation wrapper, and the preserve-don't-
delete archival posture are all principled, not shortcut-shaped.

## Findings

### Finding 1 — Moderator ticket type routes to a known-empty role

- **Severity**: MEDIUM
- **Pattern type**: DEFER-AS-WORKAROUND
- **Section of proposal**: §3 (`tickets.ticket_type` enum includes
  `moderator`), §5 (ticket routing: "`moderator`: moderation concerns,
  routed to `Moderator`, with `Staff` retained as watcher/override and
  `Trial Mod` granted read-only access"), §14 (anti-scope lists
  "Moderation tooling" as out of scope because "there are no active
  moderators")
- **Description**: v1 ships a `moderator` ticket type whose handler
  role is `Moderator`. `DECISIONS.md#D4` says "no moderation pain today
  because no mods currently exist (the `Moderator` role is empty...)".
  `NOTES.md` confirms the `Moderator` role has no members. §14
  explicitly defers moderation tooling for that reason. So v1 provisions
  a ticket route whose primary handler list is empty on day one; every
  mod ticket will fall through to the `Staff` watcher, which is the
  same handler as the `server_support` type. The proposal has shipped
  two ticket types that route to the same humans, plus a `Trial Mod`
  read-only audience that also has no members yet.
- **Why it matters**: this is the specific pattern the shortcut prompt
  calls out — "moderation tooling is listed as out-of-scope because
  'no mods today,' but the ticket subsystem includes a `moderator`
  ticket type that routes to an empty role." The half-solution
  introduces operator confusion (which queue does a staff member
  watch?), bakes a schema enum value that may be wrong once real mods
  exist, and carries provisioning weight (the mod queue channel, the
  `Trial Mod` overwrite, the private-thread seeding rules) for no
  reducible work. It is complexity paid now against a speculative
  future role model.
- **Recommendation**: drop `moderator` from `app.ticket_type` and from
  §5's four-type list for v1. When moderators exist, add the enum value
  and the routing rule via a normal additive migration — the schema
  policy is additive-first anyway (§13). If the owner wants a
  dedicated channel for mod-flavoured reports right now, make them
  `server_support` with a subject convention or post them into
  `#admin-chat`; don't ship a separate ticket type wired to zero
  humans. Alternatively, if the type must ship, the proposal must
  explicitly say "moderator tickets are handled by Staff until a
  Moderator role is populated" and drop `Trial Mod` from v1 entirely.

### Finding 2 — OCR acceptance thresholds specified before the harness that should produce them

- **Severity**: MEDIUM
- **Pattern type**: SYMPTOM MASK / HARDCODE
- **Section of proposal**: §6 ("The daemon should accept a Vision-only
  import when all of the following hold: median row confidence >= 0.85,
  fewer than 10% unmatched rows, no duplicate normalized names inside
  the same image, and at least 80% of score rows parse cleanly as
  integers. It should flag for review when confidence is between
  roughly 0.70 and 0.85..."), §11 ("OCR accuracy needs a real
  acceptance harness. Build a gold set of Humility-style screenshots
  with expected rows and scores. Measure: row detection recall,
  exact score accuracy, correct player-name normalization, unmatched-
  player rate, false acceptance rate on ambiguous screenshots.")
- **Description**: the proposal prescribes 0.85 / 0.70 / 10% /  80% as
  the acceptance-window numbers and separately says the gold-set
  harness is what measures OCR accuracy. The thresholds are therefore
  plausible-sounding defaults that are not derived from any
  measurement the proposal commits to running. Phase 2 (activity
  tracking) definition-of-done does not require the harness numbers
  to justify the thresholds before shipping. If the gold set shows
  0.85 is too aggressive (false accept on Gemini-disguised headers) or
  too conservative (most imports land in review and nothing gets
  accepted), the design number has to change, and there is no gate
  catching that.
- **Why it matters**: the "flag for review" state is exactly the
  catch-all bucket the shortcut prompt warns about — if the thresholds
  are wrong in the too-conservative direction, every import lands in
  review and the subsystem silently regresses to "OCR with human retype"
  while looking instrumented. In the too-aggressive direction,
  wrong rows get written to `activity_log` and then wrong members get
  flagged — which is exactly the failure mode the design is trying to
  avoid.
- **Recommendation**: rewrite §6 to describe the threshold
  *structure* (median row confidence + unmatched-rate + duplicate-
  name check + score-parse rate) without fixing the numbers, and add
  a Phase 2 exit gate: "thresholds are calibrated against the gold
  set in §11 before activity tracking ships; starter values are
  0.85/0.70 pending measurement." That sequences the calibration
  correctly and keeps the v1 scope honest about where the numbers
  come from. The schema does not need to change; the thresholds live
  in code, not rows.

### Finding 3 — `chapters.settings_json` is an undefined JSONB dumping ground

- **Severity**: LOW
- **Pattern type**: SCHEMA SHORTCUT
- **Section of proposal**: §3, `app.chapters` DDL: `settings_json JSONB
  NOT NULL DEFAULT '{}'::jsonb`
- **Description**: every other JSONB column in the schema has a clear
  stated purpose — `answers_json` holds form answers, `schema_json`
  holds the form schema snapshot, `raw_vision_response_json` holds
  Vision output, `spec_json` holds the provisioning spec,
  `preprocessing_json` holds the image preprocessing parameters,
  `request_payload` / `before_state` / `after_state` on audit events
  are intrinsically shape-varying. `chapters.settings_json` is the
  exception: the proposal never says what it contains. It is the
  classic "we haven't figured it out yet, leave a JSONB here"
  placeholder.
- **Why it matters**: an empty JSONB column becomes a receptacle for
  everything that couldn't be planned, and in a few months it will be
  mixing policy flags, feature toggles, channel IDs, and display
  preferences — i.e., exactly the shape that `activity_rules` gets
  a proper table for. D7 specifically chose DB rows over JSONB for
  activity rules; that reasoning applies here.
- **Recommendation**: drop the `settings_json` column from `chapters`
  in §3. If a concrete setting is needed later, add an explicit column
  via migration. The schema policy is additive-first so this costs
  nothing to defer.

### Finding 4 — `activity_flags.details_json` shape is unstated

- **Severity**: LOW
- **Pattern type**: SCHEMA SHORTCUT
- **Section of proposal**: §3, `app.activity_flags` DDL: `details_json
  JSONB NOT NULL`
- **Description**: the table already has `flag_date`,
  `computed_window_start/end`, `activity_rule_id`, and FK to the
  member. What fields does `details_json` carry? The proposal never
  says. A breach has a small, knowable shape (breached days, points
  per day, rule snapshot at evaluation time). Either this is
  structured data being smuggled into JSONB, or it is undefined.
- **Why it matters**: when officers dispute a flag (and they will),
  the flag must be reproducible from its own row. An opaque `details_json`
  without a documented shape makes dispute resolution a code-archaeology
  exercise.
- **Recommendation**: either (a) define the `details_json` shape in
  §6 — e.g., `{"breached_days": [...], "points_per_day": {...},
  "rule_snapshot": {...}}` — or (b) replace with explicit columns /
  a child `activity_flag_details` row. §6 is the right place because
  it already describes the rule evaluation flow.

### Finding 5 — Form "publish" trigger is not pinned

- **Severity**: LOW
- **Pattern type**: SOURCE/ARTIFACT CONFUSION
- **Section of proposal**: §4 ("Forms are YAML-authored in-repo and
  materialized into database snapshots on publish"), §3
  (`application_form_versions` table)
- **Description**: the proposal commits to the YAML-in-repo,
  DB-snapshot-on-publish pattern and to the `schema_hash` uniqueness
  constraint that prevents republishing identical content. It does
  not pin *what* triggers a publish. Options: a daemon startup
  reconciliation pass, a CLI command, an admin slash command, or a
  CI step on main-branch merge. Each has different drift properties.
  A daemon startup reconciliation is auto-magic but loses human
  review. A CLI command is explicit but can be forgotten. If the
  trigger isn't defined, YAML can silently drift from the DB —
  officer edits the YAML, nobody publishes, the daemon keeps rendering
  the old snapshot, and the git diff lies about what the live form
  is.
- **Why it matters**: this is a small version of the pre-research
  draft's biggest flaw — YAML as source of truth with no written
  reconciliation step. The schema protects identity (hash uniqueness)
  but nothing in the proposal catches "YAML changed, nobody
  published."
- **Recommendation**: add one sentence to §4 pinning the publish
  trigger — e.g., "Publishing is an explicit `discord_cli.py forms
  publish` command that reads the YAML, computes the hash, and
  writes a new `application_form_versions` row if the hash is new.
  Daemon startup logs a warning if any `application_forms` row's
  `current_version_number` does not match the hash of its YAML file
  on disk." That pins the source-of-truth direction and gives a
  drift alarm without making publish fully automatic.

### Finding 6 — Activity rules DB-authored, forms YAML-authored: two config surfaces, no documented boundary

- **Severity**: LOW
- **Pattern type**: SOURCE/ARTIFACT CONFUSION
- **Section of proposal**: §6 ("The activity rule 'DSL' should not be
  YAML. Officers need to edit operational thresholds from Discord, not
  from Git.") vs §4 (forms are YAML)
- **Description**: this is a D7 decision, not a proposal-invented
  split. For chapter-scoped config, the proposal lands on two
  different answers: forms via YAML publish, rules via Discord
  commands. Both are defensible individually. What the proposal does
  not do is tell an operator where to look to edit what. The next
  officer who wants to change the daily threshold will ask "where
  does that live — the form YAML or a Discord command?"
- **Why it matters**: this is recoverable — it's documentation, not
  architecture. But documentation rot compounds, and the proposal
  should call its own rule out while it's fresh.
- **Recommendation**: add a short "Configuration surface map" in §8
  or §10 that names which config lives in YAML (forms), which lives in
  DB rows edited from Discord (activity rules, chapter member
  roster, blacklist), and which lives in deploy env vars (credentials,
  OCR engine selection). That's one table.

### Finding 7 — Pre-research claim helper not flagged as needing rewrite

- **Severity**: LOW
- **Pattern type**: PRE-RESEARCH CARRYOVER (partial)
- **Section of proposal**: §8 ("The claim-visibility helper should be
  a first-class shared component... That helper is responsible for
  thread membership narrowing, queue embed update text, and durable
  audit logging."), §16 ("Which pieces of `daemon/claim.py` are worth
  keeping versus rewriting against the final watcher-aware claim
  model?")
- **Description**: `daemon/claim.py:claim_thread` narrows thread
  membership to `{claimer, requester}` and explicitly does not model
  watcher roles — Staff and Trial Mod in the ticket flows, Staff in
  the application flows. The proposal's claim model is watcher-aware
  (§5: "watcher-role members stay in the thread after claim"). So
  the pre-research helper has the wrong shape. The proposal correctly
  lists this in §16 as an open hookpoint question rather than
  pretending the old helper survives.
- **Why it matters**: not a shortcut per se — the proposal calls out
  the gap rather than hiding it. Flagging because the shortcut prompt
  specifically asks about pre-research carryover of wrong shapes.
- **Recommendation**: accept. §16 is the right place for this
  question; the hookpoint phase is where it gets answered. No
  proposal edit needed.

### Finding 8 — `audit_events.event_type` / `target_kind` / `target_ref` are stringly-typed

- **Severity**: LOW
- **Pattern type**: OTHER
- **Section of proposal**: §3, `app.audit_events` DDL
- **Description**: the schema uses enums for `application_state`,
  `ticket_state`, `audit_phase`, etc., but `event_type`, `target_kind`,
  and `target_ref` on `audit_events` are `TEXT`. This is a legitimate
  choice — audit event types are an open set and pinning an enum makes
  migrations churn — but the proposal should say so rather than leave
  it inconsistent with the rest of the schema.
- **Why it matters**: minor. The only risk is code writing
  freeform strings without a central definition, which defeats the
  "queryable audit log" goal.
- **Recommendation**: accept with a note in §3 that the audit event
  type taxonomy lives in a constants module in code rather than a
  schema enum, and that every emitter must go through that module.

### Finding 9 — Supabase RLS handwave

- **Severity**: LOW
- **Pattern type**: OTHER (accept)
- **Section of proposal**: §9 ("Row-level security is not a meaningful
  control plane in this design because the daemon is the only
  application client and uses a service credential.")
- **Description**: true in the current architecture. The Supabase
  `service_role` key bypasses RLS anyway, and `discord_cli.py` is
  operator-only and uses the same DB surface. The correct posture for
  a single-client system is schema isolation + network privacy, not
  RLS theater.
- **Why it matters**: accept, not actually a shortcut.
- **Recommendation**: accept. Worth one sentence in §9 clarifying
  that if a second client ever appears (web dashboard, read-only
  officer UI), RLS must be reconsidered — but that's a v2 concern
  that lives correctly in the anti-scope.

### Finding 10 — Provisioning saga without destructive rollback is principled, not a shortcut

- **Severity**: LOW
- **Pattern type**: OTHER (accept)
- **Section of proposal**: §7 ("Idempotency is handled with a saga-
  style workflow, not a fake global transaction..."), §13 ("preserve
  created roles/channels for audit unless the user explicitly
  approves destructive cleanup")
- **Description**: the shortcut prompt asks whether "leave orphaned
  roles" is a principled design or a cleanup-is-hard shortcut. In
  this proposal it is principled: the hard rule is preserve-don't-
  delete (D3, AGENTS.md First Principle #7), the bot holds
  Administrator so destructive cleanup is the single most dangerous
  action it can take, and the audit trail wants the orphan to exist
  until a human decides. This is exactly the right call for the
  risk posture.
- **Why it matters**: accept.
- **Recommendation**: accept.

## Overall assessment

The proposal's design is not a shortcut-shaped design. It replaces the
pre-research SQLite schema with a richer, explicit Postgres schema
(state enums, append-only history, provisioning steps, audit events).
It replaces the split-by-question-type modal logic in
`daemon/applications.py` with a split-by-component-count rule that
matches the actual Discord constraint. It replaces the claim helper's
wrong shape with a watcher-aware contract and flags the pre-research
helper as needing rewrite rather than quietly reusing it. It uses a
saga with explicit step rows rather than a fake transaction. It
snapshots form schemas so old submissions render against their own
version. None of those are shortcuts.

What is shortcut-shaped is smaller and concentrated:

1. A ticket type (`moderator`) whose handler role is known empty and
   whose subsystem (moderation tooling) is explicitly deferred in the
   same document. That is the specific "defer the feature but ship
   half of it anyway" pattern the prompt warns about.
2. OCR acceptance thresholds prescribed in §6 but measured in §11,
   with no phase-2 gate tying the two together.
3. `chapters.settings_json` with no defined shape.

These are fixable with edits to §3, §5, §6, and §11. They do not
require a redesign. Findings 4–9 are observations that can be
addressed inline without changing the shape of the proposal.

The verdict is MEDIUM because Finding 1 (moderator ticket type) and
Finding 2 (thresholds-before-harness) each meet the "proposal
introduces its own shortcut" criterion explicitly — the former is a
textbook defer-as-workaround half-solution, the latter is a textbook
hardcoded magic-number masquerading as design. Neither is fatal.
Both are small edits. A LOW verdict would require both to be
addressed; HIGH would require a shortcut that unwinds a load-bearing
design choice, and the proposal has none of those.

## What a LOW verdict requires

To move this assessment to LOW, the proposal must address at
minimum Findings 1, 2, and 3:

- Drop `moderator` from `app.ticket_type` for v1, or explicitly
  reclassify mod tickets as a Staff-handled variant of
  `server_support` until a Moderator role exists
- Rewrite §6's OCR thresholds as starter values, pin a Phase 2 exit
  gate that calibrates them against the §11 gold set, and state
  explicitly that the starter values are not design commitments
- Drop `chapters.settings_json`, or define what goes in it

Findings 4–9 should be addressed inline but do not gate the verdict
on their own.
