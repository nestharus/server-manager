# INIT-134 — Scope risk gate

**Verdict:** LOW

INIT-134 bundles BL-009 (officer Discord embed) and BL-020
(applicant Discord DM) as the public-submit notification slice.
Per problem map Q6 and proposal §2 Q6 the bundle is justified:
both fire from the same post-commit emit hookpoint in
`submit_public_application_with_receipt`, both materialize
through the existing INIT-029a notification substrate, both
deliver via the same Discord daemon handler with deterministic
nonce idempotency. Diff budget (`+950 / -20`, hard cap at
1500) is well below the split threshold, and the proposal
explicitly names the fall-back split (BL-020 DM first on
text-only path, then BL-009 officer embed) if that cap is hit.

## Gate checks

### 1. Migration is exactly the chapter Discord config (channel + role IDs)

**PASS — with intentional substrate change instead.** The proposal
deliberately diverges from the problem map's Q1 sketch (which
floated new chapter columns or a sibling table). Per §2 Q1, the
chapter→channel/role mapping reuses the existing
`ChapterDiscordResources` JSONB shape (verified at
`services/api/app/contracts/chapters.py:60,130`), reading
`channel_ids["applications_review"]` and
`role_ids["application_managers"]`. **No chapter table change.**

The actual migration (`wu-045_application_public_submit_notifications.py`,
chained to current head `wu-044_application_messages` — verified
present) does only two things:

- Adds nullable `rendered_embed_json JSONB` to `notification_envelopes`
  (substrate extension to carry pre-rendered Discord embed).
- Seeds two `notification_rules` rows for `application.public_submitted`.

**No changes to `applications`, `members`, `chapters`,
`notification_events`, indexes, grants, or any other table.**
This is a tighter migration footprint than the problem map's
hypothetical chapter-columns approach, and it eliminates a
duplicate source of truth for Discord resource mapping.

### 2. Submit path: only an emit added; no edits to transition logic, applicant flow, public submit semantics

**PASS.** §3 and §11 keep the emit hookpoint at the existing
post-commit location (`services/api/app/services/applications.py:870-885`).
The only change at the submit hookpoint is:

- Pass enough `ApplicationRead` data to render officer + applicant
  payloads (data flow change, not control flow).
- Wrap the emit call in `try/except Exception` with `logger.exception`
  and **no re-raise**, so a notification failure cannot turn a
  durably committed submit into a public 5xx (S8 lock from the
  round-1 self-review).

No edits to:
- `_submit_application_internal` body / state-machine.
- Applicant resolution / member creation flow.
- Public submit endpoint auth (`verify_applicant_receipt` unchanged
  per §6).
- `services/discord/app/handlers/application_submission.py` (the
  Discord-side submit flow — explicitly avoided per §4).
- Transition machinery (out of scope per §8; explicitly deferred
  alongside the BL-009 / BL-020 callouts in the β-iii scope verdict).

### 3. Notification template additions: only the two new templates

**PASS.** §3 seeds exactly:

- `application_public_submitted_officer_review` (channel:
  `designated_channel`, grouping: `per_event`, embed template).
- `application_public_submitted_applicant_dm` (channel: `dm`,
  grouping: `per_event`, text receipt template).

No third template, no template edits to existing rules, no
schema for template variants. The templates are deterministic
seeds in the migration (not service-level mutations).

### 4. Discord daemon: only embed-rendering extension; no changes to other handlers

**PASS.** §3 / §4 / §11 limit daemon changes to `_send_message`
in `services/discord/app/handlers/notifications.py`: pass
`embed=` when `rendered_embed_json` is present, plus a
definitive-failure branch for malformed embed JSON.
**Existing DM and designated-channel routing are reused
verbatim**; nonce / `enforce_nonce` semantics preserved
(§7 Discord daemon test asserts this). No edits to other
Discord handlers (`application_submission`, lifecycle handlers,
moderation, etc.).

### 5. No new permissions, no new actor kinds, no Pomerium changes, no auth changes

**PASS.** §6 explicitly preserves public submit auth:
`verify_applicant_receipt` unchanged, no new public endpoint,
no new authorization branch in materialization (string-only
template substitution in §5 / §11 confirms this — embed
rendering adds no auth decision). No new permission name
appears anywhere in §3, §4, §6, or §11. No new actor kind:
the submit/route actor remains the resolved Discord member
per existing service code. No new Pomerium prefix or policy
change is listed in §3's modified files.

### 6. Bundling BL-009 + BL-020 justified per problem map Q6

**PASS.** Bundling justification is explicit in both required
documents:

- Problem map Q6 (`research/26-bl-009-problem-map.md:142-164`):
  "applicant DM uses the SAME notification substrate, just with
  `channel="dm"`... Mechanically near-identical." Locks bundle.
- Proposal §2 Q6: "The existing public submit event already
  carries `recipient_discord_user_id` from the applicant
  receipt... Splitting would duplicate submit-hook, payload,
  materialization, and e2e work for little risk reduction."

Diff budget §9 estimates `+950 / -20` net, well under the 1500
ceiling. The proposal also documents the split fall-back: if
implementation exceeds 1500 net or requires a second delivery
worker path, ship BL-020 applicant DM first on the text-only
DM path, then BL-009 officer embed as the follow-up. **No
split recommendation needed at proposal time.**

## In scope (justified)

- **Migration `wu-045`:** nullable `rendered_embed_json JSONB`
  on `notification_envelopes` + two seeded `notification_rules`
  rows. No table additions; no chapter table touched.
- **Notification contracts** (`services/api/app/contracts/notifications.py`):
  add `NotificationTemplate`, `NotificationTemplateEmbed`,
  `NotificationTemplateEmbedField`, optional
  `NotificationEnvelopeRead.rendered_embed_json`. Existing
  `NotificationDeliveryCommand` envelope shape preserved.
- **Allowlist replacement** (`services/api/app/services/notifications.py`):
  `APPLICATION_PUBLIC_SUBMITTED_PAYLOAD_ALLOWLIST` is *replaced*
  (not widened): drop `applicant_member_id` and `discord_user_id`,
  keep `recipient_discord_user_id` as sole Discord recipient id,
  add only the rendered notification fields enumerated in §4.
  Per F-1 lock from round-1 self-review.
- **Submit hookpoint defensive isolation**: `try/except Exception`
  around the post-commit emit per S8 lock (no re-raise; logged
  via `logger.exception`).
- **Materializer extension** (`services/api/app/services/notifications_materialize.py`):
  string-only `Template(...).substitute(context)` for embed
  `title`, `description`, `url`, and field `name`/`value`;
  typed pass-through for `color: int | None` and
  `fields[].inline: bool` (F-4 lock). Event-payload recipient
  and designated-channel destination selectors. This is a
  substrate generalization, but bounded — the materializer was
  already the central template renderer, and the new selectors
  are required to avoid hardcoding chapter/global routing into
  the rule rows.
- **Repository** (`services/api/app/repositories/notifications.py`):
  select / insert `rendered_embed_json` next to
  `rendered_title` / `rendered_body`. Mechanical column add.
- **Discord daemon** (`services/discord/app/handlers/notifications.py`):
  pass `embed=` when present; malformed embed JSON is definitive
  failure (config error). Transient API failures still
  non-definitive.
- **Settings** (`services/api/app/core/settings.py`):
  `web_public_base_url: str = Field(...)` (no Python default per
  F-2), plus three globals for the global-scope fallback
  (`global_applications_review_channel_id`,
  `global_application_managers_role_id`,
  `global_primary_guild_channel_url`).
- **Local fixtures + deployment**:
  `e2e-fixtures-infisicalsecret.yaml` adds three test fixture
  values; `api-deployment.yaml` wires env vars into the API pod.
  Local-channel only.
- **E2e test 19 extension**: post-submit Postgres assertions for
  one `notification_events` row, two materialized envelopes
  (one designated_channel with non-null `rendered_embed_json`,
  one DM with fixture applicant Discord id), delivery effects
  queued. **No live Humility guild send.**
- **Tests**: payload builder + emit-on-submit (TG-1),
  materialization with embed + dynamic recipient + skip cases
  (TG-2), live-guild fixture guard for production-id collision
  (TG-2b, F-3 lock), Discord daemon embed delivery + nonce
  preservation (TG-3), e2e Postgres-only assertions (TG-4).

## Out of scope (deferred / explicit anti-scope §8)

- **Live Humility Discord send, deployment, or runbook execution**
  — Tier 3, separate user-approved action per AGENTS.md.
- **Private Discord thread per application** — user-confirmed
  out per BACKLOG.
- **Discord buttons, claim/assign controls, moderation actions**
  — reviews stay in-product (β-iii surface).
- **Transition Discord side-effects** (DMs, embeds, role changes)
  — separate future BL; transition logic explicitly untouched.
- **Officer-to-applicant DM flow** — covered by β-iii's
  in-product message thread / transcript.
- **Chapter Discord config UI / admin tool** — separate slice;
  this INIT reads existing resource maps only.
- **Notification preferences, opt-out, escalation policy,
  digesting, per-officer routing** — deferred.
- **Remote channel rollout** — local fixture wiring only;
  GitOps yamls touched are `gitops/channels/local/` only.
- **Backwards-compatibility aliases, feature flags for old
  behavior, deprecated fields, placeholder stubs** — none
  added (consistent with AGENTS.md no-shim policy).
- **Second public-submit event type** — explicitly forbidden
  in §11 ("Delete or avoid"); the existing
  `application.public_submitted` event is reused.
- **Direct Discord sends from the API submit service** —
  explicitly forbidden in §11.
- **Chapter config columns duplicating `discord_resources`** —
  explicitly forbidden in §11.

## Risk surface

| Area | Pre | Post (INIT-134) | Justification |
|---|---|---|---|
| Migration head | `wu-044_application_messages` | + `wu-045_application_public_submit_notifications` | Adds 1 nullable JSONB column, seeds 2 rules. No table additions, no chapter/applications/members touch. |
| Public submit endpoint | `verify_applicant_receipt` → `submit_public_application_with_receipt` | Identical | §6 preserves auth verbatim |
| Submit service hookpoint | Post-commit `notification_events.emit` (id-only payload) | Same location, enriched payload, wrapped in `try/except Exception` (no re-raise) | S8 lock — notification failures cannot 5xx after commit |
| Notification event types | Existing types incl. `application.public_submitted` | Identical | No second event type per §11 |
| Notification rules | Existing seeded rules | + 2 rules (officer embed + applicant DM) | Both `grouping="per_event"` — at most one envelope each per submit |
| Allowlist | `APPLICATION_PUBLIC_SUBMITTED_PAYLOAD_ALLOWLIST` (current shape) | Replaced: drop `applicant_member_id` + `discord_user_id`, add 14 rendered notification fields, single Discord recipient id (`recipient_discord_user_id`) | F-1 lock — PII tightening + dedupe |
| Notification envelopes schema | `rendered_title`, `rendered_body` | + nullable `rendered_embed_json JSONB` | Single column, single purpose, NULL-safe for non-embed templates |
| Materializer | String-only template substitution into title/body | + embed string-field substitution (`title`, `description`, `url`, field `name`/`value`); + event-payload recipient + designated-channel selectors; typed pass-through for `color`/`inline` | F-4 lock — no `str()` coerce-and-restore for non-string embed fields |
| Discord daemon | `_send_message` sends `content` only; supports DM + designated-channel | + `embed=` when `rendered_embed_json` present; malformed embed JSON is definitive failure | One handler edit; routing logic untouched |
| Discord submission handler | Untouched | Untouched | §4 explicitly avoids touching `services/discord/app/handlers/application_submission.py` |
| Settings | Existing required + optional | + `web_public_base_url: str = Field(...)` + 3 global fallback fields | F-2 — no Python default for web base URL; tests provide via fixture |
| Local GitOps | E2e fixtures + api-deployment in `local/` | + 3 fixture Discord ids + env wiring | Local channel only; remote channels untouched |
| Permission surface | Unchanged | Unchanged | No new permission name introduced |
| Actor kinds | Unchanged | Unchanged | Submit actor remains resolved Discord member |
| Pomerium | Unchanged | Unchanged | No new prefix or policy in §3 modified files |
| Authentik | Unchanged | Unchanged | Not in §3 modified files |
| Idempotency | `uq_notification_envelopes__per_event` + deterministic Discord nonce from envelope id | Identical (`enforce_nonce=True` preserved per §4 / TG-3) | No new key system; bundle reuses existing envelope-id nonce |
| Live guild risk | N/A | Defended by TG-2b fixture guard against guild `900000000000000001` and known production channel/role ids | F-3 defense-in-depth |
| Test 19 | Existing public-submit assertions | + Postgres assertions for event row + envelopes + delivery effects | No live Discord write; mock/dry-run path only |
| Diff budget | — | +950 / -20 (under 1500 hard cap) | Under split threshold; bundle remains correct |

## Splittable concerns

- **BL-009 officer embed vs BL-020 applicant DM** could in
  principle ship separately. The proposal bundles them because
  (a) both consume the same post-commit emit hookpoint, (b) both
  use `recipient_discord_user_id` already carried in the existing
  event payload, (c) both materialize through identical
  `per_event` grouping, (d) the Discord handler already supports
  both `dm` and `designated_channel` routing — only the embed
  path is new, (e) the diff budget is well under twice the
  per-rule cost. The fall-back split (BL-020 DM first on
  text-only path, then BL-009 officer embed) is documented as a
  contingency in §9 if implementation exceeds 1500 net lines.
  **Bundling is a correct call** and matches the problem map
  Q6 lock.
- **Embed substrate (`rendered_embed_json` column + materializer
  embed substitution + Discord handler embed delivery)** is a
  one-shot substrate addition that only INIT-134's two new
  templates exercise today. It cannot be split from the officer
  embed slice — the embed cannot ship without rendering, persisting,
  and delivering it.
- **Settings additions (`web_public_base_url` + 3 globals)** are
  not separately splittable from the slice — the global-scope
  fallback (Q2 lock) requires them, and the embed link (§4)
  requires `web_public_base_url`.
- **Allowlist replacement** is bundled with the enriched-payload
  emit because shipping the new payload fields without removing
  `applicant_member_id` / `discord_user_id` would leave the PII
  hygiene incomplete (F-1 lock).

## Verdict reasoning

LOW. The slice consumes existing substrate everywhere it can:

1. **Migration footprint is tighter than the problem map sketched**
   — no chapter table change, just one nullable JSONB column on
   `notification_envelopes` plus two seeded rules. ✅ check 1
   (with intentional improvement on the Q1 sketch).
2. **Submit path adds an emit and a defensive `try/except`, nothing
   else.** No transition logic touched, no public submit semantics
   change, no applicant flow change, no edits to the Discord-side
   submission handler. ✅ check 2.
3. **Exactly two notification templates** — officer embed +
   applicant DM, both `per_event`, both seeded in the migration.
   ✅ check 3.
4. **Discord daemon change is a single `_send_message` edit** to
   pass `embed=` when present, plus a definitive-failure branch
   for malformed embed JSON. No other handlers touched. ✅
   check 4.
5. **No new permissions, no new actor kinds, no Pomerium changes,
   no auth changes.** Public submit auth preserved verbatim per
   §6; no new permission name appears in §3 / §4 / §11. ✅
   check 5.
6. **Bundle BL-009 + BL-020 is locked by problem map Q6 and
   proposal §2 Q6**, justified by shared submit hookpoint, shared
   payload (`recipient_discord_user_id` already present), shared
   substrate, and shared Discord handler. Diff budget +950 / -20
   well under the 1500 ceiling. ✅ check 6.

Three judgment calls worth naming explicitly — all LOW-risk:

- **Materializer event-payload selectors are a substrate
  generalization.** The materializer learns to read recipient and
  destination from event payload (rather than from rule-static
  fields). This is bounded — only the two new rules use selectors,
  and the alternative (hardcoding chapter/global routing into rule
  rows) would require schema for per-rule scope dispatch and
  chapter-id fanout, which is strictly worse. The generalization
  is the smaller change.
- **`rendered_embed_json` on `notification_envelopes`** is a
  substrate column addition that only INIT-134's officer embed
  exercises. It is nullable, NULL-safe for non-embed templates,
  and parallels existing `rendered_title` / `rendered_body`
  columns — a clean shape extension rather than a side table.
- **Allowlist replacement (not widening)** removes
  `applicant_member_id` and `discord_user_id` while adding the
  new rendered fields. This is a PII-tightening change to a
  field already in active production use; existing callers must
  be verified to not require the removed fields. The proposal
  flags this in §11 ("Delete or avoid"-adjacent) and the F-1
  lock makes it explicit; the API tests (TG-1) assert the
  replaced shape.

No "while we're at it" cleanups, no audits of pre-existing
notification logic, no scope leakage outside the public-submit
notification surface, no transition-side or chapter-config-UI
work sneaking in ahead of separate BL items.

SCOPE_DONE: plans/risk/init-134-scope.md
