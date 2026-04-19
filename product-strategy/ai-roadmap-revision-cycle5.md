# AI Roadmap Revision Cycle 5

## Scope

Cycle 5 revised `product-strategy/ai roadmap.md` to clear the remaining dependency and decomposition issues from the latest risk reports without changing roadmap scope, phase count, or total work unit count.

## Applied Changes

### Dependency fixes

1. **F-1: `WU-028B-api` removed from the same parallel cohort as `WU-028A`**
   - Phase 2 cohort 2 now contains:
     - `[WU-019 + WU-022 + WU-025A-create + WU-028A + WU-029B-materialize + WU-030B]`
   - Added a new intermediate Phase 2 cohort:
     - `[WU-028B-api]`
   - Phase 2 cohort 3 remains:
     - `[WU-020 + WU-023 + WU-025A-events + WU-025B + WU-028B-discord + WU-029B-deliver + WU-032]`
   - Updated the Dependency Graph, Parallelization Map, and the affected `Parallelizable with` lists.
   - Cohort 2 max concurrency dropped from `7` to `6`.

2. **F-2: split ticket message contracts away from `contracts/tickets.py`**
   - `WU-025A-events` now owns `services/api/app/contracts/ticket_messages.py`.
   - `WU-025B` continues to own `services/api/app/contracts/tickets.py`.
   - `WU-025C` was aligned to the same `ticket_messages.py` contract surface because it is also a message-event unit.
   - This removes the Phase 2 cohort 3 shared-file collision between `WU-025A-events` and `WU-025B`.

3. **F-3: Alembic merge-head reconciliation is now explicit**
   - Added a Parallelization Map note:
     - after any cohort with multiple migration-writing work units, the next cohort cannot start a new migration-writing unit until one Alembic merge revision collapses the parallel heads
     - that merge is an acceptance criterion of the first started migration-writing unit in the next cohort, or a short pre-cohort reconciliation task when the next cohort is otherwise migration-free

4. **F-4: `WU-040B` now declares `services/api/app/contracts/compliance.py` in its code boundary**

### Decomposition fixes carried forward

1. Added missing contract-file ownership to the code boundaries of the work units that introduce new contract types and previously omitted their owning contract modules:
   - `WU-015A`, `WU-015B`, `WU-017`, `WU-028A`, `WU-029B-materialize`, `WU-029B-deliver`, `WU-032`, `WU-035`, `WU-036`, `WU-037`, `WU-038A`, `WU-038B`, `WU-040B`, `WU-041A`, `WU-042`, `WU-043A`, `WU-043B`, `WU-044A`, `WU-044B`, `WU-045A-applications`, `WU-045A-tickets`, `WU-045B`

2. Added an explicit decomposition justification to `WU-026` instead of splitting it:
   - the Discord open and moderation commands stay in one unit because they share the same thread-bootstrap, transcript-correlation, and command-routing seam

## Consistency Checks

1. Re-read the revised Phase 2 work units and confirmed:
   - `WU-028B-api` depends on `WU-028A`
   - no Phase 2 cohort groups a work unit with one of its direct dependencies

2. Re-read the ticket lifecycle work units and confirmed:
   - `WU-025A-events` and `WU-025B` no longer write the same contract file
   - `WU-025C` now follows the split contract ownership model

3. Re-read the work units called out by the decomposition report and confirmed each revised unit now declares its contract writer path in the code boundary where applicable.

4. Re-read the Dependency Graph and Parallelization Map and confirmed:
   - both now reflect the new intermediate Phase 2 cohort for `WU-028B-api`
   - Phase 2 concurrency is `7`, `6`, `1`, `7`, `3`
   - roadmap totals remain unchanged at `75` work units across `5` roadmap phases

## Result

Cycle 5 preserves roadmap coverage and ordering while removing the named dependency contradiction, the shared ticket-contract write collision, the undocumented Alembic parallel-head gap, and the missing contract ownership declarations called out by the latest risk reports.
