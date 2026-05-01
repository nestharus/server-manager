# BL-014 Scope risk gate

Verdict: **PASS**

Reviewed:

- `proposals/30-bl-014-kong-version-pin.md`
- `research/44-bl-014-kong-version-problem-map.md`
- `infra/tests/test_public_intake_rate_limit.py`

## Findings

### 1. Modifies only infra/tests/ (test extension) — PASS

Proposal §3 "Modified files" declares exactly one file in the change
surface: `infra/tests/test_public_intake_rate_limit.py`. The authorized
edits are confined to that single existing pytest module:

- add static assertions for the Kong Helm chart version, rendered manifest
  reference, Gateway image tag, and KIC image tag;
- extend the existing annotated-path check to assert the full public-intake
  supported route set, including beta-1 chapters and beta-3 upload-url
  coverage through Prefix parents;
- add negative assertions that anti-list paths are not present on
  public-intake-plugin annotated Ingress resources;
- keep the existing plugin config and catch-all unannotated checks.

Q2 locks the test location to extending that one file. Adding a separate
`infra/tests/test_kong_version_pin.py` is explicitly discouraged "in this
slice unless the implementation finds that the existing file becomes
materially harder to read." §6 diff budget caps total churn on
`test_public_intake_rate_limit.py` at "roughly 80 lines" with "No new
test file unless extending the existing guard becomes materially less
readable."

The change surface is therefore one pytest module under `infra/tests/`,
with no spill into other test directories, fixtures, or CI configuration.

### 2. No production code, no GitOps manifest changes — PASS

§3 "Unmodified substrate" forbids both surfaces explicitly:

- "No production API, Discord daemon, web, repository, service, or
  migration changes."
- "No GitOps manifest changes. This proposal locks the current local
  manifests; it does not modify Kong, KIC, Pomerium, or server-manager
  YAML."

§5 anti-scope reinforces the GitOps half: "Do not modify Kong manifests,
Pomerium manifests, server-manager manifests, or rendered Helm output.
This is a regression test proposal for the current GitOps shape." §6
diff budget repeats both: "No production code." and "No GitOps manifest
changes."

The version-touching surfaces under
`gitops/channels/local/ingress/kong/` (README.md, kustomization.yaml,
render-values.yaml, rendered/kong-3.2.0.yaml), the public-intake plugin
manifests at `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`
and `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`,
and all catch-all Ingress manifests are read-only inputs to the pytest
guard — none of them are listed as modified files. No service code,
Pomerium policy, Discord daemon code, or migration files are touched.

### 3. No live-cluster smoke (deferred) — PASS

Q1 locks the guard shape: "implement a static YAML-only guard for this
slice." §1 problem statement is explicit: "This is a static-only
regression guard. It catches local manifest drift and forces intentional
review of Kong/KIC version changes. It does not prove live KIC route/plugin
translation behavior."

§3 "Unmodified substrate" forbids the live lane: "No CI cluster, live KIC
fixture, or admission-webhook lane in this slice." §5 anti-scope is
explicit on both deferred lanes:

- "Do not add live KIC translation smoke in this slice. The follow-up
  live lane should boot a minimal Kong/KIC fixture and prove actual
  generated route/plugin association or proxy behavior for positive and
  adjacent-negative paths."
- "Do not add an admission-webhook compatibility lane. The local Kong
  chart currently disables the webhook, and webhook validation is a
  separate signal from route/plugin translation."

The research at `research/44-bl-014-kong-version-problem-map.md:128-186`
identifies live KIC translation smoke as the smallest test that catches
the deepest BL-014 runtime risk, but the proposal deliberately retains
only the "static YAML check" lane (problem map §"Test design options")
for this slice. All TG-1, TG-2, and TG-3 acceptance steps run a single
`pytest infra/tests/test_public_intake_rate_limit.py` invocation with no
cluster, no fixture pods, no Admin API calls, and no proxy traffic.

### 4. No new dependencies — PASS

The existing `infra/tests/test_public_intake_rate_limit.py` imports only
`pathlib`, `typing`, `json`, and `yaml` (lines 1-8). The proposal §3
authorizes "small helpers if needed for reading Kong version files and
comparing annotated Prefix coverage" — these read README.md,
kustomization.yaml, render-values.yaml, and rendered/kong-3.2.0.yaml from
`gitops/channels/local/ingress/kong/`, which the existing
`pathlib + yaml.safe_load_all + plain text read` stack already covers. The
chart version assertion in TG-1 (Helm chart `3.2.0`, rendered file
`rendered/kong-3.2.0.yaml`, label `helm.sh/chart: kong-3.2.0`, image
`kong:3.9`, KIC image `kong/kubernetes-ingress-controller:3.5`) is a
string/structure match, not a Helm or kustomize execution.

§6 diff budget does not introduce any new package, fixture YAML, runner
script, or CI lane. No `helm`, `kubectl`, `kustomize`, or container
toolchain is required at test time. No new Python package, Go module,
Node package, or system binary is named anywhere in the proposal's
modified-files or test-plan sections.

## Conclusion

The proposal stays within a single pytest file under `infra/tests/`,
introduces no production code or GitOps manifest changes, defers all
live-cluster and admission-webhook smoke to a separate follow-up, and
adds no new dependency or toolchain. Each gate check passes against an
explicit proposal section. Scope risk is acceptable.

SCOPE_DONE: plans/risk/bl-014-scope.md
