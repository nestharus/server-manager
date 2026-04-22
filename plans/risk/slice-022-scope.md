# SLICE-022 Scope Risk: **LOW**

Rating: **LOW** — every step in the proposal maps to one of WU-039 / WU-040A / WU-040B-correct / WU-040B-extract / WU-041A / WU-041B; no file upload endpoint, no async OCR queue, no trust-signal integration, no Discord surface, no bulk/multi-member consequence path; code footprint stays inside the new `endpoints/compliance/` subpackage, the enumerated compliance services, the compliance infrastructure module, the compliance tasks module, and tightly bounded additive wiring in `scheduler.py` / `tasks/__init__.py` / `api/v1/router.py`; migration chain is linear off `wu_038_permission_intent_expiry` per synthesis D12; the authority permission set is exactly the nine strings enumerated in D11 (seven user-facing + one internal `compliance_evaluation.write` + the reused `roster.transition`); the OCR boundary is a Protocol plus a stub that raises `OcrProviderNotConfiguredError`; the `under_review` consequence routes through `services/roster.py::transition_roster_entry` with no raw `UPDATE roster_entries` anywhere in compliance code. Seven observations are recorded below that are not gate-failing: (1) a SELECT-only `list_active_members_by_chapter` helper added to `repositories/roster.py` outside the ticket's per-WU Code Boundary columns; (2) small additive wiring to `services/scheduler.py`, `tasks/__init__.py`, and `api/v1/router.py`; (3) an extra endpoint file `evaluations_run.py` that keeps the manual-trigger route in its own module under the WU-041A endpoint file; (4) a per-endpoint subpackage `_shared.py` helper module not called out in the ticket; (5) the migration file is named `wu-041a_compliance_evaluations.py` (matching synthesis D12) rather than the ticket's `wu-041a_compliance_review_api.py`; (6) the `compliance-evaluator` service-actor grant is seeded inside the evaluations migration per D11/D12 (this IS an in-scope service actor, not a new one outside scope); (7) SLICE-023 (merged) has already introduced a parallel alembic head at `wu_042_chapter_governance` branching off `wu_022_applications`, so after SLICE-022 lands there will be two alembic heads (`wu_041a_compliance_evaluations` and `wu_042_chapter_governance`) — this is a pre-existing condition introduced by the already-merged SLICE-023 and is not a SLICE-022 scope violation, but PR review should confirm the multi-head state is expected.

## SLICE-022 ACs (ticket)

1. Compliance rule create/update persists cadence, evidence requirements, and consequence policy with optimistic locking on updates.
2. Evidence submission stores the attachment reference before OCR extraction completes and returns pending extraction state.
3. Officer correction updates extracted fields with optimistic locking and preserves the raw attachment and OCR text.
4. Scheduled evaluation is idempotent for the same member/rule/period and routes review or probation consequences through the roster API path.

---

## Findings per focus item

### Focus 1 — Every step maps to WU-039 / WU-040A / WU-040B-correct / WU-040B-extract / WU-041A / WU-041B

**Verdict: PASS.**

| Proposal step | WU |
|---|---|
| §1 AC1 block — migration `wu-039_compliance_rules.py`; `ComplianceRuleCreate/Update/Read`, `DuplicateActiveComplianceRuleError`; `create_rule`/`update_rule`/`list_rules_by_chapter`/`get_rule`; `create_rule`/`update_rule` services; `endpoints/compliance/rules.py`; `test_compliance_rules.py` | WU-039 |
| §1 AC2 WU-040A block — migration `wu-040a_compliance_evidence.py`; `EvidenceSubmissionCreate/Read`; `create_evidence`/`get_evidence`; `submit_evidence`; `endpoints/compliance/evidence.py`; `test_compliance_evidence.py` | WU-040A |
| §1 AC2 WU-040B-extract block — `EvidenceExtractionRead` in `contracts/compliance_extraction.py`; `infrastructure/ocr.py` (`OcrExtractionResult`, `OcrProvider` Protocol, `StubOcrProvider`, `get_ocr_provider`); `services/compliance_extraction.py::trigger_extraction`; `endpoints/compliance/evidence_extract.py`; `test_compliance_ocr_extract.py` | WU-040B-extract |
| §1 AC3 block — `OfficerCorrectionRequest/Read`, `CorrectionNotPermittedStatusError` in `contracts/compliance_corrections.py`; `update_evidence_correction` repo helper; `services/compliance_corrections.py::correct_evidence`; `endpoints/compliance/evidence_correct.py`; `test_compliance_ocr_correct.py` | WU-040B-correct |
| §1 AC4 WU-041A block — migration `wu-041a_compliance_evaluations.py`; `ComplianceEvaluationRead`, `ComplianceEvaluationReviewRequest`, `InvalidEvaluationReviewActionError`; `insert_evaluation_if_absent`/`get_evaluation`/`update_evaluation_review`/`mark_consequence_applied`; `services/compliance_review.py::get_evaluation`/`review_evaluation`; `endpoints/compliance/evaluations.py`; `endpoints/compliance/evaluations_run.py`; `test_compliance_review_api.py` | WU-041A |
| §1 AC4 WU-041B block — `run_scheduled_compliance_evaluations`, `_evaluate_member_rule`, `_compute_period` in `services/compliance.py`; `tasks/compliance.py::compliance_evaluation_worker_tick`; scheduler wiring; `test_compliance_evaluation_worker.py` | WU-041B |

No step in §1–§10 (AC mapping, migration plan, contracts, repository, services, OCR infrastructure, worker, endpoints, constants, tests) falls outside the six WUs. §12 PR decomposition collapses the six WUs into at most three PRs without adding new work.

### Focus 2 — No file upload endpoint (D15)

**Verdict: PASS.**

- §11 item 3: "File upload endpoint / blob storage — `attachment_ref` is opaque."
- `EvidenceSubmissionCreate` (§3) accepts `attachment_ref: str = Field(min_length=1)` as opaque caller-supplied text. No `UploadFile`, `Form`, multipart, or binary-body handling appears in §8. No blob-storage client, bucket setting, or signed-URL helper is introduced.
- `infrastructure/ocr.py` (§6) takes `attachment_ref: str` as input and does not concern itself with acquiring the binary payload — that is deferred to operator-wired providers.
- D4/D5 anchor the opacity: "`attachment_ref` is an opaque URL/path supplied by operator" (synthesis D3); "File upload endpoint — out of scope; attachment_ref is an opaque operator-supplied string" (synthesis D15).

### Focus 3 — No async OCR queue (D5 sync only)

**Verdict: PASS.**

- §11 item 2: "Async extraction queue — synchronous only (D5)."
- `services/compliance_extraction.py::trigger_extraction` (§5) invokes `OcrProvider.extract(...)` synchronously inside the request handler via `asyncio.run(...)`; the HTTP response carries the final row state. No `deferred_effects` row is written, no `scheduled_jobs` entry is added for OCR, and `tasks/compliance.py` is dedicated to the **evaluation** sweep (WU-041B) — not OCR.
- Synthesis D5 binds the shape: "`POST /evidence/{id}/extract` synchronously calls `OcrProvider.extract(...)` and updates the evidence row to `completed` or `failed` inside the request." The proposal honors this verbatim.
- No queue module (e.g., `queues/ocr.py`), no Celery/Arq/Huey dependency, no per-evidence polling endpoint.

### Focus 4 — No trust signal integration (D15)

**Verdict: PASS.**

- §11 item 8: "Trust-signal integration — compliance violations do not generate trust signals this slice."
- No import of `services/trust.py` or `repositories/trust.py` or `contracts/trust.py` in any new compliance module (§3–§7).
- The `under_review` consequence path (§5) calls only `roster.transition_roster_entry(...)`; no sibling call into trust is present.
- Synthesis D15: "Trust-signal integration — compliance violations do NOT auto-generate trust signals in this slice." The proposal's non-goal and guardrail lists both restate this.

### Focus 5 — No Discord interaction in this slice

**Verdict: PASS.**

- Ticket Technical Specification: "Discord interactions: none in this slice; evidence and evaluation surfaces are API- and worker-driven."
- No `services/discord/` path, no `discord.py` import, no `interactions/*.py` module appears in §1–§10.
- No bot command, slash command, button, modal, or thread orchestration is introduced.
- The worker (§7) emits audit rows only; downstream roster transitions already project whatever Discord surface exists for `under_review`, so no direct Discord interaction is required inside this slice.

### Focus 6 — No bulk consequence or multi-member batch

**Verdict: PASS.**

- §11 item 5: "Multi-member / batch consequences — one consequence per evaluation row."
- `_evaluate_member_rule` (§5) writes **one** evaluation per `(member_id, rule_id, period_start, period_end)`; the unique index `ux_compliance_evaluations__member_rule_period` (§2) prevents any other shape. Each evaluation dispatches at most one consequence (`none` / `review_queued` / `under_review_applied`).
- No batch endpoint (e.g., `POST /compliance/evaluations/apply-consequences`) exists; the manual-trigger route `POST /compliance/evaluations/run` invokes the same per-member loop as the worker.
- The review endpoint (`POST /compliance/evaluations/{id}/review`) operates on a single evaluation id.
- Roster dispatch call `transition_roster_entry(...)` is per-member; there is no batch transition wrapper introduced.

### Focus 7 — Code boundaries per ticket touched — migrations, contracts/compliance.py, repositories, services, endpoints/compliance/*, tasks/compliance.py

**Verdict: PASS (with observations).**

Ticket code boundaries expanded across all six WUs:

| File | Status | WU |
|---|---|---|
| `migrations/versions/wu-039_compliance_rules.py` | new (§2) | WU-039 |
| `migrations/versions/wu-040a_compliance_evidence.py` | new (§2) | WU-040A |
| `migrations/versions/wu-041a_compliance_evaluations.py` | new (§2) — ticket names it `wu-041a_compliance_review_api.py`; synthesis D12 names it `wu_041a_compliance_evaluations` (see Observation 5) | WU-041A |
| `services/api/app/contracts/compliance.py` | new (§3) | WU-039/040A/041A |
| `services/api/app/contracts/compliance_corrections.py` | new (§3) | WU-040B-correct |
| `services/api/app/contracts/compliance_extraction.py` | new (§3) | WU-040B-extract |
| `services/api/app/repositories/compliance.py` | new (§4) | WU-039/040A/040B-correct/041A |
| `services/api/app/services/compliance.py` | new (§5) | WU-039/040A/041B |
| `services/api/app/services/compliance_corrections.py` | new (§5) | WU-040B-correct |
| `services/api/app/services/compliance_extraction.py` | new (§5) | WU-040B-extract |
| `services/api/app/services/compliance_review.py` | new (§5) | WU-041A |
| `services/api/app/infrastructure/ocr.py` | new (§6) | WU-040B-extract |
| `services/api/app/tasks/compliance.py` | new (§7) | WU-041B |
| `services/api/app/api/v1/endpoints/compliance/__init__.py` | new subpackage aggregator (§8) | shared |
| `services/api/app/api/v1/endpoints/compliance/_shared.py` | new (§8) — observation 4 | shared |
| `services/api/app/api/v1/endpoints/compliance/rules.py` | new (§8) | WU-039 |
| `services/api/app/api/v1/endpoints/compliance/evidence.py` | new (§8) | WU-040A |
| `services/api/app/api/v1/endpoints/compliance/evidence_correct.py` | new (§8) | WU-040B-correct |
| `services/api/app/api/v1/endpoints/compliance/evidence_extract.py` | new (§8) | WU-040B-extract |
| `services/api/app/api/v1/endpoints/compliance/evaluations.py` | new (§8) | WU-041A |
| `services/api/app/api/v1/endpoints/compliance/evaluations_run.py` | new (§8) — observation 3 | WU-041A |
| `services/api/app/services/scheduler.py` | additive wiring (§7) — observation 2 | WU-041B |
| `services/api/app/tasks/__init__.py` | additive wiring (§7) — observation 2 | WU-041B |
| `services/api/app/api/v1/router.py` | one-line include (§8) — observation 2 | shared |
| `services/api/app/repositories/roster.py` | SELECT-only helper `list_active_members_by_chapter` (§4) — observation 1 | WU-041B |
| `services/api/tests/test_compliance_rules.py` | new (§10) | WU-039 |
| `services/api/tests/test_compliance_evidence.py` | new (§10) | WU-040A |
| `services/api/tests/test_compliance_ocr_correct.py` | new (§10) | WU-040B-correct |
| `services/api/tests/test_compliance_ocr_extract.py` | new (§10) | WU-040B-extract |
| `services/api/tests/test_compliance_review_api.py` | new (§10) | WU-041A |
| `services/api/tests/test_compliance_evaluation_worker.py` | new (§10) | WU-041B |

No `services/api/app/services/trust.py`, no `services/api/app/repositories/roster.py` write path, no `services/api/app/services/roster.py` mutation, no `services/discord/*`, no existing migration is edited. The roster repository's new helper is strictly SELECT-only (§4 "Roster member enumeration" bullet; proposal explicitly states "a single new helper `list_active_members_by_chapter(connection, chapter_id)` is added to `services/api/app/repositories/roster.py` returning `roster_entries` rows where `status = 'active'`").

### Focus 8 — Migration chain linear onto `wu_038_permission_intent_expiry`

**Verdict: PASS (with observation 7).**

- §2: "Chain (D12, linear off `wu_038`): `wu_038_permission_intent_expiry → wu_039_compliance_rules → wu_040a_compliance_evidence → wu_041a_compliance_evaluations`."
- Each proposed `revision` / `down_revision` pair is declared explicitly in §2 and conforms to the shipped naming convention (dashed filename, underscored revision id).
- Each downgrade is `pass` (live-server convention; proposal §2 pins this against `wu-038_permission_intent_expiry.py:76–79`).
- The three-migration chain is linear (no forks introduced by this slice), and `wu_041a_compliance_evaluations` becomes the new chain tip when SLICE-022 merges.

**Observation 7 (non-gating)** — SLICE-023 (already merged) introduced `migrations/versions/wu-042_chapter_governance.py` with `down_revision = "wu_022_applications"`. This is a sibling branch already present in the worktree. After SLICE-022 lands, Alembic will see two heads: `wu_041a_compliance_evaluations` (from this slice, chain-linear off `wu_038`) and `wu_042_chapter_governance` (from SLICE-023, chain off `wu_022`). Synthesis D12 binds SLICE-022's chain to `wu_038`, which the proposal honors — this is not a SLICE-022 scope violation. The alembic multi-head state is a pre-existing condition introduced by the already-merged SLICE-023 and must be reconciled by a separate merge migration (outside this slice's scope). PR review should confirm this state is expected; otherwise synthesis revision is the correct channel, not scope expansion here.

### Focus 9 — Authority permissions limited to the declared set in D11

**Verdict: PASS.**

Synthesis D11 enumerates exactly nine permission strings; the proposal §9 constants table and §1/§5 authority checks match:

| Permission | Kind | Used by |
|---|---|---|
| `compliance_rule.read` | user-facing | read paths (evaluator service-actor grant) |
| `compliance_rule.write` | user-facing | `create_rule`, `update_rule` (§5) |
| `compliance_evidence.submit` | user-facing | `submit_evidence` (§5) |
| `compliance_evidence.correct` | user-facing | `correct_evidence` (§5) |
| `compliance_evidence.extract` | user-facing | `trigger_extraction` (§5) |
| `compliance_evaluation.read` | user-facing | `get_evaluation` (§5) |
| `compliance_evaluation.review` | user-facing | `review_evaluation`, manual run endpoint (§5, §8) |
| `compliance_evaluation.write` | internal substrate | seeded on `compliance-evaluator` (§2); worker uses it via `mutate_entity` for `compliance_evaluation.create` audits |
| `roster.transition` | reused (shipped) | seeded on `compliance-evaluator` for `under_review` dispatch (§5, §7) |

No tenth permission string appears in §9. No wildcard, hierarchy, or per-rule ACL is introduced. No scope_kind beyond the shipped vocabulary (`chapter`, `global`) is invented: `_require_scoped_authority` calls (§5) use `scope_kind="chapter"` throughout, with the evaluator's global grant covering all chapters per SLICE-008 hierarchy (synthesis D11). The four `compliance_evaluation.*` review action paths (approve/override) share `compliance_evaluation.review` — no split into `.approve` vs `.override` (which would be a new permission) is introduced.

### Focus 10 — OCR provider is pluggable stub — no concrete OCR implementation in this slice

**Verdict: PASS.**

- §6 `infrastructure/ocr.py`: defines `OcrExtractionResult` model, `OcrProvider` Protocol, `StubOcrProvider` that raises `OcrProviderNotConfiguredError`, and `get_ocr_provider(settings)` that returns the stub. Inline comment: "Operators wire a concrete provider via settings in a later slice; SLICE-022 ships the stub only (D4, D15)."
- §11 item 1: "Real OCR engine implementation (Google Vision, Gemini, Tesseract, etc.) — pluggable Protocol + stub only."
- `pyproject.toml` / requirements are **not** modified to add Tesseract, PaddleOCR, `google-cloud-vision`, `google-generativeai`, or any cloud-SDK dependency.
- The stub's `OcrProviderNotConfiguredError` is mapped to HTTP 503 by the endpoint layer (§8 status-code mapping "ocr_provider_not_configured"), matching synthesis D5's "501/503 when no provider is configured" binding.
- `services/api/app/core/settings.py` already carries `google_cloud_vision_key` / `gemini_api_key` fields from prior slices (research §1); the proposal does not wire these into any concrete provider class — they remain unused by this slice.

### Focus 11 — Evaluation consequence routes through `transition_roster_entry` only — no direct roster mutation

**Verdict: PASS.**

- §5 `_evaluate_member_rule` step 4: "`consequence_kind='under_review'` AND `result='violation'` … `roster.transition_roster_entry(...)` with `RosterEntryTransitionRequest(to_status="under_review", reason="compliance_violation:{rule_name}", originating_actor_kind="service", originating_actor_id="compliance-evaluator")`."
- §12 Guardrails: "Roster consequences route only through `services/api/app/services/roster.py::transition_roster_entry` (D10). No raw `UPDATE roster_entries` in compliance code."
- Test coverage enforces both the positive route and the absence of a raw-SQL bypass:
  - `test_worker_routes_under_review_consequence_through_roster_service` (§10)
  - `test_worker_does_not_bypass_roster_service_with_raw_sql` (§10)
- The `review` consequence kind records `consequence_applied='review_queued'` and does **not** invoke any roster API — also correct per D1 (review → no automatic roster change until officer review).
- Idempotency: when the roster service raises `InvalidRosterStatusTransitionError` (member already `under_review`/`removed`), the evaluation row records `consequence_applied='none'` and the loop continues — no silent swallowing, no re-raised direct mutation attempt.
- No `UPDATE roster_entries`, no `INSERT INTO roster_transitions`, no direct import of `repositories/roster.py` mutation helpers appears anywhere in §4 / §5.

### Focus 12 — Parallelizable with SLICE-023 per ticket (but SLICE-023 already merged)

**Verdict: PASS.**

SLICE-023 shipped as `wu-042_chapter_governance` (chapter governance feature). File-collision surface check:

- Migrations: SLICE-022 adds `wu-039/wu-040a/wu-041a`; SLICE-023 added `wu-042`. No filename collision. Alembic multi-head is the only cross-slice state (see Observation 7).
- Contracts: SLICE-022 adds `contracts/compliance.py`, `contracts/compliance_corrections.py`, `contracts/compliance_extraction.py`. SLICE-023 shipped `contracts/chapter_governance.py` (disjoint module name). No overlap.
- Services: SLICE-022 adds `services/compliance.py`, `services/compliance_corrections.py`, `services/compliance_extraction.py`, `services/compliance_review.py`. SLICE-023 shipped `services/chapter_governance.py`. No overlap.
- Repositories: SLICE-022 adds `repositories/compliance.py` (new) and extends `repositories/roster.py` with one SELECT-only helper. SLICE-023 added its own repository module. No overlap on the one shared file (`repositories/roster.py`) — SLICE-023 did not modify the roster repository; SLICE-022's helper lands cleanly.
- Endpoints: SLICE-022 adds the new `endpoints/compliance/` subpackage. SLICE-023 shipped its own endpoint module. No overlap. The shared `api/v1/router.py` is touched by a single include line (§8), additive-only.
- Scheduler: SLICE-022 adds a new `_run_compliance_evaluation_if_due` method and a `COMPLIANCE_EVALUATION_INTERVAL_SECONDS` constant to `services/scheduler.py`. If SLICE-023 also touched scheduler wiring, the seam is additive — each slice adds its own interval constant + dispatch branch. No overlap of method names, constants, or dispatch slots.
- Tasks: SLICE-022 adds `tasks/compliance.py` and one `configure_compliance` call inside `tasks/__init__.py::configure_task_runtime`. Same additive pattern as SLICE-023 if it shipped a task module.

No shipped SLICE-023 file is rewritten by this proposal. The one shared shipping-time concern is the alembic multi-head (Observation 7), which is outside SLICE-022's scope control.

---

## Observations (non-gating)

1. **`list_active_members_by_chapter` in `repositories/roster.py`** — §4 "Roster member enumeration" adds a single SELECT-only helper to an existing repository that is not enumerated in the ticket's per-WU Code Boundary column. The helper is required by synthesis D8 ("Enumerate chapter members in scope") and by D10 (no direct roster mutation → compliance must enumerate members from roster read path). SELECT-only, no writes, no transaction shape change. Parallel to the SLICE-024 scope treatment of cross-repository helpers (observation 2 in `slice-024-scope.md`). Not a gate fail.

2. **Additive wiring in `services/scheduler.py`, `tasks/__init__.py`, `api/v1/router.py`** — §7 and §8 add a new interval constant + dispatch method in scheduler, a single `configure_compliance(db=db)` call in `tasks/__init__.py::configure_task_runtime`, and a one-line `router.include_router(compliance.router, prefix="/compliance")` in `api/v1/router.py`. These are the minimum wiring surfaces required to expose the worker and endpoints at runtime and mirror the SLICE-020 permission-expiry wiring (research §5). They are not in the ticket's per-WU Code Boundary column but are load-bearing for "the slice ships a running worker" per AC4 and "the slice ships reachable HTTP endpoints" per the ticket Technical Specification. Not a gate fail.

3. **`evaluations_run.py` as a separate endpoint module** — §8 places the manual-trigger route `POST /api/v1/compliance/evaluations/run` in its own file rather than adding it to `evaluations.py`. The ticket's Code Boundary lists only `endpoints/compliance/evaluations.py` for WU-041A; the additional file is a packaging choice to isolate the manual-run route (which has different handling from the per-id review/get routes). Both files are still within the `endpoints/compliance/` subpackage the ticket authorizes. Not a gate fail.

4. **`endpoints/compliance/_shared.py` helper module** — §8 adds a shared helpers module adapted from `endpoints/permissions/_shared.py`, carrying `get_db`, `parse_if_match_strong`, `set_etag`, `raise_known_compliance_error`. The ticket's Code Boundary does not list `_shared.py` explicitly. The file is a DRY helper for the six sibling endpoint modules within the same subpackage and mirrors the existing `endpoints/permissions/_shared.py` / `endpoints/trust/_shared.py` pattern. Adding it without the helper would duplicate exception-mapping logic across six files. Not a gate fail.

5. **Migration filename `wu-041a_compliance_evaluations.py` vs ticket's `wu-041a_compliance_review_api.py`** — Proposal §2 names the third migration `wu-041a_compliance_evaluations.py` (revision id `wu_041a_compliance_evaluations`). The ticket's WU-041A Code Boundary column names it `wu-041a_compliance_review_api.py`. Synthesis D12 binds the revision id to `wu_041a_compliance_evaluations` (matches the proposal). The ticket and synthesis disagree on the filename; the proposal follows synthesis. Since the migration creates the `compliance_evaluations` table (not a "review API"), the proposal's filename more accurately describes the migration's payload. Synthesis D12's binding takes precedence over the ticket's informal code-boundary filename. Not a gate fail; noting so the PR reviewer matches the filename to synthesis rather than the ticket.

6. **`compliance-evaluator` service-actor grant seeded in `wu-041a`** — Synthesis D11 requires the service actor with three grants (`compliance_rule.read`, `compliance_evaluation.write`, `roster.transition`). Synthesis D12 requires those grants to be seeded in the evaluations migration. Proposal §2 seeds them inline in `wu-041a_compliance_evaluations.py` with an idempotent `INSERT ... WHERE NOT EXISTS` that matches the shipped pattern in `wu-038_permission_intent_expiry.py:36–73`. This IS a service-actor addition — and it is explicitly in scope per D11/D12 (the binding enumerates this specific actor by name). It is not a scope violation; recording explicitly because "no new service actor" is a phrase readers sometimes expect at compliance-adjacent slices, and this slice genuinely adds one under synthesis authorization.

7. **Alembic multi-head state after merge** — See Focus 8 above. Pre-existing condition from already-merged SLICE-023 (`wu_042_chapter_governance` branches off `wu_022_applications` rather than chain-linearly off the tip). SLICE-022's `wu_041a` chain stays linear off `wu_038` per synthesis D12. Post-merge state: two heads (`wu_041a_compliance_evaluations`, `wu_042_chapter_governance`). Reconciliation via a merge migration is outside this slice's scope.

---

## Summary

| Focus | Verdict |
|---|---|
| 1. Every step maps to the six WUs | PASS |
| 2. No file upload endpoint (D15) | PASS |
| 3. No async OCR queue (D5 sync only) | PASS |
| 4. No trust signal integration (D15) | PASS |
| 5. No Discord interaction in this slice | PASS |
| 6. No bulk consequence or multi-member batch | PASS |
| 7. Code boundaries per ticket touched | PASS |
| 8. Migration chain linear onto `wu_038_permission_intent_expiry` | PASS |
| 9. Authority permissions limited to D11's declared set | PASS |
| 10. OCR provider is pluggable stub — no concrete OCR implementation | PASS |
| 11. Evaluation consequence routes through `transition_roster_entry` only | PASS |
| 12. Parallelizable with SLICE-023 (merged) — no file collision | PASS |

**Scope risk: LOW.** Proposal is shippable as-is from a scope perspective. Observations 1–7 are recorded so they surface at PR-review time; none warrant a synthesis revision.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
