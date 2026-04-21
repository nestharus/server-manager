# SLICE-016 Audit Risk Assessment

**Rating: LOW** — all 9 audit-correctness focus items are satisfied by
the current proposal. Append-only evidence, pure deterministic evaluator,
atomic policy-version pinning, explicit `payload_allowlist`s on both
mutation sites, `diff_json` carrying derived-state old→new, no Discord
bypass, and authority resolved at the expected scopes for each endpoint.

Scope: `.pipeline/proposal.md` (current revision) against
`.pipeline/synthesis.md` D1–D13 (revision 1: D7 now member-scoped for
recompute), `.pipeline/research.md`, `product-strategy/tickets/SLICE-016.md`,
and merged SLICE-007/009/010/015 substrate (`mutate_entity`,
`StateChangeDraft`, policy versioning, aggregate OCC).

Severity scale: LOW = all 9 satisfied; MEDIUM = 1–3 gaps; HIGH = audit
bypass, determinism broken, or policy version not pinned. No HIGH
condition is present, and no gaps remain.

## Focus Item Verdicts

### 1. `payload_allowlist` explicit on every `mutate_entity` call — SATISFIED

Both mutation sites declare an explicit allowlist literal:

- **Signal create** (proposal.md §5, step 6; §9, line 318):
  `payload_allowlist={"signal_type", "scope", "value", "observed_at", "expires_at"}`.
- **Recompute** (proposal.md §5, step 8; §9, line 338):
  `payload_allowlist={"member_id"}`.

Both calls go through `mutate_entity()`:

- Signal create is an aggregate-create call
  (`aggregate_type="trust_signal"`, `expected_version=0`, new UUID
  `aggregate_id`), which exercises head creation and the standard
  action/state-change audit path.
- Recompute is an aggregate-mutate call
  (`aggregate_type="trust_profile"`, `expected_version=current_version`).

No field-omitted / implicit allowlist. Signal-create exercises the
"signal create (if aggregate) and recompute" both-paths expectation by
using `mutate_entity()` uniformly (proposal §5 comment: "creation still
uses `mutate_entity()` as D8 binds so audit/action/state-change
invariants are uniform").

*Observation (non-blocking, forward drift):* the signal-create allowlist
omits `member_id`. The `StateChangeDraft.payload_json` still records
`member_id` and `aggregate_id=signal_id` preserves per-signal linkage via
the foreign key, but the raw `activity_actions.payload` row won't name
the member. Consider adding `"member_id"` to the allowlist for action-log
clarity.

### 2. `trust.recomputed` `StateChangeDraft` carries `score` / `tier` / `config_version` old→new diff — SATISFIED

proposal.md §9 enumerates the `diff_json` contract explicitly:

> `diff_json` must carry old/new values for at least:
> - `score`
> - `tier`
> - `policy_version_id`
> - `config_version`
> - canonical included signal ID list

§5 step 10 returns
`StateChangeDraft(change_type="trust.recomputed", payload_json={...}, diff_json={...})`.
§11 `test_recompute_audit_records_correct_diff` asserts presence, and the
AC4 trace in §12 links the test. This matches synthesis D8's binding.

### 3. `trust.recompute` action payload contains ONLY `{member_id}` — SATISFIED

proposal.md §5 step 8 sets `payload_allowlist={"member_id"}` and §9
reaffirms it. §9 is explicit about the derived-state separation:

> The recompute action payload must not include raw signal values; those
> are already stored and audited on signal creation. The recompute
> payload records that the member's derived profile was recomputed,
> while `diff_json` records what derived state changed.

No `score`, `tier`, `policy_version_id`, or `config_version` routes into
`activity_actions.payload`. Those live exclusively in
`activity_state_changes.diff_json`, which is the correct surface because
derived values are server-computed, not operator-supplied request fields.
No PII / derived-state leak into the action payload.

### 4. Signal append-only; no UPDATE/DELETE surface; expiry at read filter — SATISFIED

- Repositories (proposal.md §4) expose only `insert_trust_signal()` and
  `list_active_signals_for_member()`. No update, delete, or revoke
  helper is defined.
- D11 (synthesis.md) binds: no revocation endpoint, no
  `trust_signal.revoke` action, no `revoked_at` column.
- Expiry is applied in SQL at read time:
  `WHERE expires_at IS NULL OR expires_at > :as_of` (§4, §8). Synthesis
  D1 rejects a partial "active" index on `CURRENT_TIMESTAMP` because
  PostgreSQL partial indexes cannot depend on moving time.
- `mutate_entity()` for signal create uses `expected_version=0` on a
  fresh UUID aggregate — effectively insert-only.

*Observation (test-coverage, forward drift):* the bypass grep invariant
in §11 (`test_no_trust_signal_bypass_remains`) scans for
`INSERT INTO trust_signals`, `UPDATE trust_profiles`, and
`INSERT INTO trust_profiles` outside the two approved modules. It does
not scan for `UPDATE trust_signals` or `DELETE FROM trust_signals`. No
such statements exist in this slice, so the risk is purely forward-drift.
Recommend extending the regex when implementing — this is an
implementation-detail improvement, not a proposal correction.

### 5. Activity actions per mutation: 1 per signal create, 1 per recompute — SATISFIED (with retry caveat)

- Signal create: one `mutate_entity()` call per request → one accepted
  action row on success. No internal retries.
- Recompute: one `mutate_entity()` call per attempt; at most one success
  per request. Happy path = 1 action row.

*Retry caveat (D12 / §10):* on `StaleMutationError`, the service
re-reads and retries exactly once. Because `mutate_entity()` records
rejected / failed actions as part of its contract, a stale-then-success
path produces **1 rejected + 1 accepted = 2 rows**. This is the intended
substrate behavior (fail/reject audit is a feature), consistent with
existing ticket/roster retries. It is not an audit-correctness gap; read
"1 action per recompute" as "1 accepted action per successful recompute".

### 6. Policy version pinning atomic on recompute — SATISFIED (AC2)

proposal.md §5 establishes shared-connection atomicity:

- Step 2: open a transaction per attempt.
- Step 5: read policy via
  `fetch_latest_version(connection, "trust_computation", "global", None)`
  on the same connection.
- Steps 8–9: `mutate_entity(..., connection=connection)` with the
  projection writing `policy_version_id=policy["id"]` and
  `config_version=policy["version_number"]` inside the same transaction.

The profile therefore pins the exact row that was read; no race window
between "which policy was read" and "which policy was recorded".
`policy_version_id` remains the durable reference;
`config_version` is the denormalized int for operator display (D4).
D9's migration renames existing `policy_type="trust"` rows to
`"trust_computation"` with no alias, so the read lookup is unambiguous
post-deploy. `test_recompute_pins_current_policy_version` (§11) asserts
both fields on the latest policy after a multi-version seed.

### 7. Determinism: pure function, no hidden inputs — SATISFIED (AC3)

proposal.md §8 defines the evaluator boundary:

```
compute_score(active_signals, policy_content) -> (score, tier, canonical_signals_summary)
```

Forbidden inputs are enumerated: `datetime.now()`, database timestamps,
randomness, actor identity, unordered row iteration, external service
calls. Decay, if used, derives its reference point from the signal set
(e.g., max `observed_at`), not wall clock (§5 `compute_score` spec).

Ordering is canonical: `(observed_at ASC, created_at ASC, id ASC)`.
Duplicate collapse uses a deterministic key
`(member_id, signal_type, scope_kind, scope_id, observed_at,
source_actor_kind, source_actor_id, canonical_value)`. Clamp +
threshold-resolution are deterministic arithmetic.

`as_of` (expiry boundary) is captured once per recompute attempt,
outside the evaluator. Two sequential recomputes with unchanged active
signals and policy produce identical
`(score, tier, signals, policy_version_id, config_version)`.
`test_recompute_deterministic_for_same_inputs` (§11) asserts this.

The proposal's acknowledgement that two recomputes at *different* times
can differ when an expiry boundary crosses is consistent with AC3 —
AC3 is conditioned on "same signal set and policy version", and expiry
crossing changes the signal set.

### 8. No Discord bypass / alternate write path — SATISFIED (AC4)

- D13 (synthesis.md) binds: no Discord interaction, no Discord-side
  direct DB writes; no daemon / task / repository helper / adapter may
  write `trust_signals` or `trust_profiles` outside the two approved
  service functions.
- Ticket (SLICE-016 §30–31) confirms no Discord interactions in this
  slice.
- Endpoints (§6) route all writes through `create_trust_signal()` /
  `recompute_trust_profile()`, both of which funnel through
  `mutate_entity()`.
- §11 `test_no_trust_signal_bypass_remains` enforces the rule in CI.
- SLICE-007's `/api/v1/trust/compute/{member_id}` onboarding path is
  preserved but explicitly prohibited from reading or writing
  `trust_signals` (proposal §5, §6; synthesis D13).

*Non-blocking (already covered under item 4):* the bypass grep invariant
should also refuse `UPDATE trust_signals`, `DELETE FROM trust_signals`,
and `DELETE FROM trust_profiles` to lock append-only / recompute-only
surface against forward drift.

### 9. Authority resolution — SATISFIED

- **Signal create (body-scope driven).** proposal.md §6 `signals.py`
  and §7 use the roster manual-authority pattern:
  `AuthorityRequirement(permission="trust.signal.create",
  scope_kind=body.scope.scope_kind, scope_id=body.scope.scope_id)`,
  evaluated via `list_grants_for_grantee()` at `current_time()`, with
  `403 authority_decision_denied` on denial. Matches D5 / D7.

- **Recompute (path-param driven).** proposal.md §6 `recompute.py` and
  §7 use the roster manual-authority pattern after resolving
  `member_id` from the path:
  `AuthorityRequirement(permission="trust.recompute",
  scope_kind="member", scope_id=str(member_id))`. This matches synthesis
  D7 (revision 1 note) which binds recompute authority to member scope.
  `test_recompute_requires_trust_recompute_at_member_scope` (§11)
  asserts that a user holding `trust.recompute` only at global scope is
  denied, and a user holding it at
  `scope_kind="member", scope_id=str(member_id)` is allowed.

Note on a related-but-distinct concern: the `mutate_entity()` call for
recompute sets `scope_kind="global"`, `scope_id=None` on the audit
action (proposal §5 step 8, §9). That is the *aggregate/mutation* scope
recorded on `activity_actions` — trust_profiles has no scope column, and
D6 keeps the profile global until a later slice adds scoped profiles.
The *authority check* scope and the *audit action* scope are separately
chosen here and both are correct for their respective roles.

## Gap Summary

| ID | Item | Severity | Resolution |
|---|---|---|---|
| — | No gaps identified | — | — |

The prior revision of this audit flagged G1 (recompute authority at
global scope) as MEDIUM. That gap is closed: synthesis D7 (revision 1)
and proposal §6/§7 now bind recompute authority to
`scope_kind="member", scope_id=str(member_id)`.

## Non-Blocking Observations (Forward Drift)

- **O1:** Signal-create `payload_allowlist` omits `member_id`. The
  state-change payload and aggregate binding preserve linkage, but the
  raw action payload won't name the member. Adding `"member_id"` to the
  allowlist would improve action-log readability at no cost.
- **O2:** The bypass grep invariant in §11 should also refuse
  `UPDATE trust_signals`, `DELETE FROM trust_signals`, and
  `DELETE FROM trust_profiles` to lock append-only / recompute-only
  surface against forward drift. No such statements exist in the slice
  today.
- **O3:** "1 action row per recompute" holds for the happy path; OCC
  retry produces 1 rejected + 1 accepted. Implementation-side audit
  assertions should query "latest accepted action" rather than "exactly
  one row".

## AC Trace Under Audit

| AC | Verdict | Evidence |
|---|---|---|
| AC1: Signal create persists evidence without mutating profile | SATISFIED | §4 (no profile helpers on signal path), §5 step 7 (projection inserts signal only), §11 `test_create_signal_persists_fields_without_mutating_profile` |
| AC2: Recompute pins current policy/config version | SATISFIED | §5 steps 5–9 (same-connection read + pin), §11 `test_recompute_pins_current_policy_version` |
| AC3: Recompute deterministic | SATISFIED | §8 evaluator purity contract, §5 `compute_score`, §11 `test_recompute_deterministic_for_same_inputs` |
| AC4: Audit-safe, no Discord-local overrides | SATISFIED | D13, §6 endpoint wiring, §9 audit names + allowlists, §11 bypass grep invariant |

## Conclusion

Of 9 audit focus items: **9 satisfied, 0 gaps**. No HIGH condition (no
audit bypass, determinism intact, policy pinning atomic); no MEDIUM
condition (no `payload_allowlist` omissions, no authority scope
mismatch, no derived-state leak into action payloads, no alternate
write paths). Rating is **LOW**. The three non-blocking observations
(O1–O3) are forward-drift hardening suggestions for the implementation
phase and do not require proposal changes.
