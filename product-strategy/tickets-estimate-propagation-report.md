# Ticket Estimate Propagation Report

## Method

- Pulled rough magnitude and prototyping flags from `product-strategy/engineering roadmap.md`.
- Updated only the effort and prototyping fields in ticket files.
- For Phase 0 tickets that bundle multiple foundation items, listed the mapped foundation estimates inline instead of inventing a single rolled-up effort.
- In `product-strategy/tickets/INDEX.md`, added a `Prototyping` column. For bundled Phase 0 tickets, the rollup rule is `yes` > `conditional` > `no`.

## SLICE Tickets

- `SLICE-001`: mapped to Persistence substrate with migrations `L-XL (leans L)` and Single write-path mutation primitive `M-L (leans M)`; prototyping `no` and `no`.
- `SLICE-002`: mapped to Audit and notification event contract `M-L (leans M)`, Authority grant foundation `L`, and Policy version framework `M-L (leans M)`; prototyping `no`, `conditional`, and `no`.
- `SLICE-003`: mapped to Permission intent foundation `L-XL (leans L)` and Chapter role and roster entry foundation `M-L (leans M)`; prototyping `yes` and `no`.
- `SLICE-004`: mapped to Scheduler `L-XL (leans L)` and Graceful degradation mechanics `M-L (leans M)`; prototyping `yes` and `conditional`.
- `SLICE-005`: mapped to Shared test harness `M`; prototyping `no`.
- `SLICE-006`: mapped to Discord interaction framework `M-L (leans M)` and Deployable service substrate aligned to `infra/` `L-XL (leans L)`; prototyping `no` and `conditional`.
- `SLICE-007`: mapped to `VS-001` `M-L (leans M)`; prototyping `no`.
- `SLICE-008`: mapped to `VS-002` `L`; prototyping `conditional`.
- `SLICE-009`: mapped to `VS-003` `M`; prototyping `no`.
- `SLICE-010`: mapped to `VS-004` `M-L (leans M)`; prototyping `no`.
- `SLICE-011`: mapped to `VS-007` `M-L (leans M)`; prototyping `no`.
- `SLICE-012`: mapped to `VS-006` `M-L (leans M)`; prototyping `no`.
- `SLICE-013`: mapped to `VS-005` `L-XL (leans L)`; prototyping `yes`.
- `SLICE-014`: mapped to `VS-008` `XL`; prototyping `yes`.
- `SLICE-015`: mapped to `VS-009` `M-L (leans M)`; prototyping `conditional`.
- `SLICE-016`: mapped to `VS-010` `M-L (leans M)`; prototyping `no`.
- `SLICE-017`: mapped to `VS-015` `M-L (leans M)`; prototyping `no`.
- `SLICE-018`: mapped to `VS-011` `L`; prototyping `conditional`.
- `SLICE-019`: mapped to `VS-013` `L`; prototyping `conditional`.
- `SLICE-020`: mapped to `VS-014` `M-L (leans M)`; prototyping `no`.
- `SLICE-021`: mapped to `VS-012` `M`; prototyping `no`.
- `SLICE-022`: mapped to `VS-016` `XL`; prototyping `yes`.
- `SLICE-023`: mapped to `VS-017` `M-L (leans M)`; prototyping `no`.
- `SLICE-024`: mapped to `VS-018` `M-L (leans M)`; prototyping `no`.

## INIT Tickets

- `INIT-001`: added aggregate slice magnitudes for `VS-002`, `VS-003`, `VS-004`, `VS-009`, and `VS-015`, plus per-slice prototyping flags.
- `INIT-002`: added aggregate slice magnitudes for `VS-001` and `VS-010`, plus per-slice prototyping flags.
- `INIT-003`: added aggregate slice magnitudes for `VS-007` and `VS-013`, plus per-slice prototyping flags.
- `INIT-004`: added aggregate slice magnitudes for `VS-006` and `VS-012`, plus per-slice prototyping flags.
- `INIT-005`: added aggregate slice magnitudes for `VS-005`, `VS-011`, `VS-017`, and `VS-018`, plus per-slice prototyping flags.
- `INIT-006`: added aggregate slice magnitudes for `VS-008` and `VS-014`, plus per-slice prototyping flags.
- `INIT-007`: added aggregate slice magnitude for `VS-016`, plus the prototyping flag.

## Index

- `product-strategy/tickets/INDEX.md`: replaced all `not specified` effort placeholders, added a `Prototyping` column to every phase table, and documented the Phase 0 bundled-ticket rollup rule in the overview.
