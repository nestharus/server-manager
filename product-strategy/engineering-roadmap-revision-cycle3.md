# Engineering Roadmap Revision - Cycle 3

## Summary

Cycle 3 keeps all 18 value slices in their approved phases and revises the engineering decomposition to close the remaining drift, integration, and feasibility findings from the Cycle 2 risk pass.

The main structural changes are:

- Phase 0 is expanded from 9 to 12 explicit foundation rows.
- VS-004 is narrowed to the generic `PolicyVersion` framework plus the single Phase 1 policy type that already has a domain object: `TrustComputationConfig`.
- VS-002, VS-005, and VS-008 are resized to XL.
- Phase 1, Phase 2, and Phase 4 now have explicit intra-phase contract gates instead of soft parallelism claims.

## Item-by-item revision log

### 1. VS-008 permission migration tooling

**Before:** VS-008 listed drift detection and reconciliation only. The one-time migration tool for pre-existing Discord permissions was absent from the slice scope.  
**After:** VS-008 `What is new` now explicitly includes one-time permission migration tooling for pre-existing Discord permissions.  
**Structural change:** The slice scope now matches executive Risk Register #5 and Deferred Subsystems `Permission migration tooling`.

### 2. Phase 0 graceful degradation mechanics

**Before:** Phase 0 had no row naming the proposal's graceful-degradation mechanics.  
**After:** Phase 0 now has a dedicated row for deferred execution classification, consequence-graduated retry, precondition validation on recovery, and audit-blocks-consequential-actions policy.  
**Structural change:** The roadmap now makes executive Deferred Subsystems `Graceful degradation mechanics` auditable at the phase boundary.

### 3. Phase 0 data portability

**Before:** Data portability was implied but not listed in Phase 0.  
**After:** The persistence and migration row now explicitly includes documented JSON export formats for every aggregate as a Phase 0 schema-design property that extends as each subsystem ships.  
**Structural change:** The roadmap now mirrors executive Deferred Subsystems `Data portability export tooling` as an engineering-owned schema property.

### 4. VS-004 policy coverage outrunning domain existence

**Before:** VS-004 claimed preview-confirm coverage for all six policy families in Phase 1.  
**After:** VS-004 is narrowed to the generic `PolicyVersion` framework plus one working `TrustComputationConfig` integration. The other five policy families are deferred to their owning slices when their domain objects exist.  
**Structural change:** The integration mismatch identified in `plans/risk/engineering-integration.md` F-1 is removed without moving VS-004 out of Phase 1.

### 5. Template-to-roster schema gap

**Before:** VS-005 referenced template `role_structure`, and VS-006 approval implied `RosterEntry` creation, but the roadmap had no durable schema path until VS-011 in Phase 3.  
**After:** Phase 0 now includes a chapter-membership seed-schema row that adds minimal `ChapterRole` and `RosterEntry` tables. VS-005 persists seeded `ChapterRole` records, and VS-006 approvals create pending `RosterEntry` records. VS-011 still owns the roster service layer, lifecycle transitions, and operator UX.  
**Structural change:** The roadmap chooses the "Phase 0 shared schema" path instead of inventing a new intermediate record type.

### 6. VS-002 and VS-003 mutation-path overlap

**Before:** VS-002 and VS-003 both touched every mutation path, but the split between them was implicit.  
**After:** Phase 0 now owns the stable `mutate_entity()` primitive and one migrated reference path, VS-002 explicitly wraps `mutate_entity()` with a pre-check authority decorator, and VS-003 explicitly owns rollout discipline so all write paths use the primitive.  
**Structural change:** VS-002 is now additive enforcement on top of the primitive, not a second mutation framework.

### 7. VS-015 depending on unstable event schemas

**Before:** VS-015 projected against Phase 2 event types that had not yet been stabilized.  
**After:** Phase 0 now fixes the `AuditEntry` envelope, `action_type`, `target_type`, correlation and causation rules, and payload JSON conventions over the existing JSON fields. VS-015 is now described as reading that stable contract.  
**Structural change:** Projection work is tied to a fixed event envelope instead of ad hoc slice-specific event authorship.

### 8. VS-008 permission stream ordering

**Before:** The roadmap implied a relationship between VS-008 and later permission-consuming slices, but it did not state the serialization mechanism.  
**After:** VS-008 now explicitly states that permission-intent changes are serialized through the audit event stream via `mutate_entity()`, with no second ordering mechanism.  
**Structural change:** The permission stream is now anchored to the same write discipline as the rest of the roadmap.

### 9. VS-002 effort size

**Before:** VS-002 was sized L.  
**After:** VS-002 is sized XL.  
**Structural change:** The effort reasoning now treats authority enforcement as a zero-baseline, cross-cutting middleware and daemon concern rather than a normal feature extension.

### 10. VS-004 effort size after narrowing

**Before:** VS-004 was sized L while still claiming six policy families.  
**After:** VS-004 remains L, but only because the slice is now narrowed to the framework plus `TrustComputationConfig`.  
**Structural change:** The size is preserved and the rationale is made explicit in the slice's effort reasoning.

### 11. VS-008 effort size

**Before:** VS-008 was sized L.  
**After:** VS-008 is sized XL.  
**Structural change:** The slice now openly includes Discord permission readers, overwrite graph modeling, reconciliation, rate-limit-aware reads, drift surfaces, and migration tooling.

### 12. VS-003 mutate_entity rollout scope

**Before:** VS-003 was described mainly as durable audit storage and queryability.  
**After:** VS-003 now explicitly includes disciplined rollout so every mutation path uses the Phase 0 `mutate_entity()` primitive.  
**Structural change:** M is kept only because the primitive itself moved into Phase 0 and a reference adoption path is now part of Phase 0 exit criteria.

### 13. VS-013 scheduler dependency

**Before:** The scheduler lived inside a composite Phase 0 audit-and-dispatch row.  
**After:** Phase 0 now has a separate scheduler row, and VS-013 depends on that explicit framework.  
**Structural change:** Scheduler construction is no longer hidden inside VS-013 or an overloaded Phase 0 composite row.

### 14. Phase 0 test harness expansion

**Before:** The test-harness row was broad and did not list stale chapter-test cleanup, aggregate fixtures, or monorepo reproducibility.  
**After:** The Phase 0 test-harness row now explicitly includes stale chapter-test cleanup, aggregate fixtures for the new write pattern, Discord interaction utilities, and monorepo install reproducibility.  
**Structural change:** Phase 0 now owns the cleanup work identified in engineering research and the Cycle 2 feasibility report.

### 15. Phase 0 deployable substrate and hosting assumption

**Before:** The deployable-substrate row assumed hosting without naming it.  
**After:** The row now explicitly targets `Vultr VKE`, matching the current infra tree and platform-bootstrap artifacts.  
**Structural change:** The roadmap no longer treats hosting as an unnamed assumption inside Phase 0.

### 16. VS-005 effort size

**Before:** VS-005 was sized L.  
**After:** VS-005 is sized XL.  
**Structural change:** The effort reasoning now includes live Discord mutation blast radius, idempotency, retry behavior, and durable resource tracking instead of leaning on the small in-memory chapter CRUD analogue.

### 17. Parallelization map for Phase 1

**Before:** Phase 1 claimed full internal parallelism after Phase 0.  
**After:** Phase 1 now has an explicit gate: `VS-002 -> (VS-001 + VS-003 + VS-004)`.  
**Structural change:** The map now reflects that the authority wrapper touches every write path and must stabilize before the other Phase 1 slices build on it.

### 18. VS-018 dependency versus parallelism

**Before:** VS-018's slice text and the phase summary implied both dependency and partial parallelism with VS-017.  
**After:** VS-018 is now explicitly sequenced after VS-017. The Phase 4 parallelization map lists only `VS-016 + VS-017` as the clean parallel pair.  
**Structural change:** Succession is now treated as consuming chapter-governance states and pending-work rules from VS-017 instead of as a soft-overlap stream.

## Net structural effect

Compared to the previous roadmap revision:

- Phase 0 gained 3 rows: stable audit-event contract, chapter-membership seed schema, and explicit graceful-degradation mechanics.
- Phase 0 split scheduler concerns out of the old audit-and-dispatch row.
- The effort summary changed materially: VS-002, VS-005, and VS-008 are now XL; VS-004 stays L only because its scope is narrowed.
- The parallelization map is less optimistic and more explicit about contract gates.
- The chapter and permission tracks now have concrete dependency edges instead of warnings embedded in prose.

## Trace references used for this revision

- `product-strategy/executive roadmap.md`
- `product-strategy/proposal.md`
- `product-strategy/engineering research.md`
- `plans/risk/engineering-drift.md`
- `plans/risk/engineering-integration.md`
- `plans/risk/engineering-feasibility.md`
- `plans/proposals/platform-bootstrap.md`
- `plans/research/platform-bootstrap-hookpoints.md`
