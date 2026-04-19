# SLICE-008: Scoped authority with enforcement

## Parent

**Initiative:** INIT-001 — Governance Infrastructure
**Phase:** Phase 1

## What Changes for the Operator

Operators can grant and revoke authority explicitly for a defined scope, and later write surfaces deny out-of-scope actions automatically. This replaces informal reliance on ranked Discord roles with a durable delegation model that still leaves an audit trail.

## Justification Chain

**Market signal:** Governance and permission research show granular permissions exist in the market, but scoped delegation with auditable enforcement remains absent.
**Problem axis:** §10 — Delegated Authority and Governance
**Proposal mechanism:** proposal.md, Governance -> AuthorityGrant; Governance Mechanisms -> Authority Scope Enforcement
**Philosophy principles:** Principle 6: Trust and Safety, Principle 7: Delegated Authority with Accountability, Principle 15: Traceability as Outcome

## Technical Specification

**Schema objects:**
- AuthorityGrant: `grantee_id`, `scope`, `permissions`, expiry/revocation fields, `predecessor_grant_id`, `version`
- AuthorityDecisionRead: allow/deny result with optional override flag and denial reason

**API endpoints:**
- POST /api/v1/authority-grants -> AuthorityGrantRead
- GET /api/v1/authority-grants?grantee_id={uuid}&scope_kind={kind}&scope_id={id}
- POST /api/v1/authority-grants/{grant_id}/revoke -> AuthorityGrantRead

**Discord interactions:**
- none in this slice; later Discord handlers consume the enforcement surface

**State transitions:**
- grant active -> revoked
- request without matching grant -> 403 denied
- request with explicit override + reason -> allowed with override audit

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-014 | Authority Grant Lifecycle API | `services/api/app/contracts/authority.py` | migrations/versions/wu-014_authority_api.py, services/api/app/contracts/authority.py, services/api/app/repositories/authority.py, services/api/app/services/authority.py, services/api/app/api/v1/endpoints/authority.py, services/api/tests/test_authority.py |
| WU-015A | Authority Enforcement Guard | `services/api/app/contracts/authority.py` | services/api/app/contracts/authority.py, services/api/app/core/dependencies.py, services/api/app/services/authority.py, services/api/tests/test_authority_enforcement.py |
| WU-015B | Override Audit Policy | `services/api/app/contracts/authority.py` | services/api/app/contracts/authority.py, services/api/app/services/authority.py, services/api/app/services/audit_overrides.py, services/api/tests/test_authority_override_audit.py |

## Dependencies

**Upstream slices:** none
**Foundation dependencies:** SLICE-002, SLICE-005
**Parallelizable with:** SLICE-007

## Acceptance Criteria

- [ ] Grant creation persists scope, permissions, and optional expiry exactly as requested.
- [ ] Revocation records revoked_at, revoked_by, and revocation_reason.
- [ ] A guarded write surface returns 403 when the actor lacks a matching grant and succeeds when the grant covers the requested scope and permission.
- [ ] Every successful override requires a non-empty reason and records an override-used audit event under the active correlation ID.

## Engineering Notes

**Effort:** VS-002 -> L
**Prototyping:** VS-002 -> conditional
**Risk:** High — this becomes the cross-cutting authorization surface for later mutations, so scope mistakes carry system-wide blast radius.
**Existing code:** Leverage the shared contracts introduced in Phase 0; no production authority model currently exists.
**Known challenges:** Making scoped denial paths explicit and reusable so later surfaces do not fork their own permission logic.
