# SLICE-015 Scope Risk: **LOW**

Rating: **LOW** — the proposal ships exactly the 4 ACs with named tests, observes D14 anti-scope verbatim, and the two routes beyond the ticket's/roadmap's enumerated endpoint list (`GET /{rule_id}`, `PATCH /{rule_id}`) are directly required by AC1's "Rule create/**update** persists ... with stale updates rejected by optimistic locking". Handler and contract extensions all trace back to D1–D13 binding decisions.

## SLICE-015 ACs (ticket)

1. Rule create/update persists grouping, recipients, channel, and actionable state exactly as submitted, with stale updates rejected by optimistic locking.
2. Per-root-cause rules emit one envelope per root correlation ID and per-event rules emit one per triggering audit entry.
3. Replaying the same persisted notification event does not materialize duplicate envelopes.
4. Scheduled delivery marks envelopes exactly once and Discord delivery failures do not mutate rule definitions.

## Findings

### 1. AC trace is complete and testable

| AC | Named tests | Source |
|---|---|---|
| AC1 | `test_create_rule_persists_trigger_recipients_channel_grouping`; `test_patch_rule_with_current_version_succeeds`; `test_patch_rule_stale_version_returns_412`; `test_list_rules_filters_by_scope`. | proposal §3 WU-029A tests, §7 AC1. |
| AC2 | `test_per_event_rule_emits_one_envelope_per_event`; `test_per_root_cause_rule_emits_one_envelope_per_root_correlation`; `test_multiple_events_same_root_correlation_one_envelope`; `test_different_root_correlations_separate_envelopes`. | proposal §3 WU-029B-materialize tests, §7 AC2. |
| AC3 | `test_replay_same_event_no_duplicate_envelopes`; `test_unique_index_prevents_duplicate_envelope_rows`; `test_materialize_is_idempotent_under_retry`. | proposal §3 WU-029B-materialize tests, §7 AC3. |
| AC4 | `test_delivery_worker_marks_envelope_delivered_exactly_once`; `test_discord_delivery_failure_does_not_mutate_rule`; `test_delivery_uses_envelope_id_as_discord_nonce`; `test_retry_attempts_counter_increments_on_failure`. | proposal §3 WU-029B-deliver + WU-029C tests, §7 AC4. |
| Invariants | `test_notification_dispatcher_service_grants_seeded`; `test_recipient_resolution_at_materialization_time`; `test_template_rendering_snapshot_isolates_from_later_rule_edits`. | proposal §3, §7 Invariants. |

No AC is missing a direct test path. AC1 and AC4 get the heaviest coverage because each spans multiple paths (create/patch/list for AC1; API claim/mark + Discord nonce + retry counter for AC4); that is correct for the ACs, not over-scope.

### 2. Anti-scope items from synthesis D14 are absent

| D14 item | Proposal coverage |
|---|---|
| Notification acknowledgements / ack UI | Not present. §2 "Out of scope" explicit. No ack state column on envelope; `delivery_status` literal stays 4-valued (`pending`/`delivered`/`skipped`/`failed`). |
| Recurring notification schedules | Not present. §2 explicit. Proposal uses SLICE-004 deferred effects, not a new recurring-scheduler primitive. `§5 Preserved → SLICE-004 scheduler → Do not: "Add recurring scheduler primitives"`. |
| Notification digests / batching / throttling / analytics | Not present. §2 explicit. One envelope per `(event/root, rule, recipient)`; no digest-collapse logic, no throttle counter, no analytics column. |
| Compliance-driven notification templates / separate template registry | Not present. §2 explicit. `template_json` is inline JSONB on the rule; no template-table reference, no `policy_versions` hookup. |
| Per-recipient preference management | Not present. §2 explicit. No `notification_preferences` table, no recipient-opt-out path. |
| Email/SMS channels | Not present. §2 explicit. `channel` literal stays 3-valued (`dm`/`thread`/`designated_channel`). |
| Notification archival | Not present. §2 explicit. No `archived_at` column, no archival endpoint, no retention policy. |
| Cross-guild federation | Not present. §2 explicit. All recipient/channel resolution is single-guild implicit. |
| Retrofitting existing workflows to emit new event types | Explicit in §2: "SLICE-015 tests may seed `notification_events` directly." No edits to SLICE-007/013/018/019 services to add `emit()` calls beyond the one D9-required hookpoint in `notification_events.py` itself. |
| Recursive causation walking | §2 explicit: "root cause grouping uses the event `correlation_id`." Matches research §2.5 and D5 — no recursive `causation_id` walk. |
| Discord thread creation | §2 explicit: "`channel='thread'` may use an existing target from event payload/rule data, but creating a new visible thread is not included." Matches research §7 Q5. |
| Backward-compatibility aliases or transitional routes | Explicit in §2. No shims, no dual paths. |

### 3. Deviations from the AI roadmap / ticket are explicitly noted and AC-driven

The ticket and AI roadmap (`ai roadmap.md:994-1068`) both enumerate **2 API routes** + **3 handlers**:

- `POST /api/v1/notification-rules -> NotificationRuleRead`
- `GET /api/v1/notification-rules -> list[NotificationRuleRead]`
- `handler materialize_notification_envelopes(event: NotificationEventRead) -> NotificationMaterializationResult`
- `scheduled handler deliver_notifications() -> NotificationDeliveryBatchRead`
- `handler deliver_notification(command: NotificationDeliveryCommand) -> NotificationDeliveryResult`

The proposal ships **4 API routes** + **2 scheduled/deferred handlers (API side)** + **1 Discord handler**.

**+2 API routes** vs ticket/roadmap:

- `GET /api/v1/notification-rules/{rule_id}` — read-by-id. Required as the precondition read for `If-Match`-based PATCH (mirrors every other governed aggregate: `chapters`, `members`, `policies`). Without it, AC1's "with stale updates rejected by optimistic locking" has no client surface to fetch the current version against.
- `PATCH /api/v1/notification-rules/{rule_id}` — rule update. **Mandatory for AC1**: the AC says "Rule create/**update** persists ... with stale updates rejected by optimistic locking." Optimistic locking without an update endpoint is unreachable. The AI roadmap's contract inline-sketch lists only POST+GET, but its AC2 (`"Updating a rule with current version succeeds; stale version returns 412 Precondition Failed"`) *also* requires PATCH — the roadmap's inline contract block is under-specified relative to its own ACs. The proposal reconciles this explicitly in §3 WU-029A endpoints.

Both additions are justified in §3 WU-029A "Endpoints" and traced in §7 AC1 ("StaleMutationError maps to 412 with stale_notification_rule_version"). Same pattern as SLICE-018's `/sync-failure` expansion — the ticket undercounts because the AC implies a route the inline contract sketch omits.

**Handler signature drift (materialize):**

Roadmap: `materialize_notification_envelopes(event: NotificationEventRead) -> NotificationMaterializationResult`.
Proposal: `materialize_notification_envelopes(effect: DeferredEffectRead) -> NotificationMaterializationResult`.

Driven by **D9 (BINDING)**: "Each `notification_events` insert enqueues a `deferred_effects` row with `handler = 'notifications_materialize'`". The scheduler substrate dispatches handlers through `DeferredEffectRead`, not directly by event. The proposal preserves the original roadmap semantic by exposing a replay-callable `materialize_event(db, event_id, worker_id)` (§3 WU-029B-materialize "Scheduler/deferred effect integration"), so tests and replay can invoke per-event as the roadmap implied. D9 binding trumps the roadmap sketch.

**Handler signature drift (deliver):**

Roadmap: `scheduled handler deliver_notifications() -> NotificationDeliveryBatchRead` plus `deliver_notification(command) -> NotificationDeliveryResult`.
Proposal: `deliver_notification(effect: DeferredEffectRead) -> NotificationDeliveryResult` on the scheduler side, plus a batch-tick helper `deliver_pending_notifications(db, worker_id, limit)`.

Same D9 binding: per-envelope deferred effects replace the roadmap's untyped "scheduled handler". The batch-shape `NotificationDeliveryBatchRead` from the roadmap is decomposed into per-envelope results because envelopes carry their own `delivery_status` literal (D4) — aggregating into a batch response is no longer the primary worker return shape. §3 WU-029B-deliver is explicit: "The handler accepts either one envelope id from the effect payload or, for batch tests, calls `deliver_pending_notifications(db, worker_id, limit)`."

**Contract drift from AI roadmap** — `NotificationEnvelopeRead`:

Roadmap: `NotificationEnvelopeRead(id, correlation_id, recipient_ids, channel, actionable)`.
Proposal: a 26-column persisted envelope with `rule_id`, `rule_version`, `source_event_id`, `root_correlation_id`, `causation_id`, `grouping`, `recipient_key`, `recipient_discord_id`, `recipient_display`, `destination_channel_id`, `template_snapshot_json`, `rendered_title`, `rendered_body`, `delivery_status`, `claimed_by`, `claimed_at`, `lease_until`, `attempts`, `max_attempts`, `last_error_json`, `discord_message_id`, `delivered_at`, plus timestamps.

Every added field backs a binding decision:

| Field(s) | D-backing |
|---|---|
| `rule_id`, `rule_version` | D1 (rule aggregate + version from `aggregate_heads`); D4 snapshot |
| `source_event_id`, `root_correlation_id`, `causation_id`, `grouping` | D4+D5 (per-event vs per-root unique keys) |
| `recipient_key`, `recipient_discord_id`, `recipient_display` | D10 (recipient snapshot at materialization) |
| `destination_channel_id`, `channel` | D4 envelope shape (delivery reads envelope only) |
| `template_snapshot_json`, `rendered_title`, `rendered_body` | D11 (template snapshot at materialization; delivery reads only envelope) |
| `delivery_status`, `claimed_by`, `claimed_at`, `lease_until`, `attempts`, `max_attempts`, `last_error_json` | D6 (claim/lease/retry on envelope, not rule); D4 literal |
| `discord_message_id`, `delivered_at` | D6 success-transition fields; D7 idempotency trace |

The roadmap's `recipient_ids: list` collapses multiple recipients into one envelope; the proposal instead emits **one envelope per recipient**. D10 pins this: "The envelope stores the resolved `recipient_discord_id` as a string and a human-readable `recipient_display`." Binding decision trumps the roadmap sketch.

**Contract drift from AI roadmap** — `NotificationDeliveryResult`:

Roadmap: `NotificationDeliveryResult(envelope_id, delivered_at)`.
Proposal: `NotificationDeliveryResult(envelope_id, delivered_at, discord_message_id)`.

Extra `discord_message_id` is consumed by the D6 success-path write (`mark_notification_envelope_delivered`) and traced by the AC4 test `test_delivery_uses_envelope_id_as_discord_nonce` (which needs a Discord message id to assert the nonce round-trip). Minimal, AC-driven.

**Contract additions not in roadmap, required by ticket ACs or binding decisions:**

| New contract | Backing |
|---|---|
| `NotificationTrigger(event_type, payload_filters?)` | D2 BINDING (trigger shape) |
| `NotificationRulePatch` | AC1 "update" (optimistic locking needs patch body) |
| `NotificationRuleListRead` | AI roadmap's `list[NotificationRuleRead]` reified; query filters match `test_list_rules_filters_by_scope` |
| `NotificationChannel` / `NotificationGrouping` / `NotificationDeliveryStatus` literals | D1 / D4 / D5 CHECK-constraint literal vocab |
| `NotificationMaterializationResult`, `NotificationDeliveryBatchRead`, `NotificationDeliveryCommand`, `NotificationDeliveryError` | Roadmap listed these as return types or handler parameters; proposal formalizes |
| Typed errors (rule-not-found, empty-patch, unsupported-trigger, delivery-failure, stale-rule-version) | Required by AC1 (412 shape), AC4 (failure isolation), and existing error-mapping patterns |

Every contract addition ties back to a D-decision or an AC test. No shadow contracts.

### 4. Migration scope: `notification_rules` + `notification_envelopes` in one revision

The WU-029A migration creates **two** tables, not one. The ticket's WU-029A code boundary names `migrations/versions/wu-029a_notification_rules.py` (singular `notification_rules`), but §3 WU-029A migration explicitly states: "The same migration also creates `notification_envelopes` because WU-029B needs the table and deduplication indexes". Rationale:

- WU-029B-materialize and WU-029B-deliver do not own migrations per the ticket's code-boundary column (both list only services/tasks/tests files, no `migrations/versions/...`). So the envelope table has no other home.
- Bundling envelopes into the WU-029A migration follows the SLICE-018 pattern (`wu-033_roster_lifecycle.py` added both `roster_entries` lifecycle columns and `roster_transitions`).
- The proposal renames the migration from `wu-029a_notification_rules.py` to `wu-029a_notifications.py` (§3 WU-029A migration), which is cosmetic.

Infra glue that follows D-decision necessity, not scope expansion.

### 5. In scope features that extend the ticket/roadmap

| Feature | Status | Backing |
|---|---|---|
| `enabled` column + `ix_notification_rules__enabled` partial index | In scope | D1 BINDING; research §2.1 proposed `enabled BOOLEAN NOT NULL DEFAULT TRUE` |
| `GIN` index on `trigger_json` | In scope | Research §3 proposed; matches D2 "flexible JSONB"; used by `list_enabled_rules_for_event` scan |
| `ix_notification_rules__scope` composite index | In scope | D3 scope-matching scan target |
| `ix_notification_envelopes__pending_delivery` partial index | In scope | D6 claim path (`delivery_status = 'pending'`) |
| Two partial unique indexes (`per_event` vs `per_root_cause`) | In scope | D5 BINDING; enforces grouping key at DB layer |
| `notification-dispatcher` service-actor seed with `notification.read` + `notification.deliver` | In scope | D12 BINDING; follows `wu-012_trust.py:61` and `wu-019_chapter_lifecycle.py:107` guarded-insert pattern |
| `payload_filters` validator allowing exact dotted name or suffix `.*` pattern | In scope | D2 BINDING |
| `string.Template.safe_substitute` rendering with flattened `payload_<key>` context | In scope | D11 BINDING; §4 tradeoff justifies keeping template language minimal |
| Recipient kind `discord_users` / `discord_user` fully resolved; `discord_role` accepted as JSON but materializes as skipped | In scope | D10 BINDING; §4 tradeoff 5 justifies "no fake role resolver" |
| `channel='thread'` sends to existing thread ID, never creates a thread | In scope | §2 out of scope for thread creation; research §7 Q5 |

Each in-scope extension maps to a D-decision or the named AC tests. No items here are silently expanded.

### 6. Discord adapter scope stays inside WU-029C boundaries

The WU-029C adapter does exactly one materialized envelope delivery and reads only the envelope snapshot (§3 WU-029C adapter responsibilities). It does **not**:

- Read or mutate notification rules — §3 "Do not fetch or mutate notification rules."
- Create Discord threads — §3 `channel = "thread"`: "Do not create a thread in this slice."
- Call rule APIs on failure — §3 "Raise `NotificationDeliveryError` on Discord exceptions so WU-029B can mark failure and increment attempts."
- Read the current rule to reconstruct actionable components — §3 "If no component snapshot exists, send a normal informational message rather than reading the current rule." This is a D11-preserving narrowing.
- Persist Discord-side state — no writes to Discord-side DB; state transitions stay in the API layer.

### 7. No scope leakage into downstream slices

| Downstream | Would depend on | Present in proposal? |
|---|---|---|
| Notification ack UI / SLICE post-0.5 | ack columns, ack endpoint, ack UI | **No.** D14 explicit; `delivery_status` stays 4-valued. |
| Notification digest / analytics slice | digest aggregation table, analytics projection | **No.** D14 explicit; one-envelope-per-match only. |
| Per-recipient preferences slice | `notification_preferences` table, opt-out endpoint | **No.** D14 explicit. |
| Email/SMS channel slice | channel literal expansion, platform adapter | **No.** `NotificationChannel` literal stays 3-valued. |
| Recurring-schedule slice | recurring-job primitive on `scheduled_jobs` | **No.** Proposal uses SLICE-004 one-shot `deferred_effects`; §5 preserved: "Do not: Add recurring scheduler primitives." |
| Discord role recipient resolution slice | role-membership snapshot, role → Discord user resolver | **No.** `discord_role` recipient accepted but materializes as skipped; no role resolver code ships. |
| Notification archival slice | `archived_at` column, archival endpoint | **No.** D14 explicit. |
| Cross-guild federation slice | guild_id FK on rules/envelopes | **No.** Single-guild implicit; no `guild_id` column. |
| Retrofit of existing producers (SLICE-007/013/018/019) to `emit()` | `emit()` calls in those services | **No.** §2 explicit; tests seed `notification_events` directly. Only hookpoint is `notification_events.py:27` where `emit()` itself enqueues the deferred effect. |
| Recursive causation walk | `causation_id` DAG traversal | **No.** §2 explicit; `root_correlation_id = correlation_id`. |

### 8. Minor observations (not severity escalations)

| Observation | Verdict |
|---|---|
| Discord adapter tests after the first are described but not formally named (§3 WU-029C tests: "adapter success returns ..."; "adapter failure raises ..."; "DM and designated-channel routing use the envelope snapshot"). | **Minor naming weakness.** Test coverage intent is clear; implementation should bind explicit test names for each. Not a scope risk because AC4 is directly covered by the formally named `test_delivery_uses_envelope_id_as_discord_nonce`. |
| Proposal's Discord adapter contract mirrors API contract shape (`services/discord/app/contracts/notifications.py`). | **Acceptable boundary crossing.** Discord service already has its own per-feature contract modules (e.g., roster, application submission); this mirrors that pattern. Not a new cross-service coupling, just a serialization-compatible mirror. |
| `NotificationRuleRead` contract adds `version`, `created_at`, `updated_at` fields beyond the roadmap sketch. | **Standard.** Every governed aggregate Read contract in the repo exposes these (`chapters`, `members`, `policies`). Required by AC1's If-Match flow and audit trail. |
| Proposal names migration `wu-029a_notifications.py` vs ticket's `wu-029a_notification_rules.py`. | **Cosmetic.** The migration adds both `notification_rules` and `notification_envelopes`, so the shortened name is more accurate. Alembic revision identifier stays `wu_029a_notifications`. |
| Root correlation grouping naming: proposal uses `root_correlation_id` as a column name, synthesis D4 uses it as a concept. | **Naming consistency.** Research §2.5 warned against introducing a second ID if recursive causation is not implemented, but proposal is explicit in §2 that this column is set to `notification_events.correlation_id` directly. No semantic drift. |
| `NotificationEventRead` consumed by materialization: the proposal does not add a notification-event `processing_status`/`claimed_at`/`attempts` column set on `notification_events`. Research §2.4 flagged these as potentially needed if the event table was used as the queue. | **Correctly avoided.** D9 binding routes claimability through `deferred_effects` instead, so `notification_events` stays immutable (matches the SLICE-002 "durable source" invariant). Proposal §5 preserves this: "Do not: Add rule state to `notification_events`. Do not: Add delivery status to `notification_events`." |

## Summary table

| Risk category | Severity | Notes |
|---|---|---|
| Bundles downstream work (ack / digest / preferences / email / archival / recurring / cross-guild / retrofit / recursive causation / role resolution) | None | All explicitly excluded per D14 and §2 anti-scope. |
| Missing AC test path | None | All 4 ACs have direct tests per §7; 3 invariants also have explicit tests. |
| Silent deviation from AI roadmap / ticket | None | +2 routes (`GET /{id}`, `PATCH /{id}`) required by AC1 "create/update" + optimistic locking; handler signature shift to `DeferredEffectRead` required by D9; envelope contract expansion backed field-by-field by D1/D4/D5/D6/D7/D10/D11; all deviations explicit in §3 and §6 Resolved Decisions. |
| Over-scoped Discord adapter (rule reads, thread creation, DB writes, ID persistence) | None | §3 WU-029C explicitly forbids rule reads, thread creation, direct DB writes; failures raise typed error only. |
| Over-scoped migration (envelope table bundled with rules) | None | No other WU owns a migration; parallels SLICE-018's `roster_transitions` bundling in `wu-033_roster_lifecycle.py`. Migration name renamed `wu-029a_notifications.py` to reflect both tables. |
| Over-scoped permission model | None | Only `notification.read` / `notification.write` / `notification.deliver` introduced; dispatcher seeded with read+deliver, never write (D12). |
| Unnamed Discord adapter tests beyond the first | Low | §3 WU-029C lists three additional test intents without explicit names; the AC4 nonce test is formally named. Implementation should bind names. |

## What LOW requires (already met)

1. Each AC has at least one direct test — **yes** (§7).
2. Anti-scope items (D14) absent from proposal body — **yes** (§2 + table above).
3. Any deviation from the AI roadmap / ticket endpoint list is explicitly noted with rationale — **yes** (`GET /{id}` and `PATCH /{id}` justified by AC1; handler param change justified by D9; contract expansion justified field-by-field by D1/D4-D11).
4. Migration bundling is the minimum needed for dependent WUs — **yes** (envelope table has no other owning WU; parallels SLICE-018).
5. No recurring-scheduler primitive shipped in this slice — **yes** (§2 explicit; §5 preserved explicit).
6. No retrofit of existing producers / recursive causation walk / role resolver / thread creation / ack / digest / preferences — **yes** (§2 + §7 table).
7. Dispatcher seeded with minimum permissions; never `notification.write` — **yes** (D12 + §3 migration seed).
8. One envelope per `(event/root, rule, recipient)` emitted at materialization time, not delivery time — **yes** (D4/D5/D10).

No scope reductions or additions are required. The proposal is right-sized for the 4 ACs, and every expansion beyond the ticket's and AI roadmap's minimal contract sketches has an explicit D-decision or AC-derived rationale.
