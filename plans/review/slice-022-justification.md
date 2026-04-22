# SLICE-022 Phase 8 — Opus Justification Review

Reviewed: 2026-04-22
Branch: `feat/slice-022-compliance`
Branch head: `59202d4` (against `origin/main` = `e5f4ec0`)
Inputs: `git diff origin/main...feat/slice-022-compliance` (41 files, +7858/-2319),
`.pipeline/synthesis.md` (D1–D15), `.pipeline/proposal.md` (Revisions R1+R2),
`plans/risk/slice-022-{audit,scope,shortcut}.md`, `AGENTS.md`.

## 1. Verdict

**`LOW_CONCERN`** — every focus item passes against the actual implementation;
the audit/scope/shortcut MEDIUM findings (M1–M5, F1–F3) are visibly closed in
the merged code, not just in the proposal text. Three LOW observations carry
forward as hygiene notes; none gate merge.

The implementation deviates from the proposal's *naming convention* for audit
constants in two visible ways (dict-of-strings instead of `*_ACTION_TYPE`
module constants; and a simplified `reason="compliance_violation"` instead of
the proposed `f"compliance_violation:{rule['name']}"`). Both deviations are
neutral or improvements: the dict-of-strings keeps the constants-only-dispatch
guarantee (the values are fixed at module load, not interpolated from request
data); the bare reason string drops a redundant interpolation since `rule_id`
already lives in the action payload.

## 2. Focus walk-through (12 items)

### F1 — Atomic per-member tx (R2 + R6 + R7)  → PASS

`services/api/app/services/compliance.py:650-728` opens
`with db.transaction() as connection` and runs three operations on the *same*
connection inside one Postgres transaction:

1. `_insert_evaluation_row(connection, ...)` — `INSERT ... ON CONFLICT DO
   NOTHING RETURNING ...`. Returns None on conflict, in which case the function
   returns early *inside* the transaction, which then commits as a clean no-op
   (no audit row written).
2. (conditional) `roster_service.transition_roster_entry(db, ..., connection=connection)`
   — passes the shared connection through R7's new kwarg.
3. `mutate_entity(db=db, connection=connection, ...)` — writes the
   `compliance_evaluation.create` audit row with the `evaluation_created` state
   change on the same connection.

If the roster transition raises `StaleMutationError` or
`InvalidRosterStatusTransitionError`, the entire `db.transaction()` block
unwinds — evaluation insert + audit projection roll back together. The next
tick's `ON CONFLICT DO NOTHING` insert succeeds cleanly because the prior
attempt left no rows. Matches audit M1+M5 closure verbatim.

### F2 — Roster connection extension (R7)  → PASS

`services/api/app/services/roster.py:177-188` adds
`get_roster_entry(..., connection: Connection[Any] | None = None)`; lines
191-298 add the same kwarg to `transition_roster_entry`. When `connection` is
None, both fall back to opening a pool connection (preserving every existing
caller); when provided, they reuse the caller's connection and pass it through
to `mutate_entity(connection=connection, ...)` at line 277. Test
`test_transition_roster_entry_accepts_shared_connection`
(`services/api/tests/test_roster.py:558`) pins the shared-connection behavior.
Append-only signature change — no shipped roster caller breaks.

### F3 — Chapter from rule, not request (R1)  → PASS

`services/api/app/services/compliance.py:481-504`:

```python
with db.connection() as connection:
    rule_row = compliance_repo.get_rule(connection, request.rule_id)
if rule_row is None:
    raise ComplianceRuleNotFoundError(request.rule_id)            # → 404
if request.chapter_id != rule_row["chapter_id"]:
    raise EvidenceChapterMismatchError(...)                       # → 422
_require_scoped_authority(
    "compliance_evidence.submit",
    scope_kind="chapter",
    scope_id=rule_row["chapter_id"],                              # ← from rule
    actor=actor, db=db,
)
```

Persistence at line 516 hardcodes
`"chapter_id": rule_row["chapter_id"]` — the request-body `chapter_id` cannot
land in the row. `EvidenceChapterMismatchError` is mapped to 422 with the
`evidence_chapter_mismatch` code at `_shared.py:128-138`. Matches audit R1.

### F4 — Operator attribution on manual trigger (R4)  → PASS

The manual-trigger endpoint at
`services/api/app/api/v1/endpoints/compliance/evaluations_run.py:32-38` calls
`run_scheduled_compliance_evaluations(..., actor=compliance_evaluator_actor(),
originating_actor=actor, source="manual_trigger")`. The service then sets
`effective_originating_actor = actor if originating_actor is None else
originating_actor` (`compliance.py:746`), so the worker path uses the service
actor as both `actor` and `originating_actor`, while the manual-trigger path
uses the service actor as `actor` (so the audit row attributes to
`compliance-evaluator`) and the human operator as `originating_actor` (which
threads into the `RosterEntryTransitionRequest.originating_actor_kind/id` at
`compliance.py:678-679`). Test
`test_manual_run_preserves_operator_attribution_on_roster_transition`
(`test_compliance_evaluation_worker.py:179`) pins the round-trip.

### F5 — diff_json for corrections (R5)  → PASS

`services/api/app/services/compliance_corrections.py:109-122` constructs a
unified `payload` dict containing:

- `from.extracted_fields_corrected` — the prior overlay (None on first
  correction)
- `to.extracted_fields_corrected` — the new overlay
- `baseline.extracted_fields` — the immutable OCR baseline
- `evidence_id`, `corrected_by_member_id`, `correction_reason`

The dict is written into *both* `payload_json` and `diff_json` of the
`StateChangeDraft`. A second correction is therefore self-describing without
replay (the audit row carries `from = prior overlay`, `to = new overlay`,
`baseline = immutable OCR`). The repository update at
`compliance.py:295-322` only touches the four overlay columns
(`extracted_fields_corrected`, `extraction_status`, `corrected_by_member_id`,
`corrected_at`, `correction_reason`) — `raw_text` and `extracted_fields` are
never re-written, preserved by the
`evidence_submissions_corrected_requires_overlay` CHECK at
`migrations/versions/wu-040a_compliance_evidence.py:74-77`.

Note: the `diff_json` shape (`{from, to, baseline}`) is structurally
equivalent to the audit's expected shape (`{old, new, baseline}`); only the
key names differ. Not a blocker — the auditor's intent (single self-describing
state change row) is met.

### F6 — Consequence in CREATE, not separate action (R3)  → PASS

`compliance.py:686-728` issues exactly one `mutate_entity` per member-rule-
period — the `compliance_evaluation.create` action with the
`evaluation_created` state change. The roster transition at lines 666-684 is
*nested inside the same `db.transaction()` block but is not a separate
`mutate_entity` on the evaluation aggregate*; it produces its own
`roster_entry.transition` audit row on the roster aggregate via the standard
`transition_roster_entry` path. There is no `mark_consequence_applied` helper,
no `compliance_evaluation.consequence` action_type, no orphan change_type
constant. An auditor querying by `correlation_id` (tick-scoped per the worker's
root audit context) sees both rows linked. R3 closure verified.

### F7 — OCR provider stubbed (D4)  → PASS

`services/api/app/infrastructure/ocr.py`:

- `OcrExtractionResult` (Pydantic, `extra="forbid"`)
- `OcrProvider` Protocol with one async `extract(...)` method
- `OcrProviderNotConfiguredError`
- `StubOcrProvider.extract(...)` raises `OcrProviderNotConfiguredError`
  unconditionally — no quiet `pass`, no `return None`, no fixture data

`_shared.py:33-38` resolves `app.state.ocr_provider`, defaulting to
`StubOcrProvider()` when unset. `_shared.py:154-158` maps the error to HTTP
503 with `{"code": "ocr_provider_not_configured"}`. `pyproject.toml` /
requirements are not modified — no Tesseract, Vision, or Gemini dependency
added.

### F8 — Constants dispatch  → PASS (with deviation note)

Every `mutate_entity` call uses dict lookup against module-level dicts:
`AUDIT_ACTION_TYPE["rule_create"]`, `AUDIT_CHANGE_TYPE["evaluation_created"]`,
etc. across `compliance.py`, `compliance_corrections.py`,
`compliance_extraction.py`, and `compliance_review.py`. There is **zero**
runtime f-string interpolation against request data anywhere in the dispatch
path (verified with `Grep "f\".*action_type|f\".*change_type"` → 0 matches).

**Deviation:** the proposal/audit named per-action module constants
(`COMPLIANCE_RULE_CREATE_ACTION_TYPE`, `COMPLIANCE_EVALUATION_OVERRIDE_PAYLOAD_ALLOWLIST`,
etc.); the implementation uses dict-of-strings keyed by short identifier.
Functionally equivalent — both forms guarantee the dispatched value is
literal-at-module-load — but the hygiene shape differs from D13's "module-
level string constant" example. The payload allowlists *are* `frozenset`s at
module level (`compliance.py:55-101`, `compliance_corrections.py:30-36`,
`compliance_extraction.py:25-32`, `compliance_review.py:38-51`), matching the
proposal exactly. The override path correctly pairs
`AUDIT_ACTION_TYPE["override"]` with `COMPLIANCE_EVALUATION_OVERRIDE_PAYLOAD_ALLOWLIST`
(R8 closure).

The only f-string in the dispatch neighborhood is
`request_surface=f"api:/api/v1/compliance/evidence/{evidence_id}/correct"`
and similar — these are URL paths, not vocabulary, and follow shipped
precedent (e.g., `services/roster.py:283`).

### F9 — Worker root audit context (SLICE-020 R2 precedent)  → PASS

`services/api/app/tasks/compliance.py:50-71` mirrors
`services/api/app/tasks/permission_expiry.py` point-for-point:

```python
existing_ctx = get_current_audit_context()
ambient = (
    use_audit_context(_root_audit_context())
    if existing_ctx is None
    else nullcontext()
)
with ambient:
    try:
        return run_scheduled_compliance_evaluations(...)
    except StaleMutationError:
        logger.debug(...)
        return None
    except OcrProviderNotConfiguredError:
        logger.warning(...)
        return None
    except Exception:
        logger.exception(...)
        return None
```

`_root_audit_context()` builds an `AuditContextRead` with a fresh
`uuid4()` correlation id, no causation. Per-member isolation is layered at
the service: `run_scheduled_compliance_evaluations` (`compliance.py:751-802`)
runs separate try/except blocks per rule (setup) and per member, with
`StaleMutationError`/`InvalidRosterStatusTransitionError`/`Exception` caught
at the per-member level so one failure does not abort the batch. Test
`test_worker_installs_root_audit_context`
(`test_compliance_evaluation_worker.py:163`) pins the precedent.

### F10 — Service-layer authority  → PASS

Every mutating service function calls `_require_scoped_authority(...)` at the
top, before any DML:

- `create_rule` — `compliance.py:300-306`
- `update_rule` — fetches row first (to resolve scope), then authorizes
  against `current.chapter_id` (lines 381-387)
- `submit_evidence` — fetches rule first (to resolve scope from rule, not
  request), then authorizes against `rule_row["chapter_id"]` (R1 pattern,
  lines 498-504)
- `correct_evidence` — `compliance_corrections.py:68-74`
- `trigger_extraction` — `compliance_extraction.py:63-69`
- `get_rule_read` / `list_rules` / `get_evidence_submission` —
  `compliance.py:448-477, 574-580`
- `get_evaluation` / `review_evaluation` — `compliance_review.py:80-86, 115-121`
- Manual trigger endpoint — `evaluations_run.py:25-31` (uses `require_scoped`
  from `_shared.py` because the dispatch surface is the endpoint, not the
  per-member service)

Worker paths rely on the `compliance-evaluator` service-actor grant (seeded
in `wu-041a_compliance_evaluations.py:95-132` with `@>` AND `<@` containment
guards + `revoked_at` + `expires_at` checks, mirroring
`wu-038_permission_intent_expiry.py`).

### F11 — UNIQUE (member, rule, period) idempotency  → PASS

- Migration `wu-041a_compliance_evaluations.py:76-81` declares
  `ux_compliance_evaluations__member_rule_period` as
  `UNIQUE (member_id, rule_id, period_start, period_end)`.
- Repository `insert_evaluation_if_absent`
  (`repositories/compliance.py:368-415`) uses
  `INSERT ... ON CONFLICT (member_id, rule_id, period_start, period_end) DO
  NOTHING RETURNING ...` and returns the `dict_row` or None.
- Service `_evaluate_member_rule` (`compliance.py:651-664`) returns None when
  the insert returns None. The surrounding `db.transaction()` then commits a
  clean no-op — no audit row, no roster transition, no aggregate_heads
  advance. Replay on a fully-processed period writes zero rows across
  `compliance_evaluations`, `aggregate_heads`, `activity_actions`, and
  `activity_state_changes`. Test
  `test_worker_is_idempotent_on_repeat_tick`
  (`test_compliance_evaluation_worker.py:88`) pins this.

### F12 — Migration chain linear  → PASS (with multi-head note)

`migrations/versions/wu-039_compliance_rules.py:11` →
`down_revision = "wu_038_permission_intent_expiry"`.
`wu-040a_compliance_evidence.py:11` → `down_revision = "wu_039_compliance_rules"`.
`wu-041a_compliance_evaluations.py:11` → `down_revision = "wu_040a_compliance_evidence"`.
Each downgrade is `pass` per the Live Server Principle.

The chain is linear off `wu_038`, exactly as bound by synthesis D12. Note: a
sibling `wu_042_chapter_governance` shipped in SLICE-023 branches off
`wu_022_applications`, so post-merge alembic will see two heads
(`wu_041a_compliance_evaluations`, `wu_042_chapter_governance`). This is a
pre-existing condition introduced by the already-merged SLICE-023, not a
SLICE-022 violation; reconciliation by a merge migration is outside this
slice's scope.

## 3. Findings

| # | Severity | File:Line | Description | Recommendation |
|---|---|---|---|---|
| F1 | LOW | `services/api/app/services/compliance.py:642-647` | `_evaluate_member_rule` silently downgrades `consequence_applied` from `under_review_applied` to `none` (with `review_status="not_required"`) when `member["status"] not in {"active", "on_leave"}`. This pre-empts `InvalidRosterStatusTransitionError` from `transition_roster_entry`, but the persisted evaluation row records `consequence_applied="none"` rather than something like `consequence_applied="skipped_member_not_eligible"` — auditors querying for "members the worker tried to transition but couldn't" will not find them. The `roster_entries` table doesn't carry a transition-attempt counter either, so the only signal is the `result="violation"` evaluation row with `consequence_applied="none"`. | Hygiene only. Either (a) introduce a `consequence_applied="skipped_ineligible"` enum value (would require migration to widen the CHECK at `wu-041a_compliance_evaluations.py:59-62`), or (b) document that `(result="violation", consequence_applied="none", review_status="not_required")` means "member ineligible for transition" so dashboards can filter for it. Not merge-blocking. |
| F2 | LOW | `services/api/app/services/compliance.py:42-53` and three sibling services | The implementation uses dict-of-strings (`AUDIT_ACTION_TYPE["rule_create"]`) instead of named module constants (`COMPLIANCE_RULE_CREATE_ACTION_TYPE`) for audit vocabulary. Functionally equivalent (no runtime interpolation of request data), but the proposal/audit explicitly named the per-action module-constant shape per D13. The dict-of-strings collapses naming + grouping into the dict, which makes `grep -n COMPLIANCE_RULE_CREATE_ACTION_TYPE` return zero hits across the repo — a cross-reference convenience the named constants would have provided. | Hygiene only. Either (a) refactor to named module constants matching the audit's expectation, or (b) document the dict shape as the chosen convention in `services/api/app/services/compliance.py` module docstring so future slices follow suit. Not merge-blocking — the constants-only-dispatch guarantee (no f-strings interpolating request data) is intact. |
| F3 | LOW | `services/api/app/services/compliance_corrections.py:109-122` | `diff_json` shape uses `{from, to, baseline}` instead of the audit's expected `{old, new, baseline}` keys. Both shapes are self-describing and equivalent; the discrepancy will only matter if a downstream query/dashboard hardcodes one or the other. | Hygiene only. Pin the chosen shape in a module comment, or align with the SLICE-014/018 `{old, new}` convention used by `services/roster.py:269-272`. Not merge-blocking. |

No MEDIUM or HIGH findings.

## 4. Closure of prior risk-gate findings

| Prior finding | Source | Closed in code at |
|---|---|---|
| **M1 / F2** — per-member isolation | audit, shortcut | `compliance.py:773-798` (per-member try/except with `StaleMutationError → debug`, `InvalidRosterStatusTransitionError → debug`, `Exception → exception`, `continue`) |
| **M5 / F3** — roster `connection=` kwarg | audit, shortcut | `services/roster.py:181, 198` (kwarg added to both helpers, threaded into `mutate_entity` at line 277); test at `tests/test_roster.py:558` |
| **F1 (shortcut)** — `submit_evidence` chapter spoof | shortcut | `compliance.py:487-504` (rule fetched first, mismatch → 422 before authorize, scope from rule) |
| **R2** — atomic per-member tx | audit | `compliance.py:650-728` (`db.transaction()` wraps insert + roster + audit) |
| **R3** — orphan consequence audit | audit | only one `mutate_entity` per evaluation; roster call produces its own `roster_entry.transition` row on the roster aggregate, not a second compliance action |
| **R4** — operator attribution | audit | `evaluations_run.py:36`, `compliance.py:746,782` |
| **R5** — second-correction diff | audit | `compliance_corrections.py:109-122` (`{from, to, baseline}` in both `payload_json` and `diff_json`) |
| **R7** — roster signature extension | audit | `services/roster.py:181, 198` (append-only kwarg, default None preserves every existing caller) |
| **R8** — override allowlist | audit | `compliance_review.py:45-51` (`COMPLIANCE_EVALUATION_OVERRIDE_PAYLOAD_ALLOWLIST` paired with `AUDIT_ACTION_TYPE["override"]` at line 159) |
| **L1 (audit, accepted)** — 503 OCR path emits no audit row | audit | `compliance_extraction.py:81-82` (`except OcrProviderNotConfiguredError: raise` — accepted as documented; authority check ahead of provider call still 403s unauthorized probes) |

## 5. Trace matrix (summary)

| File | Justification |
|---|---|
| `migrations/versions/wu-039_compliance_rules.py` | AC1 (rule registry); D2 (flat + JSONB); D12 (chain). |
| `migrations/versions/wu-040a_compliance_evidence.py` | AC2 (evidence intake); D3 (immutable OCR + overlay); D6 (correction OCC). CHECK constraints implement D3 column shape. |
| `migrations/versions/wu-041a_compliance_evaluations.py` | AC4 (idempotent eval + roster routing); D7 (rule_version + consequence lineage); D11 (`compliance-evaluator` global grant); D12 (chain tip). |
| `services/api/app/contracts/compliance.py` | AC1/AC2/AC4 contract surface; D2/D3/D7. `_ComplianceModel` declares `extra="forbid"` (R1 spoof-proofing for `EvidenceSubmissionCreate`). |
| `services/api/app/contracts/compliance_corrections.py` | AC3 contract surface; D6. |
| `services/api/app/contracts/compliance_extraction.py` | D5 (sync extraction shape). |
| `services/api/app/repositories/compliance.py` | DML for all four AC paths; `insert_evaluation_if_absent` implements idempotency (D7+AC4); `list_current_roster_members_by_chapter` is a SELECT-only roster read for D8 enumeration. |
| `services/api/app/services/compliance.py` | AC1/AC2/AC4; R1 (chapter from rule); R2 (atomic per-member tx); R4 (originating_actor); R7 (shared connection). `_compute_period` implements D9. `_compute_consequence_shape` implements D1 + D7's fail-safe `auto_apply` default. |
| `services/api/app/services/compliance_corrections.py` | AC3; D6; R5 (diff_json chain). |
| `services/api/app/services/compliance_extraction.py` | D4/D5; sync `asyncio.run` of OCR. L1 (503 short-circuit) is documented and accepted. |
| `services/api/app/services/compliance_review.py` | AC4 review/override; D7; R8 (override allowlist). Override path also routes its conditional roster transition through `transition_roster_entry` (D10). |
| `services/api/app/services/roster.py` | R7 (`connection=` kwarg on `get_roster_entry` + `transition_roster_entry`). Append-only. |
| `services/api/app/services/scheduler.py` | D8 wiring: `COMPLIANCE_EVALUATION_INTERVAL_SECONDS` + `_run_compliance_evaluation_if_due` (mirrors permission-expiry pattern). |
| `services/api/app/tasks/compliance.py` | D8 worker tick; SLICE-020 R2 audit-context pattern. |
| `services/api/app/tasks/__init__.py` | Wires `configure_compliance_worker` into `configure_task_runtime`. |
| `services/api/app/infrastructure/ocr.py` | D4 (Protocol + stub raising explicit error). |
| `services/api/app/api/v1/endpoints/compliance/*.py` | AC1/AC2/AC3/AC4 HTTP surface; subpackage layout mirrors `endpoints/permissions/`. `_shared.py` is a DRY helper for the six sibling routers. `evaluations_run.py` houses the manual-trigger route in its own module (R4 attribution flows through `originating_actor=actor`). |
| `services/api/app/api/v1/router.py` | One-line `include_router(compliance.router, prefix="/compliance")`. |
| `services/api/app/core/factory.py` | Wires the OCR provider/state into the FastAPI app. |
| Tests | 7 new test files + 1 added test in `test_roster.py`; each pins a specific AC or revision item. |

## 6. Out-of-scope verification (D15)

- ✅ No file upload endpoint — `attachment_ref: str = Field(min_length=1)` is opaque caller-supplied text. No multipart/`UploadFile`/blob client.
- ✅ No async OCR queue — `trigger_extraction` invokes `asyncio.run(...)` synchronously inside the request handler; no `deferred_effects` row, no scheduled job, no separate worker.
- ✅ No trust-signal integration — no import of `services/trust.py`, `repositories/trust.py`, or `contracts/trust.py` in any new compliance module.
- ✅ No Discord interaction — no `services/discord/`, no slash command, no interaction handler.
- ✅ No bulk consequence path — `_evaluate_member_rule` writes one evaluation per `(member, rule, period)`; UNIQUE index prevents any other shape.
- ✅ No real OCR engine — `pyproject.toml` unchanged; only `StubOcrProvider` ships.
- ✅ No raw `UPDATE roster_entries` in compliance code — all consequence routing goes through `services/roster.py::transition_roster_entry` (verified by `Grep "UPDATE roster_entries"` returning zero hits in compliance modules).
- ✅ No new permission strings beyond D11's nine — verified against the seed at `wu-041a_compliance_evaluations.py:16-18`.

## 7. Summary

| Focus | Verdict |
|---|---|
| 1. Atomic per-member tx (R2+R6+R7) | PASS |
| 2. Roster connection extension (R7) | PASS |
| 3. Chapter from rule, not request (R1) | PASS |
| 4. Operator attribution on manual trigger (R4) | PASS |
| 5. diff_json for corrections (R5) | PASS (key naming differs: `{from,to,baseline}` vs `{old,new,baseline}`) |
| 6. Consequence in CREATE, not separate action (R3) | PASS |
| 7. OCR provider stubbed (D4) | PASS |
| 8. Constants dispatch | PASS (dict-of-strings instead of named module constants — equivalent guarantee) |
| 9. Worker root audit context (SLICE-020 R2) | PASS |
| 10. Service-layer authority | PASS |
| 11. UNIQUE (member, rule, period) idempotency | PASS |
| 12. Migration chain linear | PASS |

**Overall: `LOW_CONCERN`.** No MEDIUM or HIGH findings. Three LOW hygiene
items (F1 silent ineligibility downgrade, F2 dict-vs-constants naming, F3
diff_json key naming) noted for follow-up but do not gate merge. The
implementation matches the proposal's Revision 2 shape across every focus
item; M1–M5 / F1–F3 closures from the prior risk gates are visible in the
merged code.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
