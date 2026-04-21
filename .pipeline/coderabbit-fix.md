# SLICE-013 CodeRabbit Fix Pass

## Fixes Applied

- Guarded `/provision` so a chapter already in `provisioning` returns an "already being provisioned" `InteractionResult` and does not create Discord categories, roles, or channels.
- Scoped channel rediscovery to channels whose `category` matches the provisioned category, preventing same-name channels elsewhere in the guild from being bound.
- Added Discord regression tests:
  - `test_provision_rejects_when_chapter_already_provisioning`
  - `test_rediscovers_channel_only_within_category`
- Changed WU-018 template backfill to set `template_family_id = id` for existing rows.
- Changed chapter and chapter-template API endpoints to inject `PostgresDatabase` via `Depends(get_db)`.
- Changed chapter endpoint path parameters to `UUID` and passed `str(chapter_id)` into the existing service layer.
- Changed template patch schema inheritance to default omitted `schema_version` to `CURRENT_TEMPLATE_SCHEMA_VERSION`.
- Made the WU-019 `discord-provisioner` authority grant insert idempotent with a `WHERE NOT EXISTS` guard.

## Skipped Nitpicks

- Did not convert `@pytest.fixture()` spellings.
- Did not sort `__all__` lists.
- Did not remove redundant wrapper tests.
- Did not add the optional contracts `channel_ids` assertion.
- Did not type `chapter_transition_id` as `UUID`.
- Did not rename `merge_chapter_discord_resources`.

## Verification

- `cd services/api && uv run pytest tests/ -q`: 335 passed, 1 warning.
- `cd services/discord && uv run pytest tests/ -q`: 56 passed, 20 warnings.
