# SLICE-020 Shortcut Risk Assessment — Revision 2

**Rating: LOW.** The proposal's Revision 1 (R1–R9) closes the prior HIGH
findings F1/F2 and the prior MEDIUM findings F3–F5. Every one of the
sixteen shortcut-focus items passes in the revised text. Two residual
LOW observations survive re-review: the `FOR UPDATE SKIP LOCKED` predicate
in `select_expirable_intents` is decorative (its lock releases before the
per-intent mutation runs), and the split between `_read_intent_head_version`
and `mutate_entity`'s internal `get_head_for_update` leaves a narrow
concurrency window where a benign race surfaces as `logger.exception`
rather than `logger.debug`. Neither blocks AC1–AC4.

---

## Scope

Re-reviewed `.pipeline/proposal.md` (Revision 1, 1277 lines),
`.pipeline/synthesis.md` (D1–D15), `.pipeline/research.md`,
`product-strategy/tickets/SLICE-020.md` (AC1–AC4, WU-038A/WU-038B,
Code Boundary), and `AGENTS.md` (Live Server Principle, No Backwards
Compatibility, Test/Code Agent Separation) against the sixteen
shortcut-focus items named by the orchestrator. The R1 revision log
cross-references prior findings F1–F9; each was verified closed in the
current proposal text.

---

## Closed since Revision 0

| Prior finding | Severity | Closed by revision |
|---|---|---|
| F1 — expire + drift ran in two separate transactions | HIGH | R1 — `_expire_single_intent` opens one `db.transaction()` and threads `connection=connection` into both `mutate_entity` calls |
| F2 — chapter-scoped drift failed authority because expirer holds only a global grant | HIGH | R3 — dropped per-intent `_require_scoped_authority` inside `_create_expiry_drift`; sweep's global `permission_intent.write` gate is the sole authority boundary (mirrors SLICE-014 `_record_drift_created`) |
| F3 — stubbed `_current_intent_version(db, row_uuid)` passed the wrong id and ran outside the mutation tx | MEDIUM | R4 — `_read_intent_head_version(connection, aggregate_id=…)` uses the composite aggregate id built by `build_permission_intent_aggregate_id`, runs inside the per-intent tx |
| F4 — contract-layer `@field_validator("expires_at")` future-check drifted from the service's `now` | MEDIUM | R5 — validator removed; service raises `RenewalExpiresAtInPastError` using the same `now` as the active-expired guard; 422 mapping added |
| F5 — `StaleMutationError` classified as unexpected exception (inflated `errored_count`, log noise) | MEDIUM | R6 — `StaleMutationError` caught separately at `logger.debug`, does not increment `errored_count`; new test `test_worker_stale_mutation_collision_is_logged_at_debug_not_errored` |
| F6 — SKIP LOCKED framed as primary idempotency | MEDIUM (policy) | R6 Guardrails rewrite — OCC + `expired_at IS NULL` named as primary; SKIP LOCKED demoted to "contention-latency optimization" |
| F7 — per-intent tx claimed to "match ticket_sla" | LOW | §5.2 narrative revised to frame per-intent tx as a deliberate departure from `ticket_sla`'s batch-tx shape; precedent cited as `submit_reconciliation_snapshot` |
| F8 — `mark_intent_expired_row` rowcount=0 treated as error | LOW | Under R1's shared tx, OCC races surface as `StaleMutationError` before the projection runs; rowcount=0 now only indicates genuine data inconsistency (see Obs 2 below for the residual window) |
| F9 — inline action/change-type strings | LOW | R7 — `INTENT_ACTION_TYPE`, `INTENT_CHANGE_TYPE`, `DRIFT_ACTION_TYPE`, `DRIFT_CHANGE_TYPE` dicts dispatched at every `mutate_entity` call site |

---

## Focus Walk-Through (revised proposal)

| # | Focus | Verdict | Evidence |
|---|---|---|---|
| 1 | All mutations (renew, expire, drift) via `mutate_entity()` — no direct INSERT/UPDATE | PASS | Renew (§5.1 line 374): `mutate_entity(aggregate_type="permission_intent" …)`. Expire (§5.2 line 497): same. Drift (§5.2 line 593): `mutate_entity(aggregate_type="permission_drift" …)`. Repository writes (`update_permission_intent_row`, `mark_intent_expired_row`, `insert_permission_drift`) are all invoked inside the `mutate_projection` callback executed by `mutate_entity`; no repository write escapes the audited path. |
| 2 | Renewal requires If-Match (AC1) — OCC enforced, not optional | PASS | §7.1 line 905: `expected_version = parse_if_match_strong(request)` — missing/weak ETag returns 428/412 via the existing helper (`_shared.py:32-64`). `mutate_entity`'s `expected_version` check then raises `StaleMutationError` → 412 on stale match. |
| 3 | Renewal rejects non-temporary intents (AC2) — service-layer check AND DB CHECK backstop | PASS | Service: §5.1 line 343 `if not current.temporary: raise NonTemporaryIntentRenewalError`. DB backstop: shipped `permission_intents_temporary_shape_valid` (wu-006a:45) forbids `expires_at IS NOT NULL` when `temporary = FALSE`; any UPDATE that sets `expires_at` on a non-temporary row violates the check. Service mapping: 422 `non_temporary_intent` via `raise_known_permission_error` (§5.3). |
| 4 | Renewal rejects already-expired intents — checks both `expired_at IS NULL` AND `expires_at > now()` | PASS | §5.1 line 346: `if current.expired_at is not None or (current.expires_at is not None and current.expires_at <= now): raise ExpiredIntentRenewalError`. Both predicates use the same service-layer `now` as the future-check for `request.expires_at`, so the three time-dependent checks are internally consistent. |
| 5 | Worker idempotency via `expired_at IS NULL` filter — single-source-of-truth | PASS | Candidate SELECT filters `expired_at IS NULL` (§4.2 line 284). `mark_intent_expired_row` UPDATE repeats the predicate in its WHERE clause (§4.2 line 305) as defense-in-depth. No other idempotency dimension (e.g., drift-row uniqueness) competes. |
| 6 | `FOR UPDATE SKIP LOCKED` prevents concurrent workers from racing on same intent | PASS (with Observation 1) | §4.2 line 287 includes `FOR UPDATE SKIP LOCKED`. The proposal explicitly admits in §5.2 "Concurrency guarantees after R1" and in Guardrails that SKIP LOCKED is "a minor latency-contention optimization — the row locks release when the candidate-SELECT connection returns to the pool — not a primary idempotency layer." The actual racing guard is OCC on `aggregate_heads` + the `expired_at IS NULL` predicate in `mark_intent_expired_row`. Behavior is correct; SKIP LOCKED's effectiveness is narrower than its name suggests. See Observation 1. |
| 7 | Per-intent tx — partial batch failures don't taint successful intents | PASS | §5.2 `_expire_single_intent` opens a fresh `with db.transaction() as connection` per candidate, and the outer loop's try/except (`StaleMutationError` → debug skip; `Exception` → `logger.exception` + `errored_count += 1`) continues to the next candidate. Shape is the deliberate departure from `ticket_sla`'s batch-tx precedent, grounded in R1 atomicity between expire-stamp and drift-insert. |
| 8 | Constants-only dispatch for action_type / change_type — no inline strings, no f-string generation | PASS | §9.1 declares `INTENT_ACTION_TYPE`, `INTENT_CHANGE_TYPE`, `DRIFT_ACTION_TYPE`, `DRIFT_CHANGE_TYPE` dicts. Every `mutate_entity` call site (§5.1 lines 384/370; §5.2 lines 506/493; §5.2 lines 602/589) dereferences one of these dicts. No f-string generation of verbs; no inline literals. (Unrelated: `request_surface` is still an f-string / hardcoded — audit LOW 6, explicitly deferred; not in scope for Focus 8 which names action/change types only.) |
| 9 | Spoof-proof originating_actor on `/expire/run` endpoint | PASS | §7.1 `run_permission_expiry_endpoint` declares no body parameter; actor strictly from `Depends(get_current_actor)`. `PermissionExpirySweepResult` (§3.3) has no `originating_actor_*` fields. No request-surface input can alter the recorded actor; mirrors SLICE-021's no-body pattern. |
| 10 | Service-actor grant uses `@>` AND `<@` containment guard + expires_at + revoked_at checks (wu-028b precedent) | PASS | §2 migration lines 119-128: `WHERE NOT EXISTS (… permissions @> … AND permissions <@ … AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP))`. Verbatim shape of `wu-028b_permission_reconciliation_runs.py:127-163`. |
| 11 | Migration downgrade is no-op per live-server | PASS | §2 lines 134-136: `def downgrade() -> None: pass  # No-op per AGENTS.md Live Server Principle.` Matches every recent migration in the tree. |
| 12 | Drift row shape for expired intents: `actual_*` NULL, `intended_*` mirrors intent, `reconciliation_run_id` NULL — explicit, not silently defaulted | PASS | §5.2 `_create_expiry_drift` (lines 549-567) explicitly sets each field in the `model_validate` dict: `"reconciliation_run_id": None`, `"actual_bits": None`, `"actual_allow_bits": None`, `"actual_deny_bits": None`, and `intended_*` mirror intent via `getattr(intent, "permission_bits", None)` / `getattr(intent, "allow_bits", None)` / `getattr(intent, "deny_bits", None)`. Nothing is defaulted by Pydantic. |
| 13 | Worker resilience: `logger.exception` only for unexpected failures; `StaleMutationError` logged as `debug` (SLICE-017 MAJOR 4 pattern) | PASS | Service loop §5.2 lines 434-447: `except StaleMutationError: logger.debug(...)` (no `errored_count++`) then `except Exception: logger.exception(...); errored_count += 1`. Task tick §6.1 lines 782-788 repeats the same split. Test `test_worker_stale_mutation_collision_is_logged_at_debug_not_errored` covers the contract. |
| 14 | Pydantic validators: reason non-blank (strip-check), expires_at future-check at service layer (not contract, because "future" depends on the `now` used by the active-expired guard) | PASS | Reason: §3.2 `reject_blank_reason` validator — `if not value.strip(): raise ValueError(...)` — mirrors `PermissionDriftResolutionRequest`. Future-check: contract validator removed in R5; service raises `RenewalExpiresAtInPastError` (§5.1 line 350) using the same `now` as the active-expired guard. Mapped to 422 `renewal_expires_at_in_past` (§5.3). Note: the service's `now` is `datetime.now(tz=UTC)` (Python wall-clock), not DB `CURRENT_TIMESTAMP`; both time-dependent service checks (`expires_at <= now` active-expired guard and `request.expires_at <= now` future-check) use the same single `now`, so they are internally consistent. |
| 15 | No auto-reconciliation or auto-notification (D15 non-goals) | PASS | §10 items 1 and 2 explicitly forbid both. §1 AC4 step 1: "Worker never calls any Discord adapter." No SLICE-015 consumer hookpoint is introduced. |
| 16 | Worker actor is fixed constant, not parameter (SLICE-019 precedent for `SLA_WORKER_ID`) | PASS | §9.1: `PERMISSION_EXPIRER_ACTOR_ID: str = "permission-expirer"`. §6.1 `_expirer_service_actor()` returns `ActorIdentity(actor_kind="service", actor_id=PERMISSION_EXPIRER_ACTOR_ID)`. Actor not threaded as parameter. Manual `/expire/run` path correctly uses `Depends(get_current_actor)` instead — per D5 the worker actor is only for scheduler-driven sweeps. |

---

## Residual Observations (LOW)

### Observation 1 — `FOR UPDATE SKIP LOCKED` releases its lock before the per-intent mutation

- **References.** §4.2 lines 269-291 (`select_expirable_intents` runs inside `with connection.cursor(...)` under a `with db.connection() as connection` scope in §5.2 line 418); §5.2 line 480 (`with db.transaction() as connection` is a fresh connection for each candidate); §5.2 "Concurrency guarantees after R1" narrative; Guardrails "Concurrent worker safety" bullet.
- **Evidence.** `select_expirable_intents` returns the SELECT's connection to the pool before `_expire_single_intent` opens its own `db.transaction()`. Postgres row locks acquired by `FOR UPDATE SKIP LOCKED` are tied to the acquiring transaction; when the SELECT tx ends, the lock releases. Two concurrent workers (scheduler + manual `/expire/run`, or two scheduler processes) can therefore each SELECT the same candidate set. The proposal acknowledges this in the Guardrails bullet.
- **Why SKIP LOCKED still has value here.** It prevents two *simultaneous* SELECTs from waiting on each other when a third worker holds a lock on an overlapping row — a latency win. It does not serialize processing. Under the shipped shape, actual serialization comes from OCC on `aggregate_heads` + the `expired_at IS NULL` predicate in `mark_intent_expired_row`.
- **Test implication.** The test named `test_concurrent_sweeps_do_not_duplicate_via_for_update_skip_locked` in §8.2 will pass, but not because SKIP LOCKED dedupes concurrent workers — it passes because OCC raises `StaleMutationError` (caught at debug) or because `mark_intent_expired_row` rowcount=0 raises `PermissionIntentNotFoundError`. The test name attributes correctness to the wrong mechanism. Either rename it (`test_concurrent_sweeps_do_not_duplicate_via_occ`) or restructure the SELECT and mutation to share one transaction so the test name is accurate.
- **Severity.** LOW. The mechanism under its current name is mislabeled, but the behavior is correct and the proposal is transparent about the mislabel. Either remove SKIP LOCKED (no behavior change under R1) or restructure to share the tx (makes the name accurate and removes the narrow race in Observation 2).

### Observation 2 — `_read_intent_head_version` + `mutate_entity.get_head_for_update` split leaves a narrow concurrent-read window

- **References.** §5.2 lines 481-516 (`_expire_single_intent` reads version via `_read_intent_head_version`, then calls `mutate_entity` which internally does `get_head_for_update`); `services/api/app/services/mutations.py` (internal `SELECT … FOR UPDATE` on `aggregate_heads`); R1 "single transaction" guarantee.
- **Evidence.** Under R1 both reads run inside the same per-intent transaction. `_read_intent_head_version` is a plain `SELECT current_seq FROM aggregate_heads` with no row lock; it returns whatever is committed at read time. `mutate_entity` then issues a `SELECT … FOR UPDATE` which blocks on any concurrent row lock. Two interleavings exist:
  - **Concurrent commit between B's two reads** — worker B reads `current_seq = 5`, worker A commits (bumps to 6), B's `get_head_for_update` returns 6; `expected_version=5` != `current=6` → `StaleMutationError` → debug (benign, correct).
  - **Concurrent commit before B's first read** — worker A commits first (bumps to 6); B's `_read_intent_head_version` reads 6; B's `get_head_for_update` returns 6; `expected_version=6 == current=6` → OCC passes → projection runs → `mark_intent_expired_row` returns rowcount=0 (A already set `expired_at`) → `PermissionIntentNotFoundError` → caught by outer `except Exception` → `logger.exception` → `errored_count += 1`.
- **Consequence.** Under the second interleaving, a benign concurrency race surfaces as an error-level log and a false `errored_count` increment. The R1 revision log claims (F8) "OCC races surface as `StaleMutationError` before the projection runs"; that is true only for the first interleaving. The second interleaving is unlikely in practice (one scheduler per process, manual trigger is rare) but not impossible.
- **Remediation options.** (a) Catch `PermissionIntentNotFoundError` in the per-intent loop the same way `StaleMutationError` is caught — log at debug, skip, do not increment `errored_count`. (b) Move the SELECT candidates + per-intent mutation into a single transaction so SKIP LOCKED actually serializes workers and the concurrent-read window closes. Option (a) is the minimum fix and keeps R1 atomicity intact.
- **Severity.** LOW. Not a data-integrity defect; the intent *is* expired (by worker A), the drift row *does* exist (inside A's tx), the operator surface is intact. Only the log level and the `errored_count` metric are wrong under a narrow race.

---

## Non-findings (explicitly verified absent)

- ✅ No magic strings for action_type / change_type — all four dicts dispatched at every call site (§9.1, §9.4).
- ✅ No inline Discord mutation from the worker (§1 AC4 step 1, §10 item 1).
- ✅ No widening of `PermissionIntentUpdate` with `expired_at` (§3.1 note; §10 item 9).
- ✅ No new `permission_intent.status` column (§10 item 8).
- ✅ No new index on `permission_intents.expired_at` (§2 "Index" note; §10 item 13).
- ✅ No new authority permission — renewal and expiry both bind to `permission_intent.write` + `permission_drift.write` (D3; §10 item 12).
- ✅ No body on `POST /expire/run` — spoof-proof (§7.1; Focus 9).
- ✅ No `actual_*` fabrication on expiry drift — NULL is the contract (§5.2 `_create_expiry_drift`; §1 AC4 step 2; D9).
- ✅ No scope-filtered sweep — authority stays global (§7.1; §10 items 5, 6).
- ✅ No bulk renewal or time-travel surfaces (§10 items 3, 4).
- ✅ No env-var overrides for batch size / interval (§9; D6 binding implications).
- ✅ No backwards-compatibility shim (§Guardrails "No backwards-compatibility shims" bullet).
- ✅ `reason` non-blank strip-check at Pydantic layer (§3.2); future-check on `request.expires_at` moved from Pydantic to service under the service's own `now` (R5; §5.1 line 350).
- ✅ Worker actor constant-only; never a parameter (§9.1; §6.1).
- ✅ Migration seed uses `@>` AND `<@` containment + `revoked_at IS NULL` + `expires_at IS NULL OR > CURRENT_TIMESTAMP` (§2 lines 119-128; wu-028b precedent).
- ✅ Migration downgrade is a no-op with the Live Server comment (§2 lines 134-136).
- ✅ Per-intent transaction isolates partial failures (R1; §5.2 `_expire_single_intent`).
- ✅ `StaleMutationError` classified as expected control flow and logged at debug (R6; §5.2 loop; §6.1 tick).

---

## Summary

| # | Finding | Severity |
|---|---|---|
| Obs 1 | SKIP LOCKED in `select_expirable_intents` releases its lock before the per-intent mutation runs; the mechanism is decorative, actual serialization comes from OCC + rowcount=0. Test name `test_concurrent_sweeps_do_not_duplicate_via_for_update_skip_locked` attributes correctness to the wrong mechanism. | LOW |
| Obs 2 | `_read_intent_head_version` + `mutate_entity.get_head_for_update` split leaves a narrow concurrent-read window where a benign race surfaces as `logger.exception` + `errored_count += 1` instead of debug. R1 revision log's F8 claim of "OCC races always surface as `StaleMutationError` before the projection" does not hold for the "A commits before B's first read" interleaving. | LOW |

**Overall verdict: LOW.** All sixteen shortcut-focus items pass. The two
residual observations are cosmetic/telemetry concerns that do not block
AC1–AC4 or violate established patterns; either would be a tidy addition
to a follow-up hygiene pass. The proposal is ready for the hookpoint phase.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
