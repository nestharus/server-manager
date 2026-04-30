# Proposal 16 - INIT-134 / BL-009 + BL-020: Discord notifications on public submit

## 1. Goal

INIT-134 ships the public-submit Discord notification slice for BL-009 and BL-020: after a receipt-backed `POST /api/v1/public/applications` succeeds, the system emits one existing-substrate `application.public_submitted` notification event that materializes an officer-facing Discord embed in the configured applications-review channel and an applicant-facing Discord DM receipt, both linking to existing product or guild destinations. This closes the public-submit visibility gap called out in BL-009 while bundling BL-020 because the applicant DM uses the same submit-success hookpoint, notification substrate, Discord delivery worker, and receipt Discord identity (`plans/BACKLOG.md:260-306`, `plans/BACKLOG.md:414-426`, `research/26-bl-009-problem-map.md:142-164`).

## 2. Locked Decisions Q1..Q8

### Q1. Chapter channel/role mapping: existing `ChapterDiscordResources`

Lock the mapping in the existing chapter `discord_resources` JSONB shape, using `channel_ids["applications_review"]` and `role_ids["application_managers"]`. The problem map expected new fields or a sibling table (`research/26-bl-009-problem-map.md:71-90`), but required reading shows the chapter contract already has first-class Discord resource maps (`services/api/app/contracts/chapters.py:39-43`), the table already stores `discord_resources` as JSONB (`migrations/versions/wu-019_chapter_lifecycle.py:33-39`), and the service already merges map updates rather than replacing unrelated resources (`services/api/app/services/chapters.py:282-292`). Adding parallel columns would violate the existing resource model and create two sources of truth.

### Q2. Global scope fallback: local configured global route

Global applications use a single configured fallback route, not fan-out to every chapter. The current public form is global (`gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:39-45`), and the problem map rejected fan-out as noisy (`research/26-bl-009-problem-map.md:92-106`). The implementation adds API settings for `global_applications_review_channel_id`, `global_application_managers_role_id`, and `global_primary_guild_channel_url`; missing officer channel or role skips officer materialization with an explicit `destination_missing`/`recipient_unresolved` reason, while missing applicant guild URL skips the applicant DM. Local e2e gets non-live fixture values from `server-manager-e2e-fixtures`, whose existing pattern already carries fixture Discord IDs (`gitops/channels/local/applications/server-manager/e2e-fixtures-infisicalsecret.yaml:28-32`).

### Q3. Embed format: Discord embed, role mention in content

Officer delivery is a Discord embed, not raw markdown. The message `content` is exactly `<@&{application_managers_role_id}>`; the embed title is `New application submission - {scope_label}`, the title URL is `{web_base_url}/applications/{application_id}`, and fields include Application ID, Scope, Submitted, Form version, Support ID, and Character. The description is the Level A preview. This follows the user-confirmed format and PII boundary (`plans/BACKLOG.md:273-296`, `research/26-bl-009-problem-map.md:108-125`). The existing web detail route is `/applications/$applicationId` (`services/web/src/app/router.tsx:85-92`) and the API bridge already exposes officer detail at `/officer/applications/{application_id}` (`services/api/app/api/v1/endpoints/web.py:205-218`).

### Q4. Truncation rules: Level A preview only

The preview source is `responses["application_text"]` when present, otherwise the first non-empty string response by field order. Normalize whitespace by replacing newlines and repeated whitespace with a single space, cap at 200 characters, and append `...` only when truncation occurs. `responses["character_name"]` may appear as the Character field. Do not include Discord username, email, `applicant_id`, member UUID, full response JSON, or synthetic/public-intake identifiers. This matches the problem-map PII rules (`research/26-bl-009-problem-map.md:127-133`) and the current `ApplicationRead` shape that otherwise exposes full responses and applicant UUIDs to authenticated surfaces (`services/api/app/contracts/applications.py:352-360`).

### Q5. Idempotency: one submit event, per-event envelopes, nonce delivery

Do not introduce a second event key system. INIT-128 already emits one `application.public_submitted` event after `_submit_application_internal` returns the queued application (`services/api/app/services/applications.py:870-885`), and materialization already deduplicates per-event envelopes through `uq_notification_envelopes__per_event` (`migrations/versions/wu-029a_notifications.py:190-203`) plus `insert_notification_envelope_on_conflict_do_nothing` (`services/api/app/repositories/notifications.py:210-251`). Discord delivery already derives a deterministic nonce from the envelope id and passes `enforce_nonce=True` (`services/discord/app/handlers/notifications.py:15-33`). The two notification rules use `grouping="per_event"`, producing at most one officer envelope and one applicant envelope for the submit event.

### Q6. Bundle BL-009 and BL-020

Bundle BL-009 and BL-020 as INIT-134. BL-020's applicant DM is mechanically the same substrate: the existing public submit event already carries `recipient_discord_user_id` from the applicant receipt (`services/api/app/services/notifications.py:83-110`), and the Discord handler already supports `channel == "dm"` (`services/discord/app/handlers/notifications.py:45-62`). Splitting would duplicate submit-hook, payload, materialization, and e2e work for little risk reduction.

### Q7. Tier 3 considerations: code only; e2e uses mock/test Discord

This INIT ships code, migrations, fixtures, and tests only. It must not send messages to the live Humility guild. AGENTS marks Discord sends as Tier 3 visible writes requiring explicit per-action approval (`AGENTS.md:18-26`), so local/e2e validation must run with mock Discord delivery or a test fixture guild. The current local Discord deployment is dry-run by default (`gitops/channels/local/applications/server-manager/discord-deployment.yaml:45-46`); INIT-134 keeps that posture and extends test fixture assertions rather than enabling live delivery. Production rollout to the real guild is a separate Tier 3 deployment/runbook action.

### Q8. Anti-scope boundary

Out of scope remains: transition notifications, private Discord threads, Discord-side claim/assign buttons, chapter Discord config UI, notification preferences, opt-out, remote channel rollout, and any live Humility guild send. This follows the problem-map anti-scope (`research/26-bl-009-problem-map.md:179-192`) and the original public-intake follow-up boundary that excluded Discord-visible queue embeds and applicant notifications from INIT-120 (`proposals/02-public-application-intake.md:443-451`).

## 3. Scope

### Migration

- `migrations/versions/wu-045_application_public_submit_notifications.py` - follows current Alembic head `wu_044_application_messages` (`migrations/versions/wu-044_application_messages.py:10-11`). Adds nullable `rendered_embed_json JSONB` to `notification_envelopes`; seeds two deterministic `notification_rules` rows for `application.public_submitted`:
  - `application_public_submitted_officer_review` with `channel="designated_channel"`, `grouping="per_event"`, and an embed template.
  - `application_public_submitted_applicant_dm` with `channel="dm"`, `grouping="per_event"`, and a text receipt template.

### New files

- `services/api/app/services/application_public_submit_notifications.py` - builds the Level A notification payload from `ApplicationRead`, resolved applicant Discord id, chapter/global routing config, and web/guild base URLs.
- `services/api/tests/test_application_public_submit_notifications.py` - payload builder and emit-on-submit component tests.
- `services/discord/tests/test_notification_embeds.py` - embed delivery coverage; this can be folded into `services/discord/tests/test_notifications.py` if the final diff stays small.

### Modified files

- `services/api/app/contracts/notifications.py` - add `NotificationTemplate`, `NotificationTemplateEmbed`, `NotificationTemplateEmbedField`, and optional `NotificationEnvelopeRead.rendered_embed_json`. Existing `NotificationDeliveryCommand` remains the delivery envelope wrapper (`services/api/app/contracts/notifications.py:121-160`).
- `services/api/app/services/notifications.py` - replace `APPLICATION_PUBLIC_SUBMITTED_PAYLOAD_ALLOWLIST` rather than merely widening it (`services/api/app/services/notifications.py:40-47`): remove `applicant_member_id`, remove `discord_user_id`, keep `recipient_discord_user_id` as the sole Discord recipient id, and add only the new safe rendered notification fields listed in §4. Replace the narrow emit helper body with a call into `application_public_submit_notifications`.
- `services/api/app/services/applications.py` - keep the emit hookpoint immediately after successful public submit (`services/api/app/services/applications.py:870-885`), pass enough application read data to render officer and applicant notification payloads, and wrap the emit side effect in defensive `try/except Exception` isolation so notification failures cannot turn a durably committed submit into a public 5xx.
- `services/api/app/services/notifications_materialize.py` - render `template_json["embed"]`, support event-payload recipient selectors, support event-payload designated-channel destinations, and store `rendered_embed_json` with the existing envelope insert path (`services/api/app/services/notifications_materialize.py:151-158`, `services/api/app/services/notifications_materialize.py:195-230`). Template substitution applies only to string embed fields (`title`, `description`, `url`, and each field's `name`/`value`); non-string fields (`color`, `fields[].inline`) pass through unchanged.
- `services/api/app/repositories/notifications.py` - select and insert `rendered_embed_json` next to `rendered_title`/`rendered_body` (`services/api/app/repositories/notifications.py:34-63`, `services/api/app/repositories/notifications.py:218-279`).
- `services/discord/app/handlers/notifications.py` - extend `_send_message` to pass `embed=` when `rendered_embed_json` is present; the current handler only sends raw `content` (`services/discord/app/handlers/notifications.py:20-33`, `services/discord/app/handlers/notifications.py:76-77`).
- `services/api/app/core/settings.py` - add `web_public_base_url: str = Field(...)`, `global_applications_review_channel_id`, `global_application_managers_role_id`, and `global_primary_guild_channel_url`; `web_public_base_url` has no Python default, matching required settings such as `discord_bot_token` and `discord_guild_id` (`services/api/app/core/settings.py:13-56`). Test settings override it via fixtures.
- `gitops/channels/local/applications/server-manager/e2e-fixtures-infisicalsecret.yaml` - add test-only `applications-review-channel-id`, `application-managers-role-id`, and `primary-guild-channel-url` fixture values beside the existing applicant Discord id (`gitops/channels/local/applications/server-manager/e2e-fixtures-infisicalsecret.yaml:28-32`).
- `gitops/channels/local/applications/server-manager/api-deployment.yaml` - wire the new fixture/settings env vars into the API pod, analogous to existing runtime env injection.
- `infra/tests/e2e/tests/19-web-ui.sh` - after public submit, assert the `notification_events` row and materialized envelopes/effects for officer + applicant; do not assert against the live Humility guild (`infra/tests/e2e/tests/19-web-ui.sh:8-39`, `infra/tests/e2e/tests/19-web-ui.sh:196-220`).

### Tests

- API component tests: submit emits one enriched `application.public_submitted` event, redacts full response payload, preserves existing audit/user actor behavior, schedules materialization, and suppresses notification emit exceptions after the submit row is committed.
- Materialization tests: the officer rule renders one pending designated-channel envelope with embed JSON; the applicant rule renders one pending DM envelope; missing channel/role/guild-url yields skipped envelopes with specific reasons; embed non-string fields retain their original types.
- Discord daemon tests: embed delivery calls `send(content=..., embed=..., nonce=..., enforce_nonce=True)` and nonce idempotency remains unchanged.
- E2e: extend `19-web-ui.sh` to assert a notification event row and materialized envelopes/effects against local Postgres; optional mock Discord delivery may assert the delivered embed, but must use the dry-run/mock/test guild path, not live Humility.

### Notification templates

- `application_public_submitted_officer_review`
  - Trigger: `application.public_submitted`
  - Channel: `designated_channel`
  - Recipients: event-payload channel/role selector from `officer_review_channel_id` + `application_managers_role_id`
  - Body/content: `${payload_application_managers_role_mention}`
  - Embed: title, URL, Level A preview, Application ID, Scope, Submitted, Form version, Support ID, Character
- `application_public_submitted_applicant_dm`
  - Trigger: `application.public_submitted`
  - Channel: `dm`
  - Recipients: event-payload Discord user selector from `recipient_discord_user_id`
  - Body: receipt text plus `${payload_primary_guild_channel_url}`

## 4. API + Discord Surface

### Emit hookpoint in submit service

The hookpoint stays in `submit_public_application_with_receipt` after `_submit_application_internal` returns and before the receipt endpoint returns the application id (`services/api/app/services/applications.py:839-885`). Because `_submit_application_internal` has already committed the application row, notification emission is a best-effort side effect and MUST be isolated from the HTTP response:

```python
try:
    notification_events.emit(
        db,
        event_type="application.public_submitted",
        ...
    )
except Exception:  # noqa: BLE001 - defensive isolation
    logger.exception(
        "notification emit failed for application %s; "
        "submit row remains durably committed",
        application_id,
    )
    # Do NOT re-raise: the application has been committed.
    # Operators can manually trigger the notification from
    # the materialization queue / via re-emit if needed.
```

This preserves existing public submit auth at the endpoint (`services/api/app/api/v1/endpoints/applications/public.py:25-47`) and avoids touching the Discord-side `/api/v1/applications` submission flow (`services/discord/app/handlers/application_submission.py:47-93`). A notification-side failure must not produce a public 5xx after the submit row is durably committed.

### Notification event schema

Reuse event type `application.public_submitted`; do not create separate `officer` and `applicant` event types. The event payload expands from the current id-only payload (`services/api/app/services/notifications.py:100-105`) to:

```json
{
  "application_id": "uuid",
  "support_id": "APP-...",
  "recipient_discord_user_id": "123456789012345678",
  "scope_kind": "global|chapter|member",
  "scope_id": "string|null",
  "scope_label": "Global",
  "submitted_unix_ts": "1710000000",
  "submitted_iso": "2026-04-29T...",
  "form_version": "1",
  "character_name": "Name",
  "response_preview": "200 char max",
  "application_url": "https://<web-public-base>/applications/{id}",
  "officer_review_channel_id": "123...",
  "application_managers_role_id": "456...",
  "application_managers_role_mention": "<@&456...>",
  "primary_guild_channel_url": "https://discord.com/channels/..."
}
```

The allowlist is replaced with only these rendered notification fields:

- `application_id`
- `support_id`
- `recipient_discord_user_id`
- `scope_kind`
- `scope_id`
- `scope_label`
- `submitted_unix_ts`
- `submitted_iso`
- `form_version`
- `character_name`
- `response_preview`
- `application_url`
- `officer_review_channel_id`
- `application_managers_role_id`
- `application_managers_role_mention`
- `primary_guild_channel_url`

Remove `applicant_member_id` from the allowlist because member UUIDs are excluded by Q4. Remove `discord_user_id` because it duplicates `recipient_discord_user_id`; the recipient field is the single source of truth for applicant DM delivery. Full `responses`, applicant UUIDs, emails, usernames, and synthetic/public-intake identifiers remain excluded.

### Materializer embed substitution scope

Embed materialization uses `Template(...).substitute(context)` only for string fields: `title`, `description`, `url`, and each embed field's `name` and `value`. It passes non-string fields through unchanged: `color` remains `int | None`, and `fields[].inline` remains `bool`. The materializer must not stringify `color` or `inline` and then coerce them back.

### Discord handler extension

The existing handler supports DM and designated-channel routing but only sends `content` (`services/discord/app/handlers/notifications.py:28-33`, `services/discord/app/handlers/notifications.py:45-77`). INIT-134 extends delivery to construct a Discord embed from `envelope.rendered_embed_json` and call `target.send(content=content, embed=embed, nonce=nonce, enforce_nonce=True)`. Invalid embed JSON is a definitive failure because it is a template/config error; transient Discord API failures remain non-definitive as today (`services/discord/app/handlers/notifications.py:83-89`).

### Web URL routing for embed link

The embed URL uses `web_public_base_url.rstrip("/") + "/applications/{application_id}"`. `web_public_base_url` is required settings input declared as `Field(...)` with no hardcoded local default; tests provide it through the settings fixture. The route exists in the TanStack router (`services/web/src/app/router.tsx:85-92`) and is protected by the officer web bridge already delivered in BL-019D-beta (`plans/BACKLOG.md:613-625`). No new web route or API endpoint is added.

## 5. Component Contract Preview

### Notification template Pydantic shape

```python
class NotificationTemplateEmbedField(BaseModel):
    name: str
    value: str
    inline: bool = False

class NotificationTemplateEmbed(BaseModel):
    title: str
    description: str | None = None
    url: str | None = None
    color: int | None = Field(default=None, ge=0, le=0xFFFFFF)
    fields: list[NotificationTemplateEmbedField] = Field(default_factory=list)

class NotificationTemplate(BaseModel):
    name: str
    body: str = ""
    title: str = ""
    embed: NotificationTemplateEmbed | None = None
```

Materialization renders string template fields with the existing `Template(...).substitute(context)` behavior (`services/api/app/services/notifications_materialize.py:136-158`). For embeds, substitution applies only to `title`, `description`, `url`, and each field's `name` and `value`. Non-string fields pass through unchanged: `color: int | None` remains an integer/null value and `fields[].inline: bool` remains a boolean. The materializer MUST NOT coerce non-string embed values through `str()` and back. `NotificationRuleCreate.template_json` remains persisted as JSONB (`services/api/app/contracts/notifications.py:45-54`); the new Pydantic shape validates the JSON rather than creating a second template store.

### Chapter Discord config Pydantic shape

No new chapter fields. Use the existing shape:

```python
class ChapterDiscordResources(BaseModel):
    category_id: str | None = None
    role_ids: dict[str, str] = Field(default_factory=dict)
    channel_ids: dict[str, str] = Field(default_factory=dict)
```

Required keys for chapter-scoped application notifications are:

```json
{
  "role_ids": {"application_managers": "discord-role-snowflake"},
  "channel_ids": {"applications_review": "discord-channel-snowflake"}
}
```

Global submissions use settings-backed fallback values because there is no chapter row for `scope_kind="global"` (`research/26-bl-009-problem-map.md:92-106`).

### Discord embed render shape

```python
class DiscordEmbedFieldRead(BaseModel):
    name: str
    value: str
    inline: bool = False

class DiscordEmbedRead(BaseModel):
    title: str
    description: str | None = None
    url: str | None = None
    color: int | None = None
    fields: list[DiscordEmbedFieldRead] = Field(default_factory=list)
```

`NotificationEnvelopeRead.rendered_embed_json: DiscordEmbedRead | None` is delivered unchanged to the Discord daemon through `NotificationDeliveryCommand`, preserving the existing envelope command shape (`services/api/app/contracts/notifications.py:121-160`).

## 6. Authorization Model

Public submit auth is unchanged. The route still requires `verify_applicant_receipt`, authorizes public intake, and calls `submit_public_application_with_receipt` with the verified Discord user id (`services/api/app/api/v1/endpoints/applications/public.py:30-41`). The service still resolves/creates a real Discord member and records the submit/route actor as that user (`services/api/app/services/applications.py:859-875`). Notification emission is a system-side consequence of the accepted submit; it introduces no user-controlled authorization decision and no new public endpoint. Embed materialization is template rendering only: it substitutes string fields and leaves `color`/`inline` typed values unchanged, so it adds no authorization branch. Delivery workers continue to operate under the existing notification dispatcher substrate and grants seeded by the notification migration (`migrations/versions/wu-029a_notifications.py:229-260`).

## 7. Test Plan

### API tests: emit-on-submit

Extend or add tests beside `services/api/tests/test_public_intake_submit.py`, which already asserts the public submit event exists and targets the receipt Discord user (`services/api/tests/test_public_intake_submit.py:91-139`, `services/api/tests/test_public_intake_submit.py:141-170`). New assertions:

- One `application.public_submitted` event is created per successful receipt-backed submit.
- Payload includes application URL, scope label, form version, submitted timestamp, truncated preview, character name, destination channel id, role id, role mention, and applicant DM recipient.
- Payload excludes full `responses`, `applicant_id`, `applicant_member_id`, and applicant username/email.
- Missing global officer config does not fail submission; it produces an event that materialization can skip for officer delivery.
- If `notification_events.emit` raises, the public submit endpoint still returns its normal success response with the application id, and the application row exists in Postgres. The test mocks the emit call to raise and asserts no 5xx propagates after the submit commit.

Risk annotation: `group=TG-1; named_risk=public_submit_notification_event_payload; level=component`.

### Notification materialization tests

Extend `services/api/tests/test_notification_materialization.py`, which already covers per-event envelope idempotency, template snapshots, skipped templates, and delivery effect enqueueing (`services/api/tests/test_notification_materialization.py:455-494`, `services/api/tests/test_notification_materialization.py:523-582`):

- Officer rule renders one `designated_channel` envelope with `destination_channel_id`, `recipient_key`, role mention content, and `rendered_embed_json`.
- Applicant rule renders one `dm` envelope with `recipient_discord_id` from event payload.
- Replaying the same event does not create duplicate officer or applicant envelopes.
- Missing event-payload destination/recipient fields produce skipped envelopes and no delivery effect.
- Embed substitution preserves non-string types: a template with `color` and `fields[].inline` renders an embed whose color is still an integer/null and inline is still a boolean.

Risk annotation: `group=TG-2; named_risk=notification_materialization_embed_and_dynamic_recipient; level=component`.

### Live-guild fixture guard test

Add a unit/contract test that loads the chapter Discord config fixture and the global fallback test settings, then asserts fixture/test channel, role, and guild ids are not production ids. The guard list includes the live Humility guild id `900000000000000001` from `AGENTS.md` plus every known production application-review channel id and application-manager role id recorded in repo docs or deployment fixtures. The test fails if any configured e2e/test value equals a production id, preventing local e2e from accidentally targeting the live guild or live channel/role resources.

Risk annotation: `group=TG-2b; named_risk=live_guild_fixture_guard; level=contract`.

### Discord daemon tests

Extend the current Discord notification tests, which assert deterministic nonce and malformed recipient/destination failures (`services/discord/tests/test_notifications.py:45-84`, `services/discord/tests/test_notifications.py:87-125`):

- Designated-channel embed delivery calls `fetch_channel`, sends role mention content, passes a Discord embed object, and preserves `nonce`/`enforce_nonce`.
- DM receipt without embed still sends text content and preserves nonce behavior.
- Malformed embed JSON raises definitive `NotificationDeliveryError`.

Risk annotation: `group=TG-3; named_risk=discord_embed_delivery_idempotency; level=daemon`.

### E2e

Extend `infra/tests/e2e/tests/19-web-ui.sh` after `assert_public_submit_persisted` to query local Postgres for:

- One `notification_events` row with `event_type='application.public_submitted'` for the submitted application.
- Two notification envelopes, one `designated_channel` with non-null `rendered_embed_json`, one `dm` with the fixture applicant Discord id.
- Delivery effects queued for both envelopes unless the test explicitly runs materialization/delivery with a mock worker.

The e2e Discord leg must use dry-run/mock Discord or a test fixture guild only. It must not send to guild `900000000000000001`; visible production delivery is Tier 3 and separate from this code/test INIT (`AGENTS.md:18-26`, `research/26-bl-009-problem-map.md:166-177`).

Risk annotation: `group=TG-4; named_risk=e2e_notification_rows_without_live_discord_write; level=e2e`.

## 8. Anti-scope

- No live Humility Discord send, deployment, or runbook execution.
- No private Discord thread per application.
- No Discord buttons, claim/assign controls, or transition side effects.
- No officer-to-applicant DM flow; in-product messages/transcript stay under BL-019D-beta (`plans/BACKLOG.md:641-665`).
- No chapter Discord config UI; this slice reads existing resource maps/settings only.
- No notification preferences, opt-out, escalation policy, digesting, or per-officer routing.
- No remote channel rollout; local fixture wiring only.
- No backwards-compatibility aliases, feature flags for old behavior, deprecated fields, or placeholder stubs.

Future BL candidates: transition notifications after state changes, admin UI for chapter Discord resources, remote channel application notification rollout, and notification preferences.

## 9. Diff Budget

Estimated net: +950 / -20 lines.

- Migration + seeded rules: +120
- API contracts/repository/materialization embed support: +220
- Public submit notification payload builder + settings: +180
- Discord daemon embed delivery: +90
- API/materialization/daemon tests: +260
- E2e fixture + test 19 assertions: +100

This is under 1500 lines, so keep BL-009 + BL-020 bundled. If implementation exceeds 1500 net lines or requires a second delivery worker path, decompose: ship BL-020 applicant DM first on the existing text-only DM path, then BL-009 officer embed as the follow-up. The preferred implementation should not need that split.

## 10. Risk Gates (round-2 self-review: LOW)

R1 verdicts were audit LOW with four minor findings, scope LOW, shortcut MEDIUM on S8, and supported-surface LOW. This revision applies all five findings in place:

- F-1 payload allowlist hygiene: §3 and §4 now require replacing `APPLICATION_PUBLIC_SUBMITTED_PAYLOAD_ALLOWLIST`, removing `applicant_member_id` and `discord_user_id`, keeping `recipient_discord_user_id` as the sole Discord recipient id, and adding only the safe rendered notification fields.
- F-2 `web_public_base_url` defaulting: §3, §4, and §11 now declare `web_public_base_url: str = Field(...)` with no Python default. Tests must provide it through fixture settings; no `humility.local` literal is baked into Python settings.
- F-3 live-guild defense-in-depth: §7 now adds a unit/contract guard that fixture/test guild, channel, and role ids do not equal the live Humility guild id `900000000000000001` or known production channel/role ids.
- F-4 embed substitution scope: §3, §4, §5, §6, §7, and §11 now lock string-only `Template(...).substitute(context)` for embed `title`, `description`, `url`, and field `name`/`value`; `color` and `fields[].inline` pass through typed and are covered by a materialization test.
- S8 submit-side emit failure isolation: §3, §4, §7, and §11 now require defensive `try/except Exception` around the post-commit notification emit, log the failure, do not re-raise, and test that a raising emit still returns the normal public submit response with the committed application id.

Audit risk remains LOW because PII allowlisting, URL defaulting, live-guild fixture protection, and embed typing are explicitly locked. Scope risk remains LOW because the slice still touches only public-submit notifications, two templates, one optional envelope embed field, settings/fixture wiring, and local e2e assertions. Shortcut risk is now LOW because S8's post-commit emit isolation is part of the submit hookpoint contract and has an API test. Supported-surface risk remains LOW because the public submit request/response contract is preserved, notification failures cannot poison the accepted-submit response, and live Discord delivery remains outside this INIT.

Conclusion: LOW.

## 11. Hookpoint Preview

### Reuse

- Public submit endpoint and receipt auth: `services/api/app/api/v1/endpoints/applications/public.py:25-47`.
- Public submit service hookpoint: `services/api/app/services/applications.py:839-885`; keep the post-commit emit location, but wrap notification emission in `try/except Exception` with `logger.exception(...)` and no re-raise.
- Existing event emission helper and allowlist: `services/api/app/services/notifications.py:40-110`; replace the allowlist so `applicant_member_id` and `discord_user_id` are removed and only safe rendered notification fields remain.
- Notification event insert and materialization enqueue: `services/api/app/services/notification_events.py:32-84`.
- Materialization rule matching, templating, envelope insertion, delivery enqueue: `services/api/app/services/notifications_materialize.py:60-68`, `services/api/app/services/notifications_materialize.py:151-158`, `services/api/app/services/notifications_materialize.py:195-254`.
- Envelope idempotency indexes: `migrations/versions/wu-029a_notifications.py:190-203`.
- Discord delivery nonce/idempotency: `services/discord/app/handlers/notifications.py:15-33`.
- Chapter Discord resource maps: `services/api/app/contracts/chapters.py:39-43`.

### New

- Embed render support on notification envelopes.
- String-only embed template substitution with typed pass-through for `color` and `fields[].inline`.
- Event-payload recipient and destination selectors in materialization.
- Public-submit notification payload builder for Level A preview, web URL, global/chapter route config, role mention, and applicant DM data.
- Required `web_public_base_url: str = Field(...)` with no Python-level local default.
- Local e2e fixture values for mock/test channel, role, and primary guild URL.

### Delete or avoid

- Do not add a second public-submit event type.
- Do not send Discord messages directly from `services/api/app/services/applications.py`.
- Do not add chapter config columns duplicating `discord_resources`.
- Do not enable live Discord sends in e2e.
