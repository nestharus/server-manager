## Inputs read

READ:
- `proposals/08-applicant-discord-oauth.md`
- `research/13-applicant-discord-oauth-problem-map.md`
- `.tmp/rca/discord-oauth-linking-FINDINGS.md`
- `plans/risk/init-127-audit.md`
- `plans/risk/init-127-scope.md`
- `plans/risk/init-127-shortcut.md`
- `plans/risk/init-127-supported-surface.md`
- `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml`
- `gitops/channels/local/auth/authentik/secrets-infisicalsecret.yaml`
- `gitops/channels/local/auth/authentik/render-values.yaml`
- `gitops/channels/local/auth/authentik/kustomization.yaml`
- `gitops/channels/local/auth/authentik/ingress.yaml`
- `gitops/channels/local/auth/authentik/rendered/authentik-2026.2.2.yaml`
- `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml`
- `gitops/channels/local/auth/pomerium/ingress.yaml`
- `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`
- `gitops/channels/local/auth/networkpolicies.yaml`
- `gitops/channels/local/applications/server-manager/runtime-infisicalsecret.yaml`
- `gitops/channels/local/applications/server-manager/api-deployment.yaml`
- `gitops/channels/local/applications/server-manager/api-service.yaml`
- `gitops/channels/local/applications/server-manager/api-ingress.yaml`
- `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`
- `gitops/channels/local/applications/server-manager/networkpolicies.yaml`
- `infra/scripts/bootstrap-infisical-auth.sh`
- `infra/scripts/bootstrap-infisical-server-manager.sh`
- `infra/scripts/bring-up-local-channel.sh`
- `.sops.yaml`
- `infra/scripts/lint-sops-boundary.py`
- `.env.example`
- `containers/server-manager/nginx-web.conf`
- `services/api/pyproject.toml`
- `services/api/app/main.py`
- `services/api/app/core/factory.py`
- `services/api/app/core/settings.py`
- `services/api/app/contracts/runtime_settings.py`
- `services/api/app/api/v1/router.py`
- `services/api/app/api/v1/endpoints/applications/public.py`
- `services/api/app/api/v1/endpoints/me.py`
- `services/api/app/infrastructure/authz.py`
- `services/api/tests/conftest.py`
- `services/web/index.html`
- `services/web/package.json`
- `services/web/playwright.config.ts`
- `services/web/src/main.tsx`
- `services/web/src/app/router.tsx`
- `services/web/src/RuntimeApp.tsx`
- `services/web/tests/compat.spec.ts`
- `infra/tests/test_auth_stack_contract.py`
- `infra/tests/test_public_intake_rate_limit.py`
- `infra/tests/test_web_ui_contract.py`
- `infra/tests/fixtures/contracts/auth_stack_contract.yml`
- `infra/tests/fixtures/web-ui/contract.json`
- `infra/tests/validate_auth_stack_local.sh`
- `infra/tests/validate_web_ui_local.sh`
- `infra/tests/e2e/tests/19-web-ui.sh`

No hookpoint contradicted approved assumptions A1, A2, or A3.

## Authentik blueprint placement hookpoints

Reusable hookpoints:
- Existing Authentik blueprint ConfigMap: `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:1`. It currently has one mounted blueprint key, `init-114-local-users.yaml`, for the sample group/user only (`gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:10`).
- The only current blueprint entries are `authentik_core.group` and `authentik_core.user` (`gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:18`, `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:25`).
- Helm mounts this ConfigMap through `blueprints.configMaps` with name `authentik-init-114-blueprint` (`gitops/channels/local/auth/authentik/render-values.yaml:13`).
- Kustomize already includes the ConfigMap file (`gitops/channels/local/auth/authentik/kustomization.yaml:7`).

Placement:
- Add a separate data key in the existing ConfigMap, for example `init-127-applicant-discord-oauth.yaml`, instead of appending applicant objects to `init-114-local-users.yaml`.
- Keep the ConfigMap name unless the Helm value is updated at the same time. A new ConfigMap file would require both `kustomization.yaml` and `render-values.yaml` changes; a second data key avoids that extra mount-point churn.
- New blueprint entries belong in this new data key: Discord OAuth Source, source/user property mapping for `attributes.discord_user_id`, applicant provider scope mapping for `discord_user_id`, `server-manager-applicant` OAuth2/OIDC Provider, and `server-manager-applicant` Application.

Conflicting systems:
- `infra/scripts/bring-up-local-channel.sh` imperatively reconciles only the existing Pomerium provider/application (`infra/scripts/bring-up-local-channel.sh:478`, `infra/scripts/bring-up-local-channel.sh:545`, `infra/scripts/bring-up-local-channel.sh:582`). The applicant objects should not be added there unless the proposal is revised away from blueprint-managed objects.

Deletion candidates:
- None. The current sample-user blueprint remains needed for local Authentik/Pomerium validation.

## Pomerium route hookpoints

Reusable hookpoints:
- Pomerium config is templated inside `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:31`.
- Existing web-host route order is protected `/admin` first (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:48`) and public catch-all second (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:54`).
- The API service target already exists as `http://server-manager-api.server-manager.svc.cluster.local:8000` on the protected API route (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:58`).

Exact insertion point:
- Insert the new `web.local.humility.local` `/auth/discord/` route after the `/admin` route block ending at `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:53` and before the public catch-all starting at `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:54`.
- Route shape:
  - `from: https://web.local.humility.local`
  - `prefix: /auth/discord/`
  - `to: http://server-manager-api.server-manager.svc.cluster.local:8000`
  - `preserve_host_header: true`
  - `allow_public_unauthenticated_access: true`
- Do not set `pass_identity_headers`; applicant identity comes from the Authentik ID token, not Pomerium officer headers.

Conflicting systems:
- The catch-all web route at `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:54` would otherwise send `/auth/discord/*` to the static web pod.

Deletion candidates:
- None. The existing `/admin`, web catch-all, and protected API routes remain in scope.

## Web ingress hookpoints

Reusable hookpoints:
- `gitops/channels/local/auth/pomerium/ingress.yaml` already exposes `web.local.humility.local` through Pomerium (`gitops/channels/local/auth/pomerium/ingress.yaml:61`).
- The `web` Ingress routes `/` with `pathType: Prefix` to `pomerium-proxy` (`gitops/channels/local/auth/pomerium/ingress.yaml:80`, `gitops/channels/local/auth/pomerium/ingress.yaml:83`, `gitops/channels/local/auth/pomerium/ingress.yaml:87`).

Required change:
- No ingress change is needed for `web.local.humility.local/auth/discord/*`; the existing host-level Pomerium ingress already catches it.

Adjacent hookpoints:
- The direct API ingress `api.local.humility.local` remains separate (`gitops/channels/local/applications/server-manager/api-ingress.yaml:20`) and should not be used for the web-host callback.
- Public-intake rate-limited ingresses are path-specific and should not include the callback (`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml:24`, `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:37`).

Deletion candidates:
- None.

## API callback handler hookpoints

Reusable hookpoints:
- `services/api/app/core/factory.py` mounts the v1 router at app root with no global prefix (`services/api/app/core/factory.py:89`).
- Endpoint modules currently own their full prefixes, commonly `/api/v1/...`, inside each `APIRouter` (`services/api/app/api/v1/endpoints/applications/public.py:18`, `services/api/app/api/v1/endpoints/me.py:8`).
- The v1 router imports endpoint modules at `services/api/app/api/v1/router.py:11` and includes them at `services/api/app/api/v1/router.py:35`.
- The web container only proxies `/api/` to `/api/v1/` and otherwise serves static files (`containers/server-manager/nginx-web.conf:8`, `containers/server-manager/nginx-web.conf:22`). This supports A3: the callback should be routed directly from Pomerium to the API service, not through nginx.

Route prefix decision:
- A new endpoint module can live at `services/api/app/api/v1/endpoints/auth_discord.py` but define `router = APIRouter(prefix="/auth/discord")`.
- No `/api/v1` prefix is needed for the callback path because Pomerium forwards `/auth/discord/*` straight to the API service and the FastAPI app mounts routers at root.
- Add `auth_discord` to the import tuple in `services/api/app/api/v1/router.py:11` and include it near the other top-level routers after `router = APIRouter()` (`services/api/app/api/v1/router.py:35`).

Supporting hookpoints:
- API settings live in `services/api/app/core/settings.py:13`; add Authentik issuer/token/JWKS URLs, applicant client id/secret, receipt signing key, redirect URI, and receipt TTL there.
- The API test settings fixture is `services/api/tests/conftest.py:179`; any new required settings need test env values there.
- API runtime env is sourced from `server-manager-runtime` in `gitops/channels/local/applications/server-manager/api-deployment.yaml:35`.

Conflicting systems:
- `services/api/app/api/v1/endpoints/me.py:18` trusts Pomerium identity headers for officer/admin identity. The applicant callback must not reuse this principal path.
- The file path `api/v1/endpoints` is slightly misleading for a non-`/api/v1` route, but the current app architecture permits it because prefixes are local to modules.

Deletion candidates:
- None.

## Token exchange + JWKS validation hookpoints

Reusable hookpoints:
- There is no existing OIDC client or JWT verification implementation in `services/api`; searches for `jwt.decode`, `authlib`, `oauthlib`, `cryptography`, `JWKS`, and `id_token` found no reusable API code.
- The only existing outbound HTTP client in production API code is the Cedar client using stdlib `urllib` (`services/api/app/infrastructure/authz.py:6`, `services/api/app/infrastructure/authz.py:31`).
- `httpx` is currently a dev-only dependency for tests (`services/api/pyproject.toml:22`), not an API runtime dependency.

Package hookpoint:
- Add `PyJWT[crypto]` to `services/api/pyproject.toml:6` for ID token validation and receipt signing. PyJWT provides `PyJWKClient` for JWKS lookup and `jwt.decode` validation; the `crypto` extra supplies asymmetric algorithm support.
- Token exchange still needs HTTP. Either move `httpx` from dev dependencies into production dependencies or follow the existing stdlib `urllib` pattern from `app.infrastructure.authz`. Moving `httpx` into production is cleaner for form-encoded token exchange and test transport, but it is a new runtime dependency.

Settings hookpoints:
- Place URL settings in `services/api/app/core/settings.py:13`.
- Expected values:
  - issuer: `https://auth.local.humility.local/application/o/server-manager-applicant/`
  - token endpoint: `https://auth.local.humility.local/application/o/token/`
  - JWKS endpoint: `https://auth.local.humility.local/application/o/server-manager-applicant/jwks/`
  - redirect URI: `https://web.local.humility.local/auth/discord/callback`

NetworkPolicy hookpoints:
- API egress currently allows Postgres, MinIO, and OPAL only (`gitops/channels/local/applications/server-manager/networkpolicies.yaml:97`).
- Authentik ingress currently allows Kong to Authentik/Pomerium entrypoints (`gitops/channels/local/auth/networkpolicies.yaml:75`) and Pomerium to Authentik (`gitops/channels/local/auth/networkpolicies.yaml:148`), but not server-manager-api to Authentik.
- If the API exchanges codes or fetches JWKS against the in-cluster Authentik service, add API egress to Authentik and Authentik ingress from server-manager-api. The Authentik service is `authentik-server` on port 80 targeting 9000 (`gitops/channels/local/auth/authentik/rendered/authentik-2026.2.2.yaml:167`, `gitops/channels/local/auth/authentik/rendered/authentik-2026.2.2.yaml:181`).

Deletion candidates:
- None.

## Receipt format + signing hookpoints

Reusable hookpoints:
- No existing JWT signing helper exists in `services/api`; `cedar_authorization_url` only configures the external Cedar client (`services/api/app/core/settings.py:33`, `services/api/app/core/factory.py:44`).
- Current settings conversion exposes only database URL, Supabase key, and version (`services/api/app/core/settings.py:37`).

Package and implementation hookpoint:
- Use the same `PyJWT[crypto]` dependency for HMAC receipt signing. The receipt can use HS256 with `APPLICANT_RECEIPT_SIGNING_KEY`.
- Add a focused service module such as `services/api/app/services/applicant_discord_auth.py` for state validation, token exchange, ID token claim validation, and receipt issuing. Keep the FastAPI endpoint thin.

Secret location:
- Store `APPLICANT_RECEIPT_SIGNING_KEY` for the API in the `server-manager` Infisical project at `/runtime/local`, then expose it via `gitops/channels/local/applications/server-manager/runtime-infisicalsecret.yaml:30` and `gitops/channels/local/applications/server-manager/api-deployment.yaml:35`.
- Do not put the receipt signing key in the Authentik blueprint. Authentik does not need it.

Deletion candidates:
- None.

## Infisical secret hookpoints

Reusable hookpoints for Authentik blueprint env:
- `infra/scripts/bootstrap-infisical-auth.sh` resolves the Authentik and Pomerium Infisical paths from channel config (`infra/scripts/bootstrap-infisical-auth.sh:149`).
- It creates `/auth/local/authentik` and `/auth/local/pomerium` folders idempotently (`infra/scripts/bootstrap-infisical-auth.sh:465`).
- It has reusable `secret_exists`, `get_secret`, `set_secret_if_absent`, and `set_secret` helpers (`infra/scripts/bootstrap-infisical-auth.sh:368`, `infra/scripts/bootstrap-infisical-auth.sh:383`, `infra/scripts/bootstrap-infisical-auth.sh:396`, `infra/scripts/bootstrap-infisical-auth.sh:413`).
- It seeds Authentik values under `$AUTHENTIK_PATH` and Pomerium OIDC values under `$POMERIUM_PATH` (`infra/scripts/bootstrap-infisical-auth.sh:471`, `infra/scripts/bootstrap-infisical-auth.sh:479`).
- It mirrors only the Pomerium OIDC client id/secret into the Authentik path for the existing Pomerium setup (`infra/scripts/bootstrap-infisical-auth.sh:491`).

New Authentik-path keys:
- Add `DISCORD_OAUTH_CLIENT_ID` and `DISCORD_OAUTH_CLIENT_SECRET` under `$AUTHENTIK_PATH`.
- Add `APPLICANT_OIDC_CLIENT_ID` and `APPLICANT_OIDC_CLIENT_SECRET` under `$AUTHENTIK_PATH` for the applicant provider blueprint.
- `DISCORD_OAUTH_CLIENT_ID` and `DISCORD_OAUTH_CLIENT_SECRET` should be read from the environment when absent and fail clearly if neither Infisical nor env has them. Do not generate fake Discord OAuth app credentials.
- `APPLICANT_OIDC_CLIENT_ID` can use a stable local value such as `humility-local-server-manager-applicant`; `APPLICANT_OIDC_CLIENT_SECRET` can be generated with `generate_secret`.

Expose to Authentik:
- Add those keys to the `authentik-config` managed Secret template in `gitops/channels/local/auth/authentik/secrets-infisicalsecret.yaml:30`, following `OIDC_CLIENT_ID` and `OIDC_CLIENT_SECRET` at `gitops/channels/local/auth/authentik/secrets-infisicalsecret.yaml:42`.

API runtime keys:
- `infra/scripts/bootstrap-infisical-server-manager.sh` is the matching pattern for `/runtime/local` runtime values (`infra/scripts/bootstrap-infisical-server-manager.sh:423`).
- Add API-owned values such as `APPLICANT_OIDC_CLIENT_ID`, `APPLICANT_OIDC_CLIENT_SECRET`, and `APPLICANT_RECEIPT_SIGNING_KEY` there, or create a narrower API auth-client InfisicalSecret if the implementation wants to avoid duplicating applicant client credentials in the generic runtime secret.

Deletion candidates:
- None. Existing Pomerium `OIDC_CLIENT_ID` and `OIDC_CLIENT_SECRET` are not replacement candidates.

## SOPS blueprint values hookpoints

Reusable hookpoints:
- The only SOPS creation rule is bootstrap-only under `gitops/bootstrap/*.enc.yaml` (`.sops.yaml:1`, `.sops.yaml:7`).
- The SOPS lint allowlist is limited to `gitops/bootstrap/sops-sentinel.enc.yaml` and `gitops/bootstrap/infisical-server-bootstrap.enc.yaml` (`infra/scripts/lint-sops-boundary.py:15`, `infra/scripts/lint-sops-boundary.py:17`).
- Runtime-secret-shaped keys outside the allowlist are flagged by `infra/scripts/lint-sops-boundary.py:36` and `infra/scripts/lint-sops-boundary.py:169`.
- Existing blueprint env-var injection uses two-argument `!Env` values (`gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:32`, `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:33`).

Required pattern:
- Commit non-secret blueprint values directly: slugs, names, scopes, redirect URI, and provider metadata.
- Use `!Env [VAR, ""]` for secret-bearing Authentik fields sourced from the `authentik-config` Secret. Do not add committed SOPS-encrypted runtime OAuth values for BL-016.

Deletion candidates:
- None.

## Web SPA hookpoints

Reusable hookpoints:
- `services/web/index.html:11` loads `src/main.tsx`; the TanStack/Solid router files are present but not active in the shipped entrypoint.
- `/applications` is detected by `isApplications()` (`services/web/src/main.tsx:21`) and rendered by `applicationRoute()` (`services/web/src/main.tsx:65`).
- The current form lives at `services/web/src/main.tsx:75`; the submit button is at `services/web/src/main.tsx:84`.
- Current submit posts unchanged anonymous JSON to `/api/public/applications` (`services/web/src/main.tsx:140`, `services/web/src/main.tsx:154`).
- Existing browser state uses `sessionStorage` for `humility.publicApplication.clientApplicationId` (`services/web/src/main.tsx:120`).

Login button placement:
- Add the Discord login state/action inside `applicationRoute()`, adjacent to the form submit area around `services/web/src/main.tsx:84`, so the user sees identity state at the point of submission.
- Add browser-state helpers near `getClientApplicationId()` for applicant receipt/session marker and draft preservation.
- Add callback completion handling in `render()` or a small helper called before `bindApplicationRoute()` so `/applications?discord_auth=complete` can restore draft state and update UI before submission.

Callback integration:
- Redirect targets should use `web.local.humility.local/auth/discord/*`, which Pomerium will forward directly to the API service. The static nginx fallback does not need to serve the callback because `/auth/discord/*` should never hit the web pod after the Pomerium route is inserted.
- If the API uses an HTTP-only cookie, the SPA should call a same-host session endpoint such as `/auth/discord/session` to learn whether identity is present without reading raw Authentik tokens.

Conflicting systems:
- `services/web/src/app/router.tsx` and `services/web/src/RuntimeApp.tsx` are not active from `index.html`; do not add applicant login only to those files unless the entrypoint is changed in the same implementation.
- Current Playwright compatibility tests expect a direct public submit to `/api/public/applications` (`services/web/tests/compat.spec.ts:93`). If submit without receipt redirects to Authentik, this test must be deliberately updated or supplied a valid mocked/session marker.

Deletion candidates:
- None for BL-016.

## Test surface hookpoints

Authentik blueprint render test:
- Extend or add an infra test next to `infra/tests/test_auth_stack_contract.py:18`.
- Parse `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml` and assert the new data key contains:
  - `authentik_sources_oauth.oauthsource`
  - Discord source slug/name
  - `identify` scope only
  - `discord_user_id` source/provider mappings
  - `server-manager-applicant` Provider/Application
  - no mutation of the Pomerium provider/application.
- Also extend `infra/tests/validate_auth_stack_local.sh` static checks after kustomize render (`infra/tests/validate_auth_stack_local.sh:177`) and no-secret-literal checks (`infra/tests/validate_auth_stack_local.sh:214`).

Pomerium config render test:
- Add assertions around the `config.yaml` string in `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:31`.
- Assert route order: `/admin`, then `/auth/discord/`, then web catch-all.
- Assert `/auth/discord/` targets `server-manager-api.server-manager.svc.cluster.local:8000`, is public unauthenticated, preserves host, and does not pass identity headers.
- Extend `infra/tests/test_public_intake_rate_limit.py:91` to assert the callback path is not bound to `public-intake-rate-limit`.

API callback handler unit/component:
- Add `services/api/tests/test_auth_discord_callback.py`.
- Reuse `httpx.AsyncClient`/ASGI fixtures from `services/api/tests/conftest.py:313`.
- Add required test settings to `services/api/tests/conftest.py:179` if new API settings are required at app construction.
- Component tests should mock token exchange, mock JWKS/keys, validate issuer/audience/expiration, reject malformed `discord_user_id`, and assert the receipt contains only `discord_user_id`, `iat`, and `exp`.

SPA Login button component test:
- Extend `services/web/tests/compat.spec.ts:88` or add a sibling spec.
- Extend the contract fixture at `infra/tests/fixtures/web-ui/contract.json:36` with applicant auth fields: login button label, authorization URL shape, draft storage key, callback/session endpoint, and forbidden storage keys (`id_token`, `access_token`).
- Keep using Playwright route interception (`services/web/tests/compat.spec.ts:93`) for mocked session/callback behavior.

19-web-ui non-regression:
- `infra/tests/e2e/tests/19-web-ui.sh:35` runs the web UI validator and browser flow, then verifies persisted public submit state.
- The current e2e assertion expects a queued application attached to a synthetic `public:` member (`infra/tests/e2e/tests/19-web-ui.sh:23`, `infra/tests/e2e/tests/19-web-ui.sh:31`).
- If BL-016 introduces submit-time redirect without a receipt, this existing e2e must either seed a valid applicant session/receipt before submit or be split into two flows: old anonymous-submit API non-regression and new OAuth-start UI behavior.

## Conflicting systems / deletion candidates

Conflicting systems:
- Existing Authentik management is split: sample local users are blueprint-managed, but Pomerium provider/application is imperatively reconciled in `bring-up-local-channel.sh`. BL-016 should keep applicant provider/application blueprint-managed per proposal and avoid expanding the Pomerium imperative reconciler.
- Pomerium web catch-all currently shadows `/auth/discord/*` unless the new route is inserted before it.
- API NetworkPolicies currently block server-manager-api from calling Authentik unless explicit egress/ingress is added.
- Existing officer identity uses Pomerium headers in `/api/v1/me`; applicant receipt logic must not treat those headers as applicant proof.
- The web app has inactive Solid/TanStack files alongside the active string-rendered `main.tsx`. The applicant login UI must be added to the active entrypoint unless the implementation explicitly migrates the entrypoint.
- Approved proposal text has a test-surface tension: one test intent says submit without a receipt redirects to Authentik, while the existing 19-web-ui non-regression expects unauthenticated public submit to complete. This does not invalidate A1-A3, but implementation planning must make the test setup explicit.

Deletion candidates:
- None identified for BL-016. Existing Pomerium OIDC objects, public submit API, sample-user blueprint, public-intake rate-limit resources, and e2e public-submit checks remain adjacent supported surfaces.

## New files required

Likely new source files:
- `services/api/app/api/v1/endpoints/auth_discord.py`
- `services/api/app/services/applicant_discord_auth.py`
- Possibly `services/api/app/contracts/applicant_discord_auth.py` if callback/session responses need Pydantic contracts instead of inline endpoint models.
- `services/api/tests/test_auth_discord_callback.py`

Likely new or extended infra test files:
- Either extend `infra/tests/test_auth_stack_contract.py` or add `infra/tests/test_applicant_discord_oauth_auth_stack.py`.
- Either extend `infra/tests/test_public_intake_rate_limit.py` or add a focused Pomerium route test.

Likely new or extended web test files:
- Either extend `services/web/tests/compat.spec.ts` or add `services/web/tests/applicant-discord-auth.spec.ts`.

No new Authentik blueprint file is strictly required if the implementation adds a second data key to `bootstrap-blueprint-configmap.yaml`.

## Notable observations

- A1 is still supported by the repo shape: Authentik 2026.2.2 is the rendered local chart version and the blueprint mount point exists.
- A2 is still supported: `web.local.humility.local` already enters Pomerium and Pomerium config already has ordered route entries.
- A3 is still supported: the API can host `/auth/discord/*` at app root, while static nginx cannot own the server-side callback.
- The only material hookpoint not called out explicitly in the proposal is NetworkPolicy: the API needs a permitted path to Authentik for token exchange and JWKS fetch.
- Prefer `PyJWT[crypto]` over `python-jose` for this repo unless a later design chooses a full OAuth framework. PyJWT currently has first-class JWKS lookup support through `PyJWKClient`; the repo does not need a server-side OAuth framework for one authorization-code callback.
