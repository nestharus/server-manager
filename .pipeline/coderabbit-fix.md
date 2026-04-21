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

## Justification Fix Pass

- Deleted unused `list_chapter_transitions` from `services/api/app/repositories/chapter_transitions.py` and removed its now-unused `dict_row` import.
- Deleted unused `ChapterProvisionResult` and `ProvisioningStep` from `services/discord/app/contracts/chapters.py`.
- Kept live `ChapterProvisioningError` and simplified its `step` argument to `str`; removed the obsolete handler type ignore.

## Justification Grep Invariants

- `grep -r list_chapter_transitions services/api`: 0 hits.
- `grep -r ChapterProvisionResult services/discord`: 0 hits.
- `grep -r ProvisioningStep services/discord`: 0 hits.

## Justification Verification

- `cd services/api && uv run pytest tests/ -q`: 335 passed, 1 warning.
- `cd services/discord && uv run pytest tests/ -q`: 56 passed, 20 warnings.

# SLICE-007 CodeRabbit + Justification Fix Pass

## Fixes Applied

- Added a migration comment documenting that `wu_014_authority_api` adds `revoked_by` and `revocation_reason` before `wu_012_trust` through the `wu_033_roster -> wu_011_members` chain.
- Guarded Discord onboarding member API responses before reading `member["id"]`; malformed lookup/create responses now raise `MemberOnboardingError` with the correct step.
- Guarded Discord onboarding trust API responses so a missing `tier` raises `MemberOnboardingError` instead of silently deriving `intake_required=False`.
- Treated missing trust policy `weights` as `InvalidTrustPolicyError("weights missing")`.
- Suppressed the exception chain when re-raising the original concurrent trust compute error after recovery re-read fails.
- Removed unsupported trust policy mapping branches for tier thresholds and account-age weighting.
- Deleted the unused `_trust_create_payload` test helper and updated call sites.
- Corrected `.pipeline/synthesis.md` D7 so `POST /members` no longer claims to carry `initial_signals`.

## Tests Added

- `test_handle_member_join_raises_on_malformed_api_response`
- `test_handle_member_join_raises_on_malformed_trust_api_response`
- `test_compute_trust_returns_409_when_policy_weights_missing`

## Verification

- `cd services/api && uv run pytest tests/ -q`: 376 passed, 1 warning.
- `cd services/discord && uv run pytest tests/ -q`: 65 passed, 20 warnings.

# SLICE-015 CodeRabbit + Justification Fix Pass

## Fixes Applied

- Made the `notification-dispatcher` authority seed and downgrade predicates require exact permission equality with both `@>` and `<@`, so supersets no longer mask or remove grants.
- Added `HAVING COUNT(*) > 0` to the notification envelope degraded-summary CTE so healthy notifications no longer creates a synthetic subsystem row.
- Changed notification event inserts to use the DB-owned `created_at` and return it from `INSERT ... RETURNING`; changed the migration default to `clock_timestamp()` so same-transaction event order remains stable.
- Changed notification rule patch state-change payloads to use post-update `updated_at` and the new version, and aligned the action type to `notification_rule.patch`.
- Cached the constructed notifications delivery port in `get_delivery_port()`.
- Made malformed DM recipient IDs and designated-channel IDs definitive Discord delivery failures.
- Added `NotificationRuleCreate` scope consistency validation for global/chapter/member rules.
- Reused `_claim.claim_due_rows(..., claim_status=None)` for envelope claiming.
- Replaced the envelope materialization `max_attempts` literal with `DEFAULT_MAX_ATTEMPTS`.
- Made `stuck_in_flight_envelopes` optional on degraded summaries and only populated it for the notifications subsystem.
- Updated D9 synthesis wording to the shipped `notifications_materialize` / `notifications_deliver` effect names and payloads.
- Replaced absolute verification commands in `.pipeline/implementation.md` with repo-relative commands.

## Tests Added

- Patch audit assertions for `notification_rule.patch`, state-change version `2`, and post-update `updated_at`.
- Scope mismatch create rejection cases for `global + scope_id`, `chapter + NULL scope_id`, and `member + NULL scope_id`.
- Discord adapter malformed recipient and destination ID definitive-failure cases.

## Skipped Low Item

- Left the `emit(..., actor=...)` parameter in place because the Rev-2 contract and existing call sites require that signature; wiring it through would require a contract/proposal change rather than a local cleanup.

## Verification

- `cd services/api && uv run pytest tests/ -q`: 404 passed, 1 warning.
- `cd services/discord && uv run pytest tests/ -q`: 68 passed, 20 warnings.

Warnings were pre-existing test-environment warnings:

- API: one Pydantic deprecation warning in `tests/test_settings.py`.
- Discord: discord.py deprecation warnings in existing bot/command tests.
