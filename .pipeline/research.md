# SLICE-018 Phase 1 Research: Roster Management With Role Lifecycle

## 1. Prototyping Assessment

**YES - focused Phase 0 prototyping is recommended before production implementation.**

Triggers:

- **New Discord integration surface applies.** `/provision` creates categories, roles, channels, and patches resource IDs, but it does not add or remove roles on existing members. The current handler checks `manage_roles` only as part of provisioning permissions and uses `guild.create_role`, not `Member.add_roles` / `Member.remove_roles` (`services/discord/app/handlers/chapters.py:57`, `services/discord/app/handlers/chapters.py:212`). Bot intents include `members=True`, so member lookup is possible, but no roster sync path exists (`services/discord/app/core/bot.py:19`).
- **Concurrent edit semantics need validation.** `mutate_entity()` serializes a single aggregate with `aggregate_heads` and rejects stale expected versions (`services/api/app/services/mutations.py:94`, `services/api/app/services/mutations.py:123`). Roster sync adds an external Discord side effect after the roster aggregate changes, so the stale event / changed desired role-set case needs a small empirical test.

No prototype is needed for the core data primitive: `RosterEntry` and `ChapterRole` already exist as foundation tables/services, and `RosterTransition` can mirror the proven `chapter_transitions` projection pattern (`migrations/versions/wu-007c_roster_foundation.py:17`, `migrations/versions/wu-007b_chapter_roles_foundation.py:17`, `migrations/versions/wu-019_chapter_lifecycle.py:63`).

Prototype scope:

1. Disposable Discord handler spike for `sync_roster(event)` that:
   - Resolves a guild member by Discord user ID.
   - Adds missing target roles for active roster state.
   - Removes present target roles for removed roster state.
   - Captures `Forbidden`, `NotFound`, stale role ID, and departed-member cases.
2. API concurrency spike:
   - Read roster entry version N.
   - Transition entry to version N+1.
   - Try to record a Discord sync failure against stale N and confirm it does not enqueue a retry for outdated desired state.
3. Role resolution spike:
   - Resolve `ChapterRole.name` to `chapters.discord_resources.role_ids[name]`.
   - Confirm behavior when the role name is missing from the provisioned chapter resources.

Keep the prototype disposable under `prototyping/slice-018-roster-sync/prototype/`; do not ship prototype code.

## 2. Per-Question Answers

### 1. RosterEntry aggregate shape

Current foundation shape is `id`, `chapter_id`, `member_id`, `role_id`, `status`, `created_at`; status is constrained to `active | on_leave | under_review | removed` (`services/api/app/contracts/roster.py:10`, `services/api/app/contracts/roster.py:17`; `migrations/versions/wu-007c_roster_foundation.py:17`). The service already uses `aggregate_type="roster_entry"` for create and transition (`services/api/app/services/roster.py:93`, `services/api/app/services/roster.py:162`).

Production shape should remain aggregate type `roster_entry`. Version should be read from `aggregate_heads`, not stored as an independent mutable column, matching chapters: `fetch_chapter` joins `aggregate_heads` as `version` (`services/api/app/repositories/chapters.py:10`). `RosterEntryRead` currently lacks `version`, so WU-033 must extend the repository query and contract.

OCC behavior:

- Create uses expected version `0` and produces version `1` via `mutate_entity()` (`services/api/app/services/roster.py:93`).
- Transition must require an explicit expected version at the API boundary via `If-Match`, like chapter transitions (`services/api/app/api/v1/endpoints/chapters.py:39`, `services/api/app/api/v1/endpoints/chapters.py:126`).
- Simultaneous transitions serialize on the `aggregate_heads` row; one transition advances the head and the other receives `StaleMutationError`, translated to HTTP 412 (`services/api/app/services/mutations.py:112`, `services/api/app/services/mutations.py:123`; `services/api/app/api/v1/endpoints/chapters.py:61`).

### 2. RosterTransition projection pattern

Use the `chapter_transitions` pattern. Chapter transition rows are inserted inside the same `mutate_projection` callback that updates chapter state (`services/api/app/services/chapters.py:317`, `services/api/app/services/chapters.py:330`, `services/api/app/services/chapters.py:346`). The table has `aggregate_seq`, actor attribution, originating actor, reason, and unique `(chapter_id, aggregate_seq)` (`migrations/versions/wu-019_chapter_lifecycle.py:63`).

For roster, add `roster_transitions` and insert it in the same transaction as the `roster_entries` update. Use `aggregate_seq = expected_version + 1`, exactly as chapters do (`services/api/app/services/chapters.py:330`).

### 3. ChapterRole table

`ChapterRole` already exists as a table and contract, so this is not a new entity for SLICE-018. The current shape is stable DB identity plus `chapter_id`, optional `template_id`, `name`, `ordinal`, and `triggers_succession` (`services/api/app/contracts/chapter_roles.py:13`; `migrations/versions/wu-007b_chapter_roles_foundation.py:17`). It is distinct from `chapter_templates.role_structure`, which is copied into `chapters.template_snapshot` during chapter creation (`services/api/app/services/chapters.py:91`, `services/api/app/services/chapters.py:117`).

There is currently no `discord_role_id` on `chapter_roles`. Provisioned Discord role IDs live in `chapters.discord_resources.role_ids`, keyed by logical role name (`services/api/app/contracts/chapters.py:19`; `services/api/app/services/chapters.py:213`). `/provision` derives role names from the chapter template snapshot and patches `role_ids[logical_name] = discord_role_id` (`services/discord/app/handlers/chapters.py:24`, `services/discord/app/handlers/chapters.py:212`).

Recommended relationship: keep `ChapterRole` as stable roster identity and resolve Discord role IDs by `(chapter_id, chapter_role.name)` against `chapters.discord_resources.role_ids`. Do not duplicate Discord role IDs into `chapter_roles` in SLICE-018 unless the prototype proves name-key resolution is too fragile.

### 4. State machine

Current service matrix is:

- `active -> on_leave | under_review | removed`
- `on_leave -> active | removed`
- `under_review -> active | removed`
- `removed -> terminal`

This is already encoded in `_validate_roster_transition` (`services/api/app/services/roster.py:41`). The current tests explicitly pin `removed` as terminal (`services/api/tests/test_roster_foundation.py:206`).

Re-admission should create a new `RosterEntry`, not resurrect a removed one. This preserves removal history and avoids rewriting terminal audit facts. Enforce one current non-removed roster entry per `(chapter_id, member_id)` with a partial unique index, while allowing historical removed rows.

### 5. Discord role sync

No existing handler adds/removes roles on members. The only Discord role path creates roles during chapter provisioning (`services/discord/app/handlers/chapters.py:212`). The sync handler should be idempotent:

- For active/on-leave/under-review target state, add missing target role IDs and skip roles already present.
- For removed state, remove target role IDs that are present and skip absent roles.
- If the member has left the guild, classify as sync failure and record a consequential deferred effect. The retry/precondition validator can later mark it invalid if the member is still absent.
- If a Discord role ID is stale or the bot lacks hierarchy/permission, classify as sync failure and enqueue retry through the API.

`check_required_bot_permissions()` should be reused or generalized to include the member role sync path; it already checks `manage_roles` (`services/discord/app/handlers/chapters.py:57`).

### 6. Deferred effect on Discord sync failure

Follow the SLICE-013 API-owned enqueue pattern: failed chapter provisioning enqueues a `DeferredEffectCreate` with `consequence_level="consequential"` and inserts it through the repository with the active transaction connection (`services/api/app/services/chapters.py:273`, `services/api/app/services/chapters.py:284`, `services/api/app/services/chapters.py:300`). The deferred effect table defaults new rows to `precondition_state='unchecked'` and `status='queued'` (`services/api/app/repositories/deferred_effects.py:31`, `migrations/versions/wu-008b_deferred_effect_foundation.py:17`).

AC4 should be implemented as an API method that records roster sync failure and enqueues a consequential deferred effect inside `mutate_entity()` for the same `roster_entry` aggregate. The Discord handler should call that API method after a failed Discord mutation rather than writing to the DB directly.

### 7. Member entity

There is no merged `members` table, contract, repository, service, or endpoint in the current code. `SLICE-007` defines the future member aggregate and API (`product-strategy/tickets/SLICE-007.md:21`, `product-strategy/tickets/SLICE-007.md:26`), but it is not included in the current API router (`services/api/app/api/v1/router.py:11`) and no `members.py` files exist under the API service.

Therefore SLICE-018 must not FK `roster_entries.member_id` to `members` unless SLICE-007 is made an upstream dependency. The current foundation already uses `member_id TEXT` without an FK (`migrations/versions/wu-007c_roster_foundation.py:20`). The lowest-risk path is to treat `member_id` as an external durable identifier for now, and require `member_discord_user_id` in the roster sync event.

### 8. Authority scopes

`ScopeKind` already supports `"chapter"` (`services/api/app/contracts/scope.py:4`), and `RequireAuthority` can bind a path param as `scope_id` (`services/api/app/core/dependencies.py:56`). Chapter endpoints currently use global chapter authority (`services/api/app/api/v1/endpoints/chapters.py:88`), but roster endpoints should be chapter-scoped:

- `GET /api/v1/roster-entries/{id}`: require `roster.read` scoped to the entry's chapter. Because the chapter ID is not in the path, either use a two-step dependency that loads the entry before authorization or expose chapter-scoped list/read routes.
- `POST /api/v1/roster-entries`: require `roster.write` with `scope_kind="chapter"`, `scope_id=body.chapter_id`.
- `POST /api/v1/roster-entries/{id}/transitions`: require `roster.write` for role/status changes and `roster.remove` when `to_status="removed"`.
- Discord service actor should receive chapter-scoped grants only for chapters it may sync, or a narrowly-scoped global service grant if per-chapter service grants are not yet practical.

### 9. Existing roster code

Existing roster code is foundation-only:

- Contracts: `RosterEntryRead` and `RosterEntryCreate`, no transition request/read and no version field (`services/api/app/contracts/roster.py:17`).
- Repository: insert, fetch, and status update only (`services/api/app/repositories/roster.py:10`, `services/api/app/repositories/roster.py:36`, `services/api/app/repositories/roster.py:51`).
- Service: create, read, status transition only; system actor is hard-coded (`services/api/app/services/roster.py:31`, `services/api/app/services/roster.py:71`, `services/api/app/services/roster.py:126`).
- No API endpoint is registered for roster (`services/api/app/api/v1/router.py:11`).
- No Discord roster contract or handler exists.

## 3. Proposed Data Model

### Existing tables to extend

`chapter_roles`

- Keep existing columns: `id`, `chapter_id`, `template_id`, `name`, `ordinal`, `triggers_succession`, `created_at`.
- Add FK `chapter_id -> chapters(id)` if current migration state permits it.
- Add unique `(chapter_id, id)` to support composite FK consistency from roster entries.
- Do not add `discord_role_id` in this slice; resolve through `chapters.discord_resources.role_ids[name]`.

`roster_entries`

- Keep existing columns: `id`, `chapter_id`, `member_id`, `role_id`, `status`, `created_at`.
- Add `removal_metadata JSONB NOT NULL DEFAULT '{}'::jsonb`.
- Add `updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`.
- Add FK `chapter_id -> chapters(id)`.
- Add composite FK `(chapter_id, role_id) -> chapter_roles(chapter_id, id)` so a roster entry cannot point at a role from another chapter.
- Add partial unique index on `(chapter_id, member_id)` where `status <> 'removed'`.
- Read `version` by joining `aggregate_heads` on `aggregate_type='roster_entry'`.

New table: `roster_transitions`

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
- `UNIQUE(roster_entry_id, aggregate_seq)`
- Check constraints for valid statuses.

Deferred effect type for failed sync:

- `subsystem = "roster_role_sync"`
- `effect_type = "roster_role_sync_retry"`
- `idempotency_key = "roster_role_sync_retry:{roster_entry_id}:{aggregate_seq}"`
- `payload_json` includes roster entry ID, chapter ID, member ID, member Discord user ID if known, desired Discord role IDs, status, failure reason, and failed operation.
- `consequence_level = "consequential"`
- initial `precondition_state = "unchecked"` via existing deferred effect repository default.

## 4. Proposed API Surface

Contracts in `services/api/app/contracts/roster.py`:

- `RosterEntryCreate(chapter_id, member_id, role_id)`
- `RosterEntryRead(id, chapter_id, member_id, role_id, status, removal_metadata, created_at, updated_at, version)`
- `RosterTransitionRequest(to_status, to_role_id?, reason, originating_actor_kind="user", originating_actor_id)`
- `RosterTransitionRead(id, roster_entry_id, chapter_id, aggregate_seq, from_status, to_status, from_role_id?, to_role_id?, actor_kind, actor_id, originating_actor_kind?, originating_actor_id?, reason, removal_metadata, recorded_at)`
- `RosterSyncFailureCreate(member_discord_user_id?, desired_discord_role_ids, operation, failure_reason, failed_at_step)`
- `RosterSyncFailureRead(roster_entry_id, deferred_effect_id, deferred_effect_idempotency_key, version)`

Endpoints:

- `POST /api/v1/roster-entries -> RosterEntryRead`
  - Requires `roster.write` on body `chapter_id`.
  - Creates active entry; ignores any client-provided status.
  - Returns `201` and `ETag: "1"`.
- `GET /api/v1/roster-entries/{roster_entry_id} -> RosterEntryRead`
  - Returns current entry with `ETag` from `aggregate_heads`.
  - Requires `roster.read` for the entry chapter.
- `POST /api/v1/roster-entries/{roster_entry_id}/transitions -> RosterEntryRead`
  - Requires `If-Match`.
  - Requires `roster.write`; require `roster.remove` when `to_status="removed"`.
  - Updates status and/or role, inserts `roster_transitions`, returns new `ETag`.
  - Translates stale aggregate to `412 Precondition Failed`.
- `POST /api/v1/roster-entries/{roster_entry_id}/sync-failures -> RosterSyncFailureRead`
  - Requires `If-Match`.
  - Service-only endpoint used by Discord handler.
  - Enqueues consequential deferred effect inside the same `mutate_entity()` transaction.
  - If the roster entry version has advanced since the sync event, returns `412` and does not enqueue an obsolete retry.

## 5. Proposed Discord Handler Surface

Contracts in `services/discord/app/contracts/roster.py`:

- `RosterSyncEvent(roster_entry_id, roster_entry_version, guild_id, member_discord_user_id, chapter_role_ids, status, correlation_id?)`
- `RosterSyncResult(roster_entry_id, applied_role_ids, skipped_role_ids, deferred_effect_id?)`
- `RosterSyncError(step, reason)`

Handler:

```text
async def sync_roster(
    event: RosterSyncEvent,
    *,
    api_client: ApiClient | None = None,
    guild: discord.Guild | None = None,
) -> RosterSyncResult
```

Responsibilities:

- Check `manage_roles`.
- Resolve member by `member_discord_user_id`.
- Resolve role objects from `chapter_role_ids` / Discord role IDs passed in the event.
- For `active`, `on_leave`, and `under_review`: add missing roles.
- For `removed`: remove present roles.
- Do not mutate if target state already matches current member role set.
- On Discord failure, call `/api/v1/roster-entries/{id}/sync-failures` with `If-Match: "<roster_entry_version>"`.
- Return the deferred effect ID if failure recording succeeds.

## 6. State Machine With Invariants

Allowed transitions:

- `active -> on_leave`
- `active -> under_review`
- `active -> removed`
- `on_leave -> active`
- `on_leave -> removed`
- `under_review -> active`
- `under_review -> removed`

Disallowed:

- Any transition out of `removed`.
- `on_leave -> under_review`.
- `under_review -> on_leave`.
- Any transition that sets `to_role_id` to a role from another chapter.

Invariants:

- `removed` is terminal.
- Re-admission is a new `RosterEntry`; old removed rows remain immutable history except for audit metadata corrections if a later slice explicitly introduces them.
- Exactly one non-removed roster entry may exist for `(chapter_id, member_id)`.
- Every accepted status/role transition writes exactly one `roster_transitions` row with `aggregate_seq = new roster_entry version`.
- Every accepted transition writes through `mutate_entity()`, producing `activity_actions`, `activity_state_changes`, and a new aggregate head.
- Discord role sync is eventually consistent, not the source of truth. Durable roster state remains authoritative.

## 7. Open Questions

1. **Member prerequisite:** Should SLICE-018 depend on SLICE-007 after all? Current code has no `members` table, but future roadmap/ticket text defines one (`product-strategy/tickets/SLICE-007.md:21`). If not, SLICE-018 should explicitly accept external `member_id` strings and a separate Discord user ID for sync events.
2. **ChapterRole creation source:** Should chapter roles be materialized automatically from `chapters.template_snapshot.role_structure` when a chapter becomes active, or are operators expected to create them independently? Current `/provision` only patches `chapters.discord_resources`, not `chapter_roles`.
3. **Stable role keys:** Is `chapter_roles.name` guaranteed to match the logical keys in `chapters.discord_resources.role_ids` forever? If role renames are in scope later, `ChapterRole` needs a stable logical key separate from display name.
4. **Non-removed role sync semantics:** Should `on_leave` and `under_review` keep the chapter role set, remove it, or map to distinct Discord roles? Ticket only specifies active add and removed remove.
5. **Bot permission preflight:** Should WU-034 block sync if `manage_roles` is missing only, or also verify role hierarchy for each target role before attempting mutation? Prototype should answer this.

## 8. Recommended Magnitude

**Confirm L.**

Reasoning: the core mutation substrate, chapter transition pattern, deferred effect table, API client, actor/correlation middleware, authority guard, chapter resources, and foundation roster/role tables already exist. The slice is still large because it spans public API, migration hardening, projection history, chapter-scoped authority, a missing member prerequisite decision, and a new Discord member role sync failure path.
