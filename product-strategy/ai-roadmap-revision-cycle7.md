# AI Roadmap Revision Cycle 7

## Scope

This revision is decomposition-only. It resolves the remaining MEDIUM decomposition findings without changing initiative ordering, cross-phase ordering, or roadmap scope.

## Applied Fixes

### F-1: WU-023 split into two Discord user flows

- Replaced `WU-023` with `WU-023a: Discord Application Submission Flow`.
- Added `WU-023b: Discord Application Review Flow`.
- Gave each unit its own contract, test boundary, code boundary, and acceptance criteria.
- Kept both units in the same Phase 2 cohort because they now have disjoint Discord write boundaries and no dependency edge between them.

### F-2: WU-036 split into two Discord user flows

- Replaced `WU-036` with `WU-036a: Discord Interview Thread Flow`.
- Added `WU-036b: Discord Waitlist Flow`.
- Gave each unit its own contract, test boundary, code boundary, and acceptance criteria.
- Kept both units in the same Phase 3 cohort because they now have disjoint Discord write boundaries and no dependency edge between them.

### F-3: WU-040B split by actor class

- Replaced `WU-040B` with `WU-040B-extract: OCR Extraction API`.
- Added `WU-040B-correct: Officer Correction API`.
- Scoped extraction to the automated OCR path and correction to the officer override path.
- Kept `WU-041B` dependent only on `WU-040B-extract`, which preserves a LOW dependency posture by avoiding an unnecessary dependency on manual correction.

### F-4: Audit of remaining `And`-titled units

These units were reviewed and kept as single work units with a one-line decomposition note in the roadmap:

- `WU-011`: member aggregate plus status mutation share one versioned aggregate boundary.
- `WU-012`: trust profile read plus initial computation are one trust-profile capability.
- `WU-022`: application submission plus reviewer ownership transitions share one application aggregate lifecycle.
- `WU-028A`: permission drift read plus resolution are the read and mutation surface of one drift resource.
- `WU-035`: interview plus waitlist API actions extend one application state machine.
- `WU-037`: SLA evaluation plus escalation are one scheduled enforcement worker.

## Consistency Checks

- Inventory updated from `75` to `78` work units.
- Phase 2 cohort `[WU-020 + WU-023a + WU-023b + WU-025A-events + WU-025B + WU-028B-discord + WU-029B-deliver + WU-032]` is internally consistent and rises from `7` to `8` concurrent worktrees in that cohort.
- Phase 3 cohort `[WU-034 + WU-036a + WU-036b + WU-038B]` is internally consistent and rises from `3` to `4` concurrent worktrees in that cohort.
- Phase 4 cohort `[WU-040B-extract + WU-040B-correct + WU-041A + WU-043B + WU-044B]` is internally consistent and rises from `4` to `5` concurrent worktrees in that cohort.
- Maximum roadmap parallelization remains `11 concurrent worktrees`, so no new HIGH dependency signal was introduced.
- Critical path remains `19 work units` because none of the newly split units sit on the existing longest gated chain.
