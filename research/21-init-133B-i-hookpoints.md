# INIT-133B-i hookpoints

## Summary

The slice can reuse the existing FastAPI routing, Pomerium principal, application list/transition, ETag, member-resolution, authority, and test fixture patterns directly. The backend bridge is new but should stay thin: parse Pomerium officer identity, resolve the Discord snowflake to a real member UUID, construct `ActorIdentity(user, member.id)`, and delegate to the existing application services. The frontend needs a real TanStack Solid Router bootstrap and a fresh officer queue route, while deleting the unmounted/demo runtime and preserving the current applicant DOM contract now embedded in vanilla `main.tsx`.

## Reuse (call directly)

### Backend

- `app.api.v1.router.router` (`services/api/app/api/v1/router.py:36`) - central v1 router already includes `me.router` and `web.router` (`services/api/app/api/v1/router.py:45`, `services/api/app/api/v1/router.py:58`). New officer routes belong in the existing `web.py` router, not a new router tree.
- `app.core.factory.create_api_app` (`services/api/app/core/factory.py:29`) - app factory already installs `ActorMiddleware`, `CorrelationMiddleware`, state, and the v1 router (`services/api/app/core/factory.py:70`, `services/api/app/core/factory.py:89`). No app bootstrap hookpoint is missing.
- `app.api.v1.endpoints.me.get_pomerium_principal` (`services/api/app/api/v1/endpoints/me.py:18`) - existing Pomerium identity parser for `subject`, `email`, and `display_name`; extend it to parse `groups` and `discord_user_id` instead of creating a second principal path.
- `app.contracts.web.CurrentPrincipalRead` (`services/api/app/contracts/web.py:13`) - additive contract target for `groups: list[str]` and `discord_user_id: str | None`. Keep `_WebModel` extra-forbid behavior (`services/api/app/contracts/web.py:9`).
- `app.api.v1.endpoints.web._db` (`services/api/app/api/v1/endpoints/web.py:14`) - local dependency for `request.app.state.db`; officer endpoints can reuse this exactly.
- `app.api.v1.endpoints.web.admin_chapters` (`services/api/app/api/v1/endpoints/web.py:18`) - existing web bridge pattern: Pomerium principal dependency plus `PostgresDatabase` dependency, then call a service. Officer routes differ by being `async def`, but the dependency shape is reusable.
- `app.api.v1.endpoints.applications._shared.parse_if_match_strong` (`services/api/app/api/v1/endpoints/applications/_shared.py:33`) - emits the required `428 if_match_required` and `412 invalid_if_match` responses (`services/api/app/api/v1/endpoints/applications/_shared.py:35`, `services/api/app/api/v1/endpoints/applications/_shared.py:46`). Rename or re-export through `etag.py` before cross-package import from `web.py`.
- `app.api.v1.endpoints.applications._shared.set_etag` (`services/api/app/api/v1/endpoints/applications/_shared.py:59`) - use after successful claim so bridge responses match direct lifecycle responses.
- `app.api.v1.endpoints.applications._shared.raise_known_application_error` (`services/api/app/api/v1/endpoints/applications/_shared.py:63`) - service exception mapper for bridge list/claim. It currently lacks `ApplicationListForbiddenError`; direct list maps that locally in `lifecycle.py` (`services/api/app/api/v1/endpoints/applications/lifecycle.py:106`), so mapper migration is a prerequisite.
- `app.contracts.applications.ApplicationScope` (`services/api/app/contracts/applications.py:62`) - frontend Zod schema should mirror `scope_kind` / `scope_id` validation.
- `app.contracts.applications.ApplicationTransitionAction.claim` (`services/api/app/contracts/applications.py:49`) and `ApplicationTransitionRequest` (`services/api/app/contracts/applications.py:249`) - claim bridge constructs `ApplicationTransitionRequest(action=ApplicationTransitionAction.claim)` server-side.
- `app.contracts.applications.ApplicationRead` (`services/api/app/contracts/applications.py:352`) and `ApplicationListRead` (`services/api/app/contracts/applications.py:375`) - officer list/claim response contracts; no officer-specific duplicate response model is needed.
- `app.contracts.applications.ApplicationListForbiddenError` (`services/api/app/contracts/applications.py:463`) - fold into shared known-error mapper as `403 application_list_forbidden`.
- `app.services.applicant_discord_auth.DISCORD_SNOWFLAKE_RE` (`services/api/app/services/applicant_discord_auth.py:23`) - officer bridge should import this regex for Pomerium `discord_user_id`; do not define a bridge-local regex.
- `app.services.members.resolve_or_create_real_discord_member` (`services/api/app/services/members.py:192`) - async resolver from Discord snowflake to real member. Parameterize `originating_actor` and `request_surface`; existing validation and non-discord row rejection are reusable (`services/api/app/services/members.py:197`, `services/api/app/services/members.py:184`).
- `app.services.applications.list_applications` (`services/api/app/services/applications.py:420`) - queue list service already accepts states, scope, owner, limit, and cursor and returns `ApplicationListRead` (`services/api/app/services/applications.py:460`).
- `app.services.applications.transition_application` (`services/api/app/services/applications.py:1059`) - claim service already returns `(ApplicationRead, MutationResult)` (`services/api/app/services/applications.py:1140`), enforces transition authority (`services/api/app/services/applications.py:1078`), and accepts a custom `request_surface` (`services/api/app/services/applications.py:1065`).
- `app.services.applications._reviewer_id` (`services/api/app/services/applications.py:266`) - enforces review actions as `actor_kind="user"` and UUID actor ids; this is why the bridge must construct `ActorIdentity(user, member_uuid)`.
- `app.services.applications.require_transition_authority` (`services/api/app/services/applications.py:348`) and `_has_application_list_authority` (`services/api/app/services/applications.py:393`) - existing permission gates. Do not add officer-group auto-grants.
- `app.core.actor.ActorMiddleware` (`services/api/app/core/actor.py:63`) - actor headers are optional unless `_requires_actor` returns true (`services/api/app/core/actor.py:52`). `/api/v1/web/officer/...` is not currently in `_requires_actor`, so browser `X-Actor-*` headers are not needed and should be ignored by bridge construction.

### Frontend

- `services/web/src/main.tsx` live DOM contract - current public/applicant/admin runtime is here, not in Solid routes. Preserve `#root` lookup (`services/web/src/main.tsx:3`), public start button behavior (`services/web/src/main.tsx:58`, `services/web/src/main.tsx:168`), applicant auth states (`services/web/src/main.tsx:27`), form ids/testids (`services/web/src/main.tsx:89`, `services/web/src/main.tsx:99`, `services/web/src/main.tsx:119`), applicant receipt probe (`services/web/src/main.tsx:245`), inline public submit to `/api/public/applications` (`services/web/src/main.tsx:200`), and draft storage keys (`services/web/src/main.tsx:151`, `services/web/src/main.tsx:284`).
- `services/web/src/app/router.tsx` - real TanStack Solid Router scaffold already imports `createRootRoute`, `createRoute`, and `createRouter` (`services/web/src/app/router.tsx:1`). Add `/applications` and `/applications/queue/` to `routeTree`, and add the exact `<Link to="/applications">Application form</Link>` beside the existing nav links (`services/web/src/app/router.tsx:23`).
- `services/web/src/app/providers.tsx` - query/router provider wrapper already exists (`services/web/src/app/providers.tsx:24`). Replace the `any` router prop with `typeof router`, but keep `QueryClientProvider`, `ThemeRuntime`, and `RouterProvider` as the only runtime wrapper (`services/web/src/app/providers.tsx:26`).
- `services/web/src/app/store.ts` - current global store only owns UI theme/nav state (`services/web/src/app/store.ts:11`); officer queue state should remain route-local.
- `services/web/src/api/client.ts` - reuse `getJson` fetch/Zod pattern (`services/web/src/api/client.ts:25`) and extend `principalSchema` (`services/web/src/api/client.ts:3`). Current `/api/v1/...` literals (`services/web/src/api/client.ts:39`, `services/web/src/api/client.ts:43`) must switch to browser-facing `/api/...`.
- `services/web/src/features/admin/AdminChaptersRoute.tsx` - keep Solid Query/table/virtualization pattern (`services/web/src/features/admin/AdminChaptersRoute.tsx:34`, `services/web/src/features/admin/AdminChaptersRoute.tsx:43`, `services/web/src/features/admin/AdminChaptersRoute.tsx:53`) but update the client URL underneath.
- `services/web/src/components/primitives/Button.tsx` (`services/web/src/components/primitives/Button.tsx:5`) and `services/web/src/components/icons/Icon.tsx` (`services/web/src/components/icons/Icon.tsx:31`) - reusable controls for officer buttons/status icons.
- `services/web/src/styles/layers.css` - shared shell, nav, runtime panel, tabs, stack, field, and responsive primitives already exist (`services/web/src/styles/layers.css:110`, `services/web/src/styles/layers.css:157`, `services/web/src/styles/layers.css:204`, `services/web/src/styles/layers.css:232`, `services/web/src/styles/layers.css:253`). New officer CSS should be route-local but can align with these tokens.
- `services/web/index.html` - Vite loads `/src/main.tsx`; replacing the bootstrap there is sufficient because the page root is already `<div id="root"></div>` (`services/web/index.html:24`, `services/web/index.html:25`).

### Test fixtures

- `services/api/tests/conftest.py` - `migrated_async_client`, `governance_dsn`, and `governance_db` provide the API bridge test substrate (`services/api/tests/conftest.py:320`, `services/api/tests/conftest.py:328`, `services/api/tests/conftest.py:343`).
- `services/api/tests/test_web_identity.py` - exact `/api/v1/me` JSON contract to update for `groups` and `discord_user_id` (`services/api/tests/test_web_identity.py:21`, `services/api/tests/test_web_identity.py:37`); same file covers web-admin identity gate (`services/api/tests/test_web_identity.py:53`).
- `services/api/tests/test_applications_list.py` - reusable helpers for publishing forms, creating members, granting authority, creating applications, and claiming via direct lifecycle endpoint (`services/api/tests/test_applications_list.py:42`, `services/api/tests/test_applications_list.py:68`, `services/api/tests/test_applications_list.py:134`, `services/api/tests/test_applications_list.py:156`, `services/api/tests/test_applications_list.py:181`).
- `services/api/tests/test_applications.py` - direct claim helper and transition coverage establish expected ETag/authority behavior (`services/api/tests/test_applications.py:160`).
- `services/web/tests/compat.spec.ts` - contract fixture loading and route mocking style (`services/web/tests/compat.spec.ts:36`, `services/web/tests/compat.spec.ts:67`, `services/web/tests/compat.spec.ts:88`). New officer spec should keep this fixture-driven style but live in `officer-queue.spec.ts`.
- `infra/tests/test_applicant_discord_blueprint.py` - Authentik blueprint loader already handles `!Find` / `!Env` tags (`infra/tests/test_applicant_discord_blueprint.py:21`, `infra/tests/test_applicant_discord_blueprint.py:33`) and has entry filtering helpers (`infra/tests/test_applicant_discord_blueprint.py:48`, `infra/tests/test_applicant_discord_blueprint.py:55`).
- `infra/tests/test_applicant_discord_pomerium.py` - Pomerium config loader and web-route indexing helpers are the right place for route ordering and collision tests (`infra/tests/test_applicant_discord_pomerium.py:21`, `infra/tests/test_applicant_discord_pomerium.py:35`, `infra/tests/test_applicant_discord_pomerium.py:49`).
- `infra/tests/validate_web_ui_local.sh` - static fixture/spec/build/runtime shell proof already has assertion structure to extend (`infra/tests/validate_web_ui_local.sh:100`, `infra/tests/validate_web_ui_local.sh:122`, `infra/tests/validate_web_ui_local.sh:138`, `infra/tests/validate_web_ui_local.sh:151`).
- `infra/tests/e2e/tests/19-web-ui.sh` - already retrieves e2e applicant fixtures, runs validator, runs Playwright, and verifies the submitted application in Postgres (`infra/tests/e2e/tests/19-web-ui.sh:39`, `infra/tests/e2e/tests/19-web-ui.sh:50`, `infra/tests/e2e/tests/19-web-ui.sh:51`, `infra/tests/e2e/tests/19-web-ui.sh:8`).
- `infra/tests/e2e/lib/playwright/browser-flow.mjs` - existing web-ui flow logs into Pomerium, injects applicant receipt, submits the public application, and records `application_id` (`infra/tests/e2e/lib/playwright/browser-flow.mjs:81`, `infra/tests/e2e/lib/playwright/browser-flow.mjs:86`, `infra/tests/e2e/lib/playwright/browser-flow.mjs:121`).
- `infra/tests/fixtures/web-ui/contract.json` - fixture already declares `/api/me`, applicant receipt names, form route, and public submit contract (`infra/tests/fixtures/web-ui/contract.json:33`, `infra/tests/fixtures/web-ui/contract.json:35`, `infra/tests/fixtures/web-ui/contract.json:44`, `infra/tests/fixtures/web-ui/contract.json:60`).

### Config patterns (Authentik / Pomerium)

- The applicant Authentik blueprint already has the source property mapping shape that stores `info.get("id")` into `request.user.attributes["discord_user_id"]` (`gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:45`, `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:51`).
- The applicant scope mapping shows how to emit `discord_user_id` from `request.user.attributes.get("discord_user_id")` (`gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:57`, `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:65`).
- The applicant Discord OAuth source uses `provider_type: discord`, separate credentials, and `scope: identify` only (`gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:69`, `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:76`, `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:85`).
- The applicant OAuth provider/application pattern wires a provider to an Authentik application and source (`gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:88`, `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:104`, `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:113`). Mirror this for `pomerium` / `discord-pomerium`.
- Pomerium currently requests `openid email profile` (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:37`) and forwards email, sub, groups, and name (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:42`). Extend this exact `idp_scopes` and `jwt_claims_headers` block.
- Existing web-host route order is `/admin`, `/auth/discord/`, public catch-all (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:48`, `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:54`, `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:60`). Insert `/api/me`, `/api/web/admin/`, `/api/web/officer/`, and queue routes before the public catch-all.

## New (write fresh)

### Backend

- `services/api/app/api/v1/endpoints/web.py` officer routes - add `GET /officer/applications` and `POST /officer/applications/{application_id}/claim`. Minimal shape: `async def`, parse Pomerium principal, exact officer-group check, validate `discord_user_id` with `DISCORD_SNOWFLAKE_RE`, await `resolve_or_create_real_discord_member`, construct `ActorIdentity(actor_kind="user", actor_id=str(member.id))`, then synchronously call `list_applications` / `transition_application`.
- `services/api/app/api/v1/endpoints/web.py` local helpers - write a version-tolerant groups parser shared by list/claim and consistent with `/api/v1/me`; write small HTTP error helpers for `officer_required`, `officer_discord_identity_missing`, `officer_discord_identity_invalid`, and `officer_discord_member_invalid`.
- `services/api/app/contracts/web.py` extensions - add only `groups: list[str] = []` and `discord_user_id: str | None = None` to `CurrentPrincipalRead`; no removals and no separate officer-principal model unless tests force it.
- `services/api/app/api/v1/endpoints/applications/etag.py` - stable import surface for `parse_if_match_strong` and maybe `set_etag`. If only ETag helpers move, keep `raise_known_application_error` in `_shared.py`; if mapper moves too, update every in-tree import.
- `services/api/tests/test_web_officer_applications.py` - new API bridge tests using `migrated_async_client` and `governance_db`; cover identity failures, group parsing, missing/invalid Discord claim, applicant receipt ignored, X-Actor headers ignored, list authority denial, claim authority denial, ETag ordering, successful claim, claim ETag header, resolver non-discord row mapping, and dependency-tree guard.

### Frontend

- `services/web/src/features/public/ApplicationFormRoute.tsx` - Solid route that ports live applicant behavior from `main.tsx`; it should own applicant auth signal, 9-minute re-probe, submit-time `/auth/discord/me` recheck, draft preservation, inline `/api/public/applications` POST, and the selector/accessible-name contract from the proposal.
- `services/web/src/features/officer/ApplicationQueueRoute.tsx` - fresh route component with route-local signals: principal state, selected states, items, `next_after_id`, claiming id, and notices. It should call `fetchCurrentPrincipal`, block non-officer/missing-claim states, fetch `/api/web/officer/applications`, render state toggles, list rows, load-more, and claim only queued rows with `If-Match`.
- `services/web/src/features/officer/officer.module.css` - route-local queue CSS. Reuse global tokens, but avoid depending on deleted `runtime*` demo classes.
- `services/web/tests/officer-queue.spec.ts` - new Playwright spec. It exercises `/api/me` auth states, no `/auth/discord/me` officer calls, list query state filters, submitted-row no-claim behavior, load-more append, claim `If-Match`, conflict/precondition refetch, and forbidden/identity-incomplete panels.

### Tests

- `services/api/tests/test_web_officer_applications.py::test_raise_known_application_error_maps_application_list_forbidden` - direct mapper unit test should land before bridge endpoint tests.
- `infra/tests/e2e/lib/seed-authority-grants.mjs` - new kubectl/psql helper. It should resolve the officer Discord snowflake to a member UUID and insert or call a grant path for exactly `application.review` and `application.claim`; do not include decision permissions.
- `infra/tests/e2e/lib/playwright/browser-flow.mjs` extension - after public submit, navigate to `/applications/queue/`, assert the queued row appears, claim it, and record the claimed application id.
- `infra/tests/e2e/tests/19-web-ui.sh` extension - export `E2E_OFFICER_DISCORD_USER_ID`, seed authority grants, run queue/claim flow, and verify owner state in Postgres.
- `infra/tests/fixtures/web-ui/contract.json` extensions - add `routes.officer_queue`, `auth.officer`, `auth.headers.x-pomerium-claim-discord-user-id`, `applications.queue`, and `applications.claim`.

## Delete (parallel scaffolding)

- `services/web/src/RuntimeApp.tsx` - `rg` finds no import of `RuntimeApp` outside itself; Vite loads `src/main.tsx` instead (`services/web/index.html:25`). The file is an unmounted parallel runtime and should be deleted.
- `services/web/src/features/forms/DarkNemesisForm.tsx` - currently imported only by `HomeRoute` (`services/web/src/features/public/HomeRoute.tsx:8`) and implements a demo preview form (`services/web/src/features/forms/DarkNemesisForm.tsx:88`). Delete once `ApplicationFormRoute.tsx` owns the real applicant route.
- `services/web/src/features/forms/schema.ts` - currently imported by `DarkNemesisForm` and `RuntimeApp` only (`services/web/src/features/forms/DarkNemesisForm.tsx:8`, `services/web/src/RuntimeApp.tsx:8`). Delete if no real applicant route imports it.
- `services/web/src/features/forms/form.module.css` - currently imported by `DarkNemesisForm` only (`services/web/src/features/forms/DarkNemesisForm.tsx:15`). Delete with the demo form.
- The vanilla DOM rendering in `services/web/src/main.tsx` - replace `render()` / `root.innerHTML` routing (`services/web/src/main.tsx:146`) with `render(() => <AppProviders router={router} />, root)` while preserving `#root` lookup and moving live applicant behavior into `ApplicationFormRoute.tsx`.
- `services/api/app/api/v1/endpoints/applications/_shared.py` private ETag surface - supersede for ETag imports with `etag.py`. Do not delete the shared mapper unless the implementation moves all callers to a stable mapper module in the same change.

## Modify in place (additive only)

- `services/api/app/contracts/web.py` - `CurrentPrincipalRead` gains `groups` and `discord_user_id`; no existing fields removed (`services/api/app/contracts/web.py:13`).
- `services/api/app/api/v1/endpoints/me.py` - extend `get_pomerium_principal` to parse `x-pomerium-claim-groups` and `x-pomerium-claim-discord-user-id` (`services/api/app/api/v1/endpoints/me.py:18`). Keep `identity_missing` semantics for absent principal headers (`services/api/app/api/v1/endpoints/me.py:24`).
- `services/api/app/api/v1/endpoints/web.py` - add officer endpoints under existing `APIRouter(prefix="/api/v1/web")` (`services/api/app/api/v1/endpoints/web.py:11`). Reuse `_db`; do not add `get_current_actor`, `verify_applicant_receipt`, or cookie reads.
- `services/api/app/api/v1/endpoints/applications/_shared.py` - add `ApplicationListForbiddenError` mapping to `raise_known_application_error` before bridge work; direct list in `lifecycle.py` should delegate instead of local mapping (`services/api/app/api/v1/endpoints/applications/lifecycle.py:106`).
- `services/api/app/api/v1/endpoints/applications/lifecycle.py` - update imports after `etag.py` rename and remove local `ApplicationListForbiddenError` branch once the shared helper handles it (`services/api/app/api/v1/endpoints/applications/lifecycle.py:28`, `services/api/app/api/v1/endpoints/applications/lifecycle.py:106`).
- `services/api/app/services/members.py` - parameterize all three existing applicant-receipt audit literals inside `resolve_or_create_real_discord_member`: `action_payload` (`services/api/app/services/members.py:208`), `StateChangeDraft.payload_json` (`services/api/app/services/members.py:229`), and `_make_request(... actor/request_surface ...)` (`services/api/app/services/members.py:244`).
- `services/web/src/main.tsx` - retain only Solid bootstrap and `layers.css` import; migrate live route behavior out rather than keeping a fallback.
- `services/web/src/app/router.tsx` - add `/applications` and `/applications/queue/`, keep `/` and `/admin/chapters`, and add exact "Application form" nav link (`services/web/src/app/router.tsx:23`, `services/web/src/app/router.tsx:70`).
- `services/web/src/app/providers.tsx` - replace `router: any` (`services/web/src/app/providers.tsx:24`) with the router type.
- `services/web/src/api/client.ts` - extend schemas/types and switch browser API literals from `/api/v1/...` to `/api/...` (`services/web/src/api/client.ts:39`, `services/web/src/api/client.ts:43`).
- `services/web/src/features/public/HomeRoute.tsx` - replace demo preview with public home behavior from `main.tsx:58-76`, including `#start-application`.
- `services/web/src/features/admin/AdminChaptersRoute.tsx` - preserve table behavior but rely on updated `/api/web/admin/chapters` client path (`services/web/src/features/admin/AdminChaptersRoute.tsx:6`).
- `services/web/tests/compat.spec.ts` - update only for migrated applicant route and tightened pre-verification DOM contract; keep fixture-driven route/auth/submit/UI-library coverage (`services/web/tests/compat.spec.ts:202`, `services/web/tests/compat.spec.ts:228`).
- `services/api/tests/test_web_identity.py` - exact `/api/v1/me` expectation gains default `groups: []` and `discord_user_id: None` (`services/api/tests/test_web_identity.py:37`).
- `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml` - extend `idp_scopes`, add one `x-pomerium-claim-discord-user-id`, keep exactly one groups header, and insert protected exact/prefix routes before catch-all (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:37`, `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:42`, `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:60`).
- `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml` - add officer group/sample membership and new `init-133B-pomerium-officer-discord.yaml` data entry mirroring applicant source/scope/provider/application patterns (`gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:10`, `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:37`).
- `infra/tests/test_applicant_discord_blueprint.py` - extend existing static tests or add sibling tests using the same loader helpers (`infra/tests/test_applicant_discord_blueprint.py:36`, `infra/tests/test_applicant_discord_blueprint.py:48`).
- `infra/tests/test_applicant_discord_pomerium.py` - extend route-order tests using `_web_routes` and `_web_catch_all_index` (`infra/tests/test_applicant_discord_pomerium.py:35`, `infra/tests/test_applicant_discord_pomerium.py:49`).
- `infra/tests/validate_web_ui_local.sh` - add officer fixture/spec checks, negative `/api/v1/` grep across `services/web/src`, positive client allowlist, and live `/api/me` curl with simulated Pomerium headers (`infra/tests/validate_web_ui_local.sh:122`, `infra/tests/validate_web_ui_local.sh:151`).
- `containers/server-manager/nginx-web.conf` - no code change is required if browser paths use `/api/...`; current nginx rewrites `/api/` to API `/api/v1/` (`containers/server-manager/nginx-web.conf:8`, `containers/server-manager/nginx-web.conf:19`).
- `containers/server-manager/Containerfile.web` - no change expected; it builds `services/web` and serves `dist` through the nginx config (`containers/server-manager/Containerfile.web:10`, `containers/server-manager/Containerfile.web:19`, `containers/server-manager/Containerfile.web:23`).

## Anti-scope (do not touch)

- `services/api/app/services/applications.py` list/transition internals - bridge consumes `list_applications` and `transition_application`; do not edit state machine, ownership, authority, or audit semantics (`services/api/app/services/applications.py:420`, `services/api/app/services/applications.py:1059`).
- `services/api/app/api/v1/endpoints/applications/lifecycle.py` direct lifecycle semantics - only mapper/import cleanup; do not change direct actor-header API behavior (`services/api/app/api/v1/endpoints/applications/lifecycle.py:83`, `services/api/app/api/v1/endpoints/applications/lifecycle.py:134`).
- `services/api/app/api/v1/endpoints/applications/public.py` - applicant public submit keeps `verify_applicant_receipt` (`services/api/app/api/v1/endpoints/applications/public.py:30`).
- `services/api/app/api/v1/endpoints/auth_discord.py` and `services/api/app/services/applicant_discord_auth.py` - applicant OAuth/receipt machinery stays applicant-only (`services/api/app/api/v1/endpoints/auth_discord.py:16`, `services/api/app/api/v1/endpoints/auth_discord.py:88`, `services/api/app/services/applicant_discord_auth.py:207`).
- `app.core.dependencies.get_current_actor` and `app.core.context.CURRENT_ACTOR` - officer bridge must not depend on these (`services/api/app/core/dependencies.py:45`, `services/api/app/core/context.py:23`).
- Database schema - no `member_links`, no new actor kinds, no new permissions. Existing member UUID, member kind, applications owner, and authority grant schema already support this slice (`migrations/versions/wu-011_members.py:17`, `migrations/versions/wu-043_members_kind.py:16`, `migrations/versions/wu-022_applications.py:19`, `migrations/versions/wu-004_authority_foundation.py:17`).
- Detail/transcript/message/decision surfaces - leave application detail, transcript, messages, approve/deny/waitlist/reactivate/reassign controls to later slices.
- Discord-visible writes - no channels, messages, DMs, role changes, kicks, bans, or permission changes.
- Build/serve mechanics - keep Containerfile/nginx route behavior unless implementation discovers an actual build break (`containers/server-manager/Containerfile.web:1`, `containers/server-manager/nginx-web.conf:1`).

## Dependency ordering

The implementation must land changes in this order to keep gates green:

1. Add stable ETag import surface and fold `ApplicationListForbiddenError` into `raise_known_application_error`; update direct lifecycle list to use the helper.
2. Extend `CurrentPrincipalRead` and `/api/v1/me` group/Discord-claim parsing; update `test_web_identity.py`.
3. Parameterize `resolve_or_create_real_discord_member` audit actor/request surface and prove applicant defaults still hold.
4. Add web-officer API bridge and `test_web_officer_applications.py`; keep resolver `ValueError` handling separate from service exception mapping.
5. Migrate `main.tsx` to Solid Router bootstrap; add `ApplicationFormRoute.tsx` and keep `compat.spec.ts` green.
6. Extend `client.ts`, add `/applications/queue/` route, `ApplicationQueueRoute.tsx`, `officer.module.css`, and `officer-queue.spec.ts`.
7. Apply Authentik/Pomerium GitOps changes and static tests, including exact route-order/collision assertions.
8. Extend `contract.json`, `validate_web_ui_local.sh`, `browser-flow.mjs`, add `seed-authority-grants.mjs`, and update `19-web-ui.sh` for live queue/claim proof.

## Implementer notes

- TanStack Solid Router setup is at `services/web/src/app/`. The migration replaces `services/web/src/main.tsx`'s vanilla bootstrap with `render(() => <AppProviders router={router} />, root)` from `solid-js/web`; the project already aliases `solid-js/web` through `solid-compat/web.ts` (`services/web/src/solid-compat/web.ts:5`).
- Browser API paths must be `/api/...`, not `/api/v1/...`, because nginx rewrites `/api/` to API `/api/v1/` (`containers/server-manager/nginx-web.conf:19`). The validator should grep all `services/web/src` source literals for `/api/v1/`.
- `fetchCurrentPrincipal()` must call `/api/me` with no trailing slash. Pomerium protects exact `/api/me`; FastAPI registers `/api/v1/me` without a slash (`services/api/app/api/v1/endpoints/me.py:39`).
- The claim endpoint must validate Pomerium identity, officer group, Discord claim, and member resolution before `parse_if_match_strong(request)`. Missing identity plus missing `If-Match` should return identity failure, not `428`.
- The claim endpoint must destructure `read, result = transition_application(...)`, call `set_etag(response, result.etag)`, and return `read`.
- `ValueError` from `resolve_or_create_real_discord_member` must be caught only around the resolver; `ValueError` from service calls should continue through `raise_known_application_error`.
- Application list authority uses exact `actor.actor_id` grants (`services/api/app/services/applications.py:293`, `services/api/app/services/applications.py:400`), unlike broader alias-expanding authority helpers (`services/api/app/services/authority.py:409`). E2E grants must be written to the resolved member UUID.
- Submitted rows may appear in the queue but must not show a claim button; direct claim transition owns the state-machine denial.
- `RuntimeApp`, `DarkNemesisForm`, and `schema.ts` are scaffolding, not supported compatibility surfaces. The supported applicant surface is the DOM contract currently in `main.tsx` plus `compat.spec.ts`.

## Open questions for the orchestrator

- `RootShell` currently has no principal state. The proposal says to add queue nav only when the route has officer state; decide whether that nav is route-local on `/applications/queue/` or whether `RootShell` should own a principal query.
- The Authentik `pomerium` OAuth2 app/provider is absent from the checked-in bootstrap blueprint. The implementation should add it in GitOps, but the operator still needs real `DISCORD_OFFICER_OAUTH_CLIENT_ID` / `DISCORD_OFFICER_OAUTH_CLIENT_SECRET` values before live officer login works.
- The e2e seed helper is specified as kubectl/psql. Direct SQL is enough for application authority checks, but it will not create aggregate mutation audit rows unless it calls an API/service path; confirm whether e2e-only direct grants are acceptable.
