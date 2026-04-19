# SLICE-015: Configurable operator notifications

## Parent

**Initiative:** INIT-001 — Governance Infrastructure
**Phase:** Phase 2

## What Changes for the Operator

Operators can configure who gets notified, through which channel, with what grouping behavior, and whether the notification is actionable. Notification delivery becomes a governed system behavior instead of hard-coded workflow side effects.

## Justification Chain

**Market signal:** Governance research found notification behavior embedded inside products, but not as a configurable plane with causal grouping that protects volunteer attention.
**Problem axis:** §9 — Volunteer Coordination and Staff Burnout
**Proposal mechanism:** proposal.md, Governance -> NotificationRule; Operational Workflows and Audit-triggered notification semantics
**Philosophy principles:** Principle 1: Operator Clarity, Principle 9: Volunteer-Aware Design, Principle 15: Traceability as Outcome

## Technical Specification

**Schema objects:**
- NotificationRule: `trigger`, `scope`, `recipients`, `channel`, `template`, `actionable`, `grouping`, `version`
- NotificationEnvelopeRead: materialized delivery envelope with correlation and recipients

**API endpoints:**
- POST /api/v1/notification-rules -> NotificationRuleRead
- GET /api/v1/notification-rules -> list[NotificationRuleRead]
- scheduled handler: deliver_notifications() -> NotificationDeliveryBatchRead
- handler: materialize_notification_envelopes(event: NotificationEventRead) -> NotificationMaterializationResult
- handler: deliver_notification(command: NotificationDeliveryCommand) -> NotificationDeliveryResult

**Discord interactions:**
- Discord notification adapter delivers one materialized envelope using the envelope ID as the idempotency key

**State transitions:**
- notification event -> materialized envelope(s) -> delivered/skipped/failed batch outcome

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-029A | Notification Rule Management API | `services/api/app/contracts/notifications.py` | migrations/versions/wu-029a_notification_rules.py, services/api/app/contracts/notifications.py, services/api/app/repositories/notifications.py, services/api/app/services/notifications.py, services/api/app/api/v1/endpoints/notifications.py, services/api/tests/test_notification_rules.py |
| WU-029B-deliver | Scheduled Notification Delivery Worker | `services/api/app/contracts/notifications.py` | services/api/app/contracts/notifications.py, services/api/app/tasks/notifications_deliver.py, services/api/app/services/notifications_delivery.py, services/api/tests/test_notification_delivery_worker.py |
| WU-029B-materialize | Notification Envelope Materialization Worker | `services/api/app/contracts/notifications.py` | services/api/app/contracts/notifications.py, services/api/app/tasks/notifications_materialize.py, services/api/app/services/notifications_materialize.py, services/api/tests/test_notification_materialization.py |
| WU-029C | Discord Notification Delivery Adapter | `services/discord/app/contracts/notifications.py` | services/discord/app/contracts/notifications.py, services/discord/app/handlers/notifications.py, services/discord/tests/test_notifications.py |

## Dependencies

**Upstream slices:** SLICE-008, SLICE-009, SLICE-010
**Foundation dependencies:** SLICE-002, SLICE-004, SLICE-006
**Parallelizable with:** SLICE-011, SLICE-012, SLICE-013, SLICE-014, SLICE-016

## Acceptance Criteria

- [ ] Rule create/update persists grouping, recipients, channel, and actionable state exactly as submitted, with stale updates rejected by optimistic locking.
- [ ] Per-root-cause rules emit one envelope per root correlation ID and per-event rules emit one per triggering audit entry.
- [ ] Replaying the same persisted notification event does not materialize duplicate envelopes.
- [ ] Scheduled delivery marks envelopes exactly once and Discord delivery failures do not mutate rule definitions.

## Engineering Notes

**Effort:** VS-009 -> M-L (leans M)
**Prototyping:** VS-009 -> conditional
**Risk:** Medium — the correctness risk is event grouping and idempotent delivery once multiple workflows begin emitting operational events.
**Existing code:** Build on the Phase 0 notification event substrate, scheduler, and Discord runtime shell.
**Known challenges:** Preventing notification fatigue without obscuring why a notification fired or which root cause it belongs to.
