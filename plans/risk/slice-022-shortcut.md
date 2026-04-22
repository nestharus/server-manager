# SLICE-022 Shortcut Risk Assessment — Revision 1

**Rating: LOW.** All fifteen shortcut-focus items now PASS against the revised
proposal (`.pipeline/proposal.md` Revision 1). The three MEDIUM findings from
Revision 0 (F1 chapter_id spoof, F2 per-member isolation, F3 roster-call
signature) are closed by proposal revisions R1, R2, and R6 respectively.
Observation 3 from Revision 0 (non-atomic consequence dispatch) is closed
by R2+R6 jointly. The six LOW observations from Revision 0 that were
explicitly deferred to the implementation phase are carried forward as
advisory hygiene items; none gate the risk verdict.

No HIGH findings. No MEDIUM findings. Six LOW observations.

---

## Scope

Re-reviewed `.pipeline/proposal.md` (1977 lines including Revision 1 log),
`.pipeline/synthesis.md` (D1–D15), `.pipeline/research.md`,
`product-strategy/tickets/SLICE-022.md` (AC1–AC4, WU grid, Code Boundary),
and `AGENTS.md` against the fifteen shortcut-focus items. Diffed the
Revision 1 proposal against Revision 0 at:

- §1 AC4 (operator attribution on `/evaluations/run` — R4),
- §3 (`EvidenceChapterMismatchError`, removal of
  `COMPLIANCE_EVALUATION_CONSEQUENCE_CHANGE_TYPE` — R1, R3),
- §4 (`mark_consequence_applied` removal, `insert_evaluation_if_absent`
  tx-scoped docstring, `get_roster_entry` helper — R2, R3, R6),
- §5 (`submit_evidence` rule-first authorize pattern,
  `run_scheduled_compliance_evaluations` per-member isolation,
  `_evaluate_member_rule` single-tx rewrite with atomic roster dispatch,
  `correct_evidence.mutate_projection` richer `diff_json` — R1, R2,
  R5, R6),
- §7 (worker passes `originating_actor=None` — R4),
- §8 (status table row for `chapter_id/rule mismatch (R1)` 422),
- §10 (nine new tests across WU-040A, WU-040B-correct, WU-041B),
- §11 (out-of-scope unchanged),
- Revision log (R1–R6 summary + L1 unchanged + six LOW deferrals).

Cross-referenced shipped precedents in
`services/api/app/services/mutations.py:58,70,123,143`,
`…/services/roster.py:186-281`,
`…/services/permission_reconciliation.py:154-164,651-660`,
`…/services/permissions.py`,
`…/tasks/permission_expiry.py:43-80`,
`…/tasks/ticket_sla.py`,
`services/api/app/repositories/ticket_sla.py:119-162`,
`migrations/versions/wu-028b_permission_reconciliation_runs.py:128-163`,
`migrations/versions/wu-038_permission_intent_expiry.py:36-79`,
`services/api/app/services/scheduler.py:34,150,197,256-273`.

---

## Focus Walk-Through

| # | Focus | Verdict | Evidence |
|---|---|---|---|
| 1 | All mutations via `mutate_entity` — no direct INSERT/UPDATE on `compliance_rules`/`evidence_submissions`/`compliance_evaluations` | PASS | Rule create/update (§5 `create_rule` / `update_rule`), evidence submit (§5 `submit_evidence`), correction (§5 `correct_evidence`), extraction persist (§5 `_persist_extraction_success`/`_persist_extraction_failure`), evaluation create (§5 `_evaluate_member_rule` → `mutate_entity` with `aggregate_type="compliance_evaluation"`), evaluation review (§5 `review_evaluation`) — all routed through `mutate_entity`. Repository helpers (`create_rule`, `update_rule`, `update_evidence_after_extraction`, `update_evidence_correction`, `insert_evaluation_if_absent`, `update_evaluation_review`) run only inside the `mutate_projection` callback. **R2 hardens this**: `insert_evaluation_if_absent`'s docstring explicitly binds it to "invoked only from inside `_evaluate_member_rule`'s `mutate_projection` callback — never as a naked DML step outside a `mutate_entity` call" (§4). `mark_consequence_applied` was removed in R3 — no second mutation path, no orphan DML. |
| 2 | OCC via If-Match on rule update, evidence correction, evaluation review | PASS | §8 endpoints parse `expected_version = parse_if_match_strong(request)` on `PATCH /rules/{id}`, `POST /evidence/{id}/correct`, `POST /evaluations/{id}/review`. `_shared.raise_known_compliance_error` maps `StaleMutationError → 412`. `mutate_entity` enforces OCC via `SELECT … FOR UPDATE` on `aggregate_heads` (`mutations.py:123,143`). **R6 adds an explicit OCC surface** on the worker-side roster transition: `expected_version=roster_entry["version"]` is plumbed from `get_roster_entry`, so the worker does not gamble on a stale version. |
| 3 | Service-layer authority AT TOP of each mutating service function | PASS | `create_rule`: `_require_scoped_authority("compliance_rule.write", scope_id=request.chapter_id)` first (§5). `submit_evidence` (R1): rule is loaded first to resolve scope, then authority uses `rule["chapter_id"]` — matches the precedent at `permission_reconciliation.py:651-660` where row lookup resolves scope before authority. No DML runs before authority. `correct_evidence`, `trigger_extraction`, `review_evaluation`, `get_evaluation` continue to fetch the aggregate row first (SELECT-only) and authorize against the row's `chapter_id`. Worker paths rely on the `compliance-evaluator` service-actor grant (scope_kind=global per D11 / SLICE-008 hierarchy) enforced via `mutate_entity`. |
| 4 | Constants-only dispatch — no f-strings | PASS | §3 declares every action/change type and payload allowlist as module-level constants. Every `mutate_entity` call in §5 uses one of these constants. **R3 tightened this** by removing `COMPLIANCE_EVALUATION_CONSEQUENCE_CHANGE_TYPE` (orphan after consequence became an attribute of the CREATE change). Only residual f-strings are (a) `request_surface` values (deferred LOW in SLICE-020 R6, shipped-precedent), (b) service-actor seed SQL in `wu-041a` (verbatim wu-038 pattern, interpolating a Python constant not request data), and (c) roster `reason=f"compliance_violation:{rule['name']}"` string — a human-readable reason field on the roster transition request, not an `action_type`/`change_type` value. Acceptable under D13 which binds vocabulary, not free-form reason text. |
| 5 | `UNIQUE (member_id, rule_id, period_start, period_end)` + `ON CONFLICT DO NOTHING` for worker idempotency (AC4) | PASS | §2 declares `ux_compliance_evaluations__member_rule_period`. §4 `insert_evaluation_if_absent` is `INSERT ... ON CONFLICT (member_id, rule_id, period_start, period_end) DO NOTHING RETURNING *`, mirroring `repositories/ticket_sla.py:135-136`. **R2 hardens idempotency semantics**: when the insert returns `None`, a private `_AlreadyEvaluatedSentinel` raised inside `mutate_projection` aborts the projection cleanly (no audit row, no duplicate). When the insert succeeds but a downstream step (audit projection, roster transition) raises, the whole `mutate_entity` transaction rolls back atomically — next tick retries cleanly because the ON CONFLICT skip does not fire. |
| 6 | Consequence routing via roster service | PASS | §5 `_evaluate_member_rule` calls `roster_service.transition_roster_entry(db, entry_id=roster_entry["id"], request=RosterEntryTransitionRequest(to_status="under_review", reason=f"compliance_violation:{rule['name']}", originating_actor_kind=..., originating_actor_id=...), expected_version=roster_entry["version"], actor=actor, connection=conn)`. Guardrails: "Roster consequences route only through `services/api/app/services/roster.py::transition_roster_entry` (D10). No raw `UPDATE roster_entries` in compliance code." **R6 closes F3** by plumbing `entry_id` + `expected_version` from `get_roster_entry`, removing the under-specification. The call runs on the evaluation's `mutate_entity` connection (kwarg available at `mutations.py:70`), so roster + evaluation commit atomically. |
| 7 | Cadence period computation deterministic — specific calendar rules | PASS | §5 `_compute_period` declares explicit branches: `weekly` → ISO week Monday 00:00 UTC → Sunday 23:59:59 UTC; `monthly` → 1st → last day UTC; `quarterly` → calendar quarters in UTC. Anchor is `now - evaluation_window_days`, i.e., the most recently completed window (D9). `cadence_params.week_offset` / month / quarter offsets provide explicit backfill. `period_start` / `period_end` are stamped on the evaluation row (§2) so later rule edits cannot retroactively duplicate history. Test `test_period_computation_weekly_monthly_quarterly` (§10) pins the branches. |
| 8 | CHECK constraints enforce `extraction_status` shape (completed → raw_text+extracted_fields; failed → extraction_error; corrected → corrected_* + overlay) | PASS | §2 declares three CHECK constraints: `evidence_submissions_completed_requires_ocr`, `evidence_submissions_failed_requires_error`, `evidence_submissions_corrected_requires_overlay`. Each mirrors D3 verbatim. Additional `evidence_submissions_confidence_bounded` CHECK (0 ≤ confidence ≤ 1) + `evidence_submissions_attachment_ref_non_blank` CHECK. Observation 1 re `failed → corrected` leaving `extracted_fields NULL` carries forward as a LOW hygiene item, not a focus violation. |
| 9 | Raw text + attachment_ref preserved across corrections (AC3) | PASS | §4 `update_evidence_correction` docstring binds the helper to overlay columns only. §5 `correct_evidence` narrative reiterates the invariant. Correction payload allowlist (§3 `EVIDENCE_CORRECT_PAYLOAD_ALLOWLIST`) contains only `corrected_fields`, `correction_reason`, `corrected_by_member_id`. Tests `test_correction_preserves_raw_text_and_attachment_ref` and `test_correction_preserves_original_extracted_fields` (§10) assert DB-level preservation. **R5 strengthens audit shape**: `diff_json` now records prior overlay + new overlay + immutable `extracted_fields` baseline in one state-change row, so a second correction is self-describing without replay. |
| 10 | OCR provider interface pluggable; stub raises explicit error (not silent no-op) | PASS | §6 `StubOcrProvider.extract` raises `OcrProviderNotConfiguredError("OCR provider not configured")`. `_shared.raise_known_compliance_error` maps it to 503 (§8). Endpoint test `test_extract_with_stub_provider_returns_503` (§10) pins the behavior. No quiet success path; no `pass`/`return None` stub. Settings wire a concrete provider in production; out of scope for SLICE-022 per D15. |
| 11 | Worker tick mirrors `permission_expiry_worker_tick` / `ticket_sla_worker_tick` — root audit context; specific exception handling; per-item tx | PASS | Root audit context (§7 `_root_audit_context()` + `use_audit_context` with `nullcontext` fallback) matches `tasks/permission_expiry.py:43-74`. Tick-level try/except: `StaleMutationError → logger.debug` + `Exception → logger.exception` (§7). **R2 closes F2**: per-member try/except is now explicit inside `run_scheduled_compliance_evaluations` (§5 inner loop) with the same three-arm pattern (`StaleMutationError → debug`, `Exception → exception`, continue). Unit of work is `(member, rule, period)`, not `rule`. Per-rule setup failure is caught separately so one bad rule does not abort the remaining rules. Mirrors SLICE-020 R1 `_expire_single_intent`. Test `test_worker_member_failure_does_not_skip_remaining_members_of_rule` (§10) pins the isolation. |
| 12 | `compliance-evaluator` service actor grant uses `@>` AND `<@` containment + `expires_at` + `revoked_at` guards (wu-028b precedent) | PASS | §2 INSERT wrapped in `WHERE NOT EXISTS (… permissions @> '…'::jsonb AND permissions <@ '…'::jsonb AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP))`. Verbatim shape of `migrations/versions/wu-028b_permission_reconciliation_runs.py:128-163` and wu-038:36-79. Idempotent re-run safe. Grants are `compliance_rule.read`, `compliance_evaluation.write`, `roster.transition` at global scope (D11). |
| 13 | Consequence auto-application only when policy says — NOT always. `consequence_params.auto_apply: bool` | PASS | §5 `_compute_consequence_shape` docstring now explicitly binds the **fail-safe default**: "`consequence_params.auto_apply` (fail-safe default: must be explicitly True; absence → False) → `(under_review_applied, not_required)`. otherwise → `(none, not_required)` or `(none, pending)` per `consequence_params.require_review`." An operator who creates an `under_review` consequence rule without setting `auto_apply=True` gets `review_queued` queued state, not an automatic roster transition. The Revision 0 wording that inverted this default has been corrected. Tests `test_worker_respects_consequence_kind_under_review_only_on_violation` + `test_worker_records_review_queued_for_review_consequence_kind` pin both paths. |
| 14 | Migration downgrades no-op per live-server | PASS | §2 header: "Each downgrade is a `pass` no-op per the Live Server Principle (matches `wu-038_permission_intent_expiry.py:76–79`)." Applies to all three SLICE-022 migrations. |
| 15 | `rule_version` in evaluation = snapshot of rule's `aggregate_heads` version at evaluation time | PASS | §2 `rule_version BIGINT NOT NULL CHECK (rule_version >= 1)`. §3 contract field `rule_version: int = Field(ge=1)`. §5 `_evaluate_member_rule` now shows `rule_version = _current_rule_version(db, rule_id=rule["id"])` as an explicit lookup (previously implicit — closed by Revision 1's rewrite, though the helper's internals remain Observation 2). D7 binds the snapshot semantics. |

---

## Revision 0 MEDIUM findings — closed in Revision 1

### F1 (`submit_evidence` chapter_id spoof) — CLOSED by R1

**Revision 1 mechanics.** `submit_evidence` (§5) now:

1. Loads `rule = get_rule(conn, request.rule_id)` before any authority check.
2. Raises `ComplianceRuleNotFoundError` (→ 404) if the rule is missing.
3. Raises `EvidenceChapterMismatchError` (→ 422) if
   `request.chapter_id != rule["chapter_id"]`.
4. Authorizes with
   `_require_scoped_authority("compliance_evidence.submit", scope_kind="chapter", scope_id=rule["chapter_id"], actor=actor, db=db)`
   — scope is derived from the rule, not the request.
5. Persists `chapter_id=rule["chapter_id"]` — derived, spoof-proof — and
   `submitted_by_member_id=actor.actor_id` — spoof-proof.

`EvidenceChapterMismatchError` was added to §3 contracts with structured
fields (`rule_id`, `rule_chapter_id`, `request_chapter_id`). §8 maps the
error to 422 with `{"code": "evidence_chapter_mismatch"}`. Three tests
added in §10:

- `test_submit_rejects_chapter_id_mismatch_with_rule` — 422 on mismatch.
- `test_submit_authorizes_against_rules_chapter_not_request_chapter` —
  authority check uses the rule's chapter, and a mismatched request is
  rejected (422) before authority is consulted.
- `test_submit_persists_chapter_id_from_rule_not_request` — on a matching
  request, the persisted `chapter_id` equals the rule's chapter.

**Residual note.** The proposal chose the "service-layer CHECK" remediation
(kept `chapter_id` on the request contract, added validation) over the
"derivation-only" remediation (remove `chapter_id` from the request).
Both close the spoof surface; derivation is slightly cleaner. The retained
`chapter_id` field is defensive (future-proofing for callers that want
to discover they built the wrong request) rather than load-bearing. No
further risk action needed — this is documented as Observation 5 below.

### F2 (per-member isolation) — CLOSED by R2

**Revision 1 mechanics.** `run_scheduled_compliance_evaluations` (§5) now
wraps each member evaluation in its own try/except:

```python
for member in members:
    try:
        inserted = _evaluate_member_rule(db, rule=rule, member=member, ...)
        if inserted is not None:
            created.append(inserted)
    except StaleMutationError:
        logger.debug(
            "compliance evaluation OCC skip rule=%s member=%s",
            rule["id"], member["member_id"],
        )
        continue
    except Exception:
        logger.exception(
            "compliance evaluation failed rule=%s member=%s",
            rule["id"], member["member_id"],
        )
        continue
```

Per-rule setup (period compute, member enumeration) still lives in its own
outer try/except — so a rule-level setup error skips the rule but not
every rule in the batch. The unit of work is `(member, rule, period)`,
matching SLICE-020 R1 `_expire_single_intent` precedent. Test
`test_worker_member_failure_does_not_skip_remaining_members_of_rule`
(§10) pins the isolation.

### F3 (roster call signature under-specified) — CLOSED by R6

**Revision 1 mechanics.** `_evaluate_member_rule` (§5) now:

1. Calls `get_roster_entry(connection, chapter_id=..., member_id=...)`
   before opening the `mutate_entity` transaction, returning the roster
   row + its `aggregate_heads` version. (§4 "Roster member enumeration
   + per-member entry read" section adds this helper to
   `services/api/app/repositories/roster.py` with a service-layer alias
   if compliance needs one — SELECT-only, no authority required for the
   worker path.)
2. Passes `entry_id=roster_entry["id"]` and
   `expected_version=roster_entry["version"]` into
   `roster_service.transition_roster_entry(...)`.
3. Runs the roster transition on the same connection as the evaluation
   insert via `connection=conn` (`mutations.py:70` accepts the kwarg),
   so evaluation insert + audit projection + roster transition commit
   or roll back atomically.
4. `StaleMutationError` from the roster transition propagates out of
   `mutate_projection` → `mutate_entity` rolls back the whole per-member
   transaction → next tick's ON CONFLICT insert succeeds cleanly (no
   shadow row, no retry bookkeeping, no `deferred_occ_conflict` marker
   state).
5. `InvalidRosterStatusTransitionError` (member already
   `under_review`/`removed`) is handled upstream at
   `_compute_consequence_shape`, which chooses
   `consequence_applied="none"` when the roster precondition does not
   hold — no silent catch inside the write path.

Tests added:

- `test_worker_rolls_back_evaluation_insert_when_roster_transition_occ_fails`
  — roster OCC failure rolls back the evaluation insert; next tick
  retries cleanly.
- `test_worker_rolls_back_evaluation_insert_when_audit_projection_fails`
  — audit projection failure rolls back the evaluation insert (M1
  coverage).

### Observation 3 (non-atomic consequence dispatch) — CLOSED by R2+R6 jointly

The atomic per-member transaction (option (a) from Revision 0's
Observation 3 remediation) is now the proposal's binding shape.
Evaluation insert + audit projection + roster transition share one
`mutate_entity` transaction. If roster OCC or any downstream step
raises, the whole unit rolls back — the next tick retries naturally via
the UNIQUE key + ON CONFLICT DO NOTHING. No orphan `consequence_applied`
state, no operator-reconciliation report needed.

---

## Observations (LOW — advisory, do not gate)

### Observation 1 — `failed → corrected` transitions still permit `extracted_fields IS NULL` on a corrected row (carried from Revision 0)

- **References.** §2 `evidence_submissions_corrected_requires_overlay`
  CHECK (does not require `extracted_fields` to be non-null); D6 (allows
  correction from `failed`).
- **Why it's worth flagging.** Downstream consumers must use
  `COALESCE(extracted_fields_corrected, extracted_fields)` — if the
  evaluator in `_compute_rule_result` reads `extracted_fields` directly
  for a `failed → corrected` row, the officer's correction is invisible.
- **Remediation (hygiene).** Add a test
  `test_corrected_row_from_failed_exposes_officer_values_via_overlay_read`
  and a one-line comment on `_compute_rule_result` documenting the
  COALESCE rule. The proposal's Revision 1 log classes this as a
  LOW/Obs 1 deferral to implementation — this assessment concurs.

### Observation 2 — `_current_rule_version(...)` helper internals remain unspecified (carried from Revision 0, slightly narrowed)

- **References.** §5 `_evaluate_member_rule` shows
  `rule_version = _current_rule_version(db, rule_id=rule["id"])`.
  Revision 0 Observation 2 flagged that `list_active_rules` returns
  compliance-rule rows without joining `aggregate_heads`. Revision 1
  introduces the helper call but does not pin whether it reads
  `aggregate_heads.current_seq` or joins at the list-active-rules layer.
- **Remediation.** Either (a) extend `list_active_rules` to join
  `aggregate_heads` and return `current_seq` as `rule_version`, or (b)
  implement `_current_rule_version` via `get_head(conn,
  aggregate_type="compliance_rule", aggregate_id=rule_id)`. Either works
  — spell out in the hookpoint phase.
- **Severity.** LOW. CHECK `rule_version >= 1` blocks a default-zero
  mistake. Pin with test
  `test_evaluation_rule_version_matches_rule_aggregate_head_at_eval_time`.

### Observation 3 — `compliance_rule.read` on `compliance-evaluator` is defensive but unexercised (carried from Revision 0)

- **References.** §2 seed; §4 `list_active_rules` (repository helper,
  bypasses authority); §5 worker.
- **Severity.** LOW / cosmetic. Leave as-is for symmetry with the
  officer-facing namespace (D11). Note in the seed comment that the
  worker reads rules via the repository helper, not this grant.

### Observation 4 — `asyncio.run(...)` inside sync `trigger_extraction` is event-loop-fragile if the endpoint is `async def` (carried from Revision 0)

- **References.** §5 `trigger_extraction` (sync service calling
  `asyncio.run(ocr_provider.extract(...))`); §6 `OcrProvider.extract`
  is `async def`.
- **Remediation.** Declare the `POST /compliance/evidence/{id}/extract`
  handler as `def` (not `async def`) so FastAPI runs it via
  `run_in_threadpool` and `asyncio.run` gets a fresh loop per thread.
  Or make `trigger_extraction` async end-to-end. The shipped pattern
  favors sync services (`services/api/app/services/*`) — sync is the
  default expectation.
- **Severity.** LOW. Not a defect in the proposal — an under-specified
  endpoint declaration that should be nailed down in hookpoints/
  implementation.

### Observation 5 — `chapter_id` retained on `EvidenceSubmissionCreate` despite derivation semantics (new, minor)

- **References.** §3 `EvidenceSubmissionCreate.chapter_id: str = Field(min_length=1)`; §5 `submit_evidence` derives effective chapter
  from the rule and treats the request field as a consistency check.
- **Why it's worth flagging.** The field is load-bearing for the 422
  `EvidenceChapterMismatchError`, not for authorization or persistence.
  A later-reader could mistake it for authoritative. Removal (Revision 0
  F1 option A) is cleaner; retention (option B) is acceptable. The
  status-table row in §8 labels the 422 as "chapter_id/rule mismatch
  (R1)" so the intent is explicit.
- **Information-leak surface.** An unauthorized caller who guesses a
  valid `rule_id` with the wrong `chapter_id` receives 422 (mismatch)
  before authority is checked; with the right `chapter_id` they receive
  403. The response-code difference leaks the rule's chapter — a tiny
  enumeration surface, no worse than existing read endpoints that return
  404 vs 403. Not a blocker; worth a line in the implementation phase
  review.
- **Severity.** LOW. Document the invariant in a comment on
  `EvidenceSubmissionCreate.chapter_id`, or delete the field in a
  follow-up cleanup. Proposal is acceptable either way.

### Observation 6 — `test_worker_does_not_bypass_roster_service_with_raw_sql` overpromises a negative (carried from Revision 0)

- **References.** §10 WU-041B test list.
- **Remediation.** Rename to
  `test_worker_consequence_writes_roster_transition_audit_event_via_roster_service`
  (inspect `activity_state_changes` after a consequence is applied and
  assert a `roster_entry.transition` change exists alongside the
  `compliance_evaluation.create` change, tied by `correlation_id`), or
  `test_worker_calls_roster_transition_roster_entry_and_not_raw_sql`
  (patch `services.roster.transition_roster_entry` with a spy and assert
  the call). A linter rule banning `UPDATE roster_entries` in
  compliance modules is a separate hygiene control, not a test.
- **Severity.** LOW. The D10 intent is clear; only the test name over-
  reaches.

---

## Non-findings (explicitly verified absent)

- ✅ All mutations flow through `mutate_entity`; no direct DML on
  compliance tables outside `mutate_projection` (Focus 1). **R2/R3
  eliminated the `mark_consequence_applied` helper and the orphan
  change-type constant.**
- ✅ OCC via If-Match on all three mutation endpoints + explicit
  `expected_version` on the worker-side roster transition (Focus 2; R6).
- ✅ Service-layer authority precedes every mutation (Focus 3; R1
  closes the `submit_evidence` spoof).
- ✅ Constants-only audit dispatch (Focus 4; R3 removed the orphan
  constant).
- ✅ `UNIQUE (member_id, rule_id, period_start, period_end)` + `ON
  CONFLICT DO NOTHING` + atomic retry semantics (Focus 5; R2).
- ✅ Consequence routing via roster service only (Focus 6; R6 plumbs
  `entry_id` + `expected_version`).
- ✅ Deterministic calendar cadence windows (Focus 7).
- ✅ CHECK constraints on extraction_status shape (Focus 8).
- ✅ Raw text + attachment_ref preserved across corrections (Focus 9;
  R5 strengthened `diff_json` audit shape).
- ✅ OCR stub raises explicit `OcrProviderNotConfiguredError` → 503
  (Focus 10).
- ✅ Worker tick: root audit context, specific exception handling,
  per-member tx isolation (Focus 11; R2).
- ✅ Service-actor seed uses `@>` AND `<@` + `expires_at` + `revoked_at`
  guards (Focus 12).
- ✅ Consequence auto-application fail-safe default: `auto_apply`
  absence → False (Focus 13; Revision 1 fixed the inverted default).
- ✅ Migration downgrades no-op (Focus 14).
- ✅ `rule_version` snapshot at evaluation time (Focus 15; helper
  internals noted as LOW Observation 2).
- ✅ Operator attribution preserved on manual `/evaluations/run` via
  `originating_actor` (R4; not a focus item but a related concern the
  audit flagged — the authority-escalation shape is legitimate and
  documented).
- ✅ No `probation` roster state — vocabulary is `under_review` (D1).
- ✅ Endpoint subpackage layout mirrors `endpoints/permissions/`.

---

## Summary

| # | Finding | Severity | Status |
|---|---|---|---|
| F1 | `submit_evidence` trusts `chapter_id` from request body | MEDIUM | **CLOSED** (R1) |
| F2 | Per-member isolation missing in worker | MEDIUM | **CLOSED** (R2) |
| F3 | Roster-service call under-specified | MEDIUM | **CLOSED** (R6) |
| Obs 3 (R0) | Consequence dispatch not atomic | LOW→MEDIUM | **CLOSED** (R2+R6 jointly; atomic tx) |
| Obs 1 | `failed → corrected` permits `extracted_fields IS NULL` — COALESCE contract | LOW | Carried — hygiene |
| Obs 2 | `_current_rule_version` helper internals unspecified | LOW | Carried — hookpoints |
| Obs 3 | `compliance_rule.read` on service actor is defensive/unused | LOW | Carried — cosmetic |
| Obs 4 | `asyncio.run` inside sync `trigger_extraction` — pin endpoint as `def` | LOW | Carried — hookpoints |
| Obs 5 | `EvidenceSubmissionCreate.chapter_id` retained as consistency-check field | LOW | New — acceptable |
| Obs 6 | `test_worker_does_not_bypass_roster_service_with_raw_sql` overpromises | LOW | Carried — rename |

**Overall verdict: LOW.** All fifteen focus items PASS. All three Revision 0
MEDIUM findings closed by targeted proposal revisions. Observation 3 from
Revision 0 (non-atomic consequence) closed as a bonus by the atomic
single-transaction per-member pattern. Six LOW observations carried forward
as implementation-phase hygiene; none warrant a further revision cycle.
The proposal is cleared from this gate's perspective.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
