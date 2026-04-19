# SLICE-010: Policy versioning with configuration safety

## Parent

**Initiative:** INIT-001 — Governance Infrastructure
**Phase:** Phase 1

## What Changes for the Operator

Operators can preview a policy change, confirm it against the last-known version, and query the current effective policy without silently rewriting live operational meaning underneath in-flight work.

## Justification Chain

**Market signal:** Governance research found no public evidence of preview-confirm configuration changes, compare-and-swap policy edits, or version pinning in the reviewed field.
**Problem axis:** §13 — Live Configuration Safety and Temporal Integrity
**Proposal mechanism:** proposal.md, Governance -> PolicyVersion; Governance Mechanisms -> Policy Versioning; Configuration Safety
**Philosophy principles:** Principle 1: Operator Clarity, Principle 2: Live-Server Safety, Principle 11: Configuration by Operators, Not Developers

## Technical Specification

**Schema objects:**
- PolicyVersion: `policy_type`, `scope`, `version_number`, `content`, `effective_at`, `supersedes_id`
- PolicyPreviewRead: `preview_token`, `current_version`, `affected_objects`, rollback summary

**API endpoints:**
- POST /api/v1/policies/preview -> PolicyPreviewRead
- POST /api/v1/policies/confirm -> PolicyVersionRead
- GET /api/v1/policies/{policy_type}/current?scope_kind={kind}&scope_id={id} -> PolicyVersionRead

**Discord interactions:**
- none in this slice

**State transitions:**
- preview -> confirm
- current policy version N -> N+1 on confirm
- stale preview confirm -> 412 Precondition Failed

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-017 | Generic Policy Preview-Confirm API | `services/api/app/contracts/policies.py` | services/api/app/contracts/policies.py, services/api/app/api/v1/endpoints/policies.py, services/api/app/repositories/policies.py, services/api/app/services/policies.py, services/api/tests/test_policies.py |

## Dependencies

**Upstream slices:** SLICE-008, SLICE-009
**Foundation dependencies:** SLICE-002
**Parallelizable with:** none

## Acceptance Criteria

- [ ] Preview returns the current version, deterministic diff summary, and a stable preview token without mutating active policy state.
- [ ] Confirm persists exactly one new policy version when expected_current_version matches the live version.
- [ ] Confirming a superseded preview returns 412 Precondition Failed and leaves active policy unchanged.
- [ ] Current-policy reads return the effective version for the requested type and scope.

## Engineering Notes

**Effort:** VS-004 -> M-L (leans M)
**Prototyping:** VS-004 -> no
**Risk:** Medium — activation and stale-preview handling are correctness-critical because later slices inherit policy-backed safety guarantees from this surface.
**Existing code:** Build on the Phase 0 policy substrate; no operator-facing policy surface exists today.
**Known challenges:** Keeping preview/confirm generic enough for later slices while preserving one stale-state safety rule across all policy domains.
