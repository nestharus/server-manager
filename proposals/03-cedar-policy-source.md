READ:
- .tmp/rca/cedar-bootstrap-put-FINDINGS.md
- research/04-cedar-policy-source-problem-map.md
- plans/proposals/init-115-access-policy.md
- plans/proposals/init-114-auth-stack.md
- gitops/channels/local/auth/opal-cedar/render-values.yaml
- gitops/channels/local/auth/opal-cedar/rendered/opal-0.0.29.yaml
- gitops/channels/local/auth/opal-cedar/bootstrap-job.yaml
- gitops/channels/local/auth/opal-cedar/access-policy-configmap.yaml
- gitops/channels/local/auth/opal-cedar/kustomization.yaml
- gitops/sources/local/git-daemon.yaml
- infra/scripts/install-flux-for-channel.sh
- infra/scripts/render-gitops-source.py
- policy/cedar/channels/local/services/server-manager-api/policies.json
- policy/cedar/channels/local/services/server-manager-api/manifest.yaml
- policy/cedar/channels/local/services/server-manager-api/service-identities.json
- infra/tests/validate_access_policy_local.sh
- infra/tests/validate_tenant_isolation_local.sh
- infra/tests/test_public_intake_policy_fixture.py
- infra/tests/test_access_policy_contract.py
- infra/tests/fixtures/contracts/access_policy_matrix.yml
- infra/channels/local.yaml
- infra/channels/dev.yaml
- gitops/channels/local/auth/pomerium/ingress.yaml
- gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml
- gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml
- ~/ai/workflows/implementation-pipeline.md

## Summary

Make OPAL the only local Cedar policy authority by serving the canonical Cedar bundle from the already-seeded in-cluster Git repo, configuring OPAL Server to clone that repo, and letting OPAL Client hydrate Cedar through its normal updater into `/v1/policies`. This removes the current split-brain where OPAL is configured as a policy source but has an empty `OPAL_POLICY_REPO_URL`, while a separate ConfigMap plus one-shot bootstrap Job directly writes Cedar Agent memory. The deployment cohort is local channel first: fresh and reconciled `humility-local` clusters, local CI validators, and cluster operators; remote channel application is deferred to BL-013/INIT-124.

## Net-value statement

This proposal has positive net value because it reduces a concrete current-state risk on the supported local auth surface: a completed `Job/cedar-access-policy-bootstrap` can coexist with an empty OPAL policy source, so `GET /v1/policies` can later return `[]` and Cedar-gated paths can deny or fail despite the GitOps ConfigMap containing the expected policy JSON (`.tmp/rca/cedar-bootstrap-put-FINDINGS.md`; `research/04-cedar-policy-source-problem-map.md`). The added blast radius is limited to OPAL/Cedar manifests, the local git-daemon seed snapshot, policy-bundle materialization, and validators that currently assert ConfigMap/Job behavior. The migration burden is justified because it removes the direct writer race, makes `opal-client` logs and `/v1/policies` the source-of-truth signal, and keeps Authentik, Pomerium, application routes, and policy semantics unchanged.

## Scope

- Set local OPAL Server policy source to `http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git`.
- Keep OPAL policy extension matching on `.cedar` and keep the polling interval at 30 seconds unless the chart renderer already supplies the default.
- Keep OPAL Client policy updating enabled; do not set `OPAL_POLICY_UPDATER_ENABLED=False`.
- Keep OPAL Client bound to Cedar Agent through `OPAL_POLICY_STORE_TYPE=CEDAR`, `OPAL_POLICY_STORE_URL=http://localhost:8180`, and `OPAL_POLICY_STORE_AUTH_TYPE=none`.
- Extend `infra/scripts/render-gitops-source.py` so the local seed snapshot includes top-level `policy/` content in addition to `gitops/`.
- Materialize `policy/cedar/channels/local/services/server-manager-api/policies.json` into per-policy `.cedar` files inside the seeded repo.
- Remove `gitops/channels/local/auth/opal-cedar/bootstrap-job.yaml` and `access-policy-configmap.yaml` from the OPAL Kustomization and delete those manifests.
- Replace ConfigMap equality assertions with seeded-source equality assertions.
- Replace bootstrap-Job completion gates with `deployment/opal-client` readiness plus a runtime `/v1/policies` expected-ID probe.

## Anti-scope

- No Authentik flow changes.
- No Pomerium route, route-secret, or identity-header behavior changes.
- No changes to INIT-120 public-intake policy semantics. `public-intake-allow` and `public-intake-no-read` remain valid; they are loaded through OPAL instead of the bootstrap Job.
- No changes to server-manager API Cedar call sites or `CEDAR_AUTHORIZATION_URL`.
- No tenant-isolation policy redesign.
- No remote channel OPAL/Cedar apply. Remote is deferred to BL-013/INIT-124.
- No new Git service, Gitea, OCI policy bundle, API bundle server, or second in-cluster policy repository.
- No backwards-compatible dual loading path. The bootstrap Job and ConfigMap are removed rather than retained as a fallback.

## Implementation decisions taken in proposal

Q1. Same-repo vs. separate-repo for the policy bundle: choose the same `humility-local.git` repo, under a top-level `policy/` sub-path in the seeded snapshot. The existing local Flux source and seed flow already create and force-push one repo named `humility-${CHANNEL_ID}.git` (`infra/channels/local.yaml`; `infra/scripts/install-flux-for-channel.sh`). A separate `humility-local-cedar.git` would require a second seed path, second repo lifecycle, and another source to keep in sync, without reducing the Cedar authority risk.

Q2. Snapshot scope for `render-gitops-source.py`: copy top-level `policy/` into the seed snapshot and keep the canonical source under `policy/cedar/channels/local/services/server-manager-api/`. Engineers should not need to place Cedar source under `gitops/channels/local/auth/opal-cedar/` just because the local seed snapshot currently copies only `gitops/`. The renderer should add a `_copy_policy_tree(out)` step and materialize OPAL-ready files from the copied canonical JSON.

Q3. Bundle format for OPAL -> Cedar: emit one `<policy-id>.cedar` file per object in canonical `policies.json`. This matches the existing `OPAL_POLICY_REPO_POLICY_EXTENSIONS='[".cedar"]'` configuration and avoids teaching OPAL to consume the old bulk `[{id, content}]` JSON payload. The canonical JSON remains the authoring source; the `.cedar` files are the OPAL Git-source representation.

Q4. Replacement for ConfigMap-equality assertions: replace them with two assertions. Static: render the local seed snapshot and assert the generated `.cedar` files in the seeded `policy/` tree equal canonical `policies.json` by ID and content. Runtime: assert `GET http://opal-client:8180/v1/policies` returns the canonical policy IDs, currently all 8 IDs from `policies.json`.

Q5. Replacement for bootstrap-Job-completion gate: wait for `Deployment/opal-client` to be ready, then run a policy-hydration probe that polls `GET /v1/policies` until it returns at least the canonical count and the expected IDs. The bootstrap Job and `cedar-access-policy-bundle` ConfigMap are deleted from `kustomization.yaml`; no validator may wait on `job/cedar-access-policy-bootstrap`.

## Design

### OPAL Server config

`gitops/channels/local/auth/opal-cedar/render-values.yaml` should set:

```yaml
server:
  policyRepoUrl: http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git
  extraEnv:
    OPAL_POLICY_REPO_POLICY_EXTENSIONS: '[".cedar"]'
```

The rendered manifest must no longer contain an empty `OPAL_POLICY_REPO_URL`. Keep `OPAL_POLICY_REPO_POLLING_INTERVAL=30`, matching the currently rendered polling cadence, so local policy changes in the seeded repo are observed without introducing a new timing contract. OPAL clones the repo root; the OPAL-relevant files are the generated `.cedar` files under `policy/cedar/channels/local/services/server-manager-api/`.

### OPAL Client config

Keep the Cedar client image and current Cedar store binding:

```yaml
OPAL_POLICY_STORE_TYPE: CEDAR
OPAL_POLICY_STORE_URL: http://localhost:8180
OPAL_POLICY_STORE_AUTH_TYPE: none
```

Do not set `OPAL_POLICY_UPDATER_ENABLED=False`. The updater is the intended authority path: OPAL Server reads Git, broadcasts policy updates, and OPAL Client applies them to Cedar Agent. `OPAL_DATA_UPDATER_ENABLED=False` can remain because this slice is about policy, not OPAL data.

### Git daemon

Use the existing `git-daemon` Deployment and `Service/git-local` in `git-system`. It already serves bare repos below `/srv/git` through `git http-backend` (`gitops/sources/local/git-daemon.yaml`). The seed flow continues to create and push only `/srv/git/humility-local.git`; OPAL Server and Flux both read from that same repo. Flux continues to watch `./gitops/channels/local`, while OPAL reads `.cedar` files from the repo's top-level `policy/` tree.

### render-gitops-source.py changes

Extend the renderer so `.tmp/gitops-source/local` contains:

```text
gitops/
policy/
```

The implementation should add a `POLICY_ROOT = REPO_ROOT / "policy"` constant and a `_copy_policy_tree(out)` helper parallel to `_copy_gitops_tree(out)`. `render()` should copy both trees before rendering source manifests and the snapshot marker. The snapshot marker can remain scoped to the Flux Kustomization path because Flux reconciliation still watches `./gitops/channels/local`; the policy tree is consumed by OPAL through Git, not by Flux.

### Bundle materialization

The canonical authoring file remains:

```text
policy/cedar/channels/local/services/server-manager-api/policies.json
```

During snapshot rendering, materialize it into generated `.cedar` files inside the copied policy tree, for example:

```text
policy/cedar/channels/local/services/server-manager-api/generated/policies/local-server-manager-api-user-read.cedar
policy/cedar/channels/local/services/server-manager-api/generated/policies/local-server-manager-api-buildkite-deploy.cedar
policy/cedar/channels/local/services/server-manager-api/generated/policies/public-intake-allow.cedar
policy/cedar/channels/local/services/server-manager-api/generated/policies/public-intake-no-read.cedar
policy/cedar/channels/local/services/server-manager-api/generated/policies/local-cluster-api-crossplane-reconcile.cedar
policy/cedar/channels/local/services/server-manager-api/generated/policies/local-tenant-sample-local-access.cedar
policy/cedar/channels/local/services/server-manager-api/generated/policies/local-tenant-sample-dev-access.cedar
policy/cedar/channels/local/services/server-manager-api/generated/policies/local-tenant-other-local-access.cedar
```

Each file contains exactly the `content` string from the matching JSON object, with one trailing newline. The file stem is the policy ID. The materializer must fail on duplicate IDs, missing `id`, missing `content`, path-unsafe IDs, empty content, or invalid JSON shape. It should remove and recreate the generated policy directory each render so stale `.cedar` files cannot survive after a policy deletion.

### Removal of bootstrap Job and ConfigMap

`gitops/channels/local/auth/opal-cedar/kustomization.yaml` should keep `rendered/opal-0.0.29.yaml` and `client-probes-patch.yaml`, but remove:

```yaml
- access-policy-configmap.yaml
- bootstrap-job.yaml
```

The proposal expects the files themselves to be deleted in implementation. The rendered local root must not include `ConfigMap/cedar-access-policy-bundle` or `Job/cedar-access-policy-bootstrap`.

### Test surface changes

`infra/tests/validate_access_policy_local.sh`:

- Replace the ConfigMap parse/diff with a render-snapshot static check: run `render-gitops-source.py --channel local --out <tmp>`, read generated `.cedar` files, map file stems to contents, and compare to canonical `policies.json`.
- Keep the existing channel-contract, service identity, rotation, break-glass, object-storage, and operator RBAC checks.
- Replace the static "bootstrap job missing" assertion with negative assertions that the rendered root has no `cedar-access-policy-bootstrap` Job and no `cedar-access-policy-bundle` ConfigMap.
- Replace runtime `wait job/cedar-access-policy-bootstrap` with `rollout status deployment/opal-client` and a poll of `GET /v1/policies` through a curl pod.
- Assert all canonical policy IDs are present before running existing allow/deny authorization probes for sample user and service identity.

`infra/tests/validate_tenant_isolation_local.sh`:

- Keep static tenant Cedar policy assertions against canonical `policies.json`.
- Replace the bootstrap Job wait with the same OPAL policy-ID gate.
- Run the same tenant allow/deny `/v1/is_authorized` probes only after the policy-ID gate passes.

`infra/tests/test_public_intake_policy_fixture.py`:

- Keep the matrix-driven public allow/read-deny assertions.
- Update the validator-text assertion away from `"GitOps ConfigMap policy differs from policy repo"` and toward the seeded-source equality check name or failure message.
- Keep the guard that the validator does not hard-code `application:submit_public` or `web-intake.local`.

`infra/tests/test_access_policy_contract.py`:

- Replace `_opal_bundle_policies()` with a helper that reads or constructs the generated seeded `.cedar` policy map from `policies.json` materialization.
- Assert the generated file stems equal policy IDs and generated contents equal canonical policy contents.
- Keep service identity and token-safety tests, but remove dependence on `fixture["bundle"]["gitops_configmap"]`.
- Update `infra/tests/fixtures/contracts/access_policy_matrix.yml` to name the seeded policy directory or generated policy fixture instead of `gitops_configmap`.

## Supported-surface track

Deployment mode: local first. The local channel has a live in-cluster Git source and Flux Kustomization (`infra/channels/local.yaml`). Remote channel GitOps apply is not present and remains deferred to BL-013/INIT-124 (`infra/channels/dev.yaml`; `research/04-cedar-policy-source-problem-map.md`).

Customer cohort: no end-user workflow changes directly. The affected cohort is cluster operators and CI for fresh or reconciled `humility-local` clusters. End users benefit only indirectly because Cedar-backed paths are less likely to start empty after OPAL reconnects or pod lifecycle events.

Adjacent public/user-reachable paths: no route behavior changes for the INIT-120 adjacent paths. `https://web.local.humility.local/` remains the public SPA shell, `https://web.local.humility.local/applications` remains the public form, `https://web.local.humility.local/admin/chapters` remains Pomerium-authenticated, `https://protected-api.local.humility.local/api/v1/protected/authz-proof` remains Pomerium-authenticated and Cedar-checked, and `https://api.local.humility.local/api/v1/applications` plus its public-intake sibling remain on the existing direct API host. This proposal changes only how the Cedar policies behind those checks are loaded.

Blast-radius notes for adjacent paths: if OPAL fails to clone or broadcast, Cedar-gated routes can still deny or return unavailable, but the failure becomes visible through OPAL Server/Client logs and the `/v1/policies` runtime gate. Authentik and Pomerium routing are not edited, so this proposal does not relax admin, protected API, or web admission rules.

Migration path: atomic through the local seed and Flux path. A fresh `install-flux-for-channel.sh` run renders a snapshot with `gitops/` plus `policy/`, seeds `humility-local.git`, applies Flux source CRs, reconciles OPAL manifests without the bootstrap Job/ConfigMap, rolls `opal-server` with a non-empty repo URL, rolls `opal-client`, then validators wait for `/v1/policies` to contain the canonical IDs.

Rollback path: revert the proposal implementation commit and rerun the local seed/reconcile flow. That restores the old ConfigMap plus bootstrap Job and the old empty OPAL source behavior. If a cluster is already running the new path, rollback should roll OPAL manifests back first, then wait for the restored Job to complete and verify `/v1/policies`. The rollback is operationally straightforward but reintroduces the split-brain risk, so it is only for emergency recovery.

Observability: `opal-client` logs become useful as the policy hydration signal because the client updater is the only writer to Cedar. Runtime validators should surface the policy IDs returned by `GET /v1/policies` on failure. OPAL Server clone errors for `humility-local.git` and OPAL Client policy-transaction errors are now authoritative symptoms, not background noise hidden behind a completed bootstrap Job.

## Assumption register

A1. OPAL Server can clone the existing in-cluster HTTP Git URL from `auth-system`. Evidence: Flux already uses `http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git` and the git-daemon service is ClusterIP-readable inside the cluster (`infra/channels/local.yaml`; `gitops/sources/local/git-daemon.yaml`). Invalidation source: an implementation smoke test or pod log showing OPAL cannot resolve or clone that URL from its namespace.

A2. OPAL's Cedar path can use `.cedar` files named by policy ID and load them into Cedar such that `/v1/policies` reports those IDs. Evidence: current OPAL values already set `OPAL_POLICY_REPO_POLICY_EXTENSIONS='[".cedar"]'`, and the locked direction selects OPAL -> Cedar policy loading (`gitops/channels/local/auth/opal-cedar/render-values.yaml`; `.tmp/rca/cedar-bootstrap-put-FINDINGS.md`). Invalidation source: a runtime probe showing OPAL loads the files under different IDs or ignores the generated path.

A3. The canonical local policy count is 8 for this slice. Evidence: `policy/cedar/channels/local/services/server-manager-api/policies.json` currently contains 8 policy objects, including public-intake, service identity, user-read, crossplane, and tenant policies. Invalidation source: a change to canonical `policies.json`; tests must compute the count dynamically rather than hard-code 8 except in documentation.

A4. Copying top-level `policy/` into the seeded repo does not affect Flux reconciliation. Evidence: Flux Kustomization path remains `./gitops/channels/local`, while OPAL consumes `policy/` directly from Git (`infra/channels/local.yaml`; `infra/scripts/render-gitops-source.py`). Invalidation source: Flux source or marker behavior begins hashing, pruning, or applying the top-level policy tree unexpectedly.

A5. Removing the ConfigMap and Job does not change Cedar authorization semantics. Evidence: the ConfigMap duplicates canonical `policies.json`, and the proposal keeps the same policy contents while changing only the loading authority (`access-policy-configmap.yaml`; `policy/cedar/channels/local/services/server-manager-api/policies.json`). Invalidation source: seeded-source equality or runtime authorization probes show different policy contents or decisions.

## Test-intent track

T1. Seeded policy source equality. Change risk: moving from ConfigMap JSON to generated `.cedar` files could drop, rename, or alter policy contents. Intended behavior: the rendered local seed snapshot contains one `.cedar` file per canonical policy ID and exact matching content. Level: component. Fixture source: canonical `policy/cedar/channels/local/services/server-manager-api/policies.json`; generated snapshot under `.tmp/gitops-source/local/policy/.../generated/policies`. Assumption link: A3, A5. Expected signal: static test or shell validator passes sorted ID/content equality and fails on stale, missing, duplicate, or extra generated policies. Residual risk: does not prove OPAL consumes the files.

T2. OPAL manifest authority. Change risk: empty `OPAL_POLICY_REPO_URL`, disabled updater, or lingering direct writer preserves split-brain. Intended behavior: rendered OPAL Server has non-empty repo URL, `.cedar` extension matching, and 30-second polling; rendered OPAL Client keeps policy updater enabled and Cedar store binding; rendered root has no bootstrap Job or policy ConfigMap. Level: particular-integration. Fixture source: `gitops/channels/local/auth/opal-cedar/render-values.yaml`, `rendered/opal-0.0.29.yaml`, and `kubectl kustomize gitops/channels/local`. Assumption link: A1, A2. Expected signal: static assertions pass and negative assertions find no `cedar-access-policy-bootstrap` or `cedar-access-policy-bundle`. Residual risk: does not prove network clone succeeds.

T3. Runtime policy hydration gate. Change risk: `deployment/opal-client` can be ready while Cedar is empty. Intended behavior: after `deployment/opal-client` readiness, a curl pod polling `http://opal-client:8180/v1/policies` observes at least the canonical count and all canonical policy IDs. Level: end-to-end for local cluster. Fixture source: canonical `policies.json` IDs passed into the probe. Assumption link: A1, A2, A3. Expected signal: validator logs the returned IDs and passes only when all expected IDs are present. Residual risk: a single successful probe does not prove long-term durability across every future pod crash.

T4. Access-policy authorization proof. Change risk: policy IDs can exist while Cedar decisions differ from the access-policy contract. Intended behavior: sample user `api:read` is allowed, other user `api:read` is denied, Buildkite deploy service identity is allowed, and unrelated service actions remain denied per the access-policy matrix. Level: particular-integration. Fixture source: `infra/tests/fixtures/contracts/access_policy_matrix.yml` and existing validator payloads. Assumption link: A5. Expected signal: `/v1/is_authorized` returns expected `Allow` and `Deny` decisions after T3 passes. Residual risk: does not exercise browser or Pomerium routing.

T5. Tenant isolation authorization proof. Change risk: tenant policies may fail to materialize or load even if user/service policies load. Intended behavior: `Tenant::"sample"` can access `sample:local` and `sample:dev`, and cannot access `other:local`. Level: particular-integration. Fixture source: canonical tenant policy entries and `validate_tenant_isolation_local.sh` payloads. Assumption link: A5. Expected signal: `/v1/is_authorized` returns Allow, Allow, Deny after T3 passes. Residual risk: does not prove Kubernetes RBAC tenant isolation beyond existing validator checks.

T6. Public-intake policy fixture preservation. Change risk: replacing ConfigMap assertions could accidentally remove the matrix-driven public-intake guard or hard-code public route details in the validator. Intended behavior: public submit allow and public read forbid remain in the canonical bundle; no public service identity is added; the validator remains matrix-driven and now names seeded-source equality instead of ConfigMap equality. Level: particular-integration. Fixture source: `infra/tests/test_public_intake_policy_fixture.py`, `access_policy_matrix.yml`, canonical `policies.json`, `service-identities.json`, and validator text. Assumption link: A5. Expected signal: pytest passes with updated seeded-source assertions and no hard-coded `web-intake.local` in the shell validator. Residual risk: does not prove live public form submission.

T7. OPAL hydration after one polling interval. Change risk: immediate policy load can pass while OPAL later replaces Cedar with an empty or partial bundle. Intended behavior: after T3 passes, wait longer than `OPAL_POLICY_REPO_POLLING_INTERVAL` and re-run the policy-ID and core authorization probes. Level: end-to-end for local cluster. Fixture source: canonical policy IDs and the access-policy matrix. Assumption link: A1, A2. Expected signal: expected IDs and decisions remain present after at least one 30-second polling cycle. Residual risk: does not prove every restart path unless the validator also restarts `opal-client`; restart durability can remain follow-up if it is not included in Step 6b.

### Residual-risk artifact

If Step 6b cannot verify any named test-intent risk above, it must emit `plans/risk/init-121-test-residuals.md`. Each residual must name the unverified test-intent item, residual class, attempted or considered technique, scope, budget or bound, remaining risk, invalidating inputs, and whether the residual changes the net-value case.

## Migration / rollback

Migration order:

1. Add tests first for seeded-source equality, OPAL manifest authority, no bootstrap Job/ConfigMap, policy-ID runtime gate, and existing authorization decisions.
2. Extend `render-gitops-source.py` to copy `policy/` and generate `.cedar` files from canonical `policies.json`.
3. Update OPAL render values and committed rendered manifest so `OPAL_POLICY_REPO_URL` points at `humility-local.git` and policy extension matching stays `.cedar`.
4. Remove `access-policy-configmap.yaml` and `bootstrap-job.yaml` from the OPAL Kustomization and delete those manifests.
5. Update shell and pytest validators from ConfigMap/Job assertions to seeded-source and runtime policy-ID assertions.
6. Run static validators, render the local seed snapshot, run local kustomize checks, then run runtime validators against a fresh or reconciled local cluster.

Rollback order:

1. Revert the implementation commit.
2. Re-render and reseed the local GitOps snapshot.
3. Reconcile Flux so the old ConfigMap and bootstrap Job return.
4. Wait for `deployment/opal-client` and `job/cedar-access-policy-bootstrap`.
5. Verify `/v1/policies` and core authorization decisions.
6. Record that rollback restores the known split-brain risk and should be followed by a revised proposal or RCA if the OPAL-authoritative path failed.

## Out of scope for follow-up

- Remote channel apply and host materialization for BL-013/INIT-124.
- Strong durability proof across arbitrary `opal-client` pod crashes if Step 6b does not include a restart probe. The design improves restart hydration by making OPAL authoritative, but full chaos-style restart coverage may be a follow-up.
- Policy decision telemetry, audit dashboards, and alerting on Cedar deny rates.
- Any change to public-intake behavior, public rate limits, application persistence, or Pomerium route authorization.
- Multi-service or multi-channel Cedar bundle partitioning beyond the local `server-manager-api` policy bundle.
