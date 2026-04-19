# SLICE-009: Audit trail with causal correlation

## Parent

**Initiative:** INIT-001 — Governance Infrastructure
**Phase:** Phase 1

## What Changes for the Operator

Operators can query immutable audit history by entry, correlation chain, or backtrace and see one decision sequence instead of piecing together logs from separate tools. Discord-originated API calls preserve the same causal context end to end.

## Justification Chain

**Market signal:** Governance research repeatedly found audit depth to be fragmented, local, and retention-limited rather than cross-workflow and causal.
**Problem axis:** §4 — Audit Trail and Long-term Accountability
**Proposal mechanism:** proposal.md, Governance -> AuditEntry; Governance Mechanisms -> Audit Chain
**Philosophy principles:** Principle 1: Operator Clarity, Principle 10: Durable State over Ephemeral State, Principle 15: Traceability as Outcome

## Technical Specification

**Schema objects:**
- AuditEntry: `action_type`, `target_type`, `target_id`, `scope`, `correlation_id`, `causation_id`, policy/context snapshots
- ApiRequestContext / ApiRequestHeaders: correlation propagation across Discord->API calls

**API endpoints:**
- GET /api/v1/audit/{entry_id} -> AuditEntryRead
- GET /api/v1/audit?correlation_id={uuid} -> list[AuditEntryRead]
- GET /api/v1/audit/{entry_id}/chain -> list[AuditEntryRead]

**Discord interactions:**
- Discord API transport attaches correlation and optional causation headers on downstream API calls

**State transitions:**
- root audit event -> downstream causally linked chain
- audit query entry -> backward chain reconstruction to root

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-016A | Audit Query API | `services/api/app/contracts/audit.py` | services/api/app/api/v1/endpoints/audit.py, services/api/app/repositories/audit.py, services/api/app/services/audit_queries.py, services/api/tests/test_audit_api.py |
| WU-016B | Discord Correlation Propagation Adapter | `services/discord/app/contracts/api_transport.py` | services/discord/app/contracts/api_transport.py, services/discord/app/core/request_context.py, services/discord/tests/test_api_context.py |

## Dependencies

**Upstream slices:** SLICE-008
**Foundation dependencies:** SLICE-002, SLICE-006
**Parallelizable with:** none

## Acceptance Criteria

- [ ] Querying by correlation_id returns the full causal chain ordered by timestamp.
- [ ] Querying an entry's chain walks causation links back to the root event.
- [ ] Scoped audit queries reuse the authority guard instead of duplicating permission checks.
- [ ] Discord-originated API calls preserve correlation context and leave missing causation IDs null rather than inventing them locally.

## Engineering Notes

**Effort:** VS-003 -> M
**Prototyping:** VS-003 -> no
**Risk:** Medium — the risk is partial discipline across subsystems; later workflows only get the promised reconstructability if this slice stays universal.
**Existing code:** Phase 0 audit contracts and the Discord transport shell provide the hookpoints; no full audit query surface exists yet.
**Known challenges:** Preserving correlation across API and Discord seams without leaking Discord-specific request shapes into API contracts.
