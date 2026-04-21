# SLICE-013 Phase 3: Proposal

## 1. Executive summary

SLICE-013 should ship chapter provisioning as three work units:

- **WU-018: Template management API.** Keep SLICE-003's content-shape `schema_version` intact and add template-family lineage with `version BIGINT NOT NULL` and `template_family_id UUID NOT NULL`. Template rows remain immutable in-place; `PATCH /api/v1/chapter-templates/{template_id}` inserts a new row in the same family at `max(version) + 1`, locks the template family while checking `expected_current_version`, and rejects stale writes with `412 Precondition Failed`.
- **WU-019: Chapter lifecycle API.** Replace the legacy in-memory chapter substrate with persisted `chapters` and `chapter_transitions` tables. Chapter ids are UUID strings used as `aggregate_id` for `mutate_entity()`. Chapters start `proposed`, transition through the SLICE-013 state matrix only, copy the template snapshot at create time, and store Discord resource ids incrementally in `discord_resources`.
- **WU-020: Discord provisioning workflow.** Add one async Discord command handler, `provision_chapter`, registered through the existing interaction registry and implemented with SLICE-006's `ApiClient`. The handler checks bot permissions, calls the API as the `discord-provisioner` service actor, carries the originating Discord user in request bodies, idempotently creates Discord resources by deterministic names, persists resource ids through `PATCH /api/v1/chapters/{chapter_id}/discord-resources`, and enqueues a consequential deferred effect if provisioning fails.

This revision resolves the Phase 4 MEDIUM risks by narrowing lifecycle scope to proposed/provisioning/active/failure only, replacing the legacy in-memory chapter service atomically inside SLICE-013, adding a dedicated incremental resource persistence endpoint, making active-transition completeness strict against the template snapshot, making failed-provisioning deferred effects deterministic by transition id, making template PATCH concurrency explicitly lock the family, splitting the template migration into nullable/backfill/not-null steps, seeding the Discord provisioner service grants, requiring early Discord deferred acknowledgement, and pinning Discord-to-API actor mapping to a service actor plus originating-user payload.

Source note: the prompt names `.pipeline/research.md`, but that file is absent in this worktree. The matching prototype research exists at `prototyping/slice-013-chapter-provisioning/research.md`; it defines the prototype questions and constraints, including the existing registry/API/mutation/deferred-effect seams and the template mutability contradiction (lines 8-26, 46-80, 92-110, 121-139).

Endpoint count note: the earlier proposal followed the six route operations in the ticket and synthesis. Phase 4 risk review adds one AC3-required incremental persistence route, so this proposal now defines seven route operations: three template routes, three chapter lifecycle routes, and `PATCH /api/v1/chapters/{chapter_id}/discord-resources`.

## 2. In scope / anti-scope

In scope:

- **Template lineage, not in-place mutation.** D1 requires `chapter_templates.version` and `template_family_id`, with PATCH creating a new row in the same family while preserving `schema_version` as the separate content-shape version (`.pipeline/synthesis.md:11-18`). Current SLICE-003 evidence: `schema_version` already exists in the migration and contract (`migrations/versions/wu-007a_chapter_templates_foundation.py:21-26`, `services/api/app/contracts/chapter_templates.py:70-83`), and tests intentionally assert immutability (`services/api/tests/test_chapter_template_foundation.py:242-251`).
- **Four-state SLICE-013 chapter lifecycle.** SLICE-013 covers only `proposed`, `provisioning`, `active`, and `provisioning_failed`. `archived` is owned by SLICE-023 and is not part of this slice. The implementation must reject invalid transitions before writes.
- **Copy-on-instantiate snapshots.** D3 requires each chapter row to store the exact template version's operational structure in `template_snapshot` and retain `template_id` as provenance (`.pipeline/synthesis.md:37-44`). Prototype findings agree that live template references would retroactively change operational configuration (`prototyping/slice-013-chapter-provisioning/findings.md:37-43`).
- **Sequential Discord provisioning with failure degradation.** D4 requires category, roles, channels, persisted partial resources, transition to `provisioning_failed`, and deferred effect enqueue on failure (`.pipeline/synthesis.md:46-55`).
- **Idempotent Discord creation.** D5 requires name checks before resource creation (`.pipeline/synthesis.md:57-59`). The proposal uses name checks plus `discord_resources` as the durable anchor. If the API loses a just-created resource id because `PATCH /discord-resources` fails, retry rediscovers the resource by deterministic slug-name matching before creating anything new.
- **Deferred effect enqueue only.** D6 defines the failed provisioning payload and defers the handler/worker implementation (`.pipeline/synthesis.md:61-78`, `152-158`). Existing SLICE-004 substrate already supports idempotent enqueue, unchecked consequential preconditions, worker gating, and retry exhaustion (`services/api/app/repositories/deferred_effects.py:31-102`, `148-170`, `195-225`; `services/api/tests/test_deferred_effect_foundation.py:221-255`, `323-382`, `582-638`).
- **Canonical Discord resource storage on Chapter.** D7 requires `chapters.discord_resources` as JSONB. In this slice it is retained for provisioning audit and retry recovery; archive retention semantics are deferred to SLICE-023.
- **AC3-required Discord resource persistence endpoint.** `PATCH /api/v1/chapters/{chapter_id}/discord-resources` is in scope. AC3 requires verified Discord resource IDs to be persisted through the API before the final active transition, so WU-019 owns this merge endpoint and WU-020 must call it after each created or discovered Discord resource.
- **Authority guards and actor threading.** D8 requires `RequireAuthority` for template and chapter read/write permissions (`.pipeline/synthesis.md:92-99`). The current guard resolves actor identity from context and evaluates grants (`services/api/app/core/dependencies.py:50-58`, `61-143`), while `ActorMiddleware` resolves `X-Actor-Kind` and `X-Actor-Id` headers (`services/api/app/core/actor.py:26-42`, `63-81`). Discord-originated API calls use `X-Actor-Kind: service` and `X-Actor-Id: discord-provisioner`; the originating Discord operator is carried in request bodies and audit payloads. WU-019 seeds the required global grants for `discord-provisioner` so WU-020 calls do not all fail 403.
- **Legacy chapter substrate replacement.** SLICE-013 deletes/replaces the legacy in-memory `ChapterService` / `InMemoryChapterRepository` / integer-id contracts / `/archive` route as part of this slice; no parallel parked code. This is required because duplicate module paths, duplicate `GET /api/v1/chapters/{chapter_id}` routes with incompatible id types, one `app.state.chapter_service`, and mixed integer/text `aggregate_type="chapter"` ids would corrupt behavior.
- **Discord permission requirements.** D9 requires `MANAGE_CHANNELS`, `MANAGE_ROLES`, and `VIEW_CHANNEL`, documented in `DiscordSettingsRead`, with an optional fail-fast runtime check (`.pipeline/synthesis.md:101-108`). Current Discord settings expose only token, guild id, and API base URL (`services/discord/app/contracts/runtime_settings.py:24-30`).
- **New persisted chapter tables.** D10 defines `chapters` and `chapter_transitions`, with text primary key and `aggregate_id = str(chapter.id)` (`.pipeline/synthesis.md:109-140`).
- **Discord handler placement.** D11 requires `commands/chapters.py` for registration and `handlers/chapters.py` for the async provisioning sequence (`.pipeline/synthesis.md:141-150`). Existing dispatch already routes `InteractionEnvelope` through `InteractionRegistry` and preserves audit context (`services/discord/app/commands/registry.py:14-33`; `services/discord/tests/test_api_context.py:110-146`).

Anti-scope:

- No post-provision chapter editing, template swaps, or name changes (D12, `.pipeline/synthesis.md:152-155`).
- No archive workflow, archive state, archive transitions, resource teardown, or `archived_at` column. SLICE-023 owns chapter archival.
- No roster management, template-family permission model, retry worker, multi-guild, or multi-tenant support (D12, `.pipeline/synthesis.md:154-159`).
- No new third-party dependencies; prototype research set this as a constraint (`prototyping/slice-013-chapter-provisioning/research.md:84-90`).

The SLICE-013 transition matrix is:

```python
ChapterState = Literal["proposed", "provisioning", "active", "provisioning_failed"]
ChapterTransition = {
    ("proposed", "provisioning"),
    ("provisioning", "active"),
    ("provisioning", "provisioning_failed"),
    ("provisioning_failed", "provisioning"),
}
```

## 3. Technical approach per WU

### WU-018 (template mgmt API)

**Migration: `migrations/versions/wu-018_chapter_templates.py`**

- `revision = "wu_018_chapter_templates"`, `down_revision = "wu_014_authority_api"` because the current migration head is `wu_014_authority_api` (`migrations/versions/wu-014_authority_api.py:9-12`).
- Step 0: `CREATE EXTENSION IF NOT EXISTS pgcrypto;`. Current repo search finds no existing `pgcrypto`, `gen_random_uuid()`, or `CREATE EXTENSION` usage, so WU-018 must enable it before the backfill.
- Step 1: add nullable columns:
  - `template_family_id UUID NULL`
  - `version BIGINT NULL`
- Step 2: backfill existing rows so each existing template becomes version 1 of its own new family:

  ```sql
  UPDATE chapter_templates
  SET template_family_id = gen_random_uuid(), version = 1
  WHERE template_family_id IS NULL;
  ```

- Step 3: set constraints and indexes:
  - `ALTER COLUMN template_family_id SET NOT NULL`
  - `ALTER COLUMN version SET NOT NULL`
  - `CREATE UNIQUE INDEX uq_chapter_templates__family_version ON chapter_templates (template_family_id, version)`
  - `CREATE INDEX ix_chapter_templates__family ON chapter_templates (template_family_id)`
- Keep existing `schema_version INT` exactly as-is. It remains the content-shape validator already pinned by SLICE-003 (`services/api/tests/test_chapter_template_foundation.py:254-305`).

**Contract extensions: `services/api/app/contracts/chapter_templates.py`**

- Add `template_family_id: UUID` and `version: int = Field(ge=1)` to `ChapterTemplateRead`. This `version` is the template-family version, distinct from `schema_version`, which remains the content-shape version.
- Add optional `template_family_id: UUID | None = None` only if needed for internal creation helpers; public POST should not allow caller-provided family ids unless explicitly required later.
- Add `ChapterTemplatePatch`:
  - `expected_current_version: int = Field(ge=1)`
  - optional `name`, `channel_structure`, `role_structure`, `default_permission_intents`
  - no `schema_version` updates unless the body supplies the current `CURRENT_TEMPLATE_SCHEMA_VERSION`
  - at least one patchable field must be present.
- Add typed errors:
  - `ChapterTemplateNotFoundError`
  - `StaleTemplateVersionError`
  - `ChapterTemplatePatchEmptyError`

**Repository: `services/api/app/repositories/chapter_templates.py`**

- Extend `insert_chapter_template(...)` to insert `version` and `template_family_id`.
- Extend `fetch_chapter_template(...)` to select the new fields.
- Add `fetch_chapter_template_for_update(connection, template_id)` for PATCH. It locks the source row, returns `template_family_id`, and runs a `SELECT ... FOR UPDATE` across the family rows before version calculation.
- Add `fetch_current_template_family_version_for_update(connection, template_family_id) -> int | None`.
- Add `insert_template_version(...)` that receives the new row payload and writes the new immutable row.

**Service: `services/api/app/services/chapter_templates.py`**

- `create_chapter_template(db, request, actor)` becomes actor-aware. It creates `template_id = uuid4()`, `template_family_id = template_id`, `version = 1`, and calls `mutate_entity()` with `aggregate_type="chapter_template"` and `aggregate_id=str(template_id)`.
- `read_chapter_template(db, template_id)` returns the exact version row by id. It still rejects unsupported `schema_version` with `TemplateSchemaVersionMismatchError` as it does today (`services/api/app/services/chapter_templates.py:83-92`).
- Add `patch_chapter_template(db, template_id, request, actor)`:
  - Within one transaction, lock the source template row and all current rows in its family with `SELECT ... FOR UPDATE`.
  - If `request.expected_current_version != current_family_version`, reject with `StaleTemplateVersionError` and surface `412 Precondition Failed` before insert.
  - Build the new row by copying all omitted fields from the current row and applying supplied patch fields.
  - Insert a new `id`, same `template_family_id`, `version=current_family_version + 1`.
  - Catch `IntegrityError` on `uq_chapter_templates__family_version` as a defensive race guard and translate it to `StaleTemplateVersionError` -> `412`, not `500`.
  - Use `mutate_entity()` for the new version's aggregate row and state change. Keep old rows untouched.
- Do not introduce an `update_chapter_template` in-place mutator. The old SLICE-003 immutability test should be revised to assert no in-place update surface, while accepting `patch_chapter_template` as version creation.

**Endpoints: `services/api/app/api/v1/endpoints/chapter_templates.py`**

- `POST /api/v1/chapter-templates -> ChapterTemplateRead`
  - `Depends(RequireAuthority("chapter_template.write", "global"))`
  - `actor: ActorIdentity = Depends(get_current_actor)`
  - returns `201 Created`, body includes `version=1` and `template_family_id`.
- `GET /api/v1/chapter-templates/{template_id} -> ChapterTemplateRead`
  - `Depends(RequireAuthority("chapter_template.read", "global"))`
  - returns exact version row.
- `PATCH /api/v1/chapter-templates/{template_id} -> ChapterTemplateRead`
  - `Depends(RequireAuthority("chapter_template.write", "global"))`
  - `actor: ActorIdentity = Depends(get_current_actor)`
  - body carries `expected_current_version`; stale version returns `412 Precondition Failed`.
- Add the router to `services/api/app/api/v1/router.py`, which currently mounts only audit, authority, chapters, health, policies, ready, and system routers (`services/api/app/api/v1/router.py:11-28`).

**Tests: `services/api/tests/test_chapter_templates.py`**

- POST persists `version=1`, `template_family_id=id`, and all three JSONB structures.
- GET returns exact version and still enforces `schema_version`.
- PATCH creates a second row with the same family id and `version=2`; the original row remains unchanged.
- Two PATCHes racing on the same `expected_current_version` produce one accepted version and one `412`, never a leaked `IntegrityError`/`500`.
- PATCH with stale `expected_current_version` returns 412 and does not insert a row.
- POST/PATCH without actor headers or without matching authority grant returns the current authority errors. This should follow the existing guard tests that mount routes behind `RequireAuthority` (`services/api/tests/test_authority_enforcement.py:67-82`, `162-180`).
- Existing `services/api/tests/test_chapter_template_foundation.py` is updated only for additive `version`/`template_family_id` fields and the no-in-place-update assertion.

### WU-019 (chapter lifecycle)

**Migration: `migrations/versions/wu-019_chapters.py`**

- `revision = "wu_019_chapters"`, `down_revision = "wu_018_chapter_templates"`.
- Create `chapters`:
  - `id TEXT PRIMARY KEY`
  - `name TEXT NOT NULL`
  - `template_id UUID NOT NULL REFERENCES chapter_templates(id)`
  - `template_snapshot JSONB NOT NULL`
  - `configuration JSONB NOT NULL DEFAULT '{}'::jsonb`
  - `state TEXT NOT NULL CHECK (state IN ('proposed','provisioning','active','provisioning_failed'))`
  - `discord_resources JSONB NOT NULL DEFAULT '{}'::jsonb`
  - `created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`
  - `UNIQUE INDEX uq_chapters__name ON chapters (LOWER(name))`
- Create `chapter_transitions` as a denormalized query projection:
  - `id UUID PRIMARY KEY`
  - `chapter_id TEXT NOT NULL REFERENCES chapters(id)`
  - `aggregate_seq BIGINT NOT NULL`
  - `from_state TEXT NOT NULL`
  - `to_state TEXT NOT NULL`
  - `actor_kind TEXT NOT NULL`
  - `actor_id TEXT NOT NULL`
  - `originating_actor_kind TEXT NULL`
  - `originating_actor_id TEXT NULL`
  - `reason TEXT NOT NULL`
  - `recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`
  - `INDEX ix_chapter_transitions__chapter_id`
  - `UNIQUE INDEX uq_chapter_transitions__chapter_seq ON chapter_transitions (chapter_id, aggregate_seq)`
- Do not add `archived_at`; archival is out of scope.
- Seed the Discord provisioner service actor grant in the same migration. The actual `authority_grants` schema uses `grantee_id` plus a JSONB `permissions` set, not per-permission rows or `granted_by_actor_*` columns (`migrations/versions/wu-004_authority_foundation.py:17-35`; `services/api/app/repositories/authority.py:19-31`). Insert one global, non-expiring grant for `grantee_id='discord-provisioner'`:

  ```sql
  INSERT INTO authority_grants (
      id, grantee_id, scope_kind, scope_id, permissions, expires_at,
      revoked_at, revoked_by, revocation_reason, predecessor_grant_id
  ) VALUES (
      gen_random_uuid(),
      'discord-provisioner',
      'global',
      NULL,
      '["chapter.read","chapter.write","chapter_template.read"]'::jsonb,
      NULL,
      NULL,
      NULL,
      NULL,
      NULL
  );
  ```

- The migration test `test_discord_provisioner_service_actor_has_chapter_grants_after_migration` queries `authority_grants` for active `grantee_id='discord-provisioner'`, `scope_kind='global'`, `scope_id IS NULL`, and the three permissions in the JSONB permission set.

**Replacement contract module: `services/api/app/contracts/chapters.py`**

SLICE-013 replaces this module in place. Delete the old `ChapterStatus` enum, integer-id shapes, direct update/archive request types, and any compatibility aliases.

- `ChapterState = Literal["proposed", "provisioning", "active", "provisioning_failed"]`
- `ChapterId = str`; values are UUID strings.
- `ChapterCreate`:
  - `name: str`
  - `template_id: UUID`
  - `configuration: dict[str, Any] = {}`
  - `originating_actor_kind: Literal["user", "service"] = "user"`
  - `originating_actor_id: str`
- `ChapterRead`:
  - `id: str`
  - `name: str`
  - `template_id: UUID`
  - `template_snapshot: dict[str, Any]`
  - `configuration: dict[str, Any]`
  - `state: ChapterState`
  - `discord_resources: ChapterDiscordResources`
  - `created_at: datetime`
  - `version: int`
- `ChapterTransitionRequest`:

  ```python
  class ChapterTransitionRequest(BaseModel):
      to_state: ChapterState
      reason: str = Field(min_length=1)
      originating_actor_kind: Literal["user", "service"] = "user"
      originating_actor_id: str
  ```

- `ChapterDiscordResources`:
  - `category_id: str | None = None`
  - `role_ids: dict[str, str] = {}`
  - `channel_ids: dict[str, str] = {}`
- `ChapterResourcesPatchRequest`:
  - `resources: ChapterDiscordResources`
- `ChapterTransitionRead`:
  - fields from `chapter_transitions`, plus resulting chapter version if useful.
- `ChapterProvisionResult` may live in Discord contracts for WU-020, but the API should expose enough fields to represent success/failure in transition payloads.
- Add typed errors:
  - `ChapterNotFoundError`
  - `InvalidChapterTransitionError`
  - `IncompleteProvisioningError(missing: str)`

**Replacement repository: `services/api/app/repositories/chapters.py`**

- Replace the current in-memory protocol implementation. Current code stores `ChapterRecord.id` as `int`, defaults status to `provisioning`, and has no template fields (`services/api/app/repositories/chapters.py:25-34`, `54-72`), which is incompatible with this slice.
- Delete `InMemoryChapterRepository`, `ChapterRecord`, integer ids, and in-memory store references. The remaining repository surface is Postgres-backed:
  - `fetch_chapter(connection, chapter_id)`
  - `fetch_chapter_for_update(connection, chapter_id)`
  - `insert_chapter_transition(connection, row)`
  - `_update_chapter_state(connection, chapter_id, state)`
  - `_merge_chapter_discord_resources(connection, chapter_id, resources)`
- `insert_chapter(connection, row)` may be private if only called by `create_chapter(...)`; no public in-memory repository class remains.
- `list_chapter_transitions(connection, chapter_id)` is allowed only if tests need direct verification; no public route is required.
- State mutation helpers are underscore-prefixed and are only called by `transition_chapter(...)` or `patch_chapter_discord_resources(...)` inside `mutate_entity()`.

**Replacement service: `services/api/app/services/chapters.py`**

- Replace the old `ChapterService` class and action-store/state-change-store service path. Current service appends directly to in-memory action/state stores and keeps `_heads` in memory (`services/api/app/services/chapters.py:54-92`, `104-186`); WU-019 must use the shared `mutate_entity()` primitive, which already locks aggregate heads, rejects stale versions, inserts action/state-change rows, and advances version once (`services/api/app/services/mutations.py:58-71`, `112-185`).
- New public service functions are exactly `create_chapter`, `transition_chapter`, and `patch_chapter_discord_resources`, plus read helpers. Delete `archive_chapter`, direct update functions, `_heads`, action-store/state-change-store constructor wiring, and all in-memory store references.
- All chapter state changes go through `transition_chapter(chapter_id, to_state, actor, reason)`. No direct public state-update function is allowed.
- `create_chapter(db, request, actor)`:
  - Read the exact template row by `template_id`.
  - Validate current `schema_version`.
  - Generate `chapter_id = str(uuid4())`; do not accept integer ids or derive aggregate ids from names.
  - Deep-copy the template's `channel_structure`, `role_structure`, and `default_permission_intents` into `template_snapshot`, including provenance fields `template_id`, `template_family_id`, `template_version`, and `schema_version`.
  - Call `mutate_entity(aggregate_type="chapter", aggregate_id=chapter_id, expected_version=0, ...)`.
  - Inside the accepted mutation's projection callback, insert the chapter at `state="proposed"`, `discord_resources={"category_id": None, "role_ids": {}, "channel_ids": {}}`, `configuration=request.configuration`.
  - Include `originating_actor_kind` and `originating_actor_id` in the accepted audit payload. When `originating_actor_kind == "user"`, also record `originating_user_discord_id` for Discord-originated requests.
- `read_chapter(db, chapter_id)`:
  - Return the persisted row plus current aggregate version and set ETag from the same version.
- `patch_chapter_discord_resources(db, chapter_id, request, actor, expected_version)`:
  - Lock chapter row in `mutate_projection`.
  - Merge into existing `discord_resources`; do not replace the whole dict. `role_ids` and `channel_ids` are shallow-merged by key. `category_id=None` means "no category update" and cannot clear an existing category in this slice.
  - Require `If-Match`; missing header returns `428`, stale header returns `412`.
  - Use `RequireAuthority("chapter.write", "global")`.
- `transition_chapter(db, chapter_id, request, actor, expected_version)`:
  - Lock chapter row in the `mutate_projection`.
  - Validate `(from_state, request.to_state)` against the four-state matrix before changing row state.
  - For `to_state == "active"` only, call `_verify_provisioning_complete(chapter)` before inserting the transition or updating state. It must require `chapter.discord_resources` to contain `category_id`, a `role_ids` entry for every role name in `chapter.template_snapshot["role_structure"]`, and a `channel_ids` entry for every channel name in `chapter.template_snapshot["channel_structure"]`.

  ```python
  def _verify_provisioning_complete(chapter: Chapter) -> None:
      snapshot = chapter.template_snapshot
      resources = chapter.discord_resources

      if not resources.get("category_id"):
          raise IncompleteProvisioningError(missing="category")

      expected_role_names = {r["name"] for r in snapshot.get("role_structure", [])}
      present_role_names = set(resources.get("role_ids", {}).keys())
      missing_roles = expected_role_names - present_role_names
      if missing_roles:
          raise IncompleteProvisioningError(missing=f"roles:{sorted(missing_roles)}")

      expected_channel_names = {c["name"] for c in snapshot.get("channel_structure", [])}
      present_channel_names = set(resources.get("channel_ids", {}).keys())
      missing_channels = expected_channel_names - present_channel_names
      if missing_channels:
          raise IncompleteProvisioningError(missing=f"channels:{sorted(missing_channels)}")
  ```

  - `_verify_provisioning_complete(chapter)` raises `IncompleteProvisioningError(missing="category")`, `IncompleteProvisioningError(missing=f"roles:{sorted(missing_roles)}")`, or `IncompleteProvisioningError(missing=f"channels:{sorted(missing_channels)}")`. The endpoint maps it to `409 Conflict` with body `{"code": "incomplete_provisioning", "missing": "roles:['officer']"}`.
  - Insert one `chapter_transitions` row with a service-generated `chapter_transition_id`, actor fields, originating actor fields, and `aggregate_seq=expected_version + 1`.
  - Update `chapters.state` inside the same `mutate_entity()` transaction.
  - If `to_state == "provisioning_failed"`, insert a consequential deferred effect row inside the same transaction using repository-level `enqueue_effect(connection=...)`, not the service wrapper that opens a separate connection. Prototype findings explicitly require repository-level insert on the active connection for atomicity (`prototyping/slice-013-chapter-provisioning/findings.md:27-35`).
  - The deferred effect idempotency key is exactly `f"chapter_provision_retry:{chapter_id}:{chapter_transition_id}"`. SLICE-004's `ON CONFLICT DO NOTHING` makes duplicate enqueue for the same transition attempt a no-op. Each retry creates a new `provisioning_failed -> provisioning` transition row and therefore a new transition id/key.
- `activity_actions` remains the authoritative audit ledger. `chapter_transitions` is a denormalized per-chapter projection for fast listing. The state change is recorded in both `activity_actions`/`activity_state_changes` via `mutate_entity()` and `chapter_transitions` via the projection callback in the same transaction. If an inconsistency is ever discovered, `activity_actions` wins.

**Replacement endpoints: `services/api/app/api/v1/endpoints/chapters.py`**

- `POST /api/v1/chapters -> ChapterRead`
  - `Depends(RequireAuthority("chapter.write", "global"))`
  - `actor: ActorIdentity = Depends(get_current_actor)`
  - returns `201 Created`, state `proposed`, `version=1`, and ETag.
- `GET /api/v1/chapters/{chapter_id} -> ChapterRead`
  - `Depends(RequireAuthority("chapter.read", "global"))`
  - returns the chapter and current version/ETag.
- `POST /api/v1/chapters/{chapter_id}/transitions -> ChapterRead`
  - `Depends(RequireAuthority("chapter.write", "global"))`
  - `actor: ActorIdentity = Depends(get_current_actor)`
  - requires `If-Match`; missing returns `428`, stale returns `412`, invalid transition returns `409`.
  - `to_state="active"` also returns `409` with `{"code": "incomplete_provisioning", "missing": ...}` when the chapter lacks any template-required category, role, or channel Discord id.
- `PATCH /api/v1/chapters/{chapter_id}/discord-resources -> ChapterRead`
  - `Depends(RequireAuthority("chapter.write", "global"))`
  - `actor: ActorIdentity = Depends(get_current_actor)`
  - requires `If-Match`; missing returns `428`, stale returns `412`.
  - body: `{"resources": {"category_id": str | None, "role_ids": dict[str, str], "channel_ids": dict[str, str]}}`
  - merges into `discord_resources` instead of replacing it.
- Do not add compatibility aliases for legacy `PATCH /api/v1/chapters/{chapter_id}` or `/archive` behavior. Delete the legacy `/archive` route from this file.

**Factory/dependencies replacement**

- `services/api/app/core/factory.py` rewires `app.state.chapter_service` to the new Postgres-backed service facade or removes the state field if endpoints call functions directly. Remove `chapter_repository`, `action_store`, and `state_change_store` factory params that existed only for in-memory wiring. Remove the `InMemoryChapterRepository` import.
- `services/api/app/core/dependencies.py` updates `get_chapter_service` if a facade remains. Delete in-memory-only dependency functions.

**Tests: `services/api/tests/test_chapter_lifecycle.py`**

- Creating a chapter from a template returns `state="proposed"`, the selected `template_id`, a UUID string id, empty structured `discord_resources`, a deep-copied `template_snapshot`, `version=1`, and ETag.
- Editing a template family later does not alter an existing chapter snapshot.
- Valid transitions:
  - `proposed -> provisioning`
  - `provisioning -> active` only after category id, every template role id, and every template channel id are persisted on the chapter
  - `provisioning -> provisioning_failed`
  - `provisioning_failed -> provisioning`
- Invalid transitions return 409 before any `chapter_transitions` row is inserted.
- Active transition strict completeness tests:
  - `test_transition_to_active_rejects_when_discord_resources_missing_category`
  - `test_transition_to_active_rejects_when_discord_resources_missing_role`
  - `test_transition_to_active_rejects_when_discord_resources_missing_channel`
- Incremental resource PATCH merges category, roles, and channels across multiple calls and never replaces previously stored ids.
- Optimistic locking follows the AGENTS contract: read version N, update with `If-Match: "N"` succeeds to N+1, update with stale `If-Match: "N"` returns `412 Precondition Failed`.
- Failed provisioning transition inserts one consequential deferred effect with `precondition_state="unchecked"`, idempotency key `chapter_provision_retry:{chapter_id}:{chapter_transition_id}`, and leaves the chapter non-active.
- Retrying from `provisioning_failed` to `provisioning` is covered by AC4 with `test_retry_transition_from_provisioning_failed_to_provisioning`.
- POST/PATCH endpoints require actor headers and authority grants.
- `test_discord_provisioner_service_actor_has_chapter_grants_after_migration` asserts the migration seeds active global `chapter.read`, `chapter.write`, and `chapter_template.read` grants for `discord-provisioner`.
- Delete or rewrite legacy `services/api/tests/test_chapters.py`; it must no longer assert integer ids, `ChapterStatus`, direct PATCH, archive, or in-memory state changes.
- Delete or rewrite `services/api/tests/test_contracts_chapters.py` to assert `ChapterState`, `ChapterId = str`, `ChapterCreate`, `ChapterRead`, `ChapterTransitionRequest`, and `ChapterResourcesPatchRequest`.
- Post-implementation grep invariants against code and tests:
  - `InMemoryChapterRepository` -> 0 occurrences
  - `ChapterStatus` -> 0 occurrences
  - `class ChapterRecord` -> 0 occurrences
  - `/archive` route -> 0 occurrences under `/api/v1/chapters`
  - integer `chapter_id` path/contract declarations -> 0 occurrences

### WU-020 (Discord provisioning workflow)

**Command registration: `services/discord/app/commands/chapters.py`**

- Register a slash command named `provision_chapter` with one required option, `chapter_id`.
- Register the handler through `HumilityBot.register_interaction_handler(...)`, which delegates to `InteractionRegistry.register(...)` (`services/discord/app/core/bot.py:31-37`; `services/discord/app/commands/registry.py:18-33`).
- Ensure `build_bot_with_registry(...)` imports/installs chapter command registration before command-tree sync. Current startup only syncs when registry has handlers (`services/discord/app/__main__.py:59-70`).

**Handler: `services/discord/app/handlers/chapters.py`**

- Add async `provision_chapter_handler(envelope: InteractionEnvelope) -> InteractionResult`.
- Use `bot.api_client` / injected `ApiClient`; do not create raw `httpx` clients in the handler. Current daemon already constructs a shared `ApiClient` from settings and the async client (`services/discord/app/__main__.py:55-86`).
- The Discord handler MUST `ack_deferred()` inside the 3-second interaction window and return the final `InteractionResult` via follow-up webhook. The current registry only calls the handler and returns its result (`services/discord/app/commands/registry.py:28-33`), and `HumilityBot.dispatch_interaction(...)` only sends a Discord response after registry dispatch completes (`services/discord/app/core/bot.py:51-56`), so SLICE-013 must add the explicit deferred-ack seam before any API call or visible Discord mutation. The handler's outer Discord response completes after the API+Discord work finishes, not synchronously.
- API headers for all guarded calls:
  - `X-Actor-Kind: service`
  - `X-Actor-Id: discord-provisioner`
  - correlation and causation headers propagated through the existing SLICE-006 `ApiClient` seam.
- Request bodies for create/transition calls carry the human operator:
  - `originating_actor_kind="user"`
  - `originating_actor_id=<Discord user id from envelope>`
  - API services record this in audit payloads as `originating_user_discord_id`.
- Phase 2 simplification: permissions are granted to the `discord-provisioner` service actor. Later slices can implement per-user Discord-to-API identity federation. `ActorKind = Literal["user", "service", "system"]` already accepts `service`, and SLICE-008 `ActorMiddleware` accepts all three.
- Before any visible Discord mutation, perform a runtime permission check against `guild.me.guild_permissions`:
  - `manage_channels`
  - `manage_roles`
  - `view_channel`
  - optionally role hierarchy where accessible.
- Fetch the chapter:
  - `GET /api/v1/chapters/{chapter_id}`
  - Require `state="proposed"` for first provisioning. Retry starts from `provisioning_failed` only after the API accepts `provisioning_failed -> provisioning`.
- Transition to provisioning:
  - `POST /api/v1/chapters/{chapter_id}/transitions` with `to_state="provisioning"`, `reason`, originating actor fields, and `If-Match` from the GET response.
- Create Discord resources sequentially:
  - Determine names from the chapter name and `template_snapshot` using a stable, collision-resistant slug derivation within the guild.
  - Before each create, search existing guild category/role/channel by deterministic name. If found, record that id and skip creation.
  - Create category first.
  - Create roles in `role_structure` order. Role positioning can be deferred unless Discord creation order proves insufficient, because role ordering was not fully prototyped (`prototyping/slice-013-chapter-provisioning/findings.md:11-14`, `184-190`).
  - Create channels with permission overwrites derived from `default_permission_intents`.
  - After every successful create or existing-name match, call `PATCH /api/v1/chapters/{chapter_id}/discord-resources` with the latest ETag before the next Discord call. This follows the prototype finding that created ids must be captured append-as-you-go, not only on final success (`prototyping/slice-013-chapter-provisioning/findings.md:5-14`).
  - If a `PATCH /discord-resources` call fails after the Discord resource exists, stop the current run. On retry, rediscover the resource by deterministic slug-name matching against the guild before creating another resource with the same logical key.
- On success:
  - `POST /api/v1/chapters/{chapter_id}/transitions` with `to_state="active"`, originating actor fields, and latest ETag.
  - Return an ephemeral success `InteractionResult`.
- On failure:
  - Catch real `discord.Forbidden`, `discord.HTTPException`, and `TypeError` surfaces noted by prototype research (`prototyping/slice-013-chapter-provisioning/research.md:28-40`).
  - Persist any ids already discovered/created through `PATCH /discord-resources` before posting failure when the API is reachable.
  - POST a transition to `provisioning_failed` with originating actor fields and latest ETag. The API transition atomically inserts the deferred effect with the deterministic idempotency key.
  - Return an ephemeral failure result naming the failed step and recorded deferred effect if available.

**Discord settings/runtime check**

- Update `DiscordSettingsRead` with:
  - `required_bot_permissions: tuple[str, ...] = ("MANAGE_ROLES", "MANAGE_CHANNELS", "VIEW_CHANNEL")`
- Runtime boot-time validation is optional in SLICE-013. The handler-level preflight remains required before visible Discord writes.
- No new env var.
- Add a small runtime check helper in `handlers/chapters.py` or `core/bot.py`; keep it testable with mocks.

**Tests: `services/discord/tests/test_chapter_provisioning.py`**

- Use `MockGuild`/mock category/role/channel objects. Do not hit live Discord.
- `test_provision_chapter_handler_acks_deferred_before_api_calls` asserts deferred ack fires before the first API call.
- Success path:
  - API calls happen in order: GET chapter, transition to provisioning, resource PATCH after each found/created resource, transition to active.
  - Mock guild receives create calls only for missing deterministic names.
  - Existing names are reused and not duplicated, including `test_discord_handler_rediscovers_role_by_name_after_patch_failure`, where role creation succeeds, `PATCH /discord-resources` fails, and a retry rediscovers the role by name instead of creating a duplicate.
  - Actor headers use `service/discord-provisioner`; originating Discord user is present in transition bodies; correlation headers are present.
- Missing permission path:
  - Fails before Discord create calls and returns an ephemeral error.
- Partial failure path:
  - Inject failure on second role/channel creation.
  - Created resources before the failure are persisted through `PATCH /discord-resources`.
  - Handler does not call active transition.
  - API receives a failed transition sufficient for deferred-effect enqueue.
- API failure path:
  - If the API cannot confirm resource persistence, handler stops creating further Discord resources and returns an operator-visible error.

## 4. Tradeoffs

- **Versioned rows instead of in-place template update.** This preserves SLICE-003 immutability while satisfying AC1's PATCH surface. The cost is a family/version lookup and new stale-write semantics, but it avoids a compatibility shim and makes copy-on-instantiate auditable.
- **Template family locking instead of optimistic insert-only race handling.** Locking the family before calculating the next version gives deterministic 412 behavior under concurrent PATCHes. The unique index remains the database backstop, and its `IntegrityError` is translated to the same typed stale-version error.
- **Snapshot on `chapters.template_snapshot` instead of `configuration`.** This adds one JSONB column but keeps operator configuration separate from operational provisioning structure. Prototype findings rejected putting the snapshot in `configuration` because it violates the governance boundary (`prototyping/slice-013-chapter-provisioning/findings.md:45-51`, `107-110`).
- **Chapter row as canonical partial-resource owner.** This avoids a new `chapter_provisioning_attempts` child table in this slice. The deferred-effect payload duplicates a snapshot of partial resources for operator visibility and idempotency, but the chapter row remains canonical per D7.
- **Dedicated `PATCH /discord-resources` endpoint.** A separate merge endpoint is narrower than overloading transitions or allowing `provisioning -> provisioning` self-transitions. It keeps the state machine small and lets the Discord handler persist resources immediately after each visible write.
- **Name-based rediscovery after lost PATCH.** If `PATCH /discord-resources` fails after a Discord resource is successfully created, the resource id is lost from the API's side. On retry, the handler rediscovers it via deterministic slug-name matching against the guild (D5). Slug derivation MUST be stable and collision-resistant within a guild; name drift breaks rediscovery. No secondary anchor, such as a Discord ID stored in Discord metadata, is available in Phase 0.
- **Deterministic retry effect idempotency.** The idempotency key includes `chapter_transition_id`, making repeated enqueue for the same failed transition a no-op while allowing a later retry attempt to create a new effect row.
- **`chapter_transitions` as denormalized projection, not audit source.** `activity_actions` remains authoritative for correlation, causation, status, and audit payload. `chapter_transitions` exists for fast chapter-scoped transition reads and is written in the same transaction. If the two disagree, `activity_actions` wins.
- **Service actor for Discord provisioning.** Granting authority to `discord-provisioner` avoids premature Discord-to-API identity federation. The originating Discord user is still preserved in request/audit payloads, so operator accountability is not lost.
- **Runtime permission check is best-effort.** Checking bot permissions before provisioning prevents obvious partial writes, but Discord can still reject individual operations because of role hierarchy, channel-specific constraints, rate limits, or HTTP failures. The failure path still has to be correct.

## 5. Interaction with existing code

- `chapter_templates` already exists with `id`, `name`, `schema_version`, the three JSONB structures, and `created_at` (`migrations/versions/wu-007a_chapter_templates_foundation.py:16-48`). WU-018 only adds lineage columns and new API/service paths; it must not reinterpret `schema_version`.
- `services/api/app/contracts/chapter_templates.py` already owns the template shape and validators (`services/api/app/contracts/chapter_templates.py:19-67`, `70-93`). Extend this module instead of creating a parallel template contract.
- `services/api/app/services/chapter_templates.py` already creates templates through `mutate_entity()` (`services/api/app/services/chapter_templates.py:38-74`). Keep that mutation primitive and make actor/version behavior explicit.
- `services/api/tests/test_chapter_template_foundation.py` must be updated for the additive fields. Its immutability assertion should remain conceptually true: no in-place update surface, but PATCH-as-new-version is now permitted (`services/api/tests/test_chapter_template_foundation.py:242-251`).
- SLICE-013 deletes the legacy in-memory `ChapterService` / `InMemoryChapterRepository` / integer-id contracts / `/archive` route as part of this slice; no parallel parked code.
- The current `chapters` API is a legacy stub: integer ids, `slug`, three statuses, direct PATCH/archive routes, and in-memory heads (`services/api/app/contracts/chapters.py:7-39`; `services/api/app/services/chapters.py:54-92`, `104-186`). WU-019 replaces it in place with the new persisted lifecycle contract; do not preserve old behavior through aliases or compatibility routes.
- The current factory still wires `InMemoryChapterRepository`, `InMemoryActionStore`, and `InMemoryStateChangeStore` into `ChapterService` (`services/api/app/core/factory.py:22-25`, `37-52`, `90-99`). WU-019 removes that wiring and replaces `app.state.chapter_service` with the Postgres-backed lifecycle service, or removes the state service if endpoints call module functions directly.
- `mutate_entity()` already supports caller-supplied connections and single aggregate-head advancement (`services/api/app/services/mutations.py:58-71`, `191-197`). WU-019 should use that for transition plus deferred-effect atomicity.
- `activity_actions` and `activity_state_changes` already provide the authoritative mutation/audit ledger (`services/api/app/repositories/mutations.py:36-117`). `chapter_transitions` must remain a projection written inside the same accepted mutation.
- `deferred_effects` already supports idempotency key uniqueness, `unchecked` consequential effects, dequeue gating, and retry exhaustion (`services/api/app/repositories/deferred_effects.py:31-102`, `148-170`, `195-225`). WU-019/WU-020 should enqueue `chapter_provisioning_retry` effects only; no worker implementation belongs in this slice.
- Discord dispatch already provides `InteractionEnvelope` and async handler dispatch (`services/discord/app/contracts/interactions.py:9-31`; `services/discord/app/commands/registry.py:28-33`). WU-020 should add chapter command modules, not a second dispatch framework.
- SLICE-006's `ApiClient` currently propagates correlation/causation headers (`services/discord/app/infrastructure/api_client.py:25-62`; `services/discord/tests/test_api_transport.py:52-104`) but not actor headers. WU-020 must extend this seam so Discord provisioning calls use service actor headers and preserve the originating operator in request bodies.

## 6. Resolved decisions and pins

- `archived` and `archived_at` are removed from SLICE-013. Archival belongs to SLICE-023.
- `ChapterTransitionRequest.to_state` uses the exact `ChapterState` literal and therefore cannot drift from the D2 transition matrix.
- `PATCH /api/v1/chapters/{chapter_id}/discord-resources` is the incremental persistence route. It requires `If-Match`, merges resources, and uses the same `RequireAuthority("chapter.write", "global")` guard as transitions.
- Active transitions require complete Discord resource mappings against the template snapshot: category id, every role from `role_structure`, and every channel from `channel_structure`. Missing resources raise `IncompleteProvisioningError(missing: str)` and return `409 incomplete_provisioning`.
- Discord provisioning calls the API as `service/discord-provisioner`; the originating Discord user is body/audit metadata, not the API caller for this slice.
- WU-019 migration seeds a non-expiring global authority grant for `grantee_id='discord-provisioner'` with `chapter.read`, `chapter.write`, and `chapter_template.read` in the JSONB `permissions` set. The existing authority guard keys lookup on `actor.actor_id`, so no `actor_kind` column is involved.
- Future `chapter_provisioning_retry` worker MUST re-read `chapters.discord_resources` before acting, not trust the effect payload snapshot. Chapter row is canonical (D7).
- `Template.version` on `ChapterTemplateRead` is retained as the template-family version and remains distinct from `schema_version`.
- `DiscordSettingsRead.required_bot_permissions` is added with default `("MANAGE_ROLES", "MANAGE_CHANNELS", "VIEW_CHANNEL")`; boot-time validation is optional.
- `provision_chapter` adds a deferred-ack seam because the current registry/bot path responds only after the handler returns (`services/discord/app/commands/registry.py:28-33`; `services/discord/app/core/bot.py:51-56`).
- Retry transition coverage is added under AC4 with `test_retry_transition_from_provisioning_failed_to_provisioning`.
- Failed-provisioning deferred effects use `effect_type="chapter_provisioning_retry"` and idempotency key `chapter_provision_retry:{chapter_id}:{chapter_transition_id}`.

## 7. Acceptance criteria trace

- **AC1: Template create/update persists channel and role structure and rejects stale updates with 412 Precondition Failed.**
  - WU-018 POST persists name, `schema_version`, `channel_structure`, `role_structure`, `default_permission_intents`, `version=1`, and `template_family_id`.
  - WU-018 PATCH locks the family, inserts a new immutable template version in the same family, preserves omitted structures, and rejects stale `expected_current_version` with 412.
  - Concurrent PATCH race on the same expected version returns one success and one 412, not 500.
  - Existing SLICE-003 schema-version tests remain additive, not broken.

- **AC2: Creating a chapter returns proposed state and the selected template reference.**
  - WU-019 POST `/api/v1/chapters` reads the selected template, stores `template_id`, deep-copies `template_snapshot`, and returns `state="proposed"`.
  - Chapter id is a UUID string and used as `aggregate_id`.

- **AC3: Provisioning moves proposed -> provisioning -> active only after verified Discord resource IDs are persisted through the API.**
  - WU-019 transition endpoint enforces the four-state matrix through `mutate_entity()`.
  - WU-019 provides the AC3-required `PATCH /api/v1/chapters/{chapter_id}/discord-resources` endpoint so verified Discord resource IDs are persisted through the API before activation.
  - WU-020 handler transitions to `provisioning`, creates/reuses Discord resources by deterministic name, persists ids through `PATCH /discord-resources`, then transitions to `active` only when category id, every template role id, and every template channel id are present in `discord_resources`.
  - If a resource create succeeds but `PATCH /discord-resources` fails, retry rediscovers the resource by deterministic name and does not duplicate it.
  - The Discord handler defers the interaction before the first API call and returns the final result by follow-up webhook.
  - Bot permissions are documented and checked before visible Discord writes where possible.

- **AC4: A failed Discord provisioning step queues a consequential deferred effect instead of partially marking the chapter active.**
  - WU-020 catches Discord/API provisioning failures, persists known partial resources when possible, and posts a `provisioning_failed` transition.
  - WU-019 performs state degradation plus `deferred_effects` enqueue inside the same mutation transaction using the existing repository-level enqueue seam.
  - The deferred effect uses deterministic idempotency key `chapter_provision_retry:{chapter_id}:{chapter_transition_id}`.
  - The chapter remains `provisioning_failed`, not `active`; the effect is `consequence_level="consequential"` and `precondition_state="unchecked"` for later validation.
  - Retry from `provisioning_failed -> provisioning` is tested explicitly.

## Revision history

- Revision 3: fixed Phase 4 round 3 audit and shortcut MEDIUM findings by making SLICE-013 replace the legacy in-memory chapter substrate in place, pinning `services/api/app/api/v1/endpoints/chapters.py`, seeding `discord-provisioner` authority grants in the WU-019 migration using the actual `authority_grants` schema, documenting name-based rediscovery after lost resource PATCH, requiring Discord deferred ack before API work, adding the matching WU-019/WU-020 tests, and requiring future retry workers to re-read canonical `chapters.discord_resources`.
- Revision 2: tightened active transition completeness to require category plus every template role/channel Discord id, documented `IncompleteProvisioningError(missing: str)` and the three missing-resource tests, made `PATCH /discord-resources` explicitly AC3-required in sections 2 and 3, and aligned synthesis archive scope to SLICE-023 only.
- Phase 4 risk revision: removed archive scope, added incremental Discord resource persistence, fixed template PATCH race semantics, split template migration into nullable/backfill/not-null steps, pinned Discord service actor mapping, made failed-provisioning deferred effects deterministic, and documented LOW-risk pins.
