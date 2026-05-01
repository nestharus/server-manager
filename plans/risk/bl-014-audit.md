# BL-014 — Audit risk gate

**Verdict:** LOW

Scope: BL-014 — extend `infra/tests/test_public_intake_rate_limit.py`
with a static guard that locks Kong/KIC version surfaces, the
public-intake supported route set (including beta-1 chapters and
beta-3 upload-url Prefix coverage), and an adjacent anti-list of
non-public paths that must remain off the
`public-intake-rate-limit` annotation. The slice is YAML-only:
no production code, no GitOps manifest changes, no live KIC smoke.

The audit gate inspects: (1) version pins target the exact
Helm chart, Gateway image, and KIC image surfaces — not just the
plugin YAML; (2) the path-set assertions are exhaustive against
the current annotated Ingress manifests; (3) negative assertions
explicitly cover `/api/v1/web/`, `/auth/discord`, and
`/api/v1/health`; (4) failure messages name the specific drift
surface (chart vs image vs path) so drift is easy to localize;
(5) the test parses YAML structurally so reformatting does not
trip it.

Source proposal: `proposals/30-bl-014-kong-version-pin.md`.
Source problem map: `research/44-bl-014-kong-version-problem-map.md`.
Existing static guard: `infra/tests/test_public_intake_rate_limit.py`.

## A1 — Version pins target chart + Gateway image + KIC image as separate surfaces

**Surface (Q3, §2.3):** the proposal explicitly enumerates five
independent version-touching inputs and requires each to be a
separate test assertion:

- Helm chart version `3.2.0` — sourced from
  `gitops/channels/local/ingress/kong/README.md` (the documented
  `helm template ... --version 3.2.0` command).
- Rendered manifest reference `rendered/kong-3.2.0.yaml` —
  sourced from
  `gitops/channels/local/ingress/kong/kustomization.yaml:7`.
- Rendered chart label `helm.sh/chart: kong-3.2.0` — sourced
  from
  `gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml`
  (verified at lines 3406, 3418, 3872, 3894, 3965, 3987, 4004,
  4019, 4049, 4072).
- Kong Gateway image tag `kong:3.9` — sourced from
  `render-values.yaml:13-16` (`image.tag: "3.9"`) and rendered at
  `kong-3.2.0.yaml:4087, 4259`.
- KIC image tag `kong/kubernetes-ingress-controller:3.5` —
  sourced from `render-values.yaml:45-49`
  (`ingressController.image.tag: "3.5"`) and rendered at
  `kong-3.2.0.yaml:4221`.

This satisfies the gate criterion "exact Helm chart version +
Gateway image + KIC image surfaces (not just the plugin YAML)."
The problem map's distinction between chart `3.2.0` (a Helm
artifact) and the Gateway runtime image `kong:3.9` is preserved
in the proposal, with separate assertions.

**Coverage of compatibility inputs:** the rendered chart label
appears at least 10 times in `kong-3.2.0.yaml`. The proposal
locks the label as a single value to assert; checking any one
occurrence is sufficient since the label is set once in the
chart values. No need to scan all occurrences.

**Verdict:** Three surfaces are independently locked, with
chart version pinned at three reflection points (README, kustomization
reference, rendered label) so a partial bump cannot slip through.
Audit risk LOW for A1, with one finding (F1) on the CRD bundle
annotation that the problem map identified but the proposal omits
from the locked surface list.

## A2 — Path-set assertions are exhaustive against current annotated Ingress manifests

**Annotated Ingress source-of-truth:**

`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`
(`server-manager-public-intake-api`, namespace `server-manager`,
`konghq.com/plugins: public-intake-rate-limit`):

- `/api/v1/public/applications` (Prefix)
- `/api/v1/public/chapters` (Prefix)

`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`
(`web-public-intake`, namespace `auth-system`, same plugin
annotation):

- `/api/public/applications` (Prefix)
- `/api/public/chapters` (Prefix)
- `/api/applications` (Prefix, legacy)

**Proposal-locked supported route set (Q3 §2.3 + TG-2):**

- Direct API (literal annotated paths):
  `/api/v1/public/applications`, `/api/v1/public/chapters`.
- Direct API (Prefix-covered child):
  `/api/v1/public/applications/upload-url` — proven by Prefix
  coverage of `/api/v1/public/applications`.
- Pomerium/web (literal annotated paths):
  `/api/public/applications`, `/api/public/chapters`,
  `/api/applications`.
- Pomerium/web (Prefix-covered child):
  `/api/public/applications/upload-url` — proven by Prefix
  coverage of `/api/public/applications`.

Cross-checking the proposal's literal-path list against the two
manifests shows 5/5 literal annotated paths represented, and the
two upload-url Prefix-children are explicitly tested as
*Prefix-covered* rather than asserted as standalone Ingress
paths. This is the right model: the BL-010 β-3 upload-url
endpoints are not separate Ingress entries
(verified — only the two `*-rate-limit.yaml` files contain
`konghq.com/plugins`), and the proposal does not pretend they
are.

**Beta-1 chapter coverage:** the existing test
(`test_public_intake_plugin_is_bound_only_to_public_submit_paths`,
lines 91–116) asserts `/api/applications`,
`_web_submit_endpoint()` (which resolves to
`/api/public/applications` via the web contract fixture), and
`/api/v1/public/applications`. It does **not** currently assert
`/api/v1/public/chapters`, `/api/public/chapters`, or any
upload-url Prefix coverage. The proposal's TG-2 acceptance
criteria add all of these, closing the gap the problem map
flagged ("route topology drifts so beta-1 chapter paths or
beta-3 upload-url coverage are no longer represented").

**Verdict:** The proposal's locked path set covers every
literal annotated path in current manifests and explicitly
proves upload-url child coverage through Prefix-parent
matching. The existing test's coverage gap on beta-1 chapters
and beta-3 upload-url is closed by TG-2. Audit risk LOW for A2.

## A3 — Anti-list explicitly excludes /api/v1/web/, /auth/discord, /api/v1/health

**Proposal anti-list (Q3 §2.3, TG-3):**

- `/api/v1/web/`
- `/auth/discord`
- `/api/v1/health`
- `/`
- "any protected or authenticated API catch-all path already
  represented by the local GitOps manifests"

The three gate-required paths — `/api/v1/web/`, `/auth/discord`,
`/api/v1/health` — are all present.

**Two-form anti-list discipline:** the proposal locks two
distinct negative assertions, both of which are useful:

1. **Path-level:** the listed anti-paths must not appear as
   `path:` entries on any Ingress whose annotation is
   `public-intake-rate-limit` (TG-3 acceptance: "annotated
   public-intake Ingresses do not include `/api/v1/web/`,
   `/auth/discord`, `/api/v1/health`, `/`, or other catch-all
   paths").
2. **Ingress-level:** the existing catch-all Ingress resources
   (`web`, `protected-api`, `server-manager-api`) must remain
   *unannotated* with `public-intake-rate-limit` (TG-3
   acceptance: "the existing catch-all Ingress resources for
   `web`, `protected-api`, and authenticated `server-manager-api`
   remain unannotated"). This second form is already in the
   existing test (lines 118–136) and the proposal preserves it.

**Existing-manifest reality check:** in current local manifests,
none of the three anti-list paths appears as a discrete
Ingress `path:` entry (verified by reading `api-ingress.yaml`
and `ingress.yaml`; both catch-alls use only `path: /`). The
path-level negative assertion is therefore a *forward-looking
drift guard* — it catches a future commit that adds, e.g.,
`/auth/discord` to the public-intake-rate-limit Ingress as a
typo or scope creep. The Ingress-level negative assertion
catches the inverse drift (someone slapping the plugin
annotation onto a catch-all). Both directions are needed.

**Verdict:** All three gate-required paths are explicitly named
in the anti-list, and the proposal locks both path-level and
Ingress-level negative assertions. Audit risk LOW for A3, with
one observation (F2) that the path-level negatives are
forward-looking against current manifests but still useful for
drift defense.

## A4 — Failure messages name the specific drift surface

**Path-level drift messaging (TG-3 acceptance):** the proposal
explicitly requires "failures name the offending host/path and
source manifest so drift is easy to correct." This satisfies
the gate criterion for path drift.

**Version-level drift messaging:** the proposal §4 TG-1
acceptance lists each surface separately ("the Helm chart render
command/reference remains `3.2.0`", "the kustomization still
references `rendered/kong-3.2.0.yaml`", "the rendered chart
label remains `helm.sh/chart: kong-3.2.0`", "the Gateway image
remains `kong:3.9`", "the KIC image remains
`kong/kubernetes-ingress-controller:3.5`"), which implies one
assertion per surface but does **not** explicitly require an
assertion message string identifying which surface drifted. With
bare-`assert` Python and pytest's expression introspection,
failures will report the failing comparison
(e.g., `assert "3.9" == "3.10"`), which usually localizes drift
through the surrounding test name and traceback — but the gate
criterion is satisfied more cleanly if each version-pin assert
carries an explicit message naming the surface.

The existing test file uses bare `assert` consistently
(lines 82–88 etc.) without messages, so the proposed extension
will inherit that style unless the implementation deliberately
adds messages.

**Verdict:** Path-level drift messaging is locked. Version-level
drift messaging is implicitly localizable via separate test
cases and pytest introspection but not contractually required by
the proposal. Audit risk LOW for A4, with one finding (F3) that
the proposal should explicitly require each version-pin assert
to carry a message naming the surface (chart vs Gateway image vs
KIC image vs rendered label vs kustomization reference) so the
common "image bump" diff failure is unambiguous.

## A5 — Test parses YAML structurally, not regex string-match

**Existing parser (verified):**
`infra/tests/test_public_intake_rate_limit.py:16-22`:

```python
def _yaml_documents(path: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if isinstance(document, dict):
            document["_source_path"] = str(path.relative_to(REPO_ROOT))
            docs.append(document)
    return docs
```

All existing assertions in the file walk the parsed dict
structure (`resource.get("kind")`, `_metadata(resource)`,
`_ingress_paths(resource)`, etc.) and compare YAML *values*,
not source-text regex matches. The proposal §3 says "Add static
assertions for the Kong Helm chart version, rendered manifest
reference, Gateway image tag, and KIC image tag" without
mandating a parse strategy, but the pre-existing helpers
naturally extend the YAML-structural pattern.

**Per-surface parse fitness:**

| Surface | Source | Structural? |
|---|---|---|
| Helm chart version `3.2.0` | `README.md` (markdown code block) | No — necessarily string match in the helm command line |
| Rendered manifest reference | `kustomization.yaml` `resources` list | Yes — list of strings under `resources:` |
| Rendered chart label | `kong-3.2.0.yaml` per-resource `metadata.labels.helm.sh/chart` | Yes — pick any KongPlugin/Deployment doc and read the label |
| Gateway image | `render-values.yaml` `image.tag` | Yes — scalar under `image.tag` |
| KIC image | `render-values.yaml` `ingressController.image.tag` | Yes — scalar under nested key |

Four of five surfaces are YAML-structural. The README pin is
the only string-based check, and that is unavoidable: the
chart version lives in a documented `helm template` command
inside a markdown code fence, not in a YAML field. A regex on
the helm command (e.g., `--version (\d+\.\d+\.\d+)`) is the
right shape; the proposal's TG-1 acceptance ("the Helm chart
render command/reference remains `3.2.0`") implicitly accepts a
text scan on the command line.

**Reformatting safety:** for the four YAML-structural surfaces,
reformatting (re-indentation, comment changes, key reordering)
will not trip the test because `yaml.safe_load` normalizes
structure. For the README surface, reformatting risk is bounded
to the helm command line itself — and changing that command
line is the exact drift the test is meant to catch.

**Verdict:** Parsing strategy is YAML-structural for the four
machine-readable surfaces and necessarily textual for the
README command pin. The mix matches the underlying source
formats correctly; reformatting cannot trip the YAML asserts,
and the README assert breaks only when the helm command itself
changes (which is the desired sensitivity). Audit risk LOW for
A5.

## A6 — Cross-namespace plugin binding is locked as YAML-shape only

**Existing pattern (verified):**

- `KongPlugin` named `public-intake-rate-limit` exists only in
  namespace `server-manager`
  (`public-intake-rate-limit.yaml:1-12`).
- `web-public-intake` Ingress in namespace `auth-system`
  references the plugin via
  `konghq.com/plugins: public-intake-rate-limit`
  (no namespace prefix, no `KongClusterPlugin` declaration).

The problem map flagged this explicitly:
"The only `KongPlugin` resource found by the current static
test is in `server-manager` ... while the web annotated
Ingress is in `auth-system`. A live KIC smoke should prove
that the deployed controller resolves the web-side annotation
as intended."

**Proposal posture (Q1, §5 anti-scope):** the slice is a
static-only guard. The proposal explicitly defers the live KIC
translation smoke to a follow-up. The proposal locks the
*current* binding pattern (Q3 §2.3): "`web-public-intake`
remains an Ingress in namespace `auth-system` with
`ingressClassName: kong` and annotation
`konghq.com/plugins: public-intake-rate-limit`."

This is an honest scope: the static guard catches drift in the
manifest shape but cannot prove that KIC `3.5` actually resolves
`public-intake-rate-limit` in `auth-system` to the
`server-manager`-namespaced plugin. If the deployed KIC requires
either a `KongClusterPlugin` or a `<namespace>/<name>` reference
form, the current manifests may already be silently broken on
the web side — the static guard would not catch that.

**Verdict:** The proposal correctly identifies its own limit
("It does not prove live KIC route/plugin translation behavior"
— §1, last paragraph) and explicitly defers the cross-namespace
resolution check to a future live smoke. The risk is correctly
boxed and named. Audit risk LOW for A6, with one
forward-looking finding (F4) that the live KIC smoke must
specifically validate the web-side cross-namespace resolution,
not just the API-side same-namespace case.

## Findings

### F1 — CRD bundle annotation is in the problem map but missing from the proposal's locked surfaces

**Severity:** medium-low (completeness; missing compatibility input).

**Where:** proposal §2.3 ("Lock the Kong version-touching
surfaces") and the proposed test extension in
`infra/tests/test_public_intake_rate_limit.py`.

**Risk:** the problem map (lines 38–50) lists the CRD bundle
annotation as a separate compatibility input:

> | CRD bundle version annotation |
> `kubernetes-configuration.konghq.com/version: v1.5.2` |
> `gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml:1690-1694`
> for `KongPlugin` |

A future Kong/KIC bump can change the CRD bundle independently
of the chart version (e.g., the chart pulls in
`v1.6.0` CRDs while the chart number stays at `3.2.0` for a
patch release). The CRD schema is what defines whether the
local `KongPlugin` manifest's `plugin: rate-limiting` and
`config:` shape stays valid. The proposal locks the manifest
file reference (`rendered/kong-3.2.0.yaml`) but does not lock
the CRD bundle version inside that file as a separate
assertion.

**Action:** add a fifth version-pin assertion that walks the
rendered manifest, finds a `KongPlugin` CRD definition (or any
resource carrying `kubernetes-configuration.konghq.com/version`),
and asserts the bundle version is exactly `v1.5.2`. This costs
~5 lines and closes the missing compatibility input the problem
map identified.

### F2 — Anti-list path negatives are forward-looking against current manifests

**Severity:** low (observation, not blocker).

**Where:** TG-3 path-level negative assertions in the proposed
test extension.

**Risk:** none of `/api/v1/web/`, `/auth/discord`, or
`/api/v1/health` appears as a discrete `path:` entry in any
local Ingress today. They are served via the `/` Prefix
catch-alls on `web`, `protected-api`, and the authenticated
`server-manager-api` Ingresses. Asserting that they are *not*
present on the public-intake-annotated Ingresses is therefore
a tautology against current manifests — it succeeds vacuously
because none of those paths is on any Ingress at all.

This is still a useful guard: it catches a future commit that
adds, e.g., a discrete `/api/v1/health` rule to the
public-intake Ingress (likely as scope-creep "convenience" or
a misplaced split). But the audit gate criterion as stated
("anti-list tests assert ... NOT in the plugin annotation")
is satisfied more meaningfully by the *Ingress-level* negative
the existing test already runs (catch-all Ingresses do not
carry the annotation), which is non-vacuous against current
manifests.

**Action:** keep both forms — the path-level assertion is a
forward-looking drift guard that costs ~5 lines and catches a
real failure mode. Document in the test (or the proposal) that
the path-level form is forward-looking and the Ingress-level
form is the substantive check.

### F3 — Version-pin asserts should carry messages naming the surface

**Severity:** low (developer-experience; drift localization).

**Where:** the new TG-1 assertions added to
`test_public_intake_rate_limit.py`.

**Risk:** the existing test file uses bare `assert` consistently
(no message strings). If the proposed extension follows that
style for five separate version pins, a failure
(e.g., `assert tag == "3.9"` failing because someone bumped to
`kong:3.10`) will report the value mismatch via pytest
introspection and the test function's name, but will not
explicitly say "Kong Gateway image tag drifted." A reviewer
diagnosing CI red usually wants the surface name in the
assertion message so they can immediately see whether the
chart, the Gateway image, the KIC image, the kustomization
reference, or the rendered chart label drifted.

The gate criterion ("Failure messages name the specific drift
(chart vs image vs path)") is technically satisfiable through
distinct test functions per surface plus pytest introspection,
but adding explicit messages is the cheapest way to make
failures unambiguous in CI logs.

**Action:** add an `assert ..., f"<surface> drifted: expected
<expected>, got <actual>"` message to each version-pin
assertion (or split each surface into its own test function
with a descriptive name). One extra string per assertion.

### F4 — Future live KIC smoke must specifically validate cross-namespace web-side binding

**Severity:** low (forward-looking; outside this slice's scope).

**Where:** the deferred live KIC translation smoke (proposal §5
anti-scope; problem map "smallest test that catches the BL-014
risk").

**Risk:** the static guard locks the current YAML pattern in
which `web-public-intake` (in `auth-system`) carries the
annotation `konghq.com/plugins: public-intake-rate-limit` while
the only `KongPlugin` named `public-intake-rate-limit` lives in
`server-manager`. KIC's annotation resolution rules for
non-namespaced references are version-dependent: in some
versions, the controller resolves the reference within the
Ingress's namespace only (which would *fail* to find the plugin
on the web side), and in others it falls back to a cluster-wide
search (which would *succeed*). The static guard cannot
distinguish these cases.

If the cross-namespace resolution is silently broken on KIC
`3.5`, the web-side public intake is not actually rate-limited
in production despite passing every static check.

**Action:** when the deferred live KIC smoke lands as a
follow-up slice, ensure it *specifically* probes the web-side
binding (not just the API-side same-namespace binding) — e.g.,
by hitting `/api/public/applications` 6 times in a minute and
asserting the 6th returns 429. If the smoke reveals the
cross-namespace pattern is broken, the fix is to either
(a) introduce a `KongClusterPlugin` form, (b) duplicate the
plugin into `auth-system`, or (c) switch the annotation form to
`server-manager/public-intake-rate-limit`. All three are
out-of-scope for this slice; the audit notes the dependency so
the BL-014 effort cannot ship the static guard alone and call
the assumption verified.

## Verdict reasoning

BL-014 holds the audit gate at LOW risk:

- **Version surfaces (A1):** chart `3.2.0`, rendered reference
  `rendered/kong-3.2.0.yaml`, rendered label
  `helm.sh/chart: kong-3.2.0`, Gateway image `kong:3.9`, and
  KIC image `kong/kubernetes-ingress-controller:3.5` are all
  locked as separate assertions sourced from independent files.
  F1 flags the missing CRD bundle annotation
  (`kubernetes-configuration.konghq.com/version: v1.5.2`) that
  the problem map identified.
- **Path-set exhaustiveness (A2):** the proposal's locked route
  set covers every literal annotated path in current local
  manifests (5/5) and explicitly proves upload-url Prefix
  coverage for both `/api/v1/public/applications/upload-url`
  and `/api/public/applications/upload-url`. Beta-1 chapter
  paths and beta-3 upload-url coverage gaps in the existing
  test are closed by TG-2.
- **Anti-list (A3):** all three gate-required paths
  (`/api/v1/web/`, `/auth/discord`, `/api/v1/health`) plus
  `/` and "other catch-all paths" are explicitly named. Both
  path-level and Ingress-level negative forms are locked. F2
  is a low-severity observation that the path-level form is a
  forward-looking drift guard rather than a substantive check
  against current manifests.
- **Failure messaging (A4):** path-level drift messaging is
  contractually required by TG-3. Version-pin drift messaging
  is implicitly localizable through pytest introspection but
  F3 recommends explicit message strings for unambiguous CI
  signal.
- **Structural parsing (A5):** four of five version surfaces
  are YAML-structural via the existing `_yaml_documents`
  helper. The README chart-version pin is necessarily textual
  because the chart version lives in a markdown helm-command
  code block; this is unavoidable and reformatting-risk-bounded
  to the helm command line itself.
- **Cross-namespace binding (A6):** the proposal correctly
  identifies its own limit ("does not prove live KIC route/
  plugin translation") and defers the cross-namespace
  resolution validation to a follow-up live smoke. F4 flags
  the dependency: the live smoke must specifically exercise
  the web-side `auth-system` → `server-manager` plugin
  resolution.

The slice is YAML-only, ~80 LOC, no production code, no GitOps
manifest changes. All five gate criteria are met with
acceptable scope and explicit limits. Findings F1–F4 are
correctness/completeness improvements, not blockers.

Verdict: LOW.

AUDIT_DONE: plans/risk/bl-014-audit.md
