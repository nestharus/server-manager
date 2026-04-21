# SLICE-013 Phase 6 Implementation

## Summary

Implemented all three work units in one replacement slice:

- WU-018: versioned chapter template management API.
- WU-019: persisted chapter lifecycle API with transition projection and failed-provisioning deferred effect enqueue.
- WU-020: Discord provisioning command/handler with service-actor API calls, deferred acknowledgement, deterministic resource names, and name-based rediscovery.

## Files Touched

### CREATE

- `migrations/versions/wu-018_chapter_templates.py`
- `migrations/versions/wu-019_chapter_lifecycle.py`
- `services/api/app/api/v1/endpoints/chapter_templates.py`
- `services/api/app/repositories/chapter_transitions.py`
- `services/api/tests/test_chapter_lifecycle.py`
- `services/api/tests/test_chapter_templates.py`
- `services/api/tests/test_contracts_chapter_lifecycle.py`
- `services/discord/app/commands/chapters.py`
- `services/discord/app/contracts/chapters.py`
- `services/discord/app/handlers/chapters.py`
- `services/discord/tests/test_chapter_provisioning.py`
- `.pipeline/implementation.md`

### MODIFY

- `services/api/app/api/v1/endpoints/chapters.py`
- `services/api/app/api/v1/router.py`
- `services/api/app/contracts/chapter_templates.py`
- `services/api/app/contracts/chapters.py`
- `services/api/app/core/dependencies.py`
- `services/api/app/core/factory.py`
- `services/api/app/repositories/chapter_templates.py`
- `services/api/app/repositories/chapters.py`
- `services/api/app/services/chapter_templates.py`
- `services/api/app/services/chapters.py`
- `services/api/tests/conftest.py`
- `services/api/tests/test_activity_model.py`
- `services/api/tests/test_authority_enforcement.py`
- `services/api/tests/test_authority_override_audit.py`
- `services/api/tests/test_chapter_template_foundation.py`
- `services/api/tests/test_conftest.py`
- `services/api/tests/test_endpoints_chapters_stubs.py`
- `services/discord/app/__main__.py`
- `services/discord/app/commands/__init__.py`
- `services/discord/app/contracts/api_transport.py`
- `services/discord/app/contracts/interactions.py`
- `services/discord/app/contracts/runtime_settings.py`
- `services/discord/app/core/bot.py`
- `services/discord/app/core/settings.py`
- `services/discord/app/handlers/__init__.py`
- `services/discord/app/infrastructure/api_client.py`
- `services/discord/tests/test_api_transport.py`
- `services/discord/tests/test_main.py`
- `services/discord/tests/test_settings.py`

### DELETE

- `services/api/tests/test_chapters.py`
- `services/api/tests/test_contracts_chapters.py`

## Test Results

- `cd services/api && uv run pytest tests/ -q`
  - `335 passed, 1 warning`
- `cd services/discord && uv run pytest tests/ -q`
  - `54 passed, 20 warnings`

## Grep Invariants

All required legacy replacement invariants are zero-count:

```text
legacy_types=0
legacy_service=0
archive=0
integer_contracts=0
discord_api_client_file=0
```

Commands verified:

```bash
rg -n "InMemoryChapterRepository|class ChapterRecord|ChapterStatus|ChapterUpdate" services/api
rg -n "class ChapterService|get_chapter_service|app\\.state\\.chapter_service" services/api
rg -n "archive_chapter|/archive|chapter\\.archive" services/api
rg -n "chapter_id: int|dict\\[int, ChapterRecord\\]|discord_category_id|discord_officer_role_id|discord_member_role_id" services/api
test ! -e services/discord/app/api_client.py
```

## Deviations

No intentional deviations from the final proposal or hookpoints.

Implementation notes:

- The Discord boot-time permission check remains handler-level, which the proposal allowed; no new env var was added.
- The Discord failure path attempts the `provisioning_failed` transition when an ETag is available and suppresses secondary failure-transition errors so the interaction can still return a failure result.
