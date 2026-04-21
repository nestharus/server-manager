# SLICE-015 Phase 8 — Multi-Concern Review (PR #50)

Reviewed: 2026-04-21
PR: `feat/slice-015-notifications` (#50), 33 files, +6366 / −967 LOC
Inputs: `.pipeline/proposal.md` rev 2, `.pipeline/implementation.md`,
`gh pr diff 50`, `AGENTS.md` §"One Concern Per PR" (lines 178–193).

## 1. Verdict

**`MULTI_CONCERN_RECOMMEND_SPLIT`**

PR #50 bundles three reviewable concerns with a linear producer →
consumer → adapter dependency chain:

- **WU-029A** (rule aggregate + rule API surface) is a pure API-layer
  CRUD concern. It can ship standalone: operators can author, read, and
  patch `NotificationRule` aggregates with `If-Match`/ETag OCC while the
  downstream worker pipeline remains absent.
- **WU-029B-materialize + WU-029B-deliver** (event → envelope →
  delivery-port pipeline) is the worker-substrate concern. It can ship
  standalone on top of PR A using a fake `NotificationDeliveryPort`;
  `services/api/tests/test_notification_delivery_worker.py` already
  verifies exactly-once, retry, and `stuck_in_flight` behavior without a
  live Discord transport. Splitting `materialize` from `deliver` into
  separate PRs is **not** recommended (§6).
- **WU-029C** (Discord delivery adapter) is the transport concern inside
  `services/discord`. It implements the same command/result contract
  defined by WU-029B and has no compile-time coupling to API Python
  symbols beyond the shared contract shape.

Against AGENTS.md §"One Concern Per PR":
- "A PR that touches N independent concerns should be split into N PRs"
  — PR #50 touches three concerns that map to three disjoint code paths
  (rule CRUD at `/api/v1/notification-rules`, the materialize/deliver
  worker pipeline, and the Discord adapter).
- "Dependency order matters" — A → B → C is a linear chain, not a cycle.
- "Additive changes go before behavioral changes" — the rule API and
  migration are additive and land first; the worker pipeline is
  behavioral and lands second; the Discord transport is the last
  behavioral edge.
- "Split oversized PRs" — 33 files / +6366 LOC exceeds the typical
  single-concern envelope. For comparison, the SLICE-018 precedent (PR
  #43) was split at 19 files / +3447 LOC.

This matches the SLICE-018 precedent (PR #43 split WU-033 → WU-034 on a
producer/consumer edge) and the SLICE-013 precedent (PR #39 split
WU-018 → WU-019 → WU-020).

## 2. Concerns enumerated

### Concern A — WU-029A: rule aggregate + rule API

Rule CRUD aggregate surface. Adds the `notification_rules` table and
its aggregate-heads-joined select, rule contracts
(`NotificationTrigger`, `NotificationRuleCreate`/`Patch`/`Read`/
`ListRead` with `extra="forbid"` + `populate_by_name` aliases for
`trigger` / `recipients` / `template`, rule error types), rule
repository functions (`insert/update/fetch/fetch_for_update/list`
and `list_enabled_rules_for_event`), the rule service module backed by
`mutate_entity` with pinned `payload_allowlist` covering all nine
persisted fields, the four endpoints (`POST`, `GET` list, `GET` one,
`PATCH` with `If-Match` → 412 `stale_notification_rule_version`), and
`test_notification_rules.py` (422 lines) covering persistence, OCC,
audit payload, scope filtering, and dispatcher-grant presence.

Pure API-layer concern. No worker, no scheduler handler, no Discord
code. Passes independently; the trigger/recipients/template/grouping
columns are persisted but not yet consumed.

### Concern B — WU-029B: materialize + deliver worker pipeline

Worker-pipeline concern split across substrate extensions, envelope
schema, and two deferred-effect handlers.

Schema: adds `notification_envelopes` (26 columns) with two partial
unique indexes (`uq_notification_envelopes__per_event` keyed by
`(source_event_id, rule_id, recipient_key)`,
`uq_notification_envelopes__per_root_cause` keyed by `(rule_id,
root_correlation_id, recipient_key)`), the pending-delivery partial
index, rule/event FK restrictions, and the `delivered_at` vs
`delivery_status` consistency check.

Substrate extensions: generalizes
`services/api/app/repositories/_claim.py::claim_due_rows()` with
`claim_status: str | None = "claimed"` where `None` omits the `status =
%s` SET clause entirely (parameter order depends on the flag); extends
`services/api/app/repositories/deferred_effects.py::
query_degraded_state_summary` with a `stuck_in_flight_envelopes` count
over `delivery_status = 'delivered_in_flight' AND claimed_at < now() -
INTERVAL '1 hour'`.

Contract + behavior change on the existing emit path: rewrites
`services/api/app/services/notification_events.py::emit` to
`emit(db, *, event, actor, connection=None, payload_allowlist=None)`
and inserts a paired `notifications_materialize` deferred effect inside
the same transaction — either the caller's `connection` or a short
`db.transaction()` owned by `emit()`. This is the atomicity fix for M2
from audit round 2.

Workers: adds `services/api/app/services/notifications_materialize.py`
(rule matching, scope matching, recipient resolution,
destination/channel snapshotting, strict `string.Template.substitute`
with `TemplateRenderError` → skipped envelope, envelope insert with
`ON CONFLICT DO NOTHING`, paired `notifications_deliver` enqueue in
shared transaction), `services/api/app/services/notifications_delivery.py`
(claim via `_claim.claim_due_rows(claim_status=None)`,
`delivered_in_flight` guard before port invocation, retry accounting on
envelope, rule isolation), and two `app/tasks/*` modules that register
handlers via `register_scheduler_handler` with a `configure_task_runtime`
entry point for DI of the fake port.

Envelope repository functions (`insert_on_conflict_do_nothing`, `fetch`,
`claim_pending`, `mark_delivered_in_flight`, `mark_delivered`,
`mark_failed`, `mark_skipped`) land alongside the rule functions in
`services/api/app/repositories/notifications.py`.

Tests: `test_notification_materialization.py` (583 lines),
`test_notification_delivery_worker.py` (504 lines), plus the
`test_notification_event_contract.py` delta (53 lines) covering the new
`emit()` keyword-only signature and the atomic enqueue rollback
regression.

Touches only `services/api`, `migrations/`, and pipeline artifacts. Does
not import Discord code; delivery-port tests use an in-process fake.

### Concern C — WU-029C: Discord notification delivery adapter

Implements `services/discord/app/handlers/notifications.py::
deliver_notification(command, *, bot) -> NotificationDeliveryResult`
against the WU-029B command/result contract. Adds a mirrored
`services/discord/app/contracts/notifications.py` that keeps field
names aligned with `services/api/app/contracts/notifications.py` so the
boundary serialization stays direct; exposes a `definitive_failure`
flag on `NotificationDeliveryError` so ambiguous transport failures map
to `delivered_in_flight` reconciliation instead of retry. Derives the
Discord `nonce` as `base32(uuid.bytes)[:25]` (documented in the adapter
and covered by
`test_delivery_uses_deterministic_nonce_derived_from_envelope_id`),
sends with `enforce_nonce=True`, routes `dm` vs `designated_channel`
from the envelope snapshot, and raises on `thread` (the materializer
should have skipped thread envelopes already).

Test suite (`services/discord/tests/test_notifications.py`, 83 lines)
runs against a fake bot with no API calls. No reverse edges into
`services/api`.

## 3. Recommended PR ordering (topological)

```
PR A (WU-029A) ──▶ PR B (WU-029B materialize + deliver) ──▶ PR C (WU-029C)
```

Forcing edges (all left-to-right, none reversed):

- B → A schema: `notification_envelopes.rule_id` has
  `ON DELETE RESTRICT` FK to `notification_rules(id)` created by PR A.
- B → A runtime: `list_enabled_rules_for_event` reads
  `notification_rules`; without PR A the table is absent and
  materialization fails.
- B → A authority: the dispatcher grant (`notification-dispatcher`
  global `notification.read + notification.deliver`) is seeded by PR
  A's migration and exercised by PR B's worker (`actor_kind="service"`,
  `actor_id="notification-dispatcher"`). Seeding it in PR A before PR B
  is harmless and matches the SLICE-018 `roster-syncer` precedent.
- C → B contract: WU-029C implements `NotificationDeliveryPort`
  (command in → result out); the protocol and
  `NotificationDeliveryCommand` / `NotificationDeliveryResult` /
  `NotificationDeliveryError` shapes are defined by PR B.
- C → B wiring: PR B's `configure_task_runtime(delivery_port_factory=…)`
  is the injection point; PR C provides the Discord-backed factory.
  Until PR C lands, the worker uses a fake port in tests and remains
  unregistered in production (no Discord send).

PR A's API suite passes with the rule endpoints alone. PR B's full API
suite (401 passed) runs against the fake port. PR C's Discord suite (66
passed) runs against a fake bot.

## 4. File allocation (every code/test file → exactly one PR)

### PR A — WU-029A (rule API + migration) [7 code/test files + 7 slice docs]

Code:
- `migrations/versions/wu-029a_rules.py` (split: create
  `notification_rules` table + `ix_*_scope`, `ix_*_enabled`,
  `ix_*_trigger_json_gin`; seed `notification-dispatcher` grant)
- `services/api/app/api/v1/endpoints/notifications.py` (new — rule
  CRUD only)
- `services/api/app/api/v1/router.py` (add `notifications` include)
- `services/api/app/contracts/notifications.py` (additions: `NotificationChannel`,
  `NotificationGrouping`, `NotificationTrigger`,
  `NotificationRuleCreate/Patch/Read/ListRead`,
  `NotificationRuleNotFoundError`, `NotificationRulePatchEmptyError`,
  `NotificationRuleVersionError`,
  `UnsupportedNotificationTriggerError`)
- `services/api/app/repositories/notifications.py` (additions: `_RULE_SELECT`,
  `insert/update/fetch/fetch_for_update/list_notification_rule`,
  `list_enabled_rules_for_event`)
- `services/api/app/services/notifications.py` (new — rule service
  with `RULE_PAYLOAD_FIELDS` allowlist and `mutate_entity` calls)

Tests:
- `services/api/tests/test_notification_rules.py` (new)

Slice-level docs (see §5):
- `.pipeline/implementation.md`
- `.pipeline/proposal.md`
- `.pipeline/research.md`
- `.pipeline/synthesis.md`
- `plans/risk/slice-015-audit.md`
- `plans/risk/slice-015-scope.md`
- `plans/risk/slice-015-shortcut.md`

### PR B — WU-029B-materialize + WU-029B-deliver (worker pipeline) [18 code/test files]

Code:
- `migrations/versions/wu-029b_envelopes.py` (new split: create
  `notification_envelopes` + two partial unique indexes + pending /
  rule_id / source_event_id / root_correlation_id indexes)
- `services/api/app/contracts/notifications.py` (extensions:
  `NotificationDeliveryStatus`, `NotificationEnvelopeRead`,
  `NotificationMaterializationResult`,
  `NotificationDeliveryCommand`, `NotificationDeliveryResult`,
  `NotificationDeliveryError`,
  `AmbiguousNotificationDeliveryError`, `TemplateRenderError`)
- `services/api/app/contracts/scheduler.py` (one-line extension)
- `services/api/app/core/factory.py` (wire `configure_task_runtime`)
- `services/api/app/repositories/_claim.py` (generalize
  `claim_due_rows` with `claim_status: str | None = "claimed"`)
- `services/api/app/repositories/deferred_effects.py` (add
  `stuck_in_flight_envelopes` to `query_degraded_state_summary`)
- `services/api/app/repositories/notifications.py` (extensions:
  `_ENVELOPE_SELECT`, envelope insert/fetch/claim/mark-* functions)
- `services/api/app/services/deferred_effects.py` (one-line passthrough
  for shared connection)
- `services/api/app/services/notification_events.py` (rewrite `emit()`
  signature + atomic deferred-effect enqueue)
- `services/api/app/services/notifications_delivery.py` (new)
- `services/api/app/services/notifications_materialize.py` (new)
- `services/api/app/tasks/__init__.py` (new — `configure_task_runtime`)
- `services/api/app/tasks/notifications_deliver.py` (new)
- `services/api/app/tasks/notifications_materialize.py` (new)

Tests:
- `services/api/tests/conftest.py` (extend truncate list with
  `notification_envelopes`)
- `services/api/tests/test_notification_delivery_worker.py` (new)
- `services/api/tests/test_notification_event_contract.py` (update
  emit call sites to keyword-only; add atomic enqueue rollback
  regression)
- `services/api/tests/test_notification_materialization.py` (new)

### PR C — WU-029C (Discord delivery adapter) [4 files]

Code:
- `services/discord/app/contracts/notifications.py` (new)
- `services/discord/app/handlers/__init__.py` (register
  `deliver_notification`)
- `services/discord/app/handlers/notifications.py` (new)

Tests:
- `services/discord/tests/test_notifications.py` (new)

Total: 7 + 18 + 4 = 29 code/test files + 7 slice docs = 36. The
arithmetic exceeds PR #50's 33 because `services/api/app/contracts/
notifications.py`, `services/api/app/repositories/notifications.py`,
and `migrations/versions/wu-029a_notifications.py` each contribute to
two concerns; the migration splits into two files (net +1), while the
contracts and repository modules appear in both PRs as additive edits
(net 0 for each, but counted in both allocations). After splitting the
migration, PR #50's 33 files map cleanly to 34 distinct change-units
across the three PRs.

## 5. Straddling files — flags and justifications

### `migrations/versions/wu-029a_notifications.py` (as written) → split

The file creates **both** `notification_rules` and
`notification_envelopes` and seeds the dispatcher grant. The envelopes
table has no consumer in PR A; creating it there would ship a
dead-schema surface. The standard split is:

- `wu-029a_rules.py` in PR A: rules table + indexes + dispatcher grant
  seed (`revision="wu_029a_rules"`, `down_revision="wu_012_trust"`).
- `wu-029b_envelopes.py` in PR B: envelopes table + unique indexes +
  delivery/lookup indexes (`revision="wu_029b_envelopes"`,
  `down_revision="wu_029a_rules"`).

Seeding the `notification.deliver` permission in PR A before PR B
consumes it is harmless and mirrors the SLICE-018 `roster-syncer` grant
seed in `wu-033_roster.py` (consumed by WU-034). Do **not** defer the
grant to the PR B migration — the dispatcher actor's permission
lineage belongs with the rule-aggregate substrate that defines
`notification.*` scoping.

### `services/api/app/contracts/notifications.py` → appears in PR A and PR B

PR A introduces the file with the rule-side types and the two
cross-cutting literals (`NotificationChannel`, `NotificationGrouping`)
that rule payloads persist. PR B extends the file with
`NotificationDeliveryStatus`, envelope/worker types, and the four
delivery/template error classes. Keep the two literals in PR A because
rule create/patch validators depend on them; PR B adds
`NotificationDeliveryStatus` because it is envelope-only. No symbol is
defined in both PRs.

### `services/api/app/repositories/notifications.py` → appears in PR A and PR B

PR A introduces the module with `_RULE_SELECT` and the rule functions
(including `list_enabled_rules_for_event`, which PR B consumes). PR B
adds `_ENVELOPE_SELECT` and the envelope claim/mark functions. A
per-table split (`repositories/notification_rules.py` vs
`repositories/notification_envelopes.py`) is viable but adds churn for
no structural benefit; keep them in one module and allocate by PR.

### `services/api/app/services/notification_events.py` → PR B

Touched only to rewrite `emit()` signature and add the atomic paired
enqueue for `notifications_materialize`. PR A does not need it: rule
CRUD does not emit events. This is a behavioral change tied to the
worker pipeline and belongs with PR B.

### `services/api/app/repositories/_claim.py` (substrate change) → PR B

The `claim_status: str | None = "claimed"` generalization only matters
for envelope claiming, which lives in PR B. Existing
scheduler/deferred-effect callers keep the default. The regression
test (`test_claim_due_rows_with_claim_status_none_does_not_set_status`)
lives in `test_notification_delivery_worker.py` and belongs with PR B.

### `services/api/app/repositories/deferred_effects.py` (degraded summary) → PR B

The `stuck_in_flight_envelopes` CTE references
`notification_envelopes`, which is created by PR B's migration. Keep
the summary extension in PR B; without the envelopes table the CTE
would fail at runtime.

### `services/api/tests/conftest.py` → PR B

The truncate-list extension adds `notification_envelopes`, whose
table is created by PR B. No entry is needed for
`notification_rules` since it is created by PR A and may already be in
the fixture list after PR A lands.

### `services/api/tests/test_notification_event_contract.py` → PR B

53-line delta is entirely call-site churn for the new `emit()`
keyword-only signature plus the `test_emit_is_atomic_when_called_with_connection`
rollback regression. Both are WU-029B-materialize concerns.

### `.pipeline/*`, `plans/risk/slice-015-*.md` → PR A

7 slice-level artifacts. They describe the whole slice, not a single
WU. Cleanest allocation is to ship them with PR A since PR A lands
the substrate the artifacts primarily describe. Alternative: split
pipeline docs across PRs by WU section; adds review overhead for no
audit benefit. Match the SLICE-018 precedent — all 7 in PR A.

## 6. Should WU-029B-materialize and WU-029B-deliver be separate PRs?

**No.** The user prompt flags this as the candidate split line. The
diff does not support it; combining materialize + deliver into a single
PR B is correct.

Forcing edges inside WU-029B:

- **Deferred-effect registration cycle.** `emit()` in
  `services/api/app/services/notification_events.py` enqueues
  `effect_type = "notifications_materialize"` after every event insert,
  and `materialize_event` enqueues
  `effect_type = "notifications_deliver"` after every envelope insert.
  Both handlers are registered together in
  `services/api/app/tasks/__init__.py::configure_task_runtime`. If
  materialize ships first without deliver, every `emit()` call produces
  a `notifications_deliver` effect whose handler is unregistered —
  a latent regression that leaves envelopes permanently `pending`.
- **Shared contracts.** `NotificationDeliveryCommand` /
  `NotificationDeliveryResult` are produced by `materialize` when it
  builds the delivery port command (via the envelope read) and
  consumed by `deliver` when it invokes the port. Splitting the PRs
  would require duplicating the contracts or gating them behind
  feature flags, neither of which the codebase currently does (see
  AGENTS §"No compatibility shims").
- **Substrate change justification.** The
  `claim_due_rows(claim_status=None)` generalization has no consumer
  other than the delivery worker. Landing it ahead of deliver would
  create an unused code path.
- **Degraded-summary extension justification.** The
  `stuck_in_flight_envelopes` CTE describes a state only produced by
  the delivery worker (`delivery_status = 'delivered_in_flight'`).
  Same reasoning.
- **Test coupling.** `test_notification_materialization.py` asserts
  delivery-effect enqueue shape (count, payload, idempotency key), and
  `test_notification_delivery_worker.py` seeds envelopes via the
  materialize path. Neither suite runs independently of the other.

The proposal's "Implementation Order" (§ Implementation Order,
proposal.md:1014–1025) lists materialize (step 3) and deliver (step 4)
sequentially but does not imply PR-level separability. PR-level
separation here would produce two broken intermediate states with no
external value.

## 7. Alternative considered: combine A + B into one PR

The user prompt floats "combine 029A + 029B into PR A since they share
the migration; leave 029C as PR B." Rejected for three reasons:

1. **Size.** A+B combined is ~29 code/test files; the Discord concern
   is only 4 files. The combined PR remains oversized (cf. the
   SLICE-018 split at 19 files).
2. **Shared-migration argument is shallow.** The "shared migration"
   is one file; splitting it into two files costs <20 lines of
   Alembic boilerplate and produces independently revertable schema
   units. The schema `notification_rules` is governance substrate;
   `notification_envelopes` is workflow state — they reference each
   other via FK but are reviewed for different invariants (OCC vs
   dedup/claim/retry).
3. **Concern lineage.** Rule CRUD is an aggregate-governance concern
   (mutations, OCC, audit allowlist). Materialize + deliver are a
   workflow-substrate concern (deferred effects, claim leasing,
   template rendering, port isolation). Bundling them confuses the
   review axes.

The 3-PR split aligns with the same decomposition SLICE-013 applied
(WU-018 = family versioning substrate, WU-019 = lifecycle +
substrate-replacement, WU-020 = Discord provisioning handler).

## 8. Test-suite independence check

Each concern has a dedicated test surface with no cross-concern
imports:

- PR A: `test_notification_rules.py` imports only rule contracts,
  repository rule functions, and the rule service. It does not import
  any materialize/delivery code or Discord code.
- PR B: `test_notification_materialization.py`,
  `test_notification_delivery_worker.py`, and the
  `test_notification_event_contract.py` delta import envelope
  contracts, the materialize/delivery services, the `_claim` helper,
  and a fake `NotificationDeliveryPort`. They do not import the
  Discord adapter.
- PR C: `test_notifications.py` (Discord) imports only the mirrored
  `services/discord/app/contracts/notifications.py` and a fake bot. It
  does not import API code and does not run against a live API.

No test file straddles concerns.

## 9. Size signal

PR totals: 33 files, +6366 / −967 LOC. Excluding the 7 pipeline/risk
artifacts (~4.1k LOC), the code+tests split is roughly:

- PR A (WU-029A): migration ~180, endpoints 167, contracts ~100,
  repository ~150, service 191, tests 422 → ~1.2k added across 7 files
- PR B (WU-029B): migration ~120, contracts ~100, repositories ~290
  + 19 + 26, services 261 + 156 + rewrite of events ~50 + 1, tasks 49 +
  31 + 19, factory 2, scheduler 1, conftest 2, tests 504 + 583 + 36 →
  ~2.1k added across 18 files
- PR C (WU-029C): contracts 78, handler 82, handler-index 1, tests 83
  → ~240 added across 4 files

PR A and PR C are within typical single-concern size; PR B is larger
but unitary (see §6 — materialize and deliver cannot be split without
a broken intermediate state). No further decomposition is warranted.

## 10. Summary

Recommend splitting PR #50 into three PRs in the order **WU-029A →
WU-029B (materialize + deliver) → WU-029C**, with file allocation as
in §4. The dependency graph is a linear A → B → C chain and acyclic.
Split the `wu-029a_notifications.py` migration into `wu-029a_rules.py`
(PR A, seeds rules table + dispatcher grant) and
`wu-029b_envelopes.py` (PR B, seeds envelopes table + partial unique
indexes). WU-029B-materialize and WU-029B-deliver stay bundled because
handler registration, contracts, substrate extensions, and tests are
mutually dependent — a split there produces two broken intermediate
states.
