READ:
- proposals/03-cedar-policy-source.md
- research/04-cedar-policy-source-problem-map.md
- .tmp/rca/cedar-bootstrap-put-FINDINGS.md
- ~/ai/workflows/implementation-pipeline.md
- ~/ai/conventions/gate-ownership.md
- gitops/channels/local/auth/opal-cedar/render-values.yaml
- gitops/channels/local/auth/opal-cedar/rendered/opal-0.0.29.yaml
- gitops/channels/local/auth/opal-cedar/access-policy-configmap.yaml
- gitops/channels/local/auth/opal-cedar/bootstrap-job.yaml
- gitops/channels/local/auth/opal-cedar/kustomization.yaml
- gitops/sources/local/git-daemon.yaml
- policy/cedar/channels/local/services/server-manager-api/policies.json
- infra/channels/local.yaml
- infra/scripts/render-gitops-source.py

# INIT-121 Phase 4 — Supported-Surface Risk

## Inputs read

- `proposals/03-cedar-policy-source.md` — full proposal, including supported-surface track, net-value statement, assumption register A1–A5, and test-intent track T1–T7.
- `research/04-cedar-policy-source-problem-map.md` — approved Phase 2.5 problem map covering touched surface, current supported paths, brittle behavior already present, blast-radius adjacents, deployment cohort, and open questions for proposal.
- `.tmp/rca/cedar-bootstrap-put-FINDINGS.md` — Phase 0 RCA establishing the split-brain root cause and Candidate A as the recommended fix shape.
- Phase pipeline conventions: `~/ai/workflows/implementation-pipeline.md`, `~/ai/conventions/gate-ownership.md`.
- Cited source artifacts for assumption verification: `gitops/channels/local/auth/opal-cedar/render-values.yaml`, `rendered/opal-0.0.29.yaml`, `access-policy-configmap.yaml`, `bootstrap-job.yaml`, `kustomization.yaml`; `gitops/sources/local/git-daemon.yaml`; `policy/cedar/channels/local/services/server-manager-api/policies.json`; `infra/channels/local.yaml`; `infra/scripts/render-gitops-source.py`.

## Termination evaluation

Per `implementation-pipeline.md:106`, evaluate orthogonal termination signals before the LOW/MEDIUM/HIGH verdict. Order: invalidated assumption first, then non-positive value.

### Invalidated assumption check

I cross-checked each assumption in the proposal's register against current source. Detail in `## Assumption register cross-check`. Summary:

- A1, A3, A4, A5: cited evidence resolves at the cited locations; invalidation conditions are observable.
- A2 ("OPAL's Cedar path can use `.cedar` files named by policy ID and load them into Cedar such that `/v1/policies` reports those IDs"): the cited evidence at `render-values.yaml:6-7` proves only that `OPAL_POLICY_REPO_POLICY_EXTENSIONS='[".cedar"]'` is configured. It does not prove the file-stem → policy-ID mapping that the proposal's design and T3 depend on. The proposal explicitly names a runtime probe as the invalidation source, treating A2 as an assumption to be confirmed by Step 6b's runtime test rather than a settled fact. That posture is consistent with the assumption-register convention and does not constitute an *invalidated* assumption against current source.

No assumption is contradicted by current source. **No INVALIDATED_ASSUMPTION signal.**

### Non-positive value check

Existing-state risk on the supported surface is concrete and present today: `rendered/opal-0.0.29.yaml:188-189` ships an empty `OPAL_POLICY_REPO_URL`; the RCA documents the deployed OPAL Server failing `git clone ''` and OPAL Client receiving 503 `policy repo was not found`, while a one-shot Job writes Cedar memory directly (`bootstrap-job.yaml:36-49`, `access-policy-configmap.yaml`). This is the split-brain BL-001 risk the slice targets.

Added blast radius is bounded:
- OPAL/Cedar manifests under `gitops/channels/local/auth/opal-cedar/` (already inside touched surface).
- `infra/scripts/render-gitops-source.py` extension to copy top-level `policy/` and materialize `.cedar` files (additive helper parallel to `_copy_gitops_tree`).
- Five test/validator files explicitly enumerated in the proposal's test-surface section.
- Local seed flow continues to push one repo (`humility-local.git`); no second repo introduced.
- No edits to Authentik, Pomerium, server-manager API call sites, or remote channel.

The migration burden is the single local channel and its CI validators; rollback is `git revert + reseed`, with the honest caveat that rollback restores the broken split-brain. The reduction in concrete current-state risk clearly outweighs the additive blast radius and the migration cost.

**No NON_POSITIVE_VALUE signal.**

## Existing-state risk reduction

The RCA root cause is structural: OPAL is configured as the policy authority but its declared source is empty, while a parallel one-shot Job writes Cedar memory directly without going through OPAL's pubsub path. The proposal addresses this at the structural level rather than papering over it:

- `OPAL_POLICY_REPO_URL` becomes the existing in-cluster `humility-local.git` URL (`render-values.yaml` `server.policyRepoUrl`), so OPAL Server has a real source to clone. Verified that this is the same URL Flux already uses (`infra/channels/local.yaml:22`), so the network path is exercised today.
- The direct writer is removed entirely (`bootstrap-job.yaml` and `access-policy-configmap.yaml` deleted from the Kustomization). This eliminates the split-brain rather than retaining a fallback dual-loader, consistent with `~/ai/conventions/no-backwards-compatibility.md`.
- `OPAL_POLICY_UPDATER_ENABLED` stays enabled and `OPAL_POLICY_STORE_TYPE=CEDAR` is preserved, so the OPAL Client → Cedar Agent path becomes the single hydration channel. The RCA's H3 source-of-truth conflict is resolved rather than relocated.

The fragility shifts from "Job exit 0 ≠ Cedar hydrated" to "OPAL Client `/v1/policies` shows expected IDs," which is the signal the RCA recommended (`cedar-bootstrap-put-FINDINGS.md:70-75`). Concentration of risk on the OPAL hydration path is by design; the test-intent track binds T2–T3–T7 to that path with assumption links to A1, A2, A3.

Residual concern: A2 (file-stem → policy-ID mapping) is the load-bearing claim the new path cannot demonstrate from static manifests. The proposal correctly carries it as a runtime probe rather than as proven fact. If Step 6b cannot exercise T3 against a live cluster, this becomes a residual that must be recorded in `risk/init-121-test-residuals.md` per `implementation-pipeline.md:163`. Not a verdict-blocker, but a Step 6b watch signal.

## Adjacent-path blast-radius bounding

Adjacent paths I checked:

- **INIT-120 public-intake** (`https://web.local.humility.local/applications`, `POST /api/v1/public/applications`, `POST /api/public/applications`): `public-intake-allow` and `public-intake-no-read` policy IDs are present in canonical `policies.json` lines 11–17 and the proposal preserves them through OPAL hydration. No semantic change. The web bundle and Pomerium routes are not touched. Public-intake authorization continues to depend on Cedar; if A2 is wrong and `public-intake-allow` does not load, public submission fails closed. T6 keeps the matrix-driven public-intake assertions.

- **Tenant isolation** (`validate_tenant_isolation_local.sh`): tenant policies (`local-tenant-sample-local-access`, `local-tenant-sample-dev-access`, `local-tenant-other-local-access`) remain in canonical `policies.json` lines 22–33 and are part of the same hydration set. The proposal replaces the bootstrap-Job wait with the `/v1/policies` ID gate and keeps the same Allow/Allow/Deny tenant proof. Bound.

- **INIT-114 protected-API authz proof** (`https://protected-api.local.humility.local/api/v1/protected/authz-proof`): API server-side `CEDAR_AUTHORIZATION_URL` and the `User::<subject>` request shape are anti-scope; only the Cedar bundle loading path changes. Protected route continues to depend on Cedar Allow for `api:read`; same closed-by-default risk as today if A2 fails.

- **INIT-115 service identity proof** (`verify-service-identity-claim.sh`): `local-server-manager-api-buildkite-deploy` and `local-cluster-api-crossplane-reconcile` remain canonical. Buildkite authorization probe via `/v1/is_authorized` is preserved by the new policy-ID gate.

- **Authentik / Pomerium identity flow**: no manifest edits inside that surface. Anti-scope.

Migration order in the proposal protects these adjacents because:
1. Tests added first (Step 1) encode the new gate.
2. Renderer + OPAL config + Kustomization deletion happen in a single Flux reconcile cycle. OPAL Server rolls with the new repo URL, OPAL Client refetches, the Job and ConfigMap are pruned in the same pass.
3. Validators stop waiting on `job/cedar-access-policy-bootstrap` in the same change.

Adjacent-path coverage gap (notable observation, not a blocker): the proposal's test-surface section enumerates `validate_access_policy_local.sh`, `validate_tenant_isolation_local.sh`, `test_public_intake_policy_fixture.py`, and `test_access_policy_contract.py`, but does **not** enumerate `infra/scripts/verify-service-identity-claim.sh` or `infra/tests/validate_auth_stack_local.sh`. The problem map flags both as currently waiting on `job/cedar-access-policy-bootstrap` (`research/04-cedar-policy-source-problem-map.md:71`, `:85`). Once the Job is removed from the Kustomization, those validators will fail at the wait step. This is a Step 6a/6b contract obligation, not a proposal-design defect — but Step 6b must extend the same gate change to those files or document why they are exempt.

## Migration and rollback realism

Fresh `humility-local` bringup: `install-flux-for-channel.sh` renders the snapshot (now including top-level `policy/`), seeds `humility-local.git` with a single force-push (`install-flux-for-channel.sh:168-205`, `:471-485` per problem map), applies the git-daemon manifest, applies Flux source CRs, and reconciles. OPAL Server clones a non-empty repo for the first time and finds `.cedar` files under the generated path. OPAL Client picks them up on connection and hydrates Cedar. Validators wait for `deployment/opal-client` ready then poll `/v1/policies` for canonical IDs.

Verified preconditions for the bringup path:
- `git-local` Service is ClusterIP on port 8080 and serves `/cgi-bin/git/<repo>.git` via `git http-backend` with `GIT_HTTP_EXPORT_ALL=1` (`git-daemon.yaml:100-167`); cross-namespace ClusterIP HTTP works without auth.
- `auth-system` is not in the `network_policy.default_deny_namespaces` list (`infra/channels/local.yaml:317-328`), so OPAL Server can reach `git-system` without an explicit allow rule.
- `render-gitops-source.py` already wipes and rebuilds `out` (`render-gitops-source.py:204-208`), so adding a `_copy_policy_tree` helper does not introduce a stale-tree concern.
- The marker / tree-digest is scoped to `source_path` derived from `gitops.path` (`render-gitops-source.py:175-194`), which remains `./gitops/channels/local`. Top-level `policy/` is outside that path and therefore outside the digest. A4 holds at the renderer level.

Rollback: `git revert` + reseed restores the previous Kustomization (Job + ConfigMap re-included) and the previous render-values (empty `policyRepoUrl`). Flux applies the reverted state on the next reconcile; bootstrap Job runs again; validators wait for it again. The proposal honestly states rollback re-introduces the split-brain risk and is for emergency only — appropriate for a local-only slice on a known-broken existing state.

One non-blocking observation: the bootstrap Job has `ttlSecondsAfterFinished: 3600` (`bootstrap-job.yaml:12`). In a fresh cluster running the new path, the Job manifest is removed, so this is moot. In a cluster mid-migration that already has a completed Job, Flux prune deletes the Job resource regardless of TTL state. No operational gap.

## Observability

Per `cedar-bootstrap-put-FINDINGS.md:46-48`, the prior failure was that "bootstrap command exited 0" stood in for "Cedar is durably hydrated from the declared source of truth." The proposal moves the source-of-truth signal to:

- `opal-server` clone logs (errors are now meaningful: `humility-local.git` is non-empty, so a clone failure indicates a real configuration or network problem).
- `opal-client` policy-transaction logs (now the only writer; failures are not masked by a parallel direct PUT).
- Runtime `GET http://opal-client:8180/v1/policies` returning canonical IDs (T3 makes this the validator gate; T7 re-asserts after one polling interval).

The proposal explicitly states the validator should log returned IDs on failure (T3 expected signal, supported-surface track "Observability" paragraph). That is a meaningful improvement over the current "Job complete therefore policies present" signal.

Residual observability concerns (non-blocking):
- Alerting on Cedar deny rates and policy-decision telemetry are explicitly out of scope (proposal "Out of scope for follow-up"). Fine for this slice.
- Restart durability beyond one polling interval is acknowledged as a follow-up if Step 6b does not include a restart probe. If it does not, a `risk/init-121-test-residuals.md` entry is required per Step 6b's named-risk rule.

## Channel-template parity

The proposal stays local-first by design and defers remote to BL-013/INIT-124, matching the channel-template-pattern memory and the problem map's deployment-cohort framing.

Parity-relevant decisions in the proposal:

- `_copy_policy_tree(out)` is a renderer helper without a channel guard. When `infra/channels/dev.yaml` later wires GitOps (currently omitted at line 223 per problem map), the same renderer will copy `policy/` for that channel without a local-only conditional.
- The canonical authoring path is channel-namespaced (`policy/cedar/channels/local/services/server-manager-api/`). Remote channels would author under their own `policy/cedar/channels/<id>/...`, which fits the existing channel-template inheritance pattern.
- The OPAL render-values change for `policyRepoUrl` is in the local-channel path (`gitops/channels/local/auth/opal-cedar/render-values.yaml`). Remote channels will need an analogous render-values choice when their auth stack is materialized. This proposal does not introduce a templating mechanism for that, but it does not foreclose one either; it simply leaves the remote slot empty as today.

No local-only exception is introduced. Remote contract surface remains preserved (no `dev` channel manifests are touched). This matches the environment-agnostic-stack memory's expectation that local IS a deployment target with the same component shape.

## Assumption register cross-check

For each assumption: I check (a) the cited evidence exists at the cited location and supports the claim, and (b) the invalidation condition is observable.

**A1.** "OPAL Server can clone the existing in-cluster HTTP Git URL from `auth-system`."
- Cited at `infra/channels/local.yaml`. Verified line 22: `git_url: http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git`. Flux uses this URL, so the path is already exercised in-cluster.
- Cited at `gitops/sources/local/git-daemon.yaml`. Verified Service is ClusterIP on port 8080 (lines 153-167) and the CGI endpoint serves `git http-backend` with `GIT_HTTP_EXPORT_ALL=1` (lines 100-116).
- Invalidation condition: smoke test or pod log showing OPAL cannot resolve or clone. Observable through standard `kubectl logs deployment/opal-server`. ✓

**A2.** "OPAL's Cedar path can use `.cedar` files named by policy ID and load them into Cedar such that `/v1/policies` reports those IDs."
- Cited at `render-values.yaml:6-7`. Verified line 7: `OPAL_POLICY_REPO_POLICY_EXTENSIONS: '[".cedar"]'`. Also verified rendered manifest at `rendered/opal-0.0.29.yaml:194-195`.
- Cited at `.tmp/rca/cedar-bootstrap-put-FINDINGS.md`. The RCA describes OPAL's Cedar client behavior at a high level (lines 14, `opal_client/policy_store/cedar_client.py:338-359`) — that the client applies bundles per policy and deletes store policies absent from a complete bundle.
- Cited evidence proves OPAL watches `.cedar` files; it does **not** prove file-stem → policy-ID mapping. The proposal correctly posits this as a runtime-verifiable assumption.
- Invalidation condition: runtime probe at `/v1/policies` showing different IDs or missing files. Observable through T3. ✓ (load-bearing; flagged in Notable observations)

**A3.** "The canonical local policy count is 8."
- Cited at `policy/cedar/channels/local/services/server-manager-api/policies.json`. Verified: 8 distinct policy objects with the IDs the proposal enumerates (`local-server-manager-api-user-read`, `local-server-manager-api-buildkite-deploy`, `public-intake-allow`, `public-intake-no-read`, `local-cluster-api-crossplane-reconcile`, `local-tenant-sample-local-access`, `local-tenant-sample-dev-access`, `local-tenant-other-local-access`).
- Invalidation condition: change to canonical JSON. Observable; tests must compute count dynamically (proposal explicitly notes this except in documentation). ✓

**A4.** "Copying top-level `policy/` into the seeded repo does not affect Flux reconciliation."
- Cited at `infra/channels/local.yaml`. Verified Flux Kustomization path is `./gitops/channels/local` (line 24).
- Cited at `infra/scripts/render-gitops-source.py`. Verified that `_render_marker` scopes `_tree_digest` to `source_path` (lines 175-194), and `_source_path` returns `out / "gitops/channels/local"` (lines 83-87). Top-level `policy/` lies outside that scope, so its presence in the snapshot does not perturb the Flux source-sha or trigger Flux to apply policy YAML files.
- Invalidation condition: Flux source/marker behavior begins hashing or pruning the policy tree. Observable. ✓

**A5.** "Removing the ConfigMap and Job does not change Cedar authorization semantics."
- Cited at `access-policy-configmap.yaml` and `policies.json`. Verified by reading both: the ConfigMap's `data.policies.json` (lines 12-45) is byte-for-byte equivalent to canonical `policies.json` (lines 1-34) for all 8 policy objects.
- Invalidation condition: seeded-source equality (T1) or runtime authorization (T4, T5, T6) showing different content or decisions. Observable. ✓

All five assumptions resolve at their cited locations and have observable invalidation conditions. No assumption is contradicted by current source.

## Notable observations

These are observations and watch signals, not verdict-blockers.

1. **Test-surface enumeration gap.** The problem map flags `infra/scripts/verify-service-identity-claim.sh` (line 71) and `infra/tests/validate_auth_stack_local.sh` (line 71) as both waiting on `job/cedar-access-policy-bootstrap`. The proposal's "Test surface changes" section does not enumerate them. Once the Job manifest is removed from the Kustomization, those validators will fail at their wait step. Step 6a/6b must extend the same gate change to those files. This is a contract obligation, not a proposal-design defect.

2. **A2 is the load-bearing assumption.** Cited static evidence proves only that OPAL is configured to watch `.cedar` extensions; it does not prove that file-stem becomes the policy ID visible at `/v1/policies`. The proposal correctly carries this as a runtime probe (T2 + T3 + T7). If Step 6b cannot exercise T3 against a real cluster, a `risk/init-121-test-residuals.md` entry is required per `implementation-pipeline.md:163`.

3. **Restart durability is explicitly out of scope.** The proposal's "Out of scope for follow-up" acknowledges it. T7 covers post-polling-interval durability but does not cover an `opal-client` restart cycle, which the RCA listed as a desirable durability proof (`cedar-bootstrap-put-FINDINGS.md:75`). If Step 6b does not add a restart probe, this is the second residual that must be recorded.

4. **Migration-order concentration.** Steps 3 (OPAL config) and 4 (Job/ConfigMap deletion) are best applied in a single Flux sync so the new and old paths do not coexist. The proposal's order is correct; Step 6c should commit them together.

5. **Channel-template parity is preserved without local-only conditionals**, but the proposal does not yet templatize the OPAL render-values URL for remote channels. This is in line with the local-first scope and is not a parity violation today; it becomes a follow-up if remote channel auth-stack materialization is later requested.

## Verdict

The proposal targets the supported local Cedar policy-loading surface and reduces a concrete current-state risk (split-brain hydration documented in the RCA). The assumption register is verifiable, the supported-surface track is honest about rollback restoring the broken state, the test-intent track binds to assumptions, and the blast radius is bounded to the local channel plus its CI validators. Net value is positive on the current supported surface. The main residuals (A2 runtime verification, restart durability, two unenumerated validators) are Step 6a/6b obligations rather than proposal defects.

```
SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
```
