# INIT-134 hookpoints

## Summary

INIT-134 should extend the existing `application.public_submitted` notification path rather than create a new event, delivery worker, public endpoint, or Discord-side submit path.

The current code already has the core handoff: `submit_public_application_with_receipt` resolves the receipt Discord user, commits the application through `_submit_application_internal`, then calls `emit_application_public_submitted_event` before returning the receipt application id. The implementation hookpoint is therefore the post-commit emit site at `services/api/app/services/applications.py:839-885`, especially lines 870-884.

The main work is additive:

- Enrich the public-submit notification payload with safe Level A fields.
- Tighten the payload allowlist by removing `applicant_member_id` and duplicate `discord_user_id`.
- Materialize two seeded rules from the same event: officer designated-channel embed and applicant DM receipt.
- Store optional `rendered_embed_json` on notification envelopes.
- Teach the Discord notification handler to send an embed while preserving nonce idempotency.
- Wire required `web_public_base_url` and optional global fallback config through local settings/fixtures.

Current Alembic head is `wu_044_application_messages` in `migrations/versions/wu-044_application_messages.py`; INIT-134 migration should be `wu-045_application_public_submit_notifications.py`.

## Reuse (call directly)

### Backend

- Public submit endpoint and receipt auth: `services/api/app/api/v1/endpoints/applications/public.py:25-47`. Do not change route, response model, status, `verify_applicant_receipt`, or `authorize_public_intake`.
- Public submit service hookpoint: `services/api/app/services/applications.py:839-885`. Keep emission after `_submit_application_internal` returns and before `return created.read.id`.
- Existing notification event insertion and materialization enqueue: `services/api/app/services/notification_events.py:32-84`. Reuse `notification_events.emit`; it already persists `notification_events` and queues `notifications_materialize`.
- SLA notification emit pattern: `services/api/app/services/ticket_sla.py:242-258` and `services/api/app/services/ticket_sla.py:292-304`. It demonstrates service-layer event construction, scope propagation, connection threading, actor threading, and payload allowlisting.
- Materialization substrate in `services/api/app/services/notifications_materialize.py`: rule matching at lines 60-68, template context at 136-148, text rendering at 151-158, destination/recipient resolution at 77-133, envelope insertion and delivery enqueue at 195-254.
- Notification rules and envelopes repository in `services/api/app/repositories/notifications.py`: select list at 14-63 and insert/return path at 210-279. Add embed columns to this path; do not create a second repository.
- Notification event repository in `services/api/app/repositories/notification_events.py`: event insert, fetch, and replay are already enough for the event row. No new event table is needed.
- Envelope idempotency from `migrations/versions/wu-029a_notifications.py`: `uq_notification_envelopes__per_event` already dedupes per `(source_event_id, rule_id, recipient_key)`.
- Chapter Discord resource shape: `services/api/app/contracts/chapters.py:39-43`. Use `discord_resources.role_ids["application_managers"]` and `discord_resources.channel_ids["applications_review"]`; do not add duplicate chapter fields.

### Discord daemon

- Delivery handler: `services/discord/app/handlers/notifications.py:15-95`.
- Reuse `envelope_nonce(envelope.id)` and `target.send(..., nonce=nonce, enforce_nonce=True)`.
- Reuse existing `dm` and `designated_channel` routing branches. Only extend `_send_message` and the delivery call sites to pass `embed=` when `envelope.rendered_embed_json` is present.
- Preserve definitive vs transient failure behavior: malformed recipient/destination/template embed is definitive; Discord API/runtime failures remain non-definitive.

### Test fixtures

- API public-intake helpers already fetch `application.public_submitted` events and materialize effects in `services/api/tests/public_intake_fixtures.py:279-304`.
- Existing public submit tests in `services/api/tests/test_public_intake_submit.py:120-170` already assert the event exists and targets `recipient_discord_user_id`.
- Existing materialization tests in `services/api/tests/test_notification_materialization.py` already provide direct rule/event insertion helpers.
- Existing Discord notification tests in `services/discord/tests/test_notifications.py` already cover deterministic nonce, DM routing, designated-channel routing, and malformed id failures.
- E2e browser flow already writes submit records with `application_id`, `correlation_id`, and `applicant_discord_user_id` in `infra/tests/e2e/lib/playwright/browser-flow.mjs:112-127`.
- E2e shell already queries local Postgres after public submit in `infra/tests/e2e/tests/19-web-ui.sh:8-39`.

### Config

- Required settings use `Field(...)` in `services/api/app/core/settings.py:21-26`. Add `web_public_base_url: str = Field(...)` with no Python default.
- Global fallback settings should be optional: `global_applications_review_channel_id: str | None = None`, `global_application_managers_role_id: str | None = None`, and `global_primary_guild_channel_url: str | None = None`. Missing global fallback config means skipped notification envelope, not API startup failure.
- Local fixture seed pattern lives in `gitops/channels/local/applications/server-manager/e2e-fixtures-infisicalsecret.yaml:28-32`. Add test-only channel, role, and primary guild URL values there.
- API env injection pattern lives in `gitops/channels/local/applications/server-manager/api-deployment.yaml:44-107`. Wire `WEB_PUBLIC_BASE_URL` and optional global fallback env vars there.

## New (write fresh)

### Backend

- `services/api/app/services/application_public_submit_notifications.py`
  - Build the final safe payload from `ApplicationRead`, receipt Discord user id, settings, and chapter/global Discord routing config.
  - Compute `application_url = web_public_base_url.rstrip("/") + "/applications/{application_id}"`.
  - Compute `scope_label`, `submitted_unix_ts`, `submitted_iso`, `form_version`, `character_name`, and 200-character newline-collapsed `response_preview`.
  - Resolve chapter routing from existing `discord_resources` keys: `channel_ids.applications_review` and `role_ids.application_managers`.
  - Resolve global routing from optional settings.
  - Produce role mention as `<@&{application_managers_role_id}>`.
  - Keep `recipient_discord_user_id` as the only applicant Discord recipient id.
  - Do not include full `responses`, applicant UUIDs, member UUIDs, usernames, emails, or synthetic/public identifiers.

- Notification template contract models in `services/api/app/contracts/notifications.py`
  - `NotificationTemplate`
  - `NotificationTemplateEmbed`
  - `NotificationTemplateEmbedField`
  - `DiscordEmbedRead`
  - `DiscordEmbedFieldRead`
  - `NotificationEnvelopeRead.rendered_embed_json: DiscordEmbedRead | None`

- Migration `migrations/versions/wu-045_application_public_submit_notifications.py`
  - `down_revision = "wu_044_application_messages"`.
  - Add nullable `rendered_embed_json JSONB` to `notification_envelopes`.
  - Seed deterministic notification rules for `application.public_submitted`:
    - `application_public_submitted_officer_review`, `channel="designated_channel"`, `grouping="per_event"`, embed template, body role mention.
    - `application_public_submitted_applicant_dm`, `channel="dm"`, `grouping="per_event"`, text receipt template.
  - No chapter config columns under the current proposal; chapter routing reuses `chapters.discord_resources`.

### Discord daemon

- Embed conversion helper in `services/discord/app/handlers/notifications.py`
  - Accept `rendered_embed_json` from the envelope command.
  - Construct a Discord embed object using the daemon's existing Discord library import conventions.
  - Validate types before send; malformed embed data is a definitive `NotificationDeliveryError`.
  - Pass `embed=None` for text-only DMs so existing behavior remains unchanged.

### Tests

- API component tests beside `services/api/tests/test_public_intake_submit.py` or in `services/api/tests/test_application_public_submit_notifications.py`.
- Materialization tests in `services/api/tests/test_notification_materialization.py`.
- Discord daemon embed tests in `services/discord/tests/test_notifications.py` or `services/discord/tests/test_notification_embeds.py`.
- Settings tests in `services/api/tests/test_settings.py` for required `WEB_PUBLIC_BASE_URL` and optional `GLOBAL_*` fallbacks.
- Live-guild fixture guard test that fails if local/e2e fixture ids equal live Humility guild id `900000000000000001` or known production channel/role ids.
- E2e assertions in `infra/tests/e2e/tests/19-web-ui.sh` after `assert_public_submit_persisted`.

## Modify in place (additive only)

- `services/api/app/services/applications.py`
  - Keep the emit call after `_submit_application_internal`.
  - Wrap notification emission in `try/except Exception`, log with `logger.exception`, and do not re-raise.
  - Fold audit finding F-1: use a service actor such as `ActorIdentity(actor_kind="service", actor_id="notifications")` for notification emission rather than threading the applicant user actor into the notification substrate.

- `services/api/app/services/notifications.py`
  - Replace `APPLICATION_PUBLIC_SUBMITTED_PAYLOAD_ALLOWLIST`; do not widen it.
  - Remove `applicant_member_id` and `discord_user_id`.
  - Keep only safe rendered fields: `application_id`, `support_id`, `recipient_discord_user_id`, `scope_kind`, `scope_id`, `scope_label`, `submitted_unix_ts`, `submitted_iso`, `form_version`, `character_name`, `response_preview`, `application_url`, `officer_review_channel_id`, `application_managers_role_id`, `application_managers_role_mention`, and `primary_guild_channel_url`.
  - Delegate public-submit payload building to the new builder instead of growing inline logic here.

- `services/api/app/services/notifications_materialize.py`
  - Add event-payload recipient selector support for applicant DM: recipient id comes from `payload_recipient_discord_user_id`.
  - Add event-payload destination selector support for officer notification: destination channel id comes from `payload_officer_review_channel_id`.
  - Render `template_json["embed"]` if present.
  - Apply `Template(...).substitute(context)` only to string embed fields: `title`, `description`, `url`, `fields[].name`, and `fields[].value`.
  - Pass through non-string values unchanged: `color` stays int/null; `fields[].inline` stays bool.
  - Store `rendered_embed_json` through the existing envelope insert path.
  - Fold audit finding F-2b by making missing `primary_guild_channel_url` an explicit applicant-DM skip reason instead of an accidental template-missing-key failure.

- `services/api/app/repositories/notifications.py`
  - Select, insert, and return `rendered_embed_json` beside `rendered_title` and `rendered_body`.
  - Preserve existing claim, status, idempotency, and delivery effect behavior.

- `services/api/app/contracts/notifications.py`
  - Add typed template/embed models and optional envelope embed field.
  - Keep `NotificationDeliveryCommand` as the wrapper around `NotificationEnvelopeRead`.
  - Keep `NotificationRuleCreate.template_json` persisted as JSONB; the model validates shape, not a second template store.

- `services/discord/app/handlers/notifications.py`
  - Extend `_send_message` signature to include `embed: Any | None = None`.
  - Pass `embed=embed` into `target.send` while preserving `content`, `nonce`, and `enforce_nonce=True`.
  - Keep DM and designated-channel branches as the only in-scope routes.

- `services/api/app/core/settings.py`
  - Add required `web_public_base_url: str = Field(...)`.
  - Fold audit finding F-2: add `global_applications_review_channel_id`, `global_application_managers_role_id`, and `global_primary_guild_channel_url` as optional `str | None = None`, not `Field(...)`.

- `gitops/channels/local/applications/server-manager/e2e-fixtures-infisicalsecret.yaml`
  - Add test-only `applications-review-channel-id`, `application-managers-role-id`, and `primary-guild-channel-url`.

- `gitops/channels/local/applications/server-manager/api-deployment.yaml`
  - Inject `WEB_PUBLIC_BASE_URL` and optional global fallback values into the API pod.

- `infra/tests/e2e/tests/19-web-ui.sh`
  - After public submit, query local Postgres for the notification event and materialized envelopes/effects.
  - Assert one officer `designated_channel` envelope with non-null `rendered_embed_json`.
  - Assert one applicant `dm` envelope with fixture applicant Discord id.
  - Do not assert against or send to the live Humility guild.

## Anti-scope (do not touch)

- No second public-submit event type.
- No direct Discord sends from `services/api/app/services/applications.py`.
- No live Humility Discord messages, channel edits, role edits, deployment/runbook execution, or production rollout.
- No chapter config columns or sibling table duplicating `chapters.discord_resources` under the current proposal.
- No new public submit endpoint, request body, response model, status code, auth path, Pomerium route, or Authentik path.
- No Discord-side `/api/v1/applications` submit flow changes.
- No private Discord thread per application.
- No Discord buttons, claim controls, assignment controls, or state-transition notification side effects.
- No chapter Discord config UI.
- No notification preferences, opt-out, escalation, digesting, or per-officer routing.
- No feature flags, compatibility shims, deprecated aliases, re-exports, dual support, TODO stubs, or placeholder paths.

## Dependency ordering

1. Migration first (chapter Discord config columns or sibling table).
   - Current proposal resolves this as no chapter config migration: use existing `chapters.discord_resources`; migration should add `notification_envelopes.rendered_embed_json` and seed the two rules.
2. Settings field for `web_public_base_url`.
   - Add required `web_public_base_url` and optional global fallback settings before the payload builder depends on them.
3. Notification template (rendered in materializer).
   - Add typed template/embed contracts, seeded rule templates, embed rendering, and event-payload recipient/destination selectors.
4. Discord daemon embed support.
   - Add embed construction and `target.send(content=..., embed=..., nonce=..., enforce_nonce=True)` support.
5. Submit-side emit hookpoint.
   - Replace the current thin emit helper with the enriched payload builder and defensive post-commit isolation.
6. E2e fixtures (test guild, channel, role).
   - Wire local fixture values and add Postgres assertions; keep local Discord dry-run/mock/test-guild only.

## Implementer notes

- This is code/test/fixture work only. It must not perform a Discord-visible action. Live production delivery remains Tier 3 and needs separate explicit approval.
- Keep the event count to one `application.public_submitted` event per successful receipt-backed submit. The two Discord outcomes come from two notification rules and two envelopes, not from two event types.
- Use `grouping="per_event"` for both seeded rules so existing envelope uniqueness prevents duplicate materialized envelopes on replay.
- Treat notification emission as best-effort after commit. A failed emit must not turn an accepted public submit into a public 5xx.
- Use the system notification actor for the notification side effect. The application submit/route audit actions still use the applicant member actor.
- `web_public_base_url` is required because bad/missing application links should fail configuration loudly. The `GLOBAL_*` fallback settings are optional because global notification routing is allowed to skip when not configured.
- Missing chapter route keys should skip materialization for that route with an explicit reason, not fall back to live/global Discord resources.
- The applicant DM requires both `recipient_discord_user_id` and `primary_guild_channel_url`; missing either should produce a skipped envelope and no delivery effect.
- The officer notification requires `officer_review_channel_id` and `application_managers_role_id`; missing either should produce a skipped envelope and no delivery effect.
- Fixture values for channel/role/guild URL must be test-only and guarded against live Humility id `900000000000000001`.
- Do not stringify embed `color` or `fields[].inline`. Tests should prove typed pass-through.
- The e2e can assert database rows and queued effects. It should not require a real Discord message in the live guild.

## Open questions for the orchestrator

- None blocking. The only implementation choice from the final audit finding is resolved here as explicit skip handling for missing `primary_guild_channel_url`, rather than softening the applicant DM contract.
