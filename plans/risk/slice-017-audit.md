# SLICE-017 Audit Risk Assessment

**Severity: LOW**

The SLICE-017 proposal (`.pipeline/proposal.md`) is a read-only operational
overview backed by a single cursor row. It bypasses the audit substrate by
design (synthesis D10) — cursor advancement is infrastructure bookkeeping,
not a domain transition — and reads only from synchronous projection tables
already maintained by the write path. The audit-discipline focus items were
walked one by one against the shipped substrate
(`services/api/app/services/mutations.py`,
`services/api/app/services/scheduler.py:178-229`,
`services/api/app/api/v1/endpoints/permissions/{drift.py,_shared.py}`,
`services/api/app/repositories/applications.py`,
`services/api/app/contracts/ticket_categories.py`) and the proposal
satisfies each by construction or by binding to the shipped precedent named
in `synthesis.md` D6 / D8 / D10. Three LOW observations are recorded below
— none block the risk gate; all are stylistic or repo-wide architectural
patterns that the proposal inherits rather than introduces.

---

## Focus Walk-Through

| # | Focus | Verdict | Primary evidence |
|---|-------|---------|------------------|
| 1 | No direct INSERTs into write-side tables from the read-model path. | PASS | `.pipeline/proposal.md:486-523` (`read_operational_overview`) and `:756-797` (endpoint) import only `require_scoped`, count helpers, `load_cursor`, `max_event_id_settled`. The §8 guardrail and §5.1 module docstring (`.pipeline/proposal.md:1077-1080, 419-420`) bind the read path to SELECT-only and exclude `mutate_entity` / `mutate_projection` / `append_state_change` / `advance_aggregate_head`. Mirrors the shipped `list_drift_endpoint` pattern at `services/api/app/api/v1/endpoints/permissions/drift.py:63-78`. |
| 2 | Cursor advance via `advance_cursor`: direct UPDATE (not `mutate_entity`) with OCC. | PASS | Synthesis D10 binds the projector to a plain `UPDATE read_model_cursors ... WHERE projection_name = ...` with no audit emission (`.pipeline/synthesis.md:540-550`). Proposal §5.1.1 (`.pipeline/proposal.md:432-461`) wraps the advance in `with connection.transaction()`, locks the cursor row via `load_cursor` `FOR UPDATE`, and §4.1 (`.pipeline/proposal.md:334-350`) names the OCC clause `WHERE projection_name = :name AND version = :expected_version` with `CursorVersionConflictError` on zero rows. Belt (FOR UPDATE) + suspenders (OCC) is correct; the OCC alone is sufficient for the cursor's integrity, and either layer in isolation would also be correct. |
| 3 | Authority check happens BEFORE any data read on the overview endpoint (AC4 — 403 for unauthorized). | PASS | Proposal §5.1.2 (`.pipeline/proposal.md:485`) places `_require_overview_authority(db, actor, scope_kind, scope_id)` as the first statement of `read_operational_overview`, before `with db.connection()` opens. `require_scoped` itself reads only authority tables (`list_grants_for_grantee`, `evaluate`) at `services/api/app/api/v1/endpoints/permissions/_shared.py:71-89`, so denial returns `PermissionError` without ever touching `applications`, `tickets`, `permission_drift`, or `deferred_effects`. The endpoint then maps `PermissionError → HTTP 403` via `raise_known_permission_error` (`_shared.py:135-139`), satisfying AC4. |
| 4 | `operational_overview.read` treated consistently with `noun.read` peers. | PASS | Repo grep confirms peers (`permission_drift.read`, `chapter.read`, `ticket.read`, `notification.read`, `permission_intent.read`) are bare strings used at `require_scoped` call sites with no central enum. Proposal §9 (`.pipeline/proposal.md:972-1003`) explicitly notes "no enum or registry mutation" and points the projector's grant at the **distinct** `read_model.write` permission (D7 / D10) — the projector does not read the overview, the operator does. The two namespaces are correctly separated. |
| 5 | Failure modes — worker failure logged, not swallowed silently; cursor advance failure rolls back cleanly. | PASS | Proposal §5.3 (`.pipeline/proposal.md:665-683`) mirrors the shipped `_run_ticket_sla_if_due` at `services/api/app/services/scheduler.py:212-229` exactly: the `_last_read_model_tick_at = now` assignment happens **outside** the `try` block, the `try / except logger.exception` swallows any exception from the worker thread, and the scheduler loop continues to the next branch. A `CursorVersionConflictError` raised inside the transaction in §5.1.1 unwinds the `with connection.transaction()` context cleanly and propagates through the bare worker wrapper (§5.2 `.pipeline/proposal.md:632-635`, no try/except) into the scheduler's `except Exception → logger.exception`. The next 10s tick retries from the (still un-advanced) cursor. |
| 6 | No leaking of scoped data across scopes — chapter overview filters properly. | PASS | Proposal §4 (`.pipeline/proposal.md:361-391`) names the chapter predicates: `applications.target_scope_kind = 'chapter' AND target_scope_id = :scope_id`; `tickets.category_snapshot #>> '{routing_scope, scope_kind}' = 'chapter' AND #>> '{routing_scope, scope_id}' = :scope_id`; `permission_drift.scope_kind = 'chapter' AND scope_id = :scope_id`. The `routing_scope` JSONB shape (`scope_kind`, `scope_id`) is the canonical contract from `services/api/app/contracts/ticket_categories.py` (RoutingScope), so the JSONB path is sound. Chapter-scoped `pending_deferred_effects_count` is hard-wired to `0` (D15) because `deferred_effects` has no first-class scope column — this is a deliberate under-reporting of the chapter view (acknowledged), not a cross-scope leak. |
| 7 | Stale signal correctness — counts remain accurate when projector is down. | PASS | `mutate_entity → mutate_projection` (`services/api/app/services/mutations.py:94-185`) writes the per-subsystem projection (`applications`, `tickets`, `permission_drift`) **synchronously in the same transaction** as the state-change row. Proposal §5.1.2 (`.pipeline/proposal.md:486-499`) reads counts directly from those tables, not from any read-model-projector-derived surface. Therefore: 10-minute projector outage → cursor lag triggers `is_stale = True` per D5 thresholds, but the four counts continue to reflect the latest committed write-path mutations. Module docstring at `.pipeline/proposal.md:419-420` ("counts are always fresh from synchronous projections; `is_stale` signals projector liveness only") binds the contract. |
| 8 | No `.read` authority bypass via direct repository import. | LOW (architectural) | The count helpers in proposal §4.1 (`count_open_applications`, `count_open_tickets`, `count_pending_deferred_effects`, `count_active_drift`) are bare module-level functions in `services/api/app/repositories/read_models.py`. Any future caller that imports them outside `services/read_models.py` would skip `_require_overview_authority`. This matches the repo-wide convention — `services/api/app/repositories/applications.py` and `repositories/tickets.py` are the same shape — and is enforced by code review, not architecturally. See Finding 1. |
| 9 | Projector worker actor identity. | PASS | Proposal §2.1 step 3 (`.pipeline/proposal.md:172-211`) seeds the `read-model-projector` service-actor grant with `["read_model.write"]` at global scope, guarded by the **both-direction** containment pair (`permissions @> '...' AND permissions <@ '...'`) imported verbatim from `migrations/versions/wu-028b_permission_reconciliation_runs.py:127-163`. Per D10 the projector emits **zero** `activity_actions` / `activity_state_changes` rows, so no `actor_kind` / `actor_id` is ever written for cursor advances — the seeded grant exists only to provide a stable identity if a future slice grants the projector mutation rights. Consistent with the existing shipped pattern where `ticket_sla_worker_tick` and `archive_worker_tick` likewise do not emit per-tick audit rows. |

---

## Findings

### Finding 1 — LOW — Repository count functions are public; authority enforcement lives only at the service layer

- **File reference.** `.pipeline/proposal.md:320-392` (§4.1 — repository
  module surface), `.pipeline/proposal.md:485-523` (§5.1.2 —
  service-layer authority gate), shipped precedent at
  `services/api/app/repositories/applications.py:11-38`,
  `services/api/app/repositories/tickets.py`,
  `services/api/app/repositories/permission_drift.py`.
- **Evidence.** `services/api/app/repositories/read_models.py` exposes
  `count_open_applications`, `count_open_tickets`,
  `count_pending_deferred_effects`, and `count_active_drift` as bare
  module-level functions. The single authority check
  (`_require_overview_authority` at proposal `:549-555`) lives in the
  service module. Any future endpoint that imports a count helper
  directly — or any internal caller that bypasses
  `read_operational_overview` — skips the authority gate. Unit tests
  catching this regression require an import-graph or call-graph check,
  not a behavioural assertion.
- **Severity.** LOW. The proposal is repeating the repo-wide convention
  (the existing `permission_drift.list_permission_drift`,
  `tickets.list_*`, and `applications.list_*` all share this shape), so
  SLICE-017 introduces no new shortcut. The class of bug — "future
  endpoint forgets to call `require_scoped`" — is a perennial review
  responsibility in this codebase, not a SLICE-017-specific gap. The
  one read-only endpoint introduced here (`GET /operations/overview`)
  routes through the service layer correctly.
- **Recommendation.** None required for the gate. Optional symmetry
  improvement: add a one-line module docstring at the top of
  `services/api/app/repositories/read_models.py` stating "All callers
  must enforce `operational_overview.read` (or higher) at the service
  layer before invoking these helpers." This is a doc-only nudge and
  matches what some other repository modules already do at the top of
  the file.

### Finding 2 — LOW / INFORMATIONAL — `load_cursor` `FOR UPDATE` semantics described inconsistently across §4.1 and §5.1.2

- **File reference.** `.pipeline/proposal.md:327-332` (§4.1
  `load_cursor` SQL block — `FOR UPDATE   # held only when called from
  the projector path`), `.pipeline/proposal.md:538-542` (§5.1.2 — "the
  same repository function is reused; `FOR UPDATE` is applied only from
  the projector path by wrapping the call inside
  `connection.transaction()`"), `.pipeline/proposal.md:463-466`
  (binding implication asserting `FOR UPDATE` is sufficient on its
  own).
- **Evidence.** The §4.1 SQL contains `FOR UPDATE` unconditionally; if
  the read endpoint reuses the same function, the lock clause is
  always sent to Postgres regardless of whether the caller wraps the
  call in `connection.transaction()`. The proposal acknowledges this
  by floating an "optional `lock: bool` kwarg" in §5.1.2 but does not
  pick a path. The integrity of the cursor advance does not depend on
  this — the `WHERE version = :expected_version` OCC clause in
  `advance_cursor` (§4.1) is the actual atomicity guarantee, and
  `FOR UPDATE` in the read endpoint at worst takes a brief shared
  lock against concurrent projector ticks (and is released on
  transaction boundary or autocommit).
- **Severity.** LOW. No audit-discipline impact: the cursor row is
  the only state involved, the OCC check is correct, and the read
  path does not read or write audit tables. The risk is a future
  reader misreading the locking semantics and adding a different
  lock pattern in a follow-up slice.
- **Recommendation.** Resolve the ambiguity in implementation by
  either (a) splitting into `load_cursor_for_update(connection, ...)`
  used only by the projector and `load_cursor(connection, ...)` used
  by the read path, or (b) adding the `lock: bool = False` kwarg the
  §5.1.2 note already proposes. The implementation agent can decide;
  reviewers should not have to infer locking from call-site context.

### Finding 3 — LOW / INFORMATIONAL — Endpoint `except Exception` net is wide, but matches the shipped drift-endpoint precedent

- **File reference.** `.pipeline/proposal.md:788-797` (§7.1 — endpoint
  `try/except Exception → raise_known_permission_error`), shipped
  precedent at
  `services/api/app/api/v1/endpoints/permissions/drift.py:63-78` and
  `services/api/app/api/v1/endpoints/permissions/_shared.py:92-145`.
- **Evidence.** The endpoint catches `Exception` and routes everything
  through `raise_known_permission_error`. That helper raises
  `HTTP 403` for `PermissionError`, maps a small set of known
  exceptions to typed HTTP responses, and re-raises anything else
  unchanged (`_shared.py:145`). For SLICE-017 the only failure mode
  the service can raise inside the try-block is `PermissionError`
  (every other exception is a programming error or DB outage), so the
  wide net is harmless and the 403 mapping is correct.
- **Severity.** LOW / informational. The pattern is shipped and
  consistent with the drift endpoint; SLICE-017 does not introduce
  it.
- **Recommendation.** None. If a future refactor narrows the catch
  to `except PermissionError`, do it codebase-wide rather than
  asymmetrically here.

---

## Summary

The SLICE-017 proposal is **audit-discipline LOW**. Every focus item
either (a) is satisfied by binding to a shipped precedent
(`require_scoped` + `raise_known_permission_error` for the authority
gate, scheduler `try/except logger.exception` for resilience,
synchronous `mutate_projection` for count freshness) or (b) is
deliberately out of scope per a binding synthesis decision (no audit
emission for cursor advances per D10; no chapter-scoped deferred
effects per D15). The cursor advance correctly uses a plain
`UPDATE read_model_cursors` with explicit OCC (`WHERE version =
:expected_version`) and `FOR UPDATE` row-locking, both of which roll
back cleanly on `CursorVersionConflictError`. The read path is
SELECT-only, never imports any `mutate_*` symbol, and the authority
check executes before any SELECT on the data tables. Counts are
sourced from synchronous per-subsystem projections so a 10-minute
projector outage flips `is_stale` to `True` without making the count
fields stale. The three LOW findings (public count repository
functions, ambiguous `FOR UPDATE` semantics in `load_cursor`, wide
`except Exception` in the endpoint) are stylistic or repo-wide
patterns that SLICE-017 inherits and does not introduce; none block
the risk gate.

---

## AC Traceability

- **AC1 (causal-order resume + restart from persisted cursor).** Items
  2 and 5b verify the OCC + transaction discipline that backs cursor
  resume; D1 + D2 + D6 bind the SQL.
- **AC2 (read-model lag does not block writes).** Items 1 and 7
  confirm the read path imports no write primitive and the
  synchronous projections are independent of projector liveness; D14
  binds the contract.
- **AC3 (overview reads only from projection tables).** Item 1 (no
  write coupling) and item 6 (chapter scope predicates target
  whitelisted columns) confirm SELECT-only reads against the six
  tables enumerated in D8.
- **AC4 (stale signal + 403 for unauthorized).** Item 3 (authority
  check first), item 4 (consistent `noun.read` permission), item 7
  (counts fresh while `is_stale` is true), and item 9 (projector
  identity isolated from operator authority) jointly satisfy the
  staleness signaling and authorization requirements.
