READ:
- proposals/03-cedar-policy-source.md
- research/04-cedar-policy-source-problem-map.md
- plans/risk/init-121-audit.md
- plans/risk/init-121-scope.md
- plans/risk/init-121-shortcut.md
- plans/risk/init-121-supported-surface.md
- .tmp/rca/cedar-bootstrap-put-FINDINGS.md
- /home/nes/ai/workflows/implementation-pipeline.md
- gitops/channels/local/auth/opal-cedar/render-values.yaml
- gitops/channels/local/auth/opal-cedar/rendered/opal-0.0.29.yaml
- gitops/channels/local/auth/opal-cedar/kustomization.yaml
- gitops/channels/local/auth/opal-cedar/bootstrap-job.yaml
- gitops/channels/local/auth/opal-cedar/access-policy-configmap.yaml
- gitops/channels/local/auth/opal-cedar/client-probes-patch.yaml
- gitops/sources/local/git-daemon.yaml
- infra/channels/local.yaml
- infra/channels/dev.yaml
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
- infra/tests/validate_auth_stack_local.sh
- infra/scripts/verify-service-identity-claim.sh
- infra/tests/validate_platform_bootstrap.sh

## Inputs read

- Approved proposal: `proposals/03-cedar-policy-source.md`.
- Approved problem map: `research/04-cedar-policy-source-problem-map.md`.
- Round-1 risk reports: `plans/risk/init-121-audit.md`, `plans/risk/init-121-scope.md`, `plans/risk/init-121-shortcut.md`, `plans/risk/init-121-supported-surface.md`; all report LOW / no termination.
- RCA: `.tmp/rca/cedar-bootstrap-put-FINDINGS.md`.
- Pipeline rules: `/home/nes/ai/workflows/implementation-pipeline.md`, especially Phase 5 at lines 122-130.
- Current source hookpoints listed in the `READ:` block above.

No approved assumption was contradicted by current source. A2 remains load-bearing and runtime-only, matching the supported-surface risk report: static source proves OPAL watches `.cedar` extensions, but not that OPAL/Cedar will expose file stems as policy IDs at `/v1/policies`.

## OPAL Server config hookpoints

Reusable hookpoints:

- `gitops/channels/local/auth/opal-cedar/render-values.yaml:1-7` is the Helm values source for OPAL Server. `server.policyRepoUrl` is currently `null` at line 5, and `OPAL_POLICY_REPO_POLICY_EXTENSIONS: '[".cedar"]'` already exists at lines 6-7.
- `gitops/channels/local/auth/opal-cedar/rendered/opal-0.0.29.yaml:173-195` is the committed Helm output consumed by Kustomize. It currently renders `OPAL_POLICY_REPO_URL` with an empty value at lines 187-189, `OPAL_POLICY_REPO_POLLING_INTERVAL` with `"30"` at lines 190-191, and `.cedar` extension matching at lines 194-195.
- `proposals/03-cedar-policy-source.md:74-85` defines the approved target: non-empty repo URL, keep `.cedar` matching, keep polling at 30 seconds, and have OPAL clone the repo root.

Implementation mapping:

- Set `server.policyRepoUrl` in `render-values.yaml:5` to `http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git`.
- Re-render `rendered/opal-0.0.29.yaml` so `OPAL_POLICY_REPO_URL` at lines 188-189 is non-empty, `OPAL_POLICY_REPO_POLLING_INTERVAL` remains `"30"`, and `OPAL_POLICY_REPO_POLICY_EXTENSIONS` remains `[".cedar"]`.

New files / modules:

- None. This design point edits existing Helm values and their committed render.

Conflicting systems:

- The empty rendered `OPAL_POLICY_REPO_URL` at `rendered/opal-0.0.29.yaml:188-189` conflicts with the approved source-of-truth path and must be refactored by re-rendering, not patched by an overlay.
- The old direct writer in `bootstrap-job.yaml:36-49` conflicts with OPAL as sole policy authority; deletion is covered in the Kustomization section.

Deletion candidates:

- No server-config file is deleted. The empty value is replaced.

## OPAL Client config hookpoints

Reusable hookpoints:

- `gitops/channels/local/auth/opal-cedar/render-values.yaml:21-27` is the values source for OPAL Client. It already sets `OPAL_POLICY_STORE_TYPE: CEDAR`, `OPAL_POLICY_STORE_URL: http://localhost:8180`, and `OPAL_POLICY_STORE_AUTH_TYPE: none`.
- `gitops/channels/local/auth/opal-cedar/rendered/opal-0.0.29.yaml:90-120` is the rendered client Deployment. It uses `permitio/opal-client-cedar:0.7.12` at line 92, points at `http://opal-server:7002` at lines 110-111, disables only the data updater at lines 112-113, and keeps the Cedar store binding at lines 114-119.
- `gitops/channels/local/auth/opal-cedar/client-probes-patch.yaml:1-25` replaces the OPAL client probes with TCP probes against the Cedar Agent port. It should remain in the Kustomization.

Implementation mapping:

- Leave the Cedar store env vars in place.
- Do not add `OPAL_POLICY_UPDATER_ENABLED=False`; absence of that env is the current hookpoint for keeping the policy updater enabled.
- `OPAL_DATA_UPDATER_ENABLED=False` can remain at `rendered/opal-0.0.29.yaml:112-113` because the approved slice is policy-only.

New files / modules:

- None. This design point preserves existing client configuration.

Conflicting systems:

- Any future addition of `OPAL_POLICY_UPDATER_ENABLED=False` would conflict with `proposals/03-cedar-policy-source.md:87-97` and should be treated as a test failure, not as a compatibility option.

Deletion candidates:

- None in OPAL Client config.

## Git daemon source hookpoints

Reusable hookpoints:

- `gitops/sources/local/git-daemon.yaml:22-38` defines `Deployment/git-daemon` in namespace `git-system`.
- `gitops/sources/local/git-daemon.yaml:92-116` mounts the bare repo store at `/srv/git`, sets `GIT_PROJECT_ROOT=/srv/git`, enables `GIT_HTTP_EXPORT_ALL=1`, and serves `git http-backend` through `/cgi-bin/git`.
- `gitops/sources/local/git-daemon.yaml:153-167` exposes `Service/git-local` on port 8080. There is no `Service/git-daemon` in the current source.
- `infra/channels/local.yaml:20-32` is Flux's current Git source contract. It uses `http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git`, ref `refs/heads/main`, and path `./gitops/channels/local`.
- `infra/scripts/install-flux-for-channel.sh:168-205` seeds exactly one bare repo, `/srv/git/humility-${CHANNEL_ID}.git`; for local this is `/srv/git/humility-local.git`.
- `infra/scripts/install-flux-for-channel.sh:187-188` tars the rendered snapshot into the seed directory, so any top-level `policy/` copied into the snapshot will be pushed to the same bare repo without changing the seeding transport.

Implementation mapping:

- `OPAL_POLICY_REPO_URL` should point at the same repo root URL Flux already uses: `http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git`.
- It should not point at `http://git-daemon.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git`; current source has a Deployment named `git-daemon`, but the Service DNS name is `git-local`.
- It should not point at a sub-path such as `.../humility-local.git/policy/...`. The git HTTP backend serves bare repositories below `/srv/git`; OPAL clones the repository root, and the approved design expects OPAL to discover `.cedar` files under the repo's top-level `policy/` tree.

New files / modules:

- None. The existing in-cluster Git daemon and single `humility-local.git` repo are reused.

Conflicting systems:

- A second policy repo would conflict with `proposals/03-cedar-policy-source.md:57` and with the one-repo seed flow at `install-flux-for-channel.sh:168-205`; leave the git-daemon implementation as-is.

Deletion candidates:

- None in `git-daemon.yaml` or `install-flux-for-channel.sh`.

## render-gitops-source.py refactor hookpoints

Reusable hookpoints:

- `infra/scripts/render-gitops-source.py:20-22` defines `REPO_ROOT`, `GITOPS_ROOT`, and marker constants. This is the natural location for a new `POLICY_ROOT = REPO_ROOT / "policy"` constant.
- `infra/scripts/render-gitops-source.py:74-80` is `_copy_gitops_tree(out)`, the existing copy helper to mirror for a `_copy_policy_tree(out)` helper.
- `infra/scripts/render-gitops-source.py:83-87` resolves the Flux watched path from `gitops.path`; it remains scoped to `./gitops/channels/local`.
- `infra/scripts/render-gitops-source.py:175-195` writes the snapshot marker under the Flux Kustomization path and computes its digest from that path only.
- `infra/scripts/render-gitops-source.py:198-210` wipes and recreates the output directory, copies only `gitops/`, renders Flux source manifests, and writes the marker.

Implementation mapping:

- Add `_copy_policy_tree(out)` parallel to `_copy_gitops_tree(out)` so `.tmp/gitops-source/local` contains both `gitops/` and `policy/`, as approved at `proposals/03-cedar-policy-source.md:103-112`.
- Call `_copy_policy_tree(out)` from `render()` after `_copy_gitops_tree(out)` and before or after `_render_source_manifests`; marker scope can stay unchanged because Flux still watches only `./gitops/channels/local`.
- Materialization should operate on the copied snapshot tree, not the source tree, so generated `.cedar` files are seed artifacts and cannot become a second committed source of truth.

New files / modules:

- No new committed module is required. The helper functions can live in `infra/scripts/render-gitops-source.py`.

Conflicting systems:

- `infra/tests/validate_platform_bootstrap.sh:312-323` currently asserts a fixed subset of rendered files but does not assert absence of `policy/`; leave this test as-is unless implementation wants explicit coverage that `policy/` is copied.
- The marker digest at `render-gitops-source.py:175-195` intentionally ignores top-level `policy/`. This matches A4 and should be left as-is unless a later proposal changes Flux's watched path.

Deletion candidates:

- None in the renderer. The old "copy only gitops" behavior is removed by adding the policy copy, not by deleting the gitops copy path.

## Bundle materialization hookpoints

Reusable hookpoints:

- `policy/cedar/channels/local/services/server-manager-api/policies.json:1-34` is the canonical local authoring file. It currently contains eight policy objects.
- `policy/cedar/channels/local/services/server-manager-api/manifest.yaml:1-13` names the local service bundle, `policies.json`, `service-identities.json`, and review checks.
- `policy/cedar/channels/local/services/server-manager-api/service-identities.json:1-21` remains the service identity fixture source and is not part of `.cedar` materialization.
- `gitops/channels/local/auth/opal-cedar/render-values.yaml:6-7` and `rendered/opal-0.0.29.yaml:194-195` already restrict OPAL policy repo matching to `.cedar`, which is why JSON cannot be the OPAL-consumed format.
- `infra/scripts/render-gitops-source.py:198-210` is the approved script surface for render-time materialization.

Recommended option from the approved proposal:

- Emit at render time by `infra/scripts/render-gitops-source.py`.
- Do not emit at commit time as committed `.cedar` files; the proposal keeps `policies.json` as the authoring source and makes `.cedar` files generated seed artifacts.
- Do not emit at deploy time with an OPAL Server init container; that would add a new in-cluster mutation path and is not in the approved scope.

Implementation mapping:

- Add a Python materializer helper in `infra/scripts/render-gitops-source.py` that reads the copied snapshot file `out/policy/cedar/channels/{channel_id}/services/server-manager-api/policies.json`.
- Emit generated files under `out/policy/cedar/channels/{channel_id}/services/server-manager-api/generated/policies/`.
- Use the policy `id` as the file stem and the policy `content` as the file body with one trailing newline, matching `proposals/03-cedar-policy-source.md:122-135`.
- Remove and recreate the generated directory on each render so stale `.cedar` files cannot survive policy deletion.
- Fail the render on duplicate IDs, missing `id`, missing `content`, path-unsafe IDs, empty content, or invalid JSON shape.

New files / modules:

- Generated snapshot files only, for example `out/policy/cedar/channels/local/services/server-manager-api/generated/policies/public-intake-allow.cedar`; these should not be committed in the repo unless a later approved proposal changes the authoring model.

Conflicting systems:

- `gitops/channels/local/auth/opal-cedar/access-policy-configmap.yaml:11-45` currently duplicates the JSON policy array in a ConfigMap. That conflicts with render-time `.cedar` materialization as the OPAL source and is a deletion candidate.

Deletion candidates:

- No committed `.cedar` files exist today under `policy/cedar/channels/local/services/server-manager-api/`; nothing to delete there.
- Delete any generated `.cedar` directory inside the snapshot before regenerating it on each render.

## kustomization + bootstrap removal hookpoints

Reusable hookpoints:

- `gitops/channels/local/auth/opal-cedar/kustomization.yaml:4-7` currently lists `rendered/opal-0.0.29.yaml`, `access-policy-configmap.yaml`, and `bootstrap-job.yaml`.
- `gitops/channels/local/auth/opal-cedar/kustomization.yaml:8-18` keeps the `client-probes-patch.yaml` patch and deletes the Helm test pod.
- `gitops/channels/local/auth/opal-cedar/bootstrap-job.yaml:1-74` is the direct writer Job. It waits for `/v1/policies` reachability at lines 36-45, then performs a bulk `PUT /v1/policies` at lines 46-49 from `ConfigMap/cedar-access-policy-bundle` mounted at lines 60-74.
- `gitops/channels/local/auth/opal-cedar/access-policy-configmap.yaml:1-45` is the duplicated policy bundle ConfigMap.

Implementation mapping:

- Keep `rendered/opal-0.0.29.yaml` in `resources`.
- Keep `client-probes-patch.yaml` in `patches`.
- Keep the `opal-e2e` deletion patch unless a later OPAL chart change removes that rendered test pod.
- Remove `access-policy-configmap.yaml` and `bootstrap-job.yaml` from `resources`.
- Delete `gitops/channels/local/auth/opal-cedar/access-policy-configmap.yaml` and `gitops/channels/local/auth/opal-cedar/bootstrap-job.yaml`.
- After Kustomize, the rendered root must have no `ConfigMap/cedar-access-policy-bundle` and no `Job/cedar-access-policy-bootstrap`, per `proposals/03-cedar-policy-source.md:137-146`.

New files / modules:

- None. This design point removes old resources from the existing Kustomization.

Conflicting systems:

- `infra/channels/local.yaml:152-155` and `infra/channels/dev.yaml:94-97` still advertise `bundle_config_map_name` and `bootstrap_job_name`. They are not used by current shell validators except as resolved contract data, but they become stale contract fields once the resources are deleted. Refactor or delete these fields and the corresponding schema requirements in `infra/schemas/platform-channel*.schema.json` if implementation scope includes keeping channel contracts truthful.

Deletion candidates:

- `gitops/channels/local/auth/opal-cedar/bootstrap-job.yaml`.
- `gitops/channels/local/auth/opal-cedar/access-policy-configmap.yaml`.
- Stale channel contract fields for deleted resources: `bundle_config_map_name` and `bootstrap_job_name` in local/dev channel files and schemas, if Step 6 contract work chooses to update the channel contract instead of merely making validators stop reading them.

## Test surface refactor hookpoints

Reusable hookpoints in `validate_access_policy_local.sh`:

- `infra/tests/validate_access_policy_local.sh:91-104` resolves the channel, bundle path, `policies.json`, and `service-identities.json`; keep this setup.
- `infra/tests/validate_access_policy_local.sh:106-120` currently extracts `ConfigMap.data.policies.json` and diffs it against canonical `policies.json`. Replace this block with `render-gitops-source.py --channel local --out <tmp>`, then compare generated `.cedar` file stems and contents against canonical policy IDs and contents.
- `infra/tests/validate_access_policy_local.sh:122-136` renders the local root and currently requires `name: cedar-access-policy-bootstrap` at line 123. Replace that with negative assertions that no `cedar-access-policy-bootstrap` Job and no `cedar-access-policy-bundle` ConfigMap render; keep service identity and RBAC checks at lines 124-136.
- `infra/tests/validate_access_policy_local.sh:156-158` currently waits for `deployment/opal-client` and `job/cedar-access-policy-bootstrap`. Remove the Job wait and replace the success condition with policy-ID hydration.
- `infra/tests/validate_access_policy_local.sh:162-185` already runs a curl pod in `auth-system` and reaches `http://opal-client:8180`; extend this command to poll `/v1/policies` for canonical IDs before the existing `/v1/is_authorized` probes.
- `infra/tests/validate_access_policy_local.sh:204-205` invokes `verify-service-identity-claim.sh`; that script must receive the same Job-wait removal or this validator will still fail after the bootstrap Job is deleted.

Reusable hookpoints in `validate_tenant_isolation_local.sh`:

- `infra/tests/validate_tenant_isolation_local.sh:159-165` statically asserts tenant policy IDs against canonical `policies.json`; keep this.
- `infra/tests/validate_tenant_isolation_local.sh:206-207` waits for `deployment/opal-client` and the bootstrap Job. Remove the Job wait and reuse the policy-ID gate before building tenant authorization payloads.
- `infra/tests/validate_tenant_isolation_local.sh:211-237` already uses a curl pod in `auth-system` to call `/v1/policies` and `/v1/is_authorized`; extend the `/v1/policies` loop to assert expected IDs, not only endpoint reachability.

Reusable hookpoints in `test_public_intake_policy_fixture.py`:

- `infra/tests/test_public_intake_policy_fixture.py:44-93` contains matrix, bundle-content, and no-service-identity guards; keep these.
- `infra/tests/test_public_intake_policy_fixture.py:96-105` asserts validator text still contains `"GitOps ConfigMap policy differs from policy repo"`. Update this to the new seeded-source equality failure message or helper name, while retaining the guards that `application:submit_public` and `web-intake.local` are not hard-coded in the shell validator.

Reusable hookpoints in `test_access_policy_contract.py`:

- `infra/tests/test_access_policy_contract.py:29-40` reads canonical policies and service identities; keep these helpers.
- `infra/tests/test_access_policy_contract.py:43-45` defines `_opal_bundle_policies()` by reading `fixture["bundle"]["gitops_configmap"]`; replace it with a generated-seeded-policy helper that models the render-time materialization contract.
- `infra/tests/test_access_policy_contract.py:68-79` currently asserts ConfigMap policy objects equal repo policy objects; change this to assert generated file stems equal canonical IDs and generated contents equal canonical contents.
- `infra/tests/test_access_policy_contract.py:95-104` uses `_opal_bundle_policies()` for token-safety coverage; make it use the generated `.cedar` map or canonical/generated combined content instead of the deleted ConfigMap.

Reusable hookpoints in fixture contract:

- `infra/tests/fixtures/contracts/access_policy_matrix.yml:39-42` currently names `policy_file`, `service_identity_file`, and `gitops_configmap`. Replace `gitops_configmap` with a seeded generated policy directory or generated policy fixture key.

Other bootstrap-Job-completion waits:

- `infra/scripts/verify-service-identity-claim.sh:80-96` already has an inline curl command against `opal-client:8180`, but only checks endpoint reachability.
- `infra/scripts/verify-service-identity-claim.sh:106-107` waits for `job/cedar-access-policy-bootstrap`; remove this wait and reuse the policy-ID gate before the Buildkite authorization proof.
- `infra/tests/validate_auth_stack_local.sh:134-143` asserts `access-policy-configmap.yaml` and `bootstrap-job.yaml` exist; remove these file assertions or invert them if auth-stack validation stays responsible for no direct writer.
- `infra/tests/validate_auth_stack_local.sh:188-200` currently requires `name: cedar-access-policy-bootstrap` in rendered auth output; update it to require no bootstrap Job/ConfigMap and keep `CEDAR_AUTHORIZATION_URL` checks.
- `infra/tests/validate_auth_stack_local.sh:247-263` waits on the Job and then does sample user allow/deny probes. Replace the Job wait with the same policy-ID gate before the allow/deny probes.

New files / modules:

- No new test file is required by the proposal. A shared shell helper would reduce duplication, but current validators use inline curl pod snippets; Phase 6 can either add a small reusable helper under `infra/scripts/` or keep local functions in the touched validators. If added, it should only encapsulate the approved `/v1/policies` ID gate, not introduce a second loading path.

Conflicting systems:

- All ConfigMap-equality assertions conflict with the new seeded-source equality model and should be refactored.
- All `wait job/cedar-access-policy-bootstrap` gates conflict with the approved removal and must be deleted, not bypassed.

Deletion candidates:

- Text and fixture references to `GitOps ConfigMap policy differs from policy repo`.
- `fixture["bundle"]["gitops_configmap"]` and its YAML key.
- Job existence assertions and Job waits in `validate_access_policy_local.sh`, `validate_tenant_isolation_local.sh`, `verify-service-identity-claim.sh`, and `validate_auth_stack_local.sh`.

## Runtime probe placement hookpoints

Existing helper/test-utility placement:

- `infra/tests/validate_access_policy_local.sh:162-185` defines `cedar_proof_command` inline and runs a one-shot curl pod named `init-115-cedar` in namespace `auth-system`.
- `infra/tests/validate_tenant_isolation_local.sh:211-237` defines a similar inline `cedar_proof_command` and runs `init-116-cedar` in `auth-system`.
- `infra/scripts/verify-service-identity-claim.sh:80-96` defines an inline `proof_command` and runs `init-115-service-identity` in `auth-system`.
- `infra/tests/validate_auth_stack_local.sh:252-263` runs `init-114-cedar` in `auth-system` with an inline command.
- These probes reach `http://opal-client:8180` from inside the cluster, which is the right network placement for `GET /v1/policies`.

Placement recommendation from existing hookpoints:

- Add the `/v1/policies` expected-ID gate in the same curl pod command blocks before each `/v1/is_authorized` call.
- The expected IDs should be derived from canonical `policies.json` by the parent shell script and passed into the pod through an environment variable or mounted/generated shell payload, so the probe computes count dynamically and does not hard-code 8.
- On failure, print the raw `/v1/policies` response or returned IDs, matching the observability requirement at `proposals/03-cedar-policy-source.md:191` and T3 at line 211.
- For T7, reuse the same helper/gate after sleeping longer than `OPAL_POLICY_REPO_POLLING_INTERVAL=30`.

New files / modules:

- Optional: a small reusable shell helper under `infra/scripts/` could centralize "wait for OPAL policy IDs" for all four callers. This is not required by the approved proposal; existing inline command blocks are sufficient hookpoints.

Conflicting systems:

- The current "endpoint reachable" checks at `validate_access_policy_local.sh:165-172`, `validate_tenant_isolation_local.sh:213-221`, and `verify-service-identity-claim.sh:82-90` are too weak for the approved runtime gate because they do not assert non-empty policy state or expected IDs.

Deletion candidates:

- None if the reachability loops are converted into ID gates. If a shared helper is added, delete the duplicated reachability-only loops from the validators rather than retaining both checks.

## Conflicting systems / deletion candidates

Conflicting systems to delete or refactor:

- Direct Cedar writer Job: delete `gitops/channels/local/auth/opal-cedar/bootstrap-job.yaml`; it is the old split-brain writer and conflicts with OPAL as sole policy authority.
- Duplicated policy ConfigMap: delete `gitops/channels/local/auth/opal-cedar/access-policy-configmap.yaml`; the canonical authoring source remains `policy/.../policies.json`, and OPAL consumes generated `.cedar` files from Git.
- Kustomization resource entries: remove `access-policy-configmap.yaml` and `bootstrap-job.yaml` from `gitops/channels/local/auth/opal-cedar/kustomization.yaml:4-7`.
- ConfigMap equality test paths: refactor `validate_access_policy_local.sh:106-120`, `test_access_policy_contract.py:43-45`, `test_access_policy_contract.py:68-79`, and fixture key `access_policy_matrix.yml:42`.
- Bootstrap Job waits: refactor `validate_access_policy_local.sh:157`, `validate_tenant_isolation_local.sh:207`, `verify-service-identity-claim.sh:106`, and `validate_auth_stack_local.sh:249`.
- Bootstrap Job static assertions: refactor `validate_access_policy_local.sh:123` and `validate_auth_stack_local.sh:142-143`, `validate_auth_stack_local.sh:198`.
- Stale channel contract names: `infra/channels/local.yaml:154-155`, `infra/channels/dev.yaml:96-97`, and the corresponding schema-required fields advertise deleted ConfigMap/Job resources. Refactor or delete them if Step 6 contract work touches channel schemas.

Systems to leave as-is:

- `gitops/sources/local/git-daemon.yaml`; the existing `Service/git-local` and `/srv/git` backend are the source hookpoints.
- `infra/scripts/install-flux-for-channel.sh`; the seed flow already pushes the entire rendered snapshot into `/srv/git/humility-local.git`.
- Pomerium, Authentik, API `CEDAR_AUTHORIZATION_URL`, and server-manager API Cedar call sites; these are anti-scope in `proposals/03-cedar-policy-source.md:49-58`.
- `client-probes-patch.yaml`; it remains listed as a patch and still supports OPAL Client readiness against the Cedar Agent port.

## New files required

- Required new artifact from this phase: `research/05-cedar-policy-source-hookpoints.md`.
- No new committed production module is required by the approved design; use `infra/scripts/render-gitops-source.py` for copy and materialization helpers.
- Generated seed files are required at render time under `.tmp/gitops-source/local/policy/cedar/channels/local/services/server-manager-api/generated/policies/*.cedar`; they are derived artifacts, not source files.
- Optional implementation convenience: a reusable shell helper for the `/v1/policies` expected-ID gate under `infra/scripts/`. If introduced, it should replace duplicated reachability-only loops and be consumed by existing validators; it should not create a new policy loading mechanism.

## Notable observations

- The prompt's candidate URL `http://git-daemon.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git` does not match current source. The current Kubernetes Service is `git-local`, and Flux already uses `http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git` at `infra/channels/local.yaml:22`.
- The approved proposal's URL and A1 are aligned with current source. This is not an invalidated assumption.
- OPAL should clone the repo root, not a `policy/` sub-path. The `policy/` tree becomes part of the worktree after cloning the same `humility-local.git` repo.
- `infra/channels/local.yaml` and `infra/channels/dev.yaml` still expose ConfigMap/Job names in the access-policy contract. They are not in the proposal's explicit test-surface list, but they are stale once the resources are deleted and should be handled during Step 6 contract/test work.
- `plans/risk/init-121-supported-surface.md` flags two omitted validators, `verify-service-identity-claim.sh` and `validate_auth_stack_local.sh`, as a Step 6 obligation. Current `rg` confirms both still wait on `job/cedar-access-policy-bootstrap`.
- A2 remains the critical runtime assumption: static source supports `.cedar` extension matching, but only a live `/v1/policies` probe can prove OPAL loads generated files under the expected policy IDs.
