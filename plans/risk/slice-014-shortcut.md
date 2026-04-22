# SLICE-014 Shortcut Risk Assessment (Revision 2)

**Severity: LOW**

The prior shortcut cycle raised seven findings against the original proposal:
F1 HIGH (`permission_drift.acceptd` f-string typo), F2 MEDIUM (inline
run-status literals), F3 MEDIUM (inline run `action_type` / `change_type`),
F4 MEDIUM (drift-batch return shape + `expected_version=0` on conflict ids),
F5 MEDIUM (authority at endpoint only), F6 LOW (`resolved_by_*` partial
fields), F7 LOW (duplicate `_read_head_version`). All seven were resolved in
Proposal Revision 1 via work items R1–R8 (`.pipeline/proposal.md:2453-2541`).
This re-assessment replaces the prior shortcut report.

What remains is spec-polish: three LOW findings that do not break
determinism, correctness, or established patterns and do not block
implementation.

---

## Coverage Matrix Against Focus Items

| # | Focus | Result | Evidence |
|---|-------|--------|----------|
| 1 | All aggregate mutations via `mutate_entity()` — no direct INSERTs | PASS | §5.1 `create_permission_intent` / `update_permission_intent`, §5.2 `resolve_permission_drift`, §5.3 `create_reconciliation_run`, `_advance_run_submit`, `_advance_run_reconciled`, `_advance_run_failed`, `_record_drift_created` all call `mutate_entity()`. The repository primitive `insert_permission_drift_batch` is invoked only inside `submit_reconciliation_snapshot`, whose per-id loop immediately emits a `mutate_entity()` audit record via `_record_drift_created` for each newly inserted row (`.pipeline/proposal.md:1573-1582`). |
| 2 | VALID_TRANSITIONS for drift (D5) and run (D4) enforced at service layer AND DB CHECK where possible | PASS | Service-layer: `VALID_DRIFT_TRANSITIONS` (§10.1 `.pipeline/proposal.md:2271-2277`), `VALID_RUN_TRANSITIONS` (§10.2 `.pipeline/proposal.md:2306-2311`). DB: `permission_drift_resolution_shape_valid` couples terminal status to resolution-field presence (§2.2 `.pipeline/proposal.md:356-372`); `permission_reconciliation_runs_terminal_shape_valid` couples each status to its own timestamp column(s) (§2.3 `.pipeline/proposal.md:455-478`). Combined, these make a reverse transition to `detected` / `requested` structurally invalid at the row level. |
| 3 | Drift idempotency via partial unique indexes on `(run_id, role_id, channel_id, kind)` — two indexes for Postgres NULL-equality caveat | PASS | §2.3 `.pipeline/proposal.md:503-518`: `uq_permission_drift__run_target` (`WHERE reconciliation_run_id IS NOT NULL AND channel_id IS NOT NULL`) and `uq_permission_drift__run_target_guild` (`WHERE reconciliation_run_id IS NOT NULL AND channel_id IS NULL`). Non-overlapping partial conditions cover the NULL-equality caveat explicitly. |
| 4 | Ownership/authority check at service layer before mutation dispatch (SLICE-023 precedent) | PASS | R5 introduced `_require_scoped_authority()` (§5.1 `.pipeline/proposal.md:1113-1139`) called BEFORE every `mutate_entity()` call: `create_permission_intent` / `update_permission_intent` / `list_permission_intents` (§5.1), `list_permission_drift` / `resolve_permission_drift` (§5.2 `.pipeline/proposal.md:1237-1249, 1355-1362`), `create_reconciliation_run` / `submit_reconciliation_snapshot` (§5.3 `.pipeline/proposal.md:1442-1449, 1529-1537`). Endpoint `_require_scoped` retained as early-403 short-circuit only. |
| 5 | Resolution metadata CHECK: terminal-status drift MUST have resolved_*; non-terminal MUST NOT | PASS | §2.2 `permission_drift_resolution_shape_valid` (`.pipeline/proposal.md:356-372`): `status IN ('reconciled','accepted')` ⇒ all four resolution fields NOT NULL; `status IN ('detected','acknowledged')` ⇒ all four resolution fields NULL. Defense in depth with §3.2 contract validator. |
| 6 | Reconciliation single tx, on failure rollback + advance run to `failed` in a separate tx | PASS | §5.3 `submit_reconciliation_snapshot` wraps steps 3–9 in `with db.transaction() as connection` (`.pipeline/proposal.md:1562-1589`). `except Exception` calls `_advance_run_failed(db, ...)` on a fresh transaction (helper spec at `.pipeline/proposal.md:1636-1653` notes "runs in its own transaction (not the caller's) per D8 step 10"). Original exception re-raised so the error surfaces as the API response while `failed` terminality is durably persisted. |
| 7 | Per-row drift OCC; resolve REQUIRES If-Match (not optional fallback) | PASS | §5.2 signature `resolve_permission_drift(..., expected_version: int, ...)` — required non-Optional int (`.pipeline/proposal.md:1228-1235`). §6.3 endpoint calls `parse_if_match_strong(request)` (`.pipeline/proposal.md:1878`) which raises if the header is missing. The prior lenient `update_permission_drift_status` is removed per Revision 1 (§5.2 note `.pipeline/proposal.md:1335-1337`). |
| 8 | Migration downgrades no-op per Live Server Principle | PASS | §2.1 `.pipeline/proposal.md:227-232`, §2.2 `.pipeline/proposal.md:391-394`, §2.3 `.pipeline/proposal.md:561-565` — all `pass` with Live-Server-Principle comments. Matches WU-037 / WU-042 precedent. |
| 9 | Service actor grant uses `@>` AND `<@` (exact match, not subset/superset) | PASS | §2.3 `.pipeline/proposal.md:552-555`: `permissions @> '...'::jsonb AND permissions <@ '...'::jsonb` plus active-grant guard (`revoked_at IS NULL AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)`). Bidirectional containment ⇒ exact JSONB array match. |
| 10 | Magic values — all action_type, change_type, status as constants not inline strings | MOSTLY PASS — see F1 | R1/R3 introduced `DRIFT_RESOLUTION_ACTION_TYPE`, `DRIFT_RESOLUTION_CHANGE_TYPE`, `RUN_ACTION_TYPE`, `RUN_CHANGE_TYPE` dispatch dicts (§10.1 `.pipeline/proposal.md:2291-2300`, §10.2 `.pipeline/proposal.md:2327-2338`). F1 flags three single-use residual literals not yet routed through constants. |
| 11 | Discord adapter NEVER mutates drift locally (AC4) — read-only on drift state | PASS | §7.3 `handle_reconcile_permissions` only calls `permission_client.create_reconciliation_run`, `.submit_snapshot`, `.read_run` (on 409 replay). No local drift persistence, no `role.edit()`, no `channel.set_permissions()`, no file-backed state. AC4 tests `test_handler_never_calls_drift_mutation_endpoints` + `test_handler_never_calls_fetch_channel_or_fetch_member` pin this discipline (§8.4 `.pipeline/proposal.md:2204-2205`). |
| 12 | `decay_rules`-style silent-ignore anti-pattern on unknown snapshot entries | MOSTLY PASS — see F2 | Contracts reject unknown `kind` values via discriminated union (§3.4). `ReconciliationSnapshotRequest.reject_duplicate_keys` raises explicitly (`.pipeline/proposal.md:797-810`). The one silent filter is in the Discord adapter's `_build_snapshot` where member-target overwrites are `continue`-skipped without a log line or operator hint (F2). |
| 13 | Decimal-string masks: don't silently convert to int/string elsewhere; keep canonical | PASS | Contracts use `DecimalBitString` throughout (§3.4 `.pipeline/proposal.md:772-791`). The single int→str gateway is `_decimal_bits(value: int) -> str` in the Discord adapter (`.pipeline/proposal.md:2110`), which converts `discord.py`'s `Permissions.value` into the canonical decimal-string form. Cleared-state literals `'0'` for guild_role and `'0'`/`'0'` for channel_role preserve the canonical form (§5.3 `_build_drift_rows` step 4). Repository normalization path matches the shipped `_normalize_permission_intent_row` shape. |
| 14 | Deterministic diff ordering (role_id asc, channel_id asc) | MOSTLY PASS — see F3 | Synthesis D8 step 7 binds the sort key `sorted(union(intent_keys, snapshot_keys), key=(role_id, channel_id or ""))` (`.pipeline/synthesis.md:518-520`). Proposal §5.3 `_build_drift_rows` step 4 says "For each key in the sorted union" but does not re-assert the exact tiebreaker lambda (F3). D8 binding controls; proposal prose under-specifies. |
| 15 | Reconciliation terminal replay (AC4): idempotent return — does NOT re-compute diff or re-insert | PASS | §5.3 `submit_reconciliation_snapshot` early-returns at `if existing.status in RUN_TERMINAL_STATUSES:` BEFORE any call to `_build_drift_rows` / `insert_permission_drift_batch` (`.pipeline/proposal.md:1543-1559`). For `reconciled`, returns cached `existing` (which was loaded with `drift_ids` via `read_reconciliation_run`) + fresh ETag. For `failed`, raises 409. No mutation, no diff recomputation. |

---

## Findings

### F1 — LOW — Residual inline `permission_drift.create` / `.created` and run-status literals

- **File reference.** §5.3 `_record_drift_created` helper spec at
  `.pipeline/proposal.md:1678-1706`; §5.3 `submit_reconciliation_snapshot`
  status compares at `.pipeline/proposal.md:1543-1559`.
- **Evidence.** The helper description specifies
  `action_type="permission_drift.create"` and
  `change_type="permission_drift.created"` as inline literals — not routed
  through a dispatch dict. Every other drift/run action/change string in
  the proposal goes through a constant map after Revision 1 (R1/R3). §10.1
  declares `DRIFT_RESOLUTION_*` maps but no `DRIFT_CREATE_ACTION_TYPE` /
  `DRIFT_CREATE_CHANGE_TYPE` sibling. Similarly
  `submit_reconciliation_snapshot` uses `existing.status == "reconciled"`
  (line 1544) and `existing.status != "requested"` (line 1555) as inline
  comparisons instead of `RUN_STATUS_RECONCILED` / `RUN_STATUS_REQUESTED`
  sentinels.
- **Why this matters.** The synthesis constraint
  (`.pipeline/synthesis.md:914-916`) says "No magic action_type /
  change_type strings anywhere in the new service — constants only".
  Revision R1/R3 removed the f-string class of bug (which was HIGH), but
  these residual single-use literals were not migrated. They are
  *compile-time visible* single strings — they cannot silently drift the
  way an f-string can — so the correctness risk is essentially zero.
  The cost is only that a future rename (e.g., splitting drift-creation
  into "run-scoped vs expiry-scoped" change types) must touch raw strings
  rather than one dispatch row.
- **Severity.** LOW — single-use literals, no dispatch site.
- **Resolution (optional; not gating).** Extend §10.1 / §10.2 with:
  ```python
  DRIFT_CREATE_ACTION_TYPE = "permission_drift.create"
  DRIFT_CREATE_CHANGE_TYPE = "permission_drift.created"
  RUN_STATUS_RECONCILED          = "reconciled"
  RUN_STATUS_REQUESTED           = "requested"
  RUN_STATUS_SNAPSHOT_SUBMITTED  = "snapshot_submitted"
  RUN_STATUS_FAILED              = "failed"
  ```
  and route the three call sites through them.

---

### F2 — LOW — Discord adapter silently filters member-target overwrites

- **File reference.** §7.3 `_build_snapshot` at
  `.pipeline/proposal.md:2089-2093`.
- **Evidence.** The snapshot builder iterates `channel.overwrites` and
  discards non-role targets with `if not _is_role(target): continue`.
  No counter, no log line, no hint in the operator-visible ephemeral
  success message. The decision is documented in synthesis D13 ("Member-
  level overwrite serialization — deferred") and §11 of the proposal
  (`.pipeline/proposal.md:2399-2401`), so the scope bound is intentional.
- **Why this matters.** The silent-skip shape matches the `decay_rules`
  anti-pattern Focus 12 warns against: a branch that drops input without
  an error or observable signal. If Discord has member-level overwrites
  today, an operator running reconciliation will never know they were
  dropped as out-of-scope. The drift view will look complete but silently
  exclude a whole class of actual Discord state. This does not cause
  incorrect drift rows for in-scope (role) targets; it only hides the
  fact that out-of-scope state exists.
- **Severity.** LOW — consistent with documented scope; no correctness
  impact for role-target drift detection.
- **Resolution (optional; not gating).** Either
  (a) accumulate `ignored_count = sum(1 for t, _ in channel.overwrites.items()
      if not _is_role(t))` and append to the ephemeral success message
      ("… (N drift row(s); M member overwrites out of scope)"); or
  (b) emit a single `logger.info("snapshot dropped N member-level
      overwrites as out-of-scope", extra={"run_id": str(run_id),
      "count": N, "scope_kind": scope_kind, "scope_id": scope_id})`.
  Either makes the scope boundary observable without changing behavior.

---

### F3 — LOW — `_build_drift_rows` sort key under-specified in proposal prose

- **File reference.** §5.3 `_build_drift_rows` step 4 at
  `.pipeline/proposal.md:1660-1672`.
- **Evidence.** Step 4 says "For each key in the sorted union: …" without
  naming the sort key. Synthesis D8 step 7 is explicit:
  `sorted(union(intent_keys, snapshot_keys), key=(role_id, channel_id or ""))`
  (`.pipeline/synthesis.md:518-520`). The binding controls the code agent,
  but the proposal does not mirror it in the algorithm description.
- **Why this matters.** Focus 14 requires deterministic ordering for
  reproducibility of `drift.id` allocation and audit-row insertion order
  across replays. A code agent that defaults to Python's
  `sorted(set_of_tuples)` would effectively sort by
  `(kind, role_id, channel_id)` rather than `(role_id, channel_id or "")`,
  producing a different iteration order and therefore a different
  `drift.id` allocation sequence. Both orderings are deterministic, but
  D8 binds the second. Terminal replay would still return the same set
  (rows already persisted), but the first run's `drift_ids` listing in
  the audit row payload would differ between the two orderings, making
  cross-environment audit-diff comparisons noisy.
- **Severity.** LOW — D8 binds and is unambiguous; test fixtures can pin
  order with one explicit assertion. Missing prose is a spec-completeness
  gap, not a correctness defect.
- **Resolution (optional; not gating).** In §5.3 `_build_drift_rows` step 4,
  replace "For each key in the sorted union:" with
  "For each key in
  `sorted(set(intent_by_key) | set(snapshot_by_key), key=lambda k: (k[1], k[2] or ''))`
  (role_id ascending, channel_id NULLS FIRST per D8 step 7):".

---

## Items confirmed correct (Revision 1 resolutions)

The seven findings from the prior cycle are all resolved:

- **F1 (HIGH, `permission_drift.acceptd` typo)** — R1 introduced
  `DRIFT_RESOLUTION_ACTION_TYPE` and `DRIFT_RESOLUTION_CHANGE_TYPE` in §10.1
  and routed §5.2 through them (`.pipeline/proposal.md:1281-1282,
  2291-2300`). Regression test
  `test_resolve_drift_accept_emits_correct_change_type` pins each of the
  three actions (§8.2 `.pipeline/proposal.md:2173-2179`).
- **F2 (MEDIUM, inline run-status literals)** — R2 rewrote the terminal
  check as `if existing.status in RUN_TERMINAL_STATUSES:` with an inner
  switch on the terminal kind (`.pipeline/proposal.md:1543-1559`).
- **F3 (MEDIUM, inline run action/change strings)** — R3 added
  `RUN_ACTION_TYPE` and `RUN_CHANGE_TYPE` dispatch dicts in §10.2 and
  routed `create_reconciliation_run` + the three `_advance_run_*` helpers
  through them (`.pipeline/proposal.md:1466-1469, 1491, 2327-2338`).
  §10.3 name inventory updated for verb-past symmetry
  (`.requested` → `.created`).
- **F4 (MEDIUM, drift-batch return shape)** — R4 changed
  `insert_permission_drift_batch` to return only newly-inserted ids;
  conflict rows are silently dropped. The service iterates only
  `new_drift_ids` through `_record_drift_created` so
  `expected_version=0` can never fire against an existing aggregate head
  (`.pipeline/proposal.md:942-981, 1573-1582`). The run's final drift
  set is read back via `list_drift_ids_by_run(run_id)`.
- **F5 (MEDIUM, endpoint-only authority)** — R5 introduced
  `_require_scoped_authority()` in §5.1 called BEFORE `mutate_entity()`
  in every mutating/reading service function
  (`.pipeline/proposal.md:1113-1139`). Endpoints kept `_require_scoped`
  as an early-403 short-circuit but are no longer the sole gate.
- **F6 (LOW, partial `resolved_by_*`)** — R8(a) added
  `model_validator(mode="after")` on `PermissionDriftResolutionRequest`
  enforcing `resolved_by_kind` / `resolved_by_id` both-or-neither
  (`.pipeline/proposal.md:719-731`).
- **F7 (LOW, duplicate head-version read)** — R8(c) refactored both
  terminal-replay return paths to compute `_read_head_version` once via
  a shared helper (`.pipeline/proposal.md:1545-1550, 1596-1601`).

Other items confirmed correct on the original assessment — `mutate_entity`
coverage (Focus 1), VALID_TRANSITIONS + CHECK discipline (Focus 2), partial
unique indexes (Focus 3), resolution-metadata CHECK (Focus 5), single-tx
algorithm with separate-tx fail advance (Focus 6), required `If-Match`
(Focus 7), no-op downgrades (Focus 8), `@>/<@` exact containment (Focus 9),
read-only Discord adapter (Focus 11), decimal-string masks (Focus 13),
terminal replay without recompute (Focus 15) — remain correctly specified
in the post-Revision proposal.

---

## Summary

Proposal Revision 1 cleanly resolved all MEDIUM/HIGH shortcuts from the
prior cycle. The f-string bug that would have emitted
`permission_drift.acceptd` is replaced by constant-lookup dispatch;
run-lifecycle strings go through `RUN_ACTION_TYPE` / `RUN_CHANGE_TYPE`;
the drift-batch primitive now returns only newly-inserted ids so
`expected_version=0` is safe on every returned id; authority enforcement
moved into the service layer before `mutate_entity` so background/CLI
callers hit the same gate as HTTP callers; the resolved-by spoof-proof
pattern gains a both-or-neither validator; and the duplicate
head-version read is collapsed.

What remains are three LOW spec-polish items:

- **F1** — two residual single-use literals (`permission_drift.create`,
  `.created`) and four status-string compares in
  `submit_reconciliation_snapshot` not yet migrated to constants.
- **F2** — member-target overwrite filter in the Discord adapter is
  silent; the scope decision is documented but unobservable to operators.
- **F3** — `_build_drift_rows` step 4 does not echo the D8 sort-key
  lambda, so deterministic ordering relies on the synthesis binding
  alone.

None of these alters control flow, admits a silent correctness regression,
or breaks the shortcut constraints of the synthesis. All three are
independently fixable in a future pass without affecting any other
proposal decision. The proposal is ready to advance past the shortcut
gate.

**Severity: LOW.** No resolution required before implementation. The
three findings above are discretionary polish the proposer may fold in
without re-triggering the risk cycle.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
