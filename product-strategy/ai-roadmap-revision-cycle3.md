# AI Roadmap Revision Cycle 3

## Outcome

- Revised `product-strategy/ai roadmap.md` for the cycle 3 dependency and decomposition findings.
- Work unit count increased from `61` to `71`.
- Critical path remains `18 work units`.
- Maximum parallelization increased to `11 concurrent worktrees` because the Phase 0 foundation bundles were split into smaller independent units.

## Dependency Fixes

### F-1. Cohort contradicted declared dependency on WU-003

- Resolved by splitting the old Discord framework bundle into `WU-009C` and `WU-009D`.
- Both units now sit after `WU-003` in Phase 0, so neither is parallelized with its own correlation-context dependency.
- The old conflicting cohort `[WU-003 + WU-009B + WU-010B]` no longer exists.

### F-2. Per-unit parallel metadata contradicted cohort placement

- Rewrote the Phase 0 cohorts and updated the affected `Parallelizable with` lists to match them.
- Cleaned stale cross-cohort references that survived earlier revisions, including the old `WU-020`/`WU-023`/`WU-028B`/`WU-029C` links to `WU-026` and the old `WU-044A` link to `WU-041A`.
- The per-unit metadata now matches the global dependency graph and parallelization map.

### F-3. NotificationDispatchPort was orphaned

- Removed `NotificationDispatchPort` from `WU-003B`.
- `WU-003B` now defines only the persisted `NotificationEventRead` envelope and explicitly states that downstream workers consume those rows through runtime repository injection.
- `WU-029B` now declares the missing transformation boundary with `handler materialize_notification_envelopes(event: NotificationEventRead) -> list[NotificationEnvelopeRead]`.
- This keeps the dependency edge from `WU-029B` to `WU-003B` exact without inventing a fake compile-time port consumer.

## Decomposition Fixes

### Phase 0 splits

- `WU-009A` became `WU-009A` API test harness and `WU-009B` Discord test harness.
- Old `WU-009B` became `WU-009C` Discord interaction registry/dispatch and `WU-009D` Discord API transport.
- `WU-010A` became `WU-010A` API settings and `WU-010B` Discord settings.
- Old `WU-010B` became `WU-010C` API factory/liveness, `WU-010D` API readiness, and `WU-010E` Discord runtime entrypoint.

### Multi-concern API splits

- `WU-015` became `WU-015A` authority enforcement guard and `WU-015B` override audit policy.
- `WU-030` became `WU-030A` trust signal management and `WU-030B` trust recomputation trigger.
- `WU-040` became `WU-040A` evidence submission and `WU-040B` OCR extraction.
- `WU-044` became `WU-044A` succession plan and `WU-044B` authority transfer.
- `WU-045` became `WU-045A` pending work handoff execution and `WU-045B` leadership context view.

### Typed Discord contract fixes

- `WU-016B` now defines `ApiContextPort.attach(context: ApiRequestContext) -> ApiRequestHeaders`.
- `WU-028B` now defines `PermissionStatePort.fetch_scope_state(request: ReconciliationRunRequest) -> PermissionScopeSnapshot`.
- `WU-029C` now defines `handler deliver_notification(command: NotificationDeliveryCommand) -> NotificationDeliveryResult`.
- `WU-034` now defines `handler sync_roster(event: RosterSyncEvent) -> RosterSyncResult`.
- `WU-036` now defines typed `handle_interview(...)` and `handle_waitlist(...)` handlers.

## Validation

- `product-strategy/ai roadmap.md` now contains `71` unique work-unit headings.
- No legacy unsuffixed `WU-015`, `WU-030`, `WU-040`, `WU-044`, or `WU-045` references remain.
- Dependency declarations still topologically sort across all `71` work units.
- No em dashes were introduced in the revised roadmap or this report.
