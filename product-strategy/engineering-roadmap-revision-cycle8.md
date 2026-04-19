# Engineering Roadmap Revision Cycle 8

## Scope

This revision updates `product-strategy/engineering roadmap.md` to address the Cycle 8 MEDIUM findings without dropping slices, reordering phases, or adding feature scope beyond the approved proposal.

Drift remains LOW. The revision targets the newly surfaced MEDIUM findings in integration and feasibility.

## Applied Revisions

### Integration fixes

1. **Correlation context propagation ownership**
   - Phase 0 now explicitly owns the `correlation_id` and `causation_id` columns plus minimal request-context middleware that stamps those values onto `AuditEntry` writes.
   - VS-003 now explicitly owns the discipline that every business-logic mutation flows through `mutate_entity()` so the Phase 0 stamping path is used everywhere.

2. **`action_type` seeding for parallel migrations**
   - The roadmap no longer describes late enum growth.
   - Phase 0 now states that `action_type` and `target_type` are TEXT columns validated against startup registries in `services/api/app/contracts/audit_types.py`.
   - The Phase 0 registry is loaded once with the full proposal-known target set plus all 18 slice-anticipated action types.

3. **VS-005 and VS-008 shared Discord runtime state**
   - VS-005 now states that provisioning uses the shared Discord platform adapter.
   - VS-008 now states that reconciliation treats live Discord resource state as read-through and emits reconciliation actions through that same adapter.
   - The pushback summary and parallelization map now record the single write-path rule after the VS-008 contract gate.

4. **`RosterEntry` VS-006 to VS-011 migration hazard**
   - Phase 0 now states that the `RosterEntry` expansion in VS-011 is additive only.
   - VS-011 now states the migration adds nullable columns only, with no constraint tightening, no renames, and no drops.
   - The acceptance criteria now require Phase 0 rows to survive unchanged through the migration.

5. **`FormDefinition` ownership boundary**
   - The roadmap now states that Phase 0 does not introduce `FormDefinition`.
   - VS-006 explicitly owns `FormDefinition` end-to-end as an intake-specific table and lifecycle.

### Feasibility fixes

6. **`target_type` enum contradiction with registry design**
   - Phase 0 now aligns with the proposal implementation direction by defining `action_type` and `target_type` as TEXT columns with startup validation, not DB enums.
   - The registry location is named explicitly as `services/api/app/contracts/audit_types.py`.

7. **Deployable substrate scope decomposition**
   - The previous single L substrate row has been split into three M-sized Phase 0 items:
     - container and image build pipeline
     - Flux GitOps configuration plus secret-management wiring
     - Kubernetes manifests plus Helm chart, settings wiring, and smoke path
   - Phase 0 counts and effort summary were updated accordingly.

8. **`mutate_entity()` traceability to the proposal**
   - The Phase 0 kernel row now states that `mutate_entity()` implements the proposal's `Audit Chain` single-transaction mutation pattern.
   - VS-003 effort reasoning now names `mutate_entity()` as the concrete implementation of the proposal's `Audit Chain` write boundary.

9. **VS-008 one-time migration scope**
   - VS-008 is now described as two explicit deliverables:
     - Deliverable A: core `PermissionIntent` service, diff, reconciliation, and endpoints
     - Deliverable B: one-time migration tooling for pre-existing Discord permissions
   - The slice effort is now called out as `XL heavy` to reflect the extra migration deliverable.

## Outcome

The revised roadmap preserves the approved phase ordering and slice list while making the Phase 0 contract boundaries, Discord write-path ownership, additive migration guarantees, and VS-008 sizing assumptions explicit enough for the next risk pass.
