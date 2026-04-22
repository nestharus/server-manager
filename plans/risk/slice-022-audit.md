# SLICE-022 Audit Risk Assessment — Revision 2 Re-Audit

**Severity: LOW**

Re-audit of `.pipeline/proposal.md` Revision 2 against the ten-point
audit focus list. Revision 2 closes both open items from the prior
audit pass: R7 adds the explicit roster-service signature extension
documentation (`transition_roster_entry` + `get_roster_entry` gain an
optional `connection=None` kwarg, with SLICE-020 R1 pattern precedent
and a pinned test in `test_roster.py`), closing the M5 atomicity gap;
R8 introduces a dedicated `COMPLIANCE_EVALUATION_OVERRIDE_PAYLOAD_ALLOWLIST`
so review and override dispatches pair constants-to-allowlists
one-for-one, closing the L2 hygiene gap. R1–R6 remain verified from
Revision 1. Only L1 (503 OCR-not-configured path is audit-silent)
remains, explicitly accepted in the Revision Log.

All ten focus items pass. The proposal is structurally complete and
internally consistent; every mutation threads through `mutate_entity`
with a named payload allowlist; dispatch vocabulary is constants-only;
actor identities are derived from the authenticated `ActorIdentity`
and never from the request body; worker installs root audit context
mirroring SLICE-020 R2; consequence routing threads correlation_id
across `compliance_evaluation.create` and `roster_entry.transition`;
the idempotency insert is atomic with the audit projection AND the
roster transition via shared-connection `mutate_entity`; terminal-
state replay is a clean no-op; and correction preserves OCR baseline
plus captures full correction lineage in `diff_json`.

Verdict: **LOW**. No revision required. Implementation may proceed.

---

## Focus Walk-Through (Revision 2)

| # | Focus | Verdict | Primary evidence |
|---|-------|---------|------------------|
| 1 | Every mutation via `mutate_entity` with explicit `payload_allowlist`. | PASS | Every service function in §5 routes through `mutate_entity` with a named allowlist constant: `create_rule` (proposal.md:901-914, `payload_allowlist=set(COMPLIANCE_RULE_CREATE_PAYLOAD_ALLOWLIST)`), `update_rule` (proposal.md:918-925, COMPLIANCE_RULE_UPDATE_*), `submit_evidence` (proposal.md:928-955, EVIDENCE_SUBMIT_PAYLOAD_ALLOWLIST at proposal.md:500-503), `correct_evidence` (proposal.md:1024-1044, `payload_allowlist=set(EVIDENCE_CORRECT_PAYLOAD_ALLOWLIST)`), `trigger_extraction` through `_persist_extraction_success`/`_persist_extraction_failure` emitting `EVIDENCE_EXTRACT_ACTION_TYPE` + success/failed change types (proposal.md:1093-1097), `_evaluate_member_rule` emitting `COMPLIANCE_EVALUATION_CREATE_*` with `COMPLIANCE_EVALUATION_CREATE_PAYLOAD_ALLOWLIST` (proposal.md:1348-1375), `review_evaluation` emitting `COMPLIANCE_EVALUATION_REVIEW_*` with the review allowlist or `COMPLIANCE_EVALUATION_OVERRIDE_*` with the dedicated override allowlist selected per `request.action` (proposal.md:1129-1135; R8). No mutation bypasses `mutate_entity`. |
| 2 | Narrow allowlists — field-specific, no wildcards. | PASS | Eight `frozenset` literals of plain field names at proposal.md:490-525: `COMPLIANCE_RULE_CREATE_PAYLOAD_ALLOWLIST` (8 keys), `COMPLIANCE_RULE_UPDATE_PAYLOAD_ALLOWLIST` (8 keys including `active`), `EVIDENCE_SUBMIT_PAYLOAD_ALLOWLIST` (5 keys incl. derived `submitted_by_member_id`), `EVIDENCE_EXTRACT_PAYLOAD_ALLOWLIST` (4 keys using `raw_text_present` boolean flag instead of raw text), `EVIDENCE_CORRECT_PAYLOAD_ALLOWLIST` (3 keys — see Observation A), `COMPLIANCE_EVALUATION_CREATE_PAYLOAD_ALLOWLIST` (9 keys), `COMPLIANCE_EVALUATION_REVIEW_PAYLOAD_ALLOWLIST` (3 keys), `COMPLIANCE_EVALUATION_OVERRIDE_PAYLOAD_ALLOWLIST` (3 keys — R8, new). All `frozenset({...})` literals of explicit identifiers; no `set(request.model_dump().keys())`, no `*` wildcards, no derivation from runtime arguments. |
| 3 | Constants-only dispatch for action_type/change_type. | PASS | §3 declares every `*_ACTION_TYPE` and `*_CHANGE_TYPE` as a module-level string constant in `app/contracts/compliance.py` (proposal.md:461-481). §5 references constants verbatim (e.g., `COMPLIANCE_RULE_CREATE_ACTION_TYPE` at proposal.md:909). The review/override branch selects the correct `*_ACTION_TYPE` + matching `*_PAYLOAD_ALLOWLIST` pair from `request.action` without f-strings (proposal.md:1129-1135, R8). The one f-string in §5 — `reason=f"compliance_violation:{rule['name']}"` at proposal.md:1323 — is the free-form `reason` text on a `RosterEntryTransitionRequest`, not a dispatch vocabulary value; D13 forbids f-strings for `action_type`/`change_type`, not for reason strings. |
| 4 | Root audit context in scheduled worker (SLICE-020 R2 precedent). | PASS | `compliance_evaluation_worker_tick` (proposal.md:1537-1567) mirrors `services/api/app/tasks/permission_expiry.py:43-74` point-for-point: `get_current_audit_context()` guard, `use_audit_context(_root_audit_context())` when `existing_ctx is None` else `nullcontext()`, split exception handling (`StaleMutationError` → debug + return None; generic `Exception` → exception log + return None). `_root_audit_context()` constructs `AuditContextRead(correlation_id=uuid4(), causation_id=None, headers=CorrelationHeadersRead(...))` (proposal.md:1525-1534). Service actor via `_evaluator_service_actor()` returning `ActorIdentity(actor_kind="service", actor_id="compliance-evaluator")` (proposal.md:1519-1522). Scheduler wiring at proposal.md:1571-1590 matches the permission-expiry + ticket-SLA in-loop pattern; no new `scheduled_jobs` row. |
| 5 | Spoof-proof `submitted_by_member_id` and `corrected_by_member_id` — authenticated actor, not request body. | PASS | `EvidenceSubmissionCreate` (proposal.md:407-411) has no `submitted_by_member_id` field; `_ComplianceModel` declares `extra="forbid"` (proposal.md:360-361), so any client attempt to inject `submitted_by_member_id` is rejected with 422. Service `submit_evidence` sets the column from `actor.actor_id` (proposal.md:951-955). `OfficerCorrectionRequest` (proposal.md:600-602) declares only `corrected_fields` and `correction_reason`; service `correct_evidence` sets `corrected_by_member_id=actor.actor_id` explicitly inside the repository update (proposal.md:990-995). R1 additionally closes the chapter_id spoof: `submit_evidence` loads the rule first and authorizes/persists against `rule["chapter_id"]`, not the request body (proposal.md:937-955), with `EvidenceChapterMismatchError` → 422 when the body `chapter_id` doesn't match. `ComplianceEvaluationReviewRequest` (proposal.md:453-456) has no `reviewer_id` field — reviewer attribution is derived from `actor.actor_id` inside `review_evaluation`. Header-based actor injection (`X-Actor-Kind` / `X-Actor-Id` middleware, verified) means request body cannot override the authenticated actor. |
| 6 | Consequence routing: worker audit chain shows (a) `compliance_evaluation.create` AND (b) `roster.transition` with correlation threaded via `get_current_audit_context`. | PASS | Worker installs one root audit context per tick (proposal.md:1542-1549). Inside it, `_evaluate_member_rule.mutate_projection` runs `insert_evaluation_if_absent` and then calls `roster_service.transition_roster_entry(..., connection=conn)` from inside the callback (proposal.md:1317-1330), before returning the `COMPLIANCE_EVALUATION_CREATE_CHANGE_TYPE` draft. Both the outer `compliance_evaluation.create` `mutate_entity` call and the nested `roster_entry.transition` `mutate_entity` call inherit the ambient correlation_id via `get_current_audit_context()` (`mutations.py:74-83`, research-confirmed); the inner roster action's `causation_id` threads back to the outer audit context. R4 layers operator attribution: `originating_actor` defaults to the service actor for scheduled runs, and is set to the triggering operator when the manual `/evaluations/run` endpoint authorizes with `compliance_evaluation.review` (proposal.md:119-137, 1156-1175). An auditor running `SELECT * FROM activity_actions WHERE correlation_id = :tick` returns both `compliance_evaluation.create` and the consequent `roster_entry.transition` rows with matching correlation; `aggregate_id` separates them. |
| 7 | `_evaluate_member_rule` mutations share a connection OR run in separate tx with per-item isolation — clarify. | PASS | R2 rewrites `_evaluate_member_rule` as a single per-member `mutate_entity` transaction: the idempotency insert (`insert_evaluation_if_absent(conn, ...)`), the audit projection, AND the roster transition (`transition_roster_entry(..., connection=conn)`) all run on the same connection inside one transaction (proposal.md:1280-1346). R7 (Revision 2) adds the enabling kwarg to the roster-service signature: `transition_roster_entry` and `get_roster_entry` gain `connection: Connection[Any] | None = None` kwargs with SLICE-020 R1 precedent and a pinned test `test_transition_roster_entry_accepts_shared_connection` in `services/api/tests/test_roster.py` (proposal.md:803-857). Per-member isolation is at the worker-loop level: `run_scheduled_compliance_evaluations` catches `StaleMutationError` + generic `Exception` per-member (proposal.md:1208-1220), so one member's failure does not abort the rule or the batch. Closes both the atomicity requirement and the isolation requirement. |
| 8 | Terminal-state replay idempotency: worker re-invoke on a fully-processed period is a no-op via ON CONFLICT DO NOTHING. | PASS | `compliance_evaluations` has `UNIQUE (member_id, rule_id, period_start, period_end)` (proposal.md:279-280). `insert_evaluation_if_absent` uses `INSERT ... ON CONFLICT (...) DO NOTHING RETURNING *` and returns `None` on conflict (proposal.md:724-737). R2 moves this insert inside `mutate_projection`; when the insert returns None, `_AlreadyEvaluatedSentinel` is raised inside the projection (proposal.md:1300-1305), and `mutate_entity` propagates it so the outer transaction rolls back cleanly — no new `aggregate_heads`/`activity_actions`/`activity_state_changes` row is written for the duplicate attempt. The caller catches the sentinel and returns None (proposal.md:1376-1377). Replay on a fully-processed period → zero new rows across all audit tables. Research confirmed `fetchone()` returns None when ON CONFLICT DO NOTHING skips a row (`repositories/ticket_sla.py:135-162`). |
| 9 | OCR trigger: `POST /extract` records action even if OCR provider raises 503 — or does 503 short-circuit before mutate_entity? | ACCEPTED L1 | `trigger_extraction` (proposal.md:1057-1090) authorizes first (403 at 503-probing actors without `compliance_evidence.extract`), then on `OcrProviderNotConfiguredError` executes `raise` (bubbles to endpoint → 503) without calling `mutate_entity`. The 503 path writes no audit row. Every other provider exception routes through `_persist_extraction_failure`, which DOES call `mutate_entity` with `EVIDENCE_EXTRACT_ACTION_TYPE` + `EVIDENCE_EXTRACTION_FAILED_CHANGE_TYPE`. The asymmetry is documented as L1 LOW in the Revision Log (proposal.md:2087-2091) and accepted: mutation audit integrity is preserved (no evidence row changes), and the authority check ahead of the provider call prevents unauthorized probe-churn. Follow-up visibility work deferred to the slice that wires a real OCR provider. |
| 10 | Officer correction preserves raw_text + attachment_ref in projection (AC3) AND `activity_state_changes` captures pre-correction `extracted_fields` for audit reconstructibility. | PASS | AC3 preservation at the projection level: `update_evidence_correction` writes only overlay columns (proposal.md:709-716), and D3 CHECK constraints prevent the immutable OCR output from being overwritten (proposal.md:227-236). R5 captures the pre-correction state inside `diff_json`: `extraction_status {old, new}`, immutable baseline `extracted_fields: <baseline>`, and `extracted_fields_corrected: {old: <prior overlay or None>, new: <new overlay>}` (proposal.md:1012-1021). A single `activity_state_changes` row therefore carries (baseline, prior overlay, new overlay) — self-describing for both first-correction (`old: null`) and later-correction cases. `payload_json` captures the new state (`{evidence_id, corrected_fields, corrected_by_member_id, correction_reason}`, proposal.md:999-1004); full reconstruction requires reading `diff_json` alongside `payload_json` (Observation B), which is the canonical pattern across SLICE-014/018 audit rows. Test `test_correction_diff_json_records_prior_overlay_on_second_correction` pins the intent. |

---

## Findings

### Finding L1 — LOW — 503 extraction path emits no audit row (unchanged, accepted)

- **References.** proposal.md:1084-1086 (`except OcrProviderNotConfiguredError: raise`); proposal.md:2087-2091 (Revision Log accepts as LOW).
- **Evidence.** `OcrProviderNotConfiguredError` bubbles past `mutate_entity`, so no `evidence_submission.extract` action row is written for the 503 path. Other provider exceptions emit an `extraction_failed` audit row via `_persist_extraction_failure`. The authority check runs BEFORE the provider call, so unauthorized probes are still 403, not silent.
- **Impact.** Operator-facing audit queries on `evidence_id` will miss "who probed extraction while the provider was misconfigured." No mutation is lost — the evidence row remains in its prior state, so audit integrity for persisted state changes is preserved. The exposure window is limited to the lifetime of an unconfigured OCR provider.
- **Recommendation.** Accept as documented. If the follow-up slice that wires a real OCR provider surfaces operational need, emit an audit row from `_persist_extraction_failure` with `extraction_error="ocr_provider_not_configured"` — mechanical one-line change.

---

## Verification: prior audit findings closed by Revision 2

| Prior finding | Closed by | Verification |
|---|---|---|
| **M5** — `transition_roster_entry(..., connection=)` signature extension not enumerated in §5 | R7 | Revision 2 adds an explicit §5 subsection "Roster service signature extension (Revision 2 — R7)" (proposal.md:803-857). `transition_roster_entry` and `get_roster_entry` gain `connection: Connection[Any] | None = None`, append-only, defaulting to `None` so existing callers are unaffected. When provided, the kwarg is threaded into the internal `mutate_entity(..., connection=connection)` call (`mutations.py:70` accepts this, research-confirmed). SLICE-020 R1 is cited as the mirror pattern precedent. Pinned test `test_transition_roster_entry_accepts_shared_connection` lives in `services/api/tests/test_roster.py` (proposal.md:846-857) — the roster service's own test home — verifying both (a) pre-commit visibility inside the shared tx and (b) atomic rollback on caller rollback. This restores R2's atomicity guarantee: evaluation insert + audit projection + roster transition commit or roll back as one unit. **Verified closed.** |
| **L2** — `compliance_evaluation.override` action_type lacked a dedicated payload allowlist | R8 | Revision 2 adds `COMPLIANCE_EVALUATION_OVERRIDE_PAYLOAD_ALLOWLIST = frozenset({"evaluation_id", "override_result", "reviewer_reason"})` alongside the review allowlist (proposal.md:519-525), and §5 `review_evaluation` now spells out the per-action pairing: review dispatches pair `COMPLIANCE_EVALUATION_REVIEW_ACTION_TYPE` with `COMPLIANCE_EVALUATION_REVIEW_PAYLOAD_ALLOWLIST`; override dispatches pair `COMPLIANCE_EVALUATION_OVERRIDE_ACTION_TYPE` with `COMPLIANCE_EVALUATION_OVERRIDE_PAYLOAD_ALLOWLIST` (proposal.md:1129-1135). D13's constants-only-with-named-allowlist-per-action requirement is now met at the naming layer as well as the runtime layer. **Verified closed.** |

Revisions R1–R6 from the prior audit remain verified closed (see prior audit's verification table — R1 chapter_id spoof, R2 atomic evaluation, R3 orphan consequence, R4 operator attribution, R5 second-correction diff, R6 roster call signature reads).

---

## Observations (non-blocking)

### Observation A — `EVIDENCE_CORRECT_PAYLOAD_ALLOWLIST` includes `corrected_fields` (arbitrary JSON)

`EVIDENCE_CORRECT_PAYLOAD_ALLOWLIST` (proposal.md:508-510) whitelists `corrected_fields`, a `dict[str, Any]` of officer-supplied values. The allowlist is "narrow" in the D13 sense (no wildcards, no dynamic derivation), but `corrected_fields` can contain PII or health-adjacent data. Audit payloads inherit whatever the officer typed. This mirrors `EVIDENCE_SUBMIT_PAYLOAD_ALLOWLIST` carrying `attachment_ref`. Acceptable for this slice — flagging so a later slice introducing payload-level redaction (e.g., HIPAA alignment) has a known hook. The extract path already uses `raw_text_present` rather than raw text; the same convention could be extended to corrections if needed. Not a revision blocker.

### Observation B — `payload_json` vs `diff_json` split for correction reconstruction

R5 places the correction chain in `diff_json` (`extracted_fields_corrected: {old, new}` + immutable baseline), not in `payload_json`. This is correct per the codebase's `payload_json`-is-the-accepted-fact / `diff_json`-is-the-derived-view split (research-confirmed at `contracts/mutations.py:13-17, 55-67`). An auditor querying `payload_json` alone for corrections will see `{evidence_id, corrected_fields, corrected_by_member_id, correction_reason}` and must join `diff_json` for the chain. Matches SLICE-014/018 audit shape. Worth one sentence of documentation in the implementation-phase audit-schema notes if one is produced. Not a revision blocker.

### Observation C — `EvidenceSubmissionCreate.member_id` is a request-body field (officer-on-behalf-of pattern)

`EvidenceSubmissionCreate` (proposal.md:407-411) takes `member_id` from the body, distinct from the authenticated actor. This is the "officer submits for member X" pattern — authority `compliance_evidence.submit` at chapter scope lets officers submit on behalf of any chapter member. Spoof-proofing is intact at the audit layer: the row captures `submitted_by_member_id = actor.actor_id` (authenticated submitter) separately from `member_id` (evidence subject). The permission model, not the schema, scopes who may submit for whom — that is policy, not an audit defect. Test `test_submitted_by_is_derived_from_actor_not_request_body` (proposal.md:1733) pins the spoof-proof behavior at the actor layer.

### Observation D — `_current_rule_version` helper referenced but not enumerated

`_evaluate_member_rule` calls `_current_rule_version(db, rule_id=...)` (proposal.md:1271) but §4/§5 don't declare it. A `SELECT current_seq FROM aggregate_heads WHERE aggregate_type='compliance_rule' AND aggregate_id=:rule_id` one-liner (or a repository helper wrapping it) is required. Hygiene — absorb in implementation. No audit integrity concern (the version is read-only; worst case a stale read produces a rule_version off by one, which is still a deterministic snapshot).

### Observation E — Tick-scoped vs evaluation-scoped correlation_id

The worker installs one root audit context per tick (proposal.md:1525-1534), so every `compliance_evaluation.create` AND every downstream `roster_entry.transition` in the tick share the same `correlation_id`. Matches SLICE-020 R2 precedent. Auditors filtering by correlation_id see the whole tick, not a single `(member, rule, period)`; per-evaluation separation is via `aggregate_id`. Consistent with shipped pattern; flagging so implementation-phase docs can mention "tick-scoped correlation; use aggregate_id for per-evaluation narrowing."

---

## Severity summary

| Finding | Severity | Status |
|---|---|---|
| L1 — 503 short-circuit emits no audit row | LOW | accepted (unchanged, documented in Revision Log) |
| M5 — roster-service `connection=` kwarg (prior) | MEDIUM | **CLOSED by R7** (explicit §5 subsection + test) |
| L2 — override action lacked paired allowlist (prior) | LOW | **CLOSED by R8** (`COMPLIANCE_EVALUATION_OVERRIDE_PAYLOAD_ALLOWLIST` added) |
| M1 — bare-row atomicity (prior) | MEDIUM | CLOSED by R2, cross-service atomicity now also CLOSED by R7 |
| M2 — orphan consequence audit (prior) | MEDIUM | CLOSED by R3 |
| M3 — manual operator attribution (prior) | MEDIUM | CLOSED by R4 |
| M4 — second-correction diff (prior) | MEDIUM | CLOSED by R5 |
| F1 (shortcut) chapter_id spoof (prior) | MEDIUM | CLOSED by R1 |

**Overall: LOW.** No open MEDIUM or HIGH findings. Revision 2 is
ready to advance to the hookpoint-research gate. All ten focus items
pass; the one remaining LOW (L1) is explicitly accepted and
documented in the Revision Log.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
