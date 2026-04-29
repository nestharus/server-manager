# INIT-133B-i — Supported-surface risk gate

**Verdict:** MEDIUM

The proposal is overwhelmingly additive and preserves every external
contract that other slices depend on, but one already-merged API test
(`services/api/tests/test_web_identity.py`) is broken by the additive
change to `CurrentPrincipalRead.groups` because it does exact-shape
equality on the `/api/v1/me` JSON. The proposal must list that test
in its "Modified files" / "Tests" section so the implementer updates
the expected payload alongside the schema. With that single addition
the verdict drops to LOW.

## Surfaces touched

### 1. HTTP API

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `GET /api/v1/me` | `{subject,email,display_name,provider}` | adds `groups: list[str]` (default `[]`) | additive on the wire; **breaks `test_web_identity.test_me_reads_pomerium_identity_headers`** which compares JSON by exact equality (`services/api/tests/test_web_identity.py:37-42`) |
| `GET /api/v1/web/admin/chapters` | unchanged | unchanged | none — endpoint code untouched; only the SPA-side URL is corrected from `/api/v1/web/admin/chapters` to `/api/web/admin/chapters` so it survives the nginx `/api/` → `/api/v1/` rewrite (`containers/server-manager/nginx-web.conf:8-20`). The existing endpoint behavior and `test_web_admin_chapters_requires_identity` remain valid because the test calls the API directly without nginx (`services/api/tests/test_web_identity.py:54-69`). |
| `GET /api/v1/web/officer/applications` | n/a | new (200 / 401 / 403 / 422 / 5xx) | additive; mounted under existing `web.router` prefix `/api/v1/web` (`services/api/app/api/v1/endpoints/web.py:11`) |
| `POST /api/v1/web/officer/applications/{id}/claim` | n/a | new (200 / 401 / 403 / 404 / 409 / 412 / 422) | additive; bridge to existing `transition_application` with synthesized `ActorIdentity` |
| `POST /api/v1/applications` | unchanged | unchanged | none |
| `GET /api/v1/applications` | unchanged | unchanged | none |
| `GET /api/v1/applications/{id}` | unchanged | unchanged | none |
| `POST /api/v1/applications/{id}/transitions` | unchanged | unchanged | none — proposal calls existing service from inside the bridge with a server-built `ActorIdentity(actor_kind="user", actor_id=<member uuid>)`, no browser-supplied actor headers (`services/api/app/api/v1/endpoints/applications/lifecycle.py:91-93,140-142`) |
| `POST /api/v1/applications/{id}/messages`, `GET /api/v1/applications/{id}/transcript` | unchanged | unchanged | none — these stay reserved for INIT-133B-ii / 133B-iii |
| `GET /auth/discord/me`, `GET /auth/discord/start`, `GET /auth/discord/callback` | unchanged | unchanged | none |
| `POST /api/public/applications` | unchanged | unchanged | none — the public submit path Q1 expects `compat.spec.ts` to keep proving |

**Route ordering** under the existing `web.py` router is safe. The
new `/officer/applications` (`@router.get("/officer/applications")`)
does not collide with the existing `@router.get("/admin/chapters")`
because both have full literal prefixes; FastAPI registration order
is irrelevant here. Route ordering inside `lifecycle.py` (the empty
`@router.get("")` / `@router.get("/{application_id}")` distinction
flagged in the INIT-133A gate) is **not** retouched by this slice.

### 2. Pomerium routing

Existing routes (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:47-68`)
in registration order:

1. `web.local.humility.local` prefix `/admin` → web (auth required, identity headers)
2. `web.local.humility.local` prefix `/auth/discord/` → API (public, no identity headers)
3. `web.local.humility.local` (no prefix, catch-all) → web (public)
4. `protected-api.local.humility.local` (no prefix) → API (auth required)

| Path | Pre | Post | Risk |
|---|---|---|---|
| `/admin/*` | protected → web | unchanged | none |
| `/auth/discord/*` | public → API, `pass_identity_headers: false` | unchanged | none — `test_applicant_discord_pomerium` invariants (single `/auth/discord/` route, public, identity stripped, precedes catch-all) are preserved (`infra/tests/test_applicant_discord_pomerium.py:58-80`) |
| `/applications` (applicant form SPA route) | falls through to public catch-all | unchanged | none — proposal protects only the more specific `/applications/queue` prefix; Pomerium prefix matching is most-specific so `/applications` keeps falling into the catch-all |
| `/applications/queue` | catch-all (public) | new explicit prefix → web with auth required, identity headers | additive; must be inserted **before** the catch-all and **after** `/admin` to preserve the existing test ordering invariants |
| `/api/web/officer/*` | catch-all (public) | new explicit prefix → web with auth required, identity headers | additive; same ordering rule. Pomerium → web → nginx `/api/` rewrite → `/api/v1/web/officer/...` |
| `/api/web/admin/chapters` | catch-all (public, identity headers default off) | unchanged at the Pomerium layer | none. The proposal does not protect this route at the Pomerium layer; the AdminChapters call from the protected `/admin/chapters` SPA already relies on the SPA being loaded under Pomerium identity — no behavioral change is introduced. |
| `protected-api.local.humility.local` catch-all | unchanged | unchanged | none |

The existing `test_applicant_discord_pomerium._web_catch_all_index`
locates the catch-all by "no `prefix` key on a `web` route" — adding
new `prefix:`-bearing routes keeps this filter unique. The
proposal's `infra/tests/test_applicant_discord_pomerium.py` edit to
also assert `/applications/queue` and `/api/web/officer/` precede the
catch-all is consistent with the existing helpers.

### 3. Applicant Discord OAuth flow

`/auth/discord/start`, `/auth/discord/callback`, `/auth/discord/me`,
and the `applicant_receipt` cookie semantics
(`services/api/app/api/v1/endpoints/auth_discord.py:13-105`) are
**not** modified. The proposal only consumes them:

- The applicant form route (`/applications`) keeps probing
  `/auth/discord/me`, redirecting to
  `/auth/discord/start?return_to=/applications`, and submitting to
  `/api/public/applications` — the exact behavior asserted by
  `compat.spec.ts:202-292` and by the e2e applicant submit step
  (`infra/tests/e2e/lib/playwright/browser-flow.mjs:47-129`).
- The new web-officer bridge re-uses
  `verify_applicant_receipt`/`verify_applicant_receipt_jwt`
  (`services/api/app/services/applicant_discord_auth.py:168-236`)
  and `resolve_or_create_real_discord_member`
  (`services/api/app/services/members.py:192`) read-side. The cookie
  format, signing key, TTL, secure/HttpOnly/SameSite flags, and
  `applicant_receipt_required` error code are reused without
  modification. The e2e cookie injector (`browser-flow.mjs:47-68`)
  continues to work for the new queue navigation step.

### 4. Build pipeline (Containerfile.web, build-channel-image.sh)

No changes proposed to `containers/server-manager/Containerfile.web`,
`Containerfile.api`, `nginx-web.conf`, or `build-channel-image.sh`.
The Solid runtime swap is purely an in-source change — `npm run
build` still runs Vite, still emits `services/web/dist`, and the
multi-stage image still copies `dist` into the unprivileged nginx
image (`Containerfile.web:18-24`). The Vite alias-based Solid 2
shim in `services/web/vite.config.ts:11-26` is untouched. The
Containerfile.api is untouched; the new web-officer endpoints ship
with the existing `pip install /app/services/api` step.

### 5. K3d image rollout / GitOps

Unchanged. `validate_web_ui_local.sh` still uses
`build-channel-image.sh --app server-manager-web --tag init-118-local`
and `kubectl rollout status deployment/server-manager-web`
(`infra/tests/validate_web_ui_local.sh:159-172`). The proposal's
edits to `validate_web_ui_local.sh` are limited to additional static
assertions for the new spec/fixture (paragraph 3, "Scope/Modified
files"), so the existing pass=N counter, image build, deployment
ready check, public route 200, and admin route auth-gate steps still
run. No k3d image-import or registry-prefix change.

### 6. e2e suite (test 19, contract.json)

`infra/tests/e2e/tests/19-web-ui.sh` is the only e2e file modified.
The proposal explicitly preserves:

- `assert_public_submit_persisted` (`19-web-ui.sh:8-37`) — queries
  Postgres for `state='queued'`, real Discord member, non-synthetic
  user.
- `run_validator validate-web-ui ...` (`19-web-ui.sh:50`).
- `run-browser-flow.sh web-ui ...` (`19-web-ui.sh:51`) — the
  existing applicant submit Playwright flow.
- The fixtures Secret reads (`19-web-ui.sh:39-48`).
- Suite size stays at 19; `run-fullstack.sh` iterates
  `infra/tests/e2e/tests/*.sh` (`run-fullstack.sh:154`) so a new file
  is not introduced.

The added queue/claim assertions in `browser-flow.mjs` and
`19-web-ui.sh` come **after** the existing applicant proof, so a
regression in the new code cannot mask a regression in the
applicant flow.

`infra/tests/fixtures/web-ui/contract.json` adds new top-level keys
(`routes.officer_queue`, `auth.officer`, `applications.queue`,
`applications.claim`). All existing keys consumed by `compat.spec.ts`
and `validate_web_ui_local.sh` (`routes.public`, `routes.admin`,
`routes.application_form`, `auth.probe_endpoint`,
`auth.unauthenticated_api_status`, `form.*`, `ui_libraries.*`) are
preserved. `validate_web_ui_local.sh:100-119` invariants are still
satisfied.

`compat.spec.ts` is preserved verbatim except for the unavoidable
adjustments to keep its applicant-receipt and submit assertions
working under Solid Router. The proposal explicitly forbids stripping
its UI-library / FontAwesome / TanStack assertions
(Q7, anti-scope §8).

### 7. Python module surface

| Symbol | Pre | Post |
|---|---|---|
| `app.contracts.web.CurrentPrincipalRead.groups` | n/a | `list[str] = []` (additive) |
| `app.contracts.web.AdminChapterListRead`, `AdminChapterSummaryRead` | exported | unchanged |
| `app.api.v1.endpoints.me.get_pomerium_principal` | exported | unchanged signature; gains a parse for `x-pomerium-claim-groups` (additive in body, no signature change) |
| `app.api.v1.endpoints.me.me` | exported | unchanged signature |
| `app.api.v1.endpoints.web.admin_chapters` | exported | unchanged |
| `app.api.v1.endpoints.web.<officer list>` | n/a | new |
| `app.api.v1.endpoints.web.<officer claim>` | n/a | new |
| `app.services.applicant_discord_auth.verify_applicant_receipt(_jwt)` | exported | unchanged |
| `app.services.members.resolve_or_create_real_discord_member` | exported | unchanged |
| `app.services.applications.list_applications` (INIT-133A) | exported | unchanged |
| `app.services.applications.transition_application` | exported | unchanged |
| `app.contracts.applications.{ApplicationRead, ApplicationListRead, ApplicationTransitionRequest, ApplicationState}` | exported | unchanged |

No deletions. No signature changes. No relocations. The web-officer
bridge composes existing services rather than wrapping or
re-implementing them, so INIT-133B-ii/iii can layer on without
collision.

### 8. Frontend module surface (delete check)

Repository-wide grep for the four files marked for deletion shows the
only references are inside the deletion set itself or inside files
the proposal is rewriting:

- `services/web/src/RuntimeApp.tsx` — defined and self-imports
  `@/features/forms/schema`. **No external import** (no `from
  "./RuntimeApp"` or `from "@/RuntimeApp"` anywhere in `src/`,
  `tests/`, `infra/`). Already an unmounted parallel runtime. Safe
  to delete.
- `services/web/src/features/forms/DarkNemesisForm.tsx` — imported by
  `services/web/src/features/public/HomeRoute.tsx:8`, which the
  proposal explicitly replaces with a Solid mirror of the live
  applicant form (Modified files: `HomeRoute.tsx`). The deletion is
  safe **only if** the new `HomeRoute.tsx` lands in the same change.
- `services/web/src/features/forms/schema.ts` — imported by
  `RuntimeApp.tsx:8` and `DarkNemesisForm.tsx`. With both deleted,
  no other reference exists. Safe.
- `services/web/src/features/forms/form.module.css` — imported only
  by `DarkNemesisForm.tsx`. Safe.

No Playwright spec, e2e script, fixture, infra test, or backend file
references any of these names.

### 9. Database schema

Confirmed **no change**. Q8 anti-scope and section 11 ("Hookpoint
Preview → Leave alone") explicitly forbid schema migration. The
queue list and claim are pure SELECT plus the existing
`transition_application` write path, which already exists.

### 10. Permission namespace

Confirmed **no change**. The bridge calls into the existing
`transition_application` with `action="claim"`, which the application
service maps to the existing `application.claim` permission
(`services/api/app/services/applications.py:266-273,348-362`).
Anti-scope §8 forbids new permission names.

### 11. Authority grants

Confirmed **no change**. No `POST /api/v1/authority-grants` schema or
seed data is touched. The web-officer bridge cannot grant authority;
it only consumes the result of authority decisions enforced by the
existing application service.

## Verdict reasoning

Every protected surface this proposal can break is held intact: the
applicant Discord OAuth flow is consumed read-only, Pomerium gains
two additive prefixed routes that respect the existing `/admin` and
`/auth/discord/` ordering invariants asserted by
`test_applicant_discord_pomerium`, the build pipeline and k3d image
rollout are untouched, the e2e suite stays at 19 with the existing
applicant assertions intact, and there is no schema, permission, or
authority-grant change. The web-officer bridge composes existing
services rather than mutating them, and the deleted frontend files
are self-contained once the proposal's `HomeRoute.tsx` rewrite lands
in the same change. The only real defect is that adding `groups:
list[str] = []` to `CurrentPrincipalRead` will break
`test_web_identity.test_me_reads_pomerium_identity_headers`, which
asserts JSON equality without `groups`. That is a one-line test
update, but the proposal does not currently list
`services/api/tests/test_web_identity.py` in its Modified-files /
Tests sections. The proposal should be revised to add that file to
the "Modified files" list and to call out that the expected payload
must include `"groups": [...]` (or `[]` for the no-claim case),
otherwise the existing test will turn red on first run. With that
addition the supported-surface verdict is LOW.

SUPPORTED_SURFACE_DONE: plans/risk/init-133B-i-supported-surface.md
