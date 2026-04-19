# SLICE-023: Chapter governance lifecycle

## Parent

**Initiative:** INIT-005 — Chapter Operations
**Phase:** Phase 4

## What Changes for the Operator

Operators can place chapters on probation, generate an archive plan that enumerates pending work, and execute archival through one shared correlation chain instead of shutting down a chapter through ad hoc cleanup and memory.

## Justification Chain

**Market signal:** Chapter-management research found provisioning and lifecycle governance to be under-monetized and lightly served even in premium multi-guild suites.
**Problem axis:** §5 — Sub-community Provisioning and Lifecycle
**Proposal mechanism:** proposal.md, Sub-community Lifecycle -> Chapter lifecycle states; Operational Workflows -> Chapter Lifecycle
**Philosophy principles:** Principle 2: Live-Server Safety, Principle 7: Delegated Authority with Accountability, Principle 10: Durable State over Ephemeral State

## Technical Specification

**Schema objects:**
- Chapter: extended states `probation`, `archiving`, `archived` on the chapter aggregate
- ChapterArchivePlanRead: pending applications, open tickets, active grants, unresolved deferred effects
- ChapterArchiveExecuteRequest: transfer/closure execution under one shared reason and correlation chain

**API endpoints:**
- POST /api/v1/chapters/{chapter_id}/governance-transitions -> ChapterRead
- GET /api/v1/chapters/{chapter_id}/archive-status
- GET /api/v1/chapters/{chapter_id}/archive-plan -> ChapterArchivePlanRead
- POST /api/v1/chapters/{chapter_id}/archive-execute

**Discord interactions:**
- none directly in this slice

**State transitions:**
- active -> probation -> active
- active/probation -> archiving -> archived

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-042 | Chapter Governance Lifecycle API | `services/api/app/contracts/chapters.py` | services/api/app/contracts/chapters.py, services/api/app/services/chapters.py, services/api/app/api/v1/endpoints/chapters/governance.py, services/api/tests/test_chapter_governance.py |
| WU-043A | Chapter Archive Plan API | `services/api/app/contracts/chapters.py` | services/api/app/contracts/chapters.py, services/api/app/services/chapters.py, services/api/app/api/v1/endpoints/chapters/archive.py, services/api/tests/test_chapter_archive_plan.py |
| WU-043B | Chapter Archive Execution Worker | `services/api/app/contracts/chapters.py` | services/api/app/contracts/chapters.py, services/api/app/tasks/archive.py, services/api/app/services/chapters.py, services/api/tests/test_chapter_archive_execution.py |

## Dependencies

**Upstream slices:** SLICE-008, SLICE-009, SLICE-011, SLICE-012, SLICE-013
**Foundation dependencies:** SLICE-004
**Parallelizable with:** SLICE-022

## Acceptance Criteria

- [ ] Chapter governance transitions require current version and a non-empty reason where the contract demands it.
- [ ] A chapter cannot be marked archived until archive prerequisites are satisfied; premature archive attempts return 409 Conflict.
- [ ] Archive-plan output enumerates pending applications, open tickets, active grants, and queued consequential effects without mutating them.
- [ ] Archive execution is idempotent, shares one correlation chain across transferred or closed dependencies, and surfaces stale preconditions as deferred work instead of executing blindly.

## Engineering Notes

**Effort:** VS-017 -> M-L (leans M)
**Prototyping:** VS-017 -> no
**Risk:** Medium — the main risk is cross-subsystem pending-work handling and safe state transitions once more mature chapter operations exist.
**Existing code:** Extends the chapter and deferred-effect substrates; no approved archive or probation workflow exists today.
**Known challenges:** Preserving state and causal context during archive execution without tightly coupling application, ticket, and chapter storage models.
