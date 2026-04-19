# INIT-002: Identity and Trust

## Strategic Context

**Subsystem:** Identity and Trust
**Phase:** Phase 1 anchor; extended in Phase 2
**Executive priority:** Phase 1 anchor — tied #1 composite at 9.0 via VS-001; extended by VS-010 in Phase 2 at 0.9.

## Justification Chain

### Market Signal
**Finding:** Identity/trust research shows strong demand for newcomer screening and richer reviewer context, but no reviewed product offers persistent, inspectable trust profiles with deterministic recomputation.
**Evidence strength:** strong
**Competitor landscape:** Wick, Security Bot, Double Counter, Guild Manager, Guildbase, Gather, and Appy prove demand for trust-adjacent signals, but they stop at verification gates, application-side risk flags, or opaque vendor heuristics.

### Problem Axis
**Axis:** §1 — Trust Calibration and Identity Verification
**Core difficulty:** The hard part is not gathering signals but calibrating and maintaining trust across chapters, staff turnover, and time without over-trusting or over-gatekeeping.

### Proposal Mechanism
**Design reference:** proposal.md, Identity and Trust; Operational Workflows -> Member Onboarding
**Schema objects:** Member, TrustProfile, TrustSignal, TrustComputationConfig
**Operational workflows:** member onboarding with initial trust computation, officer-managed trust signal recording, deterministic trust recomputation

### Executive Priority
**Pain severity:** 4 — the executive roadmap marks initial trust context as a high-severity governance problem and the later advanced trust work as a persistent but less urgent extension.
**Competitive position:** gap — the reviewed field has risk scoring and verification edges, not a durable, inspectable trust subsystem.
**Dependency depth:** 0 at entry; the advanced trust extension depends on the Phase 1 trust substrate plus governance controls.
**Operational risk of delay:** active-harm — officers continue making admission and governance decisions from memory, Discord role presence, and coarse screening outcomes that do not survive staff turnover or chapter boundaries.
**Opportunity cost:** Officers continue making admission and governance decisions without systematic trust evidence, relying on memory and Discord role presence.

### Engineering Assessment
**Effort:** VS-001 -> M-L (leans M); VS-010 -> M-L (leans M)
**Prototyping:** VS-001 -> no; VS-010 -> no
**Risk:** Medium overall
**Risk factors:** Trust computation errors propagate into later governance decisions; deterministic recomputation and policy pinning must hold; officer-managed signal recording must not become an opaque override lane.
**Foundation dependencies:** Phase 0 persistence, mutation/versioning, audit, policy versioning substrate, and the API/Discord runtime shell.

## Scope

**Value slices:** SLICE-007, SLICE-016
**Dependencies:** none at Phase 1 entry; INIT-001 for the Phase 2 advanced-trust extension
**Delivers:** Operators can see a member record and the trust profile that was computed for that member at onboarding time; Trust results are deterministic for the same inputs and pinned to the governing policy/config version that produced them.

## Acceptance Criteria

- [ ] Operators can see a member record and the trust profile that was computed for that member at onboarding time.
- [ ] Trust results are deterministic for the same inputs and pinned to the governing policy/config version that produced them.
- [ ] Officers can add scoped trust signals and request recomputation without bypassing audit or policy controls.
- [ ] Trust decisions remain inspectable as evidence-backed derived state rather than opaque Discord-local heuristics.
