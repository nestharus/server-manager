READ:
- proposals/09-receipt-required-submit.md
- research/15-receipt-required-submit-problem-map.md
- .tmp/rca/member-conversion-FINDINGS.md
- ~/ai/workflows/implementation-pipeline.md
- proposals/08-applicant-discord-oauth.md
- services/api/app/api/v1/endpoints/auth_discord.py
- services/api/app/services/applicant_discord_auth.py
- plans/risk/init-127-shortcut.md (predecessor format/tone)

# INIT-128 Phase 4 — Shortcut Risk Report

## Inputs read

- `proposals/09-receipt-required-submit.md` (full file)
- `research/15-receipt-required-submit-problem-map.md` (full file)
- `.tmp/rca/member-conversion-FINDINGS.md` (full file)
- Pipeline rules (Phase 4 shortcut-risk role)
- INIT-127 OAuth surface proposal (`proposals/08-applicant-discord-oauth.md`)
  for boundary continuity with the receipt-issuing slice.
- Live `services/api/app/api/v1/endpoints/auth_discord.py` and
  `services/api/app/services/applicant_discord_auth.py` to verify
  receipt primitives the proposal builds on.
- Predecessor `plans/risk/init-127-shortcut.md` for verdict-format and tone.

## Root-cause: real verified-identity replacement, not decorative

The RCA directs Option B — remove anonymous public submit and require a
verified Discord receipt
(`.tmp/rca/member-conversion-FINDINGS.md:107-119`). The proposal
implements that, not a parallel sibling path:

- `POST /api/v1/public/applications` gains a hard
  `Depends(verify_applicant_receipt)` server-side dependency that
  returns a structured `401 applicant_receipt_required` before any
  service call (`proposals/09-receipt-required-submit.md:108-114`).
  Cedar's `Public::"web-intake.<channel>"` route gate is preserved as
  the route-level question; the receipt answers the orthogonal
  identity question (`proposals/09-receipt-required-submit.md:189-202`).
  This is the right separation — Cedar stays a coarse route gate, the
  receipt is the per-applicant authentication proof, and they layer
  rather than overlap.
- The active service path is replaced, not duplicated:
  `submit_public_application_with_receipt(...)` resolves the receipt
  snowflake to a real `members.kind='discord'` row and calls
  `_submit_application_internal(..., _SubmissionAuthority.USER)` with
  `ActorIdentity(actor_kind="user", actor_id=str(member.id))`
  (`proposals/09-receipt-required-submit.md:135-149`). The synthetic
  `_SubmissionAuthority.PUBLIC_INTAKE` path and the
  `resolve_or_create_public_intake_member()` helper are anti-scoped
  from active routes.
- Actor-identity selection is correct, not a shortcut: the proposal
  recognizes that `_require_submit_authority()` self-authorizes only
  when `actor.actor_id == str(applicant_id)`, so the actor id must be
  the resolved member UUID and not the Discord snowflake
  (`proposals/09-receipt-required-submit.md:147,
  .tmp/rca/member-conversion-FINDINGS.md:91-95`). Using the snowflake
  as the actor id would have been the silent shortcut and would have
  forced the submit through grant lookup instead of self-authorization.
- The audit substrate alignment is forward, not legacy:
  `request_surface="api:/api/v1/public/applications"` and
  `_SubmissionAuthority.USER` align the new public submit with the
  existing officer/user audit model rather than the legacy
  `public-intake` service actor
  (`proposals/09-receipt-required-submit.md:142-147,
  .tmp/rca/member-conversion-FINDINGS.md:136-138`).

The decoration-only failure mode would have been "add the dependency
but keep the synthetic member create as a fallback when the receipt is
absent." The proposal forecloses that explicitly: "Missing/invalid
receipt returns the structured `401`; it must not create a member,
application, audit action, or notification event"
(`proposals/09-receipt-required-submit.md:112`). That is the load-
bearing sentence — the new dependency is fail-closed, not fail-open.

Risk: LOW.

## Cookie path widening: bounded under HttpOnly + Secure + SameSite=Lax + 10-min TTL + HMAC

Path goes from `Path=/applications` to `Path=/`. The widening is
required, not opportunistic — the current callback's
`path="/applications"` cookie does not reach `/auth/discord/me` or
`/api/public/applications` in a real browser
(`services/api/app/api/v1/endpoints/auth_discord.py:75-84`,
`research/15-receipt-required-submit-problem-map.md:101-105`), and
nginx rewrites `/api/public/...` to `/api/v1/public/...` after
browser path matching, so a fix scoped to `/api/v1/public/applications`
would not help (`research/15-receipt-required-submit-problem-map.md:107-111`).

What widening to `/` exposes:

- The cookie is now sent on every same-origin request, including
  endpoints that do not consume it (e.g. `/admin`, future API paths).
  This expands the surface that *receives* the cookie but not the
  surface that *trusts* it — the only consumer is the new submit
  dependency, plus `/auth/discord/me`'s read-only verification.
- HttpOnly forecloses JS read access; XSS on the origin cannot
  exfiltrate the receipt directly.
- Secure forecloses plaintext capture.
- SameSite=Lax forecloses cross-site POST/XHR auto-attach. A malicious
  cross-site `<form method=POST>` to `/api/public/applications` from
  a third-party origin will not carry the receipt cookie under Lax
  rules, so the cookie cannot be used as the carrier for cross-site
  CSRF-style submit. Top-level cross-site GET to `/auth/discord/me`
  *will* carry the cookie, but `/auth/discord/me` is a read-only
  receipt-verifier with no side effects, so an attacker learns nothing
  the receipt-holder did not already know.
- HMAC forecloses claim forgery; without
  `APPLICANT_RECEIPT_SIGNING_KEY` an attacker cannot mint a receipt
  for an arbitrary `discord_user_id`.
- 10-min TTL bounds replay window; a captured receipt expires quickly
  and there is no refresh path, so a single capture cannot be turned
  into a long-lived session.

What widening does NOT prevent:

- **Same-origin XSS-driven submit-on-behalf**: an XSS payload on the
  web origin can call `fetch('/api/public/applications', {method:
  'POST', credentials: 'include', body: ...})`, the browser will
  attach the receipt cookie automatically (because HttpOnly does not
  block attach, only read), and a submit will go through under the
  victim's snowflake. This risk is identical to any same-origin
  authenticated POST endpoint and is not made worse by widening the
  receipt cookie path; if anything the 10-min TTL makes it strictly
  better than a long-lived session cookie. The proposal's submit
  endpoint correctly does not require an `X-Discord-User-Id` header
  (`proposals/09-receipt-required-submit.md:57,
  proposals/09-receipt-required-submit.md:175`); a redundant header
  read from JS would have been a *worse* shortcut, since XSS could
  forge it just as easily as it can call `fetch`. The HMAC receipt is
  the trust boundary.

The proposal pins the security tradeoff explicitly
(`proposals/09-receipt-required-submit.md:79`: "more same-origin
request paths receive the cookie, but the receipt cannot be modified
or forged without the signing key and the submit endpoint still
verifies it server-side before trusting it"), and the test-intent
track exercises the path-delivery contract with a real cookie jar
(`proposals/09-receipt-required-submit.md:233`, TG-3).

One follow-up note for Step 6a, not a verdict mover: the proposal
keeps the SameSite attribute at `Lax` (inherited from INIT-127's
callback). For a path-`/` cookie that is now sent to a wider surface,
`Strict` would be a more conservative default given that the only
flow that needs the cookie cross-site is the OAuth round-trip return,
which is a top-level navigation and is fine under either Lax or
Strict. This is a defense-in-depth refinement, not a shortcut, and
the chosen Lax is consistent with INIT-127.

Risk: LOW.

## Race-safety on member create: ON CONFLICT pattern is correct but aggregate-head invariant is unresolved

The proposal commits to `INSERT INTO members (...) VALUES (...) ON
CONFLICT (discord_user_id) DO NOTHING` followed by a `SELECT` by
`discord_user_id` (`proposals/09-receipt-required-submit.md:127`). The
unique constraint backing this is the existing
`members.discord_user_id` uniqueness from `wu-011`
(`proposals/09-receipt-required-submit.md:130`,
`research/15-receipt-required-submit-problem-map.md:150`).

This is the textbook race-safe pattern for "lookup or create on a
unique key under concurrent submitters" and is materially better than
the existing `create_or_get_member()` unique-violation recovery loop
(`research/15-receipt-required-submit-problem-map.md:127-129`):
`ON CONFLICT DO NOTHING` collapses the create-versus-rescue race into
a single statement on the database, and the follow-up `SELECT` is
guaranteed to see the row (either the one this transaction inserted
or the one a concurrent transaction inserted). The kind-mismatch guard
("If a row exists with any other kind, fail as data corruption rather
than silently treating a synthetic row as real" —
`proposals/09-receipt-required-submit.md:125`) is the correct
fail-closed posture; a numeric Discord snowflake cannot collide with
`public:<hash>` rows under the current synthetic-id format
(`.tmp/rca/member-conversion-FINDINGS.md:74`), so the guard protects
the contract without rejecting any legitimate row.

What is NOT resolved is the aggregate-head invariant. The proposal
flags it honestly: "Ensure the selected row has a corresponding member
aggregate head/version. Current member reads join `members` to
`aggregate_heads` ... and current creation uses `mutate_entity()` to
create the aggregate head plus audit action ... The Step 5 hookpoint
must pick an implementation that preserves that invariant while still
using the locked `ON CONFLICT DO NOTHING + SELECT` race posture"
(`proposals/09-receipt-required-submit.md:128`). This is load-bearing:
member reads filter by `aggregate_heads` joins
(`research/15-receipt-required-submit-problem-map.md:57-58`,
`.tmp/rca/member-conversion-FINDINGS.md:64-69`), so a member row
inserted via raw `INSERT ON CONFLICT` without a corresponding
`mutate_entity()` aggregate-head/audit-action would be invisible to
read paths and would not produce a `member.create` audit row. That is
not a hypothetical — it is the exact failure mode the existing
`mutate_entity()` design was built to prevent
(`.tmp/rca/member-conversion-FINDINGS.md:64-69`).

The proposal's escape hatch — defer the implementation choice to
Step 5/6a — is acceptable per the pipeline's contract-clarity model,
but it is a real shortcut-risk *vector*: a Step 6c implementer who
treats "use ON CONFLICT" as a literal single-statement INSERT and
skips `mutate_entity()` will silently drop the aggregate head and the
member-create audit. Step 6a needs to pin one of:

1. Use `mutate_entity()`-based create with the existing unique-
   violation recovery, accepting its slightly weaker race semantics
   (this is what `create_or_get_member()` already does today —
   `services/api/app/services/members.py:115-176`); or
2. Extend `mutate_entity()` to accept an `ON CONFLICT DO NOTHING`
   posture so the aggregate-head/audit-action lifecycle still runs
   when the underlying row insert is skipped, with explicit handling
   of the "audit row for a non-insert" case; or
3. Wrap the raw `INSERT ON CONFLICT` plus a separate
   `aggregate_heads` upsert and a `member.create` audit emit in a
   single transaction, with explicit reasoning for why this pattern
   is safe.

Pick (1) by default. (2) and (3) are escape hatches if the race
posture in (1) proves inadequate. The proposal does not commit; the
shortcut-risk concern is that this commitment must happen at Step 6a,
not surface as a Step 6c implementation accident.

This is contract-clarity to surface to audit risk, not a verdict
mover, because the proposal *names* the invariant rather than ignoring
it. A shortcut-pattern proposal would have written "use ON CONFLICT"
and silently broken the read path.

Risk: LOW with a flagged Step 6a contract obligation.

## Notification event without DM materialization: audit trail is honest

The proposal emits `application.public_submitted` with payload
`{application_id, applicant_member_id, discord_user_id}` and an event
draft that carries `event_type`, `scope_kind`/`scope_id` from the
application target scope, then enqueues a `notifications_materialize`
deferred effect under the current audit context
(`proposals/09-receipt-required-submit.md:152-165`). DM materialization
is explicitly deferred to BL-020 because the current materializer
resolves only static `discord_user`/`discord_users` rule recipients,
not "recipient comes from event payload"
(`proposals/09-receipt-required-submit.md:165,
research/15-receipt-required-submit-problem-map.md:131-133`).

What lands as audit:

- A real `notification_events` row with event type, scope, correlation,
  and payload JSON (the schema persists exactly that —
  `migrations/versions/wu-003c_notification_events.py:16-41`,
  referenced at `proposals/09-receipt-required-submit.md:163`).
- A queued `notifications_materialize` deferred effect under the
  submit correlation, even though the materializer will not produce
  a Discord envelope yet.
- Audit actions for application submit/route under `_SubmissionAuthority.USER`
  with the real applicant member as actor and the public submit
  request surface (`proposals/09-receipt-required-submit.md:142-147`,
  TG-7 at `proposals/09-receipt-required-submit.md:238`).

What does NOT land:

- A Discord DM. The proposal does not claim it does.
- A materialized envelope row. The materializer will receive the
  effect, fail to match a static recipient rule, and produce no
  envelope.

The audit trail honesty test is "if a future operator queries 'who
submitted what when through the public web path,' do the rows
support that question?" Yes:
- `applications` row with real applicant member id.
- `members` row with `kind='discord'` and the verified snowflake.
- `application.submit` and `application.route` audit actions with the
  real applicant as actor.
- `notification_events` row tying the application id to the receipt
  snowflake under the same correlation.

The trail is complete *as an internal audit trail*. The Discord-visible
DM is a separate Tier-3 surface that BL-020 owns
(`proposals/09-receipt-required-submit.md:280`). The proposal does not
imply applicants will receive a DM and does not pretend the event
emission is delivery.

One observability note for Step 6a, not a shortcut concern: the
deferred-effect queue will accumulate `notifications_materialize`
effects that produce no envelope until BL-020 lands. Step 6a should
decide whether the materializer logs "no rule matched, payload-driven
recipient deferred" at info or warn level so this is not silently
indistinguishable from a misconfigured rule. The proposal's TG-9
asserts the deferred effect is queued
(`proposals/09-receipt-required-submit.md:240`) without asserting the
materializer's behavior on it; that is correct scope.

Risk: LOW.

## E2E split honesty: receipt-required is the only active path; legacy assertion is removed

The proposal updates `19-web-ui.sh` and `browser-flow.mjs` to seed a
valid applicant receipt before form submit and exercise the receipt-
required path; suite stays at 19 specs
(`proposals/09-receipt-required-submit.md:47,70,
proposals/09-receipt-required-submit.md:264`). The legacy
`public:%`-snowflake assertion is replaced by a `kind='discord'`
real-member assertion with the verified snowflake (TG-13/TG-14 at
`proposals/09-receipt-required-submit.md:244-245`).

Honesty checks:

- The supported-surface track is explicit: "INIT-120 anonymous path:
  removed from active public submit and from the e2e suite; all
  supported submit coverage requires a receipt"
  (`proposals/09-receipt-required-submit.md:201`). And anti-scope
  bullets: "No retained anonymous submit path, including in the e2e
  suite" (`proposals/09-receipt-required-submit.md:59`). There is no
  "we'll keep one anonymous spec for compat" loophole.
- TG-14 is explicitly a regression guard: "`19-web-ui` fails unless a
  valid applicant receipt is seeded before form submit and the active
  submit path rejects anonymous operation"
  (`proposals/09-receipt-required-submit.md:245`). If a future change
  silently re-enabled anonymous submit, the e2e would catch it.
- Deferral to BL-018 covers historical *data*, not the e2e contract.
  The proposal does not say "the legacy 19-web-ui is kept until
  BL-018"; it says the legacy *synthetic rows* persist as orphans
  until BL-018 cleans them
  (`proposals/09-receipt-required-submit.md:30,
  proposals/09-receipt-required-submit.md:206-207,
  proposals/09-receipt-required-submit.md:278`). The user prompt's
  framing of "legacy 19-web-ui kept until BL-018" does not match what
  the proposal proposes — `19-web-ui` is *updated* in this slice, not
  preserved. That is the correct posture; preserving the legacy
  anonymous spec would have been the shortcut and would have hidden
  the contract change the slice exists to make.

One operational concern for Step 6a, not a verdict mover: the receipt-
seeding mechanism is named as "the new
`/api/v1/auth/discord/test-helper-issue-receipt` endpoint or a
Playwright-injected cookie with a test-mode HMAC key"
(`proposals/09-receipt-required-submit.md:70`). A `test-helper-issue-
receipt` endpoint is a live attack surface if it ships unguarded — an
attacker hitting that endpoint in a non-test environment could mint a
receipt for any snowflake. Step 6a must pin one of:

1. The endpoint is registered behind an environment guard that fails
   loud at startup if the deployment is not a test environment, with
   the guard validated by a static test (preferred); or
2. The endpoint is not registered at all; e2e uses a Playwright-
   injected cookie signed with a deployment-specific test HMAC key
   that production never sees; or
3. The endpoint is replaced by an internal CLI/helper that is not
   reachable over HTTP at all.

Either (2) or (3) is the strongest shortcut-resistant choice. The
proposal allows (1) implicitly with "using the new
`/api/v1/auth/discord/test-helper-issue-receipt` endpoint *or* a
Playwright-injected cookie with a test-mode HMAC key", which is
acceptable but needs the guard pinned at Step 6a so it does not become
a Step 6c implementation accident.

This is contract-clarity to surface to audit risk; the proposal
itself is not committing the shortcut, it is leaving a fork that one
branch of resolves to a safe Step 6c choice.

Risk: LOW with a flagged Step 6a contract obligation.

## SPA receipt caching: 10-min cache is safe because it is advisory, not authoritative

The proposal caches `{discord_user_id, verified_at, expires_at}` in
memory or session storage for at most the configured receipt TTL,
re-fetches `/auth/discord/me` before submit, and explicitly states
"The UI may display verified login state, but it must not rely on
display state as authorization"
(`proposals/09-receipt-required-submit.md:171-178`). The API remains
authoritative — submit re-validates the receipt via the FastAPI
dependency on every request.

What this defends against:

- **Stale cache exploit**: a stale cache showing "verified" when the
  receipt has expired cannot be turned into a successful submit,
  because the API re-verifies on every POST and the cookie itself
  would have expired.
- **JS-readable cache exfil**: `discord_user_id` is the only identity
  field cached; XSS can read it from sessionStorage but XSS can also
  read it from `/auth/discord/me`, so the cache adds no exfil
  surface beyond what already exists. It does not cache the receipt
  itself (which is in the HttpOnly cookie and cannot be cached in
  JS-readable storage anyway).
- **Cross-tab leakage**: sessionStorage is per-tab, so a tab logged
  into a different applicant's Discord session does not see another
  tab's cached snowflake.

What this does NOT defend against and what the proposal does not
claim:

- **Same-tab UI confusion if the receipt expires mid-session**:
  display state shows "verified" while the cookie has just expired.
  The proposal handles this correctly by re-fetching `/auth/discord/me`
  before submit, which will return 401 and trigger a redirect to
  `/auth/discord/start?return_to=/applications`
  (`proposals/09-receipt-required-submit.md:174,176`). UI-vs-truth
  divergence is bounded to the moment between cache and re-fetch,
  not the moment between cache and submit.

The shortcut-pattern alternative would have been to skip the pre-
submit `/auth/discord/me` re-fetch and trust the cache. The proposal
explicitly rejects that
(`proposals/09-receipt-required-submit.md:174`: "On submit, re-fetch
`/auth/discord/me` before posting the application"), and TG-10 covers
the unauthenticated-gate case
(`proposals/09-receipt-required-submit.md:241`).

Risk: LOW.

## Orphan stance for pre-BL-017 synthetic submissions: honest deferral to BL-018

Anti-scope is explicit: "No `member_links` table. No auto-conversion
or application re-pointing for historical synthetic/public-intake
orphans" (`proposals/09-receipt-required-submit.md:51-52`).
Implementation decision is explicit: "No `member_links` table:
historical synthetic submissions lack a durable ownership proof, so
automatic synthetic-to-real linking would be dishonest"
(`proposals/09-receipt-required-submit.md:66`). Out-of-scope follow-up
is explicit: "BL-018 historical synthetic cleanup: report, archive, or
clean old `public_intake` orphan rows"
(`proposals/09-receipt-required-submit.md:278`).

The deferral matches the RCA's analysis verbatim
(`.tmp/rca/member-conversion-FINDINGS.md:121-170`): the synthetic
member id is derived server-side from `client_application_id` plus
`PUBLIC_INTAKE_MEMBER_SALT`, hashed into `public:<sha>`, the applicant
never received the synthetic hash as a proof token, the public
response returned only `message` and `application_id`, and the old
form collected no email or Discord id. There is no honest auto-link
mechanism, and the proposal does not invent one.

The shortcut-pattern alternative would have been to add a `member_links`
table now "in case BL-017 needs it" or to auto-convert any synthetic
row whose `discord_user_id` happens to be set during this slice's run.
The proposal forecloses both:

- "No `member_links` table" — anti-scope
  (`proposals/09-receipt-required-submit.md:51`).
- "must not call `resolve_or_create_public_intake_member()` and must
  not derive a `public:<hash>` id" — service contract
  (`proposals/09-receipt-required-submit.md:149`). New submissions
  cannot accidentally land on a synthetic row.

The rollback note is also honest: "Any `members.kind='discord'` rows
created while the slice was live may remain; they are valid real
members and do not need rollback deletion"
(`proposals/09-receipt-required-submit.md:214`,
`proposals/09-receipt-required-submit.md:274`). Pre-slice synthetic
rows do not need rollback either, because they were not created or
modified by this slice. Forward and backward boundaries match.

One ambiguity worth a Step 6a tightening: line 149 says
"`submit_public_application()` can remain only if it is unreachable
from active routes and explicitly treated as BL-018 legacy/e2e cleanup
surface." Leaving the legacy function as dead code crosses against the
pipeline's no-deferred-stubs convention
(`~/ai/conventions/no-deferred-stubs.md`, referenced from the pipeline
principles). Step 6a should commit to one of:

1. Delete `submit_public_application()` and
   `resolve_or_create_public_intake_member()` in this slice; e2e tests
   no longer reach them and BL-018 owns the data, not the code.
2. Mark the legacy functions explicitly removed in this slice and
   make BL-018 strictly a data/cleanup slice, not a code-cleanup
   slice.

Either resolves the ambiguity. Leaving the legacy code present "in
case rollback needs it" would be the shortcut — rollback is git
revert, not a hidden code path
(`proposals/09-receipt-required-submit.md:266-273` describes rollback
through git revert of route/dependency/SPA changes, which would
naturally restore the legacy functions if needed). This is wording-
precision to surface to audit risk; it does not defeat the slice's
purpose.

Risk: LOW with a flagged Step 6a contract obligation.

## Notable observations

1. **No redundant identity header is the right shortcut-resistant
   choice.** The proposal explicitly rejects an `X-Discord-User-Id`
   header (`proposals/09-receipt-required-submit.md:57,68`,
   `proposals/09-receipt-required-submit.md:175,
   proposals/09-receipt-required-submit.md:188`). The HMAC-signed
   receipt is the trust boundary; a browser-supplied duplicate
   identity header would only add mismatch cases without improving
   trust, and a same-origin XSS could forge the header just as
   easily as it can call `fetch()`. A shortcut-pattern proposal might
   have added the header for "defense in depth" and the test-intent
   track for it
   (`proposals/09-receipt-required-submit.md:242`, TG-11) explicitly
   asserts the header is *absent*, which is the right inverse
   assertion.

2. **Forward-path actor identity is selected, not stumbled into.**
   `_require_submit_authority()`'s self-authorization rule is named
   in the proposal
   (`proposals/09-receipt-required-submit.md:147`) and in the RCA
   (`.tmp/rca/member-conversion-FINDINGS.md:91-95`). The proposal
   uses the resolved member UUID as actor id rather than the Discord
   snowflake, which is the correct shape and the one that bypasses
   grant lookup; using the snowflake would have silently rejected
   legitimate self-submits via the grant path. The audit-row
   contract (`actor_kind='user'`, `actor_id=<member_uuid>`,
   `request_surface='api:/api/v1/public/applications'`) flows from
   that decision and TG-7 covers it
   (`proposals/09-receipt-required-submit.md:238`).

3. **Cedar policy stays a coarse route gate.** The proposal does not
   invent a per-applicant Cedar principal or a `User::<discord_user_id>`
   policy entity (`proposals/09-receipt-required-submit.md:55,202,
   .tmp/rca/member-conversion-FINDINGS.md:188-200`). Cedar continues
   to answer "is this public submit route enabled for this channel?"
   and the receipt dependency answers "which Discord user is
   submitting?" That is the right separation of concerns and matches
   the predecessor INIT-127's posture of not overloading the
   officer/admin OIDC trust path.

4. **Aggregate-head invariant is named, not silently broken.** The
   proposal explicitly carries forward the constraint that real
   member rows must have a corresponding `aggregate_heads` row and
   `member.create` audit action
   (`proposals/09-receipt-required-submit.md:128`,
   `research/15-receipt-required-submit-problem-map.md:122-125`).
   Step 6a must commit to the implementation pattern (see §Race-
   safety), but the proposal does not propose a pattern that would
   silently skip the invariant.

5. **Receipt-only trust boundary survives the BL-016 → BL-017 → BL-020
   chain.** INIT-127 emits the HMAC-signed receipt, INIT-128
   verifies it on submit and binds to a real member, BL-020 will
   consume the same receipt-attached event for DM materialization.
   The receipt format is unchanged across slices; the consumers are
   added incrementally. That is the correct decomposition and it
   does not require receipt-format breaking changes between slices.
   The 10-min TTL in-band replay window noted in INIT-127's shortcut
   report is bounded by the same TTL here — a captured receipt within
   its window can be replayed against the submit endpoint, but the
   client-side `client_application_id` deduplication
   (`proposals/09-receipt-required-submit.md:140,
   proposals/09-receipt-required-submit.md:239`, TG-8) bounds the
   damage to one application per (member, client_application_id)
   pair. A capture-and-replay attacker can submit one application as
   the victim within the TTL; they cannot turn it into a long-lived
   identity proof. This is acceptable for a public-intake surface;
   if a stronger defense is desired later, BL-020 or a follow-on can
   bind the receipt to a single-use server-side token.

6. **Cookie-path test is a real cookie-jar test, not a bypass.** TG-3
   (`proposals/09-receipt-required-submit.md:234`) exercises the
   cookie path through an ASGI/httpx cookie jar against
   `/auth/discord/callback`, `/auth/discord/me`, and the public
   submit route, rather than passing explicit `Cookie` headers as
   the existing tests do
   (`research/15-receipt-required-submit-problem-map.md:113-116`).
   The residual is honest: "ASGI jar approximates browser path rules
   but does not prove every browser quirk"
   (`proposals/09-receipt-required-submit.md:234`). The remaining
   browser-quirk residual is covered by the live e2e at TG-13.

7. **Notification recipient is in the payload, not statically wired.**
   The event payload carries `discord_user_id` as the eventual
   recipient
   (`proposals/09-receipt-required-submit.md:160,
   proposals/09-receipt-required-submit.md:163`). The current
   materializer only resolves static recipients, so BL-020 must
   extend the materializer to support payload-driven recipients
   (`proposals/09-receipt-required-submit.md:165`,
   `research/15-receipt-required-submit-problem-map.md:131-133`).
   The proposal does not silently extend the materializer here
   (which would have widened the slice and crossed into BL-020's
   surface) and does not pretend the existing materializer will
   produce an envelope without that work.

8. **Test-helper endpoint is a fork that needs Step 6a closure.** The
   e2e seeds the receipt via "the new
   `/api/v1/auth/discord/test-helper-issue-receipt` endpoint or a
   Playwright-injected cookie with a test-mode HMAC key"
   (`proposals/09-receipt-required-submit.md:70`). The endpoint
   variant is a live attack surface if not env-gated; the injection
   variant is the safer choice. Step 6a must close the fork; see
   §E2E split honesty for the recommended posture.

9. **Legacy code-path leaves a deferred-stub fork.** Line 149
   ("`submit_public_application()` can remain only if it is
   unreachable from active routes and explicitly treated as BL-018
   legacy/e2e cleanup surface") leaves the legacy function as
   potentially dead code. This is wording-imprecision against the
   no-deferred-stubs convention; Step 6a should commit to deletion
   rather than long-term preservation. See §Orphan stance for the
   recommended posture.

10. **Rollback does not require database deletion is honest.** The
    rollback section
    (`proposals/09-receipt-required-submit.md:266-274`) correctly
    notes that any real `kind='discord'` rows created during the
    slice are valid real members that do not need rollback deletion.
    This is the correct invariant — the slice does not produce data
    that becomes invalid if the slice is reverted. A shortcut-pattern
    rollback would have required deleting created rows because the
    slice's invariant was tied to the slice itself; the proposal's
    rollback is clean because the data invariant is forward-only.

## Verdict

```
SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
```

The proposal genuinely replaces the active anonymous public submit
path with a verified-identity path: a fail-closed FastAPI dependency
verifies the HMAC receipt before any service call, the active service
binds the receipt snowflake to a real `members.kind='discord'` row,
the actor identity is correctly the resolved member UUID rather than
the Discord snowflake (which would have routed through grant lookup),
and Cedar remains a coarse route gate alongside the receipt's
identity proof. Cookie path widening to `/` is required by browser
path-matching mechanics and is bounded by HttpOnly + Secure +
SameSite=Lax + 10-min TTL + HMAC; the same-origin XSS submit-on-behalf
risk is identical to any same-origin authenticated POST and is not
made worse by widening, while a redundant `X-Discord-User-Id` header
is correctly anti-scoped because it would forge as easily as a
cross-origin `fetch()`. The `INSERT ON CONFLICT DO NOTHING + SELECT`
race posture is correct, and the aggregate-head/audit-action
invariant is named explicitly so Step 6a must commit to a preserving
pattern rather than silently breaking member reads. Notification
event emission without DM materialization is honest about its scope:
a real `notification_events` row plus a queued
`notifications_materialize` deferred effect lands as audit, while DM
delivery is correctly deferred to BL-020 where the materializer's
payload-driven-recipient extension belongs. The e2e contract is
updated, not preserved as a legacy anonymous spec, and TG-14 is a
real regression guard against silent re-enablement of anonymous
submit. SPA caching is bounded by the cookie TTL and is advisory
only; the API re-verifies on every submit. Pre-BL-017 synthetic rows
remain orphaned and BL-018 owns cleanup, with no `member_links`
table or auto-conversion shortcut introduced.

Three contract-clarity defects need Step 6a closure but none defeat
the slice's purpose:

- The aggregate-head implementation pattern under
  `INSERT ON CONFLICT DO NOTHING + SELECT` (Observation 4 / §Race-
  safety) — pin pattern (1) `mutate_entity()`-based, escape to (2) or
  (3) only with explicit reasoning.
- The e2e receipt-seeding mechanism (Observation 8 / §E2E split
  honesty) — prefer Playwright-injected cookie with test-mode HMAC
  key over a live `test-helper-issue-receipt` endpoint, or pin the
  endpoint behind a hard environment guard validated by a static
  test.
- The legacy `submit_public_application()` and
  `resolve_or_create_public_intake_member()` deletion vs preservation
  (Observation 9 / §Orphan stance) — commit to deletion in this
  slice; rollback is git revert.

These are wording-precision and Step 6a contract obligations to
surface to audit risk, not shortcut-risk verdict movers. No
invalidated assumptions and no non-positive value signal on the
current supported surface.
