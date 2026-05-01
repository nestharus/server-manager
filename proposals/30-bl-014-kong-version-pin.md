# Proposal 30 - BL-014: Kong version pin static guard

## 1. Problem statement

BL-014 protects the assumption behind INIT-120 AS-5: Kong can bind the
`public-intake-rate-limit` plugin only to the public intake route resources,
without throttling the rest of `web.local.humility.local` or the authenticated
API catch-all. The current local manifests implement that by creating separate
Ingress resources that contain only public intake paths and annotating those
Ingresses with `konghq.com/plugins: public-intake-rate-limit`.

The at-risk behavior is broader than "does YAML contain an annotation?" The
important risk is that a future Kong Helm chart, Kong Gateway image, or KIC
image change alters how the controller translates that annotation into Kong
route/plugin associations. The public write surface could remain reachable
while silently losing the intended abuse-control boundary.

The blast radius is the public intake family:

- Direct API host `api.local.humility.local`, under
  `/api/v1/public/applications` and `/api/v1/public/chapters`.
- Web host `web.local.humility.local`, under `/api/public/applications`,
  `/api/public/chapters`, and legacy `/api/applications`.
- Upload URL paths:
  `/api/v1/public/applications/upload-url` and
  `/api/public/applications/upload-url`, which are currently protected by
  Prefix matching on the public application paths rather than by separate YAML
  path entries.

Failure scenarios this slice must make visible at static-review time:

- chart or image version drift changes the controller compatibility input
  without updating the explicit test expectation;
- the binding pattern drifts away from per-Ingress
  `konghq.com/plugins` annotation on public-only Ingress resources;
- route topology drifts so beta-1 chapter paths or beta-3 upload-url coverage
  are no longer represented in the supported public intake set;
- adjacent protected surfaces such as `/api/v1/web/`, `/auth/discord`,
  `/api/v1/health`, web static assets, or authenticated catch-alls get swept
  into the public-intake plugin budget.

This is a static-only regression guard. It catches local manifest drift and
forces intentional review of Kong/KIC version changes. It does not prove live
KIC route/plugin translation behavior.

## 2. Decisions

### Q1. Guard shape

Lock: implement a static YAML-only guard for this slice.

The problem map identifies live KIC translation smoke as the smallest test
that catches the deepest BL-014 runtime risk, but that lane has higher CI cost
and requires an ephemeral Kong/KIC fixture. For this BL-014 slice, keep the
always-on regression test static and defer live translation smoke to a separate
follow-up when CI capacity surfaces.

The static guard must be explicit about its limit: it verifies pinned versions,
manifest shape, public route coverage, and adjacent-negative paths. It must not
claim to prove that the deployed KIC still attaches the plugin to generated
Kong routes.

### Q2. Test location

Lock: extend `infra/tests/test_public_intake_rate_limit.py`.

That file already owns the public-intake KongPlugin static guard, including the
rate-limit config, annotated Ingress paths, and unannotated catch-all
assertions. Extending it keeps the BL-014 checks near the existing risk
annotation and avoids a second test file that would parse the same GitOps
resources for the same public-intake boundary.

Do not add `infra/tests/test_kong_version_pin.py` in this slice unless the
implementation finds that the existing file becomes materially harder to read.
The preferred implementation is still one cohesive public-intake rate-limit
guard file.

### Q3. Surfaces to lock

Lock the Kong version-touching surfaces as separate compatibility inputs:

- Helm chart version `3.2.0`.
- Rendered manifest reference `rendered/kong-3.2.0.yaml`.
- Rendered chart label `helm.sh/chart: kong-3.2.0`.
- Kong Gateway image tag `kong:3.9`.
- KIC image tag `kong/kubernetes-ingress-controller:3.5`.

In this worktree these files live under
`gitops/channels/local/ingress/kong/`, not
`gitops/channels/local/cluster-services/kong/`. The test should target the
actual local channel layout:

- `gitops/channels/local/ingress/kong/README.md`;
- `gitops/channels/local/ingress/kong/kustomization.yaml`;
- `gitops/channels/local/ingress/kong/render-values.yaml`;
- `gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml`.

Lock the public-intake binding pattern:

- `server-manager-public-intake-api` remains an Ingress in namespace
  `server-manager` with `ingressClassName: kong` and annotation
  `konghq.com/plugins: public-intake-rate-limit`;
- `web-public-intake` remains an Ingress in namespace `auth-system` with
  `ingressClassName: kong` and annotation
  `konghq.com/plugins: public-intake-rate-limit`;
- both annotated Ingresses use path-specific `Prefix` paths, not a host-wide
  catch-all;
- the public-intake KongPlugin remains named `public-intake-rate-limit` and is
  still the plugin referenced by those annotations.

Lock the supported route set:

- Direct API side:
  `/api/v1/public/applications`,
  `/api/v1/public/chapters`,
  `/api/v1/public/applications/upload-url`.
- Pomerium/web side:
  `/api/public/applications`,
  `/api/public/chapters`,
  `/api/public/applications/upload-url`,
  legacy `/api/applications`.

The upload-url paths are supported routes covered by annotated Prefix parents.
The test should assert both facts: the literal annotated YAML paths remain the
public application/chapter paths that exist today, and each upload-url route is
covered by the corresponding annotated `Prefix` application path.

Lock the adjacent anti-list as excluded from annotated public-intake Ingresses:

- `/api/v1/web/`;
- `/auth/discord`;
- `/api/v1/health`;
- `/`;
- any protected or authenticated API catch-all path already represented by the
  local GitOps manifests.

## 3. Substrate

### Modified files

- `infra/tests/test_public_intake_rate_limit.py`
  - Add static assertions for the Kong Helm chart version, rendered manifest
    reference, Gateway image tag, and KIC image tag.
  - Extend the existing annotated-path check to assert the full public-intake
    supported route set, including beta-1 chapters and beta-3 upload-url
    coverage through Prefix parents.
  - Add negative assertions that anti-list paths are not present on
    public-intake-plugin annotated Ingress resources.
  - Keep the existing plugin config and catch-all unannotated checks.

### Unmodified substrate

- No production API, Discord daemon, web, repository, service, or migration
  changes.
- No GitOps manifest changes. This proposal locks the current local manifests;
  it does not modify Kong, KIC, Pomerium, or server-manager YAML.
- No CI cluster, live KIC fixture, or admission-webhook lane in this slice.

## 4. Test plan

### TG-1: version pins stay explicit

Run:

```bash
pytest infra/tests/test_public_intake_rate_limit.py
```

Acceptance:

- pytest reads each version-touching Kong file under
  `gitops/channels/local/ingress/kong/`;
- the Helm chart render command/reference remains `3.2.0`;
- the kustomization still references `rendered/kong-3.2.0.yaml`;
- the rendered chart label remains `helm.sh/chart: kong-3.2.0`;
- the Gateway image remains `kong:3.9`;
- the KIC image remains `kong/kubernetes-ingress-controller:3.5`.

Any chart, Gateway, or KIC version change must fail this test until the
proposal/test expectation is intentionally updated.

### TG-2: public-intake route set stays covered

Run the same pytest file.

Acceptance:

- pytest reads
  `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`
  and `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`;
- both public-intake Ingresses use per-Ingress
  `konghq.com/plugins: public-intake-rate-limit`;
- annotated literal `Prefix` paths include:
  `/api/v1/public/applications`, `/api/v1/public/chapters`,
  `/api/public/applications`, `/api/public/chapters`, and legacy
  `/api/applications`;
- supported upload-url routes are proven by Prefix coverage:
  `/api/v1/public/applications/upload-url` is under annotated
  `/api/v1/public/applications`, and
  `/api/public/applications/upload-url` is under annotated
  `/api/public/applications`.

### TG-3: adjacent protected paths stay excluded

Run the same pytest file.

Acceptance:

- annotated public-intake Ingresses do not include `/api/v1/web/`,
  `/auth/discord`, `/api/v1/health`, `/`, or other catch-all paths;
- the existing catch-all Ingress resources for `web`, `protected-api`, and
  authenticated `server-manager-api` remain unannotated with
  `public-intake-rate-limit`;
- failures name the offending host/path and source manifest so drift is easy
  to correct.

## 5. Anti-scope

Do not add live KIC translation smoke in this slice. The follow-up live lane
should boot a minimal Kong/KIC fixture and prove actual generated route/plugin
association or proxy behavior for positive and adjacent-negative paths.

Do not add an admission-webhook compatibility lane. The local Kong chart
currently disables the webhook, and webhook validation is a separate signal
from route/plugin translation.

Do not modify Kong manifests, Pomerium manifests, server-manager manifests, or
rendered Helm output. This is a regression test proposal for the current GitOps
shape.

Do not introduce compatibility shims, alternate binding patterns, feature
flags, or dual support for old/new KongPlugin attachment styles. If a future
Kong/KIC change requires a different binding pattern, update all relevant
manifests and tests cleanly in that future proposal.

## 6. Diff budget

Expected implementation size: one confined test-layer change.

Budget:

- `infra/tests/test_public_intake_rate_limit.py`: add small helpers if needed
  for reading Kong version files and comparing annotated Prefix coverage; keep
  total churn under roughly 80 lines.
- No new test file unless extending the existing guard becomes materially less
  readable.
- No production code.
- No GitOps manifest changes.
- No documentation update required beyond this proposal.

PROPOSAL_DONE: proposals/30-bl-014-kong-version-pin.md
