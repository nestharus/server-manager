# SLICE-017 Proposal: Cross-Subsystem Operational Views

This proposal is binding for the SLICE-017 implementation and is derived
directly from `.pipeline/synthesis.md` D1–D15. Nothing here widens scope
beyond a single `operational_overview` cursor row plus a read-only
`GET /api/v1/operations/overview` endpoint. When this document refers
to a decision as "per D<N>" it is binding — the synthesis is the
authoritative source of truth and this document only describes the
mechanics inside those boundaries.

The ticket (`product-strategy/tickets/SLICE-017.md`) decomposes the
work into two work units:

| WU | Scope |
|---|---|
| WU-031 | Audit projection read-model pipeline: migration, cursor table, projector service+worker, scheduler wiring, service-actor seed. |
| WU-032 | Operational views API: read-only `GET /operations/overview` endpoint, scope validation, authority check, stale signaling. |

Migration chain is `wu_028b_perm_reconciliation_runs → wu_031_read_models`
per D13.

Acceptance criteria (AC1–AC4 from `product-strategy/tickets/SLICE-017.md:51-54`)
are referenced inline per §1.

---

## §1 — AC Mapping

Each step below names a concrete file path and a single unit of work.
Step numbers are stable and referenced from tests (§8) and §9.

### AC1 — Projector consumes audit events in causal order and resumes from the last persisted cursor on restart

1. **Cursor schema + seed (D2).** Add `read_model_cursors` with the
   exact shape in §2, including the seed of
   `('operational_overview', 0, NULL, 0)` via idempotent
   `ON CONFLICT DO NOTHING`.
   - File: `migrations/versions/wu-031_read_models.py`.
2. **Cursor contract (D4).** Define `ReadModelCursorRead` per §3.
   - File: `services/api/app/contracts/read_models.py`.
3. **Cursor repository (D6).** Implement
   `load_cursor`, `advance_cursor`, `max_event_id_settled` per §4.
   All three queries are the only ones allowed to touch
   `read_model_cursors` and `activity_state_changes.id`.
   - File: `services/api/app/repositories/read_models.py`.
4. **Projector service (D1 + D6).** Implement
   `advance_operational_overview_cursor(db, *, now, min_age_seconds)`
   per §5 step 1, using `WHERE id > :cursor AND recorded_at <= :fence`
   ordered by `id ASC`, with `fence = now − min_age_seconds`. The
   cursor row is selected `FOR UPDATE` so concurrent tick attempts
   block rather than race.
   - File: `services/api/app/services/read_models.py`.
5. **Projector worker tick (D6).** Thin wrapper
   `read_model_worker_tick()` that reads the module-configured
   `PostgresDatabase` and calls the service. Shape exactly matches
   `ticket_sla_worker_tick` (`services/api/app/tasks/ticket_sla.py:22-23`).
   - File: `services/api/app/tasks/read_models.py`.
6. **Scheduler wiring (D6).** Register the worker in
   `configure_task_runtime()` and add
   `_run_read_model_projector_if_due(now)` to `SchedulerLoop._tick`
   mirroring `_run_ticket_sla_if_due`
   (`services/api/app/services/scheduler.py:212-229`).
   Interval constant `READ_MODEL_PROJECTOR_INTERVAL_SECONDS = 10`.
   - Files: `services/api/app/tasks/__init__.py`,
     `services/api/app/services/scheduler.py`.
7. **Service actor seed (D10).** Seed an `authority_grants` row for
   `read-model-projector` with `["read_model.write"]` at global scope,
   guarded by the exact `@>` / `<@` containment pattern from
   `migrations/versions/wu-028b_permission_reconciliation_runs.py:150-161`.
   - File: `migrations/versions/wu-031_read_models.py`.

### AC2 — Read-model lag or worker downtime does not block authoritative write-path operations

1. **No write coupling (D10 + D14).** The projector only updates
   `read_model_cursors`. It never calls `mutate_entity`,
   `mutate_projection`, `append_state_change`, or
   `advance_aggregate_head`. This is enforced by review — §5
   names the only DB primitives the projector may call.
2. **Scheduler resilience (D6).** `_run_read_model_projector_if_due`
   wraps the worker in `try/except logger.exception`, exactly like
   `_run_ticket_sla_if_due` and `_run_chapter_archive_if_due`. A
   crashing tick does not halt the scheduler, does not touch other
   worker paths, and does not raise into the loop
   (`services/api/app/services/scheduler.py:212-229`).
3. **No audit emission for cursor advances (D10).** The worker
   uses a plain `UPDATE read_model_cursors ...` inside its
   transaction. `activity_actions` and `activity_state_changes`
   are read-only to the projector.

### AC3 — Operational overview reads only from projection tables and deferred-effect summaries

1. **SELECT-only whitelist (D8).** The overview endpoint is read-only.
   The repository in §4 is the only place SQL is issued, and the only
   tables/columns it may touch are the six listed in D8:
   `applications`, `tickets`, `deferred_effects`, `permission_drift`,
   `read_model_cursors`, and `activity_state_changes` (MAX(id) only).
2. **Count predicates (D4).** The four counts
   (`open_applications_count`, `open_tickets_count`,
   `pending_deferred_effects_count`, `permission_drift_count`)
   follow the exact predicates in §3 and §4, matching the current
   lifecycle after WU-035 (applications) and WU-025b (`terminal_at`).
3. **Scope filtering (D4 + D15).** Global scope applies no filter.
   Chapter scope filters `applications.target_scope_kind/scope_id`,
   `tickets.category_snapshot#>>{routing_scope,scope_kind/scope_id}`,
   and `permission_drift.scope_kind/scope_id`. Chapter-scoped
   `pending_deferred_effects_count` is hard-wired to `0` per D15
   (deferred effects have no first-class scope column; research §4).

### AC4 — Missing projections surface stale-data signals, unauthorized callers receive 403

1. **Authority gate (D7 + D9).** The endpoint calls
   `require_scoped(actor, db, scope_kind, scope_id, "operational_overview.read")`
   from `services/api/app/api/v1/endpoints/permissions/_shared.py:71-89`.
   On denial, `_shared.raise_known_permission_error` maps
   `PermissionError` to HTTP 403
   (`.../permissions/_shared.py:135-139`). We wrap the service
   call in the same try/except shape as `list_drift_endpoint`
   (`.../permissions/drift.py:63-78`).
2. **Scope shape validation (D9).** `scope_kind='chapter'` without
   `scope_id` → 422. `scope_kind='global'` with `scope_id` → 422.
   Messages match the drift endpoint wording
   (`.../permissions/drift.py:47-62`).
3. **Staleness signaling (D5 + D14).** The service computes
   `lag_events = max(0, visible_head_id − cursor.last_processed_id)`
   where `visible_head_id = COALESCE(MAX(id), 0)`, then derives
   `is_stale`, `stale_projections`, and `stale_since` per D5. The
   counts themselves are always current (sourced from synchronous
   projections) — `is_stale` signals projector liveness, not count
   invalidity. The module docstring of `services/read_models.py`
   states this contract in one line per D14.

---

## §2 — Migration Plan

### 2.1 — `migrations/versions/wu-031_read_models.py`

Alembic revision metadata (D13):

```python
revision = "wu_031_read_models"
down_revision = "wu_028b_perm_reconciliation_runs"
branch_labels = None
depends_on = None
```

`upgrade()`:

1. `CREATE TABLE read_model_cursors` per D2:

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

   No secondary index (single-row-per-projection access pattern).

2. Seed the `operational_overview` cursor row (D2):

   ```sql
   INSERT INTO read_model_cursors (projection_name)
   VALUES ('operational_overview')
   ON CONFLICT (projection_name) DO NOTHING;
   ```

3. Seed the `read-model-projector` service-actor grant (D10),
   reusing the `@>` / `<@` containment guard proven in
   `migrations/versions/wu-028b_permission_reconciliation_runs.py:127-163`.
   A module-level constant mirrors the reconciler pattern:

   ```python
   _PROJECTOR_PERMISSIONS = '["read_model.write"]'
   ```

   followed by:

   ```sql
   INSERT INTO authority_grants (
       id, grantee_id, scope_kind, scope_id, permissions,
       expires_at, revoked_at, revoked_by, revocation_reason,
       predecessor_grant_id
   )
   SELECT gen_random_uuid(),
          'read-model-projector',
          'global',
          NULL,
          '["read_model.write"]'::jsonb,
          NULL, NULL, NULL, NULL, NULL
   WHERE NOT EXISTS (
       SELECT 1 FROM authority_grants
        WHERE grantee_id = 'read-model-projector'
          AND scope_kind = 'global'
          AND scope_id IS NULL
          AND permissions @> '["read_model.write"]'::jsonb
          AND permissions <@ '["read_model.write"]'::jsonb
          AND revoked_at IS NULL
          AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
   );
   ```

   The `@>` AND `<@` pair ensures both set-containment directions —
   i.e. the existing grant's `permissions` equals
   `["read_model.write"]` exactly — preventing both duplicate insertion
   on re-run and accidental matching against a superset grant.

`downgrade()` — `pass` per D13 and the Live Server Principle
(`AGENTS.md:20-32`).

### 2.2 — No other migrations

WU-032 adds zero migrations per D13. No data backfill. No snapshot
table (D15).

---

## §3 — Contracts

### 3.1 — `services/api/app/contracts/read_models.py` (new file)

```python
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ReadModelCursorRead(BaseModel):
    projection_name: str
    last_processed_id: int
    last_processed_at: datetime | None
    version: int

    model_config = ConfigDict(frozen=True)


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

    model_config = ConfigDict(frozen=True)
```

Field names bind verbatim to D4. `frozen=True` matches the project-wide
read-model convention (contracts are immutable snapshots).

Rationale for the shape relative to the prompt's sketch: D4 is the
binding contract; it names
`open_applications_count`, `open_tickets_count`,
`pending_deferred_effects_count`, `permission_drift_count`,
`stale_projections`, and `stale_since`. The prompt's field set
(`open_applications`, `open_tickets`, `pending_deferred_effects`,
`active_drift`, `cursor_lag_events`) is superseded by D4 where they
disagree (D4 is binding per synthesis §Binding Decisions). Specifically,
no `cursor_lag_events` field is added (D4 Non-goals).

### 3.2 — Constants module

Constants live in `services/api/app/services/read_models.py` (D11) —
not the contracts module — so they are importable by both production
code and tests without pulling the service layer into the contracts
module. Contracts imports constants only if needed for a `Literal`.

```python
# services/api/app/services/read_models.py (module level)

from datetime import timedelta

OPERATIONAL_OVERVIEW_PROJECTION_NAME: str = "operational_overview"
PROJECTION_NAMES: frozenset[str] = frozenset({OPERATIONAL_OVERVIEW_PROJECTION_NAME})

MIN_AGE_SECONDS: int = 5

STALE_EVENT_THRESHOLD: int = 100
STALE_TIME_THRESHOLD: timedelta = timedelta(minutes=5)

OPEN_APPLICATION_STATES: tuple[str, ...] = (
    "submitted", "queued", "claimed", "in_review", "interview", "waitlisted",
)
PENDING_DEFERRED_EFFECT_STATUSES: tuple[str, ...] = (
    "queued", "claimed", "failed",
)
UNRESOLVED_DRIFT_STATUSES: tuple[str, ...] = ("detected", "acknowledged")
```

Notes on naming relative to the prompt:
- `OPEN_APPLICATION_STATES` (not `OPEN_APPLICATION_STATUSES`) —
  the `applications` column is literally named `state`
  (`services/api/app/repositories/applications.py:20`,
  `services/api/app/contracts/applications.py:33-43`). Using the
  DB column name avoids mismatch between the constant and the query.
- `OPEN_TICKET_STATUSES` is **not** a constant. Tickets are
  category-defined (research §3); there is no fixed status set. The
  open predicate is `tickets.terminal_at IS NULL` per D4, which
  needs no list. Diverges from the prompt's sketch intentionally —
  D4 binds on `terminal_at IS NULL`.
- `STALE_TIME_THRESHOLD` is a `timedelta` (D5), not an int seconds
  value. Tests read the same constant rather than a shadow.

All query sites reference these constants; no magic strings per D11.

---

## §4 — Repository Layer

### 4.1 — `services/api/app/repositories/read_models.py` (new file)

One function per read; no class. All functions accept a `Connection`
(or `PostgresDatabase` via `with db.connection()` at the service
layer, matching `ticket_sla.py` style).

```python
def load_cursor(
    connection, projection_name: str
) -> ReadModelCursorRead | None:
    # SELECT projection_name, last_processed_id, last_processed_at, version
    # FROM read_model_cursors
    # WHERE projection_name = %s
    # FOR UPDATE                # held only when called from the projector path
    #
    # Returns None when the row is absent (seed missing). Callers in the
    # service layer decide how to react — either raise
    # ``CursorNotSeededError`` (normal path) or let the diagnostic
    # surface through the scheduler wrapper. No auto-seed here.
    ...

def advance_cursor(
    connection,
    *,
    projection_name: str,
    last_processed_id: int,
    last_processed_at: datetime,
    expected_version: int,
) -> dict[str, Any]:
    # UPDATE read_model_cursors
    #    SET last_processed_id = %s,
    #        last_processed_at = %s,
    #        version           = version + 1
    #  WHERE projection_name = %s
    #    AND version         = %s
    # RETURNING projection_name, last_processed_id, last_processed_at, version
    # Raises CursorVersionConflictError on zero rows (OCC).
    ...

def max_event_id_settled(
    connection, *, min_age_seconds: int, after_id: int
) -> int:
    # SELECT COALESCE(MAX(id), %s) FROM activity_state_changes
    #  WHERE id > %s
    #    AND recorded_at <= CURRENT_TIMESTAMP - make_interval(secs => %s)
    # Returns after_id when no events are past the fence (no advance).
    ...

def count_open_applications(
    connection, *, scope_kind: str, scope_id: str | None
) -> int:
    # SELECT count(*) FROM applications
    #  WHERE state IN %s
    #  [AND target_scope_kind = 'chapter' AND target_scope_id = %s]
    ...

def count_open_tickets(
    connection, *, scope_kind: str, scope_id: str | None
) -> int:
    # SELECT count(*) FROM tickets
    #  WHERE terminal_at IS NULL
    #  [AND category_snapshot #>> '{routing_scope,scope_kind}' = 'chapter'
    #   AND category_snapshot #>> '{routing_scope,scope_id}' = %s]
    ...

def count_pending_deferred_effects(connection) -> int:
    # Callers for chapter scope skip this function (D15);
    # no scope filter here.
    # SELECT count(*) FROM deferred_effects
    #  WHERE status IN %s    # PENDING_DEFERRED_EFFECT_STATUSES
    ...

def count_active_drift(
    connection, *, scope_kind: str, scope_id: str | None
) -> int:
    # SELECT count(*) FROM permission_drift
    #  WHERE status IN %s    # UNRESOLVED_DRIFT_STATUSES
    #  [AND scope_kind = 'chapter' AND scope_id = %s]
    ...
```

Notes:

- `CursorVersionConflictError`: a module-level exception raised by
  `advance_cursor` when the OCC `UPDATE ... WHERE version = :expected`
  returns zero rows. The service layer catches this and treats the
  tick as a no-op (`logger.exception` in the scheduler wrapper),
  relying on the next tick to advance. The `FOR UPDATE` in
  `load_cursor` makes cross-tick contention rare; the OCC guard is
  defense-in-depth.
- `max_event_id_settled` returns `after_id` when the filtered set is
  empty so callers can compare `new_id == cursor.last_processed_id`
  for the no-op branch (D6 step 3).
- All status/state IN-lists use the §3.2 constants via psycopg tuple
  adaptation (`%s` with a tuple argument, as in
  `archive_queries.py:66-68`).

---

## §5 — Service Layer

### 5.1 — `services/api/app/services/read_models.py` (new file)

Module docstring (one line per D14):

```python
"""Read-model pipeline — counts are always fresh from synchronous
projections; ``is_stale`` signals projector liveness only."""
```

Constants per §3.2. Exceptions declared at module scope:

```python
class CursorVersionConflictError(RuntimeError): ...


class CursorNotSeededError(RuntimeError):
    """Raised when ``read_model_cursors`` is missing the seed row for a
    projection. Migration seeds the row, so this indicates infra
    misconfiguration (migration skipped, row manually deleted, etc.).
    Never auto-seed from runtime — diagnose and re-migrate instead."""


class InvalidScopeError(ValueError):
    """Raised when ``scope_kind`` and ``scope_id`` disagree — e.g.,
    ``scope_kind='chapter'`` with no ``scope_id`` or ``scope_kind='global'``
    with a non-None ``scope_id``. Enforced at the service layer so
    non-HTTP callers (CLI, future Discord surface) hit the same gate."""
```

#### 5.1.1 — `advance_operational_overview_cursor`

```python
def advance_operational_overview_cursor(
    db: PostgresDatabase,
    *,
    now: datetime,
    min_age_seconds: int = MIN_AGE_SECONDS,
) -> ReadModelCursorRead:
    with db.connection() as connection:
        with connection.transaction():
            cursor = load_cursor(
                connection,
                projection_name=OPERATIONAL_OVERVIEW_PROJECTION_NAME,
            )
            # The migration seeds the row; a None here signals infra
            # misconfiguration (migration skipped or row deleted).
            # Raise explicitly rather than silently auto-seeding.
            if cursor is None:
                raise CursorNotSeededError(
                    f"read_model_cursors missing seed for "
                    f"{OPERATIONAL_OVERVIEW_PROJECTION_NAME!r}"
                )
            new_id = max_event_id_settled(
                connection,
                min_age_seconds=min_age_seconds,
                after_id=cursor.last_processed_id,
            )
            if new_id == cursor.last_processed_id:
                return cursor  # No-op tick (D6 step 3).
            updated = advance_cursor(
                connection,
                projection_name=OPERATIONAL_OVERVIEW_PROJECTION_NAME,
                last_processed_id=new_id,
                last_processed_at=now,
                expected_version=cursor.version,
            )
            return _cursor_row_to_read(updated)
```

- `load_cursor` issues `SELECT ... FOR UPDATE` so concurrent ticks
  block (D6 step 1).
- OCC via `expected_version` is defense-in-depth per D6 "Binding
  implications" — `FOR UPDATE` alone is sufficient in the current
  single-worker scheduler, but the OCC check keeps the contract
  correct under future multi-worker scenarios.
- `now` is required (not defaulted) so tests inject a deterministic
  timestamp.
- Return type is `ReadModelCursorRead` per D6 so tests assert
  without re-querying.

#### 5.1.2 — `read_operational_overview`

```python
def read_operational_overview(
    db: PostgresDatabase,
    *,
    scope_kind: Literal["global", "chapter"],
    scope_id: str | None,
    actor: ActorIdentity,
    now: datetime,
) -> OperationalOverviewRead:
    # R1 — scope shape validation at the service layer (F8, shortcut
    # risk pin P2). Non-HTTP callers hit the same gate as the endpoint.
    if scope_kind == "global" and scope_id is not None:
        raise InvalidScopeError(
            "scope_id must be None for scope_kind='global'"
        )
    if scope_kind == "chapter" and not scope_id:
        raise InvalidScopeError(
            "scope_id is required for scope_kind='chapter'"
        )
    _require_overview_authority(db, actor, scope_kind, scope_id)
    with db.connection() as connection:
        open_applications = count_open_applications(
            connection, scope_kind=scope_kind, scope_id=scope_id,
        )
        open_tickets = count_open_tickets(
            connection, scope_kind=scope_kind, scope_id=scope_id,
        )
        pending_effects = (
            0 if scope_kind == "chapter"
            else count_pending_deferred_effects(connection)
        )
        active_drift = count_active_drift(
            connection, scope_kind=scope_kind, scope_id=scope_id,
        )
        visible_head_id = max_event_id_settled(
            connection, min_age_seconds=0, after_id=0,
        )
        cursor = load_cursor(
            connection,
            projection_name=OPERATIONAL_OVERVIEW_PROJECTION_NAME,
        )
    # R2 — explicit diagnostic surface if the migration seed is missing
    # (F12, shortcut risk pin P3). Never auto-seed outside the migration.
    if cursor is None:
        raise CursorNotSeededError(
            f"read_model_cursors missing seed for "
            f"{OPERATIONAL_OVERVIEW_PROJECTION_NAME!r}"
        )
    stale = _compute_staleness(
        cursor=cursor,
        visible_head_id=visible_head_id,
        now=now,
    )
    return OperationalOverviewRead(
        scope_kind=scope_kind,
        scope_id=scope_id,
        open_applications_count=open_applications,
        open_tickets_count=open_tickets,
        pending_deferred_effects_count=pending_effects,
        permission_drift_count=active_drift,
        stale_projections=stale.projections,
        stale_since=stale.since,
        is_stale=stale.is_stale,
    )
```

- `_require_overview_authority` centralises the authority check
  (next subsection) and raises `PermissionError` on denial; the
  endpoint layer converts that to HTTP 403 via
  `raise_known_permission_error` (D7 + §7).
- `InvalidScopeError` is raised **before** the authority check so
  malformed scope inputs do not touch the authority tables. Endpoint
  maps to HTTP 422 (§7.1).
- `CursorNotSeededError` is raised **after** reads return — the
  service has already committed to the whitelisted SELECTs; the
  cursor absence is purely a staleness/initialization diagnostic.
  Endpoint maps to HTTP 503 (§7.1) since it indicates the projector
  has never been wired up for this DB.
- The read path never opens a writable transaction; no `mutate_*`
  symbol is imported into this module (D8 guardrail).
- For global scope, `count_pending_deferred_effects` runs
  unconditionally; for chapter scope it is hard-wired to `0`
  (D15). No fallback query with partial payload-key filtering.
- Inside the `with db.connection()` block we issue reads in a single
  logical snapshot. The final `_compute_staleness` runs outside the
  connection because it does not need the DB.
- `load_cursor` here does **not** use `FOR UPDATE`. The same
  repository function is reused; `FOR UPDATE` is applied only from
  the projector path by wrapping the call inside
  `connection.transaction()`. See note at the end of §4.1 on an
  optional `lock: bool` kwarg if reviewers prefer it explicit.

#### 5.1.3 — `_require_overview_authority`

```python
_OVERVIEW_PERMISSION: str = "operational_overview.read"

def _require_overview_authority(
    db: PostgresDatabase,
    actor: ActorIdentity,
    scope_kind: str,
    scope_id: str | None,
) -> None:
    require_scoped(actor, db, scope_kind, scope_id, _OVERVIEW_PERMISSION)
```

- The import is
  `from app.api.v1.endpoints.permissions._shared import require_scoped`.
  Using the shared helper avoids duplicating the authority evaluation
  logic. If a future refactor moves `require_scoped` out of the
  endpoints package, this is the only call site in the service layer
  to update.
- Per D7, this is the single permission string for the endpoint.

#### 5.1.4 — `_compute_staleness`

```python
@dataclass(frozen=True, slots=True)
class _Stale:
    projections: list[str]
    since: datetime | None
    is_stale: bool

def _compute_staleness(
    *,
    cursor: ReadModelCursorRead,
    visible_head_id: int,
    now: datetime,
) -> _Stale:
    lag_events = max(0, visible_head_id - cursor.last_processed_id)
    by_events = lag_events > STALE_EVENT_THRESHOLD
    by_time = (
        cursor.last_processed_at is not None
        and (now - cursor.last_processed_at) > STALE_TIME_THRESHOLD
    )
    is_stale = by_events or by_time
    projections = (
        [cursor.projection_name] if is_stale else []
    )
    since = (
        cursor.last_processed_at
        if is_stale and cursor.last_processed_at is not None
        else None
    )
    return _Stale(projections=projections, since=since, is_stale=is_stale)
```

- Encodes D5 exactly. The "never advanced + empty stream" case
  (`last_processed_id == 0` and `visible_head_id == 0`) yields
  `lag_events = 0` → `by_events = False`; `last_processed_at is None`
  → `by_time = False`; so `is_stale = False` with
  `stale_since = None`, per D5 "never advanced, stream empty".
- Tests monkeypatch module constants to exercise both thresholds
  (D12).

### 5.2 — Worker-tick wrapper

`services/api/app/tasks/read_models.py` (new file):

```python
from __future__ import annotations

from datetime import UTC, datetime

from app.contracts.read_models import ReadModelCursorRead
from app.repositories.db import PostgresDatabase
from app.services.read_models import advance_operational_overview_cursor

_DB: PostgresDatabase | None = None

def configure_read_models(*, db: PostgresDatabase) -> None:
    global _DB
    _DB = db

def _get_db() -> PostgresDatabase:
    global _DB
    if _DB is None:
        _DB = PostgresDatabase()
    return _DB

def read_model_worker_tick() -> ReadModelCursorRead:
    return advance_operational_overview_cursor(
        _get_db(), now=datetime.now(tz=UTC),
    )
```

- Shape mirrors `services/api/app/tasks/ticket_sla.py:1-23` exactly.
- The wrapper never catches exceptions; the scheduler's
  `try/except logger.exception` is the resilience contract (D6).

### 5.3 — Scheduler wiring

`services/api/app/services/scheduler.py`:

1. Add module constant adjacent to the existing interval constants
   (`scheduler.py:27-32`):

   ```python
   READ_MODEL_PROJECTOR_INTERVAL_SECONDS = 10
   ```

2. Add instance state in `SchedulerLoop.__init__` beside
   `_last_ticket_sla_tick_at` / `_last_archive_tick_at`
   (`scheduler.py:143-146`):

   ```python
   self._last_read_model_tick_at: datetime | None = None
   ```

3. Add `_run_read_model_projector_if_due(now)` mirroring
   `_run_ticket_sla_if_due` (`scheduler.py:212-229`):

   ```python
   async def _run_read_model_projector_if_due(self, now: datetime) -> None:
       if (
           self._last_read_model_tick_at is not None
           and (now - self._last_read_model_tick_at).total_seconds()
           < READ_MODEL_PROJECTOR_INTERVAL_SECONDS
       ):
           return

       from app.tasks.read_models import read_model_worker_tick

       self._last_read_model_tick_at = now
       try:
           await asyncio.to_thread(read_model_worker_tick)
       except Exception:
           logger.exception(
               "read-model projector tick failed for worker %s",
               self._worker_id,
           )
   ```

4. Invoke it from `_tick` after `_run_ticket_sla_if_due`
   (`scheduler.py:191`). The projector runs last so no other worker's
   run is delayed by it. The scheduler's `except Exception:
   logger.exception(...)` wrapper also catches `CursorNotSeededError`
   (R2 / F12); the worker never auto-seeds, and the next tick logs the
   same exception again until an operator re-runs the migration.

5. Export the new constant from `scheduler.py` `__all__`
   (`scheduler.py:293-308`).

### 5.4 — Task runtime wiring

`services/api/app/tasks/__init__.py`:

```python
from app.tasks.read_models import configure_read_models

def configure_task_runtime(
    *,
    db: PostgresDatabase,
    delivery_port_factory: Callable[[], NotificationDeliveryPort] | None = None,
) -> None:
    configure_archive_worker(db=db)
    configure_notifications_materialize(db=db)
    configure_notifications_deliver(
        db=db,
        delivery_port_factory=delivery_port_factory,
    )
    configure_ticket_sla(db=db)
    configure_read_models(db=db)
```

No other registration is required; the projector is invoked directly
by `SchedulerLoop`, not via the `register_scheduler_handler` registry.

---

## §6 — Worker

Summary of the worker surface introduced above, consolidated:

- `services/api/app/tasks/read_models.py::read_model_worker_tick()`
  is the scheduler entry point. Thin; no exception handling; no
  logging. Returns `ReadModelCursorRead` so tests can assert
  directly.
- `services/api/app/services/read_models.py::advance_operational_overview_cursor`
  is the business logic, with `now` and `min_age_seconds` keyword
  parameters for test injection (D1 + D6).
- Scheduler wrapper `_run_read_model_projector_if_due` gates on the
  10-second interval, records `_last_read_model_tick_at`, and
  swallows exceptions via `logger.exception`. Crashes never propagate
  to the outer loop (AC2, D6).
- No batch size, retry policy, or backpressure (D6 Non-goals). The
  next tick retries automatically.

---

## §7 — Endpoint

### 7.1 — `services/api/app/api/v1/endpoints/operations.py` (new file)

```python
from __future__ import annotations

from datetime import UTC, datetime
from http import HTTPStatus
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.endpoints.permissions._shared import (
    get_db,
    raise_known_permission_error,
)
from app.contracts.actor import ActorIdentity
from app.contracts.read_models import OperationalOverviewRead
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.read_models import (
    CursorNotSeededError,
    InvalidScopeError,
    read_operational_overview,
)

router = APIRouter(prefix="/api/v1/operations")


@router.get("/overview", response_model=OperationalOverviewRead)
def get_operational_overview_endpoint(
    scope_kind: Literal["global", "chapter"] = Query(...),
    scope_id: str | None = Query(default=None),
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> OperationalOverviewRead:
    if scope_kind == "chapter" and scope_id is None:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={
                "code": "validation_error",
                "message": "scope_id is required when scope_kind='chapter'",
            },
        )
    if scope_kind == "global" and scope_id is not None:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={
                "code": "validation_error",
                "message": "scope_id must be omitted when scope_kind='global'",
            },
        )
    try:
        return read_operational_overview(
            db,
            scope_kind=scope_kind,
            scope_id=scope_id,
            actor=actor,
            now=datetime.now(tz=UTC),
        )
    except InvalidScopeError as error:
        # Defense-in-depth — the endpoint's pre-checks above should have
        # caught this, but a service-layer raise still maps to 422.
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"code": "validation_error", "message": str(error)},
        ) from error
    except CursorNotSeededError as error:
        # Projector seed row missing — infra misconfiguration, not a 404
        # and not a client error. 503 semantically matches "projector
        # not initialized" (shortcut risk pin P3 / F12).
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail={
                "code": "projection_not_initialized",
                "message": str(error),
            },
        ) from error
    except Exception as error:
        raise_known_permission_error(error)
```

- Validator messages match `list_drift_endpoint`
  (`.../permissions/drift.py:47-62`).
- Authority enforced inside `read_operational_overview`; on denial
  `PermissionError` → 403 via `raise_known_permission_error`
  (`.../permissions/_shared.py:135-139`).
- `InvalidScopeError` (service layer) → 422; `CursorNotSeededError`
  (service layer) → 503. Both catches sit **before** the generic
  `except Exception` so `raise_known_permission_error` only handles
  `PermissionError` and unclassified failures.
- `now` injected here so tests can override the endpoint signature
  (FastAPI dependency overrides) for wall-clock-sensitive AC4 cases.
  For tests that prefer not to mock FastAPI deps, the service-layer
  entry point is also test-friendly.
- No request body; no `If-Match` header (read-only, D8 Non-goals).

### 7.2 — Router registration

`services/api/app/api/v1/router.py` — include after the existing
subsystem routers (the current import block is alphabetical;
`operations` slots between `notifications` and `permissions`):

```python
from app.api.v1.endpoints import (
    ...,
    notifications,
    operations,           # new
    permissions,
    ...,
)

router.include_router(operations.router, tags=["operations"])
```

No middleware changes (D9).

---

## §8 — Tests

Per `AGENTS.md` §Implementation Workflow — Test/Code Agent Separation,
tests are written by a separate agent from contracts only. Every test
has a docstring naming the AC it binds to (D12).

### 8.1 — WU-031: `services/api/tests/test_read_models.py`

Fixtures:

- Reuse the existing pytest DB fixture (same pattern as
  `services/api/tests/test_ticket_sla.py`). Each test starts with the
  seed row `('operational_overview', 0, NULL, 0)` from the migration.
- Helper `_append_state_change(connection, recorded_at=...)` inserts a
  row into `activity_state_changes` with a parent `activity_actions`
  row — exactly the shape used by existing audit tests. Tests inject
  `recorded_at` so min-age behaviour is deterministic.

Tests (each with AC docstring):

1. `test_projector_advances_cursor_from_seed` — AC1.
   Seed three events with `recorded_at = now − 10s`. Call
   `advance_operational_overview_cursor(db, now=now, min_age_seconds=5)`.
   Assert `last_processed_id == MAX(id)`, `version == 1`,
   `last_processed_at == now`.

2. `test_projector_resumes_from_persisted_cursor` — AC1.
   Advance once, then call again with the same stream and
   `min_age_seconds=0` — expect no change (idempotent). Append one
   more aged event; call again — expect `last_processed_id` advances
   to the new MAX and `version` becomes 2.

3. `test_projector_does_not_advance_past_min_age_fence` — AC1.
   Insert one event with `recorded_at = now` (inside the fence).
   Call with `min_age_seconds=5`. Assert cursor unchanged.

4. `test_projector_noop_tick_when_no_new_events` — AC1 / idempotency.
   Seed cursor at MAX(id). Call twice. Assert `version` unchanged
   after both calls (the `new_id == cursor.last_processed_id` branch
   in §5 step 3).

5. `test_projector_failure_does_not_halt_scheduler` — AC2.
   Monkeypatch `advance_operational_overview_cursor` to raise
   `RuntimeError`. Drive `SchedulerLoop._tick` once. Assert
   `logger.exception` observed, no raise out of `_tick`, and the
   next worker branch (e.g. `ticket_sla_worker_tick`) still runs.
   Pattern mirrors existing ticket-SLA resilience tests.

6. `test_write_path_unblocked_when_projector_halted` — AC2.
   Acquire a row lock on `read_model_cursors` (simulate a wedged
   projector). In a separate connection, perform a domain write
   (create an application via the public API or service). Assert
   the write commits and the projection row is updated in the same
   transaction. Proves domain writes have no dependency on
   `read_model_cursors` (D14).

7. `test_cursor_seed_present_after_migration` — AC1.
   Query `read_model_cursors` after fixture setup. Assert exactly
   one row with `projection_name='operational_overview'`,
   `last_processed_id=0`, `last_processed_at IS NULL`, `version=0`.

8. `test_projector_service_actor_grant_seeded` — D10.
   Query `authority_grants` for `grantee_id='read-model-projector'`.
   Assert a single active row at global scope with permissions
   exactly `["read_model.write"]`.

9. `test_projector_raises_cursor_not_seeded_when_row_missing` — R2 / F12.
   `DELETE FROM read_model_cursors WHERE projection_name =
   'operational_overview'`, then call
   `advance_operational_overview_cursor(db, now=now)`. Assert
   `CursorNotSeededError` is raised with the projection name in the
   message. No row is (auto-)inserted as a side-effect.

10. `test_scheduler_logs_cursor_not_seeded_without_halting` — R2 / AC2.
    Same setup as 9, but drive `SchedulerLoop._tick`. Assert
    `logger.exception` observed, no raise out of `_tick`, and the
    next scheduler branch still runs. Proves `CursorNotSeededError`
    flows through the same resilience gate as any other tick
    exception.

### 8.2 — WU-032: `services/api/tests/test_operational_views.py`

Fixtures:

- `httpx.AsyncClient` against the FastAPI app with a real DB (same
  pattern as `test_permission_drift.py`).
- Helpers to seed actors with/without `operational_overview.read` at
  global and chapter scopes, reusing existing authority fixtures.
- Helpers to seed applications, tickets, permission-drift rows, and
  deferred effects.

Tests (each with AC docstring):

1. `test_global_overview_returns_counts_from_projections` — AC3.
   Seed N applications in various states, M tickets with
   `terminal_at IS NULL` and K with `terminal_at` set, deferred
   effects across the full status set, and drift rows across the
   full status set. Assert
   `open_applications_count == count(state IN OPEN_APPLICATION_STATES)`,
   `open_tickets_count == M`, `pending_deferred_effects_count ==
   count(status IN PENDING_DEFERRED_EFFECT_STATUSES)`,
   `permission_drift_count == count(status IN UNRESOLVED_DRIFT_STATUSES)`.

2. `test_chapter_overview_filters_counts_to_chapter` — AC3.
   Seed rows for chapter A, chapter B, and global-scope where
   applicable. GET with `scope_kind=chapter&scope_id=A`. Assert only
   chapter A is counted for applications, tickets, and drift.

3. `test_chapter_overview_deferred_effects_count_is_zero` — AC3 / D15.
   Seed pending deferred effects. GET with
   `scope_kind=chapter&scope_id=A`. Assert
   `pending_deferred_effects_count == 0`.

4. `test_overview_stale_when_lag_exceeds_event_threshold` — AC4.
   Seed > `STALE_EVENT_THRESHOLD` events (monkeypatch the constant
   down to make the test fast). Leave cursor at 0. GET. Assert
   `is_stale=True`, `stale_projections=["operational_overview"]`,
   `stale_since=None` (cursor never advanced).

5. `test_overview_stale_when_last_processed_at_exceeds_time_threshold`
   — AC4. Advance cursor with `last_processed_at = now − 10min`
   (monkeypatch `STALE_TIME_THRESHOLD` to 5min). GET. Assert
   `is_stale=True`, `stale_projections=["operational_overview"]`,
   `stale_since == last_processed_at`.

6. `test_overview_fresh_stream_is_not_stale` — AC4.
   Advance cursor with `last_processed_at = now`. Insert zero new
   events. GET. Assert `is_stale=False`, `stale_projections=[]`,
   `stale_since=None`.

7. `test_overview_empty_stream_never_advanced_is_not_stale` — AC4 / D5.
   Fresh DB. Cursor at 0, `last_processed_at IS NULL`. Stream empty.
   GET. Assert `is_stale=False`, `stale_since=None`.

8. `test_overview_rejects_unauthorized_caller_with_403` — AC4.
   Actor without `operational_overview.read`. GET with
   `scope_kind=global`. Assert HTTP 403, body
   `{"code":"authority_decision_denied", ...}`.

9. `test_overview_rejects_chapter_scope_without_scope_id_422` — D9.
   GET `?scope_kind=chapter`. Assert HTTP 422,
   `"scope_id is required when scope_kind='chapter'"`.

10. `test_overview_rejects_global_scope_with_scope_id_422` — D9.
    GET `?scope_kind=global&scope_id=X`. Assert HTTP 422,
    `"scope_id must be omitted when scope_kind='global'"`.

11. `test_overview_response_shape_matches_contract` — D4.
    Validate the response against `OperationalOverviewRead` fields
    and types. Catches accidental renames or extra fields.

12. `test_service_rejects_chapter_scope_without_scope_id` — R1 / F8.
    Call `read_operational_overview(db, scope_kind='chapter',
    scope_id=None, actor=authorized_actor, now=now)` directly
    (bypassing the endpoint). Assert `InvalidScopeError` is raised
    **before** `_require_overview_authority` (authority tables are
    not queried). Complements endpoint test 9 by proving non-HTTP
    callers hit the same gate.

13. `test_service_rejects_global_scope_with_scope_id` — R1 / F8.
    Symmetric to 12 with `scope_kind='global', scope_id='chapter-A'`.
    Assert `InvalidScopeError`.

14. `test_overview_returns_503_when_cursor_not_seeded` — R2 / F12.
    `DELETE FROM read_model_cursors WHERE projection_name =
    'operational_overview'`. GET `/operations/overview?scope_kind=global`
    as an authorized actor. Assert HTTP 503, body
    `{"code":"projection_not_initialized", ...}`. Proves the endpoint
    maps `CursorNotSeededError` to 503, not 500.

---

## §9 — Authority Permission

Per D7, the permission name is `operational_overview.read`. The
repo does not maintain a central permission registry — permissions
are plain strings used at `require_scoped` call sites (D7 Binding
implications).

Concretely:

1. **No enum or registry mutation.** A grep of the codebase confirms
   permission strings like `permission_drift.read` and
   `ticket.read` are used as literal arguments to `require_scoped`
   and never declared in a central enum
   (`.../permissions/drift.py:65`, `tickets/reads.py:27-74`).
   Adding `operational_overview.read` only requires using it at the
   one call site in §5.1.3.

2. **No human-operator grant seeded by this migration.** Per the
   SLICE-014 precedent, migrations only seed service-actor grants.
   Human grants are issued at runtime via the authority API and are
   an operator-policy concern outside this slice
   (D7 Binding implications).

3. **Service-actor grant is scoped to `read_model.write`, not
   `operational_overview.read`.** The projector updates the cursor
   table; it does not read the overview. The two permission names
   are intentionally distinct (D10 Binding implications).

4. **Tests cover the authority decision.** §8.2 test 8 asserts 403
   for a caller without the permission; tests that exercise the
   happy path seed the grant in the fixture.

---

## §10 — Constants

All constants required by this slice are collected in one location —
`services/api/app/services/read_models.py` — except for interval
(in `scheduler.py` per D11) and the contract-layer `Literal` values.

No magic strings at query sites, no magic strings at test sites.
Tests import the same constants as production code (D11 Binding
implications).

Listing per D11 (reproduced for completeness):

- `OPERATIONAL_OVERVIEW_PROJECTION_NAME: str = "operational_overview"`
- `PROJECTION_NAMES: frozenset[str] = frozenset({OPERATIONAL_OVERVIEW_PROJECTION_NAME})`
- `MIN_AGE_SECONDS: int = 5`
- `STALE_EVENT_THRESHOLD: int = 100`
- `STALE_TIME_THRESHOLD: timedelta = timedelta(minutes=5)`
- `OPEN_APPLICATION_STATES: tuple[str, ...] = ("submitted", "queued", "claimed", "in_review", "interview", "waitlisted")`
- `PENDING_DEFERRED_EFFECT_STATUSES: tuple[str, ...] = ("queued", "claimed", "failed")`
- `UNRESOLVED_DRIFT_STATUSES: tuple[str, ...] = ("detected", "acknowledged")`
- `scheduler.READ_MODEL_PROJECTOR_INTERVAL_SECONDS: int = 10`

Permission name literal lives at the one call site in §5.1.3 as a
module-level constant:

- `services/api/app/services/read_models.py::_OVERVIEW_PERMISSION: str = "operational_overview.read"`

---

## §11 — Out of Scope (Explicit)

Per D15, the following are explicitly out of scope for WU-031 and
WU-032 and must **not** be added:

- `operational_overview_snapshot` or any other materialized
  cross-subsystem projection table.
- Additional projection cursors beyond `operational_overview`.
  The substrate supports adding rows to `read_model_cursors` in
  future slices; none are seeded here.
- Chapter-scoped `pending_deferred_effects_count`.
  `deferred_effects` has no first-class scope column; chapter
  responses return `0` for this field. A future slice that adds
  `deferred_effects.scope_kind` / `scope_id` may replace the zero.
- `member` scope on the overview. No AC requires it, and none of
  the requested counts are member-centric.
- Historical / time-series views of the overview.
- Cursor-lag integer as a first-class response field. Operators get
  `is_stale` + `stale_since`; debugging can hit the
  `read_model_cursors` table directly.
- Audit emission for cursor advances
  (`activity_actions` / `activity_state_changes` rows authored by
  `read-model-projector`). Cursor advancement is infrastructure
  bookkeeping, not a domain transition (D10).
- Retry policy / backpressure / circuit breaker for the projector
  beyond `try/except logger.exception`.
- Any write / mutation endpoint under `/operations/**`.
- Discord-side surface for the overview
  (`SLICE-017.md:29-30`: "none in this slice").
- UI / frontend consumers. Contract-only surface this slice.
- Operator alerting / paging when `is_stale=True`.
- Pagination, ETag, caching on the overview endpoint (D8 Non-goals).

---

## Guardrails

- **D1–D15 bound.** Every mechanic above cites the binding decision
  it implements. Scope expansion requires amending the synthesis,
  not the proposal.
- **Read-only endpoint.** `GET /api/v1/operations/overview` issues
  only `SELECT` statements; the service and repository modules do
  not import `mutate_entity`, `mutate_projection`,
  `append_state_change`, or `advance_aggregate_head` (D8).
- **No audit emission for cursor advances.** The projector uses a
  plain `UPDATE read_model_cursors ...` (D10).
- **Migration downgrade no-op.** Per Live Server Principle (D13).
- **Per-test AC docstring.** Every test in §8 states which AC it
  binds to (D12).
- **No backwards-compatibility shims.** No feature flags, no dual
  paths, no transitional aliases (`AGENTS.md:564-575`).
- **No deferred stubs.** Everything described here is implemented
  in this slice; nothing is left as `TODO`
  (`AGENTS.md:579-583`).

---

## AC Traceability

- **AC1** — §1 AC1 steps 1–6; §2.1 migration; §4 `load_cursor`,
  `advance_cursor`, `max_event_id_settled`; §5.1.1
  `advance_operational_overview_cursor`; §8.1 tests 1–4, 7, 9.
- **AC2** — §1 AC2 steps 1–3; §5.3 scheduler `try/except`; §8.1
  tests 5–6, 10; §11 (no retry policy beyond the scheduler).
- **AC3** — §1 AC3 steps 1–3; §4 count functions; §5.1.2
  `read_operational_overview`; §8.2 tests 1–3, 11.
- **AC4** — §1 AC4 steps 1–3; §5.1.3 authority gate; §5.1.4
  `_compute_staleness`; §7 endpoint with scope validation; §8.2
  tests 4–10, 12–14.

---

## Revision Log

### Revision 1 — 2026-04-21

Applied MEDIUM pins from `plans/risk/slice-017-shortcut.md` (F8, F12).
No scope expansion; both changes sit inside existing D4/D6/D9
boundaries.

| # | Pin | Change | Sections touched |
|---|-----|--------|------------------|
| R1 | F8 (shortcut risk pin P2) | Add service-layer `InvalidScopeError` raised at the top of `read_operational_overview` for `scope_kind='global' with scope_id` and `scope_kind='chapter' without scope_id`. Endpoint maps to 422 (defense-in-depth alongside the existing endpoint-layer pre-check). | §5.1 exceptions, §5.1.2 service body + notes, §7.1 endpoint imports + exception mapping, §8.2 tests 12–13. |
| R2 | F12 (shortcut risk pin P3) | `load_cursor` now returns `ReadModelCursorRead \| None`; `advance_operational_overview_cursor` and `read_operational_overview` raise `CursorNotSeededError` when the seed row is missing. Scheduler resilience wrapper catches + logs (next tick retries until the migration is re-run). Endpoint maps to 503 (`projection_not_initialized`). No auto-seed outside migration. | §4.1 `load_cursor` signature, §5.1 exceptions, §5.1.1 projector, §5.1.2 read path + notes, §5.3 scheduler note, §7.1 endpoint imports + exception mapping, §8.1 tests 9–10, §8.2 test 14, AC Traceability (AC1/AC2/AC4). |

Scope finding F1 (from `plans/risk/slice-017-scope.md`) and audit
findings 1–3 (from `plans/risk/slice-017-audit.md`) are LOW and
require no proposal revision — they are all inherited conventions
expressly sanctioned by synthesis D6 / D9 / D10.
