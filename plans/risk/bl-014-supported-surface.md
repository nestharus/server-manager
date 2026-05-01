# BL-014 — Supported-surface risk gate

**Verdict:** LOW

BL-014 (`proposals/30-bl-014-kong-version-pin.md`) is a test-layer-only
slice that extends `infra/tests/test_public_intake_rate_limit.py` with
static assertions that pin Kong-version-touching surfaces (Helm chart
`3.2.0`, rendered manifest reference `rendered/kong-3.2.0.yaml`,
rendered chart label `helm.sh/chart: kong-3.2.0`, Kong Gateway image
`kong:3.9`, KIC image `kong/kubernetes-ingress-controller:3.5`),
expand the public-intake supported route set assertions
(beta-1 chapter paths and beta-3 upload-url Prefix coverage), and add
explicit anti-list negative assertions on annotated public-intake
Ingresses (`/api/v1/web/`, `/auth/discord`, `/api/v1/health`, `/`,
catch-alls). Proposal §3 "Unmodified substrate" and §5 "Anti-scope"
explicitly forbid any change to production code, GitOps manifests,
Kong/KIC/Pomerium/Authentik/server-manager YAML, rendered Helm output,
or CI lanes. Every public surface that operators or other infrastructure
depends on is preserved verbatim.

## Check results

### 1. No public API change — ✓ PASS

No changes to:

- `services/api/app/api/v1/endpoints/applications/public.py`,
  `services/api/app/api/v1/endpoints/applications/public_uploads.py`,
  `.../chapters/public.py`, or any other public/protected API route
  module;
- `PublicApplicationSubmission` /
  `PublicApplicationSubmissionReceipt` / chapter / upload-url
  request/response contracts;
- public-intake auth chain (`verify_applicant_receipt`,
  `authorize_public_intake`);
- web client (`services/web/src/api/client.ts`) or any caller of the
  public/upload-url endpoints.

The proposal is purely test-layer additive: it extends an existing
pytest module to lock the *current* manifest shape. Static YAML
introspection cannot alter routing, request shape, or auth behavior;
the assertions only fail CI if a future commit drifts the manifests
themselves.

### 2. No env vars / migrations / GitOps / Pomerium / Authentik changes — ✓ PASS

| Surface | Pre | Post | Status |
|---|---|---|---|
| Process / Settings env vars | unchanged | unchanged — proposal §3 "No production API, Discord daemon, web, repository, service, or migration changes" | ✓ |
| Alembic / DB migrations | post-INIT-137 head | unchanged — test-only slice | ✓ |
| GitOps manifests (`gitops/channels/local/**`) | current local channel | unchanged — proposal §3 "No GitOps manifest changes. This proposal locks the current local manifests; it does not modify Kong, KIC, Pomerium, or server-manager YAML" | ✓ |
| Kong chart / render-values / rendered Helm output (`gitops/channels/local/ingress/kong/`) | chart `3.2.0`, gateway `kong:3.9`, KIC `kong/kubernetes-ingress-controller:3.5` | unchanged — pinned by additive read-only assertions; no edits to `README.md`, `kustomization.yaml`, `render-values.yaml`, or `rendered/kong-3.2.0.yaml` | ✓ |
| Public-intake KongPlugin + Ingresses (`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`, `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`) | INIT-120 / β-1 / β-3 shape | unchanged — proposal §3 forbids manifest changes; new assertions only *read* current annotated Prefix paths | ✓ |
| Pomerium routes / auth blueprint | post-INIT-137 set | unchanged — not touched | ✓ |
| Authentik blueprint | post-INIT-134 set | unchanged — not touched | ✓ |
| OPAL / Cedar policy bundle | post-BL-012 set | unchanged — not touched | ✓ |
| CI lanes (Buildkite pipeline, validate scripts) | existing | unchanged — proposal §5 "Do not add live KIC translation smoke", "Do not add an admission-webhook compatibility lane" | ✓ |

Proposal §3 "Modified files" lists exactly one entry:
`infra/tests/test_public_intake_rate_limit.py`. Proposal §6 caps
total churn at ~80 lines. Both constraints rule out any env-var,
migration, GitOps, Pomerium, or Authentik footprint.

### 3. Pytest collects in existing infra/tests/ lane — ✓ PASS

`infra/tests/test_public_intake_rate_limit.py` already exists (137
lines today) and is collected by the existing pytest lane:

- it sits in the same directory as `test_public_intake_policy_fixture.py`,
  `test_kong_ingress_contract.py`, `test_opal_manifest_authority.py`,
  and the other static-contract tests that the lane already runs;
- it shares the `infra/tests/conftest.py` session fixtures (which do
  not touch this file's tests — they are pure YAML/JSON readers);
- its current two functions
  (`test_public_intake_kong_plugin_has_documented_rate_limit_config`,
  `test_public_intake_plugin_is_bound_only_to_public_submit_paths`)
  use only `pathlib`, `yaml`, and `json` — the same idiom the new
  version-pin and anti-list assertions will use.

Proposal §2 Q2 explicitly locks placement: "extend
`infra/tests/test_public_intake_rate_limit.py` … keeps the BL-014
checks near the existing risk annotation and avoids a second test
file." Proposal §3 confirms: "Add static assertions for the Kong Helm
chart version, rendered manifest reference, Gateway image tag, and
KIC image tag" inside the same file. No new conftest, no new pytest
marker, no new fixture infrastructure, no new collection lane. Adding
helper functions for reading
`gitops/channels/local/ingress/kong/{README.md, kustomization.yaml,
render-values.yaml, rendered/kong-3.2.0.yaml}` is purely
file-local — the four files already exist on disk in the worktree
under that exact path layout.

### 4. Test failure mode is loud + actionable — ✓ PASS

The proposal's acceptance criteria are explicit literal pins, which
yield clean assertion failures when a future commit drifts a
version-touching surface or the supported route set. Concretely:

- **TG-1 (version pins, proposal §4)**: each assertion checks a single
  literal — `"3.2.0"` in the chart render command, `"rendered/kong-3.2.0.yaml"`
  in the kustomization, `"helm.sh/chart: kong-3.2.0"` in the rendered
  output, `"kong:3.9"` in `render-values.yaml` / rendered manifest,
  `"kong/kubernetes-ingress-controller:3.5"` in
  `render-values.yaml` / rendered manifest. A drift produces a pytest
  diff of expected vs actual literal, plus the source path (the
  existing `_yaml_documents` helper at line 16-22 already stamps
  `_source_path`, and the new helpers will follow the same idiom per
  proposal §6 "add small helpers if needed for reading Kong version
  files"). Failure message names the offending file and value.
- **TG-2 (supported route set, proposal §4)**: extends the existing
  `annotated_paths` set assertion (current file:91-117) with explicit
  `(host, path)` tuples for `/api/v1/public/applications`,
  `/api/v1/public/chapters`, `/api/public/applications`,
  `/api/public/chapters`, legacy `/api/applications`, plus Prefix
  coverage proofs `assert "/api/v1/public/applications/upload-url".startswith(annotated_prefix)`
  and the web-side equivalent. Missing-tuple failures already produce
  readable pytest output today
  (`(...) in annotated_paths` style), and the upload-url Prefix proof
  fails with the literal upload path and the missing parent prefix.
- **TG-3 (adjacent anti-list, proposal §4 acceptance: "failures name
  the offending host/path and source manifest so drift is easy to
  correct")**: assertions iterate over annotated public-intake
  Ingresses and reject any path in `{ "/api/v1/web/", "/auth/discord",
  "/api/v1/health", "/" }`. Each violation pytest message includes
  the host, path, and the manifest's stamped `_source_path` (the
  same pattern used by the existing catch-all checks at lines 118-136
  which already pull resources by `metadata.name`).
- **No silent skipping**: the existing `_local_resources()` helper
  at lines 25-43 already asserts that required GitOps manifests
  exist (`assert path.is_file(), f"missing expected local GitOps manifest: …"`).
  Extending this to require `gitops/channels/local/ingress/kong/README.md`,
  `kustomization.yaml`, `render-values.yaml`, and
  `rendered/kong-3.2.0.yaml` follows the same loud-fail idiom — a
  rename/move of a Kong file produces an immediate `AssertionError`
  naming the missing path rather than a silent pass.

The slice is also explicit (proposal §1) about what the static guard
does *not* prove: it does not validate live KIC route/plugin
translation. That non-claim is not a failure-mode weakness — it is a
correctly scoped supported-surface guard, with the live-translation
follow-up deferred to a separate slice (proposal §5 anti-scope).

## Findings

None blocking. Two observations worth surfacing for implementation:

- **Helper additions for new files.** The existing test only reads
  `gitops/channels/local/applications/server-manager/*.yaml` and
  `gitops/channels/local/auth/pomerium/*.yaml`
  (`infra/tests/test_public_intake_rate_limit.py:25-43`). Adding
  version-pin helpers will need to read four additional files under
  `gitops/channels/local/ingress/kong/` (README.md is plain text;
  kustomization.yaml and render-values.yaml are YAML; the rendered
  Helm output is multi-doc YAML at ~4000+ lines). Implementer should
  read README and rendered manifest as text (the chart label
  `helm.sh/chart: kong-3.2.0` and the `kong/kong --version 3.2.0`
  command line are easier to assert as substrings than as full YAML
  parses), and parse render-values.yaml / kustomization.yaml as YAML.
  Proposal §6 explicitly authorizes "small helpers" for this purpose.

- **Optional second test file path.** Proposal §2 Q2 says
  "Do not add `infra/tests/test_kong_version_pin.py` in this slice
  unless the implementation finds that the existing file becomes
  materially harder to read." If the implementer takes that escape
  hatch, the new file must still live under `infra/tests/` (so the
  existing pytest lane collects it transparently) and follow the
  same risk-annotation docstring style. Either path satisfies all
  four supported-surface gates; the choice is implementer's.

## Verdict reasoning

LOW.

1. **Public API surface (gate 1)**: zero touches. Public submit,
   chapter, and upload-url routes plus their request/response
   contracts and auth chain are byte-identical. The proposal cannot
   alter routing because it modifies only test code that reads YAML.
2. **Cross-cutting infra surfaces (gate 2)**: zero env / migration /
   GitOps / Pomerium / Authentik / Kong / OPAL / Authentik /
   server-manager edits. Anti-scope is unusually explicit for this
   slice (proposal §3 "Unmodified substrate" + §5 "Anti-scope" +
   §6 ~80-line cap). The slice locks current manifest shape via
   read-only assertions; it does not propose any manifest mutation.
3. **Pytest collection surface (gate 3)**: the guard extends an
   existing file under `infra/tests/` that the existing pytest lane
   already collects. No new conftest, marker, fixture, or lane.
   The four new GitOps Kong files the helpers must read all exist
   in the local channel today at the exact paths proposal §2 Q3
   names.
4. **Failure-mode surface (gate 4)**: every new assertion has a
   single, literal expected value (chart `3.2.0`, gateway `kong:3.9`,
   KIC `3.5`, rendered file path, chart label, supported route
   tuples, anti-list paths). Drift produces a pytest assertion
   failure that names the offending file and value, and the
   `_source_path` stamp on every parsed YAML doc means anti-list
   violations point at the manifest that introduced the regression.
   The proposal also correctly flags its own non-coverage (does not
   prove live KIC translation), so the failure-mode contract is
   honestly scoped.

The slice has zero blocking findings against the four supported-surface
gate criteria. Implementation can proceed without a supported-surface
re-gate, provided the implementer:

- keeps all changes inside `infra/tests/test_public_intake_rate_limit.py`
  (or, if exercising the proposal §2 Q2 escape hatch, places the
  new file in `infra/tests/`);
- treats Helm chart, Gateway image, KIC image, rendered file
  reference, and chart label as five separate literal pins (per
  proposal §2 Q3 and the research problem map's "Important naming
  wrinkle" call-out);
- preserves anti-list failure messages that name the offending
  host/path and the manifest's `_source_path`;
- keeps `gitops/channels/local/ingress/kong/**`,
  `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`,
  and `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`
  unmodified;
- does not introduce any live KIC, admission-webhook, or
  server-side-apply lane in this slice.

Verdict: **LOW**.

SUPPORTED_SURFACE_DONE: plans/risk/bl-014-supported-surface.md
