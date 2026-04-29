READ:
- proposals/08-applicant-discord-oauth.md
- research/13-applicant-discord-oauth-problem-map.md
- .tmp/rca/discord-oauth-linking-FINDINGS.md
- ~/ai/workflows/implementation-pipeline.md
- plans/BACKLOG.md
- gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml
- gitops/channels/local/auth/authentik/render-values.yaml
- gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml
- services/api/app/api/v1/router.py
- services/api/app/api/v1/endpoints/applications/public.py
- services/api/app/core/settings.py
- services/web/src/main.tsx

# INIT-127 / BL-016 Phase 4 — Scope Risk

**Verdict:** LOW
**Supported-surface termination signal:** none observed in this dimension (handled by the supported-surface report)
**Re-runs against revisions:** none yet

This report evaluates only scope coherence. Audit checklist obligations, assumption-register evidence, and net-value/blast-radius are owned by the audit and supported-surface reports.

## 1. Scope ↔ Anti-scope coherence

| Scope item | Matched anti-scope guard | Coherent? |
|---|---|---|
| Authentik blueprint adds Discord OAuth Source, source/property mapping, applicant Provider, applicant Application, scope-mapping for `discord_user_id` | "No modifications to officer OIDC or the existing Pomerium `pomerium` Provider/Application"; "No `email`, `guilds`, or `guilds.members.read` Discord scope" | Yes — the new objects are additive and the proposal states scopes are exactly `identify` and the Pomerium Provider/Application is untouched (`proposals/08-applicant-discord-oauth.md:178-182`). |
| Pomerium route on `/auth/discord/*` | "preserve `/admin`, public web catch-all, protected API, and public-intake rate-limit ingress behavior" | Yes — proposal explicitly orders the new route above the existing `web.local.humility.local` catch-all and excludes Pomerium identity headers (`proposals/08-applicant-discord-oauth.md:96-104`). |
| Callback handler under `/auth/discord/*` in API service | "No INIT-120 public submit contract change"; "No new Cedar applicant principal or public-submit authorization change" | Yes — the callback is a sibling route, not a public-submit dependency. `services/api/app/api/v1/endpoints/applications/public.py:18-38` keeps `authorize_public_intake` and `PublicApplicationSubmission` unchanged, and the proposal commits to no Cedar principal change. |
| Receipt format: HMAC short-lived JWT with only `discord_user_id`, `iat`, `exp` | "No `email`, `guilds`, or `guilds.members.read` Discord scope"; "Discord-visible side effects" anti-scope | Yes — receipt is a closed claim set; proposal explicitly excludes Authentik tokens, subject, email, display name, avatar, guild, role data (`proposals/08-applicant-discord-oauth.md:166-172`). |
| SPA submit-time redirect | "No INIT-120 public submit contract change" | Coherent at the **API contract** layer — see the watch signal below for the SPA-UX nuance. |
| Per-developer Discord application docs + `.env.example` | "No remote-channel Discord app rollout beyond documenting that each remote channel needs its own Discord OAuth app and redirect URI" | Yes — proposal limits to documentation, not blueprint or scripted remote-app provisioning. |
| Static, component, and mocked integration tests in test-intent track | (no anti-scope conflict) | Yes — test track stops at component/particular-integration plus the unchanged 19-web-ui live e2e non-regression. |

**Watch signal (non-blocking):** the net-value statement says BL-016 keeps "INIT-120's supported anonymous submit path stable" (`proposals/08-applicant-discord-oauth.md:41`), but the SPA submit-time redirect makes a first-time `/applications` visitor (no receipt yet) effectively unable to drive the anonymous endpoint through the SPA — they will be redirected to Authentik before the POST. The API endpoint contract remains literally stable, and any direct API consumer or e2e contract test still works, but SPA-driven anonymous submit is gated. This is consistent with the scope item "redirect to Authentik at submit time if no valid receipt exists" (`proposals/08-applicant-discord-oauth.md:50`) and the proposal explicitly admits "the receipt is held by the SPA for BL-017; it is not sent to `POST /api/public/applications` in BL-016" (`proposals/08-applicant-discord-oauth.md:114`). It does not violate the literal anti-scope ("No INIT-120 public submit contract change") because that anti-scope is contract-scoped. Recommend the implementation surface this clearly in observability and the live e2e non-regression test design so future readers do not interpret "supported anonymous submit path stable" as "anonymous submit reachable through `/applications` after this slice ships."

## 2. Implementation choices inside scope

Each implementation decision in `proposals/08-applicant-discord-oauth.md:66-77` lives inside the declared scope:

- **Separate applicant OIDC client in Authentik** — within the "applicant OIDC Provider/Application" scope item; explicitly avoids overloading the existing `pomerium` provider, matching the RCA recommendation that Pomerium's `sub_mode='hashed_user_id'` and officer-claim shape should not be reused for applicant identity (`.tmp/rca/discord-oauth-linking-FINDINGS.md:130-138`, `research/13-applicant-discord-oauth-problem-map.md:222-227`).
- **Server-side OIDC exchange in the API process** — within the "callback handler in the existing API service" scope item; matches the problem map's note that the web pod is static nginx with only `/api/` proxy and SPA fallback while the API has FastAPI routing/settings (`research/13-applicant-discord-oauth-problem-map.md:94-104`, `services/api/app/api/v1/router.py:1-56`, `services/api/app/core/settings.py:13-35`).
- **Discord scope `identify` only** — anti-scope literal match.
- **Blueprint-managed Authentik objects** — within the "extend the Authentik blueprint ConfigMap" scope item; consistent with the existing INIT-114 sample-user pattern (`gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:1-37`) and explicitly avoids duplicating the work into `bring-up-local-channel.sh` Authentik API reconciliation (`proposals/08-applicant-discord-oauth.md:181`).
- **Claim contract is only `discord_user_id`** — supports the receipt anti-scope ("No `email`, `guilds`, …").
- **Callback verifies only, no member creation** — matches the "No member creation" / "No synthetic-to-real conversion" / "No application re-pointing" anti-scope items and explicitly defers to BL-017 (`proposals/08-applicant-discord-oauth.md:73`).
- **No public-submit API change** — matches the literal anti-scope.
- **Submit-time redirect, not load-time** — within the SPA scope item, and avoids landing a load-time-redirect that would have to be undone by BL-017.
- **Per-developer Discord application** — within the local-developer onboarding scope item; bounded by the supported-surface track's local-first cohort (`proposals/08-applicant-discord-oauth.md:176`).

No decision asserts behavior outside the declared scope.

## 3. Out-of-scope discipline

| Forbidden surface | Verdict | Evidence |
|---|---|---|
| Member creation | Held | Callback flow stops at "Sign an applicant identity receipt and return it to the SPA" (`proposals/08-applicant-discord-oauth.md:124-131`); receipt format does not persist to DB; "BL-016 stores no receipt-derived database state" (`proposals/08-applicant-discord-oauth.md:172`). |
| Application re-pointing | Held | Receipt is not sent to `POST /api/public/applications`; "the receipt is held by the SPA for BL-017; it is not sent to `POST /api/public/applications` in BL-016" (`proposals/08-applicant-discord-oauth.md:114`). |
| INIT-120 contract change | Held | `services/api/app/api/v1/endpoints/applications/public.py:18-38` retains existing `PublicApplicationSubmission` request body, `authorize_public_intake` dependency, and `submit_public_application` call. No request/response schema delta in scope. |
| Officer OIDC unaffected | Held | Proposal commits to leaving the existing Pomerium `pomerium` Provider/Application, redirect URI `https://authenticate.local.humility.local/oauth2/callback`, and `openid email profile` scope unchanged (`proposals/08-applicant-discord-oauth.md:178-182`); the existing `pomerium-config` `idp_scopes` and `idp_provider_url` in `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:32-46` are not on the touched-surface list. |
| Cedar applicant principal | Held | "No new Cedar applicant principal or public-submit authorization change" anti-scope; consistent with the problem map's recommendation to keep claim verification at the API edge until forced-auth redirect ships (`research/13-applicant-discord-oauth-problem-map.md:140-147`, `research/13-applicant-discord-oauth-problem-map.md:274-277`). |
| Discord-visible side effects | Held | `identify`-only scope; no Discord API calls beyond the OAuth flow; no guilds/roles claim. |
| Remote-channel Discord rollout | Held | Migration step 1 explicitly limits to "local developer documentation and `.env.example` keys" (`proposals/08-applicant-discord-oauth.md:216`). |

**Soft-edge to watch in implementation, not a blocker:** the bootstrap script `infra/scripts/bootstrap-infisical-auth.sh` currently mirrors Pomerium OIDC client id/secret into the Authentik path. The proposal explicitly says the new applicant OIDC values must **not** mirror into existing Pomerium keys (`proposals/08-applicant-discord-oauth.md:143`). Implementation must preserve that boundary; otherwise the "officer OIDC unaffected" anti-scope is at risk through a non-obvious shared script.

## 4. Convention compliance (no backwards-compat shim, no deferred stubs)

- **No backwards-compat shim:** the proposal does not add an "old vs new" toggle on the public-submit endpoint, does not introduce a `discord_user_id` shim claim alongside an "anonymous submit even though we have a receipt" branch, and does not register a fallback Pomerium catch-all that would survive after the new specific route is removed. The blueprint extension is additive YAML with no compatibility branching.
- **ConfigMap naming nuance (not a shim):** the proposal mentions optionally renaming `authentik-init-114-blueprint` to a neutral name while preserving the Helm `blueprints.configMaps` mount (`gitops/channels/local/auth/authentik/render-values.yaml:13-15`). This is a rename, not a compat shim; either keep the existing name (acceptable; INIT-127 entries simply share the INIT-114-named ConfigMap) or rename atomically with the matching `render-values.yaml` update. Implementation must not leave both names live as a "transitional" setup, since that would be a BC shim.
- **No deferred stubs:** the callback handler delivers the full intended capability — code exchange, JWKS validation of issuer/audience/expiration, claim extraction, receipt signing — within BL-016. There is no "TODO: validate JWKS later" or "stub receipt without signing" branch declared in scope. The receipt format is final-shape; BL-017 will consume it without renegotiation. The SPA's "If a valid receipt exists, allow the current submit code path to continue unchanged for this slice" is a slice boundary, not a stub: BL-016 ends with the SPA holding a verified receipt. BL-017 is the conversion + re-pointing slice that consumes that receipt.
- **Test-intent residual policy:** the proposal references `plans/risk/init-127-test-residuals.md` as a Step-6b output if any named risk cannot be verified (`proposals/08-applicant-discord-oauth.md:208-210`); that is the convention-compliant residual artifact, not a stub.

No backwards-compat shim or deferred-stub violations identified.

## 5. Adjacent-path discipline

| Adjacent surface | Stated guard | Verdict |
|---|---|---|
| Pomerium officer routes (`/admin` on `web.local.humility.local`, `protected-api.local.humility.local`) | "Add only the specific `/auth/discord/` route; preserve `/admin`, public web catch-all, protected API, and public-intake rate-limit ingress behavior" | Held — the new route is specific (`prefix: /auth/discord/`), public-unauthenticated, and ordered before the existing host catch-all (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:47-57`). The proposal correctly identifies that Pomerium currently has `/admin` (protected) → host catch-all (public) on `web.local.humility.local`. |
| INIT-114 Pomerium OIDC scope set | "Leave the existing Pomerium Provider/Application and `openid email profile` scope set unchanged" | Held — the new applicant Provider is a separate Authentik object with property mappings limited to `openid` plus the custom `discord_user_id` mapping (`proposals/08-applicant-discord-oauth.md:88-89`). The Pomerium `idp_scopes` line (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:37`) is untouched. |
| Authentik blueprint loader | "Keep blueprint ConfigMap mounting through Helm and avoid extending `bring-up-local-channel.sh` Authentik API reconciliation for applicant objects" | Held — proposal explicitly leaves Authentik API reconciliation in `infra/scripts/bring-up-local-channel.sh:483-604` for the existing Pomerium provider only (`proposals/08-applicant-discord-oauth.md:181`). |
| Public-intake rate-limit ingresses (Pomerium subtree + server-manager subtree) | "The new callback route must not accidentally inherit public-intake rate limits, because that rate limit is scoped to application submit paths" | Held — proposal isolates `/auth/discord/*` from the public-intake rate-limit ingresses (`proposals/08-applicant-discord-oauth.md:182-183`); rate-limit configs (`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`, `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`) are not on the touched-surface list. |
| `/api/v1/me` officer header model | "Officers remain on existing Pomerium OIDC; `/admin` and `/api/v1/me` keep their Pomerium-header model" | Held — the new applicant identity surface lives at `/auth/discord/*` and never produces a `CurrentPrincipalRead(provider="pomerium")` payload. |
| `members.kind` discriminator (INIT-125A) | (not in scope) | Held — proposal does not write to `members`; INIT-125A's recently-added `kind` column is read-only territory for BL-016. |
| Web SPA storage (`humility.publicApplication.clientApplicationId`) | (not anti-scoped, but adjacent) | Held — the proposed `humility.applicantIdentityReceipt` storage key is parallel to the existing `clientApplicationId` storage key (`services/web/src/main.tsx:120-127`), not a replacement. Implementation must keep both keys distinct so a receipt cannot be confused with a client-application identifier. |

No adjacent surface is silently mutated by the proposal.

## Decomposition assessment

The RCA suggested splitting the larger linking fix into INIT-125A (kind), INIT-125B (Discord OAuth/Authentik plumbing), INIT-125C (conversion + re-pointing), and INIT-125D (cleanup). The backlog mapped that into BL-016 (OAuth plumbing), BL-017 (conversion/re-pointing), and BL-018 (cleanup). BL-016 corresponds to INIT-125B plus the minimum SPA wiring required to actually drive the OAuth flow. The proposal stays within those slice borders: no `member_links` table, no `application.applicant_repointed` event, no historical cleanup job. Decomposition is appropriate; no scope-creep into BL-017 or BL-018 territory was found.

## Watch signals (non-blocking, propagate to Phase 6/7)

1. **SPA "anonymous submit path stable" phrasing.** The net-value statement reads "while keeping INIT-120's supported anonymous submit path stable" but the SPA submit-time redirect changes the *effective* path for first-time `/applications` users. Recommend either tightening the net-value language to "API endpoint contract for `POST /api/v1/public/applications` stable" or making the SPA-gating explicit in the supported-surface track. This is a clarity issue, not a scope violation.
2. **ConfigMap rename.** If the Authentik blueprint ConfigMap is renamed away from `authentik-init-114-blueprint`, `gitops/channels/local/auth/authentik/render-values.yaml:13-15` must be updated atomically. A staged rename would create a BC shim window — disallowed by convention.
3. **Bootstrap-script secret separation.** Implementation must not extend the existing Pomerium-OIDC mirror in `infra/scripts/bootstrap-infisical-auth.sh:480-494` to applicant client material. Proposal commits to this separation explicitly; Phase 6 should treat any cross-mirror as a regression of the "officer OIDC unaffected" anti-scope.
4. **Receipt vs raw-token storage in the SPA.** The proposal's preferred transport is HTTP-only short-lived cookie; the alternate transfer-token path is acceptable but must avoid placing the receipt in the URL. Implementation should not regress to URL-fragment receipts as a "simpler" path because that re-introduces a browser-storage attack surface that the proposal explicitly avoided.

## Verdict

**LOW.** Scope and anti-scope are coherent, every implementation decision lives inside scope, the four out-of-scope guards (no member creation, no application re-pointing, no INIT-120 contract change, officer OIDC unaffected) are held, no backwards-compat shim or deferred stub is introduced, and adjacent paths (Pomerium officer routes, INIT-114 Pomerium OIDC, Authentik blueprint loader, public-intake rate limits, `/api/v1/me`, INIT-125A `members.kind`) are preserved. Watch signals above are clarity/implementation hygiene items for Phase 6, not Phase 4 blockers.
