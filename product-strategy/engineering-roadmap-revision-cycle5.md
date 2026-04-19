# Engineering Roadmap Revision Cycle 5

## Scope

Cycle 5 resolves the two remaining HIGH integration findings and the open MEDIUM integration and feasibility findings without changing phase order, without dropping any value slices, and without adding new feature scope.

The revision keeps all 18 value slices in their approved phases. The work here is contract clarification, Phase 0 ownership correction, and effort and parallelization recalibration.

## Applied Revisions

### HIGH findings

| Finding | Resolution in `engineering roadmap.md` |
|---|---|
| F-1 `RosterEntry` service boundary required in Phase 2 but owned in Phase 3 | Phase 0 now owns only the `RosterEntry` table, base columns, and a thin primitive for writing a minimal pending entry. VS-006 explicitly writes through that Phase 0 minimal path. VS-011 later owns the full roster lifecycle service and broader transitions. |
| F-2 Audit enum extension creates a migration conflict point | Replaced the slice-by-slice enum growth model with a single Phase 0 seeded `target_type` enum covering the full proposal-known aggregate registry. Later slices consume that registry rather than appending enum values in their own migrations. |

### Integration MEDIUM findings

| Finding | Resolution in `engineering roadmap.md` |
|---|---|
| F-3 `PermissionIntent` table ownership | Phase 0 now explicitly owns the `PermissionIntent` table, minimal column set, and migration ownership. VS-008 owns only the service layer, reconciliation logic, and endpoints. |
| F-4 `NotificationRule` dispatch contract unspecified | Phase 0 now states the dispatch contract directly: emitting slices write `AuditEntry`; VS-009 subscribes to the audit stream; downstream notification delivery remains owned by VS-009. |
| F-5 Correlation and causation propagation named but not specified | Phase 0 now names `correlation_id` and `causation_id` as concrete `AuditEntry` schema columns, not just narrative behavior. VS-003 consumes that schema. |
| F-6 VS-002 wrapper contract surface not enumerated | VS-002 now lists the required contract surface explicitly: `@requires_authority(scope, grant_type)`, `check_authority(actor, grant_type, scope) -> bool`, and decoration of every mutation path. |
| F-7 PermissionIntent service serialization bottleneck | VS-008 now states that Phase 2 and 3 permission-intent writes serialize through the VS-008-owned service by design, and that this is acceptable at Humility scale. Horizontal scaling is deferred rather than hidden. |
| F-8 Deployable substrate not gated against unresolved platform decision | The technical landscape summary and Phase 0 substrate row now state that the current target is "as configured in `infra/`" for Vultr VKE, while also flagging formalization in `DECISIONS.md` as a prerequisite before the deployable substrate is considered complete. |

### Feasibility MEDIUM findings

| Finding | Resolution in `engineering roadmap.md` |
|---|---|
| F-1 Phase 0 deployable substrate hosting assumption | Same resolution as Integration F-8. The language is softened to match the actual repo baseline and the missing decision-log formalization is stated as a prerequisite. |
| F-2 VS-003 audit still carried too much rollout breadth for M | VS-003 is upgraded from M to L. The reasoning now reflects the cross-system rollout discipline required across every mutation path. |
| F-3 VS-015 CQRS projection estimated too low | VS-015 is upgraded from M to L. The reasoning now treats cross-subsystem projection infrastructure as greenfield work, not a bounded extension. |
| F-4 Parallel-effort column underestimates serialization | The Parallelization Map and Effort Summary now model the real gates: VS-002 before Phase 1 parallel work, VS-008 before VS-005, and the shared VS-008 `PermissionIntent` service bottleneck in Phase 3. |
| F-5 VS-006 implicitly built on rejected draft code | VS-006 now states that `daemon/applications.py` and related files exist only as D3-preserved pre-research hookpoints and are not part of the build baseline. The L estimate remains, but the baseline assumption is corrected. |

## Resulting Roadmap Changes

The roadmap now makes four ownership boundaries explicit:

1. Phase 0 owns foundational tables and thin primitives only where later value slices need an earlier minimal write path.
2. VS-011 owns the full roster lifecycle service, but not the initial Phase 0 seed-table migration.
3. Phase 0 owns the `PermissionIntent` table, while VS-008 owns the operating service around it.
4. VS-009 owns notification delivery, but not event emission from other slices.

The roadmap also now makes three contract rules explicit:

1. Audit targets are seeded once at Phase 0, not extended slice by slice.
2. Audit correlation and causation are schema columns, not informal propagation guidance.
3. Authority enforcement is a defined wrapper contract applied to every mutation path.

## Effort and Parallelization Impact

Two slice estimates increased:

- VS-003 moved from M to L.
- VS-015 moved from M to L.

The parallel-effort summary is now less optimistic:

- Phase 0 changed from `3L` parallel best case to `4L`.
- Phase 1 changed from `XL + L` to `XL + 2L`.
- Phase 2 changed from `2XL` to `2XL + L`.
- Phase 3 changed from `L + M` to `2L`.

Total serial effort is now `4XL + 13L + 13M`. Total parallel best case is now `4XL + 9L + 2M`.

## Drift Check

- No value slices were dropped.
- No slice moved to a different phase.
- No new features were introduced.
- The revision is limited to ownership correction, contract specification, and effort recalibration.
