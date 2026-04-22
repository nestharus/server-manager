# SLICE-020 Phase 2 Synthesis: Binding Decisions

These decisions are binding for the SLICE-020 proposal, hookpoint research,
risk, test, and implementation phases. The proposal may choose mechanics
inside these boundaries, but it must not expand scope beyond the
renewal API (WU-038A) and the expiry worker + manual trigger (WU-038B),
reshape the existing `permission_intent` / `permission_drift` aggregates,
or introduce a parallel audit namespace for renewal/expiry.

## Inputs

- `.pipeline/research.md` — Phase 1 research report.
- `product-strategy/tickets/SLICE-020.md` — Acceptance Criteria (AC1–AC4),
  Work Units (WU-038A, WU-038B), Code Boundary.
- `AGENTS.md` — Live Server Principle, No Backwards Compatibility,
  migration discipline, Test/Code Agent separation.
- `product-strategy/proposal.md` — Permission Management →
  PermissionIntent temporary lifecycle
  (`proposal.md:523`, `proposal.md:530`, `proposal.md:746`).
- Existing code in worktree:
  - `services/api/app/contracts/permissions.py` — intent/drift/reconciliation
    contracts.
  - `services/api/app/services/permissions.py` — `create_permission_intent`,
    `update_permission_intent`, `_require_scoped_authority`, dispatch
    constants.
  - `services/api/app/services/mutations.py` — `mutate_entity` OCC + audit
    emission contract.
  - `services/api/app/services/scheduler.py` — `SchedulerLoop` + worker-tick
    pattern (archive, ticket SLA, read models).
  - `services/api/app/tasks/ticket_sla.py`,
    `services/api/app/tasks/read_models.py`,
    `services/api/app/tasks/__init__.py` — task-wrapper shape and
    `configure_task_runtime()`.
  - `services/api/app/api/v1/endpoints/permissions/intents.py`,
    `services/api/app/api/v1/endpoints/permissions/_shared.py` —
    scoped authority, OCC via strong `If-Match`, 412 mapping.
  - `services/api/app/services/permission_reconciliation.py` —
    drift row shapes (mismatched / intent-only / orphan) and the fact
    that reconciliation excludes expired intents.
  - `migrations/versions/wu-028b_permission_reconciliation_runs.py` —
    service-actor seed shape precedent.
  - Migration head: `wu_031_read_models`
    (`migrations/versions/wu-031_read_models.py:11`).

## Acceptance Criteria Reference

- **AC1**: Renewing a temporary intent with the current version updates
  `expires_at`, while stale renewal returns 412 Precondition Failed.
  (`product-strategy/tickets/SLICE-020.md:52`.)
- **AC2**: Renewal is rejected for non-temporary intents. (`…:53`.)
- **AC3**: The expiry worker creates drift entries for expired temporary
  intents and remains idempotent on rerun. (`…:54`.)
- **AC4**: Expired intents flow through the stable reconciliation path
  instead of mutating Discord-managed state inline. (`…:55`.)

## Resolved Existing State

- `permission_intents` already carries `temporary BOOLEAN NOT NULL`,
  `expires_at TIMESTAMPTZ NULL`, the `permission_intents_temporary_shape_valid`
  check, and the partial `expires_at` index for temporary rows only
  (research §1). There is no `expired_at` column.
- `PermissionIntentRead` / `PermissionIntentCreate` already enforce the
  temporary/`expires_at` shape; `PermissionIntentUpdate` is a partial
  patch re-validated via `validated_update()` (research §1).
- There is no dedicated renewal endpoint or worker: the permissions API
  exposes only `intents`, `drift`, and `reconciliation` routers
  (`services/api/app/api/v1/endpoints/permissions/__init__.py`).
- `update_permission_intent()` hard-codes `action_type="permission_intent.update"`
  and `change_type="permission_intent.updated"`
  (`services/api/app/services/permissions.py:275-289`). It does not
  block updates to already-expired intents.
- `permission_drift` can already encode a standalone (non-reconciliation)
  finding with `permission_intent_id`, `intent_version`, scope, target,
  nullable `reconciliation_run_id`, actual/intended masks, and `status`
  (research §4).
- Reconciliation deliberately excludes expired intents
  (`permission_reconciliation.py:460-466`), so expired temporary
  overrides have no current drift surface.
- `SchedulerLoop` runs internal periodic workers (archive, ticket SLA,
  read-model projector) with `*_INTERVAL_SECONDS` constants and
  `_last_*_tick_at` markers (`services/api/app/services/scheduler.py`).
- Task wrappers follow a fixed shape (`configure_*`, `get_*_db`,
  `*_worker_tick()`) wired from `configure_task_runtime()`
  (`services/api/app/tasks/__init__.py`).
- Service-actor seeding inside migrations is the established pattern
  (`migrations/versions/wu-028b_permission_reconciliation_runs.py:127-163`,
  `migrations/versions/wu-031_read_models.py`,
  `migrations/versions/wu-037_ticket_sla_triggers.py`).
- Current Alembic head is `wu_031_read_models`
  (`migrations/versions/wu-031_read_models.py:11`).

## Binding Decisions

### D1 — BINDING: `expired_at` column on `permission_intents`

**Decision.** Add `expired_at TIMESTAMPTZ NULL` to `permission_intents`
in a new migration `migrations/versions/wu-038_permission_intent_expiry.py`.
`expired_at` is set exclusively by the expiry worker when it records
drift. It is the idempotency key for the worker:

```sql
SELECT ...
FROM permission_intents
WHERE temporary = TRUE
  AND expires_at <= :now
  AND expired_at IS NULL
FOR UPDATE SKIP LOCKED
LIMIT :batch_size;
```

A CHECK constraint `permission_intents_expired_at_valid` enforces
`expired_at IS NULL OR expired_at >= expires_at` — an intent cannot be
marked expired before its own scheduled expiration.

**Rationale.** Research §3 and §5 show that standalone expiry drift has
no built-in dedupe key today and that `expired_at` is the cleanest
fit-to-substrate. Using `expired_at IS NULL` as the scheduling filter
makes exactly-once semantics structural rather than a side-effect of
drift-row uniqueness (which is keyed to reconciliation runs and would
not help standalone expiry drift).

**Binding implications.**
- No changes to the existing `permission_intents_temporary_shape_valid`
  check. The new check is orthogonal.
- Contract + repository plumbing surfaces `expired_at` (see D10, and
  the repository `SELECT`s in `repositories/permissions.py`).
- The partial `expires_at` index already in `wu-006a` is sufficient;
  no new index is added in this slice (the worker's filter is
  `temporary=TRUE AND expires_at<=now AND expired_at IS NULL`, for
  which the existing partial index already narrows rows efficiently).

**Non-goals.** No `expired_by_kind` / `expired_by_id` columns. No
dedicated `expired_reason` column. No separate "expiry batch id"
column. No column rename or widening of `expires_at`.

### D2 — BINDING: Renewal semantics (WU-038A)

**Decision.** Add a new endpoint:

```
POST /api/v1/permission-intents/{intent_id}/renew
Headers: If-Match: "<strong-etag>"
Body:    PermissionIntentRenewalRequest
Response: PermissionIntentRead (ETag header set to new version)
```

`PermissionIntentRenewalRequest` lives in
`services/api/app/contracts/permissions.py` and is shaped:

```python
class PermissionIntentRenewalRequest(_PermissionModel):
    expires_at: datetime
    reason: str = Field(min_length=1)
```

Validators (Pydantic):
- `expires_at` must be timezone-aware and strictly in the future at
  request time (`AwareDatetime` treatment; `value > now()`). Server
  clock `now()` is the reference.
- `reason` is non-blank after `strip()` (mirrors
  `PermissionDriftResolutionRequest.reject_blank_reason`).

Service-layer policy (in `renew_permission_intent()` in
`services/api/app/services/permissions.py`):
1. Fetch current intent by `intent_id`. If absent →
   `PermissionIntentNotFoundError` → 404.
2. Scoped authority check: `_require_scoped_authority(
   "permission_intent.write", …)` against the current intent's
   `scope_kind` / `scope_id` (see D3).
3. If `current.temporary is False` → raise
   `NonTemporaryIntentRenewalError` → 422.
4. If `current.expired_at is not None` **or**
   `current.expires_at <= now` → raise `ExpiredIntentRenewalError`
   → 422. Operator must re-create.
5. Build patch `{ "expires_at": new_expires_at }` and re-validate
   via `validated_update(current, patch)`.
6. Persist via `mutate_entity(...)` with
   `action_type="permission_intent.renew"` and
   `change_type="permission_intent.renewed"`,
   `payload_allowlist=INTENT_RENEW_PAYLOAD_ALLOWLIST` (D12).

OCC is enforced by `mutate_entity`'s expected-version check; stale
`If-Match` → 412, consistent with existing intent write paths.

**Rationale.** AC1 (`SLICE-020.md:52`) and AC2 (`…:53`) are the first
two acceptance gates; both require a renewal-specific surface. Research
§2 confirms that the existing update helper hard-codes the `update`
verbs and that "renew active only" is a new policy, not currently
enforced. Introducing a dedicated service function plus renewal-specific
error classes keeps `update_permission_intent()` unchanged and avoids
overloading `PermissionIntentUpdate`. `reason` is required because
renewal is an explicit operator action that must be audit-legible
(proposal.md:530: "every permission override should be attributable to
an intent and explainable on review").

**Binding implications.**
- Two new exception classes in
  `services/api/app/contracts/permissions.py`:
  - `NonTemporaryIntentRenewalError(Exception)` — 422, code
    `non_temporary_intent`.
  - `ExpiredIntentRenewalError(Exception)` — 422, code
    `expired_intent`.
- `raise_known_permission_error` in `permissions/_shared.py` maps
  each to 422 with the above error codes.
- Renewal does **not** change the intent's `temporary` flag; the
  intent stays temporary with a new `expires_at`. `expired_at`
  remains NULL by construction (renewal of non-expired intents only).
- The endpoint is added in a new file
  `services/api/app/api/v1/endpoints/permissions/temporary.py`
  (per the ticket's WU-038A code boundary), and its router is
  included by `services/api/app/api/v1/endpoints/permissions/__init__.py`.
- The endpoint requires strong `If-Match`; missing/weak ETag → 428/412
  via the existing `parse_if_match_strong` helper.

**Non-goals.** No bulk renewal endpoint (D15). No renewal that also
rewrites `permission_bits` / `allow_bits` / `deny_bits` (those go
through the existing `PATCH` update path). No renewal that flips
`temporary`. No soft renewal (e.g., "extend by N days"); the caller
supplies an absolute `expires_at`.

### D3 — BINDING: Authority for renewal reuses `permission_intent.write`

**Decision.** Renewal requires `permission_intent.write` at the
intent's existing scope, enforced via
`_require_scoped_authority("permission_intent.write", …)` inside
`renew_permission_intent()`. No new permission name is introduced.

**Rationale.** Research §2 confirms the repo's
`permission_intent.write` already governs create and update on intents
and that there is no separate renewal permission. Renewal is an update
to an existing intent's lifecycle, not a privilege-escalating action,
so splitting the authority namespace would add friction without
governance value. SLICE-014 R5 established the service-layer
`_require_scoped_authority` call-before-mutate pattern; we inherit it.

**Binding implications.**
- Seed data does not need a new human permission.
- The `permission-expirer` service actor (D7) requires
  `permission_intent.write` so its `mutate_entity` path succeeds.
- Authority is checked at service layer; the endpoint also calls
  `require_scoped(...)` prior to service entry, matching the current
  intents router shape (belt-and-braces, consistent with intents.py).

**Non-goals.** No `permission_intent.renew` permission name. No
per-field authority on renewal. No scope upgrade (renewal cannot be
used to change scope; scope is immutable on intents).

### D4 — BINDING: Expiry worker (WU-038B)

**Decision.** A new module
`services/api/app/tasks/permission_expiry.py` exposes:

```python
def configure_permission_expiry(*, db: PostgresDatabase) -> None: ...
def get_permission_expiry_db() -> PostgresDatabase: ...
def permission_expiry_worker_tick(
    *, now: datetime | None = None, batch_size: int | None = None,
) -> PermissionExpirySweepResult: ...
```

The tick's core logic lives in
`services/api/app/services/permissions.py::expire_temporary_permission_intents(
    db, *, actor, now, batch_size,
) -> PermissionExpirySweepResult`.

Per tick:

1. Open a DB connection. Load a batch of candidate intents with
   `SELECT … FROM permission_intents
       WHERE temporary = TRUE
         AND expires_at <= :now
         AND expired_at IS NULL
       FOR UPDATE SKIP LOCKED
       LIMIT :batch_size`.
2. For each candidate, in a fresh transaction (per-intent tx so one
   failure does not abort the batch):
   a. Stamp `expired_at = :now` via `mutate_entity(
      aggregate_type="permission_intent", …,
      action_type="permission_intent.expire",
      change_type="permission_intent.expired", …)`.
      `payload_allowlist = INTENT_EXPIRE_PAYLOAD_ALLOWLIST` (D12).
   b. Create a drift row via `mutate_entity(
      aggregate_type="permission_drift", …,
      action_type="permission_drift.detect_expired",
      change_type="permission_drift.detected", …)`, with the shape
      defined in D9.
   c. Commit tx. Advance to next candidate.
3. Catch per-intent exceptions: log via `logger.exception`, skip the
   intent, continue the batch. Mirrors the resilience shape of
   `ticket_sla_worker_tick`.
4. Return a `PermissionExpirySweepResult` summarizing the sweep (see
   D5 contract).

The service function uses a fixed service actor
(`ActorIdentity(actor_kind="service", actor_id="permission-expirer")`),
consistent with `sla-worker` / `chapter-archiver` / `read-model-projector`
precedents.

**Rationale.** Research §3, §5, and §7 map this worker directly onto the
existing scheduler/task patterns. `FOR UPDATE SKIP LOCKED` is Postgres
idiom for non-blocking job-queue claim semantics and is the minimum
mechanism required for concurrent-safe batched expiry. Per-intent
transactions honor AGENTS.md's preference for resilient workers that do
not abort batches on a single bad row.

**Binding implications.**
- Scheduler wiring (D8) calls this tick on an interval gate.
- `mutate_entity` emits audit rows for both the intent update and the
  drift creation — operators see the expiry as a first-class domain
  action.
- `batch_size` defaults to `PERMISSION_EXPIRY_BATCH_SIZE` (D6); keyword
  override exists for tests.
- `now` is keyword-injectable at the service entry point; the task
  wrapper resolves `datetime.now(tz=UTC)` unless injected.

**Non-goals.** No per-chapter fan-out (global worker, shared pool).
No parallelism inside one tick (single-threaded batch loop). No
notification emission (see D15). No Discord mutation (see AC4 and
D9).

### D5 — BINDING: Manual expiry trigger endpoint

**Decision.** Expose a synchronous operator trigger:

```
POST /api/v1/permission-intents/expire/run
Response: PermissionExpirySweepResult (200)
```

`PermissionExpirySweepResult` lives in
`services/api/app/contracts/permissions.py`:

```python
class PermissionExpirySweepResult(_PermissionModel):
    expired_intent_ids: list[UUID]
    drift_ids: list[UUID]
    inspected_count: int
    expired_count: int
    errored_count: int
```

Policy:
- Authority: `permission_intent.write` at **global** scope
  (operator-level). Enforced via
  `require_scoped(actor, db, "global", None, "permission_intent.write")`
  at the endpoint and a matching `_require_scoped_authority` call at
  service entry.
- `originating_actor` for the audit path is the caller
  (`actor` from `get_current_actor`); the worker actor is only used
  when the scheduler runs the sweep. The endpoint delegates to the
  same `expire_temporary_permission_intents()` service with the
  caller-supplied actor, so operator-triggered expiries are audit-
  attributable per the proposal's accountability principle.
- The sweep is spoof-proof: the service never accepts an
  `originating_actor_kind` / `originating_actor_id` from the request
  body. The actor is always taken from the session. This mirrors
  SLICE-021's pattern and avoids the CodeRabbit-flagged spoof class.
- Batch size for the manual run is the same
  `PERMISSION_EXPIRY_BATCH_SIZE` default, keyword-overridable in tests
  only.

**Rationale.** Ticket contract line `POST /api/v1/permission-intents/expire/run`
(`SLICE-020.md:27`) is binding. Operator-level authority is appropriate:
this is a global sweep, not scoped. Proposal.md:530 requires every
override to be attributable; returning the sweep result ensures the
operator has a direct, reviewable artifact.

**Binding implications.**
- No request body — the endpoint takes zero body params (avoids
  spoofable originating-actor inputs).
- 200 OK with the sweep result on success; known permission errors
  mapped via `raise_known_permission_error` (403 for authority
  failures).
- The endpoint file is `services/api/app/api/v1/endpoints/permissions/temporary.py`
  (shared with WU-038A renewal).

**Non-goals.** No `scope_kind` / `scope_id` filtering on the manual
sweep. No dry-run mode. No `Content-Type` other than JSON on
response. No async job handle.

### D6 — BINDING: Batch size + scheduler interval

**Decision.** Module-level constants:

```python
# services/api/app/tasks/permission_expiry.py
PERMISSION_EXPIRY_BATCH_SIZE: int = 50
# services/api/app/services/scheduler.py
PERMISSION_EXPIRY_INTERVAL_SECONDS: int = 60
```

`FOR UPDATE SKIP LOCKED` on the candidate SELECT guarantees that
concurrent sweeps (scheduler + manual run) never double-process the
same intent; per-tick batching bounds the work each wake-up does.

**Rationale.** 50 rows per tick at 60-second intervals yields a
sustained drain rate of ~3000 intents/minute, far above the expected
steady-state temporary-override volume, while keeping per-tick latency
bounded. Values match the operational order-of-magnitude used by
other scheduler workers (read-model projector = 10s; ticket SLA = 60s;
archive = 300s).

**Binding implications.**
- Constants are importable by tests; tests monkeypatch via
  `monkeypatch.setattr(tasks.permission_expiry, "PERMISSION_EXPIRY_BATCH_SIZE", ...)`.
- `batch_size` is keyword-only on the service entry so the manual
  sweep can be exercised without relying on scheduler wiring.
- Scheduler gate follows the shipped `_last_*_tick_at` + interval
  pattern from `scheduler.py`.

**Non-goals.** No env-var override (not needed in this slice; values
are code-level). No adaptive batch sizing. No per-scope interval.

### D7 — BINDING: `permission-expirer` service actor

**Decision.** The new migration seeds an authority grant for the
expiry worker:

- Actor kind: `service`
- Actor id: `permission-expirer`
- Scope: `global`
- Permissions: `["permission_intent.write", "permission_drift.write"]`

The seed follows the row shape used by
`migrations/versions/wu-028b_permission_reconciliation_runs.py:127-163`:
idempotent `ON CONFLICT DO NOTHING`, `@>` AND `<@` containment for
permission arrays, `expires_at IS NULL`, `revoked_at IS NULL`.

**Rationale.** Research §6 identifies the exact permissions needed:
`permission_intent.write` to stamp `expired_at` via `mutate_entity`,
and `permission_drift.write` because the worker also creates drift
rows via `mutate_entity` (the drift creation path is authority-checked
at the service layer — see D9). No `permission_intent.read` is needed
because the worker uses a direct repository query, not
`list_permission_intents()`.

**Binding implications.**
- The actor id `permission-expirer` is a module constant in
  `services/api/app/tasks/permission_expiry.py` (no magic strings).
- Manual trigger endpoint does **not** use this service actor — it
  uses the caller's actor (D5).
- If a future slice adds read-path authority on expiry, the service
  actor gains `permission_intent.read` at that time, not now.

**Non-goals.** No per-scope service-actor grants (global is
sufficient; expiry is intent-scoped but authority is checked against
the intent's scope at mutate time). No separate Discord-side actor.

### D8 — BINDING: Scheduler integration

**Decision.** `services/api/app/services/scheduler.py` gains:

- `PERMISSION_EXPIRY_INTERVAL_SECONDS: int = 60`
- `_last_permission_expiry_tick_at: datetime | None = None`
- `_run_permission_expiry_if_due(now)` — follows
  `_run_ticket_sla_if_due` exactly (interval gate,
  `asyncio.to_thread`, `try/except logger.exception`).
- Invoked from `_tick()` after the existing workers.

`services/api/app/tasks/__init__.py::configure_task_runtime()` calls
`configure_permission_expiry(db=db)`.

**Rationale.** Research §3 and §7 map the worker onto the shipped
pattern: interval constant, tick guard, `asyncio.to_thread` to keep
the blocking DB call out of the event loop, and an exception barrier
so projector/SLA/archive ticks continue to fire if the expiry tick
raises.

**Binding implications.**
- Scheduler never raises; any worker failure is captured via
  `logger.exception` and surfaces in logs (matches existing
  resilience contract).
- The tick is single-instance per process; `FOR UPDATE SKIP LOCKED`
  handles multi-instance safety (D6, D4).
- No new `asyncio` primitives beyond the existing scheduler shape.

**Non-goals.** No cron-expression scheduling (fixed interval only).
No scheduler-level backpressure (batch size is the only rate limit).

### D9 — BINDING: Drift row shape for expired intents

**Decision.** The expiry worker creates a drift row per expired
intent with the following field bindings:

| Field | Value |
|---|---|
| `id` | fresh UUID |
| `permission_intent_id` | expired intent id |
| `intent_version` | expired intent's current aggregate version |
| `scope_kind`, `scope_id` | mirror intent |
| `role_id`, `channel_id`, `kind` | mirror intent |
| `reconciliation_run_id` | **NULL** (not a reconciliation sweep) |
| `intended_bits` | intent's `permission_bits` if `kind='guild_role'`, else NULL |
| `intended_allow_bits` / `intended_deny_bits` | intent's `allow_bits` / `deny_bits` if `kind='channel_role'`, else NULL |
| `actual_bits` / `actual_allow_bits` / `actual_deny_bits` | **NULL** |
| `status` | `'detected'` |
| `detected_at` | `:now` |
| `resolved_*` | NULL (detected drift has no resolution metadata) |

Semantic reading: "the system intended this permission to apply;
Discord's live state is unknown; an operator must reconcile or
accept." `actual_*` being NULL is **required** and differs from
reconciliation-generated drift (which populates `actual_*` from the
snapshot). Research §4 confirms the substrate already allows NULL
actuals for standalone drift.

**Database-level constraint review:** the existing
`permission_drift_resolution_shape_valid` check only constrains
`status` and `resolved_*` fields — it does not require `actual_*` to
be populated. No new CHECK is needed. The
`PermissionDriftRead.validate_intent_anchor` validator is already
satisfied because both `permission_intent_id` and `intent_version`
are populated.

Drift creation is routed through
`services/api/app/services/permissions.py::create_expiry_drift(
    db, *, intent, actor, now) -> PermissionDriftRead` which:
1. Calls `_require_scoped_authority("permission_drift.write", …)`
   against the intent's scope.
2. Calls `mutate_entity(
   aggregate_type="permission_drift", …,
   action_type="permission_drift.detect_expired",
   change_type="permission_drift.detected", …)`.

Operator resolution paths are unchanged:
- `reconcile` → operator triggers reconciliation (existing flow) which
  populates `actual_*` from Discord and resolves the drift.
- `accept` → operator acknowledges the permission should remain and
  must create a new (non-temporary or newly scoped) intent if they
  want it re-intended.

**Rationale.** AC3 (`SLICE-020.md:54`) and AC4 (`…:55`) demand a
stable, reviewable surface rather than silent mutation or inline
Discord writes. Research §4 shows the drift schema already supports
this shape. NULL-`actual_*` drift is the only honest encoding: the
expiry worker does **not** know Discord's live state, and fabricating
zeroed actuals would claim knowledge the system doesn't have.

**Binding implications.**
- The drift row's idempotency is delegated to the intent's `expired_at`
  filter (D1). A second worker tick against the same intent never
  even selects the candidate, so no duplicate drift row is created.
- If a drift row for an expired intent already exists from a prior
  reconciliation (unlikely because reconciliation excludes expired
  intents today — research §3), the expiry worker still creates its
  own standalone row; the two are distinguishable by
  `reconciliation_run_id` NULL vs. non-NULL.
- `action_type="permission_drift.detect_expired"` is a new verb in the
  audit namespace (see D12); it is not the same as
  `"permission_drift.detect"` used by reconciliation, so audit
  filters can separate expiry drift from reconciliation drift.

**Non-goals.** No new `drift.reason` / `drift.type` column. No new
`drift.status` value (stays `'detected'`). No automatic reconciliation
triggered from the expiry worker (D15). No change to existing
reconciliation drift shapes.

### D10 — BINDING: Contract additions

**Decision.** `services/api/app/contracts/permissions.py` gains:

- `PermissionIntentRenewalRequest` (D2 shape).
- `PermissionExpirySweepResult` (D5 shape).
- `NonTemporaryIntentRenewalError`, `ExpiredIntentRenewalError` (D2).
- `expired_at: datetime | None = None` field on `_PermissionIntentBase`
  (propagates to `PermissionIntentRead` variants, so Read responses
  expose the expiry stamp for operator audit trails).

Update-side (`PermissionIntentUpdate`) is **not** widened with
`expired_at`. The only writer of `expired_at` is the expiry service
path, which builds the patch internally. Widening the update contract
would let operators poke `expired_at` directly, violating the
"lifecycle-managed, not metadata" framing in proposal.md:523.

Temporal-shape validator (`validate_temporal_shape`) is not changed:
the rule "`temporary` requires `expires_at`; `temporary=False` forbids
`expires_at`" still holds. `expired_at` is orthogonal to that rule.
A read-side cross-field validator is added to `_PermissionIntentBase`:

```python
@model_validator(mode="after")
def validate_expired_shape(self) -> "_PermissionIntentBase":
    if self.expired_at is not None and self.expires_at is None:
        raise ValueError("expired_at requires expires_at")
    if self.expired_at is not None and self.expired_at < self.expires_at:
        raise ValueError("expired_at cannot precede expires_at")
    return self
```

This mirrors the DB CHECK from D1 at the contract layer, keeping the
Pydantic model and Postgres constraint in lockstep.

**Rationale.** Principle 13 (Derived State Transparency) requires
operator-visible lifecycle state. Exposing `expired_at` on reads turns
"is this intent expired?" into a first-class field instead of a
computation against wall-clock time. Keeping the update contract
narrow (no `expired_at` write path) keeps lifecycle state under
domain control.

**Binding implications.**
- `services/api/app/repositories/permissions.py` SELECT / INSERT /
  UPDATE helpers round-trip `expired_at`.
- JSON responses from `GET /api/v1/permission-intents/**` include
  `expired_at`. Test harnesses assert on both `expires_at` and
  `expired_at`.
- No renaming of existing fields.

**Non-goals.** No separate `PermissionIntentExpiredRead` model. No
synthetic `is_expired` / `is_active` computed fields (operators compute
from `expires_at` + `expired_at` + `now()`). No `expired_at` on
`PermissionIntentCreate` (create always starts with `expired_at=NULL`).

### D11 — BINDING: Implicit state model for permission_intent

**Decision.** `permission_intent` does **not** gain a `status` column
in this slice. Its lifecycle state is derived:

- *active*: `temporary=FALSE` OR
  (`temporary=TRUE` AND `expires_at > now()` AND `expired_at IS NULL`).
- *expired*: `temporary=TRUE` AND
  (`expired_at IS NOT NULL` OR `expires_at <= now()`).
- *renewed* is not a persistent state; it's an audit verb
  (`permission_intent.renewed`) that advances the aggregate version
  and moves `expires_at` forward. The intent remains *active*.

Validation lives at service layer:
- Renewal service path (D2) rejects expired intents.
- Expiry worker (D4) rejects already-expired intents via the
  `expired_at IS NULL` filter.

No `VALID_INTENT_TRANSITIONS` constant is declared because there is
no enum column to transition between.

**Rationale.** Research §3 shows the substrate has no status column and
the existing drift status enum is the only finite-state machine in the
permissions namespace. Introducing `permission_intent.status` would
duplicate state already expressible via two existing columns and would
require rewriting every read path. The implicit model is sufficient
for AC1/AC2/AC3/AC4 because every gate is a service-layer query, not
an FSM transition.

**Binding implications.**
- Operators who want "active temporary intents" list use the existing
  `GET /api/v1/permission-intents?temporary=true&include_expired=false`
  filter (already shipped — research §1).
- Future slices may add a `status` column if new states (e.g.,
  "superseded", "revoked") emerge. This slice does not foreclose that.

**Non-goals.** No `status` enum. No state-machine transition table.
No `renewed` audit row bookkeeping beyond the single audit verb.

### D12 — BINDING: Constants and registries

**Decision.** The following symbols land in the tree:

- `services/api/app/services/permissions.py`:
  - `INTENT_RENEW_PAYLOAD_ALLOWLIST: set[str] = {"expires_at", "reason"}`
  - `INTENT_EXPIRE_PAYLOAD_ALLOWLIST: set[str] = {"expired_at"}`
  - `EXPIRY_DRIFT_DETECT_PAYLOAD_ALLOWLIST: set[str] = {
      "permission_intent_id", "intent_version", "scope_kind",
      "scope_id", "role_id", "channel_id", "kind",
      "intended_bits", "intended_allow_bits", "intended_deny_bits",
      "status", "detected_at"
    }`
  - `PERMISSION_EXPIRER_ACTOR_ID: str = "permission-expirer"`
- `services/api/app/tasks/permission_expiry.py`:
  - `PERMISSION_EXPIRY_BATCH_SIZE: int = 50`
- `services/api/app/services/scheduler.py`:
  - `PERMISSION_EXPIRY_INTERVAL_SECONDS: int = 60`

New audit verbs (plain strings used at `mutate_entity` call sites, no
central registry exists for these in the repo today):

| Action type | Change type |
|---|---|
| `permission_intent.renew` | `permission_intent.renewed` |
| `permission_intent.expire` | `permission_intent.expired` |
| `permission_drift.detect_expired` | `permission_drift.detected` |

Allowlists scope the audit payload per call site. Renewal emits
`{"expires_at", "reason"}`; expiry emits `{"expired_at"}`; drift
creation emits the drift-shape allowlist above. No free-form JSON
flows into the audit stream.

**Rationale.** Guardrail: no magic strings. Every literal repeated
across service / repository / test / endpoint code is hoisted to a
named constant. Audit verbs are new because SLICE-014 shipped only
`permission_intent.update` (research §2 open question Q4), and
merging renewal/expiry into `update`/`updated` would break audit-
filter queries that operators rely on to distinguish renewal from
edit.

**Binding implications.**
- Tests import the same constants as production code (no shadow
  copies).
- The reuse of `permission_drift.detected` (change type) across
  reconciliation and expiry is intentional: the row *is* detected
  drift. The distinction lives in `action_type` (`detect` vs.
  `detect_expired`).

**Non-goals.** No pydantic enums wrapping these verbs. No new
registries in `AUDIT_ACTION_TYPE` enums (the repo uses plain strings
at call sites). No centralized audit-verb module introduction in
this slice.

### D13 — BINDING: Migration chain and downgrade policy

**Decision.** The WU-038 migration:

- File: `migrations/versions/wu-038_permission_intent_expiry.py`
- `revision = "wu_038_permission_intent_expiry"`
- `down_revision = "wu_031_read_models"` (current head confirmed by
  scanning `migrations/versions/` — the only head is
  `wu_031_read_models`).
- Upgrade does:
  1. `ALTER TABLE permission_intents ADD COLUMN expired_at TIMESTAMPTZ NULL`.
  2. `ALTER TABLE permission_intents ADD CONSTRAINT
      permission_intents_expired_at_valid
      CHECK (expired_at IS NULL OR expired_at >= expires_at)`.
  3. Seed `permission-expirer` service actor grants (D7).
- Downgrade is a **no-op** per the Live Server Principle — the
  project does not support rollback migrations in production.

**Rationale.** Migration head `wu_031_read_models` confirmed by
inspection. No-op downgrade matches every recent migration in the
tree.

**Binding implications.**
- A follow-up slice chains from `wu_038_permission_intent_expiry`.
- WU-038A (renewal API) adds no migration. WU-038B (worker) shares
  the same migration (single file for the slice).

**Non-goals.** No data migration / backfill. The new column defaults
to NULL, matching the current state of every existing row. No
split into multiple migration files.

### D14 — BINDING: Test boundaries

**Decision.** Tests split along the WU boundary stated in
`SLICE-020.md:41-42`:

- **WU-038A: `services/api/tests/test_permission_temporary_api.py`** —
  renewal endpoint only.
  - AC1-a: renew a temporary intent with current `If-Match` advances
    `expires_at` and aggregate version, returns 200 + new ETag, emits
    `permission_intent.renew` audit row with allowlisted payload.
  - AC1-b: renew with stale `If-Match` returns 412.
  - AC2-a: renew a non-temporary intent returns 422 with code
    `non_temporary_intent`.
  - Renew an expired intent (`expires_at <= now()`) returns 422 with
    code `expired_intent`.
  - Renew an intent with `expired_at IS NOT NULL` returns 422 with
    code `expired_intent`.
  - Renew with past `expires_at` returns 422 (Pydantic validator).
  - Renew with blank / whitespace-only `reason` returns 422.
  - Authority: 403 when actor lacks `permission_intent.write` at the
    intent's scope.
  - Response includes `expired_at: null` on the renewed intent.

- **WU-038B: `services/api/tests/test_permission_temporary_worker.py`** —
  worker + manual trigger endpoint.
  - AC3-a: worker marks expired temporary intents with `expired_at`
    and creates one drift row per expired intent with the D9 shape.
  - AC3-b: running the worker again is idempotent — no second
    `expired_at` write, no second drift row (verified via count
    assertions on `permission_intents` and `permission_drift`).
  - AC3-c: non-temporary intents with no `expires_at` are never
    selected.
  - AC3-d: temporary intents with `expires_at > now()` are not
    selected.
  - AC3-e: already-expired intents (`expired_at IS NOT NULL`) are
    not re-selected.
  - AC4-a: drift rows have `permission_intent_id` set, `intent_version`
    set, `actual_*` fields NULL, `reconciliation_run_id` NULL,
    `intended_*` mirroring intent mask, `status='detected'`.
  - AC4-b: drift is discoverable via
    `GET /api/v1/permission-drift?scope_kind=…` (scope-bound query
    returns the expiry drift alongside reconciliation drift).
  - AC4-c: drift is resolvable via the existing
    `POST /api/v1/permission-drift/{id}/resolve` flows
    (acknowledge / reconcile / accept).
  - Concurrency: two sweeps run against overlapping candidates via
    `FOR UPDATE SKIP LOCKED` — no duplicate drift, total
    expired_count equals the candidate set.
  - Batching: a candidate set larger than
    `PERMISSION_EXPIRY_BATCH_SIZE` drains across multiple ticks; no
    candidate is processed twice.
  - Resilience: a synthetic per-intent failure (monkeypatched service
    raising in the middle of a batch) does not abort the batch; the
    remaining intents still expire; the failing intent remains
    un-expired and is retried on the next tick.
  - Manual trigger: `POST /api/v1/permission-intents/expire/run`
    returns `PermissionExpirySweepResult` with accurate counts and
    drift ids; authority requires `permission_intent.write` at
    **global** scope (403 otherwise).
  - Audit emission: one `permission_intent.expire` action per
    expired intent and one `permission_drift.detect_expired` action
    per drift row, both with allowlisted payloads.

**Rationale.** Splits along the WU contract boundary (`SLICE-020.md:41-42`).
The test agent writes tests from contracts; the code agent implements to
make them pass (AGENTS.md §Implementation Workflow — Test/Code Agent
Separation).

**Binding implications.**
- AC1 / AC2 are verified in `test_permission_temporary_api.py`.
- AC3 / AC4 are verified in `test_permission_temporary_worker.py`.
- Tests inject `now` at service entry points rather than sleeping;
  they monkeypatch `PERMISSION_EXPIRY_BATCH_SIZE` to exercise
  multi-batch drains.

**Non-goals.** No end-to-end Discord tests (AC4 says "through the
stable reconciliation adapter" — reconciliation is the Discord
surface, not this slice). No load/perf tests for the worker.

### D15 — BINDING: Out of scope for SLICE-020

**Decision.** The following are explicitly out of scope and must not
be added in WU-038A or WU-038B:

- Auto-reconciliation of expired intents against Discord
  (research §3: would require triggering a reconciliation run from
  within the expiry worker). Operators trigger reconciliation via the
  existing flow.
- Expiry notifications / alerts via SLICE-015 consumer hooks.
- Time-travel / historical views of past expiries.
- Bulk renewal endpoint.
- Scope-filtered expiry (e.g., "expire only chapter X"). The worker
  is global.
- `scope_kind='chapter'` authority on the manual trigger endpoint
  (D5 fixes global).
- Backpressure / circuit-breaker around the worker beyond the
  scheduler's `try/except logger.exception` (resilience is per-intent,
  not per-batch).
- `permission_intent.status` column / FSM (D11).
- Widening `PermissionIntentUpdate` with `expired_at` (D10).
- Reconciliation-run-scoped dedupe for expiry drift
  (research §3 identifies this as a bad fit; expiry drift carries
  `reconciliation_run_id = NULL`).
- UI / frontend consumers. Contract-only surface.
- Any new permission namespace (`permission_intent.renew`,
  `permission_intent.expire` as **permissions** — D3 binds to
  `permission_intent.write`).

**Rationale.** Preserves the slice's scope statement and keeps the
WU-038A/WU-038B effort inside the "M-L (leans M)" envelope
(`SLICE-020.md:59`).

**Binding implications.**
- Proposal, hookpoint research, risk assessment, and implementation
  phases must treat any of the above as scope creep and reject.
- If a risk agent flags absence of auto-reconciliation as a risk, the
  correct response is to cite D9 (stable review surface) and D15
  rather than expand scope.

**Non-goals.** Everything above.

## Summary of Decisions

| # | Title | Scope |
|---|---|---|
| D1  | `expired_at` column on `permission_intents` + CHECK | WU-038B (migration) |
| D2  | Renewal endpoint + `PermissionIntentRenewalRequest` + error classes + policy | WU-038A |
| D3  | Authority for renewal reuses `permission_intent.write` | WU-038A + WU-038B |
| D4  | Expiry worker contract (`permission_expiry_worker_tick`) + per-intent tx + `FOR UPDATE SKIP LOCKED` | WU-038B |
| D5  | Manual trigger endpoint `POST /api/v1/permission-intents/expire/run` + `PermissionExpirySweepResult` + spoof-proof actor | WU-038B |
| D6  | Batch size 50 / interval 60s constants | WU-038B |
| D7  | `permission-expirer` service actor seeded in migration | WU-038B (migration) |
| D8  | Scheduler wiring (`PERMISSION_EXPIRY_INTERVAL_SECONDS`, `_run_permission_expiry_if_due`) | WU-038B |
| D9  | Drift row shape for expired intents (NULL actuals, linked via `permission_intent_id`) | WU-038B |
| D10 | Contract additions (`expired_at` on Read, renewal request, sweep result, renewal errors); update not widened | WU-038A + WU-038B |
| D11 | Implicit state model — no `permission_intent.status` column | WU-038A + WU-038B |
| D12 | Constants & payload allowlists; new audit verbs `permission_intent.renew`/`.expire`, `permission_drift.detect_expired` | WU-038A + WU-038B |
| D13 | Migration chain `wu_031_read_models → wu_038_permission_intent_expiry`; downgrade no-op | WU-038B |
| D14 | Test boundaries split across `test_permission_temporary_api.py` (WU-038A) and `test_permission_temporary_worker.py` (WU-038B) | WU-038A + WU-038B |
| D15 | Out of scope: auto-reconciliation, notifications, history, bulk renewal, chapter-scoped expiry, status column, update-widening | WU-038A + WU-038B |

## AC Traceability

- **AC1** (renew advances `expires_at`; stale → 412):
  D2 (policy + `mutate_entity` OCC), D10 (request/read contracts),
  D12 (`permission_intent.renew`/`.renewed` verbs),
  D14 AC1-a/b (tests).
- **AC2** (renewal rejected for non-temporary intents):
  D2 (`NonTemporaryIntentRenewalError` → 422),
  D10 (`NonTemporaryIntentRenewalError` export),
  D14 AC2-a (tests).
- **AC3** (worker creates drift + remains idempotent):
  D1 (`expired_at` as idempotency key),
  D4 (worker contract, `FOR UPDATE SKIP LOCKED`, per-intent tx),
  D9 (drift shape),
  D14 AC3-a/b/c/d/e (tests).
- **AC4** (expired intents flow through stable reconciliation path,
  not inline Discord mutation):
  D4 (no Discord calls in the worker),
  D9 (drift row as the review surface; `reconcile` resolution path
  uses the existing reconciliation flow),
  D11 (no inline state mutation beyond `expired_at` bookkeeping),
  D14 AC4-a/b/c (tests).
