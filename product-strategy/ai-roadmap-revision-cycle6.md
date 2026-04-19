# AI Roadmap Revision Cycle 6

## Scope

Final dependency pass against `product-strategy/ai roadmap.md` after prior rounds already cleared decomposition and coverage.

Target findings for this cycle:

- F-1 MEDIUM: false shared-write claim between `WU-045A-applications` and `WU-045A-tickets`
- F-2 MEDIUM: Phase 0 cohort 4 parallelization map inconsistent with per-unit declarations
- F-3 LOW: critical-path length under-counted by one work unit
- F-4 INFO: `WU-028B-api` singleton cohort posture

## Revisions

### F-1

Status: fixed

Change:

- Removed `services/api/app/contracts/authority.py` from the code boundary of both `WU-045A-applications` and `WU-045A-tickets`.
- Kept `authority.py` in the test boundary for both units because they consume authority contracts but do not need to author new authority contract surface.

Result:

- The pair no longer claims a shared writable file.
- Their parallel relationship remains valid without adding a sequencing edge.

### F-2

Status: fixed

Change:

- Kept Phase 0 cohort 4 at `11` concurrent worktrees.
- Updated the `Parallelizable with` declarations for all cohort-4 members so they consistently reflect the cohort map:
  `WU-003B`, `WU-004`, `WU-005`, `WU-006A`, `WU-007A`, `WU-007B`, `WU-008A`, `WU-009C`, `WU-009D`, `WU-010D`, `WU-010E`.

Reasoning:

- The cohort members have no dependency edges between each other.
- Their code boundaries do not share output files or migration files.
- The previous inconsistency was documentation drift, not a real scheduling constraint.

Result:

- The cohort map and per-unit declarations now agree.
- Maximum parallelization remains `11 concurrent worktrees`.

### F-3

Status: fixed

Change:

- Updated the critical path from `18` to `19` work units.
- Inserted `WU-034` into the critical-path chain:
  `WU-001 -> WU-002 -> WU-003 -> WU-008A -> WU-008B -> WU-014 -> WU-015A -> WU-016A -> WU-017 -> WU-024 -> WU-025A-create -> WU-025B -> WU-025C -> WU-033 -> WU-034 -> WU-039 -> WU-040A -> WU-041A -> WU-041B`
- Added a note explaining that the roadmap's phase gate holds Phase 4 until the longest Phase 3 pair completes.

Result:

- The summary metric and narrative now match the gated roadmap structure.

### F-4

Status: no roadmap change

Decision:

- Left `WU-028B-api` as a singleton cohort.

Reasoning:

- The current singleton posture is conservative and internally consistent.
- Broadening it was optional and would not improve correctness.
- Keeping it isolated avoids reopening dependency discussions in a final-pass revision that was otherwise limited to concrete defects.

## Dependency Safety Check

- No new dependency edges were added.
- No dependency cycles were introduced.
- `WU-045A-applications` and `WU-045A-tickets` remain parallel without shared writable files.
- Phase 0 cohort 4 still represents the maximum safe concurrency set.

## Outcome

- Decomposition posture unchanged: LOW preserved
- Coverage posture unchanged: LOW preserved
- Dependency finding disposition: remaining MEDIUM items resolved
