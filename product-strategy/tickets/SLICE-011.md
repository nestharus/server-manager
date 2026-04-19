# SLICE-011: Ticket creation and case lifecycle

## Parent

**Initiative:** INIT-003 — Case Management
**Phase:** Phase 2

## What Changes for the Operator

Operators can define ticket categories, open cases, transition them through category-specific workflows, and append immutable message history without relying on ad hoc Discord threads as the source of truth. Discord ticket flows become API-backed case operations rather than thread-only staff rituals.

## Justification Chain

**Market signal:** Ticketing research found strong willingness to pay for assignment and transcripts, but per-category state machines and mandatory resolution reasons are still missing.
**Problem axis:** §3 — Case Routing and State Management
**Proposal mechanism:** proposal.md, Case Management; Operational Workflows -> Ticket Lifecycle
**Philosophy principles:** Principle 6: Trust and Safety, Principle 10: Durable State over Ephemeral State, Principle 14: Graduated Consequence

## Technical Specification

**Schema objects:**
- TicketCategory: `name`, `routing_scope`, `state_machine`, `privacy_level`, optional `sla_rules`, `version`
- Ticket: `category_id`, `reporter_id`, `subject_id`, `state`, `priority`, `owner_id`, `resolution`, `version`
- TicketMessage: append-only message/transcript records with visibility
- TicketTransition: `from_state`, `to_state`, `actor_id`, `reason`, `timestamp`

**API endpoints:**
- POST /api/v1/ticket-categories -> TicketCategoryRead
- PATCH /api/v1/ticket-categories/{category_id} -> TicketCategoryRead
- POST /api/v1/tickets -> TicketRead
- POST /api/v1/tickets/{ticket_id}/transitions -> TicketRead
- POST /api/v1/tickets/{ticket_id}/messages -> TicketMessageAppendRead

**Discord interactions:**
- ticket open command submits the API ticket before creating Discord thread/channel state
- moderation commands forward triage/assign/escalate/resolve/close transitions to the API

**State transitions:**
- category-defined ticket states such as open -> triaged -> assigned -> resolved -> closed
- ticket message append leaves ticket state unchanged

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-024 | Ticket Category Configuration API | `services/api/app/contracts/tickets.py` | migrations/versions/wu-024_ticket_categories.py, services/api/app/contracts/tickets.py, services/api/app/repositories/ticket_categories.py, services/api/app/services/ticket_categories.py, services/api/app/api/v1/endpoints/tickets/categories.py, services/api/tests/test_ticket_categories.py |
| WU-025A-create | Ticket Creation API | `services/api/app/contracts/tickets.py` | migrations/versions/wu-025a_tickets_create.py, services/api/app/contracts/tickets.py, services/api/app/repositories/tickets.py, services/api/app/services/tickets.py, services/api/app/api/v1/endpoints/tickets/create.py, services/api/tests/test_ticket_create.py |
| WU-025A-events | Ticket Initial Message Event Persistence | `services/api/app/contracts/ticket_messages.py` | services/api/app/contracts/ticket_messages.py, services/api/app/repositories/ticket_messages.py, services/api/app/services/ticket_messages.py, services/api/tests/test_ticket_initial_message_events.py |
| WU-025B | Ticket Transition API | `services/api/app/contracts/tickets.py` | services/api/app/contracts/tickets.py, services/api/app/repositories/tickets.py, services/api/app/services/tickets.py, services/api/app/api/v1/endpoints/tickets/transitions.py, services/api/tests/test_ticket_transitions.py |
| WU-025C | Ticket Message Append API | `services/api/app/contracts/ticket_messages.py` | services/api/app/contracts/ticket_messages.py, services/api/app/repositories/ticket_messages.py, services/api/app/services/ticket_messages.py, services/api/app/api/v1/endpoints/tickets/messages.py, services/api/tests/test_ticket_messages.py |
| WU-026 | Discord Ticket Interaction Flow | `services/discord/app/contracts/tickets.py` | services/discord/app/contracts/tickets.py, services/discord/app/commands/tickets.py, services/discord/app/handlers/tickets.py, services/discord/tests/test_tickets.py |

## Dependencies

**Upstream slices:** SLICE-008, SLICE-009, SLICE-010
**Foundation dependencies:** SLICE-005, SLICE-006
**Parallelizable with:** SLICE-012, SLICE-013, SLICE-014, SLICE-015, SLICE-016

## Acceptance Criteria

- [ ] Ticket category create/update persists routing scope, privacy level, and the declared state machine, with stale updates rejected by optimistic locking.
- [ ] Opening a ticket places it in the category's configured initial state and keeps initial message-event persistence separate from ticket creation.
- [ ] Transitioning with expected_version N succeeds once and a stale retry with N returns 412 Precondition Failed.
- [ ] Discord ticket flows mutate Discord-visible state only after API success and preserve the API ticket ID for later transcript correlation.

## Engineering Notes

**Effort:** VS-007 -> M-L (leans M)
**Prototyping:** VS-007 -> no
**Risk:** Medium — the main risks are private-thread behavior, category-state correctness, and keeping transcripts append-only instead of reintroducing thread-local truth.
**Existing code:** Reuse the Discord runtime shell and Phase 1 governance substrate; ticket workflow behavior in preserved draft code is hookpoint material only.
**Known challenges:** Separating ticket aggregate mutations from immutable message-event persistence and keeping category state machines operator-defined but enforceable.
