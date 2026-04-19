# SLICE-018: Roster management with role lifecycle

## Parent

**Initiative:** INIT-005 — Chapter Operations
**Phase:** Phase 3

## What Changes for the Operator

Operators can add members directly to a chapter roster, move them through chapter role and status transitions, and synchronize the resulting role set into Discord instead of maintaining roster truth in spreadsheets and role presence.

## Justification Chain

**Market signal:** Roster/activity research shows the strongest willingness-to-pay signal is integrated roster plus activity plus analytics, and communities still manage rosters across multiple surfaces today.
**Problem axis:** §5 — Sub-community Provisioning and Lifecycle
**Proposal mechanism:** proposal.md, Sub-community Lifecycle -> ChapterRole, RosterEntry, RosterTransition
**Philosophy principles:** Principle 7: Delegated Authority with Accountability, Principle 10: Durable State over Ephemeral State, Principle 11: Configuration by Operators, Not Developers

## Technical Specification

**Schema objects:**
- RosterEntry: `chapter_id`, `member_id`, `role_id`, `status`, removal metadata, `version`
- RosterTransition: `from_state`, `to_state`, optional role changes, `actor_id`, `reason`, `timestamp`
- ChapterRole: stable role identity and succession metadata consumed by roster transitions

**API endpoints:**
- POST /api/v1/roster-entries -> RosterEntryRead
- POST /api/v1/roster-entries/{roster_entry_id}/transitions -> RosterEntryRead
- GET /api/v1/roster-entries/{roster_entry_id} -> RosterEntryRead
- handler: sync_roster(event: RosterSyncEvent) -> RosterSyncResult

**Discord interactions:**
- roster sync handler adds or removes the configured chapter role set in Discord based on roster event state

**State transitions:**
- active -> on_leave/under_review/removed
- on_leave -> active/removed
- under_review -> active/removed

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-033 | Roster Lifecycle API | `services/api/app/contracts/roster.py` | migrations/versions/wu-033_roster.py, services/api/app/contracts/roster.py, services/api/app/repositories/roster.py, services/api/app/services/roster.py, services/api/app/api/v1/endpoints/roster.py, services/api/tests/test_roster.py |
| WU-034 | Discord Roster Role Synchronization Flow | `services/discord/app/contracts/roster.py` | services/discord/app/contracts/roster.py, services/discord/app/handlers/roster.py, services/discord/tests/test_roster_sync.py |

## Dependencies

**Upstream slices:** SLICE-008, SLICE-009, SLICE-013
**Foundation dependencies:** SLICE-003, SLICE-004, SLICE-006
**Parallelizable with:** SLICE-019, SLICE-020, SLICE-021

## Acceptance Criteria

- [ ] Direct roster add creates an active roster entry tied to a chapter role.
- [ ] Status and role transitions create a RosterTransition record with actor attribution and reason.
- [ ] Read with version N, transition with expected_version N, then retry with stale N returns 412 Precondition Failed.
- [ ] A failed Discord role update queues a consequential deferred effect instead of silently drifting.

## Engineering Notes

**Effort:** VS-011 -> L
**Prototyping:** VS-011 -> conditional
**Risk:** Medium — roster state touches chapters, authority, compliance, and Discord role synchronization, so lifecycle mistakes ripple outward quickly.
**Existing code:** Extends the chapter lifecycle substrate and the Discord runtime shell; no approved roster system exists yet.
**Known challenges:** Keeping roster truth in durable state while ensuring Discord role sync remains eventual and recoverable rather than implicit truth.
