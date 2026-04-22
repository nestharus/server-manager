# SLICE-014 Phase 2 Synthesis: Binding Decisions

These decisions are binding for the SLICE-014 proposal, hookpoint research,
risk, test, and implementation phases. The proposal may choose mechanics
inside these boundaries, but it must not expand lifecycle scope, create a
parallel permission/drift subsystem, introduce compatibility aliases, or
rewrite shipped WU-006a / WU-006b foundations as if they did not exist.

## Inputs

- `.pipeline/research.md` (Phase 1 research report).
- `product-strategy/tickets/SLICE-014.md` — acceptance criteria and WU table.
- `AGENTS.md` — Live Server Principle, No Backwards Compatibility, Test/Code
  agent separation, migration discipline.
- `product-strategy/proposal.md` §Permission Management + §Operational Workflows
  → Permission Reconciliation (`product-strategy/proposal.md:509-554`,
  `product-strategy/proposal.md:738-754`).
- `product-strategy/problem.md` §7 Permission Model and State Explosion
  (`product-strategy/problem.md:77-87`).
- Existing code in worktree:
  - `services/api/app/services/permissions.py`
  - `services/api/app/contracts/permissions.py`
  - `services/api/app/repositories/permissions.py`
  - `migrations/versions/wu-006a_permission_intents_foundation.py`
  - `migrations/versions/wu-006b_permission_drift_foundation.py`
  - Migration head `migrations/versions/wu-035_application_interview.py`
    (`revision = "wu_035_application_interview"`).

## Acceptance Criteria Reference

- **AC1**: Creating or updating an intent persists the exact scope, role/channel
  target, bitset, and reason, with stale updates rejected by 412.
  (`product-strategy/tickets/SLICE-014.md:60`.)
- **AC2**: Drift reads include both intent-linked and orphaned Discord state
  and resolving with stale version returns 412. (`…:61`.)
- **AC3**: Reconciliation runs create drift rows both for mismatches against
  declared intent and for unmanaged Discord state with no matching intent.
  (`…:62`.)
- **AC4**: The Discord snapshot adapter never mutates drift rows locally and
  reuses the API run ID as the idempotency key on retry. (`…:63`.)

## Resolved Existing State

- WU-006a shipped `permission_intents` with variant-shaped `guild_role` /
  `channel_role` rows, decimal-string masks over `NUMERIC(39,0)`, and
  aggregate-head OCC keyed by a compound intent aggregate id.
  (`migrations/versions/wu-006a_permission_intents_foundation.py:16-85`,
  `services/api/app/services/permissions.py:29-41`.)
- WU-006b shipped `permission_drift` with only `permission_intent_id`,
  `intent_version`, intended/actual mask columns, a status enum, and a
  detection timestamp. The table has no target locator, no resolution
  metadata, and no reconciliation-run anchor.
  (`migrations/versions/wu-006b_permission_drift_foundation.py:16-79`,
  research report §1.)
- No reconciliation-run table, no permission API router, no Discord
  permission adapter, and no permission authority permission names currently
  exist in the tree (research report §§4–7).
- `aggregate_heads.aggregate_type` is plain `TEXT` (no enum/registry), so new
  aggregate type values are added by convention only
  (`migrations/versions/wu-002_activity_substrate.py:113-135`).
- Current Alembic head is `wu_035_application_interview`
  (`migrations/versions/wu-035_application_interview.py:9-12`). SLICE-014
  migrations chain from there.

## Binding Decisions

### D1 — BINDING: PermissionIntent scope kinds narrowed to `global|chapter`

**Decision.** Narrow intent scope at the schema, contract, and service layers
to `scope_kind IN ('global', 'chapter')` via a forward migration. Drop the
`'member'` option from the shipped WU-006a constraint and the
`ScopeKind`-sourced validator on the permission intent contracts so that
`member`-scoped intents are no longer representable.

**Rationale.** The proposal’s PermissionIntent table defines scope as
`global` or chapter FK only (`product-strategy/proposal.md:517-528`), and the
problem statement frames the permission-model pain at the server-wide and
chapter layer (`product-strategy/problem.md:77-87`). The research report
flags this as an explicit synthesis question (research §1 and §9, Q1).
Accepting `member` at the schema forever re-opens state explosion at the very
layer that §7 warns against. Validating only at the contract layer violates
the defense-in-depth pattern used for the variant-shape CHECK constraints
already shipped in WU-006a. Live-server principle (AGENTS.md) means we cannot
rely on a transitional alias; narrowing in place is the clean path.

**Binding implications.**
- New migration (see D14) executes, in the same transaction, a guard that
  errors out if any production row has `scope_kind='member'`:
  ```sql
  DO $$
  BEGIN
      IF EXISTS (SELECT 1 FROM permission_intents WHERE scope_kind = 'member') THEN
          RAISE EXCEPTION
              'SLICE-014 D1: permission_intents contains scope_kind=member rows; '
              'forward migration refuses to narrow scope.';
      END IF;
  END
  $$;
  ```
  followed by `ALTER TABLE permission_intents DROP CONSTRAINT
  permission_intents_scope_kind_valid, ADD CONSTRAINT
  permission_intents_scope_kind_valid CHECK (scope_kind IN ('global',
  'chapter'));`.
- Permission intent contracts use a narrowed scope type (e.g. a
  `PermissionIntentScopeKind: TypeAlias = Literal["global", "chapter"]`) that
  does not import the wider `ScopeKind`. Do not re-export or alias the old
  wider scope on intent contracts. `services/api/app/contracts/scope.py` may
  remain wider for other aggregates.
- Service-layer creation rejects `member` via the contract itself; no
  runtime string compare.
- No backwards-compatibility shim for existing callers that pass `member`;
  there are none in the tree.

**Non-goals.** Does not change scope kinds used by any other aggregate.
Does not modify `authority_grants.scope_kind` options. Does not attempt to
migrate hypothetical member-scoped intent data; the migration refuses to run
instead.

### D2 — BINDING: `permission_drift` widened in place; no parallel table

**Decision.** Extend `permission_drift` in place via the SLICE-014 drift
migration (see D14). Do not create a `permission_drift_findings` table.
Add the following columns and constraints:

- `scope_kind TEXT NOT NULL CHECK (scope_kind IN ('global','chapter'))`
- `scope_id TEXT NULL`
- `role_id TEXT NOT NULL`
- `channel_id TEXT NULL`
- `kind TEXT NOT NULL CHECK (kind IN ('guild_role','channel_role'))`
- `reconciliation_run_id UUID NULL`
  (FK to `permission_reconciliation_runs.id` with `ON DELETE RESTRICT`)
- `resolved_by_kind TEXT NULL`
- `resolved_by_id TEXT NULL`
- `resolved_at TIMESTAMPTZ NULL`
- `resolution_reason TEXT NULL`

Constraints:

- `permission_drift_variant_shape_valid`:
  - `kind='guild_role'` rows require `channel_id IS NULL`.
  - `kind='channel_role'` rows require `channel_id IS NOT NULL`.
- `permission_drift_scope_shape_valid`:
  - `scope_kind='chapter'` rows require `scope_id IS NOT NULL`.
  - `scope_kind='global'` rows require `scope_id IS NULL`.
- `permission_drift_resolution_shape_valid`:
  - `status IN ('reconciled','accepted')` requires
    `resolved_by_kind IS NOT NULL AND resolved_by_id IS NOT NULL AND
    resolved_at IS NOT NULL AND resolution_reason IS NOT NULL`.
  - `status IN ('detected','acknowledged')` requires
    `resolved_by_kind IS NULL AND resolved_by_id IS NULL AND
    resolved_at IS NULL AND resolution_reason IS NULL`.
- Retain existing `permission_drift_intent_anchor_valid`
  (`permission_intent_id IS NULL <-> intent_version IS NULL`).

Indexes:

- `ix_permission_drift__scope (scope_kind, scope_id)`
- `ix_permission_drift__reconciliation_run_id (reconciliation_run_id)`
- `ix_permission_drift__role_channel_kind (role_id, channel_id, kind)`

**Rationale.** The existing schema cannot identify orphaned Discord state
when `permission_intent_id` is NULL (research §1 and §3); AC2 requires drift
reads to include intent-linked *and* orphaned state. In-place widening keeps
one aggregate per drift row (D3) and avoids parking a legacy table — the
Live Server Principle (AGENTS.md) forbids shadow tables that linger. The
split resolution CHECK mirrors WU-006a’s variant-shape defense in depth.

**Binding implications.**
- Resolution metadata lives on `permission_drift`, not on a separate
  resolutions table.
- The drift read contract grows to expose scope/target columns and
  resolution metadata; orphaned-drift rows no longer lose their Discord
  coordinates.
- New indexes support the GET `/permission-drift` filter set (D10).
- Pre-existing rows are impossible today (shipped schema guarantees only
  intent-linked rows could exist, and variant/scope columns would be NULL);
  the migration must backfill legacy rows from their linked intent when
  `permission_intent_id IS NOT NULL`, and must refuse to run if an
  intent-less legacy row already exists:
  ```sql
  DO $$
  BEGIN
      IF EXISTS (
          SELECT 1 FROM permission_drift
          WHERE permission_intent_id IS NULL
      ) THEN
          RAISE EXCEPTION
              'SLICE-014 D2: pre-existing orphaned permission_drift row; '
              'widening refuses to synthesize a target locator.';
      END IF;
  END
  $$;
  ```

**Non-goals.** No JSONB blob for drift details, no per-run finding child
table, no historical version table. Does not add policy-version or
authority-grant FKs.

### D3 — BINDING: Drift aggregate stays per-row; run-scoped uniqueness key

**Decision.** Each `permission_drift` row remains its own aggregate keyed
by `aggregate_type='permission_drift'` and `aggregate_id=str(drift.id)`.
Drift is *not* re-routed under a run aggregate.

Uniqueness for idempotent re-submission is expressed as a partial unique
index:

```sql
CREATE UNIQUE INDEX uq_permission_drift__run_target
    ON permission_drift (reconciliation_run_id, role_id, kind, channel_id)
    WHERE reconciliation_run_id IS NOT NULL;
```

`NULL`-equality caveat: because `channel_id` can be NULL for guild-role
drift, the index uses the three-column form including `channel_id`; Postgres
treats two NULL `channel_id` values as distinct, so the implementation must
also include a second partial index covering the guild-role case:

```sql
CREATE UNIQUE INDEX uq_permission_drift__run_target_guild
    ON permission_drift (reconciliation_run_id, role_id, kind)
    WHERE reconciliation_run_id IS NOT NULL AND channel_id IS NULL;
```

Reconciliation inserts use `INSERT … ON CONFLICT DO NOTHING` against these
indexes, then read back the existing row, mirroring
`services/api/app/repositories/deferred_effects.py:31-104`.

**Rationale.** Per-drift aggregates preserve per-row OCC required for AC2
(stale resolution → 412). Running resolution through a run aggregate would
couple unrelated drift mutations and block independent officer action
across the same run. Research report §2 (prototyping Q2) specifically asks
this question; keeping drift as its own aggregate matches the shipped
`mutate_entity()` pattern. Run-scoped uniqueness guarantees AC4 idempotent
retries without duplicate rows.

**Binding implications.**
- The drift resolution endpoint demands `If-Match`; service reads the
  aggregate head for that drift id, does not fall back to a silent version
  lookup (removes the existing “optional expected_version” leniency in
  `services/api/app/services/permissions.py:251-264`).
- Reconciliation algorithm (D8) writes drift via `mutate_entity()` with
  `expected_version=0`, inside the same transaction that advances the run.
- For drift created outside a run (e.g. future expiry-driven drift), the
  uniqueness indexes are skipped because `reconciliation_run_id IS NULL`.

**Non-goals.** No cross-run dedup (two runs may each detect the same
target and produce two drift rows). No per-scope uniqueness when
`reconciliation_run_id IS NULL`.

### D4 — BINDING: `permission_reconciliation_runs` table + lifecycle

**Decision.** Create a new table `permission_reconciliation_runs` with
aggregate type `permission_reconciliation_run`:

Columns:

- `id UUID PRIMARY KEY`
- `scope_kind TEXT NOT NULL`
- `scope_id TEXT NULL`
- `requested_by_kind TEXT NOT NULL`
- `requested_by_id TEXT NOT NULL`
- `requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `snapshot_submitted_at TIMESTAMPTZ NULL`
- `reconciled_at TIMESTAMPTZ NULL`
- `failed_at TIMESTAMPTZ NULL`
- `failure_reason TEXT NULL`
- `status TEXT NOT NULL`

Constraints:

- `permission_reconciliation_runs_scope_kind_valid`:
  `scope_kind IN ('global','chapter')`.
- `permission_reconciliation_runs_scope_shape_valid`:
  `scope_kind='chapter'` ⇒ `scope_id IS NOT NULL`; `scope_kind='global'` ⇒
  `scope_id IS NULL`.
- `permission_reconciliation_runs_status_valid`:
  `status IN ('requested','snapshot_submitted','reconciled','failed')`.
- `permission_reconciliation_runs_terminal_shape_valid`:
  - `status='reconciled'` ⇒ `snapshot_submitted_at IS NOT NULL AND
    reconciled_at IS NOT NULL AND failed_at IS NULL`.
  - `status='failed'` ⇒ `failed_at IS NOT NULL AND failure_reason IS NOT
    NULL AND reconciled_at IS NULL`.
  - `status='snapshot_submitted'` ⇒ `snapshot_submitted_at IS NOT NULL AND
    reconciled_at IS NULL AND failed_at IS NULL`.
  - `status='requested'` ⇒ `snapshot_submitted_at IS NULL AND reconciled_at
    IS NULL AND failed_at IS NULL`.

Indexes:

- `ix_permission_reconciliation_runs__scope (scope_kind, scope_id)`
- `ix_permission_reconciliation_runs__status_requested_at (status,
  requested_at)`

State machine (service-level `VALID_TRANSITIONS` constant, not inline
string compares):

- `requested → snapshot_submitted` (snapshot POST)
- `snapshot_submitted → reconciled` (drift materialization succeeds)
- `snapshot_submitted → failed` (diff or insert fails)
- `requested → failed` (operator/system cancellation only — no auto TTL in
  SLICE-014)

`reconciled` and `failed` are terminal.

**Rationale.** AC3 and AC4 both pivot on a run aggregate that owns
idempotency; no table currently exists. The lifecycle matches the ticket
spec (`product-strategy/tickets/SLICE-014.md:39-41`). Terminal-shape
CHECK constraints apply the same defense-in-depth pattern used elsewhere in
the repo (WU-006a variant shape, WU-035 state validity) and align with the
schema-first approach called out in AGENTS.md.

**Binding implications.**
- Aggregate id: `aggregate_type='permission_reconciliation_run'`,
  `aggregate_id=str(run.id)`.
- `scope_id` validated per `scope_kind` on insert and update.
- `requested_by_*` are the *authenticated* actor (service or user) at POST
  `/runs`; spoofing-through-body is rejected (see D7 and D9).
- No implicit TTL cleanup in this slice; the `requested → failed` edge is
  reserved for a future scheduler slice and is not wired yet.

**Non-goals.** No JSONB snapshot archive column (payload is diffed and
discarded). No run/drift materialized join column; drift rows already link
back via `reconciliation_run_id`. No per-scope uniqueness on runs; two
operators may create two runs for the same scope concurrently.

### D5 — BINDING: Drift resolution state machine

**Decision.** The allowed drift state graph is:

- `detected → acknowledged`
- `detected → reconciled`
- `detected → accepted`
- `acknowledged → reconciled`
- `acknowledged → accepted`

Terminal states: `reconciled`, `accepted`. No transitions leave terminal
states. Acknowledging a drift is optional.

Enforcement lives in a `VALID_TRANSITIONS` constant on the drift service
(parallel to `services/api/app/services/applications.py:48` style). Extend
with `.update({...})` when future actions are added — never inline compare.
A CHECK constraint additionally enforces terminal immutability through the
`permission_drift_resolution_shape_valid` rule in D2 (resolved fields are
required for terminals, forbidden for non-terminals) so a terminal row
cannot be silently re-opened without violating the constraint.

**Rationale.** Matches ticket/proposal lifecycle
(`product-strategy/tickets/SLICE-014.md:39-41`,
`product-strategy/proposal.md:543-550`) and research §2. Skipping
`acknowledged` is explicitly permitted by the proposal (“Acknowledge: …
for cases where the operator needs to investigate or coordinate before
resolving”, not a required staging step).

**Binding implications.**
- Service calls must map incoming request `action` → target status through
  a constant map (D6) rather than passing raw status strings.
- Terminal rows refuse further state mutations with HTTP 409 from the
  service layer; OCC failures return 412.

**Non-goals.** No `reopen` action. No multi-step approval ladder.

### D6 — BINDING: Drift resolution request contract

**Decision.** Add a dedicated request contract for
`POST /api/v1/permission-drift/{drift_id}/resolve`:

```python
class PermissionDriftResolutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["acknowledge", "reconcile", "accept"]
    reason: str = Field(min_length=1)
    resolved_by_kind: str | None = None
    resolved_by_id: str | None = None

    @field_validator("reason")
    @classmethod
    def reject_blank_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason must be non-blank")
        return value
```

Action → target status map (constant, not inline):

```python
DRIFT_RESOLUTION_TARGET_STATUS = {
    "acknowledge": "acknowledged",
    "reconcile": "reconciled",
    "accept": "accepted",
}
```

Originating-actor rule (spoof-proofed, same pattern as SLICE-021 /
applications): when the authenticated actor is a **service actor**,
`resolved_by_kind` / `resolved_by_id` in the body is accepted and persisted
as the `resolved_by_*` metadata. When the authenticated actor is a **user
actor**, those two fields are *overridden* (ignored) with the authenticated
actor. This matches
`services/api/app/services/applications.py:189-195` and
`services/api/app/contracts/applications.py:223-227`.

**Rationale.** AC2 requires drift resolution with OCC. The contract must
let the Discord reconciler impersonate the originating operator (service
actor authenticates, but the operator is the human who clicked the button)
without letting a user caller forge attribution. The same precedent is
shipped for applications and chapters
(`services/api/app/services/chapters.py:197-213`).

**Binding implications.**
- `resolved_by_kind` / `resolved_by_id` are only persisted when
  authentication kind is `service`; otherwise the authenticated user
  identity wins.
- `reason` is mandatory for every resolution action, including `acknowledge`
  (matches the spoof-proof pattern for waitlist reasons in SLICE-021).
- The endpoint requires `If-Match` and returns 412 on stale version.
- Terminal transition rejection yields 409 (service-layer) not 412.

**Non-goals.** No multi-drift batch resolve. No resolution without a reason.
No action-specific extra fields in this slice.

### D7 — BINDING: Reconciliation snapshot contracts

**Decision.** Add snapshot contracts in
`services/api/app/contracts/permissions.py`:

```python
class _PermissionSnapshotBase(_PermissionModel):
    role_id: str = Field(min_length=1)

class GuildRolePermissionSnapshotEntry(_PermissionSnapshotBase):
    kind: Literal["guild_role"]
    permission_bits: DecimalBitString

class ChannelRolePermissionSnapshotEntry(_PermissionSnapshotBase):
    kind: Literal["channel_role"]
    channel_id: str = Field(min_length=1)
    allow_bits: DecimalBitString
    deny_bits: DecimalBitString

PermissionSnapshotEntry = Annotated[
    GuildRolePermissionSnapshotEntry | ChannelRolePermissionSnapshotEntry,
    Field(discriminator="kind"),
]

class ReconciliationSnapshotRequest(_PermissionModel):
    entries: list[PermissionSnapshotEntry] = Field(default_factory=list)

    @field_validator("entries")
    @classmethod
    def reject_duplicate_keys(cls, value: list[Any]) -> list[Any]:
        seen: set[tuple[str, str, str | None]] = set()
        for entry in value:
            key = (entry.kind, entry.role_id, getattr(entry, "channel_id", None))
            if key in seen:
                raise ValueError(f"duplicate snapshot entry for {key}")
            seen.add(key)
        return value
```

The reconciliation-run response contract is
`PermissionReconciliationRunRead` returning the run row plus a
`drift_ids: list[UUID]` field populated after reconciliation.

**Rationale.** Variant shape mirrors WU-006a intents exactly
(`services/api/app/contracts/permissions.py:70-80`), preserving round-trip
to decimal bitstrings (`_validate_decimal_bit_string`) and the
`NUMERIC(39,0)` column bounds. Discord snapshots are untrusted input and
must reject duplicate role/channel/kind keys at the contract boundary.

**Binding implications.**
- The snapshot endpoint accepts `entries: list[...]` (possibly empty, which
  reconciles to “everything declared as intent is drifted away”).
- The adapter cannot submit raw ints or hex; it must encode decimal strings
  (same contract as intents).
- The diff engine (D8) consumes these contracts directly, not JSONB blobs.

**Non-goals.** No snapshot archival, no streaming/chunked snapshots, no
pagination in the snapshot payload. No member-scoped entries (already
forbidden by D1).

### D8 — BINDING: Reconciliation algorithm placement and atomicity

**Decision.** Create `services/api/app/services/permission_reconciliation.py`
with entry point:

```python
def submit_reconciliation_snapshot(
    db: PostgresDatabase,
    *,
    run_id: UUID,
    entries: list[PermissionSnapshotEntry],
    actor: ActorIdentity,
) -> PermissionReconciliationRunRead: ...
```

Algorithm (executed inside a single `with db.connection() as conn` that
also wraps every `mutate_entity()` call via the existing mutation
substrate):

1. Load the run by id. If not found → `LookupError` → 404.
2. If `status != 'requested'` AND the run is terminal with the same
   `aggregate_id`, return the cached result for AC4 idempotency: load
   associated drift rows via `reconciliation_run_id` and return. This uses
   `status='reconciled'` for success replay and `status='failed'` propagates
   the original failure reason as a 409 to the adapter so the operator sees
   the prior outcome rather than duplicate work.
3. Otherwise, require `status='requested'`; anything else (e.g. a second
   snapshot submission that finds `snapshot_submitted` without terminal) is
   a 409 conflict.
4. Advance the run `requested → snapshot_submitted` through
   `mutate_entity()` on the run aggregate with `expected_version=0`.
5. Load intents for the run’s scope
   (`(scope_kind, scope_id)` match); normalize to the key
   `(kind, role_id, channel_id)` per research §3.
6. Normalize snapshot entries to the same key.
7. Iterate `sorted(union(intent_keys, snapshot_keys),
   key=(role_id, channel_id or ""))`:
   - equal masks: skip.
   - diverged masks: build drift with intent anchor and both mask sides.
   - intent without snapshot: drift with cleared-state actuals
     (`actual_bits='0'` for guild_role; `actual_allow_bits='0' and
     actual_deny_bits='0'` for channel_role).
   - snapshot without intent: drift with `permission_intent_id=NULL`,
     `intent_version=NULL`, scope/target/kind taken from the snapshot entry
     and the run’s scope.
8. For each drift, `INSERT ... ON CONFLICT (reconciliation_run_id, role_id,
   channel_id, kind) DO NOTHING` through the repository, then read the
   persisted row; each drift insert is wrapped in a `mutate_entity()` for
   its own aggregate so OCC audit rows are produced even under the
   idempotent conflict case.
9. Advance the run `snapshot_submitted → reconciled` via `mutate_entity()`.
10. On any uncaught exception during steps 5–9: the transaction is rolled
    back, then (in a new transaction) the run is advanced
    `snapshot_submitted → failed` with `failure_reason = repr(exc)[:500]`
    and the original exception is translated to the API error response.

**Rationale.** Live-server principle requires that the run and drift rows
commit or fail together (research §3, AC3, AC4). Wrapping steps 4–9 in a
single transaction prevents the “run reconciled, drift never persisted” or
“drift persisted, run stuck in snapshot_submitted” split brain. Step 2
(idempotency replay) satisfies AC4 for retried POSTs that share the same
`run_id`.

**Binding implications.**
- No separate Celery/background worker is introduced in SLICE-014 — the
  snapshot POST runs the diff synchronously.
- The service uses the shipped `mutate_entity()` call pattern with
  `payload_allowlist`, `action_type` constants, and structured state-change
  drafts.
- Failure-terminal replay returns the same failure as the original attempt
  (no retries are magic).

**Non-goals.** No scheduled background reconciliation runs. No partial /
incremental reconciliation. No “reconcile subset of targets” — a run always
reconciles the full scope.

### D9 — BINDING: Permission reconciler service actor

**Decision.** Seed a `permission-reconciler` service-actor authority grant
via the WU-028B-api migration (see D14), using the exact-containment guard
pattern from WU-037 (`migrations/versions/wu-037_ticket_sla_triggers.py:96-
133`):

```sql
INSERT INTO authority_grants (
    id, grantee_id, scope_kind, scope_id, permissions, ...
) SELECT
    gen_random_uuid(),
    'permission-reconciler',
    'global',
    NULL,
    '["permission_intent.read",
      "permission_drift.read",
      "permission_drift.write",
      "permission_reconciliation_run.write"]'::jsonb,
    NULL, NULL, NULL, NULL, NULL
WHERE NOT EXISTS (
    SELECT 1 FROM authority_grants
     WHERE grantee_id = 'permission-reconciler'
       AND scope_kind = 'global'
       AND scope_id IS NULL
       AND permissions @> '[... same array ...]'::jsonb
       AND permissions <@ '[... same array ...]'::jsonb
       AND revoked_at IS NULL
       AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
);
```

Downgrade is a **no-op** with an explanatory comment citing the Live Server
Principle (same precedent as WU-037 / WU-033).

**Rationale.** Research §7 confirms service-actor seeding is the established
mechanism. Exact `@> / <@` containment plus the `expires_at` and
`revoked_at` checks ensure the migration is idempotent and never collides
with an operator-created identical grant. Scheduled/background reconciliation
is deferred; the seeded grant is used only for the Discord adapter’s
service-actor calls (D12).

**Binding implications.**
- Endpoint authority: dependencies require the matching permission name at
  the correct scope (D11).
- No member-scope grants for the reconciler (D1 bans member scope here).
- The same service actor is reused for drift resolution when the Discord
  adapter or a background job later proxies a user-triggered resolution,
  passing `resolved_by_*` in the body per D6.

**Non-goals.** No user-identity grants created or modified by the
migration. No chapter-scoped seeded grant (central reconciler is
global-scoped; chapter-scoped authority is granted to operators through
the existing authority API, not seeded in SLICE-014).

### D10 — BINDING: Endpoint / router layout

**Decision.** Create an `api/v1/endpoints/permissions/` subpackage mirroring
the SLICE-011 pattern
(`services/api/app/api/v1/endpoints/applications/__init__.py`):

```
services/api/app/api/v1/endpoints/permissions/
    __init__.py          # subpackage aggregator router
    intents.py           # POST /permission-intents
                         # PATCH /permission-intents/{intent_id}
                         # GET  /permission-intents
    drift.py             # GET  /permission-drift
                         # POST /permission-drift/{drift_id}/resolve
    reconciliation.py    # POST /permission-reconciliation/runs
                         # POST /permission-reconciliation/runs/{run_id}/snapshots
```

`__init__.py` exposes a single `router = APIRouter()` including each
submodule’s router with tags `permission-intents`, `permission-drift`,
`permission-reconciliation`. `services/api/app/api/v1/router.py` includes
that aggregator router at prefix `/` (no global permission prefix — paths
are absolute per the ticket).

GET `/permission-intents` supports filters:
`scope_kind`, `scope_id`, `role_id`, `channel_id`, `kind`,
`temporary`, `include_expired=false` (bool); default ordering by
`(scope_kind, scope_id NULLS FIRST, role_id, channel_id NULLS FIRST)`.

GET `/permission-drift` supports filters:
`status` (repeatable), `scope_kind`, `scope_id`, `role_id`,
`reconciliation_run_id`, `has_intent` (bool); default ordering by
`detected_at DESC, id`.

All mutation endpoints require `If-Match` headers parsed through the
existing strong-ETag utilities and return fresh ETags on success (same as
SLICE-021).

**Rationale.** Mirrors the SLICE-011 tickets subpackage layout
(`services/api/app/api/v1/endpoints/tickets/...`, applications/...) for
consistency. Filters on drift are required so AC2’s “include orphaned
state” can be queried separately from intent-linked rows.

**Binding implications.**
- The run POST returns `PermissionReconciliationRunRead` with
  `status='requested'` and an empty `drift_ids`. The snapshot POST returns
  the same contract populated post-reconciliation.
- Drift GET returns the same orphaned and intent-linked rows uniformly;
  orphaned rows include `scope_kind`, `scope_id`, `role_id`,
  `channel_id?`, `kind` populated by D2.

**Non-goals.** No UI read model endpoint. No `GET /permission-reconciliation
/runs/{run_id}` in this slice (research §9 Q5 open question — deferred;
clients that need to observe a run poll the snapshot POST with the same
id-idempotent semantics defined in D8).

### D11 — BINDING: Authority permission names

**Decision.** Introduce the following permission name strings, used by
`RequireAuthority(...)` at each endpoint:

| Endpoint | Permission name |
|---|---|
| POST `/permission-intents` | `permission_intent.write` |
| PATCH `/permission-intents/{intent_id}` | `permission_intent.write` |
| GET `/permission-intents` | `permission_intent.read` |
| GET `/permission-drift` | `permission_drift.read` |
| POST `/permission-drift/{drift_id}/resolve` | `permission_drift.write` |
| POST `/permission-reconciliation/runs` | `permission_reconciliation_run.write` |
| POST `/permission-reconciliation/runs/{run_id}/snapshots` | `permission_reconciliation_run.write` |

Scope evaluation: the endpoint resolves the target scope from the request
(intent/drift/run scope) and calls
`evaluate(actor, permission, scope_kind=..., scope_id=...)`. This matches
the pattern in `services/api/app/services/authority.py:224-276` and
`services/api/app/core/dependencies.py:56-138`.

**Rationale.** Consistent with existing permission naming (`roster.read`,
`roster.write`, `application.reactivate`, etc.) and keeps read/write
symmetry. Research §7 confirms no prior permission namespace exists for
these aggregates. SLICE-014 does not ship a new `policy_type` or
permission-policy seed update; existing operator roles acquire these
permissions by explicit authority grants.

**Binding implications.**
- These four permission strings are added to the permission-name registry
  (if one exists in the tree today) or simply used at call sites — no
  policy-version migration is required for SLICE-014 (PolicyVersion
  infrastructure is covered by other slices).
- The seeded reconciler service actor (D9) holds all four.

**Non-goals.** No per-action (acknowledge/reconcile/accept) permission
splits. No read-only drift operator role scheme.

### D12 — BINDING: Discord permission snapshot adapter

**Decision.** Add the following in `services/discord/`:

- `services/discord/app/contracts/permissions.py` — request/response
  contracts mirroring the API (reused where possible).
- `services/discord/app/infrastructure/permission_client.py` — service-actor
  API client wrapper with methods `create_reconciliation_run(scope_kind,
  scope_id, correlation_id)` and `submit_snapshot(run_id, entries,
  correlation_id)`. Authenticates as `permission-reconciler` (D9). Reuses
  existing correlation propagation from
  `services/discord/app/infrastructure/api_client.py:25-65`.
- `services/discord/app/handlers/permissions.py` — handler
  `handle_reconcile_permissions(envelope, api_client, guild) ->
  InteractionResult` that executes:
  1. `ack_deferred` on the interaction.
  2. POST `/permission-reconciliation/runs` with `scope_kind`, `scope_id`,
     `originating_actor_kind`/`originating_actor_id` from the interaction
     member (these are the spoofed-through fields from D6/D9).
  3. Enumerate live Discord state (D13).
  4. POST `/runs/{run_id}/snapshots` with `entries` and an `Idempotency-Key`
     header set to `str(run_id)` (per AC4).
  5. On 200: ephemeral success including the drift count summary.
  6. On 409: read the existing run’s drift ids (step 2 idempotency replay
     in D8) and report the same summary.
  7. On 412: retry by re-fetching the run and resubmitting once; on second
     412, surface an operator error.
  8. On 5xx: ephemeral error with retry guidance. No local state is kept to
     clean up — the run + drift lifecycle is API-owned.
- `services/discord/app/commands/permissions.py` — register a slash command
  `/reconcile-permissions <scope>` that dispatches to the handler.

**Rationale.** The adapter follows the established pattern from
`services/discord/app/handlers/chapters.py:12-16` and
`services/discord/app/handlers/roster.py:16-19`. AGENTS.md Live Server
Principle: visible Discord effect only after API confirms. AC4 mandates
that the Discord adapter never mutates drift rows locally — using the run
id as the idempotency anchor realizes this. No thread/state-local artifacts
are created.

**Binding implications.**
- Discord daemon never calls the drift or intent endpoints directly in
  SLICE-014; only reconciliation.
- `submit_snapshot` reuses the API-provided `run_id` as the retry key; the
  Discord daemon does not generate its own idempotency key.
- Handler is synchronous within the interaction deferred-ack window;
  scope-limited fetching (D13) keeps execution inside the deadline.

**Non-goals.** No interactive drift resolution UI in Discord in this slice
(operators resolve via API / web UI). No background scheduling. No cache
invalidation of guild state.

### D13 — BINDING: Snapshot fetch discipline (rate-limit-aware)

**Decision.** The Discord adapter walks guild/channel state via in-memory
cache only — no `fetch_*` API calls:

- Roles: iterate `guild.roles`, skipping `guild.default_role` and bot roles
  that the managed-intent set should not claim (explicit role-id filter
  unnecessary; the diff algorithm uses the intent set as the managed
  surface).
- Channel overwrites: iterate `guild.channels`, and for each channel,
  iterate `channel.overwrites`
  (a `dict[Role|Member, PermissionOverwrite]` held in the gateway cache).

Scope-limiting rules:

- **`chapter` scope**: enumerate `guild.channels` whose chapter association
  matches `scope_id`. Chapter-to-channel resolution uses the existing
  chapter repository helpers used by
  `services/discord/app/handlers/chapters.py:200-247`; the adapter passes
  the chapter’s role/channel ids rather than walking the entire guild.
- **`global` scope**: submit only `guild.roles` (guild-role permission
  bits). Do **not** walk per-channel overwrites for `global` scope in
  SLICE-014 — channel-level drift belongs to chapter scope.

Snapshot entries always use the decimal-string bitset form
(`_validate_decimal_bit_string`).

**Rationale.** The engineering roadmap calls out rate-limit-aware reads
(research §4). `channel.overwrites` is in-memory on the gateway, so no API
fanout is required. Scoping `global` runs to guild roles keeps the POST
bounded; chapter-scope coverage is sufficient for channel drift because
managed channels belong to chapters under the shipped provisioning model.

**Binding implications.**
- No per-role-per-channel Discord API fetches.
- Tests for the Discord adapter mock `guild.roles` and `guild.channels`;
  they do not mock `fetch_channel` or `fetch_member`.
- Bot / integration-managed overwrites still appear in the snapshot but
  surface as orphaned drift rather than being silently skipped; operators
  decide classification (AC2 coverage).

**Non-goals.** No fetch fallback when cache is cold. No member-level
overwrite serialization. No compression / batching of the snapshot payload.

### D14 — BINDING: Migration chain

**Decision.** Three separate migrations, chained from the current head:

```
wu_035_application_interview   (current head)
  └── wu_027_permission_intents_refinements
        └── wu_028a_permission_drift_widening
              └── wu_028b_permission_reconciliation_runs
```

- **`wu-027_permission_intents_refinements.py`** — D1: scope narrowing
  guard + CHECK constraint swap on `permission_intents`. File name reflects
  ticket WU-027 boundary.
- **`wu-028a_permission_drift_widening.py`** — D2: new columns, new
  CHECK constraints, new indexes on `permission_drift`. No cross-table FK
  yet (see wu-028b).
- **`wu-028b_permission_reconciliation_runs.py`** — D4: create
  `permission_reconciliation_runs`; then add FK from
  `permission_drift.reconciliation_run_id` to
  `permission_reconciliation_runs.id ON DELETE RESTRICT`; then add the
  partial unique indexes from D3; then seed the `permission-reconciler`
  service actor from D9.

Each migration’s `downgrade()` is a **no-op** with an explanatory comment
citing the Live Server Principle, matching WU-033, WU-037, and WU-042
precedent.

**Rationale.** Splitting the three migrations matches the WU boundaries
(WU-027, WU-028A, WU-028B-api) in the ticket and keeps rollback granular
should a defect be found post-deploy. The run FK lives on the drift
widening *after* run-table creation, so each migration is individually
applicable. AGENTS.md forbids modifying shipped migrations.

**Binding implications.**
- All three files are added under `migrations/versions/` with
  Alembic-standard `revision`/`down_revision` keys.
- The service-actor seed (D9) is embedded in `wu-028b` (the last migration
  in the chain) so it runs after the run-table exists.

**Non-goals.** No consolidation into a single migration. No touch of any
unrelated table. No renaming of existing shipped migrations.

### D15 — BINDING: Test boundaries per work unit

**Decision.** Test file layout and boundary:

- **WU-027 tests**: `services/api/tests/test_permission_intents.py` —
  CRUD through the API router, OCC 412 on PATCH with stale `If-Match`,
  scope validation (D1 narrow), variant-shape validation, read filter
  coverage.
- **WU-028A tests**: `services/api/tests/test_permission_drift.py` —
  GET filter behavior (status, scope, orphaned), POST resolve transitions
  (D5), resolve OCC 412, resolve 409 on terminal, spoof-proof
  `resolved_by_*` for user vs service actors (D6).
- **WU-028B-api tests**:
  `services/api/tests/test_permission_reconciliation_api.py` — run
  creation, snapshot idempotent replay under retry (D8 step 2), drift
  materialization with mismatch / missing-snapshot / orphaned-actual cases
  (AC3), failure-path terminal assertion, transaction atomicity (run and
  drift commit together).
- **WU-028B-discord tests**:
  `services/discord/tests/test_permission_reconciliation_adapter.py` —
  handler flow (`ack_deferred` → API → visible effect), chapter / global
  scope enumeration (D13), decimal-bitset serialization, retry uses
  `run_id` as idempotency key (AC4), 412 retry-once behavior, cache-only
  fetch discipline (mocks assert no `fetch_channel` / `fetch_member`).

Each test carries an AC-referenced docstring (`"""AC1: ..."""` /
`"""AC2: ..."""` / etc.) following SLICE-021 precedent.

Per AGENTS.md, **the test agent sees only the contracts**
(`services/api/app/contracts/permissions.py`,
`services/discord/app/contracts/permissions.py`, endpoint signatures,
command definitions). It does not see the service / repository / handler
implementations.

**Rationale.** Matches the work unit decomposition in the ticket
(`product-strategy/tickets/SLICE-014.md:46-50`) and the test/code agent
separation rule in AGENTS.md. Per-AC docstrings keep traceability from
test → AC as shipped in SLICE-019, SLICE-021, SLICE-023.

**Binding implications.**
- Discord tests do not make live Discord calls; `discord.py` objects are
  mocked.
- API tests use `httpx.AsyncClient` against the FastAPI app fixture (same
  pattern as the shipped test suites).
- Reconciliation tests seed intents via the intent API, not by direct DB
  writes — this keeps the test against public contract.

**Non-goals.** No cross-service E2E tests in SLICE-014 (deferred to a
future integration slice). No property-based / fuzz tests for the diff
engine in this slice.

## Proposal Constraints

- Do not re-introduce `scope_kind='member'` for PermissionIntent in any
  layer (contract, service, schema).
- Do not park a legacy `permission_drift_findings` table; widening is
  in place.
- Drift rows remain per-row aggregates with per-drift OCC. Do not route
  resolution mutations through the run aggregate.
- The Discord adapter does not own lifecycle state for runs or drift — the
  API is the source of truth, and the Discord side only reports outcome.
- No background scheduled reconciliation in this slice (D9 grant is for
  manual adapter-triggered runs only).
- No `policy_version` / seeded operator policy changes — new permission
  names are introduced only as authority-grant strings.
- No backwards-compatibility shims or aliases anywhere in the permission
  surface (AGENTS.md No Backwards Compatibility).
- No magic action_type / change_type strings anywhere in the new service —
  constants only; `VALID_TRANSITIONS` is extended with `.update({...})`
  patterns.
- All mutations go through `mutate_entity()` with explicit
  `payload_allowlist`; originating actor fields in request bodies are
  service-actor-only (D6, D9).
- Migration downgrades are no-ops with Live-Server-Principle comments; no
  destructive revert of seeded service-actor grants.

## Summary Table

| ID  | Decision |
|-----|----------|
| D1  | Narrow intent scope to `global|chapter` via forward migration with guard; no `member`. |
| D2  | Widen `permission_drift` in place with target locator, run anchor, resolution metadata, variant/scope/resolution CHECKs. |
| D3  | Keep drift as per-row aggregate; idempotency via partial unique indexes on `(run_id, role_id, channel_id, kind)`. |
| D4  | Create `permission_reconciliation_runs` table; lifecycle `requested → snapshot_submitted → reconciled | failed`. |
| D5  | Drift state machine `detected → {acknowledged, reconciled, accepted}`, `acknowledged → {reconciled, accepted}`; terminals immutable. |
| D6  | Drift resolve request contract with action/reason/resolved-by, spoof-proof for user vs service actors. |
| D7  | Variant-shaped snapshot entries with duplicate-key rejection; decimal-bitset round-trip. |
| D8  | Single-tx reconciliation algorithm in `permission_reconciliation.py` with idempotent terminal replay. |
| D9  | Seed `permission-reconciler` service actor with read+write permissions via `@>/<@` guard; downgrade is no-op. |
| D10 | Subpackage `api/v1/endpoints/permissions/` mirroring applications; GET filters defined. |
| D11 | Permission names: `permission_intent.read|write`, `permission_drift.read|write`, `permission_reconciliation_run.write`. |
| D12 | Discord adapter: service-actor client, `/reconcile-permissions` handler, run-id idempotency, cache-only reads. |
| D13 | In-memory guild/channel cache only; chapter scope walks chapter channels; global scope walks roles only. |
| D14 | Migration chain `wu-027 → wu-028a → wu-028b`; downgrades no-op. |
| D15 | Test boundaries: four test files matching WU-027 / WU-028A / WU-028B-api / WU-028B-discord; AC docstrings. |
