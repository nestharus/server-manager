# INIT-134 — Supported-surface risk gate

**Verdict:** LOW

INIT-134 (BL-009 + BL-020 bundle) ships the public-submit Discord
notification slice on top of the existing INIT-029a notification
substrate: a new optional `rendered_embed_json` column on
`notification_envelopes`, two seeded `application.public_submitted`
rules (officer designated-channel embed, applicant DM), an extended
Discord delivery `_send_message` that passes `embed=` only when an
embed JSON is present, and a payload-allowlist tightening on the
existing emit helper. The public submit HTTP contract is byte-identical;
the notification emit is isolated post-commit so a failure cannot
poison the receipt response. Pomerium, Authentik, the build pipeline,
the chapter contract, and the direct lifecycle API are untouched.

## Surfaces touched

### 1. Database schema

| Surface | Pre (post-WU-044) | Post (WU-045) | Risk |
|---|---|---|---|
| Alembic head | `wu_044_application_messages` (`migrations/versions/wu-044_application_messages.py:10-11`) | `wu_045_application_public_submit_notifications` chained off `down_revision = "wu_044_application_messages"` | additive — single linear chain preserved |
| `notification_envelopes` columns | INIT-029a columns including `rendered_title`, `rendered_body`, `template_snapshot_json`, `recipient_key`, `recipient_discord_id`, `destination_channel_id`, etc. (`migrations/versions/wu-029a_notifications.py`, `services/api/app/repositories/notifications.py:34-63`) | adds **nullable** `rendered_embed_json JSONB` | additive — existing inserts and selects keep working; legacy text-only envelopes leave the column NULL |
| `notification_envelopes` indexes / constraints | `uq_notification_envelopes__per_event` (`migrations/versions/wu-029a_notifications.py:190-203`) | unchanged | none |
| `notification_rules` rows | INIT-029a seeded rules; no rule currently bound to `application.public_submitted` | seeds two rules (`application_public_submitted_officer_review`, `application_public_submitted_applicant_dm`) — no edits to existing rule rows | additive — additional rule data only |
| Other tables (`applications`, `application_messages`, `members`, `notification_events`, `notification_rules`, `aggregate_heads`, `activity_actions`, `activity_state_changes`, `chapters`) | unchanged | unchanged | none |
| Destructive ALTER TABLE / column drops / table renames | none | none — proposal §3 is additive only; §8 anti-scope rules out a second event type, chapter column duplication of `discord_resources`, and live Discord side effects | none |

The migration is forward-additive. Older API code reading
`notification_envelopes` continues to function: the existing
`_ENVELOPE_SELECT` (`services/api/app/repositories/notifications.py:34-63`)
does not touch the new column, and the proposal extends both the
SELECT projection and the INSERT path to include `rendered_embed_json`
beside `rendered_title` / `rendered_body` (proposal §3).

Risk on §1: **none** — gate criterion 1 (schema additions only, no
destructive `ALTER TABLE`) holds.

### 2. Notification event / template schema

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `application.public_submitted` event type | emitted from `submit_public_application_with_receipt` (`services/api/app/services/applications.py:870-885`) with payload `{application_id, applicant_member_id, discord_user_id, recipient_discord_user_id}` (`services/api/app/services/notifications.py:83-110`) | same event type — **not** a new event name; payload expands per proposal §4 to add `support_id, scope_kind, scope_id, scope_label, submitted_unix_ts, submitted_iso, form_version, character_name, response_preview, application_url, officer_review_channel_id, application_managers_role_id, application_managers_role_mention, primary_guild_channel_url`; `recipient_discord_user_id` keeps its meaning as the applicant DM recipient | additive on the payload; **no new event type** |
| `APPLICATION_PUBLIC_SUBMITTED_PAYLOAD_ALLOWLIST` | `{application_id, applicant_member_id, discord_user_id, recipient_discord_user_id}` (`services/api/app/services/notifications.py:40-47`) | **replaced** with the safe rendered set listed in proposal §4: `application_id, support_id, recipient_discord_user_id, scope_kind, scope_id, scope_label, submitted_unix_ts, submitted_iso, form_version, character_name, response_preview, application_url, officer_review_channel_id, application_managers_role_id, application_managers_role_mention, primary_guild_channel_url`. Removes `applicant_member_id` and `discord_user_id` (the second is a duplicate of `recipient_discord_user_id`) | tightening — existing event consumers do not exist beyond the materializer, which only references payload keys it has templates for; `recipient_discord_user_id` stays |
| `NotificationEventDraft` / `NotificationEventRead` Pydantic shape | `services/api/app/contracts/notifications.py:103-118` | unchanged | none |
| `NotificationRuleCreate.template_json` JSONB shape | `dict[str, Any]` (`services/api/app/contracts/notifications.py:45-54`) | unchanged at the persistence layer; new `NotificationTemplate` / `NotificationTemplateEmbed` / `NotificationTemplateEmbedField` Pydantic models are added in `app.contracts.notifications` to validate the JSON content for the two new rules. No existing rule template needs to revalidate against the new shape because they have no `embed` key and `embed: NotificationTemplateEmbed \| None = None` (proposal §5). | additive — Pydantic validation models layered on top of existing JSONB |
| `NotificationEnvelopeRead` shape | `services/api/app/contracts/notifications.py:121-148` | adds optional `rendered_embed_json: DiscordEmbedRead \| None` (proposal §5). All existing fields preserved. | additive |
| `NotificationDeliveryCommand` shape | `envelope: NotificationEnvelopeRead` (`services/api/app/contracts/notifications.py:159-160`) | unchanged — embed JSON rides inside the envelope | none |
| Existing notification rules (`ticket_sla_*`, INIT-029a seeds) | unchanged | unchanged — proposal explicitly does not edit existing template rows | none |
| Existing notification template names | unchanged | adds two new template names (`application_public_submitted_officer_review`, `application_public_submitted_applicant_dm`); no edits to existing template names | additive |

Risk on §2: **none** — gate criterion 2 (new template names added; no
edits to existing templates) holds. The allowlist tightening is internal
to `emit_application_public_submitted_event`; no existing materializer
template references the dropped keys (no rule for
`application.public_submitted` exists today), and `recipient_discord_user_id`
remains as the canonical applicant DM recipient.

### 3. Discord daemon delivery contract

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `deliver_notification(command, *, bot)` signature | `services/discord/app/handlers/notifications.py:36-40` | unchanged | none |
| `envelope_nonce(envelope_id)` derivation | base32-then-strip on `envelope.id.bytes`, truncated to 25 chars (`services/discord/app/handlers/notifications.py:15-17`) | unchanged | none |
| `_send_message(target, *, content, nonce)` | `target.send(content=..., nonce=..., enforce_nonce=True)` (`services/discord/app/handlers/notifications.py:28-33`) | extended to `_send_message(target, *, content, nonce, embed=None)`; when `embed is None`, the call is byte-identical to today (no `embed=` kwarg passed); when an embed object is built from `envelope.rendered_embed_json`, the call adds `embed=embed`. discord.py's `TextChannel.send` / `DMChannel.send` already accept an optional `embed=` kwarg; passing `embed=None` is also a no-op. | additive — text-only delivery path preserved |
| `_message_content(command)` body | strips `rendered_title`/`rendered_body` and joins with `\n` (`services/discord/app/handlers/notifications.py:20-25`) | unchanged | none |
| DM channel branch | `bot.fetch_user → user.dm_channel | user.create_dm() → _send_message(...)` (`services/discord/app/handlers/notifications.py:45-62`) | unchanged when `rendered_embed_json is None`; the DM rule for INIT-134 ships **without** an embed (text-only receipt), so applicant DM delivery uses the existing path | none |
| Designated-channel branch | `bot.fetch_channel(int(destination_channel_id)) → _send_message(...)` (`services/discord/app/handlers/notifications.py:63-77`) | unchanged when `rendered_embed_json is None`; for the new officer rule, `rendered_embed_json` is set and the call adds `embed=` | additive |
| Definitive-failure branches: missing `recipient_discord_id` for DM, malformed numeric ids, `thread` channel | `services/discord/app/handlers/notifications.py:46-82` | unchanged; the new officer rule uses `designated_channel`, not `thread` | none |
| `NotificationDeliveryError` definitive vs non-definitive semantics | `services/discord/app/handlers/notifications.py:83-89`, `services/api/app/contracts/notifications.py:207-215` | unchanged; per proposal §4, malformed embed JSON is a definitive failure (template/config error), but transient Discord API failures remain non-definitive | none for the existing contract; new behavior is additive |
| Existing daemon tests (`services/discord/tests/test_notifications.py`) | `test_delivery_uses_deterministic_nonce_derived_from_envelope_id`, `test_malformed_recipient_discord_id_is_definitive_failure`, `test_malformed_destination_channel_id_is_definitive_failure` (`services/discord/tests/test_notifications.py:45-126`) | continue passing — the existing fixtures construct envelopes with no `rendered_embed_json` attribute (or set it to None), and the handler keeps the `_send_message(content=..., nonce=...)` call when embed is absent. New tests live alongside without disturbing the existing assertions. | none |

Risk on §3: **none** — gate criterion 3 (extension to support embeds;
existing text-only deliveries still work) holds. The `_send_message`
signature widening (adding a default-`None` `embed=` kwarg) is a
backwards-compatible refinement; every current caller keeps working
without source change. The applicant DM rule deliberately has no embed,
so the DM path is byte-identical to today.

### 4. Public submit HTTP API

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `POST /api/v1/public/applications` route prefix + path | `services/api/app/api/v1/endpoints/applications/public.py:22-30` | unchanged | none |
| Request body shape | `PublicApplicationSubmission` | unchanged | none |
| Auth dependency | `Depends(verify_applicant_receipt)` + `Depends(authorize_public_intake)` (`services/api/app/api/v1/endpoints/applications/public.py:30-41`) | unchanged | none |
| Response model | `PublicApplicationSubmissionReceipt` with `{message: "Application received", application_id: <uuid>}` (`services/api/app/api/v1/endpoints/applications/public.py:25-47`) | unchanged | none |
| Success status code | `HTTPStatus.CREATED` (201) | unchanged | none |
| Error mapping | `raise_known_application_error(error)` (`services/api/app/api/v1/endpoints/applications/public.py:42-43`) | unchanged | none |
| Notification emit relative position to commit | post-commit (after `_submit_application_internal` returns) (`services/api/app/services/applications.py:870-885`) | unchanged position; **wrapped in `try/except Exception` with `logger.exception(...)` and no re-raise** (proposal §4 / §10 / §11). Side-effect-only; never converts a committed submit into a 5xx. | hardened — the response contract is more stable than today, not less |
| `submit_public_application_with_receipt(...)` return value | `UUID` of created application (`services/api/app/services/applications.py:839-885`) | unchanged | none |
| `notification_events.emit` raising → endpoint behavior | currently could in theory propagate an exception out of the post-commit emit (no defensive isolation today) and surface as a 5xx | per proposal §7 the new test asserts `notification_events.emit` raising still returns the normal `HTTPStatus.CREATED` response with the application id; the application row remains durably committed | response contract strengthened |

Risk on §4: **none** — gate criterion 4 (response shape and status
codes unchanged; notification emit is a side-effect, not part of the
response contract) holds. The defensive `try/except` around the
post-commit emit specifically bolts down the "side-effect only"
property.

### 5. Existing tests preserved

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `services/api/tests/test_public_intake_submit.py` (existing event-emit assertions; `:91-170`) | asserts a single `application.public_submitted` event with the receipt Discord user as `recipient_discord_user_id` | unchanged on the existing assertion structure; new assertions are additive (full payload set, full-`responses` redaction, applicant_id / applicant_member_id / username / email exclusion, missing-global-config skipped envelope, raising emit returns normal 201). The existing receipt-recipient assertion still holds because the allowlist preserves `recipient_discord_user_id`. | additive |
| `services/api/tests/test_notification_materialization.py` (per-event idempotency, template snapshots, skipped templates, delivery effects; `:455-582`) | exercises the existing materializer envelope shape with text rule template | unchanged on the existing assertion structure; new tests cover (a) officer rule renders one designated-channel envelope with embed JSON, (b) applicant rule renders one DM envelope, (c) replays produce no duplicates (per-event grouping idempotency unchanged), (d) missing destination/recipient → skipped envelope, (e) embed substitution preserves non-string types | additive |
| `services/discord/tests/test_notifications.py` | nonce determinism, malformed recipient/destination definitive failures (`:45-126`) | unchanged; new tests cover (a) designated-channel embed delivery passes role-mention content + embed object + nonce, (b) DM receipt without embed still sends text content with nonce, (c) malformed embed JSON is a definitive failure | additive |
| Compat / β-i / β-ii / β-iii officer flows (`services/web/tests/compat.spec.ts`, `services/web/tests/officer-queue.spec.ts`, `services/web/tests/officer-detail.spec.ts`, `services/api/tests/test_web_officer_applications.py`) | β-i / β-ii / β-iii officer bridge and web detail flow | unchanged — INIT-134 does not touch officer routes, the web SPA, the queue/detail components, the dependency-tree guard, or `client.ts`. | none |
| Officer dependency-tree guard `test_officer_endpoints_have_locked_actor_construction` (`services/api/tests/test_web_officer_applications.py:1110-1147`) | enforces six officer routes use `_build_officer_actor` and forbid `verify_applicant_receipt` / `CURRENT_ACTOR.get` | unchanged — INIT-134 introduces zero new officer bridge routes and zero officer-route handler edits | none |
| `infra/tests/test_applicant_discord_pomerium.py` (Pomerium static route assertions) | β-i / β-ii / β-iii Pomerium ordering | unchanged — INIT-134 introduces zero Pomerium changes | none |
| `infra/tests/e2e/tests/19-web-ui.sh` (`assert_public_submit_persisted`, `assert_officer_review_persisted`, `assert_officer_detail_checked`) | β-i / β-ii / β-iii e2e assertions | preserved unchanged in structure; INIT-134 appends new assertions after `assert_public_submit_persisted` for the `notification_events` row, two materialized envelopes (one `designated_channel` with non-null `rendered_embed_json`, one `dm` with the fixture applicant Discord id), and queued delivery effects (proposal §3, §7). Existing assertions are not mutated. Suite count stays at 19. | additive |
| Live-guild fixture guard | not present today | new contract test (`group=TG-2b; named_risk=live_guild_fixture_guard; level=contract`) asserts fixture/test channel, role, and guild ids are not the live Humility guild id `900000000000000001` or known production channel/role ids (proposal §7). | additive — defense-in-depth |

Risk on §5: **none** — gate criterion 5 (applicant compat, β-i/β-ii/β-iii
tests continue passing) holds. Every existing assertion in
`test_public_intake_submit.py`, `test_notification_materialization.py`,
`test_notifications.py`, `compat.spec.ts`, `officer-queue.spec.ts`,
`officer-detail.spec.ts`, `test_web_officer_applications.py`,
`test_applicant_discord_pomerium.py`, and `19-web-ui.sh` is preserved
verbatim or extended additively without removing or weakening any
existing condition.

### 6. Pomerium / Authentik

**No new entries. No re-ordering. No identity-header changes. No new
Authentik blueprint, application, provider, source, or scope mapping.**
The `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml`
block stays at its post-β-iii state with the same eight web-host
routes, the public catch-all, and the protected-api host.
`/api/v1/public/applications` continues to resolve through the public
catch-all; the notification emit hookpoint sits inside the API service
behind the same auth chain (applicant receipt → public intake authz)
that exists today (`services/api/app/api/v1/endpoints/applications/public.py:30-41`).
`gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml`
is unchanged.

`infra/tests/test_applicant_discord_pomerium.py` is unchanged.

Risk on §6: **none** — gate criterion 6 (no Pomerium / Authentik
changes) holds.

### 7. Environment variables / settings

| Setting | Pre | Post | Required? | Risk |
|---|---|---|---|---|
| `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `SUPABASE_DB_URL`, `SUPABASE_SERVICE_KEY` | `services/api/app/core/settings.py:21-26` | unchanged | required (existing) | none |
| `WEB_PUBLIC_BASE_URL` | not present | **new** — `web_public_base_url: str = Field(...)` declared with no Python default (proposal §3, §11; F-2 audit lock from §10) | **required** at API boot for any channel; tests provide it through fixture settings; the slice updates `gitops/channels/local/applications/server-manager/api-deployment.yaml` to wire it from the `server-manager-e2e-fixtures` Infisical secret | additive new required env var; coupled to deployment YAML update in the same slice → single-channel atomic rollout. **F-7-A** below tracks this. |
| `GLOBAL_APPLICATIONS_REVIEW_CHANNEL_ID` | not present | **new** — optional API setting; missing → officer envelope skipped with `destination_missing` reason (proposal §3 / §4) | optional — missing is logged, not an error | criterion 7 holds: missing → no notification fires, logged not error |
| `GLOBAL_APPLICATION_MANAGERS_ROLE_ID` | not present | **new** — optional API setting; missing → officer envelope skipped with `recipient_unresolved` reason (proposal §3 / §4) | optional | criterion 7 holds |
| `GLOBAL_PRIMARY_GUILD_CHANNEL_URL` | not present | **new** — optional API setting; missing → applicant DM skipped (proposal §3 / §4) | optional | criterion 7 holds |
| `gitops/channels/local/applications/server-manager/e2e-fixtures-infisicalsecret.yaml` | applicant Discord id, applicant receipt signing key, etc. (`gitops/channels/local/applications/server-manager/e2e-fixtures-infisicalsecret.yaml:28-32`) | adds test-only `applications-review-channel-id`, `application-managers-role-id`, `primary-guild-channel-url` (and `web-public-base-url` if not already present in another secret) | fixture-only test values; live-guild guard (proposal §7 TG-2b) asserts these are NOT live Humility ids | additive |
| `gitops/channels/local/applications/server-manager/api-deployment.yaml` | existing API runtime env injection | extends env injection for the new fixture/settings keys analogous to existing pattern | additive | none |
| `gitops/channels/local/applications/server-manager/discord-deployment.yaml` | dry-run by default (`gitops/channels/local/applications/server-manager/discord-deployment.yaml:45-46`) | unchanged — INIT-134 keeps dry-run posture; live delivery is Tier 3 / separate runbook (proposal §2 Q7, §8) | unchanged | none |

**F-7-A (LOW finding, supported-surface).** `WEB_PUBLIC_BASE_URL` is
additive and required. Gate criterion 7 explicitly cites
`GLOBAL_APPLICATIONS_REVIEW_CHANNEL_ID` and the other two GLOBAL_*
vars as the optional set; it is silent on `WEB_PUBLIC_BASE_URL`. The
proposal's audit lock F-2 (proposal §10) deliberately makes
`web_public_base_url` required — `Field(...)`, no Python default — so
that no `humility.local` literal leaks into Python settings. Risk is
LOW because (a) the slice atomically updates
`gitops/channels/local/applications/server-manager/api-deployment.yaml`
to wire the env var from the existing fixture/secret pipeline; (b) only
the `local` channel exists today (per
`gitops/channels/local/.../api-deployment.yaml`), so there is no
remote deployment that could fail to start due to a missing variable
without the slice's own YAML change reaching it; (c) the API settings
loader (`load_settings()` /
`_missing_env_vars_from_error`,
`services/api/app/core/settings.py:80-86`) already raises
`SettingsConstructionError` listing missing required env vars at boot,
so a misconfigured deploy fails loudly rather than silently degrading.
**Mitigation:** the per-channel deployment YAML must include
`WEB_PUBLIC_BASE_URL` in the same commit as the migration / settings
change, which proposal §3 explicitly requires. No change to the gate
verdict.

Risk on §7: **LOW** — criterion 7 holds for the GLOBAL_* trio; the new
required `WEB_PUBLIC_BASE_URL` is tracked as F-7-A above and mitigated
by atomic YAML wiring in the same slice. No silent failure mode.

### 8. Chapter config (`ChapterDiscordResources` / `chapters` table)

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `ChapterDiscordResources` Pydantic shape | `category_id: str \| None`, `role_ids: dict[str, str]`, `channel_ids: dict[str, str]` (`services/api/app/contracts/chapters.py:39-43`) | unchanged | none |
| `chapters.discord_resources` JSONB column | `migrations/versions/wu-019_chapter_lifecycle.py:33-39` | unchanged | none |
| Chapter resource merge service | `services/api/app/services/chapters.py:282-292` | unchanged | none |
| Chapter rows that do not set `role_ids["application_managers"]` or `channel_ids["applications_review"]` | currently unset for all chapters (no first user) | INIT-134 reads these keys for chapter-scoped applications; **missing → officer envelope skipped with `destination_missing` / `recipient_unresolved` reason; no error**. Proposal §2 Q1 deliberately reuses the existing dict-based shape rather than adding columns. | backwards-compatible |
| Public submit's current scope | `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:39-45` shows `scope_kind="global"` | unchanged — global submit uses the global fallback settings (criterion 7), not chapter dicts; chapter-scoped applications keep working when chapter dicts are unset (skipped, not error) | none |
| `ChapterRead` / `ChapterCreate` / `ChapterTransitionRequest` / `ChapterArchive*` | `services/api/app/contracts/chapters.py:45-159` | unchanged | none |

Risk on §8: **none** — gate criterion 8 (nullable / optional fields =
backwards-compatible with chapters that don't set them) holds. The slice
adds **zero** new chapter fields — proposal §5 ("No new chapter
fields. Use the existing shape") — and the missing-key behavior is the
problem-map-specified "skipped envelope, logged, not error."

### 9. Build pipeline

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `containers/server-manager/Containerfile.api` | β-i / β-ii / β-iii API image build | unchanged | none |
| `containers/server-manager/Containerfile.web` | β-i / β-ii / β-iii web image build | unchanged | none |
| `containers/server-manager/Containerfile.discord` | discord daemon image build | unchanged — daemon code change is a Python edit inside an existing module, no new system dep, no new pip dep | none |
| `infra/scripts/build-channel-image.sh` | β-i / β-ii / β-iii build script | unchanged | none |
| `infra/tests/e2e/run-fullstack.sh` | suite count 19 | unchanged | none |
| `pyproject.toml` / API + Discord deps | β-i / β-ii / β-iii dependency closure | unchanged — discord.py already supports `discord.Embed`, no new pip dep | none |
| `services/web/package.json` | β-iii frontend deps | unchanged — INIT-134 ships zero frontend changes | none |
| Migrations runner | Alembic | unchanged; new migration follows the existing chain head | none |

Risk on §9: **none** — gate criterion 9 (no Containerfile changes
expected) holds. Zero Containerfile, build-script, package-manifest, or
build-arg changes.

### 10. Authority grants / permissions

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Permission namespace | INIT-104 / INIT-128 / INIT-131 / β-iii names (`application.{review, claim, route, message, withdraw, reassign, request_interview, waitlist, approve, deny, reactivate}`) | unchanged | none |
| `seed-authority-grants.mjs` / `grant_officer_message_authority` (e2e fixture seeds) | β-iii fixture seeds | unchanged — INIT-134 introduces no new permission name and no new authority issuance path; notification emission is system-side, not user-authorized | none |
| New grants issued by the slice itself | none | none — proposal §6 "Notification emission is a system-side consequence of the accepted submit; it introduces no user-controlled authorization decision and no new public endpoint." | none |
| Notification migration grants (`migrations/versions/wu-029a_notifications.py:229-260`) | INIT-029a-issued seeds | unchanged | none |

Risk on §10: **none** — gate criterion 10 (no authority grants) holds.

### 11. Python module surface

| Symbol | Pre | Post |
|---|---|---|
| `app.api.v1.endpoints.applications.public.submit_public_application_endpoint` | `services/api/app/api/v1/endpoints/applications/public.py:25-47` | unchanged — endpoint body, signature, response model, status code, dependencies, error mapping all preserved |
| `app.services.applications.submit_public_application_with_receipt` | `services/api/app/services/applications.py:839-885` | unchanged signature; body adds `try/except Exception` around the post-commit `emit_application_public_submitted_event` call (proposal §4 / §11). Return value remains the application UUID. |
| `app.services.notifications.emit_application_public_submitted_event` | `services/api/app/services/notifications.py:83-110` | body replaced — payload is built by the new `app.services.application_public_submit_notifications` builder (proposal §3); allowlist tightened (see §2 above). Module import path preserved; existing call site continues to work. |
| `app.services.notifications.APPLICATION_PUBLIC_SUBMITTED_PAYLOAD_ALLOWLIST` | `frozenset({...})` (`services/api/app/services/notifications.py:40-47`) | replaced contents (see §2 above). Symbol kept; no broader rename. |
| `app.services.notification_events.emit` | INIT-029a service | unchanged signature |
| `app.services.notifications_materialize.materialize_event` | INIT-029a service | body extends template substitution to handle `template_json["embed"]` (string-only `Template(...).substitute(context)` for `title` / `description` / `url` / `fields[].name` / `fields[].value`; pass-through for `color: int \| None` and `fields[].inline: bool`); supports event-payload recipient and destination selectors; stores `rendered_embed_json` next to `rendered_title` / `rendered_body`. **No signature change.** Existing rules with no `embed` key continue to materialize identically. (proposal §3 / §5 / §11) |
| `app.repositories.notifications.insert_notification_envelope_on_conflict_do_nothing` | `services/api/app/repositories/notifications.py:210-251` | extends INSERT to include `rendered_embed_json`; preserves on-conflict-do-nothing behavior; row contract widens by one optional key |
| `app.repositories.notifications._ENVELOPE_SELECT` | `services/api/app/repositories/notifications.py:34-63` | adds `rendered_embed_json` to the SELECT projection |
| `app.contracts.notifications.NotificationEnvelopeRead` | `services/api/app/contracts/notifications.py:121-148` | adds optional `rendered_embed_json: DiscordEmbedRead \| None` |
| `app.contracts.notifications.NotificationTemplate` / `NotificationTemplateEmbed` / `NotificationTemplateEmbedField` | n/a | **new** Pydantic models for template JSON validation (proposal §5) |
| `app.contracts.notifications.DiscordEmbedRead` / `DiscordEmbedFieldRead` | n/a | **new** Pydantic read models for envelope embed payload (proposal §5) |
| `app.contracts.notifications.NotificationDeliveryCommand` | unchanged | unchanged |
| `app.services.application_public_submit_notifications` (new module) | n/a | **new** — builds the payload from `ApplicationRead`, applicant Discord id, chapter / global routing, and base URLs (proposal §3 / §4) |
| `app.core.settings.Settings` | `services/api/app/core/settings.py:13-56` | adds `web_public_base_url: str = Field(...)`, plus optional `global_applications_review_channel_id`, `global_application_managers_role_id`, `global_primary_guild_channel_url` |
| `app.handlers.notifications._send_message` (Discord daemon) | `services/discord/app/handlers/notifications.py:28-33` | adds optional `embed=None` kwarg; passes through to `target.send(...)` only when truthy |
| `app.handlers.notifications.deliver_notification` | `services/discord/app/handlers/notifications.py:36-96` | unchanged signature; body builds a `discord.Embed` from `envelope.rendered_embed_json` (when present) before calling `_send_message`; treats malformed embed JSON as definitive failure |
| Direct lifecycle / officer bridge / web detail / β-iii composer / β-iii transition handlers | β-iii | unchanged |
| Existing notification rules / notification dispatcher / DeferredEffects pipeline | INIT-029a | unchanged |

**Edits to existing exports:** notifications module gains additional
template / embed Pydantic exports; existing names
(`NotificationDeliveryCommand`, `NotificationDeliveryError`,
`NotificationDeliveryResult`, `NotificationDeliveryStatus`,
`NotificationEnvelopeRead`, `NotificationEventDraft`,
`NotificationEventRead`, `NotificationGrouping`,
`NotificationMaterializationResult`, `NotificationRule*`,
`NotificationTrigger`, `TemplateRenderError`,
`UnsupportedNotificationTriggerError`,
`AmbiguousNotificationDeliveryError`) are not renamed or removed.

Risk on §11: **none** — every new Python symbol is additive; the only
existing-symbol body changes are the `_send_message` widening (default
`None` keeps callers identical), the `materialize_event` template
substitution extension (rules without `embed` continue to materialize
identically), the `submit_public_application_with_receipt` defensive
wrap (response shape preserved), and the
`emit_application_public_submitted_event` body replacement (allowlist
tightened, payload expanded; the public function name and call shape
are preserved).

## Verdict reasoning

LOW.

1. **Database schema (gate §1)**: one additive nullable column on
   `notification_envelopes` plus two seeded `notification_rules` rows
   for a new event type binding. Zero destructive `ALTER TABLE`, zero
   column drops, zero index changes, zero constraint changes, zero
   table renames. Migration chains linearly off the current head
   `wu_044_application_messages`.
2. **Notification event / template schema (gate §2)**: `application.public_submitted`
   stays a single event type. Two new template names. Zero edits to
   existing template rows. Allowlist tightening removes only
   `applicant_member_id` and the duplicate `discord_user_id`; the
   single existing materializer consumer (no rule currently bound to
   this event) is unaffected. `recipient_discord_user_id` remains the
   canonical applicant DM recipient.
3. **Discord daemon (gate §3)**: handler extension is a default-`None`
   `embed=` kwarg on `_send_message`; the text-only delivery path is
   byte-identical to today, and the existing
   `services/discord/tests/test_notifications.py` cases (nonce
   determinism, malformed recipient/destination definitive failures)
   continue to pass without modification. The new applicant DM rule
   ships **without** an embed, so the DM branch is unchanged.
4. **Public submit (gate §4)**: `POST /api/v1/public/applications`
   route, request body, auth dependencies, response model, success
   status code, and error mapping are byte-identical. The post-commit
   notification emit is hardened via `try/except Exception` so an emit
   failure cannot turn a committed submit into a 5xx — the response
   contract is more stable than today, not less.
5. **Existing tests (gate §5)**: applicant compat (`compat.spec.ts`,
   `test_applicant_discord_pomerium.py`), β-i / β-ii / β-iii officer
   bridge tests (`officer-queue.spec.ts`, `officer-detail.spec.ts`,
   `test_web_officer_applications.py` including the dependency-tree
   guard), and the existing notification / public-submit / discord
   tests continue passing — INIT-134 only **adds** assertions and never
   weakens or removes one.
6. **Pomerium / Authentik (gate §6)**: zero changes. No new route entry,
   no re-ordering, no identity-header change, no Authentik blueprint
   change, no Infisical secret rename.
7. **Required env vars (gate §7)**: the GLOBAL_* trio is optional with
   the gate-specified "missing → no notification fires (logged, not
   error)" semantics. `WEB_PUBLIC_BASE_URL` is a new required env var
   tracked as F-7-A (LOW); the slice atomically updates the only
   active channel's API deployment YAML, and the API boot path raises
   a structured `SettingsConstructionError` listing missing env vars
   so a misconfigured deploy fails loudly rather than silently
   degrading. No silent failure mode; no remote deployment to break.
8. **Chapter config (gate §8)**: zero new chapter columns, zero new
   chapter fields. Reuse of the existing `ChapterDiscordResources`
   dict-based shape with the gate-required "missing key → skipped
   envelope, logged, not error" semantics.
9. **Build pipeline (gate §9)**: zero Containerfile changes, zero
   build-script changes, zero new pip / npm dependency, zero new
   build-arg, zero new dist path.
10. **Authority grants (gate §10)**: zero. Notification emission is
    system-side; no new permission name, no new authority issuance
    path, no new actor kind.

The single tracked finding is **F-7-A**: `WEB_PUBLIC_BASE_URL` is a
new required setting. It is mitigated by atomic YAML wiring in the
same slice and a loud-failure boot path; it does not open a silent
backwards-compatibility hole on existing deployments because the only
existing deployment (the `local` channel) is updated in lockstep with
the migration and the API code change.

Tier 3 (live Humility guild send) remains explicitly out of scope per
proposal §2 Q7 and §8; the local Discord deployment stays at its
existing dry-run posture; the e2e suite uses fixture / mock Discord
delivery and is bolstered by a new live-guild fixture guard
(proposal §7, TG-2b).

Verdict: **LOW**.

SUPPORTED_SURFACE_DONE: plans/risk/init-134-supported-surface.md
