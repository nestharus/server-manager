# AI Roadmap Revision Report

## Scope

Revised `product-strategy/ai roadmap.md` to clear the blocking dependency findings first, then the decomposition findings, while keeping stable numbering where practical by introducing suffix IDs.

Current totals:

- Previous work-unit count: `45`
- Revised work-unit count: `56`

## Splits Applied

### Phase 0 foundation splits

- `WU-006` split into `WU-006A` (Permission Intent Foundation) and `WU-006B` (Permission Drift Foundation).
- `WU-007` split into `WU-007A` (Chapter Template Foundation), `WU-007B` (Chapter Role Foundation), and `WU-007C` (Roster Foundation).
- `WU-008` split into `WU-008A` (Scheduler Foundation) and `WU-008B` (Deferred-Effect Foundation).

### API and worker splits

- `WU-029` split into `WU-029A` (Notification Rule Management API), `WU-029B` (Notification Delivery Worker), and `WU-029C` (Discord Notification Delivery Adapter).
- `WU-038` split into `WU-038A` (Temporary Permission Renewal API) and `WU-038B` (Temporary Permission Expiry Worker).
- `WU-041` split into `WU-041A` (Compliance Evaluation Review API) and `WU-041B` (Scheduled Compliance Evaluation Worker).
- `WU-043` split into `WU-043A` (Chapter Archive Plan API) and `WU-043B` (Chapter Archive Execution Worker).

### Cross-service API and Discord splits

- `WU-016` split into `WU-016A` (Audit Query API) and `WU-016B` (Discord Correlation Propagation Adapter).
- `WU-028` split into `WU-028A` (Permission Drift Read and Resolution API) and `WU-028B` (Discord Permission Reconciliation Adapter).
- `WU-015` was narrowed to API-only code boundaries instead of carrying Discord adapter work inside the same PR.

### Low-severity decomposition fix

- `WU-025` was not split. The contract now explicitly defines `TicketMessageCreate`, and the acceptance criteria now require append-only message stream behavior for `POST /api/v1/tickets/{ticket_id}/messages`.

## Dependency Fixes Applied

### F-2: WU-009 and WU-010

Resolution: the declared dependency was kept as real.

- `WU-010` still depends on `WU-009`.
- `WU-009` and `WU-010` were removed from the same parallel cohort.
- Phase 0 now stages them as:
  - `[WU-001 + WU-009]`
  - `[WU-002 + WU-010]`

### F-3: WU-015, WU-016, WU-017 chain

Resolution: the parallelization claim was corrected to match the dependency chain.

- `WU-015` stays first.
- `WU-016A` depends on `WU-015`.
- `WU-017` depends on `WU-015` and `WU-016A`.
- `WU-016B` is the Discord adapter split and can run in parallel with `WU-017` only after `WU-016A` exists.
- Phase 1 now stages them as:
  - `[WU-012 + WU-015]`
  - `[WU-013 + WU-016A]`
  - `[WU-016B + WU-017]`

### F-4: impossible Phase 0 and Phase 1 cohorts

Resolution: the cohort map was rebuilt from the revised DAG and rechecked so no unit in a cohort depends directly or transitively on another unit in that same cohort.

- The old impossible Phase 0 entries were removed.
- The old impossible Phase 1 entries were removed.
- The revised map is listed in the final section below.

## Contract Fixes Applied

### F-5: WU-035 state enum mismatch

Resolved by extending `WU-022`'s `ApplicationRead.state` literal.

Added states:

- `interview`
- `waitlisted`

This keeps `WU-035` on the same `ApplicationRead` contract instead of inventing a separate extended read type.

## Updated Parallelization Map

Every group below was revalidated so no two units in the same group have a direct or transitive dependency on each other.

| Phase | Parallel groups | Max concurrent worktrees |
|---|---|---|
| 0 | `[WU-001 + WU-009]`, `[WU-002 + WU-010]`, `[WU-003]`, `[WU-004 + WU-005 + WU-006A + WU-007A + WU-007B + WU-008A]`, `[WU-006B + WU-007C + WU-008B]` | `2`, `2`, `1`, `6`, `3` |
| 1 | `[WU-011 + WU-014]`, `[WU-012 + WU-015]`, `[WU-013 + WU-016A]`, `[WU-016B + WU-017]` | `2`, `2`, `2`, `2` |
| 2 | `[WU-018 + WU-021 + WU-024 + WU-027 + WU-029A + WU-030 + WU-031]`, `[WU-019 + WU-022 + WU-025 + WU-028A + WU-029B]`, `[WU-020 + WU-023 + WU-026 + WU-028B + WU-029C + WU-032]` | `7`, `5`, `6` |
| 3 | `[WU-033 + WU-035 + WU-037 + WU-038A]`, `[WU-034 + WU-036 + WU-038B]` | `4`, `3` |
| 4 | `[WU-039 + WU-040 + WU-042]`, `[WU-041A + WU-043A + WU-044]`, `[WU-041B + WU-043B + WU-045]` | `3`, `3`, `3` |
