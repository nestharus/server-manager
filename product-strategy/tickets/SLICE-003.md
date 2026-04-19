# SLICE-003: Permission and chapter core schemas

## Parent

**Initiative:** Phase 0 foundation slice
**Phase:** Phase 0

## What Changes for the Operator

The platform gains durable, versioned core objects for chapter templates, chapter roles, rosters, permission intent, and permission drift. Later operational slices can build on named aggregates instead of inventing feature-local JSON or Discord-only state.

## Justification Chain

**Market signal:** Permission-management and chapter-management research both found missing declared-state control planes and weak lifecycle-grade chapter administration.
**Problem axis:** §5 — Sub-community Provisioning and Lifecycle
**Proposal mechanism:** proposal.md, Sub-community Lifecycle; Permission Management
**Philosophy principles:** Principle 5: Low Lock-in, Principle 10: Durable State over Ephemeral State, Principle 11: Configuration by Operators, Not Developers

## Technical Specification

**Schema objects:**
- PermissionIntent / PermissionDrift: intended permission state plus divergence records
- ChapterTemplate: stored channel, role, and default-permission blueprint
- ChapterRole: ordered chapter governance role with succession metadata
- RosterEntry: chapter/member/role lifecycle identity

**API endpoints:**
- none

**Discord interactions:**
- none

**State transitions:**
- permission drift detected -> acknowledged/reconciled/accepted
- roster status active -> on_leave/under_review/removed

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-006A | Permission Intent Foundation | `services/api/app/contracts/permissions.py` | migrations/versions/wu-006a_permission_intents_foundation.py, services/api/app/contracts/permissions.py, services/api/app/repositories/permissions.py, services/api/app/services/permissions.py, services/api/tests/test_permission_intent_foundation.py |
| WU-006B | Permission Drift Foundation | `services/api/app/contracts/permissions.py` | migrations/versions/wu-006b_permission_drift_foundation.py, services/api/app/contracts/permissions.py, services/api/app/repositories/permissions.py, services/api/app/services/permissions.py, services/api/tests/test_permission_drift_foundation.py |
| WU-007A | Chapter Template Foundation | `services/api/app/contracts/chapter_templates.py` | migrations/versions/wu-007a_chapter_templates_foundation.py, services/api/app/contracts/chapter_templates.py, services/api/app/repositories/chapter_templates.py, services/api/app/services/chapter_templates.py, services/api/tests/test_chapter_template_foundation.py |
| WU-007B | Chapter Role Foundation | `services/api/app/contracts/chapter_roles.py` | migrations/versions/wu-007b_chapter_roles_foundation.py, services/api/app/contracts/chapter_roles.py, services/api/app/repositories/chapter_roles.py, services/api/app/services/chapter_roles.py, services/api/tests/test_chapter_role_foundation.py |
| WU-007C | Roster Foundation | `services/api/app/contracts/roster.py` | migrations/versions/wu-007c_roster_foundation.py, services/api/app/contracts/roster.py, services/api/app/repositories/roster.py, services/api/app/services/roster.py, services/api/tests/test_roster_foundation.py |

## Dependencies

**Upstream slices:** none
**Foundation dependencies:** SLICE-001, SLICE-002
**Parallelizable with:** SLICE-004, SLICE-006

## Acceptance Criteria

- [ ] Permission intents and drift rows round-trip as documented exportable contracts.
- [ ] Temporary permission intents require expires_at and reject invalid update shapes.
- [ ] Chapter templates preserve channel structure, role structure, and default permission intents separately.
- [ ] Roster entries remain versioned and tied to stable chapter-role identity for later lifecycle transitions.

## Engineering Notes

**Effort:** Permission intent foundation -> L-XL (leans L); Chapter role and roster entry foundation -> M-L (leans M)
**Prototyping:** Permission intent foundation -> yes; Chapter role and roster entry foundation -> no
**Risk:** Medium — these are schema foundations rather than direct operator workflows, but they define the aggregates later slices must not need to rework.
**Existing code:** Use the current `services/api/` layering as the pattern; no durable implementation currently exists for these aggregates.
**Known challenges:** Keeping foundation schemas sufficiently complete for downstream slices without over-designing later operator behavior inside Phase 0.
