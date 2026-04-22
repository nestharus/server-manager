# SLICE-014 Research: Permission Intent And Drift Detection

## 1. Domain Model

### Existing permission foundations in the repo today

#### `permission_intents`

Source of truth: `migrations/versions/wu-006a_permission_intents_foundation.py:16-85`.

- Columns
  - `id UUID PRIMARY KEY`
  - `kind TEXT NOT NULL`
  - `scope_kind TEXT NOT NULL`
  - `scope_id TEXT NULL`
  - `role_id TEXT NOT NULL`
  - `channel_id TEXT NULL`
  - `permission_bits NUMERIC(39,0) NULL`
  - `allow_bits NUMERIC(39,0) NULL`
  - `deny_bits NUMERIC(39,0) NULL`
  - `reason TEXT NULL`
  - `temporary BOOLEAN NOT NULL`
  - `expires_at TIMESTAMPTZ NULL`
  - `created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`
- Constraints
  - `permission_intents_kind_valid`: `kind IN ('guild_role', 'channel_role')`
  - `permission_intents_scope_kind_valid`: `scope_kind IN ('global', 'chapter', 'member')`
  - `permission_intents_temporary_shape_valid`: temporary rows require `expires_at`; non-temporary rows forbid it
  - `permission_intents_variant_shape_valid`: `guild_role` rows require `permission_bits` and forbid channel overwrite fields; `channel_role` rows require `channel_id`, `allow_bits`, and `deny_bits`, and forbid `permission_bits`
- Indexes
  - `ix_permission_intents__scope_kind (scope_kind, scope_id)`
  - `ix_permission_intents__role_id (role_id)`
  - `ix_permission_intents__expires_at (expires_at) WHERE temporary`

Current contract/service shape:

- Pydantic models split intents into `GuildRolePermissionIntent` and `ChannelRolePermissionIntent`, with decimal-string masks rather than integers: `services/api/app/contracts/permissions.py:20-172`.
- Repository normalization converts Postgres `NUMERIC` to canonical decimal strings on read: `services/api/app/repositories/permissions.py:11-32`.
- The service does not store a physical `version` column on `permission_intents`; OCC version lives in `aggregate_heads`, keyed by a compound aggregate id derived from `(scope_kind, scope_id, role_id, channel_id)`: `services/api/app/services/permissions.py:29-41`, `services/api/tests/test_permission_intent_foundation.py:359-399`.

Important mismatch with the ticket:

- The foundation is already more specific than the ticket summary. It does not model one generic `permission_bits` field for all intents; it models `guild_role` vs `channel_role` variants.
- The foundation also allows `scope_kind='member'`, but the proposal’s PermissionIntent table describes scope as `global` or chapter FK only: `product-strategy/proposal.md:515-528`.

#### `permission_drift`

Source of truth: `migrations/versions/wu-006b_permission_drift_foundation.py:16-79`.

- Columns
  - `id UUID PRIMARY KEY`
  - `permission_intent_id UUID NULL`
  - `intent_version BIGINT NULL`
  - `actual_bits NUMERIC(39,0) NULL`
  - `actual_allow_bits NUMERIC(39,0) NULL`
  - `actual_deny_bits NUMERIC(39,0) NULL`
  - `intended_bits NUMERIC(39,0) NULL`
  - `intended_allow_bits NUMERIC(39,0) NULL`
  - `intended_deny_bits NUMERIC(39,0) NULL`
  - `status TEXT NOT NULL`
  - `detected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`
- Constraints
  - FK `fk_permission_drift__permission_intent_id__permission_intents` to `permission_intents.id` with `ON DELETE RESTRICT`
  - `permission_drift_status_valid`: `status IN ('detected', 'acknowledged', 'reconciled', 'accepted')`
  - `permission_drift_intent_anchor_valid`: `permission_intent_id` and `intent_version` must be both set or both null
- Indexes
  - `ix_permission_drift__permission_intent_id (permission_intent_id)`
  - `ix_permission_drift__status (status)`
  - `ix_permission_drift__detected_at (detected_at)`

Current contract/service shape:

- The contract mirrors the table exactly and enforces the intent-anchor invariant: `services/api/app/contracts/permissions.py:153-172`.
- The service writes drift rows as their own aggregates keyed by drift UUID, not by permission target: `services/api/app/services/permissions.py:216-243`.
- Status updates go through `mutate_entity()`, but the service only re-validates the enum; it does not enforce a lifecycle graph or store resolution metadata: `services/api/app/services/permissions.py:246-290`.

Major gap relative to SLICE-014:

- The table has no target locator for orphaned drift. If `permission_intent_id` is null, the row has no `scope_kind`, `scope_id`, `role_id`, `channel_id`, or `kind`, so unmanaged live Discord state is not identifiable from the row alone.
- The table also has no `resolved_by`, `resolved_at`, or reconciliation-run anchor, even though the proposal’s drift object includes resolution metadata: `product-strategy/proposal.md:536-550`.

#### `chapter_templates.default_permission_intents`

Permission-adjacent schema from the same foundation path:

- Foundation table includes `default_permission_intents JSONB NOT NULL`: `migrations/versions/wu-007a_chapter_templates_foundation.py:16-48`.
- The current table has later-added `template_family_id` and `version` columns from `wu-018`: `migrations/versions/wu-018_chapter_templates.py:16-47`.
- Current contract shape for default intents is separate from runtime PermissionIntent rows and already mirrors `guild_role` vs `channel_role` plus temporary expiry semantics: `services/api/app/contracts/chapter_templates.py:31-67`.

#### Versioning substrate used by permission aggregates

Source of truth: `migrations/versions/wu-002_activity_substrate.py:69-135`, `migrations/versions/wu-003a_widen_aggregate_id.py:19-40`.

- `aggregate_heads`
  - `aggregate_type TEXT`
  - `aggregate_id TEXT`
  - `current_seq BIGINT NOT NULL DEFAULT 0`
  - `latest_change_id BIGINT NULL`
- `activity_actions`
  - mutable-action audit rows with `aggregate_type`, `aggregate_id`, `actor_kind`, `actor_id`, request surface, request JSON, status
  - correlation/scope columns added later in `wu-003b`: `migrations/versions/wu-003b_audit_context_columns.py:16-49`
- `activity_state_changes`
  - immutable accepted changes keyed by `(aggregate_type, aggregate_id, aggregate_seq)`

`mutate_entity()` is the shared OCC + audit writer for all of this: `services/api/app/services/mutations.py:58-225`.

### `authority_grants` versus declared permission intent

These are different concepts.

- `authority_grants` are API capability grants for actors. They answer “may actor X perform operation Y in scope Z?” and carry a JSONB permission set such as `chapter.read` or `roster.write`: `migrations/versions/wu-004_authority_foundation.py:16-74`, `services/api/app/contracts/authority.py:20-77`, `services/api/app/services/authority.py:224-301`.
- `PermissionIntent` is declared desired Discord resource state for a role or role-channel tuple. It answers “what permission configuration should exist in Discord?”: `product-strategy/proposal.md:511-528`.

Operationally, they are orthogonal:

- `authority_grants` gate control-plane mutations inside our API.
- `permission_intents` declare target state in Discord and are themselves subject to authority checks.

The current permission foundation accidentally blurs none of this in schema, but the current permission service is still only a foundation helper: it hardcodes `actor_kind='system'` / `actor_id='permissions-service'` and has no authority enforcement or user/service actor input yet: `services/api/app/services/permissions.py:44-55`.

### What “PermissionIntent” means versus `authority_grants`

The proposal is explicit:

- PermissionIntent is “the declarative model of what permissions should exist” and is operator-facing intended state: `product-strategy/proposal.md:528-530`.
- AuthorityGrant is scoped operational authority and later write surfaces deny on missing grant: `product-strategy/proposal.md:556-579`, `product-strategy/proposal.md:774-786`.

The shipped code agrees with that split:

- authority enforcement is implemented by `evaluate()` and `RequireAuthority(...)`: `services/api/app/services/authority.py:224-276`, `services/api/app/core/dependencies.py:56-138`
- nothing in the authority substrate models Discord overwrite state

### Valid scope kinds for intents

Current code:

- `ScopeKind = Literal["global", "chapter", "member"]`: `services/api/app/contracts/scope.py:1-5`
- both permission contract and migration reuse that wider set: `services/api/app/contracts/permissions.py:52-80`, `migrations/versions/wu-006a_permission_intents_foundation.py:41-44`

Proposal/problem intent:

- the PermissionIntent table in the proposal says scope is `global` or chapter FK only: `product-strategy/proposal.md:517-528`
- the problem statement discusses server-wide and chapter/governance complexity, not member-scoped permission intent: `product-strategy/problem.md:77-87`

Research conclusion:

- The current foundation allows `member`, but the product docs for PermissionIntent point to `global` and `chapter` only.
- This is an explicit synthesis question, not a settled fact.

## 2. State Machines

### PermissionIntent

There is no explicit lifecycle state in the shipped foundation.

- Current behavior is create/update only, with temporal shape validation (`temporary` + `expires_at`): `services/api/app/contracts/permissions.py:52-151`
- OCC is already required for update through `mutate_entity()`: `services/api/app/services/permissions.py:149-202`, `services/api/tests/test_permission_intent_foundation.py:402-423`

### PermissionDrift lifecycle

Ticket/proposal lifecycle:

- `detected -> acknowledged -> reconciled | accepted`: `product-strategy/tickets/SLICE-014.md:39-41`, `product-strategy/proposal.md:543-550`

Operational meaning from the proposal:

- `detected`: reconciliation found divergence
- `acknowledged`: operator marked the drift known and deferred
- `reconciled`: system applied intent to Discord
- `accepted`: operator decided reality is correct and the intended state should be updated to match

Current code gap:

- the shipped service accepts any enum value transition and does not enforce `detected`-first or terminal resolution semantics: `services/api/app/services/permissions.py:246-290`
- there are no resolution fields yet

### PermissionReconciliationRun lifecycle

Ticket lifecycle:

- `requested -> snapshot_submitted -> reconciled | failed`: `product-strategy/tickets/SLICE-014.md:23-24`, `product-strategy/tickets/SLICE-014.md:39-41`

Interpretation against current architecture:

- `requested`: API has created a run aggregate for a scope and returned a run id
- `snapshot_submitted`: the Discord adapter has POSTed a typed live-state snapshot for that run id
- `reconciled`: the API has diffed snapshot vs intents and materialized the drift set
- `failed`: snapshot processing failed and the run has an error terminal state

There is no existing schema, contract, service, or endpoint for runs in the current tree.

### OCC requirements

Confirmed today:

- Intent OCC already exists and is routed through `mutate_entity()`: `services/api/app/services/permissions.py:132-146`, `services/api/app/services/permissions.py:188-202`, `services/api/tests/test_permission_intent_foundation.py:402-423`
- Drift OCC technically exists in the service because drift status updates use `mutate_entity()`: `services/api/app/services/permissions.py:278-290`

Important caveat:

- Drift OCC is optional in the current service. If `expected_version` is omitted, the service reads the current head and uses it implicitly: `services/api/app/services/permissions.py:251-264`
- SLICE-014 AC2 requires stale resolution to return HTTP 412, so the eventual drift-resolution endpoint must require `If-Match` and must not rely on that fallback

## 3. Reconciliation Algorithm

No reconciliation implementation exists yet. The algorithm below is a ticket/proposal binding, not a description of shipped code.

### Normalized comparison key

Given the shipped foundation, the natural normalized key is:

- `kind`
- `role_id`
- `channel_id` where `None` means guild-level

For deterministic ordering inside one scope, sort by:

1. `role_id`
2. `channel_id or ""`

That ordering is stable and matches the aggregate-id helper’s distinction between null and non-null channel targets: `services/api/app/services/permissions.py:29-41`, `services/api/tests/test_permission_intent_foundation.py:438-470`.

### Pseudocode

```text
load intents for requested scope
normalize each intent to key -> intended mask payload

load actual Discord snapshot for requested scope
normalize each snapshot entry to key -> actual mask payload

for key in sorted(union(intent_keys, actual_keys), key=(role_id, channel_id or "")):
    intended = intents.get(key)
    actual = snapshot.get(key)

    if intended and actual and masks_equal(intended, actual):
        continue

    if intended and actual and not masks_equal(intended, actual):
        emit drift:
          permission_intent_id = intended.id
          intent_version = intended.version
          intended_* = intended masks
          actual_* = actual masks
          status = detected

    elif intended and not actual:
        emit drift:
          permission_intent_id = intended.id
          intent_version = intended.version
          intended_* = intended masks
          actual_* = cleared-state sentinel
          status = detected

    elif actual and not intended:
        emit drift:
          permission_intent_id = NULL
          intent_version = NULL
          intended_* = NULL
          actual_* = actual masks
          status = detected
```

### Edge cases that matter here

- Guild-role versus channel-role rows must stay separate. The shipped foundation already treats them as different shapes, so reconciliation cannot collapse them into one generic mask.
- “Actual missing” should be represented as a cleared-state value, not absence of the drift row. For the shipped variant model that means:
  - guild-role: `actual_bits = "0"`
  - channel-role: `actual_allow_bits = "0"` and `actual_deny_bits = "0"`
- Orphaned/unmanaged actual state requires a target locator in the drift payload or related run snapshot rows. The current `permission_drift` table cannot represent that yet.
- Expired temporary intents are explicitly part of the same workflow in the proposal: `product-strategy/proposal.md:530`, `product-strategy/proposal.md:746`

### Idempotency on run re-submission

Ticket requirement:

- same `run_id` retry must not duplicate drift rows; the Discord adapter reuses the API run id as idempotency key: `product-strategy/tickets/SLICE-014.md:63`

Relevant existing precedent:

- deferred effects use `INSERT ... ON CONFLICT (idempotency_key) DO NOTHING` then load the existing row: `services/api/app/repositories/deferred_effects.py:31-104`

Research conclusion:

- A reconciliation run should be the idempotency boundary.
- Today there is no run table and no way to attach drift rows to a run, so idempotent “same run id returns same drift set” behavior is not currently representable.

## 4. Discord Adapter Shape + Rate-Limit Plan

### What exists today

There is no permission-specific Discord adapter in the current tree:

- no `services/discord/app/contracts/permissions.py`
- no `services/discord/app/handlers/permissions.py`
- no `services/discord/app/infrastructure/permission_client.py`

The existing Discord runtime patterns are:

- API-backed service actor calls with explicit headers: `services/discord/app/handlers/chapters.py:12-16`, `services/discord/app/handlers/roster.py:16-19`
- correlation propagation through the Discord interaction registry and API client: `services/discord/app/commands/registry.py:28-33`, `services/discord/app/infrastructure/api_client.py:25-65`
- read-through against guild cache first, then fetch fallback only when needed:
  - roster member resolution checks `guild.members`, `guild.get_member`, then `fetch_member`: `services/discord/app/handlers/roster.py:53-78`
  - role/channel provisioning uses `guild.roles`, `guild.categories`, and `guild.channels`: `services/discord/app/handlers/chapters.py:200-247`

### What the snapshot adapter will need to fetch

Inference from the shipped runtime shell and the permission model:

- one guild-level role pass
- one channel pass that inspects per-channel overwrite data for roles

The expensive shape is not “N_roles x N_channels API calls” if the adapter walks the in-memory guild/channel objects once and serializes their overwrite maps. That is also consistent with the roadmap note that VS-008 needs “Discord permission readers” and “rate-limit-aware reads” rather than Discord write-path fanout: `product-strategy/engineering-roadmap-revision-cycle3.md:76-80`, `product-strategy/engineering-roadmap-revision-cycle8.md:22-25`.

### Snapshot payload shape for `POST /snapshots`

No contract exists yet. Minimum shape implied by the current intent foundation is:

```text
PermissionSnapshotSubmit
  snapshot_entries: list[PermissionSnapshotEntry]

PermissionSnapshotEntry
  kind: Literal["guild_role", "channel_role"]
  role_id: str
  channel_id: str | None
  permission_bits: DecimalBitString | None
  allow_bits: DecimalBitString | None
  deny_bits: DecimalBitString | None
```

Reasoning:

- current intent/drift schemas are already variant-shaped around `guild_role` vs `channel_role`: `services/api/app/contracts/permissions.py:70-80`, `migrations/versions/wu-006a_permission_intents_foundation.py:50-65`
- decimal-string masks are the current contract boundary, not raw Python ints: `services/api/app/contracts/permissions.py:20-30`

### Rate-limit handling

Current architecture gives two existing patterns:

- inline Discord handlers for bounded work: chapter provisioning and roster sync
- background/scheduled worker substrate for retryable or larger units of work: `services/api/app/services/deferred_effects.py:161-223`

Research conclusion:

- small manual chapter-scoped snapshots could run inline from the Discord daemon
- scheduled or wide-scope reconciliation is a better fit for background execution because the codebase already has worker/retry discipline and the roadmap explicitly calls out rate-limit-aware reads

## 5. Contract Surfaces

There are no shipped permission API routes yet. `services/api/app/api/v1/router.py:11-42` includes no permissions router.

The ticket names eight concrete surfaces, not nine: seven HTTP endpoints plus one Discord handler. A dedicated run-read endpoint is not currently specified in the ticket.

### Existing shipped permission contracts

- `PermissionIntentCreate`
- `PermissionIntentUpdate`
- `PermissionIntentRead`
- `PermissionDriftRead`

Sources: `services/api/app/contracts/permissions.py:101-188`.

### Ticket-bound HTTP surfaces

#### 1. `POST /api/v1/permission-intents -> PermissionIntentRead`

- Request body can reuse the existing discriminated `PermissionIntentCreate`: `services/api/app/contracts/permissions.py:105-142`
- Response should be `PermissionIntentRead`
- Should return strong `ETag` like other mutation endpoints: `services/api/app/contracts/mutations.py:44-52`, `services/api/app/api/v1/endpoints/roster.py:56-57`

#### 2. `PATCH /api/v1/permission-intents/{intent_id} -> PermissionIntentRead`

- Request body can reuse `PermissionIntentUpdate`: `services/api/app/contracts/permissions.py:144-150`
- Must require `If-Match` and translate stale writes to 412, following the shared mutation contract: `services/api/app/contracts/mutations.py:28-52`

#### 3. `GET /api/v1/permission-intents?scope_kind={kind}&scope_id={id} -> list[PermissionIntentRead]`

- Query surface is in the ticket: `product-strategy/tickets/SLICE-014.md:27-34`
- No repository/service list helper exists yet. Current repo only supports fetch-by-id: `services/api/app/repositories/permissions.py:89-106`, `services/api/app/services/permissions.py:205-213`

#### 4. `GET /api/v1/permission-drift -> list[PermissionDriftRead]`

- Current contract exists, but it is too narrow for orphaned drift because it has no target locator: `services/api/app/contracts/permissions.py:153-172`
- Filters are unspecified in the ticket and remain an open question

#### 5. `POST /api/v1/permission-drift/{drift_id}/resolve -> PermissionDriftRead`

- No request model exists yet
- Minimum body implied by the proposal is a resolution action selecting one of `acknowledged | reconciled | accepted`: `product-strategy/proposal.md:547-550`
- Must require `If-Match` per AC2: `product-strategy/tickets/SLICE-014.md:60-63`

#### 6. `POST /api/v1/permission-reconciliation/runs -> PermissionReconciliationRunRead`

- No run contracts exist yet
- Minimum request shape implied by the ticket:
  - `scope_kind`
  - `scope_id`
  - possibly requester metadata only if service-authenticated manual triggers need attribution

#### 7. `POST /api/v1/permission-reconciliation/runs/{run_id}/snapshots -> PermissionReconciliationRunRead`

- No snapshot submission contract exists yet
- This is the idempotent adapter callback surface bound to `run_id`

### Discord handler surface

#### 8. `submit_permission_snapshot(command: ReconciliationRunCommand) -> PermissionReconciliationSubmissionRead`

There is no current contract or handler file for this. Existing Discord command-handler shape is:

- `InteractionEnvelope` input
- `InteractionResult` output
- per-command handler functions registered in the interaction registry: `services/discord/app/contracts/interactions.py:10-37`, `services/discord/app/commands/registry.py:14-33`

Research conclusion:

- the ticket’s named handler is a not-yet-shipped application-level contract, not an existing runtime interface
- if it follows current patterns, it will authenticate to the API as a service actor and preserve the originating Discord user in the request body when the trigger is manual

## 6. Migration Chain + Aggregate Types

### Migration chain head

- `migrations/versions/wu-035_application_interview.py:9-12` defines the current latest revision as `wu_035_application_interview`

### What new migrations actually need to do

The repo already has phase-0 permission tables from `wu-006a` and `wu-006b`. New SLICE-014 migrations therefore need to alter existing tables and add the missing run table; they do not create permission foundations from scratch.

Likely work implied by the current gaps:

- `wu-027_permission_intents.py`
  - constrain or clarify scope handling if `member` is no longer valid
  - possibly add uniqueness/index support if the API needs stronger read/query guarantees than the current aggregate-id-only discipline
- `wu-028a_permission_drift_api.py`
  - widen `permission_drift` so orphaned/unmanaged state can be located and resolution metadata can be stored
  - likely add run linkage
- `wu-028b_permission_reconciliation_runs.py`
  - add the run aggregate table because nothing like it exists today

The ticket’s “or consolidated” note is accurate. Given the current schema gaps, drift widening and run creation are tightly coupled.

### Aggregate type values

`aggregate_heads.aggregate_type` is plain `TEXT`; there is no enum or registry table: `migrations/versions/wu-002_activity_substrate.py:113-135`.

So:

- no schema migration is needed to “register” aggregate types
- current code already uses:
  - `permission_intent`
  - `permission_drift`
  - `authority_grant`
  - other slice-specific values
- only `permission_reconciliation_run` is truly new at the aggregate-head level

## 7. Service-Actor Pattern For The Reconciler

### Existing service-actor precedent

Discord/API service actors are already a normal pattern.

- Provisioning handler authenticates as `discord-provisioner`: `services/discord/app/handlers/chapters.py:12-16`
- Roster sync authenticates as `roster-syncer`: `services/discord/app/handlers/roster.py:16-19`
- Service actors are granted authority in migrations:
  - `discord-provisioner`: `migrations/versions/wu-019_chapter_lifecycle.py:107-142`
  - `roster-syncer`: `migrations/versions/wu-033_roster.py:134-169`
  - `sla-worker`: `migrations/versions/wu-037_ticket_sla_triggers.py:96-133`
  - `chapter-archiver`: `migrations/versions/wu-042_chapter_governance.py:165-202`

### Originating-user attribution precedent

This pattern already exists.

- Chapter service writes `originating_user_discord_id` only when the originating actor in the request body is a user: `services/api/app/services/chapters.py:197-213`, `services/api/app/services/chapters.py:420-430`
- Application contracts explicitly say body `originating_*` fields are only honored for service-authenticated callers; user callers are normalized to the authenticated actor: `services/api/app/contracts/applications.py:223-227`, `services/api/app/services/applications.py:189-195`

Research conclusion:

- A permission reconciler should follow the same pattern:
  - API authentication by a seeded service actor
  - optional `originating_actor_kind/id` in body for manual Discord-triggered runs
  - API ignores/spoof-proofs those fields for non-service callers

### What grants exist today for permissions

None.

- There are no existing authority permission names for permission intents/drift/runs in the tree: only foundation action/change names like `permission_intent.create` exist in the internal mutation log: `services/api/app/services/permissions.py:128-141`, `services/api/app/services/permissions.py:227-240`

So a seeded reconciler actor is very likely needed, but the exact permission namespace is not yet established in code. The user’s suggested names such as `permission_intent.read` / `permission_drift.write` are consistent with current naming style, but they are still inference rather than shipped fact.

## 8. Prototyping Questions

Ticket says prototyping is required: `product-strategy/tickets/SLICE-014.md:67-70`.

### 1. Orphaned drift data model

Problem:

- current `permission_drift` rows cannot identify unmanaged actual Discord state because there is no target locator when `permission_intent_id` is null

Spike:

- prove whether orphaned drift should remain its own aggregate with added target columns, or whether drift findings should instead be run-scoped rows attached to `permission_reconciliation_run`

### 2. Run-idempotency versus per-drift aggregates

Problem:

- same `run_id` retry must return the same drift rows
- current drift writes create one aggregate head per drift UUID

Spike:

- compare:
  - distinct `permission_drift` aggregates with stable per-run/per-target uniqueness
  - run-scoped finding rows materialized under the run aggregate only
- measure the aggregate-head write amplification and the ergonomics of subsequent resolution APIs

### 3. Discord snapshot serialization path

Problem:

- the old candidate question about `BIGINT` is partly stale because the shipped foundation already chose decimal-string contracts plus `NUMERIC(39,0)`: `migrations/versions/wu-006a_permission_intents_foundation.py:25-27`, `services/api/app/contracts/permissions.py:20-30`, `services/api/tests/test_permission_intent_foundation.py:324-330`

Spike:

- validate one full read-through of guild roles plus channel overwrites into the existing decimal-string mask format
- confirm the adapter can avoid per-role/per-channel fetch fanout and can round-trip overwrite masks into the intended API payload shape

## 9. Open Questions For Synthesis

1. Should PermissionIntent scope be narrowed from the shipped `global|chapter|member` foundation to `global|chapter` only?
2. How should orphaned drift be represented durably: widened `permission_drift` rows, or run-scoped findings attached to `permission_reconciliation_run`?
3. What is the intended behavior of `accepted` for orphaned drift with `permission_intent_id = NULL`? Does it create a new intent, or only mark the finding resolved?
4. Should reconciliation runs be chapter-scoped only at first, or also support `global` snapshots in phase 1?
5. Does the ticket need an explicit `GET /api/v1/permission-reconciliation/runs/{run_id}` read surface for adapter retry/poll ergonomics, or is the create+submit flow sufficient?
6. What exact authority permission names will gate operator reads/writes and the seeded reconciler service actor, given that no permission-management namespace exists yet?

## Final Summary

- The shipped foundation already includes `permission_intents` and `permission_drift`, but only as phase-0 storage/helpers; there are still no permission API routes or Discord permission adapter files in the repo.
- `authority_grants` and declared permission intent are orthogonal systems: one governs actor capabilities inside the API, the other declares desired Discord state.
- The current drift schema is too narrow for SLICE-014’s operator workflow. It cannot identify orphaned/unmanaged live Discord state and does not store resolution metadata or reconciliation-run linkage.
- Intent OCC is already in place through `mutate_entity()`. Drift OCC exists at the service layer too, but the future API must require `If-Match` explicitly to satisfy AC2.
- The most important prototype question is the data model boundary: whether drift remains a standalone aggregate per target or becomes a run-scoped finding set attached to a reconciliation-run aggregate.
