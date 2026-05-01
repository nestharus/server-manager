# BL-014 problem map — Kong path-specific KongPlugin binding

## What's at risk

BL-014 is about the assumption behind INIT-120 AS-5: Kong can attach the
`public-intake-rate-limit` plugin to only the public intake route resources,
without throttling the rest of `web.local.humility.local` or the authenticated
API catch-all. The current manifests implement that by creating separate
Ingress resources with only the public paths and annotating those Ingresses
with `konghq.com/plugins: public-intake-rate-limit`.

The risk is not "does YAML contain the annotation?" Current static tests
already check that. The risk is "does the deployed KIC version still translate
that annotation into Kong route/plugin associations for only those paths?"
If a future Kong chart, Kong Gateway image, or KIC image changes that
translation behavior, the public write surface could remain reachable while
losing the intended abuse-control boundary.

The blast radius is the public intake family:

- Direct API host: `api.local.humility.local` paths under
  `/api/v1/public/applications` and `/api/v1/public/chapters`
  (`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:33-50`).
- Web host: `web.local.humility.local` paths under
  `/api/public/applications`, `/api/public/chapters`, and the legacy
  `/api/applications`
  (`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml:20-44`).
- Upload URL inherits from Prefix matching rather than a separate YAML entry:
  `services/web/src/api/client.ts` calls `/api/public/applications/upload-url`,
  and `services/api/app/api/v1/endpoints/applications/public_uploads.py`
  mounts `/upload-url` under `/api/v1/public/applications`. The existing
  `/api/public/applications` and `/api/v1/public/applications` Prefix paths
  are therefore the route-level rate-limit dependency for upload-url.

## Existing pin + binding patterns

Kong-version-touching surfaces today:

| Surface | Current value | Evidence |
|---|---:|---|
| Helm chart render command | `kong/kong --version 3.2.0` | `gitops/channels/local/ingress/kong/README.md:10-15` |
| Rendered manifest filename | `rendered/kong-3.2.0.yaml` | `gitops/channels/local/ingress/kong/kustomization.yaml:7` |
| Rendered Helm chart label | `helm.sh/chart: kong-3.2.0` | `gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml:4072` |
| Kong Gateway image value | `kong:3.9` | `gitops/channels/local/ingress/kong/render-values.yaml:13-16`; rendered at `.../kong-3.2.0.yaml:4087`, `4259` |
| KIC image value | `kong/kubernetes-ingress-controller:3.5` | `gitops/channels/local/ingress/kong/render-values.yaml:45-49`; rendered at `.../kong-3.2.0.yaml:4221` |
| KIC controller mode | `CONTROLLER_INGRESS_CLASS=kong`; admin URL `https://localhost:8444` | `gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml:4210-4221` |
| Kong mode | DB-less, traditional router | `gitops/channels/local/ingress/kong/render-values.yaml:8-10`; rendered `KONG_DATABASE=off` at `.../kong-3.2.0.yaml:4128-4129` and `KONG_ROUTER_FLAVOR=traditional` at `.../kong-3.2.0.yaml:4154-4155` |
| CRD bundle version annotation | `kubernetes-configuration.konghq.com/version: v1.5.2` | `gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml:1690-1694` for `KongPlugin` |
| Kong admission webhook | disabled | `gitops/channels/local/ingress/kong/render-values.yaml:52-53`; README notes no chart-generated webhook TLS keys are committed |
| Static public-intake test | no Kong/KIC version pin | `infra/tests/test_public_intake_rate_limit.py:71-136` checks plugin config and annotated paths only |

Important naming wrinkle: the backlog says "Current Kong 3.2.0 + KIC". In the
repo, `3.2.0` is the Helm chart version, not the Gateway image. The rendered
Gateway image is `kong:3.9`, and the KIC image is
`kong/kubernetes-ingress-controller:3.5`. BL-014 should lock and test all three
surfaces separately.

Current binding pattern:

- One namespaced `KongPlugin` named `public-intake-rate-limit` in namespace
  `server-manager`, configured as Kong `rate-limiting` with `minute: 5`,
  `hour: 50`, `policy: local`, `fault_tolerant: true`, and
  `hide_client_headers: false`
  (`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:1-12`).
- A direct API Ingress named `server-manager-public-intake-api` in namespace
  `server-manager`, `ingressClassName: kong`, annotated with
  `konghq.com/plugins: public-intake-rate-limit`, with Prefix paths
  `/api/v1/public/applications` and `/api/v1/public/chapters`
  (`.../server-manager/public-intake-rate-limit.yaml:14-50`).
- A web/Pomerium Ingress named `web-public-intake` in namespace `auth-system`,
  `ingressClassName: kong`, annotated with the same plugin name, with Prefix
  paths `/api/public/applications`, `/api/public/chapters`, and
  `/api/applications`
  (`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml:1-44`).
- Catch-all Ingress resources remain unannotated. The existing static test
  asserts the `web`, `protected-api`, and authenticated `server-manager-api`
  catch-alls do not carry the plugin annotation
  (`infra/tests/test_public_intake_rate_limit.py:118-136`).

The web-side namespace shape deserves explicit validation in the eventual
proposal. The only `KongPlugin` resource found by the current static test is in
`server-manager` (`infra/tests/test_public_intake_rate_limit.py:75-85`), while
the web annotated Ingress is in `auth-system`. A live KIC smoke should prove
that the deployed controller resolves the web-side annotation as intended, or
the proposal should change the manifest pattern instead of assuming static YAML
coverage is enough.

## Failure scenarios

1. Chart/image bump changes KIC annotation support silently.
   The Ingress still applies, the application remains reachable, and static CI
   still sees `konghq.com/plugins`. KIC no longer attaches the plugin to the
   generated route, so `/api/public/applications`, upload-url, or
   `/api/v1/public/applications` lose route-level throttling at runtime.

2. KIC changes plugin binding granularity from route/path to service/Ingress.
   This is noiseless from Kubernetes' perspective. The plugin may be absent on
   the intended route, or it may attach too broadly and throttle the catch-all
   web/API routes. The first case is a silent abuse-control miss; the second is
   user-visible collateral damage.

3. KIC route merge or path precedence changes.
   Because the protected routes and the rate-limited public routes are
   separate Ingress resources on the same hosts, a controller change in route
   de-duplication, path sorting, or Prefix handling could route traffic through
   a catch-all that lacks the plugin. Static manifest checks would still pass.

4. KongPlugin CRD or rate-limiting schema changes noisily.
   If the CRD version, `plugin`, or `config` schema rejects the manifest, CI can
   catch it with server-side apply or kustomize/apply validation. This is the
   easier failure mode because Kubernetes rejects or marks the resource invalid.

5. Admission-webhook-specific validation is absent.
   The local chart intentionally disables the Kong admission webhook. Any test
   option that depends on the webhook would require enabling a different
   deployment shape than local currently uses. That can be useful as an
   additional compatibility signal, but it is not the smallest local-faithful
   guard.

6. Upload URL falls outside the Prefix route after a path rule change.
   No explicit `/api/public/applications/upload-url` or
   `/api/v1/public/applications/upload-url` path exists in GitOps today. The
   endpoint is protected only because it is a strict child of the existing
   Prefix path. If a future proposal changes pathType, host routing, or the
   upload endpoint path, the inherited rate-limit protection can disappear.

## Test design options

Static YAML check:

- Extend `infra/tests/test_public_intake_rate_limit.py` to lock all
  version-touching surfaces: Helm chart `3.2.0`, Gateway image `kong:3.9`,
  KIC image `kong/kubernetes-ingress-controller:3.5`, rendered file reference,
  and admission webhook disabled.
- Add explicit assertions that upload-url is covered by a Prefix parent, not
  by accident: `/api/public/applications/upload-url` must start with an
  annotated Prefix path, and same for `/api/v1/public/applications/upload-url`.
- Value: cheap and always-on.
- Limit: does not prove KIC still attaches the plugin to generated Kong routes.
  It catches accidental local manifest drift, not BL-014's controller-version
  compatibility risk.

Kustomize plus Kubernetes server-side apply:

- In CI, render the local Kong and public-intake manifests and run
  `kubectl apply --dry-run=server` against an ephemeral cluster with the
  rendered CRDs installed.
- Value: catches noisy CRD/API incompatibility from chart or CRD changes.
- Limit: still does not prove KIC route/plugin translation, especially because
  the local admission webhook is disabled.

Live KIC translation smoke:

- Start an ephemeral local cluster in CI with the candidate Kong chart/render.
- Apply only the Kong stack, the `public-intake-rate-limit` plugin/Ingress
  resources, and tiny dummy Services/Pods for the backends. This avoids needing
  Postgres, Pomerium, or server-manager application state.
- Wait for KIC to reconcile.
- Prove either through Kong Admin API route/plugin inspection from inside the
  Kong pod, or by curl behavior through the proxy:
  - intended public paths have a `rate-limiting` plugin association or return
    `429` after the configured burst;
  - adjacent catch-all paths on the same hosts are still routed but are not
    associated with the public-intake plugin.
- Value: catches the silent failure mode BL-014 is about.
- Limit: more expensive than static checks and requires a small fixture
  cluster lane.

Admission-webhook smoke:

- Run a separate compatibility lane with Kong admission webhook enabled and
  submit the plugin/Ingress resources.
- Value: can catch future controller-side validation errors earlier.
- Limit: local intentionally disables the webhook, so this is not faithful to
  the deployed local channel and will not catch route/plugin translation by
  itself.

Smallest test that catches the BL-014 risk:

The smallest meaningful guard is a live KIC translation smoke that boots the
candidate Kong/KIC render, applies minimal dummy backends plus the two
public-intake Ingress resources, and asserts generated Kong state or proxy
behavior for both positive and adjacent-negative paths. Static YAML and
server-side apply should be retained as fast prechecks, but neither catches a
future KIC that accepts the manifests while dropping path-specific plugin
binding.

## What the proposal must lock

- Treat Helm chart version, Gateway image tag, KIC image tag, and CRD bundle as
  separate compatibility inputs. Do not describe chart `3.2.0` as the Kong
  Gateway runtime version.
- Lock the exact supported route set:
  `/api/v1/public/applications`, `/api/v1/public/chapters`,
  `/api/public/applications`, `/api/public/chapters`, legacy
  `/api/applications`, and upload-url as a child of the application Prefix
  path.
- Lock the non-goal: do not rate-limit web static assets, `/auth/discord/*`,
  protected API catch-alls, or authenticated API catch-alls with the public
  intake budget.
- Require any Kong chart, Gateway image, KIC image, CRD render, or route
  topology change to run the live KIC translation smoke before merge.
- Resolve or explicitly preserve the current namespace pattern for the web
  Ingress annotation. The proposal must not rely only on the static fact that
  a plugin named `public-intake-rate-limit` exists somewhere in local GitOps.
- Preserve the no-backwards-compatibility rule: if the binding pattern changes,
  update all public-intake manifests and tests to the new pattern instead of
  carrying dual old/new binding paths.

## Diff budget

Research-only phase: this file only.

Expected future proposal/implementation budget:

- One focused static test addition or update in
  `infra/tests/test_public_intake_rate_limit.py` for version pins, upload-url
  Prefix coverage, and manifest namespace expectations.
- One small live validation script or CI lane under `infra/tests/` that deploys
  a minimal Kong/KIC fixture and proves route/plugin attachment behavior.
- Optional fixture YAML for dummy backends if the live smoke chooses proxy
  behavior over Admin API inspection.
- No service code, database migrations, Pomerium policy changes, Discord
  changes, or public API contract changes should be needed for BL-014.

PROBLEM_MAP_DONE: research/44-bl-014-kong-version-problem-map.md
