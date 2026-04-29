READ:
- proposals/06-members-kind.md
- research/10-members-kind-problem-map.md
- .tmp/rca/discord-oauth-linking-FINDINGS.md
- ~/ai/workflows/implementation-pipeline.md (Phase 4)
- ~/ai/conventions/no-backwards-compatibility.md
- plans/BACKLOG.md (BL-008 decomposition; BL-016/017/018)
- plans/risk/init-124-scope.md (format reference; INIT-124 anti-scope
  carry-over)

# INIT-125A Scope-Risk Report

## Inputs read

- Proposal: `proposals/06-members-kind.md`.
- Problem map: `research/10-members-kind-problem-map.md`.
- RCA: `.tmp/rca/discord-oauth-linking-FINDINGS.md`.
- Pipeline rules: `~/ai/workflows/implementation-pipeline.md` §Phase 4.
- Backlog: `plans/BACKLOG.md` BL-008 (decomposed parent), BL-016
  (INIT-125B Discord OAuth provider), BL-017 (INIT-125C conversion
  service + application re-pointing), BL-018 (INIT-125D historical
  cleanup / read-hardening).
- Locked direction: RCA recommended fix shape lines 339-345
  ("Identity discriminator slice") and lines 376-380 ("INIT-125A:
  `members.kind` and guard migration"). Schema slice only. No OAuth,
  no conversion, no cleanup, no `linked_pending` enum value.

## Scope ↔ Anti-scope check

Each design change below is paired with the Scope clause it
satisfies and the Anti-scope clause it must not violate.

1. **Add Alembic migration `wu-043_members_kind.py` introducing
   `members.kind TEXT NOT NULL` with check constraint
   `kind IN ('discord', 'public_intake')`** (proposal §Scope lines
   37-39; §Design lines 89-135; Q1 lines 59-61; Q2 lines 63-65).
   - Scope: explicit lines 37-39 ("Add Alembic migration… add
     `members.kind TEXT NOT NULL`… backfill `public:%` rows to
     `public_intake` and all other rows to `discord`").
   - Anti-scope guard: "No `linked_pending` value in `members.kind`"
     (line 52). The check constraint is restricted to two values.
     RCA line 246 sketches a three-value enum including
     `linked_pending`; the proposal explicitly excludes it (proposal
     line 52, design lines 125-129) because BL-017 chose
     `member_links` supersession instead of an in-row pending state
     (RCA lines 256-259).
   - Anti-scope guard: "No Discord OAuth provider, Authentik source,
     OIDC callback, or applicant login/link route" (line 49). The
     migration is pure DDL plus a SQL backfill; no auth code, no
     callback route, no Authentik blueprint touched.
   - Anti-scope guard: "No conversion service, `member_links` table,
     synthetic-to-real promotion, or application re-pointing" (line
     50). The migration neither creates `member_links` nor mutates
     `applications.applicant_id`; downgrade explicitly says "It does
     not mutate `discord_user_id` or application references" (line
     137).
   - Anti-scope guard: "No read-side roster/trust cleanup, historical
     data sweep, or query-level roster hardening" (line 51). The
     backfill is one in-place `UPDATE members` keyed by the locked
     INIT-120 prefix; it does not delete, transition, or rewrite
     `roster_entries`, `trust_profiles`, `trust_signals`, or
     `applications.owner_id`.
   - Verdict: in scope. The migration is a discriminator-add only.

2. **Update `_MEMBER_SELECT`, `_insert_member()`, and
   `_member_from_row()` to read/insert/expose `kind`** (proposal
   §Scope lines 40-44; §Design lines 161-174, Q3 lines 67-69, Q4
   lines 71-73).
   - Scope: "Update member repository reads/inserts so fetched rows
     include `kind` and new rows persist it" (line 40); "Update
     `MemberRead` and the service mapper… to expose `kind`" (line
     41).
   - Anti-scope guard: "No caller-supplied `kind` in `MemberCreate`"
     (line 53). Proposal line 174 enforces this: "`MemberCreate`
     remains unchanged and must not accept caller-supplied `kind`."
     The `_kind` knob lives only on the private `_insert_member()`
     helper (line 69, line 204), keyed off whether the caller is
     `resolve_or_create_public_intake_member()` (then
     `public_intake`) or `create_or_get_member()` (defaulting to
     `discord`).
   - Anti-scope guard: "No conversion service…" (line 50). The
     repository changes do not add a re-classification path or a
     mutation that changes `kind` after insert; `kind` is set once
     on insert and selected on read.
   - Verdict: in scope. The internal-only `_kind` knob honors both
     the caller-contract preservation (Q3 line 69) and the no-
     caller-supplied anti-scope clause.

3. **Narrow `is_synthetic_member()` to member-like input and key it
   off `kind == "public_intake"`** (proposal §Scope line 42;
   §Design lines 139-152; Q5 lines 75-77).
   - Scope: "Change `is_synthetic_member()` to accept only
     member-like objects with a `kind` attribute/key and to return
     true only for `kind == 'public_intake'`" (line 42).
   - Anti-scope guard: "No rename of INIT-124 shipped error codes
     such as `trust_subject_synthetic_not_allowed`" (line 54). The
     helper change is an internal predicate swap; it does not
     change which error code each call site emits. Q7 lines 83-85
     explicitly preserve every shipped INIT-124 code, and §Design
     lines 178-200 walk each guard call site without renaming the
     emitted strings.
   - Anti-scope guard: "No conversion…" (line 50). The helper is
     read-only over `kind`; it does not promote, link, or re-point
     anything.
   - Verdict: in scope. The dropped string-input branch is the
     deliberate hard break called out in Q5 and convention-compliant
     (see §Convention compliance below).

4. **Migrate INIT-124 BL-005 guard call sites from
   `discord_user_id` strings to fetched member rows** (proposal
   §Scope line 43; §Design lines 176-200).
   - Scope: "Update INIT-124 BL-005 guard call sites to pass fetched
     member rows, not raw Discord id strings" (line 43).
   - Anti-scope guard: "No rename of INIT-124 shipped error codes"
     (line 54). Each of the six call-site sub-bullets in §Design
     (`applicant_synthetic_not_allowed`, `owner_synthetic_not_allowed`,
     `trust_subject_synthetic_not_allowed`,
     `roster_member_synthetic_not_allowed`,
     `leadership_alias_synthetic_not_allowed`,
     `member_status_synthetic_not_allowed`) names the existing code
     and the existing call site; no rename.
   - Anti-scope guard: "No read-side roster/trust cleanup…" (line
     51). Each guard call site is a write boundary or alias
     expansion (matching the INIT-124 cohort exactly), not a roster
     listing, compliance evaluation, succession-holder list, or
     trust profile read. Authority/leadership keeps the
     `synthetic_policy="reject"` for direct context and
     `synthetic_policy="omit"` for succession-plan handoff (lines
     191-192) — INIT-124's split policy is preserved verbatim.
   - Verdict: in scope. The migration is a one-for-one predicate
     swap inside the INIT-124 cohort, not an extension of it.

5. **Update fixtures and tests so `kind` is set on direct inserts
   and assertions move from prefix to kind** (proposal §Scope line
   45; Q6 lines 79-81).
   - Scope: line 45 ("Update fixtures and tests so real members
     default to `discord`, synthetic/public-intake members default
     to `public_intake`, and prefix-specific assertions become
     kind-specific assertions").
   - Anti-scope guard: "No Discord-visible mutation" (line 56). Test
     fixtures are API/DB level, not Discord-bot tests.
   - Anti-scope guard: "No sweep or deletion of existing synthetic
     rows" (anti-scope §50, §51). Test fixtures are inserts in
     ephemeral test databases; they do not mutate prod or
     `humility-local` rows.
   - Verdict: in scope.

## Implementation decisions inside scope?

Q1..Q7 from `## Implementation decisions taken in proposal`
(lines 57-85). Each must be implementable within the touched
surface named in the problem map (lines 22-32) and must not
require a deferred-anti-scope concession.

- **Q1 — Migration mechanics: nullable add → SQL backfill →
  `server_default=None` → `NOT NULL` → check constraint** (lines
  59-61). Touched surface: a new `migrations/versions/wu-043_*.py`
  file plus the existing `members` table. The pattern matches
  `wu-028a_permission_drift_widening.py:34-110` (cited by the
  proposal). No persistent `server_default`, so the migration does
  not become a deferred-stub backwards-compat shim. **In touched
  surface.**

- **Q2 — `revision = "wu_043_members_kind"`, `down_revision =
  "wu_041a_compliance_evaluations"`** (lines 63-65). Problem map
  line 22 confirms current Alembic head is `wu_041a` and that
  `wu_042_chapter_governance` is on a side branch off `wu_035`.
  The proposal locks the explicit `down_revision` rather than
  letting Alembic infer it. **Watch point**: Phase 6 should
  re-verify `alembic heads` before commit in case a newer head
  lands during implementation; the proposal anticipates this in
  problem map line 78. **In touched surface.**

- **Q3 — `create_or_get_member(db, request, actor)` external
  signature unchanged; private `_insert_member()` gets internal
  `_kind: MemberKind = "discord"` keyword; only
  `resolve_or_create_public_intake_member()` overrides it to
  `public_intake`** (lines 67-69). Touched surface:
  `services/api/app/services/members.py:116-206` and
  `services/api/app/repositories/members.py:58-79` (problem map
  lines 25-26). The internal-`_kind` boundary keeps caller contract
  stable while the new discriminator is internal-only — this is a
  single-entrypoint preservation, not a behavior-toggle shim
  (parallels INIT-124's preservation of
  `resolve_or_create_public_intake_member()`). **In touched
  surface.**

- **Q4 — Add `MemberKind = Literal["discord", "public_intake"]` and
  expose `kind` on `MemberRead`; `MemberCreate` does not accept
  `kind`** (lines 71-73). Touched surface:
  `services/api/app/contracts/members.py:18-32`,
  `services/api/app/services/members.py:87-96` (problem map line
  27). The exposed read field documents the locked enum so callers
  do not parse `discord_user_id`. The asymmetric write/read
  contract honors anti-scope line 53. **In touched surface.**

- **Q5 — `is_synthetic_member()` accepts member-like objects only
  (dict / Pydantic / object with `kind`); raw string input is
  dropped** (lines 75-77). Touched surface:
  `services/api/app/services/members.py:46-56` (problem map line
  26). The string branch is dropped because every production guard
  already fetches a member row before classifying (proposal line
  152 lists the five call sites). The dropped string branch is a
  deliberate hard break under `no-backwards-compatibility.md`, not
  a quiet renaming with adapter. **In touched surface.**

- **Q6 — Direct test inserts (conftest.py and the four named test
  modules) include `kind`; predicate test rewrites from prefix to
  kind** (lines 79-81). Touched surface:
  `services/api/tests/conftest.py:208-233`,
  `services/api/tests/test_synthetic_member_helper.py:10-54`,
  `services/api/tests/test_public_intake_synthetic_member.py:37-45`,
  `services/api/tests/test_public_intake_submit.py:54-62` (problem
  map line 32). **Watch point**: problem map line 47 also names
  `services/api/tests/public_intake_fixtures.py`,
  `services/api/tests/test_members.py`,
  `services/api/tests/test_roster.py`, and
  `services/api/tests/chapter_governance_helpers.py` as fixture
  sites that insert into `members` directly. Phase 6 must sweep
  every direct insert; the column is `NOT NULL`, so a missed
  fixture surfaces as a load-time error rather than silent drift.
  This is enumeration tightness, not scope creep — Q6 names the
  pattern, the broader fixture sweep is implementation-only.
  **In touched surface.**

- **Q7 — Preserve every shipped INIT-124 error code:
  `applicant_synthetic_not_allowed`, `owner_synthetic_not_allowed`,
  `trust_subject_synthetic_not_allowed`,
  `roster_member_synthetic_not_allowed`,
  `leadership_alias_synthetic_not_allowed`,
  `member_status_synthetic_not_allowed`** (lines 83-85). Touched
  surface: each named code is at an existing INIT-124 boundary
  (see proposal lines 178-200). Anti-scope line 54 explicitly
  forbids renames. The problem map (line 83) noted that the
  INIT-124 prose mixed `trust_subject_synthetic_not_allowed`
  (shipped) with `trust_member_synthetic_not_allowed` (proposal
  prose); INIT-125A correctly chooses the shipped code. **In
  touched surface.**

All seven Q-decisions are implementable inside the migration plus
the helper plus the same six guard call sites that INIT-124 owns.
None require a new schema table, a new public endpoint, OAuth
infrastructure, an Authentik client, a member-link record, an
application re-point, a roster/trust cleanup pass, a Discord
handler change, or a new Cedar authority.

## Out-of-scope discipline

The proposal lists deferrals as `## Out of scope for follow-up`
(lines 284-288). Cross-checked against `## Anti-scope` (lines
47-56) and `## Design`:

- **No Discord OAuth provider / Authentik Discord source / OIDC
  callback / applicant login route** (anti-scope line 49;
  out-of-scope line 286 routes to BL-016). Not in §Design. No
  edit to `gitops/channels/local/auth/authentik/`,
  `gitops/channels/local/auth/pomerium/`,
  `infra/scripts/bootstrap-infisical-auth.sh`, or any
  `services/api/app/api/v1/endpoints/me.py`-class authn surface.
  RCA lines 87-115 enumerate these as the BL-016 surface.

- **No conversion service / `member_links` table / synthetic-to-real
  promotion / application re-pointing** (anti-scope line 50;
  out-of-scope line 287 routes to BL-017). Not in §Design. The
  proposal does not add a `member_links` migration, does not
  introduce `services/api/app/services/member_linking.py` or
  `identity_linking.py` (RCA line 191-192 names these as the
  BL-017 surface), does not touch `applications.applicant_id`,
  and does not rewrite `applications.owner_id`. Downgrade
  explicitly preserves application FKs (proposal line 137,
  280-281).

- **No read-side roster/trust cleanup / historical data sweep /
  query-level roster hardening** (anti-scope line 51; out-of-scope
  line 288 routes to BL-018). Not in §Design. The migration
  backfill touches `members.kind` only, not `roster_entries`,
  `trust_profiles`, `trust_signals`, or `applications.owner_id`.
  No read-side filter is added to roster/trust/compliance read
  surfaces. RCA lines 201-227 explicitly defer this to BL-018,
  noting that `humility-local` currently has zero polluted
  roster/trust rows so an ambient cleanup pass is unnecessary.

- **No `linked_pending` enum value** (anti-scope line 52). Not in
  §Design. The check constraint is `kind IN ('discord',
  'public_intake')` (proposal line 128). RCA line 246 sketched
  three values including `linked_pending`; RCA lines 256-259
  acknowledged the cleaner enum if supersession lives in
  `member_links`. INIT-125A picks the cleaner enum because BL-017
  is committed to the `member_links` model.

- **No caller-supplied `kind` in `MemberCreate`** (anti-scope line
  53). Not in §Design. `MemberCreate` is unchanged (proposal line
  174). Public-intake gets `public_intake` only because the
  internal helper `resolve_or_create_public_intake_member()` is
  the one supported synthetic write path (problem map line 39,
  proposal lines 154-160).

- **No rename of INIT-124 shipped error codes** (anti-scope line
  54). Not in §Design. Q7 lines 83-85 enumerate the six shipped
  codes; §Design lines 178-200 reference each by the shipped
  string.

- **No Discord-visible mutation** (anti-scope line 56). Not in
  §Design. No edit to `services/discord/`, `daemon/`, or any
  Discord embed/command/thread/notification path. Problem map
  line 67 confirms this: "No Discord-visible mutation is part of
  this slice."

None of the listed follow-ups are silently in scope. The slice is
intentionally smaller than BL-008's parent scope and matches the
RCA's explicit "smaller first PR" recommendation (RCA lines
385-386: "If the project needs a smaller first PR, start with
INIT-125A. It reduces current classification risk without
committing to the final OAuth callback shape").

## Convention compliance

`~/ai/conventions/no-backwards-compatibility.md`:

- **Helper string-input branch is dropped, not adapter-wrapped.**
  Q5 (lines 75-77) and §Design line 152 are explicit:
  "Do not retain string-input support. Every production guard
  already fetches a member row before making the decision, so the
  call sites can pass the row directly." The new helper "fails
  loudly for raw strings or missing `kind` during tests"
  (line 77). There is no
  `is_synthetic_member_legacy(discord_user_id: str)` shim, no
  `accept_str: bool = False` flag, and no transition period
  during which both inputs are silently accepted. This is the
  convention's hard-break model: ship the new contract, delete
  the old one.

- **`SYNTHETIC_MEMBER_PREFIX` constant remains, but as an opaque
  hash format token, not as the discriminator.** Public-intake
  identifier generation still produces `discord_user_id =
  "public:<digest>"` for idempotency (proposal lines 156-158);
  the `public:` prefix continues to exist on the row, but it is
  no longer the synthetic-vs-real predicate — `kind` is. This is
  not a dual-discriminator shim; it is a deliberate separation
  of "ID format" from "row classification." **Phase 6 watch
  point**: the constant should remain because removing it would
  break public-intake idempotency, but its docstring/usage should
  reflect "opaque identifier hash format" rather than "synthetic
  member discriminator." This is hygiene, not a scope-gate
  failure.

- **`create_or_get_member()` external signature is unchanged.**
  This is single-entrypoint preservation, not a backwards-compat
  shim. The proposal explicitly addresses this at line 204:
  "This is a caller contract preservation, not a dual-behavior
  shim: all call sites are updated to the single `kind`
  discriminator, and string-prefix synthetic checks are deleted."
  No parallel `create_or_get_member_v2()`, no
  `USE_KIND_DISCRIMINATOR` flag, no per-environment opt-out. The
  internal `_kind` parameter on `_insert_member()` is keyed off
  the caller (which helper invoked the insert), not off a
  feature flag. This parallels INIT-124's single-shared-helper
  pattern (`_resolve_member_aliases(..., synthetic_policy=...)`).

- **`MemberCreate` unchanged; `MemberRead` adds the field.**
  Proposal line 174 confirms `MemberCreate` is not extended; only
  the read contract grows. There is no
  `MemberCreateWithKind` parallel class, no
  `MemberCreate.with_kind()` builder, and no deprecated wrapper.
  This is the convention's "ship clean changes" outcome: the
  write contract stays narrow, the read contract becomes
  explicit.

- **Migration drops temporary `server_default` before NOT NULL.**
  §Design lines 122-124 show the explicit
  `op.alter_column("members", "kind", server_default=None)` step
  before `nullable=False`. The migration does not leave a
  permanent default that future inserts would silently honor —
  this matches `wu-003b_audit_context_columns.py:17-38` (cited
  by the proposal). No `server_default` shim survives the
  migration.

- **Rollback drops the column rather than retaining a "v1
  fallback" path.** §Design lines 132-135 and proposal lines
  276-282 specify drop-constraint + drop-column. No rollback
  retention of a parallel old path; rollback is the inverse of
  the migration. Pre-existing `public:` prefix data on
  `discord_user_id` remains intact, so a re-deployed prefix-based
  guard would still work — that is recovery semantics, not a
  shim.

- **Test rewrites replace prefix assertions with kind
  assertions.** Q6 (lines 79-81) and proposal line 81 are
  explicit: prefix-specific assertions become kind-specific
  assertions, "while leaving the `public:` token format only
  where it remains part of public-intake idempotency." The old
  predicate test name (`test_is_synthetic_member_identifies_only_public_prefix`,
  problem map line 45) becomes kind-keyed; no "old behavior +
  new behavior" double assertion is kept.

The convention is honored: the proposal removes the prefix
predicate cleanly, drops the helper's string-input branch
without adapter, leaves no `linked_pending` partial-state
deferred stub, and uses single-entrypoint preservation rather
than dual-path shims.

## Adjacent-path discipline

Cross-check of proposal §Supported-surface track (lines 206-228),
§Anti-scope (lines 47-56), and §Out-of-scope follow-up (lines
284-288) against problem-map adjacents (lines 50-67) and RCA
adjacent surfaces.

- **INIT-120 public submit (`POST /api/v1/public/applications`)**:
  proposal line 219 and lines 224-225 explicitly preserve
  behavior. Public submit still resolves/creates a public-intake
  member, queues the application, returns the same receipt
  shape; only the inserted member row's `kind` field is new. The
  public route remains the one approved synthetic write path
  (proposal line 160; problem map line 39 carrying INIT-124's
  discipline forward). The receipt's `applicant_discord_user_id`
  still uses `public:` because that is the idempotency token,
  not a discriminator (test rewrite per Q6). **Not silently
  changed.**

- **INIT-124 BL-005 guards (authenticated submit, owner
  claim/reassign/reactivate, trust signal/compute/recompute,
  roster create, leadership alias reject/omit, member status
  PATCH)**: proposal lines 220, 226 explicitly preserve guard
  behavior — real members accepted, public-intake rejected, error
  codes stable; only the internal mechanism switches from prefix
  to `kind`. Each call site is enumerated in §Design lines
  178-200 with its shipped error code. **Behavior preserved;
  predicate source migrated.**

- **Discord submission flow
  (`services/discord/app/handlers/application_submission.py`)**:
  proposal line 221 and lines 227-228 preserve the path. The
  handler resolves a numeric Discord snowflake through
  `/api/v1/members/by-discord/{discord_user_id}`, calls
  `create_or_get_member()` (whose external signature is
  unchanged, defaulting `_kind="discord"`), and submits as the
  authenticated route. Q4's guard accepts `kind="discord"`, so
  the submission path "stays behaviorally unchanged" (proposal
  line 227). **Not silently changed.**

- **Discord onboarding and Discord roster sync**: not edited.
  Both paths handle real Discord snowflakes only; INIT-124
  guards already protected these surfaces from synthetic input
  via the prefix predicate, and INIT-125A swaps the predicate
  source without changing the surface. No edit to
  `services/discord/app/handlers/`. **Not silently changed.**

- **Audit substrate**: proposal line 228 is explicit: "`kind` is
  not audit-tracked in this slice. Regressions inside this slice
  include altering audit context, adding audit writes for `kind`,
  or changing existing audit row shape." No edit to
  `mutate_entity()` or `activity_actions`/`activity_state_changes`
  schemas. The INIT-120 audit pattern (`actor_kind="service"`,
  `actor_id="public-intake"` for synthetic creation) carries
  forward unchanged. **Not silently changed.**

- **Exact member reads (`/api/v1/members/{id}`,
  `/api/v1/members/by-discord/{discord_user_id}`)**: read
  contract grows by one field (`kind`). This is intentional and
  documented (Q4 lines 71-73; problem map line 80 calls out that
  exposing `kind` is "probably acceptable because `kind` is not
  sensitive and makes the identity contract explicit"). The
  Discord submission handler depends on exact lookup with
  numeric snowflakes; public-intake idempotency depends on
  `fetch_member_by_discord_id("public:<hash>")` working. Both
  continue to work because exact reads remain unfiltered. The
  added field is read-only and additive — pre-existing client
  parsers do not break unless they fail closed on unknown
  fields. **Additive, intentional cohort change.**

- **`POST /api/v1/members`**: not behaviorally changed.
  `MemberCreate` payload is unchanged (anti-scope line 53;
  proposal line 174); the response (`MemberRead`) gains `kind`
  (additive). All members created through this route get
  `kind="discord"` because public-intake never reaches this
  endpoint. **Additive read field; write contract unchanged.**

- **Roster reads, trust profile reads, compliance evaluations,
  archive counts, succession-plan holder lists,
  application-owner workload queries**: not edited. Anti-scope
  line 51 routes all read-side cleanup to BL-018. The proposal
  acknowledges in supported-surface (line 226) that pre-existing
  polluted reads are not repaired; that residual is BL-018's
  scope, and `humility-local` currently has zero such rows (RCA
  lines 79-85). **Not silently changed; residual named.**

- **Operational overview / `read_operational_overview()`**: not
  edited. No global member count is in scope. **Not silently
  changed.**

- **`linked_pending` and `member_links`**: explicitly out of
  scope (anti-scope line 52, line 50). No code path mentions
  these names. The downgrade migration leaves application FKs
  unchanged so BL-017 can introduce them later without unwinding
  this slice. **Out of scope; no silent foothold.**

The proposal swaps the synthetic-vs-real predicate from a magic
prefix to a typed column at exactly the seven surfaces the
INIT-124 cohort already covers, plus the three creation surfaces
that emit the column value (normal `create_or_get_member()`,
public `resolve_or_create_public_intake_member()`, test fixture
inserts). It does not silently mutate Discord submission, Discord
onboarding, Discord roster sync, audit substrate, the INIT-120
public-submit receipt, exact member read responses beyond the
additive `kind` field, trust profile reads, roster reads,
operational overview, compliance, archive, application-owner
workload queries, or any auth/Authentik/Pomerium configuration.

## Notable observations

1. **The migration head is locked explicitly to `wu_041a_compliance_evaluations`,
   not inferred.** Q2 (lines 63-65) names
   `down_revision = "wu_041a_compliance_evaluations"` and notes
   that `wu-042_chapter_governance.py` is on a side branch off
   `wu_035_application_interview`, so the Alembic graph has two
   leaves at the moment the proposal was authored. **Phase 6 watch
   point**: re-run `alembic heads` immediately before commit. If a
   new head lands during implementation (e.g. a parallel slice
   bumps to `wu_044_*`), the proposal's explicit chain choice
   needs an update — but this is implementation hygiene, not a
   scope-gate failure.

2. **`SYNTHETIC_MEMBER_PREFIX` constant is preserved as an
   idempotency hash format token, not as a discriminator.** The
   proposal does not explicitly say "delete the constant" because
   `resolve_or_create_public_intake_member()` still produces
   `discord_user_id = "public:<digest>"` (proposal line 158). This
   is a deliberate separation: `kind` becomes the classification
   contract, `public:` becomes an opaque hash format. Phase 6
   should keep the constant but ensure no new code path uses it
   as a synthetic-vs-real predicate. **Hygiene watch point, not
   scope creep.**

3. **Test fixture sweep is broader than Q6 enumerates.** Q6 (lines
   79-81) names four files (conftest, helper test, public-intake
   synthetic test, public-intake submit test). Problem map line
   47 identifies four additional files that insert into `members`
   directly: `services/api/tests/public_intake_fixtures.py`,
   `services/api/tests/test_members.py`,
   `services/api/tests/test_roster.py`,
   `services/api/tests/chapter_governance_helpers.py`. Because
   `members.kind` is `NOT NULL`, a missed insert surfaces at test
   load as an `IntegrityError`, not silent drift — but Phase 6
   must sweep them all. **Enumeration tightness, not scope creep
   — proposal line 45 covers "Update fixtures and tests" at the
   pattern level.**

4. **Helper signature drop is a hard break for any caller still
   passing strings.** Q5 (lines 75-77) is explicit that the
   string branch is removed and raw-string input fails loudly.
   Proposal line 152 enumerates the five production guard call
   sites that already fetch a member row. **Phase 6 watch point**:
   verify no test or service code path retained a string-passing
   call after the production migration. The "fail loudly during
   tests" wording in Q5 implies this is intentional; the test
   suite is the canary. **Convention-compliant hard break, not a
   silent rollback path.**

5. **The new `MemberRead.kind` field is read-only and additive.**
   Q4 (lines 71-73) exposes `kind` on the read contract but does
   not accept it on `MemberCreate`. Phase 6 should verify that
   `_member_from_row()` populates `kind` from the row (proposal
   line 174) and that no other code path constructs a
   `MemberRead` without `kind` (e.g. a synthetic test fixture
   model). Because `kind` is non-optional in the Pydantic model,
   any missing-field construction fails loudly. **Phase 6
   verification, not scope creep.**

6. **`humility-local` currently has 14 synthetic member rows and
   2 synthetic-applicant applications; zero roster/trust
   pollution.** RCA lines 73-85 confirm this. The migration's
   backfill must classify those 14 rows as `public_intake` and
   all other rows (including the canonical real members) as
   `discord`. The check `discord_user_id LIKE 'public:%'` is
   sufficient because Assumption A1 (proposal line 249) holds:
   Discord snowflakes are numeric, never `public:`-prefixed.
   This is consistent with INIT-124's A1, which the prior
   scope-risk report verified. **No new assumption surface
   beyond what INIT-124 cleared.**

7. **The proposal does not attempt to migrate INIT-120's
   `applicant_discord_user_id` receipt field.** The public-submit
   receipt still surfaces `public:<hash>` because it remains the
   idempotency token; only the predicate source migrates from
   prefix to `kind`. Test rewrites in Q6 reflect this: assertions
   move from "starts with `public:`" to "row has
   `kind='public_intake'`," but the `public:<hash>` format token
   itself stays. **Receipt shape preserved; classification
   contract migrated.**

## Verdict

```
SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
```

No assumption invalidates the supported surface. A1 (existing
rows are either `public:%` or numeric Discord IDs) is verified
by RCA local-database check (FINDINGS lines 73-85) and INIT-124's
already-cleared A1 carry-forward. A2 (all production
`INSERT INTO members` paths go through `_insert_member()`) is
verified by repository search (problem map line 25). A3
(`MemberRead` is the only public read contract and adding `kind`
does not break clients) is bounded by additive-read semantics
and an explicit invalidation path (proposal line 251).

The proposal stays cleanly inside Scope, honors the locked RCA
direction (schema discriminator only — no OAuth, no conversion,
no read-side cleanup, no `linked_pending`), keeps every
Anti-scope item out of §Design (no Authentik / Pomerium / Discord
OAuth wiring, no `member_links` table or conversion service, no
`applications.applicant_id` re-pointing, no roster/trust cleanup
or read-side filter, no `linked_pending` enum value, no
caller-supplied `kind` on `MemberCreate`, no INIT-124 error code
rename, no Discord-visible mutation), complies with
`no-backwards-compatibility` (the helper drops string-input as a
hard break, no `linked_pending` deferred stub, single-entrypoint
preservation on `create_or_get_member()` and
`resolve_or_create_public_intake_member()` rather than dual paths,
no permanent `server_default`, no version-gated rollout), and
does not silently mutate Discord submission, Discord onboarding,
Discord roster sync, audit substrate, the INIT-120 public-submit
receipt, exact member reads beyond the additive `kind` field,
trust profile reads, roster reads, operational overview, or
compliance/archive/owner-workload aggregates.

The migration-head re-check (notable observation 1), constant-as-
hash-format hygiene (notable observation 2), broader fixture
sweep (notable observation 3), string-input drop verification
(notable observation 4), and `MemberRead` non-optional construction
(notable observation 5) are Phase-6 implementation watch points
bounded by the proposal text, not scope-gate failures.
