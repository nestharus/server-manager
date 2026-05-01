# BL-014 — Shortcut risk gate (Kong version pin static guard)

**Verdict:** MEDIUM

Scope: BL-014 — protect INIT-120 AS-5's assumption that Kong attaches the
`public-intake-rate-limit` plugin only to the public intake routes by adding
a static, always-on guard that fails on Kong/KIC version drift, public-intake
binding-pattern drift, route-set drift, and adjacent-protected-path bleed.
Proposal 30 chooses Q1 = static YAML-only guard (live KIC translation smoke
is anti-scoped to a future slice), Q2 = extend
`infra/tests/test_public_intake_rate_limit.py` rather than create a new file,
and Q3 = lock chart `3.2.0`, Gateway `kong:3.9`, KIC
`kong/kubernetes-ingress-controller:3.5`, the rendered file reference, the
`helm.sh/chart` label, the binding pattern (per-Ingress
`konghq.com/plugins: public-intake-rate-limit`), the supported route set
(including upload-url Prefix coverage), and an adjacent anti-list.

The shortcut gate inspects whether the slice (1) parses YAML with
`yaml.safe_load`/`safe_load_all` for the version surfaces rather than doing
naive substring scans on raw file text, (2) actually pins all four version
surfaces — Helm chart, Kong Gateway image, KIC image, and the CRD bundle
version when applicable — rather than a subset, (3) covers both the
server-manager-side YAML
(`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`)
and the pomerium-side YAML
(`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`) for
the binding-pattern and route-set assertions, and (4) avoids "TODO: extend
later" stubs in the test code.

Source: `proposals/30-bl-014-kong-version-pin.md`,
`research/44-bl-014-kong-version-problem-map.md`,
`infra/tests/test_public_intake_rate_limit.py`,
`gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml`,
`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`,
`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`.

## C1 — Real YAML parse, not substring scan

**Pass with a caveat.**

The proposal extends an existing test file
(`infra/tests/test_public_intake_rate_limit.py`) that already parses every
manifest it touches with `yaml.safe_load_all` — `_yaml_documents` at line 18
streams documents through `yaml.safe_load_all`, and every existing assertion
walks structured `metadata`, `spec.rules`, and `annotations` dicts rather
than running text matches over raw file bytes. By choosing Q2 = "extend the
existing file" (proposal lines 64-77), the new BL-014 assertions inherit
that idiomatic shape; a substring grep over a YAML buffer would visibly
clash with the surrounding helpers. The shape that the proposal asks for —
"both public-intake Ingresses use per-Ingress
`konghq.com/plugins: public-intake-rate-limit`", "annotated literal `Prefix`
paths include …", and "`/api/public/applications/upload-url` is under
annotated `/api/public/applications`" (proposal lines 191-201) — is
expressible only against parsed `spec.rules[].http.paths[].path` lists with
`pathType == "Prefix"`, not via substring scans.

For the version-pin surfaces specifically, the proposal lists four
version-touching files (proposal lines 90-96):

- `gitops/channels/local/ingress/kong/README.md`
- `gitops/channels/local/ingress/kong/kustomization.yaml`
- `gitops/channels/local/ingress/kong/render-values.yaml`
- `gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml`

Three of these four are YAML and can/should go through `yaml.safe_load`:

- `kustomization.yaml` exposes the rendered file reference as a structured
  `resources:` list entry — a YAML parse can pluck the entry rather than
  string-matching `rendered/kong-3.2.0.yaml` anywhere in the file.
- `render-values.yaml` exposes both the Gateway image (`image.repository`
  and `image.tag`) and the KIC image (`ingressController.image.repository`
  and `.image.tag`) as structured Helm-values keys; a YAML parse asserts
  the exact keypaths rather than substring-matching `kong:3.9`, which would
  also collide with the rendered manifest's mentions of the same string.
- `rendered/kong-3.2.0.yaml` is a multi-document YAML; the
  `helm.sh/chart: kong-3.2.0` label lives at structured
  `metadata.labels."helm.sh/chart"` on every chart-emitted resource, the
  Gateway image lives at structured `spec.template.spec.containers[].image`
  on the proxy Deployment, and the KIC image lives at the same path on the
  controller Deployment. The existing `_yaml_documents` helper already
  yields these as parsed dicts.

The caveat is `README.md`, which is markdown, not YAML. The proposal's
Q3 line 91 lists the README's render command (`kong/kong --version 3.2.0`)
as a version-touching surface. That surface is not YAML and cannot be
parsed with `yaml.safe_load`; if the implementation exercises it, it will
necessarily be a substring or regex check. This is appropriate for that
specific surface (a markdown render command is not parseable structure)
and does not undercut the YAML-parse pattern for the three actual YAML
surfaces — but the proposal could be clearer that the README check is the
one substring-allowed assertion and the other three go through structured
parse.

**Risk:** the natural shortcut would be (a) implement all version-pin
checks as `assert "kong:3.9" in path.read_text()` substring scans across
the four files, which would silently pass for any version string that
happens to appear anywhere in the file (e.g., a comment), or (b) drop the
existing `_yaml_documents` helper for the new code and read raw text,
diverging from the test file's idiom and inviting future drift.

**Mitigation:** the test file already routes every manifest read through
`yaml.safe_load_all` and all existing assertions walk parsed dicts; the
new assertions about path lists, annotation maps, and rendered chart
labels have no natural shortcut to a substring scan because they need
structural fields (pathType, host, namespace, kind). The version-pin
checks should land on the same parsed-dict path. The README markdown
surface is the one acceptable substring exception.

**Verdict:** Not a shortcut for the structural assertions; the README
line is a defensible substring exception, not a shape regression.

## C2 — All four version surfaces pinned (chart, gw image, KIC image, CRD bundle)

**Partial fail — CRD bundle missing.**

The shortcut gate calls out four version surfaces. Mapping each to the
proposal:

- **Helm chart version `3.2.0`.** Pinned three ways (proposal lines
  84-86): the chart version itself, the rendered file reference
  `rendered/kong-3.2.0.yaml`, and the rendered chart label
  `helm.sh/chart: kong-3.2.0`. **Pinned.**
- **Kong Gateway image `kong:3.9`.** Pinned (proposal line 87) and
  reinforced in TG-1 (proposal line 177). **Pinned.**
- **KIC image `kong/kubernetes-ingress-controller:3.5`.** Pinned
  (proposal line 88) and reinforced in TG-1 (proposal line 178).
  **Pinned.**
- **CRD bundle version `v1.5.2`.** **Not pinned.** The research file
  identifies this surface as a separate compatibility input
  (research/44 lines 48 and 190-191: "Treat Helm chart version, Gateway
  image tag, KIC image tag, and CRD bundle as separate compatibility
  inputs."). The CRD bundle annotation
  `kubernetes-configuration.konghq.com/version: v1.5.2` exists today on
  every chart-rendered CRD in `rendered/kong-3.2.0.yaml` (verified at
  lines 8, 66, 374, 626, 905, … of the rendered manifest). The proposal's
  Q3 surface list (lines 84-88) drops it without anti-scoping it in
  Section 5, and the TG-1 acceptance list (lines 169-178) does not
  mention it.

This is a real gap. The shortcut question hedges with "if applicable" —
the CRD bundle *is* applicable here: it is the schema version that
governs how `KongPlugin`, `KongClusterPlugin`, and Ingress-attached
plugin annotations are validated by KIC at apply time. A future chart
bump that holds the gateway and KIC image versions steady but advances
`kubernetes-configuration.konghq.com/version` to a release that retires
or rewrites a `KongPlugin` field would translate to a silent change in
which annotations the controller honors. The research document called
this out as failure scenario #4 ("KongPlugin CRD or rate-limiting
schema changes"). The proposal asserts five surfaces (counting the
chart-version triple as one bucket plus gateway plus KIC) but
specifically the CRD bundle annotation that research flagged is
silently omitted. Whether by oversight or deliberate compression, it is
shortcut-shaped.

The other surfaces relevant to BL-014 — admission webhook disabled
(`render-values.yaml:52-53`), KIC controller mode `CONTROLLER_INGRESS_CLASS=kong`,
DB-less / traditional router mode — are likewise present in the
research's "version-touching surfaces" table but absent from the
proposal. Of those, only the CRD bundle is named in the shortcut gate
question itself, so the others are noted in passing rather than scored.

**Risk:** the natural shortcut is (a) call "chart 3.2.0 + gateway
kong:3.9 + KIC 3.5" the full version surface list and ship the slice
without ever reading the CRD bundle annotation, leaving silent CRD
schema bumps unguarded; or (b) note CRD as anti-scope in Section 5
without justification, which is what BL-012's anti-scope sections do
correctly for live KIC smoke but is *not* done here for CRD.

**Mitigation:** none in the current proposal. The CRD bundle gap is
real. Closing the gap is a small extension — one extra assertion that
walks `rendered/kong-3.2.0.yaml` for resources of `kind: CustomResourceDefinition`
(or any kind with the annotation), pulls
`metadata.annotations["kubernetes-configuration.konghq.com/version"]`,
and asserts the value is exactly `v1.5.2`. It fits the same parsed-dict
shape as the other version assertions and stays inside the
"~80 line" diff budget (proposal line 240). The proposal should either
add this assertion or anti-scope the CRD bundle explicitly with stated
reasoning, the way BL-012 anti-scopes the matrix runner.

**Verdict:** Shortcut-shaped at the CRD bundle surface. Three of the
four named surfaces are pinned; the fourth — the one research
specifically flagged — is silently dropped without anti-scoping.

## C3 — Both server-manager-api and pomerium-proxy YAMLs covered

**Pass.**

The proposal explicitly names both manifests as test inputs (Q3,
proposal lines 100-105):

> - `server-manager-public-intake-api` remains an Ingress in namespace
>   `server-manager` with `ingressClassName: kong` and annotation
>   `konghq.com/plugins: public-intake-rate-limit`;
> - `web-public-intake` remains an Ingress in namespace `auth-system`
>   with `ingressClassName: kong` and annotation
>   `konghq.com/plugins: public-intake-rate-limit`;

TG-2 (proposal lines 184-201) names both files explicitly:

> pytest reads
> `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`
> and `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`;
> both public-intake Ingresses use per-Ingress
> `konghq.com/plugins: public-intake-rate-limit`;
> annotated literal `Prefix` paths include:
> `/api/v1/public/applications`, `/api/v1/public/chapters`,
> `/api/public/applications`, `/api/public/chapters`, and legacy
> `/api/applications`;

Direct API side paths
(`/api/v1/public/applications`, `/api/v1/public/chapters`,
`/api/v1/public/applications/upload-url`) and pomerium/web side paths
(`/api/public/applications`, `/api/public/chapters`,
`/api/public/applications/upload-url`, legacy `/api/applications`) are
both enumerated in the supported route set (proposal lines 113-121).
The upload-url Prefix-coverage check applies on both sides
(proposal lines 197-201). The adjacent anti-list also covers both sides
via the existing `web` (web side) and `protected-api` /
`server-manager-api` (server-manager side) catch-all assertions
(proposal lines 128-135 + TG-3 at lines 207-215).

The existing test file at `infra/tests/test_public_intake_rate_limit.py:25-43`
already loads YAML from both
`LOCAL_GITOPS / "applications" / "server-manager"` and
`LOCAL_GITOPS / "auth" / "pomerium"`, with explicit `required` paths
asserting both `pomerium/ingress.yaml` and
`server-manager/api-ingress.yaml` exist, so the BL-014 additions
inherit a loader that already reads both directories. The research
document independently confirms this dual-side coverage at
research/44 lines 22-34, 65-74.

**Risk:** the natural shortcut would be (a) cover only the
server-manager-side `KongPlugin` and Ingress, since the only `KongPlugin`
resource lives in the `server-manager` namespace — which research
explicitly calls out as a "namespace wrinkle" worth validating (research
lines 80-86), so a casual implementation could mistakenly assume the
plugin is only relevant on the server-manager side and skip the
pomerium-side Ingress; or (b) cover only the pomerium-side, since the
INIT-120 AS-5 assumption is most user-visible on
`web.local.humility.local`.

**Mitigation:** the proposal names both file paths in TG-2, lists both
Ingresses in Q3 (with namespaces), enumerates both path families in the
supported route set, and the existing test loader already reads both
directories. Both the positive (annotated path) and negative (catch-all
unannotated) assertions exist on each side.

**Verdict:** Not a shortcut; both sides are covered by exact-path
assertions on parsed YAML.

## C4 — No "TODO: extend later" stubs

**Partial pass.**

The proposal handles the live KIC translation smoke deferral cleanly:
it is anti-scoped in Section 5 (proposal lines 219-221), with stated
reasoning back at Q1 (proposal lines 53-57):

> The problem map identifies live KIC translation smoke as the smallest
> test that catches the deepest BL-014 runtime risk, but that lane has
> higher CI cost and requires an ephemeral Kong/KIC fixture. For this
> BL-014 slice, keep the always-on regression test static and defer
> live translation smoke to a separate follow-up when CI capacity
> surfaces.

This is the same shape BL-012 used to anti-scope its matrix runner: the
deferred work is named, the reasoning is explicit, and there is no
placeholder stub left in the test code that some future reader has to
expand or delete. Section 5 also explicitly says "Do not introduce
compatibility shims, alternate binding patterns, feature flags, or dual
support for old/new KongPlugin attachment styles" (proposal lines
232-235), which forecloses a different stub-shape (a flagged
half-implementation of a new binding pattern). Q2 also closes off a
separate-file stub: "Do not add `infra/tests/test_kong_version_pin.py`
in this slice unless the implementation finds that the existing file
becomes materially harder to read." (proposal lines 74-76). That is a
conditional, not a TODO.

The remaining concern is the same surface as C2: the CRD bundle. The
research document explicitly calls out the CRD bundle as a separate
compatibility input (research lines 48, 188-192) and as failure
scenario #4 (research lines 108-111). The proposal silently drops it
from Q3's locked surfaces and from TG-1's acceptance list. Without a
sentence in Section 5 that explicitly anti-scopes "do not pin the CRD
bundle annotation in this slice; the CRD bundle compatibility risk is
[reason] and is tracked separately at [follow-up]," the omission reads
as an implicit "extend later" stub: research said do it, the proposal
silently chose not to, and there is no record of why or where that
work re-enters the queue. That matches the pattern this gate is
designed to flag — research-identified work that gets quietly dropped
from a slice scope without an explicit anti-scope decision and a
follow-up pointer.

This is softer than a literal "# TODO: pin CRD later" comment in test
code, but it is the same failure mode in proposal form: a known surface
that research validated as relevant, dropped from the slice without a
named owner or named follow-up.

**Risk:** the natural shortcut is (a) leave the CRD bundle out of both
Q3 and Section 5, so the next reviewer cannot tell whether the omission
was deliberate or an oversight, and the CRD compatibility risk lives
between proposals; or (b) drop a `# TODO: lock CRD bundle once we
decide on cadence` comment in the test code, which would invite a
follow-up that may or may not happen.

**Mitigation:** none in the current proposal for the CRD bundle. For
the live KIC smoke, the mitigation is correct: the deferral is anti-
scoped with stated reasoning. The CRD bundle deserves the same
treatment — either pin it in this slice (small extra assertion, fits
the diff budget) or anti-scope it in Section 5 with a stated reason
and a follow-up pointer.

**Verdict:** Partial. Live-smoke deferral is clean; CRD bundle
omission is implicit-stub-shaped.

## Verdict reasoning

BL-014 mostly fits the contour the gate watches for, with one
identified gap:

- The new assertions ride on a test file that already parses every
  manifest with `yaml.safe_load_all` and walks structured dicts. The
  shapes the proposal asks for (per-Ingress annotation maps, Prefix
  path lists with structured `pathType`, host-keyed rule sets, parsed
  rendered `helm.sh/chart` labels and container `image` fields) have
  no natural substring-scan shortcut. The one surface that legitimately
  cannot be YAML-parsed is the README markdown render command, which
  is appropriate.

- Three of the four named version surfaces are pinned: Helm chart
  `3.2.0` (in three forms), Kong Gateway image `kong:3.9`, and KIC
  image `kong/kubernetes-ingress-controller:3.5`. The fourth — the CRD
  bundle annotation `kubernetes-configuration.konghq.com/version:
  v1.5.2` — is identified by the research document as a separate
  compatibility input and as a named failure scenario, but is silently
  absent from both Q3's surface list and TG-1's acceptance list, and
  is not anti-scoped in Section 5. This is the central shortcut on the
  proposal.

- Both the server-manager-side YAML (Ingress
  `server-manager-public-intake-api` in namespace `server-manager`,
  paths under `/api/v1/public/...`) and the pomerium-side YAML
  (Ingress `web-public-intake` in namespace `auth-system`, paths
  under `/api/public/...` plus legacy `/api/applications`) are
  exercised. The existing test loader already reads both directories,
  the proposal names both files explicitly in TG-2, and both positive
  (annotated path) and negative (catch-all unannotated) assertions
  apply on each side.

- The live KIC translation smoke is correctly anti-scoped with stated
  reasoning, no stub left behind in test code. Compatibility shims and
  dual-binding patterns are explicitly forbidden. The new-test-file
  alternative is conditional, not a deferred TODO. The one gap is
  again the CRD bundle: dropped from scope without anti-scoping
  reasoning, leaving the surface in implicit-extend-later limbo.

The slice is appropriately small (proposal §6 caps total churn at
~80 lines, no production code, no GitOps changes), runs on the right
lane for static drift coverage (extends the existing always-on
public-intake guard), correctly defers live KIC smoke to a follow-up
slice with explicit reasoning, and covers both sides of the
public-intake Ingress shape. The single concrete shortcut is the
silent omission of the CRD bundle annotation from the version-pin
surface list, which the research file specifically flagged as a
separate compatibility input. Closing the gap is a small extension
that fits the diff budget; alternatively, anti-scoping it in
Section 5 with stated reasoning and a follow-up pointer would
match the pattern the proposal already uses correctly for live KIC
smoke.

Verdict: MEDIUM. Three of four checks pass cleanly; the CRD bundle
omission is shortcut-shaped and should be either pinned in this
slice or explicitly anti-scoped before implementation.

SHORTCUT_DONE: plans/risk/bl-014-shortcut.md
