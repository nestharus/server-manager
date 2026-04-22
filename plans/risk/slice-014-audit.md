# SLICE-014 Audit Risk Assessment (Revision 2)

**Severity: LOW**

Revision 1 of the SLICE-014 proposal (see `.pipeline/proposal.md:2450-2546`
"Revision log") addresses every MEDIUM finding raised in the prior audit gate
(R6 / R7 concretize drift-create + run-advance payloads; R1 / R3 move all
`action_type` and `change_type` values into dispatch dicts; R8 adds `diff_json`
to the new projections and a spoof-proof validator on
`PermissionDriftResolutionRequest`; R4 re-specifies the drift-batch return
shape; R9 documents the denial-audit non-goal). I re-ran all ten Focus items
against the revised spec and the shipped `mutate_entity()` substrate
(`services/api/app/services/mutations.py:58-225`); every item is satisfied by
construction or by the shipped precedent the proposal binds to. What remains
are three LOW / informational observations about inline literals on single-use
create paths, pre-existing shipped behavior on intent update, and an implicit
convention that the in-loop helpers share the outer transaction — none of
which block the risk gate.

---

## Focus Walk-Through

| # | Focus | Verdict | Primary evidence |
|---|-------|---------|------------------|
| 1 | Every aggregate mutation through `mutate_entity()` with explicit `payload_allowlist`. | PASS | §5.1 (intent create/update — `INTENT_{CREATE,UPDATE}_PAYLOAD_ALLOWLIST`), §5.2 (`resolve_permission_drift` — `DRIFT_RESOLUTION_PAYLOAD_ALLOWLIST[request.action]`), §5.3 (`create_reconciliation_run` — `RUN_CREATE_PAYLOAD_ALLOWLIST`; `_advance_run_*` — `RUN_ADVANCE_PAYLOAD_ALLOWLIST[key]`; `_record_drift_created` — `DRIFT_CREATE_PAYLOAD_ALLOWLIST`). `.pipeline/proposal.md:1312-1327, 1479-1502, 1606-1653, 1678-1710, 2256-2350`. |
| 2 | `action_type` constants, no magic strings. | PASS (with one acknowledged single-use literal) | §10.1 `DRIFT_RESOLUTION_ACTION_TYPE` / `DRIFT_RESOLUTION_CHANGE_TYPE`; §10.2 `RUN_ACTION_TYPE` / `RUN_CHANGE_TYPE`. `_record_drift_created` uses the inline literal `"permission_drift.create"` / `"permission_drift.created"`, acknowledged as-such in §10.3 — this matches the shipped `create_permission_intent` / `create_permission_drift` single-action precedents at `services/api/app/services/permissions.py:140, 227-239`. `.pipeline/proposal.md:1681-1687, 2291-2338, 2354-2362`. |
| 3 | `state_change_draft` records BEFORE + AFTER or `change_type`. | PASS | Drift resolve projection adds `diff_json={"from": from_state, "to": next_status}` (R8b). Each `_advance_run_*` projection adds `diff_json` with the BEFORE→AFTER pair (R7). Create projections (`permission_intent.created`, `permission_reconciliation_run.created`, `permission_drift.created`) carry full AFTER state in `payload_json`; BEFORE is void by definition. `.pipeline/proposal.md:1306-1310, 1619-1652`. |
| 4 | Spoof-proof originating-actor on drift resolve (SLICE-021 precedent). | PASS | `_drift_originating_actor` at §5.2 (`.pipeline/proposal.md:1217-1226`) mirrors `services/api/app/services/applications.py:189-195`: honours `request.resolved_by_*` only when `actor.actor_kind == "service"`; user actors collapse to the authenticated identity. R8a also pins the both-or-neither validator on `PermissionDriftResolutionRequest` (`.pipeline/proposal.md:719-731`). |
| 5 | Run state transitions (`requested → snapshot_submitted → reconciled \| failed`) each write a change row tied to the run aggregate. | PASS | `create_reconciliation_run` (`.pipeline/proposal.md:1479-1502`) → `change_type="permission_reconciliation_run.created"`. `_advance_run_submit` / `_advance_run_reconciled` / `_advance_run_failed` each wrap `mutate_entity` on `("permission_reconciliation_run", str(run_id))` with a `payload_json` that includes `status`, the transition timestamp, and the transition's distinctive field (`entry_count` / `drift_count` + `drift_ids` / `failure_reason`). `.pipeline/proposal.md:1606-1653`. |
| 6 | Each drift row has its own `activity_actions` + `activity_state_changes` pair; batch inserts do not skip audit. | PASS | `_record_drift_created` is invoked in a `for drift_id in new_drift_ids:` loop inside the reconciliation transaction (§5.3 `.pipeline/proposal.md:1576-1582`). R4 guarantees `new_drift_ids` contains only newly-inserted ids (from `insert_permission_drift_batch` returning only `RETURNING id` hits), so `expected_version=0` never fires on an existing aggregate head. `DRIFT_CREATE_PAYLOAD_ALLOWLIST` pins the ten fields that are written on both `action_payload` and `payload_json`. `.pipeline/proposal.md:942-981, 1567-1582, 1678-1710, 2346-2350`. |
| 7 | Discord-originating user id captured in the run's audit payload. | PASS | `PermissionReconciliationRunCreate` exposes `originating_actor_kind` / `originating_actor_id` (§3.4 `.pipeline/proposal.md:737-741`); `_requested_by` writes them through to `requested_by_kind` / `requested_by_id` only when authenticated actor is `service` (`.pipeline/proposal.md:1429-1433`); `create_reconciliation_run`'s `action_payload` includes both fields and they are members of `RUN_CREATE_PAYLOAD_ALLOWLIST` (`.pipeline/proposal.md:1491-1498, 2313-2316`). The Discord adapter passes `envelope.actor_kind` / `envelope.actor_id` into `permission_client.create_reconciliation_run` (§7.3 `.pipeline/proposal.md:2034-2040`). |
| 8 | Causation threading via `get_current_audit_context()`. | PASS | `mutate_entity` reads correlation / causation from the ambient `ContextVar` when the `MutationRequest` does not set them (`services/api/app/services/mutations.py:74-92`). The proposal's `MutationRequest` constructors do not set `correlation_id` / `causation_id`, so every mutation inside one HTTP request — the run-advance trio AND the per-drift `_record_drift_created` loop — shares the ambient correlation_id. This matches the shipped applications precedent, which also inherits causation from context rather than threading action-level causation by hand. |
| 9 | Terminal replay idempotency does NOT duplicate audit rows on retry. | PASS | Terminal replay is handled *before* entering the transaction or calling `mutate_entity` (§5.3 `.pipeline/proposal.md:1543-1559`): `if existing.status in RUN_TERMINAL_STATUSES:` returns the cached `MutationResult` for `reconciled` and raises `ReconciliationRunConflictError` for `failed`. No new action or state-change row is written on replay. AC4. |
| 10 | Authority-denial audit row (SLICE-008 precedent). | PASS (documented non-goal) | R9 / §11 "Denial-audit rows" (`.pipeline/proposal.md:2406-2420`) confirms the shipped `RequireAuthority` precedent logs *overrides* (`services/api/app/services/audit_overrides.py:13-56`) but **not** plain denials — denials yield 403 with no audit row. SLICE-014 inherits this behavior at both the endpoint `_require_scoped` gate and the new service-layer `_require_scoped_authority` gate (R5). The prior "SLICE-008 precedent" framing in the Focus prompt was ambiguous; the revised non-goal bullet disambiguates. A future slice can add a symmetric `record_authority_denial` helper if needed; out of scope here. |

---

## Findings

### Finding 1 — LOW — `_record_drift_created` uses inline literals for `action_type` / `change_type`

- **File reference.** `.pipeline/proposal.md:1682, 1687` (§5.3 helper),
  `.pipeline/proposal.md:2354-2362` (§10.3 name inventory),
  `services/api/app/services/permissions.py:140, 227-239` (shipped precedent
  for inline create-action literals).
- **Evidence.** `_record_drift_created` declares
  `action_type="permission_drift.create"` and
  `change_type="permission_drift.created"` as inline string literals
  rather than reading from a dispatch dict. §10.3 acknowledges this
  explicitly: *"the `permission_drift.created` literal in
  `_record_drift_created`."* Every other new call site routes through a
  dispatch dict (`DRIFT_RESOLUTION_*`, `RUN_ACTION_TYPE`,
  `RUN_CHANGE_TYPE`).
- **Severity.** LOW. The synthesis "Proposal Constraints" bullet 14
  (`.pipeline/synthesis.md:914-916`) reads "No magic action_type /
  change_type strings anywhere in the new service — constants only".
  Inline literals on a single-action create path are a grey area; the
  shipped `create_permission_intent` and the shipped
  `create_permission_drift` both use the same inline pattern, so SLICE-014
  is not introducing a new shortcut. The class of bug the dispatch dicts
  were introduced to forbid — f-string generation of `.acceptd` (shortcut
  F1, R1) — cannot occur at a single-action site because there is no
  variable substitution. Informational only.
- **Recommendation.** None required. For maximum symmetry, the proposer
  could promote the two strings to module-level constants
  (`DRIFT_CREATE_ACTION_TYPE: str = "permission_drift.create"`,
  `DRIFT_CREATE_CHANGE_TYPE: str = "permission_drift.created"`) alongside
  `DRIFT_CREATE_PAYLOAD_ALLOWLIST` in §10.2 so the drift-create call site
  reads purely from the constants section, but this is stylistic and not
  a gate blocker.

### Finding 2 — LOW / INFORMATIONAL — `update_permission_intent` projection lacks `diff_json`

- **File reference.** `.pipeline/proposal.md:1161-1167` (§5.1 update
  description — "uses the actor-scoped `_make_request` and the
  `INTENT_UPDATE_PAYLOAD_ALLOWLIST`"),
  `services/api/app/services/permissions.py:174-202` (shipped update
  projection),
  `services/api/app/services/applications.py:715-721` (applications
  precedent using `diff_json`).
- **Evidence.** R8(b) added `diff_json` to the drift-resolve projection
  (§5.2) and the three run-advance projections (§5.3) for parity with
  the applications precedent. R8 does **not** add `diff_json` to the
  pre-existing `update_permission_intent` projection — the shipped code
  writes only `payload_json=updated.model_dump(mode="json")` with no
  BEFORE state captured.
- **Severity.** LOW / informational. Focus 3 is satisfied because
  `change_type="permission_intent.updated"` encodes the transition kind
  ("BEFORE + AFTER state **or** change_type"). The applications
  precedent is a usability improvement, not a contract requirement, and
  the proposer has legitimately scoped R8 to *new* projections rather
  than touching shipped code. No regression vs. WU-006a.
- **Recommendation.** None required. A follow-up slice that tightens
  audit diff coverage across the permissions service could add
  `diff_json={"from": current.model_dump(mode="json"),
  "to": updated.model_dump(mode="json")}` symmetrically. Not blocking.

### Finding 3 — LOW / INFORMATIONAL — Single-transaction convention is documented only at the section close, not per helper

- **File reference.** `.pipeline/proposal.md:1561-1594` (§5.3
  `submit_reconciliation_snapshot` body),
  `.pipeline/proposal.md:1720-1724` (§5.3 closing paragraph).
- **Evidence.** The three helpers called inside the outer
  `with db.transaction() as connection:` block — `_advance_run_submit`,
  `_advance_run_reconciled`, `_record_drift_created` — each take
  `connection` as the first positional argument. Their individual
  descriptions say *"calls `mutate_entity` against aggregate …"* without
  explicitly restating that `connection=connection` must be forwarded to
  `mutate_entity`. The closing paragraph documents the convention:
  *"passing the explicit `connection` keeps all mutations inside one
  transaction"*. `_advance_run_failed` is the explicit exception —
  documented as *"runs in its own transaction (not the caller's) per D8
  step 10"* — and takes `db` rather than `connection`.
- **Why this matters for audit.** If `_record_drift_created` or the
  run-advance helpers were to open their own transactions by omitting
  `connection=connection`, the per-drift `activity_actions` /
  `activity_state_changes` rows would commit independently of the drift
  row itself. On an outer rollback (the D8 step-10 failure path), the
  drift row would disappear but the audit records would persist, leaving
  phantom audit entries for non-existent drift aggregates. This would
  also violate D8 atomicity.
- **Severity.** LOW / informational. The proposer's intent is clear
  ("passing the explicit `connection` keeps all mutations inside one
  transaction"), and this is a spec-completeness tightening rather than
  an architectural defect. The test for atomicity is already listed as
  `test_submit_snapshot_failure_advances_run_to_failed` in §8.3 WU-028B-api
  (`.pipeline/proposal.md:2193`), which implicitly exercises the shared
  transaction.
- **Recommendation.** Add an explicit `connection=connection` mention
  inside each of the three helper bullets (§5.3
  `.pipeline/proposal.md:1606-1653`) so the convention is stated at
  each call site instead of only in the closing paragraph. A one-line
  change per bullet, e.g., *"calls `mutate_entity(connection=connection,
  …)` with:"*. Optional but reduces the chance of the code agent
  accidentally omitting the keyword.

---

## Summary

Every Focus obligation is met by the revised proposal:

- **Focus 1–2** — all eight new mutation paths (intent create/update,
  drift resolve, drift create, run create + three advances) route through
  `mutate_entity()` with an explicitly declared `payload_allowlist` and
  an `action_type` read from a module-level constant (six via dispatch
  dict, one single-use inline literal matching shipped precedent, zero
  f-strings).
- **Focus 3** — every new projection (drift resolve, three run advances)
  carries both AFTER state (on `payload_json`) and BEFORE→AFTER
  (`diff_json={"from", "to"}`). Create projections carry full AFTER
  state; BEFORE is void by definition.
- **Focus 4** — `_drift_originating_actor` enforces the SLICE-021
  service-only override rule; R8a pins the both-or-neither validator on
  the resolution request contract.
- **Focus 5** — all four run-lifecycle transitions
  (`create` / `submit_snapshot` / `reconcile` / `fail`) write a dedicated
  change row keyed by the run aggregate with the full transition field
  set in `payload_json`.
- **Focus 6** — each drift row is its own aggregate with its own
  action + state-change pair via `_record_drift_created`; R4 guarantees
  the helper is only called for newly-inserted ids so `expected_version=0`
  is always correct; `DRIFT_CREATE_PAYLOAD_ALLOWLIST` pins the ten
  audited fields.
- **Focus 7** — `originating_actor_kind` / `originating_actor_id` are
  members of `RUN_CREATE_PAYLOAD_ALLOWLIST`, are threaded into the
  create action's `action_payload`, and are spoof-proofed by
  `_requested_by`.
- **Focus 8** — `mutate_entity()` inherits correlation and causation
  from `get_current_audit_context()` when the `MutationRequest` does
  not set them (`services/api/app/services/mutations.py:74-92`); the
  proposal never sets them explicitly, so every per-drift mutation
  inside the reconciliation transaction shares the outer HTTP
  request's correlation id.
- **Focus 9** — terminal replay returns the cached `MutationResult`
  before touching `mutate_entity`; no new action / state_change rows
  on retry.
- **Focus 10** — authority-denial auditing is explicitly a
  documented non-goal (R9 / §11), matching the shipped
  `RequireAuthority` precedent which logs overrides but not denials.

The three remaining LOW findings are informational: one acknowledges a
single-use inline literal on the drift-create path (matching shipped
precedent), one notes that `update_permission_intent` — a shipped
projection — does not carry `diff_json`, and one recommends restating
the shared-transaction convention at each helper bullet instead of only
in the closing paragraph. None of the three require proposal revision.

---

## Resolution Recommendations

Severity is **LOW** — no gate blockers. The following items may be folded
into the proposer's next touch of §5.3 / §10 at their discretion, without
re-running the audit risk gate:

1. **(Optional, Finding 1)** Promote the drift-create literals
   `"permission_drift.create"` / `"permission_drift.created"` to
   module-level constants in §10.2 alongside `DRIFT_CREATE_PAYLOAD_ALLOWLIST`
   for purely-constant-sourced audit strings everywhere in the new
   service.
2. **(Optional, Finding 2)** A future hardening slice could add
   `diff_json={"from": current.model_dump(...), "to": updated.model_dump(...)}`
   to `update_permission_intent` for symmetry with the applications
   precedent. Not in SLICE-014 scope — touches shipped code.
3. **(Recommended, Finding 3)** Add an explicit
   `connection=connection` mention inside each
   `_advance_run_submit` / `_advance_run_reconciled` /
   `_record_drift_created` bullet in §5.3 so the single-transaction
   contract is visible at every call site rather than only in the
   closing paragraph.

After (optional) folding these in, no re-audit is required. The
proposal clears the audit risk gate.
