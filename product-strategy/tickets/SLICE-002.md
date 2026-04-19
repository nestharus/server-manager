# SLICE-002: Audit, authority, and policy event substrate

## Parent

**Initiative:** Phase 0 foundation slice
**Phase:** Phase 0

## What Changes for the Operator

Platform operators gain the shared governance contracts every later slice assumes: causal audit context, replayable notification events, durable authority grants, and preview-confirm policy versioning. This turns governance from a later feature into a substrate requirement.

## Justification Chain

**Market signal:** Governance research repeatedly found fragmented audit, absent scoped grants, and no public evidence of policy versioning or compare-and-swap configuration safety.
**Problem axis:** §4 — Audit Trail and Long-term Accountability
**Proposal mechanism:** proposal.md, Governance; Governance Mechanisms -> Policy Versioning, Authority Scope Enforcement, Audit Chain
**Philosophy principles:** Principle 1: Operator Clarity, Principle 7: Delegated Authority with Accountability, Principle 15: Traceability as Outcome

## Technical Specification

**Schema objects:**
- AuditEntry / AuditContext: correlation, causation, actor, and append-only decision history
- NotificationEventRead: replayable event envelope for downstream notification materialization
- AuthorityGrant / AuthorityRequirement: scope-bound grants and evaluation requirements
- PolicyPreview / PolicyVersion: preview-confirm policy lifecycle with stale-preview protection

**API endpoints:**
- none

**Discord interactions:**
- none

**State transitions:**
- policy preview -> confirm
- authority grant active -> revoked/expired
- audit event root -> downstream causally linked events

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-003 | Audit Registry And Correlation Context Foundation | `services/api/app/contracts/audit.py` | migrations/versions/wu-003_audit_foundation.py, services/api/app/contracts/audit.py, services/api/app/core/context.py, services/api/app/repositories/audit.py, services/api/app/services/audit.py, services/api/tests/test_audit_foundation.py |
| WU-003B | Notification Event Envelope Foundation | `services/api/app/contracts/notifications.py` | services/api/app/contracts/notifications.py, services/api/app/repositories/notification_events.py, services/api/app/services/notification_events.py, services/api/tests/test_notification_event_contract.py |
| WU-004 | Authority Grant Foundation | `services/api/app/contracts/authority.py` | migrations/versions/wu-004_authority_foundation.py, services/api/app/contracts/authority.py, services/api/app/repositories/authority.py, services/api/app/services/authority.py, services/api/tests/test_authority_foundation.py |
| WU-005 | Policy Version Preview-Confirm Foundation | `services/api/app/contracts/policies.py` | migrations/versions/wu-005_policy_foundation.py, services/api/app/contracts/policies.py, services/api/app/repositories/policies.py, services/api/app/services/policies.py, services/api/tests/test_policy_foundation.py |

## Dependencies

**Upstream slices:** none
**Foundation dependencies:** SLICE-001
**Parallelizable with:** none

## Acceptance Criteria

- [ ] Audit entries are immutable and preserve correlation and causation context across root and downstream events.
- [ ] Authority evaluation only allows operations whose scope and permission both match an active, unexpired grant.
- [ ] Policy preview captures current state without mutation, and confirming a stale preview returns 412 Precondition Failed.
- [ ] Notification event envelopes remain replayable after restart without changing downstream payload semantics.

## Engineering Notes

**Effort:** Audit and notification event contract -> M-L (leans M); Authority grant foundation -> L; Policy version framework -> M-L (leans M)
**Prototyping:** Audit and notification event contract -> no; Authority grant foundation -> conditional; Policy version framework -> no
**Risk:** High — these contracts become shared control surfaces for later mutations, so mistakes here propagate across the whole roadmap.
**Existing code:** Reuse the existing layered API seam; keep authority, audit, and policy as shared contracts rather than feature-local utilities.
**Known challenges:** Selecting one audit/action registry and one policy preview-confirm model that every later slice can inherit without compatibility shims.
