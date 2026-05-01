# BL-014 hookpoints — Kong version pin static guard

Phase 5 research for Proposal 30 (`proposals/30-bl-014-kong-version-pin.md`).
Cross-referenced against `research/44-bl-014-kong-version-problem-map.md`,
the audit/scope/shortcut/supported-surface gates under `plans/risk/`, and
the actual files that hold each pin in the worktree. The shortcut gate
(MEDIUM) flagged the CRD bundle annotation
`kubernetes-configuration.konghq.com/version: v1.5.2` as the missing
fourth surface; this document folds it into the locked surface list so
6c does not have to reconcile that gap by reading the gate file again.

The implementer phase (6c) must:

- Parse YAML structurally with `yaml.safe_load` / `yaml.safe_load_all` for
  every YAML surface — no substring scans on raw file text. The single
  exception is `gitops/channels/local/ingress/kong/README.md`, which is
  markdown around a `helm template ... --version 3.2.0` command line and
  is not parseable as YAML.
- Pin all four version surfaces independently: Helm chart `3.2.0`
  (locked at three reflection points), Kong Gateway image `kong:3.9`,
  KIC image `kong/kubernetes-ingress-controller:3.5`, and CRD bundle
  annotation `kubernetes-configuration.konghq.com/version: v1.5.2`.
- Land all assertions inside
  `infra/tests/test_public_intake_rate_limit.py` (Q2 in the proposal).

## H0 — Test file to extend

`infra/tests/test_public_intake_rate_limit.py:1-137`

The full file is the implementation surface. Existing helpers and
assertions to preserve:

- `_yaml_documents(path)` at lines 16-22 — `yaml.safe_load_all` over a
  multi-document file, stamps each parsed dict with `_source_path` so
  failure messages can name the offending manifest. Reuse this helper
  for new YAML reads. Do not bypass it with raw text reads on YAML
  surfaces.
- `_local_resources()` at lines 25-43 — globs
  `LOCAL_GITOPS / "applications" / "server-manager" / *.yaml` and
  `LOCAL_GITOPS / "auth" / "pomerium" / *.yaml`, asserts the two
  required Ingress manifests exist. Extend the `required` list to add
  the four Kong version files (see H1–H4). Use the same
  `assert path.is_file(), f"missing expected local GitOps manifest: ..."`
  loud-fail idiom for any newly required file.
- `_metadata`, `_annotations`, `_ingress_paths`, `_plugin_annotation`
  at lines 50-68 — structural readers over parsed YAML; extend the new
  Prefix-coverage and anti-list assertions on top of these, do not
  duplicate them.
- `_web_submit_endpoint()` at lines 46-47 — pulls the canonical web
  submit path from `infra/tests/fixtures/web-ui/contract.json`; keep
  routing the web-side `(host, path)` tuple through this helper so the
  contract fixture remains the source of truth for that one path.
- The two existing test functions:
  - `test_public_intake_kong_plugin_has_documented_rate_limit_config`
    at lines 71-88 — locks the `KongPlugin` config (`minute: 5`,
    `hour: 50`, `policy: local`, namespace `server-manager`). Do not
    modify; the BL-014 extensions are additive.
  - `test_public_intake_plugin_is_bound_only_to_public_submit_paths`
    at lines 91-136 — asserts three annotated `(host, path)` tuples
    and three catch-all Ingresses (`web`, `protected-api`,
    `server-manager-api`) are unannotated. **Extend** this test (or
    add a sibling test in the same file) to cover the full route set
    in H6 and the full anti-list in H7.

REPO_ROOT and LOCAL_GITOPS at lines 10-11 already point at the right
roots; reuse them. PLUGIN_NAME at line 13 is the plugin string to keep
referencing.

## H1 — Helm chart version `3.2.0` (README render command)

`gitops/channels/local/ingress/kong/README.md:7-16`

The only non-YAML surface in the slice. The chart version lives inside
a fenced bash code block:

```
 7  ```bash
 8  helm repo add kong https://charts.konghq.com
 9  helm repo update
10  helm template kong kong/kong \
11    --version 3.2.0 \
12    --namespace kong-system \
13    --include-crds \
14    -f gitops/channels/local/ingress/kong/render-values.yaml \
15    > gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml
16  ```
```

Read the file as text (`Path.read_text(encoding="utf-8")`) and assert
the literal substring `--version 3.2.0` is present. This is the one
defensible substring exception because the surface is markdown, not
YAML. A regex of the form `--version\s+(\d+\.\d+\.\d+)` is acceptable
if the implementer wants to surface the actual drifted value in the
failure message; either form satisfies the proposal's TG-1 acceptance
("the Helm chart render command/reference remains `3.2.0`").

Failure message must name the surface ("Kong Helm chart version drifted
in README render command") so a Gateway-image bump does not look like a
chart-version bump in CI logs (audit F3).

## H2 — Rendered manifest reference `rendered/kong-3.2.0.yaml` (kustomization)

`gitops/channels/local/ingress/kong/kustomization.yaml:1-29` — assertion
target is line 7.

```
 1  apiVersion: kustomize.config.k8s.io/v1beta1
 2  kind: Kustomization
 3  resources:
 4    - namespace.yaml
 5    - ingress-class.yaml
 6    - networkpolicy.yaml
 7    - rendered/kong-3.2.0.yaml
 8  patches:
 ...
```

Parse with `yaml.safe_load(path.read_text(...))` (single-doc file) and
assert `"rendered/kong-3.2.0.yaml" in document["resources"]`. Do not
substring-match on the raw text — `image.tag: "3.9"` would also
contain `"3.2.0"` somewhere in another file, and a structural read on
the `resources` list is the same idiom as the rest of the test file.

## H3 — Rendered chart label `helm.sh/chart: kong-3.2.0`

`gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml:4072`
(canonical assertion line — the proxy Deployment's
`spec.template.metadata.labels["helm.sh/chart"]`).

Other reflection points the audit gate verified (4072 is sufficient
for a single-source-of-truth assert, but any of these is structurally
equivalent because the chart sets the label once via Helm values):
3406, 3418, 3872, 3894, 3965, 3987, 4004, 4019, 4049, 4072.

Use `yaml.safe_load_all` on the rendered file (it is multi-doc, ~4000+
lines). Walk parsed documents, find at least one chart-emitted
resource that carries the label (e.g., `kind == "Deployment"` and
`metadata.name == "kong-kong"`), and assert
`metadata.labels["helm.sh/chart"] == "kong-3.2.0"`. The structural read
naturally tolerates re-rendering whitespace/comment changes that would
break a substring approach.

This is the third reflection point of the chart `3.2.0` value (after
the README command and the kustomization filename), so a partial bump
that updates one file but not the others fails CI immediately.

## H4 — Kong Gateway image `kong:3.9`

Two pinning surfaces — both must assert independently so a Helm-values
edit that slips past `helm template` (or vice versa) is caught.

### H4a — Helm values source

`gitops/channels/local/ingress/kong/render-values.yaml:13-16`

```
13  image:
14    repository: kong
15    tag: "3.9"
16    pullPolicy: IfNotPresent
```

`yaml.safe_load(path.read_text(...))`, then assert
`document["image"]["repository"] == "kong"` and
`document["image"]["tag"] == "3.9"`. Use the structured key path; do
not substring-match `"kong:3.9"` against the raw text (the raw text
does not contain that exact form — it appears only in the rendered
manifest).

### H4b — Rendered Deployment image fields

`gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml:4087` and
`:4259`

- `4087` — init container `clear-stale-pid` on the `kong-kong`
  Deployment: `image: kong:3.9`.
- `4259` — main `proxy` container on the `kong-kong` Deployment:
  `image: kong:3.9`.

Walk the parsed multi-doc YAML, find the `kong-kong` Deployment in
namespace `kong-system`, and assert that every container under
`spec.template.spec.containers` and `spec.template.spec.initContainers`
named `clear-stale-pid` or `proxy` has `image == "kong:3.9"`. (If
preferred, assert all containers whose `image` starts with `kong:`
exactly equal `kong:3.9` — same effect, simpler loop.) The structured
walk handles the YAML-file's multi-document layout cleanly.

## H5 — KIC image `kong/kubernetes-ingress-controller:3.5`

Two pinning surfaces, same shape as H4.

### H5a — Helm values source

`gitops/channels/local/ingress/kong/render-values.yaml:45-49`

```
45  ingressController:
46    enabled: true
47    image:
48      repository: kong/kubernetes-ingress-controller
49      tag: "3.5"
```

`yaml.safe_load(...)`, then
`document["ingressController"]["image"]["repository"] == "kong/kubernetes-ingress-controller"`
and `document["ingressController"]["image"]["tag"] == "3.5"`.

### H5b — Rendered Deployment image field

`gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml:4221`

```
4221  image: kong/kubernetes-ingress-controller:3.5
```

Same `kong-kong` Deployment as H4b; the `ingress-controller` container
sits at `spec.template.spec.containers[name == "ingress-controller"]`.
Assert
`container["image"] == "kong/kubernetes-ingress-controller:3.5"`.

## H6 — CRD bundle annotation `kubernetes-configuration.konghq.com/version: v1.5.2`

This is the surface the shortcut gate (MEDIUM) flagged as missing. Pin
it here so the proposal's locked-surface list matches the research
problem map's compatibility-input list.

`gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml:1690-1694`
(canonical assertion target — the `KongPlugin` CRD's bundle
annotation):

```
1688  apiVersion: apiextensions.k8s.io/v1
1689  kind: CustomResourceDefinition
1690  metadata:
1691    annotations:
1692      kubernetes-configuration.konghq.com/channels: ingress-controller,gateway-operator
1693      kubernetes-configuration.konghq.com/version: v1.5.2
1694    name: kongplugins.configuration.konghq.com
```

The same annotation is rendered on every chart-emitted CRD (verified
reflection points: lines 6-8 for `ingressclassparameterses`, 64-66 for
`kongclusterplugins`, plus every other CRD the chart bundles). One
assertion targeting the `KongPlugin` CRD specifically is sufficient —
that CRD is the schema input to the public-intake `KongPlugin`
manifest, which is the resource BL-014 protects.

Walk parsed multi-doc YAML, find
`document["kind"] == "CustomResourceDefinition"
 and document["metadata"]["name"] == "kongplugins.configuration.konghq.com"`,
and assert
`document["metadata"]["annotations"]["kubernetes-configuration.konghq.com/version"] == "v1.5.2"`.

Failure message must name the surface ("Kong CRD bundle annotation
drifted on KongPlugin CRD") so a CRD-only bump (chart and image
versions held steady) is unambiguous in CI logs.

## H7 — Public-intake supported route set (TG-2)

The full route set the proposal locks at §2.3 / TG-2. Use both
`(host, path)` tuple membership for literal annotated paths and
Prefix-coverage proofs for upload-url children.

### H7a — Direct API side

`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:1-51`

- `KongPlugin public-intake-rate-limit` (lines 1-12) — already locked
  by `test_public_intake_kong_plugin_has_documented_rate_limit_config`.
- `Ingress server-manager-public-intake-api` (lines 14-50):
  - namespace `server-manager` (line 18);
  - `konghq.com/plugins: public-intake-rate-limit` (line 26);
  - `ingressClassName: kong` (line 28);
  - host `api.local.humility.local` (line 34);
  - Prefix paths:
    - `/api/v1/public/applications` (lines 37-43);
    - `/api/v1/public/chapters` (lines 44-50).

Required `(host, path)` tuples in `annotated_paths`:

- `("api.local.humility.local", "/api/v1/public/applications")`;
- `("api.local.humility.local", "/api/v1/public/chapters")`.

Required upload-url Prefix-coverage proof:
`"/api/v1/public/applications/upload-url".startswith(parent_prefix)`
must hold for some annotated `(host, parent_prefix)` on
`api.local.humility.local`. The candidate parent prefix is
`/api/v1/public/applications` (line 37).

### H7b — Pomerium/web side

`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml:1-45`

- `Ingress web-public-intake` (lines 1-44):
  - namespace `auth-system` (line 5);
  - `konghq.com/plugins: public-intake-rate-limit` (line 13);
  - `ingressClassName: kong` (line 15);
  - host `web.local.humility.local` (line 21);
  - Prefix paths:
    - `/api/public/applications` (lines 24-30);
    - `/api/public/chapters` (lines 31-37);
    - `/api/applications` legacy (lines 38-44).

Required `(host, path)` tuples in `annotated_paths`:

- `("web.local.humility.local", "/api/public/applications")` —
  also reachable via `_web_submit_endpoint()`; either form is fine,
  but using the contract fixture keeps the canonical web submit path
  routed through one source.
- `("web.local.humility.local", "/api/public/chapters")`;
- `("web.local.humility.local", "/api/applications")` (legacy).

Required upload-url Prefix-coverage proof:
`"/api/public/applications/upload-url".startswith(parent_prefix)` must
hold for some annotated `(host, parent_prefix)` on
`web.local.humility.local`. The candidate parent prefix is
`/api/public/applications` (line 24).

### H7c — Coverage gap closed

The existing test at lines 105-116 currently asserts only three
tuples: `(web, /api/applications)`, `(web, _web_submit_endpoint())`,
`(api, /api/v1/public/applications)`. It misses
`/api/v1/public/chapters`, `/api/public/chapters`, and both
upload-url Prefix-coverage proofs. The audit gate identified this gap
explicitly (audit A2). The H7 extension closes it.

## H8 — Adjacent anti-list (TG-3)

Two distinct negative assertions per the proposal §2.3 / TG-3 and the
audit-gate A3 finding.

### H8a — Path-level negative on annotated public-intake Ingresses

For every Ingress whose
`metadata.annotations["konghq.com/plugins"] == "public-intake-rate-limit"`,
assert that none of the following appears in the Ingress's
`(host, path)` tuples:

- `/api/v1/web/`;
- `/auth/discord`;
- `/api/v1/health`;
- `/`.

This is forward-looking (audit F2): none of these paths is on any
annotated Ingress today, so the assertion is currently vacuous against
manifest reality. It catches a future commit that adds, e.g.,
`/api/v1/health` to the public-intake Ingress as a misplaced split or
typo. Failure message must name the offending host, path, and source
manifest — use the `_source_path` stamp from `_yaml_documents`.

### H8b — Ingress-level negative on catch-all Ingresses

This is the substantive check (non-vacuous against current manifests)
and is already at lines 118-136 of the existing test. Preserve it.
Assert that the catch-all Ingresses do not carry the
`public-intake-rate-limit` annotation:

- `web` Ingress (Pomerium catch-all on `web.local.humility.local`,
  path `/`);
- `protected-api` Ingress (Pomerium-fronted protected API);
- `server-manager-api` Ingress (authenticated catch-all on
  `api.local.humility.local`, path `/`).

The existing assertions at lines 134-136 cover these. Extend if and
only if a new catch-all surface is identified by reading current
manifests; do not invent surfaces.

## H9 — Required-files extension to `_local_resources()`

`infra/tests/test_public_intake_rate_limit.py:25-43`

The current `required` list (lines 34-37) covers only the two
public-intake-binding Ingress manifests. Add the four Kong-version
surfaces so a rename or move produces a loud `AssertionError` instead
of a silent skip:

- `gitops/channels/local/ingress/kong/README.md`;
- `gitops/channels/local/ingress/kong/kustomization.yaml`;
- `gitops/channels/local/ingress/kong/render-values.yaml`;
- `gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml`.

These files are not YAML-parsable as a single resource list (README is
markdown; `rendered/kong-3.2.0.yaml` is a 4000+-line multi-doc file
that should not be loaded into `_local_resources()` because that
helper expects per-resource Kubernetes objects). Either:

- Add a parallel `_local_kong_version_files()` helper that returns a
  dict of `{name: Path}` and drives the four version assertions in a
  single test function. Each version-pin assertion reads only the file
  it cares about, with the appropriate parser (text for README, single
  `safe_load` for kustomization.yaml + render-values.yaml, multi-doc
  `safe_load_all` for the rendered manifest). Each assertion carries
  a message naming the surface (audit F3).

Whichever shape the implementer picks, every newly required file path
must go through an `assert path.is_file(), f"..."` precondition so a
file rename produces a localized failure instead of an AttributeError
deep inside a parser.

## H10 — Failure-message convention (audit F3)

The existing test file uses bare `assert` consistently. For BL-014, add
explicit messages on **every version-pin assertion** so CI output names
the drifted surface unambiguously:

- "Kong Helm chart version drifted in README render command: expected
  `--version 3.2.0`, got ..." (H1);
- "Kong rendered manifest reference drifted in kustomization: expected
  `rendered/kong-3.2.0.yaml`, got ..." (H2);
- "Kong rendered chart label drifted on kong-kong Deployment: expected
  `helm.sh/chart: kong-3.2.0`, got ..." (H3);
- "Kong Gateway image drifted in render-values: expected `kong:3.9`,
  got ..." (H4a);
- "Kong Gateway image drifted on kong-kong Deployment: expected
  `kong:3.9`, got ..." (H4b);
- "KIC image drifted in render-values: expected
  `kong/kubernetes-ingress-controller:3.5`, got ..." (H5a);
- "KIC image drifted on kong-kong Deployment: expected
  `kong/kubernetes-ingress-controller:3.5`, got ..." (H5b);
- "Kong CRD bundle annotation drifted on KongPlugin CRD: expected
  `v1.5.2`, got ..." (H6).

For the route-set and anti-list assertions (H7, H8), the existing
`_source_path`-stamped failure pattern at lines 118-136 is sufficient;
keep the same idiom and ensure the message carries the offending host,
path, and source manifest.

## Out-of-scope reminders (do not implement)

From proposal §5 and the supported-surface gate:

- No live KIC translation smoke (deferred follow-up).
- No admission-webhook compatibility lane (local chart disables the
  webhook by design).
- No GitOps manifest mutation. The four Kong version files and the two
  public-intake Ingress files are read-only inputs.
- No production code, migration, or contract change.
- No new test file unless extending
  `test_public_intake_rate_limit.py` becomes materially less readable
  (proposal Q2). The expected outcome is one cohesive file under
  ~80 LOC of churn (proposal §6).

HOOKPOINTS_DONE: research/45-bl-014-hookpoints.md
