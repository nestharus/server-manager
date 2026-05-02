# INIT-139 problem map — live KIC translation smoke

## What's at risk

BL-014 pinned the static Kong/KIC inputs and the local GitOps manifests, but it still only proves that the committed YAML says the right thing. The harder failure mode is a future Kong Gateway or Kong Ingress Controller version that still accepts the manifests, renders a valid configuration, and serves traffic, but silently fails to attach the `public-intake-rate-limit` `KongPlugin` to the path-specific Kong Routes.

That would make the static tests pass while runtime public intake rate limiting disappears. The current manifest intent is:

- `server-manager/public-intake-rate-limit.yaml` defines `KongPlugin/public-intake-rate-limit` as `rate-limiting` with `minute: 5`, `hour: 50`, and `policy: local`, then annotates `Ingress/server-manager-public-intake-api` with `konghq.com/plugins: public-intake-rate-limit` for `api.local.humility.local` paths `/api/v1/public/applications` and `/api/v1/public/chapters`.
- `auth/pomerium/public-intake-rate-limit.yaml` annotates `Ingress/web-public-intake` with the same plugin for `web.local.humility.local` paths `/api/public/applications`, `/api/public/chapters`, and `/api/applications`.
- Adjacent catch-all Ingresses remain unannotated: `server-manager-api` on `api.local.humility.local /`, `web` on `web.local.humility.local /`, and `protected-api` on `protected-api.local.humility.local /`.

The runtime smoke must prove the controller translated the annotation into Kong Route-scoped plugin entities, not merely that Kubernetes accepted the CRD.

## Existing CI lanes

There are two relevant Buildkite lanes:

- `.buildkite/pipeline.yml` is the default lane. It runs `python -m pytest tests infra/tests`, service tests, web tests, and static validators such as `validate_application_workloads_local.sh --static-only`, `validate_auth_stack_local.sh --static-only`, and `validate_web_ui_local.sh --static-only`. BL-014's `infra/tests/test_public_intake_rate_limit.py` belongs here because it is a local/static contract test.
- `.buildkite/pipeline-cluster.yml` is the cluster-runtime lane. It checks Docker/k3d/kubectl, runs `infra/scripts/bring-up-local-channel.sh --channel local --force --cluster-only`, waits, then runs `pr-cluster-merge-readiness-runtime-validators` with `--cluster` validators under a 180 minute timeout.

The new validator belongs in `.buildkite/pipeline-cluster.yml`, not the default unit-test lane. It needs a live Kong data plane after KIC has reconciled the local GitOps resources.

The natural shape is a new `infra/tests/validate_public_intake_rate_limit_local.sh` following the existing validator contract:

- `set -euo pipefail`
- default `KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"`
- `--static-only` for any cheap local manifest preconditions, if useful
- `--cluster` to make runtime mode explicit
- `PASS:`/`ERROR:` or `PASS:`/`FAIL:` output consistent with the current shell validators
- no Discord-visible writes

The exact slot is the cluster runtime validator step after Kong, auth, and server-manager workloads are already available. If the cluster lane remains one monolithic command block, add it after the prerequisite runtime validators that prove Kong and the server-manager/Pomerium routes exist. If capacity argues for isolation, make it a sibling Buildkite step that depends on `humility-local-cluster-bringup` and the same workload readiness prerequisites, but keep it in `pipeline-cluster.yml`.

One thing the proposal must clarify: the current cluster lane calls bring-up with `--cluster-only`, which skips Flux post-install. The smoke cannot be meaningful against an empty k3d cluster. INIT-139 should either rely on a pre-existing cluster state that the lane already preserves in practice, or explicitly lock the bootstrap/reseed prerequisite before adding the validator.

## Smoke options

### Option A: Kong Admin API introspection

Kong exposes exactly the surface needed for a fast translation smoke:

- Kong's Admin API is the internal REST API for Gateway administration. The docs list default Admin API ports as HTTP `8001` and HTTPS `8444`, configurable by `admin_listen`: <https://developer.konghq.com/admin-api/>.
- Kong Routes match inbound requests and can have plugins attached. Kong's Route docs explicitly describe route-specific rate limiting for different paths and say a Route may have one or more plugins attached: <https://developer.konghq.com/gateway/entities/route/>.
- Kong's Plugin docs say scoped plugins can target Routes, Services, Consumers, and Consumer Groups, and a Route-scoped plugin only triggers when a request matches that Route's path: <https://developer.konghq.com/gateway/entities/plugin/>.
- KIC's annotation docs say `konghq.com/plugins` associates `KongPlugin` resources with an Ingress, and `konghq.com/tags` can assign custom tags to generated Kong Gateway entities: <https://developer.konghq.com/kubernetes-ingress-controller/reference/annotations/>.
- KIC's Ingress docs say an Ingress is translated directly into a Kong Route, and KIC filters resources by `ingressClassName`/ingress class: <https://developer.konghq.com/kubernetes-ingress-controller/ingress/>.
- The Kong Admin OpenAPI spec includes `GET /routes`, `GET /routes/{RouteIdOrName}`, `GET /plugins`, and `GET /routes/{RouteIdOrName}/plugins`. The Plugin schema includes `name`, `enabled`, `config`, and `route`; the JSON Route schema includes `hosts`, `paths`, `methods`, `service`, and `tags`.

For this repo's rendered Kong chart, the Admin API is not exposed as a normal cluster Service. The rendered pod sets `KONG_ADMIN_LISTEN` to `127.0.0.1:8444 ... ssl`, and the ingress controller uses `CONTROLLER_KONG_ADMIN_URL=https://localhost:8444` with TLS skip verify. The validator should therefore use a temporary `kubectl port-forward` to the Kong deployment or pod and curl `https://127.0.0.1:<local-port>` with `-k`, then clean up the port-forward in a trap.

The introspection assertion should avoid generated route-name assumptions. Use route attributes:

Expected positive routes:

- host `api.local.humility.local`, path `/api/v1/public/applications`
- host `api.local.humility.local`, path `/api/v1/public/chapters`
- host `web.local.humility.local`, path `/api/public/applications`
- host `web.local.humility.local`, path `/api/public/chapters`
- host `web.local.humility.local`, path `/api/applications`

Expected negative/adjacent routes:

- host `api.local.humility.local`, path `/`
- host `web.local.humility.local`, path `/`
- host `protected-api.local.humility.local`, path `/`

For each expected positive route:

1. Find exactly one Kong Route in `/routes` whose `hosts` contains the host and whose `paths` contains the exact path.
2. Query `/routes/<route-id>/plugins`.
3. Assert at least one enabled plugin has `name == "rate-limiting"` and config includes `minute == 5`, `hour == 50`, `policy == "local"`, `fault_tolerant == true`, and `hide_client_headers == false`.

For each adjacent route:

1. Find the route by host/path.
2. Query `/routes/<route-id>/plugins`.
3. Assert no enabled `rate-limiting` plugin with the public-intake config is attached.

This catches the BL-014 silent-drop scenario directly: if KIC drops the Ingress annotation during translation, the routes still exist and the manifests still pass static tests, but `/routes/<id>/plugins` is empty or missing the expected rate-limiting plugin.

### Option B: proxy behavior burst test

The behavior smoke would hit the proxy through the already-mapped k3d load balancer ports:

- Rapid-fire `https://web.local.humility.local/api/public/applications` or `https://api.local.humility.local/api/v1/public/applications` until the configured burst threshold returns `429`.
- Rapid-fire an adjacent authenticated/admin path, for example `https://api.local.humility.local/api/v1/web/admin/chapters`, and assert it does not return `429` from the public-intake rate limiter.

This proves end-to-end behavior instead of only translated config, but it is less deterministic:

- Public submit endpoints may require valid payload shape and can fail before the rate limiter in ways that obscure the signal.
- Pomerium/authenticated paths may redirect, reject, or require cookies; "not 429" is easy to assert, but the request path may not exercise the intended upstream behavior.
- Kong's `policy: local` counter state is per gateway instance and can leak between tests unless the path, client identity, or gateway state is controlled.
- The configured limit is `minute: 5`, so the positive test needs six or more requests and must distinguish Kong `429` from application-level failures.

Behavior burst is valuable as a later confidence layer, but it is not the smallest CI test for INIT-139.

### Option C: hybrid

Hybrid means:

1. Admin API introspection first, as the fast precondition.
2. A small burst against one public route only, if and only if the route binding exists.
3. One adjacent path burst or repeated check that does not return Kong `429`.

This gives the best end-to-end story, but it is more likely to exceed the desired CI budget and produce flaky failures when auth, app readiness, or rate-limit state changes. It is better as a follow-up after the fast introspection smoke is stable.

## What the proposal must lock

- Validator location: add a cluster-runtime validator under `infra/tests/`, wired from `.buildkite/pipeline-cluster.yml`, not from `.buildkite/pipeline.yml`.
- Bootstrap prerequisite: define whether the cluster lane has a reconciled local GitOps stack despite `--cluster-only`; if not, add the minimum bootstrap/reseed step before runtime validators.
- Access method: use `kubectl port-forward` to the Kong pod/deployment Admin API on HTTPS `8444` with `-k`, because the rendered Admin API listens on pod-local loopback.
- Route identity: select Kong Routes by `hosts` and `paths`, not generated route names.
- Positive route set: the five public-intake paths listed above.
- Negative route set: at least the API catch-all route for `/api/v1/web/admin/chapters` coverage, plus the web and protected catch-alls if present.
- Plugin identity: assert `name == "rate-limiting"` and the public-intake config, not Kubernetes CR name alone. The Admin API plugin entity's `name` is the Kong plugin type.
- Timing budget: wait only for Kong deployment availability and route visibility; do not create proof pods for this smoke. Existing validators already cover DNS/curl patterns.
- Failure output: print the discovered routes/plugins compactly enough to debug missing binding without dumping the whole Admin API payload.
- No behavior-only implementation for INIT-139. Behavior burst can be documented as a later extension, but the core failure mode is translated association and Admin API introspection is the direct signal.

## Diff budget

Small.

Expected files:

- Add `infra/tests/validate_public_intake_rate_limit_local.sh`.
- Update `.buildkite/pipeline-cluster.yml` to call it in the runtime validator lane.
- Optionally add a tiny fixture or embedded expected route table if the shell script stays readable.
- Do not modify application code, Kubernetes manifests, or BL-014 static tests unless hookpoint research finds an existing validator that should absorb this instead of adding a new script.

The smallest, fastest CI test is Option A only: port-forward Kong Admin API, list routes, assert five public-intake routes have the enabled `rate-limiting` plugin with the expected config, and assert adjacent catch-all routes do not. It should run in well under 30 seconds after the cluster is already reconciled; most time should be route-visibility polling, not request volume.

PROBLEM_MAP_DONE: research/50-init-139-kic-smoke-problem-map.md
