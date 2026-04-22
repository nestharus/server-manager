# SLICE-017 Phase 2 Synthesis: Binding Decisions

These decisions are binding for the SLICE-017 proposal, hookpoint research,
risk, test, and implementation phases. The proposal may choose mechanics
inside these boundaries, but it must not expand scope beyond a single
`operational_overview` cursor + read-only overview endpoint, introduce a
materialized overview snapshot table, or retrofit write-path code to emit
read-model deferred effects.

## Inputs

- `.pipeline/research.md` — Phase 1 research report.
- `product-strategy/tickets/SLICE-017.md` — Acceptance Criteria (AC1–AC4),
  Work Units (WU-031, WU-032), Code Boundary.
- `AGENTS.md` — Live Server Principle, No Backwards Compatibility, No
  Deferred Stubs, Test/Code agent separation, migration discipline.
- `product-strategy/proposal.md` — Cross-cutting Concerns:
  - §Cross-workflow State Coherence (`proposal.md:843-857`): CQRS read
    model, derived from events, updated asynchronously, no authority.
  - §Graceful Degradation (`proposal.md:879-911`): CQRS lag does not block
    writes; read model updates are low-consequence deferred execution that
    auto-retry.
- Existing code in worktree:
  - `services/api/app/services/mutations.py` — `mutate_entity`, aggregate
    head + state change write path.
  - `services/api/app/services/scheduler.py` — SchedulerLoop + worker-tick
    pattern (archive, ticket SLA, deferred effects).
  - `services/api/app/tasks/ticket_sla.py` — canonical worker-tick shape.
  - `services/api/app/tasks/__init__.py` — `configure_task_runtime()`.
  - `services/api/app/repositories/applications.py`,
    `services/api/app/repositories/tickets.py`,
    `services/api/app/repositories/deferred_effects.py`,
    `services/api/app/contracts/permissions.py` — existing projection
    read surfaces.
  - `services/api/app/api/v1/endpoints/permissions/drift.py` — scoped
    `require_scoped(... "<permission>.read")` authority pattern.
  - Migration head: `wu_028b_perm_reconciliation_runs`
    (`migrations/versions/wu-028b_permission_reconciliation_runs.py:11`).

## Acceptance Criteria Reference

- **AC1**: Projector consumes audit events in causal order and resumes
  from the last persisted cursor on restart.
  (`product-strategy/tickets/SLICE-017.md:51`.)
- **AC2**: Read-model lag or worker downtime does not block authoritative
  write-path operations. (`…:52`.)
- **AC3**: Operational overview reads only from projection tables and
  deferred-effect summaries. (`…:53`.)
- **AC4**: Missing projections surface stale-data signals instead of
  silent empty results; unauthorized callers receive 403 for scoped
  views. (`…:54`.)

## Resolved Existing State

- `activity_state_changes` is the authoritative accepted-state-change
  stream with a global monotonic `id BIGINT IDENTITY`, per-aggregate
  causal `aggregate_seq`, and no commit-order watermark column.
  (`migrations/versions/wu-002_activity_substrate.py:69-112`.)
- `activity_actions` carries correlation/scope; `activity_state_changes`
  does not. Any consumer needing scope joins via `action_id`.
  (`migrations/versions/wu-003b_audit_context_columns.py:16-49`.)
- Every subsystem already maintains its own projection table that is
  written synchronously in the same transaction as the state-change row
  via `mutate_entity()` → `mutate_projection()`. Reads from
  `applications`, `tickets`, `permission_drift`, and `deferred_effects`
  therefore read from first-class projections, not from the raw event
  stream. (`services/api/app/services/mutations.py:94-185`,
  `services/api/app/repositories/applications.py:11-38`, etc.)
- `SchedulerLoop` runs internal recurring workers (archive, ticket SLA)
  with `*_INTERVAL_SECONDS` gates and `_last_*_tick_at` markers.
  (`services/api/app/services/scheduler.py:178-229`.)
- No `read_model_cursors` table, `operations` router, `read_models.py`
  contracts/services/tasks, or `operational_overview.read` permission
  currently exist in the tree.
- Current Alembic head is `wu_028b_perm_reconciliation_runs`
  (`migrations/versions/wu-028b_permission_reconciliation_runs.py:10`).

## Binding Decisions

### D1 — BINDING: Resume cursor uses `activity_state_changes.id` with a minimum-lag fence

**Decision.** The projector resumes strictly from
`read_model_cursors.last_processed_id` using `WHERE id > :cursor` against
`activity_state_changes.id`. To defend against the commit-order race
called out in research §1 (sequence-backed `id` is monotonic but not
commit-ordered), the projector applies a **minimum-age fence**: it only
considers events with `recorded_at <= now() - interval '<min_age_seconds>
seconds'`. The default is `MIN_AGE_SECONDS = 5`. Events younger than the
fence are ignored on this tick and picked up on the next tick. The
projection itself is idempotent, so any double-read remains harmless.

**Rationale.** The research report flags `id` as the best available
global ordering primitive in the current schema and identifies the
commit-order hazard as the dominant design risk (research §1, §2, §8
Q1). Three options were considered:

- *(a)* `id` + min-age fence.
- *(b)* `pg_current_snapshot()` / `pg_snapshot_xmin` — stronger but
  requires schema/query plumbing not present anywhere else in the repo.
- *(c)* Pure at-least-once with idempotent writes — acceptable on its
  own, but without a fence the cursor might jump past a still-in-flight
  txid whose `id` was already allocated, causing the later-committed
  event to be permanently skipped (not just re-read). That is not a
  duplicate risk; it is a loss risk.

Option (a) layered on (c)'s idempotency is the smallest credible design:
the fence pushes the cursor only past events whose transactions have
almost certainly committed, and idempotent projection writes absorb any
rare duplicate. This is consistent with the "low-consequence deferred
execution, auto-retry on recovery" framing in
`product-strategy/proposal.md:900`. Option (b) is rejected as
over-engineering for a slice whose only projection is the cursor row
itself (see D3). Per-aggregate cursor fan-out is rejected: it explodes
cursor rows and is unnecessary when causal order is preserved globally
by `id` + fence.

**Binding implications.**
- Projector SQL uses `WHERE id > :cursor AND recorded_at <= :fence`,
  ordered by `id ASC`, with `:fence = now - MIN_AGE_SECONDS`.
- `MIN_AGE_SECONDS` is a module-level constant in
  `services/api/app/services/read_models.py`. Tests may override via
  keyword argument on `read_model_worker_tick`.
- The projector is idempotent by construction; re-reading an already-
  advanced event is a no-op (see D3 — the only side effect is advancing
  the cursor, which is itself idempotent under `id`-max semantics).

**Non-goals.** No `pg_snapshot` / LSN / commit-order column is
introduced in this slice. No per-aggregate cursors. No serializable
isolation escalation.

### D2 — BINDING: `read_model_cursors` schema (WU-031)

**Decision.** WU-031 introduces exactly one new table in migration
`migrations/versions/wu-031_read_models.py`:

```sql
CREATE TABLE read_model_cursors (
    projection_name   TEXT        PRIMARY KEY,
    last_processed_id BIGINT      NOT NULL DEFAULT 0,
    last_processed_at TIMESTAMPTZ NULL,
    version           BIGINT      NOT NULL DEFAULT 0,
    CHECK (last_processed_id >= 0),
    CHECK (version >= 0)
);
```

The migration seeds exactly one row:

```sql
INSERT INTO read_model_cursors (projection_name)
VALUES ('operational_overview')
ON CONFLICT (projection_name) DO NOTHING;
```

**Rationale.** Matches the ticket's named contract surface
(`SLICE-017.md:22-27`) and the research recommendation
(research §2, §6). `version` supports optimistic updates if a future
projector needs concurrent workers (not required in this slice).
`last_processed_at` is the stale-since anchor referenced by AC4.

**Binding implications.**
- No separate index on `last_processed_id` — single-row-per-projection
  access pattern does not benefit.
- The seed is idempotent so re-running migrations on an existing
  cursor row does not reset progress.
- Cursor advancement uses `UPDATE … SET last_processed_id = :id,
  last_processed_at = :now, version = version + 1 WHERE
  projection_name = :name`.

**Non-goals.** No `scope_kind` / `scope_id` columns on the cursor
table. Cursors are per-projection, not per-scope. No FK to
`activity_state_changes` (cursor can legally be `0` and the referenced
row may be purged by a future archival policy).

### D3 — BINDING: Exactly one projection in scope — `operational_overview`

**Decision.** SLICE-017 ships a single cursor row,
`projection_name = 'operational_overview'`. The projection maintains
the cursor only. There is **no** materialized overview snapshot table.
Overview reads (WU-032) compute counts live from the existing subsystem
projection tables.

**Rationale.** The ticket's contract surface names only
`ReadModelCursorRead` and `OperationalOverviewRead` and does not name a
snapshot table (`SLICE-017.md:21-27`). The current overview fields are
aggregate counts already available synchronously from
`applications`, `tickets`, `deferred_effects`, and `permission_drift`
(research §3). A second denormalized snapshot would duplicate
synchronous state, add lag, and create another stale surface without
adding meaning.

**Binding implications.**
- `PROJECTION_NAMES: frozenset[str] = frozenset({"operational_overview"})`
  in `services/api/app/services/read_models.py`.
- `read_model_worker_tick` advances only the
  `operational_overview` cursor.
- Future slices may add rows to `read_model_cursors` and dedicated
  materialized projection tables; the substrate is ready.

**Non-goals.** No `operational_overview_snapshot` table. No materialized
member-history / causal-chain / scope-filtered projections in this
slice. No dashboards / leaderboards.

### D4 — BINDING: `OperationalOverviewRead` contract shape

**Decision.** `services/api/app/contracts/read_models.py` exposes:

```python
class ReadModelCursorRead(BaseModel):
    projection_name: str
    last_processed_id: int
    last_processed_at: datetime | None
    version: int


class OperationalOverviewRead(BaseModel):
    scope_kind: Literal["global", "chapter"]
    scope_id: str | None
    open_applications_count: int
    open_tickets_count: int
    pending_deferred_effects_count: int
    permission_drift_count: int
    stale_projections: list[str]
    stale_since: datetime | None
    is_stale: bool
```

Count predicates are fixed:

| Field | Predicate | Source table |
|---|---|---|
| `open_applications_count` | `status IN ('submitted','queued','claimed','in_review','interview','waitlisted')` | `applications` |
| `open_tickets_count` | `terminal_at IS NULL` | `tickets` |
| `pending_deferred_effects_count` | `status IN ('queued','claimed','failed')` | `deferred_effects` |
| `permission_drift_count` | `status IN ('detected','acknowledged')` | `permission_drift` |

Scope filtering:

- `scope_kind='global'` → no scope filter; all rows counted.
- `scope_kind='chapter'` → filter each source by chapter:
  - `applications.target_scope_kind='chapter' AND applications.target_scope_id = :scope_id`
  - `tickets` via `category_snapshot->>'routing_scope'` chapter path (per research §4)
  - `permission_drift.scope_kind='chapter' AND permission_drift.scope_id = :scope_id`
  - `deferred_effects` is **excluded** from chapter counts; the
    table has no first-class scope column (research §4). Chapter-scoped
    responses return `pending_deferred_effects_count = 0`. See D15.

**Rationale.** Predicates match the current lifecycle after WU-035
(applications) and WU-025b (tickets `terminal_at`), avoiding the
undercount bug in the older archive helper (research §3). The
`pending_deferred_effects_count` predicate matches the archive-helper
convention rather than the degraded-state summary: `skipped` effects are
no longer pending retry and would inflate the backlog signal.

The contract includes both `stale_projections: list[str]` and a derived
`is_stale: bool` for operator ergonomics. `stale_since: datetime | None`
is the cursor's `last_processed_at` when stale; `None` when fresh.

**Binding implications.**
- All four count predicates use literal tuples defined as module
  constants in `services/api/app/services/read_models.py` (no magic
  strings at query sites).
- The `Literal["global","chapter"]` scope narrowing is enforced at
  the endpoint (D9) and the service layer. No `member` scope in this
  slice.
- `stale_projections` contains the names of projections whose cursor
  meets the staleness rule (D5). With only one projection in scope,
  the list is either `[]` or `["operational_overview"]`.
- `is_stale = bool(stale_projections)`.
- `stale_since` is the cursor's `last_processed_at` when `is_stale` is
  true; `None` when fresh; `None` when the cursor has never advanced
  (see D5 resolution of research Q5).

**Non-goals.** No per-status breakdown counts. No `member` scope. No
chapter breakdown of deferred effects. No cursor-lag integer exposed as
a first-class contract field (operators get `is_stale` + `stale_since`;
debugging can hit `GET /api/v1/operations/overview?...` logs or the
cursor table directly if ever surfaced later).

### D5 — BINDING: Staleness thresholds

**Decision.** Staleness is computed from two thresholds, both module
constants in `services/api/app/services/read_models.py`:

```python
STALE_EVENT_THRESHOLD: int = 100          # events behind
STALE_TIME_THRESHOLD: timedelta = timedelta(minutes=5)
```

For each projection in `PROJECTION_NAMES`:

```
visible_head_id = MAX(activity_state_changes.id)   # may be 0 if stream empty
lag_events      = max(0, visible_head_id - cursor.last_processed_id)

is_stale =
    (lag_events > STALE_EVENT_THRESHOLD)
    OR (
        cursor.last_processed_at IS NOT NULL
        AND (now - cursor.last_processed_at) > STALE_TIME_THRESHOLD
    )
```

If `cursor.last_processed_at IS NULL` (the projection has never
advanced):

- Stream empty (`visible_head_id = 0`) → `is_stale = False`,
  `stale_since = None`.
- Stream non-empty → `is_stale = (lag_events > STALE_EVENT_THRESHOLD)`,
  `stale_since = None`. (Resolves research Q5: do **not** synthesize
  `stale_since` from the oldest unprocessed event's timestamp;
  `stale_since` is only populated from cursor state.)

`stale_since` in the response:

- If `is_stale` and `last_processed_at IS NOT NULL` →
  `stale_since = last_processed_at`.
- Else → `stale_since = None`.

**Rationale.** Two-dimensional staleness (volume + wall-clock) is
standard for cursor-based pipelines and keeps the signal meaningful
in both a burst-and-idle regime (lots of events, processor caught
up within seconds) and a steady low-volume regime (few events but
processor down for hours). Threshold values are conservative defaults
sufficient for the test harness; WU-032 tests can override by
monkeypatching the module constants.

**Binding implications.**
- Thresholds are module constants, **not** DB config or env settings
  in this slice. No new settings field.
- Threshold decisions are documented in code via the constant names;
  no comments required.
- `visible_head_id` query is `SELECT COALESCE(MAX(id), 0) FROM
  activity_state_changes` — `COALESCE` keeps the empty-stream case
  explicit and avoids `NULL` arithmetic.

**Non-goals.** No per-projection threshold overrides in this slice.
No adaptive thresholds. No alerting / paging — operators see
`is_stale` on the overview response and nothing more.

### D6 — BINDING: Projector worker contract + scheduler wiring

**Decision.** WU-031 adds:

1. `services/api/app/services/read_models.py::read_model_worker_tick(
    db: PostgresDatabase, *, now: datetime | None = None,
    min_age_seconds: int = MIN_AGE_SECONDS,
   ) -> ReadModelCursorRead`
   - Transactionally:
     1. `SELECT ... FROM read_model_cursors WHERE projection_name =
        'operational_overview' FOR UPDATE`.
     2. `SELECT COALESCE(MAX(id), cursor.last_processed_id) FROM
        activity_state_changes WHERE id > cursor.last_processed_id
        AND recorded_at <= :now - :min_age_seconds * interval '1 second'`.
     3. If the new id equals the cursor's existing id: commit with no
        update (no-op tick).
     4. Else: `UPDATE read_model_cursors SET last_processed_id = :new_id,
        last_processed_at = :now, version = version + 1 WHERE
        projection_name = 'operational_overview'`.
     5. Commit.
   - Returns the resulting `ReadModelCursorRead`.

2. `services/api/app/tasks/read_models.py::read_model_worker_tick()
    -> ReadModelCursorRead` — the thin wrapper in the
   `services/api/app/tasks/ticket_sla.py` shape, reading a
   module-configured `PostgresDatabase`, used by the scheduler.

3. `services/api/app/tasks/__init__.py::configure_task_runtime()` calls
   `configure_read_models(db=db)`.

4. `services/api/app/services/scheduler.py` gains:
   - `READ_MODEL_PROJECTOR_INTERVAL_SECONDS: int = 10`
   - `_last_read_model_tick_at: datetime | None = None`
   - `_run_read_model_projector_if_due(now)` — follows the
     `_run_ticket_sla_if_due` pattern exactly (interval gate,
     `asyncio.to_thread`, `try/except logger.exception`).
   - Invoked from `_tick` after `_run_ticket_sla_if_due`.

**Rationale.** Mirrors the existing, shipped pattern for ticket SLA
and chapter archive workers (`services/api/app/services/scheduler.py:
178-229`, `services/api/app/tasks/ticket_sla.py:1-24`). The 10s
interval is tight enough that the fence doesn't starve operator
visibility (worst-case staleness ≈ `min_age_seconds + interval ≈ 15s`)
while keeping the scheduler loop cheap.

**Binding implications.**
- The scheduler tick never raises; projector failures are logged via
  `logger.exception` and do not block other scheduler work
  (AC2 compliance — see D14).
- The service function returns the cursor row so tests can assert on
  advancement without re-querying.
- `min_age_seconds` is keyword-only on the service entry point so
  tests can push the fence to `0` to exercise immediate advancement.

**Non-goals.** No batch-size cap (the projector only updates a single
cursor row; there are no per-event writes to throttle). No retry
policy beyond the scheduler's next tick. No deferred-effect scheduling
per event. No cross-process locking — the scheduler already runs one
worker per process and `FOR UPDATE` on the single cursor row is
sufficient.

### D7 — BINDING: Authority permission is `operational_overview.read`

**Decision.** The overview endpoint requires a new permission named
`operational_overview.read`, checked via the existing
`require_scoped(actor, db, scope_kind, scope_id,
"operational_overview.read")` helper
(`services/api/app/api/v1/endpoints/permissions/_shared.py:71-90`).

- `scope_kind='global'` → requires `operational_overview.read` at the
  `global` scope.
- `scope_kind='chapter'` → requires `operational_overview.read` at the
  given `chapter` `scope_id`.

Unauthorized callers receive `HTTP 403` (AC4) via the standard
`require_scoped` refusal path.

**Rationale.** Existing permission names in the repo uniformly follow
the `noun.read` / `noun.write` pattern (`chapter.read`, `ticket.read`,
`permission_drift.read`, `notification.read`). Using
`operational_overview.read` matches that convention, isolates overview
visibility from application/ticket/drift read/write permissions, and
plugs cleanly into `require_scoped`. The prompt's suggestion of
`operations.view` is rejected in favor of repo consistency.

**Binding implications.**
- No new enum / registry entry is required — permission names in this
  repo are plain strings used at the `require_scoped` call site.
- No permission is granted to any human actor by the migration. Human
  grants are an operator-policy concern outside this slice.
- If a future slice adds a dedicated read-model service actor (D10),
  it does **not** need `operational_overview.read` — the projector
  does not read the overview; it only advances a cursor.

**Non-goals.** No `operations.*` permission namespace. No
`operational_overview.write`. No per-field authority. No UI for
granting the permission in this slice.

### D8 — BINDING: Read-only compute path (AC3)

**Decision.** `GET /api/v1/operations/overview` issues **only**
`SELECT` statements, and only against these tables/columns:

- `applications (status, target_scope_kind, target_scope_id)`
- `tickets (terminal_at, category_snapshot)`
- `deferred_effects (status)`
- `permission_drift (status, scope_kind, scope_id)`
- `read_model_cursors (projection_name, last_processed_id, last_processed_at)`
- `activity_state_changes (id, recorded_at)` — `MAX(id)` only, for the
  staleness lag calculation.

The read path never writes. It never calls `mutate_entity`,
`mutate_projection`, `advance_aggregate_head`, `append_state_change`,
or any function that produces an `activity_action` row.

**Rationale.** AC3 requires reading only from projection tables and
deferred-effect summaries. `applications`, `tickets`, and
`permission_drift` are first-class synchronous projection tables.
`deferred_effects` is a summary/backlog surface. `read_model_cursors`
+ `activity_state_changes.MAX(id)` supply the lag signal required by
AC4. Nothing else is queried.

**Binding implications.**
- Repository helpers live in
  `services/api/app/repositories/read_models.py` and expose one
  function per count plus one for the cursor snapshot. Each returns
  plain scalars / Pydantic rows — no ORM session leakage.
- The endpoint function body contains zero SQL; all SQL is in the
  repository layer.
- No joins to `aggregate_heads`, `activity_actions`, or
  `activity_state_changes` except the bounded `MAX(id)` lag query.

**Non-goals.** No caching (the overview is cheap and the staleness
signal depends on a live `MAX(id)` query). No ETag / `If-Match` on
reads. No pagination (single scalar response).

### D9 — BINDING: Endpoint surface + router registration

**Decision.** WU-032 adds:

- `services/api/app/api/v1/endpoints/operations.py`
  - `router = APIRouter(prefix="/api/v1/operations")`
  - `@router.get("/overview", response_model=OperationalOverviewRead)`
    - Query params:
      - `scope_kind: Literal["global","chapter"] = Query(...)`
      - `scope_id: str | None = Query(default=None)`
    - Validation:
      - `scope_kind='chapter'` requires `scope_id` (422 otherwise).
      - `scope_kind='global'` requires `scope_id` omitted (422
        otherwise).
      - These two validations mirror the shape used by
        `list_drift_endpoint`
        (`services/api/app/api/v1/endpoints/permissions/drift.py:47-62`).
    - Authority via `require_scoped(...)` as per D7.
    - Delegates to
      `app.services.read_models.read_operational_overview(
        db, scope_kind=scope_kind, scope_id=scope_id, now=<injected>)`.

- `services/api/app/api/v1/router.py` — include the new `operations`
  router after existing subsystem routers. No changes to middleware
  order.

**Rationale.** Matches the ticket's `GET /api/v1/operations/overview`
surface (`SLICE-017.md:27`). `Literal["global","chapter"]` narrowing in
the query signature gives FastAPI automatic 422 on unknown values, and
the cross-field validation (scope_id ↔ scope_kind) is copy-shaped with
the drift endpoint so reviewers can compare them directly.

**Binding implications.**
- No `POST`, `PUT`, or `PATCH` on `/api/v1/operations/**` in this
  slice.
- `now` is injected from `datetime.now(tz=UTC)` at the endpoint layer
  so tests can monkeypatch time.
- Error handling: known permission errors are raised as `403` via
  the `require_scoped` path; any other exception bubbles to the
  existing global handler.

**Non-goals.** No overview listing, no historical overview, no
per-subsystem endpoints under `/operations/*`. No CSV / export
format. No Discord integration in this slice
(`SLICE-017.md:29-30`).

### D10 — BINDING: Service actor + audit emission policy

**Decision.** Two linked sub-decisions:

1. **Service actor.** WU-031 seeds an authority grant for the
   projector service actor, matching the convention from
   `notification-dispatcher`, `permission-reconciler`, `sla-worker`,
   and `chapter-archiver`:

   - Actor kind: `service`
   - Actor id: `read-model-projector`
   - Scope: `global`
   - Permissions: `["read_model.write"]`

   The seed is idempotent (`ON CONFLICT DO NOTHING`) and follows the
   row shape used by `migrations/versions/wu-028b_permission_reconciliation_runs.py:127-163`.

2. **Audit emission.** The projector does **not** emit
   `activity_actions` / `activity_state_changes` rows for cursor
   advances. Cursor advancement is infrastructure bookkeeping, not a
   domain transition. Emitting an audit row per tick would flood the
   audit stream (every 10s by default).

   Consequence: `mutate_entity()` is **not** called by the projector.
   The cursor table is updated with a plain `UPDATE ... WHERE
   projection_name = 'operational_overview'` inside the worker's
   transaction. Errors are surfaced via `logger.exception` in the
   scheduler wrapper (D6).

**Rationale.** The service-actor row aligns the projector with every
other worker in the repo, so future changes (e.g., adding an authority
check to the projector, or surfacing `who advanced the cursor` in
diagnostics) have a consistent identity to reference. Skipping audit
emission keeps the event stream dedicated to domain transitions and
avoids a feedback loop where cursor advancement itself generates
events the cursor must process.

**Binding implications.**
- `AUDIT_ACTION_TYPE` / audit-action registries gain **zero** new
  entries in this slice.
- The permission name `read_model.write` is authority-side only; it
  is not referenced by any endpoint, because the projector is an
  internal worker invoked by the scheduler (not by an HTTP route).
- If a future slice grants the projector the right to write
  materialized projection rows, the existing `read_model.write`
  permission provides a stable authority name.

**Non-goals.** No audit trail of cursor advances. No
`activity_actions` rows with `actor_id='read-model-projector'` in
this slice. No Discord-side actor for the projector.

### D11 — BINDING: Constants and registries

**Decision.** The following symbols land in the tree:

- `services/api/app/services/read_models.py`:
  - `PROJECTION_NAMES: frozenset[str] = frozenset({"operational_overview"})`
  - `OPERATIONAL_OVERVIEW_PROJECTION_NAME: str = "operational_overview"`
  - `MIN_AGE_SECONDS: int = 5`
  - `STALE_EVENT_THRESHOLD: int = 100`
  - `STALE_TIME_THRESHOLD: timedelta = timedelta(minutes=5)`
  - `OPEN_APPLICATION_STATUSES: tuple[str, ...] = (
      "submitted","queued","claimed","in_review","interview","waitlisted")`
  - `PENDING_DEFERRED_EFFECT_STATUSES: tuple[str, ...] = (
      "queued","claimed","failed")`
  - `UNRESOLVED_DRIFT_STATUSES: tuple[str, ...] = (
      "detected","acknowledged")`
- `services/api/app/services/scheduler.py`:
  - `READ_MODEL_PROJECTOR_INTERVAL_SECONDS: int = 10`
- `services/api/app/api/v1/endpoints/operations.py`:
  - `OPERATIONAL_OVERVIEW_PERMISSION: str = "operational_overview.read"`

**Rationale.** Every string literal that would otherwise be repeated
across service / repository / test / endpoint code is hoisted to a
named constant. This satisfies the "no magic strings" guardrail and
keeps the staleness rule visible at the module level.

**Binding implications.**
- Tests import the same constants as production code (no shadow
  copies of status lists).
- Adding a new projection in a future slice requires adding to
  `PROJECTION_NAMES` and the cursor seed; the projector's loop
  structure already iterates `PROJECTION_NAMES` (even though the
  current set has one element).

**Non-goals.** No pydantic `Enum` for projection names (single-element
set, adding an enum is premature). No `AUDIT_ACTION_TYPE` entries
(see D10).

### D12 — BINDING: Test boundaries

**Decision.** Tests split along the WU boundary:

- **WU-031: `services/api/tests/test_read_models.py`** — projector
  pipeline only.
  - AC1-a: projector advances cursor from `0` to `MAX(id)` for a
    seeded stream of events older than `MIN_AGE_SECONDS`.
  - AC1-b: a restart simulation (new worker instance pointed at the
    same DB) resumes from the persisted cursor — events already
    processed are not re-processed in the sense of producing side
    effects; since the only side effect is cursor advancement, the
    test asserts the cursor is unchanged on a no-op tick.
  - AC1-c: cursor does **not** advance past events whose
    `recorded_at > now - MIN_AGE_SECONDS` (min-age fence).
  - AC2-a: projector failure (injected via monkeypatched service
    raising `RuntimeError`) does **not** prevent the scheduler from
    running other worker ticks in the same loop iteration.
  - AC2-b: a separate write-path test (e.g., creating a ticket)
    succeeds even when the projector is artificially halted (DB
    row-level lock on the cursor does not block domain writes —
    domain writes touch `applications`, `tickets`, etc., not
    `read_model_cursors`).
  - Idempotency: running the worker twice in succession with no new
    events is a no-op (cursor `last_processed_id` and `version`
    unchanged on the second call).
  - Cursor seed: migration upgrade creates exactly one row with
    `projection_name='operational_overview'`, `last_processed_id=0`,
    `last_processed_at IS NULL`, `version=0`.

- **WU-032: `services/api/tests/test_operational_views.py`** —
  overview endpoint only.
  - AC3-a: response counts match direct queries against
    `applications`, `tickets`, `deferred_effects`,
    `permission_drift` using the D4 predicates.
  - AC3-b: global scope aggregates across all chapters;
    chapter scope filters each source per D4 (and returns `0`
    for `pending_deferred_effects_count` per D15).
  - AC4-a: `is_stale=True` and `stale_projections=["operational_overview"]`
    when `MAX(id) - cursor.last_processed_id > STALE_EVENT_THRESHOLD`.
  - AC4-b: `is_stale=True` when `now - last_processed_at >
    STALE_TIME_THRESHOLD`.
  - AC4-c: `is_stale=False`, `stale_projections=[]`,
    `stale_since=None` on a fresh/idle stream.
  - AC4-d: `is_stale=False` when the cursor has never advanced **and**
    the stream is empty (resolved per D5).
  - AC4-e: `HTTP 403` for an actor lacking
    `operational_overview.read` at the requested scope.
  - Schema validation: `scope_kind='chapter'` without `scope_id`
    returns `422`; `scope_kind='global'` with `scope_id` returns
    `422`.

**Rationale.** Splits along the WU contract boundary stated in
`SLICE-017.md:38-41`. The test agent writes tests from contracts; the
code agent implements to make them pass (AGENTS.md §Implementation
Workflow — Test/Code Agent Separation).

**Binding implications.**
- AC2 is verified by a test that specifically exercises the
  scheduler-loop resilience, not merely the projector service in
  isolation.
- Tests monkeypatch `MIN_AGE_SECONDS`, `STALE_EVENT_THRESHOLD`,
  `STALE_TIME_THRESHOLD`, or inject `now` at the entry point rather
  than sleeping.

**Non-goals.** No Discord-side tests. No end-to-end `/operations` UI
tests. No load/perf tests for the projector.

### D13 — BINDING: Migration chain and downgrade policy

**Decision.** The WU-031 migration lands at:

- File: `migrations/versions/wu-031_read_models.py`
- `revision = "wu_031_read_models"`
- `down_revision = "wu_028b_perm_reconciliation_runs"` (current head).

The `downgrade()` body is a no-op per the Live Server Principle — the
project does not support rollback migrations in production.

**Rationale.** Confirmed head by scanning all revisions in
`migrations/versions/`: the single head is
`wu_028b_perm_reconciliation_runs`. The rollback prohibition matches
every recent migration in the tree.

**Binding implications.**
- A follow-up slice chains from `wu_031_read_models`.
- WU-032 adds no migration (read-only endpoint).

**Non-goals.** No data migration / backfill. No split into
multiple migration files.

### D14 — BINDING: Graceful degradation semantics (AC2 / AC4)

**Decision.** The overview endpoint separates two classes of
freshness:

1. **Count freshness.** The four counts
   (`open_applications_count`, `open_tickets_count`,
   `pending_deferred_effects_count`, `permission_drift_count`) are
   **always current** because they read from synchronous projection
   tables written in the same transaction as the domain mutation
   (`services/api/app/services/mutations.py:94-185`). Projector
   liveness does **not** affect these counts.

2. **Projector liveness.** The `is_stale` / `stale_projections` /
   `stale_since` fields signal only the projector's cursor lag. They
   are meaningful to operators as a *projection-health* signal — they
   do not indicate that the counts themselves are stale.

This is documented with a single module-level docstring at the top of
`services/api/app/services/read_models.py`. No inline comments on
individual fields.

**Rationale.** Required by the proposal's graceful-degradation rubric:
"CQRS read model: Cross-subsystem queries fall back to direct
AuditEntry correlation queries; slower but complete" applies **to
future materialized views**. In this slice, the counts come from the
per-subsystem synchronous projections, which are always fresh.
Surfacing the cursor lag alongside gives operators the visibility
AC4 demands without lying about data currency.

**Binding implications.**
- If the projector worker is down, writes proceed unimpeded (AC2)
  because domain writes have no dependency on `read_model_cursors`.
- The overview endpoint stays up when the projector is down; it
  returns accurate counts plus `is_stale=True`.
- Operators reading the response interpret `is_stale` as "the event
  projection pipeline is behind", not "these counts are wrong". A
  single line in the module docstring captures this contract.

**Non-goals.** No fallback path to "correlate events directly" — not
needed for the current count set, which is already sourced from
authoritative projection tables. No circuit breaker around the
projector (the scheduler's `try/except logger.exception` is the
entire resilience contract).

### D15 — BINDING: Out of scope for SLICE-017

**Decision.** The following are explicitly out of scope and must not
be added in WU-031 or WU-032:

- `operational_overview_snapshot` materialized table or any other
  materialized cross-subsystem projection.
- Additional projection cursors beyond `operational_overview`.
  (Substrate is ready; consumers add their own rows when they ship
  the consumer.)
- Chapter-scoped `pending_deferred_effects_count`. Resolved per
  research §4 and D4: `deferred_effects` has no first-class scope
  column. Chapter-scoped responses return `0` for this field. A future
  slice that adds `deferred_effects.scope_kind` / `scope_id` may
  replace the zero.
- `member` scope on the overview (research §4). Not needed by any
  AC; none of the requested counts are member-centric.
- Backpressure, retry policy, or circuit-breaker for the projector
  beyond the scheduler's existing `try/except logger.exception`.
- Any write/mutation endpoint under `/operations/**`.
- Discord-side surface for the overview
  (`SLICE-017.md:29-30`: "none in this slice").
- UI / frontend consumers. Contract-only surface.
- Audit emission for cursor advances (D10).
- Historical / time-series views of the overview.
- Operator alerting / paging when `is_stale=True`.

**Rationale.** Preserves the slice's scope statement and keeps the
WU-031/WU-032 effort inside the "M (leans M)" envelope
(`SLICE-017.md:58`).

**Binding implications.**
- Proposal, hookpoint research, risk assessment, and implementation
  phases must treat any of the above as scope creep and reject.
- If a risk agent flags absence of materialized views as a risk, the
  correct response is to cite D3/D15 rather than expand scope.

**Non-goals.** Everything above.

## Summary of Decisions

| # | Title | Scope |
|---|---|---|
| D1 | Resume cursor uses `activity_state_changes.id` with a minimum-age fence | WU-031 |
| D2 | `read_model_cursors` schema (projection_name, last_processed_id, last_processed_at, version) | WU-031 |
| D3 | Exactly one projection: `operational_overview`; no materialized snapshot | WU-031 + WU-032 |
| D4 | `OperationalOverviewRead` / `ReadModelCursorRead` contract shape + count predicates | WU-031 (contracts) + WU-032 |
| D5 | Staleness thresholds (`STALE_EVENT_THRESHOLD=100`, `STALE_TIME_THRESHOLD=5min`) and `stale_since` rule | WU-032 |
| D6 | Projector worker contract (`read_model_worker_tick`) + scheduler wiring at 10s interval | WU-031 |
| D7 | Authority permission `operational_overview.read` via `require_scoped` | WU-032 |
| D8 | Read-only compute path (SELECT-only; whitelisted tables) | WU-032 |
| D9 | Endpoint surface `GET /api/v1/operations/overview` + router registration | WU-032 |
| D10 | Service actor `read-model-projector` with `read_model.write`; no audit emission | WU-031 |
| D11 | Constants & registries (`PROJECTION_NAMES`, status tuples, interval/threshold constants) | WU-031 + WU-032 |
| D12 | Test boundaries split across `test_read_models.py` (WU-031) and `test_operational_views.py` (WU-032) | WU-031 + WU-032 |
| D13 | Migration chain: `wu_028b_perm_reconciliation_runs` → `wu_031_read_models`; downgrade no-op | WU-031 |
| D14 | Graceful degradation: counts always fresh (from synchronous projections); `is_stale` signals projector liveness only | WU-031 + WU-032 |
| D15 | Out of scope (no snapshot table, no multi-cursor, no chapter-scoped deferred effects, no `member` scope, no audit on cursor, no alerting, no Discord/UI, no history) | WU-031 + WU-032 |

## AC Traceability

- **AC1**: D1 (safe resume semantics), D2 (persisted cursor), D6 (restart via cursor load), D12 AC1-a/b/c (tests).
- **AC2**: D6 (scheduler try/except), D10 (no audit write coupling), D14 (write-path independence), D12 AC2-a/b (tests).
- **AC3**: D4 (count predicates over projection tables), D8 (SELECT-only whitelist), D12 AC3-a/b (tests).
- **AC4**: D4 (`is_stale`, `stale_projections`, `stale_since`), D5 (thresholds + `stale_since` rule), D7 (`require_scoped` → 403), D9 (422 for malformed scope args), D14 (health-signal semantics), D12 AC4-a/b/c/d/e (tests).
