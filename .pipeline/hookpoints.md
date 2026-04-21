# SLICE-013 Phase 5: Hookpoints

Inputs used:
- `.pipeline/proposal.md` revision 3
- `.pipeline/synthesis.md` D1-D12 binding
- `plans/risk/slice-013-{audit,scope,shortcut}.md` all LOW
- `product-strategy/tickets/SLICE-013.md`

Implementation rule: this slice replaces the legacy chapter substrate in place. Do not keep compatibility aliases, dual routes, parked in-memory code, or legacy integer id behavior.

## Full File List

| WU | Action | File | Purpose | Specific hook points |
|---|---|---|---|---|
| WU-018 | CREATE | `migrations/versions/wu-018_chapter_templates.py` | Add template family lineage to existing `chapter_templates`. | `upgrade()`: `CREATE EXTENSION IF NOT EXISTS pgcrypto`, add nullable `template_family_id`, `version`, backfill each existing row to its own family/version 1, set NOT NULL, create `uq_chapter_templates__family_version` and `ix_chapter_templates__family`. `downgrade()`: drop index/constraint columns in reverse. |
| WU-019 | CREATE | `migrations/versions/wu-019_chapter_lifecycle.py` | Persist chapters, chapter transitions, and seed Discord provisioner grants. | `upgrade()`: create `chapters`, create `chapter_transitions`, create indexes, insert active global grant for `grantee_id='discord-provisioner'` with `chapter.read`, `chapter.write`, `chapter_template.read`. `downgrade()`: delete that seed grant, drop transition table, drop chapter table. |
| WU-019 | MODIFY/REPLACE | `services/api/app/contracts/chapters.py` | Replace integer-id/update/archive contract with persisted lifecycle contract. | Delete `ChapterStatus`, `ChapterUpdate`, enum import, `slug`, `discord_*_id` fields. Add `ChapterState`, `ChapterId`, `ChapterDiscordResources`, `ChapterCreate`, `ChapterRead`, `ChapterTransitionRequest`, `ChapterResourcesPatchRequest`, `ChapterTransitionRead`, typed errors. Update `__all__`. |
| WU-018 | MODIFY | `services/api/app/contracts/chapter_templates.py` | Add immutable versioning contract. | Add `template_family_id`, `version` to `ChapterTemplateRead`; add `ChapterTemplatePatch`; add `ChapterTemplateNotFoundError`, `StaleTemplateVersionError`, `ChapterTemplatePatchEmptyError`; preserve `schema_version`; keep `ChapterTemplateCreate` free of caller-supplied `template_family_id`. |
| WU-020 | CREATE | `services/discord/app/contracts/chapters.py` | Discord-local provisioning result/step contract. | Public surface: `ProvisioningStep`, `ChapterProvisionResult`, `ChapterProvisioningError` if needed by handler tests. Keep this daemon-local; API chapter contracts remain in `services/api`. |
| WU-020 | MODIFY | `services/discord/app/contracts/interactions.py` | Add deferred-ack seam to interaction contract. | Extend `InteractionEnvelope` only if needed to carry a raw interaction/ack handle, or add protocol `InteractionAcknowledger`. Keep `InteractionHandler` async. Update `__all__`. |
| WU-020 | MODIFY | `services/discord/app/contracts/api_transport.py` | Allow actor/If-Match headers on API calls. | Add `headers: dict[str, str] | None = None` to `ApiTransportRequest` so chapter provisioning can send `X-Actor-*` and `If-Match` without raw httpx. |
| WU-019 | MODIFY/REPLACE | `services/api/app/repositories/chapters.py` | Replace in-memory repository with Postgres accessors. | Delete `ChapterRepository`, `InMemoryChapterRepository`, `ChapterRecord`, `StalePreconditionError`, `replace`, timezone imports, `ChapterStatus` import. Add `fetch_chapter`, `fetch_chapter_for_update`, `insert_chapter`, `_update_chapter_state`, `_merge_chapter_discord_resources`; `ChapterNotFoundError` now takes `str`. |
| WU-018 | MODIFY | `services/api/app/repositories/chapter_templates.py` | Persist and lock template versions. | Extend `insert_chapter_template` and `fetch_chapter_template` select/insert columns. Add `fetch_chapter_template_for_update`, `fetch_current_template_family_version_for_update`, `insert_template_version`. Use `SELECT ... FOR UPDATE` for family locking. |
| WU-019 | CREATE | `services/api/app/repositories/chapter_transitions.py` | Query/write chapter transition projection rows. | Public surface: `insert_chapter_transition`, `list_chapter_transitions`, optional `fetch_chapter_transition`. All write calls receive active `Connection`. |
| WU-019 | MODIFY/REPLACE | `services/api/app/services/chapters.py` | Replace old `ChapterService` class with mutation-backed lifecycle functions. | Delete `ChapterService`, `_heads`, `_format_etag`, `_record_to_payload`, `_compute_diff`, `_check_precondition`, `_to_read`, in-memory store imports. Add `create_chapter`, `read_chapter`, `transition_chapter`, `patch_chapter_discord_resources`, `_verify_transition`, `_verify_provisioning_complete`, `_chapter_from_row`, `_make_mutation_request`, `_enqueue_failed_provisioning_effect`. Use `mutate_entity()`. |
| WU-018 | MODIFY | `services/api/app/services/chapter_templates.py` | Make template create actor-aware and add PATCH-as-new-version. | Change `_make_request` to accept `ActorIdentity`; change `create_chapter_template(db, request, actor)` to version/family v1; preserve `read_chapter_template`; add `patch_chapter_template(db, template_id, request, actor)`; catch unique-index `IntegrityError` as stale 412. |
| WU-019 | MODIFY/REPLACE | `services/api/app/api/v1/endpoints/chapters.py` | Replace legacy chapter routes with lifecycle routes. | Delete `list_chapters`, `update_chapter`, `archive_chapter`, `ChapterUpdate`, `ChapterService`, `get_chapter_service`, integer `chapter_id`. Add `_parse_if_match`, `_db`, `_set_etag`, typed error mapper. Routes: `POST ""`, `GET "/{chapter_id}"`, `POST "/{chapter_id}/transitions"`, `PATCH "/{chapter_id}/discord-resources"`. Add `RequireAuthority` and `get_current_actor`. |
| WU-018 | CREATE | `services/api/app/api/v1/endpoints/chapter_templates.py` | Template create/read/patch HTTP API. | Public surface: `router`; helpers `_db`, `_map_template_error`. Routes: `POST /api/v1/chapter-templates`, `GET /api/v1/chapter-templates/{template_id}`, `PATCH /api/v1/chapter-templates/{template_id}`. Use `RequireAuthority` and actor dependency. |
| WU-018 | MODIFY | `services/api/app/api/v1/router.py` | Mount chapter template routes. | Import `chapter_templates`; add `router.include_router(chapter_templates.router, tags=["chapter-templates"])`. Keep existing `chapters` include but it now points to replacement lifecycle router. |
| WU-019 | MODIFY | `services/api/app/core/factory.py` | Remove legacy in-memory chapter wiring. | Delete imports of `InMemoryActionStore`, `InMemoryStateChangeStore`, `ChapterRepository`, `InMemoryChapterRepository`, `ChapterService`. Remove `chapter_repository`, `action_store`, `state_change_store` parameters. Remove `app.state.activity_action_store`, `app.state.activity_state_change_store`, `app.state.chapter_service` unless another non-legacy test still requires them. Keep `app.state.db` and scheduler wiring. |
| WU-019 | MODIFY | `services/api/app/core/dependencies.py` | Remove in-memory service dependency. | Delete `ChapterService` import and `get_chapter_service`. Keep `get_current_actor` and `RequireAuthority`. |
| WU-020 | CREATE | `services/discord/app/commands/chapters.py` | Register `provision_chapter` command handler. | Public surface: `PROVISION_CHAPTER_COMMAND`, `register_chapter_commands(bot)`. Calls `bot.register_interaction_handler("provision_chapter", provision_chapter_handler)`. |
| WU-020 | MODIFY | `services/discord/app/commands/__init__.py` | Export chapter registration. | Import/export `register_chapter_commands` if tests import from `app.commands`. Preserve `InteractionRegistry` export. |
| WU-020 | CREATE | `services/discord/app/handlers/chapters.py` | Sequential Discord provisioning workflow. | Public surface: `provision_chapter_handler`, `check_required_bot_permissions`, `derive_resource_names`/slug helper if test needs it. Handler: ack deferred before API calls, GET chapter, transition to `provisioning`, create/reuse category/roles/channels, PATCH resources after each success, transition to `active`, on failure transition to `provisioning_failed`. |
| WU-020 | MODIFY | `services/discord/app/handlers/__init__.py` | Export chapter handler symbols if tests import package-level handlers. | Add `provision_chapter_handler` and permission helper to `__all__` only if needed. |
| WU-020 | MODIFY | `services/discord/app/infrastructure/api_client.py` | Propagate actor and precondition headers. | In `ApiClient.call`, merge `request.headers` with correlation/causation headers. Caller-supplied `X-Correlation-Id` must not override ambient correlation. Actor headers are supplied by WU-020 calls. |
| WU-020 | MODIFY | `services/discord/app/core/bot.py` | Support deferred acknowledgement and command registration context. | `HumilityBot.dispatch_interaction`: expose raw interaction response/defer path to handler through envelope or an ack protocol; do not send a second immediate response if already deferred and follow-up path is used. Existing `register_interaction_handler` remains. |
| WU-020 | MODIFY | `services/discord/app/__main__.py` | Install chapter command registration before sync/start. | `build_bot_with_registry`: create `HumilityBot`, call `register_chapter_commands(bot)`, return bot. Keep `sync_command_tree` behavior. |
| WU-020 | MODIFY | `services/discord/app/contracts/runtime_settings.py` | Document required bot permissions in read contract. | Add `required_bot_permissions: tuple[str, ...] = ("MANAGE_ROLES", "MANAGE_CHANNELS", "VIEW_CHANNEL")` to `DiscordSettingsRead`. No new env var. |
| WU-020 | MODIFY | `services/discord/app/core/settings.py` | Populate runtime settings read model. | `Settings.to_read()` passes the default required permission tuple through `DiscordSettingsRead`. |

## 1. Migrations

| WU | Action | File | Hook points |
|---|---|---|---|
| WU-018 | CREATE | `migrations/versions/wu-018_chapter_templates.py` | `revision = "wu_018_chapter_templates"`, `down_revision = "wu_014_authority_api"`. Use Alembic `op.add_column`, SQL backfill via `gen_random_uuid()`, `op.alter_column`, `op.create_index`. |
| WU-019 | CREATE | `migrations/versions/wu-019_chapter_lifecycle.py` | `revision = "wu_019_chapter_lifecycle"`, `down_revision = "wu_018_chapter_templates"`. Use Postgres JSONB and UUID types. Seed grant using actual `authority_grants` columns: `id`, `grantee_id`, `scope_kind`, `scope_id`, `permissions`, `expires_at`, `revoked_at`, `revoked_by`, `revocation_reason`, `predecessor_grant_id`. |

Migration tests must prove:
- Upgrade creates lineage columns and backfills existing templates as version 1.
- `(template_family_id, version)` uniqueness exists.
- `chapters` and `chapter_transitions` exist with the four-state check only.
- `discord-provisioner` grant is active and global with exactly the permissions needed for WU-020.

## 2. Contracts

| WU | Action | File | Public surface / hook points |
|---|---|---|---|
| WU-019 | MODIFY/REPLACE | `services/api/app/contracts/chapters.py` | Export `ChapterState = Literal["proposed", "provisioning", "active", "provisioning_failed"]`, `ChapterId = str`, `ChapterDiscordResources`, `ChapterCreate`, `ChapterRead`, `ChapterTransitionRequest`, `ChapterResourcesPatchRequest`, `ChapterTransitionRead`, `ChapterNotFoundError`, `InvalidChapterTransitionError`, `IncompleteProvisioningError`. No `ChapterStatus`, `ChapterUpdate`, integer ids, `slug`, or archive shapes. |
| WU-018 | MODIFY | `services/api/app/contracts/chapter_templates.py` | `ChapterTemplateRead` gains `template_family_id: UUID`, `version: int`. `ChapterTemplatePatch` has `expected_current_version` plus optional `name`, `channel_structure`, `role_structure`, `default_permission_intents`; validator rejects empty patch and wrong `schema_version`. Export typed errors. |
| WU-020 | CREATE | `services/discord/app/contracts/chapters.py` | Export daemon-local provisioning result contract used by handler tests. Suggested symbols: `ProvisioningStep`, `ChapterProvisionResult`. |
| WU-020 | MODIFY | `services/discord/app/contracts/interactions.py` | Add only the minimum deferred-ack contract needed by handler/bot. Suggested symbols if used: `InteractionAcknowledger` protocol with `defer(ephemeral: bool = True)`. |
| WU-020 | MODIFY | `services/discord/app/contracts/api_transport.py` | `ApiTransportRequest` adds optional `headers` field. Existing response/error public surface remains unchanged. |

## 3. Repositories

| WU | Action | File | Hook points |
|---|---|---|---|
| WU-019 | MODIFY/REPLACE | `services/api/app/repositories/chapters.py` | Functions: `insert_chapter(connection, row)`, `fetch_chapter(connection, chapter_id)`, `fetch_chapter_for_update(connection, chapter_id)`, `_update_chapter_state(connection, chapter_id, state)`, `_merge_chapter_discord_resources(connection, chapter_id, resources)`. Use `Jsonb`. No classes or protocols. |
| WU-018 | MODIFY | `services/api/app/repositories/chapter_templates.py` | Modify `insert_chapter_template` and `fetch_chapter_template`; create `fetch_chapter_template_for_update`, `fetch_current_template_family_version_for_update`, `insert_template_version`. |
| WU-019 | CREATE | `services/api/app/repositories/chapter_transitions.py` | Public surface: `insert_chapter_transition(connection, row)`, `list_chapter_transitions(connection, chapter_id)`. Projection only; `activity_actions` remains authoritative. |

## 4. Services

| WU | Action | File | Hook points |
|---|---|---|---|
| WU-019 | MODIFY/REPLACE | `services/api/app/services/chapters.py` | Functions: `create_chapter(db, request, actor) -> tuple[ChapterRead, MutationResult]`, `read_chapter(db, chapter_id) -> tuple[ChapterRead, str]`, `transition_chapter(db, chapter_id, request, actor, expected_version) -> tuple[ChapterRead, MutationResult]`, `patch_chapter_discord_resources(db, chapter_id, request, actor, expected_version) -> tuple[ChapterRead, MutationResult]`. Helpers: `_verify_provisioning_complete`, `_build_template_snapshot`, `_chapter_from_row`, `_make_mutation_request`, `_enqueue_failed_provisioning_effect`, `_merge_resources`. |
| WU-018 | MODIFY | `services/api/app/services/chapter_templates.py` | Functions affected: `_make_request`, `create_chapter_template`, `read_chapter_template`. New `patch_chapter_template`. `create_chapter_template` now receives actor and stores `template_family_id = template_id`, `version = 1`. |

Chapter service invariants:
- All writes go through `mutate_entity`.
- `transition_chapter(... to_state="active")` must call `_verify_provisioning_complete` before writing transition or state.
- Failed transition uses repository-level `enqueue_effect(connection, ...)` on the same active connection.
- Payload allowlists are explicit for create, transition, and resource patch.

## 5. Endpoints

| WU | Action | File | Hook points |
|---|---|---|---|
| WU-019 | MODIFY/REPLACE | `services/api/app/api/v1/endpoints/chapters.py` | Route functions: `create_chapter`, `get_chapter`, `transition_chapter_endpoint`, `patch_chapter_discord_resources_endpoint`. Delete legacy route functions `list_chapters`, `update_chapter`, `archive_chapter`. Imports change from `get_chapter_service`/`ChapterService` to `PostgresDatabase`, `get_current_actor`, `RequireAuthority`, lifecycle service functions. |
| WU-018 | CREATE | `services/api/app/api/v1/endpoints/chapter_templates.py` | Route functions: `create_chapter_template_endpoint`, `get_chapter_template`, `patch_chapter_template_endpoint`. Maps stale version to 412, not-found to 404, empty patch to 422 or 400, schema mismatch to existing explicit error behavior. |
| WU-018 | MODIFY | `services/api/app/api/v1/router.py` | Import `chapter_templates`; include router. |

Endpoint policy:
- Template POST/PATCH: `RequireAuthority("chapter_template.write", "global")`
- Template GET: `RequireAuthority("chapter_template.read", "global")`
- Chapter POST/transition/resource patch: `RequireAuthority("chapter.write", "global")`
- Chapter GET: `RequireAuthority("chapter.read", "global")`
- Transition/resource patch require `If-Match`; missing 428, stale 412.

## 6. Factory and Dependencies

| WU | Action | File | Hook points |
|---|---|---|---|
| WU-019 | MODIFY | `services/api/app/core/factory.py` | `create_api_app` signature removes chapter repository and in-memory stores. It only accepts `settings` and optional `db`. App state keeps `settings`, `db`, scheduler. Delete `app.state.chapter_service`, `app.state.activity_action_store`, `app.state.activity_state_change_store` if no non-legacy caller remains. |
| WU-019 | MODIFY | `services/api/app/core/dependencies.py` | Delete `get_chapter_service` and `ChapterService` import. Leave authority dependencies unchanged. |

Tests currently reading `app.state.activity_action_store` or `app.state.activity_state_change_store` must be rewritten to query Postgres `activity_actions` / `activity_state_changes`, or deleted if they only prove the legacy chapter proof-of-concept.

## 7. Discord Service

| WU | Action | File | Hook points |
|---|---|---|---|
| WU-020 | CREATE | `services/discord/app/commands/chapters.py` | `register_chapter_commands(bot)` registers `provision_chapter`. No Discord-visible mutation happens at registration. |
| WU-020 | MODIFY | `services/discord/app/commands/__init__.py` | Re-export registration only if needed by startup/tests. |
| WU-020 | CREATE | `services/discord/app/handlers/chapters.py` | Handler owns ack, permission preflight, API sequencing, Discord resource creation/reuse, resource PATCH, success/failure transitions. Do not create raw `httpx` clients. |
| WU-020 | MODIFY | `services/discord/app/handlers/__init__.py` | Optional export hook. |
| WU-020 | MODIFY | `services/discord/app/infrastructure/api_client.py` | Merge request headers into outbound call. This is the actual existing path; do not create `services/discord/app/api_client.py` as a shim. |
| WU-020 | MODIFY | `services/discord/app/core/bot.py` | Support deferred ack/follow-up contract without breaking existing registry dispatch tests. |
| WU-020 | MODIFY | `services/discord/app/__main__.py` | `build_bot_with_registry` installs chapter commands before `sync_command_tree`. |
| WU-020 | MODIFY | `services/discord/app/contracts/runtime_settings.py` | Add required permissions tuple to read model. |
| WU-020 | MODIFY | `services/discord/app/core/settings.py` | Include required permissions in `Settings.to_read()`. |

Discord handler API call order:
1. Ack deferred.
2. `GET /api/v1/chapters/{chapter_id}` with `X-Actor-Kind: service`, `X-Actor-Id: discord-provisioner`.
3. `POST /api/v1/chapters/{chapter_id}/transitions` to `provisioning` with `If-Match`.
4. For each discovered/created category/role/channel: `PATCH /api/v1/chapters/{chapter_id}/discord-resources` with latest ETag.
5. On complete resources: transition to `active`.
6. On failure: persist known resources if API reachable, then transition to `provisioning_failed`; API enqueues the deferred effect.

## 8. Tests

| WU | Action | File | Purpose / hook points |
|---|---|---|---|
| WU-019 | DELETE | `services/api/tests/test_chapters.py` | Legacy integer-id, direct PATCH, list, archive, and in-memory ETag tests. Replace coverage in `test_chapter_lifecycle.py`. |
| WU-019 | DELETE | `services/api/tests/test_contracts_chapters.py` | Legacy `ChapterStatus`, slug, update contract tests. Replace coverage in `test_contracts_chapter_lifecycle.py`. |
| WU-018 | CREATE | `services/api/tests/test_chapter_templates.py` | Endpoint/service tests for POST, GET, PATCH new-version behavior, stale 412, concurrent PATCH race, authority guard. |
| WU-019 | CREATE | `services/api/tests/test_chapter_lifecycle.py` | Chapter create/read, transitions, resource patch merge, active completeness, optimistic locking, failed transition deferred effect, seeded service-actor grants. |
| WU-019 | CREATE | `services/api/tests/test_contracts_chapter_lifecycle.py` | Contract tests for `ChapterState`, UUID-string `ChapterId`, `ChapterCreate`, `ChapterRead`, `ChapterTransitionRequest`, `ChapterResourcesPatchRequest`, `ChapterDiscordResources`. |
| WU-018/WU-019 | CREATE | `services/api/tests/test_chapter_migrations.py` | Migration assertions for WU-018 lineage columns/indexes and WU-019 chapter tables/grant seed. |
| WU-020 | CREATE | `services/discord/tests/test_chapter_provisioning.py` | Handler success, deferred ack before API calls, permission preflight, name rediscovery after failed PATCH, partial failure, actor/originating-user headers/body. |
| WU-018 | MODIFY | `services/api/tests/test_chapter_template_foundation.py` | Add `version` and `template_family_id` to `ChapterTemplateRead` fixtures and DB assertions; keep no-in-place-update assertion but allow `patch_chapter_template` as create-new-version surface. |
| WU-019 | MODIFY | `services/api/tests/conftest.py` | Add `chapters` and `chapter_transitions` to `GOVERNANCE_TABLES` reset list after migrations create them. |
| WU-019 | MODIFY | `services/api/tests/test_endpoints_chapters_stubs.py` | Replace expected routes with lifecycle routes; remove `GET /api/v1/chapters`, `PATCH /api/v1/chapters/{chapter_id}`, `/archive`; add transitions and discord-resources paths. |
| WU-019 | MODIFY | `services/api/tests/test_conftest.py` | Replace reachability checks for legacy chapter routes with new guarded lifecycle route expectations or remove chapter-specific reachability from generic fixture tests. |
| WU-019 | MODIFY | `services/api/tests/test_activity_model.py` | Remove or rewrite the old "chapters-as-first-aggregate" proof-of-concept section that depends on in-memory stores, direct update, archive, slug, and integer ids. New assertions should query persisted mutation tables if retained. |
| WU-019 | MODIFY | `services/api/tests/test_authority_enforcement.py` | Rename test-only route/permission away from `/archive` and `chapter.archive` if final grep invariant uses broad `/archive`/`chapter.archive` zero-count. Use `chapter.write` on a neutral test route. |
| WU-019 | MODIFY | `services/api/tests/test_authority_override_audit.py` | Same neutral-route rename as authority enforcement tests. |
| WU-020 | MODIFY | `services/discord/tests/test_api_transport.py` | Add coverage that request headers are sent with correlation headers and cannot override correlation. |
| WU-020 | MODIFY | `services/discord/tests/test_api_context.py` | Add end-to-end assertion for service actor headers where `ApiTransportRequest.headers` includes `X-Actor-Kind`/`X-Actor-Id`. |
| WU-020 | MODIFY | `services/discord/tests/test_interaction_framework.py` | Adjust dispatch tests for deferred ack/follow-up behavior while preserving registry audit context. |
| WU-020 | MODIFY | `services/discord/tests/test_bot.py` | Add bot-level test for deferred response seam if implemented in `HumilityBot`. |
| WU-020 | MODIFY | `services/discord/tests/test_main.py` | Assert `build_bot_with_registry` registers chapter command handlers before sync. |
| WU-020 | MODIFY | `services/discord/tests/test_settings.py` | Assert `DiscordSettingsRead.required_bot_permissions` default and no new env var. |
| WU-020 | MODIFY | `services/discord/tests/conftest.py` | Extend mock interaction/guild/Discord objects for deferred ack, permission bits, categories, roles, channels, and creation calls. |

## 9. Legacy Deletions

These are not standalone file deletions except for the two legacy test files above. They are required removals inside replacement files:

| WU | Location | Delete |
|---|---|---|
| WU-019 | `services/api/app/contracts/chapters.py` | `ChapterStatus`, `ChapterUpdate`, integer `id`, `slug`, `discord_category_id`, `discord_officer_role_id`, `discord_member_role_id`, archived status. |
| WU-019 | `services/api/app/repositories/chapters.py` | `ChapterRepository`, `InMemoryChapterRepository`, `ChapterRecord`, in-memory dict, `_next_id`, `archive`. |
| WU-019 | `services/api/app/services/chapters.py` | `ChapterService`, in-memory stores, `_heads`, `list_chapters`, `update_chapter`, `archive_chapter`, direct action/state-store append logic. |
| WU-019 | `services/api/app/api/v1/endpoints/chapters.py` | `GET /api/v1/chapters`, `PATCH /api/v1/chapters/{chapter_id}`, `POST /api/v1/chapters/{chapter_id}/archive`, integer path params. |
| WU-019 | `services/api/app/core/factory.py` | `chapter_repository`, `action_store`, `state_change_store`, `app.state.chapter_service`, legacy activity stores if only used by chapter proof tests. |
| WU-019 | `services/api/app/core/dependencies.py` | `get_chapter_service`. |

Rationale: revision 3 requires atomic replacement. Keeping the legacy substrate would create duplicate route semantics, incompatible id types, duplicate chapter state owners, and mixed `aggregate_type="chapter"` id forms.

## 10. Final Grep Invariants

After implementation, these commands must return zero matches:

```bash
rg -n "InMemoryChapterRepository|class ChapterRecord|ChapterStatus|ChapterUpdate" services/api
rg -n "class ChapterService|get_chapter_service|app\\.state\\.chapter_service" services/api
rg -n "archive_chapter|/archive|chapter\\.archive" services/api
rg -n "chapter_id: int|dict\\[int, ChapterRecord\\]|discord_category_id|discord_officer_role_id|discord_member_role_id" services/api
test ! -e services/discord/app/api_client.py
```

Allowed nonzero legacy-adjacent strings:
- `slug` in root-level historical daemon tests and config code outside `services/api` is unrelated to the SLICE-013 API chapter contract.
- `InMemoryActionStore` and `InMemoryStateChangeStore` may remain in the activity substrate if still used outside the legacy chapter service. They must not be imported by `services/api/app/services/chapters.py` or wired for chapter service state in `factory.py`.

## 11. Implementation Order

1. WU-018 tests/contracts/migration/repository/service/endpoint/router.
2. WU-019 tests/contracts/migration/repositories/service/endpoint/factory/dependencies, deleting legacy tests and legacy code in the same commit slice.
3. WU-020 Discord contracts/api transport/handler/command/startup/settings/tests.
4. Run grep invariants, then targeted API and Discord test suites.
