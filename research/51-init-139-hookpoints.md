# INIT-139 — Hookpoints (Kong KIC translation smoke)

Source proposal: `proposals/34-init-139-kong-kic-smoke.md`.
Source problem map: `research/50-init-139-kic-smoke-problem-map.md`.
Source risk gates: `plans/risk/init-139-{audit,scope,shortcut,supported-surface}.md`.

INIT-139 ships exactly three substrate hooks plus two test-only
guard hooks:

1. `infra/tests/validate_kong_kic_translation_local.sh` (NEW shell
   validator).
2. `.buildkite/pipeline-cluster.yml` (one appended command-line in
   the existing `pr-cluster-merge-readiness-runtime-validators`
   step — TG-3 guard substrate).
3. The two pytest guards (TG-2 validator-contents guard and TG-3
   Buildkite-wiring guard) — extending an existing pytest file
   under `infra/tests/` rather than authoring a new one when the
   diff budget allows.

The hookpoints below are H-numbered. Each H is anchored to one or
more concrete files that the implementer must touch (or
deliberately not touch). Findings F1 (HIGH, namespace) and F2
(MEDIUM, plugin-endpoint pagination) from the audit gate are
folded directly into H2 and H3 respectively, so the implementer
cannot land code without reconciling them.

---

## H1 — Validator script structure

**File:** `infra/tests/validate_kong_kic_translation_local.sh` (NEW).

**Anchor pattern:** the existing `infra/tests/validate_*_local.sh`
family. The closest structural prior art is
`infra/tests/validate_object_storage_local.sh` (port-forward +
`trap` cleanup + `--cluster` mode) and
`infra/tests/validate_kong_ingress_local.sh` (Kong-namespace
discovery + `pass`/`fail`/`die`/`finish` helpers).

The validator must adopt these structural elements **in this order**:

### H1.1 — Header and shell discipline

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
```

These three are non-negotiable: every sibling validator opens
identically. Match the line shape so the shell-style sniff
(`set -euo pipefail` first, then constants) is preserved.

### H1.2 — Argument parsing

Required flags:

- `--cluster` — sets `CLUSTER_MODE=1`. Required by the
  Buildkite cluster lane (TG-3 asserts the literal `--cluster`
  appears next to the validator path).
- `--kubeconfig PATH` — overrides the default
  `KUBECONFIG_PATH`. Same semantics as
  `validate_object_storage_local.sh` lines 83–87 and
  `validate_kong_ingress_local.sh` lines 104–108.
- `-h` / `--help` — prints usage and exits 0.

**Anti-flag (forbidden):** do not implement `--static-only` (the
proposal Q2 line 72 explicitly bars a second BL-014 static layer)
and do not implement `--skip-negative` or any flag that lets the
mandatory adjacency check be turned off (shortcut gate C4).

The argument loop must `die "unknown argument: $1"` on
unrecognized flags so a future PR cannot silently smuggle a
weakening flag past the guard.

### H1.3 — Result helpers

Adopt the helper shape from
`validate_kong_ingress_local.sh:55-78`:

- `pass "<msg>"` — prints `PASS:` and increments `PASS_COUNT`.
- `fail "<msg>"` — prints `FAIL:` to stderr and increments
  `FAIL_COUNT`.
- `die "<msg>"` — prints `FAIL:` and `RESULT: pass=… fail=… skip=…`,
  then `exit 1`.
- `finish` — prints the final `RESULT:` summary line.

This keeps Buildkite log grep parity with the rest of the
validator family. The shortcut gate C5 + audit gate F4 require the
script to actually emit `PASS:`/`FAIL:` literals (not merely
contain comments saying it does), so these helpers must be invoked
on each assertion path.

### H1.4 — Tool requirements

```bash
command -v kubectl >/dev/null 2>&1 || die "kubectl is required"
command -v curl   >/dev/null 2>&1 || die "curl is required"
command -v jq     >/dev/null 2>&1 || die "jq is required"
```

These three are the only new tool requirements (proposal §4 + the
problem map's "no new dependencies" gate). Do not introduce
`yq`, `python` (Python is already present elsewhere but not
needed here — `jq` is the supported JSON tool), `httpie`, or any
other binary.

### H1.5 — Port-forward lifecycle and `trap` cleanup

Anchor: `validate_object_storage_local.sh:47-52` (`stop_port_forward`),
`:65-71` (`cleanup`), and `:73` (`trap cleanup EXIT`).

The validator must:

1. Pick a local port that does not collide with the lane's other
   port-forwards. The cluster lane currently uses `19000` for
   MinIO (`validate_object_storage_local.sh:8`); pick a different
   free port for Kong's Admin API. Recommend `18444` (suffixes
   match the upstream `8444` for log readability and the `1` prefix
   matches the existing `19000` convention).
2. Start the port-forward in the background, capturing
   `$!` into `PORT_FORWARD_PID`, with stdout+stderr redirected to
   a log file under `${REPO_ROOT}/.tmp/` (mirror the MinIO
   validator's `start_port_forward` shape at lines 184-206).
3. Poll the Admin API's `/status` endpoint
   (`https://127.0.0.1:${PORT}/status`) with `curl -k -fsS` until
   it returns 200 or a budgeted retry count is exhausted; on
   timeout, `die` and dump the port-forward log path so Buildkite
   logs point at the failure.
4. Register `trap cleanup EXIT INT TERM` so the port-forward is
   reaped on success, on assertion failure, and on Buildkite
   SIGTERM at timeout (audit gate A5).

**Forbidden shapes** (audit gate A5 + shortcut gate C1):

- `kill %1` at the script tail without a `trap` (leaks on
  failure paths).
- `trap` registered after the background `kubectl port-forward`
  is already running but before `PORT_FORWARD_PID` is captured
  (race window where the trap reads an empty PID and silently
  no-ops).
- `wait` without a guard against `kubectl port-forward` having
  already exited; use `kill -0 "$PORT_FORWARD_PID"` first as
  `validate_object_storage_local.sh:48` does.

### H1.6 — `curl` invocation against the Admin API

Locked shape (proposal Q3):

```bash
curl --fail --silent --show-error --insecure \
     "https://127.0.0.1:${PORT}/<endpoint>"
```

- `--insecure` matches the rendered chart's self-signed local
  TLS (audit gate A1; the rendered Kong listener at
  `gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml`
  binds `KONG_ADMIN_LISTEN: 127.0.0.1:8444 ssl` and KIC itself
  consumes it with TLS skip-verify via
  `CONTROLLER_KONG_ADMIN_URL`).
- `--fail` is mandatory so Kong 4xx/5xx responses cause a
  non-zero exit instead of silently returning the error
  payload as the response body (a curl-without-`--fail`
  regression is a classic green-light shortcut).
- `--silent --show-error` keeps Buildkite logs quiet on success
  but loud on failure.

### H1.7 — Route discovery (positives)

For each of the five expected public-intake host/path tuples
(proposal Q4 lines 110-115):

| host                          | path                              |
|-------------------------------|-----------------------------------|
| `api.local.humility.local`    | `/api/v1/public/applications`     |
| `api.local.humility.local`    | `/api/v1/public/chapters`         |
| `web.local.humility.local`    | `/api/public/applications`        |
| `web.local.humility.local`    | `/api/public/chapters`            |
| `web.local.humility.local`    | `/api/applications`               |

Walk paginated `GET /routes` (see H3) collecting every Kong
Route. Select the route for each tuple by matching:

```jq
.hosts // [] | index($host)
and
.paths // [] | index($path)
```

Forbidden (audit gate A2 + shortcut gate C2):

- Selecting routes by KIC-generated route name
  (`server-manager-public-intake-api.api-local-humility-local.0`
  or similar). KIC's name templating has changed across major
  versions; the slice exists exactly to catch silent translation
  drift, not to encode KIC's current naming.
- Substring-match on `paths` (e.g. checking that any Kong route
  `paths` element *starts with* the expected path). KIC may emit
  Kong path expressions with regex prefixes (`~/api/v1/...`); the
  match must be against the canonical exact-path entry KIC
  produces for `pathType: Prefix`/`ImplementationSpecific`. If
  Kong emits the path with a `~` regex prefix in some KIC
  versions, the match needs to handle that — but it must be a
  controlled comparison, not an unbounded substring search.

If any of the five tuples cannot be resolved to exactly one
route, `fail` and emit the H1.10 compact diagnostic for the host
group, then `die`.

### H1.8 — Plugin assertion (positives)

For each resolved positive route, walk paginated
`GET /routes/<route_id>/plugins` (see H3) and assert at least one
returned plugin matches:

```jq
.enabled == true
and
.name == "rate-limiting"
```

Locked plugin identity (audit gate A3): the assertion is against
the **Kong plugin type** `rate-limiting`, not the Kubernetes
`KongPlugin` CR name `public-intake-rate-limit`. The Admin API
plugin entity's `name` field carries the plugin type; the CR
name appears (if at all) in `tags`. An assertion against the CR
name silently passes on a misconfigured CR with the right name
but a different plugin type.

The validator may **optionally** also print the discovered
config (`config.minute`, `config.hour`, `config.policy`) for
debugging, but the mandatory assertion is presence of an
enabled `rate-limiting` plugin on the route. Stronger config
assertions are not in this slice's contract — the BL-014 static
pin at `infra/tests/test_public_intake_rate_limit.py:328-345`
already locks `minute=5`, `hour=50`, `policy=local`, so the
runtime side asserts binding presence and leaves config
verification to the static layer.

### H1.9 — Adjacent route assertion (mandatory negative)

The required adjacent path is
`api.local.humility.local` + `/api/v1/web/admin/chapters`
(proposal Q6, audit gate A4, shortcut gate C3).

Resolution rule (proposal Q6 lines 142-150 + audit gate A4):

1. Walk `GET /routes` and find the Kong Route whose `hosts`
   contains `api.local.humility.local` and whose `paths` would
   handle `/api/v1/web/admin/chapters`. In the post-INIT-137
   topology this is the authenticated API catch-all route,
   typically with `paths` like `["/api/v1/web"]` or
   `["/api/v1"]`.
2. The required negative must resolve to **exactly one** route
   or `die` with a compact `/routes` listing for
   `api.local.humility.local`. This explicitly forbids the
   vacuous-pass shape where "no route matches and the negative
   is therefore trivially true" — that shape silently green-lights
   a regressed cluster.
3. Walk paginated `GET /routes/<route_id>/plugins` (see H3) and
   assert no enabled plugin has `name == "rate-limiting"`.

Optional additional negatives (allowed but not required, per
Q6 lines 152-156):

- `web.local.humility.local` + `/`
- `protected-api.local.humility.local` + `/`

A missing optional adjacent route is `skip`, not `pass`. Q6
explicitly forbids treating a missing optional negative as a
substitute for the required admin negative — the required one
must resolve, and a missing optional cannot mask its absence.

### H1.10 — Failure output shape

Locked compact format (proposal Q7, audit gate A6). On any
positive miss, negative violation, or resolution failure, emit
one line per **relevant** route (not every route in the
gateway):

```
ROUTE id=<route_id> hosts=[<host>,…] paths=[<path>,…] plugins=[<plugin_name>,…]
```

- "Relevant" means: the routes whose host matches the failing
  assertion's expected host group. With KIC reconciling the full
  local stack, `/routes` can return many entries; dumping all of
  them on failure obscures the signal in Buildkite log
  truncation.
- The plugin-name list must come from
  `GET /routes/<route_id>/plugins` walked with pagination (H3),
  not from a single `GET /plugins` page or from the route
  payload's embedded plugin reference (which only carries IDs).

Do not emit raw JSON dumps, do not include `config` payloads in
the per-route line (config is verbose and noisy), and do not
include `service`/`tags`/`headers` unless an assertion failed on
that field.

### H1.11 — Order of operations in `main`

```text
parse_args
validate_required_tools
start_port_forward (on its own log file under .tmp/)
wait_admin_api_reachable
discover_routes (paginated /routes)
resolve_positive_routes (host + path match per H1.7)
assert_positive_plugins (paginated /routes/<id>/plugins per H1.8)
resolve_required_negative (host + path match for /api/v1/web/admin/chapters)
assert_required_negative_no_rate_limiting (paginated per H3)
resolve_optional_negatives (best-effort, skip if absent)
assert_optional_negatives_no_rate_limiting (paginated per H3)
finish
```

The `trap cleanup EXIT INT TERM` reaps the port-forward at any
exit point. `finish` prints `RESULT: pass=N fail=M skip=K` so
Buildkite parsing matches sibling validators.

---

## H2 — Namespace pinning (`kong-system`, NOT `kong`)

**Severity:** HIGH (audit finding F1). Locking the wrong namespace
makes the validator unable to reach the Admin API and converts the
slice into a green-light no-op.

**Files affected:**

- `infra/tests/validate_kong_kic_translation_local.sh` (the
  port-forward command).
- `proposals/34-init-139-kong-kic-smoke.md` Q3 (the locked command
  shape — must be reconciled before implementation lands, per
  the proposal's own punt at lines 92-96).
- TG-2 guard token list (must reference the corrected namespace
  literal so a regression to `-n kong` fails the guard).

**The fix:** the locked command shape must be:

```bash
kubectl --kubeconfig "$KUBECONFIG_PATH" \
        port-forward -n kong-system deploy/kong-kong \
        "${PORT}:8444" \
        >"$log_file" 2>&1 &
```

**Repository facts confirming the namespace:**

- `gitops/channels/local/ingress/kong/namespace.yaml` declares
  exactly one namespace: `kong-system`. There is no `kong`
  namespace anywhere under `gitops/`.
- `gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml`
  places `Deployment/kong-kong`, `Service/kong-kong-proxy`, and
  all Kong RBAC under `namespace: kong-system`.
- `infra/channels/local.yaml:94` declares
  `gateway_namespace: kong-system` and
  `:100 gateway_deployment_name: kong-kong`.
- `infra/tests/test_public_intake_rate_limit.py:96-100`
  hard-asserts the rendered `Deployment/kong-kong` is in
  `namespace: kong-system`.
- `infra/tests/validate_auth_stack_local.sh:286` references
  `kong-kong-proxy.kong-system.svc.cluster.local`.

**Live verification (audit pre-read):**

```text
kubectl get deploy -A | grep kong
NAMESPACE     NAME       READY   UP-TO-DATE   AVAILABLE
kong-system   kong-kong  1/1     1            1
```

This is the F1 audit finding's source.

**Choice of pin form (audit F1 forms a/b):**

- (a) **Static lock** — encode `-n kong-system` as a literal in
  the script. **Recommended.** One-line change; matches every
  other validator in the family that also encodes its target
  namespace literally
  (e.g. `validate_object_storage_local.sh` uses `minio-system`).
  TG-2 can guard the literal token directly.
- (b) **Discovery** — query the namespace at runtime via a
  label selector like
  `kubectl get deployment -A -l app.kubernetes.io/name=kong -o
  jsonpath='{.items[0].metadata.namespace}'`. More robust to
  future namespace drift, but adds complexity, opens a "what if
  the selector returns zero or many" failure shape, and would
  require TG-2 to guard the selector instead of the namespace
  literal — a weaker guard.

Pick form (a). This is the same posture the rest of the
`validate_*_local.sh` family takes; the `infra/channels/local.yaml`
contract already pins `gateway_namespace: kong-system`, so a
future namespace migration would update both the channel contract
and the validator at the same time. Form (a) keeps the contract
surface visible and the guard tokens crisp.

**Where the pin lives in the script:**

The constant should sit beside `KUBECONFIG_PATH` near the top of
the file:

```bash
KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
KONG_NAMESPACE="kong-system"
KONG_DEPLOYMENT="kong-kong"
KONG_ADMIN_PORT="8444"
LOCAL_PORT="18444"
```

This shape lets TG-2 enforce all four literals
(`kong-system`, `kong-kong`, `8444`, `port-forward`) with simple
substring checks while keeping any future change to a single
location.

**Forbidden alternatives (audit F1):**

- Do not write `kubectl port-forward deploy/kong-kong -n kong …`
  literally as the proposal Q3 currently does. The proposal punts
  the namespace; the hookpoint locks it.
- Do not silently fall back to a hardcoded `kong-system` while
  also accepting `kong` as an env-var override. There is no
  legitimate caller passing `-n kong`, so there is no override
  surface to support.
- Do not switch to proxy burst behavior because the namespace
  was wrong (proposal Q3 lines 92-96 + shortcut gate C1
  explicitly forbid this escape).

---

## H3 — Pagination (routes AND plugins)

**Severity:** Routes pagination is locked (audit gate A7 LOW,
proposal Q4 lines 117-118). Plugin-endpoint pagination is the
F2 finding (MEDIUM) that must be folded in here.

**Files affected:**

- `infra/tests/validate_kong_kic_translation_local.sh` — both
  `GET /routes` and `GET /routes/<id>/plugins` walks must
  paginate identically.
- TG-2 guard tokens — must require structural pagination evidence
  (a `next` field reference *and* a loop construct) in **both**
  walks (audit F4 sharpening).

### H3.1 — Kong's pagination shape

Kong Admin API list endpoints return:

```json
{
  "data": [ {…}, {…} ],
  "next": "/routes?offset=<opaque>"
}
```

When there are no more pages, `next` is `null` (or absent). The
opaque offset can be used either as a path with the offset
preserved or as a query parameter on the same endpoint.

### H3.2 — Routes walk

```bash
discover_routes() {
  local url="https://127.0.0.1:${LOCAL_PORT}/routes"
  ROUTES_JSON='[]'
  while [[ -n "$url" && "$url" != "null" ]]; do
    local page
    page="$(curl --fail --silent --show-error --insecure "$url")"
    ROUTES_JSON="$(jq -s '.[0] + (.[1].data // [])' \
                       <(echo "$ROUTES_JSON") <(echo "$page"))"
    local next
    next="$(jq -r '.next // empty' <<<"$page")"
    if [[ -z "$next" || "$next" == "null" ]]; then
      url=""
    else
      # next is a relative path like "/routes?offset=…"; rebase
      # onto the port-forwarded host
      url="https://127.0.0.1:${LOCAL_PORT}${next}"
    fi
  done
}
```

The exact shape is illustrative; the substantive contract (audit
F2 + F4) is:

1. The walk **must** loop over `next` until empty/null.
2. The walk **must** accumulate all `data` entries into a single
   collection before any positive/negative resolution happens.
3. The walk **must not** truncate at the first page.

### H3.3 — Plugin walk per route (the F2 fix)

The plugin-endpoint walk has the **same shape** as the routes
walk, applied per resolved route:

```bash
list_route_plugins() {
  local route_id="$1"
  local url="https://127.0.0.1:${LOCAL_PORT}/routes/${route_id}/plugins"
  local plugins='[]'
  while [[ -n "$url" && "$url" != "null" ]]; do
    local page
    page="$(curl --fail --silent --show-error --insecure "$url")"
    plugins="$(jq -s '.[0] + (.[1].data // [])' \
                   <(echo "$plugins") <(echo "$page"))"
    local next
    next="$(jq -r '.next // empty' <<<"$page")"
    if [[ -z "$next" || "$next" == "null" ]]; then
      url=""
    else
      url="https://127.0.0.1:${LOCAL_PORT}${next}"
    fi
  done
  echo "$plugins"
}
```

This closes the F2 silent-regression failure mode:

- **False-negative (positive miss):** a public-intake route has
  rate-limiting bound, but on plugin page 2. Without the walk,
  the positive assertion fails on a correctly-bound route. CI
  flakes on a green system.
- **False-positive (negative miss):** the adjacent admin route
  has rate-limiting bound (a regression — this is exactly the
  silent-drop failure mode the slice exists to catch), but on
  plugin page 2. Without the walk, the negative assertion
  passes on a regressed system. The validator becomes a
  green-light regressor — the worst possible smoke outcome.

The negative-direction shape is the dangerous one and is the
explicit reason F2 is MEDIUM rather than LOW.

### H3.4 — Pagination guard surface (TG-2)

For TG-2 to defend pagination structurally (audit F4), the
script must contain literal substrings that a regex guard can
catch:

- The literal `.next` (jq path), or `"next"` if the script
  parses without jq, in **both** the routes walk and the plugins
  walk.
- A `while`/`until` loop construct in **both** walk regions.

A guard like `assert script_text.count("\".next\"") >= 2` (or
the equivalent jq-form) catches a regression that strips
pagination from one walk while keeping it in the other —
exactly the F2 shape.

### H3.5 — Forbidden shapes

- `curl … "?size=1000"` (or any explicit size) **as a substitute
  for pagination.** Kong's default size is currently 100; raising
  to 1000 in the URL works today, papers over the failure
  mode F2 describes, and silently breaks if a future Kong major
  version caps `size` lower or renames the parameter.
- Calling `GET /plugins` (the unscoped collection) and inferring
  per-route binding from `plugin.route.id` filtering. The
  proposal Q5 lock is `GET /routes/<route_id>/plugins`; that's
  the route-scoped endpoint and the right contract surface.
- Reading the route payload's embedded plugin field
  (`route.plugins`) — Kong does not embed plugin entities on
  routes in the standard JSON form; this would silently always
  return empty.

---

## H4 — Buildkite pipeline step wiring

**File:** `.buildkite/pipeline-cluster.yml`.

**Anchor:** the existing
`pr-cluster-merge-readiness-runtime-validators` step's `command:`
block at lines 25-34. The new validator is appended as a sixth
sibling line.

### H4.1 — Required edit

Append exactly one line to the end of the block:

```yaml
  - key: pr-cluster-merge-readiness-runtime-validators
    label: "PR cluster merge readiness runtime validators"
    if: build.pull_request.id != null
    timeout_in_minutes: 180
    command: |
      infra/tests/validate_object_storage_local.sh --cluster
      infra/tests/validate_tls_dns_local.sh --cluster
      infra/tests/validate_app_clusters_local.sh --cluster
      infra/tests/validate_cluster_security_local.sh --cluster
      infra/tests/validate_container_delivery_local.sh --cluster
      infra/tests/validate_kong_kic_translation_local.sh --cluster
```

### H4.2 — Locked invariants

- **Lane:** `.buildkite/pipeline-cluster.yml`, **not**
  `.buildkite/pipeline.yml` (proposal §3, scope gate §3,
  shortcut gate C6). The validator needs a live Kong data plane
  reconciled by KIC; the default unit-test lane has no cluster.
- **Step:** the existing
  `pr-cluster-merge-readiness-runtime-validators` step. No new
  step, no new lane, no new agent queue, no new
  `timeout_in_minutes` value.
- **Position:** appended at the bottom of the existing five-line
  block. The proposal §3 says "after Kong, TLS/DNS,
  auth/server-manager, or existing readiness validators have
  made the live route state meaningful." None of the existing
  five validators are explicitly Kong/KIC-readiness gates, so
  the practical placement is "last" — after `validate_app_clusters`
  has waited for application workloads (which depend on Kong
  routes existing).
- **Flag:** `--cluster`. No `--static-only`. TG-3 explicitly
  asserts the literal `--cluster` appears next to the validator
  path, so omitting the flag fails the guard.
- **Agents:** inherits `agents.queue: cicd-local` from the
  pipeline top-level. Do not override.
- **Conditional:** inherits `if: build.pull_request.id != null`
  from the existing step. Do not add a separate `if:` gate that
  could evaluate false on PRs (shortcut gate C6 risk b).

### H4.3 — F3 bootstrap-prerequisite handling

The cluster lane brings up with `--cluster-only`
(`.buildkite/pipeline-cluster.yml:21`), which the problem map
flags as Flux-skip. None of the five existing validators in the
runtime block prove that KIC has reconciled the public-intake
Ingresses — so the new validator must defend itself against an
empty-cluster vacuous-pass shape (audit F3, supported-surface F2).

Pick **form (c) — fail-fast precondition inside the validator**.
This is the cheapest option, lives entirely in the validator (no
new pipeline step), and produces a distinguishable error
message from the silent-drop case the slice exists to catch:

```bash
if [[ "$(jq -r 'length' <<<"$ROUTES_JSON")" -eq 0 ]]; then
  fail "expected at least one Kong Route; got zero — likely \
GitOps not reconciled (cluster-lane bring-up uses --cluster-only)"
  emit_routes_diagnostic
  die "precondition failed: empty Kong Route table"
fi
```

A loud, distinct failure message in this shape is **not** a
shortcut; the shortcut gate explicitly approves it (shortcut
gate F2 closing paragraph: "deterministic loud failure is not a
shortcut path"). Forms (a) and (b) — assume reconciled state, or
add a reconciliation predecessor — are pipeline-level and out of
this slice's diff budget; defer them to a follow-up if the
fail-fast inside the validator surfaces real flakes.

### H4.4 — Forbidden wiring shapes

Each is an explicit silent-disable shortcut (shortcut gate C6):

- Adding the validator to `.buildkite/pipeline.yml` (wrong lane).
- Embedding the validator path in a YAML comment in
  `pipeline-cluster.yml` (TG-3 uses `yaml.safe_load`, comments
  are stripped, so the guard fails — but the regression would
  also be silently disabled).
- Wrapping the validator in an `if:` gate that always evaluates
  false on PRs.
- Stripping the `--cluster` flag (the validator becomes a no-op
  on workstation defaults).
- Putting the validator into a separate Buildkite step that
  lacks a `depends_on:` edge to `humility-local-cluster-bringup`
  (the validator runs before the cluster is up).

---

## H5 — Pytest guard test points

**Files:** prefer extending an existing pytest module under
`infra/tests/` rather than creating a new one (proposal §6
diff-budget note + supported-surface F3).

For TG-2 (validator-contents guard), the natural home is a new
module **only if** no existing module owns "shell-validator
contents" assertions. There is no current cross-validator
contents-guard module under `infra/tests/`; the closest is
`infra/tests/test_public_intake_rate_limit.py` (which is the
BL-014 static layer and is **anti-scope** for INIT-139 per
proposal §5). A small new file
`infra/tests/test_kong_kic_translation_validator.py` is the
right shape; keep it short.

For TG-3 (Buildkite-wiring guard), extend
`infra/tests/buildkite_pipeline/test_cluster_lane.py`. That file
already owns the cluster-lane validator wiring assertions (it
checks `validate_object_storage_local.sh --cluster`,
`validate_tls_dns_local.sh --cluster`, etc., via the
`required_cluster_runtime_validators` fixture in
`infra/tests/fixtures/buildkite_pipeline.py`). The minimal change
is a one-line addition to
`REQUIRED_CLUSTER_RUNTIME_VALIDATORS` in the fixture; that
single edit causes the existing
`test_required_runtime_validators_run_in_cluster_mode` test to
exercise the new validator's cluster wiring.

### H5.1 — TG-2 (validator-contents guard) test points

File: `infra/tests/test_kong_kic_translation_validator.py` (NEW).

Each test below is one `def test_…` function. Together they
implement audit gate F4's "structural presence" sharpening over
proposal §4 TG-2's "literal presence" baseline.

#### TG-2.A — script exists and is executable

```python
def test_validator_script_exists_and_is_executable():
    path = REPO_ROOT / "infra/tests/validate_kong_kic_translation_local.sh"
    assert path.is_file()
    assert os.access(path, os.X_OK), "validator must be executable"
```

#### TG-2.B — required public-intake host/path tuples appear

```python
def test_validator_contains_all_five_public_intake_tuples():
    text = read_validator()
    expected = [
        ("api.local.humility.local", "/api/v1/public/applications"),
        ("api.local.humility.local", "/api/v1/public/chapters"),
        ("web.local.humility.local", "/api/public/applications"),
        ("web.local.humility.local", "/api/public/chapters"),
        ("web.local.humility.local", "/api/applications"),
    ]
    for host, path in expected:
        assert host in text, f"missing host literal {host}"
        assert path in text, f"missing path literal {path}"
```

The host and path literals appear separately in the assertion
because the script may parameterize the loop body but must still
encode each value once.

#### TG-2.C — both endpoint queries appear

```python
def test_validator_calls_both_admin_api_endpoints():
    text = read_validator()
    assert "/routes" in text
    assert "/routes/" in text and "/plugins" in text, (
        "must call /routes/<id>/plugins, not just /plugins"
    )
```

The second assertion enforces the route-scoped endpoint, not the
unscoped `/plugins` collection (audit gate A3 + shortcut gate C2
risk c).

#### TG-2.D — Kong plugin type literal appears in an assertion context

```python
def test_validator_asserts_rate_limiting_plugin_type():
    text = read_validator()
    assert "rate-limiting" in text, "must assert Kong plugin type"
    # Must not appear *only* in a comment line. Heuristic: at least
    # one non-comment line contains the literal.
    non_comment_hits = [
        line for line in text.splitlines()
        if "rate-limiting" in line
        and not line.lstrip().startswith("#")
    ]
    assert non_comment_hits, "rate-limiting must appear in code, not only comments"
```

This is audit F4's sharpening: literal-substring presence is
satisfiable by a comment, so the guard must require non-comment
presence.

#### TG-2.E — required adjacent negative literal AND route-resolution call

```python
def test_validator_contains_required_adjacent_negative():
    text = read_validator()
    assert "/api/v1/web/admin/chapters" in text
    # Audit F4: must also have a route-resolution call near the
    # negative — guard against the vacuous-pass regression.
    # Heuristic: the script must contain both the negative path
    # literal AND a /routes walk reference.
    assert "/routes" in text, "negative requires /routes resolution"
```

#### TG-2.F — pagination structural presence on routes AND plugins (F2 + F4)

```python
def test_validator_paginates_both_endpoints():
    text = read_validator()
    # `.next` (jq form) or `"next"` (string form) must appear at
    # least twice — once for routes, once for plugins.
    next_hits = text.count(".next") + text.count('"next"')
    assert next_hits >= 2, (
        "pagination must walk `next` for both /routes and "
        "/routes/<id>/plugins (F2)"
    )
    # And there must be at least one loop construct.
    assert any(token in text for token in ("while ", "until ")), (
        "pagination requires a loop construct"
    )
```

This is the F2 + F4 sharpened guard. A regression that strips
pagination from one of the two walks reduces `next_hits` below 2
and fails the test.

#### TG-2.G — namespace and Admin API access literals (audit F1 + shortcut gate adjacent gap)

```python
def test_validator_pins_kong_system_and_admin_api_access():
    text = read_validator()
    # F1: namespace must be kong-system, not kong.
    assert "kong-system" in text
    assert " -n kong " not in text and "-n=kong " not in text, (
        "must not target nonexistent `kong` namespace"
    )
    # Shortcut gate adjacent gap: live access shape must be present.
    assert "port-forward" in text, "live Admin API access required"
    assert "8444" in text, "Admin API port required"
    assert "--insecure" in text or " -k " in text, (
        "self-signed local TLS skip required"
    )
```

This closes both audit F1 (namespace) and the shortcut gate's
adjacent gap (TG-2 should also assert `port-forward` and `8444`).

#### TG-2.H — port-forward cleanup `trap` is present

```python
def test_validator_cleans_up_port_forward_on_exit():
    text = read_validator()
    assert "trap" in text, "port-forward cleanup trap required (A5)"
    # Trap must reference EXIT (and ideally INT/TERM).
    assert "EXIT" in text, "trap must run on EXIT"
```

### H5.2 — TG-3 (Buildkite-wiring guard) test points

File: extend
`infra/tests/fixtures/buildkite_pipeline.py` and rely on
`infra/tests/buildkite_pipeline/test_cluster_lane.py`.

#### TG-3.A — fixture extension (one-line addition)

In `infra/tests/fixtures/buildkite_pipeline.py` line 6-12:

```python
REQUIRED_CLUSTER_RUNTIME_VALIDATORS = (
    "infra/tests/validate_object_storage_local.sh",
    "infra/tests/validate_tls_dns_local.sh",
    "infra/tests/validate_app_clusters_local.sh",
    "infra/tests/validate_cluster_security_local.sh",
    "infra/tests/validate_container_delivery_local.sh",
    "infra/tests/validate_kong_kic_translation_local.sh",  # NEW
)
```

This single edit causes
`test_required_runtime_validators_run_in_cluster_mode`
(`infra/tests/buildkite_pipeline/test_cluster_lane.py:74-91`) to
assert that:

- the new validator path appears in a cluster-lane step's
  `command:` (the test loops over all
  `REQUIRED_CLUSTER_RUNTIME_VALIDATORS`);
- the matching step contains `--cluster`;
- the matching step does **not** contain `--static-only` —
  closing the silent-disable shortcut where someone adds the
  validator with the wrong flag.

The fixture loads the cluster pipeline with `yaml.safe_load`
(`fixtures/buildkite_pipeline.py:75`), so a comment-only
reference to the validator path fails the test (shortcut gate C6
risk c).

#### TG-3.B — confirm the validator lands in the cluster lane, not the default lane

The existing
`test_cluster_pipeline_or_cluster_aware_main_lane_exists`
(`test_cluster_lane.py:57-71`) and
`test_humility_local_cluster_bringup_precedes_runtime_validators`
(`test_cluster_lane.py:94-120`) collectively enforce this. The
fixture extension in TG-3.A automatically extends both tests'
coverage to the new validator. No new test function is required.

#### TG-3.C — defense against wrong-lane regression

If a future PR adds the validator to `.buildkite/pipeline.yml`
instead of `.buildkite/pipeline-cluster.yml`, the existing
fixture's `cluster_sources` property
(`fixtures/buildkite_pipeline.py:44-48`) prefers
`pipeline-cluster.yml` when present and falls back to
`pipeline.yml` only when the cluster file does not exist. The
new validator's PR will land alongside the existing
`pipeline-cluster.yml`, so the fallback does not apply, and the
test in TG-3.A correctly fails when the new validator path is
missing from the cluster lane.

### H5.3 — Test surface that TG-2/TG-3 must NOT add

- No execution of the shell validator from pytest. The validator
  needs a live cluster; the unit-test lane (`pipeline.yml`) has
  no cluster. TG-2 reads the file as text; TG-1 (proposal §4)
  is the runtime exercise.
- No assertion on the BL-014 static manifests
  (`infra/tests/test_public_intake_rate_limit.py` is anti-scope
  per proposal §5).
- No assertion on Kong/KIC manifests, the rendered chart, or
  the KongPlugin CR. INIT-139 is runtime-only verification of
  whatever those manifests produce, not a re-pin of their
  contents.
- No new GitHub Actions workflow, no new Buildkite plugin, no
  new container image (proposal §6 diff budget; supported-surface
  gate §4).

---

## Cross-reference summary

| Hook | File(s)                                                                       | Anchor                                                          | Risk-gate finding folded in |
|------|-------------------------------------------------------------------------------|-----------------------------------------------------------------|-----------------------------|
| H1   | `infra/tests/validate_kong_kic_translation_local.sh` (NEW)                    | `validate_object_storage_local.sh`, `validate_kong_ingress_local.sh` | A1, A2, A3, A4, A5, A6     |
| H2   | same shell + script-top constants                                             | `infra/channels/local.yaml:94`, rendered chart `kong-system`     | F1 (HIGH)                   |
| H3   | same shell, `discover_routes` and `list_route_plugins` helpers                | Kong Admin API list-pagination shape                            | A7, F2 (MEDIUM), F4         |
| H4   | `.buildkite/pipeline-cluster.yml` line 25-34                                  | existing 5-line `pr-cluster-merge-readiness-runtime-validators` block | C6, F3 (form c)         |
| H5   | `infra/tests/test_kong_kic_translation_validator.py` (NEW), `infra/tests/fixtures/buildkite_pipeline.py` (extend) | `infra/tests/buildkite_pipeline/test_cluster_lane.py` (existing) | C5, C6, F4              |

Two findings the implementer must reconcile **before** code lands:

- **F1 (HIGH):** namespace pin must be `kong-system`, not `kong`.
  Apply at H2.
- **F2 (MEDIUM):** plugin-endpoint pagination must mirror routes
  pagination. Apply at H3.

Two findings the implementer should fold in opportunistically:

- **F3 (MEDIUM):** add a fail-fast precondition (form c) inside
  the validator at H4.3 to distinguish empty-cluster from
  silent-drop.
- **F4 (LOW):** TG-2 guard tokens must enforce structural
  presence, not just literal substrings. Apply at H5.1
  (TG-2.D, TG-2.F, TG-2.G).

HOOKPOINTS_DONE: research/51-init-139-hookpoints.md
