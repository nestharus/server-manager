# SLICE-019: SLA enforcement for tickets

## Parent

**Initiative:** INIT-003 — Case Management
**Phase:** Phase 3

## What Changes for the Operator

Operators can define time-based accountability for ticket categories, and the system will notify, flag, or escalate cases that age beyond configured thresholds instead of relying on manual attention to notice stalls.

## Justification Chain

**Market signal:** Ticket research shows shallow time/status rigor and no meaningful market support for per-category SLA rules with graduated consequences.
**Problem axis:** §3 — Case Routing and State Management
**Proposal mechanism:** proposal.md, Case Management -> TicketCategory.sla_rules; Operational Workflows -> Ticket Lifecycle
**Philosophy principles:** Principle 9: Volunteer-Aware Design, Principle 12: Graceful Degradation, Principle 14: Graduated Consequence

## Technical Specification

**Schema objects:**
- TicketCategory: SLA rules extension on category configuration
- SlaThresholdRead / SlaTriggerRead: elapsed threshold and applied trigger record

**API endpoints:**
- scheduled handler: evaluate_ticket_sla() -> list[SlaTriggerRead]

**Discord interactions:**
- none directly; consequences flow through the notification and ticket-transition surfaces

**State transitions:**
- ticket ages past threshold -> notify_owner/notify_scope/flag_for_review/auto_escalate

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-037 | Ticket SLA Evaluator And Escalation Worker | `services/api/app/contracts/tickets.py` | services/api/app/contracts/tickets.py, services/api/app/services/tickets.py, services/api/app/tasks/ticket_sla.py, services/api/tests/test_ticket_sla.py |

## Dependencies

**Upstream slices:** SLICE-011, SLICE-015
**Foundation dependencies:** SLICE-004
**Parallelizable with:** SLICE-018, SLICE-020, SLICE-021

## Acceptance Criteria

- [ ] Thresholds fire in ascending elapsed-time order and do not skip earlier configured consequences.
- [ ] Auto-escalate follows the category's escalation path, or flags for review when no such path exists.
- [ ] Re-running the SLA worker does not duplicate an already-applied threshold for the same ticket.
- [ ] Notifications and ticket transitions triggered by the SLA worker flow through the existing published contracts instead of custom side effects.

## Engineering Notes

**Effort:** VS-013 -> L
**Prototyping:** VS-013 -> conditional
**Risk:** High — scheduler reliability, notification routing, and category-specific escalation semantics all converge in one enforcement loop.
**Existing code:** Build on the scheduler foundation, ticket lifecycle slice, and notification delivery slice.
**Known challenges:** Making time-based enforcement strong enough to matter without creating duplicate escalations or opaque automation.
