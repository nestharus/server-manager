# INIT-118 Proposal: Web UI Substrate

Stand up the first product-surface SPA for Humility. The output is a local
k3d-deployed, Pomerium-fronted static SPA that covers one public route and one
auth-gated admin route. INIT-118 is substrate only: it proves framework,
toolchain, auth boundary, token flow, containerization, GitOps, and harness.

## Scope

- Add `services/web` as the first frontend package.
- Pin Solid 2 beta, Vite, TanStack adapters, Ark UI Solid, FontAwesome SVG
  Core, Oxlint, Oxfmt, tsgo, and Playwright.
- Add `/api/v1/me` and `/api/v1/web/admin/chapters` as the minimum API surface
  for auth identity and admin list rendering.
- Deploy the SPA under `gitops/channels/local/applications/web`.
- Add Pomerium routes for `https://web.local.humility.local`, public root, and
  auth-gated `/admin`.
- Add non-cluster and optional cluster harness checks.

## File Surface

- `services/web/**`
- `containers/server-manager/Containerfile.web`
- `containers/server-manager/nginx-web.conf`
- `infra/tests/validate_web_ui_local.sh`
- `infra/tests/test_web_ui_contract.py`
- `services/api/app/api/v1/endpoints/{me,web}.py`
- `services/api/app/contracts/web.py`
- `services/api/app/{repositories,services}/web.py`
- `gitops/channels/local/applications/web/**`
- `gitops/channels/local/auth/pomerium/{ingress,secrets-infisicalsecret}.yaml`
- `.buildkite/pipeline.yml`
- `product-strategy/tickets/PHASE_5_INDEX.md`

## Schema Additions

No database schema changes. API DTOs are read models only:

- `CurrentPrincipalRead`
- `AdminChapterSummaryRead`
- `AdminChapterListRead`

## Slices

### SLICE-118.01 Toolchain Pins

Add package and cluster-toolchain pins. `install-cluster-tools.sh` records Node,
npm, Solid, Vite, Oxfmt, Oxlint, tsgo, and Playwright versions.

### SLICE-118.02 Web Skeleton

Add `services/web` with package metadata, tsconfig, Vite config, Oxlint config,
Oxfmt config, npmrc template, package lock, and base CSS layers.

### SLICE-118.03 TanStack Wiring

Pin and wire Router, Query, Form, Store, Table, Virtual, and devtools. Because
Solid 2 beta has shifted exports, compatibility files are release-gated.

### SLICE-118.04 Ark UI Primitives

Add Ark UI primitive wrappers and CSS Modules for Button, Input, Dialog, Select,
Combobox, and Tabs.

### SLICE-118.05 Gap Components

Add Meter, Toolbar, and Breadcrumb components. Toolbar has a Playwright roving
tabindex check.

### SLICE-118.06 FontAwesome Integration

Add FontAwesome SVG Core wrapper, npmrc generation script, and Playwright token
bootstrap entrypoint. No token material is committed.

### SLICE-118.07 Forms

Render `forms/dark-nemesis.yaml` into the public application surface and validate
payload shape with Zod.

### SLICE-118.08 Auth Integration

Add `/api/v1/me`, sample admin chapter list endpoint, Pomerium identity header
handling, public route, and admin route.

### SLICE-118.09 GitOps + CI

Add web container, Buildkite static step, web image build step, raw manifests,
Service, Deployment, NetworkPolicy, and Pomerium ingress.

### SLICE-118.10 End-to-End Harness

Add `infra/tests/validate_web_ui_local.sh` and contract tests. Static mode
proves package pins, build, Kustomize render, Pomerium routes, and no committed
token material. Runtime mode proves Pod Ready and route behavior.

## Local-As-First Deployment Proof

Local proof is not a screenshot. It is the combination of package build,
Playwright compatibility tests, API tests, Kustomize render, and optional k3d
runtime checks against `web.local.humility.local`.

## Risk Track

- Solid 2 beta adapter churn: LOW with explicit compatibility files and tests.
- Auth leakage: LOW because no OIDC exists in the SPA.
- Token leakage: LOW because `.npmrc` generation is scripted and checked.
- Scope creep: LOW because complete admin/applicant workflows are named
  handoff items.

## Anti-Scope

- No full admin console.
- No complete applicant submission or review workflow.
- No role matrix, waitlist, or officer workflow UI.
- No WebAwesome.
- No Tailwind, Panda, or CSS-in-JS.
- No helm-controller or HelmRelease.
- No SPA-side OIDC.
