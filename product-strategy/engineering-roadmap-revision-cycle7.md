# Engineering Roadmap Revision Cycle 7

## Objective

Apply the systematic sizing upgrades required by the latest feasibility pass without dropping slices, reordering phases, or expanding proposal scope.

## Result

Cycle 7 is applied in `product-strategy/engineering roadmap.md`. The roadmap keeps the same phase ordering and slice set, but tightens sizing, gate wording, and slack policy where the feasibility review found underestimation.

## Revisions Applied

| Fix | Change applied |
|---|---|
| F-1 | Phase 0 graceful degradation mechanics upgraded from M to L and explicitly framed as cross-slice mechanics rather than a local helper. |
| F-2 | Phase 0 scheduler remains L. The roadmap now states that scheduler technology selection between APScheduler, Celery Beat, or a built-in scheduler is an explicit Phase 0 deliverable and remains open. |
| F-3 | Phase 0 deployable service substrate upgraded from M to L, with zero-baseline repo state called out directly in the foundation item. |
| F-4 | VS-002 now carries an explicit 25% schedule buffer because it is the Phase 1 critical-path contract gate with the largest downstream blast radius. |
| F-5 | The VS-008 gate for VS-005 is sharpened to concrete acceptance criteria: committed `PermissionIntent` schema migration, frozen `snapshot_permissions(chapter_id) -> PermissionDiff`, frozen `reconcile_permissions(diff, mode)`, and a working `diff` endpoint. |
| F-6 | VS-009 keeps L sizing, but its scope is now broken into `NotificationRule` schema plus CRUD, subscription mechanism, Discord delivery via platform adapter, and causal grouping of notification bursts. |
| F-7 | VS-016 risk factors now explicitly name Google Cloud Vision API, Gemini API fallback, and scheduler dependency concentration. The roadmap also states that VS-016 is the highest-uncertainty slice and should not be compressed under schedule pressure. |
| F-8 | VS-010 is upgraded from M to L. The reasoning now reflects signal collection, endorsement workflow, recomputation triggers, and officer management surface. |
| F-9 | The roadmap now includes an explicit migration plan for Phase 0 minimal `RosterEntry` rows, and VS-011 acceptance criteria now require migration into the full lifecycle schema with no data loss and no state regression. |
| F-11 | Buffer policy is restated as 20% on all L items, 30% on all XL items, with 25% critical-path overrides on VS-002 and VS-008. |

## Aggregate Impact

- Phase 0 foundation mix changed from `6L + 7M` to `8L + 6M`.
- Phase 2 changed from `2XL + 4L + M` to `2XL + 5L`.
- Total serial roadmap mix changed from `4XL + 15L + 12M` to `4XL + 18L + 10M`.
- Critical-path wording is now explicit about VS-002 and VS-008 buffers and the Phase 4 uncertainty concentration around VS-016.

## Guardrail Check

- No slices were dropped.
- No phases were reordered.
- No new feature scope was added beyond the proposal. The edits are sizing, gate, migration, and slack clarifications only.
