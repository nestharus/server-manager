# INIT-118 Phase 2 Synthesis

## D-FRAMEWORK

Use Solid 2 beta as the application runtime. The pinned package is
`solid-js@2.0.0-beta.8`, paired with `@solidjs/web@2.0.0-beta.8` because the beta
has moved browser rendering out of the `solid-js/web` export used by Solid 1
ecosystem packages.

Decision: accept the beta and add a release gate. The gate must render the real
SPA locally and catch breakage from Solid 2 adapter churn.

## D-BUILD

Use Vite with `vite@8.0.10` and `vite-plugin-solid@3.0.0-next.5`. The web
package lives in `services/web` and builds to static files served by an
unprivileged nginx container.

Decision: no server-side rendering in INIT-118.

## D-ROUTER

TanStack Router Solid adapter is pinned as the selected router. Route contracts
are public `/` and auth-gated `/admin/chapters`.

Decision: INIT-118 keeps route count minimal; successor initiatives add route
depth.

## D-DATA

TanStack Query Solid adapter is pinned for server state. API reads use relative
`/api` paths so Pomerium and same-origin deployment remain the default.

Decision: query cache policy is conservative; stale time is short and no
optimistic mutation model is introduced.

## D-FORMS

TanStack Form is pinned with Standard Schema validation through Zod 4. The
initial renderer consumes `forms/dark-nemesis.yaml`.

Decision: INIT-118 proves schema rendering and local payload preview, not the
full applicant submission workflow.

## D-STATE

TanStack Store is pinned for non-server UI state. Theme and navigation state are
the intended first use.

Decision: do not introduce a second state library.

## D-TABLES

TanStack Table and TanStack Virtual are pinned for admin-grade list surfaces.
The sample admin table is intentionally small but wired to the future table
shape.

Decision: full chapter management interactions are INIT-119+.

## D-PRIMITIVES

Ark UI Solid is the headless primitive choice. Current explicit Solid 2 support
is not complete, so INIT-118 records the compatibility adapter and release-gate
test instead of assuming transitive readiness.

Decision: keep Ark UI as primary, WebAwesome out.

## D-STYLING

Styling is vanilla CSS with CSS Modules and cascade layers:
`reset`, `tokens`, `theme`, `base`, `components`, `utilities`, `overrides`.
Tokens use primitive, semantic, and component tiers with OKLCH source colors.

Decision: no Tailwind, Panda, CSS-in-JS, or styling DSL.

## D-ICONS

FontAwesome Pro+ is represented through `@fortawesome/fontawesome-svg-core` and
a thin Solid-compatible wrapper. Token retrieval is operational tooling, not
runtime code.

Decision: no committed token-bearing `.npmrc`.

## D-GAP-COMPONENTS

Meter uses native `<meter>`. Toolbar follows the WAI-ARIA roving tabindex
pattern. Breadcrumbs are route-driven by the router contract.

Decision: these remain hand-rolled until Ark UI ships equivalent Solid 2-safe
coverage or a future proposal replaces them.

## D-TOOLCHAIN

Oxlint owns lint. Oxfmt owns formatting, with Prettier available as a fallback
lane if Oxfmt beta blocks CI. Type-checking uses `tsgo` from
`@typescript/native-preview`, with `tsc` fallback.

Decision: CI runs explicit static validation plus package-local checks.

## D-AUTH

Pomerium fronts the SPA. The SPA contains no OIDC client, token storage, or
login callback code. The API exposes `/api/v1/me` from verified Pomerium
identity headers.

Decision: public routes are open; admin routes are Pomerium-gated.

## D-CREDENTIAL-FLOW

Build-time npm credentials are `FA_NPM_TOKEN` and `WA_NPM_TOKEN`, sourced from
Infisical project `platform-frontend` or environment fallback in dev. The build
writes `.npmrc` at start and deletes it after install.

Decision: developer dashboard automation is Playwright-only and stays out of
the cluster image.

## D-LOCAL-CONTRACT

The local proof is a real SPA reconciliation: package build, compatibility
tests, raw manifest render, Pod Ready, public route `200`, and admin route auth
redirect before login.

Decision: runtime cluster proof is part of the harness but may be skipped when
no local cluster is active.

## D-INIT-119+-HANDOFF

Out of scope: admin console completeness, full applicant submission, applicant
review flow, role matrix UI, waitlist views, officer dashboards, tenant-specific
navigation, and production UX polish.
