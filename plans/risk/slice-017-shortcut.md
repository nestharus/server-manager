# SLICE-017 Shortcut Risk Assessment

**Rating: LOW**

## Scope

Reviewed `.pipeline/proposal.md` (including Revision 1 — 2026-04-21,
pins R1/R2), `.pipeline/synthesis.md` (D1–D15), `.pipeline/research.md`,
`product-strategy/tickets/SLICE-017.md`, and `AGENTS.md` ("No Backwards
Compatibility", "No Deferred Stubs", Live Server Principle,
Test/Code Agent Separation) against the fourteen shortcut-focus items
named by the orchestrator. Verified cited patterns against live code:

- `services/api/app/tasks/ticket_sla.py:1-23` — canonical worker-tick
  shape (no catch at wrapper; scheduler catches).
- `services/api/app/services/scheduler.py:200-229` — archive + ticket-SLA
  `try/except logger.exception` resilience contract.
- `migrations/versions/wu-028b_permission_reconciliation_runs.py:127-163`
  — service-actor grant seed (`@>` AND `<@` containment) pattern.

## Revision-1 status

Revision 1 of the proposal already closed the two MEDIUM pins this role
raised in its prior pass (focus items F8 and F12). Concretely:

| Prior pin | Closure | Proposal anchors |
|---|---|---|
| P2 (F8) — service-layer scope shape validation missing | R1 adds `InvalidScopeError` at the top of `read_operational_overview`, raised **before** `_require_overview_authority` so authority tables are not queried on malformed input. Endpoint catches and maps to 422 as defense-in-depth. | §5.1 exceptions; §5.1.2 lines 514-521; §7.1 lines 854-860; §8.2 tests 12–13. |
| P3 (F12) — missing `None`-guard on `load_cursor` | R2 changes `load_cursor` to `ReadModelCursorRead \| None`; `advance_operational_overview_cursor` and `read_operational_overview` raise `CursorNotSeededError`. Scheduler's `try/except logger.exception` catches it so the loop survives. Endpoint maps to HTTP 503 (`projection_not_initialized`). No auto-seed anywhere outside the migration. | §4.1 signature; §5.1 exceptions; §5.1.1 lines 468-472; §5.1.2 lines 546-550; §5.3 note lines 740-742; §7.1 lines 861-871; §8.1 tests 9–10; §8.2 test 14. |

No further proposal revision is required. The twelve remaining findings
are LOW and consistent with shipped worker-tick / authority conventions.

---

## Findings

### F1. Cursor advance uses OCC (`expected_version`) — LOW

Proposal §4 `advance_cursor` issues
`UPDATE ... WHERE projection_name = %s AND version = %s RETURNING ...`
and raises `CursorVersionConflictError` on zero rows
(proposal.md:341-357). §5.1.1 `advance_operational_overview_cursor`
reads `cursor.version` inside a `SELECT ... FOR UPDATE` and passes it
as `expected_version` (proposal.md:480-486). D6 Binding implications
(synthesis.md:386-400) name this as defense-in-depth over the row-level
lock — the OCC predicate remains correct under a hypothetical
multi-worker scheduler. No silent swallow: the scheduler wrapper logs
the conflict via `logger.exception` and the next tick re-reads and
re-attempts.

### F2. `min_age_seconds` fence applied consistently — LOW

`max_event_id_settled` (§4.1, proposal.md:359-366) hardcodes the fence
into the SQL predicate:

```
WHERE id > :after_id
  AND recorded_at <= CURRENT_TIMESTAMP - make_interval(secs => :min_age_seconds)
```

The projector path (§5.1.1) calls it with
`min_age_seconds=MIN_AGE_SECONDS` (default `5`). The read path (§5.1.2)
calls it with `min_age_seconds=0, after_id=0` to compute
`visible_head_id`. That is **correct** per D5
(synthesis.md:293-302): the lag comparison needs the unfenced head or
else staleness is under-reported against a burst of freshly-committed
events.

**Observation (LOW, optional).** Sharing a function named `*_settled`
across the two call sites leaves a future footgun — if a later refactor
defaulted `min_age_seconds` to `MIN_AGE_SECONDS` (or re-used the helper
from a new projector) the staleness head would silently clamp and hide
projector lag. Two equally safe remediations sit inside the current
scope:

1. Require `min_age_seconds` as a keyword-only positional on
   `max_event_id_settled` (no default) and split out a thin
   `max_event_id(connection)` helper for the unfenced staleness head.
2. Leave as-is; rely on the module docstring (D14, proposal.md:425-427)
   and the `MIN_AGE_SECONDS` constant name to signal intent.

Not merge-blocking; not a correctness bug.

### F3. Worker tick exceptions caught and logged — LOW

§5.3 step 3 registers `_run_read_model_projector_if_due` with
`try: await asyncio.to_thread(read_model_worker_tick) except Exception:
logger.exception(...)` (proposal.md:716-734), byte-shaped identically
to `_run_ticket_sla_if_due` (`scheduler.py:212-229`). The worker
wrapper in §5.2 is explicitly documented to **not** catch — the
scheduler wrapper is the sole resilience contract (D6). A single failing
tick (including `CursorNotSeededError` and
`CursorVersionConflictError` per R2) updates `_last_read_model_tick_at`,
logs, and returns; `_run_ticket_sla_if_due`, deferred-effect tick, and
`_run_chapter_archive_if_due` remain unaffected.

### F4. Staleness thresholds declared as constants — LOW

§3.2 hoists to module scope in
`services/api/app/services/read_models.py`:

- `STALE_EVENT_THRESHOLD: int = 100`
- `STALE_TIME_THRESHOLD: timedelta = timedelta(minutes=5)` — a
  `timedelta`, not `int` seconds, eliminating unit-mismatch risk
- `MIN_AGE_SECONDS: int = 5`
- `OPEN_APPLICATION_STATES`, `PENDING_DEFERRED_EFFECT_STATUSES`,
  `UNRESOLVED_DRIFT_STATUSES`

§10 reiterates the complete list. `_compute_staleness` (§5.1.4) and
the projector (§5.1.1) both read these symbols — no inline magic
numbers at query or compute sites. D11 binds (synthesis.md:574-610).
Tests monkeypatch the module attributes rather than passing thresholds
as parameters (§8.2 tests 4–5, proposal.md:1026-1036).

### F5. Read path touches only whitelisted tables — LOW

Proposal §1 AC3 step 1 and D8 (synthesis.md:439-476) enumerate the
whitelist: `applications`, `tickets`, `deferred_effects`,
`permission_drift`, `read_model_cursors`, and `activity_state_changes
(MAX(id) only)`.

Auditing §4 and §5.1.2: the only SQL against `activity_state_changes`
is via `max_event_id_settled`, and its `SELECT COALESCE(MAX(id), ...)`
form ensures the table is touched only via the indexed aggregate — not
scanned or joined. Neither `activity_actions` nor `aggregate_heads` is
queried by any of the count/cursor/lag helpers. The endpoint function
body (§7.1) contains zero SQL; all SQL lives in the repository module
(D8). The service module does not import `mutate_entity`,
`mutate_projection`, `append_state_change`, or `advance_aggregate_head`
(§1 AC2 step 1; §5.1.2 note at proposal.md:580-582).

### F6. `OperationalOverviewRead.is_stale` matches `_compute_staleness` — LOW

Single source of truth: `_compute_staleness` (§5.1.4, proposal.md:619-648)
computes `is_stale = by_events or by_time` and returns a `_Stale`
dataclass with `.is_stale`, `.projections`, `.since`.
`read_operational_overview` (§5.1.2) assigns each contract field
from the dataclass verbatim — `is_stale=stale.is_stale`,
`stale_projections=stale.projections`, `stale_since=stale.since`
(proposal.md:560-566). The contract field `is_stale` is never re-derived
(no `bool(stale_projections)` fallback at the contract boundary). The
endpoint (§7.1) is a pass-through and contains no staleness logic.
D4 / D5 binding (synthesis.md:266-330).

### F7. Authority check at service layer — LOW

`_require_overview_authority` (§5.1.3, proposal.md:598-607) lives in
`services/api/app/services/read_models.py`, wraps
`require_scoped(actor, db, scope_kind, scope_id, _OVERVIEW_PERMISSION)`,
and is invoked from `read_operational_overview` — not from the
endpoint (proposal.md:522). The endpoint (§7.1) does not call
`require_scoped` directly; it only converts `PermissionError` → 403
via the shared `raise_known_permission_error` helper
(proposal.md:872-873), matching the drift-endpoint precedent
(`permissions/drift.py:63-78`). A future non-HTTP caller (diagnostics
CLI, Discord surface, etc.) hits the same gate.

### F8. Scope shape validation at service layer — LOW (previously MEDIUM; closed by R1)

**Previously (pre-R1).** Scope shape was validated only at the
endpoint layer. A non-HTTP caller invoking
`read_operational_overview(scope_kind='chapter', scope_id=None)` would
bypass validation and filter on `target_scope_id = NULL`.

**Current (R1).** `read_operational_overview` raises
`InvalidScopeError` at the top of the function for both shape
violations (proposal.md:514-521) **before** `_require_overview_authority`
— so malformed inputs do not touch authority tables. Endpoint pre-check
(proposal.md:830-845) remains for fast 422 on the HTTP path; endpoint
catch on the service-layer raise (proposal.md:854-860) is
defense-in-depth for programmatic callers that skip the pre-check.
Two-layer coverage is exercised by tests 9/10 (endpoint) and 12/13
(service without endpoint) (proposal.md:1052-1058, 1064-1074).

**Note on "contract" enforcement.** Pydantic-layer cross-field
validation is not added to `OperationalOverviewRead` — but that model
is a *response* contract, not the request contract. The request contract
is the FastAPI query signature, enforced at the endpoint pre-check.
"Both enforced at contract AND service layer" is therefore satisfied
by endpoint (request contract) + service, matching the drift-endpoint
precedent at `permissions/drift.py:47-62`.

### F9. Counts computed via predicate whitelist, not free-form SQL — LOW

§4 defines exactly five count/head helpers: `count_open_applications`,
`count_open_tickets`, `count_pending_deferred_effects`,
`count_active_drift`, `max_event_id_settled`. Each binds its IN-list to
a module constant (`OPEN_APPLICATION_STATES`,
`PENDING_DEFERRED_EFFECT_STATUSES`, `UNRESOLVED_DRIFT_STATUSES`) and
its filter column to the D4 predicate (synthesis.md:228-245). No
function accepts a free-form `WHERE` argument or a `status`
parameter. The service layer (§5.1.2) never calls the repository with
user-supplied status tuples — the endpoint only forwards `scope_kind`
and `scope_id`. Parameter binding uses psycopg tuple adaptation
(`%s` with a tuple argument), matching `archive_queries.py:66-68`
(proposal.md:413-415). No `%` formatting, no f-string SQL.

### F10. Cursor PK is `projection_name (TEXT)` — LOW

Proposal §2.1 and D2 (synthesis.md:132-173) both declare
`projection_name TEXT PRIMARY KEY` with no secondary index — single
row per projection, accessed exclusively by PK lookup. Check
constraints `last_processed_id >= 0` and `version >= 0` defend against
counter underflow. Seed uses
`INSERT ... VALUES ('operational_overview') ON CONFLICT (projection_name)
DO NOTHING` (proposal.md:166-170) — idempotent, non-destructive on
re-migration.

### F11. Service-actor grant uses `@>` AND `<@` containment — LOW

Proposal §2.1 step 3 reproduces the in-tree precedent
`migrations/versions/wu-028b_permission_reconciliation_runs.py:150-161`
(verified via Read). Both directions of jsonb set containment are
used:

```
permissions @> '["read_model.write"]'::jsonb
AND permissions <@ '["read_model.write"]'::jsonb
```

The pair enforces exact set equality — preventing both duplicate
insertion on re-migration and accidental matching against a superset
grant (proposal.md:207-210). Also guarded on `revoked_at IS NULL` and
`(expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)`,
line-for-line with wu-028b.

**Note on sourcing.** The focus-item text says "wu-029a pattern"; the
nearer in-tree precedent the proposal cites is **wu-028b** — both
migrations apply the identical `@>`/`<@` idiom, so substantive
equivalence holds. Reviewers scanning for the pattern should search
wu-028b.

### F12. No silent fallback on missing cursor row — LOW (previously MEDIUM; closed by R2)

**Previously (pre-R2).** Neither §5.1.1 nor §5.1.2 guarded against a
`None` return from `load_cursor`; a missing seed would surface as
`TypeError`/`AttributeError` rather than a domain exception.

**Current (R2).**
- `load_cursor` returns `ReadModelCursorRead | None` and explicitly
  disclaims any auto-seed (proposal.md:327-339: "No auto-seed here").
- `advance_operational_overview_cursor` raises `CursorNotSeededError`
  on `None` (proposal.md:468-472); the scheduler's
  `try/except logger.exception` surfaces the diagnostic without
  halting the loop (proposal.md:740-742).
- `read_operational_overview` raises the same error on `None`
  (proposal.md:546-550); endpoint maps to HTTP 503
  (`projection_not_initialized`) — deliberately not 500 and not 404
  (proposal.md:861-871).
- Coverage: test 9 (service raise), test 10 (scheduler resilience on
  `CursorNotSeededError`), test 14 (endpoint 503)
  (proposal.md:979-991, 1076-1082).

No auto-seed anywhere outside the migration.

### F13. `PROJECTION_NAMES` registry consistent — LOW

§3.2 declares `OPERATIONAL_OVERVIEW_PROJECTION_NAME: str =
"operational_overview"` and
`PROJECTION_NAMES: frozenset[str] = frozenset({OPERATIONAL_OVERVIEW_PROJECTION_NAME})`.
§5.1.1 references `OPERATIONAL_OVERVIEW_PROJECTION_NAME` at the worker
call site (proposal.md:463, 484); §5.1.2 references it at the read
path (proposal.md:542, 548). The migration seed (§2.1 step 2) uses the
literal `'operational_overview'` — correct because migrations run against
raw SQL and cannot import Python constants.

**Observation (LOW, for the test agent).** §8 tests reference the
string literal `'operational_overview'` inside `DELETE` fixtures
(e.g. tests 9 at proposal.md:980, 14 at proposal.md:1077). Per §10
"Tests import the same constants as production code"
(proposal.md:1126-1128) the test-writing agent should import
`OPERATIONAL_OVERVIEW_PROJECTION_NAME` and bind via parameter
placeholders rather than inlining the literal. This is a test-authoring
note, not a proposal change.

### F14. No automatic backfill from historical events — LOW

§2.2 states "WU-032 adds zero migrations per D13. No data backfill.
No snapshot table (D15)." (proposal.md:216-218). The migration seeds
`last_processed_id = 0` / `last_processed_at NULL`
(proposal.md:166-170). On first scheduler tick the projector advances
naturally through the fenced event stream (§5.1.1, D1) — this is cursor
initialisation, not historical replay. No one-shot "catch-up" routine,
no startup hook under `configure_read_models`, and no `__init__` side
effect beyond storing the `PostgresDatabase` handle (§5.2). §11
explicitly forbids materialised snapshots and additional cursors
(proposal.md:1150-1180). D15 bounds (synthesis.md:748-785).

Observation (not a blocker): the cursor advance has no downstream
materialised side effects because the only projection in scope is the
cursor itself (D3). `SELECT COALESCE(MAX(id), ...)` is O(log n) via
the PK index, not O(n) — so the first tick on a long-running DB is
cheap.

## Summary

| # | Focus item | Severity | Note |
|---|---|---|---|
| F1 | Cursor advance uses OCC (`expected_version`) | LOW | Defense-in-depth over `FOR UPDATE`; logs on conflict, next tick retries |
| F2 | `min_age_seconds` fence applied consistently | LOW | Unfenced `MAX(id)` for lag is per D5; optional helper split is non-blocking |
| F3 | Worker tick exceptions caught + logged | LOW | Scheduler wrapper mirrors `_run_ticket_sla_if_due` byte-for-byte |
| F4 | Staleness thresholds as module constants | LOW | `STALE_EVENT_THRESHOLD`, `STALE_TIME_THRESHOLD` hoisted per D11 |
| F5 | Read path touches only whitelisted tables | LOW | No peek at `activity_actions` / `aggregate_heads` |
| F6 | `is_stale` matches `_compute_staleness` helper | LOW | Single source of truth; no contract-layer re-derivation |
| F7 | Authority check at service layer | LOW | `_require_overview_authority` first-line in service, not endpoint |
| F8 | Scope shape validation at service + endpoint | LOW | Closed by R1 (`InvalidScopeError`); two-layer coverage in tests 12–13 |
| F9 | Counts via predicate whitelist | LOW | No free-form SQL; constants bind IN-lists |
| F10 | Cursor PK is `projection_name (TEXT)` | LOW | No secondary index; CHECK guards negatives |
| F11 | Service-actor grant uses `@>` AND `<@` | LOW | Matches wu-028b:150-161 precedent; expiry/revoke guarded |
| F12 | No silent missing-cursor fallback | LOW | Closed by R2 (`CursorNotSeededError` → 503; no auto-seed) |
| F13 | `PROJECTION_NAMES` registry consistent | LOW | Single-element set is the D3 seam; test agent should import the constant |
| F14 | No automatic backfill at startup | LOW | Migration seed + natural tick advance; no replay routine |

No MEDIUM or HIGH shortcut findings remain after Revision 1.

## Rating

**LOW.** Revision 1 closed the two MEDIUM pins (F8, F12) in-patch
inside the bindings D4/D6/D9/D15 already fix — neither required a
synthesis revision or scope expansion. The remaining twelve items are
consistent with the shipped worker-tick and authority conventions. The
proposal does not authorize any backwards-compatibility shim, deferred
stub, magic literal at a query site, or audit/write-path coupling that
would compromise AC2–AC4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
