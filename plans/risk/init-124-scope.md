READ:
- proposals/05-synthetic-member-guard.md
- research/08-synthetic-member-guard-problem-map.md
- .tmp/rca/synthetic-public-member-pollution-FINDINGS.md
- ~/ai/workflows/implementation-pipeline.md (Phase 4)
- ~/ai/conventions/no-backwards-compatibility.md
- plans/risk/init-122-scope.md (format reference)
- plans/BACKLOG.md (BL-005, BL-008)

# INIT-124 Scope-Risk Report

## Inputs read

- Proposal: `proposals/05-synthetic-member-guard.md`.
- Problem map: `research/08-synthetic-member-guard-problem-map.md`.
- RCA: `.tmp/rca/synthetic-public-member-pollution-FINDINGS.md`.
- Conventions: `~/ai/conventions/no-backwards-compatibility.md`.
- Phase-4 rules: `~/ai/workflows/implementation-pipeline.md` §Phase 4.
- Backlog: `plans/BACKLOG.md` BL-005 (this slice) and BL-008
  (deferred OAuth linking, read-side hardening, `members.kind`).
- Locked direction confirmed in problem map line 11 and RCA
  lines 132-148: query/service-boundary guard with one shared
  predicate `discord_user_id LIKE 'public:%'`, no schema column
  in this slice.

## Scope ↔ Anti-scope check

Each design change below is paired with the Scope clause it
satisfies and the Anti-scope clause it must not violate.

1. **Add `is_synthetic_member()` in
   `services/api/app/services/members.py` and a typed
   `SyntheticMemberNotAllowedError` in
   `services/api/app/contracts/members.py`** (proposal §Scope
   line 45; §Design lines 110-132).
   - Scope: "Add `is_synthetic_member()` in
     `services/api/app/services/members.py`" (line 45). The
     helper centralizes the `discord_user_id.startswith("public:")`
     predicate so call sites do not duplicate the magic string
     (proposal lines 113-120).
   - Anti-scope guard: "No schema migration" (line 55) and "No
     `members.kind`, `members.linked_at`, separate
     synthetic-member table, or namespace refactor" (line 56).
     The helper is a Python predicate over the existing
     `discord_user_id` column; it adds no migration, no new
     column, no new table, and no namespace move.
   - Anti-scope guard: "No SQL repository helper such as
     `member_exists_real(...)` for write-side queries in this
     slice" (line 58). The proposal explicitly declines the SQL
     helper at lines 204-207, citing public-intake idempotency
     and exact reads as reasons to keep canonical repository
     methods unfiltered.
   - Verdict: in scope; the surface is service-layer Python only.

2. **Add service-layer guards at the nine named write
   boundaries** (proposal §Scope line 46; §Design lines
   138-201).
   - Scope: "Add service-layer guards for authenticated
     application submit, application owner assignment,
     application claim, trust signal creation, trust compute,
     trust recompute, leadership alias expansion, roster entry
     creation, and member status mutation" (line 46).
   - Anti-scope guard: "No read-side roster hardening for
     compliance, archive counts, succession role-holder lists,
     or roster listing" (line 57). Each boundary in §Design is
     a write site or an alias-expansion site, never a roster
     read or aggregate count. The succession-plan branch uses
     `synthetic_policy="omit"` on alias collection (lines
     188), not a join into `roster_entries`, `compliance`, or
     archive aggregates.
   - Anti-scope guard: "No Discord OAuth linking or
     synthetic-to-real member conversion. Those belong to
     BL-008" (line 59). None of the nine guards convert,
     promote, or link synthetic rows; they only reject writes
     or omit aliases.
   - Anti-scope guard: "No sweep or deletion of existing
     synthetic rows, trust profiles, roster entries,
     application owners, or audit rows" (line 60). Every guard
     fires at write time. Pre-existing rows are explicitly
     left intact, including in the rollback path (lines
     328-329).
   - Verdict: in scope; nine guards are exhaustively the named
     write/alias sites and stop at the boundary the anti-scope
     draws.

3. **Keep `submit_public_application()` and
   `resolve_or_create_public_intake_member()` creating
   synthetic members; bypass via `_SubmissionAuthority.PUBLIC_INTAKE`**
   (proposal §Scope line 49; §Design lines 142-145).
   - Scope: "Keep `submit_public_application()` and
     `resolve_or_create_public_intake_member()` creating
     synthetic members" (line 49). The applicant guard is
     conditional on `submission_authority !=
     _SubmissionAuthority.PUBLIC_INTAKE` (line 143), and the
     positive component test asserts public submit still
     succeeds and `members.discord_user_id LIKE 'public:%'`
     (line 267).
   - Anti-scope guard: "No Discord-visible action" (line 61).
     The bypass is a private service-authority enum
     (`_SubmissionAuthority`); no Discord handler, command,
     embed, or thread is touched. The anti-scope is honored.
   - Anti-scope guard: "No sweep or deletion of existing
     synthetic rows" (line 60). Allowing public-intake to
     keep creating synthetic rows is consistent with leaving
     existing synthetic data and creation discipline alone.
   - Verdict: in scope; the one supported synthetic-creation
     path is preserved by the same authority enum that
     INIT-120 already established (problem map line 53).

4. **Add typed `SyntheticMemberNotAllowedError` mapping to
   stable HTTP 422 response codes instead of generic
   `validation_error`** (proposal §Scope line 47; §Design
   lines 124-136).
   - Scope: "Add typed error handling so guarded API surfaces
     return stable 422 response codes instead of generic
     `validation_error`" (line 47). The shared endpoint
     handler at `services/api/app/api/v1/endpoints/applications/_shared.py:171`
     currently maps generic `ValueError` to
     `{"code":"validation_error"}`; the proposal requires a
     specific synthetic-member branch before that fallback
     (line 134).
   - Anti-scope guard: "No Discord-visible action" (line 61).
     Stable HTTP error codes are API-only contract; no
     Discord embed text, ephemeral message, or notification
     uses these strings.
   - Verdict: in scope; the error contract is observable
     (stable codes are the proposal's primary observability
     signal at line 246) and stays inside the API service.

## Implementation decisions inside scope?

Q1..Q8 from `## Implementation decisions taken in proposal`
(lines 65-104). Each must be implementable within the touched
surface named in the problem map (lines 18-99) and must not
require a deferred-anti-scope concession.

- **Q1 — Helper lives in `services/api/app/services/members.py`**
  (lines 67). Touched surface: that module already owns
  member service semantics, exact member reads, status
  mutation, and the public synthetic creation point
  (`services/api/app/services/members.py:103`, `:167`, `:216`;
  problem map lines 41-44). No new module is introduced; the
  helper sits next to the synthetic creation site so the
  prefix string is centralized. **In touched surface.**

- **Q2 — Helper signature `is_synthetic_member(member_or_discord_user_id: object | str) -> bool`**
  (lines 71-78). Touched surface: a single Python predicate
  over `discord_user_id`. Repository rows pass
  `row["discord_user_id"]`; member-like objects pass through
  `getattr(...)`. The signature does not introduce a new
  protocol class, dataclass, or repository method, so it
  stays inside the touched surface and respects anti-scope
  line 58 (no SQL repository helper). **In touched surface.**

- **Q3 — Negative polarity `is_synthetic_member()` rather than
  positive `is_real_discord_member()`** (lines 81-83). Touched
  surface: helper naming only. The proposal explicitly cites
  the risk that a positive name "would invite call sites to
  duplicate the negation or conflate 'not synthetic' with a
  fully validated Discord snowflake" (line 82), which would
  expand scope into Discord-snowflake validation. The
  negative name keeps the contract tied to the locked
  discriminator `discord_user_id LIKE 'public:%'`. **In
  touched surface.**

- **Q4 — Authenticated `POST /api/v1/applications` rejects
  synthetic `applicant_id` with HTTP 422
  `applicant_synthetic_not_allowed`; public submit bypasses
  via `_SubmissionAuthority.PUBLIC_INTAKE`** (lines 86). Touched
  surface: `_submit_application_internal()` at
  `services/api/app/services/applications.py:572` (problem
  map line 52). The authority enum already exists; the
  proposal does not add a new authority value or rewrite the
  `_SubmissionAuthority` taxonomy. **In touched surface.**

- **Q5 — `PATCH /api/v1/members/{member_id}/status` rejects
  synthetic members** (lines 90). Touched surface:
  `patch_member_status()` after `_fetch_member_by_id_for_update()`
  (services/api/app/services/members.py:216, :227, :235;
  problem map line 44). The guard fires after the row lock
  and before transition validation, so it does not move the
  status state machine, the version contract, or the
  optimistic-locking ETag flow. **In touched surface.**

- **Q6 — Roster entry creation requires a UUID string that
  resolves to a non-synthetic member; no read-side rewrite
  of roster queries** (lines 94). Touched surface:
  `create_roster_entry()` before `_insert_roster_entry()`
  stores `request.member_id` (services/api/app/services/roster.py:117,
  :124, :131; problem map line 85). The proposal explicitly
  scopes this to write-side only (line 94: "Do not join or
  rewrite roster read queries in INIT-124"), which honors
  anti-scope line 57. The proposal acknowledges
  `roster_entries.member_id` is unconstrained `TEXT` (problem
  map line 31, line 165) but defers any schema/contract
  change to BL-008. **In touched surface.**

- **Q7 — Trust signal creation, trust compute, and trust
  recompute reject synthetic members at the service
  boundary; trust profile reads remain unchanged** (lines 98).
  Touched surface: `create_trust_signal()`, `compute_trust()`,
  `_recompute_once()` (services/api/app/services/trust.py:302,
  :375, :462; problem map lines 65-69). The proposal
  explicitly preserves `fetch_trust_profile_by_member_id()`
  and `list_active_signals_for_member()` repository reads
  (lines 98, problem map line 70-71), which honors
  anti-scope line 57 (no read-side hardening). **In touched
  surface.**

- **Q8 — Leadership alias expansion uses `synthetic_policy:
  Literal["reject", "omit"]`; direct
  `read_leadership_context()` rejects synthetic UUIDs;
  succession plan omits synthetic roster-derived holders;
  application owner workload queries do not get repository
  joins** (lines 102-104). Touched surface:
  `_resolve_member_aliases()` and `_collect_member_aliases()`
  in `services/api/app/services/authority.py:142, :159, :161`
  and the consuming sites in `read_leadership_context()`
  (`services/api/app/services/read_models.py:232, :247`) and
  `compute_succession_plan()`
  (`services/api/app/services/authority.py:493, :527`)
  (problem map lines 77-82). The split-policy argument
  honors both the rejection-clearer-for-direct-calls and
  omission-safer-for-pre-existing-roster-rows tradeoffs that
  the problem map's open question raised (lines 312-315).
  Owner workload queries are explicitly not joined into
  `members` (line 104), so anti-scope line 57 stays intact.
  **In touched surface.**

All eight Q-decisions are implementable inside the helper
plus the nine boundary checks. None require a new schema
column, a new repository method, a new endpoint, a new Cedar
authority, a Discord handler change, or a sweep over
existing rows.

## Out-of-scope discipline

The proposal lists deferrals as `## Out of scope for follow-up`
(lines 334-337). Cross-checked against `## Anti-scope`
(lines 53-61) and `## Design`:

- **No schema migration / no `members.kind` column** (anti-scope
  lines 55-56; out-of-scope line 336). Not in §Design. The
  helper is a Python predicate, not a column read or DDL
  change. The proposal does not author a new
  `migrations/versions/*.py`, does not edit `wu-011_members.py`,
  and does not assert a backfill of `discord_user_id LIKE
  'public:%'` to a kind discriminator. RCA recommendation #3
  (FINDINGS lines 174-178) explicitly says the schema
  discriminator "likely belongs after or alongside OAuth-linking
  cleanup," and the proposal honors that deferral.

- **No read-side roster hardening for compliance, archive
  counts, succession role-holder lists, or roster listing**
  (anti-scope line 57; out-of-scope line 336). Not in §Design.
  The problem map enumerates the read-side surfaces
  (`list_current_roster_members_by_chapter`,
  `run_scheduled_compliance_evaluations`,
  `compliance_review`, `list_active_roster_entries_for_chapter`,
  `list_latest_role_holders` — problem map lines 87-90,
  169-178). None of those repositories or services are
  edited. The succession-plan path uses alias-policy
  filtering (Q8) rather than rewriting `list_latest_role_holders()`,
  so the read query stays unchanged. RCA Method 2 (FINDINGS
  lines 166-173) explicitly defers roster/read-side
  hardening to BL-008.

- **No Discord OAuth linking or synthetic-to-real member
  conversion** (anti-scope line 59; out-of-scope line 336).
  Not in §Design. No code path links `members.discord_user_id`
  back to a real Discord snowflake, no
  `services/discord/app/handlers/*` is edited, no Authentik
  client is configured, and no
  `resolve_or_create_public_intake_member()` consumer is
  taught to "promote" a row. The locked direction in problem
  map line 11 ("Do not add a schema column in this slice")
  is honored.

- **No SQL repository helper for write-side queries** (anti-scope
  line 58). Not in §Design. The proposal explicitly declines
  the SQL helper at lines 204-207. Canonical repository
  methods `fetch_member_by_id()` and
  `fetch_member_by_discord_id()` remain exact and unfiltered
  (problem map lines 38-39; FINDINGS lines 50-51), which
  public-intake idempotency depends on.

- **No sweep or deletion of existing synthetic rows, trust
  profiles, roster entries, application owners, or audit
  rows** (anti-scope line 60; out-of-scope line 337). Not in
  §Design. Rollback explicitly says "Keep synthetic member
  rows, applications, audit rows, trust rows, and roster
  rows intact" (line 329). Pre-existing pollution is
  acknowledged in §Supported-surface track blast-radius
  (line 235) and routed to BL-008 / a dedicated cleanup
  slice.

- **No Discord-visible action** (anti-scope line 61). Not in
  §Design. No Discord embed, command, thread, ephemeral
  message, or guild API call is added or modified. The new
  HTTP 422 error codes are API-only.

None of the listed follow-ups are silently in scope. The
slice is intentionally smaller than BL-008, as the proposal
states explicitly at line 41: "It prevents new pollution but
does not hide, migrate, or repair any already-polluted read
rows."

## Convention compliance

`~/ai/conventions/no-backwards-compatibility.md`:

- The synthetic creation path stays as-is in the INIT-120
  helper. `resolve_or_create_public_intake_member()` is the
  one supported source of synthetic members (proposal line 49,
  problem map line 42), and INIT-120 owns the `public:`
  prefix contract (problem map line 254, FINDINGS lines
  118-127). The proposal does not introduce a parallel
  `resolve_or_create_public_intake_member_v2()`, a feature
  flag like `USE_NEW_SYNTHETIC_HELPER`, or a deprecated alias
  on the existing helper. There is no transitional dual
  creation path.
- The proposal does not version-gate the guard. There is no
  `if env.allow_synthetic_owner_assignment:` branch, no
  staged rollout flag like `ENABLE_SYNTHETIC_GUARD_FOR_TRUST`,
  and no per-environment opt-out. All nine boundaries flip
  on with the code change.
- `SyntheticMemberNotAllowedError` is a new typed exception,
  not a renamed-with-alias of an existing class. The
  proposal explicitly says it is added in
  `services/api/app/contracts/members.py` (line 124), and
  the existing generic `ValueError → validation_error`
  fallback is preserved unchanged at the same call site
  (line 134) — the new branch is added before the fallback,
  not as a deprecated wrapper around it.
- The shared submit helper `_submit_application_internal()`
  is not duplicated for "old behavior vs new behavior." The
  proposal adds one branch keyed off the existing
  `_SubmissionAuthority` enum (lines 142-145) rather than
  forking the function. Public submit and authenticated
  submit continue to share the helper, which keeps the
  authority taxonomy as the single discriminator.
- The leadership alias expansion adds a `synthetic_policy:
  Literal["reject", "omit"]` argument (line 186) rather
  than introducing a parallel `_resolve_member_aliases_v2()`.
  Two consumer sites pass distinct policy values; no
  transitional adapter sits between them. This is a single
  signature change, not a dual-path migration.
- Rollback (lines 326-332) is reverse-the-branches plus
  reverse-the-error-mappings, with synthetic data preserved.
  This is consistent with the convention: revert the code,
  not maintain a parallel "old guard / new guard" toggle.

The "no-backwards-compatibility" convention is honored: the
proposal does not introduce a transitional shim, a feature
flag for the old behavior, or a deprecated alias. The
synthetic creation path stays as-is — single source of
truth in `resolve_or_create_public_intake_member()` —
because that is the one supported path by design, not as
a compatibility concession.

## Adjacent-path discipline

Cross-check of proposal §Supported-surface track (lines
209-248), §Anti-scope (lines 53-61), and §Out-of-scope
follow-up (lines 334-337) against problem-map adjacents
(lines 73-99) and FINDINGS adjacent surfaces (lines
80-82, 187-263).

- **Discord application submission**: anti-scope line 61
  ("No Discord-visible action"). No edit in §Design.
  `services/discord/app/handlers/application_submission.py`
  resolves the interaction actor through
  `/api/v1/members/by-discord/{discord_user_id}` using a
  numeric Discord snowflake and posts authenticated
  `/api/v1/applications` as that member (problem map line
  97, FINDINGS line 80). The handler cannot naturally pass
  a `public:<hash>` value because Discord IDs are numeric
  snowflakes (FINDINGS lines 113-117). The Q4 guard fires
  on the API side, so the Discord submit path "should
  continue to pass" (proposal line 225) without any
  handler-side change.
- **Discord onboarding**: not edited. The handler reads
  `discord_user_id` from a Discord join event and computes
  trust for that real member (problem map line 98, FINDINGS
  line 81). Trust compute's Q7 guard rejects synthetic
  members, but onboarding always passes a real Discord
  snowflake, so this path "should continue to pass"
  (proposal line 226).
- **Discord roster sync**: not edited. The handler converts
  member IDs with `int(user_id)` during guild resolution
  (problem map line 99, FINDINGS line 82), so a `public:<hash>`
  value would fail the int conversion, not silently
  pollute. The proposal correctly stops synthetic roster
  events at roster-write time (Q6 guard) rather than
  retrofitting Discord mutation code (proposal line 227).
- **Audit substrate**: not edited. INIT-120 already routes
  public intake audit rows with `actor_kind="service"` and
  `actor_id="public-intake"` while storing the synthetic
  member as the `applications.applicant_id` subject
  (proposal lines 104, 228; problem map lines 29, 199-200).
  The new HTTP 422 rejections do not write audit rows —
  they short-circuit before service execution, so no
  `activity_actions` row is created for a rejected synthetic
  attempt. This is consistent with existing rejected-write
  semantics.
- **INIT-120 public submit (`POST /api/v1/public/applications`)**:
  anti-scope-equivalent on the supported surface (proposal
  line 221). The proposal explicitly preserves it: the
  applicant guard at `_submit_application_internal()` line
  594 is gated on `submission_authority !=
  _SubmissionAuthority.PUBLIC_INTAKE` (proposal line 143),
  and `submit_public_application()` continues to call
  `resolve_or_create_public_intake_member()` and submit
  through `_SubmissionAuthority.PUBLIC_INTAKE` (proposal
  lines 145, 229). The positive component test confirms
  HTTP 201 and `members.discord_user_id LIKE 'public:%'`
  on the public-submit path (proposal line 267). INIT-120
  is not silently changed.
- **Authenticated `POST /api/v1/applications`**: behavior
  changes by design — synthetic `applicant_id` now returns
  HTTP 422 instead of being silently accepted (problem map
  line 51, 137-140). This is the named risk reduction, not
  a silent change to an adjacent path. The proposal cohort
  list (line 219) explicitly names authenticated application
  submit as in the rejection cohort.
- **Application transitions (`/api/v1/applications/{id}/transitions`)**:
  three transition branches (`claim`, `reassign`, `reactivate`)
  now reject synthetic owners with stable HTTP 422 codes
  (proposal lines 147-163; problem map lines 226-228). This
  is intended new behavior on a named cohort (line 219), not
  a silent adjacent change.
- **Trust endpoints (`/api/v1/trust/signals`,
  `/api/v1/trust/compute/{id}`, `/api/v1/trust/recompute/{id}`)**:
  three new HTTP 422 rejection paths for synthetic
  `member_id` (proposal lines 165-181; problem map lines
  234-240). The trust profile read endpoint
  `GET /api/v1/trust/{member_id}` is explicitly not changed
  (proposal Q7, lines 98), so existing trust profile reads
  for any pre-existing synthetic profile rows continue to
  return today's response. No silent read-side change.
- **Member exact reads (`/api/v1/members/{member_id}`,
  `/api/v1/members/by-discord/{discord_user_id}`)**: not
  edited. Exact reads remain unfiltered (proposal line 48,
  234; problem map line 43). This is intentional — the
  Discord submission handler depends on
  `/api/v1/members/by-discord/{discord_user_id}` exact
  lookup with a numeric snowflake, and public-intake
  idempotency depends on
  `fetch_member_by_discord_id("public:<hash>")` working
  (FINDINGS line 51). Anti-scope is honored.
- **Member status (`PATCH /api/v1/members/{member_id}/status`)**:
  behavior changes for synthetic UUIDs (Q5; proposal lines
  197-201). Real member status mutation behavior is
  unchanged. Cohort list at line 219 covers this.
- **Roster endpoints (`POST /api/v1/roster-entries`)**:
  synthetic `member_id` now rejected at create time (Q6;
  proposal lines 191-195). Roster get/transition endpoints
  are not edited (problem map lines 244-245), and roster
  read queries are not joined to `members` (Q6 line 94).
  No silent read-side change.
- **Authority/read-model endpoints
  (`/api/v1/members/{member_id}/leadership-context`,
  `/api/v1/chapters/{chapter_id}/succession-plan`)**: Q8
  applies split policy (reject for direct, omit for
  succession; proposal lines 183-188; problem map lines
  79-82, 246-250). Direct leadership for a synthetic UUID
  changes from "expand to `public:<hash>` aliases" to
  "HTTP 422 reject" — this is the named risk reduction.
  Succession plan changes from "include synthetic
  roster-derived holders in alias sets" to "omit synthetic
  roster-derived holders" — same named risk reduction.
  Neither is a silent change; both are listed in the
  cohort and observability sections (lines 219, 246).
- **Operational overview / `read_operational_overview()`**:
  not edited. FINDINGS line 100 confirmed no production
  global member count exists, and the overview's
  application/ticket/effect/drift counts are unchanged.
- **Compliance, archive, scheduled-evaluation paths**:
  not edited. Anti-scope line 57 explicitly defers
  read-side roster hardening, and FINDINGS lines 86-95
  enumerate these surfaces as deferred to a later slice.
  Pre-existing polluted roster entries can still produce
  compliance evaluations and archive counts; the proposal
  acknowledges this in blast-radius (line 235) and
  observability residual (line 248).
- **Audit/review actor fields**: anti-scope-equivalent.
  `application_reviews.actor_id` and
  `activity_actions.actor_id` remain text actors (problem
  map lines 28-29). The proposal makes "synthetic members
  are never valid `actor_id` values for public intake"
  explicit (line 104) by relying on the existing INIT-120
  audit pattern (`actor_kind="service"`,
  `actor_id="public-intake"`), not by mutating audit rows.
- **Application owner workload queries
  (`list_open_applications_for_owner_ids`)**: not joined to
  `members` (Q8 line 104). Pre-existing synthetic owner IDs
  may still appear in the workload list; proposal line 235
  acknowledges this and routes the cleanup to BL-008.

The proposal blocks new synthetic pollution at nine named
write boundaries and one alias-expansion split, and it does
not silently mutate Discord submission, Discord onboarding,
Discord roster sync, audit substrate, INIT-120 public route,
exact member reads, trust profile reads, roster reads,
operational overview, compliance, archive, or owner
workload queries.

## Notable observations

1. **The locked discriminator is a magic prefix, not a column.**
   Assumption A1 (proposal lines 252) and FINDINGS lines
   118-127 establish that `discord_user_id LIKE 'public:%'`
   is sound because Discord snowflakes are numeric strings.
   The proposal's helper centralizes the prefix string at
   `SYNTHETIC_MEMBER_DISCORD_ID_PREFIX = "public:"` (line 113)
   so future migration to `members.kind` (BL-008) only
   touches this constant and the helper body. **This is good
   convergence discipline, not scope creep.**

2. **The `synthetic_policy` argument is a single-signature
   change, not a parallel function.** Q8 introduces
   `_collect_member_aliases(..., synthetic_policy: Literal["reject",
   "omit"])` with two consumers (proposal lines 183-188).
   Phase 6 should verify that `_resolve_member_aliases()` and
   `_collect_member_aliases()` are not duplicated into
   `_v2` variants — the convention requires one function with
   a policy parameter, not a dual-path migration.

3. **Roster `member_id` is `TEXT` and the write guard depends
   on UUID parsing.** Q6 (line 94, problem map line 31, line
   165) requires that `request.member_id` "parse as a UUID
   string … and reject if missing or synthetic." Phase 6
   should verify the parse step preserves existing non-UUID
   error semantics (HTTP 422 or 404 per implementation
   convention, but not the synthetic code per proposal line
   195) so callers that pass legitimate non-UUID strings
   today are not retroactively reclassified as
   synthetic-rejection cases. **This is enumeration
   tightness, not scope creep — the contract is explicit.**

4. **The proposal explicitly declines a SQL repository helper.**
   Lines 204-207 say "Do not add a SQL repository helper such
   as `repository.member_exists_real(...)` in this slice"
   because public-intake idempotency depends on canonical
   exact lookup. Anti-scope line 58 reinforces this. Phase 6
   must not add `member_exists_real()` or any SQL-side
   `WHERE discord_user_id NOT LIKE 'public:%'` predicate to
   `repositories/members.py` even as a "small helper" —
   that would silently expand into the BL-008 surface
   (read-side hardening).

5. **The synthetic creation path is preserved exactly.**
   `resolve_or_create_public_intake_member()` is the one
   supported source of synthetic members
   (problem map lines 41-42; FINDINGS line 54). The proposal
   does not introduce a parallel `_v2`, a "use_old_synthetic"
   flag, or a deprecated alias. The `public-intake` audit
   actor and `_SubmissionAuthority.PUBLIC_INTAKE` enum value
   carry over from INIT-120 unchanged. This is the
   convention's "ship clean changes" outcome, not a
   transitional shim.

6. **Pre-existing-pollution residual is named, not silently
   accepted.** Proposal blast-radius (line 235) says
   "Pre-existing synthetic owners, trust profiles, roster
   entries, and aliases are not repaired. Reads over those
   rows may still show polluted data until BL-008 or the
   cleanup sweep." Out-of-scope follow-up (line 337)
   re-states the routing. The residual is captured in the
   to-be-written `plans/risk/init-124-test-residuals.md`
   per proposal line 51, 314. **This is the
   no-deferred-stubs-compliant pattern: bounded residual,
   named follow-up, not a silent partial migration.**

## Verdict

```
SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
```

No assumption invalidates the supported surface: A1 (the
`public:` prefix is stable because Discord snowflakes are
numeric strings) is verified by Discord developer
documentation and three local sources (FINDINGS lines
118-127); A2 (only INIT-120's helper writes `public:`-prefixed
member rows) is verified by repository search at
`services/api/app/services/members.py:175` (proposal line
253); A3 (pre-INIT-120 roster entries do not contain
synthetic UUIDs) is bounded with an explicit invalidation
path that routes to a separate cleanup slice (proposal line
254). The proposal stays cleanly within Scope, honors the
locked direction (write-boundary guard only, no
`members.kind` schema column, no Discord OAuth linking, no
read-side hardening), keeps every Anti-scope item out of
§Design (no schema migration, no schema column or table, no
read-side join over `roster_entries`/compliance/archive, no
SQL repository helper, no OAuth linking, no sweep over
existing rows, no Discord-visible action), complies with
`no-backwards-compatibility` (single owning helper, single
shared submit function with one authority-keyed branch,
single alias-expansion function with a policy argument, no
transitional dual paths, no version-gated rollout), and
does not silently mutate Discord submission, Discord
onboarding, Discord roster sync, audit substrate, the
INIT-120 public route, exact member reads, trust profile
reads, roster reads, the operational overview, or
compliance/archive/owner-workload aggregates. The
roster-`TEXT`-parse, single-signature alias policy, and
SQL-helper-decline guards in notable observations 2, 3,
and 4 are Phase-6 implementation watch points bounded by
the proposal text, not scope-gate failures.
