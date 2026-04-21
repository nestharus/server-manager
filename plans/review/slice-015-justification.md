# SLICE-015 Phase 5+6 — Opus Justification Review (PR #50)

Reviewed: 2026-04-21
PR: `feat/slice-015-notifications` (#50)
Branch head: `a5fa811` (against `origin/main` = `e335f5a`)
Inputs: `.pipeline/proposal.md` (Revision 2), `.pipeline/synthesis.md` (D1–D14),
`product-strategy/tickets/SLICE-015.md` (AC1–AC4), `plans/risk/slice-015-audit.md`
(LOW; A1–A6 gates), `plans/risk/slice-015-scope.md` (LOW),
`plans/risk/slice-015-shortcut.md` (LOW; S1–S15),
`git diff origin/main..HEAD`.

## 1. Verdict

**`LOW_CONCERN`** — no HIGH findings. Every non-trivial file traces to an
AC / D-decision / prior-slice / revision rationale. The findings below are
specification drifts and hygiene items that do not block merge; three should
be absorbed before downstream notification slices open.

No scope creep blocks merge. Every D14 anti-scope item (ack UI, recurring
schedules, digests, preferences, email/SMS, archival, cross-guild, template
registry, recursive causation, thread creation, retrofit of existing
producers, role resolver) is absent from the diff. No `TODO`,
`NotImplementedError`, `...`-only bodies, or placeholder `pass` exist in
production code. The two routes beyond the ticket's sketch
(`GET /{rule_id}`, `PATCH /{rule_id}`) are required by AC1's "Rule
create/**update** persists ... with stale updates rejected by optimistic
locking" and were explicitly blessed by `slice-015-scope.md:3,56-60`.

## 2. Findings

| # | Severity | File:Line | Description | Proposed fix / justification |
|---|---|---|---|---|
| F1 | LOW-MEDIUM | `services/api/app/services/deferred_effects.py:70-82` | The service wrapper `enqueue_effect(db, request)` was **not** extended to accept `connection: Connection \| None = None`. Audit gate **A2** (`plans/risk/slice-015-audit.md:409-416`) and proposal §WU-029B-materialize (`.pipeline/proposal.md:422-426`) explicitly required this extension: "If the existing `deferred_effects.enqueue_effect()` service function cannot accept a shared connection, extend it to accept `connection: Connection \| None = None`; when supplied, it must insert through that connection and must not open or commit a separate transaction." The implementation works around the gap by importing the repository-level `enqueue_effect` directly in `notification_events.py:14` and `notifications_materialize.py:20`. Atomicity is preserved — both callers pass an active `Connection` to the repository function, which already accepts it — but the A2 gate was literally to evolve the **service** surface. | Either (a) extend `services/api/app/services/deferred_effects.py::enqueue_effect` with optional `connection`, retain the default-db path, and migrate notification callers to the service wrapper; or (b) amend audit A2 to note that the repository-level function is the substrate and the service wrapper stays db-only. The test `test_emit_is_atomic_when_called_with_connection` at `services/api/tests/test_notification_materialization.py:310-349` does prove rollback atomicity through the repository path. **Not merge-blocking** because the atomicity invariant (M2) is satisfied. |
| F2 | LOW-MEDIUM | `services/api/app/repositories/notifications.py:310-341` `claim_notification_envelope` | The envelope claim is a bespoke CTE using `FOR UPDATE SKIP LOCKED`, not a call to `claim_due_rows(..., claim_status=None)`. Proposal §WU-029A-repository (`.pipeline/proposal.md:272-285`) is explicit: "Envelope claiming must use `SELECT ... FOR UPDATE SKIP LOCKED` semantics and **reuse the SLICE-004 claim helper by extending `_claim.py::claim_due_rows()` to accept an optional `claim_status`**." Shortcut S4 (`plans/risk/slice-015-shortcut.md:75-93`) reinforces this with a pin: "one-envelope delivery handler passes `batch_size=1` with an `id = %s AND ...` ready predicate. ... no envelope-specific claim SQL." The `_claim.py` helper **was** correctly extended per A1 gate and is covered by `test_claim_due_rows_with_claim_status_none_does_not_set_status` at `services/api/tests/test_notification_delivery_worker.py:382`, but nothing in the envelope claim path actually invokes it. Semantically the bespoke CTE is equivalent (`delivery_status='pending' AND attempts < max_attempts AND (claimed_by IS NULL OR lease_until < now)`), so no behavior bug, but the proposal's substrate-reuse contract is broken. | Replace `claim_notification_envelope` with `claim_due_rows(connection, table="notification_envelopes", primary_key="id", worker_id=..., batch_size=1, ..., ready_predicate="id = %s AND delivery_status = 'pending' AND attempts < max_attempts AND (claimed_by IS NULL OR lease_until < %s)", predicate_params=(envelope_id, now), order_by="id", claim_status=None)`. **Not merge-blocking** because the helper is dead-equivalent and the generalized `_claim_status=None` behavior is tested, but leaving two parallel skip-locked claim paths invites drift. |
| F3 | LOW | `services/api/app/services/notifications.py:105,182` action_type names | Proposal §WU-029A-service (`.pipeline/proposal.md:315-316`) pins: "create action type: `notification_rule.create`; patch action type: `notification_rule.patch`." The create path correctly uses `action_type="notification_rule.create"` at line 105, but the patch path uses `action_type="notification_rule.update"` at line 182. The corresponding `StateChangeDraft` at line 169 uses `change_type="notification_rule.updated"` (past tense) which mirrors the `chapters`/`members` change-type convention, so the ambiguity is really between "updated" (projection change) and "patch" (mutation action). | Rename `action_type="notification_rule.update"` → `"notification_rule.patch"` at `services/api/app/services/notifications.py:182`. Trivial one-line fix; consistent with the proposal's explicit pin and with the HTTP verb (`PATCH`). **Not merge-blocking**; audit payload shape is unaffected. |
| F4 | LOW | `services/api/app/services/notification_events.py:36` `actor: ActorIdentity,  # noqa: ARG001` | The `emit()` signature per M2/Rev 2 is `emit(db, *, event, actor, connection=None, payload_allowlist=None)`, but `actor` is never read inside the function; it's silenced with `# noqa: ARG001 - reserved for worker-attribution parity`. The repo guidance explicitly says: "Don't add ... validation for scenarios that can't happen. Trust internal code and framework guarantees." And: "Avoid backwards-compatibility hacks like renaming unused _vars ... If you are certain that something is unused, you can delete it completely." The reason `actor` is parameterized is D13's "Materialization operations record this actor in audit payloads" — but that happens at the `notifications_materialize` handler boundary through `use_audit_context(_reconstruct_audit_context(...))` (see `services/api/app/services/deferred_effects.py:178`), not inside `emit()` itself. The `notification_events` audit actor is already captured through the caller's audit context. | Either (a) drop the `actor` parameter from `emit()` since the audit-context actor is the one persisted, or (b) actually use it when writing an audit/activity row. The Rev-2 `emit()` signature ships verbatim from the proposal, so (a) requires a proposal amendment. **Not merge-blocking**, and Rev 2 reserves the parameter by design, but the `# noqa: ARG001 - reserved for worker-attribution parity` comment betrays a designed-for-hypothetical shape that the repo style discourages. |
| F5 | LOW | `services/api/app/services/notifications_materialize.py:224` `"max_attempts": 3` hardcoded | Materialization inserts envelope rows with a hardcoded `max_attempts=3` literal rather than `DEFAULT_MAX_ATTEMPTS` (imported at line 26 and used at line 251 for the `enqueue_effect` call). The DB column default is `DEFAULT 3` (proposal §WU-029A-migration `.pipeline/proposal.md:151`) and `DEFAULT_MAX_ATTEMPTS=3` in `services/api/app/services/scheduler.py:29`, so the values agree today. Shortcut S15 (`plans/risk/slice-015-shortcut.md:280-289`) correctly says notifications reuse the scheduler default. Since the row-insert passes the value explicitly rather than relying on the DB DEFAULT, the literal is a subtle redundancy: if operators tune `DEFAULT_MAX_ATTEMPTS` later, the envelope insert will silently stay at 3. | Replace line 224 with `"max_attempts": DEFAULT_MAX_ATTEMPTS,` to keep the envelope retry budget coupled to the scheduler default, or remove the explicit `max_attempts` key and rely on the DB DEFAULT. **Not merge-blocking**; it is a coupling/magic-value hygiene item. |
| F6 | LOW | `services/api/app/contracts/scheduler.py` `DegradedStateSummaryRead.stuck_in_flight_envelopes: int = Field(default=0, ge=0)` | Audit M3 (resolved in Rev 2) extended `query_degraded_state_summary` to include `stuck_in_flight_envelopes` **for the `notifications` subsystem** (proposal §WU-029B-deliver/"Operator visibility" `.pipeline/proposal.md:641-656`; audit §M3 `plans/risk/slice-015-audit.md:91-113`). The contract field was added as a universal column on `DegradedStateSummaryRead` with `default=0`, so every subsystem row (scheduler, deferred-effects, notifications) now carries the field. It is zero for non-notification subsystems and non-zero only for `notifications`. This is a mild premature abstraction: the field is not subsystem-specific in the contract, which invites future subsystems to overload a notification-shaped counter. | Either (a) accept the universal default as the minimum viable extension to the existing summary shape (keeps the contract shape flat and consistent with `pending_effect_count` / `scheduled_job_count`), or (b) move the counter into a subsystem-keyed map (`stuck_in_flight_counts: dict[str, int]`) if operators expect more subsystems to contribute. **Not merge-blocking**; option (a) is defensible and lighter. |
| F7 | LOW | Test-name drift from proposal | The proposal enumerates exact test names in §WU-029A tests, §WU-029B-materialize tests, §WU-029B-deliver tests, §WU-029C tests, and §7 AC-trace + Invariants. Several committed tests diverge (impl-side name on left; proposal spec on right): `test_create_rule_persists_all_fields` vs `test_create_rule_persists_trigger_recipients_channel_grouping`; `test_notification_dispatcher_grants_seeded_without_notification_write` vs `test_notification_dispatcher_service_grants_seeded`; `test_multiple_events_same_root_correlation_produce_one_envelope` vs `test_multiple_events_same_root_correlation_one_envelope`; `test_different_root_correlations_produce_separate_envelopes` vs `test_different_root_correlations_separate_envelopes`; `test_replay_same_event_does_not_create_duplicate_envelopes` vs `test_replay_same_event_no_duplicate_envelopes`; `test_materialize_skips_rules_when_enabled_false` vs `test_disabled_rule_does_not_materialize` (A4 gate); `test_materialize_skips_when_template_missing_key` vs `test_materialize_skips_when_template_has_missing_key`; `test_delivery_uses_envelope_id_as_discord_nonce` (scope §1) vs actual `test_delivery_uses_deterministic_nonce_derived_from_envelope_id` (matches proposal §WU-029C). The A5/A6 gates are satisfied by test content even though name drifts (impl's `test_notification_dispatcher_grants_seeded_without_notification_write` pins the exclusion explicitly, per A5 intent). | Rename tests to match proposal spec in a follow-up housekeeping commit, OR amend proposal test-name list to match committed names. **Not merge-blocking** — behaviors under test are correct, and the impl-side name for the dispatcher grants test is arguably clearer than the proposal's. |
| F8 | LOW | Missing tests from proposal spec | Three test names explicitly enumerated in proposal (§WU-029B-materialize tests and §AC3 trace, §WU-029B-deliver tests and §AC4 trace) are absent from the committed suites: (a) `test_unique_index_prevents_duplicate_envelope_rows` — partially covered by `test_replay_same_event_does_not_create_duplicate_envelopes` (same on-conflict path) but the name-pinned "DB-layer unique-index enforcement" probe is absent. (b) `test_designated_channel_destination_snapshotted_at_materialization_time` — recipient snapshot is covered by `test_recipient_resolution_at_materialization_time` and destination/template-snapshot by `test_template_rendering_snapshot_isolates_from_later_rule_edits`, but no test asserts the `destination_channel_id` write specifically. (c) `test_delivery_worker_skips_delivered_in_flight_without_resend` — `test_delivery_worker_marks_envelope_delivered_exactly_once` covers the exactly-once semantic through the claim-once path but does not directly probe the post-`delivered_in_flight` short-circuit at `services/api/app/services/notifications_delivery.py:69-76`. | Add the three tests. (a) asserts an attempted direct `INSERT` with the same `(source_event_id, rule_id, recipient_key, grouping='per_event')` raises `UniqueViolation` at the DB layer; (b) asserts `notification_envelopes.destination_channel_id = rule.recipients_json['designated_channel_id']` after materialization; (c) primes an envelope to `delivered_in_flight` and asserts the second worker pass returns `noop=True, delivery_status="delivered_in_flight"` with the `delivery_port.deliver` **not** called. **Not merge-blocking** — the underlying behaviors are all exercised indirectly by the committed suite, and AC3/AC4 are covered. |
| F9 | LOW | `services/discord/tests/test_notifications.py` | Only one test is committed: `test_delivery_uses_deterministic_nonce_derived_from_envelope_id`. Proposal §WU-029C tests (`.pipeline/proposal.md:754-761`) enumerates three additional intents (admittedly unnamed): "adapter success returns envelope id, Discord message id, and delivered time", "adapter failure raises a typed delivery error without calling any rule API", "DM and designated-channel routing use the envelope snapshot". Scope §8 (`plans/risk/slice-015-scope.md:171`) already flagged this as a "Minor naming weakness. Test coverage intent is clear; implementation should bind explicit test names for each." The committed Discord suite therefore ships only the single nonce probe and relies on API-side `test_discord_delivery_failure_does_not_mutate_rule` for failure isolation (from the port's perspective, not the adapter's Discord-exception taxonomy). | Add explicit Discord-side tests: `test_adapter_success_returns_message_id_and_delivered_time`, `test_adapter_failure_raises_notification_delivery_error_without_reading_rule_api`, `test_adapter_routes_dm_to_recipient_discord_id_from_envelope`, `test_adapter_routes_designated_channel_to_envelope_destination`. Each can be a small mock-bot assertion. **Not merge-blocking** — the nonce test plus the API-side fake-port tests cover AC4 end-to-end, but Discord-specific failure taxonomy (definitive vs. ambiguous) is important enough to probe directly. |
| F10 | LOW | `.pipeline/implementation.md:118-119` note: "Existing dirty worktree files under `.pipeline/` and `plans/risk/` were left untouched aside from this implementation report." | The implementation report acknowledges a dirty worktree at the time of the commit, but the committed tree appears clean at `a5fa811`. The note is now stale and potentially confusing for reviewers reading the commit after-the-fact. | Drop or rewrite the note in a doc-only follow-up. **Not merge-blocking**. |

No MEDIUM or HIGH findings.

## 3. Trace matrix

Every non-trivial file → AC / D-decision / prior-slice / Revision-2 rationale.

### Migration

| File | Justification |
|---|---|
| `migrations/versions/wu-029a_notifications.py` | `down_revision = "wu_012_trust"` — proposal §WU-029A-migration line 98 + audit F12 (`plans/risk/slice-015-audit.md:316-329`) confirms `wu_012_trust` is current HEAD. `notification_rules` shape — **D1** (synthesis.md:22-36) + proposal lines 100-126. `notification_envelopes` shape — **D4/D5/D6** + proposal lines 128-164. Two partial unique indexes (`per_event`, `per_root_cause`) — **D5 BINDING** (synthesis.md:79-87) + proposal lines 167-174 + audit F1. `ix_notification_envelopes__pending_delivery` — **D6** claim predicate. GIN on `trigger_json` — **D2** flexible JSONB + shortcut S10. `notification-dispatcher` service-actor seed with `["notification.read","notification.deliver"]` — **D12 BINDING** (synthesis.md:168-177) + proposal lines 184-192 + audit F9 + A5 gate. Idempotent `WHERE NOT EXISTS` pattern follows `wu-012_trust.py:61-97` and `wu-019_chapter_lifecycle.py:107`. |

### API contracts

| File | Justification |
|---|---|
| `services/api/app/contracts/notifications.py` `NotificationChannel`/`NotificationGrouping`/`NotificationDeliveryStatus` literals | **D1/D4/D5** CHECK-constraint literal vocab + proposal lines 200-202. |
| `NotificationTrigger` with dotted-name/`.*` validator | **D2 BINDING** (synthesis.md:38-46) + proposal lines 206-209. |
| `NotificationRuleCreate`/`RulePatch`/`RuleRead`/`RuleListRead` with `trigger`/`recipients`/`template` aliases | **D1 BINDING** + **AC1** + proposal lines 210-226. `RulePatch` `model_fields_set` non-empty check satisfies proposal line 222 "at least one field must be present." Audit **M4** pin: `NotificationRuleCreate.model_dump().keys()` is exactly the 9-field allowlist (proposal lines 240-244). |
| `NotificationEnvelopeRead` (27 fields) | Every field traces to a D-decision: `rule_id`/`rule_version` — D1 snapshot; `source_event_id`/`root_correlation_id`/`causation_id`/`grouping` — D4/D5; `recipient_key`/`recipient_discord_id`/`recipient_display` — D10; `destination_channel_id`/`channel` — D4; `template_snapshot_json`/`rendered_title`/`rendered_body` — D11; `delivery_status`/`claimed_by`/`claimed_at`/`lease_until`/`attempts`/`max_attempts`/`last_error_json` — D6; `discord_message_id`/`delivered_at` — D6+D7. Scope §3 per-field mapping (`plans/risk/slice-015-scope.md:83-94`) pins this. |
| `NotificationMaterializationResult`, `NotificationDeliveryCommand`, `NotificationDeliveryResult` | Proposal §WU-029A-contracts + D6/D7 delivery port shape + scope §3 "Contract drift from AI roadmap." `NotificationDeliveryResult` `noop: bool` field backs D6 no-op return from delivered/delivered-in-flight short-circuit. |
| Typed errors (`NotificationRuleNotFoundError`, `NotificationRulePatchEmptyError`, `UnsupportedNotificationTriggerError`, `NotificationRuleVersionError`, `TemplateRenderError`, `NotificationDeliveryError`, `AmbiguousNotificationDeliveryError`) | Proposal §WU-029A-contracts lines 233-236 + AC4 failure isolation (D6). |

### API repositories

| File | Justification |
|---|---|
| `services/api/app/repositories/notifications.py` `_RULE_SELECT` joining `aggregate_heads` | **D1** version resolution pattern from `services/api/app/repositories/members.py:10` (proposal line 259). |
| `insert_notification_rule`/`update_notification_rule`/`fetch_notification_rule`/`fetch_notification_rule_for_update`/`list_notification_rules`/`list_enabled_rules_for_event` | Proposal §WU-029A-repository lines 251-257. `list_enabled_rules_for_event` filters `enabled = TRUE` explicitly at line 181, satisfying **A4 gate** (audit `plans/risk/slice-015-audit.md:424-426`). |
| `insert_notification_envelope_on_conflict_do_nothing` | **D8 BINDING** (synthesis.md:116-123) + proposal lines 264 + shortcut S10. |
| `fetch_notification_envelope` | Delivery service no-op short-circuit path at `services/api/app/services/notifications_delivery.py:65`. |
| `claim_notification_envelope` | **D6** skip-locked lease semantics. *See F2 — bespoke CTE instead of `claim_due_rows(claim_status=None)` reuse.* |
| `mark_envelope_delivered_in_flight`/`mark_envelope_delivered`/`mark_envelope_delivery_failure`/`mark_envelope_ambiguous_failure` | **D6** delivery-state transitions (synthesis.md:89-103) + proposal §WU-029B-deliver flow lines 599-628. Each function scopes its UPDATE to `claimed_by = worker_id` to preserve the lease contract. |
| `services/api/app/repositories/_claim.py::claim_due_rows(..., claim_status="claimed")` | **A1 gate** satisfied (`plans/risk/slice-015-audit.md:401-407`): when `claim_status is None`, `status_assignment = sql.SQL("")` is substituted and the params tuple drops the placeholder entirely (lines 25-27, 55-66). Covered by `test_claim_due_rows_with_claim_status_none_does_not_set_status` (`services/api/tests/test_notification_delivery_worker.py:382`). Existing scheduler and deferred-effect callers keep the default `"claimed"`. |
| `services/api/app/repositories/deferred_effects.py::query_degraded_state_summary` | Extended per **M3**/A-gate to compute `stuck_in_flight_envelopes` via CTE (`notification_envelopes WHERE delivery_status='delivered_in_flight' AND claimed_at < now() - INTERVAL '1 hour'`), proposal lines 641-656 + audit §M3. *See F6 for the universal-field placement.* |

### API services

| File | Justification |
|---|---|
| `services/api/app/services/notifications.py::create_notification_rule` | **AC1** + **D1** `mutate_entity(expected_version=0)` + **D12** scope; proposal §WU-029A-service lines 305-321. `payload_allowlist = RULE_PAYLOAD_FIELDS` (the pinned 9-field frozenset) satisfies **M4** (audit `plans/risk/slice-015-audit.md:115-135`). `action_type="notification_rule.create"` ✅. |
| `services/api/app/services/notifications.py::read_notification_rule`/`list_notification_rules`/`patch_notification_rule` | **AC1** + **D1** ETag/OCC semantics + **D12** scope; proposal §WU-029A-service + Endpoints. *See F3 — `action_type="notification_rule.update"` drifts from proposal's pin of `.patch`.* |
| `services/api/app/services/notification_events.py::emit` | Rev-2 keyword-only `emit(db, *, event, actor, connection=None, payload_allowlist=None)` signature per **M2** (proposal lines 394-409, audit §M2 `plans/risk/slice-015-audit.md:50-90`). Inserts the `notification_events` row and the `notifications_materialize` deferred effect through the shared connection atomically. *See F4 — unused `actor` parameter marked `noqa: ARG001`.* |
| `services/api/app/services/notifications_materialize.py::materialize_event` | **D4/D5/D8/D9/D10/D11**. Flow matches proposal §WU-029B-materialize-service lines 442-473 exactly: load event, list enabled rules, apply trigger matching (exact + `.*` suffix), apply payload filters, resolve recipients at materialization, resolve destination at materialization, render template strictly, insert envelope `ON CONFLICT DO NOTHING`, enqueue per-envelope delivery effect through the same connection. `_recipient_selector_key` uses `hashlib.sha256(json.dumps(recipients, sort_keys=True, separators=(",",":"))).hexdigest()[:16]`, satisfying **A3 gate** + shortcut S13. `_resolve_destination` skips thread with `thread_channel_out_of_scope` (D10 + §2 out-of-scope); designated-channel with no id skips with `destination_missing`. Template rendering uses `Template(...).substitute()` per D11; missing keys raise `TemplateRenderError` mapped to `template_missing_key`. Disabled rules filtered by both `list_enabled_rules_for_event` SQL (`r.enabled = TRUE`) and the `not rule.enabled` guard at line 186 (belt-and-suspenders). *See F5 — hardcoded `"max_attempts": 3` at line 224 instead of `DEFAULT_MAX_ATTEMPTS`.* |
| `services/api/app/services/notifications_delivery.py::deliver_envelope` | **D6/D7**. Claim → `delivered_in_flight` pre-send → invoke port → mark delivered / failed / ambiguous. Reads `LEASE_SECONDS` from scheduler (S15). Ambiguous branch leaves the envelope `delivered_in_flight` for operator reconciliation (M3 / audit F3), matches proposal §WU-029B-deliver-service step 8 exactly (lines 624-626). The delivery service never writes `notification_rules` — AC4 invariant. The no-op short-circuit at lines 63-81 handles both `delivered` and `delivered_in_flight`, satisfying `test_delivery_worker_skips_delivered_in_flight_without_resend` intent (though no test name-pins it — F8). |
| `services/api/app/tasks/notifications_materialize.py` | `@register_scheduler_handler("notifications_materialize")` per **D9** + proposal §WU-029B-materialize-scheduler lines 382-388. `get_materialize_db()` lazy DB resolution for worker tests. |
| `services/api/app/tasks/notifications_deliver.py` | `@register_scheduler_handler("notifications_deliver")` per **D9** + proposal §WU-029B-deliver-scheduler lines 574-580. Configurable `_DELIVERY_PORT_FACTORY` so tests inject fake ports (proposal line 638). |

### API endpoints + router

| File | Justification |
|---|---|
| `services/api/app/api/v1/endpoints/notifications.py` router mount | Ticket Technical Specification; proposal §WU-029A-endpoints lines 337-361. |
| `_parse_if_match`/`_set_etag` | Mirrors `services/api/app/api/v1/endpoints/members.py:36,57` — SLICE-010/011 OCC pattern (proposal line 361). |
| `POST /api/v1/notification-rules` | **AC1** + **D12** `notification.write` at global scope; proposal lines 342-346. Sets ETag to the aggregate version. |
| `GET /api/v1/notification-rules` (list) | **AC1** + **D12** `notification.read` at global scope; proposal lines 346-350. Supports `scope_kind`/`scope_id` query filters. |
| `GET /api/v1/notification-rules/{rule_id}` | **AC1** precondition read for If-Match PATCH; scope §3 (`plans/risk/slice-015-scope.md:56-57`). +1 route beyond ticket/roadmap sketch, required by AC1 "update" semantics. |
| `PATCH /api/v1/notification-rules/{rule_id}` | **AC1** "stale updates rejected by optimistic locking"; scope §3 (`plans/risk/slice-015-scope.md:58-60`). +1 route beyond ticket/roadmap sketch, mandatory for the "update" half of AC1. `StaleMutationError` → 412 with `stale_notification_rule_version` code matches §WU-029A-endpoints lines 357-358. |
| `_raise_known` | Typed-error → HTTP status mapping (proposal line 236). |
| `services/api/app/api/v1/router.py` (+1 line `notifications` import/mount) | Required by ticket Technical Specification. |
| `services/api/app/tasks/__init__.py` (+2 imports `notifications_materialize`, `notifications_deliver`) | **D9** handler registration at module load (proposal §WU-029B tasks). |
| `services/api/app/core/factory.py` | Wires `configure_notifications_materialize(...)` and `configure_notifications_deliver(...)` at app startup so the DB and optional delivery port factory are available to the registered handlers. Consistent with existing task-runtime wiring. |

### API tests

| File:Line | Justification |
|---|---|
| `services/api/tests/test_notification_rules.py:150 test_create_rule_persists_all_fields` | **AC1** create trace (proposal §AC Trace lines 896-897). *F7 name drift from `test_create_rule_persists_trigger_recipients_channel_grouping`.* |
| `:206 test_patch_rule_with_current_version_succeeds` | **AC1** OCC trace (proposal §AC Trace line 898). |
| `:255 test_patch_rule_stale_version_returns_412` | **AC1** stale-update trace (proposal §AC Trace line 899). |
| `:286 test_list_rules_filters_by_scope` | **AC1** list-filter trace (proposal §AC Trace line 900). |
| `:328 test_rule_create_requires_notification_write_permission` | **D12** authority gate (proposal §WU-029A-endpoints line 343). |
| `:351 test_rule_create_audit_payload_includes_all_rule_fields` | **M4**/**A6 gate** (audit `plans/risk/slice-015-audit.md:432-436`): exact-key-set equality against activity-action `request_json` for `notification_rule.create`. |
| `:400 test_notification_dispatcher_grants_seeded_without_notification_write` | **D12**/**A5 gate** (audit `plans/risk/slice-015-audit.md:428-430`): asserts `notification.write NOT IN permissions` for the dispatcher grant row. *F7 name drift from `test_notification_dispatcher_service_grants_seeded`, but impl name is arguably clearer.* |
| `services/api/tests/test_notification_materialization.py:267 test_notification_migration_creates_tables_and_partial_unique_indexes` | Structural probe of the wu-029a migration (backs proposal §WU-029A-migration indexes 167-182). *Not name-pinned by proposal, partial coverage of F8 item (a).* |
| `:310 test_emit_is_atomic_when_called_with_connection` | **M2 gate** (audit `plans/risk/slice-015-audit.md:50-90`): forced enqueue failure, asserts the `notification_events` row and paired deferred effect are both absent after rollback. |
| `:351 test_materialize_enqueues_delivery_effects_in_one_transaction` | **D9** + Rev-1 S12 pin (`plans/risk/slice-015-shortcut.md:215-232`): envelope insert and `notifications_deliver` enqueue share one connection. Extra test beyond proposal spec; aligns with shortcut guidance. |
| `:378 test_per_event_rule_emits_one_envelope_per_event` | **AC2** trace (proposal §AC Trace line 922). |
| `:397 test_per_root_cause_rule_emits_one_envelope_per_root_correlation` | **AC2** trace (proposal §AC Trace line 923). |
| `:414 test_multiple_events_same_root_correlation_produce_one_envelope` | **AC2** trace (proposal §AC Trace line 924). *F7 name drift.* |
| `:432 test_different_root_correlations_produce_separate_envelopes` | **AC2** trace (proposal §AC Trace line 925). *F7 name drift.* |
| `:455 test_replay_same_event_does_not_create_duplicate_envelopes` | **AC3** trace (proposal §AC Trace line 942). *F7 name drift.* |
| `:475 test_materialize_is_idempotent_under_retry` | **AC3** trace (proposal §AC Trace line 944). |
| `:497 test_recipient_resolution_at_materialization_time` | **D10**/Invariants (proposal §AC Trace line 992). |
| `:523 test_template_rendering_snapshot_isolates_from_later_rule_edits` | **D11**/Invariants (proposal §AC Trace line 995). |
| `:549 test_materialize_skips_rules_when_enabled_false` | **A4 gate** (audit `plans/risk/slice-015-audit.md:424-426`). *F7 name drift from proposal's `test_disabled_rule_does_not_materialize`.* |
| `:563 test_materialize_skips_when_template_missing_key` | **D11**/Invariants (proposal §AC Trace line 994). *F7 name drift from `test_materialize_skips_when_template_has_missing_key`.* |
| *(missing)* `test_unique_index_prevents_duplicate_envelope_rows` | **AC3**/Invariants name-pinned in proposal §AC Trace line 943 and §WU-029B-materialize-tests line 556. *See F8(a).* |
| *(missing)* `test_designated_channel_destination_snapshotted_at_materialization_time` | Invariants name-pinned in proposal §AC Trace line 993 and §WU-029B-materialize-tests line 559. *See F8(b).* |
| `services/api/tests/test_notification_delivery_worker.py:382 test_claim_due_rows_with_claim_status_none_does_not_set_status` | **A1 gate**/Invariants (proposal §AC Trace line 990 + audit `plans/risk/slice-015-audit.md:401-407`). |
| `:422 test_delivery_worker_marks_envelope_delivered_exactly_once` | **AC4** trace (proposal §AC Trace line 963). |
| `:445 test_discord_delivery_failure_does_not_mutate_rule` | **AC4** trace (proposal §AC Trace line 966). |
| `:467 test_retry_attempts_counter_increments_on_failure` | **AC4** trace (proposal §AC Trace line 968). |
| `:483 test_degraded_state_summary_counts_stuck_in_flight_envelopes` | **M3 gate**/AC4 (audit `plans/risk/slice-015-audit.md:111-113`, proposal §AC Trace line 965). |
| *(missing)* `test_delivery_worker_skips_delivered_in_flight_without_resend` | **AC4** name-pinned in proposal §AC Trace line 964 and §WU-029B-deliver-tests line 664. The no-op short-circuit at `services/api/app/services/notifications_delivery.py:69-76` exercises this path, but no direct test. *See F8(c).* |
| `services/api/tests/test_notification_event_contract.py` | Updated to the Rev-2 `emit()` keyword contract (audit `plans/risk/slice-015-audit.md:86-89` flagged this as the only pre-PR `emit()` caller). |
| `services/api/tests/conftest.py` | Adds `notification_rules` and `notification_envelopes` to `GOVERNANCE_TABLES` per proposal §WU-029A-migration. |

### Discord contracts + handler + tests

| File | Justification |
|---|---|
| `services/discord/app/contracts/notifications.py` | Mirrors the minimum command/result shape needed by the adapter — proposal §WU-029C-contracts lines 681-693. `NotificationDeliveryError.definitive_failure: bool` distinguishes retryable rejected sends from ambiguous transport failures (D6 step 8). |
| `services/discord/app/handlers/notifications.py::envelope_nonce` | **D7 BINDING** (synthesis.md:105-111): `base64.b32encode(envelope_id.bytes).decode("ascii").rstrip("=")[:25]`. Covered by `test_delivery_uses_deterministic_nonce_derived_from_envelope_id`. |
| `:deliver_notification` | Uses envelope snapshot only per **D11** / proposal §WU-029C-adapter responsibilities lines 729-735. DM opens/creates; designated channel sends to `destination_channel_id`; thread raises definitive `NotificationDeliveryError` (defensive — materializer already skips threads). Generic exceptions become ambiguous (`definitive_failure=False`) so the API worker can keep the envelope in `delivered_in_flight`. `enforce_nonce=True`. Does not fetch or mutate notification rules (§WU-029C-adapter line 736). |
| `services/discord/app/handlers/__init__.py` | Registers the notification handler alongside existing roster/onboarding handlers. |
| `services/discord/tests/test_notifications.py` | Only the formally-named nonce test is committed. *See F9 for the three missing adapter tests enumerated informally in proposal §WU-029C-tests lines 758-760.* |

### Anti-scope confirmation (D14)

Spot-checked against scope §2 and §7, and the diff:

- No ack UI / ack endpoint / ack column — `delivery_status` literal stays 5-valued (`pending`/`delivered_in_flight`/`delivered`/`skipped`/`failed`). **D14 preserved.**
- No recurring-scheduler primitive — only `deferred_effects` enqueues; no new entries in `scheduled_jobs`. **D14 preserved.**
- No digest/batching/analytics — one envelope per `(event/root, rule, recipient)` at materialization time. **D14 preserved.**
- No separate template registry — `template_json` is inline JSONB on the rule (proposal line 108). **D14 preserved.**
- No recipient preferences table — not present. **D14 preserved.**
- No email/SMS — `NotificationChannel` literal stays 3-valued. **D14 preserved.**
- No archival — no `archived_at`, no archival endpoint. **D14 preserved.**
- No cross-guild federation — no `guild_id` column on rules or envelopes. **D14 preserved.**
- No retrofit of existing producers (SLICE-007/013/018/019) — only `notification_events.py::emit` was touched (the D9-required hookpoint), no new `emit()` calls elsewhere. **§2 preserved.**
- No recursive causation walk — `root_correlation_id` is assigned from `notification_events.correlation_id` directly (materialize service line 207), no DAG traversal. **§2 preserved.**
- No thread creation — `channel='thread'` rules materialize as skipped with `reason='thread_channel_out_of_scope'`. **§2 preserved.**
- No backwards-compat shims — `emit()` was extended in place, no `emit_v2`, no aliases. **§2 preserved.**
- No role resolver — `discord_role` recipients persist on rules but materialize as skipped with `reason='recipient_unresolved'`. **§2 preserved.**

## 4. Sanity probes for "deferred stubs"

Grepped the PR for `TODO`, `NotImplementedError`, `...`-only function bodies, `pass  #`, `raise NotImplementedError`. None found in production code paths.

The one `# noqa: ARG001` in `services/api/app/services/notification_events.py:36` is a *used-but-referenced-as-reserved* signal, not a stub — see F4 for justification-chain gap.

The `"thread_channel_out_of_scope"` branch in `_resolve_destination` and the `"recipient_unresolved"` branch in `_resolve_recipients` are not stubs: they materialize *skipped* envelopes with stable `last_error_json.reason` values per D10 and §2 Out-of-scope. These are bounded scope boundaries, not placeholders.

Thread-channel raise in the Discord adapter (`services/discord/app/handlers/notifications.py`) is a defensive definitive-error: materializer should already have skipped these envelopes, and if a future slice removes the materializer guard first, the adapter will surface the mistake at delivery time rather than silently drop.

## 5. Sanity probes for "premature abstractions"

- **Delivery port protocol** (`NotificationDeliveryPort` Protocol) — justified by D6 (separate API worker from Discord mechanics) and by tests needing a fake port (proposal §WU-029B-deliver-service line 637). Not premature.
- **`DegradedStateSummaryRead.stuck_in_flight_envelopes` universal field** — see F6. Mild premature abstraction: field defaults to 0 for non-notification subsystems. Defensible as "extend existing summary shape" but surfaces a notification-specific counter universally.
- **`configure_notifications_deliver` with `_DELIVERY_PORT_FACTORY` module globals** — justified by "testable with an injected fake delivery port" (proposal §WU-029B-deliver-service line 637). Pattern matches existing scheduler task-runtime wiring; not premature.
- **Lazy `get_delivery_db()` / `get_materialize_db()`** — implementation.md §Notes line 113-115 discloses this as supporting "direct worker tests can execute without building the FastAPI app first." Reasonable for worker ergonomics; one short function each, not an abstraction layer.

## 6. Sanity probes for "dead code"

- `actor: ActorIdentity` in `emit()` — see F4. Reserved-but-unused parameter ships verbatim per Rev-2 proposal §WU-029B-materialize lines 394-402; the `noqa: ARG001` comment is a code-smell signal per repo guidance, but the parameter was demanded by the proposal. Narrow finding.
- `get_delivery_port()` raises `RuntimeError("notifications delivery port is not configured")` at `services/api/app/tasks/notifications_deliver.py:38` — this is a runtime boundary check, not dead code; it guards against worker-start before `configure_notifications_deliver` is invoked.
- No unused imports surfaced; no unreachable branches.

## 7. Sanity probes for "magic values"

- `"max_attempts": 3` at `services/api/app/services/notifications_materialize.py:224` — see F5. Literal equals the DB column DEFAULT and `DEFAULT_MAX_ATTEMPTS`, so behaviorally safe; hygienically, it should be `DEFAULT_MAX_ATTEMPTS` to track shared scheduler tuning.
- `"notification-dispatcher"` worker-id default at `services/api/app/services/notifications_materialize.py:169`, `services/api/app/services/notifications_delivery.py:51`, and `services/api/app/tasks/notifications_deliver.py:43` — matches the service actor id seeded in the migration (**D13 BINDING**, proposal §WU-029A-migration line 187). Shortcut S2 (`plans/risk/slice-015-shortcut.md:41-52`) explicitly blesses this as matching existing service-actor convention.
- `[:16]` SHA-256 truncation for unresolved-selector hash at `services/api/app/services/notifications_materialize.py:73` — **A3 gate** (audit `plans/risk/slice-015-audit.md:418-422`) satisfied: full selector JSON sorted-keys → SHA-256 → 16 hex chars. Documented inline as `_recipient_selector_key`.
- `[:25]` base32 nonce truncation at `services/discord/app/handlers/notifications.py::envelope_nonce` — Discord API constraint (**D7 BINDING**, audit F3, research §Discord nonce); not a magic number.
- `LEASE_SECONDS` / `DEFAULT_MAX_ATTEMPTS` — imported from `services/api/app/services/scheduler.py:27-30` per **S15** (`plans/risk/slice-015-shortcut.md:280-289`). Not smuggled.
- `"stuck_in_flight_envelopes"` threshold `INTERVAL '1 hour'` in `query_degraded_state_summary` — **M3** pinned literal (audit `plans/risk/slice-015-audit.md:102-107`).

## 8. Tests without AC trace

Two tests in the committed suite are not name-pinned by proposal but extend coverage:

- `test_notification_migration_creates_tables_and_partial_unique_indexes` (`test_notification_materialization.py:267`) — structural probe of the wu-029a migration (indexes, check constraints). Covers an implicit proposal §WU-029A-migration requirement; arguably should be in a dedicated `test_wu_029a_notifications_migration.py`. Acceptable.
- `test_materialize_enqueues_delivery_effects_in_one_transaction` (`:351`) — exercises shortcut S12 pin (`plans/risk/slice-015-shortcut.md:215-232`). The S12 pin itself is a one-liner implementation note; the test is legitimate coverage of the "same-connection" invariant that S12 guards. Acceptable.

Three tests are **missing** from the proposal-specified list — see F8. Five test names drift from proposal-specified names — see F7.

## 9. "Non-trivial file" coverage checklist

| File in diff | Traced? |
|---|---|
| `migrations/versions/wu-029a_notifications.py` | ✅ |
| `services/api/app/api/v1/endpoints/notifications.py` | ✅ |
| `services/api/app/api/v1/router.py` | ✅ |
| `services/api/app/contracts/notifications.py` | ✅ |
| `services/api/app/contracts/scheduler.py` | ✅ (F6 for universal `stuck_in_flight_envelopes` field) |
| `services/api/app/core/factory.py` | ✅ |
| `services/api/app/repositories/notifications.py` | ✅ (F2 for bespoke envelope claim CTE) |
| `services/api/app/repositories/_claim.py` | ✅ (A1 gate satisfied) |
| `services/api/app/repositories/deferred_effects.py` | ✅ (M3 resolution) |
| `services/api/app/services/deferred_effects.py` | ✅ (F1 for unextended service wrapper) |
| `services/api/app/services/notification_events.py` | ✅ (F4 for reserved `actor` parameter) |
| `services/api/app/services/notifications.py` | ✅ (F3 for `action_type="notification_rule.update"` drift) |
| `services/api/app/services/notifications_materialize.py` | ✅ (F5 for hardcoded `max_attempts: 3`) |
| `services/api/app/services/notifications_delivery.py` | ✅ |
| `services/api/app/tasks/__init__.py` | ✅ |
| `services/api/app/tasks/notifications_materialize.py` | ✅ |
| `services/api/app/tasks/notifications_deliver.py` | ✅ |
| `services/api/tests/conftest.py` | ✅ |
| `services/api/tests/test_notification_rules.py` | ✅ (F7 for name drifts) |
| `services/api/tests/test_notification_materialization.py` | ✅ (F7 for name drifts, F8 for missing tests) |
| `services/api/tests/test_notification_delivery_worker.py` | ✅ (F8 for missing `test_delivery_worker_skips_delivered_in_flight_without_resend`) |
| `services/api/tests/test_notification_event_contract.py` | ✅ (Rev-2 caller update) |
| `services/discord/app/contracts/notifications.py` | ✅ |
| `services/discord/app/handlers/notifications.py` | ✅ |
| `services/discord/app/handlers/__init__.py` | ✅ |
| `services/discord/tests/test_notifications.py` | ✅ (F9 for missing adapter tests) |
| `.pipeline/*.md`, `plans/risk/slice-015-*.md` | Planspace — informational, not production code. |

## 10. Merge recommendation

**Merge allowed under `LOW_CONCERN`.**

All four ACs are covered by at least one direct test, the four audit Rev-2
resolutions (M1–M4) are implemented and tested, all six phase-3 gates
(A1–A6) are satisfied in behavior (though F2 drifts on the A2/S4 helper-reuse
pin and tests are named differently — F7), and every non-trivial file traces
to a D-decision, AC, or revision rationale.

Non-blocking polish to absorb before SLICE-016/017 (or the next notification
slice) opens:

1. **F1** — Extend `services/api/app/services/deferred_effects.py::enqueue_effect` to accept `connection: Connection | None = None`, migrate `notification_events.emit` and `notifications_materialize.materialize_event` to call the service wrapper, OR amend audit A2 to note the repository-level function is the substrate.
2. **F2** — Replace `claim_notification_envelope` with a `claim_due_rows(..., claim_status=None, batch_size=1, ready_predicate="id = %s AND ...")` call to honor shortcut S4 and the proposal's substrate-reuse contract.
3. **F3** — Rename `action_type="notification_rule.update"` → `"notification_rule.patch"` at `services/api/app/services/notifications.py:182`.
4. **F4** — Either remove the unused `actor` parameter from `emit()` (requires proposal amendment) or wire it through to the audit-context actor write.
5. **F5** — Replace hardcoded `"max_attempts": 3` at `services/api/app/services/notifications_materialize.py:224` with `DEFAULT_MAX_ATTEMPTS`.
6. **F6** — Decide between universal `DegradedStateSummaryRead.stuck_in_flight_envelopes: int` (keep as-is) or subsystem-keyed counter map.
7. **F7** — Align committed test names with proposal spec (or amend proposal), especially A4/A5/A6-gate tests.
8. **F8** — Add the three missing name-pinned tests: `test_unique_index_prevents_duplicate_envelope_rows` (DB-layer enforcement), `test_designated_channel_destination_snapshotted_at_materialization_time`, `test_delivery_worker_skips_delivered_in_flight_without_resend` (direct short-circuit probe).
9. **F9** — Bind explicit Discord-side adapter tests (success, failure, DM/designated-channel routing) matching proposal §WU-029C-tests intents.
10. **F10** — Drop the stale dirty-worktree note in `.pipeline/implementation.md:118-119`.

No HIGH findings. No merge block.
