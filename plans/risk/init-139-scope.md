# INIT-139 Scope risk gate

Verdict: **PASS**

Reviewed:

- `proposals/34-init-139-kong-kic-smoke.md`
- `research/50-init-139-kic-smoke-problem-map.md`
- `.buildkite/pipeline-cluster.yml`

## Findings

### 1. Only adds `infra/tests/validate_kong_kic_translation_local.sh` + 1 pipeline step — PASS

Proposal §3 "New file" enumerates exactly one new substrate file:

- `infra/tests/validate_kong_kic_translation_local.sh`

Proposal §3 "Modified file" enumerates exactly one existing pipeline file:

- `.buildkite/pipeline-cluster.yml`, with the new validator added to the
  existing `pr-cluster-merge-readiness-runtime-validators` command block
  (one additional command-line entry, not a new step). §3 also explicitly
  pins lane choice: "Keep it in the cluster-runtime lane, not
  `.buildkite/pipeline.yml`."

§6 diff budget restates the same surface: "one new shell validator,
roughly 150-250 lines… one `.buildkite/pipeline-cluster.yml` command-line
addition." The current `pipeline-cluster.yml` already runs five
`infra/tests/validate_*_local.sh --cluster` commands inside the
`pr-cluster-merge-readiness-runtime-validators` block, so the proposed
addition is a sixth sibling line in the same block — no new Buildkite
step, no new lane, no new dependency on bringup ordering beyond what the
existing validators already inherit.

Test-only guard files (TG-2 and TG-3) are explicitly segregated under
"Test-only guard files" with the note that they "are not runtime
substrate." §6 prefers "extending an existing Buildkite pipeline test if
one already owns cluster-lane assertions" rather than authoring a new
test file. That keeps the production-runtime change surface at exactly
one new validator + one pipeline-line addition, satisfying the gate.

### 2. No production code changes — PASS

§5 anti-scope explicitly excludes every production surface: "Modifying
Kong manifests, KIC manifests, Pomerium manifests, or server-manager
Ingress manifests… Changing the BL-014 static pins in
`infra/tests/test_public_intake_rate_limit.py`… Adding compatibility
shims, feature flags, dual route-binding support, or alternate old/new
plugin attachment behavior… Any Discord-visible mutation."

§6 reinforces the same prohibition: "No application code, API contracts,
migrations, generated TypeScript, web code, Discord daemon code, or
Kubernetes manifest changes are in budget." The validator is a runtime
introspection script that reads Kong's Admin API; it does not write to
the cluster, mutate state, or alter any application/runtime artifact.

### 3. No GitOps / Kong manifest changes — PASS

§5 anti-scope blocks every manifest surface adjacent to the runtime
binding under test: "Modifying Kong manifests, KIC manifests, Pomerium
manifests, or server-manager Ingress manifests." The proposal frames the
slice as runtime-only verification of the BL-014 manifests, not a change
to them: §1 states the validator must "prove the controller translated
the annotation into Kong Route-scoped plugin entities, not merely that
Kubernetes accepted the CRD," and §2 Q2 explicitly notes "This validator
is runtime-only. It does not add another static manifest check for
BL-014."

The route discovery contract in §2 Q4 binds the validator to the
existing manifest topology by `hosts` and `paths` rather than generated
route names, so the validator depends on — but does not modify — the
KongPlugin/KongIngress/Ingress surface already pinned by BL-014.

### 4. No new dependencies — PASS

§2 Q2 requires only `kubectl`, `curl`, and `jq`, matching the toolset
used by existing `infra/tests/validate_*_local.sh` scripts. The problem
map confirms that "Existing validators already cover DNS/curl patterns"
and that the access pattern is `kubectl port-forward` + `curl -k` —
both already present in the cluster lane. No new pip package, no new
shell binary, no new Helm chart, no new container image, no new
service-account, and no Buildkite plugin is authorized. The only new
network surface used is Kong's Admin API on HTTPS `8444`, which is
internal to the rendered Kong pod and reached via a temporary
port-forward that the validator must clean up in a `trap`.

### 5. No ephemeral kind cluster (uses existing humility-local) — PASS

§5 anti-scope is explicit: "Ephemeral kind or k3d fixture cluster. Use
the existing `humility-local` cluster lane." §2 Q2 sets
`KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"` as the default,
matching the cluster-lane convention. The pipeline addition lands inside
`pr-cluster-merge-readiness-runtime-validators`, which runs after the
existing `humility-local-cluster-bringup` step — no new cluster
provisioning, no new k3d/kind invocation, and no new bringup script is
authorized.

The problem map raised a related concern that the cluster lane brings
up with `--cluster-only` (which skips Flux post-install) and asked the
proposal to lock the bootstrap/reseed prerequisite. The proposal does
not extend the bringup contract; it relies on whatever reconciled state
the existing cluster lane already provides at the point the runtime
validators run. That deference is feasibility risk, not scope creep —
it keeps the slice from acquiring new cluster-bringup responsibility.

### 6. No behavior-burst test (separate slice) — PASS

§2 Q8 locks the decision: "behavior burst testing is out of scope for
this slice. Do not send request bursts through the proxy to force `429`,
and do not use proxy behavior as the primary assertion. A behavior
burst can be proposed as a separate confidence layer after this
introspection smoke is stable." §5 anti-scope restates: "Behavior burst
test. That is a separate slice if needed."

The validator's mandatory assertions in §2 Q5 and §2 Q6 are purely
Admin-API introspection: `GET /routes`, `GET /routes/<route_id>/plugins`,
positive presence of `name == "rate-limiting"` on five public-intake
routes, and negative absence on the API admin path
`/api/v1/web/admin/chapters`. No proxy traffic, no burst loop, no `429`
expectation, and no rate-limit timing window is in scope.

## Notes (non-blocking)

These do not violate the scope gate but should be reconciled during
hookpoint research or implementation:

- **Namespace lock vs. rendered manifests.** §2 Q3 locks the
  port-forward target as `deploy/kong-kong -n kong 8444:8444`, while the
  proposal itself notes "the current local rendered Kong manifests show
  the release under `kong-system`." Reconciliation is required before
  code lands; the proposal correctly forbids using the mismatch as a
  reason to switch to behavior-burst mode, which preserves scope.
- **Bootstrap reconciliation.** The cluster lane uses `--cluster-only`
  bringup, which skips Flux post-install (problem map). If the lane
  does not, in practice, leave Kong/KIC reconciled before the runtime
  validators run, the validator will fail to find any Kong Routes. This
  is feasibility risk owned by implementation/hookpoint research, not a
  scope expansion in this proposal.

## Conclusion

The proposal authorizes exactly one new file
(`infra/tests/validate_kong_kic_translation_local.sh`) and one
pipeline-line addition to the existing
`pr-cluster-merge-readiness-runtime-validators` command block in
`.buildkite/pipeline-cluster.yml`. It explicitly anti-scopes production
code, Kong/KIC/Pomerium/server-manager manifest changes, BL-014 static
pin edits, behavior-burst testing, and ephemeral kind/k3d clusters. It
introduces no new dependencies beyond `kubectl`/`curl`/`jq`, all already
required by sibling validators. Each gate check is satisfied by an
explicit proposal section. Scope risk is acceptable.

SCOPE_DONE: plans/risk/init-139-scope.md
