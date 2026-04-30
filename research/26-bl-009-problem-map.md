# BL-009 problem map — officer Discord notification on public submit

Source: BL-009 in `plans/BACKLOG.md`. Both blockers (BL-016
Discord OAuth, BL-019 in-product review surface) are now
resolved.

## What we're building

When a public web submission lands at `POST
/api/public/applications`, fire a Discord embed in the chapter's
`#applications-review` channel @-mentioning the chapter's
application-managers role, linking back to the in-product
detail page.

User-confirmed product direction (per BACKLOG entry):
- Discord embed in `#applications-review` channel.
- Embed format: app_id, support_id, scope, submitted time, form
  version, truncated response preview. Hide synthetic ids.
- @-mention chapter-specific application-managers role.
- PII level A: minimal preview only; full content stays in
  the API.
- "Routes back to application" link → in-product detail
  (`/applications/{id}`, β-ii surface).
- No private Discord thread per application — reviews happen
  in-product.

This slice is the **officer notification**. **Applicant DM**
(BL-020) is closely related but mechanically separable; the
proposal will decide whether to bundle.

## Substrate audit (what exists)

- **Notification event substrate** (INIT-029a):
  - `services/api/app/services/notification_events.py::emit`
  - `services/api/app/services/notifications_materialize.py`
  - `services/api/app/repositories/notification_events.py`
  - `notification_events` table (already in production
    schema).

- **Discord delivery handler**:
  `services/discord/app/handlers/notifications.py::deliver_notification`
  already supports `channel == "dm"` and channel posts via
  `bot.fetch_channel(...)`. Uses nonce-enforcement for
  idempotency.

- **Notification contract**:
  `services/api/app/contracts/notifications.py::NotificationDeliveryCommand`
  with `envelope.channel`, `envelope.rendered_title`,
  `envelope.rendered_body`, `envelope.recipient_discord_id`.

- **Existing emit sites**:
  - `services/api/app/services/notifications.py::publish` (line
    ~94) — generic.
  - `services/api/app/services/ticket_sla.py` — fires
    notifications on SLA breach (line ~243, 293).
  - These are the patterns the new emit site will mirror.

- **Application submit path**:
  `services/api/app/services/applications.py` — `_submit_application`
  or similar. After successful insert + state="queued",
  trigger the notification.

- **Chapter config**:
  - `services/api/app/contracts/chapters.py` — chapter has
    metadata; need to check if `applications_review_channel_id`
    + `application_managers_role_id` already exist as fields.
    Likely need to add.

## Open questions for the proposal

### Q1. Where does the chapter→channel/role mapping live?

Two options:
- **(A) New columns on `chapters` table** (or chapter
  metadata): `applications_review_channel_id` (Discord channel
  snowflake), `application_managers_role_id` (Discord role
  snowflake). Migration needed.
- **(B) Use existing `chapter_role` aggregate** (per substrate
  audit; chapter_role refers to in-product role mapped to
  Discord role per-chapter). Add a "channel binding" alongside.

Option (A) is simpler. Option (B) reuses existing chapter-role
infrastructure but requires extending it to include channel
bindings.

Lock: **(A) new chapter-discord-config table or columns**.
Migration adds two nullable Discord snowflake fields to
chapters (or a sibling `chapter_discord_settings` table if
chapter rows shouldn't grow). Per-chapter; nullable means
"not configured, no notification fires."

### Q2. What about `global` scope applications?

Public submit creates applications at `scope_kind=global`
(per existing INIT-128 contract). There is no chapter to look
up.

Lock: **send to a single global fallback channel** configured
similarly. New env var or singleton config row:
`GLOBAL_APPLICATIONS_REVIEW_CHANNEL_ID` and
`GLOBAL_APPLICATIONS_REVIEW_ROLE_ID`. If missing, no
notification fires (logged, not error).

Or alternatively: **fan out to all chapters' channels** (since
a global application can be claimed by any officer). But
that's noisier. Lock the global-fallback approach.

### Q3. Embed format

Template (Discord embed, NOT raw markdown):
- Title: `New application submission — {scope_label}`
- Description: truncated response preview (Level A PII).
  Strip newlines, max 200 chars. If responses contain
  `application_text`, use that; truncate to first 200 chars.
- Fields:
  - `Application ID`: `{application_id}` (full UUID; not
    sensitive).
  - `Submitted`: `<t:{unix_ts}:R>` (relative time).
  - `Form version`: `{form_version}`.
- URL: `https://web.local.humility.local/applications/{id}`
  (or env-driven web base URL). Clickable embed title.
- Color: blue (per Discord embed convention for "info").

Message content (above the embed): `<@&{role_id}>` to mention
the role.

### Q4. Truncation rules (PII level A)

- Application_text: max 200 chars, replace newlines with
  spaces, suffix with `…` if truncated.
- Character_name: full (it's a chosen handle, not real PII).
- Hide: applicant's real Discord username, email,
  applicant_id (UUID is OK), member UUID.

### Q5. Idempotency

The notification_events substrate already has nonce-based
idempotency. The emit site should use a deterministic event
key (e.g., `application:{id}:public_submit:officer`) so
retries don't double-post.

### Q6. Should we bundle BL-020 (applicant DM)?

The applicant DM uses the SAME notification substrate, just
with `channel="dm"` and `recipient_discord_id={applicant
discord id}`. Mechanically near-identical.

Pros of bundling:
- Both consume the same on-submit emit hookpoint.
- Both need the chapter config field (DM links back to "the
  primary guild channel" per the BACKLOG; for global scope,
  that's the global fallback).
- Cohesive product story.

Cons:
- Doubles the diff. β-i ballooned to 70KB; this could
  similarly grow.
- Two notification events emitted per submit (officer +
  applicant) means two failure modes.

Lock: **bundle BL-009 + BL-020** as INIT-134. Both fire from
the same submit-success hookpoint; both use the existing
notification substrate. The ROUTING templates are different
(channel vs DM, different content).

### Q7. Tier 3 considerations

Per AGENTS.md "Live Server Principle", Discord-visible writes
are Tier 3. This INIT delivers CODE, not Tier 3 actions —
implementation, build, e2e validation are Tier 2. The
proposal must lock:
- E2e tests target a TEST guild, not the live "Humility"
  guild. The e2e infra has Discord test fixtures via the
  existing daemon; verify what's available.
- Production rollout (deploying this code to the live
  server) IS Tier 3 and would be a separate user-approved
  action.

### Q8. Anti-scope

Out of scope for INIT-134:
- Discord-visible side effects on transitions (separate
  follow-up — likely bigger because each transition has
  different routing semantics).
- Private Discord thread per application (user-confirmed:
  reviews stay in-product).
- Applicant DM materialization for officers
  (officer-to-applicant DM via the in-product message
  thread already covered by β-iii).
- Chapter Discord config UI (admin tool for setting channel
  + role IDs — separate slice).
- Notification preferences / opt-out — defer.

## What the proposal must lock

1. Q1 chapter config schema (new columns or sibling table).
2. Q2 global scope fallback.
3. Q3 embed format + URL routing.
4. Q4 truncation rules.
5. Q5 idempotency key.
6. Q6 bundling BL-009 + BL-020.
7. Q7 e2e test guild fixture (verify against existing infra).
8. Q8 anti-scope.

## Diff budget

Estimate ~+800 / -50 net lines:
- Migration: chapter discord config schema (~+80).
- API service: emit on submit success (~+150).
- Notification templates: officer embed + applicant DM
  (~+150).
- Discord daemon: embed-format support (existing notification
  handler may need extension; +100).
- Tests: API + Discord daemon + e2e (~+300).

This may need decomposition. The proposal will recommend.
