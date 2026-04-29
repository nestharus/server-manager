# Proposal 13 - INIT-133B-i / BL-019D-beta slice 1: officer queue

## 1. Goal

INIT-133B-i ships the first BL-019D-beta officer review surface: a TanStack Solid Router-backed `/applications/queue/` page where an authenticated officer can see submitted/queued applications, page through the queue, and claim one application. This consumes the INIT-133A `ApplicationListRead` / `ApplicationRead` contracts and the existing application transition service; detail, transcript, messaging, and non-claim decisions remain in INIT-133B-ii / INIT-133B-iii.

The critical correction after the audit gate is identity binding: officer actor identity comes only from a Pomerium-asserted `discord_user_id` claim emitted by Authentik after Discord OAuth. The `applicant_receipt` cookie remains load-bearing for the public applicant route, but officer routes do not read it, trust it, or use it as an actor source.

## 2. Locked Decisions Q1..Q8

### Q1. SPA architecture: B, wire TanStack Solid Router as the real entry

Choose B: replace the live vanilla `main.tsx` bootstrap with `AppProviders + router`, migrate the current `/`, `/applications`, and `/admin/chapters` behavior into Solid routes, and add `/applications/queue/` as a first-class route. `index.html` loads only `/src/main.tsx` today, while the live runtime is a pathname switch in `main.tsx`. The router/provider scaffold already exists but is not mounted, so mounting the router beside the vanilla app would preserve the dual-system state the project rules reject. This choice is justified by removing the parallel runtime before 133B-ii and 133B-iii build on top of it, not by diff size.

### Q2. Officer identity surface: Pomerium officer session carries Discord identity

Call `/api/v1/me` once on route mount for the Pomerium principal, but do not call the core `/api/v1/applications` endpoint directly from the browser. The browser cannot supply trusted `X-Actor-*` headers, and application list/claim still require `ActorIdentity(actor_kind="user", actor_id=<member uuid>)`.

This slice uses the M1 binding from `research/20-init-133B-officer-identity-binding.md`: officer login goes through Pomerium -> Authentik -> Discord OAuth. Authentik stores the Discord snowflake from the Discord `identify` response, emits it as a `discord_user_id` claim in the `pomerium` OAuth2 application tokens, and Pomerium forwards it as `x-pomerium-claim-discord-user-id`. The web-officer bridge validates that Pomerium-forwarded snowflake, calls `resolve_or_create_real_discord_member`, and constructs `ActorIdentity(actor_kind="user", actor_id=<member uuid>)` from the resolved member UUID.

Officer endpoints must NOT depend on `app.core.dependencies.get_current_actor`, `app.core.context.get_current_actor`, or any dependency that reads `CURRENT_ACTOR.get()`. The bridge constructs `ActorIdentity` locally from the resolved member UUID as specified in §6 step 7. Officer endpoints ignore any `X-Actor-Kind` / `X-Actor-Id` request headers - those headers are honored only by the actor middleware for explicit `_requires_actor` paths, which the new `/api/v1/web/officer/...` paths are NOT.

The web-officer bridge must not consult `applicant_receipt`. An unrelated applicant receipt cookie can be present in the browser and must have no effect on list, claim, ownership, or audit actor identity. This keeps the core API unchanged, avoids browser-supplied actor headers, and binds review/audit writes to the authenticated officer's Discord identity.

### Q3. Route path: `/applications/queue/`

Use `/applications/queue/` for the queue page and reserve `/applications/{id}` for INIT-133B-ii. `/applications` remains the applicant form. Pomerium protection must use exact `path: /applications/queue` for the bare page plus `prefix: /applications/queue/` for nested queue-owned routes, because a bare `prefix: /applications/queue` would also protect `/applications/queue-foo`. The implementation must add those Pomerium entries because the current local Pomerium config protects only `/admin` on the web host and leaves the catch-all route public.

### Q4. Filter UX: state toggles only

Ship a compact state toggle row with default states `submitted,queued`. Submitted rows are visible in the queue but have no claim button - they must first be `route`d to `queued` by another surface (133B-iii) or by an external mechanism. This slice does not include the route action. The backend list endpoint accepts `state`, `scope_kind`, `scope_id`, `owner_id`, `limit`, and `after_id`, and the state enum is locked in the application contract. Scope selector and owner filter are not in this slice because 133B-i is proving the queue and claim workflow; API-side authority remains authoritative through the existing list service.

### Q5. Pagination UX: explicit Load More

Use a "Load more" button when `next_after_id` is present. `ApplicationListRead` returns `items` plus `next_after_id`, and the repository already owns ordering/paging. No infinite scroll, prefetch, counts, or total pages are included.

### Q6. Claim button semantics: real transition with browser `If-Match`

Render a claim button only for rows in `queued`. The bridge claim endpoint is `POST /api/web/officer/applications/{id}/claim`, but the browser sends no `expected_version` body. Instead, the browser sends `If-Match: "<version>"`, derived from the `ApplicationRead.version` it just fetched. The bridge validates the Pomerium principal, officer group, Discord claim, and resolved member before calling `parse_if_match_strong(request)` directly (importing the helper from `services/api/app/api/v1/endpoints/applications/etag.py`). The 428/412 status codes are emitted by reusing this helper - the bridge does not re-encode them. After validation, the bridge calls the synchronous `transition_application(..., request_surface=f"api:/api/v1/web/officer/applications/{application_id}/claim")` directly as a Python service function - NOT an HTTP self-call.

The bridge must never silently fall through to "use current server version." On success, update the row from the returned `ApplicationRead` and refetch the queue once. On `409` or `412`, show a conflict message and refetch. On `428`, show a precondition-required message and refetch. On `403`, show forbidden state and disable claim controls.

### Q7. Test surface: new officer spec plus test 19 augmentation

Add `services/web/tests/officer-queue.spec.ts` rather than making `compat.spec.ts` carry both applicant compatibility and officer workflow coverage. Keep the shared contract fixture, Playwright route mocking, and risk-annotation pattern already used by `compat.spec.ts`. Extend `infra/tests/e2e/tests/19-web-ui.sh` instead of adding a new e2e number because test 19 already validates the web image, Pomerium/admin route, applicant receipt submit, and persistence.

The test surface gains Authentik/Pomerium static tests for the officer Discord claim chain, API tests for Pomerium `discord_user_id` claim handling, and a `/api/v1/me` exact-shape update for the two new fields.

### Q8. Anti-scope: queue and claim only

Out of scope: application detail page and transcript view (133B-ii), message thread and non-claim decision actions (133B-iii), applicant DM materialization (BL-020), Discord-visible channel/DM side effects (BL-009), bulk actions, search, sorting beyond existing backend order, officer scope selector, owner/mine filter, export, Storybook, mobile polish beyond responsive non-overlap, `member_links`, new schema, new permissions, new actor kinds, and any reuse of `applicant_receipt` for officer actor identity.

## 3. Scope

### New files

- `services/web/src/features/public/ApplicationFormRoute.tsx` - Solid route that mirrors the current receipt-gated applicant form behavior from `main.tsx`.
- `services/web/src/features/officer/ApplicationQueueRoute.tsx` - officer queue route with state toggles, table/list rows, load-more, claim action, and status messages.
- `services/web/src/features/officer/officer.module.css` - route-local queue layout and row styling.
- `services/web/tests/officer-queue.spec.ts` - Playwright component tests for officer queue auth, list, filters, pagination, and claim.
- `services/api/tests/test_web_officer_applications.py` - API tests for the Pomerium Discord-claim bridge, list, claim, failure cases, and the server-side guard that officer endpoints do not depend on applicant receipt verification.

### Modified files

- `services/web/src/main.tsx` - replace vanilla DOM routing with Solid `render(() => <AppProviders router={router} />, root)` while preserving the same mounted `#root`.
- `services/web/src/app/router.tsx` - add `/applications` and `/applications/queue/`; keep `/` and `/admin/chapters`; mount exactly `<Link to="/applications">Application form</Link>` in `RootShell` alongside Public and Admin, with no inner element that could alter the computed accessible name, so the existing role=link contract remains true (A9); add queue nav only when the route has officer state and have it navigate to `/applications/queue/`.
- `services/web/src/app/providers.tsx` - remove the `any` router prop type and keep query/router providers as the only runtime wrapper.
- `services/web/src/api/client.ts` - add officer-side and admin-side fetch helpers plus Zod schemas for `ApplicationScope`, `ApplicationRead`, `ApplicationListRead`, transition request/response, `CurrentPrincipal.groups`, and `CurrentPrincipal.discord_user_id`; keep only the applicant Discord identity probe helper for `/auth/discord/me`; switch browser-facing API URLs to `/api/...` so nginx maps them to API `/api/v1/...`. The current-principal helper must call `/api/me` with no trailing slash, matching FastAPI's registered `/api/v1/me` route and avoiding the default trailing-slash 307 redirect. Pomerium collision protection comes from an exact `path: /api/me` route, not from a slash-terminated prefix. The applicant submit POST stays inline in `ApplicationFormRoute.tsx` because it has no shared Zod schemas with officer code and ties to the receipt-state signal local to that route.
- `services/web/src/features/public/HomeRoute.tsx` - replace demo preview behavior with a Solid mirror of the current public home route and link to `/applications`.
- `services/web/src/features/admin/AdminChaptersRoute.tsx` - preserve the current chapter table behavior while using the corrected browser-facing `/api/web/admin/chapters` client path.
- `services/api/app/contracts/web.py` - add `groups: list[str] = []` and `discord_user_id: str | None = None` to `CurrentPrincipalRead`; add web-officer response/error helper types only if needed by endpoint tests.
- `services/api/app/api/v1/endpoints/me.py` - parse `x-pomerium-claim-groups` into `CurrentPrincipalRead.groups` with a version-tolerant parser: if the value starts with `[`, use `json.loads` and require a JSON array of strings; otherwise split on `,`; trim each part, drop empty parts, and reject membership only on exact, post-trim match. Treat an absent header as `[]`. Parse `x-pomerium-claim-discord-user-id` into nullable `CurrentPrincipalRead.discord_user_id` (A6).
- `services/api/app/api/v1/endpoints/web.py` - add `/officer/applications` list and `/officer/applications/{application_id}/claim` endpoints using Pomerium groups plus Pomerium-asserted `discord_user_id`; both endpoints are `async def` because `resolve_or_create_real_discord_member` is `async`, and each endpoint awaits only the resolver before calling the synchronous `list_applications(...)` / `transition_application(...)` service functions. The claim endpoint signature must include the live FastAPI `response: Response` parameter so `set_etag(response, result.etag)` can write the header, matching the direct lifecycle endpoint shape. Officer endpoints must not call `verify_applicant_receipt`, read the `applicant_receipt` cookie, depend on `app.core.dependencies.get_current_actor`, depend on `app.core.context.get_current_actor`, or depend on any callable that reads `CURRENT_ACTOR.get()`. Officer endpoints ignore any browser-supplied `X-Actor-Kind` / `X-Actor-Id` request headers and construct `ActorIdentity` locally from the Pomerium-resolved member UUID only. The claim path must validate Pomerium identity, officer group, Discord claim, and member resolution before calling `parse_if_match_strong(request)`, so missing identity plus missing `If-Match` returns `401`, not `428`. The bridge must wrap every call to `list_applications(...)` and `transition_application(...)` in `try/except` and forward known service exceptions to `raise_known_application_error(...)` instead of re-encoding them locally. `ValueError` from `resolve_or_create_real_discord_member(...)` is handled in a separate resolver-only block and must not be caught by the transition mapper block. On successful claim, the bridge destructures `read, result = transition_application(...)`, calls `set_etag(response, result.etag)`, and returns `read`, so the response carries the same strong ETag header emitted by the direct application lifecycle endpoint.
- `services/api/app/api/v1/endpoints/applications/_shared.py` - today this file owns both `parse_if_match_strong` and `raise_known_application_error`, while the direct list endpoint maps `ApplicationListForbiddenError` beside the helper. Step 1 (must land first): add an `ApplicationListForbiddenError` -> `403 application_list_forbidden` branch to `raise_known_application_error` in `services/api/app/api/v1/endpoints/applications/_shared.py` (or the renamed `etag.py`/stable mapper module). Update the direct list endpoint at `services/api/app/api/v1/endpoints/applications/lifecycle.py:106-110` to delegate to the helper instead of mapping locally. Step 2: add a unit test that calls the helper directly with `ApplicationListForbiddenError` and asserts the 403 mapping. Step 3: build the bridge on top. Rename the ETag/import helper surface to `services/api/app/api/v1/endpoints/applications/etag.py` (or an equally stable public name) so cross-package imports from `web.py` use a non-private surface. Update all in-tree imports of `parse_if_match_strong` accordingly. If the rename moves `raise_known_application_error`, the bridge imports it from the renamed stable module; if the implementation splits only ETag parsing into `etag.py`, the bridge imports `parse_if_match_strong` from `etag.py` and keeps `raise_known_application_error` from `_shared.py`.
- `services/api/app/services/members.py` - parameterize `resolve_or_create_real_discord_member` with optional `originating_actor` and `request_surface` parameters. Defaults preserve the applicant path. The web-officer bridge passes `originating_actor=ActorIdentity(actor_kind="service", actor_id="web-officer-bridge")` and `request_surface="api:/api/v1/web/officer/applications"` so first-login member creation is attributed to the officer bridge, not the applicant receipt service (A5). The `originating_actor` / `request_surface` parameterization must thread through all three actor-literal embedding sites in `services/api/app/services/members.py:200-256`: the `_make_request(..., actor=..., request_surface=...)` call, the outer `action_payload` literals, and the `StateChangeDraft.payload_json` literals. Missing any of the three sites silently leaks the `applicant-receipt` actor into officer member-creation audit records.
- `services/api/tests/test_web_identity.py` - update exact `/api/v1/me` JSON expectations to include `groups: []` and `discord_user_id: None` by default.
- `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml` - add data entry `init-133B-pomerium-officer-discord.yaml` that defines the missing `pomerium` OAuth2 application and provider, a distinct Discord OAuth source such as `discord-pomerium`, a distinct source property mapping mirroring `discord-applicant-snowflake`, and a distinct scope mapping such as `server-manager-pomerium-discord_user_id` with `scope_name: discord_user_id`. The Discord source must use `scope: identify` only, matching the applicant blueprint. The new `discord-pomerium` Authentik OAuth source uses separate Discord developer application credentials from the existing `discord-applicant` source. The Infisical secret store gains `DISCORD_OFFICER_OAUTH_CLIENT_ID` and `DISCORD_OFFICER_OAUTH_CLIENT_SECRET` as the officer mirror of the existing `DISCORD_APPLICANT_OAUTH_*` pair, and the operator must register a second Discord developer application before the officer flow can authenticate. This separation is recommended for cleaner isolation and revocation independence: revoking one Discord app's credentials does not break the other flow. Also extend the existing `init-114-local-users.yaml` sample user so the e2e Authentik username/password login has the same officer Discord claim path Pomerium expects. The existing applicant e2e snowflake resolves to `123456789012345678` from `server-manager-e2e-fixtures` / `E2E_APPLICANT_DISCORD_USER_ID`, so use the distinct valid Discord snowflake `210987654321098765` for the officer fixture:

  ```yaml
  - model: authentik_core.group
    state: present
    identifiers:
      name: officers
    attrs:
      name: officers
      is_superuser: false
  - model: authentik_core.user
    state: present
    identifiers:
      username: sample
    attrs:
      username: sample
      name: Humility Sample User
      email: !Env [SAMPLE_USER_EMAIL, sample@local.humility.local]
      password: !Env [SAMPLE_USER_PASSWORD, ""]
      is_active: true
      groups:
        - !Find [authentik_core.group, [name, Humility Local Users]]
        - !Find [authentik_core.group, [name, officers]]
      attributes:
        discord_user_id: "210987654321098765"  # E2E_OFFICER_DISCORD_USER_ID - distinct from E2E_APPLICANT_DISCORD_USER_ID
  ```
- `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml` - extend `idp_scopes` from `openid email profile` to include `discord_user_id`; ensure `jwt_claims_headers` contains exactly one `x-pomerium-claim-groups: groups` entry and add `x-pomerium-claim-discord-user-id: discord_user_id`; protect exact `/api/me`, exact `/applications/queue`, nested `/applications/queue/`, `/api/web/admin/`, and `/api/web/officer/` with Pomerium identity headers before the public catch-all.
- `infra/tests/test_applicant_discord_blueprint.py` - or a new sibling static blueprint test - assert the Pomerium officer Authentik app/provider/source/scope mapping exists, uses a distinct `discord-pomerium` source, emits `discord_user_id`, and does not request `email`, `guilds`, or `guilds.members.read`; assert the Authentik scope mapping reads `request.user.attributes.get("discord_user_id")` so the pre-bound sample user's `attributes.discord_user_id` reaches the Pomerium token; assert the e2e principal's group membership includes both `Humility Local Users` and `officers`.
- `infra/tests/test_applicant_discord_pomerium.py` - assert the new protected officer routes precede the public catch-all, `/applications` resolves to the catch-all, `/applications/queue` resolves to the auth-gated exact-path entry, `/applications/queue/` resolves to the nested auth-gated prefix entry, `/api/me` resolves to the auth-gated exact-path entry, the `/api/web/officer/` route targets the web service, `idp_scopes` set-compares exactly to `{openid, email, profile, discord_user_id}`, and `jwt_claims_headers` has exactly `email`, `sub`, `x-pomerium-claim-groups`, `name`, and `x-pomerium-claim-discord-user-id` (A7, A8). Also assert `x-pomerium-claim-groups` appears exactly once in `jwt_claims_headers`, locking the in-tree config to the single-header semantics the parser assumes. If a future Pomerium upgrade or ingress rewrite breaks this, the static test fails before the parser silently mis-classifies an officer. Extend the static test with collision-class assertions: `/api/me-foo`, `/api/members/...`, and `/applications/queue-foo` must not match the auth-gated `/api/me` or `/applications/queue` exact-path entries; `/api/me` must be protected by `path: /api/me`, not `prefix: /api/me`.
- `infra/tests/validate_web_ui_local.sh` - extend static checks for the officer queue fixture/spec and keep the existing web build/runtime proof; add a negative grep across all source literals: `grep -rE "[\"']/api/v1/" services/web/src/` must return zero matches for any `/api/v1/...` literal in any source file under `services/web/src/`, not just direct `fetch()` call sites. Combined with positive allowlist assertions for `client.ts` calls to `/api/me`, `/api/web/admin/chapters`, `/api/web/officer/applications`, `/api/web/officer/applications/{id}/claim`, and `/auth/discord/me`, this guards against indirect `/api/v1/...` use anywhere in the SPA. The script also performs a live `curl -sk` against `https://web.local.humility.local/api/me` with simulated Pomerium identity headers and asserts a `CurrentPrincipalRead` JSON body with the expected `subject`, `groups`, and `discord_user_id`. The applicant submit POST to `/api/public/applications` is inline in `ApplicationFormRoute.tsx`, contains no `/v1/` literal, and is NOT in `client.ts`; the allowlist applies only to `client.ts` (A6, A7).
- `infra/tests/e2e/lib/seed-authority-grants.mjs` - add the e2e authority-grant seed helper because `infra/tests/e2e/lib/` has no existing authority-grants seed path. The helper is a small kubectl/psql wrapper used only by test 19 to issue exactly `application.review` and `application.claim` grants for a resolved member UUID (A7).
- `infra/tests/e2e/lib/playwright/browser-flow.mjs` - after existing applicant submit, navigate to `/applications/queue/`, wait for the queue, and record a claimed application id.
- `infra/tests/e2e/tests/19-web-ui.sh` - seed/read the officer queue assertion, call `infra/tests/e2e/lib/seed-authority-grants.mjs` for the resolved member UUID before navigating to `/applications/queue/`, and verify the claimed application owner/state in Postgres (A7). After the queue/claim step, query the primary application pod with psql and assert `applications.owner_id != applications.applicant_id`, the owner's `members.discord_user_id` equals `E2E_OFFICER_DISCORD_USER_ID` from the bootstrap fixture user's `attributes.discord_user_id`, and the owner row has `members.kind = 'discord'`.
- `infra/tests/fixtures/web-ui/contract.json` - keep `auth.probe_endpoint` aligned with the live SPA principal probe at `/api/me`; add `routes.officer_queue`, `auth.officer`, `auth.headers.x-pomerium-claim-discord-user-id`, `applications.queue`, and `applications.claim` fixture data while preserving the existing applicant form fixture consumed by `compat.spec.ts` and test 19.

### Pomerium route shape

Lock the web-host route ordering with these explicit additions before the public catch-all:

```yaml
- from: https://web.local.humility.local
  path: /applications/queue
  to: http://server-manager-web.web.svc.cluster.local:8080
  preserve_host_header: true
  pass_identity_headers: true
  allow_any_authenticated_user: true
- from: https://web.local.humility.local
  prefix: /applications/queue/
  to: http://server-manager-web.web.svc.cluster.local:8080
  preserve_host_header: true
  pass_identity_headers: true
  allow_any_authenticated_user: true
- from: https://web.local.humility.local
  path: /api/me
  to: http://server-manager-web.web.svc.cluster.local:8080
  preserve_host_header: true
  pass_identity_headers: true
  allow_any_authenticated_user: true
- from: https://web.local.humility.local
  prefix: /api/web/admin/
  to: http://server-manager-web.web.svc.cluster.local:8080
  preserve_host_header: true
  pass_identity_headers: true
  allow_any_authenticated_user: true
- from: https://web.local.humility.local
  prefix: /api/web/officer/
  to: http://server-manager-web.web.svc.cluster.local:8080
  preserve_host_header: true
  pass_identity_headers: true
  allow_any_authenticated_user: true
```

In the full Pomerium route list, the exact `/api/me` and `/api/web/admin/` entries are inserted before the existing `/admin` prefix entry; the existing `/admin` route remains unchanged after them. The `/api/me`, `/api/web/admin/`, and `/api/web/officer/` targets are the web service, not the API service, because only the web nginx applies the `/api/` -> `/api/v1/` rewrite. Static tests must assert this. The exact `path: /api/me` route prevents `/api/me-foo` and `/api/members/...` collisions without forcing the browser onto `/api/me/`, which FastAPI would redirect to `/api/v1/me` before Pomerium re-evaluation. The queue route gets both `path: /applications/queue` and `prefix: /applications/queue/`: the exact path protects the current page, and the prefix reserves nested queue-owned routes without shadowing `/applications/queue-foo`. Tests must assert `/applications` resolves to the public catch-all, `/applications/queue` resolves to the exact auth-gated entry, `/applications/queue/` resolves to the nested auth-gated prefix entry, `/api/me` resolves to the exact auth-gated entry, and all identity-bearing web-host routes precede the public catch-all.

### Applicant form DOM contract

The migrated `ApplicationFormRoute.tsx` must preserve the load-bearing DOM contract from the live applicant route because `compat.spec.ts` and e2e test 19 bind to these selectors:

- Element ids: `application-form`, `submit-status`, `discord-login`, `discord-login-state`, `tab-overview`, `tab-details`, `open-details`, `details-panel`.
- Data-testids: `application-submit-icon`, `application-status-icon`.
- Accessible names: `role="form"` named "Application form"; `role="tab"` named "Overview" and "Details"; `role="button"` named "Login with Discord", "Submit application", and "Open details"; `role="dialog"` containing the literal text "Application details".
- `discord-login-state` exact text strings: `checking` -> "Checking Discord login..."; `anonymous` -> "Not logged in with Discord."; `verified` -> "Logged in as Discord <discord_user_id>". The verified string matches `auth.applicant.identity_indicator_prefix` in `infra/tests/fixtures/web-ui/contract.json`.
- **Auth-state-conditional rendering**. **Intentional contract tightening** (NOT pure preservation): the live `services/web/src/main.tsx:109-130` template renders `#tab-overview` / `#tab-details` / `#details-panel` regardless of auth state, while form/submit are auth-state-conditional. Migrating to a single auth-state-conditional render block (only `#discord-login` + `#discord-login-state` in checking/anonymous) is a defensible tightening: no existing `compat.spec.ts` test or downstream consumer depends on the tabs/details-panel being present pre-verification. This tightening becomes the new compatibility surface 133B-ii can rely on.
  - `checking` / `anonymous`: render only `#discord-login` and `#discord-login-state`. Do NOT render `#application-form`, the submit button, `#tab-overview`, `#tab-details`, or `#details-panel`.
  - `verified`: render all listed selectors. The tabs are decorative rule applies only inside `verified` - `#application-form` and `#details-panel` remain rendered regardless of which tab is active.
- Tab semantics: tabs are decorative inside the `verified` auth state. The form, submit button, and `#details-panel` must all remain rendered on the route regardless of the selected tab. Only the `aria-selected` attribute on the tab buttons and the `[hidden]` attribute on `#details-panel` change on tab click. Do not unmount the form when the user activates the Details tab; the `application-submit-icon` and `application-status-icon` must both remain visible after a Details click, which is what `services/web/tests/compat.spec.ts:228-246` asserts.

These are emitted as plain DOM attributes and text, not Ark-UI `<Tabs>` / `<Dialog>` framework-managed ids or generated identifiers. The route may reuse styling primitives, but the selectors above are compatibility contract, not implementation detail.

### HomeRoute (public route) DOM contract

`services/web/src/main.tsx:58-77` renders the public route's start button outside the applicant form. `HomeRoute.tsx` must preserve that surface:

- Element id: `start-application`.
- Click handler: `window.location.assign("/applications")`.
- Element type: `<button id="start-application">...Start application...</button>`.

### Deleted files

- `services/web/src/RuntimeApp.tsx` - delete the unmounted parallel runtime.
- `services/web/src/features/forms/DarkNemesisForm.tsx` - delete or replace with the real `ApplicationFormRoute`; do not keep a demo form parallel to the supported applicant form.
- `services/web/src/features/forms/schema.ts` - delete if no longer imported by the real applicant route.
- `services/web/src/features/forms/form.module.css` - delete if no longer imported.

### Tests

- `services/web/tests/compat.spec.ts` - update only as needed to keep the applicant route, receipt gating, UI-library smoke, "Application form" link, and contract fixture behavior passing under TanStack Solid Router.
- `services/web/tests/officer-queue.spec.ts` - new officer route test file described below.
- `services/api/tests/test_web_identity.py` - update `/api/v1/me` exact equality for `groups` and `discord_user_id`.
- `services/api/tests/test_web_officer_applications.py` - new API bridge tests.
- `services/api/tests/test_web_officer_applications.py::test_officer_endpoints_have_locked_actor_construction` - server-side FastAPI dependency-tree check for officer endpoints, asserting no `app.core.dependencies.get_current_actor`, no `app.core.context.get_current_actor`, no `verify_applicant_receipt`, no callable that reads `CURRENT_ACTOR.get()`, and no callable that reads `applicant_receipt` from request cookies.
- `infra/tests/test_applicant_discord_blueprint.py` or sibling - Authentik officer Pomerium blueprint tests.
- `infra/tests/test_applicant_discord_pomerium.py` - route-order, target-service, and claim-forwarding static Pomerium tests.
- `infra/tests/validate_web_ui_local.sh` - static coverage assertions.
- `infra/tests/e2e/tests/19-web-ui.sh` and `infra/tests/e2e/lib/playwright/browser-flow.mjs` - live local e2e queue proof.

### Fixtures

- `infra/tests/fixtures/web-ui/contract.json` - set `auth.probe_endpoint` to `/api/me`; add `routes.officer_queue`, `auth.officer`, `auth.headers.x-pomerium-claim-discord-user-id`, `applications.queue`, and `applications.claim` fixture data while preserving the existing applicant form fixture consumed by `compat.spec.ts` and test 19.

This remains within the prior LOW scope decision. The Authentik blueprint adds a small GitOps declaration for a Pomerium app already referenced by Pomerium config but missing from the tree; without it, M1 would not be reproducible. This does not introduce a new identity subsystem, schema, permission namespace, or actor kind.

## 4. API Surface Consumed

### GET `/api/v1/me`

Browser path: `/api/me` through the web nginx proxy. Request shape: no body; Pomerium supplies claim headers. Response shape: `{ subject: string, email: string | null, display_name: string | null, provider: "pomerium", groups: string[], discord_user_id: string | null }`. The two additive fields on `CurrentPrincipalRead` are `groups` and `discord_user_id`.

Auth: Pomerium identity required; the existing dependency returns `401 identity_missing` when identity headers are absent. UI handling: anonymous users should be redirected by Pomerium before the route renders; if the SPA receives any non-2xx response, redirect (302/303), opaque response, or fetch failure from `/api/me`, show an auth-required panel and no queue controls. If groups do not include `officers`, show forbidden/non-officer state. If the officer route sees `groups` include `officers` but `discord_user_id` is null, show an identity-incomplete panel and a hard Pomerium sign-in action; the server still rejects list/claim with `401 officer_discord_identity_missing`. Per A6, the `x-pomerium-claim-groups` wire format is version-tolerant: if the header value starts with `[`, parse it with `json.loads` as a JSON array of strings; otherwise split the single header value on `,`. Trim each part, drop empties, treat an absent header as `[]`, and use exact post-trim equality only for group membership.

### GET `/auth/discord/me`

Applicant route only. Request shape: no body; `applicant_receipt` cookie. Response shape: `{ discord_user_id: string }`. Auth: applicant Discord receipt cookie required. UI handling: `/applications` probes this endpoint, shows "Login with Discord" when missing/expired, and rechecks before submit. Officer queue routes do not call this endpoint and do not use this cookie for actor identity.

### GET `/api/v1/web/officer/applications`

Browser path: `/api/web/officer/applications`. Query: `state?: string` comma list, `limit?: number`, `after_id?: uuid`; no `scope_kind`, `scope_id`, or `owner_id` UI in this slice. Response shape: exactly `ApplicationListRead`.

Auth: Pomerium principal must include officer group; Pomerium must forward a valid Discord snowflake claim; the bridge resolves that claim to a real Discord member UUID and calls the existing application list service. The endpoint is `async def` because `resolve_or_create_real_discord_member` is `async`, and the bridge awaits the resolver before calling the synchronous `list_applications(...)` service. The endpoint does not depend on `get_current_actor` or `CURRENT_ACTOR.get()` and ignores any `X-Actor-Kind` / `X-Actor-Id` request headers. Existing application authority must allow list. The bridge wraps `list_applications(...)` in `try/except` and forwards typed core exceptions to `raise_known_application_error(...)` from `services/api/app/api/v1/endpoints/applications/_shared.py` or the stable renamed module, so list errors preserve the same status+code wire format as the direct `/api/v1/applications/*` endpoints. Because `ApplicationListForbiddenError` is currently mapped in the direct lifecycle endpoint rather than inside the helper, this slice must first fold that mapping into the shared known-error mapper surface and update the direct endpoint to use it. Failure modes handled: `401 identity_missing` shows auth-required; `401 officer_discord_identity_missing` shows identity-incomplete and no data; `401 officer_discord_identity_invalid` shows the same identity-incomplete UX while distinguishing claim-format drift in logs/tests; `403 officer_required` shows non-officer; `403 application_list_forbidden` shows list-forbidden state; `403 authority_decision_denied` shows transition-forbidden state if encountered after a claim attempt; `422 officer_discord_member_invalid` shows identity invalid; `422 validation_error` shows filter error and resets to default states; network/5xx shows retry panel.

### POST `/api/v1/web/officer/applications/{application_id}/claim`

Browser path: `/api/web/officer/applications/{id}/claim`. Request shape: `If-Match: "<version>"`; no `expected_version` JSON body. The endpoint is `async def` because `resolve_or_create_real_discord_member` is `async`, and the bridge awaits only the resolver before calling the synchronous `transition_application(...)` service. The endpoint signature includes `response: Response` so the success path can call `set_etag(response, result.etag)`. The endpoint does not depend on `get_current_actor` or `CURRENT_ACTOR.get()` and ignores any `X-Actor-Kind` / `X-Actor-Id` request headers. The bridge validates Pomerium identity, officer group, Discord claim, and member resolution before it calls `parse_if_match_strong(request)` directly (importing the helper from `services/api/app/api/v1/endpoints/applications/etag.py`) to validate the browser-supplied header. The 428/412 status codes are emitted by reusing this helper - the bridge does not re-encode them. After validation, the bridge calls `transition_application(..., request_surface=f"api:/api/v1/web/officer/applications/{application_id}/claim")` directly as a Python service function - NOT an HTTP self-call. The custom `request_surface` ensures `application_reviews` and `activity_actions` audit rows distinguish officer-bridge claims from direct-API claims. Response shape: `ApplicationRead`; on successful claim, the bridge destructures `read, result = transition_application(...)`, calls `set_etag(response, result.etag)`, and returns `read`, so the response carries the same `etag: "<version>"` strong ETag header the direct `/api/v1/applications/*` endpoints emit. This preserves the `If-Match` symmetry across both bridge and direct API.

Concrete claim wiring is illustrative: Phase 6c may refine naming, error-handling style, and parameter ordering as long as identity validation runs before optimistic-locking helpers, service calls stay synchronous, tuple returns are destructured, and the success path calls `set_etag(response, result.etag)` before returning `read`.

```python
async def claim_application(
    application_id: UUID,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(_db),
) -> ApplicationRead:
    # 1. Pomerium principal (officer group)
    principal = get_pomerium_principal(request)
    if "officers" not in principal.groups:
        raise HTTPException(403, "officer_required")

    # 2. Pomerium Discord claim
    discord_user_id = principal.discord_user_id
    if not discord_user_id:
        raise HTTPException(401, "officer_discord_identity_missing")
    if not DISCORD_SNOWFLAKE_RE.match(discord_user_id):
        raise HTTPException(401, "officer_discord_identity_invalid")

    # 3. Member resolution
    try:
        member = await resolve_or_create_real_discord_member(
            db,
            discord_user_id=discord_user_id,
            originating_actor=ActorIdentity(
                actor_kind="service",
                actor_id="web-officer-bridge",
            ),
            request_surface="api:/api/v1/web/officer/applications",
        )
    except ValueError as exc:
        if "non-discord member row" in str(exc):
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "officer_discord_member_invalid",
                    "message": "Officer Discord identity is bound to a non-discord member.",
                },
            )
        raise

    # 4. Now parse If-Match (only if claim path)
    expected_version = parse_if_match_strong(request)

    # 5. Construct ActorIdentity from member UUID
    actor = ActorIdentity(actor_kind="user", actor_id=str(member.id))

    # 6. Call core service
    try:
        read, result = transition_application(
            db,
            actor=actor,
            application_id=application_id,
            expected_version=expected_version,
            request=ApplicationTransitionRequest(
                action=ApplicationTransitionAction.claim,
            ),
            request_surface=f"api:/api/v1/web/officer/applications/{application_id}/claim",
        )
    except (
        ApplicationNotFoundError,
        StaleMutationError,
        ApplicationAlreadyClaimedError,
        ApplicationNotOwnerError,
        InvalidApplicationTransitionError,
        MissingAggregateError,
        ApplicationListForbiddenError,
        DuplicateApplicationCreateError,
        PermissionError,
    ) as exc:
        raise_known_application_error(exc)

    # 7. Set ETag and return
    set_etag(response, result.etag)
    return read
```

Auth: same Pomerium officer + Pomerium Discord claim + existing `application.claim` authority. The bridge wraps `transition_application(...)` in `try/except` and forwards typed core exceptions to `raise_known_application_error(...)` from `services/api/app/api/v1/endpoints/applications/_shared.py` or the stable renamed module, so claim errors preserve the same status+code wire format as the direct `/api/v1/applications/*` endpoints. Failure modes handled: `401` shows auth/identity-incomplete state; `403 authority_decision_denied` disables claim; `404 application_not_found` removes/refetches row; `409 application_already_claimed`, `409 application_not_owner`, or `409 invalid_application_transition` shows conflict and refetches; `412 invalid_if_match` or `412 stale_application_version` shows conflict and refetches; `428 if_match_required` shows a precondition-required message and refetches; `422 officer_discord_member_invalid` shows identity invalid; `422 validation_error` shows validation error.

The web-officer bridge status-code map is:

| Failure | Status | Code |
|---|---:|---|
| Pomerium claim header absent | 401 | `officer_discord_identity_missing` |
| Pomerium claim header present but not snowflake-shaped | 401 | `officer_discord_identity_invalid` |
| Member resolution: invalid snowflake | 401 | `officer_discord_identity_invalid` |
| Member resolution: bound to non-discord row | 422 | `officer_discord_member_invalid` |
| Missing `If-Match` after identity succeeds | 428 | `if_match_required` |
| Malformed/weak `If-Match` after identity succeeds | 412 | `invalid_if_match` |
| Stale version | 412 | `stale_application_version` |
| Core list/transition exceptions | Emitted via `raise_known_application_error`, producing identical status mappings as the direct `/api/v1/applications/*` endpoints: `404`, `409` variants, `412`, `422`, `403`, etc. | Direct endpoint codes including `application_not_found`, `application_already_claimed`, `application_not_owner`, `invalid_application_transition`, `stale_application_version`, `validation_error`, `application_list_forbidden`, and `authority_decision_denied` |

The bridge passes the helper's HTTPException verbatim for `If-Match` parsing after identity succeeds; do not re-code `if_match_required` -> `precondition_required`, and do not re-code `invalid_if_match`.

For `officer_discord_identity_invalid`, the bridge imports `from app.services.applicant_discord_auth import DISCORD_SNOWFLAKE_RE` and uses it directly to validate the header. No bridge-local regex is defined.

## 5. Component Contract Preview

### Route components

```ts
export type ApplicationQueueRouteProps = {
  readonly initialStates?: readonly ApplicationState[];
};

export function ApplicationQueueRoute(props: ApplicationQueueRouteProps): JSX.Element;

export function ApplicationFormRoute(): JSX.Element;
export function HomeRoute(): JSX.Element;
export function AdminChaptersRoute(): JSX.Element;
```

Router-owned route components should fetch through client functions directly; tests may render through the full router and mock network routes. Per A9, the "Application form" top-nav entry uses exactly Solid `<Link to="/applications">Application form</Link>`, with no icon/span/inner element, so it remains a role=link with accessible name exactly "Application form" and resolves to `/applications`. Officer "Login required" / Pomerium-redirect actions use `window.location.assign("/.pomerium/sign_in")`. Applicant "Login with Discord" and stale-submit redirects use `window.location.assign("/auth/discord/start?return_to=/applications")`, not Solid `navigate()`, because `/auth/discord/*` is a different upstream that the SPA must not intercept.

### Applicant form route parity

`ApplicationFormRoute` must preserve the current live route behavior:

- Auth signal: `checking | anonymous | verified(discord_user_id, expires_at)`.
- 9-minute re-probe timer matching the current receipt expiry guard.
- Submit-time `/auth/discord/me` recheck; on `401`, preserve draft and redirect to `/auth/discord/start?return_to=/applications` without POSTing.
- Session storage keys: `humility.publicApplication.clientApplicationId` and `humility.publicApplication.draft`.
- Plain-DOM selector contract from §3 "Applicant form DOM contract".

All four `applicantDiscordTest` / `loggedInApplicantTest` / `staleApplicantReceiptTest` cases at `services/web/tests/compat.spec.ts:202-291` must continue to pass against the migrated route.

### Sub-components

```ts
export type QueueFilterBarProps = {
  readonly selectedStates: readonly ApplicationState[];
  readonly onChange: (states: readonly ApplicationState[]) => void;
  readonly disabled?: boolean;
};

export type ApplicationQueueListProps = {
  readonly applications: readonly ApplicationRead[];
  readonly currentOfficerMemberId?: string;
  readonly claimingId?: string;
  readonly onClaim: (application: ApplicationRead) => void;
};

export type ApplicationQueueRowProps = {
  readonly application: ApplicationRead;
  readonly canClaim: boolean;
  readonly isClaiming: boolean;
  readonly onClaim: () => void;
};
```

### API client functions

```ts
export const applicationStateSchema: z.ZodEnum<[...states]>;
export const applicationReadSchema: z.ZodType<ApplicationRead>;
export const applicationListReadSchema: z.ZodType<ApplicationListRead>;

export type CurrentPrincipal = z.infer<typeof principalSchema>;
export type ApplicantDiscordMe = z.infer<typeof applicantDiscordMeSchema>;
export type ApplicationRead = z.infer<typeof applicationReadSchema>;
export type ApplicationListRead = z.infer<typeof applicationListReadSchema>;

export function fetchCurrentPrincipal(): Promise<CurrentPrincipal>;
export function fetchApplicantDiscordIdentity(): Promise<ApplicantDiscordMe>;
export function fetchOfficerApplicationQueue(input: {
  readonly states: readonly ApplicationState[];
  readonly limit?: number;
  readonly afterId?: string;
}): Promise<ApplicationListRead>;
export function claimOfficerApplication(input: {
  readonly applicationId: string;
  readonly version: number;
}): Promise<ApplicationRead>;
```

`claimOfficerApplication` sends `If-Match: "\"${version}\""` and no `expected_version` body. All client functions validate with Zod; no `any`. The current `AppProviders` `router: any` must be replaced.

### Signals / stores

No global TanStack Store state is introduced. Route-local Solid signals:

- Officer auth state: `checking | anonymous | non_officer | officer_missing_discord_claim | officer_verified(discord_user_id)`.
- `selectedStates: Accessor<ApplicationState[]>`, default `["submitted", "queued"]`.
- `items: Accessor<ApplicationRead[]>`.
- `nextAfterId: Accessor<string | null>`.
- `claimingId: Accessor<string | null>`.
- `notice: Accessor<{ kind: "info" | "error" | "success"; message: string } | null>`.

TanStack Query may cache the principal and queue responses through `createQuery`; the durable UI store remains theme/navigation only.

## 6. Authorization Model

Trust chain:

1. Officer navigates to `/applications/queue/`.
2. Pomerium protects `/applications/queue/` and `/api/web/officer/`, requiring an authenticated session.
3. Authentik's `pomerium` OAuth2 application is GitOps-declared in `init-133B-pomerium-officer-discord.yaml`; it uses a distinct `discord-pomerium` Discord OAuth source with `scope: identify`, stores `info.get("id")` as `request.user.attributes["discord_user_id"]`, and exposes a `discord_user_id` scope mapping. The `discord-pomerium` source uses separate Discord developer application credentials from `discord-applicant`; Infisical supplies `DISCORD_OFFICER_OAUTH_CLIENT_ID` and `DISCORD_OFFICER_OAUTH_CLIENT_SECRET`, and an operator must register that second Discord developer application before officer login can authenticate. This keeps credential revocation independent across applicant and officer flows.
4. Pomerium requests `discord_user_id` in `idp_scopes` and forwards it as `x-pomerium-claim-discord-user-id` through `jwt_claims_headers`.
5. `/api/v1/me` exposes the forwarded claim as nullable `CurrentPrincipalRead.discord_user_id`. Per A6, it parses `x-pomerium-claim-groups` as either a JSON array when the header starts with `[` or a comma-delimited string otherwise; both shapes trim strings, drop empties, and treat an absent header as `[]`. `officers` membership is exact post-trim match, never substring match.
6. The web-officer bridge applies the same exact group parsing rule, requires the `officers` group and a present, valid Pomerium-asserted Discord snowflake. A missing claim returns `401 officer_discord_identity_missing`; a present but non-snowflake-shaped claim returns `401 officer_discord_identity_invalid`. Neither path returns `applicant_receipt_required`.
7. The bridge endpoints are `async def`. They await `resolve_or_create_real_discord_member(discord_user_id=..., originating_actor=ActorIdentity(actor_kind="service", actor_id="web-officer-bridge"), request_surface="api:/api/v1/web/officer/applications")` and construct `ActorIdentity(actor_kind="user", actor_id=<member uuid>)` locally from the resolved member UUID. They do not depend on `app.core.dependencies.get_current_actor`, `app.core.context.get_current_actor`, or any dependency that reads `CURRENT_ACTOR.get()`. They ignore `X-Actor-Kind` / `X-Actor-Id` request headers; those headers are honored only by the actor middleware for explicit `_requires_actor` paths, which the new `/api/v1/web/officer/...` paths are NOT. This parameterized path keeps first-login member creation audit trails under the officer bridge surface instead of `actor_id="applicant-receipt"` / `request_surface="api:/api/v1/public/applications"`. Member-resolution exceptions are mapped explicitly instead of leaking as implicit synthetic-member failures. The `originating_actor` / `request_surface` parameterization must thread through all three actor-literal embedding sites in `services/api/app/services/members.py:200-256`: the `_make_request(..., actor=..., request_surface=...)` call, the outer `action_payload` literals, and the `StateChangeDraft.payload_json` literals. Missing any of the three sites silently leaks the `applicant-receipt` actor into officer member-creation audit records. The existing `discord_user_id` field in the member-creation `action_payload` is the intentional forensic link from the audit row back to the Pomerium-asserted snowflake that triggered the lookup. The originating Pomerium subject is NOT separately recorded in this slice; cross-referencing Pomerium-subject <-> Discord-snowflake is deferred to operational dashboards (BL-020 or later).
8. Existing application list/transition services enforce `application.review` / `application.claim` authority for that member UUID and write existing audit/ownership records. The list endpoint calls the synchronous `list_applications(...)` directly as a Python service function after awaiting member resolution. The claim endpoint validates identity, officer group, Discord claim, and member resolution first, then captures `expected_version = parse_if_match_strong(request)`, constructs `ApplicationTransitionRequest(action=ApplicationTransitionAction.claim)` server-side from no caller body, and calls the synchronous `transition_application(..., expected_version=expected_version, request=transition_request, request_surface=f"api:/api/v1/web/officer/applications/{application_id}/claim")` directly as a Python service function - NOT an HTTP self-call. The claim endpoint signature includes `response: Response`, matching the direct lifecycle endpoint, because the success path destructures `read, result = transition_application(...)`, calls `set_etag(response, result.etag)`, and returns `read`. The bridge wraps calls to `list_applications(...)` and `transition_application(...)` in service-only `try/except` blocks that catch typed service exceptions including `ApplicationNotFoundError`, `StaleMutationError`, `ApplicationAlreadyClaimedError`, `ApplicationNotOwnerError`, `InvalidApplicationTransitionError`, `MissingAggregateError`, `ApplicationListForbiddenError`, `DuplicateApplicationCreateError`, and `PermissionError`, and forwards them to `raise_known_application_error(...)` from `services/api/app/api/v1/endpoints/applications/_shared.py` or wherever the rename lands. `ValueError` from `resolve_or_create_real_discord_member(...)` is handled in its own resolver block and maps the non-discord-member case to `422 officer_discord_member_invalid`; it stays out of the `transition_application(...)` mapper block. The `ApplicationListForbiddenError` mapper migration is a hard prerequisite: add the shared `403 application_list_forbidden` branch and direct-helper unit test before implementing the bridge. This guarantees the bridge emits the same HTTP status + error code wire format as the direct `/api/v1/applications/*` endpoints. The bridge must NOT re-encode service exceptions to custom codes. For claim requests, the 428/412 status codes are emitted by reusing `parse_if_match_strong(request)` after identity succeeds - the bridge does not re-encode them. On successful claim, `set_etag(response, result.etag)` preserves `If-Match` symmetry across both bridge and direct API. The custom `request_surface` ensures `application_reviews` and `activity_actions` audit rows distinguish officer-bridge claims from direct-API claims.

Bridge identity and authority failures map as follows:

| Source | Failure | Status | Code |
|---|---|---:|---|
| Pomerium claim header absent | - | 401 | `officer_discord_identity_missing` |
| Pomerium claim header present but not snowflake-shaped | - | 401 | `officer_discord_identity_invalid` |
| `resolve_or_create_real_discord_member` raises `ValueError("invalid Discord snowflake")` | - | 401 | `officer_discord_identity_invalid` |
| `resolve_or_create_real_discord_member` raises `ValueError("bound to a non-discord member row")` | - | 422 | `officer_discord_member_invalid` |
| Core list/transition exceptions | typed service errors | emitted via `raise_known_application_error`, producing identical status+code mappings as the direct `/api/v1/applications/*` endpoints | `404 application_not_found`, `409` variants, `412 stale_application_version`, `422 validation_error`, `403 application_list_forbidden`, `403 authority_decision_denied`, etc. |
| Any other unexpected exception | - | 500 | `internal_error` |

For `officer_discord_identity_invalid`, the bridge imports `from app.services.applicant_discord_auth import DISCORD_SNOWFLAKE_RE` and uses it directly to validate the header. No bridge-local regex is defined.

Anonymous: Pomerium intercepts unauthenticated browser navigation to `/applications/queue/` with a 302 to the sign-in page; the SPA never mounts the route. For mid-session AJAX calls (e.g., session expiry while the queue is open), Pomerium responds with a 302 to sign-in. The SPA treats any non-2xx response, redirect (302/303), opaque response, or fetch failure on `/api/me` or `/api/web/officer/applications` as auth-required: it shows the auth panel and stops fetching queue data. There is no assumption that a clean 401 is returned by Pomerium.

Non-officer: `/api/me` succeeds but `groups` lacks `officers`; the route shows a forbidden panel. The web-officer API repeats this check server-side before resolving the Discord member. The UI cannot unlock itself by changing local state.

Officer with missing Pomerium Discord claim: `/api/me` succeeds and groups include `officers`, but `discord_user_id` is null. The page shows an identity-incomplete panel and a hard sign-in action to `/.pomerium/sign_in`; server list/claim returns `401 officer_discord_identity_missing`.

Officer with Discord claim but no application grant: the bridge resolves the member UUID, then existing application services deny list/claim. The API maps core list `ApplicationListForbiddenError` to `403 application_list_forbidden` and core transition `PermissionError` to `403 authority_decision_denied`; officer-group membership alone is never sufficient authority.

An officer's resolved Discord member UUID has no application authority grants by default. An operator must grant `application.review` (or the broader review-permission set) on the resolved member UUID at the relevant scope before queue access works. The slice does NOT auto-grant; that would circumvent the existing authority model and is anti-scope.

Officer with Discord claim and authority: the bridge resolves the member UUID, calls existing list/transition services, and lets those services enforce review authority. Submitted rows show in the list but have no claim button (state machine forbids `submitted -> claim`); officers must wait for the row to be routed to `queued` before claiming. The client treats API `403` as authoritative even if `/api/me` says the user is in the officer group.

Applicant receipt: the `applicant_receipt` cookie remains scoped to `/applications`, `/auth/discord/me`, and public application submit. Officer routes ignore it completely. This specifically removes the bridge's prior use of the receipt; it does not delete applicant receipt machinery.

## 7. Test Plan

### Unit/component tests (Playwright)

- `officer queue redirects anonymous Pomerium user`: route `/applications/queue/`, mock `/api/me` as 401, assert auth panel and no queue table.
- `officer queue treats opaque/302 fetch response on /api/me as auth-required`: mock `/api/me` as a redirect/opaque response or fetch failure, assert auth panel, no queue table, and no queue data fetch continues.
- `officer queue blocks non-officer principal`: mock `/api/me` with no `officers` group, assert forbidden panel and no queue fetch.
- `officer queue blocks officer missing Discord claim`: mock `/api/me` officer with `discord_user_id: null`, assert identity-incomplete panel and `/.pomerium/sign_in` hard redirect action.
- `officer queue ignores applicant receipt`: set an unrelated `applicant_receipt`, mock `/api/me` with a different Pomerium `discord_user_id`, assert no `/auth/discord/me` request is made and queue requests proceed only with Pomerium identity.
- `officer queue renders submitted and queued rows`: mock principal with groups and `discord_user_id`, and list response from `contract.json`; assert headings, state toggles, row fields, and claim buttons only for `queued`.
- `officer queue submitted row shows no claim button`: assert the claim button is absent for `state == "submitted"`.
- `officer queue filters by state`: click state toggles and assert query string sent to `/api/web/officer/applications?state=...`.
- `officer queue load more appends rows`: first response has `next_after_id`, second request includes `after_id`, UI appends without replacing earlier rows.
- `officer queue queued row claim posts If-Match`: click claim on a queued row, assert `If-Match: "<row.version>"`, no `expected_version` body, returned row updates state/owner, and a refetch occurs.
- `officer queue claim conflict refetches`: claim returns `409 application_already_claimed` or `412 stale_application_version`, assert conflict notice and refetch.
- Existing `compat.spec.ts` tests continue to cover public route, applicant receipt gate, submit payload, "Application form" role=link navigation, UI library smoke, and the stale receipt redirect behavior.
- Add to `services/web/tests/compat.spec.ts` (or a new `applicant-route.spec.ts`) explicit assertions that `#tab-overview`, `#tab-details`, and `#details-panel` are NOT in the DOM under both the `checking` and `anonymous` auth states. This lock-in pins the new tightened compatibility surface 133B-ii will rely on.
- Add an assertion to the existing `loggedInApplicantTest` "Ark FontAwesome and TanStack" test (or a new test) that, in `verified` state before clicking the Details tab, `#details-panel` is present in the DOM with the `[hidden]` attribute set; after clicking the Details tab, `[hidden]` is removed. This locks the toggle invariant the DOM contract claims instead of relying only on post-click icon visibility.

### API tests

- `web officer list requires Pomerium identity`: no Pomerium headers -> 401.
- `web officer list requires officers group`: Pomerium principal without `officers` -> 403.
- `web officer list requires Pomerium Discord claim`: officer headers without `x-pomerium-claim-discord-user-id` -> 401 `officer_discord_identity_missing`.
- `web officer list rejects invalid Discord claim`: officer headers with non-snowflake claim -> 401 `officer_discord_identity_invalid`.
- `web officer claim rejects looser-regex Discord claim`: officer claim header that satisfies a looser regex but fails `DISCORD_SNOWFLAKE_RE`, such as `123`, returns `401 officer_discord_identity_invalid`.
- `web officer list ignores applicant receipt`: mismatched applicant receipt cookie does not change the resolved actor.
- `officer bridge endpoints are coroutine functions`: import the bridge module / app route table and assert each `/api/v1/web/officer/...` route's `endpoint` is a coroutine function via `asyncio.iscoroutinefunction(...)`.
- `web officer list returns ApplicationListRead`: officer + Discord claim + authority -> 200 matching `ApplicationListRead`.
- `web officer list/claim distinguish authority failures`: Pomerium principal is in `officers`, Discord claim resolves to a real member, but member has no application grants. List returns `403 application_list_forbidden`; claim returns `403 authority_decision_denied`.
- `web officer claim maps Pomerium Discord claim to member actor`: claim succeeds, returned `ApplicationRead.owner_id` equals the resolved member UUID.
- `test_officer_claim_ignores_x_actor_headers`: send a valid Pomerium officer + Discord claim request along with `X-Actor-Kind: user` and `X-Actor-Id: <attacker-chosen UUID>`. Assert the resulting `ApplicationRead.owner_id` after claim equals the Pomerium-resolved officer member UUID, NOT the attacker-supplied UUID.
- `web officer claim without grant maps PermissionError`: Pomerium officer + valid Discord claim but no claim grant -> 403 `authority_decision_denied`.
- `web officer claim missing If-Match returns 428 if_match_required / malformed returns 412 invalid_if_match / stale returns 412 stale_application_version`: missing or weak/malformed/stale header never defaults to the current server version, and the bridge passes the core HTTPException code verbatim (A3).
- `web officer claim missing identity headers and missing If-Match returns 401`: a request with neither Pomerium identity headers nor `If-Match` returns `401 officer_discord_identity_missing` or the bridge's equivalent identity-missing response, not `428 if_match_required`, proving identity validation runs before `parse_if_match_strong(request)` (A5).
- `officer bridge claim response carries etag header matching ApplicationRead.version`: after a successful claim, assert `response.headers["etag"] == f'"{response.json()["version"]}"'`.
- `raise_known_application_error maps ApplicationListForbiddenError`: call the shared helper directly with `ApplicationListForbiddenError` and assert it raises `HTTPException(status_code=403, detail["code"] == "application_list_forbidden")`. This test lands before the bridge tests so the mapper migration is proven independently.
- `web officer claim stale version returns conflict/precondition failure`: stale `If-Match` maps to structured error without swallowing service errors.
- `web officer claim against non-existent application id returns 404 application_not_found`: the bridge forwards `ApplicationNotFoundError` through `raise_known_application_error` and does not degrade it to 500.
- `web officer claim while application is owned by another officer returns 409 application_not_owner`: the bridge forwards `ApplicationNotOwnerError` through `raise_known_application_error` with the direct endpoint error code.
- `web officer claim against application in non-claimable state returns 409 invalid_application_transition`: the bridge forwards `InvalidApplicationTransitionError` through `raise_known_application_error` with the direct endpoint error code.
- `web officer claim member-resolution non-discord row -> 422 officer_discord_member_invalid`: a Discord snowflake bound to a non-discord member row is a structured identity-invalid response, not a 500 or authority denial (A4).
- `web officer first login records member creation under web-officer-bridge actor`: when the bridge creates a previously unseen Discord member, the member aggregate audit rows contain `originating_actor_kind="service"`, `originating_actor_id="web-officer-bridge"`, and `request_surface="api:/api/v1/web/officer/applications"` (A5).
- `officer queue claim audit row records bridge request surface`: after a successful bridge claim, `application_reviews` and `activity_actions` audit rows record `request_surface="api:/api/v1/web/officer/applications/{id}/claim"`, not the legacy direct-API path `api:/api/v1/applications/{id}/transitions`.
- `test_officer_endpoints_have_locked_actor_construction`: import the FastAPI app, walk the route dependency tree for every `/api/v1/web/officer/` route, and assert the dependency tree contains none of `app.core.dependencies.get_current_actor`, `app.core.context.get_current_actor`, `verify_applicant_receipt`, any callable that reads `CURRENT_ACTOR.get()`, or any callable that reads `applicant_receipt` from request cookies. This is a Python test under `services/api/tests/`, not only a web-side grep, so it survives refactors that move literal strings.
- `test_web_identity.py` asserts `/api/v1/me` returns exact JSON including `groups: []` and `discord_user_id: None` when those headers are absent.
- Officer Discord identity parsing tests cover both status codes: absent `x-pomerium-claim-discord-user-id` returns `401 officer_discord_identity_missing`; present but not snowflake-shaped returns `401 officer_discord_identity_invalid`. Both produce the same auth-required/identity-incomplete UX.
- `/api/v1/me` group parsing test covers absent `x-pomerium-claim-groups` -> `groups: []`, `"officers"` -> `["officers"]`, `"officers, admins"` -> `["officers", "admins"]`, `'["officers", "admins"]'` -> `["officers", "admins"]`, and `""` -> `[]`; exact membership uses post-trim values only (A6).

### Static infra tests

- Authentik blueprint test asserts `init-133B-pomerium-officer-discord.yaml` exists in the mounted configmap data and declares the `pomerium` OAuth2 provider/application.
- Authentik blueprint test asserts a distinct `discord-pomerium` OAuth source with `scope: identify` and no `email`, `guilds`, or `guilds.members.read`.
- Authentik blueprint test asserts a source property mapping stores `discord_user_id` from `info.get("id")`.
- Authentik blueprint test asserts the Pomerium OAuth2 provider has a `server-manager-pomerium-discord_user_id` scope mapping and includes claims in tokens.
- Authentik blueprint test asserts the Pomerium `discord_user_id` scope mapping reads `request.user.attributes.get("discord_user_id")` so the bootstrap fixture user's `attributes.discord_user_id` reaches the Pomerium token.
- Authentik blueprint test asserts the e2e Pomerium principal, the `sample` user, belongs to both `Humility Local Users` and `officers`.
- Pomerium static test asserts `idp_scopes` split on whitespace set-compares exactly to `{openid, email, profile, discord_user_id}` (A7).
- Pomerium static test asserts `jwt_claims_headers` has exactly five keys: `email`, `sub`, `x-pomerium-claim-groups`, `name`, and `x-pomerium-claim-discord-user-id`; also assert `jwt_claims_headers.x-pomerium-claim-discord-user-id == discord_user_id` (A7).
- Pomerium static test asserts `x-pomerium-claim-groups` appears exactly once in `jwt_claims_headers`, locking the single-header semantics the parser assumes.
- Pomerium static test asserts exact `/api/me`, exact `/applications/queue`, nested `/applications/queue/`, `/api/web/admin/`, and `/api/web/officer/` precede the public catch-all and do not shadow `/applications`.
- Pomerium static test resolves both directions: an `/applications` request resolves to the public catch-all entry, not the `/applications/queue` entry; `/applications/queue` resolves to the exact auth-gated entry; `/applications/queue/` resolves to the nested auth-gated prefix entry (A8).
- Pomerium static test includes collision-class fixtures: hypothetical `/api/me-foo`, `/applications/queue-foo`, and `/api/members/...` requests must not match the auth-gated `/api/me` or `/applications/queue` exact-path entries; `/api/me` must use `path:`, not `prefix:`.
- Pomerium static test asserts `/api/me`, `/api/web/admin/`, and `/api/web/officer/` resolve to identity-bearing routes targeting `http://server-manager-web.web.svc.cluster.local:8080`.
- `validate_web_ui_local.sh` static test widens the negative grep to `grep -rE "[\"']/api/v1/" services/web/src/`, which must return zero matches for any `/api/v1/...` literal anywhere under `services/web/src/`, not just direct `fetch()` call sites. Combined with the positive `client.ts` allowlist, this guards against indirect `/api/v1/...` use anywhere in the SPA. The applicant submit POST in `ApplicationFormRoute.tsx` uses `/api/public/applications` with no `/v1/` literal, so it does not trigger the grep. The script still asserts `client.ts` calls only `/api/me`, `/api/web/admin/chapters`, `/api/web/officer/applications`, `/api/web/officer/applications/{id}/claim`, and `/auth/discord/me`, and asserts the applicant submit POST remains inline in `ApplicationFormRoute.tsx`, not in `client.ts`. It also curls the live local `https://web.local.humility.local/api/me` endpoint with simulated Pomerium headers and verifies the JSON shape:

  ```bash
  curl -sk \
    -H "x-pomerium-claim-sub: humility-officer-1" \
    -H "x-pomerium-claim-email: officer@humility.local" \
    -H "x-pomerium-claim-name: Humility Officer" \
    -H "x-pomerium-claim-groups: officers" \
    -H "x-pomerium-claim-discord-user-id: 210987654321098765" \
    https://web.local.humility.local/api/me \
    | jq -e '.subject == "humility-officer-1" and .groups == ["officers"] and .discord_user_id == "210987654321098765"'
  ```

### E2E

Extend `19-web-ui.sh` and `browser-flow.mjs`. After the existing public applicant submit persists a queued application with a real Discord member, resolve or create the member UUID for the contract.json officer principal, then seed authority grants before navigating to `/applications/queue/`. The e2e Pomerium principal is the `sample` user, who is now a member of both `Humility Local Users` and `officers`. The bridge's officer-group check resolves true because Authentik emits `groups` containing `officers`. The same principal acquires the Discord claim via the bootstrap fixture user's `attributes.discord_user_id`; the seed-authority-grants helper resolves this snowflake to a member UUID and grants on it. There is no existing authority-grants seed helper under `infra/tests/e2e/lib/`; add `infra/tests/e2e/lib/seed-authority-grants.mjs` as the concrete seed surface. It must use the existing `KUBECONFIG_PATH` and the primary-pod kubectl/psql pattern from `19-web-ui.sh` to idempotently insert active grants on the resolved member UUID for exactly `application.review` and `application.claim` at the relevant scope. Then navigate as the authenticated Pomerium user to `/applications/queue/`, rely on Pomerium identity headers including the new Discord claim, assert the queued application appears, click claim, record the application id, and verify in Postgres that `state='claimed'`, `applications.owner_id != applications.applicant_id`, `members.discord_user_id WHERE id = applications.owner_id` matches `E2E_OFFICER_DISCORD_USER_ID` from the bootstrap fixture user's `attributes.discord_user_id`, and the matching `members.kind = 'discord'` rather than synthetic. Keep the suite count at 19. The e2e flow may still inject `applicant_receipt` for the applicant submit step; the queue step must not rely on that cookie.

## 8. Anti-scope

- No application detail page; INIT-133B-ii owns `/applications/{id}` and full `GET /api/v1/applications/{id}` rendering.
- No transcript view; INIT-133B-ii owns `GET /api/v1/applications/{id}/transcript`.
- No message thread; INIT-133B-iii owns `GET/POST /api/v1/applications/{id}/messages`.
- No decisions beyond claim; INIT-133B-iii owns review, approve, deny, waitlist, request interview, reassign, reactivate, and withdraw controls.
- No Discord-visible writes, channel creation, DMs, or officer review embed; BL-009 and BL-020 own those.
- No scope selector, "mine" filter, search, export, or bulk actions.
- No schema migration, `member_links` table, or new durable identity-link subsystem.
- No new authority permission names.
- No `actor_kind="officer"` or any new actor kind.
- No browser-supplied `X-Actor-Kind` / `X-Actor-Id`; the web-officer API bridge constructs actor identity server-side.
- No reuse of `applicant_receipt` for officer actor identity.
- No feature flag, legacy vanilla route fallback, or retained `RuntimeApp` parallel entry.

## 9. Diff Budget

Estimated net: `+1,060 / -260` lines.

Breakdown: web TanStack Solid Router migration and queue `+520 / -220`; web tests `+220`; API web-officer bridge, member-service parameterization, and API tests `+280`; Authentik blueprint and static tests `+90`; fixture/e2e/Pomerium route assertions `+190 / -40`; `infra/tests/e2e/lib/seed-authority-grants.mjs` `+20`. The seed helper's approximate diff is one small Node script that shells to `kubectl` to locate the primary Postgres pod, reads `server-manager-postgres-url`, and runs one idempotent psql transaction inserting exactly `application.review` and `application.claim` for the supplied member UUID and scope. Bumping the grant set to include `application.approve`, `application.deny`, `application.waitlist`, `application.reactivate`, or `application.withdraw` is anti-scope and belongs in 133B-iii's e2e fixture. The Pomerium/Authentik identity-binding addition replaces the old receipt bridge rather than adding a second auth path, so this should remain under the prior `+1,250` net-line ceiling. If implementation exceeds that ceiling or touches unrelated backend services, the scope gate should fail and split the TanStack Solid Router migration from the queue route.

## 10. Risk Gates (Self-Review)

### Audit

Round 10 audit returned MEDIUM with one HIGH severity finding (A1), two MEDIUM findings (A2, A3), and four LOW findings (A4..A7). This r11 revision applies all seven corrections in the proposal text; audit is LOW after these resolutions.

- A1: §3, §4, §6, and §7 switch the SPA principal probe back to `/api/me` with no trailing slash, replace the Pomerium `/api/me/` prefix with exact `path: /api/me`, and add collision tests proving `/api/me-foo` and `/api/members/...` do not match. `/applications/queue` gets the same exact-path protection plus `prefix: /applications/queue/` for nested routes.
- A2: §4 and §6 state that `list_applications(...)` and `transition_application(...)` are synchronous service calls. The bridge endpoints remain `async def` only because `resolve_or_create_real_discord_member(...)` is async.
- A3: §4 and §6 destructure the transition return as `read, result = transition_application(...)`, then call `set_etag(response, result.etag)` and return `read`.
- A4: §4 and §6 handle `ValueError` from `resolve_or_create_real_discord_member(...)` in a resolver-only block and map the non-discord-member case to `422 officer_discord_member_invalid`; `ValueError` is not caught by the `transition_application(...)` mapper block.
- A5: §4 and §6 order claim handling as Pomerium principal, officer group, Discord claim, member resolution, then `parse_if_match_strong(request)`. §7 adds the API test that missing identity headers plus missing `If-Match` returns `401`, not `428`.
- A6: §3 updates `infra/tests/fixtures/web-ui/contract.json` so `auth.probe_endpoint` is `/api/me`, matching the live SPA path.
- A7: §3 and §7 add the live `validate_web_ui_local.sh` curl assertion for `https://web.local.humility.local/api/me` with simulated Pomerium identity headers and `CurrentPrincipalRead` JSON verification.

### Scope

Scope remains LOW. The queue is still list + claim only; the revisions above pin behavior and tests without adding schema, actor kinds, permissions, detail view, transcript, messaging, or Discord-visible writes.

### Shortcut

Shortcut remains LOW. The bridge still constructs actor identity server-side from Pomerium, validates real `If-Match` with the shared helper, uses Zod-validated client contracts, and delegates list/claim logic to existing application services.

### Supported-surface

Supported-surface remains LOW. The applicant surface, `/auth/discord/*`, `applicant_receipt`, public submit, and existing compat coverage remain supported; Pomerium additions are exact-path or nested-prefix protected routes before the catch-all and now have explicit non-shadow tests. Officer Discord OAuth uses separate `DISCORD_OFFICER_OAUTH_CLIENT_ID` / `DISCORD_OFFICER_OAUTH_CLIENT_SECRET` credentials, so officer credential revocation is operationally independent from the applicant OAuth source.

## 11. Hookpoint Preview

Reuse:

- `services/web/src/app/router.tsx`, `providers.tsx`, and `store.ts` as the real TanStack Solid Router runtime.
- Reuse the existing `@tanstack/solid-router` `createRoute` / `createRouter` API; do NOT add `@solidjs/router` (a different package).
- Existing primitives/components where they serve real UI (`Button`, `Icon`, table/layout CSS patterns).
- Existing applicant receipt verifier only for applicant routes; do not delete it.
- Existing `resolve_or_create_real_discord_member` for converting the Pomerium-asserted Discord snowflake to a real member UUID.
- Existing application list and transition services/contracts; do not duplicate list/claim logic.
- Existing Playwright fixture/mocking style and test 19 browser flow.
- Existing applicant Authentik blueprint pattern for the officer Pomerium app's Discord source property mapping and `discord_user_id` scope mapping.

Delete:

- `services/web/src/RuntimeApp.tsx`, because it is a second unmounted runtime.
- Demo-only form scaffolding if it is not transformed into the real applicant route.
- Vanilla DOM rendering in `main.tsx`; keep only TanStack Solid Router bootstrap.

Leave alone:

- Core `/api/v1/applications` endpoint semantics, including actor headers and `If-Match`.
- Public submit API and applicant Discord OAuth endpoints.
- `applicant_receipt` cookie machinery for applicant routes.
- Build image, nginx container, and deployment image tag mechanics.
- Database schema, authority permission names, and `ActorIdentity` literal values.

Under this architecture, `features/{public,admin}/*Route.tsx` stop being parallel scaffolding: `HomeRoute` and `AdminChaptersRoute` become the actual routes mounted by `main.tsx`, while the applicant form and officer queue are added beside them as real TanStack Solid Router routes. The bridge's use of `applicant_receipt` is removed; the receipt system itself is kept for the public applicant flow.
