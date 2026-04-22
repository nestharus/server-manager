# SLICE-017 Research: Cross-Subsystem Operational Views

## 1. Audit event stream shape + ordering

### `activity_state_changes` shape

`activity_state_changes` is the accepted-state-change stream created by WU-002. Its columns are:

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGINT IDENTITY` | Global surrogate key, primary key. |
| `action_id` | `BIGINT` | FK to `activity_actions.id`. |
| `aggregate_type` | `TEXT` | Aggregate namespace. |
| `aggregate_id` | `TEXT` in live schema terms | Aggregate identifier; migration was widened to text in WU-003a. |
| `aggregate_seq` | `BIGINT` | Per-aggregate causal sequence. |
| `change_type` | `TEXT` | Business transition label. |
| `payload_json` | `JSONB` | Authoritative accepted fact. |
| `diff_json` | `JSONB NULL` | Optional ergonomic diff. |
| `recorded_at` | `TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP` | Write timestamp, but not a safe unique ordering key. |

Sources: `migrations/versions/wu-002_activity_substrate.py:69-112`, `migrations/versions/wu-003a_widen_aggregate_id.py:19-40`, `services/api/app/contracts/mutations.py:13-17`, `services/api/app/contracts/mutations.py:55-67`.

Important: correlation and scope do **not** live on `activity_state_changes`; they live on `activity_actions` (`correlation_id`, `causation_id`, `scope_kind`, `scope_id`). Any projector that needs causal-chain or scope metadata must join through `action_id`. Sources: `migrations/versions/wu-003b_audit_context_columns.py:16-49`, `services/api/app/repositories/mutations.py:46-99`, `services/api/app/repositories/mutations.py:109-148`.

### Ordering guarantees that exist today

- Per-aggregate causal order is explicit and strong. `activity_state_changes` has a unique constraint on `(aggregate_type, aggregate_id, aggregate_seq)`, and `mutate_entity()` locks the aggregate head, writes the projection, inserts the state change with `new_version = current_seq + 1`, then advances `aggregate_heads.current_seq` inside one transaction. Sources: `migrations/versions/wu-002_activity_substrate.py:99-105`, `services/api/app/services/mutations.py:112-185`.
- Cross-aggregate there is only a **candidate** global order: `activity_state_changes.id`. It is a `BIGINT IDENTITY` primary key, so values increase globally, but the codebase does not add any stronger commit-order fence. Source: `migrations/versions/wu-002_activity_substrate.py:69-92`.
- `recorded_at` is weaker than `id` for cursoring. Audit queries already need `ORDER BY recorded_at ASC, id ASC` to stabilize correlation reads, which is a sign that `recorded_at` alone is not unique. Source: `services/api/app/repositories/audit.py:39-69`.

### Ordering risk for WU-031

The current schema does **not** prove that `activity_state_changes.id` is a safe restart cursor under concurrency. Sequence-backed IDs are monotonic, but they are not guaranteed to match commit visibility order. A projector that persists `last_processed_id = 11` after seeing row `11` can, in principle, miss a later-committing row `10` from another transaction.

That means:

- Per-aggregate causal order is confirmed.
- A single global `id` cursor is the best available ordering primitive in the schema today.
- But using `WHERE id > last_processed_id` as the only resume rule is a design risk that needs an explicit synthesis decision.

## 2. Projection pipeline design (cursor, batching, idempotency)

### Existing read-side pattern in the codebase

The repo already treats subsystem tables as projection tables. The write path mutates the domain table inside a `mutate_projection()` callback, then appends the immutable state change, then advances `aggregate_heads`; reads join back to `aggregate_heads` to recover version state. Sources:

- Generic primitive: `services/api/app/services/mutations.py:94-185`
- Applications: `services/api/app/repositories/applications.py:11-38`
- Tickets: `services/api/app/repositories/tickets.py:11-31`
- Chapters: `services/api/app/repositories/chapters.py:10-17`
- Authority grants: `services/api/app/repositories/authority.py:48-66`
- Trust profiles: `services/api/app/repositories/trust.py:12-24`

This matters for AC3: reading from `applications`, `tickets`, `permission_drift`, and similar tables is still reading from projection tables, not bypassing the write model.

### Recommended cursor table

WU-031 should introduce a single cursor row per named projection:

| Column | Recommendation | Why |
|---|---|---|
| `projection_name` | `TEXT PRIMARY KEY` | Independent progress per projection. |
| `last_processed_id` | `BIGINT NOT NULL DEFAULT 0` | Simplest global cursor shape for current schema. |
| `last_processed_at` | `TIMESTAMPTZ NULL` | Freshness/stale-since anchor. |
| `version` | `BIGINT NOT NULL DEFAULT 0` | Lets the cursor row itself use optimistic updates if needed. |

This matches the ticket’s proposed contract surface and supports multiple independent projectors. Source: `product-strategy/tickets/SLICE-017.md:21-27`, `product-strategy/tickets/SLICE-017.md:38-41`.

### Resume and batching semantics

Recommended worker loop:

1. Load cursor row for projection `P`.
2. Read a batch of events ordered by `id ASC` with `id > last_processed_id`.
3. Apply projection writes for the batch.
4. Update `read_model_cursors.last_processed_id` to the highest successfully applied event in the same transaction.
5. Commit.

That gives at-least-once delivery with transactional cursor advancement. If the batch fails, the cursor does not advance.

### Idempotency

Two idempotency strategies are available:

- For WU-031’s minimal pipeline, idempotency is trivial if the worker only updates cursor state. Re-reading an already-applied batch is harmless as long as cursor advancement and any side writes are committed together.
- For future materialized views, use deterministic upserts keyed by the projection’s natural identity. The repo already uses that pattern elsewhere, for example trust profile recompute uses `INSERT ... ON CONFLICT DO UPDATE`. Source: `services/api/app/repositories/trust.py:68-103`.

### Scheduler integration

A periodic worker tick is the best fit, not a per-event deferred effect:

- `SchedulerLoop` already runs internal recurring workers directly for archive and ticket SLA, while also running the deferred-effect queue every loop. Sources: `services/api/app/services/scheduler.py:178-191`, `services/api/app/services/scheduler.py:193-229`.
- Task runtime wiring is centralized in `app.tasks.configure_task_runtime()`. Source: `services/api/app/tasks/__init__.py:12-24`.
- Proposal text classifies read model updates as low-consequence effects that can lag and auto-retry without blocking writes. Source: `product-strategy/proposal.md:879-900`.

Recommendation: add `read_model_worker_tick()` and invoke it from the scheduler loop with a small interval gate, following the `ticket_sla_worker_tick()` pattern. Sources: `services/api/app/tasks/ticket_sla.py:10-23`, `services/api/app/services/scheduler.py:212-229`.

### Why not a deferred effect per audit event?

The closest async materialization path today is notifications: emit an event, then enqueue a safe deferred effect to materialize envelopes. Source: `services/api/app/services/notification_events.py:46-67`.

That pattern is **not** a good fit here because the audit substrate does not currently enqueue projector work on every write. Retrofitting every mutation site to emit a read-model deferred effect would be much more invasive than a periodic scanner over `activity_state_changes`.

## 3. Operational overview data sources + computation

### Recommended data sources

Use existing subsystem projection tables plus deferred-effect summaries/direct backlog queries:

| Field | Recommended source | Notes |
|---|---|---|
| `open_applications_count` | `applications` | Count non-terminal application states. |
| `open_tickets_count` | `tickets` | Count `terminal_at IS NULL`. |
| `pending_deferred_effects_count` | `deferred_effects` or a tightened summary query | Count unresolved backlog, not completed rows. |
| `permission_drift_count` | `permission_drift` | Count unresolved drift rows. |
| `stale_projections` | `read_model_cursors` + `MAX(activity_state_changes.id)` | Lag signal only. |

This stays within AC3 because the domain tables are already the official projection/read side of the evented write path. Sources: `product-strategy/tickets/SLICE-017.md:51-54`, `services/api/app/services/mutations.py:94-185`, `services/api/app/repositories/applications.py:11-38`, `services/api/app/repositories/tickets.py:11-31`.

### `open_applications_count`

The authoritative application lifecycle states are:

`submitted`, `queued`, `claimed`, `in_review`, `interview`, `waitlisted`, `approved`, `denied`, `withdrawn`.

Sources: `migrations/versions/wu-035_application_interview.py:15-41`, `services/api/app/contracts/applications.py:33-43`.

For an operational overview, the non-terminal set is:

- `submitted`
- `queued`
- `claimed`
- `in_review`
- `interview`
- `waitlisted`

Important mismatch: the chapter archive helper still counts only `submitted|queued|claimed|in_review`, which predates WU-035 and would undercount open work if copied unchanged. Source: `services/api/app/repositories/archive_queries.py:37-55`, `services/api/app/repositories/archive_queries.py:157-176`.

### `open_tickets_count`

Tickets do not use a fixed global enum for “open.” Ticket states are category-defined, and the service derives terminality from the category state machine, setting `terminal_at` when a transition enters a terminal state. Sources: `services/api/app/contracts/ticket_categories.py:32-53`, `services/api/app/services/tickets.py:152-205`.

So the correct count predicate is:

- `tickets.terminal_at IS NULL`

That is also what current chapter archive queries use. Source: `services/api/app/repositories/archive_queries.py:58-76`, `services/api/app/repositories/archive_queries.py:179-199`.

### `pending_deferred_effects_count`

Current deferred effect statuses are `queued`, `claimed`, `completed`, `failed`, `skipped`. Source: `migrations/versions/wu-008b_deferred_effect_foundation.py:17-67`, `services/api/app/contracts/scheduler.py:11-13`.

There are two existing “backlog” interpretations:

- `query_degraded_state_summary()` counts all `status <> 'completed'`, which includes `skipped`. Source: `services/api/app/repositories/deferred_effects.py:345-416`.
- Chapter archive helpers treat unresolved work as `queued|claimed|failed`. Source: `services/api/app/repositories/archive_queries.py:101-118`, `services/api/app/repositories/archive_queries.py:224-241`.

Recommendation: use `queued|claimed|failed` for `pending_deferred_effects_count`. `skipped` is no longer pending retry and will otherwise inflate the backlog signal.

### `permission_drift_count`

Drift statuses are `detected`, `acknowledged`, `reconciled`, `accepted`. Sources: `migrations/versions/wu-006b_permission_drift_foundation.py:49-52`, `services/api/app/contracts/permissions.py:175-248`.

The unresolved operational set is:

- `detected`
- `acknowledged`

The service transition graph confirms `acknowledged` is still non-terminal and can still become `reconciled` or `accepted`. Source: `services/api/app/services/permissions.py:396-494`.

### `stale_projections`

The straightforward lag signal is:

- `visible_head_id = MAX(activity_state_changes.id)`
- `lag = visible_head_id - read_model_cursors.last_processed_id`

If `lag > threshold`, include that projection in `stale_projections`. The ticket explicitly calls for this comparison. Source: `product-strategy/tickets/SLICE-017.md:49-54`.

Because the current endpoint can read live counts from subsystem projections directly, the stale signal is mainly a projection-health signal, not a reason to zero out the overview.

### Snapshot table vs direct reads

Recommendation: **do not** introduce `operational_overview_snapshot` in this slice.

Reasoning:

- The current overview fields are aggregate counts already available from first-class subsystem projections.
- A second denormalized snapshot would duplicate synchronous state, add lag, and create another stale surface without adding meaning.
- The ticket’s own contract surface only names cursor state plus the overview response; it does not require a materialized overview table. Source: `product-strategy/tickets/SLICE-017.md:21-27`, `product-strategy/tickets/SLICE-017.md:38-41`.

## 4. Scope + authority model

### Scope that exists in current data

- Applications carry first-class scope in `target_scope_kind` and `target_scope_id`, and the form snapshot also carries `target_scope`. Sources: `migrations/versions/wu-022_applications.py:26-38`, `services/api/app/contracts/applications.py:319-339`, `services/api/app/services/applications.py:293-310`.
- Tickets carry scope in `category_snapshot.routing_scope`. Sources: `services/api/app/contracts/ticket_categories.py:18-30`, `services/api/app/services/tickets.py:117-127`.
- Permission drift carries first-class `scope_kind` and `scope_id`. Sources: `migrations/versions/wu-028a_permission_drift_widening.py:34-68`, `services/api/app/contracts/permissions.py:175-248`.
- Deferred effects do **not** have first-class scope columns. Chapter-specific queries only work today where payload conventions happen to include `chapter_id`. Source: `migrations/versions/wu-008b_deferred_effect_foundation.py:17-67`, `services/api/app/repositories/archive_queries.py:101-118`.

### Recommended scope surface

The proposal explicitly calls for scope-filtered read models, including per-chapter views. Source: `product-strategy/proposal.md:851-857`.

Recommendation:

- Support `global` and `chapter` overview scope in WU-032.
- Do not add `member` scope in this slice; none of the requested overview counters are member-centric.

### Authority recommendation

Existing permission names follow a `noun.read` / `noun.write` pattern (`chapter.read`, `ticket.read`, `notification.read`, `permission_drift.read`). Sources: `services/api/app/api/v1/endpoints/chapters/base.py:139-154`, `services/api/app/api/v1/endpoints/tickets/reads.py:27-74`, `services/api/app/api/v1/endpoints/permissions/drift.py:36-78`, `migrations/versions/wu-029a_notifications.py:243-264`.

Recommendation:

- Use `operational_overview.read`, not `operations.view`.

Why:

- It matches the repo’s existing naming convention.
- It isolates overview visibility from application/ticket/drift write permissions.
- It cleanly supports both `global` and `chapter` scope checks.

Implementation pattern:

- If scope comes from query params, follow the `require_scoped()` pattern used by permission-drift endpoints. Source: `services/api/app/api/v1/endpoints/permissions/_shared.py:71-90`, `services/api/app/api/v1/endpoints/permissions/drift.py:36-78`.
- If a future route encodes scope in the path, `RequireAuthority()` is the existing fixed-scope dependency pattern. Source: `services/api/app/core/dependencies.py:56-138`.

## 5. Graceful degradation semantics (stale signal)

The product requirement is clear: read model lag must not block writes, and stale/unavailable projections must surface explicit degradation rather than silent empties. Sources: `product-strategy/tickets/SLICE-017.md:49-54`, `product-strategy/proposal.md:879-900`.

Recommended behavior:

- Authoritative writes continue exactly as they do now through synchronous `mutate_entity()` projection updates. Sources: `services/api/app/services/mutations.py:94-185`.
- The overview endpoint returns live counts from existing subsystem projection tables.
- The endpoint also returns stale metadata derived from `read_model_cursors`.
- If a projection is missing or behind threshold, return it in `stale_projections`; do **not** synthesize zero counts.

Recommended `stale_since` semantics:

- If a cursor exists, `stale_since = last_processed_at` for the stalest affected projection.
- If no cursor row exists yet and audit rows exist, synthesis must decide whether `stale_since` should be `NULL` or the oldest unprocessed event timestamp. The current schema supports either computation, but this needs one explicit rule.

This approach preserves graceful degradation: operators may lose freshness/convenience, but they do not lose data integrity or write-path availability. Source: `product-strategy/proposal.md:851-857`, `product-strategy/proposal.md:883-900`.

## 6. Schema proposals (WU-031 / WU-032)

### `migrations/versions/wu-031_read_models.py`

Recommended new table:

```sql
read_model_cursors (
    projection_name   text primary key,
    last_processed_id bigint not null default 0,
    last_processed_at timestamptz null,
    version           bigint not null default 0
)
```

Recommended indexes:

- Primary key on `projection_name` only.
- No separate index on `last_processed_id` is needed for the current access pattern.

### No snapshot table in this slice

Recommended: no `operational_overview_snapshot` table yet.

If future slices need true asynchronous cross-subsystem materialization, add dedicated projection tables then. For SLICE-017’s current field set, direct reads from existing projection tables are lower risk and more consistent with AC3.

### `services/api/app/contracts/read_models.py`

Recommended contracts:

- `ReadModelCursorRead`
  - `projection_name: str`
  - `last_processed_id: int`
  - `last_processed_at: datetime | None`
  - `version: int`

- `OperationalOverviewRead`
  - `scope_kind: Literal["global", "chapter"]`
  - `scope_id: str | None`
  - `open_applications_count: int`
  - `open_tickets_count: int`
  - `pending_deferred_effects_count: int`
  - `permission_drift_count: int`
  - `stale_projections: list[str]`
  - `stale_since: datetime | None`

## 7. Service actor for projector

Existing worker slices seed dedicated authority-grant rows for service actors such as:

- `notification-dispatcher` with `notification.read` / `notification.deliver` (`migrations/versions/wu-029a_notifications.py:243-264`)
- `permission-reconciler` with reconciliation/drift permissions (`migrations/versions/wu-028b_permission_reconciliation_runs.py:16-21`, `migrations/versions/wu-028b_permission_reconciliation_runs.py:127-163`)
- `sla-worker` with ticket/notification permissions (`migrations/versions/wu-037_ticket_sla_triggers.py:16-17`, `migrations/versions/wu-037_ticket_sla_triggers.py:96-133`)
- `chapter-archiver` with chapter-scoped worker permissions (`migrations/versions/wu-042_chapter_governance.py:165-202`)

Runtime worker code uses `ActorIdentity(actor_kind="service", actor_id=...)` for these flows. Sources: `services/api/app/tasks/archive.py:43-49`, `services/api/app/services/ticket_sla.py:500-558`.

Recommendation for WU-031:

- Service actor ID: `read-model-projector`
- Scope: `global`
- Permission set: `["read_model.write"]`

That keeps the worker aligned with existing seeded-actor conventions without giving it unrelated subsystem powers.

## 8. Open questions for synthesis

1. Is `activity_state_changes.id` acceptable as the sole resume cursor despite the commit-order race described above, or does WU-031 need a stronger watermark strategy?
2. Should chapter-scoped `pending_deferred_effects_count` be in scope now? Current `deferred_effects` rows lack first-class scope columns, so generic chapter filtering is not available.
3. Should `open_applications_count` include `interview` and `waitlisted`? The current lifecycle says yes, but the existing chapter archive helper still excludes them.
4. Should the endpoint permission be `operational_overview.read` at `global` / `chapter` scope, as recommended here, or is a different permission taxonomy already intended elsewhere?
5. How should `stale_since` behave for a projection that has never processed any event but the audit stream is already non-empty?
6. Should `pending_deferred_effects_count` exclude `skipped` by definition? The current degraded-state summary includes it, while archive backlog queries do not.

## Final Summary

- The existing event substrate gives strong per-aggregate causal order through `aggregate_seq`, but only a risky global cursor candidate through `activity_state_changes.id`; that risk is the key synthesis issue for WU-031.
- The codebase already uses synchronous subsystem projection tables plus `aggregate_heads` as its read side, so AC3 is satisfied by reading `applications`, `tickets`, `permission_drift`, and deferred-effect backlog data directly.
- `open_tickets_count` should be `terminal_at IS NULL`, and `open_applications_count` should include `interview` and `waitlisted`; copying older archive predicates would undercount work.
- A periodic scheduler tick is the least invasive projector runtime pattern; a per-event deferred effect would require much broader write-path changes.
- The lowest-risk slice shape is: add `read_model_cursors`, add a `read-model-projector` worker actor, compute overview counts from existing projection tables, and use cursor lag only for explicit stale signaling.
