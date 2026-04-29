# INIT-133B-i — Supported-surface risk gate

**Verdict:** LOW

## Surfaces touched

### 1. HTTP API

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `GET /api/v1/me` | `{subject, email, display_name, provider}` | `{subject, email, display_name, provider, groups, discord_user_id}` | additive (two new fields with defaults `[]` / `None`); only `services/api/tests/test_web_identity.py` exact-equality assertion needs the additive update the proposal already calls out |
| `GET /api/v1/web/admin/chapters` | unchanged dependency tree, same response | unchanged response, unchanged dependency tree | none |
| `GET /api/v1/web/officer/applications` | n/a | new (200/401/403/422) | additive, new path under `/api/v1/web/...` |
| `POST /api/v1/web/officer/applications/{id}/claim` | n/a | new (200/401/403/404/409/412/422/428) | additive |
| `GET /api/v1/applications` (INIT-133A) | maps `ApplicationListForbiddenError` locally to 403 | delegates 403 mapping into `raise_known_application_error` helper | wire format identical (`403 application_list_forbidden`); proposal Step 2 requires unit test of helper before bridge lands |
| `GET /api/v1/applications/{id}` | unchanged | unchanged | none |
| `POST /api/v1/applications` | unchanged | unchanged | none |
| `POST /api/v1/applications/{id}/transitions` | unchanged | unchanged | none |
| `POST /api/v1/applications/{id}/messages` (INIT-131) | unchanged | unchanged | none |
| `GET /api/v1/applications/{id}/messages` (INIT-131) | unchanged | unchanged | none |
| `GET /api/v1/applications/{id}/transcript` (INIT-132) | unchanged | unchanged | none |
| `POST /api/v1/public/applications` | unchanged | unchanged | none — applicant submit POST stays inline in `ApplicationFormRoute.tsx`, hitting `/api/public/applications` |
| `GET /auth/discord/me` | unchanged (api host through Pomerium passthrough) | unchanged | none — applicant only |
| `GET /auth/discord/start` | unchanged | unchanged | none |
| `GET /auth/discord/callback` | unchanged | unchanged | none |

The `/api/v1/me` change is purely additive: `groups: list[str] = []` and
`discord_user_id: str | None = None` default in `CurrentPrincipalRead`.
The only test that fails is `test_web_identity.py::test_me_reads_pomerium_identity_headers`,
which uses exact `==` JSON equality and needs the two new keys; the proposal
identifies that test for update.

The browser uses `/api/me`, `/api/web/admin/chapters`,
`/api/web/officer/applications`, `/api/web/officer/applications/{id}/claim`,
and `/auth/discord/me`; nginx-web rewrites `/api/` → `/api/v1/` so these
reach the FastAPI routes `/api/v1/me`, `/api/v1/web/...`. Today the client at
`services/web/src/api/client.ts:39,43` calls `/api/v1/me` and
`/api/v1/web/admin/chapters`, which through the existing nginx-web
`/api/` → `/api/v1/` rewrite would become `/api/v1/v1/...`. Those calls
are currently exercised only through Playwright `page.route` mocks and
the live admin chapter route is not wired in production (no Pomerium
entry exists for `/api/v1/me` or `/api/v1/web/admin/chapters`). The
proposal swaps those literals to the proxy-correct `/api/me` and
`/api/web/admin/chapters` browser paths and adds a static negative grep
(`grep -rE "[\"']/api/v1/" services/web/src/`) so the SPA can never
re-introduce a path that breaks under the rewrite. This is a **fix**,
not a regression of a working surface.

### 2. Pomerium routing

| Path | Pre | Post | Risk |
|---|---|---|---|
| `https://web.local.humility.local/admin/...` | `prefix: /admin`, web service, auth-gated | unchanged ordering, still `prefix: /admin`, web service, auth-gated | none — proposal explicitly inserts `/api/me`, `/api/web/admin/`, `/api/web/officer/`, `/applications/queue`, and `/applications/queue/` BEFORE the existing `/admin` prefix |
| `https://web.local.humility.local/auth/discord/...` | `prefix: /auth/discord/`, **API** service, public-unauthenticated, `pass_identity_headers: false` | unchanged | none — applicant Discord OAuth path stays public and routes to API service; proposal adds nothing on `/auth/discord/*` |
| `https://web.local.humility.local/applications` | catches the public catch-all (allow_public_unauthenticated_access) | catches the public catch-all (the new `/applications/queue` exact-path entry does NOT match `/applications`) | LOW — proposal adds an explicit static test asserting `/applications` resolves to the catch-all and `/applications/queue-foo` does not match the exact-path or nested-prefix entries |
| `https://web.local.humility.local/applications/queue` | catches the public catch-all | new `path: /applications/queue`, web service, auth-gated, before catch-all | additive |
| `https://web.local.humility.local/applications/queue/...` | catches the public catch-all | new `prefix: /applications/queue/`, web service, auth-gated, before catch-all | additive |
| `https://web.local.humility.local/api/me` | catches the public catch-all (and resolves to nginx → API) | new `path: /api/me`, web service, auth-gated, before catch-all | additive — exact path prevents `/api/me-foo` and `/api/members/...` collisions |
| `https://web.local.humility.local/api/web/admin/...` | catches the public catch-all | new `prefix: /api/web/admin/`, web service, auth-gated, before catch-all | additive |
| `https://web.local.humility.local/api/web/officer/...` | catches the public catch-all | new `prefix: /api/web/officer/`, web service, auth-gated, before catch-all | additive |
| `https://web.local.humility.local/` (catch-all) | unchanged: web service, public | unchanged: web service, public; remains last for the host | none |
| `https://protected-api.local.humility.local/...` | unchanged | unchanged | none |

Existing `idp_scopes: openid email profile` is widened to add
`discord_user_id`; existing `jwt_claims_headers` (email, sub,
groups (already mapped as `x-pomerium-claim-groups: groups`), name)
is widened to add `x-pomerium-claim-discord-user-id: discord_user_id`.
Both changes are additive and proposal §3 demands the static test
set-compare the values exactly so a future drift fails the gate.

The existing static test `infra/tests/test_applicant_discord_pomerium.py`
has `_web_catch_all_index()` defined as "first web-service route without
a `prefix` key." The new `/api/me` and `/applications/queue` entries use
the `path:` key (not `prefix:`) and target the web service, so the
naive helper would now incorrectly return the index of `/api/me` as the
"catch-all." The proposal addresses this directly by rewriting
`test_applicant_discord_pomerium.py` to do path-based route resolution
in both directions and to assert exact `/api/me`, exact
`/applications/queue`, nested `/applications/queue/`, `/api/web/admin/`,
and `/api/web/officer/` precede the public catch-all and do not shadow
`/applications`. This is a planned test update for the new ordering, not
a regression of existing assertions.

### 3. Applicant Discord OAuth flow

`/auth/discord/start`, `/auth/discord/callback`, `/auth/discord/me`,
and the `applicant_receipt` cookie semantics remain entirely unchanged:

- Pomerium route `prefix: /auth/discord/` continues to target the API
  service, with `allow_public_unauthenticated_access: true` and
  `pass_identity_headers: false`. Proposal does not touch this entry.
- `applicant_receipt` cookie is still issued by the API after the
  Discord OAuth callback and consumed by `/auth/discord/me` and
  `/api/v1/public/applications`.
- `ApplicationFormRoute.tsx` (the migrated applicant route) still
  probes `/auth/discord/me`, runs the 9-minute re-probe timer, and
  redirects to `/auth/discord/start?return_to=/applications` on
  401 / `applicant_receipt_required`.
- The new SPA client hardly grows: only the applicant Discord identity
  probe stays in `client.ts`; the applicant submit POST stays inline in
  `ApplicationFormRoute.tsx`, preserving the existing
  `/api/public/applications` path with no `/v1/` literal.
- Officer routes do not call `/auth/discord/me`, do not read
  `applicant_receipt`, and the bridge’s server-side dependency tree
  test (`test_officer_endpoints_have_locked_actor_construction`) bans
  `verify_applicant_receipt` and any callable that reads
  `applicant_receipt` from request cookies.

The `compat.spec.ts` cases that depend on this flow
(`applicantDiscordTest`, `loggedInApplicantTest`,
`staleApplicantReceiptTest`) bind to selector ids
(`#application-form`, `#submit-status`, `#discord-login`,
`#discord-login-state`, `#tab-overview`, `#tab-details`, `#open-details`,
`#details-panel`, test ids `application-submit-icon`,
`application-status-icon`), the `/auth/discord/me` and
`/api/public/applications` paths via `page.route`, and the
`/auth/discord/start?return_to=/applications` URL. Proposal §3
"Applicant form DOM contract" enumerates each of these selectors and
the conditional rendering rules. The one **intentional tightening** is
that `#tab-overview`, `#tab-details`, and `#details-panel` are no
longer rendered in `checking` / `anonymous` auth states (the live
`main.tsx:109-130` template renders them unconditionally). The proposal
flags this as a defensible tightening and adds new assertions in
`compat.spec.ts` that those ids are absent in `checking` / `anonymous`
and present (with `[hidden]` on `#details-panel`) in `verified`. None
of the four existing `loggedInApplicantTest` / `applicantDiscordTest`
/ `staleApplicantReceiptTest` cases at `compat.spec.ts:202-291`
depends on the pre-verification tab markup, so they pass under the
tightened DOM contract.

### 4. Build pipeline (Containerfile.web, build-channel-image.sh)

`containers/server-manager/Containerfile.web` is unchanged: it still
runs `npm ci` then `npm run build` from `services/web`, copies
`dist/` into the nginx layer, and runs `nginxinc/nginx-unprivileged`
on port 8080. The Solid runtime swap (`main.tsx` mounting
`<AppProviders router={router} />` instead of vanilla DOM) does not
add a new build script, dist path, or nginx config requirement —
`npm run build` continues to invoke `vite build` and emit
`services/web/dist`. The TanStack Solid Router and `@tanstack/solid-query`
packages already exist in the tree (used by `app/router.tsx` and
`AdminChaptersRoute.tsx`); no new top-level toolchain dependency is
introduced. `services/web/index.html` already loads only
`/src/main.tsx`, so swapping `main.tsx`'s body keeps the existing
entry contract.

`containers/server-manager/Containerfile.api` is unchanged: it still
copies `services/api`, installs the package, and starts uvicorn on
the existing factory.

`infra/scripts/build-channel-image.sh` is unchanged: it still resolves
the channel registry, builds with `--file`/`--context` args, pushes,
and optionally `k3d image import`s. The proposal does not modify
build-arg shape, registry path, or tag conventions.

### 5. K3d image rollout / GitOps

- `validate_web_ui_local.sh` retains its current asserts (contract
  fixture, Playwright spec coverage, `npm run build`, image build,
  Pomerium-protected admin route check, public route check). The
  proposal adds a negative `grep -rE "[\"']/api/v1/" services/web/src/`,
  positive allowlists for `client.ts` paths, and a live `curl`
  against `https://web.local.humility.local/api/me` with simulated
  Pomerium identity headers. Existing `assert_contract_fixture`,
  `assert_playwright_contract_spec`, `assert_web_build`, and
  `assert_runtime` flows continue to pass.
- `infra/tests/e2e/run-fullstack.sh` is unchanged. The suite count stays
  at 19; no new `infra/tests/e2e/tests/NN-*.sh` is added.
- The new `init-133B-pomerium-officer-discord.yaml` Authentik blueprint
  ConfigMap data entry is additive: extends
  `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml`
  with a separate `pomerium` OAuth2 application/provider, a distinct
  `discord-pomerium` Discord OAuth source, and a
  `server-manager-pomerium-discord_user_id` scope mapping. The
  separation from the existing `discord-applicant` source is
  intentional (revocation independence). FluxCD reconciliation of the
  ConfigMap is unchanged — it is one new data entry alongside existing
  blueprint entries.
- Infisical secret store gains
  `DISCORD_OFFICER_OAUTH_CLIENT_ID` /
  `DISCORD_OFFICER_OAUTH_CLIENT_SECRET`, mirroring the existing
  `DISCORD_APPLICANT_OAUTH_*` pair. This requires an operator
  precondition (registering a second Discord developer application)
  before officer login can authenticate, but it does not break the
  applicant flow which uses the existing `DISCORD_APPLICANT_OAUTH_*`
  credentials.

### 6. e2e suite (test 19, contract.json)

Existing assertions in `infra/tests/e2e/tests/19-web-ui.sh`:

- `assert_public_submit_persisted` — preserved unchanged. It still reads
  `web-ui-public-submit.json` and asserts `applications.state='queued'`,
  `members.kind='discord'`, and the bootstrap-fixture
  `applicant-discord-user-id` matches.
- `run_validator validate-web-ui` — preserved (still calls
  `infra/tests/validate_web_ui_local.sh`).
- `run-browser-flow.sh web-ui` — preserved; only the inner
  `infra/tests/e2e/lib/playwright/browser-flow.mjs` gains an officer-queue
  step after the existing applicant submit.
- E2E_APPLICANT_RECEIPT_SIGNING_KEY / E2E_APPLICANT_DISCORD_USER_ID
  reads from `server-manager-e2e-fixtures` — preserved.
- `e2e_init "19-web-ui" "SPA public and authenticated admin UI"` —
  preserved; the suite count stays at 19, satisfying the required
  "extend test 19, do not add a new e2e number" rule.

Additions: a new `infra/tests/e2e/lib/seed-authority-grants.mjs`
helper (additive file, no existing seed at that path), an officer
queue claim navigation step in `browser-flow.mjs`, and a Postgres
assertion that `applications.owner_id != applications.applicant_id`,
`members.discord_user_id` for the resolved owner equals
`E2E_OFFICER_DISCORD_USER_ID` from the bootstrap fixture, and
`members.kind = 'discord'`.

`infra/tests/fixtures/web-ui/contract.json`:

- `auth.probe_endpoint` is already `/api/me` in the live fixture
  (`infra/tests/fixtures/web-ui/contract.json:33`). The proposal
  preserves it.
- All `routes.public`, `routes.application_form`, `routes.admin`,
  `auth.identity`, `auth.headers`, `auth.applicant`, `form.fields`,
  `form.submit.*`, and `ui_libraries.*` keys are unchanged. Tests
  consuming these — `compat.spec.ts` (loadContract), `validate_web_ui_local.sh`
  (`assert_contract_fixture` schema check) — keep working.
- New keys added: `routes.officer_queue`, `auth.officer`,
  `auth.headers.x-pomerium-claim-discord-user-id`,
  `applications.queue`, `applications.claim`. These are additive and
  the `assert_contract_fixture` node check at
  `validate_web_ui_local.sh:104-118` does not assert object shape
  exclusivity — it only asserts the existence of certain keys, so new
  keys do not break it.

### 7. Python module surface

| Symbol | Pre | Post |
|---|---|---|
| `app.contracts.web.CurrentPrincipalRead` | `subject, email, display_name, provider` | adds `groups: list[str] = []`, `discord_user_id: str \| None = None` |
| `app.api.v1.endpoints.me.get_pomerium_principal` | header parser, returns 4-field principal | adds version-tolerant `x-pomerium-claim-groups` parsing and `x-pomerium-claim-discord-user-id` parsing |
| `app.api.v1.endpoints.web.router` | exposes `GET /api/v1/web/admin/chapters` | adds `GET /api/v1/web/officer/applications` and `POST /api/v1/web/officer/applications/{application_id}/claim` |
| `app.services.members.resolve_or_create_real_discord_member` | `(db, *, discord_user_id) -> MemberRead` | `(db, *, discord_user_id, originating_actor: ActorIdentity = APPLICANT_RECEIPT_MEMBER_ACTOR, request_surface: str = "api:/api/v1/public/applications") -> MemberRead` (defaults preserve applicant path) |
| `app.api.v1.endpoints.applications._shared.raise_known_application_error` | maps existing app exceptions | adds `ApplicationListForbiddenError -> 403 application_list_forbidden` branch (mirrors today's local mapping in `lifecycle.py:106-110`) |
| `app.api.v1.endpoints.applications._shared` (module name) | `_shared.py` | proposal allows renaming the ETag/import surface to `etag.py` for non-private cross-package imports; if renamed, all in-tree imports of `parse_if_match_strong` are updated atomically; `raise_known_application_error` either moves with it or stays in `_shared.py` |
| `app.api.v1.endpoints.applications.lifecycle.list_applications_endpoint` | catches `ApplicationListForbiddenError` and `ValueError` locally | delegates `ApplicationListForbiddenError` through `raise_known_application_error`; `ValueError` mapping still local (validation_error mapping is in the helper too, so this could also delegate) |
| Existing `/api/v1/applications/*` endpoint signatures and dependency tree | unchanged | unchanged |
| Existing applicant-receipt service + dependency | unchanged | unchanged |

The bridge does NOT depend on
`app.core.dependencies.get_current_actor`,
`app.core.context.get_current_actor`, `verify_applicant_receipt`, or
any `CURRENT_ACTOR.get()` reader; the proposal’s
`test_officer_endpoints_have_locked_actor_construction` Python test
walks the FastAPI route dependency tree to enforce this server-side.
The bridge ignores `X-Actor-Kind` / `X-Actor-Id` request headers; the
proposal adds `test_officer_claim_ignores_x_actor_headers` to prove
attacker-supplied actor headers cannot influence ownership.

The `members.py` parameterization MUST thread the
`originating_actor` and `request_surface` through all three actor-
literal embedding sites in `services/api/app/services/members.py:200-256`
(the `_make_request(...)` call, the `action_payload` dict, and the
`StateChangeDraft.payload_json` dict). Missing any one site silently
attributes officer-bridge-triggered first-login member rows to the
applicant-receipt service. Proposal §3 and §6 step 7 call this out
explicitly and §7 adds
`web officer first login records member creation under web-officer-bridge actor`
to lock it.

### 8. Frontend module surface (delete check)

Cross-source references to deleted files:

- `services/web/src/RuntimeApp.tsx` — referenced ONLY by itself in
  `services/web/src/`. All other matches are documentation
  (`proposals/`, `research/`, `plans/BACKLOG.md`). It is not imported
  by `main.tsx`, `app/`, `features/`, or any test. Safe to delete.
- `services/web/src/features/forms/DarkNemesisForm.tsx` — imported by
  `services/web/src/features/public/HomeRoute.tsx:8`. The proposal
  rewrites `HomeRoute.tsx` to remove the demo preview behavior and
  drop the `DarkNemesisForm` import; once that change lands, no other
  in-tree consumer remains. Safe to delete.
- `services/web/src/features/forms/schema.ts` — imported by
  `services/web/src/RuntimeApp.tsx:8` and
  `services/web/src/features/forms/DarkNemesisForm.tsx:8-13`. Both
  importers are deleted by the proposal. Safe to delete.
- `services/web/src/features/forms/form.module.css` — imported by
  `DarkNemesisForm.tsx:15` only. Safe to delete with `DarkNemesisForm.tsx`.

`grep -rn` across `services/web/`, `services/api/`, `infra/`,
`gitops/`, `forms/`, and `containers/` shows no other references to
these four files outside the proposal/research/backlog markdown.
Deletion does not break any test or runtime consumer.

The `services/web/src/app/providers.tsx` `router: any` type tightening
is internal — `AppProviders` is currently unmounted, so there is no
external consumer to break. The proposal’s `main.tsx` rewrite is the
first real callsite.

### 9. Database schema

NONE. No migration is added or modified. The bridge calls existing
`list_applications(...)` and `transition_application(...)`, which
operate on the existing `applications` and `aggregate_heads` tables.
The members service signature change does not alter the `members`
table or its writes; it only relabels the `originating_actor_kind`,
`originating_actor_id`, and `request_surface` audit fields written
into `state_changes` / `activity_actions` for officer-triggered
first-login member rows. Verified.

### 10. Permission namespace

NONE. The bridge reuses the existing `application.review` and
`application.claim` permissions (existing repository functions enforce
authority). No new `application.*` or `member.*` permission name is
introduced. Proposal §8 anti-scope explicitly rules out new permission
names. The existing authority-grant endpoint is not touched.
Verified.

### 11. Authority grants

NONE issued by the slice itself. Proposal §6 step 8 requires an
operator to grant `application.review` (and `application.claim`) on
the resolved officer member UUID before queue access works; the slice
does NOT auto-grant. The new `seed-authority-grants.mjs` helper exists
solely for the e2e harness and runs a single idempotent psql
transaction inserting `application.review` + `application.claim` for
the resolved member UUID. It does not change runtime authority code,
the gRPC/HTTP authority API, or the existing
`infra/tests/e2e/lib/...` helper inventory beyond an additive file.
Verified.

## Verdict reasoning

LOW. Every supported surface is preserved:

1. **HTTP API**: `/api/v1/me` adds two fields with safe defaults;
   `/api/v1/applications/*` is untouched; `/api/v1/web/officer/*` is
   net-new; `/api/v1/public/applications` and `/auth/discord/*` are
   untouched. The `_shared.py` mapper migration of
   `ApplicationListForbiddenError` is wire-format-preserving and
   proposal Step 1 + a unit test prove it independently before the
   bridge consumes the mapper.
2. **Pomerium routing**: existing `/admin` prefix and `/auth/discord/`
   prefix are preserved; new exact-path and nested-prefix entries are
   inserted before the public catch-all in a way the new static tests
   pin in both directions. The catch-all still answers
   `/applications`. Existing route ordering invariants survive.
3. **Applicant Discord OAuth flow**: cookie semantics, probe endpoint,
   submit endpoint, redirect targets, and DOM selectors are all
   preserved. The one DOM tightening (no tabs/details panel before
   verified) is documented and locked with new compat assertions.
4. **Build pipeline / k3d / GitOps**: Containerfile.web,
   Containerfile.api, build-channel-image.sh, validate_web_ui_local.sh,
   run-fullstack.sh, and the FluxCD-reconciled blueprint configmap
   are extended additively. No build-arg, dist path, image tag, or
   nginx config change.
5. **e2e suite**: test 19 keeps its `assert_public_submit_persisted`
   coverage and only gains an officer-queue claim step after the
   existing applicant submit. Suite count stays at 19.
6. **Python and frontend module surfaces**: net-new exports plus
   defaulted parameter additions; deleted files
   (`RuntimeApp.tsx`, `DarkNemesisForm.tsx`, `schema.ts`,
   `form.module.css`) have no external in-tree references after the
   proposal’s `HomeRoute.tsx` rewrite.
7. **Database schema, permission namespace, authority grants**: zero
   change in all three.

The only gap-class breakages a 6c implementation must avoid are
already enforced by tests the proposal commits to: server-side
dependency-tree check banning applicant-receipt readers; static test
that all three `members.py:200-256` actor-literal sites are
parameterized; static Pomerium tests resolving routes in both
directions across collision classes; and a `compat.spec.ts` lock for
the tightened auth-state-conditional applicant DOM. With those
guarantees, every supported surface this slice touches stays
backward-compatible.

SUPPORTED_SURFACE_DONE: plans/risk/init-133B-i-supported-surface.md
