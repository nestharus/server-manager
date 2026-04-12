# Shortcut risk assessment — proposals/01-v1-scope.md

Date: 2026-04-11
Assessor: claude-opus (shortcut)

## Verdict

**LOW**

The proposal's design pulls its weight at every layer. The three
MEDIUM findings from the rev0 assessment (`moderator` ticket type
routing to an empty role, OCR thresholds prescribed before the
harness, and `chapters.settings_json` as undefined JSONB) are all
resolved in-text, not papered over. The remaining observations are
minor and do not meet the "introduces its own shortcut" bar.

What is positively strong: the proposal replaces pre-research
shortcuts (SQLite, shared `Chapter*` roles, split-by-question-type
modal flow, in-module session TTL) with real designs rather than
compat shims; it snapshots form schemas so old applications render
against their own version; it uses a saga with explicit step rows
rather than a fake global transaction; its rollback plan is
principled preserve-don't-delete, not cleanup-is-hard handwaving;
and every JSONB column in the schema now has a stated shape or an
explicit reason to be variable. The `moderator` and `chapter_incident`
deferrals are clean — neither appears in `app.ticket_type`, §5 lists
only two types, and §14 explains the reasoning in one paragraph
each.

## Findings

### Finding 1 — Rev0 Finding 1 resolved: `moderator` ticket type removed

- **Severity**: LOW
- **Pattern type**: DEFER-AS-WORKAROUND (resolved)
- **Section of proposal**: §3 enum, §5, §14
- **Description**: Rev0 flagged MEDIUM because v1 was shipping a
  `moderator` ticket type whose handler role is known empty. The
  current proposal resolves this: `app.ticket_type` contains only
  `server_support` and `chapter_support`; §5 describes only those
  two types; §14 explicitly defers `moderator` and `chapter_incident`
  with a stated reason ("prior plumbing to empty roles would be a
  half-solution"). There is no stray `Trial Mod` overwrite, no
  empty mod-queue channel, no split that routes two ticket types
  to the same humans. The half-solution pressure is gone.
- **Why it matters**: this was the load-bearing defer-as-workaround
  pattern. It is fixed.
- **Recommendation**: accept.

### Finding 2 — Rev0 Finding 2 resolved: OCR thresholds have an exit gate

- **Severity**: LOW
- **Pattern type**: SYMPTOM MASK / HARDCODE (resolved)
- **Section of proposal**: §6 and §12 Phase 2a exit gate
- **Description**: §6 now commits to the threshold *structure* —
  median row confidence, unmatched-rate, duplicate-name check,
  score-parse rate — and then says "Those are pending measurement,
  not fixed design commitments. The thresholds live in code, not
  DB rows, so calibration is a normal code change rather than a
  migration." §12 Phase 2a adds: "Exit gate: thresholds are
  calibrated against the gold set in §11 before phase 2a is
  declared done." Phase 2b is now explicitly conditional on 2a
  missing the calibrated gate. That sequences the measurement
  correctly: starter values ship, but phase 2a cannot close until
  calibration happens against the §11 gold set. If calibration
  shows the numbers are wrong, the fix is a code change before the
  phase closes.
- **Why it matters**: the "flag for review" bucket is no longer a
  parking lot for an uncalibrated pipeline. Either the threshold
  structure earns its place against measured accuracy, or phase 2a
  does not ship.
- **Recommendation**: accept.

### Finding 3 — Rev0 Finding 3 resolved: `chapters.settings_json` removed

- **Severity**: LOW
- **Pattern type**: SCHEMA SHORTCUT (resolved)
- **Section of proposal**: §3 `app.chapters` DDL
- **Description**: The `chapters` table no longer carries a
  `settings_json` column. It has `slug`, `display_name`, `game`,
  `description`, provenance, and archival columns — nothing else.
  Any future chapter-level setting has to earn an explicit column
  via migration, matching the D7 principle that chose DB rows over
  JSONB for activity rules.
- **Why it matters**: no placeholder JSONB dumping ground on the
  chapter row.
- **Recommendation**: accept.

### Finding 4 — Rev0 Finding 4 resolved: `activity_flags.details_json` shape defined

- **Severity**: LOW
- **Pattern type**: SCHEMA SHORTCUT (resolved)
- **Section of proposal**: §3 `app.activity_flags`
- **Description**: §3 now states explicitly that `details_json`
  "must be sufficient to reproduce the flag from the row alone and
  carries `{"breached_days": [ISO dates...], "points_per_day":
  {date: points}, "rule_snapshot": {threshold, window, operator,
  ...}}`." The shape is documented, the reproducibility requirement
  is stated, and dispute resolution becomes a row read rather than
  code archaeology.
- **Why it matters**: structured data is no longer smuggled into an
  opaque column.
- **Recommendation**: accept.

### Finding 5 — Rev0 Finding 5 resolved: form publish trigger pinned

- **Severity**: LOW
- **Pattern type**: SOURCE/ARTIFACT CONFUSION (resolved)
- **Section of proposal**: §4
- **Description**: §4 now says: "At publish time, `discord_cli.py
  forms publish` reads the YAML, computes the schema hash, and
  writes a new `application_form_versions` row if the hash is new.
  If the authored form would require more than five components,
  publish fails with a clear error and does not store the version.
  Daemon startup logs a warning if any
  `application_forms.current_version_number` does not match the
  hash of its YAML file on disk; that is a drift alarm, not an
  automatic republish." The source-of-truth direction is pinned
  (YAML → CLI → DB), the drift alarm exists, and publish cannot
  store a version that violates the single-modal capacity rule.
- **Why it matters**: the classic YAML-vs-DB drift failure mode is
  controlled by an explicit trigger plus a startup warning.
- **Recommendation**: accept.

### Finding 6 — Rev0 Finding 6 resolved: configuration surface map added

- **Severity**: LOW
- **Pattern type**: SOURCE/ARTIFACT CONFUSION (resolved)
- **Section of proposal**: §8 "Configuration surface map" table
- **Description**: §8 now carries a table mapping each config kind
  to its storage and editor: forms (YAML + DB snapshot, CLI
  publish), activity rules (DB rows, slash commands), roster (DB
  rows, slash + auto-upsert), blacklist (DB rows, slash), chapter
  registry (DB rows, CLI), secrets (Railway env vars), panel
  messages (Discord, owned by provisioning runs only). An operator
  asking "where do I edit this?" has one table to read.
- **Why it matters**: D7 split rules/forms across YAML and DB; §8
  makes that split legible rather than implicit.
- **Recommendation**: accept.

### Finding 7 — Rev0 Finding 8 resolved: audit taxonomy documented

- **Severity**: LOW
- **Pattern type**: OTHER (resolved)
- **Section of proposal**: §3 `app.audit_events`
- **Description**: §3 now states that `event_type`, `target_kind`,
  and `target_ref` "stay `TEXT` because the audit taxonomy is
  intentionally open-ended; the concrete event strings live in a
  code constants module and every emitter imports from there." The
  apparent inconsistency with the enum-heavy rest of the schema is
  justified, and the constants-module discipline is stated.
- **Why it matters**: no stringly-typed freeform sprawl; the
  taxonomy is pinned in code with a single source.
- **Recommendation**: accept.

### Finding 8 — Rev0 Finding 9 resolved: RLS revisit clause added

- **Severity**: LOW
- **Pattern type**: OTHER (resolved)
- **Section of proposal**: §9
- **Description**: §9 now frames the single-client RLS posture as
  v1-only: "If a second DB client ever appears later (web
  dashboard, read-only officer UI, or similar), row-level security
  must be reconsidered at that point." That names the exact
  trigger that would reopen RLS as a concern.
- **Why it matters**: the single-client justification is principled,
  not a handwave.
- **Recommendation**: accept.

### Finding 9 — `application_status_history.metadata_json` shape is undefined

- **Severity**: LOW
- **Pattern type**: SCHEMA SHORTCUT
- **Section of proposal**: §3 `app.application_status_history`:
  `metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb`
- **Description**: This is the one remaining JSONB column in the
  schema whose shape is not stated. Rev0 caught
  `chapters.settings_json` and `activity_flags.details_json`; this
  one slipped through. Its default is `'{}'`, so it is effectively
  optional, and the table's primary shape (from/to status, actor,
  reason, created_at) carries the load. Still, the cleanup is
  consistent with how the proposal now treats every other JSONB
  column, and this is the one outlier.
- **Why it matters**: low. A `NOT NULL DEFAULT '{}'` column cannot
  break reads, and the history row is usable without it.
- **Recommendation**: add one sentence to §3 stating what
  `metadata_json` may carry (examples would suffice) or drop the
  column until a concrete use case exists. Non-blocking for LOW.

### Finding 10 — Single-modal form cap is a scope commitment, not a shortcut

- **Severity**: LOW
- **Pattern type**: OTHER (accept)
- **Section of proposal**: §4 ("v1 supports single-modal forms only")
- **Description**: The proposal limits v1 to forms that fit inside
  one Discord modal (≤5 components). The pre-research `daemon/`
  draft attempted a split-flow design (ephemeral select menus →
  continue button → modal) and `forms/dark-nemesis.yaml` has 7
  components, so the v1 cap means Dark Nemesis as authored could
  not publish. That sounds like a shortcut at first glance ("we
  couldn't figure out multi-step forms, so we banned them"), but
  the proposal handles it honestly: `discord_cli.py forms publish`
  refuses to store a version that violates the cap, so the limit
  is enforced at publish time, not hidden at runtime. And the
  pre-research split flow required an in-memory `_pending_sessions`
  store (`daemon/applications.py`), which the proposal's
  "persistence before staff-facing side effects" principle would
  forbid anyway.
- **Why it matters**: accept. This is a deliberate v1 narrowing
  enforced by the publish path, not a silent bypass. §14 could
  mention multi-step forms explicitly, but the omission is minor —
  the publish-time failure is the real gate.
- **Recommendation**: optionally add "multi-step application forms"
  to §14. Non-blocking.

### Finding 11 — `chapter_members.source_application_id` is a bare UUID

- **Severity**: LOW
- **Pattern type**: OTHER
- **Section of proposal**: §3 `app.chapter_members`
- **Description**: `source_application_id UUID` has no `REFERENCES
  app.applications(id)` clause. Every other cross-table UUID in
  the schema carries an explicit FK. This is almost certainly
  intentional (roster history outlives applications in some flows,
  and an FK would force ON DELETE logic), but the proposal does not
  say so.
- **Why it matters**: minor. Data-integrity concern, not a
  shortcut.
- **Recommendation**: accept. Not a shortcut; referential integrity
  is covered elsewhere in the schema.

### Finding 12 — Pre-research claim helper correctly flagged

- **Severity**: LOW
- **Pattern type**: PRE-RESEARCH CARRYOVER (accept)
- **Section of proposal**: §8, §16
- **Description**: `daemon/claim.py:claim_thread` narrows thread
  membership to `{claimer, requester}` and does not model watcher
  roles. The proposal's claim model (§5, §8) is watcher-aware. §8
  describes the final shape ("the list of persistent watcher
  members to keep") and §16 flags the pre-research helper as an
  open hookpoint question rather than quietly reusing it. The
  pre-research wrong shape has been called out, not carried.
- **Why it matters**: accept.
- **Recommendation**: accept. The hookpoint phase is the right
  place to resolve it.

### Finding 13 — Saga without destructive rollback is principled

- **Severity**: LOW
- **Pattern type**: TRANSACTION SHORTCUT (accept)
- **Section of proposal**: §7, §13
- **Description**: "Leave orphaned roles" on provisioning failure
  is the correct posture given the bot holds `Administrator`, D3's
  preserve-don't-delete principle, and the `AGENTS.md` live-server
  rules. The rollback plan explicitly makes destructive cleanup "a
  separate, explicit, approved operation," not an automatic saga
  step. That matches the tier-3 mutation safety model.
- **Why it matters**: accept.
- **Recommendation**: accept.

### Finding 14 — Mixed OCR architecture is justified, not defensive

- **Severity**: LOW
- **Pattern type**: DEFENSIVE OVERENGINEERING (accept)
- **Section of proposal**: §6, §12 Phase 2b (conditional)
- **Description**: The research (`research/04-ocr-backends.md`)
  recommends a mixed classical-plus-LLM path precisely because
  neither is clearly sufficient on game HUDs alone. The proposal
  guards the complexity of that mixed path behind a Phase 2b gate:
  Gemini fallback and second-pass validation ship only if Phase 2a
  misses the calibrated accuracy gate. The simplest path (Vision
  only + human review) gets measured first, and complexity is
  added only if required.
- **Why it matters**: accept. This is the opposite of defensive
  overengineering — the fallback tier is deferred, not pre-built.
- **Recommendation**: accept.

### Finding 15 — Audit log duplication is justified, not "log everything"

- **Severity**: LOW
- **Pattern type**: OTHER (accept)
- **Section of proposal**: §3 `audit_events`, §5 ticket transcripts
- **Description**: Discord's 45-day audit retention does not cover
  the "keep everything forever" policy set in `DECISIONS.md#D4`.
  `audit_events` captures domain state transitions, not Discord's
  own audit log — actor, target, before/after, phase. The fields
  are purposeful (correlation_id for cross-row tracing, phase for
  saga visibility, target_kind/ref for query), not "log
  everything." Message tables are a separate retention copy keyed
  on D4's retention rule.
- **Why it matters**: accept.
- **Recommendation**: accept.

## Overall assessment

The rev0 verdict was MEDIUM based on three concrete findings. This
revision of the proposal addresses all three in the exact text
locations rev0 called out:

1. `moderator` ticket type is gone from `app.ticket_type`; §5 lists
   two types; §14 explains the deferral.
2. OCR thresholds in §6 are marked as starter values pending
   measurement, and §12 Phase 2a carries an explicit exit gate tied
   to the §11 gold set. Phase 2b is conditional.
3. `chapters.settings_json` is deleted; the chapters row has no
   undefined JSONB columns.

Four of rev0's smaller findings (Findings 4–6, 8, 9) are also
fixed inline: `activity_flags.details_json` has a documented shape;
§4 pins the form publish trigger; §8 adds a configuration surface
map; §9 adds an RLS revisit clause; §3 explains the stringly-typed
audit taxonomy.

Against that, the new observations (Findings 9–15) are small. The
only residual concrete edit worth considering is Finding 9
(`application_status_history.metadata_json` shape), which is a
one-sentence fix and not a verdict blocker. The rest are accept
entries that document why design choices are principled under
scrutiny.

The proposal's design is not shortcut-shaped. It replaces the
pre-research SQLite schema with a richer, explicit Postgres schema;
replaces `_pending_sessions` in-memory session state with a
publish-time capacity check and a persistence-before-side-effects
submission flow; replaces the pre-research claim helper's wrong
shape with a watcher-aware contract and flags the old helper for
rewrite; uses a saga with explicit step rows; snapshots form
schemas for historical rendering; gates the OCR fallback complexity
behind a measurement exit gate; and treats provisioning rollback as
preserve-don't-delete per the project's hard rule. None of those
are shortcuts.

## What a LOW verdict requires

The verdict is LOW because the proposal's design pulls its weight
at every layer — no deferred complexity masked as "out of scope,"
no JSONB dumping ground, no plausibly-but-unproven thresholds
without a measurement gate, no carryover of wrong shapes from the
pre-research draft, and no compatibility shims. Finding 9
(undefined `metadata_json` shape) is the only residual observation
worth a small edit, and it does not meet the "introduces its own
shortcut" bar on its own.
