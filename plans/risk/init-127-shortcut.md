READ:
- proposals/08-applicant-discord-oauth.md
- research/13-applicant-discord-oauth-problem-map.md
- .tmp/rca/discord-oauth-linking-FINDINGS.md
- ~/ai/workflows/implementation-pipeline.md
- plans/risk/init-125a-shortcut.md (predecessor format/tone)

# INIT-127 Phase 4 — Shortcut Risk Report

## Inputs read

- `proposals/08-applicant-discord-oauth.md` (full file)
- `research/13-applicant-discord-oauth-problem-map.md` (full file)
- `.tmp/rca/discord-oauth-linking-FINDINGS.md` (full file)
- Pipeline rules (Phase 4 shortcut-risk role)
- Predecessor `plans/risk/init-125a-shortcut.md` for verdict-format and tone

## Root-cause: real verification surface, not a placeholder

The RCA's "What is missing" list for the applicant identity surface
(`.tmp/rca/discord-oauth-linking-FINDINGS.md:108-115`) names five gaps:
no Discord OAuth Source in Authentik, no server-manager Authentik
application/provider, no applicant login/link route, no claim/property
mapping that exposes the Discord snowflake, and no API service that
consumes a successful OIDC callback.

The proposal fills each by name, not by stub:

- Discord OAuth Source: `authentik_sources_oauth.oauthsource` slug
  `discord`, scope `identify`, declared in the blueprint
  (`proposals/08-applicant-discord-oauth.md:86`).
- Server-manager applicant Provider/Application: a *separate*
  `authentik_providers_oauth2.oauth2provider` named
  `server-manager-applicant` with strict redirect URI and an
  `authentik_core.application` slug `server-manager-applicant`
  (`proposals/08-applicant-discord-oauth.md:89-90`).
  Explicitly does not overload the existing `pomerium` provider, which
  is the failure mode the RCA called out
  (`.tmp/rca/discord-oauth-linking-FINDINGS.md:128-138`).
- Applicant login/link route: Pomerium `/auth/discord/` route to the
  API service plus SPA login state
  (`proposals/08-applicant-discord-oauth.md:96-104,107-114`).
- Claim mapping: a provider scope mapping that emits exactly
  `{"discord_user_id": request.user.attributes.get("discord_user_id")}`,
  populated from a Source property mapping that copies Discord
  `info["id"]` into `attributes.discord_user_id`
  (`proposals/08-applicant-discord-oauth.md:87-88`). The chain from
  Discord snowflake to API-visible claim is end-to-end declared.
- Callback handler: API endpoint at `/auth/discord/callback` that does
  the full code-exchange/JWKS-validate/claim-extract/receipt-issue
  sequence (`proposals/08-applicant-discord-oauth.md:118-131`).

Each of these is a real artifact with a defined contract, not a
deferred TODO. The blueprint entries are full Authentik object
specifications; the callback handler has a 6-step flow with explicit
validation predicates; the receipt format pins exactly three claims.

The slice does stop at "proof of identity" rather than consuming
identity (no member create, no application re-point, no submit
authorization change — `proposals/08-applicant-discord-oauth.md:56-64`).
That is correct decomposition: the RCA's recommended sequence is
`A discriminator → B OAuth → C conversion → D cleanup`
(`.tmp/rca/discord-oauth-linking-FINDINGS.md:337-383`); INIT-125A
delivered A, BL-016/INIT-127 delivers B, BL-017 will deliver C. The
receipt is the bounded artifact that crosses the B→C interface.

One adjacent observation under this question: the receipt is generated
but BL-016 has no production consumer. The SPA holds it
(`proposals/08-applicant-discord-oauth.md:114`) and the public submit
endpoint is anti-scoped from accepting it
(`proposals/08-applicant-discord-oauth.md:60-61,73-74`). This is not a
placeholder pattern — the receipt is a real signed artifact validated
end-to-end by the callback's tests — but it does mean BL-016 in
isolation produces an output nothing reads in production. That is the
correct decomposition cost (BL-017 needs the verified surface to
exist before it can convert) rather than a shortcut, and the test-
intent track exercises the receipt contract in `component`/`unit` tests
that do not require BL-017 (`proposals/08-applicant-discord-oauth.md:201`).

Verdict on this question: the proposal establishes a real verified
Discord identity surface, not a stub. Risk: LOW.

## Security choices serve their stated purpose

### Server-side OIDC exchange

The decision is recorded explicitly: "Server-side OIDC exchange: the
API callback exchanges the code, validates the JWT against JWKS, and
returns an applicant receipt so the SPA never holds raw Authentik
OIDC tokens" (`proposals/08-applicant-discord-oauth.md:69`). The flow
at `proposals/08-applicant-discord-oauth.md:122-129` keeps Authentik
client_secret, the authorization code redemption, the ID token, and
JWKS verification on the API server. The SPA only ever receives the
HMAC-signed applicant receipt.

This is the right shortcut-resistant choice over the alternative
(SPA-driven implicit/PKCE flow with ID token in browser): an XSS in
the SPA would expose only a short-lived single-claim receipt scoped
to the applicant identity contract, not raw Authentik OIDC material
that could be replayed against any Authentik-backed surface. The RCA
called this question out as an open IMPLEMENTATION decision
(`.tmp/rca/discord-oauth-linking-FINDINGS.md:362-365,389-392`); the
proposal takes the safer side and names why.

The "why" survives BL-017's later expansion: when BL-017 begins
consuming the receipt at conversion time, it will be verifying an
HMAC produced by the same trust boundary, not re-validating an OIDC
ID token in the browser session.

Risk: LOW.

### JWKS validation

Step 4 of the callback flow validates the ID token against the
applicant Application JWKS and verifies issuer, audience, expiration,
issued-at, and "nonce where present"
(`proposals/08-applicant-discord-oauth.md:127`). The test-intent track
covers the failure modes: bad signature, wrong audience, expired token
(`proposals/08-applicant-discord-oauth.md:200`).

Two minor sharp edges to flag for Step 6a/6c, neither of which is a
shortcut-risk verdict mover:

1. "nonce where present" is softer than the rest of the validation
   list. OIDC `nonce` SHOULD always be present on authorization-code
   flows that the client requests it on; allowing absence opens a
   replay window if the SPA's redirect was intercepted. The
   `state`/`nonce` generation contract belongs in Step 6a so the
   callback either always requires nonce or has a documented reason
   not to.
2. JWKS endpoint pin is `/application/o/<application slug>/jwks/`
   (`proposals/08-applicant-discord-oauth.md:92`). Step 6c needs to
   wire JWKS caching with a bounded TTL so a key rotation in
   Authentik does not silently break callbacks (the test intent
   honestly flags this residual:
   `proposals/08-applicant-discord-oauth.md:200`).

These are implementation concerns surfaced for downstream phases, not
deferred risk.

Risk: LOW.

### Identify-only scope

The Discord OAuth scope is explicitly `identify` only
(`proposals/08-applicant-discord-oauth.md:62,86`), and the anti-scope
forbids `email`, `guilds`, and `guilds.members.read`
(`proposals/08-applicant-discord-oauth.md:62`). The provider scope
mapping emits exactly `discord_user_id` and the receipt format
constrains its three claims (`discord_user_id`, `iat`, `exp`) with
explicit prohibition on raw Authentik tokens, Authentik subject,
email, display name, avatar, guilds, or roles
(`proposals/08-applicant-discord-oauth.md:166-172`).

This is least-privilege carried through three layers (Discord scope →
Authentik provider mapping → applicant receipt). A future temptation
to add `email` for "convenience" must add a Discord scope, an
Authentik mapping change, and a receipt-format change; no single
silent add propagates. That is the correct shortcut-resistant
posture.

The RCA's PRODUCT question on guild-membership gating
(`.tmp/rca/discord-oauth-linking-FINDINGS.md:398-400`) is honestly
deferred — adding `guilds`/`guilds.members.read` would be a separate
PII review and is not a hidden requirement of BL-016.

Risk: LOW.

### HMAC-signed receipt: forgery yes, replay partially

The receipt format is HS-signed JWT with `discord_user_id`, `iat`,
`exp`, default 10-minute TTL, signed with
`APPLICANT_RECEIPT_SIGNING_KEY`
(`proposals/08-applicant-discord-oauth.md:155-172`).

What this prevents:

- **Claim forgery**: yes. Without the signing key an attacker cannot
  mint a receipt that claims an arbitrary `discord_user_id`. The
  signing key lives in Infisical
  (`proposals/08-applicant-discord-oauth.md:141`) and is not in the
  blueprint or SOPS material.
- **Long-window replay**: bounded by 10-min TTL.
- **Bait-and-switch claim mutation**: the `exp`/`iat` and the
  signature cover the entire payload, so adding/changing
  `discord_user_id` invalidates the signature.

What this does NOT prevent and what the proposal does not claim:

- **Replay within TTL**: there is no `jti`, no server-side issued-
  receipt registry, and no audience claim. A receipt captured on the
  wire (or via XSS) inside its 10-min window can be replayed against
  any future surface that consumes the receipt. For BL-016 this is
  moot — the public submit endpoint is anti-scoped from accepting
  the receipt
  (`proposals/08-applicant-discord-oauth.md:60-61,73-74`) — but the
  proposal should flag for BL-017 that the conversion endpoint will
  need replay protection (e.g., bind the receipt to an application id
  or to a server-side single-use token). This is forward-looking
  scope, not BL-016 shortcut.

The "JWT vs cookie" framing in the proposal
(`proposals/08-applicant-discord-oauth.md:131,153-172`) is a category
mix worth pinning in Step 6a:

- The receipt *format* is HMAC-signed JWT.
- The receipt *transport* to the SPA is either a redirect-with-
  transfer-token followed by a one-time fetch, or an HTTP-only
  cookie that the SPA cannot read directly.

Section "Receipt format" prefers cookie
(`proposals/08-applicant-discord-oauth.md:131`); Section "Web SPA"
says the SPA holds the receipt in browser state for BL-017
(`proposals/08-applicant-discord-oauth.md:114`). HTTP-only cookies
are not readable from the SPA, so an HTTP-only cookie *plus* a SPA
that needs to read the receipt requires the one-time transfer
endpoint. The proposal already names that variant
(`proposals/08-applicant-discord-oauth.md:131`), so the resolution
exists — Step 6a needs to commit to one transport so the test-intent
SPA-storage assertions
(`proposals/08-applicant-discord-oauth.md:203`) match what is
actually shipped.

This is a contract-clarity defect to resolve at 6a, not a shortcut.
The shortcut alternative would be putting the receipt in the URL on
the redirect (in browser history, in proxy logs); the proposal
explicitly rejects that
(`proposals/08-applicant-discord-oauth.md:131` "avoids putting the
receipt in the URL"). Risk on the security choice is bounded.

Risk on this dimension: LOW. Forgery is prevented, replay is bounded
to 10 min, and the BL-017 follow-on replay surface is named below
under §Notable observations.

## Anti-scope deferrals: BL-017, BL-009, INIT-120

### BL-017 (member creation/conversion/re-pointing)

Anti-scope bullets `proposals/08-applicant-discord-oauth.md:56-58`:
"No member creation. No application re-pointing. No synthetic-to-real
conversion." Implementation decision
`proposals/08-applicant-discord-oauth.md:73`: "Callback verifies only:
BL-016 does not create or update `members` or `applications`; BL-017
owns conversion and application re-pointing." Receipt-format constraint
`proposals/08-applicant-discord-oauth.md:172`: "BL-016 stores no
receipt-derived database state."

This matches the RCA's BL-017 boundary
(`.tmp/rca/discord-oauth-linking-FINDINGS.md:354-360`) — the
conversion service, supersession/link record, and re-pointing are
explicitly the *next* slice and the proposal does not silently
encroach. The callback's exit point is "return signed receipt", not
"upsert member". The shortcut alternative — let the callback also
mint or update a member row "while we're here" — would have collapsed
the B/C boundary and reproduced the RCA's exact concern about
mixing OAuth plumbing with cross-aggregate mutation
(`.tmp/rca/discord-oauth-linking-FINDINGS.md:368-370`). The proposal
holds the line.

Honest. Risk: LOW.

### BL-009 (Discord-visible side effects)

Anti-scope bullet `proposals/08-applicant-discord-oauth.md:63`: "No
Discord-visible side effects." The Discord OAuth scope is `identify`
only (no `guilds.join`, no message posting, no role assignment), and
the callback does no Discord API calls. This is the right deferral —
BL-009's user-confirmed direction depends on having a linked member
(`proposals/08-applicant-discord-oauth.md:41`), which BL-017 produces,
not BL-016. Honest.

Risk: LOW.

### INIT-120 (public submit redirect / Cedar / contract)

This is the deferral that needs the most careful read. The proposal
makes three overlapping claims:

1. Anti-scope `proposals/08-applicant-discord-oauth.md:60-61`: "No
   INIT-120 public submit contract change. No new Cedar applicant
   principal or public-submit authorization change."
2. Implementation decision `proposals/08-applicant-discord-oauth.md:74`:
   "No public submit API change: `POST /api/v1/public/applications`
   remains the existing anonymous Cedar-authorized path."
3. Net-value `proposals/08-applicant-discord-oauth.md:41`:
   "establishes the missing Discord identity proof needed by BL-017
   and BL-009 while keeping INIT-120's supported anonymous submit
   path stable."
4. SPA behavior `proposals/08-applicant-discord-oauth.md:75,108-114`:
   "Redirect timing is submit-time… submitting without a receipt
   redirects to Authentik" / "On submit, if no valid receipt exists,
   persist the form draft and OIDC `state` in `sessionStorage`, then
   redirect the browser to Authentik's applicant authorization URL.
   On return from `/auth/discord/callback`, receive the server-issued
   receipt, store it… If a valid receipt exists, allow the current
   submit code path to continue unchanged."

Reading these together, the proposal is honest at the API layer and
ambiguous at the SPA layer:

- **API-level**: `POST /api/v1/public/applications` is unchanged. It
  still accepts the same `PublicApplicationSubmission`, still
  authorizes through `Public::"web-intake.local"`, still does not
  require a receipt. A direct API client (curl, bot, alternate web
  surface) can still submit anonymously. The test-intent
  non-regression test asserts the submit response shape is unchanged
  (`proposals/08-applicant-discord-oauth.md:204`).
- **SPA-level**: the canonical
  `https://web.local.humility.local/applications` flow now gates
  submit on having an applicant receipt and forces an Authentik
  round-trip on the first submit. The receipt is then collected and
  *not used* by the API call (since the contract anti-scope forbids
  sending it). So during the BL-016 → BL-017 gap, the user pays the
  OAuth round-trip while the server-side behavior is identical to
  pre-BL-016.

The "INIT-120 supported anonymous submit path stable" claim
(`proposals/08-applicant-discord-oauth.md:41`) is true at the API and
arguably misleading for the SPA. The supported-surface reading saves
it: INIT-120's *supported surface* is the `/api/public/applications`
contract, the `public_intake` member kind classification, and the
public-intake rate-limit/Cedar wiring — all of which are preserved.
The SPA UX *is* in scope (proposal:107-114 is the SPA design
section), and the proposal does not pretend otherwise.

The shortcut-risk question is: does forcing OAuth at SPA submit while
discarding the receipt server-side defeat BL-016's purpose, or is it
a step on the path? It is a step on the path:

- It exercises the OAuth flow end-to-end through the SPA, which is
  the only way the receipt-collection contract gets real coverage
  before BL-017.
- It de-risks the SPA → callback handoff, redirect URI handling,
  and `sessionStorage` draft preservation that BL-017 will rely on.
- It does not require BL-017 to also re-design the SPA; BL-017
  becomes "wire the held receipt into the conversion endpoint,"
  which is bounded.

The shortcut alternative would have been to skip SPA changes
entirely in BL-016, ship just the callback endpoint and blueprint,
and have BL-017 add the SPA. That is also defensible but pushes more
end-to-end risk into BL-017, not less. Either decomposition is
honest; the chosen one is internally consistent.

What is *not* honest enough is the wording in the net-value
sentence. "Keeping INIT-120's supported anonymous submit path
stable" reads as "the user-facing submit flow is unchanged," which
is not true under proposal:112. Step 6a or a proposal revision
should tighten this to "keeping the INIT-120 public submit API
contract stable" so the supported-surface verdict and audit verdict
have an unambiguous claim to evaluate.

This is a wording-precision defect, not a shortcut. The actual
deferral architecture is correct.

Risk on this dimension: LOW with a flagged audit-clarity note.

## Per-developer Discord application: workable, with bounded tax

The proposal commits to a per-developer Discord application pattern
(`proposals/08-applicant-discord-oauth.md:51,76`) and supports it
with:

- `.env.example` keys and onboarding documentation
  (`proposals/08-applicant-discord-oauth.md:51,216`).
- A bootstrap script change that reads
  `DISCORD_OAUTH_CLIENT_ID`/`DISCORD_OAUTH_CLIENT_SECRET` from the
  environment if absent in Infisical and "fail with a clear message
  if neither source exists"
  (`proposals/08-applicant-discord-oauth.md:143`).
- Test-intent honesty: the live e2e residual explicitly says "Does
  not prove live Discord OAuth because per-developer Discord app
  credentials may be absent"
  (`proposals/08-applicant-discord-oauth.md:204`).

Tax assessment:

- **One-time onboarding cost per developer**: register a Discord
  Developer Portal application, configure redirect URI
  `https://auth.local.humility.local/source/oauth/callback/discord/`,
  paste client id/secret. ~5–10 minutes if the developer has a
  Discord account; longer if not.
- **Unavoidable**: Discord does not expose an API for application
  creation, so no script can fully automate this for a fresh
  developer machine. The proposal does not pretend otherwise; it
  routes the secret through the same `bootstrap-infisical-auth.sh`
  fail-loud pattern already used for other auth secrets
  (`infra/scripts/bootstrap-infisical-auth.sh:368-425` referenced in
  `proposals/08-applicant-discord-oauth.md:143`).
- **Opt-out behavior**: a developer who skips Discord app setup can
  still run the static, component, and mocked-integration tests
  (which use generated keypairs/JWKS and a mocked Authentik token
  endpoint:
  `proposals/08-applicant-discord-oauth.md:199-201`). They lose
  only the live local OAuth round-trip, and the bootstrap script
  fails loudly rather than silently degrading
  (`proposals/08-applicant-discord-oauth.md:143`). That matches the
  problem-map flag against silent no-op auth bootstrap
  (`research/13-applicant-discord-oauth-problem-map.md:218-221`).

Shortcut-risk question: is a shared dev Discord app a hidden better
choice that the proposal silently rejected? The RCA flagged this as
an AMBIGUOUS open question
(`.tmp/rca/discord-oauth-linking-FINDINGS.md:356-359`). A shared
dev app would mean shared client_secret in version control or in a
team-wide secret store, shared redirect URI ownership across
developer-specific local hostnames (which all map to the same
`auth.local.humility.local`, so technically shareable), and a single
rotation/owner. Per-developer apps cost onboarding minutes but
avoid the secret-sharing surface.

The proposal's choice (per-developer) is the right shortcut-resistant
choice for security: each developer's local OAuth flow uses
credentials only that developer holds, so a leak is bounded to that
developer's machine. The cost is bounded, the failure mode is loud,
and the test plan does not depend on every developer having Discord
credentials. This is a tax, not a hidden tax.

Risk on this dimension: LOW.

## Notable observations

1. **Separate applicant Provider, not Pomerium overload.** The
   proposal carries forward the RCA's strongest design constraint —
   do not overload the existing `pomerium` provider — by introducing a
   distinct `server-manager-applicant` Provider/Application
   (`proposals/08-applicant-discord-oauth.md:68,89-90`). The
   `pomerium` provider's `sub_mode='hashed_user_id'` is appropriate
   for officer/admin sessions and is the wrong shape for an applicant
   Discord-snowflake claim
   (`research/13-applicant-discord-oauth-problem-map.md:222-226`).
   Reusing it would have been the shortcut. The proposal does not
   take that path and pins audit-clarity blast-radius bullets that
   forbid it (`proposals/08-applicant-discord-oauth.md:182`).

2. **Blueprint vs imperative-script split is decided, not deferred.**
   The RCA flagged a real risk that adding applicant OAuth partly
   in YAML blueprints and partly in
   `infra/scripts/bring-up-local-channel.sh` could create ordering
   drift (`research/13-applicant-discord-oauth-problem-map.md:212-215`).
   The proposal commits all applicant Authentik objects (Source,
   property mapping, Provider, Application) to the blueprint
   (`proposals/08-applicant-discord-oauth.md:71,82-90`) and explicitly
   keeps `bring-up-local-channel.sh` out of applicant reconciliation
   (`proposals/08-applicant-discord-oauth.md:181`). One source of
   truth, atomic apply
   (`proposals/08-applicant-discord-oauth.md:92`). This is the
   right anti-drift posture.

3. **Two-argument `!Env` enforced.** The blueprint is required to use
   `!Env [VAR, ""]` two-argument forms for all secret-derived values
   (`proposals/08-applicant-discord-oauth.md:82`), preventing the
   exact one-element-list failure that already burned INIT-114
   (`research/13-applicant-discord-oauth-problem-map.md:207-210`).
   Worth carrying into Step 6a as a contract obligation.

4. **SOPS boundary preserved.** The proposal explicitly does not
   commit Discord client secrets or applicant OIDC secrets into the
   blueprint or into SOPS-encrypted runtime files
   (`proposals/08-applicant-discord-oauth.md:147-151`), and routes all
   secret material through Infisical's `/auth/local/authentik` path
   following the existing OIDC client shape. This matches the
   bootstrap-only SOPS lint boundary
   (`research/13-applicant-discord-oauth-problem-map.md:154-158`,
   `infra/scripts/lint-sops-boundary.py`). The shortcut would have
   been "just commit the encrypted secrets next to the blueprint" —
   the proposal rejects it and names why.

5. **Pomerium route ordering is named, not assumed.** The proposal
   requires the `/auth/discord/` prefix route to land *before* the
   public web catch-all
   (`proposals/08-applicant-discord-oauth.md:96-104,183`) and to be
   `allow_public_unauthenticated_access: true` so it does not inherit
   officer auth. The test-intent track has a dedicated render-order
   assertion (`proposals/08-applicant-discord-oauth.md:198`). The
   public-intake rate-limit ingress
   (`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`,
   `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`)
   is named as something the callback must *not* accidentally inherit
   (`proposals/08-applicant-discord-oauth.md:183`). These are the
   exact failure modes the problem map called out
   (`research/13-applicant-discord-oauth-problem-map.md:88-93,
   258-261`).

6. **Receipt-transport ambiguity needs Step 6a resolution.** Section
   "Server-side callback handler" describes two return mechanisms
   (transfer token via redirect, or HTTP-only short-lived cookie) and
   prefers the cookie
   (`proposals/08-applicant-discord-oauth.md:129-131`). Section "Web
   SPA" requires the SPA to hold the receipt in browser state for
   BL-017 (`proposals/08-applicant-discord-oauth.md:108-114`). HTTP-
   only cookies are not readable from the SPA, so the cookie variant
   alone does not satisfy "SPA holds receipt". The transfer-endpoint
   variant does. The proposal contains both options but does not
   commit to one. Step 6a must pin the transport so the test-intent
   SPA-storage assertion
   (`proposals/08-applicant-discord-oauth.md:203`) is not testing a
   different mechanism than what ships. This is a contract-clarity
   defect to surface to audit risk; it does not change the shortcut
   verdict because the *security* properties (no receipt in URL, no
   raw OIDC tokens in SPA) hold under either option.

7. **Receipt has forgery protection but no in-TTL replay defense.**
   The HMAC-signed JWT format
   (`proposals/08-applicant-discord-oauth.md:155-172`) has no `jti`,
   no audience, and no server-side issued-receipt registry. Within
   the 10-min TTL, a captured receipt is replayable to any future
   surface that consumes it. For BL-016 this is moot because no
   surface consumes the receipt
   (`proposals/08-applicant-discord-oauth.md:60-61,73-74,114`). For
   BL-017 this becomes load-bearing: the conversion endpoint will
   need to bind the receipt to a specific application id or to a
   server-side single-use token, or rotate the receipt to an
   `aud`-bound form. This is a forward-looking note to capture in
   the BL-017 problem map, not a BL-016 shortcut. It is honest of
   the proposal to ship the minimal forgery-resistant primitive
   without prematurely designing BL-017's replay defense.

8. **Net-value wording overclaims SPA stability.** Net-value
   (`proposals/08-applicant-discord-oauth.md:41`) says BL-016 keeps
   "INIT-120's supported anonymous submit path stable." This is
   true at the `POST /api/v1/public/applications` contract layer
   (anti-scope `proposals/08-applicant-discord-oauth.md:60-61,74`)
   but not at the SPA flow layer (proposal:112 forces an Authentik
   round-trip on first SPA submit). A reasonable reader of the
   net-value sentence would assume the user-facing flow is
   unchanged. Recommend tightening to "keeping the INIT-120 public
   submit *API contract* stable" so the supported-surface verdict
   and audit verdict have an unambiguous claim. This is
   wording-precision, not a shortcut — the SPA changes are
   honestly described in the design section — but it is the kind
   of imprecision that lets a shortcut hide later. Surface to audit
   risk for capture.

9. **Test-intent residuals are honest.** The track explicitly names
   what each test does *not* prove
   (`proposals/08-applicant-discord-oauth.md:197-204`): static
   blueprint checks do not prove live Authentik acceptance; route-
   render checks do not prove browser-through-Pomerium-through-Kong;
   mocked token-endpoint tests do not prove live Authentik token
   behavior; JWKS validation tests do not prove key-rotation caching;
   live e2e cannot prove Discord OAuth without per-developer
   credentials. The required residual artifact at
   `plans/risk/init-127-test-residuals.md`
   (`proposals/08-applicant-discord-oauth.md:208-210`) gives Step 6b
   a shaped place to enumerate any unverified items. This is
   shortcut-resistant test posture: the proposal does not pretend
   mocks prove production behavior.

10. **Per-channel Discord app remote-rollout is named as
    out-of-scope, not silently skipped.** Anti-scope
    (`proposals/08-applicant-discord-oauth.md:64`): "No remote-
    channel Discord app rollout beyond documenting that each remote
    channel needs its own Discord OAuth app and redirect URI." The
    supported-surface track repeats this
    (`proposals/08-applicant-discord-oauth.md:176`). This is the
    correct deferral — remote-channel rollout is a separate Discord
    Developer Portal exercise per channel — and it is honest about
    the operational consequence (each channel needs its own app),
    not pretending one Discord app can serve all channels.

## Verdict

```
SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
```

The proposal establishes a real applicant Discord identity
verification surface — Authentik Discord OAuth Source, distinct
applicant OIDC Provider/Application, claim-mapping chain that lands
the Discord snowflake as a single `discord_user_id` claim, server-
side OIDC code exchange with JWKS validation, and an HMAC-signed
short-lived applicant identity receipt — rather than a placeholder.
The key security choices serve their stated purpose: server-side
exchange keeps raw Authentik OIDC tokens out of the SPA, JWKS
validation covers signature/issuer/audience/expiration, and
`identify`-only scope is least-privilege carried through Discord
scope, Authentik mapping, and receipt format with no silent
expansion path. The HMAC-signed receipt prevents claim forgery and
bounds replay to a 10-min TTL; in-TTL replay defense is correctly
deferred to BL-017's conversion endpoint where a consumer exists.
The BL-017, BL-009, and INIT-120 deferrals are honest at the
contract/architecture level: callback verifies only and writes no
DB state, no Discord-visible side effects, no public submit API
contract change, no Cedar applicant principal. The per-developer
Discord application pattern is workable with a bounded one-time
onboarding tax, fail-loud bootstrap, and honest test-residual
disclosure that mocked tests do not prove live Discord OAuth. Two
contract-clarity defects (receipt-transport ambiguity between
HTTP-only cookie and SPA-readable transfer token, Observation 6;
net-value wording overclaiming SPA stability while SPA submit
flow does change, Observation 8) should be surfaced to audit risk
and resolved at Step 6a, but neither defeats the slice's purpose
nor introduces a security shortcut. No invalidated assumptions and
no non-positive value signal on the current supported surface.
