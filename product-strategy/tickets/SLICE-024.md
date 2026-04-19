# SLICE-024: Leadership succession with context transfer

## Parent

**Initiative:** INIT-005 — Chapter Operations
**Phase:** Phase 4

## What Changes for the Operator

Operators can generate a succession plan, transfer scoped authority to a designated successor, hand off pending applications and tickets, and query the successor's inherited context instead of reconstructing leadership turnover from memory.

## Justification Chain

**Market signal:** Chapter-management research found succession and delegated-local-authority continuity to remain implicit rather than modeled across the reviewed field.
**Problem axis:** §5 — Sub-community Provisioning and Lifecycle
**Proposal mechanism:** proposal.md, Governance -> AuthorityGrant predecessor linkage; Sub-community Lifecycle -> ChapterRole succession metadata
**Philosophy principles:** Principle 7: Delegated Authority with Accountability, Principle 10: Durable State over Ephemeral State, Principle 15: Traceability as Outcome

## Technical Specification

**Schema objects:**
- AuthorityGrant: transfer creates successor grant with `predecessor_grant_id` linkage
- ChapterRole: `triggers_succession` metadata drives succession planning
- SuccessionPlanRead / LeadershipContextRead: pending work and inherited operational context views

**API endpoints:**
- GET /api/v1/chapters/{chapter_id}/succession-plan -> SuccessionPlanRead
- POST /api/v1/authority-grants/{grant_id}/transfer -> AuthorityGrantRead
- POST /api/v1/authority-grants/{grant_id}/handoff/applications -> ApplicationHandoffRead
- POST /api/v1/authority-grants/{grant_id}/handoff/tickets -> TicketHandoffRead
- GET /api/v1/members/{member_id}/leadership-context -> LeadershipContextRead

**Discord interactions:**
- none directly in this slice

**State transitions:**
- role holder departs -> succession plan available
- authority transfer executed -> pending applications and tickets handed off or flagged
- leadership context view updated from projection state

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-044A | Succession Plan API | `services/api/app/contracts/authority.py` | services/api/app/contracts/authority.py, services/api/app/services/authority.py, services/api/app/api/v1/endpoints/authority/succession_plan.py, services/api/tests/test_succession_plan.py |
| WU-044B | Authority Transfer API | `services/api/app/contracts/authority.py` | services/api/app/contracts/authority.py, services/api/app/services/authority.py, services/api/app/api/v1/endpoints/authority/transfer.py, services/api/tests/test_authority_transfer.py |
| WU-045A-applications | Pending Application Handoff Execution | `services/api/app/contracts/authority.py` | services/api/app/contracts/applications.py, services/api/app/services/leadership_handoff_applications.py, services/api/app/api/v1/endpoints/authority/handoff_applications.py, services/api/tests/test_leadership_handoff_applications.py |
| WU-045A-tickets | Pending Ticket Handoff Execution | `services/api/app/contracts/authority.py` | services/api/app/contracts/tickets.py, services/api/app/services/leadership_handoff_tickets.py, services/api/app/api/v1/endpoints/authority/handoff_tickets.py, services/api/tests/test_leadership_handoff_tickets.py |
| WU-045B | Leadership Context View API | `services/api/app/contracts/read_models.py` | services/api/app/contracts/read_models.py, services/api/app/services/read_models.py, services/api/app/api/v1/endpoints/authority/leadership_context.py, services/api/tests/test_leadership_context.py |

## Dependencies

**Upstream slices:** SLICE-008, SLICE-009, SLICE-011, SLICE-012, SLICE-017, SLICE-018, SLICE-023
**Foundation dependencies:** none
**Parallelizable with:** none

## Acceptance Criteria

- [ ] A succession-triggering departure produces a queryable plan even when no successor is designated, and no automatic authority transfer occurs without that designation.
- [ ] Authority transfer creates a new grant linked to the predecessor and reuses the existing grant lifecycle path instead of bypassing audit.
- [ ] Application and ticket handoff executions are idempotent and write one causal chain linking departure, grant transfer, and each handoff action.
- [ ] The leadership-context view reads from projection state and surfaces missing handoff state as an explicit stale-context signal rather than empty output.

## Engineering Notes

**Effort:** VS-018 -> M-L (leans M)
**Prototyping:** VS-018 -> no
**Risk:** Medium — succession spans authority, roster, chapter governance, and open work, so mistakes show up exactly when the organization is already changing leaders.
**Existing code:** Relies on the authority, chapter, roster, ticket, application, and read-model substrates established in earlier slices.
**Known challenges:** Preserving continuity without hard-coding cross-subsystem foreign-key coupling as the traceability mechanism.
