# INIT-134 — Shortcut risk gate

**Verdict:** LOW

Scope: BL-009 (officer Discord embed) bundled with BL-020
(applicant Discord DM) on the public-submit hookpoint, riding
the existing `notification_events` substrate.

The shortcut gate inspects whether INIT-134 reuses the
existing notifications substrate end-to-end, locks PII rules,
preserves submit durability under emit failure, and avoids
config/UI/template stubs. Per-shortcut analysis follows.

## S1 — Notification events use the existing `notification_events` substrate

**Choice:** §4 (Notification event schema) and §11 (Reuse) lock
the emit to the existing substrate: `notification_events.emit`
(`services/api/app/services/notification_events.py:32-84`)
called via `emit_application_public_submitted_event`
(`services/api/app/services/notifications.py:83-110`), with
materialization enqueued through the existing
`enqueue_effect("notifications_materialize")` path. §3
explicitly states "do not introduce a second event key system"
and "Reuse event type `application.public_submitted`; do not
create separate `officer` and `applicant` event types."

The proposal expands the existing event payload (replacing the
allowlist contents) rather than minting `application.officer_notify`
and `application.applicant_notify` parallel events; both
templates fire from the same single `application.public_submitted`
event row with `grouping="per_event"` so envelope-level dedup
still applies (`migrations/versions/wu-029a_notifications.py:190-203`).

**Risk:** a parallel "discord_notifications" table or
`discord_send_request` event type would split the audit/replay
trail, double the dispatcher surface, and bypass envelope
idempotency.

**Mitigation:** explicit reuse of `notification_events`,
`notification_envelopes`, `insert_notification_envelope_on_conflict_do_nothing`,
the existing `notifications_materialize` deferred effect, and
the existing `notifications_deliver` deferred effect. New work
is two seeded `notification_rules` rows plus a payload
expansion plus an envelope `rendered_embed_json` column — all
inside the existing schema's degrees of freedom.

**Verdict:** Not a shortcut.

## S2 — Discord daemon embed support extends the existing `deliver_notification`

**Choice:** §3 (Modified files / discord notifications
handler) and §4 (Discord handler extension) lock the embed
delivery into the existing handler:
`services/discord/app/handlers/notifications.py` — extend
`_send_message` to pass `embed=` when `rendered_embed_json` is
present. §11 (Reuse) keeps "Discord delivery nonce/idempotency:
`services/discord/app/handlers/notifications.py:15-33`" and
adds embed support inside the same `deliver_notification`
function. There is no new daemon entrypoint, no second
delivery worker path, and no parallel "embed dispatcher."

The DM and `designated_channel` branches inside
`deliver_notification` are reused verbatim
(`services/discord/app/handlers/notifications.py:45-77`); the
only change is that `_send_message` accepts an optional embed
constructed from `envelope.rendered_embed_json` and passes it
to `target.send(content=..., embed=..., nonce=..., enforce_nonce=True)`.
Nonce derivation (`envelope_nonce(envelope.id)`) is unchanged.

**Risk:** a sibling `deliver_embed_notification` or a
notification-type discriminator that branched at the deferred
effect level would split idempotency/nonce policy and let
embed delivery diverge from text DM delivery on retries.

**Mitigation:** single function, single nonce, single
`enforce_nonce=True` policy. Embed JSON is derived from a new
nullable column on the existing envelope row; absence of
`rendered_embed_json` falls through to the current text-only
behavior used by the SLA path.

**Verdict:** Not a shortcut.

## S3 — PII truncation rules are explicit in the proposal text

**Choice:** §2 (Q4) locks the truncation rules end-to-end and
§4 reiterates them on the payload allowlist:

- Source: `responses["application_text"]`, otherwise the first
  non-empty string response by field order.
- Whitespace normalization: replace newlines and repeated
  whitespace with a single space.
- Cap: 200 characters; append `...` only when truncation occurs.
- `responses["character_name"]` may appear as the Character
  field (chosen handle, not real PII).
- Excluded: Discord username, email, `applicant_id`, member
  UUID (`applicant_member_id`), full response JSON, synthetic
  / public-intake identifiers.

§4 codifies these exclusions by replacing
`APPLICATION_PUBLIC_SUBMITTED_PAYLOAD_ALLOWLIST` rather than
widening it: `applicant_member_id` and `discord_user_id` are
removed from the allowlist; `recipient_discord_user_id` stays
as the sole Discord recipient id; only the safe rendered
notification fields (`response_preview`, `character_name`,
`scope_label`, `submitted_iso`, `application_url`, etc.) are
added. F-1 in §10 explicitly locks this hygiene pass.

§7 names the tests that prevent regression:
`payload excludes full responses, applicant_id,
applicant_member_id, and applicant username/email`
(group=TG-1).

**Risk:** "we'll figure out PII later" wording would either
ship the full responses blob into Discord or leak applicant
UUIDs / Discord usernames into the embed.

**Mitigation:** every truncation rule is locked with a
character cap, normalization rule, source-field fallback rule,
and a denylist; the allowlist replacement is non-additive
(removes old over-broad fields) and the API-side test asserts
the deny-list at the event-payload boundary, not just the
embed.

**Verdict:** Not a shortcut.

## S4 — Idempotency uses notification_events' built-in nonce/dedup pattern

**Choice:** §2 (Q5) explicitly says "Do not introduce a second
event key system." Idempotency is layered on the existing
substrate:

1. INIT-128 already emits one `application.public_submitted`
   event after `_submit_application_internal` returns
   (`services/api/app/services/applications.py:870-885`); a
   resubmit of the same `client_application_id` collapses on
   the upstream submit dedup, not in notifications.
2. Materialization deduplicates per-event envelopes through
   `uq_notification_envelopes__per_event` and
   `insert_notification_envelope_on_conflict_do_nothing`
   (`migrations/versions/wu-029a_notifications.py:190-203`,
   `services/api/app/repositories/notifications.py:210-251`),
   so re-running the materialize effect produces zero new
   envelopes.
3. Discord delivery derives a deterministic nonce from the
   envelope id and sets `enforce_nonce=True`
   (`services/discord/app/handlers/notifications.py:15-33`),
   so a re-run of the deliver effect is collapsed by Discord's
   nonce dedup.

Both new rules use `grouping="per_event"`, producing at most
one officer envelope and one applicant envelope per submit.
§7 includes "Replaying the same event does not create
duplicate officer or applicant envelopes" as a named
materialization test (group=TG-2).

**Risk:** a "we'll add a `discord_message_idempotency_key`
column on applications" or "fire-and-hope the bot doesn't
double-post" approach would break under deferred-effect
retries (which are the substrate's stated retry path) and
under restart-driven materialize replays.

**Mitigation:** three-layer idempotency (per-event envelope
unique index, nonce-enforced Discord send, deterministic
deferred-effect idempotency keys
`notifications:materialize:{event_id}` and
`notifications:deliver:{envelope_id}`) all already exist;
INIT-134 reuses them without modification.

**Verdict:** Not a shortcut.

## S5 — Chapter config: existing JSONB resource maps, not env vars or hardcoded constants

**Choice:** §2 (Q1) and §5 (Chapter Discord config Pydantic
shape) lock chapter config to the existing
`ChapterDiscordResources` JSONB shape on the chapters table:

```
role_ids:    {"application_managers": "<role-snowflake>"}
channel_ids: {"applications_review": "<channel-snowflake>"}
```

The contract already exists
(`services/api/app/contracts/chapters.py:39-43`), the column
already exists as JSONB
(`migrations/versions/wu-019_chapter_lifecycle.py:33-39`), and
the chapter service merges resource updates rather than
replacing them
(`services/api/app/services/chapters.py:282-292`). §11
(Delete or avoid) explicitly says "Do not add chapter config
columns duplicating `discord_resources`."

The new Alembic migration `wu-045` does NOT add chapter
columns; it adds `rendered_embed_json` to
`notification_envelopes` and seeds two `notification_rules`
rows. The chapter side is pure JSONB-key extension, which the
existing channel/role-id-shape supports as designed.

There is no env-var-only chapter mapping (chapter config does
not live in env vars), no in-code dict from chapter UUID to
channel id, no parallel `chapter_discord_settings` table, and
no migration that copies env var values into the table.

**Risk:** a "for now, hardcode `chapter_id ->
channel_id` in `settings.py`" or "ship a `chapter_channel_map.yaml`
in gitops we read at boot" shortcut would freeze the
per-tenant Discord routing into config-file deploys instead of
data, and force a redeploy for every new chapter.

**Mitigation:** chapter routing reads from the existing JSONB
columns at materialize time via `application_public_submit_notifications`;
the only constants live for global scope, where there is no
chapter row to read from.

**Verdict:** Not a shortcut.

## S6 — Global scope fallback uses real settings, not magic strings

**Choice:** §2 (Q2), §3 (Modified files / settings), and §4
(Notification event schema) lock the global fallback to three
explicit settings fields:

- `global_applications_review_channel_id`
- `global_application_managers_role_id`
- `global_primary_guild_channel_url`

`web_public_base_url: str = Field(...)` is required (no Python
default); the three global-fallback fields are likewise wired
through `services/api/app/core/settings.py` and surfaced into
`api-deployment.yaml`. Local e2e values come from
`e2e-fixtures-infisicalsecret.yaml` rather than literal
strings in Python.

§7's live-guild fixture-guard test (TG-2b) goes one further:
the test asserts that `global_applications_review_channel_id`,
`global_application_managers_role_id`, and the chapter's
fixture role id are NOT equal to known-production Discord ids,
including the live Humility guild id `900000000000000001`
(F-3 in §10). This is real config — typed, settable per
channel, fixture-overridable, and guarded against bleed into
prod ids — not a magic-string fallback wired into Python
constants.

Missing global officer config does not panic: it produces an
event that materialization records as a skipped envelope with
a specific reason (`destination_missing` /
`recipient_unresolved`), and the public submit endpoint still
returns success. §7 names the test for that path explicitly:
"Missing event-payload destination/recipient fields produce
skipped envelopes and no delivery effect."

**Risk:** hardcoding `if scope_kind == "global": channel = "12345..."`
into `notifications_materialize.py` would couple the global
route to source code; "default to the first chapter's channel"
would either fan out to a chapter that should not see global
applications or pick a non-deterministic chapter.

**Mitigation:** typed pydantic settings with no Python
default, fixture override via Infisical secret bundle, e2e
guard test that fixtures are not prod ids, and explicit
skipped-envelope path when fallback values are missing.

**Verdict:** Not a shortcut.

## S7 — E2e exercises real `notification_events` creation and full envelope path

**Choice:** §7 (E2e) extends `infra/tests/e2e/tests/19-web-ui.sh`
after `assert_public_submit_persisted` to query local
Postgres for:

- One `notification_events` row with
  `event_type='application.public_submitted'` for the
  submitted application (NOT just an `applications` row).
- Two `notification_envelopes` rows: one `designated_channel`
  with non-null `rendered_embed_json`, one `dm` with the
  fixture applicant Discord id.
- Delivery effects queued for both envelopes through the
  existing `deferred_effects` substrate (or, optionally, a
  mock worker actually executes the delivery effect and
  asserts the rendered embed).

This goes past "verify the SQL row" — the test asserts the
full chain: `notification_events` insert -> materialize
deferred effect -> envelope insert with rendered embed JSON
-> deliver deferred effect. The Discord roundtrip is
asserted via the dry-run/mock daemon, not skipped: §7 says
"optional mock Discord delivery may assert the delivered
embed, but must use the dry-run/mock/test guild path, not
live Humility." The Discord-daemon TG-3 unit tests separately
assert that designated-channel embed delivery calls
`fetch_channel`, sends role-mention content, passes a Discord
embed object, and preserves nonce/enforce_nonce.

§2 (Q7) and §10 (F-3) lock the live-guild guard: e2e must
NOT send to guild `900000000000000001`; the fixture-guard
contract test (TG-2b) prevents fixture drift into prod ids.

**Risk:** "assert the SQL row but skip the Discord
roundtrip" would let the embed renderer ship broken JSON, or
let the daemon's new `embed=` argument silently no-op, with
nothing flagging it before a Tier 3 production cutover.

**Mitigation:** the e2e leg asserts envelope shape *and*
rendered-embed JSON shape; the daemon-unit leg asserts the
exact `target.send(content=..., embed=..., nonce=...,
enforce_nonce=True)` call against the dry-run/mock guild;
fixture guard prevents bleed; and a malformed-embed-JSON case
is asserted to raise a definitive `NotificationDeliveryError`.

**Verdict:** Not a shortcut.

## S8 — Submit-side emit isolated in try/except so notification failure does not roll back the submit

**Choice:** §4 (Emit hookpoint in submit service), §10
(F/S8 in round-2 self-review), and §11 (Reuse) lock the
defensive isolation contract:

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
```

The contract is documented at three points:

- §3 (`services/api/app/services/applications.py`) — "wrap the
  emit side effect in defensive `try/except Exception`
  isolation so notification failures cannot turn a durably
  committed submit into a public 5xx."
- §4 — full code preview as quoted above, including the
  `logger.exception(...)` call and the explicit "Do NOT
  re-raise" comment.
- §7 (TG-1 named risk
  `public_submit_notification_event_payload`) — "If
  `notification_events.emit` raises, the public submit
  endpoint still returns its normal success response with the
  application id, and the application row exists in Postgres.
  The test mocks the emit call to raise and asserts no 5xx
  propagates after the submit commit."

This is the round-2 fix for the prior R1 self-review's
medium-risk S8 finding (§10), and it is not deferred — it is
called out as a contract requirement of the submit hookpoint
with an API test that asserts no 5xx leaks through.

**Risk:** without the wrap, a notification-substrate
exception (DB hiccup during enqueue_effect, NotificationRule
fetch failure, payload allowlist regression) would propagate
out of `submit_public_application_with_receipt` after the
application row was already committed, surfacing a public 5xx
to the applicant who already has a queued application —
the exact "user gets an error after their submission worked"
trap the BACKLOG calls out.

**Mitigation:** the wrap is locked at the contract level
(proposal text), at the implementation level (exact code
preview), and at the test level (mocked emit raise must not
produce a 5xx). The `logger.exception(...)` call ensures the
failure is observable; operators retain the ability to
re-trigger materialization via the normal materialize
deferred effect path.

**Verdict:** Not a shortcut — the prior MEDIUM is closed.

## S9 — Chapter Discord config has no "we'll add the UI later" stub

**Choice:** §8 (Anti-scope) and §11 (Delete or avoid)
explicitly hold the line: "No chapter Discord config UI; this
slice reads existing resource maps/settings only" and
"`Future BL candidates: ... admin UI for chapter Discord
resources, ...`". The configuration channels are:

- Per-chapter: write to `chapters.discord_resources` JSONB
  via the existing `PATCH /api/v1/chapters/{id}` /
  service-level merge path
  (`services/api/app/services/chapters.py:282-292`) that
  already merges resource maps. This is not a UI stub — the
  existing chapter maintenance path already supports
  arbitrary key writes into the resource map; INIT-134 reads
  two specific keys from it.
- Global fallback: settings env vars in
  `services/api/app/core/settings.py`, sourced from
  Infisical/secret bundles in deployed channels and from
  `e2e-fixtures-infisicalsecret.yaml` locally.

There is no "and later we'll add an officer Slack-connect-
style modal in the SPA"; the proposal fully scopes config to
data the system already accepts (JSONB merge, settings
fields). The gitops/seed/migration path covers production
config — chapter-row writes by way of the existing chapter
admin tooling, settings by way of the deployed channel's
secret bundle.

**Risk:** if §11 punted "config UI is INIT-XYZ" while
shipping a stub `discord_resources_admin.tsx` page or a
`POST /api/v1/web/admin/chapter-discord-config` placeholder,
the slice would either ship dead code or block merging the
SPA work behind an unfinished admin route.

**Mitigation:** anti-scope is concrete; the data path is the
existing chapter resource-merge service plus settings; no
admin route or SPA page is added; e2e fixture wiring covers
the local-mode case directly with no UI requirement.

**Verdict:** Not a shortcut.

## S10 — BL-009 and BL-020 templates are distinct (officer embed vs applicant DM), not a single template with a `recipient_kind` switch

**Choice:** §3 (Migration) seeds two notification rules with
distinct identities, channels, and templates:

- `application_public_submitted_officer_review`
  - channel: `designated_channel`
  - recipients: event-payload channel/role selector from
    `officer_review_channel_id` + `application_managers_role_id`
  - body/content: `<@&{application_managers_role_id}>`
  - embed: title, URL, Level A preview, Application ID,
    Scope, Submitted, Form version, Support ID, Character
- `application_public_submitted_applicant_dm`
  - channel: `dm`
  - recipients: event-payload Discord user selector from
    `recipient_discord_user_id`
  - body: receipt text plus `${payload_primary_guild_channel_url}`
  - no embed

§3 (Notification templates) and §11 (Reuse) reinforce this:
the two rules are independent rows, with independent recipient
selectors and independent template_json payloads. The
materializer treats them as two independent rule rows
(`list_enabled_rules_for_event` returns both; per-rule
processing already exists), and per-event grouping yields
one envelope per rule.

A `recipient_kind` switch was rejected by Q6 in the problem
map ("Mechanically near-identical" but "two notification
events emitted per submit (officer + applicant) means two
failure modes" — bundling at the rule level, not at the
template level, isolates each delivery's failure path). The
proposal codifies this: officer failure does not block
applicant DM, applicant DM failure does not block officer
embed, and missing global config skips one envelope without
affecting the other.

**Risk:** a single template with branching (e.g.,
`if recipient_kind == "officer": render embed else: render
dm text`) would couple two unrelated failure surfaces, force
the materializer to encode UI-style flow logic, and make the
seeded `notification_rules` row ambiguous (one row, two
possible deliveries — breaking per-event envelope dedup since
both branches share an envelope key).

**Mitigation:** two distinct rules, two distinct templates,
two distinct channels (designated vs dm), two distinct
recipient selectors, two independent envelopes (officer +
applicant), independent skipped-envelope reasons, independent
delivery failure handling. §7 names tests for both rule rows
separately (TG-2 covers officer rule and applicant rule
distinctly).

**Verdict:** Not a shortcut.

## Verdict reasoning

INIT-134 ships exactly the contour the gate watches for:

- One existing event type (`application.public_submitted`)
  reused; no second event-key system.
- One existing Discord delivery handler extended with an
  `embed=` argument; no second daemon path.
- PII rules locked at the source-field level, the
  truncation-cap level, the normalization level, and the
  payload-allowlist level — with the allowlist explicitly
  replaced (not widened) so that removed fields cannot leak
  by accident.
- Idempotency layered on the substrate's existing per-event
  envelope unique index plus deterministic envelope-id-derived
  Discord nonces; no parallel idempotency table.
- Chapter routing via the existing JSONB resource map; no
  hardcoded constants and no parallel chapter table.
- Global fallback via typed pydantic settings fields with
  required `web_public_base_url: str = Field(...)` and a
  fixture-guard test that prevents bleed into the live
  Humility guild id; no magic strings.
- E2e exercises full `notification_events` -> envelope ->
  deliver path with assertions on the rendered embed JSON
  shape, daemon delivery call (mocked), and a live-guild
  guard; no SQL-only verification.
- Submit-side emit wrapped in `try/except Exception` with
  `logger.exception(...)` and explicit "do not re-raise"
  comment; an API test asserts no 5xx propagates after a
  raised emit. Closes the prior R1 MEDIUM finding.
- Chapter config is read-only-here; the existing chapter
  resource-merge path plus deployed settings bundles cover
  production writes; no UI stub.
- BL-009 and BL-020 are two distinct seeded notification
  rules with independent channels, recipients, templates,
  and envelopes — no `recipient_kind` switch.

Verdict: LOW.

SHORTCUT_DONE: plans/risk/init-134-shortcut.md
