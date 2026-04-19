# AI Roadmap Revision Cycle 2

## Scope

This revision updates `product-strategy/ai roadmap.md` to clear the remaining medium-risk findings from cycle 1 without reintroducing dependency cycles or false parallelism.

## Dependency Fixes

### F-2: WU-007A and WU-007B shared an output file while marked parallel

- Revised WU-007A to own `services/api/app/contracts/chapter_templates.py`.
- Revised WU-007B to own `services/api/app/contracts/chapter_roles.py`.
- Kept them parallel because their write targets are now disjoint and match the split concerns.
- Updated WU-018 to consume `chapter_templates.py` directly.

### F-3: WU-039 and WU-040 were parallel despite shared compliance files

- Removed the false parallel claim.
- Made WU-040 depend on WU-039.
- Updated the Phase 4 graph to sequence `WU-039 -> WU-040 -> WU-041A -> WU-041B`.

### F-4: Shared Discord `api_client.py` write target across parallel Discord units

- Added WU-009B, `Discord Interaction Framework Foundation`.
- WU-009B is now the sole owner of `services/discord/app/infrastructure/api_client.py`.
- Removed `api_client.py` from downstream Discord work-unit code boundaries:
  - WU-013
  - WU-020
  - WU-023
  - WU-026
  - WU-034
- WU-016B was also narrowed so it no longer claims the shared transport file.
- Added explicit WU-009B dependencies to Discord-facing units that consume the stable client surface.

### F-5 and F-6: Missing application and ticket lifecycle dependencies

- Added explicit application and ticket lifecycle dependencies to WU-043B.
- Added explicit application and ticket lifecycle dependencies to WU-045.
- After the ticket split, those references now point to WU-022, WU-025A, and WU-025B.

### F-7: WU-032 surfaced deferred-effect and drift counts without declared sources

- Added WU-008B as the deferred-effect summary source dependency.
- Added WU-028A as the drift-resolution source dependency.
- Expanded the WU-032 test boundary to include the source contracts it reads.

## Coverage Fixes

### F-1: Missing Discord interaction framework work unit

- Added WU-009B for bot entry, command registration, interaction routing, and the shared API client boundary.
- All Discord-facing work units now depend on that foundation instead of each claiming framework ownership.

### F-2: Data portability lacked acceptance coverage

- Added a portability acceptance criterion to the relevant Phase 0 aggregate foundations:
  - WU-004
  - WU-005
  - WU-006A
  - WU-006B
  - WU-007A
  - WU-007B
  - WU-007C
- The criteria require a documented JSON export shape at the contract level.

### F-3: Missing notification event contract in Phase 0

- Added WU-003B, `Notification Event Dispatch Contract`.
- WU-029B now depends on WU-003B before notification delivery work begins.

### F-4: Hosting decision formalization had no implementation slot

- Chose the cleaner non-work-unit option.
- Added a Phase 0 phase-boundary gate requiring `DECISIONS.md` to record the hosting decision and rationale before Phase 0 closes.

## Decomposition Fixes

### F-1: Bundled work units split into single-concern units

- Split WU-009 into:
  - WU-009A `Shared Test Harness Foundation`
  - WU-009B `Discord Interaction Framework Foundation`
- Split WU-010 into:
  - WU-010A `Secret Management And Service Settings Substrate`
  - WU-010B `Deployable Service Runtime And Health Substrate`
- Split WU-025 into:
  - WU-025A `Ticket Creation API`
  - WU-025B `Ticket Transition API`
  - WU-025C `Ticket Message Append API`

### F-2: Test boundaries included implementation files

- Removed implementation files from test boundaries.
- WU-001 now exposes only `services/api/app/contracts/persistence.py`.
- WU-009A and WU-010A now use dedicated contract files for test-agent input instead of `conftest.py` or runtime settings modules.
- Verified every work unit test boundary now contains contracts only.

### F-3: WU-025 ticket lifecycle merged three endpoint families

- Replaced WU-025 with WU-025A, WU-025B, and WU-025C.
- Sequenced them as requested:
  - creation first
  - transitions second
  - message append third
- Updated downstream dependencies and the Phase 2 cohort map accordingly.

## Resulting Roadmap Shape

- Total work units increased from `56` to `61`.
- Maximum parallelization remains `7` concurrent worktrees.
- Critical path is now `18` gated work units.
- Phase 2 now has an explicit fourth cohort for the ticket message append and Discord ticket flow.
- Phase 4 no longer claims impossible parallelism between compliance rule management and evidence ingestion.

## Verification Notes

- No stale references to retired IDs `WU-009`, `WU-010`, or `WU-025` remain.
- Every dependency and parallelization reference resolves to an existing work unit.
- Every test boundary contains contract files only.
- The shared Discord `api_client.py` write target is owned by exactly one work unit.
