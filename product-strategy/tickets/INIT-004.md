# INIT-004: Structured Intake

## Strategic Context

**Subsystem:** Intake and Adjudication
**Phase:** Phase 2 anchor; extended in Phase 3
**Executive priority:** Phase 2 co-anchor — VS-006 is tied #2 at composite 3.0; VS-012 extends it in Phase 3 at 0.75.

## Justification Chain

### Market Signal
**Finding:** Application-tool research shows strong demand for richer Discord-native review, but reviewer collision prevention, waitlists, interview handling, and mandatory decision reasons remain rare across the market.
**Evidence strength:** strong
**Competitor landscape:** Gather, Appy, Application Bot, ApplicationForms, Google Forms stacks, Typeform stacks, Guildbase, and Guild Manager validate the space, but mostly stop at shared dashboards and accept/deny outcomes.

### Problem Axis
**Axis:** §2 — Structured Intake and Adjudication
**Core difficulty:** Applications are lifecycle objects competing for scarce volunteer attention, and concurrent reviewer access turns missing ownership controls into duplicated effort and conflict resolution.

### Proposal Mechanism
**Design reference:** proposal.md, Intake and Adjudication; Operational Workflows -> Application Intake
**Schema objects:** FormDefinition, Application, ApplicationReview
**Operational workflows:** form version publish, submission -> queue -> claim -> review -> decide, interview and waitlist handling

### Executive Priority
**Pain severity:** 5 at entry — the executive roadmap treats duplicated review effort and missing rationale as active harm, with interview/waitlist depth following once the main queue exists.
**Competitive position:** table-stakes at entry, gap on lifecycle depth — structured intake is required to compete, while reviewer ownership plus interview/waitlist handling remains under-served.
**Dependency depth:** 4 at entry; the interview/waitlist extension deepens the same application state machine later.
**Operational risk of delay:** active-harm — duplicate review work and conflicting decisions continue burning scarce volunteer attention and make appeals unreconstructable.
**Opportunity cost:** Officers keep duplicating review effort on the same applications, and decisions still lack mandatory rationale and lifecycle visibility.

### Engineering Assessment
**Effort:** VS-006 -> M-L (leans M); VS-012 -> M
**Prototyping:** VS-006 -> no; VS-012 -> no
**Risk:** Medium overall
**Risk factors:** Reviewer ownership must remain single-writer safe; form versioning must pin in-flight submissions correctly; Discord-side interview and waitlist flows must not create duplicate external state.
**Foundation dependencies:** Phase 0 persistence, mutation/versioning, audit, policy/version substrate, and the Discord/API runtime shell.

## Scope

**Value slices:** SLICE-012, SLICE-021
**Dependencies:** INIT-001, INIT-002
**Delivers:** Operators can publish scoped form definitions, accept applications against a pinned form version, and route them into a single-reviewer queue; Application decisions require the correct state transition and preserve optimistic locking under concurrent reviewer activity.

## Acceptance Criteria

- [ ] Operators can publish scoped form definitions, accept applications against a pinned form version, and route them into a single-reviewer queue.
- [ ] Application decisions require the correct state transition and preserve optimistic locking under concurrent reviewer activity.
- [ ] Discord submission and review flows remain thin clients of the published API contracts rather than Discord-local workflow state.
- [ ] Interview and waitlist handling reuse the same application lifecycle instead of creating side-channel review state.
