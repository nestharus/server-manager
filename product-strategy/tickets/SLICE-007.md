# SLICE-007: Member onboarding with initial trust assessment

## Parent

**Initiative:** INIT-002 — Identity and Trust
**Phase:** Phase 1

## What Changes for the Operator

Operators can see each new member as a durable system record with an initial trust assessment instead of relying on Discord role presence or memory. The onboarding flow consistently creates the member record, computes trust, and returns whether further intake is required.

## Justification Chain

**Market signal:** Trust research found strong demand for richer operator trust context and repeated complaints about coarse verification that rejects legitimate users or leaves reviewers blind.
**Problem axis:** §1 — Trust Calibration and Identity Verification
**Proposal mechanism:** proposal.md, Identity and Trust; Operational Workflows -> Member Onboarding
**Philosophy principles:** Principle 1: Operator Clarity, Principle 6: Trust and Safety, Principle 13: Derived State Transparency

## Technical Specification

**Schema objects:**
- Member: `id`, `discord_user_id`, `joined_at`, `status`
- TrustProfile: `member_id`, computed score/tier, signals, policy/config linkage, `version`
- TrustSignal: initial platform-metadata signal captured during onboarding

**API endpoints:**
- POST /api/v1/members -> MemberRead
- GET /api/v1/members/{member_id} -> MemberRead
- GET /api/v1/members/by-discord/{discord_user_id} -> MemberRead
- PATCH /api/v1/members/{member_id}/status -> MemberRead
- POST /api/v1/trust/compute/{member_id} -> TrustProfileRead
- GET /api/v1/trust/{member_id} -> TrustProfileRead
- handler: handle_member_join(event: MemberJoinEvent) -> MemberJoinOutcomeRead

**Discord interactions:**
- member join event handler creates or finds the member, requests trust computation, and returns whether intake is required

**State transitions:**
- member status active -> suspended/departed -> active
- member join event -> member record present + trust profile computed

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-011 | Member Aggregate And Status API | `services/api/app/contracts/base.py` | migrations/versions/wu-011_members.py, services/api/app/contracts/members.py, services/api/app/repositories/members.py, services/api/app/services/members.py, services/api/app/api/v1/endpoints/members.py, services/api/tests/test_members.py |
| WU-012 | Trust Profile And Initial Computation API | `services/api/app/contracts/trust.py` | migrations/versions/wu-012_trust.py, services/api/app/contracts/trust.py, services/api/app/repositories/trust.py, services/api/app/services/trust.py, services/api/app/api/v1/endpoints/trust.py, services/api/tests/test_trust.py |
| WU-013 | Discord Member-Join Onboarding Flow | `services/discord/app/contracts/onboarding.py` | services/discord/app/contracts/onboarding.py, services/discord/app/handlers/onboarding.py, services/discord/tests/test_onboarding.py |

## Dependencies

**Upstream slices:** none
**Foundation dependencies:** SLICE-001, SLICE-002, SLICE-005, SLICE-006
**Parallelizable with:** SLICE-008

## Acceptance Criteria

- [ ] Creating a member returns an active member record with a server-assigned identifier.
- [ ] Initial trust computation persists a deterministic trust profile for an existing member and uses the current trust policy version.
- [ ] Discord member-join onboarding requests member creation/lookup and trust computation through the API rather than Discord-local logic.
- [ ] Read with version N, patch status with expected_version N, then retry with stale N returns 412 Precondition Failed.

## Engineering Notes

**Effort:** VS-001 -> M-L (leans M)
**Prototyping:** VS-001 -> no
**Risk:** Medium — trust output feeds later governance decisions, so signal capture and deterministic recomputation must be correct from the first onboarding surface.
**Existing code:** Reuse the current API layering and the Discord runtime shell; no durable onboarding flow exists yet.
**Known challenges:** Keeping the onboarding handler thin so trust logic stays in API contracts and remains explainable to operators.
