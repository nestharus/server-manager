# SLICE-015 Phase 2 Synthesis: Binding Decisions

These decisions are binding for the SLICE-015 proposal and implementation.
The proposal may choose implementation mechanics inside these boundaries, but
it must not add scope, replace these directions, or introduce compatibility
paths around them.

## Acceptance Criteria Reference

- **AC1**: Rule create/update persists grouping, recipients, channel, and
  actionable state exactly as submitted, with stale updates rejected by
  optimistic locking.
- **AC2**: Per-root-cause rules emit one envelope per root correlation ID and
  per-event rules emit one per triggering event.
- **AC3**: Replaying the same persisted notification event does not
  materialize duplicate envelopes.
- **AC4**: Scheduled delivery marks envelopes exactly once and Discord delivery
  failures do not mutate rule definitions.

## Binding Decisions

- **D1 — BINDING: NotificationRule aggregate and table.**
  `NotificationRule` uses `aggregate_type = "notification_rule"` and persists
  to `notification_rules`. The table shape is:
  `id UUID PRIMARY KEY`, `trigger_json JSONB NOT NULL`,
  `scope_kind TEXT NOT NULL CHECK (scope_kind IN ('global','chapter','member'))`,
  `scope_id TEXT NULL`, `recipients_json JSONB NOT NULL`,
  `channel TEXT NOT NULL CHECK (channel IN ('dm','thread','designated_channel'))`,
  `template_json JSONB NOT NULL`, `actionable BOOL NOT NULL`,
  `grouping TEXT NOT NULL CHECK (grouping IN ('per_event','per_root_cause'))`,
  `enabled BOOL NOT NULL DEFAULT TRUE`, `created_at`, and `updated_at`.
  Version comes from `aggregate_heads`, not a rule-table version column.

  AC traceability: supports AC1 by defining the persisted rule fields and
  optimistic-locking source. Supports AC2 by making grouping a persisted rule
  field used by materialization.

- **D2 — BINDING: Trigger shape.**
  `trigger_json` has this contract:
  `{"event_type": str | prefix_pattern_ending_in_.*, "payload_filters": dict | None}`.
  Exact dotted event names and suffix `.*` prefix patterns are valid. Trigger
  values are not DB-enumerated; `trigger_json` remains flexible JSONB.

  AC traceability: supports AC2 by defining how rules match triggering events.
  Supports AC1 by requiring triggers to be persisted as submitted instead of
  normalized into a restrictive enum.

- **D3 — BINDING: Scope matching.**
  Notification rules use the same `ScopeKind` vocabulary as the rest of the
  system: `global`, `chapter`, and `member`. A global rule matches any event.
  A chapter rule matches only events with the same `scope_kind = 'chapter'` and
  `scope_id`. A member rule matches only events with the same
  `scope_kind = 'member'` and `scope_id`. SLICE-015 does not infer scope from
  arbitrary payload fields.

  AC traceability: supports AC2 by making envelope emission deterministic for
  scoped rules. Supports AC3 by keeping replay matching dependent only on
  persisted event scope and rule scope.

- **D4 — BINDING: Materialization flow and envelope table.**
  `notification_events` is the queue. A separate `notification_envelopes` table
  stores materialized per-recipient envelopes with
  `delivery_status IN ('pending','delivered_in_flight','delivered','skipped','failed')`.
  The materialize worker claims unprocessed `notification_events`, matches them
  against enabled rules, and emits one `notification_envelopes` row for each
  `(event, rule, recipient)` that resolves successfully, plus skipped envelope
  rows for supported failure cases such as unresolved recipients, missing
  destinations, or missing template keys.
  Envelope uniqueness is:
  `UNIQUE(event_id, rule_id, recipient_key)` for `per_event`, and
  `UNIQUE(rule_id, root_correlation_id, recipient_key)` for `per_root_cause`.
  For SLICE-015, `root_correlation_id` is the event correlation/root value used
  for causal grouping.

  AC traceability: supports AC2 by separating persisted events from
  per-recipient envelopes. Supports AC3 through unique materialization keys.
  Supports AC4 by giving delivery its own status-bearing work units.

- **D5 — BINDING: Grouping semantics.**
  `per_event` creates one envelope per `(event, rule, recipient)` and the
  unique key includes `event_id`. `per_root_cause` creates one envelope per
  `(root_correlation_id, rule, recipient)` and the unique key omits `event_id`;
  multiple events sharing the same root correlation produce a single envelope.

  AC traceability: directly satisfies AC2. Supports AC3 because repeated
  materialization attempts collide on the same grouping key instead of creating
  duplicate envelopes.

- **D6 — BINDING: Delivery worker behavior.**
  The delivery worker claims
  `notification_envelopes WHERE delivery_status = 'pending' AND attempts < max_attempts`
  using `FOR UPDATE SKIP LOCKED`. It calls the Discord adapter with the
  materialized envelope. Immediately before calling the adapter, it sets
  `delivery_status = 'delivered_in_flight'` so retries outside Discord's nonce
  window do not resend a message that may already have been submitted. On
  success, it sets `delivery_status = 'delivered'`.
  On definitive failure, it increments `attempts` and records failure detail;
  at `max_attempts`, it sets `delivery_status = 'failed'`. On ambiguous
  transport failure after Discord may have accepted the request, it leaves the
  row `delivered_in_flight` for operator reconciliation instead of retrying.

  AC traceability: directly satisfies AC4 by making envelope delivery the
  once-marked unit and by isolating retry/failure state from rule definitions.

- **D7 — BINDING: Discord idempotency.**
  Discord sends use Create Message `nonce` with `enforce_nonce = true`. The
  nonce is a deterministic Discord-safe token derived from `envelope_id`, not
  the raw UUID string: base32-encode the UUID bytes, strip padding, and use the
  first 25 characters. This satisfies Discord's 25-character nonce limit while
  preserving deterministic retry behavior. The nonce deduplicates duplicate
  retry sends within Discord's nonce window.

  AC traceability: supports AC4 by adding adapter-level idempotency in addition
  to database-level envelope claiming.

- **D8 — BINDING: Replay deduplication.**
  The materialize worker inserts envelopes with `INSERT ... ON CONFLICT DO
  NOTHING` against the D5 uniqueness rules. Replaying the same
  `notification_events.id` must not create duplicate envelopes.

  AC traceability: directly satisfies AC3. Supports AC2 by preserving the same
  grouping semantics during original processing and replay.

- **D9 — BINDING: Scheduler integration.**
  Materialization and delivery are scheduled handlers registered through the
  SLICE-004 `register_scheduler_handler` mechanism. Each `notification_events`
  insert enqueues a `deferred_effects` row with
  `effect_type = "notifications_materialize"` and
  `payload_json = {"event_id": <notification_events.id>}`. The
  `notifications_materialize` handler then enqueues one
  `notifications_deliver` effect per materialized envelope with
  `payload_json = {"envelope_id": <notification_envelopes.id>}` in the same
  database transaction as the envelope insert.

  AC traceability: supports AC4 by making materialization and delivery
  scheduled, claimable effects. Supports AC3 because replay uses the same
  materialization handler and D8 conflict behavior.

- **D10 — BINDING: Recipient resolution timing and envelope snapshot.**
  `recipients_json` is shaped as rule-owned JSON such as
  `{"kind": "discord_role", "chapter_id": UUID, "role_name": str}`. Recipient
  resolution happens at materialization time. The envelope stores the resolved
  `recipient_discord_id` as a string and a human-readable
  `recipient_display`. Destination channel resolution also happens at
  materialization time: `channel = "dm"` stores
  `destination_channel_id = NULL`, `channel = "designated_channel"` stores the
  rule `recipients_json.designated_channel_id`, and `channel = "thread"` is
  out of scope for SLICE-015. If recipient or destination resolution fails,
  the envelope is marked `skipped` with a reason.

  AC traceability: supports AC1 by persisting recipient configuration exactly
  as submitted. Supports AC2 by converting a matching rule into concrete
  per-recipient envelopes. Supports AC4 by snapshotting delivery recipients so
  retries do not depend on later rule or role changes.

- **D11 — BINDING: Template rendering timing and snapshot.**
  `template_json` is a Python-compatible template, for example
  `{"title": "Chapter ${chapter_id} transitioned to ${to_state}", "body": "..."}`.
  Rendering happens strictly at materialization time with
  `string.Template.substitute()`. Missing keys raise a render error and
  produce a skipped envelope with reason `template_missing_key`; unresolved
  `${missing_key}` text must not be shipped to users. The envelope stores fully
  rendered `rendered_title` and `rendered_body`. The delivery worker only
  transmits rendered strings. Rule edits after materialization do not affect
  already created envelopes.

  AC traceability: supports AC1 by persisting template configuration as
  submitted. Directly supports AC4 by ensuring delivery failures and retries do
  not mutate or reread rule definitions.

- **D12 — BINDING: Authority model and service actor grants.**
  Rule reads require `notification.read` at `scope_kind = 'global'`. Rule
  creates and updates require `notification.write` at `scope_kind = 'global'`.
  The service actor `notification-dispatcher` has `notification.read` and
  `notification.deliver` globally. These grants are seeded in the WU-029A
  migration.

  AC traceability: supports AC1 by governing rule create/update through the
  authority model. Supports AC4 by authorizing worker delivery without granting
  worker write access to mutate rule definitions.

- **D13 — BINDING: Worker actor identity.**
  Internal worker API calls use
  `X-Actor-Kind: service` and `X-Actor-Id: notification-dispatcher`.
  Materialization operations record this actor in audit payloads.

  AC traceability: supports AC4 by making scheduled worker actions attributable
  while keeping them separate from human rule edits. Supports AC3 by making
  replay materialization auditable under the same service identity.

- **D14 — BINDING: Anti-scope.**
  SLICE-015 does not implement notification acknowledgement or ack UI,
  recurring notification schedules, notification digests,
  compliance-driven notification templates, per-recipient preference
  management, email or SMS channels, notification archival, or cross-guild
  federation.

  AC traceability: supports AC1-AC4 by limiting the slice to configurable
  rules, materialization, replay deduplication, and scheduled Discord delivery.
  Excluded features must not be introduced to satisfy any SLICE-015 AC.

## Synthesis Notes

- Rule state is governed aggregate state. Delivery state is operational worker
  state. The two must remain physically separate so retries and failures cannot
  mutate rules.
- Materialization is the boundary where flexible rule configuration becomes a
  stable delivery contract: recipients and rendered content are snapshotted on
  envelopes.
- Idempotency is layered: envelope uniqueness prevents replay duplicates, row
  claiming prevents concurrent delivery duplication, and Discord nonce handling
  reduces duplicate sends during retry windows.
