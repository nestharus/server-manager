# Engineering Roadmap Estimate Additions

## Counting rule

Estimate distribution below uses the leaning magnitude when a band is given.

- `S-M (leans S)` counts as `S`
- `M-L (leans M)` counts as `M`
- `L-XL (leans L)` counts as `L`

This keeps the distribution readable while preserving the uncertainty bands in the roadmap itself.

## Estimate distribution

| Scope | S | M | L | XL | Total |
|---|---:|---:|---:|---:|---:|
| Phase 0 foundation items | 1 | 7 | 5 | 0 | 13 |
| Value slices (VS-001 to VS-018) | 0 | 12 | 4 | 2 | 18 |
| **Combined** | **1** | **19** | **9** | **2** | **31** |

## Value slices flagged for prototyping

### `yes`

- `VS-005` Chapter provisioning from templates
- `VS-008` Permission intent and drift detection
- `VS-016` Compliance rule evaluation with evidence

### `conditional`

- `VS-002` Scoped authority with enforcement
- `VS-009` Configurable operator notifications
- `VS-011` Roster management with role lifecycle
- `VS-013` SLA enforcement for tickets

## Foundation items flagged for prototyping

### `yes`

- Permission intent foundation
- Scheduler

### `conditional`

- Authority grant foundation
- Graceful degradation mechanics
- Deployable service substrate aligned to `infra/`

## Wide uncertainty bands

- No value slice spans 2+ sizes.
- No Phase 0 foundation item spans 2+ sizes.
- The uncertainty is concentrated in adjacent bands, not in extremely wide estimate ranges.

## Concentrated uncertainty notes

- Phase 0 carries the heaviest foundation uncertainty because persistence, scheduler choice, deployment substrate, and permission-intent groundwork are all still mostly greenfield.
- Phase 2 is the widest value-delivery phase; its schedule risk is concentrated in `VS-005` and `VS-008`.
- Phase 4 uncertainty is dominated by `VS-016`, where OCR accuracy and fallback behavior determine whether the full subsystem stays bounded.
