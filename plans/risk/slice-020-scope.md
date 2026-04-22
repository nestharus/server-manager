# SLICE-020 Risk: Scope

**Severity: LOW**

The proposal stays inside the WU-038A + WU-038B envelope on every binding axis: no new permissions, no new scope kinds, no new aggregate types, no Discord adapter calls, no reconciliation-run lifecycle changes, no bulk renewal, no time-travel, scheduler integration via the existing `SchedulerLoop`. The audit verbs (`permission_intent.renew/.expire`, `permission_drift.detect_expired`) are new strings but reuse existing aggregate types and authority namespaces, exactly as D12 binds.

The only scope friction is that the proposal touches a handful of files outside the strict file lists in `SLICE-020.md:41-42`. Each is necessary plumbing for the listed work units (a new column needs repository round-trip; a new endpoint needs router registration; a new task needs `configure_task_runtime` wiring; a new error class needs a mapping in `_shared.py`; a new column + service-actor seed needs a migration). None of these introduce new behavior beyond renewal API + expiry worker. They are flagged below as observations rather than gate-blockers.

---

## Verified within scope

| # | Focus | Verdict | Evidence |
|---|---|---|---|
| 1 | Every proposal step maps to WU-038A or WU-038B | ✅ | `proposal.md:18-53` — every numbered step under §1 cites an AC and binds to a WU via D-tags. |
| 2 | No new authority permissions | ✅ | D3 (`synthesis.md:222-247`) + proposal §10 item 12 (`proposal.md:1036`). Renewal & expiry both call `_require_scoped_authority("permission_intent.write", …)`; drift creation uses `permission_drift.write`. Both already exist from SLICE-014. |
| 3 | No new scope kinds | ✅ | D7 (`synthesis.md:414-447`) + proposal §6.1 service-actor scope is `"global"`; renewal/expiry use the intent's existing scope. No new `PermissionIntentScopeKind` literal added (`contracts/permissions.py` change in §3.1 only appends `expired_at`). |
| 4 | No Discord adapter changes (AC4 stable reconciliation path) | ✅ | Proposal §1 AC4 step 1 (`proposal.md:49`): "Worker never calls any Discord adapter; only writes `permission_intents.expired_at` and inserts a `permission_drift` row." §10 item 1 (`proposal.md:1025`) explicitly excludes auto-reconciliation. `actual_*` columns deliberately NULL (D9, `synthesis.md:495`) — no fabricated Discord state. |
| 5 | No new aggregate types — reuses `permission_intent` and `permission_drift` | ✅ | Every `mutate_entity` call site uses `aggregate_type="permission_intent"` (§5.1, §5.2) or `aggregate_type="permission_drift"` (§5.2 `_create_expiry_drift`). No new aggregate strings; no schema additions to `permission_drift` table. |
| 6 | Migration chain linear onto `wu_031_read_models` | ✅ | Verified by walking every `down_revision` in `migrations/versions/`: `wu_031_read_models` is the only leaf (no migration claims it as parent). Proposal §2 sets `down_revision = "wu_031_read_models"` (`proposal.md:73`) — correct. |
| 7 | Code boundaries per ticket | ⚠ Minor — see Findings 1–4 | Tightly-scoped plumbing edits exceed listed boundaries. None are cross-cutting. |
| 8 | No cross-cutting edits (no ticket/application flow changes) | ✅ | No edits to `tickets.py`, `applications.py`, `members.py`, `chapters.py`, `forms.py`, `roster.py`, `chapter_roles.py`, `chapter_templates.py`, `notifications.py`, `audit*.py`, or any other domain module outside permissions + scheduler + tasks plumbing. |
| 9 | No additions to SLICE-014 reconciliation run lifecycle | ✅ | D9 binds `reconciliation_run_id = NULL` for expiry drift (`synthesis.md:492`). Proposal §10 item 14 (`proposal.md:1038`) explicitly excludes "Any changes to reconciliation drift shapes or `_build_drift_rows` in `permission_reconciliation.py`". No edits to `services/api/app/services/permission_reconciliation.py` planned. |
| 10 | Scheduler integration reuses existing `SchedulerLoop` | ✅ | §6.3 (`proposal.md:681-720`) adds one method (`_run_permission_expiry_if_due`), one constant (`PERMISSION_EXPIRY_INTERVAL_SECONDS`), one instance var (`_last_permission_expiry_tick_at`) — mirrors `_run_ticket_sla_if_due` exactly. No new scheduler types. D8 binds (`synthesis.md:450-478`). |
| 11 | No bulk renewal or time-travel features | ✅ | §10 items 3 & 4 (`proposal.md:1027-1028`) explicitly exclude both. The renewal endpoint takes a single `intent_id` path param; no list/batch input. No "expired_at history" view planned. |

---

## Findings (LOW severity, observational)

### Finding 1 — Migration file outside listed code boundary

`SLICE-020.md:41-42` does not list any `migrations/versions/*.py` file under either WU's code boundary. The proposal adds `migrations/versions/wu-038_permission_intent_expiry.py` (§2). This is required by D1 (`expired_at` column) and D7 (service-actor seed); migrations are universally implicit plumbing for any new column or seed across this codebase. Recommend treating as in-scope by convention but noting the ticket's code-boundary cell does not enumerate migration files for any prior slice either (verify against shipped tickets). **Severity: LOW.**

### Finding 2 — Repository plumbing outside listed code boundary

`services/api/app/repositories/permissions.py` is not in either WU's code boundary, but the proposal modifies it:
- §4.1 — round-trip `expired_at` through `insert_permission_intent`, `fetch_permission_intent`, `list_permission_intents`, `_normalize_permission_intent_row`.
- §4.2 — adds `select_expirable_intents` (with `FOR UPDATE SKIP LOCKED`) and `mark_intent_expired_row`.

These are mechanically required by D1's column and D4's worker contract. Without them the new column is invisible to the service layer and the worker has nothing to claim. The edits are tightly scoped (no other repository surface changes). Recommend the ticket be updated to acknowledge `services/api/app/repositories/permissions.py` as an implicit boundary, or that the orchestrator confirm this is acceptable plumbing. **Severity: LOW.**

### Finding 3 — Endpoint package wiring outside listed boundary

Two files are touched outside the WU-038A boundary:
- `services/api/app/api/v1/endpoints/permissions/_shared.py` — extending `raise_known_permission_error` with two new isinstance branches for `NonTemporaryIntentRenewalError` and `ExpiredIntentRenewalError` (§5.3).
- `services/api/app/api/v1/endpoints/permissions/__init__.py` — adding `permissions_router.include_router(temporary_router)` (§7.2).

Both are single-spot, additive, and necessary to expose `temporary.py`'s new endpoints. They follow the same plumbing pattern used by `intents`, `drift`, and `reconciliation` routers shipped in SLICE-014. **Severity: LOW.**

### Finding 4 — Scheduler file path mismatch with ticket boundary

The ticket lists `services/api/app/contracts/scheduler.py` under WU-038B (`SLICE-020.md:42`), but the proposal modifies `services/api/app/services/scheduler.py` instead (§6.3, §9.3). Inspection shows `contracts/scheduler.py` defines `ScheduledJobCreate` / `ScheduledJobRead` Pydantic models — the wrong file for adding a `SchedulerLoop` tick. The proposal's choice of `services/scheduler.py` is correct on architectural grounds: that's where `SchedulerLoop` and `_run_ticket_sla_if_due` live. The ticket cell appears to be a typo (should read `services/api/app/services/scheduler.py`). Also missing from the ticket boundary: `services/api/app/tasks/__init__.py` (`configure_task_runtime` wiring, §6.2). Both are required by D8. **Severity: LOW.** Recommend the orchestrator either correct the ticket or accept the discrepancy as a known plumbing footprint.

### Finding 5 — Mild constant duplication

`PERMISSION_EXPIRY_MANUAL_DEFAULT_BATCH_SIZE` (in `services/permissions.py`, §9.1) and `PERMISSION_EXPIRY_BATCH_SIZE` (in `tasks/permission_expiry.py`, §9.2) both bind to `50`. D6 names only the latter. The duplication is small but the manual-trigger constant is not bound by any decision and has no test reference; the manual endpoint could simply import `PERMISSION_EXPIRY_BATCH_SIZE` from `tasks.permission_expiry`. Not a scope expansion (no new behavior), but a clarity nit. **Severity: LOW (cosmetic).**

---

## Non-findings (explicitly verified absent)

- ✅ No new `permission_intent.renew` / `permission_intent.expire` permission name (these are audit verbs, not authority strings — D3 confirmed, §10 item 12).
- ✅ No widening of `PermissionIntentUpdate` with `expired_at` (D10, §10 item 9; only `_PermissionIntentBase` gains `expired_at` for read responses).
- ✅ No new `permission_intent.status` column (D11, §10 item 8).
- ✅ No new index on `permission_intents.expired_at` (D1 binding implications, §10 item 13; existing `ix_permission_intents__temporary_expires` is reused).
- ✅ No `expired_at` on `PermissionIntentCreate` (proposal §3.1, "PermissionIntentCreate and PermissionIntentUpdate are not widened").
- ✅ No `actual_*` fabrication on expiry drift (D9, §1 AC4 step 2 — NULL is the contract).
- ✅ No new `permission_drift.status` value (D9, §10 item 14).
- ✅ No new resolution surface for expiry drift (proposal §1 AC4 step 4: reuses `POST /api/v1/permission-drift/{id}/resolve`).
- ✅ No env-var override for batch size or interval (D6 binding implications).
- ✅ No scope-filtered worker / per-chapter fan-out (D4 non-goals, §10 item 5).
- ✅ No body on `POST /expire/run` — spoof-proof actor (D5, §7.1, §10 item 6 by implication).
- ✅ No notification emission from worker (§10 item 2).
- ✅ No backwards-compatibility shims (proposal §"Guardrails", AGENTS.md No Backwards Compatibility honored).

---

## Recommendation

Pass scope risk at **LOW**. Findings 1–4 are observational: they describe plumbing edits the ticket's code-boundary cell does not enumerate but which are mechanically required by the binding decisions and are universally treated as implicit in this codebase (per the shipped pattern of every prior slice that added a column + endpoint + worker). No proposal step expands the slice's behavioral surface beyond AC1–AC4 and the WU-038A / WU-038B work-unit envelope.

If the orchestrator wants strictly tight code boundaries, a follow-up edit to `SLICE-020.md` could enumerate `migrations/versions/wu-038_permission_intent_expiry.py`, `services/api/app/repositories/permissions.py`, `services/api/app/api/v1/endpoints/permissions/_shared.py`, `services/api/app/api/v1/endpoints/permissions/__init__.py`, `services/api/app/services/scheduler.py` (correcting the `contracts/` typo), and `services/api/app/tasks/__init__.py` under the appropriate WU. Otherwise the proposal as written is consistent with how prior slices have shipped.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
