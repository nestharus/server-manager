# SLICE-014 Phase 8 — Multi-Concern Review (PR #60)

Reviewed: 2026-04-21
PR: `feat/slice-014-permission-drift` (#60), 30 files, +9085 / −1733 LOC
Inputs: `git diff origin/main...feat/slice-014-permission-drift`,
`product-strategy/tickets/SLICE-014.md`, `.pipeline/proposal.md`,
AGENTS.md §"One Concern Per PR", prior-slice precedents (SLICE-011
split 3, SLICE-015 review-recommended split 3 / merged atomic,
SLICE-018 split 2, SLICE-012/016/021/023 atomic).

## 1. Verdict

**`MULTI_CONCERN_RECOMMEND_SPLIT`** — split into two PRs on the
API↔Discord seam (WU-028B-discord is a pure API consumer with zero
compile-time Python dependencies into `services/api`).

The four work units have a linear producer/consumer shape:

```
WU-027 ──▶ WU-028A ──▶ WU-028B-api ──▶ WU-028B-discord
```

but the three **API-side** work units (WU-027, WU-028A, WU-028B-api)
are tightly interleaved across the same contract, repository, and
endpoint-support modules. Splitting them further fragments the review
without producing independently deployable intermediate states. The
Discord adapter, by contrast, is a clean standalone concern matching
the SLICE-018 WU-033→WU-034 shape exactly.

Against AGENTS.md §"One Concern Per PR":
- "A PR that touches N independent concerns should be split into N
  PRs." — PR #60 touches exactly two independently testable concerns:
  the API control plane (three WUs that share files) and the Discord
  snapshot adapter (zero-import consumer).
- "Dependency order matters — if B depends on A, A merges first." —
  WU-028B-discord depends at runtime on WU-028B-api's endpoints and
  the seeded `permission-reconciler` grant. Acyclic linear edge.
- "Additive changes go before behavioral changes." — The API surface
  is additive; the Discord adapter is a behavioral consumer.
- "Split oversized PRs." — 30 files / +9085 LOC exceeds the
  single-concern envelope (cf. SLICE-018 split at 19 files / +3447;
  SLICE-015 split at 33 files / +6366).

A three-way split (A=WU-027, B=WU-028A+WU-028B-api, C=WU-028B-discord)
mirroring the SLICE-015 review recommendation is **rejected** in §7
because the contract, repository, and endpoint-support modules
interleave WU-027 / WU-028A / WU-028B-api at every layer: splitting
them forces all three PRs to straddle the same three files, and the
wu-027 narrowing migration (53 LOC) lacks standalone operator value
without the downstream reconciliation flow that populates the
`permission_intents` table for comparison.

## 2. Concerns enumerated

### Concern A — API control plane (WU-027 + WU-028A + WU-028B-api)

Adds the full declared-state reconciliation substrate inside
`services/api` and `migrations/`. Ships three migrations on a single
linear chain (`wu_035_application_interview` → `wu_027` → `wu_028a` →
`wu_028b`), the three-router permissions package, the shared
contracts/repository/service modules, and the reconciliation service
that consumes intents and produces drift.

**WU-027 — Permission Intent Management API.** Narrows
`permission_intents.scope_kind` to `{'global','chapter'}` via
`wu-027_permission_intents_refinements.py` (53 LOC, guard-and-replace
CHECK), replaces the foundation shim `actor_kind='system'` with a
real `ActorIdentity` in `create_permission_intent` /
`update_permission_intent`, adds `read_permission_intent` /
`list_permission_intents`, adds the three `/api/v1/permission-intents`
endpoints (POST / PATCH with `If-Match` strong ETag → 412 /
GET list), and deletes the 470-line
`test_permission_intent_foundation.py` in favor of the 391-line
`test_permission_intents.py`.

**WU-028A — Permission Drift Read + Resolution API.** Widens
`permission_drift` via `wu-028a_permission_drift_widening.py`
(161 LOC) — adds `scope_kind`, `scope_id`, `role_id`, `channel_id`,
`kind`, `reconciliation_run_id`, `resolved_by_kind`, `resolved_by_id`,
`resolved_at`, `resolution_reason`; backfills from linked intents;
installs four CHECK constraints (scope shape, variant shape,
resolution shape, kind validity) and three indexes. Adds
`PermissionDriftRead` + `PermissionDriftResolutionRequest` to the
contract module with shape validators, adds
`list_permission_drift` / `fetch_permission_drift` /
`insert_permission_drift` / `insert_permission_drift_batch` /
`update_permission_drift_resolution` to the repository, adds
`VALID_DRIFT_TRANSITIONS` state machine + spoof-proof
`_drift_originating_actor` + `resolve_permission_drift` +
`create_permission_drift` service helper (used by tests and by the
reconciliation service), adds the two `/api/v1/permission-drift`
endpoints, and deletes the 284-line
`test_permission_drift_foundation.py` in favor of the 545-line
`test_permission_drift.py`.

**WU-028B-api — Permission Reconciliation Run API.** Creates
`permission_reconciliation_runs` via
`wu-028b_permission_reconciliation_runs.py` (166 LOC), adds the FK
`permission_drift.reconciliation_run_id → permission_reconciliation_runs.id
ON DELETE RESTRICT` on the column created by wu-028a, installs two
partial unique indexes on `(reconciliation_run_id, role_id, kind,
channel_id)` (channel/guild variants), seeds the
`permission-reconciler` service actor grant. Adds
`PermissionReconciliationRunCreate/Read`, `PermissionSnapshotEntry`
(discriminated guild/channel union), and
`ReconciliationSnapshotRequest` (duplicate-key rejection) to the
contract module; adds run repository helpers
(`insert_reconciliation_run`, `fetch_reconciliation_run`,
`update_reconciliation_run_status`, `list_drift_ids_by_run`) and
`insert_permission_drift_batch`. Adds the new 717-LOC
`services/api/app/services/permission_reconciliation.py` implementing
the D8 intent-vs-snapshot comparison algorithm (terminal replay for
reconciled runs, failure path, `_build_drift_rows` for
match/mismatch/orphan cases, and audited advance helpers). Adds the
two `/api/v1/permission-reconciliation/runs` endpoints and the
599-LOC `test_permission_reconciliation_api.py`.

This concern ships entirely inside `services/api` +
`migrations/versions`. It does not import any Discord code. The API
suite passes in isolation against the in-process FastAPI client and a
real Postgres instance.

### Concern B — Discord permission snapshot adapter (WU-028B-discord)

Adds the `/reconcile_permissions` slash-command handler inside
`services/discord`. Two contract modules, one handler, one
infrastructure client, one command registration module, one test
suite. 125 LOC mirrored contracts
(`DiscordReconciliationRunCreate/Read`,
`DiscordGuildRoleSnapshotEntry`, `DiscordChannelRoleSnapshotEntry`,
`DiscordReconciliationSnapshotRequest` with identical shape to the
API-side contracts). 148 LOC `PermissionApiClient` over the SLICE-006
`ApiClient` / `ApiTransportRequest` surface with 409
(`PermissionApiConflictError`) / 412
(`PermissionApiPreconditionFailedError`) carve-outs and the
`X-Actor-Kind: service` / `X-Actor-Id: permission-reconciler` trust
headers. 202 LOC `handle_reconcile_permissions` that
(a) calls `POST /api/v1/permission-reconciliation/runs`,
(b) walks the in-memory guild cache to build guild-role + channel-role
snapshot entries per-scope, and
(c) calls `POST /api/v1/permission-reconciliation/runs/{run_id}/snapshots`
with the same run_id (idempotent retry), surfacing drift count in the
ephemeral response. 29 LOC `register_permission_commands` binding.
379 LOC `test_permission_reconciliation_adapter.py` against fake
guild / role / overwrite / API client.

Zero imports from `services/api/*`. Zero API/migration edits. The
adapter test suite runs green without a live API, asserting captured
`ApiTransportRequest` records instead.

## 3. Recommended PR ordering (topological)

```
PR A (WU-027 + WU-028A + WU-028B-api) ──▶ PR B (WU-028B-discord)
```

Forcing edges, all A→B, none B→A:

- **B → A runtime (run endpoint):** The adapter's
  `PermissionApiClient.create_reconciliation_run` POSTs
  `/api/v1/permission-reconciliation/runs`; route added by PR A's
  `services/api/app/api/v1/endpoints/permissions/reconciliation.py`.
- **B → A runtime (snapshot endpoint):**
  `PermissionApiClient.submit_snapshot` POSTs
  `/api/v1/permission-reconciliation/runs/{run_id}/snapshots`; same.
- **B → A authority:** The adapter sends `X-Actor-Kind: service` +
  `X-Actor-Id: permission-reconciler` (constant `SERVICE_ACTOR_ID`
  in `services/discord/app/infrastructure/permission_client.py:18`).
  The matching `authority_grants` row with
  `['permission_intent.read', 'permission_drift.read',
  'permission_drift.write', 'permission_reconciliation_run.write']`
  is seeded by PR A's wu-028b migration
  (`migrations/versions/wu-028b_permission_reconciliation_runs.py:
  123-158`). Without PR A the adapter 403s.
- **B → A contract:** `DiscordReconciliationRunRead` mirrors PR A's
  `PermissionReconciliationRunRead`; body shape must align for
  `model_validate(response.body)` to succeed. PR A defines the wire
  shape.
- **B → A handler contract:** The snapshot wire body
  `{"entries": [...]}` with the discriminated `kind`/`role_id`/
  `permission_bits` vs `channel_id`/`allow_bits`/`deny_bits` shape is
  declared by PR A's `ReconciliationSnapshotRequest` +
  `PermissionSnapshotEntry`.

No reverse edges. PR A's API test suite passes with no Discord code
present. PR B's adapter suite (fake bot, fake API client) passes with
no live API.

## 4. File allocation (every code/test file → exactly one PR)

### PR A — API control plane (WU-027 + WU-028A + WU-028B-api) [22 code/test files + 6 slice docs]

Migrations (three-file chain, linearly ordered):
- `migrations/versions/wu-027_permission_intents_refinements.py`
- `migrations/versions/wu-028a_permission_drift_widening.py`
- `migrations/versions/wu-028b_permission_reconciliation_runs.py`

API code:
- `services/api/app/api/v1/endpoints/permissions/__init__.py`
- `services/api/app/api/v1/endpoints/permissions/_shared.py`
- `services/api/app/api/v1/endpoints/permissions/drift.py`
- `services/api/app/api/v1/endpoints/permissions/intents.py`
- `services/api/app/api/v1/endpoints/permissions/reconciliation.py`
- `services/api/app/api/v1/router.py` (add `permissions` include)
- `services/api/app/contracts/permissions.py` (intent + drift + run
  + snapshot types, all three WUs)
- `services/api/app/repositories/permissions.py` (intent + drift +
  run functions, all three WUs)
- `services/api/app/services/permissions.py` (intent CRUD + drift
  resolve + `create_permission_drift` helper)
- `services/api/app/services/permission_reconciliation.py` (new,
  717 LOC reconciliation service)

API tests:
- `services/api/tests/conftest.py` (one-line truncate-list extension
  for `permission_reconciliation_runs`)
- `services/api/tests/test_permission_drift_foundation.py` (DELETE,
  −284 LOC)
- `services/api/tests/test_permission_drift.py` (new, 545 LOC)
- `services/api/tests/test_permission_intent_foundation.py` (DELETE,
  −470 LOC)
- `services/api/tests/test_permission_intents.py` (new, 391 LOC)
- `services/api/tests/test_permission_reconciliation_api.py` (new,
  599 LOC)

Slice-level docs (see §5):
- `.pipeline/proposal.md`
- `.pipeline/research.md`
- `.pipeline/synthesis.md`
- `plans/risk/slice-014-audit.md`
- `plans/risk/slice-014-scope.md`
- `plans/risk/slice-014-shortcut.md`

### PR B — Discord permission snapshot adapter (WU-028B-discord) [5 files]

Discord code:
- `services/discord/app/commands/permissions.py`
- `services/discord/app/contracts/permissions.py`
- `services/discord/app/handlers/permissions.py`
- `services/discord/app/infrastructure/permission_client.py`

Discord tests:
- `services/discord/tests/test_permission_reconciliation_adapter.py`

Total: 22 + 5 = 27 code/test files + 6 slice docs = 33. Exceeds PR
#60's 30 by three because the shared-file overlap across WU-027 /
WU-028A / WU-028B-api is resolved by keeping all three WUs in PR A
(no straddling). If Option 1 (3-PR split) had been selected, the
contract + repository + shared-endpoint modules would each straddle
three PRs; see §7.

## 5. Straddling files — flags and justifications

### `services/api/app/contracts/permissions.py` → PR A

Contains intent types (WU-027: `_PermissionIntentBase`,
`GuildRolePermissionIntent`, `ChannelRolePermissionIntent`,
`PermissionIntentRead`, `*Create`, `PermissionIntentUpdate`,
`PermissionIntentNotFoundError`), drift types (WU-028A:
`PermissionDriftRead` with three shape validators,
`PermissionDriftResolutionRequest`, `PermissionDriftStatus`,
`DriftResolutionAction`, `PermissionDriftNotFoundError`), and run +
snapshot types (WU-028B-api: `PermissionReconciliationRunCreate/Read`,
`PermissionReconciliationRunStatus`, `GuildRolePermissionSnapshotEntry`,
`ChannelRolePermissionSnapshotEntry`, `PermissionSnapshotEntry`
discriminator, `ReconciliationSnapshotRequest`). The module also
hosts the shared `DecimalBitString` validator, the
`_PermissionModel`(extra="forbid") base, and the
`PermissionIntentScopeKind` / `PermissionIntentKind` literal aliases
that all three WUs depend on. Splitting this file per-WU (e.g.
`contracts/permission_intents.py`, `contracts/permission_drift.py`,
`contracts/permission_runs.py`) would force every downstream module
to fan out imports and defeats the discriminated-union pattern used
for `PermissionSnapshotEntry`. Keep in PR A.

### `services/api/app/repositories/permissions.py` → PR A

Contains intent CRUD helpers (`insert_permission_intent`,
`fetch_permission_intent`, `list_permission_intents`,
`update_permission_intent_row`), drift helpers
(`fetch_permission_drift`, `list_permission_drift`,
`insert_permission_drift`, `insert_permission_drift_batch`,
`update_permission_drift_resolution`), and run helpers
(`insert_reconciliation_run`, `fetch_reconciliation_run`,
`update_reconciliation_run_status`, `list_drift_ids_by_run`). Also
hosts the shared `db_value_to_bit_str` normalizer and the two
`_normalize_permission_*_row` helpers. The reconciliation service
consumes all three helper groups in `submit_reconciliation_snapshot`
(reads intents, creates drift batch, updates run status). Keep
unified in PR A.

### `services/api/app/services/permissions.py` → PR A

Contains intent CRUD (`create_permission_intent`,
`update_permission_intent`, `read_permission_intent`,
`list_permission_intents`), drift resolution
(`read_permission_drift`, `list_permission_drift`,
`resolve_permission_drift`, `create_permission_drift`), and the
shared `_require_scoped_authority` helper imported by
`services/permission_reconciliation.py:22`. The `mutate_entity`
allowlist constants (`INTENT_CREATE_PAYLOAD_ALLOWLIST`,
`INTENT_UPDATE_PAYLOAD_ALLOWLIST`,
`DRIFT_RESOLUTION_PAYLOAD_ALLOWLIST`) and the
`VALID_DRIFT_TRANSITIONS` state machine live here. Keep in PR A.

### `services/api/app/api/v1/endpoints/permissions/_shared.py` → PR A

Adds `parse_if_match_strong` (strong-ETag validator shared by intent
PATCH, drift resolve, and — indirectly via common error handling — the
reconciliation endpoints), `set_etag`, `require_scoped`, and
`raise_known_permission_error` which unions all three WUs' error
taxonomies into HTTP responses: `PermissionIntentNotFoundError` (WU-
027), `PermissionDriftNotFoundError` + `InvalidDriftTransitionError`
(WU-028A), and `ReconciliationRunConflictError` +
`ReconciliationRunNotFoundError` (WU-028B-api). Per-WU extraction
would force each PR to import the shared error-union helper and add
per-WU cases in the other PRs. Keep in PR A.

### `services/api/app/api/v1/router.py` → PR A

One-line change adding
`router.include_router(permissions.router, prefix="", tags=[...])`
for the new `permissions` package. All three API WUs share the
include. Keep in PR A.

### `services/api/tests/conftest.py` → PR A

Adds `permission_reconciliation_runs` to the truncate list. The
table is created by wu-028b; the fixture update is a consequence of
the migration. Single-line change.

### `services/api/tests/test_permission_drift_foundation.py` (DELETE, −284 LOC) → PR A

Replaced by `test_permission_drift.py`. Under AGENTS.md "A large
deletion is its own PR, separate from the addition that replaces it"
the question is whether this deletion should be a third PR. It should
not: the foundation test covered the WU-006b shipped drift surface
(`update_permission_drift_status` with implicit version, permissive
schema); WU-028A replaces those service helpers in place with
`resolve_permission_drift` (required `expected_version`, state
machine, spoof-proof resolver, resolution-metadata writes). The same
service module cannot export both APIs; splitting the delete from its
rewrite would leave one PR with imports at symbols that no longer
exist. Same coupling as SLICE-018 WU-033's
`test_roster_foundation.py` deletion (kept with the addition that
replaced it).

### `services/api/tests/test_permission_intent_foundation.py` (DELETE, −470 LOC) → PR A

Same reasoning. The foundation test covered the
`actor_kind='system'` shim in `create_permission_intent` /
`update_permission_intent` that WU-027 explicitly replaces with a
real `ActorIdentity`. Keep with the rewrite in PR A.

### `.pipeline/*`, `plans/risk/slice-014-*.md` → PR A

6 slice-level artifacts describing the whole slice, not a single WU.
Match the SLICE-015 / SLICE-018 precedent — ship with PR A since PR A
lands the substrate they primarily describe.

## 6. Should the deletion of both foundation test files be its own PR?

**No.** 754 LOC of combined foundation-test deletion is bundled with
the rewrite that replaces the surface they tested. The same module
(`services/api/app/services/permissions.py`) cannot export both the
shim-based foundation API (`update_permission_drift_status` with
implicit version, `create_permission_intent(db, request, *, actor=...)`
with foundational `actor_kind='system'` default) and the hardened
SLICE-014 API at the same time. Splitting the delete off would leave
an intermediate state with failing imports. Precedent: SLICE-018 PR
A kept the `test_roster_foundation.py` delete with WU-033.

## 7. Why not a 3-PR split (SLICE-015 shape)?

The SLICE-015 review recommended splitting into three PRs along the
edges **aggregate-CRUD → worker-substrate → adapter**. The same shape
maps to SLICE-014 as **WU-027 → WU-028A+WU-028B-api → WU-028B-discord**.
For SLICE-014 this split is **not** recommended. Three reasons:

1. **File-level straddling is worse than SLICE-015.** SLICE-015's
   rule types (WU-029A) and envelope types (WU-029B) live in the same
   contract module but are cleanly disjoint symbol sets
   (`NotificationRuleCreate` vs `NotificationDeliveryCommand`). In
   SLICE-014, WU-027's `PermissionIntentScopeKind` / `PermissionIntentKind`
   literals are consumed by WU-028A's `PermissionDriftRead` and by
   WU-028B-api's `PermissionReconciliationRunCreate` / snapshot
   entries. The shared `_PermissionModel` base, the shared
   `DecimalBitString` validator, the shared scope-shape and
   variant-shape validators, and the shared
   `_reject_empty_optional_identifiers` field validator cut across
   all three WUs. Splitting requires declaring these in PR A and
   re-importing in PRs B and C, which means the contract module
   straddles every PR.

2. **WU-027's standalone operator value is thin.** The WU-027
   narrowing migration is 53 LOC — it only replaces a CHECK
   constraint to refuse `scope_kind = 'member'`. Intent CRUD was
   already shipped at the foundation layer (WU-006a/b); WU-027
   replaces the system-actor shim and adds list, but the
   reconciliation flow (WU-028B-api) is what makes intents
   operationally meaningful (otherwise intents are just a catalog
   with no comparison target). Shipping WU-027 alone creates an
   intermediate state where operators can author intents but the
   rest of the slice cannot consume them.

3. **WU-028A and WU-028B-api cannot cleanly separate.** The
   wu-028a widening migration adds `scope_kind`, `scope_id`,
   `role_id`, `channel_id`, `kind`, and `reconciliation_run_id`
   columns that are **written exclusively by the reconciliation
   flow** (`_build_drift_rows` in
   `services/api/app/services/permission_reconciliation.py:456-564`).
   The wu-028b migration then adds the FK
   `permission_drift.reconciliation_run_id →
   permission_reconciliation_runs.id ON DELETE RESTRICT` on a
   column created by wu-028a. Splitting into two PRs leaves an
   intermediate state where wu-028a's widened columns are dormant
   and the resolve endpoint has no production producer of drift
   rows to act on (only the `create_permission_drift` test helper).
   This is the same reasoning SLICE-015 used to keep materialize +
   deliver bundled.

A 2-PR split (API + Discord) captures the real concern boundary —
the zero-import producer/consumer seam between `services/api` and
`services/discord` — without introducing the three-way straddling
overhead that would dominate review of PR A.

## 8. Test-suite independence check

Each concern has a dedicated test surface with the expected
imports:

- **PR A tests:** `test_permission_intents.py` imports only contract
  types and `grant_authority`; it hits the API via `httpx.AsyncClient`.
  `test_permission_drift.py` additionally imports
  `create_permission_intent` + `create_permission_drift` +
  `DRIFT_RESOLUTION_CHANGE_TYPE` from
  `app.services.permissions` to seed fixtures — these are WU-027
  and WU-028A symbols that co-exist in PR A.
  `test_permission_reconciliation_api.py` creates intents via the
  API URL (`/api/v1/permission-intents`) rather than direct service
  imports — the test doesn't couple to WU-027 at the import level,
  only at the wire level. None of the three API test files import
  Discord code or run against a live Discord bot.

- **PR B tests:** `test_permission_reconciliation_adapter.py`
  imports only `app.commands.permissions`, `app.handlers.permissions`,
  `app.contracts.permissions`, and `app.infrastructure.permission_client`
  from `services/discord`. It asserts against captured API request
  records (`FakePermissionClient.create_calls` /
  `.submit_calls`) rather than hitting a live API. No imports from
  `services/api`, no imports from `migrations`. Runs green in
  isolation.

No test file straddles the API↔Discord seam.

## 9. Size signal

PR totals: 30 files, +9085 / −1733 LOC. Excluding the 6
pipeline/risk artifacts (`.pipeline/proposal.md` alone is +2902
lines, `research.md` +641, `synthesis.md` +1141; risk audit/scope/
shortcut another ~520), the code+tests split is roughly:

- **PR A (WU-027 + WU-028A + WU-028B-api):**
  - Migrations: 53 + 161 + 166 = 380 LOC
  - Contracts: +204 LOC (intent/drift/run/snapshot additions)
  - Repository: +269 LOC
  - Service — permissions: +418 LOC (intent CRUD + drift resolve +
    create_permission_drift helper)
  - Service — reconciliation: 717 LOC (new file)
  - Endpoints package (5 files): 16 + 144 + 93 + 119 + 79 = 451 LOC
  - Router: +2 LOC
  - Tests: 545 + 391 + 599 = 1535 LOC added
  - Tests removed: 284 + 470 = 754 LOC removed
  - conftest: +1 LOC
  - **Total: ~3976 LOC added / 754 LOC removed across 22 files**

- **PR B (WU-028B-discord):**
  - Discord contracts: 125 LOC
  - Discord client: 148 LOC
  - Discord handler: 202 LOC
  - Discord command: 29 LOC
  - Tests: 379 LOC
  - **Total: ~883 LOC across 5 files**

PR A is large but unitary (see §7 — splitting further creates broken
intermediate states or three-way straddling). PR B is within typical
single-concern size and matches the SLICE-018 WU-034 /
SLICE-015 WU-029C adapter precedents exactly.

## 10. Summary

Recommend splitting PR #60 into two PRs in the order **WU-027 +
WU-028A + WU-028B-api → WU-028B-discord**, with file allocation as
in §4. The dependency graph is a single API→Discord edge and
acyclic. Keep the three-migration chain (wu-027 → wu-028a → wu-028b)
bundled inside PR A because the schema unit is only coherent when
applied together (wu-028a widens drift columns that wu-028b's
reconciliation flow populates; wu-028b adds an FK on a column
created by wu-028a). Keep both foundation-test deletions
(`test_permission_intent_foundation.py`, −470 LOC and
`test_permission_drift_foundation.py`, −284 LOC) inside PR A
alongside the rewrites that replace them. A three-way split along
the WU boundary is rejected (see §7) because the shared contract,
repository, and service modules interleave WU-027 / WU-028A /
WU-028B-api too tightly, and WU-027's narrowing migration lacks
standalone operator value without the downstream reconciliation
flow.
