READ:
- `research/13-applicant-discord-oauth-problem-map.md`
- `plans/BACKLOG.md`
- `.tmp/rca/discord-oauth-linking-FINDINGS.md`
- `plans/proposals/init-114-auth-stack.md`
- `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml`
- `gitops/channels/local/auth/authentik/secrets-infisicalsecret.yaml`
- `gitops/channels/local/auth/authentik/render-values.yaml`
- `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml`
- `gitops/channels/local/auth/pomerium/ingress.yaml`
- `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`
- `gitops/channels/local/applications/server-manager/api-ingress.yaml`
- `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`
- `gitops/channels/local/applications/server-manager/runtime-infisicalsecret.yaml`
- `gitops/channels/local/applications/web/deployment.yaml`
- `infra/scripts/bootstrap-infisical-auth.sh`
- `infra/scripts/bring-up-local-channel.sh`
- `.sops.yaml`
- `.env.example`
- `containers/server-manager/nginx-web.conf`
- `services/web/src/main.tsx`
- `services/api/app/api/v1/endpoints/applications/public.py`
- `services/api/app/api/v1/endpoints/me.py`
- `services/api/app/api/v1/router.py`
- `services/api/app/core/settings.py`
- Authentik docs: `https://docs.goauthentik.io/users-sources/sources/social-logins/discord/`
- Authentik docs: `https://docs.goauthentik.io/add-secure-apps/providers/oauth2/`
- Authentik docs: `https://docs.goauthentik.io/customize/blueprints`
- Authentik docs: `https://docs.goauthentik.io/customize/blueprints/v1/models`

# INIT-127 / BL-016 Phase 3 - Proposal: Authentik Discord OAuth provider for applicants

## Summary

Add the applicant Discord identity-verification surface without changing public application submit. Authentik gets a Discord OAuth Source and a separate server-manager applicant OIDC Provider/Application. The web application adds a submit-time Discord login path on `/applications`, and a server-side callback exchanges the Authentik authorization code, validates the ID token through Authentik JWKS, extracts one claim (`discord_user_id`), and returns a short-lived applicant identity receipt to the SPA.

This slice stops at proof of identity. It does not create members, convert synthetic public-intake members, re-point applications, require receipts on public submit, or touch the existing Pomerium officer OIDC client.

## Net-value statement

BL-016 has positive net value because it establishes the missing Discord identity proof needed by BL-017 and BL-009 while keeping INIT-120's supported anonymous submit path stable. The backlog decomposes the larger linking fix into BL-016 OAuth plumbing, BL-017 conversion/re-pointing, and BL-018 cleanup (`plans/BACKLOG.md:240-247`, `plans/BACKLOG.md:378-389`). BL-009's user-confirmed direction requires applicants to Discord-OAuth before submission in the eventual product path, but that redirect belongs after this identity surface exists (`plans/BACKLOG.md:262-289`). The RCA and problem map both show that Authentik/Pomerium are present locally, but there is no Discord OAuth Source, applicant OIDC client, applicant callback, or stable Discord snowflake claim today (`.tmp/rca/discord-oauth-linking-FINDINGS.md:87-138`, `research/13-applicant-discord-oauth-problem-map.md:106-147`).

## Scope

- Extend the Authentik blueprint ConfigMap with declarative entries for a Discord OAuth Source, source/user property mapping that stores Discord `id`, a provider scope mapping that emits `discord_user_id`, a separate applicant OAuth2/OIDC Provider, and a server-manager applicant Application.
- Extend the Authentik InfisicalSecret template and bootstrap script with applicant Discord OAuth and applicant OIDC client secret keys.
- Add a Pomerium route on `web.local.humility.local` for `/auth/discord/*` to reach the server-side callback handler without affecting `/admin`, `/applications`, or `/api/public/applications`.
- Add a server-side callback handler in the existing API service for `/auth/discord/callback` and receipt-return/fetch paths under `/auth/discord/*`.
- Add API settings for Authentik issuer/JWKS/token endpoint, applicant OIDC client id/secret, applicant receipt signing key, and receipt TTL.
- Add SPA behavior on `/applications`: show Discord login state, redirect to Authentik at submit time if no valid receipt exists, and hold the returned receipt in browser state for this slice.
- Add local developer onboarding and `.env.example` entries for per-developer Discord application client id/secret and applicant receipt/OIDC settings.
- Add static, component, and mocked integration tests listed in the test-intent track.

## Anti-scope

- No member creation.
- No application re-pointing.
- No synthetic-to-real conversion.
- No modifications to officer OIDC or the existing Pomerium `pomerium` Provider/Application.
- No INIT-120 public submit contract change.
- No new Cedar applicant principal or public-submit authorization change.
- No `email`, `guilds`, or `guilds.members.read` Discord scope.
- No Discord-visible side effects.
- No remote-channel Discord app rollout beyond documenting that each remote channel needs its own Discord OAuth app and redirect URI.

## Implementation decisions taken in proposal

- Separate applicant OIDC client in Authentik: use a new server-manager applicant Provider/Application, not the existing Pomerium provider, to preserve officer/applicant security boundaries and audit clarity.
- Server-side OIDC exchange: the API callback exchanges the code, validates the JWT against JWKS, and returns an applicant receipt so the SPA never holds raw Authentik OIDC tokens.
- Discord OAuth scope is `identify` only: this captures the Discord snowflake with the least applicant PII.
- Blueprint-managed Authentik objects: the Discord Source, applicant Provider, and Application live in `gitops/channels/local/auth/authentik/`, matching the committed blueprint pattern (`gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:10-36`).
- Claim contract is only `discord_user_id`: display name, avatar URL, email, guild membership, and role data remain out of scope.
- Callback verifies only: BL-016 does not create or update `members` or `applications`; BL-017 owns conversion and application re-pointing (`plans/BACKLOG.md:391-400`).
- No public submit API change: `POST /api/v1/public/applications` remains the existing anonymous Cedar-authorized path (`services/api/app/api/v1/endpoints/applications/public.py:18-38`).
- Redirect timing is submit-time: `/applications` loads as today; submitting without a receipt redirects to Authentik so first page load remains low-friction.
- Per-developer Discord application for dev: `.env.example` and docs name where each developer pastes their own client id/secret; channel bootstrap reads Infisical first and local runs can fall back to env.

## Design

### Authentik blueprints for Discord OAuth Source + applicant Provider + Application

Add a new blueprint document in `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml` or rename the ConfigMap to a neutral init-127 auth blueprint while preserving the Helm `blueprints.configMaps` mount (`gitops/channels/local/auth/authentik/render-values.yaml:13-15`). The blueprint must use `!Env [VAR, ""]` two-argument forms for all secret-derived values, matching the repaired sample-user pattern (`gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:32-33`).

Expected Authentik entries:

- `authentik_sources_oauth.oauthsource` with slug `discord`, provider type `discord`, consumer key from `DISCORD_OAUTH_CLIENT_ID`, consumer secret from `DISCORD_OAUTH_CLIENT_SECRET`, and scopes exactly `identify`. Authentik 2026.2 docs list Discord OAuth Source and require Discord redirect URI `https://<authentik-host>/source/oauth/callback/discord/` (`https://docs.goauthentik.io/users-sources/sources/social-logins/discord/`).
- OAuth Source property mapping that copies Discord's `info["id"]` into an Authentik user attribute such as `attributes.discord_user_id`. The docs' Discord mapping examples show the Discord API payload exposes `info.get("id")` (`https://docs.goauthentik.io/users-sources/sources/social-logins/discord/`).
- OAuth2 provider scope mapping that emits exactly `{"discord_user_id": request.user.attributes.get("discord_user_id")}` into the applicant ID token. Do not emit email/profile/guild claims.
- `authentik_providers_oauth2.oauth2provider` named `server-manager-applicant`, confidential client, per-provider issuer mode, authorization-code flow, `include_claims_in_id_token: true`, strict redirect URI `https://web.local.humility.local/auth/discord/callback`, and property mappings limited to `openid` plus the custom `discord_user_id` mapping.
- `authentik_core.application` with slug `server-manager-applicant`, provider set to the applicant provider, and launch URL `https://web.local.humility.local/applications`.

Authentik provider endpoints are stable for this design: authorization at `/application/o/authorize/`, token at `/application/o/token/`, JWKS at `/application/o/<application slug>/jwks/`, and OIDC discovery at `/application/o/<application slug>/.well-known/openid-configuration` (`https://docs.goauthentik.io/add-secure-apps/providers/oauth2/`). Authentik blueprints are intended for infrastructure-as-code and apply atomically, so a bad provider/source entry should fail the whole blueprint apply instead of partially mutating Authentik (`https://docs.goauthentik.io/customize/blueprints`).

### Pomerium route for the callback

Add a specific Pomerium route before the existing public web catch-all:

- `from: https://web.local.humility.local`
- `prefix: /auth/discord/`
- `to: http://server-manager-api.server-manager.svc.cluster.local:8000`
- `preserve_host_header: true`
- `allow_public_unauthenticated_access: true`

The current Pomerium config already supports path-prefix routes on the web host: `/admin` is protected, then the host catch-all is public (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:47-57`). The callback route must be more specific than the catch-all and must not pass Pomerium identity headers; Authentik's ID token is the authority for this applicant receipt. The existing web ingress sends `web.local.humility.local` to the Pomerium proxy (`gitops/channels/local/auth/pomerium/ingress.yaml:37-60`), so no new host is required.

### Web SPA

On `/applications`, add a small applicant-auth state module:

- On load, inspect browser storage for `humility.applicantIdentityReceipt`; if present, parse only untrusted metadata needed for UI freshness and optionally call the callback/session endpoint to verify the server signature.
- Render a Login with Discord action near the submit control, but do not redirect on initial page load.
- On submit, if no valid receipt exists, persist the form draft and OIDC `state` in `sessionStorage`, then redirect the browser to Authentik's applicant authorization URL.
- On return from `/auth/discord/callback`, receive the server-issued receipt, store it in memory/session storage, restore the draft, and return to `/applications`.
- If a valid receipt exists, allow the current submit code path to continue unchanged for this slice. The receipt is held by the SPA for BL-017; it is not sent to `POST /api/public/applications` in BL-016.

This builds on the current single-file runtime where `/applications` renders the form (`services/web/src/main.tsx:65-88`) and posts the unchanged payload to `/api/public/applications` (`services/web/src/main.tsx:140-160`).

### Server-side callback handler

Implement the callback in the existing API process under `/auth/discord/*`, outside the `/api/v1/public/applications` contract. The API service is the right local owner because it already has FastAPI routing and Pydantic settings (`services/api/app/api/v1/router.py:1-39`, `services/api/app/core/settings.py:13-35`), while the web pod is static nginx with only `/api/` proxying and SPA fallback (`containers/server-manager/nginx-web.conf:1-31`).

Flow:

1. Receive Authentik authorization code at `GET /auth/discord/callback?code=...&state=...`.
2. Validate `state` against the stored browser nonce or server-side signed state value.
3. Exchange the authorization code with Authentik's token endpoint using applicant OIDC `client_id`, `client_secret`, redirect URI, and authorization-code grant.
4. Validate the returned ID token signature against the applicant Application JWKS, and validate issuer, audience, expiration, issued-at, and nonce where present.
5. Extract `discord_user_id` from the validated ID token. Reject if absent or if it does not match a Discord snowflake string shape.
6. Sign an applicant identity receipt and return it to the SPA by redirecting to `/applications?discord_auth=complete` with a short opaque transfer token, or by setting an HTTP-only short-lived session cookie and returning to `/applications`.

The preferred first implementation is an HTTP-only short-lived cookie because it avoids putting the receipt in the URL. If the SPA must read the receipt directly, use a one-time transfer endpoint that returns the receipt after the callback stores it server-side.

### Infisical secrets for Discord OAuth client id/secret

Extend `/auth/local/authentik` and the generated `authentik-config` Secret with:

- `DISCORD_OAUTH_CLIENT_ID`
- `DISCORD_OAUTH_CLIENT_SECRET`
- `APPLICANT_OIDC_CLIENT_ID`
- `APPLICANT_OIDC_CLIENT_SECRET`
- `APPLICANT_RECEIPT_SIGNING_KEY`

`infra/scripts/bootstrap-infisical-auth.sh` already creates auth folders and sets missing secrets idempotently (`infra/scripts/bootstrap-infisical-auth.sh:368-425`). For local developer mode, the script should read `DISCORD_OAUTH_CLIENT_ID` and `DISCORD_OAUTH_CLIENT_SECRET` from the environment if absent in Infisical and fail with a clear message if neither source exists. It may generate applicant OIDC client secret and receipt signing key if absent. Do not mirror these values into the existing Pomerium OIDC keys; the current mirror is only for the Pomerium client (`infra/scripts/bootstrap-infisical-auth.sh:396-425`, `infra/scripts/bootstrap-infisical-auth.sh:480-494`).

Extend `gitops/channels/local/auth/authentik/secrets-infisicalsecret.yaml` to template the new Authentik values into `authentik-config`, following the existing `OIDC_CLIENT_ID` and `OIDC_CLIENT_SECRET` shape (`gitops/channels/local/auth/authentik/secrets-infisicalsecret.yaml:31-43`). If the callback handler needs the same applicant client secret and receipt key, either add an application runtime InfisicalSecret entry in `gitops/channels/local/applications/server-manager/runtime-infisicalsecret.yaml` or create a narrowly scoped auth-client secret for the API namespace.

### SOPS-encrypted blueprint values

Do not commit Discord client secrets or applicant OIDC secrets into the Authentik blueprint. The current repo's SOPS policy is bootstrap-only under `gitops/bootstrap/*.enc.yaml` (`.sops.yaml:1-9`), and the problem map explicitly records that runtime/auth credentials are expected in Infisical rather than committed SOPS runtime files (`research/13-applicant-discord-oauth-problem-map.md:154-158`).

The blueprint may commit non-secret values such as slugs, redirect URIs, and scope names in plain GitOps YAML. Secret-bearing blueprint fields must use `!Env [VAR, ""]` from the Infisical-managed `authentik-config` Secret. If a future channel requires committed encrypted runtime blueprint values, that is a separate SOPS-boundary change, not part of BL-016.

### Receipt format

Use an HMAC-signed short-lived JWT:

```json
{
  "discord_user_id": "123456789012345678",
  "iat": 1777500000,
  "exp": 1777500600
}
```

Constraints:

- `discord_user_id` is the only identity claim.
- `iat` and `exp` are required.
- TTL should be short, default 10 minutes for local.
- Sign with `APPLICANT_RECEIPT_SIGNING_KEY`.
- Do not include raw Authentik ID/access tokens, Authentik subject, email, display name, avatar, guilds, or roles.
- BL-016 stores no receipt-derived database state.

## Supported-surface track

- Deployment mode: local first. Remote channels need their own Discord Developer Portal applications because redirect URIs and client ids are channel-specific.
- Cohort: web applicants only. Officers remain on existing Pomerium OIDC; `/admin` and `/api/v1/me` keep their Pomerium-header model (`services/api/app/api/v1/endpoints/me.py:18-41`).
- Adjacent path - INIT-114 OIDC: leave the existing Pomerium Provider/Application and `openid email profile` scope set unchanged (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:32-47`).
- Adjacent path - Pomerium routes: add only the specific `/auth/discord/` route; preserve `/admin`, public web catch-all, protected API, and public-intake rate-limit ingress behavior.
- Adjacent path - INIT-120 public submit: no request/response schema change and no receipt requirement; existing route and service continue to accept `PublicApplicationSubmission` (`services/api/app/api/v1/endpoints/applications/public.py:21-38`).
- Adjacent path - Authentik blueprint loader: keep blueprint ConfigMap mounting through Helm and avoid extending `bring-up-local-channel.sh` Authentik API reconciliation for applicant objects (`gitops/channels/local/auth/authentik/render-values.yaml:13-15`, `infra/scripts/bring-up-local-channel.sh:483-604`).
- Blast-radius note: the new applicant provider must not alter default authentication flows used by Pomerium. Prefer a dedicated applicant Application launch URL and provider mapping rather than mutating the Pomerium application.
- Blast-radius note: the new callback route must not accidentally inherit public-intake rate limits, because that rate limit is scoped to application submit paths (`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml:1-32`, `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:1-28`).
- Migration / rollback: revert the Authentik blueprint additions, remove the new Infisical template keys only after rollback no longer references them, remove the Pomerium `/auth/discord/` route, and remove the SPA login/callback behavior. No data migration is involved.
- Observability: rely on Authentik audit logs for source/provider authentication events and add callback handler logs for request received, state validation failed, token exchange failed, JWKS validation failed, missing claim, receipt issued, and callback completed. Logs must include correlation/state id, not raw tokens or secrets.

## Assumption register

- A1: Authentik 2026.x supports Discord as an OAuth Source. Evidence: local Authentik is version `2026.2.2` (`research/13-applicant-discord-oauth-problem-map.md:162-164`), Authentik 2026.2 docs document Discord OAuth Source configuration and the Discord callback URI, and the blueprint model docs list `authentik_sources_oauth.oauthsource` as a blueprint model. Invalidated by the installed chart lacking the Discord provider type or the blueprint model fields differing from docs at runtime.
- A2: Pomerium can route callback paths to a server-side handler. Evidence: current Pomerium config has path-prefix route entries for `/admin` and a catch-all route on `web.local.humility.local` (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:47-57`), and the web ingress already routes the host to Pomerium (`gitops/channels/local/auth/pomerium/ingress.yaml:37-60`). Invalidated by Pomerium route ordering or path-prefix semantics not matching the rendered chart.
- A3: The web pod has somewhere to host the callback handler. Decision: host the handler in the existing API process and route `/auth/discord/*` directly to the API service. Evidence: the web container is static nginx with only `/api/` proxy and SPA fallback (`containers/server-manager/nginx-web.conf:8-23`), while the API has FastAPI routing/settings and can own token exchange/signing (`services/api/app/api/v1/router.py:1-39`, `services/api/app/core/settings.py:13-35`). Invalidated if the API ingress/middleware assumes all public endpoints are under `/api/v1` or if Pomerium cannot route web-host paths to the API service.

## Test-intent track

| Test / group | Named risk | Intended behavior | Selected level | Fixture source | Assumption link | Expected observable signal | Residual risk |
|---|---|---|---|---|---|---|---|
| Authentik blueprint render | Applicant objects missing or accidentally mutate officer OIDC | Rendered blueprint contains Discord Source, applicant Provider, applicant Application, `identify` scope, custom `discord_user_id` mapping, and no changes to `pomerium` Provider/Application | particular-integration | `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml` static parse plus Authentik blueprint schema/render check | A1 | Static assertions pass; rendered/applied blueprint includes expected slugs and excludes Pomerium changes | Static checks may not prove live Authentik accepts every field until local apply |
| Pomerium route render | Callback route is shadowed by catch-all or protects applicants with officer auth | Rendered Pomerium config has `/auth/discord/` before the public catch-all, targets API service, and is public unauthenticated | particular-integration | `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml` render/static parse | A2 | Route order/target assertions pass; `/admin` and catch-all entries remain unchanged | Does not prove full browser redirect through Kong/Pomerium |
| Callback token exchange | Handler trusts a code without server-side exchange | Callback posts authorization code to mocked Authentik token endpoint using applicant client credentials and rejects token endpoint failures | component | FastAPI/httpx test with mocked Authentik token endpoint | A3 | HTTP success only when mock token endpoint returns token JSON; failure maps to non-2xx with no receipt | Mock cannot prove Authentik's live token endpoint behavior |
| Callback JWT validation | Forged or wrong-audience ID token is accepted | Handler validates ID token signature via JWKS plus issuer, audience, and expiration; bad signature is rejected | component | Generated test keypair/JWKS and malformed-token fixtures | A1, A3 | Good token returns receipt; bad signature/wrong aud/expired token returns auth error and logs validation failure | Does not prove key rotation caching under live JWKS changes |
| Receipt claim contract | Receipt leaks extra PII or omits Discord snowflake | Handler returns an HMAC-signed short-lived JWT with only `discord_user_id`, `iat`, and `exp` | unit/component | Callback service test with validated ID token fixture | A3 | Decoded receipt payload has exactly three allowed fields and expected TTL | Browser storage/cookie transport tested separately |
| SPA login redirect | Submit proceeds without verified identity when it should start OAuth | `/applications` submit without receipt stores draft/state and redirects to Authentik applicant authorization URL | component | Playwright/component test around `services/web/src/main.tsx` with location/fetch mocks | A3 | Redirect URL contains applicant client id, redirect URI, state, nonce, response_type=code, and no raw client secret | Does not prove Authentik login screen usability |
| SPA receipt handling | Callback completion loses applicant proof or raw tokens enter SPA storage | SPA receives server completion signal, stores only applicant receipt/session marker, restores draft, and does not store ID/access tokens | component | Web component test with mocked `/auth/discord/session` response or callback redirect | A3 | Storage assertions show receipt/session marker present, form draft restored, no `id_token` or `access_token` keys | Does not prove cookie attributes in a real browser unless e2e includes them |
| Live e2e non-regression | New auth surface breaks current public form while unused | Existing 19-web-ui spec still passes with the login surface present but no auth flow exercised | end-to-end | Existing local web UI e2e contract/spec | A2, A3 | Existing e2e summary remains `pass=19/19`; submit path response shape unchanged | Does not prove live Discord OAuth because per-developer Discord app credentials may be absent |

### Residual-risk artifact

`plans/risk/init-127-test-residuals.md`

If Step 6b cannot verify any named test-intent risk above, it must emit `plans/risk/init-127-test-residuals.md`. Each residual must name the unverified test-intent item, residual class, attempted or considered technique, scope, budget or bound, remaining risk, invalidating inputs, and whether the residual changes the net-value case.

## Migration / rollback

Migration:

1. Add local developer documentation and `.env.example` keys for per-developer Discord OAuth client id/secret and applicant auth settings.
2. Extend Infisical bootstrap so `/auth/local/authentik` has Discord OAuth and applicant OIDC values before Authentik starts applying the blueprint.
3. Extend `authentik-config` templating with the new environment keys.
4. Add the Authentik blueprint entries for Discord Source, property mappings, applicant Provider, and applicant Application.
5. Add the Pomerium `/auth/discord/` route to the API callback handler.
6. Add the callback handler and SPA login/callback behavior.
7. Run static render tests, component tests, mocked callback tests, and the unchanged live web e2e non-regression spec.

Rollback:

1. Revert the SPA login/callback change so `/applications` returns to current submit behavior.
2. Remove or disable the API `/auth/discord/*` callback handler.
3. Remove the Pomerium `/auth/discord/` route.
4. Revert Authentik blueprint entries for the Discord Source, applicant Provider, applicant Application, and applicant mappings.
5. Leave Infisical secrets in place until all deployed manifests no longer reference them; then remove them manually if desired.

Rollback restores the current anonymous public-intake behavior and the current officer Pomerium auth behavior. No database cleanup is needed because BL-016 writes no member/application rows.

## Out of scope for follow-up

- BL-017: member link/conversion + application re-pointing.
- BL-009: Discord-visible side effects, depending on BL-017's linked-member contract.
- INIT-120 public submit redirect to require receipt, landing with BL-017.
