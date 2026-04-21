# SLICE-016 Shortcut Risk Assessment

**Rating: LOW**

## Scope

Reviewed `.pipeline/proposal.md` and `.pipeline/synthesis.md` against
`.pipeline/research.md`, `AGENTS.md` §"No Backwards Compatibility"
(lines 564-576) and §"No Deferred Stubs" (lines 580-585), and the
current SLICE-007 trust substrate:

- `services/api/app/services/trust.py`
- `services/api/app/repositories/trust.py`
- `services/api/app/contracts/trust.py`
- `services/api/app/api/v1/endpoints/trust.py`
- `services/api/app/services/mutations.py`
- `services/api/app/api/v1/endpoints/roster.py` (manual-authority reference)

The audit walks each of the twelve focus items the orchestrator named
and records a severity. No item crossed MEDIUM; one design gap (S4,
onboarding evaluator vs. new content shape) and one discipline pin
(S11, per-test AC annotation) are called out as sharp pins to resolve
during implementation rather than revise-and-re-gate items.

## Findings

### S1. Substrate bypass — all writes funnel through `mutate_entity()`

Both writes go through `mutate_entity()`:

- Signal append: `aggregate_type="trust_signal"`, `aggregate_id=str(signal_id)`,
  `expected_version=0`, `action_type="trust.signal.created"`, with
  `insert_trust_signal()` called inside `mutate_projection`
  (`.pipeline/proposal.md:303-322`; D8 binding at `.pipeline/synthesis.md:233-247`).
- Recompute: `aggregate_type="trust_profile"`, `aggregate_id=str(member_id)`,
  `expected_version=current_profile_version`, `action_type="trust.recompute"`,
  with `upsert_trust_profile_for_recompute()` called inside
  `mutate_projection` (`.pipeline/proposal.md:324-345`).

The recompute helper is explicitly fenced:
"It must not create or advance `aggregate_heads`; that remains exclusively
inside `mutate_entity()`" (`.pipeline/proposal.md:250`). There is no
direct `UPDATE trust_profiles ...` write path, and the repository only
exposes insert/update helpers intended to be called from within the
`mutate_projection` callback. D13 binds the grep invariant
(`.pipeline/synthesis.md:311-328`) and the proposal codifies it as
`test_no_trust_signal_bypass_remains` in §11. LOW.

### S2. Policy versioning — reads current trust_computation policy via SLICE-010 substrate

Recompute reads policy via `fetch_latest_version(connection,
"trust_computation", "global", None)` (`.pipeline/proposal.md:329-331`),
which is the SLICE-010 policy substrate
(`services/api/app/repositories/policies.py:fetch_latest_version`). The
selected row's `id` and `version_number` are pinned onto the profile as
`policy_version_id` and `config_version`
(`.pipeline/proposal.md:342`). D2 binds `trust_computation` content to
`policy_versions.content` and forbids a parallel
`trust_computation_configs` table (`.pipeline/synthesis.md:80-106`). No
hardcoded JSON fallback, no inline default policy constant. LOW.

### S3. Signal shape validation — Pydantic + DB check constraints enforce invariants twice

`TrustSignalScope` has `@model_validator(mode="after") validate_scope`
that rejects global-with-`scope_id` and chapter/member-without-`scope_id`
(`.pipeline/proposal.md:159-175`). `scope_kind: ScopeKind` uses the
existing `Literal["global","chapter","member"]` type, so enum validity
is caught by Pydantic at parse time. `TrustSignalCreate.validate_value`
rejects non-numeric `schema_version` including bool
(`.pipeline/proposal.md:185-191`). `validate_expiry` enforces
`expires_at > observed_at`
(`.pipeline/proposal.md:193-197`). Service layer also calls
`validate_trust_signal_scope()` before insert
(`.pipeline/proposal.md:306`, `:348-352`), and the DB has nine CHECK
constraints covering the same invariants
(`.pipeline/proposal.md:37-68`), including
`scope->>'scope_kind' = scope_kind` and `value ? 'schema_version' AND
jsonb_typeof(value->'schema_version') = 'number'`. Belt-and-suspenders
without a shortcut path. LOW.

### S4. Legacy substrate replacement — in-place, with one design gap

The proposal replaces SLICE-007 trust policy naming in-place rather than
parking behind a shim:

- Migration `wu-030b` renames `policy_type = 'trust'` to
  `'trust_computation'` for rows referenced by `trust_profiles`
  (`.pipeline/proposal.md:100-106`). No alias, no dual read path
  (`.pipeline/synthesis.md:258-262`).
- Onboarding `compute_trust()` is updated in-place to fetch
  `policy_type="trust_computation"` and the D2 content shape
  (`.pipeline/proposal.md:366-370`).
- Dual support for the old `rules` shape is explicitly out of scope
  (`.pipeline/proposal.md:581`, `.pipeline/synthesis.md:103-106`).

Sharp design gap (not a shortcut introduced by the proposal, but a gap
the proposal must not paper over during implementation): the current
`evaluate_trust()` in
`services/api/app/services/trust.py:106-143` reads
`rules.weights.discord_account_age_days`,
`rules.weights.has_avatar`, `rules.weights.has_verified_badge`, and
`rules.flags`. The D2 minimum content shape has no `rules` wrapper and
no `weights.discord_account_age_days` key — it has
`signal_weights: {signal_type: weight}` and `level_thresholds`. The
onboarding `compute_trust()` path feeds `TrustSignalsInput` (platform
metadata, no `signal_type`), so it cannot naturally use the new
`signal_weights` map without either synthesizing signal types or
switching to a default-score-only path.

This creates implementation pressure to either reintroduce a `rules`
compatibility branch or dual-support both shapes — both of which the
proposal forbids (`.pipeline/proposal.md:154`, `:581`;
`.pipeline/synthesis.md:103-106`). The implementer must pick one of
the two clean paths and document it:

- Pin option A: onboarding synthesizes deterministic signal types
  (e.g., `identity.discord_account_age_days`,
  `identity.has_avatar`, `identity.has_verified_badge`,
  `identity.account_flag.<flag>`) and evaluates them against
  `signal_weights` with a `default_score` baseline and
  `level_thresholds`. The onboarding path still does not write
  `trust_signals` rows.
- Pin option B: onboarding consumes only
  `default_score`/`level_thresholds` from the new content and returns
  the default tier until a recompute runs; onboarding signals become
  a no-op for scoring. Operator policy content must be written with
  that expectation.

The proposal should not ship without resolving this, but resolving it
does not require another risk pass — the ambiguity sits inside the
boundaries D2 already binds. LOW (with Pin P1 below). If the
implementer reintroduces a `rules` fallback or parallel content branch,
that is a MEDIUM/HIGH regression to flag at PR-review time, not a
shortcut the proposal authorizes.

### S5. Determinism — wall clock captured once, outside the evaluator

`compute_score(active_signals, policy_content)` is the pure boundary
(`.pipeline/proposal.md:461-464`). Forbidden inputs inside the
evaluator: `datetime.now()`, database timestamps, randomness, actor
identity, unordered row iteration, external service calls
(`.pipeline/proposal.md:470-473`). `as_of = datetime.now(UTC)` is
captured once at the top of `recompute_trust_profile()` before any
reads, used only to select active signals and to persist `computed_at`;
it is explicitly not passed as a score input
(`.pipeline/proposal.md:326`). Decay, if implemented, must derive its
reference point from the included signal set (e.g. max `observed_at`),
not current wall clock (`.pipeline/proposal.md:362`). `computed_at` is
persisted but deliberately excluded from `TrustProfileRead`
(`.pipeline/proposal.md:480`, `.pipeline/synthesis.md:144-146`) so it
never leaks back in as a client-driven score input. D10 binds the
boundary (`.pipeline/synthesis.md:269-286`). LOW.

### S6. Authority — body-scope via AuthorityRequirement; no allow-all

Two permissions, two evaluation styles:

- `trust.signal.create`: scope is body-driven (`body.scope.scope_kind`,
  `body.scope.scope_id`). Endpoint uses the roster-style manual
  evaluation: construct `AuthorityRequirement`, call
  `list_grants_for_grantee()`, evaluate at `current_time()`, and return
  403 `authority_decision_denied` on denial
  (`.pipeline/proposal.md:388-404`; pattern at
  `services/api/app/api/v1/endpoints/roster.py:78-102`).
- `trust.recompute`: profile scope is fixed to global for SLICE-016
  because `trust_profiles` has no scope column (D6 binding,
  `.pipeline/synthesis.md:196-217`). Endpoint uses static
  `RequireAuthority("trust.recompute", "global")`
  (`.pipeline/proposal.md:414`).

D7 forbids seeding a new trust service actor grant
(`.pipeline/synthesis.md:219-231`). There is no "allow-all" branch, no
actor-kind whitelist shortcut. `actor.actor_kind == "system"` is
explicitly rejected at the signal create service layer because
`trust_signals.source_actor_kind` is constrained to `user|service` at
the DB (`.pipeline/proposal.md:307-308`, `:47-49`). LOW.

### S7. Concurrency — OCC on `trust_profile` aggregate, `FOR UPDATE` row lock, bounded retry

Recompute:

1. Reads current trust profile and aggregate version via
   `get_trust_profile_for_update()` with `SELECT ... FOR UPDATE OF t, h`
   (`.pipeline/proposal.md:281-287`, `:327-329`).
2. Calls `mutate_entity(expected_version=current_version)` — or
   `expected_version=0` when no profile row exists yet, which matches
   the substrate's "create aggregate head on first mutate" path
   (`.pipeline/proposal.md:289`, `:333-335`).
3. On `StaleMutationError`, re-reads member/policy/signals/profile and
   retries once; second stale raises `TrustRecomputeConflictError` →
   HTTP 409 (`.pipeline/proposal.md:344`, `:519-534`; D12 binding at
   `.pipeline/synthesis.md:297-309`).

Signal creation uses `expected_version=0` with a new UUID aggregate
id; UUID collisions are not user-visible OCC failures
(`.pipeline/proposal.md:536`). No "skip lock" path, no silent stale
swallow. LOW.

Observation, not a block: the `FOR UPDATE OF t, h` row lock and the
`aggregate_heads` OCC check are both active. The row lock is
transaction-scoped and falls away at commit; the aggregate version is
the real arbiter across connections. Not duplicative in a harmful way —
the row lock narrows the stale window inside a single transaction
attempt — but worth noting so no one misreads the row lock as a
cross-transaction guarantee.

### S8. Policy caching — no request-level cache

The proposal introduces no per-request or per-process policy cache.
Recompute reads policy with `fetch_latest_version()` inside each
transaction attempt, including the retry pass
(`.pipeline/proposal.md:329-331`, `:519-526`). There is no memoized
`get_trust_policy()` helper, no `@lru_cache` decorator, no module-level
policy dictionary. Because the proposal does not introduce caching, it
cannot introduce a stale-across-recomputes invalidation bug. LOW.

### S9. Tests exercise actual computation

Test list in `.pipeline/proposal.md:546-568`:

- `test_recompute_deterministic_for_same_inputs` (AC3): runs two real
  recomputes, asserts identical `score`, `tier`, `signals`,
  `policy_version_id`, `config_version`.
- `test_recompute_pins_current_policy_version` (AC2): seeds two real
  `trust_computation` policy versions and recomputes.
- `test_recompute_honors_expired_signals_by_ignoring_them`: real expired
  signal vs. real unexpired equivalent.
- `test_recompute_produces_new_profile_version`: real version bump.
- `test_recompute_audit_records_correct_diff`: inspects
  `activity_actions` and `activity_state_changes` rows.
- `test_create_signal_persists_fields_without_mutating_profile` (AC1):
  actual insert + non-mutation assertion.
- `test_recompute_returns_409_on_stale_conflict_after_retry`: the only
  mock-heavy test (repository or mutation hook monkeypatch to force
  stale) — legitimate, because contention is hard to reproduce without
  synchronization.

Pure-function coverage is not called out by a dedicated unit test in
the list, but `test_recompute_deterministic_for_same_inputs` and
`test_recompute_honors_expired_signals_by_ignoring_them` exercise the
evaluator through the service, which is sufficient for AC3. LOW.

Observation: a direct unit test on `compute_score(signals,
policy_content)` across input orderings (research §AC3,
`.pipeline/research.md:474-477`) is cheap and would harden the D10
determinism boundary. Not a blocker; worth adding during
implementation.

### S10. Signal append-only — no mutate repository helpers exposed

`.pipeline/proposal.md:255-277` lists only two repository additions for
signals:

- `insert_trust_signal(connection, *, row)` — single INSERT, no UPDATE.
- `list_active_signals_for_member(connection, *, member_id, as_of)` —
  read-only SELECT.

No `update_trust_signal(...)`, no `delete_trust_signal(...)`, no
`revoke_trust_signal(...)`. D11 binds revocation out of scope
(`.pipeline/synthesis.md:288-295`). The migration's trust_signals
schema omits `revoked_at` entirely, unlike the research draft which
had considered it (`.pipeline/research.md:260-261`). The grep invariant
in `test_no_trust_signal_bypass_remains` fails if any module outside
`services/api/app/services/trust.py` and
`services/api/app/repositories/trust.py` contains
`INSERT INTO trust_signals`, `UPDATE trust_profiles`, or `INSERT INTO
trust_profiles` (`.pipeline/proposal.md:563-566`). The test does not
grep for `UPDATE trust_signals` or `DELETE FROM trust_signals` because
the proposal commits to never writing those statements anywhere in the
slice. LOW.

Sharp pin (P2 below): extend the grep invariant to also fail on
`UPDATE trust_signals` and `DELETE FROM trust_signals` outside
migrations/tests. One line; closes a quiet bypass window before it
opens.

### S11. Tests without AC trace — partial annotation

Explicit AC cites on individual test bullets:

- `test_create_signal_persists_fields_without_mutating_profile` (AC1) ✓
- `test_recompute_pins_current_policy_version` (AC2) ✓
- `test_recompute_deterministic_for_same_inputs` (AC3) ✓
- `test_no_trust_signal_bypass_remains` (D13)

Tests without an explicit AC cite on the bullet:

- `test_create_signal_requires_authority_at_scope`
- `test_create_signal_rejects_invalid_scope_shape`
- `test_create_signal_with_expires_at_persists_correctly`
- `test_recompute_produces_new_profile_version`
- `test_recompute_returns_409_on_stale_conflict_after_retry`
- `test_recompute_honors_expired_signals_by_ignoring_them`
- `test_recompute_audit_records_correct_diff`

Each of the unannotated tests maps cleanly to the AC → Implementation
matrix in §12 (`.pipeline/proposal.md:573-579`), which does trace tests
to acceptance criteria. So the traceability exists as a matrix, even
if per-bullet annotation is partial. LOW.

Sharp pin (P3 below): during test-writing, each test's docstring
should cite the AC or D-binding it defends. The matrix is a design
artifact; the docstring is where a future reader finds the contract
claim being asserted. No revision needed at proposal time.

### S12. Magic values — named constants pulled out at the service boundary

Proposal §5 declares module-level constants
(`.pipeline/proposal.md:296-301`):

- `TRUST_POLICY_TYPE = "trust_computation"`
- `TRUST_PROFILE_AGGREGATE_TYPE = "trust_profile"`
- `TRUST_SIGNAL_AGGREGATE_TYPE = "trust_signal"`

Scope vocabulary uses the existing
`ScopeKind = Literal["global","chapter","member"]` type
(`services/api/app/contracts/scope.py`) — the enum itself is the named
constant set. Tier thresholds live in `policy_versions.content`, not
in code, which is the correct home per P11 (operator-managed config)
and D2 (policy substrate is the config store). Score floor/ceiling and
default score likewise live in policy content
(`.pipeline/synthesis.md:85-102`). LOW.

Pin (P4): action_type and change_type strings `"trust.signal.created"`,
`"trust.recompute"`, `"trust.recomputed"` appear as literals at several
call sites (proposal §5, §9). Pull them into module-level constants
next to the aggregate-type constants so the audit/grep surface has a
single source of truth. One-liners, no revision needed.

### S13. No backwards-compat shims, no deferred stubs

Checked against AGENTS.md §"No Backwards Compatibility" and §"No
Deferred Stubs":

- No alias keeping `policy_type = 'trust'` alive for trust_computation
  reads. `wu-030b` data-renames referenced rows
  (`.pipeline/proposal.md:99-106`) and D9 forbids dual-name support
  (`.pipeline/synthesis.md:258-262`).
- No dual content shape support; D2 binds the new shape and §12 lists
  old-shape support as explicitly out of scope
  (`.pipeline/proposal.md:581`).
- No `revoked_at` column sneaking into the `trust_signals` table as a
  future-compat placeholder (D11, `.pipeline/synthesis.md:288-295`).
- No `signal_revision_at` placeholder on `trust_profiles` (D4,
  `.pipeline/synthesis.md:139-143`; reiterated at proposal §8,
  `:482-484`).
- Endpoint package conversion replaces the single-module `trust.py`
  in place (§6, `.pipeline/proposal.md:374-442`), no shim
  `trust_legacy.py` left behind.
- `_insert_trust_profile()` is replaced by explicit profile helpers
  (`.pipeline/proposal.md:240-251`), not left in place alongside a new
  helper.
- The `TrustRecomputeRequest` class appears only for generated contract
  completeness and is explicitly "not accepted by the endpoint"
  (`.pipeline/proposal.md:222-225`). This is a soft footgun — an unused
  Pydantic model is one PR away from being wired in. Observation, not
  a blocker.

LOW.

## Summary

| # | Area | Severity | Note |
|---|---|---|---|
| S1 | Substrate bypass — both writes via `mutate_entity()` | LOW | Grep invariant test enforces it |
| S2 | Policy read via SLICE-010 `fetch_latest_version()` | LOW | No hardcoded JSON |
| S3 | Pydantic scope + value validators + DB CHECK constraints | LOW | Belt-and-suspenders |
| S4 | SLICE-007 onboarding evaluator vs. new content shape | LOW | Pin P1 — resolve in-place, no dual shape |
| S5 | Determinism — `as_of` captured once outside evaluator | LOW | `computed_at` not in `TrustProfileRead` |
| S6 | Authority — body-scope `AuthorityRequirement`; static for recompute | LOW | No allow-all, no system-actor bypass |
| S7 | OCC on `trust_profile` + `FOR UPDATE` + one retry → 409 | LOW | Row lock is intra-tx; aggregate version is the arbiter |
| S8 | No policy cache introduced | LOW | Cannot have a stale-cache bug it doesn't have |
| S9 | Tests exercise real recompute; only stale-conflict mocks | LOW | Consider adding direct unit test on `compute_score` |
| S10 | Signal repo exposes only INSERT + SELECT | LOW | Pin P2 — extend grep to `UPDATE/DELETE trust_signals` |
| S11 | AC trace present as matrix; per-test-bullet partial | LOW | Pin P3 — cite AC in test docstrings |
| S12 | Policy type / aggregate types named constants | LOW | Pin P4 — promote action/change_type strings too |
| S13 | No compat shims, no deferred stubs | LOW | `TrustRecomputeRequest` unused; observation only |

No MEDIUM / HIGH shortcut findings.

## Implementation pins (one-liners, not blockers)

- **P1 (S4)**: onboarding `compute_trust()` must consume only the D2
  content shape. Pick option A (synthesize deterministic onboarding
  signal types and use `signal_weights`) or option B (default score +
  `level_thresholds` only) and delete the old `rules`-shape evaluator
  path in the same PR. Do not restore a `rules` fallback.
- **P2 (S10)**: extend `test_no_trust_signal_bypass_remains` to grep
  for `UPDATE trust_signals` and `DELETE FROM trust_signals` in
  addition to the three patterns already listed.
- **P3 (S11)**: each test in `test_trust_signals.py` and
  `test_trust_recompute.py` annotates the AC or D-binding it defends in
  its docstring, so the grep surface for "which test pins AC*N*" stays
  one command away.
- **P4 (S12)**: promote `"trust.signal.created"`, `"trust.recompute"`,
  and `"trust.recomputed"` to module-level constants alongside
  `TRUST_POLICY_TYPE` / `TRUST_PROFILE_AGGREGATE_TYPE` /
  `TRUST_SIGNAL_AGGREGATE_TYPE`.
- **S7 observation**: the `FOR UPDATE OF t, h` row lock is
  transaction-scoped; reviewers should not treat it as a
  cross-connection guarantee. The aggregate version in
  `aggregate_heads` is the real OCC arbiter.
- **S9 observation**: add a direct unit test on `compute_score()` with
  input rows shuffled across permutations to harden the D10
  determinism boundary.
- **S13 observation**: `TrustRecomputeRequest` is defined but
  explicitly unused. If generated contract completeness does not
  require it, drop it to remove the unused-model footgun.

## Rating

**LOW.** The proposal clears the shortcut-risk bar. The single design
gap worth a sharp pin (S4/P1) is an in-place decision inside the
boundaries already bound by D2/D9, not a shim the proposal authorizes.
The remaining pins (P2-P4, observations) are one-liners the
implementation and test agents can apply without a revise-and-re-gate
cycle.
