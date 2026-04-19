# SLICE-016: Advanced trust management

## Parent

**Initiative:** INIT-002 — Identity and Trust
**Phase:** Phase 2

## What Changes for the Operator

Operators can add trust signals beyond onboarding and request deterministic recomputation under the current trust policy instead of treating trust as a one-time join-screening score.

## Justification Chain

**Market signal:** Trust research found demand for richer operator trust views, but only indirect evidence for officer-managed signals and no reviewed product exposes inspectable recomputation.
**Problem axis:** §1 — Trust Calibration and Identity Verification
**Proposal mechanism:** proposal.md, Identity and Trust -> TrustSignal and TrustComputationConfig
**Philosophy principles:** Principle 6: Trust and Safety, Principle 11: Configuration by Operators, Not Developers, Principle 13: Derived State Transparency

## Technical Specification

**Schema objects:**
- TrustSignal: all signal types beyond platform metadata, including scope, value, source, expiry
- TrustComputationConfig: scope-specific weights, decay rules, thresholds, and version linkage
- TrustProfile: recomputed score/tier pinned to the governing config version

**API endpoints:**
- POST /api/v1/trust/signals -> TrustSignalRead
- POST /api/v1/trust/recompute/{member_id} -> TrustProfileRead

**Discord interactions:**
- none in this slice

**State transitions:**
- signal append -> trust profile unchanged until recompute requested
- recompute under current config -> new deterministic trust profile

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-030A | Trust Signal Management API | `services/api/app/contracts/trust.py` | migrations/versions/wu-030_trust_signals.py, services/api/app/contracts/trust.py, services/api/app/repositories/trust.py, services/api/app/services/trust.py, services/api/app/api/v1/endpoints/trust/signals.py, services/api/tests/test_trust_signals.py |
| WU-030B | Trust Recomputation Trigger API | `services/api/app/contracts/trust.py` | services/api/app/contracts/trust.py, services/api/app/services/trust.py, services/api/app/api/v1/endpoints/trust/recompute.py, services/api/tests/test_trust_recompute.py |

## Dependencies

**Upstream slices:** SLICE-007, SLICE-009, SLICE-010
**Foundation dependencies:** none
**Parallelizable with:** SLICE-011, SLICE-012, SLICE-013, SLICE-014, SLICE-015

## Acceptance Criteria

- [ ] Creating a trust signal persists type, scope, value, and optional expiry without mutating the current trust profile immediately.
- [ ] Recompute pins the current trust policy/config version when producing the new profile.
- [ ] Recompute is deterministic for the same signal set and policy version.
- [ ] Trust writes remain audit-safe and do not accept Discord-local ad hoc overrides.

## Engineering Notes

**Effort:** VS-010 -> M-L (leans M)
**Prototyping:** VS-010 -> no
**Risk:** Medium — this slice widens trust from onboarding into an operational subsystem, so operator-managed signals must stay bounded by deterministic recomputation rules.
**Existing code:** Extends the initial trust slice and the Phase 1 policy/audit substrate.
**Known challenges:** Expanding trust expressiveness without turning trust state into opaque manual overrides.
