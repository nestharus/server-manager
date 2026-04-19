# INIT-003: Case Management

## Strategic Context

**Subsystem:** Case Management
**Phase:** Phase 2 anchor; extended in Phase 3
**Executive priority:** Phase 2 highest-priority initiative — VS-007 ranks #1 at composite 3.75; VS-013 extends it in Phase 3 at 1.5.

## Justification Chain

### Market Signal
**Finding:** Ticketing research shows strong demand for assignment, transcripts, and case workflow depth, but per-category configurable state machines, mandatory reasons, and time-based accountability are effectively missing.
**Evidence strength:** strong
**Competitor landscape:** Ticket Tool, Helper.gg, SCNX, Discord Tickets, Modmail, ticket.pm, Mava, Oapps, and DiscoDesk all compete here, but they remain transcript-first or inbox-first rather than lifecycle-first.

### Problem Axis
**Axis:** §3 — Case Routing and State Management
**Core difficulty:** A ticket is not a thread; it has ownership, privacy, typed state, and time-based accountability that must survive reassignment, escalation, and vendor failures.

### Proposal Mechanism
**Design reference:** proposal.md, Case Management; Operational Workflows -> Ticket Lifecycle
**Schema objects:** TicketCategory, Ticket, TicketMessage, TicketTransition
**Operational workflows:** ticket open/triage/assign/escalate/resolve/close, ticket messaging, per-category SLA escalation

### Executive Priority
**Pain severity:** 5 — harassment reports and appeals aging silently are called out as active harm, and the executive roadmap puts the base ticket slice at the top of Phase 2.
**Competitive position:** table-stakes at entry, gap on operational depth — communities need ticketing to switch at all, and the SLA extension remains differentiated beyond the current field.
**Dependency depth:** 3 at entry; the SLA extension deepens the same case substrate after notifications and scheduler support exist.
**Operational risk of delay:** active-harm — sensitive cases continue living in DM threads with no durable state, ownership, or escalation path, eroding community trust when they stall.
**Opportunity cost:** Harassment reports and appeals keep living in ephemeral DM threads without durable state, ownership tracking, or time-based accountability.

### Engineering Assessment
**Effort:** VS-007 -> M-L (leans M); VS-013 -> L
**Prototyping:** VS-007 -> no; VS-013 -> conditional
**Risk:** High overall
**Risk factors:** Private-thread and privacy behavior must stay correct; category state-machine enforcement must be deterministic; SLA logic compounds scheduler, notification, and escalation semantics.
**Foundation dependencies:** Phase 0 persistence, audit, scheduler/deferred effects, test harnesses, and the Discord/API integration shell.

## Scope

**Value slices:** SLICE-011, SLICE-019
**Dependencies:** INIT-001, INIT-002
**Delivers:** Operators can define ticket categories with explicit state machines and privacy rules and then move tickets through those states with mandatory rationale where required; Ticket history is append-only and reconstructable across creation, moderation actions, and message appends.

## Acceptance Criteria

- [ ] Operators can define ticket categories with explicit state machines and privacy rules and then move tickets through those states with mandatory rationale where required.
- [ ] Ticket history is append-only and reconstructable across creation, moderation actions, and message appends.
- [ ] Discord ticket interactions update Discord-visible state only after the API mutation succeeds.
- [ ] Configured SLA thresholds produce proportionate consequences without duplicating previously applied escalations.
