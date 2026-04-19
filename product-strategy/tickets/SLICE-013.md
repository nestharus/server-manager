# SLICE-013: Chapter provisioning from templates

## Parent

**Initiative:** INIT-005 — Chapter Operations
**Phase:** Phase 2

## What Changes for the Operator

Operators can create chapter templates, propose a chapter from a selected template, and provision the corresponding Discord roles and channels through an explicit lifecycle instead of assembling chapter infrastructure by hand.

## Justification Chain

**Market signal:** Chapter-management research found strong demand for multi-unit organization but little evidence of provisioning automation or explicit lifecycle control.
**Problem axis:** §5 — Sub-community Provisioning and Lifecycle
**Proposal mechanism:** proposal.md, Sub-community Lifecycle; Operational Workflows -> Chapter Lifecycle
**Philosophy principles:** Principle 2: Live-Server Safety, Principle 7: Delegated Authority with Accountability, Principle 11: Configuration by Operators, Not Developers

## Technical Specification

**Schema objects:**
- ChapterTemplate: `name`, `channel_structure`, `role_structure`, `default_permission_intents`, `version`
- Chapter: `name`, `template_id`, `state`, `discord_resources`, `configuration`, `created_at`, `archived_at?`
- ChapterTransition: `from_state`, `to_state`, `actor_id`, `reason`, `timestamp`

**API endpoints:**
- PATCH /api/v1/chapter-templates/{template_id} -> ChapterTemplateRead
- GET /api/v1/chapter-templates/{template_id} -> ChapterTemplateRead
- POST /api/v1/chapter-templates -> ChapterTemplateRead
- POST /api/v1/chapters -> ChapterRead
- POST /api/v1/chapters/{chapter_id}/transitions -> ChapterRead
- GET /api/v1/chapters/{chapter_id} -> ChapterRead
- handler: provision_chapter(command) -> ChapterProvisionResult

**Discord interactions:**
- chapter provision command creates the Discord category, roles, and channels defined by the selected template and then confirms the result through the API

**State transitions:**
- chapter proposed -> provisioning -> active

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-018 | Chapter Template Management API | `services/api/app/contracts/chapter_templates.py` | migrations/versions/wu-018_chapter_templates.py, services/api/app/contracts/chapter_templates.py, services/api/app/repositories/chapter_templates.py, services/api/app/services/chapter_templates.py, services/api/app/api/v1/endpoints/chapters/templates.py, services/api/tests/test_chapter_templates.py |
| WU-019 | Chapter Lifecycle API | `services/api/app/contracts/chapters.py` | migrations/versions/wu-019_chapter_lifecycle.py, services/api/app/contracts/chapters.py, services/api/app/repositories/chapters.py, services/api/app/services/chapters.py, services/api/app/api/v1/endpoints/chapters/lifecycle.py, services/api/tests/test_chapter_lifecycle.py |
| WU-020 | Discord Chapter Provisioning Workflow | `services/discord/app/contracts/chapters.py` | services/discord/app/contracts/chapters.py, services/discord/app/commands/chapters.py, services/discord/app/handlers/chapters.py, services/discord/tests/test_chapter_provisioning.py |

## Dependencies

**Upstream slices:** SLICE-008, SLICE-009, SLICE-010
**Foundation dependencies:** SLICE-003, SLICE-004, SLICE-005, SLICE-006
**Parallelizable with:** SLICE-011, SLICE-012, SLICE-014, SLICE-015, SLICE-016

## Acceptance Criteria

- [ ] Template create/update persists channel and role structure and rejects stale updates with 412 Precondition Failed.
- [ ] Creating a chapter returns proposed state and the selected template reference.
- [ ] Provisioning moves proposed -> provisioning -> active only after verified Discord resource IDs are persisted through the API.
- [ ] A failed Discord provisioning step queues a consequential deferred effect instead of partially marking the chapter active.

## Engineering Notes

**Effort:** VS-005 -> L-XL (leans L)
**Prototyping:** VS-005 -> yes
**Risk:** High — this is the highest-fanout live Discord resource workflow in the roadmap and later chapter work depends on it.
**Existing code:** The current chapter API proof point is the strongest local analogue and should be reused for layering and lifecycle semantics.
**Known challenges:** Keeping the slice template-driven and approval-gated without expanding into later chapter editing, archival, or roster-management scope.
