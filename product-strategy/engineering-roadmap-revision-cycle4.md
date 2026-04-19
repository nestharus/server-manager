# Engineering Roadmap Revision Report - Cycle 4

## Scope

This revision updates `product-strategy/engineering roadmap.md` to address the 11 targeted feasibility and integration findings while preserving all 18 value slices and their phase placement.

## Applied Revisions

1. **F-1 Phase 0 aggregate effort**
Changed the Phase 0 heading and total-effort line to state the aggregate explicitly. Because Cycle 4 also re-rated the scheduler and Discord framework to `L`, the corrected aggregate is now `XL (aggregate: 5L + 7M items)` rather than the older `3L + 9M` count.

2. **F-2 Scheduler framework at M**
Upgraded the Phase 0 scheduler foundation row from `M` to `L`.

3. **F-3 Discord interaction framework at M**
Upgraded the Phase 0 Discord interaction framework row from `M` to `L`.

4. **F-4 Hosting target wording**
Softened the hosting language. The roadmap now refers to "the hosting target defined in `infra/` OpenTofu configuration" in both the technical summary and the Phase 0 substrate row, which treats `infra/` as the current engineering source of truth without claiming a formalized `DECISIONS.md` entry.

5. **F-5 Downstream slices depending on incomplete Phase 0 primitives**
Added an explicit fallback statement under Phase 0: dependent slices pause if a required primitive ships late or short of acceptance criteria, and they do not proceed on a partial primitive.

6. **I-1 VS-001 ↔ VS-004 `TrustComputationConfig` coupling**
Added explicit sequencing in VS-001, VS-004, the pushback-summary gates, the parallelization map, and the critical path: `VS-004 framework -> VS-001 trust computation`.

7. **I-2 `AuditEntry.target_type` enum completion policy**
Documented the enum-extension policy in Phase 0. The roadmap now states that Phase 0 seeds a known-at-build-time enum and later slices append new target types in their own migrations.

8. **I-3 `RosterEntry` ownership across VS-006, VS-011, VS-016, and VS-017**
Added an ownership rule in Phase 0 and reinforced it in the relevant slice descriptions: VS-011 owns the `RosterEntry` service boundary and write authority; the other slices trigger roster outcomes through that service rather than writing the table directly.

9. **I-4 VS-016 and VS-017 parallelization conflict**
Resolved this by de-parallelizing the Phase 4 pair. The roadmap now states `VS-016 -> VS-017 -> VS-018`, updates both slice sections, updates the parallelization map, and revises the critical path accordingly.

10. **I-5 VS-008 contract-stability gate for VS-005**
Defined a concrete acceptance gate in VS-005, VS-008, and the parallelization map. VS-005 starts only after all three are true:
`PermissionIntent` table migration committed, snapshot and reconcile service API frozen, and a working `diff` endpoint exists.

11. **I-6 VS-011 ↔ VS-014 concurrent `PermissionIntent` writes**
Added the ordering and serialization rule to VS-008, VS-011, VS-014, the pushback-summary gates, and the Phase 3 parallelization row: both slices write through the VS-008-owned `PermissionIntent` service, which serializes via the Phase 0 `mutate_entity()` primitive.

## Result

The revised roadmap keeps all 18 slices, preserves executive phase placement, sharpens the Phase 0 aggregate, and replaces the remaining medium integration ambiguities with explicit sequencing and service-ownership rules.
