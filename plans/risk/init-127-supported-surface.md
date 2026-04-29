READ:
- proposals/08-applicant-discord-oauth.md
- research/13-applicant-discord-oauth-problem-map.md
- .tmp/rca/discord-oauth-linking-FINDINGS.md
- /home/nes/ai/workflows/implementation-pipeline.md
- gitops/channels/local/auth/authentik/render-values.yaml
- gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml
- gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml
- gitops/channels/local/auth/pomerium/ingress.yaml
- gitops/channels/local/applications/server-manager/api-ingress.yaml
- gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml
- gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml
- containers/server-manager/nginx-web.conf
- services/api/app/api/v1/router.py
- services/api/app/api/v1/endpoints/applications/public.py
- services/api/app/api/v1/endpoints/me.py
- services/api/app/core/settings.py
- services/web/src/main.tsx
- infra/scripts/bootstrap-infisical-auth.sh
- infra/scripts/bring-up-local-channel.sh

# INIT-127 / BL-016 Phase 4 — Supported-Surface Risk

## Inputs read

- `proposals/08-applicant-discord-oauth.md` — full proposal: scope (lines 43-53), anti-scope (55-64), implementation decisions (66-77), design (78-172), supported-surface track (174-186), assumption register A1–A3 (187-191), test-intent track (193-204), residual-risk artifact link (206-210), migration/rollback (212-232), out-of-scope follow-ups (234-238).
- `research/13-applicant-discord-oauth-problem-map.md` — approved Phase 2.5 problem map: touched surface (53-158), current supported paths (160-203), known brittle behavior (205-245), adjacent blast-radius surfaces (247-285), public/user-reachable paths (287-319), deployment cohort (321-346), open questions (348-405).
- `.tmp/rca/discord-oauth-linking-FINDINGS.md` — RCA: Authentik gap (87-138), identity-linking model options (141-166), conversion service shape (168-198), recommended decomposition into INIT-125A/B/C/D (372-386).
- `~/ai/workflows/implementation-pipeline.md` — Phase 4 risk-gate rules and the supported-surface termination rule (line 106) requiring orthogonal evaluation: invalidated-assumption check first, then non-positive-value check, then LOW/MEDIUM/HIGH verdict.
- Cited evidence from current source: `gitops/channels/local/auth/authentik/render-values.yaml:13-15` (Helm `blueprints.configMaps` mount of `authentik-init-114-blueprint`), `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:47-62` (Pomerium route ordering on `web.local.humility.local`), `gitops/channels/local/auth/pomerium/ingress.yaml:37-60` (web host fronted by Pomerium), `services/api/app/api/v1/endpoints/applications/public.py:18-38` (anonymous Cedar-authorized public submit), `services/api/app/api/v1/endpoints/me.py:18-41` (Pomerium-header officer principal), `services/api/app/api/v1/router.py:1-39` (FastAPI router), `services/web/src/main.tsx:65-160` (current SPA submit), `containers/server-manager/nginx-web.conf:1-31` (static nginx with `/api/` proxy + SPA fallback), `infra/scripts/bootstrap-infisical-auth.sh:368-494` (existing auth bootstrap idempotency), `infra/scripts/bring-up-local-channel.sh:483-604` (Pomerium-only Authentik provider/application reconciliation).

## Termination evaluation

Per `~/ai/workflows/implementation-pipeline.md:106`, evaluate orthogonal termination signals first, in this order: invalidated assumption that breaks the current problem framing → return to research at Phase 2.5; otherwise non-positive value on the current supported surface → terminate; otherwise NONE.

### Invalidated-assumption check

I cross-checked each proposal assumption against current source and the problem map.

- **A1** — Authentik 2026.x supports Discord as an OAuth Source. Local Authentik is `authentik/authentik` chart `2026.2.2` (`research/13-applicant-discord-oauth-problem-map.md:162-164`). Authentik 2026.2 docs document Discord OAuth Source configuration and the Discord callback URI (`https://docs.goauthentik.io/users-sources/sources/social-logins/discord/`). The blueprint model docs list `authentik_sources_oauth.oauthsource` (`https://docs.goauthentik.io/customize/blueprints/v1/models`). The RCA's hookpoint sketch (`.tmp/rca/discord-oauth-linking-FINDINGS.md:118-138`) names the same provider/source/mapping shape. No source today contradicts A1. Invalidation observable: a blueprint apply error from Authentik naming an unknown provider type, an unknown OAuth source slug `discord`, or a schema mismatch on `authentik_providers_oauth2.oauth2provider` / `authentik_core.application` fields used by the proposal.
- **A2** — Pomerium can route callback paths to a server-side handler. Verified at `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:47-62`: existing route table on `web.local.humility.local` has a path-prefix `/admin` route, then a host-level catch-all, then a separate host route for `protected-api.local.humility.local`. The web ingress already directs `web.local.humility.local` to the Pomerium proxy (`gitops/channels/local/auth/pomerium/ingress.yaml:37-60`). The proposal places the new `/auth/discord/` route before the catch-all and points it at the API service with `allow_public_unauthenticated_access: true` and no `pass_identity_headers` (`proposals/08-applicant-discord-oauth.md:97-104`). No source contradicts A2. Invalidation observable: rendered Pomerium config does not contain the new prefix entry before the catch-all, or a live request to `https://web.local.humility.local/auth/discord/callback` reaches the catch-all (web pod) instead of the API service.
- **A3** — The web pod has no native callback host; proposal hosts the handler inside the existing API process and routes `/auth/discord/*` to the API service. Verified at `containers/server-manager/nginx-web.conf:1-31`: web container is static nginx with only `/api/` reverse-proxy + SPA fallback; it cannot terminate OAuth token exchange. The API has FastAPI routing (`services/api/app/api/v1/router.py:1-39`) and Pydantic settings (`services/api/app/core/settings.py:13-35`). No source contradicts A3. Invalidation observable: API ingress middleware rejects non-`/api/v1` public paths, or Pomerium cannot route a `web.local.humility.local` prefix to the `server-manager-api` service.

The proposal is also explicit that A1, A2, and A3 each have a concrete invalidation surface that surfaces during render-test/integration (proposal lines 189-191).

No INVALIDATED_ASSUMPTION signal.

### Non-positive-value check

Existing-state risk on the supported surface is concrete and named. Today there is no Discord OAuth Source, no applicant Authentik Application/Provider, no callback handler, no stable `discord_user_id` claim, and no server-signed applicant identity surface (`.tmp/rca/discord-oauth-linking-FINDINGS.md:106-138`, `research/13-applicant-discord-oauth-problem-map.md:107-147`). Without that surface, BL-017 (member link/conversion + application re-pointing) and BL-009 (Discord-visible applicant flow) cannot proceed without conflating identity verification with conversion or with synthetic-member work. The RCA explicitly recommends decomposition with this slice as INIT-125B identity plumbing only (`.tmp/rca/discord-oauth-linking-FINDINGS.md:372-386`).

The proposal's blast radius is bounded:

- One Authentik blueprint extension (Discord Source, source/user property mapping, provider scope mapping, applicant Provider, applicant Application) authored as a separate blueprint document or as a renamed neutral ConfigMap that preserves the Helm `blueprints.configMaps` mount (`proposals/08-applicant-discord-oauth.md:80-92`, `gitops/channels/local/auth/authentik/render-values.yaml:13-15`).
- One Pomerium route addition on `web.local.humility.local` ahead of the catch-all (`proposals/08-applicant-discord-oauth.md:94-104`).
- One server-side callback handler under `/auth/discord/*` outside the `/api/v1/public/applications` contract (`proposals/08-applicant-discord-oauth.md:118-131`).
- Five new Infisical keys (`DISCORD_OAUTH_CLIENT_ID`, `DISCORD_OAUTH_CLIENT_SECRET`, `APPLICANT_OIDC_CLIENT_ID`, `APPLICANT_OIDC_CLIENT_SECRET`, `APPLICANT_RECEIPT_SIGNING_KEY`) (`proposals/08-applicant-discord-oauth.md:133-145`).
- One SPA submit-time login state branch on `/applications` (`proposals/08-applicant-discord-oauth.md:106-116`).
- Zero changes to `POST /api/v1/public/applications` request/response schema, zero changes to the existing `pomerium` Authentik Provider/Application, zero changes to the existing Pomerium routes for `/admin`, host catch-all, and `protected-api.local.humility.local`, zero `members` mutations, zero `applications` re-pointing, zero Cedar policy edits, zero Discord-visible side effects.

Migration is sequenced so Infisical seeding precedes blueprint application precedes route + handler + SPA work (`proposals/08-applicant-discord-oauth.md:212-222`). Rollback walks the same surface in reverse and explicitly does not require database cleanup because BL-016 writes no member/application rows (`proposals/08-applicant-discord-oauth.md:224-232`). The current-state risk reduction (introducing a verified `discord_user_id` claim path that BL-017/BL-009 can build on, without forcing INIT-120's anonymous submit to change) clearly outweighs the additive blast radius and the rollback burden.

No NON_POSITIVE_VALUE signal.

Termination outcome: NONE. Proceed to LOW/MEDIUM/HIGH verdict.

## Existing-state risk reduction (verified-identity surface for BL-017/BL-009)

The proposal closes the named gaps from the RCA and problem map.

- A separate `server-manager-applicant` Provider/Application is added rather than overloading the existing `pomerium` Provider whose `sub_mode='hashed_user_id'` is appropriate for officer sessions but wrong for applicant Discord-snowflake identity (`research/13-applicant-discord-oauth-problem-map.md:223-226`, `.tmp/rca/discord-oauth-linking-FINDINGS.md:128-138`). This preserves the officer/applicant security boundary at the Authentik object level.
- The Discord OAuth Source is scoped to `identify` only and emits exactly `discord_user_id` (`proposals/08-applicant-discord-oauth.md:86-90`). Email, guilds, guild members, display name, and avatar are explicitly excluded. The receipt schema enforces the same minimal claim surface (`proposals/08-applicant-discord-oauth.md:155-172`). This converts an undefined PII envelope into a typed minimal contract before BL-017 ever touches it.
- The callback exchange is server-side: code → Authentik token endpoint → JWKS validation → claim extraction → HMAC-signed short-TTL receipt (`proposals/08-applicant-discord-oauth.md:122-131`). The SPA never holds raw Authentik ID/access tokens, eliminating the broader browser-security surface called out in the problem map (`research/13-applicant-discord-oauth-problem-map.md:388-392`).
- The receipt is short-lived (default 10 min local) and HMAC-signed with a dedicated `APPLICANT_RECEIPT_SIGNING_KEY`, not derived from Authentik or Pomerium keys (`proposals/08-applicant-discord-oauth.md:141, 165-172`). Replay/PII risk is bounded.
- BL-016 writes no `members` rows, no `applications` rows, and no audit rows (`proposals/08-applicant-discord-oauth.md:73, 173`). Conversion is left intact for BL-017 with a typed receipt as input.
- The blueprint pattern uses two-argument `!Env [VAR, ""]` per the previously-repaired Authentik sharp edge (`proposals/08-applicant-discord-oauth.md:82, gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:32-33`, `research/13-applicant-discord-oauth-problem-map.md:207-211`). The brittle one-argument `!Env` form is avoided.

The fragility shifts from "no applicant identity surface exists" to "applicant identity is a typed minimal claim plus an HMAC-signed short-TTL server-issued receipt", with the conversion step explicitly deferred and named.

Verdict on this dimension: **LOW**.

## Adjacent path safety (officer flows + INIT-120 anon submit)

Adjacent paths I checked:

- **INIT-120 public submit** (`POST /api/v1/public/applications`, `POST /api/public/applications`). The proposal explicitly preserves `PublicApplicationSubmission`, the anonymous Cedar principal `Public::"web-intake.local"`, and the existing route (`services/api/app/api/v1/endpoints/applications/public.py:18-38`, `proposals/08-applicant-discord-oauth.md:74, 60-61`). The receipt is held by the SPA but is not sent on `POST /api/public/applications` in BL-016 (`proposals/08-applicant-discord-oauth.md:114`). The submit redirect is gated behind a future BL-009 redirect that lands with BL-017 (`proposals/08-applicant-discord-oauth.md:236-238`).
- **Officer Pomerium OIDC** (`pomerium` Authentik Provider/Application, `https://authenticate.local.humility.local/oauth2/callback`, `idp_scopes: openid email profile`, `x-pomerium-claim-*` headers). The proposal's anti-scope explicitly forbids modifications to officer OIDC and the existing `pomerium` Provider/Application (`proposals/08-applicant-discord-oauth.md:59-61`). The new applicant Provider is parallel rather than overloading the existing one. `services/api/app/api/v1/endpoints/me.py:18-41` continues to read `x-pomerium-claim-*` headers without a new branch.
- **Pomerium route ordering on `web.local.humility.local`**. Current order: protected `/admin` → host catch-all → `protected-api.local.humility.local` (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:47-62`). The proposal inserts a more specific `/auth/discord/` prefix entry before the catch-all (`proposals/08-applicant-discord-oauth.md:97-104`). The new route is `allow_public_unauthenticated_access: true` and does not pass identity headers, so it cannot accidentally inject Pomerium claim headers into the API callback. The static-render test in the test-intent track verifies route order, target, and policy (`proposals/08-applicant-discord-oauth.md:198`).
- **Public-intake rate limits**. Two ingress definitions: web-host one in `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml` and direct-API one in `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`. The proposal explicitly notes these must not extend to the new callback path (`proposals/08-applicant-discord-oauth.md:183`). The Pomerium rate-limit ingress is path-scoped to the public-intake submit prefix, so a separately declared `/auth/discord/` route does not inherit it as long as the proposal does not add the callback path to those rate-limit ingresses. This is a process-discipline concern and will be visible in the Pomerium render test (`proposals/08-applicant-discord-oauth.md:198`).
- **Web pod surface** (`containers/server-manager/nginx-web.conf:1-31`). The web container's nginx already proxies `/api/*` to the API service and serves the SPA fallback. The proposal does not touch nginx; the callback is reached via Pomerium routing direct to the API service. No web container changes are needed.
- **API ingress surface** (`gitops/channels/local/applications/server-manager/api-ingress.yaml`). The Pomerium-to-API leg of the new callback uses the in-cluster service `server-manager-api.server-manager.svc.cluster.local:8000` (`proposals/08-applicant-discord-oauth.md:101`). The proposal does not extend `protected-api.local.humility.local` ingress; the new route is a Pomerium config-side route, not a Kong host change.
- **Authentik blueprint atomicity**. Authentik blueprints apply atomically per blueprint document (`https://docs.goauthentik.io/customize/blueprints`). The proposal's design adds a "new blueprint document" or "renames the ConfigMap" while preserving the Helm mount (`proposals/08-applicant-discord-oauth.md:82`). If implemented as an additional blueprint document inside the same ConfigMap, an applicant-side error fails only the applicant blueprint and the existing INIT-114 sample-user/group blueprint stays applied. If implemented as a single rewritten blueprint, an applicant-side error could fail both. The proposal allows either; the risk is that the implementation chooses the single-blueprint path and breaks the sample-user blueprint on a typo. The render-test in the test-intent track partly catches this (`proposals/08-applicant-discord-oauth.md:197`). The Helm mount references `authentik-init-114-blueprint` (`gitops/channels/local/auth/authentik/render-values.yaml:13-15`); a ConfigMap rename without updating `render-values.yaml` would break Authentik startup. The proposal flags preserving the mount but does not pin the implementation choice; this is a watch item, not an invalidator.
- **Applicant flow vs. Authentik default authentication flows**. The proposal defaults to a separate applicant Application launch URL (`https://web.local.humility.local/applications`) and a dedicated provider mapping rather than mutating the Pomerium application's flow (`proposals/08-applicant-discord-oauth.md:90, 182`). This avoids the risk that a Discord-source-bound flow short-circuits the existing Pomerium identification stage.

The proposal's anti-scope and supported-surface track address every adjacent path the problem map flagged. The watch item is the blueprint-document choice (extension document vs. rename).

Verdict on this dimension: **LOW**.

## Migration / rollback realism

Migration sequence (`proposals/08-applicant-discord-oauth.md:212-222`):

1. `.env.example` + onboarding docs.
2. Infisical bootstrap seeds new keys under `/auth/local/authentik`.
3. `authentik-config` Secret templates the new env keys.
4. Authentik blueprint adds Discord Source, mappings, applicant Provider, applicant Application.
5. Pomerium `/auth/discord/` route.
6. Callback handler + SPA login state.
7. Static render tests, component tests, mocked callback tests, unchanged live e2e non-regression.

Strengths:

- Order is correct: secrets exist before blueprint apply consumes them; blueprint applies before the Pomerium route is added; route exists before the SPA tries to drive a redirect.
- The bootstrap script is idempotent and explicitly fails when neither Infisical nor env supplies Discord OAuth credentials (`proposals/08-applicant-discord-oauth.md:143`); the silent-no-op pattern flagged in the problem map (`research/13-applicant-discord-oauth-problem-map.md:217-221`) is closed for this slice.
- Rollback walks the surface in reverse (SPA → handler → Pomerium route → blueprint → Infisical secrets); rollback restores INIT-120 anon submit and Pomerium officer auth without database cleanup because no DB rows are written (`proposals/08-applicant-discord-oauth.md:224-232`).
- BL-017/BL-018 conversion and historical cleanup are out of scope so the rollback contract is not entangled with member/application data state.

Watch items:

- Blueprint object deletion on rollback is not specified. Reverting blueprint YAML does not always remove already-applied Authentik objects (Source, Provider, Application, mappings) unless the blueprint uses an explicit deletion shape. The proposal's rollback step 4 says "revert Authentik blueprint entries"; an operator following that literally may leave the live Authentik objects orphaned. Operationally this is recoverable (delete via Authentik admin UI or API), and orphaned applicant objects are inert because the SPA login surface and callback are gone, so the consequence is housekeeping debt rather than a functional regression. Acceptable for a local-first slice; should be explicit in BL-016 implementation notes.
- The render-values mount reference. If the implementation renames the ConfigMap rather than adding a second key, `render-values.yaml:15` must be updated in the same commit. The proposal mentions preserving the mount but does not enumerate the file change; this is an implementation-discipline watch item, not a design-level risk.
- Receipt-signing-key rotation. The proposal generates `APPLICANT_RECEIPT_SIGNING_KEY` if absent but does not document a rotation procedure. Acceptable for BL-016 because TTL is short (10 min default) so an in-flight receipt simply expires after a key swap; operators can rotate by deleting the secret and reapplying. Out of scope for this slice.

Verdict on this dimension: **LOW**.

## Observability (Authentik audit + callback log)

- Authentik audit logs cover Source authentication events, Provider authorization events, and Application launches. The proposal does not modify Authentik audit settings, so existing operator-visible audit continues to apply to the new Source/Provider/Application (`proposals/08-applicant-discord-oauth.md:185`).
- Callback handler emits explicit log lines for: request received, state validation failed, token exchange failed, JWKS validation failed, missing claim, receipt issued, callback completed (`proposals/08-applicant-discord-oauth.md:185`). Each log includes the correlation/state id and excludes raw tokens or secrets.
- The SPA does not need its own observability beyond surfacing handler errors; the test-intent track verifies SPA storage assertions exclude `id_token` and `access_token` keys (`proposals/08-applicant-discord-oauth.md:203`).
- One gap: the proposal does not name a specific log destination or correlation-id format. Local channel logs are pod-scoped and viewable through cluster log aggregation; this is sufficient for the local-first deployment cohort. Remote channels would need a structured-log convention, but remote rollout is explicitly out of scope (`proposals/08-applicant-discord-oauth.md:64, 176`).

Verdict on this dimension: **LOW**.

## Channel-template parity

- The proposal is explicitly local-first: "Deployment mode: local first. Remote channels need their own Discord Developer Portal applications because redirect URIs and client ids are channel-specific" (`proposals/08-applicant-discord-oauth.md:176`).
- All blueprint values are scoped under `gitops/channels/local/auth/authentik/` matching the existing INIT-114 channel pattern (`gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml`, `gitops/channels/local/auth/authentik/render-values.yaml`).
- Channel-specific values (Discord client id/secret, applicant OIDC client id/secret, receipt signing key, applicant redirect URI `https://web.local.humility.local/auth/discord/callback`) come from Infisical at `/auth/local/authentik` (`proposals/08-applicant-discord-oauth.md:133-145`). The Infisical path mirrors the channel naming convention used by the existing `/auth/local/authentik` and `/auth/local/pomerium` paths (`research/13-applicant-discord-oauth-problem-map.md:332-338`).
- The proposal acknowledges that future channels need their own Discord Developer Portal apps and does not commit channel-specific Discord OAuth secrets to GitOps (`proposals/08-applicant-discord-oauth.md:64, 147-151`). The SOPS-encrypted-blueprint section preserves the bootstrap-only SOPS boundary set by `.sops.yaml:1-9` and `infra/scripts/lint-sops-boundary.py`.
- Watch item: when remote channels lift this slice, the applicant redirect URI, Authentik issuer URL, and Pomerium route hostname need parameterization. The proposal does not introduce a channel-template helper for these, but the file layout (`gitops/channels/<channel>/...`) is the established convention and a future remote-channel slice can copy the local layout. This is appropriate for a local-first scope.

Verdict on this dimension: **LOW**.

## LOW/MEDIUM/HIGH verdict

Existing-state risk reduction: **LOW**. Adjacent path safety: **LOW**. Migration / rollback realism: **LOW**. Observability: **LOW**. Channel-template parity: **LOW**.

Overall verdict: **LOW**.

## Assumption-register cross-check

| ID | Statement | Evidence | Invalidation observable | Status |
|---|---|---|---|---|
| A1 | Authentik 2026.x supports Discord as an OAuth Source. | Local chart `authentik/authentik` at `2026.2.2` (`research/13-applicant-discord-oauth-problem-map.md:162-164`); Authentik 2026.2 docs document Discord OAuth Source configuration and the Discord callback URI; blueprint model docs list `authentik_sources_oauth.oauthsource`. | Blueprint apply error naming an unknown provider type or a schema mismatch on `authentik_providers_oauth2.oauth2provider` / `authentik_core.application` fields used by the proposal; Authentik admin UI shows the Discord Source missing after a successful chart deploy. | Cleared. Concrete evidence + observable invalidation. |
| A2 | Pomerium can route callback paths to a server-side handler. | Path-prefix `/admin` route on `web.local.humility.local` followed by host catch-all (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:47-62`); web ingress already routes the host to Pomerium (`gitops/channels/local/auth/pomerium/ingress.yaml:37-60`). | Rendered Pomerium config does not include the new prefix entry before the catch-all, or the static-render test for route ordering fails (`proposals/08-applicant-discord-oauth.md:198`); a live request to `https://web.local.humility.local/auth/discord/callback` reaches the catch-all (web pod) instead of the API service. | Cleared. Concrete evidence + observable invalidation. |
| A3 | The web pod has somewhere to host the callback handler — proposal hosts it in the existing API process and routes `/auth/discord/*` directly to the API service. | Web container is static nginx with only `/api/` proxy + SPA fallback (`containers/server-manager/nginx-web.conf:1-31`); API has FastAPI routing (`services/api/app/api/v1/router.py:1-39`) and Pydantic settings (`services/api/app/core/settings.py:13-35`); the Pomerium route targets `server-manager-api.server-manager.svc.cluster.local:8000` (`proposals/08-applicant-discord-oauth.md:101`). | API ingress middleware rejects non-`/api/v1` public paths, or callback returns 404 from the API; Pomerium cannot route a `web.local.humility.local` prefix to the `server-manager-api` service. | Cleared. Concrete evidence + observable invalidation. |

All three assumptions name evidence and an observable invalidation surface. The proposal does not introduce assumptions outside this register that affect the supported surface.

## Watch signals (not blocking, do not flip the verdict)

- Implementation choice between (a) adding a separate blueprint document inside the existing ConfigMap and (b) renaming the ConfigMap and updating `render-values.yaml:15`. Either is safe; the static-render test in the test-intent track will catch a Helm-mount drift if the rename path is taken without updating render-values.
- Authentik blueprint object deletion on rollback (Source, Provider, Application, mappings) is housekeeping debt, not a functional regression. Implementation notes should call out the manual delete path so operators do not assume blueprint reversion is sufficient.
- Per-developer Discord Developer Portal app credentials. Onboarding requires each developer to paste their own client id/secret; the bootstrap script fails closed when neither Infisical nor env supplies them. This is the documented behavior, but expect first-time-setup friction; not a supported-surface risk.
- Live e2e non-regression must be run after the slice lands to verify the existing 19-web-ui spec still passes with the login surface present but no auth flow exercised (`proposals/08-applicant-discord-oauth.md:204`). The static and component tests do not cover full browser redirect through Kong/Pomerium (residuals are explicit in the test-intent track).
