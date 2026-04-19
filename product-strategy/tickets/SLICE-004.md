# SLICE-004: Scheduler and deferred-effects backbone

## Parent

**Initiative:** Phase 0 foundation slice
**Phase:** Phase 0

## What Changes for the Operator

Operators gain the reliability substrate required for time-based work and safe cross-subsystem recovery. Scheduled jobs, deferred effects, and degraded-state summaries exist before any slice starts relying on asynchronous enforcement or recovery.

## Justification Chain

**Market signal:** Cross-cutting findings validate graceful-degradation and portability as differentiators because the market repeatedly ties operational continuity to unstable vendors or brittle dashboards.
**Problem axis:** §14 — Consolidated Failure Risk and Operational Availability
**Proposal mechanism:** proposal.md, Cross-cutting Concerns -> Graceful Degradation
**Philosophy principles:** Principle 2: Live-Server Safety, Principle 9: Volunteer-Aware Design, Principle 12: Graceful Degradation

## Technical Specification

**Schema objects:**
- ScheduledJobRead: durable job registration and next-run state
- DeferredEffectRead: queued cross-subsystem effects with consequence level and precondition status
- DegradedStateSummaryRead: subsystem-level pending-effect visibility

**API endpoints:**
- none

**Discord interactions:**
- none

**State transitions:**
- deferred effect unchecked -> valid/invalid precondition state
- scheduled job registered -> persists across restart

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-008A | Scheduler Foundation | `services/api/app/contracts/scheduler.py` | migrations/versions/wu-008a_scheduler_foundation.py, services/api/app/contracts/scheduler.py, services/api/app/repositories/scheduler.py, services/api/app/services/scheduler.py, services/api/tests/test_scheduler_foundation.py |
| WU-008B | Deferred-Effect Foundation | `services/api/app/contracts/scheduler.py` | migrations/versions/wu-008b_deferred_effect_foundation.py, services/api/app/contracts/scheduler.py, services/api/app/repositories/deferred_effects.py, services/api/app/services/deferred_effects.py, services/api/app/tasks/__init__.py, services/api/tests/test_deferred_effect_foundation.py |

## Dependencies

**Upstream slices:** none
**Foundation dependencies:** SLICE-001, SLICE-002
**Parallelizable with:** SLICE-003, SLICE-006

## Acceptance Criteria

- [ ] Scheduled jobs survive service restart and keep stable identity independent from next-run state.
- [ ] Consequential deferred effects never execute without explicit precondition validation state.
- [ ] Deferred effects remain queryable independently from scheduled jobs.
- [ ] The degraded-state summary exposes queued effects by subsystem without blocking unrelated writes.

## Engineering Notes

**Effort:** Scheduler -> L-XL (leans L); Graceful degradation mechanics -> M-L (leans M)
**Prototyping:** Scheduler -> yes; Graceful degradation mechanics -> conditional
**Risk:** High — later SLA, notification, compliance, chapter, and permission lifecycle work all rely on this substrate behaving safely under outage and retry.
**Existing code:** No completed workload substrate exists; this is new infrastructure work on top of the current runtime shell.
**Known challenges:** Separating safe deferred recording from consequence-bearing deferred execution without introducing hidden cross-subsystem coupling.
