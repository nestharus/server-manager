# Proposal 34 - INIT-139: Kong KIC translation smoke

## 1. Problem statement

BL-014 pinned the static Kong/KIC inputs and the local GitOps manifests, but
it still only proves that the committed YAML says the right thing. The harder
failure mode is a future Kong Gateway or Kong Ingress Controller version that
still accepts the manifests, renders a valid configuration, and serves
traffic, but silently fails to attach the `public-intake-rate-limit`
`KongPlugin` to the path-specific Kong Routes.

That would make the static tests pass while runtime public intake rate
limiting disappears. The current manifest intent is:

- `server-manager/public-intake-rate-limit.yaml` defines
  `KongPlugin/public-intake-rate-limit` as `rate-limiting` with `minute: 5`,
  `hour: 50`, and `policy: local`, then annotates
  `Ingress/server-manager-public-intake-api` with
  `konghq.com/plugins: public-intake-rate-limit` for
  `api.local.humility.local` paths `/api/v1/public/applications` and
  `/api/v1/public/chapters`.
- `auth/pomerium/public-intake-rate-limit.yaml` annotates
  `Ingress/web-public-intake` with the same plugin for
  `web.local.humility.local` paths `/api/public/applications`,
  `/api/public/chapters`, and `/api/applications`.
- Adjacent catch-all Ingresses remain unannotated: `server-manager-api` on
  `api.local.humility.local /`, `web` on
  `web.local.humility.local /`, and `protected-api` on
  `protected-api.local.humility.local /`.

The runtime smoke must prove the controller translated the annotation into
Kong Route-scoped plugin entities, not merely that Kubernetes accepted the CRD.

## 2. Decisions

### Q1. Smoke mechanism

Lock: use Admin API introspection, Option A from the problem map.

Kong's Admin API is the direct runtime surface for Gateway entities. The
official docs describe it as the internal REST API for administration and list
HTTPS `8444` as the default Admin API port. Kong's Route documentation says
Routes can have plugins attached and calls out route-specific rate limiting as
a supported use case. KIC's Ingress documentation says an `Ingress` is
translated directly into a Kong Route, and KIC annotation docs define
`konghq.com/plugins` as the annotation that runs plugins for a specific
Ingress.

Sources:

- <https://developer.konghq.com/admin-api/>
- <https://developer.konghq.com/gateway/entities/route/>
- <https://developer.konghq.com/gateway/entities/plugin/>
- <https://developer.konghq.com/kubernetes-ingress-controller/ingress/>
- <https://developer.konghq.com/kubernetes-ingress-controller/reference/annotations/>

### Q2. Validator location

Lock: add `infra/tests/validate_kong_kic_translation_local.sh`.

The script follows the local validator pattern already used by
`infra/tests/validate_*_local.sh`:

- `set -euo pipefail`;
- default `KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"`;
- support `--cluster`, `--kubeconfig PATH`, and `--help`;
- require `kubectl`, `curl`, and `jq`;
- print `PASS:` lines for successful assertions and `ERROR:` or `FAIL:` for
  blocking failures.

This validator is runtime-only. It does not add another static manifest check
for BL-014.

### Q3. Admin API access method

Lock: access Kong's Admin API through a temporary port-forward. The canonical
command shape is:

```bash
kubectl port-forward deploy/kong-kong -n kong 8444:8444 &
curl --fail --silent --show-error --insecure https://localhost:8444/routes
```

The implementation may thread `--kubeconfig "$KUBECONFIG_PATH"` through the
`kubectl` invocation, but the target resource, namespace, and port mapping
remain `deploy/kong-kong -n kong 8444:8444`.

Use `--insecure` because the Admin API listener uses self-signed local TLS.
The implementation must clean up the port-forward process in a `trap`.

The current local rendered Kong manifests show the release under
`kong-system`; the INIT-139 contract intentionally locks the command above.
Hookpoint research or implementation must reconcile that namespace detail
before code lands. It must not use the mismatch as a reason to switch to proxy
burst behavior.

### Q4. Route discovery

Lock: discover routes through paginated `GET /routes`.

The validator must not use generated route names. It must identify routes by
route attributes:

- `hosts` contains the expected host;
- `paths` contains the expected path for public-intake positives;
- for adjacent negatives, the selected Kong Route is the route whose
  host/path combination would handle the adjacent request path.

Expected public-intake routes:

- `api.local.humility.local` + `/api/v1/public/applications`;
- `api.local.humility.local` + `/api/v1/public/chapters`;
- `web.local.humility.local` + `/api/public/applications`;
- `web.local.humility.local` + `/api/public/chapters`;
- `web.local.humility.local` + `/api/applications`.

Pagination must follow Kong's response shape until there is no next page
before asserting missing or duplicate routes.

### Q5. Plugin discovery

Lock: for each selected route, call `GET /routes/<route_id>/plugins`.

For every public-intake route, assert that the returned plugin list contains
an enabled plugin with `name == "rate-limiting"`. The assertion is against the
Kong plugin type, not the Kubernetes `KongPlugin` CR name.

The validator may also print the discovered config values for debugging, but
the mandatory binding assertion for this slice is the route-scoped
`rate-limiting` plugin presence.

### Q6. Anti-list assertions

Lock: assert that adjacent non-public routes do not have route-scoped
`rate-limiting`.

At minimum, cover the authenticated/admin adjacent request path
`api.local.humility.local` + `/api/v1/web/admin/chapters`. Because the current
manifest topology represents that request through the authenticated API
catch-all route, the validator should resolve the matching Kong Route by host
and route path, then assert `GET /routes/<route_id>/plugins` does not include
`rate-limiting`.

Additional negative route checks are allowed if the route is present:

- `web.local.humility.local` + `/`;
- `protected-api.local.humility.local` + `/`.

Do not treat a missing optional adjacent route as a pass for the required
admin-path negative. The required negative must resolve to exactly one route
or fail with route-listing diagnostics.

### Q7. Failure output

Lock: failures must print a compact route/plugin listing.

On route lookup or plugin assertion failure, the validator should print one
line per relevant route with:

- route id;
- hosts;
- paths;
- plugin names from `GET /routes/<route_id>/plugins`.

The output must be compact enough for Buildkite logs and specific enough that
a missing binding is identifiable without dumping the whole Admin API payload.

### Q8. Behavior burst scope

Lock: behavior burst testing is out of scope for this slice.

Do not send request bursts through the proxy to force `429`, and do not use
proxy behavior as the primary assertion. A behavior burst can be proposed as a
separate confidence layer after this introspection smoke is stable.

## 3. Substrate

### New file

- `infra/tests/validate_kong_kic_translation_local.sh`
  - Parses validator arguments.
  - Waits for Kong deployment availability.
  - Port-forwards Admin API HTTPS `8444`.
  - Reads all Kong Routes through paginated `GET /routes`.
  - Selects routes by `hosts` and `paths`.
  - Reads route-scoped plugins through `GET /routes/<route_id>/plugins`.
  - Asserts the positive and negative public-intake binding contract.
  - Prints compact diagnostics on failure.

### Modified file

- `.buildkite/pipeline-cluster.yml`
  - Add the new validator to the
    `pr-cluster-merge-readiness-runtime-validators` command block.
  - Place it after Kong, TLS/DNS, auth/server-manager, or existing readiness
    validators have made the live route state meaningful.
  - Keep it in the cluster-runtime lane, not `.buildkite/pipeline.yml`.

### Test-only guard files

TG-2 and TG-3 may modify existing pytest guard files under `infra/tests/` to
protect the validator and Buildkite wiring from silent removal. Those test
files are not runtime substrate.

## 4. Test plan

### TG-1: validator passes against humility-local

Run:

```bash
infra/tests/validate_kong_kic_translation_local.sh --cluster
```

Acceptance:

- the script reaches Kong Admin API through the `8444` port-forward;
- all five public-intake host/path routes are found through `GET /routes`;
- every public-intake route has a route-scoped enabled `rate-limiting` plugin;
- the required adjacent admin path
  `api.local.humility.local/api/v1/web/admin/chapters` resolves to its route
  and has no route-scoped `rate-limiting` plugin;
- failures print compact route id, host, path, and plugin-name diagnostics.

### TG-2: pytest guard protects validator assertions

Run:

```bash
pytest infra/tests
```

Acceptance:

- pytest reads `infra/tests/validate_kong_kic_translation_local.sh`;
- the guard asserts the script contains the expected public-intake route set;
- the guard asserts the script checks `GET /routes`;
- the guard asserts the script checks `GET /routes/<route_id>/plugins`;
- the guard asserts the script searches for `rate-limiting`;
- the guard asserts the script contains the adjacent
  `/api/v1/web/admin/chapters` negative.

This catches accidental deletion, broadening, or replacement with a weaker
static-only validator.

### TG-3: Buildkite cluster lane includes validator

Run:

```bash
pytest infra/tests
```

Acceptance:

- pytest loads `.buildkite/pipeline-cluster.yml` with `yaml.safe_load`;
- the cluster runtime validator step command includes
  `infra/tests/validate_kong_kic_translation_local.sh --cluster`;
- the assertion fails if the validator is only present in comments, only in
  `.buildkite/pipeline.yml`, or missing from the PR cluster runtime lane.

## 5. Anti-scope

- Behavior burst test. That is a separate slice if needed.
- Ephemeral kind or k3d fixture cluster. Use the existing `humility-local`
  cluster lane.
- Modifying Kong manifests, KIC manifests, Pomerium manifests, or
  server-manager Ingress manifests.
- Changing the BL-014 static pins in
  `infra/tests/test_public_intake_rate_limit.py`.
- Adding compatibility shims, feature flags, dual route-binding support, or
  alternate old/new plugin attachment behavior.
- Any Discord-visible mutation.

## 6. Diff budget

Small.

Expected implementation budget:

- one new shell validator, roughly 150-250 lines depending on how route
  pagination and diagnostics are factored;
- one `.buildkite/pipeline-cluster.yml` command-line addition;
- one small pytest guard for validator contents;
- one small pytest guard for Buildkite wiring, preferably extending an
  existing Buildkite pipeline test if one already owns cluster-lane assertions.

No application code, API contracts, migrations, generated TypeScript, web
code, Discord daemon code, or Kubernetes manifest changes are in budget.

PROPOSAL_DONE: proposals/34-init-139-kong-kic-smoke.md
