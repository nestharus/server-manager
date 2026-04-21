# SLICE-015 Phase 3 Proposal Revision 2: Configurable Operator Notifications

## 1. Source

This proposal implements WU-029A, WU-029B-materialize,
WU-029B-deliver, and WU-029C from
`product-strategy/tickets/SLICE-015.md`.

Inputs used:

- `.pipeline/research.md`: confirms the existing notification event
  substrate, mutation/ETag primitive, scheduler/deferred effect substrate,
  and Discord nonce strategy. Revision 1 incorporates the audit findings that
  raw UUID envelope IDs exceed Discord's 25-character nonce limit.
- `.pipeline/synthesis.md`: D1-D14 are binding and are treated as the
  implementation contract.
- Audit round 2: Scope and shortcut risk converged LOW; Revision 2 resolves
  the four remaining audit MEDIUM implementation-discipline findings.
- `product-strategy/tickets/SLICE-015.md`: 4 acceptance criteria and 4 work
  units.
- Merged code through SLICE-018:
  - SLICE-002 notification events:
    `migrations/versions/wu-003c_notification_events.py`,
    `services/api/app/contracts/notifications.py`,
    `services/api/app/services/notification_events.py`, and
    `services/api/app/repositories/notification_events.py`.
  - SLICE-004 scheduler/deferred effects:
    `services/api/app/services/scheduler.py`,
    `services/api/app/services/deferred_effects.py`,
    `services/api/app/repositories/_claim.py`, and
    `services/api/app/repositories/deferred_effects.py`.
  - Aggregate mutation/versioning:
    `services/api/app/services/mutations.py`.
  - Authority enforcement and service actor patterns:
    `services/api/app/core/dependencies.py`,
    `migrations/versions/wu-012_trust.py`, and
    `migrations/versions/wu-019_chapter_lifecycle.py`.
  - Discord API-call and handler patterns:
    `services/discord/app/infrastructure/api_client.py`,
    `services/discord/app/handlers/onboarding.py`, and
    `services/discord/app/handlers/chapters.py`.

The proposal does not perform any live Discord-visible action. WU-029C adds
code that can send Discord messages, but executing it against the live guild is
Tier 3 and remains subject to explicit per-action approval unless a runbook is
pre-authorized.

## 2. In Scope / Out of Scope

### In scope

- A governed `NotificationRule` aggregate backed by `notification_rules`,
  versioned through `aggregate_heads`.
- Rule create, list, read, and patch API endpoints under
  `/api/v1/notification-rules`.
- Rule optimistic locking with `If-Match`; stale patch returns `412
  Precondition Failed`.
- New notification envelope persistence in `notification_envelopes`.
- Materialization from persisted `notification_events` into per-recipient
  `notification_envelopes`.
- `per_event` and `per_root_cause` grouping.
- Replay-safe deduplication through database unique indexes plus
  `INSERT ... ON CONFLICT DO NOTHING`.
- Scheduler integration through registered handlers and deferred effects.
- Delivery claiming with `FOR UPDATE SKIP LOCKED`.
- Delivery status transitions to `delivered_in_flight`, `delivered`, `failed`,
  or `skipped`.
- Failure retry accounting on envelopes, isolated from rule rows.
- Discord delivery adapter that sends exactly one materialized envelope and
  passes a deterministic 25-character nonce derived from `envelope_id` with
  nonce enforcement.
- Tests named in the AC traceability section below.

### Out of scope

- Notification acknowledgements and acknowledgement UI.
- Recurring notification schedules.
- Digests, batching policy, throttling policy, analytics, archival, or
  recipient preferences.
- Email, SMS, or cross-guild delivery.
- A separate template registry or compliance template lifecycle.
- Retrofitting all existing workflows to emit new notification event types.
  SLICE-015 tests may seed `notification_events` directly.
- Recursive causation walking. For this slice, root cause grouping uses the
  event `correlation_id`.
- Discord thread delivery and thread creation. `channel='thread'` remains
  persisted rule input but materializes as skipped until a later slice defines
  reliable thread destination semantics.
- Backward-compatibility aliases or transitional routes.

## 3. Work Units

### WU-029A - Notification Rule Management API

#### Migration

Create `migrations/versions/wu-029a_notifications.py` with
`revision = "wu_029a_notifications"` and `down_revision = "wu_012_trust"`.

This migration creates `notification_rules`:

- `id UUID PRIMARY KEY`
- `trigger_json JSONB NOT NULL`
- `scope_kind TEXT NOT NULL`
- `scope_id TEXT NULL`
- `recipients_json JSONB NOT NULL`
- `channel TEXT NOT NULL`
- `template_json JSONB NOT NULL`
- `actionable BOOLEAN NOT NULL`
- `grouping TEXT NOT NULL`
- `enabled BOOLEAN NOT NULL DEFAULT TRUE`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`

Constraints:

- `scope_kind IN ('global', 'chapter', 'member')`
- `channel IN ('dm', 'thread', 'designated_channel')`
- `grouping IN ('per_event', 'per_root_cause')`

Indexes:

- `ix_notification_rules__scope` on `(scope_kind, scope_id)`
- `ix_notification_rules__enabled` on `(enabled)`
- `ix_notification_rules__trigger_json_gin` as a GIN index on `trigger_json`

The same migration also creates `notification_envelopes` because WU-029B needs
the table and deduplication indexes:

- `id UUID PRIMARY KEY`
- `rule_id UUID NOT NULL REFERENCES notification_rules(id) ON DELETE RESTRICT`
- `rule_version BIGINT NOT NULL`
- `source_event_id UUID NOT NULL REFERENCES notification_events(id) ON DELETE RESTRICT`
- `root_correlation_id UUID NOT NULL`
- `causation_id UUID NULL`
- `grouping TEXT NOT NULL`
- `recipient_key TEXT NOT NULL`
- `recipient_discord_id TEXT NULL`
- `recipient_display TEXT NOT NULL`
- `channel TEXT NOT NULL`
- `destination_channel_id TEXT NULL`
- `template_snapshot_json JSONB NOT NULL`
- `rendered_title TEXT NOT NULL`
- `rendered_body TEXT NOT NULL`
- `actionable BOOLEAN NOT NULL`
- `delivery_status TEXT NOT NULL DEFAULT 'pending'`
- `claimed_by TEXT NULL`
- `claimed_at TIMESTAMPTZ NULL`
- `lease_until TIMESTAMPTZ NULL`
- `attempts INTEGER NOT NULL DEFAULT 0`
- `max_attempts INTEGER NOT NULL DEFAULT 3`
- `last_error_json JSONB NULL`
- `discord_message_id TEXT NULL`
- `delivered_at TIMESTAMPTZ NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`

Envelope constraints:

- `grouping IN ('per_event', 'per_root_cause')`
- `channel IN ('dm', 'thread', 'designated_channel')`
- `delivery_status IN ('pending', 'delivered_in_flight', 'delivered', 'skipped', 'failed')`
- `attempts >= 0`
- `max_attempts > 0`
- `delivered_at IS NULL OR delivery_status = 'delivered'`

Envelope dedup indexes:

- `uq_notification_envelopes__per_event`:
  unique `(source_event_id, rule_id, recipient_key)` where
  `grouping = 'per_event'`.
- `uq_notification_envelopes__per_root_cause`:
  unique `(rule_id, root_correlation_id, recipient_key)` where
  `grouping = 'per_root_cause'`.

Delivery indexes:

- `ix_notification_envelopes__pending_delivery` on `(created_at, id)` where
  `delivery_status = 'pending'`.
- `ix_notification_envelopes__rule_id`
- `ix_notification_envelopes__source_event_id`
- `ix_notification_envelopes__root_correlation_id`

Seed the service actor grant using the existing guarded insert pattern from
`wu-012_trust.py` and `wu-019_chapter_lifecycle.py`:

- `grantee_id = 'notification-dispatcher'`
- `scope_kind = 'global'`
- `scope_id = NULL`
- `permissions @> ["notification.read", "notification.deliver"]`

Do not seed `notification.write` for the dispatcher.

#### Contracts

Extend `services/api/app/contracts/notifications.py`.

New literals:

- `NotificationChannel = Literal["dm", "thread", "designated_channel"]`
- `NotificationGrouping = Literal["per_event", "per_root_cause"]`
- `NotificationDeliveryStatus = Literal["pending", "delivered_in_flight", "delivered", "skipped", "failed"]`

Rule contracts:

- `NotificationTrigger`
  - `event_type: str`
  - `payload_filters: dict[str, Any] | None = None`
  - validator: exact dotted name or suffix pattern ending in `.*`
- `NotificationRuleCreate`
  - `trigger_json: NotificationTrigger` with public API alias `trigger`
  - `scope_kind: ScopeKind`
  - `scope_id: str | None = None`
  - `recipients_json: dict[str, Any]` with public API alias `recipients`
  - `channel: NotificationChannel`
  - `template_json: dict[str, Any]` with public API alias `template`
  - `actionable: bool`
  - `grouping: NotificationGrouping`
  - `enabled: bool = True`
- `NotificationRulePatch`
  - same fields optional
  - at least one field must be present
- `NotificationRuleRead`
  - all persisted rule fields plus `id`, `version`, `created_at`, `updated_at`
- `NotificationRuleListRead`
  - `items: list[NotificationRuleRead]`

Envelope/worker contracts shared with WU-029B:

- `NotificationEnvelopeRead`
- `NotificationMaterializationResult`
- `NotificationDeliveryCommand`
- `NotificationDeliveryResult`
- typed errors for rule not found, empty patch, unsupported trigger, delivery
  failure, ambiguous delivery failure, template render failure, and stale rule
  version.

Use public aliases `trigger`, `recipients`, `template`, and `payload` at the
HTTP boundary while keeping the contract model field names aligned with the
persisted `_json` columns. `NotificationRuleCreate.model_dump().keys()` must
therefore be exactly `{"trigger_json", "scope_kind", "scope_id",
"recipients_json", "channel", "template_json", "actionable", "grouping",
"enabled"}`. This keeps audit payload allowlists and repository row mappings
on the same vocabulary without exposing `_json` names in request bodies.

#### Repository

Create `services/api/app/repositories/notifications.py`.

Rule functions:

- `insert_notification_rule(connection, row)`
- `update_notification_rule(connection, rule_id, patch_row)`
- `fetch_notification_rule(connection, rule_id)`
- `fetch_notification_rule_for_update(connection, rule_id)`
- `list_notification_rules(connection, scope_kind=None, scope_id=None)`
- `list_enabled_rules_for_event(connection, event_row)`

The rule select joins `aggregate_heads` for version, following the member
pattern in `services/api/app/repositories/members.py:10`.

Envelope functions needed by WU-029B:

- `insert_notification_envelope_on_conflict_do_nothing(connection, row)`
- `fetch_notification_envelope(connection, envelope_id)`
- `claim_pending_notification_envelope(connection, envelope_id, worker_id, now, lease_seconds)`
- `mark_notification_envelope_delivered_in_flight(connection, envelope_id, worker_id)`
- `mark_notification_envelope_delivered(connection, envelope_id, worker_id, discord_message_id, delivered_at)`
- `mark_notification_envelope_failed(connection, envelope_id, worker_id, error)`
- `mark_notification_envelope_skipped(connection, envelope_id, worker_id, reason)`

Envelope claiming must use `SELECT ... FOR UPDATE SKIP LOCKED` semantics and
reuse the SLICE-004 claim helper by extending
`services/api/app/repositories/_claim.py::claim_due_rows()` to accept an
optional `claim_status`. Existing scheduler callers keep the default
`claim_status="claimed"`. Notification envelopes call the helper with
`claim_status=None`, which makes the helper update only claim ownership and
lease columns without changing `delivery_status`.

The helper must generate the `UPDATE ... SET` list conditionally. When
`claim_status is None`, the generated SQL omits the `status = 'claimed'` SET
clause entirely; it must never emit `status = NULL`, an empty status, or a
`status` assignment against `notification_envelopes`. Parameter order must be
covered by regression tests against the existing scheduler and deferred-effect
callers, which must continue to pass unchanged.

Since D4 does not define a `claimed` status for envelopes, claiming never sets
`delivery_status = 'claimed'`. A row is claimable when:

- `delivery_status = 'pending'`
- `attempts < max_attempts`
- `claimed_by IS NULL OR lease_until < now`

The claim update sets `claimed_by`, `claimed_at`, and `lease_until`, but keeps
`delivery_status = 'pending'`. A claimed row becomes
`delivery_status = 'delivered_in_flight'` only at the delivery service boundary
immediately before invoking the Discord delivery port.

#### Service

Create `services/api/app/services/notifications.py`.

Rule service functions:

- `create_notification_rule(db, request, actor) -> tuple[NotificationRuleRead, MutationResult]`
- `get_notification_rule(db, rule_id) -> tuple[NotificationRuleRead, str]`
- `list_notification_rules(db, scope_kind=None, scope_id=None) -> NotificationRuleListRead`
- `patch_notification_rule(db, rule_id, patch, actor, expected_version) -> tuple[NotificationRuleRead, MutationResult]`

Use `mutate_entity()` exactly as other aggregate services do:

- `aggregate_type = "notification_rule"`
- create uses `expected_version = 0`
- patch uses the parsed `If-Match` value
- create action type: `notification_rule.create`
- patch action type: `notification_rule.patch`
- scope passed to mutation is the rule scope
- payload allowlist is pinned to the persisted rule-field key set so audit
  captures the governed rule definition:
  `{"trigger_json", "scope_kind", "scope_id", "recipients_json", "channel",
  "template_json", "actionable", "grouping", "enabled"}`

For create, the action payload passed to `mutate_entity()` must contain exactly
the keys produced by `NotificationRuleCreate.model_dump()`. For patch, the
allowlist is the same set, and the action payload is the caller-provided subset
after Pydantic alias validation. Do not pass `payload_allowlist=None` or derive
a narrower bespoke set; that would make the activity action unreconstructable
for audit review.

Rule create and patch persist `trigger_json`, `recipients_json`,
`template_json`, `channel`, `actionable`, `grouping`, and `enabled` exactly as
submitted after Pydantic validation. No enum expansion table and no template
normalization are introduced.

#### Endpoints

Create `services/api/app/api/v1/endpoints/notifications.py` and include it in
`services/api/app/api/v1/router.py`.

Endpoints:

- `POST /api/v1/notification-rules`
  - requires `notification.write` at global scope
  - returns `201 NotificationRuleRead`
  - sets `ETag` to the aggregate version
- `GET /api/v1/notification-rules`
  - requires `notification.read` at global scope
  - supports `scope_kind` and `scope_id` filters
  - returns `NotificationRuleListRead`
- `GET /api/v1/notification-rules/{rule_id}`
  - requires `notification.read` at global scope
  - returns `NotificationRuleRead`
  - sets `ETag`
- `PATCH /api/v1/notification-rules/{rule_id}`
  - requires `notification.write` at global scope
  - requires `If-Match`
  - stale version maps to `412` with code `stale_notification_rule_version`
  - returns updated `NotificationRuleRead` and `ETag`

Use the local `_parse_if_match`/`_set_etag` pattern from
`services/api/app/api/v1/endpoints/members.py:36` and `:57`.

#### Tests

Create `services/api/tests/test_notification_rules.py`:

- `test_create_rule_persists_trigger_recipients_channel_grouping`
- `test_rule_create_audit_payload_includes_all_rule_fields`
- `test_patch_rule_with_current_version_succeeds`
- `test_patch_rule_stale_version_returns_412`
- `test_list_rules_filters_by_scope`
- `test_notification_dispatcher_service_grants_seeded`

### WU-029B-materialize - Notification Envelope Materialization Worker

#### Scheduler/deferred effect integration

Create `services/api/app/tasks/notifications_materialize.py` and import it from
`services/api/app/tasks/__init__.py` so handler registration happens at module
load.

Register:

```python
@register_scheduler_handler("notifications_materialize")
def materialize_notification_envelopes(effect: DeferredEffectRead) -> NotificationMaterializationResult:
    ...
```

Update `services/api/app/services/notification_events.py:27` so every
successful `emit()` also inserts a deferred effect in the same database
transaction. Replace the existing signature with:

```python
def emit(
    db: PostgresDatabase | None,
    *,
    event: NotificationEventDraft,
    actor: ActorIdentity,
    connection: Connection[Any] | None = None,
) -> NotificationEventRead:
    ...
```

If `connection` is supplied, `emit()` uses the caller's transaction for both
the `notification_events` insert and the deferred-effect enqueue. If
`connection` is not supplied, `db` must be supplied and `emit()` opens one
connection and commits both writes together. Update all callers to the new
keyword-only contract; do not keep a legacy positional connection/draft path.

The paired deferred effect uses:

- `subsystem = "notifications"`
- `effect_type = "notifications_materialize"`
- `idempotency_key = f"notifications:materialize:{event_id}"`
- `payload_json = {"event_id": str(event_id)}`
- `consequence_level = "safe"`
- `correlation_id = current audit context correlation_id`

Use the repository-level deferred effect insert if necessary so `emit()` can
reuse the supplied connection. This preserves `notification_events` as the
source event table and uses SLICE-004 deferred effects as the claimable queue.
If the existing `deferred_effects.enqueue_effect()` service function cannot
accept a shared connection, extend it to accept
`connection: Connection | None = None`; when supplied, it must insert through
that connection and must not open or commit a separate transaction.

Any caller that is already inside a mutation transaction, including projection
mutation code such as `mutate_projection`, passes its current `connection`.
Callers outside a transaction pass `db` and let `emit()` own the short
transaction.

Replay support must also be explicit: materialization service exposes
`materialize_event(db, event_id, worker_id="notification-dispatcher")`, and
tests can call it directly for replay. It uses the same insert path and the
same unique indexes.

#### Materialization service

Create `services/api/app/services/notifications_materialize.py`.

Flow:

1. Load the persisted `notification_events` row by `event_id`.
2. Load enabled rules whose scope and trigger can match the event.
3. Apply trigger matching:
   - exact `event_type` equals event type
   - suffix pattern `foo.*` matches `foo.` prefix
   - `payload_filters` exact-match against stored event payload keys
4. Apply scope matching:
   - global rule matches any event
   - chapter rule matches only `event.scope_kind == "chapter"` and same
     `scope_id`
   - member rule matches only `event.scope_kind == "member"` and same
     `scope_id`
5. Resolve recipients at materialization time.
6. Resolve `destination_channel_id` at materialization time from the resolved
   channel semantics.
7. Render the template at materialization time.
8. Insert one envelope per resolved recipient using
   `INSERT ... ON CONFLICT DO NOTHING`.
9. If recipient, destination, or template rendering fails for a recipient
   selector, insert a skipped envelope with `delivery_status = 'skipped'` and
   `last_error_json.reason`. Recipient-resolution failures use
   `recipient_discord_id = NULL` and
   `recipient_key = "unresolved:<stable-selector-hash>"`; destination and
   template failures keep the resolved recipient fields when available.
10. For each newly created deliverable envelope, enqueue a deferred effect:
   - `effect_type = "notifications_deliver"`
   - `idempotency_key = f"notifications:deliver:{envelope_id}"`
   - `payload_json = {"envelope_id": str(envelope_id)}`
   - `consequence_level = "safe"`

The envelope inserts and their corresponding `notifications_deliver` deferred
effects must be written in one database transaction. The materialization
service owns the transaction and passes the same connection to
`insert_notification_envelope_on_conflict_do_nothing()` and
`deferred_effects.enqueue_effect(connection=shared_connection, ...)`. If the
current deferred-effect service substrate does not expose connection injection,
the implementation changes that substrate as described above instead of
enqueueing delivery effects out-of-transaction.

Recipient resolution for SLICE-015 supports:

- `{"kind": "discord_users", "user_ids": ["123", "456"]}`
- `{"kind": "discord_user", "user_id": "123"}`

The resolver returns `recipient_key = f"discord_user:{user_id}"`,
`recipient_discord_id = user_id`, and `recipient_display = user_id`. Other
recipient kinds, including `discord_role`, are accepted as persisted rule JSON
but materialize as skipped until a later slice adds a reliable role membership
source. This keeps AC1 exact persistence while avoiding fake role resolution.

Destination resolution for SLICE-015 is:

- `channel = "dm"`: store `destination_channel_id = NULL`; the Discord adapter
  creates or opens the DM channel at delivery time.
- `channel = "designated_channel"`: read
  `recipients_json.designated_channel_id` and store it on the envelope. If the
  field is absent or blank, materialize a skipped envelope with
  `reason = "destination_missing"`.
- `channel = "thread"`: materialize a skipped envelope with
  `reason = "thread_channel_out_of_scope"`.

Template rendering for SLICE-015 uses Python `string.Template.substitute`
over a flattened context:

- `event_id`
- `event_type`
- `correlation_id`
- `causation_id`
- `scope_kind`
- `scope_id`
- `payload.<key>` values flattened as `payload_<key>`
- `rule_id`

The supported template shape is:

```json
{"title": "Chapter ${payload_chapter_id}", "body": "Moved to ${payload_to_state}"}
```

`safe_substitute()` is forbidden because it silently leaves `${missing_key}` in
operator-visible messages. Missing template keys raise `TemplateRenderError`
at materialization time. The materialization service then inserts a skipped
envelope for the affected recipient with `reason = "template_missing_key"` and
does not enqueue a delivery effect for that envelope.

The materialized envelope stores both `template_snapshot_json` and rendered
`rendered_title`/`rendered_body`, so later rule edits do not affect pending
delivery.

#### Deduplication

Materialization computes:

- `per_event`: unique key is `(source_event_id, rule_id, recipient_key)`
- `per_root_cause`: unique key is `(rule_id, root_correlation_id, recipient_key)`

`root_correlation_id` is `notification_events.correlation_id`.

Repository inserts use `ON CONFLICT DO NOTHING` and return a flag indicating
whether the envelope was created or already existed. Existing envelopes are not
updated on replay.

#### Tests

Create `services/api/tests/test_notification_materialization.py`:

- `test_emit_is_atomic_when_called_with_connection`
- `test_per_event_rule_emits_one_envelope_per_event`
- `test_per_root_cause_rule_emits_one_envelope_per_root_correlation`
- `test_multiple_events_same_root_correlation_one_envelope`
- `test_different_root_correlations_separate_envelopes`
- `test_replay_same_event_no_duplicate_envelopes`
- `test_unique_index_prevents_duplicate_envelope_rows`
- `test_materialize_is_idempotent_under_retry`
- `test_recipient_resolution_at_materialization_time`
- `test_designated_channel_destination_snapshotted_at_materialization_time`
- `test_materialize_skips_when_template_has_missing_key`
- `test_template_rendering_snapshot_isolates_from_later_rule_edits`

`test_emit_is_atomic_when_called_with_connection` must simulate a deferred
effect enqueue failure and assert both the `notification_events` row and the
paired deferred effect are absent after rollback.

### WU-029B-deliver - Scheduled Notification Delivery Worker

#### Scheduler/deferred effect integration

Create `services/api/app/tasks/notifications_deliver.py` and import it from
`services/api/app/tasks/__init__.py`.

Register:

```python
@register_scheduler_handler("notifications_deliver")
def deliver_notification(effect: DeferredEffectRead) -> NotificationDeliveryResult:
    ...
```

The handler accepts exactly one envelope id from the effect payload. There is
no separate batch helper or second delivery entry path in SLICE-015. Tests
exercise delivery by invoking the registered handler or the one-envelope
service function with a test envelope and fake delivery port.

#### Delivery service

Create `services/api/app/services/notifications_delivery.py`.

Introduce a small delivery port protocol in the API contracts or service
module:

```python
class NotificationDeliveryPort(Protocol):
    def deliver(self, command: NotificationDeliveryCommand) -> NotificationDeliveryResult: ...
```

The service flow:

1. Claim the requested pending envelope with `FOR UPDATE SKIP LOCKED`
   semantics:
   `delivery_status = 'pending'`, `attempts < max_attempts`, and unclaimed or
   expired lease.
2. If the envelope is already `delivered` or `delivered_in_flight`, return a
   no-op success result and do not call the delivery port.
3. Convert the claimed row to `NotificationDeliveryCommand`.
4. Mark the envelope `delivery_status = 'delivered_in_flight'` immediately
   before invoking the configured delivery port. This is not a claim status; it
   is the local guard against replaying an already submitted Discord send after
   Discord's nonce window expires.
5. Call the configured delivery port.
6. On success, update only the envelope:
   - `delivery_status = 'delivered'`
   - `discord_message_id = result.discord_message_id`
   - `delivered_at = result.delivered_at`
   - clear claim fields
7. On a definitive pre-send or rejected-send failure, update only the envelope:
   - `attempts = attempts + 1`
   - `last_error_json` stores error class/message
   - clear claim fields
   - keep `delivery_status = 'pending'` when attempts remain
   - set `delivery_status = 'failed'` when attempts reaches `max_attempts`
8. On an ambiguous transport failure after the send may have reached Discord,
   keep `delivery_status = 'delivered_in_flight'`, store the error detail, and
   require operator reconciliation rather than retrying after the nonce window.
9. Never update `notification_rules` from the delivery service.

The service actor identity is fixed:

- `actor_kind = "service"`
- `actor_id = "notification-dispatcher"`

Use this actor for audit context around materialization/delivery operations and
for internal API calls where endpoints are used.

The task handler must be testable with an injected fake delivery port. WU-029C
provides the real Discord implementation of the same command/result contract.

#### Operator visibility

Extend
`services/api/app/repositories/deferred_effects.py::query_degraded_state_summary`
so the existing degraded-state summary includes stale in-flight notification
envelopes. For the `notifications` subsystem, add
`stuck_in_flight_envelopes` as the count of:

```sql
notification_envelopes
WHERE delivery_status = 'delivered_in_flight'
  AND claimed_at < now() - INTERVAL '1 hour'
```

This is a read-only extension of the existing summary query, not a new endpoint
and not a reconciliation action. It gives operators visibility into ambiguous
transport failures that cannot safely be retried by the worker.

#### Tests

Create `services/api/tests/test_notification_delivery_worker.py`:

- `test_claim_due_rows_with_claim_status_none_does_not_set_status`
- `test_delivery_worker_marks_envelope_delivered_exactly_once`
- `test_delivery_worker_skips_delivered_in_flight_without_resend`
- `test_degraded_state_summary_counts_stuck_in_flight_envelopes`
- `test_discord_delivery_failure_does_not_mutate_rule`
- `test_retry_attempts_counter_increments_on_failure`

The exactly-once test should simulate two handler invocations for the same
pending envelope and assert that only one call reaches the delivery port and
only one delivered transition is persisted.

Existing scheduler and deferred-effects claim regression tests must remain
unchanged and green; the helper default still writes `status = 'claimed'` for
those tables.

### WU-029C - Discord Notification Delivery Adapter

#### Contracts

Create `services/discord/app/contracts/notifications.py`.

Mirror the minimum command/result shape needed by the adapter:

- `NotificationEnvelopeRead`
- `NotificationDeliveryCommand`
- `NotificationDeliveryResult`
- `NotificationDeliveryError`, with a `definitive_failure: bool` flag so the
  API worker can distinguish retryable rejected sends from ambiguous transport
  failures after Discord may have accepted the request.

Keep the field names aligned with `services/api/app/contracts/notifications.py`
so serialization across the API/Discord boundary stays direct.

#### Adapter

Create `services/discord/app/handlers/notifications.py`.

Implement:

```python
async def deliver_notification(
    command: NotificationDeliveryCommand,
    *,
    bot: Any,
) -> NotificationDeliveryResult:
    ...
```

Responsibilities:

- Deliver exactly one materialized envelope.
- Use `envelope_nonce(envelope.id)` as the Discord Create Message `nonce`,
  where:

  ```python
  import base64
  from uuid import UUID

  def envelope_nonce(envelope_id: UUID) -> str:
      encoded = base64.b32encode(envelope_id.bytes).decode("ascii").rstrip("=")
      return encoded[:25]
  ```

  UUID4 has 128 bits. Base32 encoding without padding is 26 characters; the
  truncated 25-character token leaves roughly 123 bits of collision space and
  stays within Discord's nonce limit.
- Set `enforce_nonce = True`.
- Use the envelope snapshot only:
  - `rendered_title`
  - `rendered_body`
  - `recipient_discord_id`
  - `channel`
  - `destination_channel_id`
  - `actionable`
- Do not fetch or mutate notification rules.
- For `channel = "dm"`, open/create a DM with `recipient_discord_id`.
- For `channel = "designated_channel"`, send to `destination_channel_id`.
- For `channel = "thread"`, raise `NotificationDeliveryError` if reached; the
  materializer should have skipped these envelopes in SLICE-015.
- If `actionable = true`, include only components represented by the
  materialized envelope snapshot. If no component snapshot exists, send a
  normal informational message rather than reading the current rule.
- Return `discord_message_id` and `delivered_at`.
- Raise `NotificationDeliveryError` on Discord exceptions, including whether
  the failure is definitive or ambiguous, so WU-029B can either retry a
  definitively failed send or keep `delivered_in_flight` for reconciliation.

If `discord.py` does not expose `enforce_nonce` on its high-level send helper,
use the library's HTTP route/client escape hatch in the adapter, not in the API
service. The adapter owns Discord-specific mechanics.

#### Tests

Create `services/discord/tests/test_notifications.py`:

- `test_delivery_uses_deterministic_nonce_derived_from_envelope_id`
- adapter success returns envelope id, Discord message id, and delivered time
- adapter failure raises a typed delivery error without calling any rule API
- DM and designated-channel routing use the envelope snapshot

## 4. Tradeoffs

- **Deferred effects instead of recurring scheduler jobs.** D9 says each
  `notification_events` insert enqueues materialization, and the current
  scheduler already runs `deferred_effect_worker_tick()` from
  `SchedulerLoop._tick()`. This avoids adding recurring scheduler primitives.

- **Envelope claim fields without a `claimed` delivery status.** D4 fixes
  delivery claiming to lease fields instead of a `claimed` status. Claim
  ownership lives in `claimed_by`, `claimed_at`, and `lease_until`, so the
  worker can still use skip-locked leasing. `delivered_in_flight` is separate:
  it records that the send may already have reached Discord and prevents
  retries after Discord's nonce window has expired. Revision 2 requires the
  shared claim helper to omit the `status` SET clause entirely when
  `claim_status=None`, preserving the existing scheduler/deferred-effect claim
  behavior while allowing envelope leasing without a `status` column.

- **Deterministic short nonce plus local delivery guard.** Discord's nonce
  window is only a few minutes. The adapter still sends
  `envelope_nonce(envelope_id)` with `enforce_nonce = True` as a
  belt-and-suspenders dedupe mechanism inside that window. For later retries,
  the delivery service falls back to local state: if
  `delivery_status IN ('delivered', 'delivered_in_flight')`, it does not
  re-attempt the Discord send.

- **Two partial unique indexes instead of one generic materialization key.**
  The binding decisions specify different uniqueness for `per_event` and
  `per_root_cause`. Partial unique indexes encode that contract directly and
  make accidental cross-mode dedup impossible.

- **Template rendering is intentionally small and strict.** `string.Template`
  with a flattened event context is enough for the required snapshot tests. The
  implementation uses `substitute()`, not `safe_substitute()`, so missing
  variables become skipped envelopes instead of broken operator-visible
  messages. A richer template language would add escaping, validation, and
  security surface that belongs outside this slice.

- **Explicit user recipients first.** The current database has members and
  chapter roles, but not a reliable local role membership view. Persisting
  `discord_role` recipient JSON exactly while marking unsupported role
  resolution as skipped avoids a fake resolver and keeps later role-based
  delivery clean.

- **Delivery port abstraction.** The API worker owns envelope claiming and
  delivery state. Discord-specific message mechanics stay in WU-029C. Tests use
  a fake port so exactly-once and retry behavior are verified without sending
  live Discord messages.

- **Stuck in-flight visibility without reconciliation.** Ambiguous transport
  failures remain `delivered_in_flight` and are not retried automatically. This
  slice surfaces stale rows in the existing degraded-state summary as
  `stuck_in_flight_envelopes`; actual operator reconciliation remains outside
  SLICE-015.

## 5. Preserved

### SLICE-002 notification_events

Preserve:

- `notification_events` as the durable source event table.
- `NotificationEventDraft` and `NotificationEventRead` semantics.
- `emit()` requiring an audit context.
- `replay()` ordering by `(created_at ASC, id ASC)`.
- Existing indexes on correlation and `(event_type, created_at)`.

Change only:

- Replace `emit()` with the keyword-only `db`/`event`/`actor` plus optional
  `connection` contract.
- After inserting a notification event, enqueue a deferred materialization
  effect in the same transaction.

Do not:

- Add rule state to `notification_events`.
- Add delivery status to `notification_events`.
- Scan `activity_actions` directly.
- Change event redaction behavior.

### SLICE-004 scheduler

Preserve:

- `register_scheduler_handler()` as the handler registration mechanism.
- `SchedulerLoop._tick()` dispatching scheduled jobs and then
  `deferred_effect_worker_tick()`.
- `deferred_effects` idempotency by `idempotency_key`.
- Claim/lease/retry behavior based on `_claim.claim_due_rows()`, generalized
  so notification envelopes can claim rows without writing a `claimed` status.

Change only:

- Add notification handler modules that register
  `notifications_materialize` and `notifications_deliver`.
- Add deferred effects from event emit/materialization.
- Add `claim_status: str | None = "claimed"` to `_claim.claim_due_rows()` so
  existing callers retain current behavior and notification envelopes pass
  `None`; `None` means omit the status SET clause entirely.
- Extend `query_degraded_state_summary()` with a read-only
  `stuck_in_flight_envelopes` count for stale
  `notification_envelopes.delivery_status = 'delivered_in_flight'` rows.

Do not:

- Add recurring scheduler primitives.
- Change scheduler job status semantics.
- Change global claim constants for all subsystems.

## 6. Resolved Decisions

| Decision | Resolution with code refs |
|---|---|
| D1 | Implement `notification_rules` exactly in `migrations/versions/wu-029a_notifications.py`. Version is read by joining `aggregate_heads`, following `services/api/app/repositories/members.py:10`. Mutations use `aggregate_type="notification_rule"` through `services/api/app/services/mutations.py:58`. |
| D2 | Add `NotificationTrigger` to `services/api/app/contracts/notifications.py`, preserving trigger JSON as flexible JSONB. Existing event types are free text in `migrations/versions/wu-003c_notification_events.py:20` and `NotificationEventDraft.event_type` at `services/api/app/contracts/notifications.py:12`. |
| D3 | Use existing `ScopeKind` from `services/api/app/contracts/scope.py` and the same scope vocabulary enforced by `notification_events` in `migrations/versions/wu-003c_notification_events.py:37`. Matching is implemented in `services/api/app/services/notifications_materialize.py`. |
| D4 | Keep `notification_events` as the source queue and add `notification_envelopes` in `wu-029a_notifications.py`. Existing event insert/read code remains in `services/api/app/repositories/notification_events.py:14` and `:55`. |
| D5 | Store `grouping` on both rules and envelopes. Implement `per_event` and `per_root_cause` with partial unique indexes in `wu-029a_notifications.py`; materialization computes root from `notification_events.correlation_id`, which is persisted by `migrations/versions/wu-003c_notification_events.py:21`. |
| D6 | Implement delivery claiming in `services/api/app/repositories/notifications.py` using `FOR UPDATE SKIP LOCKED`, by generalizing `services/api/app/repositories/_claim.py:10` to allow `claim_status=None` for envelope rows. When `None`, `_claim` omits the `status` SET clause entirely. Delivery status mutation lives in `services/api/app/services/notifications_delivery.py`. |
| D7 | Implement deterministic short nonce handling in `services/discord/app/handlers/notifications.py`; `services/discord/tests/test_notifications.py::test_delivery_uses_deterministic_nonce_derived_from_envelope_id` verifies the 25-character derived nonce and `enforce_nonce = True`. |
| D8 | Implement envelope inserts with `ON CONFLICT DO NOTHING` in `services/api/app/repositories/notifications.py`; tests verify replay and retry idempotency against the unique indexes. |
| D9 | Register handlers with `register_scheduler_handler()` from `services/api/app/services/scheduler.py:80`. `emit()` in `services/api/app/services/notification_events.py:27` accepts either a caller-supplied transaction connection or a `db` to open its own transaction, then atomically inserts the event and enqueues `notifications_materialize`; materialization enqueues `notifications_deliver`; `SchedulerLoop._tick()` already runs deferred effects at `services/api/app/services/scheduler.py:180`. |
| D10 | Persist `recipients_json` exactly on rules. Resolve recipients and `destination_channel_id` only in `services/api/app/services/notifications_materialize.py`, then snapshot `recipient_discord_id`, `recipient_display`, and `destination_channel_id` on `notification_envelopes`. Unsupported recipient selectors, missing designated-channel destinations, and thread channels create skipped envelopes. |
| D11 | Persist `template_json` exactly on rules. Render strictly with `string.Template.substitute()` in `services/api/app/services/notifications_materialize.py` and snapshot `template_snapshot_json`, `rendered_title`, and `rendered_body` on envelopes. Missing keys raise `TemplateRenderError` and materialize as skipped envelopes. Delivery reads only envelope fields. |
| D12 | Endpoints use `RequireAuthority` from `services/api/app/core/dependencies.py:129`. Migration seeds global `notification.read` and `notification.deliver` for `notification-dispatcher`, following guarded service-grant patterns in `migrations/versions/wu-012_trust.py:61` and `migrations/versions/wu-019_chapter_lifecycle.py:107`. Rule writes require `notification.write` and are not granted to the dispatcher. |
| D13 | Worker code uses `ActorIdentity(actor_kind="service", actor_id="notification-dispatcher")` and, where API calls are made, the headers `X-Actor-Kind: service` and `X-Actor-Id: notification-dispatcher`, matching Discord service call patterns in `services/discord/app/handlers/onboarding.py:10` and `services/discord/app/infrastructure/api_client.py:25`. |
| D14 | Excluded features stay out of the migration, contracts, services, endpoints, and tests. No ack UI, digest, preferences, email/SMS, archival, cross-guild federation, recurring schedules, or template registry is added. |

## 7. AC Trace

### AC1: Rule create/update persists exactly and stale patch returns 412

Tests:

- `test_create_rule_persists_trigger_recipients_channel_grouping`
- `test_rule_create_audit_payload_includes_all_rule_fields`
- `test_patch_rule_with_current_version_succeeds`
- `test_patch_rule_stale_version_returns_412`
- `test_list_rules_filters_by_scope`

Implementation trace:

- `NotificationRuleCreate` and `NotificationRulePatch` expose trigger,
  recipients, channel, template, actionable, grouping, scope, and enabled.
- `notification_rules` stores `trigger_json`, `recipients_json`, and
  `template_json` without normalization.
- `create_notification_rule()` uses `mutate_entity(... expected_version=0)`.
- Create audit payload contains exactly `trigger_json`, `scope_kind`,
  `scope_id`, `recipients_json`, `channel`, `template_json`, `actionable`,
  `grouping`, and `enabled`.
- `patch_notification_rule()` parses `If-Match` and uses
  `mutate_entity(... expected_version=<If-Match>)`.
- `StaleMutationError` maps to `412` with
  `stale_notification_rule_version`.
- List filters query persisted `scope_kind` and `scope_id`.

### AC2: Grouping per_root_cause vs per_event

Tests:

- `test_per_event_rule_emits_one_envelope_per_event`
- `test_per_root_cause_rule_emits_one_envelope_per_root_correlation`
- `test_multiple_events_same_root_correlation_one_envelope`
- `test_different_root_correlations_separate_envelopes`

Implementation trace:

- `NotificationGrouping` persists on rules and envelopes.
- `per_event` inserts one envelope for each `(event, rule, recipient)`.
- `per_root_cause` inserts one envelope for each
  `(event.correlation_id, rule, recipient)`.
- The per-root-cause unique index omits `source_event_id`, so multiple events
  with the same correlation collapse to one envelope.
- Events with different correlations produce separate envelopes.

### AC3: Replay dedup

Tests:

- `test_emit_is_atomic_when_called_with_connection`
- `test_replay_same_event_no_duplicate_envelopes`
- `test_unique_index_prevents_duplicate_envelope_rows`
- `test_materialize_is_idempotent_under_retry`

Implementation trace:

- `materialize_event()` is the only envelope insert path for initial handling,
  retry, and replay.
- `emit(connection=...)` inserts the source event and enqueues the
  `notifications_materialize` deferred effect in the caller's transaction, so a
  forced enqueue failure rolls both writes back.
- Envelope repository inserts use `ON CONFLICT DO NOTHING`.
- Partial unique indexes enforce the binding grouping keys at the database
  layer.
- Existing envelopes are not updated on replay, preserving the original
  rendered/template/recipient snapshot.

### AC4: Exactly-once delivery and rule preservation

Tests:

- `test_delivery_worker_marks_envelope_delivered_exactly_once`
- `test_delivery_worker_skips_delivered_in_flight_without_resend`
- `test_degraded_state_summary_counts_stuck_in_flight_envelopes`
- `test_discord_delivery_failure_does_not_mutate_rule`
- `test_delivery_uses_deterministic_nonce_derived_from_envelope_id`
- `test_retry_attempts_counter_increments_on_failure`

Implementation trace:

- Delivery claims pending envelopes with skip-locked leasing.
- A claimed envelope is sent once by the winning worker.
- Before invoking Discord, delivery marks the row `delivered_in_flight`; later
  retries do not resend rows already in `delivered` or `delivered_in_flight`.
- Success updates only `notification_envelopes`.
- Failure increments envelope attempts and stores error metadata; when attempts
  are exhausted, status becomes `failed`.
- Delivery never calls rule update repository functions and never writes
  `notification_rules`.
- Existing degraded-state summary reports stale
  `delivered_in_flight` envelopes as `stuck_in_flight_envelopes`.
- WU-029C sends `nonce = envelope_nonce(envelope_id)` with
  `enforce_nonce = True`.

### Invariants

Tests:

- `test_claim_due_rows_with_claim_status_none_does_not_set_status`
- `test_notification_dispatcher_service_grants_seeded`
- `test_recipient_resolution_at_materialization_time`
- `test_designated_channel_destination_snapshotted_at_materialization_time`
- `test_materialize_skips_when_template_has_missing_key`
- `test_template_rendering_snapshot_isolates_from_later_rule_edits`

Implementation trace:

- Migration seed grants `notification-dispatcher` only
  `notification.read` and `notification.deliver`.
- `_claim.claim_due_rows(claim_status=None)` omits the status assignment while
  the existing scheduler and deferred-effect callers keep the default claimed
  status behavior.
- Recipient resolution writes concrete recipient fields onto the envelope at
  materialization time.
- Destination resolution writes the concrete destination channel onto the
  envelope at materialization time.
- Template rendering writes rendered title/body and the template snapshot onto
  the envelope at materialization time.
- Strict template rendering turns missing keys into skipped envelopes with
  `template_missing_key` instead of shipping `${missing_key}` text.
- Later rule edits do not change existing envelopes.

## Implementation Order

1. WU-029A contracts and migration.
2. WU-029A repository/service/endpoints and rule tests.
3. WU-029B-materialize envelope repository functions, materialization service,
   task registration, event emit signature/atomic enqueue, and materialization
   tests.
4. WU-029B-deliver claim/mark repository functions, delivery service, task
   registration, degraded summary extension, and delivery worker tests with a
   fake port.
5. WU-029C Discord contracts, adapter, and Discord adapter tests.
6. Run API and Discord test suites.

## Revision History

- **Revision 2**: Addressed audit round 2 M1-M4; scope and shortcut risks were
  already LOW, and these changes remove the remaining audit MEDIUMs.
  - Pinned `_claim.claim_due_rows(claim_status=None)` to omit the `status` SET
    clause entirely, with regression coverage for existing scheduler and
    deferred-effect callers plus
    `test_claim_due_rows_with_claim_status_none_does_not_set_status`.
  - Replaced `emit()` with a `db`/`event`/`actor` plus optional `connection`
    contract so event insert and `notifications_materialize` enqueue are
    atomic whether called inside or outside an existing transaction; added
    `test_emit_is_atomic_when_called_with_connection`.
  - Extended the existing degraded-state summary with
    `stuck_in_flight_envelopes` for stale `delivered_in_flight` rows.
  - Pinned rule mutation audit payload fields to the persisted rule-field
    allowlist and added
    `test_rule_create_audit_payload_includes_all_rule_fields`.

- **Revision 1**: Addressed Audit M1/M2 and Shortcut #1-#5.
  - Replaced raw UUID Discord nonce usage with deterministic 25-character
    `envelope_nonce(envelope_id)` and documented local delivery-state fallback
    after Discord's nonce window.
  - Required materialization to insert envelopes and enqueue per-envelope
    delivery effects in one transaction through a shared deferred-effect
    connection.
  - Added materialization-time `destination_channel_id` resolution for DM and
    designated-channel rules, with thread delivery deferred out of scope.
  - Replaced template `safe_substitute()` with strict `substitute()` and
    skipped envelopes on `template_missing_key`.
  - Generalized `_claim.claim_due_rows()` with `claim_status=None` instead of
    adding an envelope `claimed` status.
  - Removed the batch delivery helper path; production and tests now use the
    one-envelope deferred-effect handler/service path.
