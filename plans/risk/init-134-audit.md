# INIT-134 audit — public-submit Discord notifications (BL-009 + BL-020)

Source: `proposals/16-init-134-discord-notifications.md`.
Round: R2 audit gate.

## Verdict: LOW (proceed with three minor finding fixes folded in)

The proposal locks every Tier-3-adjacent invariant the gate
asks for: post-commit emit isolation, PII-A redaction,
per-event idempotency, system-side notification side
effect, nullable chapter routing, settings-driven global
fallback, env-var web URL, mock/fixture-only e2e Discord,
explicit Discord-handler embed extension, and
receipt-bound applicant identity. Three findings (F-1..F-3)
are below — all are tightenings, none invalidate the slice.

## Check-by-check findings

### 1. Hookpoint: emit AFTER successful submit + commit, never on failure paths — PASS

`submit_public_application_with_receipt`
(`services/api/app/services/applications.py:839-885`) calls
`_submit_application_internal` first; that helper opens its
own `db.transaction()` and commits the application row
(submit + route) before returning. The emit call at
`applications.py:876-884` runs only when the submit helper
returned successfully — any duplicate, validation, or
authority error raised inside the helper short-circuits
before the emit line. The proposal §3/§4/§11 also locks a
defensive `try/except Exception` wrapper around the emit so
a notification-side raise cannot turn the durably
committed submit into a public 5xx. Test coverage for the
raise path is mandated in §7. The new
`application_public_submit_notifications.emit_*` body and
`notification_events.emit` open a separate transaction
(`notification_events.py:83`) so the submit row is durable
before any notification I/O — failure isolation is
mechanical, not just defensive coding.

### 2. PII Level A truncation rules — PASS

Final allowlist (proposal §4) keeps only:
`application_id`, `support_id`,
`recipient_discord_user_id`, `scope_kind`, `scope_id`,
`scope_label`, `submitted_unix_ts`, `submitted_iso`,
`form_version`, `character_name`, `response_preview`,
`application_url`, `officer_review_channel_id`,
`application_managers_role_id`,
`application_managers_role_mention`,
`primary_guild_channel_url`.

The current `APPLICATION_PUBLIC_SUBMITTED_PAYLOAD_ALLOWLIST`
in `services/api/app/services/notifications.py:40-47` still
contains `applicant_member_id` and a duplicated
`discord_user_id`. The proposal §3 + §4 + §11 + R-2 F-1
explicitly require *replacement* (not widening) of that
allowlist, removing both keys. The audit gate's
"no member UUID exposure beyond `applicant_id` (UUID, not
sensitive)" criterion is satisfied — the proposal is
strictly tighter, excluding even `applicant_id` /
`applicant_member_id` from the rendered payload entirely.

`recipient_discord_user_id` is an opaque snowflake routing
key for the DM only; it never substitutes into the officer
embed (officer template fields per §3 are: title, URL,
Level A preview, Application ID, Scope, Submitted, Form
version, Support ID, Character — no recipient id rendered).
Real Discord username and email never enter the payload.

`response_preview` is normalised whitespace, ≤200 chars,
sourced from `responses["application_text"]` else first
non-empty string response, with `…` suffix on truncation
(§3 Q4 + problem-map Q4) — Level A.

### 3. Idempotency — PASS

Proposal §2 Q5 reuses the existing two-layer idempotency:

- One `application.public_submitted` event per submit
  (single emit hookpoint). Replaying the event id through
  `materialize_event` is safe because envelope inserts go
  through `insert_notification_envelope_on_conflict_do_nothing`
  with `uq_notification_envelopes__per_event` on
  `(rule_id, source_event_id)` for `grouping="per_event"`
  (`migrations/versions/wu-029a_notifications.py:190-203`,
  `services/api/app/services/notifications_materialize.py:200`).
- Discord delivery uses a deterministic
  `envelope_nonce(envelope.id)` + `enforce_nonce=True`
  (`services/discord/app/handlers/notifications.py:15-33`),
  so retry of the same envelope short-circuits at Discord
  itself.

Both rules are `grouping="per_event"`, so at most one
officer envelope and one applicant envelope per submit
event. No new key system introduced.

### 4. Authorization / actor — PASS with FINDING F-1 (minor)

The public submit endpoint (`public.py:25-47`) is
unchanged: receipt verify → public-intake authz →
`submit_public_application_with_receipt`. The submit
service still resolves a real Discord member from the
verified `discord_user_id` and records the user-actor for
the *submit row*. Notification emission introduces no new
public endpoint and no user-controlled authz branch.

**F-1 (minor): emit carries the applicant user actor, not a
system actor.** `applications.py:869` constructs
`actor = ActorIdentity(actor_kind="user", actor_id=str(member.id))`
and threads it into
`emit_application_public_submitted_event(... actor=actor ...)`
(`applications.py:883`), which forwards it into
`notification_events.emit` (`notifications.py:107`). The
`actor` parameter is currently unused in `emit`
(`notification_events.py:36` — `# noqa: ARG001 - reserved
for worker-attribution parity`), so today there is no leak
to disk. But the proposal does not lock this. If a future
change wires `actor` into the persisted notification event
row or the deferred-effect actor field, the applicant's
member id will silently start appearing as the actor of a
*system-side notification action*, against the audit
gate's "emit is system-actor; no actor leakage from
applicant flow" intent.

Fix: in `emit_application_public_submitted_event` (or its
new `application_public_submit_notifications` callsite),
pass an explicit
`ActorIdentity(actor_kind="service", actor_id="notifications")`
(or the existing system-actor convention used elsewhere in
the codebase) into `notification_events.emit`. The submit
row's actor stays the applicant — only the notification
event's actor becomes system. Add a one-line test asserting
the emit call receives a service actor.

### 5. Chapter config schema (nullable, missing = skip) — PASS

Proposal §2 Q1 reuses
`ChapterDiscordResources.channel_ids["applications_review"]`
and `role_ids["application_managers"]`
(`services/api/app/contracts/chapters.py:39-43`). Both
maps are `dict[str, str]` with empty default factories,
i.e. nullable by absence — no migration needed. Missing
keys produce empty payload entries, which the materializer
maps to `destination_missing` /`recipient_unresolved`
skipped envelopes via `_resolve_destination` /
`_resolve_recipients`
(`notifications_materialize.py:125-133`,
`notifications_materialize.py:77-122`). No error path; the
submit endpoint is unaffected. Anti-duplicate-source: §3
explicitly forbids new chapter columns shadowing
`discord_resources`.

### 6. Global scope fallback — PASS with FINDING F-2 (minor)

Proposal §2 Q2 routes global submissions through three new
settings: `global_applications_review_channel_id`,
`global_application_managers_role_id`,
`global_primary_guild_channel_url`. §3 + §11 lock that
missing officer channel/role yields a skipped officer
envelope and missing applicant guild URL "skips the
applicant DM". §3 names `web_public_base_url: str =
Field(...)` as required (no Python default) — but the
proposal does not state the optionality of the *global_\**
settings.

**F-2 (minor): lock global_\* settings as `Optional[str] =
None`, not `Field(...)`.** If the new global routing
settings are declared `str = Field(...)`, missing config
becomes a startup crash, contradicting Q2's "missing
config = no notification fires (not error)" lock and the
audit gate's "missing global config = no notification
(not error)". Inverse to F-2 in §10 R-2 (which is about
`web_public_base_url` defaulting), this finding is about
the global-routing settings specifically. State in §3 +
§5 + §11:

- `global_applications_review_channel_id: str | None = None`
- `global_application_managers_role_id: str | None = None`
- `global_primary_guild_channel_url: str | None = None`

…and add the corresponding "missing global officer config
materializes a skipped envelope, no exception" component
test (already implied by §7 but should explicitly cover
*all three* global settings being None at the same time).

**Sub-finding F-2b (minor): "skip applicant DM if guild URL
missing" is not mechanically enforced.** The materializer
skip paths are destination-based and recipient-based; an
empty `${payload_primary_guild_channel_url}` substitution
would still produce a non-empty body (the receipt text)
and a non-skipped DM. Either:

(a) Add an explicit skip rule keyed on a new payload field
    `applicant_dm_enabled: bool` set false when the guild
    URL is empty, plumbed through the recipient resolver
    or a new event-payload-driven skip selector; or
(b) Soften the proposal lock from "skips the applicant DM"
    to "renders the receipt text without the guild URL
    line" — and update the test plan accordingly.

Recommend (a) — keeps the BACKLOG/problem-map promise that
"missing config = silence", not "partially configured DM".

### 7. URL routing / env-var indirection — PASS

Proposal §3 (settings) + §4 (Web URL routing) + §11 R-2
F-2 lock `web_public_base_url: str = Field(...)` as
*required* settings input with no Python-level default. No
`https://web.local.humility.local/...` literal lives in
Python. Tests provide the value through fixture settings;
local k8s deploy gets it from the e2e fixture infisical
secret (§3 modified files + e2e wiring). Embed URL is built
as `web_public_base_url.rstrip("/") + "/applications/{id}"`,
matching the existing TanStack route at
`services/web/src/app/router.tsx:85-92`. The web detail
route is already protected by the officer bridge from
β-i, so no new web endpoint is added.

### 8. E2e: TEST fixture/mock guild only, never live Humility — PASS

Proposal §2 Q7 + §3 + §7 + §10 R-2 F-3 lock:

- E2e extends `infra/tests/e2e/tests/19-web-ui.sh` to query
  local Postgres for `notification_events` rows and
  materialized envelopes. **No Discord live send.** Discord
  daemon stays in dry-run / mock posture
  (`gitops/channels/local/applications/server-manager/discord-deployment.yaml:45-46`).
- A new defense-in-depth contract test
  (`group=TG-2b; named_risk=live_guild_fixture_guard`)
  loads chapter Discord config + global fallback fixtures
  and fails if any configured channel/role/guild id equals
  the live Humility guild id `900000000000000001` or any
  recorded production application-review channel/role id.
- Production rollout is explicitly Tier 3 and out of scope.

`infra/tests/e2e/tests/19-web-ui.sh` already plumbs the
applicant Discord id through
`server-manager-e2e-fixtures` (lines 196-210); §3 adds
sibling fixture entries for the channel/role/guild URL.
None of the existing fixture wiring touches the live
guild.

### 9. Discord daemon embed support, no overflow — PASS

Current `_send_message`
(`services/discord/app/handlers/notifications.py:28-33`)
sends `content` only. Proposal §3 + §4 + §7 lock:

- Extend `_send_message` (and `deliver_notification`'s
  designated-channel branch) to call
  `target.send(content=..., embed=..., nonce=..., enforce_nonce=True)`
  when `envelope.rendered_embed_json` is set; otherwise
  current text-only behaviour is unchanged.
- Add `rendered_embed_json` to `NotificationEnvelopeRead`
  and to the repository select/insert columns next to
  `rendered_title` / `rendered_body`.
- Malformed embed JSON raises a definitive
  `NotificationDeliveryError` (template/config fault); the
  transient-failure semantics for Discord API errors are
  unchanged (`notifications.py:83-89`).
- Daemon test asserts that DM-without-embed still sends
  text content and preserves nonce behaviour — i.e. no
  overflow into the DM path, no overflow into the
  thread-out-of-scope branch.

The change is additive and gated on
`rendered_embed_json is not None`. The DM path
(`channel == "dm"`) does not get an embed, matching the
template lock (`application_public_submitted_applicant_dm`
has `body` only, no embed).

### 10. BL-020 applicant DM — applicant identity from receipt, not spoofable — PASS

The applicant Discord identity flows:

`POST /api/v1/public/applications`
→ `verify_applicant_receipt` (HMAC-signed receipt) returns
   `DiscordIdentity.discord_user_id`
   (`public.py:32`)
→ `submit_public_application_with_receipt(... discord_user_id=identity.discord_user_id)`
   (`public.py:37-41`)
→ `member = await resolve_or_create_real_discord_member(db, discord_user_id=discord_user_id)`
   (`applications.py:859-862`)
→ event payload `recipient_discord_user_id = discord_user_id`
   (current `notifications.py:104`, preserved by §4).

The applicant's form `responses` are validated separately
and never used to derive the recipient. The
`PublicApplicationSubmission` body has no Discord-identity
field (`public.py` body type), so a malicious applicant
cannot inject a recipient id distinct from the receipt
subject. The existing test
`services/api/tests/test_public_intake_submit.py:91-170`
already asserts the event targets the receipt Discord
user; the new assertions in §7 keep that invariant.

The applicant DM is also not used as a *return channel*
for officer messages (§8: "No officer-to-applicant DM
flow") — DM is one-shot receipt only — so there is no
secondary spoofing surface.

## Side checks (Tier-3-adjacent hygiene)

- §7 "live-guild fixture guard" test (TG-2b) is the
  belt-and-braces check; it is the only mechanical
  prevention against a misconfigured fixture pointing at
  the live Humility guild. Recommend it be required, not
  optional, and run in pre-merge CI (already implied by §7
  test list — confirm it is wired into the API test
  suite, not gated behind an opt-in marker).
- Discord daemon stays dry-run by default in local; this
  must remain true in any CI environment that runs e2e.
  No proposal change, just a reminder for the
  reviewer / runner.

## Required fixes before merge (delta from R-2)

1. **F-1**: emit a system actor, not the applicant user
   actor. Update
   `application_public_submit_notifications` (or
   `emit_application_public_submitted_event`) to pass
   `ActorIdentity(actor_kind="service", actor_id="notifications")`
   into `notification_events.emit`. Add a unit test
   asserting the actor on the emit call.
2. **F-2**: declare the three new global routing settings
   as `str | None = None`, not `Field(...)`. Add a
   component test that all three None → skipped officer
   envelope + skipped DM (per F-2b decision).
3. **F-2b**: pick (a) explicit applicant-DM skip on
   missing guild URL or (b) soften the proposal lock to
   "render without URL". Update §2 Q2 + §3 templates +
   §7 tests accordingly.

None of these block the slice's overall LOW verdict; all
three are tightenings to the existing locked design and
keep within the +950/-20 diff budget.

## Conclusion

Audit risk: **LOW**. Scope risk: LOW (slice still bounded
to public-submit notifications, two templates, one
optional envelope embed field, settings/fixture wiring,
local e2e rows). Shortcut risk: LOW (post-commit emit
isolation explicit and tested). Supported-surface risk:
LOW (no public contract change; no live Discord delivery;
daemon embed extension is additive and gated).

Proceed once F-1, F-2, and F-2b are folded into the
proposal text and the linked test plan.
