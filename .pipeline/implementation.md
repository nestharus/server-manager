# SLICE-015 Phase 5+6 Implementation

## Scope Delivered

Implemented all requested work units from proposal revision 2:

- `WU-029A` notification rule management API
- `WU-029B-materialize` notification event -> envelope materialization worker
- `WU-029B-deliver` scheduled delivery worker
- `WU-029C` Discord delivery adapter

No Discord-visible Tier 3 action was executed.

## Hookpoints Used

- `services/api/app/services/mutations.py`
  Reused `mutate_entity()` for `NotificationRule` OCC and audit logging with
  `aggregate_type = "notification_rule"`.
- `services/api/app/repositories/notification_events.py`
  Kept `notification_events` as the persisted event substrate; extended
  `services/api/app/services/notification_events.py` so `emit()` now inserts
  the event and enqueues `notifications_materialize` atomically.
- `services/api/app/repositories/_claim.py`
  Extended `claim_due_rows(..., claim_status=None)` so delivery claims can omit
  the status assignment entirely.
- `services/api/app/repositories/deferred_effects.py`
  Reused deferred effects as the worker queue and extended degraded-state
  reporting with `stuck_in_flight_envelopes`.
- `services/api/app/services/scheduler.py`
  Reused the existing scheduler/deferred-effect dispatch path; notification
  handlers register through `register_scheduler_handler(...)`.
- `services/discord/app/infrastructure/api_client.py` and existing Discord test
  patterns
  Reused the established Discord adapter style for the new notification send
  handler and nonce coverage.

## Files Added

### API

- `migrations/versions/wu-029a_notifications.py`
- `services/api/app/api/v1/endpoints/notifications.py`
- `services/api/app/repositories/notifications.py`
- `services/api/app/services/notifications.py`
- `services/api/app/services/notifications_materialize.py`
- `services/api/app/services/notifications_delivery.py`
- `services/api/app/tasks/notifications_materialize.py`
- `services/api/app/tasks/notifications_deliver.py`
- `services/api/tests/test_notification_rules.py`
- `services/api/tests/test_notification_materialization.py`
- `services/api/tests/test_notification_delivery_worker.py`

### Discord

- `services/discord/app/contracts/notifications.py`
- `services/discord/app/handlers/notifications.py`
- `services/discord/tests/test_notifications.py`

## Files Updated

### API

- `services/api/app/api/v1/router.py`
- `services/api/app/contracts/notifications.py`
- `services/api/app/contracts/scheduler.py`
- `services/api/app/core/factory.py`
- `services/api/app/repositories/_claim.py`
- `services/api/app/repositories/deferred_effects.py`
- `services/api/app/services/deferred_effects.py`
- `services/api/app/services/notification_events.py`
- `services/api/app/tasks/__init__.py`
- `services/api/tests/conftest.py`
- `services/api/tests/test_notification_event_contract.py`

### Discord

- `services/discord/app/handlers/__init__.py`

## Key Outcomes

- Added `notification_rules` and `notification_envelopes` schema with the two
  grouping-specific partial unique indexes.
- Seeded `notification-dispatcher` with exactly
  `notification.read + notification.deliver`, not `notification.write`.
- Added `/api/v1/notification-rules` create/list/read/patch with ETag/OCC.
- Enforced audit payload allowlists across all 9 persisted rule fields.
- Changed `emit()` to `emit(db, *, event, actor, connection=None, ...)` and
  made event insert + materialize enqueue atomic when a shared connection is
  supplied.
- Materialization resolves recipients and destination at materialization time,
  snapshots rendered template output, skips disabled rules, and writes skipped
  envelopes for template/destination/unsupported-recipient failures.
- Delivery isolates retries/failures on envelopes only, marks
  `delivered_in_flight` before send, and leaves rules unchanged on delivery
  failure.
- Discord adapter uses deterministic `base32(uuid_bytes)[:25]` nonce generation
  and sends with `enforce_nonce=True`.

## Verification

- `cd services/api && uv run pytest tests/ -q`
  - `401 passed, 1 warning in 150.62s`
- `cd services/discord && uv run pytest tests/ -q`
  - `66 passed, 20 warnings in 0.28s`

Warnings were pre-existing test-environment warnings:

- API: one Pydantic deprecation warning in `tests/test_settings.py`
- Discord: discord.py deprecation warnings in existing bot/command tests

## Notes

- The delivery task runtime supports explicit configuration via
  `configure_task_runtime(...)` and also lazy DB resolution so direct worker
  tests can execute without building the FastAPI app first.
- Existing dirty worktree files under `.pipeline/` and `plans/risk/` were left
  untouched aside from this implementation report.
