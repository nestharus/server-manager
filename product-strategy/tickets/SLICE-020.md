# SLICE-020: Temporary permission management

## Parent

**Initiative:** INIT-006 — Permission Management
**Phase:** Phase 3

## What Changes for the Operator

Operators can renew temporary permission intents through the API and rely on an expiry worker to surface expired overrides as drift instead of hoping someone remembers to clean them up later.

## Justification Chain

**Market signal:** Permission research found no support for temporal intent tracking even though forgotten temporary overrides are a recurring governance failure mode.
**Problem axis:** §7 — Permission Model and State Explosion
**Proposal mechanism:** proposal.md, Permission Management -> PermissionIntent temporary lifecycle
**Philosophy principles:** Principle 7: Delegated Authority with Accountability, Principle 13: Derived State Transparency, Principle 14: Graduated Consequence

## Technical Specification

**Schema objects:**
- PermissionIntent: temporary flag and `expires_at` become an enforced lifecycle instead of optional metadata
- PermissionDrift: expired-intent drift rows created by the expiry worker

**API endpoints:**
- POST /api/v1/permission-intents/{intent_id}/renew -> PermissionIntentRead
- POST /api/v1/permission-intents/expire/run
- scheduled handler: expire_temporary_permission_intents() -> list[PermissionDriftRead]

**Discord interactions:**
- none directly; expiry flows through the stable reconciliation adapter rather than inline Discord mutation

**State transitions:**
- temporary intent active -> renewed
- temporary intent expired -> drift entry created

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-038A | Temporary Permission Renewal API | `services/api/app/contracts/permissions.py` | services/api/app/contracts/permissions.py, services/api/app/services/permissions.py, services/api/app/api/v1/endpoints/permissions/temporary.py, services/api/tests/test_permission_temporary_api.py |
| WU-038B | Temporary Permission Expiry Worker | `services/api/app/contracts/permissions.py` | services/api/app/contracts/permissions.py, services/api/app/contracts/scheduler.py, services/api/app/tasks/permission_expiry.py, services/api/app/services/permissions.py, services/api/tests/test_permission_temporary_worker.py |

## Dependencies

**Upstream slices:** SLICE-008, SLICE-009, SLICE-014, SLICE-015
**Foundation dependencies:** SLICE-004
**Parallelizable with:** SLICE-018, SLICE-019, SLICE-021

## Acceptance Criteria

- [ ] Renewing a temporary intent with the current version updates expires_at, while stale renewal returns 412 Precondition Failed.
- [ ] Renewal is rejected for non-temporary intents.
- [ ] The expiry worker creates drift entries for expired temporary intents and remains idempotent on rerun.
- [ ] Expired intents flow through the stable reconciliation path instead of mutating Discord-managed state inline.

## Engineering Notes

**Effort:** VS-014 -> M-L (leans M)
**Prototyping:** VS-014 -> no
**Risk:** Medium — the slice rides on the intent/drift model established earlier, but lifecycle mistakes still compound permission-state complexity over time.
**Existing code:** Extends the permission intent/drift APIs, scheduler, and reconciliation adapter from the prior phase.
**Known challenges:** Ensuring expiry creates an explainable review surface rather than silently deleting or mutating access state.
