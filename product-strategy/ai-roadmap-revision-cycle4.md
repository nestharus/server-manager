# AI Roadmap Revision Cycle 4

## Scope

Targeted final pass against `product-strategy/ai roadmap.md` to close the outstanding Decomposition and Dependency findings from the Cycle 4 review brief.

## Applied Fixes

### Decomposition

- F-1: Split `WU-028B` into `WU-028B-api` and `WU-028B-discord`.
- F-2: Split `WU-029B` into `WU-029B-materialize` and `WU-029B-deliver`.
- F-3: Rewrote `WU-003` to use typed correlation models: `CorrelationHeadersRead` and `AuditContextRead`.
- F-4: Rewrote `WU-003B` acceptance criteria to describe replayable persisted behavior instead of dispatcher wiring.
- F-5: Added officer-correction contract to `WU-040B` with `OfficerCorrectionRequest`, `OfficerCorrectionRead`, and a typed correction endpoint.
- F-6: Split `WU-025A` into `WU-025A-create` and `WU-025A-events`.
- F-7: Replaced inline dict returns with named models in `WU-013`, `WU-025C`, and `WU-036`.
- F-8: Split `WU-045A` into `WU-045A-applications` and `WU-045A-tickets`.

### Dependency

- F-1: Preserved parallelism between `WU-015B` and `WU-016A` by splitting the shared write surface into `services/api/app/services/audit_overrides.py` and `services/api/app/services/audit_queries.py`.
- F-2: Preserved parallelism between `WU-040B` and `WU-041A` by splitting the shared write surface into `services/api/app/services/compliance_extraction.py` and `services/api/app/services/compliance_review.py`.
- F-3: Normalized all `Parallelizable with` annotations to be symmetric.
- F-4: Annotated non-contract dependencies on `WU-017` as runtime dependencies where the consuming work unit does not exercise policy contract types directly.

## Cohort Changes

- Total work units increased from `71` to `75`.
- Phase 2 cohorts are now:
  - `[WU-018 + WU-021 + WU-024 + WU-027 + WU-029A + WU-030A + WU-031]`
  - `[WU-019 + WU-022 + WU-025A-create + WU-028A + WU-028B-api + WU-029B-materialize + WU-030B]`
  - `[WU-020 + WU-023 + WU-025A-events + WU-025B + WU-028B-discord + WU-029B-deliver + WU-032]`
  - `[WU-025C + WU-026 + WU-029C]`
- Phase 4 cohorts are now:
  - `[WU-039 + WU-042]`
  - `[WU-040A + WU-043A + WU-044A]`
  - `[WU-040B + WU-041A + WU-043B + WU-044B]`
  - `[WU-041B + WU-045A-applications + WU-045A-tickets]`
  - `[WU-045B]`

## Verification

- Dependency graph is acyclic.
- `Parallelizable with` annotations are symmetric across all `75` work units.
- Split work units were propagated through inventory, dependency graph, critical path, parallelization map, and summary metrics.
- `WU-017` dependency notes now distinguish runtime dependency from contract dependency where applicable.
- No em dashes were introduced.

## Outcome

`product-strategy/ai roadmap.md` now reflects the requested final-pass decomposition and dependency corrections while preserving coverage and cohort integrity.
