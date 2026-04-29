READ:
- plans/BACKLOG.md
- .tmp/rca/discord-oauth-linking-FINDINGS.md
- plans/proposals/init-114-auth-stack.md
- docs/init-114-application-auth-handoff.md
- .tmp/rca/oauth-flow-loop-FINDINGS.md
- .tmp/rca/oauth-flow-loop-rca.md
- gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml
- gitops/channels/local/auth/authentik/secrets-infisicalsecret.yaml
- gitops/channels/local/auth/authentik/render-values.yaml
- gitops/channels/local/auth/authentik/ingress.yaml
- gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml
- gitops/channels/local/auth/pomerium/ingress.yaml
- gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml
- gitops/channels/local/auth/pomerium/local-all-in-one-patch.yaml
- gitops/channels/local/auth/pomerium/kustomization.yaml
- gitops/channels/local/applications/server-manager/api-ingress.yaml
- gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml
- gitops/channels/local/applications/server-manager/kustomization.yaml
- gitops/channels/local/dns/auth-ingress-aliases.yaml
- infra/scripts/bootstrap-infisical-auth.sh
- infra/scripts/bring-up-local-channel.sh
- infra/scripts/lint-sops-boundary.py
- .sops.yaml
- containers/server-manager/nginx-web.conf
- containers/server-manager/Containerfile.web
- gitops/channels/local/applications/web/deployment.yaml
- policy/cedar/channels/local/services/server-manager-api/policies.json
- policy/cedar/channels/local/services/server-manager-api/service-identities.json
- policy/cedar/channels/local/services/server-manager-api/manifest.yaml
- services/web/src/main.tsx
- services/web/src/api/client.ts
- services/web/src/app/router.tsx
- services/web/src/RuntimeApp.tsx
- services/web/src/features/public/HomeRoute.tsx
- services/web/src/features/forms/DarkNemesisForm.tsx
- services/api/app/api/v1/endpoints/applications/public.py
- services/api/app/api/v1/endpoints/applications/lifecycle.py
- services/api/app/api/v1/endpoints/applications/_shared.py
- services/api/app/api/v1/endpoints/me.py
- services/api/app/contracts/applications.py
- services/api/app/contracts/members.py
- services/api/app/services/applications.py
- services/api/app/services/authorization.py
- services/api/app/services/members.py
- services/api/app/repositories/members.py
- migrations/versions/wu-043_members_kind.py
- services/api/tests/test_public_application_route.py
- services/api/tests/test_public_intake_submit.py
- services/api/tests/test_public_intake_synthetic_member.py
- services/api/tests/test_web_identity.py

# INIT-127 / BL-016 Applicant Discord OAuth Problem Map

## Touched surface

- `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml`
  likely grows beyond the current INIT-114 local user/group blueprint. Expected
  objects: Discord OAuth Source, applicant-facing authentication or enrollment
  flow wiring, source/property mappings that persist Discord's snowflake, an
  applicant OIDC provider, and an Authentik Application for the web/API callback.
  If blueprints prove brittle for OAuth provider setup, the existing pattern in
  `infra/scripts/bring-up-local-channel.sh` is a precedent for reconciling
  Authentik provider/application records through the Authentik API instead.

- `gitops/channels/local/auth/authentik/secrets-infisicalsecret.yaml` and
  `infra/scripts/bootstrap-infisical-auth.sh` need new Infisical keys for
  Discord OAuth credentials and probably applicant OIDC client credentials. The
  existing script seeds `/auth/local/authentik` and `/auth/local/pomerium`, then
  mirrors Pomerium OIDC client id/secret into the Authentik path. BL-016 needs a
  separate secret shape for the Discord OAuth Source, and probably a separate
  server-manager applicant OIDC client id/secret from Pomerium's client.

- `infra/scripts/bring-up-local-channel.sh` is in the blast radius if applicant
  OIDC provider/application setup follows the current Pomerium pattern. Today it
  creates or patches only the `pomerium` OAuth2Provider and Application with
  redirect URI `https://authenticate.local.humility.local/oauth2/callback`,
  `sub_mode=hashed_user_id`, and openid/email/profile mappings.

- `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml` and
  `gitops/channels/local/auth/pomerium/ingress.yaml` may need a route entry and
  ingress exposure for the applicant callback path, depending on whether the
  callback lands on the web host through Pomerium or directly on API/web through
  Kong. Today Pomerium protects `/admin` on `web.local.humility.local`, leaves
  the rest of that host public, and protects all of
  `protected-api.local.humility.local`.

- `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml` and
  `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`
  are adjacent because they bind rate limits to public intake paths. A new
  callback path such as `/auth/discord/callback` should be routed deliberately
  rather than accidentally inheriting the wrong public-intake behavior.

- `containers/server-manager/nginx-web.conf` is a likely routing hook if the web
  callback or session endpoint is served on `web.local.humility.local`. Current
  `/api/` proxying rewrites to the API service under `/api/v1/`, which is why
  the SPA's `fetch("/api/public/applications")` reaches
  `/api/v1/public/applications`.

- `services/web/src/main.tsx` is the active public submit surface. It renders
  `/applications`, stores a public client application id in `sessionStorage`,
  and posts unauthenticated JSON to `/api/public/applications`. BL-016 likely
  adds login/callback state handling here or replaces this thin runtime with a
  routed component that can read applicant session state.

- `services/web/src/api/client.ts` only models Pomerium current-principal reads
  for admin flows. It has no applicant OIDC/session client today.

- `services/api/app/api/v1/endpoints/applications/public.py` currently accepts
  `PublicApplicationSubmission`, depends only on `authorize_public_intake`, and
  calls `submit_public_application()`. BL-016 likely adds an alternate
  OAuth-authenticated submit contract or an optional verified Discord claim
  token path while keeping the anonymous INIT-120 path until BL-017/redirect work
  replaces it.

- `services/api/app/contracts/applications.py` likely needs a request/receipt
  contract for applicant Discord identity proof. Current
  `PublicApplicationSubmission` has only `scope`, `responses`, and
  `client_application_id`; there is no token, session, issuer, or
  `discord_user_id` field.

- `services/api/app/services/applications.py` is the public submit owner. Current
  `submit_public_application()` deterministically creates or resolves a
  `public_intake` member and submits under service actor `public-intake`. BL-016
  should not mutate existing applications, but this service is where the later
  redirect to real Discord identity will converge.

- `services/api/app/services/members.py`,
  `services/api/app/repositories/members.py`, and
  `services/api/app/contracts/members.py` are adjacent because the verified
  Discord snowflake must ultimately map to `members.discord_user_id` and current
  member kinds are only `discord` and `public_intake`. BL-016 should establish
  verification surface, not the BL-017 conversion service.

- `services/api/app/api/v1/endpoints/me.py` currently trusts Pomerium headers
  and returns `CurrentPrincipalRead(provider="pomerium")`. Applicant OIDC should
  not be mistaken for this officer/admin principal surface unless the proposal
  deliberately routes it through Pomerium.

- `policy/cedar/channels/local/services/server-manager-api/policies.json` may
  need a new policy entry if the applicant OIDC client is represented as a Cedar
  principal. Current public submit is authorized as
  `Public::"web-intake.local"` for
  `Action::"application:submit_public"` on
  `Resource::"server-manager-api:public-applications"`. A simpler BL-016 design
  may verify the Discord claim at the API edge and leave Cedar unchanged until
  submit is actually redirected.

- `policy/cedar/channels/local/services/server-manager-api/service-identities.json`
  is probably not the right place for applicant identities. It currently models
  Kubernetes service account identities for Buildkite and Crossplane, not
  browser users.

- SOPS files are a policy surface, but not necessarily a touched implementation
  surface. `.sops.yaml` and `infra/scripts/lint-sops-boundary.py` enforce a
  bootstrap-only SOPS boundary for `gitops/bootstrap/*.enc.yaml`. Current
  runtime/auth credentials are expected to be operator-seeded or generated in
  Infisical, not committed as SOPS-encrypted application OAuth secrets.

## Current supported paths

- Authentik is deployed locally at `auth.local.humility.local` from the
  `authentik/authentik` chart, version `2026.2.2`. The committed blueprint
  creates only the local sample group and user.

- Pomerium is deployed locally at `authenticate.local.humility.local` and fronts
  protected routes. It uses an Authentik OIDC provider/application named
  `pomerium`, reconciled by `infra/scripts/bring-up-local-channel.sh`, not by the
  committed Authentik blueprint.

- Officer/sample-user OIDC works through the Pomerium provider shape: Pomerium
  requests `openid email profile`; Authentik issues claims; Pomerium forwards
  `x-pomerium-claim-sub`, `x-pomerium-claim-email`,
  `x-pomerium-claim-groups`, and `x-pomerium-claim-name` on protected routes.
  The API `/api/v1/me` reads those headers for web/admin identity.

- Pomerium protects `/admin` on `https://web.local.humility.local` and all of
  `https://protected-api.local.humility.local`. The root web shell and
  `/applications` remain public.

- INIT-120 public submit works anonymously. The SPA posts to
  `/api/public/applications`; nginx rewrites that to
  `/api/v1/public/applications`; the endpoint authorizes the fixed Cedar
  principal `Public::"web-intake.local"` and then creates a queued application.

- Anonymous public submit currently creates or reuses a `members` row with
  `kind='public_intake'` and a `discord_user_id` shaped as `public:<digest>`.
  The application is submitted under service actor `public-intake`, not under an
  applicant user actor.

- `members.kind` is already present from INIT-125A. Existing rows are classified
  as `discord` or `public_intake`, and synthetic guards now use kind-aware
  behavior instead of prefix-only checks.

- Discord submission service for officer/Discord-side flows uses the bot token
  and API calls. It is not a user OAuth flow and does not provide applicant
  Discord OAuth identity.

- NEEDS_RESEARCH: whether the current live local cluster still has a fully
  functioning Pomerium session after the Authentik callback. The RCA shows
  Authentik token/userinfo exchange can succeed when driven through the canonical
  OAuth URL, but BL-016 should not assume browser session persistence without a
  smoke test.

## Known risky or brittle behavior already present

- Authentik blueprint YAML has a known sharp edge around `!Env`: the previous
  INIT-114 recovery hit Authentik's one-element-list failure and fixed
  `!Env [SAMPLE_USER_PASSWORD]` to `!Env [SAMPLE_USER_PASSWORD, ""]`. New
  blueprint entries must use two-argument `!Env [VAR, default]` forms.

- The existing Authentik sample-user blueprint and the Pomerium OIDC bootstrap
  are split across GitOps YAML and an imperative script. Adding applicant OAuth
  partly in one and partly in the other could create ordering drift or leave
  live Authentik records different from Git.

- `bring-up-local-channel.sh` talks directly to Authentik's API through a host
  port-forward and silently skips bootstrap on missing inputs or readiness
  failures. That is workable for local-first recovery, but applicant OAuth would
  need explicit validation so missing Discord credentials do not look like a
  successful no-op.

- The current Pomerium provider uses `sub_mode='hashed_user_id'`. That is
  appropriate for Pomerium's officer session, but applicant identity needs a
  stable Discord snowflake claim. Reusing Pomerium's provider risks confusing an
  Authentik user subject with the Discord user id.

- SOPS+age is bootstrap-only in this repo. Runtime credentials, including auth
  stack credentials, are expected to live in Infisical. Adding committed
  SOPS-encrypted Discord OAuth secrets would conflict with the current lint
  boundary unless the proposal explicitly changes the channel policy.

- Public submit still stores a `client_application_id` in browser
  `sessionStorage` and posts without applicant identity. BL-016 must avoid
  treating that browser-generated id as proof of identity.

- The public route currently depends on a broad fixed Cedar public principal.
  If the OAuth path simply adds a Discord claim while leaving the anonymous
  authorization path as-is, tests must prove the verified claim is required only
  for the new authenticated branch and not silently accepted from client JSON.

- Authentik OAuth flow tests are easy to drive incorrectly. The RCA showed that
  calling the flow executor directly without preserving the nested OAuth query
  and `next=/application/o/authorize/...` context produces misleading
  `xak-flow-redirect` loops.

## Adjacent surfaces inside the blast radius

- INIT-114 Pomerium/sample-user OIDC must not regress. The new applicant
  provider should be parallel to the `pomerium` provider rather than overloading
  it with applicant-specific claims or callback URLs.

- Pomerium route ordering on `web.local.humility.local` matters. Current config
  has a protected `/admin` route followed by a public catch-all route. A callback
  route must be explicit enough that it is not accidentally protected as admin or
  treated as generic public content.

- The public web host has two rate-limit ingress definitions near public intake:
  one in the auth/Pomerium subtree for web-host paths, and one in the
  server-manager API subtree for direct API host paths. The OAuth callback should
  have its own expected ingress behavior.

- INIT-120 public submit should remain supported during BL-016. This slice adds
  an OAuth-authenticated path or verification surface, but does not force
  `/applications` to redirect and does not replace the anonymous submit endpoint
  until BL-017's conversion service and the follow-on redirect are ready.

- The application lifecycle and audit surfaces are adjacent. Public submit
  currently emits `application.submit` and automatic `application.route` actions
  under service actor `public-intake`. BL-016 should avoid introducing
  application re-pointing or historical mutation before BL-017.

- Cedar policy is adjacent but may not need a new applicant principal yet. If
  claim verification happens entirely at the API edge, Cedar can continue
  authorizing the temporary anonymous public path until the forced-auth redirect
  is implemented.

- `members.kind` is adjacent because public-intake rows are now explicitly typed.
  The applicant OAuth surface should preserve the distinction between
  `public_intake` synthetic members and real `discord` members for BL-017.

- Web admin current-principal and applicant identity should remain separate.
  `CurrentPrincipalRead(provider="pomerium")` is an officer/admin header model,
  not an applicant Discord claim model.

## Adjacent public or user-reachable paths

- `https://web.local.humility.local/` is the public web shell.

- `https://web.local.humility.local/applications` is the current public
  application form. It submits without OAuth today.

- `https://web.local.humility.local/api/public/applications` is the web-hosted
  public submit path used by the SPA and proxied to the API.

- `https://api.local.humility.local/api/v1/public/applications` is the direct
  public API submit path with rate limiting.

- `https://web.local.humility.local/auth/discord/callback` is the likely
  applicant callback URL if the web host owns callback/session completion.
  NEEDS_RESEARCH: the proposal must choose web callback vs API callback and exact
  path.

- `https://auth.local.humility.local/source/oauth/callback/discord/` is the
  candidate Discord OAuth Source callback into Authentik from the RCA. The exact
  path must be verified against the Authentik 2026.2.2 source slug and provider
  setup during hookpoint research.

- `https://auth.local.humility.local/application/o/<applicant-app>/` is the
  expected Authentik OIDC issuer/application surface for the applicant client,
  with the exact slug to be chosen in proposal.

- `https://authenticate.local.humility.local/oauth2/callback` is the existing
  Pomerium callback. It should remain dedicated to Pomerium unless the proposal
  intentionally routes applicants through Pomerium.

- Authentik admin UI at `https://auth.local.humility.local` is user-reachable to
  operators and will show any new Source, Provider, Application, mappings, and
  flows.

## Deployment mode and cohort

- Local-first. BL-016 should land and validate against the local channel before
  remote channels.

- Local uses hosts under `*.local.humility.local`, local Step CA TLS, Kong
  ingress, Authentik, Pomerium, and Infisical project `platform-auth` with
  environment `local`.

- Remote channels need their own Discord Developer Portal OAuth application or
  at least their own redirect URI and client secret. Discord OAuth client
  credentials are per-environment deployment inputs, not code constants.

- Existing local auth secrets live in Infisical paths `/auth/local/authentik`
  and `/auth/local/pomerium`. The cleanest candidate is either a new
  `/auth/local/discord` path for Discord OAuth client credentials, or adding
  Discord OAuth keys under `/auth/local/authentik` if only Authentik consumes
  them. This is an implementation decision with onboarding consequences.

- Existing SOPS+age files should remain bootstrap-only unless the proposal
  explicitly changes that policy. New Discord OAuth client material should be
  operator-supplied or generated into Infisical, not added as a normal GitOps
  secret.

- Cohort is applicants on the public application flow. Officers/admins continue
  using the Pomerium protected surface and sample-user/local Authentik flow.

## Open questions for proposal

- IMPLEMENTATION: Do we add a separate applicant OIDC client in Authentik, or
  reuse the officer/Pomerium client with a different scope claim? Current
  evidence favors a separate applicant provider/application because Pomerium's
  provider uses hashed Authentik subject semantics and protects officer/admin
  routes.

- AMBIGUOUS: Where does the Discord OAuth client id/client secret come from in
  dev: a per-developer Discord application, or a shared local-only test app?
  This affects onboarding, redirect URI ownership, and whether local bootstrap
  can be fully automated.

- IMPLEMENTATION: Does the Discord-claim token live in the SPA session, or does
  the callback exchange it for a server-side API session before submit? A
  server-side exchange reduces client-side claim spoofing risk, but requires a
  session or signed receipt contract that does not exist today.

- AMBIGUOUS: What Discord OAuth scopes should Authentik request? `identify` is
  sufficient for a stable snowflake; `email` increases applicant PII collection;
  `guilds` or `guilds.members.read` would imply guild-membership gating and
  broader privacy/security review.

- UX: Should `/applications` redirect to OAuth on form load, or wait until the
  user hits Submit? This should go to HCI research, not a user gate at this
  phase.

- IMPLEMENTATION: Should the Authentik applicant Source/Provider/Application be
  managed declaratively in blueprints or reconciled through the Authentik API in
  `bring-up-local-channel.sh` like the current Pomerium provider?

- IMPLEMENTATION: What exact claim name should the API require for the Discord
  snowflake: `discord_user_id`, a namespaced claim, or a userinfo lookup? The
  proposal needs a single contract and tests for missing, malformed, wrong
  issuer, and wrong audience cases.

- IMPLEMENTATION: Should the BL-016 callback contract only verify and return a
  signed applicant identity receipt, or should it also create a real
  `members.kind='discord'` row when no member exists? Creating members starts to
  overlap BL-017 unless tightly scoped.

- IMPLEMENTATION: Does the API validate the applicant OIDC ID token directly via
  Authentik JWKS, or should the web callback exchange the code server-side and
  store only a server-signed claim receipt? Direct SPA-owned ID token handling is
  a wider browser security surface.

- PRODUCT: Is email collection allowed or desired for applicants if Discord
  offers it? If not, keep scope to `identify` and avoid emitting email into API
  contracts.

- PRODUCT: Is guild membership required before submission, or is proving control
  of a Discord account enough? Guild gating changes Discord scopes, error
  states, and onboarding copy.

- AMBIGUOUS: Should remote channels share one Discord Developer application with
  multiple redirect URIs, or have per-channel Discord Developer applications?
  This affects operational ownership and secret rotation.
