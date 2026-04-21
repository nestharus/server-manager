# SLICE-015 Phase 1 Research: Configurable Operator Notifications

## 1. Prototyping Assessment

**NO - production design can proceed without a disposable prototype.**

The risky parts are data semantics, not unknown external mechanics:

- `notification_events` already exists as a durable, replayable event substrate with `event_type`, correlation, causation, scope, payload JSON, and created timestamp (`migrations/versions/wu-003c_notification_events.py:17`, `services/api/app/contracts/notifications.py:12`).
- The API already has the optimistic-locking primitive needed for `NotificationRule.version`: `mutate_entity()` creates an aggregate head for `expected_version=0`, locks the head, rejects stale writes, records accepted/rejected/failed audit actions, and returns an ETag (`services/api/app/services/mutations.py:58`, `services/api/app/services/mutations.py:97`, `services/api/app/services/mutations.py:112`, `services/api/app/services/mutations.py:123`, `services/api/app/services/mutations.py:150`, `services/api/app/services/mutations.py:167`).
- The scheduler foundation already has claim/lease mechanics through `FOR UPDATE SKIP LOCKED` and status transitions (`services/api/app/repositories/_claim.py:10`, `services/api/app/repositories/scheduler.py:104`, `services/api/app/services/scheduler.py:174`).
- Discord message idempotency is supported by Discord's Create Message `nonce` + `enforce_nonce` fields. Official docs say `enforce_nonce=true` dedupes messages for the same sender for a few minutes when the same nonce is supplied (https://docs.discord.com/developers/resources/message#create-message, lines 930-944; https://docs.discord.com/developers/change-log, lines 2152-2154).

The proposal must still pin two design choices: how the materialize/deliver ticks are triggered under the currently one-shot scheduler model, and how authority-derived recipients become concrete Discord users.

## 2. Per-Question Answers

### 2.1 NotificationRule Aggregate

No `NotificationRule` code exists today. The only notification production code is the Phase 0 event envelope (`services/api/app/contracts/notifications.py:12`, `services/api/app/services/notification_events.py:27`).

Recommended aggregate:

- `aggregate_type = "notification_rule"`
- `notification_rules.id UUID PRIMARY KEY`
- `trigger_json JSONB NOT NULL`
- `scope_kind TEXT NOT NULL CHECK IN ('global','chapter','member')`
- `scope_id TEXT NULL`
- `recipients_json JSONB NOT NULL`
- `channel TEXT NOT NULL CHECK IN ('dm','thread','designated_channel')`
- `template_json JSONB NOT NULL`
- `actionable BOOLEAN NOT NULL`
- `grouping TEXT NOT NULL CHECK IN ('per_event','per_root_cause')`
- `enabled BOOLEAN NOT NULL DEFAULT TRUE`
- `created_at`, `updated_at`

`version` should come from `aggregate_heads.current_seq`, not a separate `version` column, matching `chapters` and `members` read models (`services/api/app/repositories/chapters.py:10`, `services/api/app/repositories/members.py:10`).

`template` should be inline JSONB on the rule, not a template-table reference. The proposal defines `template` as JSONB (`product-strategy/proposal.md:624`, `product-strategy/proposal.md:635`), and the existing `policy_versions` table is a generic preview-confirm surface, not a notification template registry (`migrations/versions/wu-005_policy_foundation.py:17`, `services/api/app/contracts/policies.py:63`). Materialized envelopes should snapshot the rendered payload or template JSON so delivery is not affected by later rule edits.

### 2.2 Trigger Types

Current code has no trigger enum. Both audit actions and notification events are free-text dotted strings:

- `notification_events.event_type` is free text (`migrations/versions/wu-003c_notification_events.py:20`).
- `NotificationEventDraft.event_type` is an unconstrained non-empty string (`services/api/app/contracts/notifications.py:12`).
- Existing mutation action types include `chapter.transition`, `roster_entry.transition`, `roster_entry.sync_failure`, `authority.override`, `policy.confirm`, `permission_drift.update_status`, and similar dotted names (`services/api/app/services/chapters.py:392`, `services/api/app/services/roster.py:275`, `services/api/app/services/roster.py:369`, `services/api/app/services/audit_overrides.py:50`, `services/api/app/services/policies.py:167`, `services/api/app/services/permissions.py:286`).

Recommended trigger contract:

```text
NotificationTrigger(
  event_type: str,              # exact dotted name or prefix pattern ending in .*
  payload_filters: dict | None  # optional exact-match JSON keys for later proposal if needed
)
```

Examples:

- `chapter.*`
- `chapter.transition`
- `roster_entry.*`
- `roster_entry.sync_failure`
- `permission_drift.*`
- Future: `application.*`, `ticket.*`, `sla.*`, `compliance.*`

Avoid a database enum for trigger values. Later slices will add producers, and enum growth would create migration conflicts. Treat `audit.*` as a naming convention only if a publisher emits `notification_events.event_type = "audit.<action_type>"`; SLICE-015 should not scan `activity_actions` directly.

### 2.3 Scope and Authority

Rule scope should use the same `ScopeKind` vocabulary as audit, notification events, policies, and authority grants: `global`, `chapter`, `member` (`services/api/app/contracts/scope.py:4`, `migrations/versions/wu-003c_notification_events.py:37`, `migrations/versions/wu-004_authority_foundation.py:51`).

Matching semantics:

- A global rule may match any event.
- A chapter rule matches only events with `scope_kind='chapter'` and the same `scope_id`.
- A member rule matches only events with `scope_kind='member'` and the same `scope_id`.
- Do not infer chapter/member scope from arbitrary payload fields in Phase 2.

Authority:

- `notification.read`: list/read rules and envelopes.
- `notification.write`: create/update rules.
- `notification.deliver`: service-only permission for materialization and delivery workers if exposed through API routes.

Scope should be global or chapter. Use global authority for global rules and chapter authority for chapter-scoped rules. Existing `RequireAuthority` supports static route checks (`services/api/app/core/dependencies.py:56`), but list/create with body-driven scope needs manual evaluation like roster endpoints do (`services/api/app/api/v1/endpoints/roster.py:78`).

Seed a service grant for the delivery actor, e.g. `notification-worker`, with global `notification.deliver`. Current migrations seed service actors with guarded inserts for `discord-provisioner` and `member-onboarder`; follow that pattern rather than relying on manual grants.

### 2.4 Notification Event Substrate

The table exists from WU-003C:

- `id UUID PRIMARY KEY`
- `event_type TEXT NOT NULL`
- `correlation_id UUID NOT NULL`
- `causation_id UUID NULL`
- `scope_kind TEXT NULL`
- `scope_id TEXT NULL`
- `payload_json JSONB NOT NULL DEFAULT {}`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`
- indexes on `correlation_id` and `(event_type, created_at)` (`migrations/versions/wu-003c_notification_events.py:17`).

The service layer redacts payloads unless a caller passes an allowlist (`services/api/app/services/notification_events.py:14`) and requires an active audit context (`services/api/app/services/notification_events.py:27`). Replay is by `correlation_id`, ordered by `(created_at ASC, id ASC)` (`services/api/app/repositories/notification_events.py:71`).

No status, claim, attempts, or lease columns exist on `notification_events`. If it is used as a persistent queue, SLICE-015 must add processing metadata or create a separate processing table.

### 2.5 Grouping Semantics

The product proposal defines root cause by correlation: all events in one causal cascade share `correlation_id`; direct causation is represented separately by `causation_id` (`product-strategy/proposal.md:610`, `product-strategy/proposal.md:620`). Current SLICE-009 implementation returns a "chain" by selecting every audit entry with the seed entry's `correlation_id`, not by walking `causation_id` recursively (`services/api/app/services/audit_queries.py:49`, `services/api/app/repositories/audit.py:39`, `services/api/tests/test_audit_api.py:451`).

Therefore for SLICE-015:

- `per_event`: grouping key is `event:{notification_events.id}`.
- `per_root_cause`: grouping key is `root:{notification_events.correlation_id}`.
- Root correlation ID is currently just `correlation_id`; do not introduce a second `root_correlation_id` field unless the audit query slice later implements recursive causation backtracking.

### 2.6 Materialization Trigger

Current `emit()` only inserts a `notification_events` row and returns the event UUID (`services/api/app/services/notification_events.py:27`). It does not enqueue a scheduled job, dispatch a handler, or automatically inspect `activity_actions`.

Recommended answer: materialization should be triggered by persisted `notification_events`, not by every `activity_actions` insert. Producers decide when an operational event is notification-worthy and call `emit()` inside their mutation projection. This preserves the Phase 0 boundary that notification delivery is owned by VS-009 while event emission belongs to emitting slices (`product-strategy/engineering-roadmap-revision-cycle5.md:22`, `product-strategy/engineering-roadmap-revision-cycle5.md:46`).

Open implementation issue: the existing scheduler is one-shot. `SchedulerLoop` claims due `scheduled_jobs`, dispatches a handler, and marks the job completed (`services/api/app/services/scheduler.py:174`, `services/api/app/services/scheduler.py:199`, `services/api/app/services/scheduler.py:234`). There is no recurring schedule field or reschedule hook in `scheduled_jobs` (`migrations/versions/wu-008a_scheduler_foundation.py:17`). The proposal must explicitly choose one:

1. Add notification tick calls beside `deferred_effect_worker_tick()` in `SchedulerLoop._tick()`.
2. Add self-rescheduling notification jobs with unique time-bucket keys.
3. Add a recurring-job primitive to the scheduler substrate.

Given the WU-029B code boundary does not list `services/api/app/services/scheduler.py`, option 2 is the least invasive if the proposal wants to keep the scheduler boundary unchanged.

### 2.7 Rule Evaluation Timing

Recommended: evaluate rules at materialization time against persisted events.

Rationale:

- `notification_events` is the replayable source (`product-strategy/tickets/SLICE-002.md:21`, `product-strategy/tickets/SLICE-002.md:58`).
- AC3 requires replaying the same persisted event without duplicate envelopes, so idempotency belongs in materialization, not event creation (`product-strategy/tickets/SLICE-015.md:55`).
- Rule creation/update is a governed aggregate; evaluating at materialization time lets tests seed one event and multiple rules without changing every event producer.

Do not scan all events forever. Use claim/lease processing metadata on events or a separate materialization-state table, plus envelope uniqueness for replay safety.

### 2.8 Template Rendering

Render before delivery, in the API materialization service, and snapshot the result onto `notification_envelopes`.

Reasons:

- Delivery failures must not mutate rule definitions (`product-strategy/tickets/SLICE-015.md:58`).
- The Discord adapter should be a platform adapter that delivers one typed envelope, not a rule evaluator.
- Snapshotting protects pending envelopes from later rule edits.

The Discord adapter may translate the snapshot into Discord embeds/components, but it should not read current rules.

### 2.9 Recipient Resolution

Resolve recipients at materialization time, not delivery time.

Reasons:

- `notification_envelopes` should be one row per materialized recipient, as the work unit expects.
- Delivery retries should not change recipient sets after a rule or authority grant changes.
- Envelope uniqueness needs a concrete recipient key.

Recommended recipient JSON shapes:

```json
{"type": "discord_users", "user_ids": ["123", "456"]}
{"type": "authority", "permission": "roster.write", "scope": "event"}
```

Authority-derived recipients require a binding decision because `authority_grants` has `grantee_id` but no `grantee_kind` (`migrations/versions/wu-004_authority_foundation.py:17`, `services/api/app/repositories/authority.py:69`). If `grantee_id` is assumed to be a Discord user snowflake for user actors, materialization can exclude known service actor IDs and non-snowflake IDs. A stricter design would add recipient resolution through `members.discord_user_id`.

## 3. Proposed Data Model

### `notification_rules`

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

Constraints/indexes:

- `CHECK scope_kind IN ('global','chapter','member')`
- `CHECK channel IN ('dm','thread','designated_channel')`
- `CHECK grouping IN ('per_event','per_root_cause')`
- `INDEX (scope_kind, scope_id)`
- `INDEX USING GIN (trigger_json)`

Version comes from `aggregate_heads` with `aggregate_type='notification_rule'`.

### `notification_events` additions or side table

Preferred minimal addition if using event rows as the queue:

- `materialization_status TEXT NOT NULL DEFAULT 'pending'`
- `claimed_by TEXT NULL`
- `claimed_at TIMESTAMPTZ NULL`
- `lease_until TIMESTAMPTZ NULL`
- `attempts INT NOT NULL DEFAULT 0`
- `max_attempts INT NOT NULL DEFAULT 3`
- `last_error_json JSONB NULL`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`

Constraints/indexes:

- `CHECK materialization_status IN ('pending','claimed','materialized','failed','skipped')`
- partial index on `(created_at, id)` where status is `pending` or `claimed`

Alternative: `notification_event_materialization_state(event_id PK, ...)` if the proposal wants `notification_events` payload rows to remain physically immutable.

### `notification_envelopes`

- `id UUID PRIMARY KEY`
- `rule_id UUID NOT NULL REFERENCES notification_rules(id) ON DELETE RESTRICT`
- `rule_version BIGINT NOT NULL`
- `source_event_id UUID NOT NULL REFERENCES notification_events(id) ON DELETE RESTRICT`
- `correlation_id UUID NOT NULL`
- `causation_id UUID NULL`
- `grouping TEXT NOT NULL`
- `materialization_key TEXT NOT NULL`
- `recipient_kind TEXT NOT NULL DEFAULT 'discord_user'`
- `recipient_id TEXT NOT NULL`
- `channel TEXT NOT NULL`
- `destination_channel_id TEXT NULL`
- `template_snapshot_json JSONB NOT NULL`
- `rendered_payload_json JSONB NOT NULL`
- `actionable BOOLEAN NOT NULL`
- `delivery_status TEXT NOT NULL DEFAULT 'pending'`
- `claimed_by TEXT NULL`
- `claimed_at TIMESTAMPTZ NULL`
- `lease_until TIMESTAMPTZ NULL`
- `attempts INT NOT NULL DEFAULT 0`
- `max_attempts INT NOT NULL DEFAULT 3`
- `last_error_json JSONB NULL`
- `discord_message_id TEXT NULL`
- `delivered_at TIMESTAMPTZ NULL`
- `created_at`, `updated_at`

Constraints/indexes:

- `UNIQUE (rule_id, recipient_kind, recipient_id, materialization_key)`
- partial index on `(created_at, id)` where `delivery_status IN ('pending','claimed')`
- `INDEX (correlation_id)`
- `INDEX (source_event_id)`
- `CHECK delivery_status IN ('pending','claimed','delivered','failed','skipped')`

AC3 is satisfied by the unique materialization key. For `per_event`, `materialization_key='event:<event_id>'`; for `per_root_cause`, `materialization_key='root:<correlation_id>'`. A unique key on only `(event_id, rule_id)` is insufficient because one rule can emit one envelope per recipient, and it is wrong for `per_root_cause` because multiple events share the same root.

## 4. Proposed API Surface

Contracts in `services/api/app/contracts/notifications.py`:

```text
NotificationTrigger(event_type: str, payload_filters?: dict)
NotificationRuleCreate(trigger, scope_kind, scope_id?, recipients, channel, template, actionable, grouping, enabled=true)
NotificationRulePatch(trigger?, scope_kind?, scope_id?, recipients?, channel?, template?, actionable?, grouping?, enabled?)
NotificationRuleRead(id, trigger, scope_kind, scope_id?, recipients, channel, template, actionable, grouping, enabled, version, created_at, updated_at)
NotificationRuleListRead(items, next_cursor?)

NotificationEnvelopeRead(id, rule_id, correlation_id, source_event_id, recipient_id, channel, actionable, delivery_status, delivered_at?)
NotificationMaterializationResult(event_id, created_envelope_ids, skipped_envelope_ids)
NotificationDeliveryBatchRead(delivered_envelope_ids, skipped_envelope_ids, failed_envelope_ids)
NotificationDeliveryCommand(envelope: NotificationEnvelopeRead)
NotificationDeliveryResult(envelope_id, delivered_at, discord_message_id)
```

Endpoints:

- `POST /api/v1/notification-rules -> NotificationRuleRead`
- `GET /api/v1/notification-rules?scope_kind=&scope_id= -> NotificationRuleListRead`
- `GET /api/v1/notification-rules/{rule_id} -> NotificationRuleRead`
- `PATCH /api/v1/notification-rules/{rule_id} -> NotificationRuleRead` with `If-Match`; stale returns `412`.

Optional internal endpoints only if the Discord service pulls from API instead of receiving commands in-process:

- `POST /api/v1/notifications/{envelope_id}/delivered`
- `POST /api/v1/notifications/{envelope_id}/failed`

Authority:

- Reads require `notification.read` on requested rule scope.
- Creates/updates require `notification.write` on submitted rule scope.
- Delivery status mutation, if HTTP-exposed, requires service actor `notification-worker` with `notification.deliver`.

## 5. Worker Design

### Materialize Worker

Files:

- `services/api/app/tasks/notifications_materialize.py`
- `services/api/app/services/notifications_materialize.py`
- `services/api/app/repositories/notifications.py`

Handler:

```text
@register_scheduler_handler("notifications.materialize")
def materialize_notifications(job: ScheduledJobRead) -> NotificationMaterializationBatchRead
```

Service flow:

1. Claim pending/stale `notification_events` rows using the existing `_claim.claim_due_rows()` pattern.
2. For each event, select enabled rules whose trigger and scope match.
3. Resolve recipients to concrete Discord user IDs.
4. Compute `materialization_key`.
5. Insert one `notification_envelopes` row per concrete recipient with `ON CONFLICT DO NOTHING`.
6. Mark event `materialized` if all rule evaluations succeeded, `skipped` if no matching rules, or requeue/fail with `last_error_json` on error.

Idempotency:

- Event replay calls the same insert path.
- Duplicate materialization is prevented by `UNIQUE (rule_id, recipient_kind, recipient_id, materialization_key)`.

### Delivery Worker

Files:

- `services/api/app/tasks/notifications_deliver.py`
- `services/api/app/services/notifications_delivery.py`
- `services/api/app/repositories/notifications.py`

Handler:

```text
@register_scheduler_handler("notifications.deliver")
def deliver_notifications(job: ScheduledJobRead) -> NotificationDeliveryBatchRead
```

Service flow:

1. Claim pending/stale envelopes with `delivery_status IN ('pending','claimed')`, `FOR UPDATE SKIP LOCKED`.
2. For each envelope, call a delivery port with `NotificationDeliveryCommand`.
3. On success, update only that envelope: `delivery_status='delivered'`, clear claim fields, set `discord_message_id`, `delivered_at`.
4. On delivery failure, update only that envelope: increment attempts, set `last_error_json`, requeue or mark `failed`.
5. Never update `notification_rules` during delivery failure handling.

This mirrors `deferred_effect_worker_tick()` and the scheduler mark functions, which claim rows, dispatch, and mark completed/failed without changing source configuration (`services/api/app/services/deferred_effects.py:136`, `services/api/app/repositories/deferred_effects.py:173`).

## 6. Discord Adapter Design

Files:

- `services/discord/app/contracts/notifications.py`
- `services/discord/app/handlers/notifications.py`
- `services/discord/tests/test_notifications.py`

Contract:

```text
NotificationDeliveryCommand(envelope: NotificationEnvelopeRead)
NotificationDeliveryResult(envelope_id, delivered_at, discord_message_id)
```

Handler responsibilities:

- Accept one materialized envelope.
- Use `envelope.id` as the idempotency key.
- For Discord Create Message, pass `nonce=<envelope_id-derived <=25 char token>` and `enforce_nonce=True`. Discord supports `nonce` up to 25 characters and `enforce_nonce` dedupes recent duplicate sends by the same author (https://docs.discord.com/developers/resources/message#create-message, lines 930-944).
- Preserve `actionable` exactly: actionable envelopes include configured components/buttons; informational envelopes do not.
- Return `discord_message_id` and `delivered_at`.
- On Discord exceptions, raise a typed delivery error. Do not call rule APIs.

Envelope IDs are UUIDs, which are 36 characters. Because Discord nonce is limited to 25 characters, use a deterministic short token such as base32/base36 of the UUID integer or a 20-byte digest prefix. Store the actual `envelope_id` in the envelope row and in embed/footer/custom_id metadata as needed; use the short nonce only for Discord dedupe.

## 7. Open Questions

1. **Recurring trigger:** The scheduler is currently one-shot. Should notification workers be self-rescheduling jobs, always-run scheduler tick workers, or should SLICE-015 expand the scheduler substrate with recurrence?
2. **Recipient authority resolution:** Are user `authority_grants.grantee_id` values guaranteed to be Discord user IDs? If not, materialization needs a mapping from grantee to member/Discord user.
3. **Rule-history semantics:** If a rule changes after an event is created but before replay, should replay use current rule state or the rule version active at first materialization? The recommended M scope uses current rules plus envelope uniqueness and rule-version snapshot.
4. **Template language:** Inline JSONB is enough for Phase 2, but the proposal must define the minimal supported placeholders and validation failures. Recommended placeholders: `event.*`, `payload.*`, `correlation_id`, `scope_id`, `rule.id`.
5. **Thread delivery:** For `channel='thread'`, does the envelope target an existing thread ID from payload, or should Discord create a thread? Creating threads is a visible Discord write and may broaden WU-029C. Recommended Phase 2 behavior: deliver only to an existing thread/channel ID supplied by the event payload or rule.
6. **Event producer ownership:** Existing services do not emit notification events for real actions. SLICE-015 can test against seeded `notification_events`; later value slices must add producer calls where they need notifications.

## 8. Recommended Magnitude

**Confirm M-L, leaning M if scope is held to rules + event materialization + envelope delivery + Discord adapter.**

Keep it M by:

- Using inline JSONB templates, not a template registry.
- Evaluating only persisted `notification_events`, not retrofitting every `activity_actions` producer.
- Supporting exact/prefix event-type triggers and simple scope matching only.
- Resolving recipients at materialization time with explicit `discord_users` plus one authority-recipient strategy.
- Implementing delivery idempotency with envelope uniqueness plus Discord `nonce`/`enforce_nonce`.

It becomes L if SLICE-015 also adds recurring scheduler primitives, full audit-stream subscription, recursive causation walking, rich template language, thread creation, notification analytics, digests, or broad backfill of notification producers across existing slices.
