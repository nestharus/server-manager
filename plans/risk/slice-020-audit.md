# SLICE-020 Audit Risk Assessment — Revision 2

**Severity: LOW**

Revision 1 of `.pipeline/proposal.md` closes the two MEDIUM audit findings
recorded in the prior iteration of this file and four of the five LOW
findings. Every new mutation — renew, expire, expiry-drift create — now
routes through `mutate_entity()` with an explicit, field-level
`payload_allowlist`; per-intent atomicity is enforced by threading a single
`connection` into both `mutate_entity` calls via the shared-connection
precedent from `permission_reconciliation._record_drift_created`; and the
worker task now installs a root `use_audit_context()` when no ambient
context exists, matching `evaluate_ticket_sla`.

One LOW finding remains open (`request_surface` hardcoded across worker and
manual-endpoint paths, explicitly deferred to a future hygiene pass in the
Revision 1 log). A second LOW-severity documentation observation is
recorded: the Focus criterion 4 wording (`permission_drift.create` +
`permission_drift.created`) diverges from the proposal's deliberately-
distinct verbs (`permission_drift.detect_expired` +
`permission_drift.detected_expired`, R9). The proposal's rationale for
distinct verbs is sound and explicitly documented; the observation is
recorded so the wording drift between Focus prompt, synthesis D12, and
proposal does not resurface in implementation.

No MEDIUM or HIGH audit-discipline risks remain. The slice can proceed to
hookpoint research on audit grounds.

---

## Focus Walk-Through

| # | Focus | Verdict | Primary evidence |
|---|-------|---------|------------------|
| 1 | Every mutation (renew, expire, drift create) routes through `mutate_entity()` with explicit `payload_allowlist`. | PASS | `renew_permission_intent` (proposal.md:374-393) routes via `mutate_entity` with `payload_allowlist=INTENT_RENEW_PAYLOAD_ALLOWLIST`. `_expire_single_intent` (proposal.md:497-516) uses `payload_allowlist=INTENT_EXPIRE_PAYLOAD_ALLOWLIST`. `_create_expiry_drift` (proposal.md:593-609) uses `payload_allowlist=EXPIRY_DRIFT_CREATE_PAYLOAD_ALLOWLIST`. No direct-repository write path exists for any of these three actions. |
| 2 | `INTENT_RENEW_PAYLOAD_ALLOWLIST` and `INTENT_EXPIRE_PAYLOAD_ALLOWLIST` concretely defined with field-level keys. | PASS | §9.1 (proposal.md:1158-1163): `INTENT_RENEW_PAYLOAD_ALLOWLIST = frozenset({"new_expires_at", "reason"})`; `INTENT_EXPIRE_PAYLOAD_ALLOWLIST = frozenset({"expired_at", "source"})`. `source ∈ {"worker_sweep", "manual_trigger"}` is threaded via a new `source` parameter on `expire_temporary_permission_intents` (§5.2, §7.1). Both dicts are `frozenset` of plain field names — no wildcards, no `**kwargs`. |
| 3 | Drift creation during expiry uses the same `_record_drift_created` helper from SLICE-014 (or an equivalent `mutate_entity`-routed helper). | PASS (equivalent helper) | `_create_expiry_drift` (proposal.md:532-610) is a `mutate_entity`-routed helper that mirrors `_record_drift_created`'s contract: accepts `connection=connection` and runs inside the caller's transaction, sets `aggregate_type="permission_drift"`, emits lean `action_payload` + full `payload_json`, performs no per-intent scope authority check (R3, matching `_record_drift_created` precedent at `permission_reconciliation.py:581-639`). It does not reuse the shipped helper byte-for-byte because D9 binds a distinct `permission_drift.detect_expired` action verb and D11/R9 a distinct `permission_drift.detected_expired` change verb; routing discipline is identical. |
| 4 | Each expired intent produces one `permission_intent.expired` state change + two aggregate mutations (intent + drift). | PASS (verb names differ from Focus wording — see Observation A) | `_expire_single_intent` (proposal.md:461-529) opens one `db.transaction()` and invokes `mutate_entity` twice — once on `permission_intent` aggregate (`action_type=INTENT_ACTION_TYPE["expire"]="permission_intent.expire"`, `change_type=INTENT_CHANGE_TYPE["expired"]="permission_intent.expired"`) and once on `permission_drift` aggregate (`action_type=DRIFT_ACTION_TYPE["detect_expired"]="permission_drift.detect_expired"`, `change_type=DRIFT_CHANGE_TYPE["detected_expired"]="permission_drift.detected_expired"`). Two aggregate mutations per intent, one `permission_intent.expired` state-change row per intent, one drift state-change row per intent. Verb-name divergence from the Focus wording is intentional (R9) so operators can filter expiry-origin drift from reconciliation drift without joining to `permission_intent_id IS NOT NULL`; see Observation A below. |
| 5 | `action_payload` and `StateChangeDraft.payload_json` specified (not bare `...`) for all new audit flows. | PASS | Renewal: `action_payload={"new_expires_at": request.expires_at.isoformat(), "reason": request.reason}` (proposal.md:385-388); `payload_json=updated.model_dump(mode="json")` (proposal.md:371). Expire: `action_payload={"expired_at": now.isoformat(), "source": source}` (proposal.md:507-510); `payload_json=updated.model_dump(mode="json")` (proposal.md:494). Drift create: `action_payload` is a lean 9-key dict (proposal.md:572-582); `payload_json=drift.model_dump(mode="json")` (proposal.md:590). R8 split matches `_record_drift_created`'s pattern (lean action_payload, fat state-change payload_json). No `...` / TODO placeholders anywhere. |
| 6 | Spoof-proof originating actor on manual `/expire/run` endpoint (SLICE-014 pattern). | PASS | `run_permission_expiry_endpoint` (proposal.md:920-938) declares no body parameter; the actor is strictly `Depends(get_current_actor)`. `PermissionExpirySweepResult` (§3.3, proposal.md:208-215) has **no** `originating_actor_*` fields — there is no request shape a client can populate that would forge the recorded actor. Synthesis D5 binds this explicitly. |
| 7 | Worker exceptions caught and logged via `logger.exception`; `StaleMutationError` handled explicitly. | PASS (R6 resolved prior Finding 3) | Per-intent loop (proposal.md:434-448) splits: `StaleMutationError` → `logger.debug` + `continue` (no `errored_count` increment); other `Exception` → `logger.exception` + `errored_count += 1` + `continue`. Worker tick wrapper (proposal.md:782-788) applies the same split at the outer boundary. Matches the shipped `ticket_sla._handle_threshold` pattern. R6 entry in revision log confirms the split. |
| 8 | Batch-wise audit: each intent's expire + drift creation happen in their own tx; partial batch failure doesn't taint successes. | PASS (R1 resolved prior Finding 2) | `_expire_single_intent` (proposal.md:480) opens one `db.transaction() as connection`. Both `mutate_entity` calls receive `connection=connection` (proposal.md:515, 520, 608) — confirmed by `grep` of the proposal. Single tx per intent; commit on `with` exit; rollback on any exception rolls back expire-stamp + drift-insert + both audit rows + both state-change rows together. `expired_at` remains NULL on rollback, so the candidate is re-selected on the next tick. Per-intent failure does not abort the batch because `_expire_single_intent` is invoked per-candidate inside the batch for-loop. |
| 9 | Correlation/causation threading via `get_current_audit_context()` inherits for both expire and drift rows within a single intent's tx. | PASS (R2 resolved prior Finding 1) | `permission_expiry_worker_tick` (proposal.md:758-788) installs `use_audit_context(_root_audit_context())` when `get_current_audit_context()` returns `None`, mirroring `evaluate_ticket_sla` at `ticket_sla.py:508-513`. All `mutate_entity` calls within one tick — across every intent processed — now execute under one correlation_id, so the per-intent expire + drift audit rows share a correlation_id (and causation_id=None, per the root-context shape). The manual `/expire/run` endpoint inherits FastAPI's per-request `CorrelationMiddleware` context via the `nullcontext()` branch, so operator-triggered sweeps use the HTTP request's correlation_id. |
| 10 | No bypassed audit paths — migration backfill (if any) does not insert into activity tables directly. | PASS | Migration `wu_038_permission_intent_expiry` (proposal.md:84-131) performs only `ALTER TABLE permission_intents ADD COLUMN expired_at`, `ADD CONSTRAINT … CHECK (…)`, and a single idempotent `INSERT INTO authority_grants` (the `permission-expirer` seed). No backfill of `expired_at` values, no writes to `aggregate_heads` / `activity_actions` / `activity_state_changes`. Rows with `expires_at <= now()` at deploy time are caught by the first worker tick post-migration and flow through `mutate_entity` normally — every expiry produces audit rows. |

---

## Findings

### Finding A — LOW — `request_surface` is hardcoded to `"worker:permission_expiry"` even when invoked from the manual endpoint

- **References.** proposal.md:504
  (`_expire_single_intent._make_request(… request_surface="worker:permission_expiry")`),
  proposal.md:600
  (`_create_expiry_drift._make_request(… request_surface="worker:permission_expiry")`),
  proposal.md:920-938 (manual `/expire/run` endpoint),
  proposal.md:1275 (Revision 1 log entry: "audit LOW 6 — `request_surface`
  hardcoded. Not revised in this iteration … Deferred to future hygiene pass.").
- **Evidence.** Both `_make_request` call sites inside the service layer
  bake `"worker:permission_expiry"` into the `MutationRequest`, regardless
  of whether the caller arrived from the scheduler tick or from the
  `POST /api/v1/permission-intents/expire/run` HTTP endpoint. The proposal
  explicitly acknowledges this in the Revision 1 log as a deferred item.
  The `action_payload["source"]` discriminator (`"worker_sweep"` vs.
  `"manual_trigger"`) partially compensates — operators filtering by the
  `source` key in `activity_actions.request_json` can separate the two
  surfaces — but the top-level `activity_actions.request_surface`
  column still reads `worker:permission_expiry` for both flavors.
- **Consequence.** Minor audit-trail muddiness on the manual trigger.
  Operators filtering `activity_actions` by
  `request_surface='api:/api/v1/…'` will miss operator-driven expiry
  sweeps; those show up only when filtering on the worker surface or on
  the nested `source` key. The **actor** disambiguates correctly (session
  user vs. `permission-expirer` service), so accountability is preserved;
  only the surface label is wrong.
- **Fix (explicitly deferred).** Add a keyword-only `request_surface`
  parameter to `expire_temporary_permission_intents` and
  `_expire_single_intent`, default `"worker:permission_expiry"`; the
  manual endpoint passes
  `"api:/api/v1/permission-intents/expire/run"`. Thread into both
  `_make_request` call sites alongside the existing `source` thread.
- **Severity.** LOW. Not a blocker; explicitly deferred by the proposal's
  own revision log.

---

## Observations

### Observation A — Focus criterion 4 verb names diverge from the proposal's deliberately-distinct verbs

The Focus prompt for this audit (item #4) names the drift action/change
verbs as `permission_drift.create` and `permission_drift.created`. The
proposal's R9 revision deliberately introduces **distinct** verbs —
`permission_drift.detect_expired` and `permission_drift.detected_expired`
— to keep expiry-origin drift separable from reconciliation-origin drift
in `activity_actions` / `activity_state_changes` without forcing a join
to `permission_intent_id IS NOT NULL`. The proposal's revision log
(R9 at proposal.md:1267) documents this choice and corrects the
prior synthesis D12 claim that the change type was "reused" (which was
factually wrong — reconciliation emits `permission_drift.created`, not
`permission_drift.detected`).

Two aggregate mutations per intent still hold. Audit-discipline intent
is preserved: every expired intent produces one expire action + one
expire state-change on the `permission_intent` aggregate, and one
drift-create action + one drift-create state-change on the
`permission_drift` aggregate. Only the **verb labels** differ. This is
a wording-alignment issue across Focus prompt / synthesis / proposal,
not an audit defect. The proposal's rationale is sound and explicit; no
revision is requested on audit grounds. Logged here so implementation
does not inadvertently "correct" the proposal verbs back to the Focus
wording and erase the filter-discriminator that R9 introduces.

### Observation B — Batch-level (not per-intent) correlation_id under R2

The R2 fix installs **one** root audit context at the task-tick level,
not one per intent. All intents processed within a single worker tick
therefore share the same `correlation_id` in `activity_actions` /
`activity_state_changes`. Within a single intent's transaction, the
expire + drift rows trivially share that correlation_id (satisfying
Focus criterion 9). Across the batch, every intent also shares it —
which matches the shipped `evaluate_ticket_sla` precedent (also one
context per batch) but may be mildly surprising to an operator
investigating "all audit rows for intent X's expiry" who filters by
correlation_id and gets every other intent processed in the same tick
too. Filtering by `aggregate_id` (composite for intent, drift_id for
drift) remains precise. No audit defect; the Focus criterion is
satisfied. Recorded so the implementation phase understands the shape.

### Observation C — StaleMutationError "rejected" audit row shares the per-intent transaction

Under R1's shared-transaction model, if `mutate_entity` detects a
stale version and writes its internal `status="rejected"` action row
before raising `StaleMutationError`, that rejected row lives inside the
same `db.transaction()` as the would-be expire + drift rows. When the
outer `with` block catches the exception and rolls back, the rejected
audit row rolls back with it. This matches the shipped
`permission_reconciliation` precedent (same `connection=` threading;
same implicit rollback-on-raise), so it is not a new defect introduced
by this slice. It is a property of `mutate_entity`'s transaction
semantics. If operators rely on rejected audit rows persisting across
rollback windows, that would be a platform-level change well outside
SLICE-020's scope.

No finding. Recorded so the implementation phase and future audit
reviewers do not mistake the rollback for a bug.

---

## Resolution Status of Prior Findings

| Prior finding | Severity | Status in Revision 1 | Evidence |
|---|---|---|---|
| F1 — Worker doesn't install a root audit context | MEDIUM | RESOLVED (R2) | `permission_expiry_worker_tick` installs `use_audit_context(_root_audit_context())` under `existing_ctx is None` guard (proposal.md:768-774). New helper `_root_audit_context()` at proposal.md:741-755 mirrors `ticket_sla._root_audit_context` verbatim. |
| F2 — Expire + drift in two separate transactions | MEDIUM | RESOLVED (R1) | `_expire_single_intent` opens one `db.transaction() as connection` (proposal.md:480). Both `mutate_entity` calls receive `connection=connection` (proposal.md:515, 520, 608). |
| F3 — `StaleMutationError` classified as an unexpected exception | LOW | RESOLVED (R6) | Per-intent loop splits `StaleMutationError` → `logger.debug` + `continue` (no `errored_count` increment) from other `Exception` → `logger.exception` + `errored_count += 1` (proposal.md:434-448). Worker tick applies the same split (proposal.md:782-788). |
| F4 — `EXPIRY_DRIFT_DETECT_PAYLOAD_ALLOWLIST` wider than synthesis D12 | LOW | RESOLVED (R8) | Renamed to `EXPIRY_DRIFT_CREATE_PAYLOAD_ALLOWLIST`; narrowed from 17 keys to 9 (drift_id + permission_intent_id + intent_version + scope + target + status). No bit masks in action_payload (proposal.md:1164-1174). Matches `_record_drift_created`'s stricter shape. |
| F5 — `action_payload` and `payload_json` identical dumps | LOW | RESOLVED (R8) | `_create_expiry_drift` now constructs a lean `action_payload` dict separate from `payload_json=drift.model_dump(mode="json")` (proposal.md:571-591). Mirrors `_record_drift_created`'s lean/fat split. |
| F6 — `request_surface` hardcoded | LOW | DEFERRED (acknowledged in revision log) | See Finding A above. |
| F7 — Synthesis D12 falsely claimed `permission_drift.detected` reuse | LOW | RESOLVED (R9) | Revision log explicitly supersedes the synthesis claim and introduces distinct `DRIFT_CHANGE_TYPE["detected_expired"] = "permission_drift.detected_expired"` (proposal.md:1148-1150). See also Observation A for Focus-prompt wording alignment. |

---

## Summary

| Finding / Observation | Severity |
|---|---|
| A — `request_surface` hardcoded to `"worker:permission_expiry"` on manual `/expire/run` path | LOW (deferred) |
| Observation A — Focus criterion 4 verb names differ from proposal verbs | — (documentation alignment) |
| Observation B — Batch-level correlation_id under R2 | — (shape note) |
| Observation C — `StaleMutationError` rejected-row rolls back with shared tx | — (platform-level behavior; not a slice defect) |

Prior Findings 1 and 2 (both MEDIUM) and prior Findings 3, 4, 5, 7 (LOW)
are resolved by Revisions R1, R2, R6, R8, R9. Prior Finding 6 (LOW) is
re-raised here as Finding A and is explicitly deferred by the proposal's
own Revision 1 log.

Overall verdict: **LOW**. All Focus criteria pass. The single open LOW
finding is a minor audit-trail label ambiguity that the proposal
acknowledges and defers. The three observations are shape/documentation
notes rather than audit defects. SLICE-020's audit discipline is adequate
for hookpoint research and implementation to proceed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
