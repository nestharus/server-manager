# SLICE-014 Risk: Scope

**Severity:** LOW

Gated against `.pipeline/proposal.md` (Revision 1),
`.pipeline/synthesis.md` D1–D15, `product-strategy/tickets/SLICE-014.md`,
and AGENTS.md (Live Server Principle, No Backwards Compatibility).

## Scope Discipline Checklist

| # | Focus | Result | Evidence |
|---|---|---|---|
| 1 | Every proposal step maps to a WU | PASS | `.pipeline/proposal.md:11-22` (WU table); §1 AC→WU map; §8 test files one-to-one with WU-027 / WU-028A / WU-028B-api / WU-028B-discord (`.pipeline/proposal.md:2148-2206`). |
| 2 | No new scope kinds beyond `global\|chapter` | PASS | D1 (`.pipeline/synthesis.md:67-117`); proposal §3.1 `PermissionIntentScopeKind: TypeAlias = Literal["global", "chapter"]` (`.pipeline/proposal.md:590`); §2.1 migration drops and re-adds `permission_intents_scope_kind_valid` with `scope_kind IN ('global','chapter')` (`.pipeline/proposal.md:208-217`); same narrowing flows to `permission_drift.scope_kind` (§2.2 line 337) and `permission_reconciliation_runs.scope_kind` (§2.3 lines 442-445). No contract re-exports or aliases the wider `ScopeKind` from `services/api/app/contracts/scope.py`. |
| 3 | No scheduled reconciliation (deferred per D9) | PASS | D9 explicitly says “manual adapter-triggered runs only” (`.pipeline/synthesis.md:597-599`); §11 first bullet defers scheduled reconciliation (`.pipeline/proposal.md:2379-2382`); §2.3 note confirms service actor is not used for background jobs (`.pipeline/proposal.md:568-575`). No Celery/scheduler/cron additions anywhere in the proposal. |
| 4 | No automatic drift remediation (Discord not pushed to) | PASS | §7.3 handler only enumerates `guild.roles` and (chapter scope only) `channel.overwrites`, POSTs to API, and returns an ephemeral message (`.pipeline/proposal.md:2022-2103`). No `guild.edit_role`, `channel.set_permissions`, `role.edit`, or any Discord write APIs. Drift `reconcile` action only mutates the DB status + resolution metadata (§5.2 `_drift_originating_actor` / `mutate_projection` at `.pipeline/proposal.md:1217-1310`). AC4 test `test_handler_never_calls_drift_mutation_endpoints` (`.pipeline/proposal.md:2204`) pins read-only behaviour. |
| 5 | AC1–4 each map to concrete test cases | PASS | §8.1 AC1 (`test_create_intent_persists_full_target_and_returns_etag`, `test_patch_intent_with_stale_if_match_returns_412`, … at `.pipeline/proposal.md:2150-2159`); §8.2 AC2 (`test_list_drift_returns_intent_linked_and_orphaned_rows`, `test_resolve_drift_stale_if_match_returns_412`, … at `.pipeline/proposal.md:2163-2179`); §8.3 AC3 (`test_submit_snapshot_materializes_drift_for_mismatches`, `…_for_orphaned_actual`, `…emits_cleared_state_drift_for_missing_actual` at `.pipeline/proposal.md:2184-2195`); §8.4 AC4 (`test_submit_snapshot_idempotent_replay_returns_same_drift_set`, `test_handler_retry_reuses_run_id_no_second_run_created`, `test_handler_never_calls_drift_mutation_endpoints` at `.pipeline/proposal.md:2189-2206`). Each test carries an AC docstring per §8 preamble (`.pipeline/proposal.md:2143-2147`). |
| 6 | Code Boundary files touched exactly | MINOR (see F1, F2) | Ticket `product-strategy/tickets/SLICE-014.md:46-50` enumerates leaf files; proposal adds four plumbing files plus cosmetic migration-name variants. |
| 7 | No parallel aggregate model (D3) | PASS | D3 (`.pipeline/synthesis.md:199-249`); proposal §5.2 `resolve_permission_drift` uses `aggregate_type="permission_drift", aggregate_id=str(drift_id)` (`.pipeline/proposal.md:1313-1327`); §5.3 `_record_drift_created` issues one `mutate_entity` per drift id (`.pipeline/proposal.md:1678-1715`). Idempotency expressed only as partial unique indexes (§2.3 lines 503-518); no `permission_drift_findings` child table. |
| 8 | No new authority permissions beyond the 5 in D11 | PASS | D11 (`.pipeline/synthesis.md:670-706`) lists exactly five names. §9 (`.pipeline/proposal.md:2219-2243`) and §5 call sites reference only those five: `permission_intent.read`, `permission_intent.write`, `permission_drift.read`, `permission_drift.write`, `permission_reconciliation_run.write`. Reconciler service actor receives four (write on intents withheld — correct per D9/§9). No per-action permission splits (`acknowledge` vs `reconcile`) — §11 defers explicitly (`.pipeline/proposal.md:2390-2391`). |
| 9 | Snapshot fetch scope discipline (D13) | PASS | D13 (`.pipeline/synthesis.md:760-802`); proposal §7.3 `_build_snapshot` unconditionally walks `guild.roles` and walks `channel.overwrites` only under `if scope_kind == "chapter":` via `_channels_for_chapter(guild, scope_id)` (`.pipeline/proposal.md:2080-2103`); comment line 2102 states "D13: `global` scope does NOT walk channels". Tests `test_handler_chapter_scope_walks_chapter_channels_only`, `test_handler_global_scope_does_not_walk_channels`, and `test_handler_never_calls_fetch_channel_or_fetch_member` (`.pipeline/proposal.md:2199-2205`) pin cache-only discipline. |
| 10 | Migration chain linear onto `wu_035_application_interview` | PASS | D14 (`.pipeline/synthesis.md:806-815`); proposal §2.1 `down_revision = "wu_035_application_interview"` (`.pipeline/proposal.md:185`); §2.2 chains from wu-027 (`.pipeline/proposal.md:248`); §2.3 chains from wu-028a (`.pipeline/proposal.md:410`). Strictly linear, no branching. |
| 11 | No cleanup of unrelated modules | PASS | All diffs target permission contracts/repo/services/endpoints/tests, the three new migrations, and the Discord permissions surface. Single removal is the lenient `update_permission_drift_status` in `services/api/app/services/permissions.py` (§5.2 note at `.pipeline/proposal.md:1335-1338`) — this file is in the WU-028A Code Boundary, and removal is justified by the strict `resolve_permission_drift` replacement per AGENTS.md No Backwards Compatibility. |
| 12 | Legacy substrate replacement is in-place, no parallel tables | PASS | D2 widens `permission_drift` via `op.add_column` / `op.alter_column` / `op.create_check_constraint` (`.pipeline/proposal.md:273-388`). D1 narrows `permission_intents_scope_kind_valid` by dropping and re-adding the CHECK in place (`.pipeline/proposal.md:208-217`). The only new table (`permission_reconciliation_runs`) is a genuinely new aggregate — `.pipeline/synthesis.md:55-57` confirms no prior run table exists. No `permission_drift_findings` or parallel intent table introduced. All three migration `downgrade()` bodies are Live-Server-Principle no-ops (`.pipeline/proposal.md:227-232`, `391-394`, `561-565`). |

## Findings

### F1 — LOW — Plumbing files outside the strict WU Code-Boundary table

The ticket enumerates leaf files (contract, repository, service, endpoint, test, migration). The proposal adds four plumbing files not listed in any WU row:

- `services/api/app/api/v1/endpoints/permissions/__init__.py` — subpackage aggregator router (`.pipeline/proposal.md:1736-1748`).
- `services/api/app/api/v1/endpoints/permissions/_shared.py` — shared `get_db`, `parse_if_match_strong`, `set_etag`, `raise_known_permission_error` (`.pipeline/proposal.md:1945-1957`).
- `services/api/app/api/v1/router.py` — one-line `router.include_router(permissions.router)` mount (`.pipeline/proposal.md:1750-1760`).
- `services/discord/app/commands/permissions.py` — registers `/reconcile-permissions` and dispatches to the handler (`.pipeline/proposal.md:2115-2133`).

**Why LOW.** Each file is mechanically required to activate the declared boundary files: the endpoint modules cannot be mounted without `router.include_router`, the subpackage cannot be imported without `__init__.py`, the error helper is referenced by every endpoint in §6.2–§6.4, and the handler in `services/discord/app/handlers/permissions.py` is dead code without a command registration. SLICE-011 / SLICE-012 / SLICE-021 set the same precedent — `services/api/app/api/v1/endpoints/applications/` already ships `__init__.py` + `_shared.py`, and `services/discord/app/commands/` already holds sibling command files for chapters, tickets, and application lifecycle. All four stay strictly inside the permissions domain; none touch unrelated modules.

**Resolution.** None required. Implementation should keep these files to their stated purpose (aggregation, error mapping, slash-command dispatch) and not grow reconciliation logic into them.

### F2 — LOW — Migration filenames diverge from ticket literals

Ticket row WU-027 names `migrations/versions/wu-027_permission_intents.py`; proposal uses `wu-027_permission_intents_refinements.py` (`.pipeline/proposal.md:176, 184`). Ticket row WU-028A names `wu-028a_permission_drift_api.py`; proposal uses `wu-028a_permission_drift_widening.py` (`.pipeline/proposal.md:238, 247`). Ticket WU-028B-api row lists no migration file, but `wu-028b_permission_reconciliation_runs.py` is unavoidable — the new `permission_reconciliation_runs` table (D4), the `reconciliation_run_id` FK + partial unique indexes (D3), and the `permission-reconciler` service-actor seed (D9) must all exist before WU-028B-api service code can insert a run (`.pipeline/proposal.md:400-566`).

**Why LOW.** The wu-027 and wu-028a filenames still carry their WU prefix and sit under `migrations/versions/`, so mapping to the ticket is unambiguous. The wu-028b addition is structural scaffolding for WU-028B-api’s leaf files; without it the WU cannot run. No existing migration is modified, the chain remains strictly linear from the head, and `downgrade()` is a no-op with a Live-Server-Principle comment in every file.

**Resolution.** None required for scope. Implementation may either keep the descriptive suffixes or rename to the ticket literals (`wu-027_permission_intents.py`, `wu-028a_permission_drift_api.py`, `wu-028b_permission_reconciliation_runs.py`) without functional change.

## Out-of-Scope Items the Proposal Correctly Defers

Cross-checked against synthesis D4/D8/D9/D13/D15 and §11 (`.pipeline/proposal.md:2375-2421`):

- Automatic / scheduled reconciliation.
- `requested → failed` TTL automation.
- “Accept orphaned drift creates an intent” convenience flow.
- Drift notifications / alerting.
- `GET /api/v1/permission-reconciliation/runs/{run_id}` read endpoint.
- Per-action permission splits (`acknowledge` vs `reconcile` vs `accept`).
- Cross-run drift dedup; per-scope uniqueness when `reconciliation_run_id IS NULL`.
- JSONB snapshot archive on the run row.
- Cross-service E2E tests; property-based diff fuzz.
- Member-level channel-overwrite serialization.
- New `policy_type` / seeded operator policy.
- Denial-audit rows (R9 clarification inherits shipped `RequireAuthority` behaviour — overrides log, denials don't).
- Backwards-compatibility shims for the removed `update_permission_drift_status`.

## Summary

All twelve scope focus items pass materially. Scope kinds stay at `global|chapter` at every layer (contract, service, three CHECK constraints). Drift is widened in place per D2; no parallel `permission_drift_findings` or shadow intent table is introduced. The only new table (`permission_reconciliation_runs`) is a legitimately new aggregate mandated by D4, not a shadow of existing substrate. Drift remains a per-row aggregate (D3); resolution mutations go through `mutate_entity("permission_drift", drift_id)` rather than a run aggregate. Exactly five permission names are introduced (D11). The Discord adapter is read-only against Discord and idempotent via `run_id` (D12 + AC4); no scheduled remediation, no local drift store. Every AC has at least one AC-tagged test in §8. The migration chain is strictly linear from `wu_035_application_interview`.

The two LOW findings (F1, F2) describe plumbing-file expansions and cosmetic migration-name variants that shipped precedent (SLICE-011 / SLICE-012 / SLICE-021 / WU-037) already normalises inside a slice. Neither admits a parallel system nor expands lifecycle beyond the WU table.

**Severity: LOW. No resolution required.**

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
