# SLICE-017: Cross-subsystem operational views

## Parent

**Initiative:** INIT-001 — Governance Infrastructure
**Phase:** Phase 2

## What Changes for the Operator

Operators can open a shared operational overview fed by projection state instead of manually correlating applications, tickets, permissions, and deferred work across multiple tools or screens.

## Justification Chain

**Market signal:** Cross-cutting market findings show the reviewed field repeatedly fails to offer one decision chain spanning intake, cases, permissions, chapters, and compliance.
**Problem axis:** §12 — Cross-workflow State and Operational Continuity
**Proposal mechanism:** proposal.md, Cross-cutting Concerns -> Cross-workflow State Coherence; Graceful Degradation; Governance read-side patterns
**Philosophy principles:** Principle 1: Operator Clarity, Principle 12: Graceful Degradation, Principle 15: Traceability as Outcome

## Technical Specification

**Schema objects:**
- ReadModelCursorRead: projection cursor state for audit-driven materialization
- OperationalOverviewRead: open applications, open tickets, pending effects, drift count, stale projection flags

**API endpoints:**
- scheduled handler: project_audit_read_models() -> ReadModelCursorRead
- GET /api/v1/operations/overview -> OperationalOverviewRead

**Discord interactions:**
- none in this slice

**State transitions:**
- audit stream advances -> projection cursor advances
- projection stale/unavailable -> explicit stale signal rather than silent empty result

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-031 | Audit Projection Read-Model Pipeline | `services/api/app/contracts/read_models.py` | migrations/versions/wu-031_read_models.py, services/api/app/contracts/read_models.py, services/api/app/repositories/read_models.py, services/api/app/services/read_models.py, services/api/app/tasks/read_models.py, services/api/tests/test_read_models.py |
| WU-032 | Operational Views API | `services/api/app/contracts/read_models.py` | services/api/app/contracts/read_models.py, services/api/app/api/v1/endpoints/operations.py, services/api/app/services/read_models.py, services/api/tests/test_operational_views.py |

## Dependencies

**Upstream slices:** SLICE-008, SLICE-009, SLICE-014
**Foundation dependencies:** SLICE-004
**Parallelizable with:** none

## Acceptance Criteria

- [ ] The projector consumes audit events in causal order and resumes from the last persisted cursor on restart.
- [ ] Read-model lag or worker downtime does not block authoritative write-path operations.
- [ ] Operational overview reads only from projection tables and deferred-effect summaries.
- [ ] Missing projections surface stale-data signals instead of silent empty results, and unauthorized callers receive 403 for scoped views.

## Engineering Notes

**Effort:** VS-015 -> M-L (leans M)
**Prototyping:** VS-015 -> no
**Risk:** Medium — freshness and completeness matter because these views are only as good as the event discipline and projection cursor they rely on.
**Existing code:** Phase 0 scheduler plus Phase 1 audit chain provide the required substrate; there is no approved read-model pipeline yet.
**Known challenges:** Delivering operator-ergonomic views without violating the event-based traceability rule at the write layer.
