# INIT-139 — Audit risk gate

**Verdict:** MEDIUM

Scope: INIT-139 — add `infra/tests/validate_kong_kic_translation_local.sh`,
a cluster-runtime validator that introspects Kong's Admin API to prove
KIC translated the `public-intake-rate-limit` `KongPlugin` annotation
into route-scoped `rate-limiting` plugin entities on the five
public-intake Kong Routes, asserts adjacent routes (notably
`/api/v1/web/admin/chapters`) do not carry route-scoped
`rate-limiting`, and is wired into
`.buildkite/pipeline-cluster.yml`'s `pr-cluster-merge-readiness-runtime-validators`
step. The slice is validator-only: no application code, no Kubernetes
manifest changes, no BL-014 static-test changes.

The audit gate inspects: (1) Admin API access at port 8444 with `-k`
for self-signed TLS; (2) routes selected by hosts + paths, not
generated route names; (3) plugin name asserted is the Kong plugin
type `rate-limiting`, not the K8s `KongPlugin` CR name; (4) negative
assertion covers the adjacent admin path; (5) port-forward cleanup
in a trap; (6) compact, debuggable failure output; (7) no false
positives or false negatives if Kong paginates `/routes` or
`/routes/<id>/plugins`.

Source proposal: `proposals/34-init-139-kong-kic-smoke.md`.
Source problem map: `research/50-init-139-kic-smoke-problem-map.md`.
Existing CI lane: `.buildkite/pipeline-cluster.yml`.

## Repository facts cross-checked

- `.buildkite/pipeline-cluster.yml` exists with the four-step shape
  the proposal describes: tooling preflight → bring-up → wait → PR
  cluster runtime validators (`object_storage`, `tls_dns`,
  `app_clusters`, `cluster_security`, `container_delivery`). The
  bring-up uses `--cluster-only` (line 21), which the problem map
  flags as skipping Flux post-install.
- The existing runtime validator block does **not** include any
  Kong-, KIC-, server-manager-, or Pomerium-readiness validator. The
  five validators that run (object storage, TLS/DNS, app clusters,
  cluster security, container delivery) do not assert that KIC has
  reconciled the public-intake Ingresses or that Kong Routes for the
  public-intake host/path tuples exist.
- `gitops/channels/local/ingress/kong/namespace.yaml` defines exactly
  one Kong namespace: `kong-system`. The rendered chart at
  `gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml`
  places `Deployment/kong-kong`, `Service/kong-kong-proxy`, and all
  Kong RBAC under `namespace: kong-system` (lines 3402–3403,
  3883–3884, 3890–3891, 3961–3962, 4015–4016, etc.). There is no
  `kong` namespace anywhere in `gitops/`.
- The proposal's Q3 lock is the literal command
  `kubectl port-forward deploy/kong-kong -n kong 8444:8444 &`. That
  command would fail against the actual rendered substrate because
  the namespace is `kong-system`. Q3 itself flags this verbatim:
  *"current local rendered Kong manifests show the release under
  `kong-system`; the INIT-139 contract intentionally locks the
  command above. Hookpoint research or implementation must reconcile
  that namespace detail before code lands."* The proposal punts the
  reconciliation rather than locking it. See F1.
- `infra/tests/test_public_intake_rate_limit.py` is the BL-014 static
  pin and is explicitly out of scope for this slice.
- `infra/tests/validate_kong_ingress_local.sh` and
  `infra/tests/test_kong_ingress_contract.py` are existing
  Kong-related substrate the new validator should sit alongside (not
  modify).

## A1 — Admin API port 8444 and self-signed TLS

**Lock (Q3):** Admin API access via `kubectl port-forward
deploy/kong-kong -n kong 8444:8444` + `curl --fail --silent
--show-error --insecure https://localhost:8444/routes`. The
`--insecure` flag is locked because "the Admin API listener uses
self-signed local TLS."

**Cross-check against rendered Kong:** the rendered chart
(`kong-3.2.0.yaml`) sets `KONG_ADMIN_LISTEN` to
`127.0.0.1:8444 ssl ...` on the `kong-kong` deployment, and
KIC consumes `https://localhost:8444` with TLS skip-verify. Port
8444 is correct. The Admin API does listen on TLS and the
certificate is generated locally (self-signed in this rendered
release shape), so `--insecure` is the right flag for the smoke.

**What the audit can verify at proposal stage:** the port number
and the `-k`/`--insecure` decision are both locked correctly. The
deployment name `kong-kong` is also correct. The namespace flag
value `kong` is wrong (see F1).

**Verdict:** Port and TLS-skip lock are correct. Audit risk LOW for
A1's port + cert-skip dimensions. Namespace correctness is split
out as F1 because Q3 explicitly punts it.

## A2 — Route selection by hosts + paths, not generated names

**Lock (Q4):** "must not use generated route names. It must
identify routes by route attributes: `hosts` contains the expected
host; `paths` contains the expected path for public-intake
positives; for adjacent negatives, the selected Kong Route is the
route whose host/path combination would handle the adjacent request
path."

Five public-intake host/path tuples are explicitly enumerated
(Q4 §107–115). Negative selection is by host/path attribute
matching, not by route name.

**Why route-name avoidance matters:** KIC route names are generated
from a hash of the Ingress + path index, and the format has changed
between KIC major versions. A route-name assumption would silently
break on KIC upgrades — exactly the silent-drop failure mode the
slice exists to catch. The Kong Admin API Route schema (Routes have
`hosts: [...]` and `paths: [...]` fields) is the stable contract.

**Verdict:** Routes are selected by `hosts` + `paths` per the locked
contract. The five expected host/path tuples are explicitly
enumerated. Audit risk LOW for A2.

## A3 — Plugin name asserted is `rate-limiting` (Kong plugin type)

**Lock (Q5):** "for each selected route, call `GET
/routes/<route_id>/plugins`. For every public-intake route, assert
that the returned plugin list contains an enabled plugin with `name
== "rate-limiting"`. The assertion is against the Kong plugin type,
not the Kubernetes `KongPlugin` CR name."

**Why this distinction matters:** the K8s CR is named
`public-intake-rate-limit` and the Kong plugin entity carries that
name in `tags` or in metadata, but the plugin's `name` field on the
Admin API is the Kong plugin *type* — `rate-limiting`. KIC sets the
plugin's type from the CR's `plugin:` field, which is
`rate-limiting`. An assertion against the CR name would silently
pass on a misconfigured CR with the right name but a different
plugin type (a forward-compat failure mode); an assertion against
the Kong plugin type catches that.

**Verdict:** Plugin identity is locked at the Kong plugin type
level. Audit risk LOW for A3.

## A4 — Negative assertion includes /api/v1/web/admin/chapters

**Lock (Q6):** "At minimum, cover the authenticated/admin adjacent
request path `api.local.humility.local` + `/api/v1/web/admin/chapters`."

Q6 also locks two important sub-properties:

1. *Resolution requirement:* "the validator should resolve the
   matching Kong Route by host and route path, then assert `GET
   /routes/<route_id>/plugins` does not include `rate-limiting`."
   This rules out a vacuous-pass where the negative is asserted
   against zero matched routes (which is always trivially true).
2. *Required-vs-optional split:* "Do not treat a missing optional
   adjacent route as a pass for the required admin-path negative.
   The required negative must resolve to exactly one route or fail
   with route-listing diagnostics."

The optional negatives (`web.local.humility.local /` and
`protected-api.local.humility.local /`) are allowed but not
required, and Q6 explicitly separates them from the mandatory admin
path so a missing optional cannot mask a missing mandatory.

**Verdict:** The required adjacent admin path is locked, and the
proposal explicitly closes the vacuous-pass loophole by requiring
the route to resolve. Audit risk LOW for A4.

## A5 — Port-forward cleanup on exit

**Lock (Q3):** "The implementation must clean up the port-forward
process in a `trap`."

This matches the existing `infra/tests/validate_*_local.sh` pattern
and is the cheapest correct shape for cleaning up a backgrounded
`kubectl port-forward`. A `trap '<cleanup>' EXIT INT TERM` covers
the script-success path, the assertion-failure path, and Buildkite
SIGTERM at timeout.

**What a regression to a weaker shape would look like:** a
`kill %1` at the script tail without a trap would leak the
port-forward on assertion failure; a missing trap entirely would
leak on timeout. Both are common copy-paste regressions. The
proposal's `trap` lock is the right shape.

**Verdict:** Cleanup-on-exit is locked at the correct level. Audit
risk LOW for A5.

## A6 — Compact, debuggable failure output

**Lock (Q7):** failures must print "one line per relevant route
with: route id; hosts; paths; plugin names from `GET
/routes/<route_id>/plugins`. The output must be compact enough for
Buildkite logs and specific enough that a missing binding is
identifiable without dumping the whole Admin API payload."

**Three properties locked:**

1. *Compact:* one line per route, not a JSON dump.
2. *Specific:* enough fields (id + hosts + paths + plugin names)
   that the reader can tell *which* expected route is missing the
   binding without re-running with `--debug`.
3. *Targeted:* "relevant" routes only, not every Kong route in the
   gateway. With KIC reconciling the full local stack, `/routes`
   can return tens to hundreds of entries; dumping all of them on
   failure would obscure the signal in Buildkite log truncation.

**Verdict:** Failure output is locked at the right granularity for
a CI smoke. Audit risk LOW for A6.

## A7 — No false positives under route + plugin pagination

**Lock (Q4, routes):** "Pagination must follow Kong's response
shape until there is no next page before asserting missing or
duplicate routes."

**Gap (Q5, plugins):** Q5 says "call `GET
/routes/<route_id>/plugins`" and "assert that the returned plugin
list contains an enabled plugin with `name == "rate-limiting"`". It
does **not** require pagination of the plugin response.

**Why this matters:** Kong's Admin API paginates the
`/routes/<id>/plugins` collection identically to `/routes`. A route
with many bound plugins (consumer-scoped plugins, observability
plugins, auth plugins, plus the rate-limiting plugin) can return
the rate-limiting plugin on page 2 or later. The default Kong
`size` is 100, so this is not the common case today, but pagination
is a forward-compat concern: as more KIC features land,
plugin-per-route counts can grow, and `size` defaults can change
between Kong major versions. The audit gate explicitly asks about
this case (item 7 of the gate).

**Two failure shapes the gap enables:**

1. *Positive false-negative:* a public-intake route has
   rate-limiting bound, but it is on page 2. The non-paginated
   check sees only page 1 plugins, asserts "no rate-limiting
   bound", and fails the validator on a route that is correctly
   bound. CI flake on real-but-correct binding.
2. *Negative false-positive:* an adjacent admin route has
   rate-limiting bound (a regression — the slice's exact failure
   mode), but on page 2. The non-paginated check sees only page 1
   plugins, asserts "no rate-limiting bound", and passes the
   validator on a regressed binding. The smoke silently misses the
   regression it was built to catch.

The second shape is the more dangerous one because it converts the
validator into a green-light regressor: the worst possible failure
mode for a smoke that exists specifically to catch silent drops.

See F2 for the recommended pagination lock.

**Verdict:** Routes pagination is locked correctly. Plugin
pagination is not locked. Audit risk MEDIUM for A7.

## Findings

### F1 — Locked Kong namespace `kong` does not exist; rendered chart is `kong-system`

**Severity:** HIGH (correctness; validator will not run as locked).

**Where:** Q3 locked command shape, proposal §2 ("the canonical
command shape is: `kubectl port-forward deploy/kong-kong -n kong
8444:8444`").

**Risk:** The proposal locks the namespace to `kong`. The actual
rendered Kong release is in `kong-system`
(`gitops/channels/local/ingress/kong/namespace.yaml` and the
`kong-3.2.0.yaml` rendered chart confirm this; no `kong` namespace
exists anywhere under `gitops/`). The locked command will fail with
`Error from server (NotFound): deployments.apps "kong-kong" not
found` in the `kong` namespace.

The proposal acknowledges this verbatim in Q3 and defers it to
"hookpoint research or implementation". That defers the audit gate
to a downstream phase, but the audit asks (item 1) whether the
validator queries Kong's Admin API "at the right port (8444) with
-k for self-signed certs". The port is right, the TLS skip is
right, but the namespace is wrong, and a runtime smoke that cannot
even reach the Admin API will fail at port-forward, not at the
introspection assertions — which means the slice's primary signal
(translation drift) cannot be exercised at all.

Two implementer responses are possible:

- (a) Update the locked namespace to `kong-system`. Lowest-risk; a
  one-line change in the validator and the proposal.
- (b) Discover the namespace at runtime via `kubectl get
  deployment -A -l app.kubernetes.io/name=kong -o
  jsonpath='{.items[0].metadata.namespace}'` (or similar selector
  query). More robust to future namespace drift; longer to read.

The proposal does not pick. Without a locked answer, an implementer
following the contract literally produces a broken validator that
would only be caught at first cluster CI run.

**Action:** lock the namespace before implementation. Recommend
form (a): change Q3 to `kubectl port-forward deploy/kong-kong -n
kong-system 8444:8444 &`. Update Q3's command shape, the §3
substrate description, and any TG-2 guard token list that contains
the literal `-n kong` string.

### F2 — Plugin pagination is not locked; route-pagination is

**Severity:** MEDIUM (correctness; silent-regression failure mode
in the slice's primary use case).

**Where:** Q5 plugin discovery contract, contrasted with Q4 route
pagination contract.

**Risk:** Q4 says "Pagination must follow Kong's response shape
until there is no next page before asserting missing or duplicate
routes." Q5 says "call `GET /routes/<route_id>/plugins`" and
"assert that the returned plugin list contains an enabled plugin
with `name == "rate-limiting"`." Q5 does not extend the pagination
requirement to the plugin endpoint.

The Kong Admin API paginates `/routes/<id>/plugins` identically to
`/routes`. The negative-route case is the dangerous shape: an
adjacent admin route with regressed rate-limiting binding on plugin
page 2 will pass the non-paginated check, and the validator —
designed precisely to catch silent translation regressions — will
silently miss the regression. See A7 above for the full failure
shape.

**Action:** extend Q5 to require pagination of
`/routes/<route_id>/plugins` until there is no next page, before
asserting plugin presence or absence. Same response-shape walking
pattern as Q4. Cost: a handful of extra lines in the validator and
one extra TG-2 guard token to assert plugin pagination is present.

### F3 — Bootstrap prerequisite is unresolved; cluster lane has no Kong/KIC readiness gate

**Severity:** MEDIUM (vacuous-pass risk in CI; the validator can
silently green-light an empty cluster).

**Where:** proposal §3 substrate ("Place it after Kong, TLS/DNS,
auth/server-manager, or existing readiness validators have made the
live route state meaningful"); the actual
`.buildkite/pipeline-cluster.yml` runtime validator block.

**Risk:** The current cluster lane bring-up uses `--cluster-only`
(pipeline-cluster.yml line 21), which the problem map (lines 22,
35) flags as skipping Flux post-install. The runtime validator
block (`pr-cluster-merge-readiness-runtime-validators`, lines
30–35) currently runs:

```
infra/tests/validate_object_storage_local.sh --cluster
infra/tests/validate_tls_dns_local.sh --cluster
infra/tests/validate_app_clusters_local.sh --cluster
infra/tests/validate_cluster_security_local.sh --cluster
infra/tests/validate_container_delivery_local.sh --cluster
```

None of these prove that Kong is reachable, that KIC has reconciled
the public-intake Ingresses, or that the five public-intake Kong
Routes exist. If the new validator is appended to this block as
locked in §3, and Flux post-install has not landed the
public-intake `Ingress` + `KongPlugin` resources by the time the
validator runs, then `GET /routes` returns zero routes matching the
expected host/path tuples. The validator's positive assertion
fails, but the negative assertion (`/api/v1/web/admin/chapters` has
no rate-limiting) passes vacuously — same shape as the missing
mandatory negative trap that Q6 explicitly closes for the
introspection assertion, but reintroduced one layer up at the
"validator runs against an empty cluster" level.

The problem map locks this question explicitly (lines 35, 110:
"Bootstrap prerequisite: define whether the cluster lane has a
reconciled local GitOps stack despite `--cluster-only`; if not, add
the minimum bootstrap/reseed step before runtime validators"). The
proposal does not lock an answer.

**Action:** before implementation lands, decide one of:

- (a) The cluster lane preserves a reconciled GitOps stack across
  bring-ups. Lock that as a prerequisite assumption with a one-line
  reference (where the cluster state survives, and how the lane
  enforces it).
- (b) Add a reconciliation step (or a Kong/KIC readiness validator
  predecessor) before the new validator runs. The new validator
  then only runs after KIC has reconciled the public-intake
  resources.
- (c) Add a precondition assertion at the head of the new validator
  that fails fast with a distinct message ("expected at least one
  Kong Route for `api.local.humility.local`; found zero — likely
  GitOps not reconciled; see <runbook>") so the empty-cluster shape
  is distinguishable from the silent-drop shape the slice exists
  to catch.

Form (c) is the cheapest and is recoverable inside the validator
itself; forms (a) and (b) are pipeline-level. Whichever form is
chosen, lock it in the proposal so the contract is closed before
implementation.

### F4 — TG-2 guard tokens are weakly specified

**Severity:** LOW (regression-defense completeness).

**Where:** TG-2 acceptance, proposal §4.

**Risk:** TG-2 says the pytest guard "asserts the script contains
the expected public-intake route set; ... checks `GET /routes`;
... checks `GET /routes/<route_id>/plugins`; ... searches for
`rate-limiting`; ... contains the adjacent
`/api/v1/web/admin/chapters` negative." These are substring-or-
literal-presence checks. They can be satisfied by a comment that
says "we check `GET /routes/<route_id>/plugins`" without the
script actually performing the call. They can also be satisfied
by a script that performs the call but doesn't paginate, doesn't
check the right plugin type, or doesn't tie the negative path
back to a resolved route id.

This is the same regression-defense ambiguity that BL-013's audit
F1 flagged at the aggregation level: the contract is locked at the
proposal level, but the test enforcement is one ply weaker than
the contract. A future implementer trimming the validator could
preserve the literal tokens and pass TG-2 while violating the
contract.

**Action:** sharpen TG-2's guard tokens to require structural
presence, not just literal presence:

- For pagination: require both a `next` field reference *and* a
  loop construct (`while`/`until`/recursion) in the route-walking
  section. (And, after F2, in the plugin-walking section.)
- For plugin type: require the literal `'rate-limiting'` string
  inside an assertion or filter expression, not in a comment.
- For the adjacent negative: require both the literal
  `/api/v1/web/admin/chapters` *and* a route-resolution call (so
  the negative does not silently regress to a vacuous-pass shape).

Cost: a handful of extra regex assertions in the pytest guard.
This is a defense against a future trim that preserves the surface
shape but loses the substance — exactly the silent-drop failure
mode the slice itself exists to catch, applied one layer up at
the test-enforcement level.

## Verdict reasoning

INIT-139 holds at MEDIUM audit risk:

- **Admin API access (A1):** Q3 locks port 8444 + `--insecure`
  correctly. Namespace is wrong (F1).
- **Route selection (A2):** Q4 locks host/path attribute selection
  with five enumerated public-intake tuples. LOW risk.
- **Plugin identity (A3):** Q5 locks Kong plugin type
  `rate-limiting`, not the K8s CR name. LOW risk.
- **Negative assertion (A4):** Q6 locks the mandatory
  `/api/v1/web/admin/chapters` negative *and* explicitly closes
  the missing-route vacuous-pass loophole. LOW risk.
- **Cleanup (A5):** Q3 locks `trap`-based port-forward cleanup.
  LOW risk.
- **Failure output (A6):** Q7 locks compact one-line-per-route
  output with id + hosts + paths + plugin names. LOW risk.
- **Pagination (A7):** Q4 locks routes pagination correctly. Q5
  does not lock plugin pagination; the slice's most dangerous
  failure mode (silent miss of a regressed admin-route binding)
  reappears under plugin-page-2 conditions. MEDIUM risk; see F2.

Two findings are implementation-blocking before code can land:

- **F1 (HIGH):** locked namespace `kong` does not exist; the
  actual rendered Kong is in `kong-system`. Fix the lock or the
  validator will not even reach the Admin API.
- **F2 (MEDIUM):** plugin endpoint pagination must be locked to
  match Q4's route pagination, or the slice's primary signal
  (silent translation drop on adjacent routes) is lost on routes
  with many plugins.

Two findings are completeness improvements that should be folded
in before implementation:

- **F3 (MEDIUM):** bootstrap-prerequisite ambiguity in the cluster
  lane can vacuously green-light an empty cluster. Pick form (a)
  reconciled-state-survives, (b) add-reconciliation-predecessor,
  or (c) fail-fast-precondition. Form (c) is cheapest and
  inside-validator-recoverable.
- **F4 (LOW):** TG-2 guard tokens are substring-presence checks
  and can pass on a contract-violating trim. Sharpen to require
  structural presence (pagination loops, route-resolution for the
  negative, plugin-type filter expression).

The proposal's substantive locks (Q1–Q8) are sound on
introspection-vs-behavior, validator location, route attribute
selection, plugin type identity, mandatory negative, cleanup, and
failure output shape. The two correctness gaps (namespace, plugin
pagination) and the two completeness gaps (bootstrap prerequisite,
guard token strength) are recoverable with one focused proposal
revision before EXECUTE_IMPLEMENTATION begins.

Verdict: MEDIUM.

AUDIT_DONE: plans/risk/init-139-audit.md
