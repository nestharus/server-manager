READ:
- proposals/03-cedar-policy-source.md
- research/04-cedar-policy-source-problem-map.md
- .tmp/rca/cedar-bootstrap-put-FINDINGS.md
- ~/ai/conventions/no-backwards-compatibility.md
- ~/ai/conventions/no-deferred-stubs.md
- AGENTS.md
- ~/ai/workflows/implementation-pipeline.md (Phase 4)
- plans/risk/init-120-scope.md (format reference)

# INIT-121 Scope-Risk Report

## Inputs read

- Proposal: `proposals/03-cedar-policy-source.md`.
- Problem map: `research/04-cedar-policy-source-problem-map.md`.
- RCA: `.tmp/rca/cedar-bootstrap-put-FINDINGS.md`.
- Conventions: `~/ai/conventions/no-backwards-compatibility.md`,
  `~/ai/conventions/no-deferred-stubs.md`.
- AGENTS.md (`No Backwards Compatibility`, `No Deferred Stubs`).
- Phase-4 rules: `~/ai/workflows/implementation-pipeline.md` §Phase 4.
- Locked direction confirmed in problem map line 52: Candidate A —
  OPAL is sole Cedar policy authority via in-cluster `humility-local.git`,
  bootstrap Job is removed.

## Scope ↔ Anti-scope check

Each design change below is paired with the Scope clause it satisfies
and the Anti-scope clause it must not violate.

1. **Set OPAL Server policy source to in-cluster `humility-local.git`**
   (proposal §Design `### OPAL Server config`, lines 76-85; Scope
   line 39).
   - Scope: "Set local OPAL Server policy source to
     `http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git`."
   - Anti-scope guard: "No new Git service, Gitea, OCI policy bundle,
     API bundle server, or second in-cluster policy repository"
     (line 57). The design reuses the existing `Service/git-local`
     and the existing one-repo seed flow, no new Git surface.
   - Verdict: in scope, no smuggling.

2. **Materialize `policies.json` into per-policy `.cedar` files in the
   seeded snapshot** (proposal §Design `### Bundle materialization`,
   lines 114-135; Scope lines 43-44).
   - Scope: "Extend `infra/scripts/render-gitops-source.py` so the
     local seed snapshot includes top-level `policy/` content..." +
     "Materialize `policy/cedar/channels/local/services/server-manager-api/policies.json`
     into per-policy `.cedar` files inside the seeded repo."
   - Anti-scope guard: "No changes to INIT-120 public-intake policy
     semantics. `public-intake-allow` and `public-intake-no-read`
     remain valid; they are loaded through OPAL instead of the
     bootstrap Job" (line 53). The materializer requires
     `content` byte-for-byte equality to canonical JSON (line 135),
     which preserves Cedar text and policy IDs.
   - Verdict: in scope; only the loading mechanism changes.

3. **Delete `bootstrap-job.yaml` and `access-policy-configmap.yaml`
   plus drop them from `kustomization.yaml`** (proposal §Design
   `### Removal of bootstrap Job and ConfigMap`, lines 137-146;
   Scope line 45).
   - Scope: "Remove `gitops/channels/local/auth/opal-cedar/bootstrap-job.yaml`
     and `access-policy-configmap.yaml` from the OPAL Kustomization
     and delete those manifests."
   - Anti-scope guard: "No backwards-compatible dual loading path.
     The bootstrap Job and ConfigMap are removed rather than retained
     as a fallback" (line 58). The proposal forbids "no validator may
     wait on `job/cedar-access-policy-bootstrap`" (line 70), which is
     a global ban consistent with the anti-scope.
   - Verdict: in scope; convention-aligned with no-backwards-compat.

4. **Replace bootstrap-Job completion gate with `Deployment/opal-client`
   readiness plus runtime `/v1/policies` ID probe** (proposal §Design
   `### Test surface changes`, lines 150-176; Scope lines 46-48).
   - Scope: "Replace ConfigMap equality assertions with seeded-source
     equality assertions" + "Replace bootstrap-Job completion gates
     with `deployment/opal-client` readiness plus a runtime
     `/v1/policies` expected-ID probe."
   - Anti-scope guard: "No changes to server-manager API Cedar call
     sites or `CEDAR_AUTHORIZATION_URL`" (line 54). The probe targets
     `opal-client:8180/v1/policies` from a curl pod; no edit to
     `services/api/.../authz.py`, `protected.py`, or
     `api-deployment.yaml`'s `CEDAR_AUTHORIZATION_URL`.
   - Verdict: in scope.

5. **Keep OPAL Client policy updater enabled with Cedar store
   binding unchanged** (proposal §Design `### OPAL Client config`,
   lines 87-97; Scope lines 41-42).
   - Scope: "Keep OPAL Client policy updating enabled; do not set
     `OPAL_POLICY_UPDATER_ENABLED=False`" + "Keep OPAL Client bound
     to Cedar Agent through `OPAL_POLICY_STORE_TYPE=CEDAR`,
     `OPAL_POLICY_STORE_URL=http://localhost:8180`, and
     `OPAL_POLICY_STORE_AUTH_TYPE=none`."
   - Anti-scope guard: locked direction states OPAL is sole
     authority — explicitly does not select Candidate B (disabling
     updater). The proposal honors that selection.
   - Verdict: in scope.

## Implementation decisions inside scope?

Q1..Q5 from `## Implementation decisions taken in proposal`
(lines 60-70). Each must be implementable within the touched surface
named in the problem map (lines 38-50).

- **Q1 — Same-repo `humility-local.git` with top-level `policy/`
  sub-path** (line 62). Touched surface: `infra/channels/local.yaml`,
  `infra/scripts/install-flux-for-channel.sh`, `git-daemon.yaml`,
  `render-gitops-source.py`. The git-daemon already serves any repo
  under `/srv/git` via `git http-backend` (problem map line 44), the
  seed flow already pushes one repo named `humility-${CHANNEL_ID}.git`
  (problem map line 45). No new repo is created. **In touched
  surface.**

- **Q2 — `render-gitops-source.py` copies top-level `policy/` in
  addition to `gitops/`** (line 64). Touched surface:
  `infra/scripts/render-gitops-source.py` only. The renderer's current
  `_copy_gitops_tree(out)` boundary (problem map line 46, line 82) is
  the precise file requiring a parallel `_copy_policy_tree(out)`. No
  edit to Flux Kustomization path (`./gitops/channels/local`),
  consistent with assumption A4 (line 201). **In touched surface.**

- **Q3 — One `<policy-id>.cedar` per object emitted into the
  generated tree** (line 66). Touched surface:
  `infra/scripts/render-gitops-source.py` (materializer) plus the
  already-rendered OPAL Server `OPAL_POLICY_REPO_POLICY_EXTENSIONS='[".cedar"]'`
  (problem map line 39). The proposal commits the rendered manifest
  must no longer contain an empty `OPAL_POLICY_REPO_URL` (line 84).
  No new bundle-server component, no Cedar-Agent format change. **In
  touched surface.**

- **Q4 — Replace ConfigMap equality with seeded-source equality
  (static) + canonical-ID `/v1/policies` (runtime)** (line 68).
  Touched surface: `infra/tests/validate_access_policy_local.sh`,
  `infra/tests/test_access_policy_contract.py`,
  `infra/tests/test_public_intake_policy_fixture.py`,
  `infra/tests/fixtures/contracts/access_policy_matrix.yml`. The
  Phase-2 problem map already named all four files (lines 49, 84) as
  inside the touched surface. **In touched surface.**

- **Q5 — Replace bootstrap-Job-completion gate with `opal-client`
  readiness plus `/v1/policies` ID poll** (line 70). Touched surface:
  `validate_access_policy_local.sh`, `validate_tenant_isolation_local.sh`,
  and the global ban "no validator may wait on
  `job/cedar-access-policy-bootstrap`" (line 70). The ban is global
  and authoritative; see notable observation 1 about the two
  validators not enumerated in `### Test surface changes`. **In
  touched surface, with one enumeration gap flagged below.**

All five Q-decisions are implementable inside the manifest, render,
and validator surfaces named in the problem map. None require a new
component or a new external dependency.

## Out-of-scope discipline

The proposal lists these as `## Out of scope for follow-up`
(lines 245-251). Cross-checked against `## Design`:

- **Remote channel apply / BL-013 / INIT-124** (lines 56, 247): not
  implemented; `infra/channels/dev.yaml` still has no GitOps block
  (problem map line 47). The Design references only `local.yaml`
  paths and the `local` channel suffix in policy materialization
  (lines 119, 125-132). No silent dev/remote enablement.
- **`opal-client` restart durability proof** (line 248): T7 covers
  one polling-interval recheck (lines 219-220), but full chaos-style
  restart coverage is explicitly named as follow-up. The proposal
  also names the residual-risk artifact `plans/risk/init-121-test-residuals.md`
  (lines 222-223) so any unverified test-intent risk surfaces
  rather than silently passes.
- **Policy decision telemetry / Cedar deny-rate alerting** (line 249):
  not in §Design; the only observability change is "OPAL Server clone
  errors and OPAL Client policy-transaction errors are now
  authoritative symptoms" (line 191), which is interpretive guidance
  for existing logs, not a new dashboard.
- **Public-intake behavior change / public rate limits / Pomerium
  authorization** (line 250): Anti-scope lines 50-53 are mirrored.
  No edit to `gitops/channels/local/auth/pomerium/ingress.yaml`,
  `public-intake-rate-limit.yaml`, or
  `services/api/app/api/v1/endpoints/applications/public.py`.
- **Multi-service / multi-channel partitioning** (line 251): the
  generated tree path is hardcoded to `policy/cedar/channels/local/services/server-manager-api/`
  (lines 119, 125-132). Single channel, single service. No silent
  multi-service surface.

None of the listed follow-ups are silently in scope.

## Convention compliance

`~/ai/conventions/no-backwards-compatibility.md`:

- Anti-scope line 58 forbids dual loading: "No backwards-compatible
  dual loading path. The bootstrap Job and ConfigMap are removed
  rather than retained as a fallback." This is the canonical anti-shim
  clause.
- Migration order (lines 227-234): step 4 deletes both manifests;
  the rendered local root must not include `ConfigMap/cedar-access-policy-bundle`
  or `Job/cedar-access-policy-bootstrap` (line 146).
- Negative assertions (line 154): the static validator is required
  to fail if the rendered root still contains either object. This is
  a grep-invariant guard against reintroduction, matching the
  convention's `test_no_<legacy_symbol>_remains()` pattern.
- Rollback path (lines 236-243) restores the old shape via
  `git revert`, not via a runtime fallback branch. This is a
  reverse-the-commit rollback, not a transitional dual-path.

`~/ai/conventions/no-deferred-stubs.md`:

- Materializer is fully specified (line 135): "fail on duplicate IDs,
  missing `id`, missing `content`, path-unsafe IDs, empty content,
  or invalid JSON shape." No `# TODO: handle later` placeholder.
- Generated directory is removed and recreated each render (line 135),
  preventing stale `.cedar` files from surviving deletions — no
  silent fallback empty file.
- Test-intent track (T1-T7, lines 207-220) names a real assertion
  surface for each item. T7's restart-durability gap is bounded by
  the residual-risk artifact (lines 222-223), which is the
  authorized-deferral pattern: a follow-up artifact captures
  unverified residuals rather than leaving a silent stub.
- A3 explicitly forbids hard-coded policy counts: "tests must compute
  the count dynamically rather than hard-code 8 except in
  documentation" (line 199) — no magic-number stub.

Both conventions are met by the proposal text.

## Adjacent-path discipline

Cross-check of proposal §Supported-surface track (lines 178-191) and
Anti-scope (lines 49-58) against problem-map adjacents (lines 78-104).

- **INIT-120 public-intake policies** (`public-intake-allow`,
  `public-intake-no-read`): bundle content preserved (line 53,
  line 135). The materializer copies `content` exactly. T6 keeps
  the matrix-driven public-intake guard and the validator-text
  rename to seeded-source naming (lines 217-218). No public-intake
  semantic edit.
- **Pomerium routes / route-secrets / identity headers**: no edit
  in §Design. Anti-scope line 51 explicit. Adjacent file
  `gitops/channels/local/auth/pomerium/ingress.yaml` is not in the
  proposal's touched-file list.
- **Authentik flows**: no edit in §Design. Anti-scope line 50
  explicit.
- **Tenant isolation policies**: bundle content preserved (line 53,
  line 135). T5 asserts `Tenant::"sample"` allow/allow/deny remains
  intact (lines 215-216). No tenant model redesign.
- **Server-manager API call sites**: Anti-scope line 54 explicit.
  `CEDAR_AUTHORIZATION_URL=http://opal-client.auth-system.svc.cluster.local:8180`
  in `api-deployment.yaml` (problem map line 62) is unchanged. The
  runtime probe targets the same URL through a curl pod; no edit to
  `authz.py`, `protected.py`, or `applications/public.py`.
- **`Deployment/opal-client` Cedar binding**: kept identical (lines
  91-95), so Cedar Agent itself, its port 8180, and the OPAL Client
  image continue to behave the same.
- **`auth-system` namespace boundary**: the proposal uses
  `git-local.git-system.svc.cluster.local:8080` from `auth-system`,
  which is the same cross-namespace HTTP path Flux already uses
  (assumption A1, line 195). No NetworkPolicy edit named.

The bundle content is preserved; only the loading mechanism changes.

## Notable observations

1. **`validate_auth_stack_local.sh` and `verify-service-identity-claim.sh`
   are not listed in `### Test surface changes` despite waiting on
   the bootstrap Job.** The problem map names both as part of the
   touched test surface (line 49) and identifies their bootstrap-Job
   waits (lines 57, 60, 71). The proposal's design section enumerates
   four test files (validate_access_policy_local.sh,
   validate_tenant_isolation_local.sh, test_public_intake_policy_fixture.py,
   test_access_policy_contract.py) but does not list these two. The
   global ban at line 70 ("no validator may wait on
   `job/cedar-access-policy-bootstrap`") does cover them, and
   migration order step 5 says "Update shell and pytest validators
   from ConfigMap/Job assertions to seeded-source and runtime
   policy-ID assertions" generally. Implementation must apply the
   global ban beyond the explicitly listed files; otherwise removing
   the bootstrap Job leaves these scripts deadlocked on
   `wait job/cedar-access-policy-bootstrap`. **This is enumeration
   tightness, not scope creep — the global ban is unambiguous, but
   Phase 6 should verify both files are updated.**

2. **`validate_auth_stack_local.sh` static asserts the rendered
   bootstrap Job exists.** Per problem map lines 57, 71, the
   validator currently asserts `cedar-access-policy-bundle`,
   `bootstrap-job.yaml`, and `cedar-access-policy-bootstrap` Job
   are rendered (`validate_auth_stack_local.sh:134-143, 188-200`).
   Removing the manifests will flip these to negative assertions,
   matching the proposal's negative-assertion pattern at line 154
   for `validate_access_policy_local.sh`. Same observation as #1 —
   covered by the proposal's intent but not enumerated.

3. **Anti-scope explicitly forbids a second policy repository, but
   the snapshot now contains both `gitops/` and `policy/` trees in
   one repo.** Anti-scope line 57 reads "No new Git service, Gitea,
   OCI policy bundle, API bundle server, or second in-cluster policy
   repository." The proposal stays inside this by reusing
   `humility-local.git` and adding only a top-level subdirectory
   (Q1, line 62). No second `humility-local-cedar.git` is created.
   Worth noting that the snapshot's payload widens (gitops + policy)
   but the repo count and the git-daemon surface do not.

4. **A4 invariance is asserted, not proven, in the proposal.**
   Assumption A4 (line 201) claims that copying top-level `policy/`
   into the seeded repo "does not affect Flux reconciliation" because
   Flux's Kustomization path remains `./gitops/channels/local`. This
   is accurate against current `infra/channels/local.yaml` (problem
   map line 47), but the snapshot marker scope and any future Flux
   Kustomization that watches the repo root would invalidate the
   assumption. The proposal correctly names this in `## Assumption
   register` with an invalidating-input — not a scope leak, but a
   legitimate Phase-6 implementation guard ("snapshot marker remains
   scoped to the Flux Kustomization path", line 112).

5. **`access_policy_matrix.yml` rename inside fixture is in scope.**
   Line 175 asks the fixture to "name the seeded policy directory
   or generated policy fixture instead of `gitops_configmap`". This
   is the only fixture key edit; all matrix entries (public-intake,
   user, service identity, tenant) keep their semantic content. No
   matrix rule rewrite.

6. **Locked direction is honored, alternatives are not reopened.**
   The RCA (lines 54-60) presents Candidates A/B/C; the problem map
   (line 52) records Candidate A as locked. The proposal does not
   flirt with Candidate B (disabling updater) or Candidate C (API
   bundle source) — it commits to A end-to-end. This is appropriate
   for Phase 4 scope discipline.

## Verdict

```
SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
```

No assumption invalidates the supported surface: the local channel
contract still points at `humility-local.git`, Flux still watches
`./gitops/channels/local`, Cedar Agent at `opal-client:8180` still
serves authorization for protected API and public intake, and the
8-policy bundle content is preserved byte-for-byte through the
materializer. The proposal stays cleanly within Scope, honors the
locked Candidate A direction, keeps every Anti-scope item out of
§Design, complies with `no-backwards-compatibility` (explicit dual-
path ban + delete-not-fallback removal) and `no-deferred-stubs` (full
materializer spec, residual-risk artifact for unverified test
intents), and does not silently mutate INIT-120 public-intake
semantics, Pomerium routes, Authentik flows, tenant policies, or
server-manager API Cedar call sites. The two enumeration gaps in
notable observations 1 and 2 are bounded by the proposal's global
ban on bootstrap-Job waits and its general migration-order step 5;
they are Phase-6 verification points, not scope-gate failures.
