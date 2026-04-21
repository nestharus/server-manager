# SLICE-018 Phase 3: Proposal

## 1. Source

This proposal implements WU-033 and WU-034 from
`product-strategy/tickets/SLICE-018.md`: operators can add members directly to
a chapter roster, transition roster status or role with attribution, enforce
optimistic concurrency, and queue a consequential deferred effect when Discord
role synchronization fails.

Primary source inputs:

- `.pipeline/research.md` establishes the implementation substrate: keep
  `roster_entries` as aggregate type `roster_entry`, read version from
  `aggregate_heads`, mirror `chapter_transitions`, resolve Discord role IDs via
  `chapters.discord_resources.role_ids[chapter_role.name]`, keep
  `member_id TEXT`, use chapter-scoped authority for operator endpoints, and
  record Discord sync failure through the API rather than writing directly from
  Discord.
- `.pipeline/synthesis.md` is binding. D1-D12 define the roster aggregate,
  transition matrix, projection pattern, chapter role identity, member identity,
  current roster uniqueness, authority model, Discord idempotency, deferred
  effect semantics, service actor, originating-user propagation, and anti-scope.
- Existing merged code provides the patterns to extend:
  `services/api/app/services/mutations.py` for OCC and aggregate heads,
  `services/api/app/services/chapters.py` and
  `services/api/app/repositories/chapter_transitions.py` for transition
  projections and failed-provisioning deferred effects,
  `services/api/app/repositories/chapters.py` for version joins,
  `services/discord/app/handlers/chapters.py` for the SLICE-013
  Discord-to-API service actor flow, and the WU-007B/WU-007C roster and
  chapter-role foundation migrations/contracts/services.

## 2. In Scope / Out of Scope

In scope:

- Extend, not replace, the existing roster foundation from
  `migrations/versions/wu-007c_roster_foundation.py`,
  `services/api/app/contracts/roster.py`,
  `services/api/app/repositories/roster.py`, and
  `services/api/app/services/roster.py`.
- Add `migrations/versions/wu-033_roster.py` with roster lifecycle schema:
  adjusted `roster_entries` columns/constraints where needed,
  `roster_transitions`, current-entry partial uniqueness, and seeded
  `roster-syncer` service actor grants.
- Add the roster lifecycle API:
  `POST /api/v1/roster-entries`,
  `GET /api/v1/roster-entries/{id}`,
  `POST /api/v1/roster-entries/{id}/transitions`, and
  `POST /api/v1/roster-entries/{id}/sync-failure`.
- Add two-tier roster authority:
  - operator-facing create, read, and transition endpoints require
    chapter-scoped `roster.read`, `roster.write`, or `roster.remove` as
    appropriate, and are user-actor-only;
  - service-only sync-failure reporting requires global-scoped
    `roster.write` and a service actor.
- Add `RosterEntryTransitionRequest` and `RosterSyncFailureRequest`, and extend
  `RosterEntryRead` with `version`.
- Add Discord-side `RosterSyncEvent`, `RosterSyncResult`, and
  `sync_roster(event)` that uses Discord member role add/remove APIs
  idempotently.
- On Discord sync failure, call the API as service actor `roster-syncer` and
  let the API enqueue the consequential deferred effect inside the roster
  aggregate mutation.

Out of scope:

- No advanced roster analytics.
- No bulk CSV or file import.
- No leadership succession workflow; SLICE-024 owns it.
- No roster archival workflow.
- No cross-chapter transfer.
- No automatic synchronization of per-role permission grants into
  `authority_grants`.
- No SLICE-007 member table dependency or FK from `roster_entries.member_id` to
  members.
- No deferred-effect worker for executing roster sync retries. This slice
  enqueues the effect only.
- No Discord-visible mutation is run by this proposal. Implementation tests use
  mocks/fakes; any live Discord role change remains Tier 3 and requires
  explicit per-action approval under `AGENTS.md`.

D12 anti-scope is binding exactly as stated in synthesis: SLICE-018 must not
implement advanced roster analytics, bulk CSV import, leadership succession,
roster archival, cross-chapter transfer, or automatic synchronization of
per-role permission grants into `authority_grants`.

## 3. Work Units

### WU-033 Roster Lifecycle API

**Migration: `migrations/versions/wu-033_roster.py`**

- Set `down_revision` to the current migration head that includes
  `wu_019_chapter_lifecycle`.
- Extend `roster_entries` without adding a version column:
  - Keep `id`, `chapter_id`, `member_id`, `role_id`, `status`, `created_at`.
  - Add `updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`.
  - Add `removal_metadata JSONB NOT NULL DEFAULT '{}'::jsonb`.
  - Add FK `chapter_id -> chapters(id)` and update roster tests to seed a
    chapter before creating chapter roles or roster entries.
  - Add `UNIQUE (chapter_id, id)` on `chapter_roles` as
    `uq_chapter_roles__chapter_id_id` to support the composite FK.
  - Add composite FK `(chapter_id, role_id) -> chapter_roles(chapter_id, id)`
    so a roster entry cannot point at a role from another chapter.
  - Add partial unique index
    `uq_roster__chapter_member_active` on `(chapter_id, member_id) WHERE status
    != 'removed'` per D6.
- Create `roster_transitions`:
  - `id UUID PRIMARY KEY`
  - `roster_entry_id UUID NOT NULL REFERENCES roster_entries(id) ON DELETE RESTRICT`
  - `chapter_id TEXT NOT NULL`
  - `aggregate_seq BIGINT NOT NULL`
  - `from_status TEXT NOT NULL`
  - `to_status TEXT NOT NULL`
  - `from_role_id UUID NULL REFERENCES chapter_roles(id) ON DELETE RESTRICT`
  - `to_role_id UUID NULL REFERENCES chapter_roles(id) ON DELETE RESTRICT`
  - `actor_kind TEXT NOT NULL`
  - `actor_id TEXT NOT NULL`
  - `originating_actor_kind TEXT NULL`
  - `originating_actor_id TEXT NULL`
  - `reason TEXT NOT NULL`
  - `removal_metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
  - `recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`
  - FK `chapter_id -> chapters(id) ON DELETE RESTRICT`
  - checks for valid roster statuses
  - `UNIQUE (roster_entry_id, aggregate_seq)` per D3
  - index on `(chapter_id, recorded_at)`
- Seed a global, active `authority_grants` row for `grantee_id='roster-syncer'`
  with permissions `["roster.read", "roster.write"]`, `scope_kind='global'`,
  and `scope_id IS NULL` per D10. Do not introduce per-chapter service grants.

**Contracts: `services/api/app/contracts/roster.py`**

- Keep `RosterStatus = Literal["active", "on_leave", "under_review",
  "removed"]`.
- Extend `RosterEntryRead` with:
  - `updated_at: datetime`
  - `removal_metadata: dict[str, Any] = Field(default_factory=dict)`
  - `version: int = Field(ge=1)`
- Update `RosterEntryCreate` to only accept `chapter_id`, `member_id`, and
  `role_id`. Creation always writes `status="active"` server-side. Delete the
  public create-status input and update foundation tests rather than preserving
  a compatibility path.
- Add `RosterEntryTransitionRequest`:
  - `to_status: RosterStatus`
  - `to_role_id: UUID | None = None`
  - `reason: str = Field(min_length=1)`
  - `removal_metadata: dict[str, Any] = Field(default_factory=dict)`
  - `originating_actor_kind: Literal["user", "service"] = "user"`
  - `originating_actor_id: str = Field(min_length=1)`
- Add `RosterSyncFailureRequest`:
  - `transition_id: UUID`
  - `reason: str = Field(min_length=1)`
  - `member_discord_user_id: str | None = None`
  - `operation: Literal["add_roles", "remove_roles", "resolve_member", "resolve_role"]`
  - `failed_at_step: str = Field(min_length=1)`
  - `desired_discord_role_ids: list[str] = Field(default_factory=list)`
  - `error_type: str | None = None`
  - `originating_actor_kind: Literal["user", "service"] = "service"`
  - `originating_actor_id: str = Field(min_length=1)`
- Add typed errors:
  - `RosterEntryNotFoundError`
  - `RosterRoleNotFoundError` remains
  - `InvalidRosterStatusTransitionError` remains
  - `RosterRoleChapterMismatchError`
  - `RosterDuplicateCurrentEntryError`

**Repository: `services/api/app/repositories/roster.py`**

Use underscore-prefixed helpers as the module's internal persistence API:

- `_ROSTER_ENTRY_SELECT` joins `roster_entries` to `aggregate_heads` with
  `aggregate_type='roster_entry'` and `aggregate_id = roster_entries.id::text`
  to return `version`.
- `_fetch_roster_entry(connection, entry_id)` returns the read row with version.
- `_fetch_roster_entry_for_update(connection, entry_id)` locks the roster row
  for transition and sync-failure recording.
- `_insert_roster_entry(connection, row)` inserts the active entry.
- `_insert_roster_transition(connection, row)` inserts the projection row.
- `_update_roster_entry(connection, entry_id, status, role_id,
  removal_metadata)` updates status/role/removal metadata and `updated_at`.
- `_fetch_chapter_role_for_update_or_validate(connection, chapter_id, role_id)`
  verifies the role belongs to the same chapter before insert or transition.

This replaces the current public-only foundation helpers
`insert_roster_entry`, `fetch_roster_entry`, and `update_roster_status` without
leaving compatibility aliases.

**Service: `services/api/app/services/roster.py`**

- `create_roster_entry(db, request, actor) -> tuple[RosterEntryRead,
  MutationResult]`
  - Validates `request.role_id` belongs to `request.chapter_id`.
  - Inserts an `active` row through `_insert_roster_entry`.
  - Uses `mutate_entity(aggregate_type="roster_entry", expected_version=0)`.
  - Returns `RosterEntryRead` with version `1` and ETag `"1"`.
  - Translates partial unique index violation to
    `RosterDuplicateCurrentEntryError`.
- `get_roster_entry(db, entry_id) -> tuple[RosterEntryRead, str]`
  - Fetches by `_fetch_roster_entry`.
  - Returns body plus ETag from `version`.
- `transition_roster_entry(db, entry_id, request, actor, expected_version) ->
  tuple[RosterEntryRead, MutationResult]`
  - Fetches current row `FOR UPDATE` inside `mutate_entity`.
  - Applies D2 state matrix exactly:
    `active -> on_leave | under_review | removed`,
    `on_leave -> active | removed`,
    `under_review -> active | removed`,
    no transition out of `removed`.
  - If `request.to_role_id` is present, validates it belongs to the same
    chapter and writes the role change in the same mutation.
  - Computes `aggregate_seq = expected_version + 1`.
  - Inserts one `roster_transitions` row with actor, originating actor, reason,
    from/to status, from/to role, removal metadata, and aggregate sequence.
  - Updates `roster_entries` in the same transaction.
  - Emits action/state-change payloads that include `originating_actor_kind` and
    `originating_actor_id` per D11.
- `record_roster_sync_failure(db, roster_entry_id, request, actor,
  expected_version) -> tuple[RosterEntryRead, MutationResult]`
  - Enforces actor `service/roster-syncer` at the endpoint layer and still uses
    the passed actor for audit.
  - Runs `mutate_entity` for aggregate type `roster_entry` with the supplied
    `expected_version`; stale versions become 412 and enqueue nothing.
  - Does not change `roster_entries.status` or `role_id`.
  - Enqueues `DeferredEffectCreate` in the same transaction via
    `enqueue_effect`, with:
    `subsystem="roster_role_sync"`,
    `effect_type="roster_sync_retry"`,
    `idempotency_key=f"roster_sync_retry:{roster_entry_id}:{request.transition_id}"`,
    `consequence_level="consequential"`, and repository default
    `precondition_state="unchecked"`.
  - Payload includes roster entry id, chapter id, member id,
    member Discord user id, transition id, desired Discord role ids,
    operation, failed step, failure reason, and originating actor.

Remove or rename `read_roster_entry` and `transition_roster_status`; the
implementation must update all call sites and tests to the new lifecycle
service names with no compatibility shim.

**Endpoints: `services/api/app/api/v1/endpoints/roster.py`**

- Mount the router from `services/api/app/api/v1/router.py`.
- Add a local service-actor dependency for sync-failure reporting:
  `_service_actor_only(actor: ActorIdentity = Depends(get_current_actor))`.
  It rejects any actor whose `actor_kind != "service"` with
  `403 {"code": "service_actor_required"}` before mutation. The endpoint also
  rejects service actors other than `actor_id="roster-syncer"` with 403, using
  the same actor-id guard already required by the service contract.
- Reuse the chapter endpoint ETag parse/set pattern:
  - missing `If-Match` -> `428 Precondition Required`
  - malformed `If-Match` -> `400 Bad Request`
  - stale aggregate -> `412 Precondition Failed`
- `POST /api/v1/roster-entries -> RosterEntryRead`
  - Requires actor headers.
  - Requires `actor_kind="user"`; service actors must not use operator
    endpoints.
  - Uses body-aware chapter-scoped authority:
    `roster.write` on `scope_kind="chapter"`, `scope_id=body.chapter_id`.
  - Returns `201 Created`, body status `active`, and ETag `"1"`.
- `GET /api/v1/roster-entries/{id} -> RosterEntryRead`
  - Requires `actor_kind="user"`; service actors must not use operator
    endpoints.
  - Fetches the entry first, derives `chapter_id`, then evaluates
    `roster.read` for that chapter. Do not rely on path-only
    `RequireAuthority`, because chapter id is not in the path.
  - Returns ETag from read `version`.
- `POST /api/v1/roster-entries/{id}/transitions -> RosterEntryRead`
  - Requires `actor_kind="user"`; service actors must not use operator
    endpoints.
  - Requires `If-Match`.
  - Fetches the entry first, derives chapter scope, then requires
    `roster.remove` when `to_status == "removed"` and otherwise
    `roster.write`.
  - Calls `transition_roster_entry`.
- `POST /api/v1/roster-entries/{id}/sync-failure -> RosterEntryRead`
  - Requires `If-Match`.
  - Requires current actor to be `actor_kind="service"` and
    `actor_id="roster-syncer"`.
  - Requires `roster.write` at `scope_kind="global"` with no chapter
    `scope_id`. Do not derive authority from the roster entry chapter for this
    service-only endpoint, because `services/api/app/services/authority.py`
    rejects grants whose `scope_kind` differs from the requirement and D10
    seeds `roster-syncer` with global grants only.
  - Calls `record_roster_sync_failure`.

**WU-033 tests**

- API endpoint tests live in `services/api/tests/test_roster.py`.
- Migration/invariant tests may remain in or extend
  `services/api/tests/test_roster_foundation.py` where that keeps foundation
  coverage readable.
- Required sync-failure authority tests:
  - `test_sync_failure_rejects_non_service_actors_with_403`: a user actor with
    a valid chapter-scoped roster grant is rejected before mutation.
  - `test_sync_failure_accepts_roster_syncer_service_actor_with_global_grant`:
    the Discord handler uses `roster-syncer` service headers, the seeded global
    `roster.write` grant authorizes the API call, and a deferred effect row is
    enqueued.
- Required tests are listed in the AC trace below.

### WU-034 Discord Roster Role Sync

**Contracts: `services/discord/app/contracts/roster.py`**

- `RosterSyncEvent`
  - `roster_entry_id: str`
  - `roster_entry_version: int`
  - `transition_id: str`
  - `chapter_id: str`
  - `member_id: str`
  - `member_discord_user_id: str`
  - `chapter_role_name: str`
  - `chapter_discord_role_id: str | None = None`
  - `chapter_discord_resources: dict[str, Any]`
  - `status: Literal["active", "on_leave", "under_review", "removed"]`
  - `originating_actor_kind: Literal["user", "service"] = "user"`
  - `originating_actor_id: str`
  - `reason: str`
  - `correlation_id: str | None = None`
- `RosterSyncResult`
  - `roster_entry_id: str`
  - `transition_id: str`
  - `applied_role_ids: list[str]`
  - `skipped_role_ids: list[str]`
  - `failure_recorded: bool = False`
  - `deferred_effect_id: str | None = None`

**Handler: `services/discord/app/handlers/roster.py`**

- Add `SERVICE_ACTOR_HEADERS = {"X-Actor-Kind": "service",
  "X-Actor-Id": "roster-syncer"}` locally rather than reusing the
  `discord-provisioner` headers from chapter provisioning.
- `async def sync_roster(event: RosterSyncEvent, *, api_client: Any | None =
  None, guild: Any | None = None) -> RosterSyncResult`.
- Resolve the guild member by `event.member_discord_user_id`. Use a local
  helper that first checks cached guild members when available and then uses a
  fetch method if the fake/discord object exposes it.
- Resolve the Discord role ID:
  - Prefer `event.chapter_discord_role_id` when present.
  - Otherwise read `event.chapter_discord_resources["role_ids"][event.chapter_role_name]`.
  - Then resolve the role object from `guild.roles`.
  - If the stored ID is stale, rediscover by deterministic role name using the
    same chapter resource naming substrate as SLICE-013 where available. This
    satisfies `test_discord_handler_rediscovers_role_id_by_name_for_chapter`
    without adding a new persistence path for the rediscovered ID in this slice.
- For `active`, `on_leave`, and `under_review`, call
  `Member.add_roles(role, reason=...)` only when the member does not already
  have the role.
- For `removed`, call `Member.remove_roles(role, reason=...)` only when the
  member currently has the role.
- Reason strings include roster entry id, transition id, and originating actor.
- Catch Discord `Forbidden`, `NotFound`, and `HTTPException`, plus stale role
  or departed member resolution failures, and call:
  `POST /api/v1/roster-entries/{roster_entry_id}/sync-failure`
  with `If-Match: "{roster_entry_version}"`, `SERVICE_ACTOR_HEADERS`, and a
  `RosterSyncFailureRequest` body.
- If the sync-failure API returns 412, return a result with
  `failure_recorded=False`; the API has correctly rejected an obsolete retry.
- Do not write to the database directly from Discord.
- Do not create, rename, or persist Discord roles in WU-034. Role creation and
  resource persistence remain the chapter provisioning substrate's job.

**WU-034 tests**

- Tests live in `services/discord/tests/test_roster_sync.py`.
- Use fake guild, member, role, and API client objects following
  `services/discord/tests/test_chapter_provisioning.py`.
- Required scenarios: idempotency, `Forbidden`, `NotFound`, stale role id,
  departed member, and sync-failure API call shape.

## 4. Tradeoffs

- **Substrate parity with SLICE-013.** The roster API deliberately copies the
  chapter lifecycle patterns instead of creating a separate mutation style:
  `mutate_entity` for OCC, transition projection rows in the same transaction,
  ETags from aggregate version, service actor headers, originating actor in the
  request body, and API-owned deferred-effect enqueue. This keeps WU-033 close
  to `services/api/app/services/chapters.py` and WU-034 close to
  `services/discord/app/handlers/chapters.py`.
- **Global service grant for `roster-syncer`.** Per-chapter service grants
  would be tighter, but D10 explicitly defers them. The sync-failure endpoint
  therefore requires global-scoped `roster.write`, enforces the service actor
  and `roster-syncer` actor id, and audits as `roster-syncer`.
- **Deferred effect dedup by idempotency key.** The API uses
  `roster_sync_retry:{roster_entry_id}:{transition_id}`. This deduplicates
  repeat failure reports for the same desired transition while allowing a later
  transition on the same roster entry to enqueue its own retry.
- **No duplicated Discord role IDs in `chapter_roles`.** D4 keeps stable roster
  identity in `chapter_roles.id` and resolves Discord IDs through chapter
  resources. This means a stale role ID recovery can be attempted by name in
  the Discord handler, but persisting the corrected role ID is deferred to a
  later resource-reconciliation slice.
- **No member table dependency.** Keeping `member_id TEXT` avoids blocking on
  SLICE-007. The cost is that Discord sync events must carry
  `member_discord_user_id` explicitly.

## 5. Preserved

- Preserve the WU-007C `roster_entries` foundation as the durable roster
  aggregate table. It is extended with lifecycle columns and constraints, not
  replaced.
- Preserve `aggregate_type="roster_entry"` already used by
  `services/api/app/services/roster.py`.
- Preserve the existing WU-007B `chapter_roles` table and contracts. It remains
  the stable roster role identity anchor.
- Preserve the current roster state names and transition validator semantics
  already present in `_validate_roster_transition`; SLICE-018 exposes them
  through API contracts, transition rows, and OCC.
- Preserve the activity/audit substrate from `mutate_entity`; accepted,
  rejected, and failed roster operations continue to produce activity actions
  and aggregate state changes.
- Preserve the SLICE-013 chapter Discord resource storage model:
  Discord role IDs stay in `chapters.discord_resources.role_ids`, keyed by
  logical chapter role name.

## 6. Resolved Decisions

| Decision | Resolution and code references |
|---|---|
| D1 | `roster_entries` remains the `RosterEntry` aggregate table using `aggregate_type="roster_entry"` in `services/api/app/services/roster.py`. No version column is added. `RosterEntryRead.version` is read by joining `aggregate_heads`, matching `services/api/app/repositories/chapters.py` and OCC in `services/api/app/services/mutations.py`. |
| D2 | The state machine is the existing roster matrix in `_validate_roster_transition` in `services/api/app/services/roster.py`, now enforced by `transition_roster_entry` and API tests. `removed` remains terminal; re-admission uses a new row and is protected by the D6 partial unique index. |
| D3 | `roster_transitions` mirrors `chapter_transitions` from `migrations/versions/wu-019_chapter_lifecycle.py` and `services/api/app/repositories/chapter_transitions.py`. `transition_roster_entry` inserts the transition projection and updates `roster_entries` inside the same `mutate_entity` transaction, with `aggregate_seq = expected_version + 1`. |
| D4 | `roster_entries.role_id`, `roster_transitions.from_role_id`, and `roster_transitions.to_role_id` store `chapter_roles.id`. Discord IDs are resolved from `chapters.discord_resources.role_ids[chapter_role.name]`, following `services/api/app/contracts/chapters.py` and `services/discord/app/handlers/chapters.py`. |
| D5 | `roster_entries.member_id` stays `TEXT`, as defined by `migrations/versions/wu-007c_roster_foundation.py`. No member FK is introduced. `RosterSyncEvent.member_discord_user_id` carries the Discord user ID explicitly. |
| D6 | `migrations/versions/wu-033_roster.py` adds `uq_roster__chapter_member_active` on `(chapter_id, member_id) WHERE status != 'removed'`. Removed historical rows remain allowed. |
| D7 | Operator-facing roster endpoints evaluate `roster.read`, `roster.write`, and `roster.remove` against `scope_kind="chapter"` and require user actors. Create derives scope from `body.chapter_id`; read and transition routes fetch the row first and derive scope from `roster_entries.chapter_id`, because existing `RequireAuthority` only reads path params in `services/api/app/core/dependencies.py`. The service-only sync-failure endpoint follows D10 instead of chapter scope. |
| D8 | `services/discord/app/handlers/roster.py::sync_roster` is idempotent: skip already-present adds and already-absent removes, call `Member.add_roles(..., reason=...)` and `Member.remove_roles(..., reason=...)`, and report `Forbidden`, `NotFound`, `HTTPException`, stale role, or departed member failures to the API. |
| D9 | `record_roster_sync_failure` runs through `mutate_entity` for the roster entry aggregate and enqueues a `DeferredEffectCreate` via `services/api/app/repositories/deferred_effects.py::enqueue_effect` in the same transaction. Stale `If-Match` returns 412 and enqueues nothing. |
| D10 | `migrations/versions/wu-033_roster.py` seeds global `authority_grants` for `grantee_id='roster-syncer'` with `roster.read` and `roster.write`, parallel to the `discord-provisioner` seed in `migrations/versions/wu-019_chapter_lifecycle.py`. `POST /api/v1/roster-entries/{id}/sync-failure` requires `actor_kind="service"`, `actor_id="roster-syncer"`, and `roster.write` at `scope_kind="global"` so the endpoint matches the seeded service grant. |
| D11 | `RosterEntryTransitionRequest` and `RosterSyncFailureRequest` carry `originating_actor_kind` and `originating_actor_id`. Services record them in action payloads and `roster_transitions`, following the originating actor fields in `services/api/app/contracts/chapters.py` and `services/api/app/services/chapters.py`. |
| D12 | Anti-scope is enforced by omission: no analytics modules, import endpoints, succession code, archival state, transfer endpoint, or authority auto-sync job are added. The only authority write is the `roster-syncer` seed required by D10. |

## 7. AC Trace

AC1: direct roster add creates active entry tied to a chapter role.

- `test_create_roster_entry_in_active_state`
- `test_create_roster_entry_requires_roster_write_permission_chapter_scope`

AC2: status and role transitions create a `RosterTransition` row with
attribution and reason.

- `test_transition_creates_roster_transition_row_with_actor`
- `test_transition_records_reason`
- `test_transition_state_machine_allowed_and_rejected_transitions`
- `test_removed_is_terminal_no_further_transitions`

AC3: OCC with `If-Match`; current version succeeds, stale version returns 412.

- `test_transition_with_current_version_succeeds`
- `test_transition_with_stale_version_returns_412`
- `test_get_roster_entry_returns_version_and_etag`

AC4: failed Discord sync queues a consequential deferred effect instead of
silently drifting.

- `test_sync_failure_enqueues_deferred_effect_atomically`
- `test_sync_failure_idempotency_key_per_transition`
- `test_sync_failure_preserves_roster_entry_state`
- `test_sync_failure_rejects_non_service_actors_with_403`
- `test_sync_failure_accepts_roster_syncer_service_actor_with_global_grant`
- `test_discord_handler_calls_sync_failure_on_forbidden`
- `test_discord_handler_rediscovers_role_id_by_name_for_chapter`

Invariants:

- `test_partial_unique_index_allows_one_active_per_chapter_member`
- `test_roster_syncer_service_actor_grants_seeded`
- `test_no_legacy_roster_in_memory_remains`
- `test_discord_handler_idempotently_skips_existing_role`
- `test_discord_handler_idempotently_skips_absent_removed_role`
- `test_discord_handler_calls_sync_failure_on_not_found`
- `test_discord_handler_calls_sync_failure_on_stale_role_id`
- `test_discord_handler_calls_sync_failure_on_departed_member`

## Revision history

- Revision 1: Split roster authority into chapter-scoped user-actor operator
  endpoints and a global-scoped service-only `/sync-failure` endpoint. This
  resolves Audit F1 by matching the endpoint's required scope to the seeded
  `roster-syncer` global grant and adding explicit tests for non-service
  rejection and successful global service authorization.
