# SLICE-014: Permission intent and drift detection

## Parent

**Initiative:** INIT-006 — Permission Management
**Phase:** Phase 2

## What Changes for the Operator

Operators can record what permission state should exist, run reconciliation against live Discord state, and resolve or accept drift explicitly instead of treating permissions as a pile of one-off overrides and logs.

## Justification Chain

**Market signal:** Permission/security research found declared-state reconciliation to be under-served despite strong demand for role automation, recovery, and governance visibility.
**Problem axis:** §7 — Permission Model and State Explosion
**Proposal mechanism:** proposal.md, Permission Management; Operational Workflows -> Permission Reconciliation
**Philosophy principles:** Principle 1: Operator Clarity, Principle 7: Delegated Authority with Accountability, Principle 13: Derived State Transparency

## Technical Specification

**Schema objects:**
- PermissionIntent: `scope`, `role_id`, optional `channel_id`, `permission_bits`, `reason`, `temporary`, `expires_at?`, `version`
- PermissionDrift: `permission_intent_id?`, `actual_bits`, `intended_bits?`, `status`, resolution fields, `version`
- PermissionReconciliationRun: requested scope, submitted snapshot, run status, drift IDs

**API endpoints:**
- POST /api/v1/permission-intents -> PermissionIntentRead
- PATCH /api/v1/permission-intents/{intent_id} -> PermissionIntentRead
- GET /api/v1/permission-intents?scope_kind={kind}&scope_id={id} -> list[PermissionIntentRead]
- GET /api/v1/permission-drift -> list[PermissionDriftRead]
- POST /api/v1/permission-drift/{drift_id}/resolve -> PermissionDriftRead
- POST /api/v1/permission-reconciliation/runs -> PermissionReconciliationRunRead
- POST /api/v1/permission-reconciliation/runs/{run_id}/snapshots -> PermissionReconciliationRunRead
- handler: submit_permission_snapshot(command: ReconciliationRunCommand) -> PermissionReconciliationSubmissionRead

**Discord interactions:**
- Discord reconciliation adapter fetches actual role/channel permission state for a scope and submits a typed snapshot to the API

**State transitions:**
- drift detected -> acknowledged/reconciled/accepted
- reconciliation run received -> reconciled/failed

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-027 | Permission Intent Management API | `services/api/app/contracts/permissions.py` | migrations/versions/wu-027_permission_intents.py, services/api/app/contracts/permissions.py, services/api/app/repositories/permissions.py, services/api/app/services/permissions.py, services/api/app/api/v1/endpoints/permissions/intents.py, services/api/tests/test_permission_intents.py |
| WU-028A | Permission Drift Read And Resolution API | `services/api/app/contracts/permissions.py` | migrations/versions/wu-028a_permission_drift_api.py, services/api/app/contracts/permissions.py, services/api/app/repositories/permissions.py, services/api/app/services/permissions.py, services/api/app/api/v1/endpoints/permissions/drift.py, services/api/tests/test_permission_drift.py |
| WU-028B-api | Permission Reconciliation Run API | `services/api/app/contracts/permissions.py` | services/api/app/contracts/permissions.py, services/api/app/repositories/permissions.py, services/api/app/services/permission_reconciliation.py, services/api/app/api/v1/endpoints/permissions/reconciliation.py, services/api/tests/test_permission_reconciliation_api.py |
| WU-028B-discord | Discord Permission Snapshot Adapter | `services/api/app/contracts/permissions.py` | services/discord/app/contracts/permissions.py, services/discord/app/infrastructure/permission_client.py, services/discord/app/handlers/permissions.py, services/discord/tests/test_permission_reconciliation_adapter.py |

## Dependencies

**Upstream slices:** SLICE-008, SLICE-009
**Foundation dependencies:** SLICE-003, SLICE-006
**Parallelizable with:** SLICE-011, SLICE-012, SLICE-013, SLICE-015, SLICE-016

## Acceptance Criteria

- [ ] Creating or updating an intent persists the exact scope, role/channel target, bitset, and reason, with stale updates rejected by 412 Precondition Failed.
- [ ] Drift reads include both intent-linked and orphaned Discord state and resolving with stale version returns 412 Precondition Failed.
- [ ] Reconciliation runs create drift rows both for mismatches against declared intent and for unmanaged Discord state with no matching intent.
- [ ] The Discord snapshot adapter never mutates drift rows locally and reuses the API run ID as the idempotency key on retry.

## Engineering Notes

**Effort:** VS-008 -> XL
**Prototyping:** VS-008 -> yes
**Risk:** High — this slice introduces the most novel control-plane model in Phase 2 and must keep orphaned state, intended state, and live Discord snapshots distinguishable.
**Existing code:** No declared-intent control plane exists today; Phase 0 permission schemas and the Discord transport shell are the main reuse points.
**Known challenges:** Handling hybrid managed/unmanaged permission state without hiding the boundary from operators.
