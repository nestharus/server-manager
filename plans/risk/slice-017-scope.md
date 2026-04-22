# SLICE-017 Risk: Scope

**Severity:** LOW

Gated against `.pipeline/proposal.md`, `.pipeline/synthesis.md` D1–D15,
`product-strategy/tickets/SLICE-017.md`, and `AGENTS.md`
(Live Server Principle, No Backwards Compatibility, No Deferred Stubs,
Test/Code agent separation).

## Scope Discipline Checklist

| # | Focus | Result | Evidence |
|---|---|---|---|
| 1 | Every proposal step maps to WU-031 or WU-032 | PASS | Proposal §1 routes AC1 steps 1–7 to WU-031 (`proposal.md:32-71`), AC2 step 3 to WU-031 (`proposal.md:72-88`), AC3 steps 1–3 and AC4 steps 1–3 to WU-032 (`proposal.md:89-131`). §8 tests split WU-031 → `test_read_models.py` and WU-032 → `test_operational_views.py` (`proposal.md:839-968`). §12 AC Traceability closes the loop (`proposal.md:1092-1103`). |
| 2 | No new projection beyond `operational_overview` (D3) | PASS | §3.2 defines `PROJECTION_NAMES: frozenset[str] = frozenset({OPERATIONAL_OVERVIEW_PROJECTION_NAME})` (`proposal.md:284`). §2.1 migration seeds only the `operational_overview` cursor row (`proposal.md:164-170`). §11 first bullet explicitly out-of-scopes "Additional projection cursors beyond `operational_overview`" (`proposal.md:1042-1044`). |
| 3 | No materialized snapshot table (D3 non-goal) | PASS | §2.2 states "No snapshot table (D15)" (`proposal.md:216-219`). §11 first bullet explicitly excludes `operational_overview_snapshot` (`proposal.md:1040-1041`). Migration creates only `read_model_cursors` (`proposal.md:149-160`); overview counts are computed live from existing projection tables per §5.1.2 (`proposal.md:476-524`). |
| 4 | No Discord interactions in this slice | PASS | §11 explicitly out-of-scopes "Discord-side surface for the overview" quoting the ticket's "none in this slice" (`proposal.md:1062-1063`). No imports from `services/discord/` anywhere in the proposal. §7.1 endpoint has no Discord handler dispatch; §5.3 scheduler wiring has no Discord notifier. |
| 5 | No write-side mutations from read path (D8) | PASS | §1 AC2 step 1 pins the rule: "The projector only updates `read_model_cursors`. It never calls `mutate_entity`, `mutate_projection`, `append_state_change`, or `advance_aggregate_head`" (`proposal.md:74-79`). §5.1.2 read-path comment: "The read path never opens a writable transaction; no `mutate_*` symbol is imported into this module" (`proposal.md:531-532`). §10 Guardrails enforces the same: "the service and repository modules do not import `mutate_entity`…" (`proposal.md:1076-1079`). §1 AC2 step 3 confirms the projector uses a plain `UPDATE read_model_cursors` — no audit emission (`proposal.md:86-88`). |
| 6 | No new authority permission beyond `operational_overview.read` | PASS (see F1) | §9 centres on `operational_overview.read` (D7, `proposal.md:974-1002`). The service-actor grant names `read_model.write` per D10 (`proposal.md:176-210`); D10 is binding in synthesis (`synthesis.md:523-572`) and the permission is authority-side only — not referenced at any endpoint. §11 does not add `operations.*` or `operational_overview.write`. See F1 for the `read_model.write` note. |
| 7 | Code boundaries from ticket exactly | PASS (see F2) | Ticket table lists seven leaf files (`SLICE-017.md:38-41`); proposal creates all seven with the exact paths (`proposal.md:38,57,62-65,137,225,320,414,609,742`). Three plumbing edits land in existing files (`tasks/__init__.py`, `services/scheduler.py`, `api/v1/router.py`) — see F2. |
| 8 | Migration chain linear onto `wu_028b_permission_reconciliation_runs` | PASS | §2.1 pins `revision = "wu_031_read_models"` and `down_revision = "wu_028b_perm_reconciliation_runs"` (`proposal.md:141-142`). §2.2 confirms WU-032 adds zero migrations (`proposal.md:216-219`). Matches D13 (`synthesis.md:681-701`) and the resolved head in `synthesis.md:75-76`. No branching, no second migration. |
| 9 | No retrofitting of existing aggregate tables | PASS | §4.1 query docstrings show SELECT-only access to `applications`, `tickets`, `deferred_effects`, `permission_drift` (`proposal.md:361-392`); no `ALTER TABLE` on any existing table in §2.1 — the migration only creates `read_model_cursors` and seeds one `authority_grants` row (`proposal.md:147-205`). §8 D8 whitelist: "six listed in D8" (`proposal.md:94-97`). |
| 10 | Scheduler integration reuses existing SchedulerLoop | PASS | §5.3 extends `SchedulerLoop` with `_last_read_model_tick_at`, `_run_read_model_projector_if_due`, and a single invocation from `_tick` after `_run_ticket_sla_if_due` (`proposal.md:642-690`). The new method "mirrors `_run_ticket_sla_if_due`" exactly — interval gate, `asyncio.to_thread`, `try/except logger.exception` — and §5.4 registers the worker via the existing `configure_task_runtime()` rather than a new runtime path (`proposal.md:694-715`). No new `asyncio.create_task`, no parallel loop, no separate worker process. |
| 11 | Staleness thresholds defined as constants | PASS | §3.2 / §10 declare module-level `STALE_EVENT_THRESHOLD: int = 100`, `STALE_TIME_THRESHOLD: timedelta = timedelta(minutes=5)`, `MIN_AGE_SECONDS: int = 5`, `READ_MODEL_PROJECTOR_INTERVAL_SECONDS = 10` (`proposal.md:286-298,1017-1027`). §5.1.4 `_compute_staleness` references the constants, never literals (`proposal.md:568-597`). §8.2 tests 4 and 5 monkeypatch these constants rather than using magic numbers (`proposal.md:932-942`). |
| 12 | SLICE-008/009/014 foundations reused, no re-implementation | PASS | §4.1 reads `applications.state` via `OPEN_APPLICATION_STATES` (SLICE-008 projection; `proposal.md:361-368,300-307`), `tickets.terminal_at` (SLICE-009 projection; `proposal.md:370-377`), `deferred_effects.status` (SLICE-009 substrate; `proposal.md:378-383`), `permission_drift.status/scope_*` (SLICE-014 projection; `proposal.md:385-392`). §5.1.3 reuses `require_scoped` from the SLICE-014 shared helper (`services/api/app/api/v1/endpoints/permissions/_shared.py:71-89`), not a new authority evaluator (`proposal.md:547-564`). §7.1 endpoint reuses `get_db`, `raise_known_permission_error`, and the drift endpoint validation shape (`proposal.md:752-798`). No parallel application/ticket/drift repository is introduced. |

## Findings

### F1 — LOW — `read_model.write` service-actor permission is a second name beyond `operational_overview.read`

Focus #6 asks for "no new authority permission beyond `operational_overview.read`". The proposal seeds `read_model.write` at the projector service actor (`proposal.md:175-210`) in addition to declaring `operational_overview.read` at the endpoint call site (`proposal.md:547-564,1028-1031`).

**Why LOW.**

- D10 is binding in synthesis and explicitly mandates the grant: "Actor id: `read-model-projector` … Permissions: `["read_model.write"]`" (`synthesis.md:525-538`).
- D10 Binding implications expressly state the name is "authority-side only; it is not referenced by any endpoint, because the projector is an internal worker invoked by the scheduler" (`synthesis.md:563-565`). No endpoint — overview or otherwise — calls `require_scoped(..., "read_model.write")`, so no new authority surface is exposed to callers.
- D10 Non-goals bar audit emission for cursor advances; the grant exists solely to mirror the `notification-dispatcher` / `permission-reconciler` / `sla-worker` / `chapter-archiver` service-actor convention, keeping future slices consistent when a projector is given the right to write materialised projection rows.
- §11 (`proposal.md:1055-1058`) reaffirms no audit trail, no domain actions attributed to `read-model-projector` — the grant is idle authority metadata, not an enforced gate.

**Resolution.** None required. Implementation should keep `read_model.write` strictly as the service-actor grant (no new endpoint should require it, no enum should surface it) and preserve the D10 no-audit stance.

### F2 — LOW — Three plumbing edits land outside the ticket's Code Boundary table

The ticket Code Boundary (`SLICE-017.md:38-41`) enumerates leaf files only. The proposal also edits three existing files:

- `services/api/app/tasks/__init__.py` — appends `configure_read_models(db=db)` to `configure_task_runtime()` (`proposal.md:694-715`).
- `services/api/app/services/scheduler.py` — adds interval constant, `_last_read_model_tick_at`, `_run_read_model_projector_if_due`, and invocation from `_tick` (`proposal.md:643-690`).
- `services/api/app/api/v1/router.py` — one-line `router.include_router(operations.router, tags=["operations"])` mount (`proposal.md:812-828`).

**Why LOW.**

- Each edit is mechanically required to activate declared boundary files: the projector worker in `tasks/read_models.py` is inert without `configure_task_runtime()` registration; the scheduled handler contract in the ticket Technical Specification (`SLICE-017.md:26`) cannot run without `SchedulerLoop` wiring; the endpoint in `endpoints/operations.py` is unreachable without router inclusion.
- Both scheduler wiring (D6, `synthesis.md:341-400`) and router registration (D9, `synthesis.md:477-521`) are binding in synthesis, so these edits were sanctioned at the synthesis gate rather than added by the proposal.
- The SLICE-014 scope risk report accepted the same precedent for equivalent plumbing files (`plans/risk/slice-014-scope.md:28-39`), and the current proposal's edits are narrower in scope — one new line in `tasks/__init__.py`, one new `include_router` call, one new `if_due` branch mirroring `_run_ticket_sla_if_due` exactly.
- None of the three edits touch unrelated modules, mutate write-path behaviour of existing workers, or introduce abstractions beyond mirroring `ticket_sla` / existing routers.

**Resolution.** None required. Implementation must keep the edits minimal and mirror existing `_run_ticket_sla_if_due` / `include_router` shapes verbatim; any divergence (e.g. adding middleware, batch-size configuration, or a registry indirection) should be rejected as scope creep.

## Out-of-Scope Items the Proposal Correctly Defers

Cross-checked against synthesis D15 and proposal §11 (`proposal.md:1035-1067`):

- `operational_overview_snapshot` / any materialised cross-subsystem snapshot table.
- Additional `read_model_cursors` rows beyond `operational_overview`.
- Chapter-scoped `pending_deferred_effects_count` (hard-wired `0` per D15).
- `member` scope on the overview.
- Cursor-lag integer as a first-class response field.
- Audit emission for cursor advances (`activity_actions` / `activity_state_changes` rows authored by `read-model-projector`).
- Retry policy / backpressure / circuit breaker for the projector beyond `try/except logger.exception`.
- Any write / mutation endpoint under `/operations/**`.
- Discord-side overview surface; UI / frontend consumers.
- Operator alerting / paging when `is_stale=True`.
- Historical / time-series overview views.
- Pagination, ETag, caching on the overview endpoint.

## Summary

Proposal holds to the scope envelope set by SLICE-017 and synthesis D1–D15. All twelve focus items pass; two LOW findings (F1 on the `read_model.write` service-actor grant, F2 on three necessary plumbing edits outside the ticket's Code Boundary table) are both explicitly sanctioned by binding synthesis decisions (D10 and D6/D9 respectively) and precedented by prior slices. No materialised snapshot table, no second projection, no Discord surface, no write-side coupling, no parallel scheduler, no new scope kind, and no expansion of the authority surface beyond `operational_overview.read` are introduced.

**Recommendation:** Proceed to hookpoint research. No proposal revision required on scope grounds.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
