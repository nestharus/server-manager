# INIT-103 Phase 5 Hookpoint Research

Binding spec: `.pipeline/proposal.md` (1039 lines). Supporting synthesis:
`.pipeline/synthesis.md` D1..D11. Current INIT-103 worktree is identical to
`../init-102-gitops-substrate` for `gitops/`, `infra/channels/`, and
`infra/scripts/` except for an `infra/scripts/__pycache__` directory in the
INIT-102 worktree.

Research only. No production code changes are proposed here.

## 1. Reuse Points

R1. INIT-102 Flux substrate, extended in place.

- INIT-103 depends on INIT-102's committed Flux substrate: proposal binding says
  INIT-102 provides raw Git source, `source-controller` plus
  `kustomize-controller`, bootstrap-only SOPS+age, and no Helm controller
  (`.pipeline/proposal.md:8-14`).
- Current docs identify the installed path as pinned Flux components,
  in-cluster Git daemon, `GitRepository/humility-local`, and
  `Kustomization/humility-local` (`infra/README.md:116-122`).
- Reuse action: do not add `helm-controller`, `HelmRelease`, or runtime Helm
  fetch. Render Infisical charts to raw manifests before Flux sees them
  (`.pipeline/proposal.md:266-304`).

R2. INIT-102 local GitOps overlay.

- Current local overlay is `gitops/channels/local/kustomization.yaml:1-6`;
  it includes `namespace.yaml`, the generated snapshot marker, and the
  encrypted SOPS sentinel.
- Proposal adds only one root entry, `infisical/`, to that overlay
  (`.pipeline/proposal.md:58-74`, `.pipeline/proposal.md:119-122`).
- Reuse action: add the new subtree under `gitops/channels/local/infisical/`;
  do not create a parallel top-level `k8s/`, `gitops/apps/`, or remote
  `gitops/channels/dev/` tree.

R3. INIT-102 rendered Git source snapshot.

- `infra/scripts/render-gitops-source.py` copies the whole `gitops/` tree into
  `.tmp/gitops-source/<channel>/`, renders source CRs, and writes the snapshot
  marker (`infra/scripts/render-gitops-source.py:74-80`,
  `infra/scripts/render-gitops-source.py:197-209`).
- `install-flux-for-channel.sh` renders that snapshot before applying Flux and
  seeding the in-cluster Git daemon (`infra/scripts/install-flux-for-channel.sh:234-248`).
- Reuse action: the Infisical subtree is picked up by the existing snapshot
  copy; no separate seed path is needed.

R4. INIT-102 age key channel and bootstrap SOPS rule.

- `.sops.yaml` already scopes encrypted files to
  `^gitops/bootstrap/.*\.enc\.yaml$` and encrypts `data|stringData`
  (`.sops.yaml:1-7`).
- `bootstrap-sops-age-key.sh` creates/applies the `Secret/sops-age` key channel
  (`infra/scripts/bootstrap-sops-age-key.sh:103-113`).
- `install-flux-for-channel.sh` ensures that Secret exists before applying Flux
  source CRs (`infra/scripts/install-flux-for-channel.sh:175-187`).
- Reuse action: put only the Infisical server-root bootstrap Secret on this
  channel. The Operator UA Secret remains generated post-startup and outside
  Git/SOPS (`.pipeline/proposal.md:439-451`).

R5. INIT-102 bring-up script.

- `bring-up-local-channel.sh` resolves a channel, creates or reuses the k3d
  cluster, writes kubeconfig, checks node readiness, and invokes the Flux
  installer unless `--cluster-only` is set
  (`infra/scripts/bring-up-local-channel.sh:223-230`,
  `infra/scripts/bring-up-local-channel.sh:232-314`).
- Reuse action: invoke `bootstrap-infisical-identity.sh` after Flux applies
  the server and before sample reconciliation, preserving the existing
  already-up and create paths (`.pipeline/proposal.md:439-487`).

R6. INIT-101 local channel and kubeconfig, already extended by INIT-102.

- Local channel target and topology live in `infra/channels/local.yaml:1-15`;
  the INIT-102 `gitops` block already occupies `infra/channels/local.yaml:20-32`.
- The kubeconfig default is produced by the bring-up resolver field
  `~/.kube/humility-<id>.yaml`, which resolves to
  `~/.kube/humility-local.yaml` for `local`
  (`infra/scripts/bring-up-local-channel.sh:90-116`,
  `infra/README.md:82-83`).
- Reuse action: place the `infisical` block in the same channel YAML, adjacent
  to `gitops`, and use the same kubeconfig/harness entrypoints.

R7. Channel YAML schema pattern.

- Source schema is strict and currently exposes `gitops` as a top-level block
  (`infra/schemas/platform-channel.schema.json:16-50`), with `gitops` required
  for `k3d-local` (`infra/schemas/platform-channel.schema.json:66-83`).
- Resolved schema mirrors that shape (`infra/schemas/platform-channel-resolved.schema.json:17-47`,
  `infra/schemas/platform-channel-resolved.schema.json:49-67`).
- Existing `gitops` field definitions are strict maps
  (`infra/schemas/platform-channel.schema.json:270-335`,
  `infra/schemas/platform-channel-resolved.schema.json:254-319`).
- Reuse action: add a sibling `$defs.infisical` and require `["gitops",
  "infisical"]` only for `cluster.target == "k3d-local"` as bound by the
  proposal (`.pipeline/proposal.md:124-264`).

R8. Resolver inheritance.

- Resolver deep-merges parent and child channel maps generically
  (`infra/scripts/resolve_platform_channel.py:148-156`,
  `infra/scripts/resolve_platform_channel.py:179-208`).
- Local child fixture currently inherits from `local` with no concrete
  `gitops` block (`infra/channels/fixtures/local-child.yaml:1-7`).
- Reuse action: let `infisical` inherit through the existing deep merge. Avoid
  compatibility aliases such as `project_slug`, `env_slug`, or
  `service_token_secret_name` (`.pipeline/proposal.md:262-264`).

R9. Channel registry validator.

- Validator discovers active and fixture channels, validates sources, resolves
  active channels, and checks active state keys
  (`infra/scripts/validate_platform_channels.py:34-42`,
  `infra/scripts/validate_platform_channels.py:55-85`,
  `infra/scripts/validate_platform_channels.py:87-104`).
- Reuse action: add Infisical schema/resolver fixture assertions here and in
  the new pytest file. Keep `dev` valid without `infisical`.

R10. Tool installer framework.

- Existing installer already has version constants, checksum verification,
  `--check`, `--install`, `--no-color`, `~/.local/bin`, version probes, and
  idempotent reinstall behavior (`infra/scripts/install-cluster-tools.sh:4-15`,
  `infra/scripts/install-cluster-tools.sh:138-148`,
  `infra/scripts/install-cluster-tools.sh:273-281`,
  `infra/scripts/install-cluster-tools.sh:391-427`).
- Reuse action: extend this script with Helm `v3.20.2` and Infisical CLI
  `v0.43.78`; do not add a second tool installer
  (`.pipeline/proposal.md:571-592`).

R11. SOPS boundary linter.

- Current linter allows exactly one encrypted file and rejects
  runtime-secret-shaped path components and keys
  (`infra/scripts/lint-sops-boundary.py:14-22`,
  `infra/scripts/lint-sops-boundary.py:25-30`,
  `infra/scripts/lint-sops-boundary.py:67-90`).
- Reuse action: convert `ALLOWED_FILE` to an exact two-file allowlist and add a
  file-specific key allowlist for Infisical server-root keys. Keep the
  directory containment and runtime-secret rejection behavior
  (`.pipeline/proposal.md:395-437`).

R12. Existing bootstrap harness.

- Default harness already checks channel schema/resolution, tool installer,
  GitOps rendering, Flux lockfile shape, and SOPS boundary
  (`infra/tests/validate_platform_bootstrap.sh:850-953`).
- Cluster mode already brings up local, waits Flux Ready, verifies the snapshot
  marker, checks git-daemon restart recovery, reruns bring-up, then deletes
  the cluster (`infra/tests/validate_platform_bootstrap.sh:710-848`).
- Reuse action: call the new Infisical runtime harness from cluster mode after
  Flux is Ready and before local cleanup (`.pipeline/proposal.md:742-785`).

R13. INIT-102 docs and handoff text.

- `gitops/README.md` already frames `gitops/bootstrap/` as bootstrap-only and
  says runtime application secrets move through Infisical in INIT-103
  (`gitops/README.md:12-16`).
- `infra/README.md` states runtime application secrets, Discord tokens,
  database passwords, and Infisical runtime data belong to INIT-103
  (`infra/README.md:188-190`).
- `.pipeline/implementation.md` gives the INIT-103 handoff:
  local overlay, Flux install path, rendered GitOps source pipeline, age key
  channel, and no runtime app secrets in SOPS (`.pipeline/implementation.md:61-82`).
- Reuse action: update these docs; do not introduce a new documentation root.

R14. Flux lockfile guardrail.

- Harness asserts the Flux lockfile has exactly two Deployments and excludes
  helm, notification, and image controller Deployments
  (`infra/tests/validate_platform_bootstrap.sh:291-323`).
- Reuse action: keep that guard. INIT-103 Helm use is render-time only and
  must not create a Helm controller runtime surface.

R15. External pins verified.

- Proposal pins Helm, chart versions, Infisical images, PostgreSQL, Redis, and
  CLI versions (`.pipeline/proposal.md:271-282`).
- Cloudsmith Helm index currently contains `infisical-standalone` `1.8.0` and
  `secrets-operator` `0.10.32` (verified 2026-04-26 by index fetch).
- `mirror.gcr.io/bitnamilegacy/postgresql:16.2.0-debian-11-r16` and
  `mirror.gcr.io/bitnamilegacy/redis:7.2.4-debian-11-r18` both returned
  HTTP 200 from the registry manifest endpoint on 2026-04-26.
- Helm tarball `https://get.helm.sh/helm-v3.20.2-linux-amd64.tar.gz` and
  Infisical CLI tarball
  `https://github.com/Infisical/cli/releases/download/v0.43.78/cli_0.43.78_linux_amd64.tar.gz`
  returned HTTP 200.

Reuse-point count: 15.

## 2. Collision Points

C1 [HIGH]. Current SOPS linter rejects the proposed Infisical bootstrap file.

- Current shape: `ALLOWED_FILE` is only
  `gitops/bootstrap/sops-sentinel.enc.yaml`, and every path component/key is
  checked for `^infisical`, `password`, and other runtime-secret patterns
  (`infra/scripts/lint-sops-boundary.py:15-22`,
  `infra/scripts/lint-sops-boundary.py:67-90`).
- Proposed file path contains `infisical`, and proposed keys include
  `INFISICAL_AUTO_BOOTSTRAP_PASSWORD`
  (`.pipeline/proposal.md:395-437`).
- Required resolution: update the linter and its tests in the same slice as
  the encrypted file. Do not weaken to `gitops/bootstrap/*.enc.yaml`.

C2 [HIGH]. Strict channel schema currently has no `infisical` property.

- Current source/resolved schemas are `additionalProperties: false` and only
  define `gitops`, not `infisical`
  (`infra/schemas/platform-channel.schema.json:5-50`,
  `infra/schemas/platform-channel-resolved.schema.json:5-47`).
- Current `local.yaml` has `gitops` but no `infisical`
  (`infra/channels/local.yaml:20-32`).
- Proposal requires `infisical` for `k3d-local` and optional omission for
  `vultr-vms` (`.pipeline/proposal.md:124-264`).
- Required resolution: schema update, `local.yaml` update, resolver/validator
  tests, and local-child inheritance need to land together in SLICE-103.05.

C3 [MEDIUM]. Existing `.pipeline/implementation.md` has INIT-101/102 shape.

- Current file starts as `# INIT-101 Implementation` and records INIT-102
  handoff content (`.pipeline/implementation.md:1-17`,
  `.pipeline/implementation.md:40-82`).
- Proposal requires `.pipeline/implementation.md` to record completed
  INIT-103 slices, verification commands, and INIT-104 handoff
  (`.pipeline/proposal.md:787-801`).
- Required resolution: replace or clearly rewrite this artifact for INIT-103;
  do not append a second unrelated implementation report below stale content.

C4 [MEDIUM]. Synthesis directory names differ from the binding proposal.

- Synthesis D1/D2 names `gitops/channels/local/infisical-server/` and
  `gitops/channels/local/infisical-operator/`
  (`.pipeline/synthesis.md:20-27`, `.pipeline/synthesis.md:57-64`).
- Binding proposal names `gitops/channels/local/infisical/server/` and
  `gitops/channels/local/infisical/operator/`
  (`.pipeline/proposal.md:96-122`, `.pipeline/proposal.md:1013-1019`).
- Required resolution: follow the proposal. Treat synthesis names as superseded
  by the proposal's D-record binding confirmation.

C5 [MEDIUM]. Harness insertion point is inside a create/delete flow.

- Existing cluster harness deletes the local cluster after bring-up/reconcile
  checks (`infra/tests/validate_platform_bootstrap.sh:710-848`).
- Proposal expects Infisical runtime checks in cluster mode and a second
  bring-up/idempotency proof (`.pipeline/proposal.md:742-785`,
  `.pipeline/proposal.md:813-873`).
- Required resolution: insert the Infisical runtime harness before local
  cleanup, or it will validate against a deleted cluster.

C6 [LOW]. Flux lockfile contains Helm source CRD/RBAC strings even though
runtime Helm is forbidden.

- Current `gitops/flux/gotk-components.yaml` contains Helm source CRDs/RBAC
  strings, but harness excludes only Helm controller Deployments
  (`infra/tests/validate_platform_bootstrap.sh:291-323`).
- Proposal's render script must fail on `HelmRelease`, `OCIRepository`, Helm
  ownership annotations, and unpinned images in the rendered Infisical outputs
  (`.pipeline/proposal.md:376-389`, `.pipeline/proposal.md:633-640`).
- Required resolution: scope render-script forbidden-token checks to the
  Infisical rendered output, not the whole repository or Flux lockfile.

C7 [LOW]. Infisical CLI asset lives in `Infisical/cli`, not the main monorepo.

- Proposal names the asset but not the repository URL
  (`.pipeline/proposal.md:577-590`).
- Verified working URL:
  `https://github.com/Infisical/cli/releases/download/v0.43.78/cli_0.43.78_linux_amd64.tar.gz`.
- URLs under `https://github.com/Infisical/infisical/releases/...` returned
  404 during this research.
- Required resolution: installer must use the `Infisical/cli` release path.

Collision count: 7 total: 2 high, 3 medium, 2 low.

## 3. Deletion Candidates

None for implementation code or repo layout. INIT-103 is additive on top of
INIT-102.

The only replacement performed by this research phase is this hookpoint
artifact itself: the pre-existing `.pipeline/hookpoints.md` contained stale
INIT-102 Phase 5 hookpoint research and is not an implementation deletion.

Deletion candidate count: 0.

## 4. Channel YAML Hooks

Local channel:

- Add the proposal's top-level `infisical` block in `infra/channels/local.yaml`
  after the existing `gitops` block, so all reconciliation/runtime-secret
  channel metadata is adjacent (`infra/channels/local.yaml:20-32`,
  `.pipeline/proposal.md:238-251`).
- The block should be concrete, not defaulted implicitly:
  `server_url`, `project_id`, `environment`, `secrets_path`, `auth_method`,
  UA Secret name/namespace, operator namespace, and `resync_interval`
  (`.pipeline/proposal.md:175-233`).

Local child fixture:

- `infra/channels/fixtures/local-child.yaml` should keep inheriting from
  `local` (`infra/channels/fixtures/local-child.yaml:1-7`). Tests should prove
  the resolved child inherits `infisical` through the existing deep merge.

Dev channel:

- Do not add `infisical` to `infra/channels/dev.yaml` in INIT-103. Current dev
  is `cluster.target: vultr-vms`, with `gitops` deliberately omitted
  (`infra/channels/dev.yaml:8-28`).
- Proposal explicitly keeps `infisical` optional for `vultr-vms` and defers
  remote Flux/Infisical installation (`.pipeline/proposal.md:253-264`,
  `.pipeline/proposal.md:968-977`).

## 5. Slice-by-Slice Surface Map

### SLICE-103.01 - Toolchain Pins

- Files added: none.
- Files modified: `infra/scripts/install-cluster-tools.sh`, `infra/README.md`,
  `infra/tests/validate_platform_bootstrap.sh` (`.pipeline/proposal.md:596-620`).
- Files deleted: none.
- Adjacent surfaces: existing K3D/Flux/SOPS/age installer framework
  (`infra/scripts/install-cluster-tools.sh:4-15`,
  `infra/scripts/install-cluster-tools.sh:273-281`,
  `infra/scripts/install-cluster-tools.sh:391-427`); harness tool-version
  assertions (`infra/tests/validate_platform_bootstrap.sh:604-646`).

### SLICE-103.02 - Infisical Server Raw Manifests

- Files added:
  `gitops/channels/local/infisical/kustomization.yaml`,
  `gitops/channels/local/infisical/namespace.yaml`,
  `gitops/channels/local/infisical/server/kustomization.yaml`,
  `gitops/channels/local/infisical/server/render-values.yaml`,
  `gitops/channels/local/infisical/server/rendered/infisical-standalone-1.8.0.yaml`,
  `infra/scripts/render-infisical-manifests.sh`.
- Files modified: `gitops/channels/local/kustomization.yaml`
  (`.pipeline/proposal.md:622-650`).
- Files deleted: none.
- Adjacent surfaces: local overlay ordering (`gitops/channels/local/kustomization.yaml:1-6`),
  GitOps snapshot copy (`infra/scripts/render-gitops-source.py:74-80`), SOPS
  sentinel path, Flux Kustomization readiness.

### SLICE-103.03 - Infisical Operator Raw Manifests

- Files added:
  `gitops/channels/local/infisical/operator/kustomization.yaml`,
  `gitops/channels/local/infisical/operator/render-values.yaml`,
  `gitops/channels/local/infisical/operator/rendered/secrets-operator-0.10.32.yaml`.
- Files modified: `infra/scripts/render-infisical-manifests.sh`
  (`.pipeline/proposal.md:652-675`).
- Files deleted: none.
- Adjacent surfaces: cluster-scoped CRDs and RBAC
  (`.pipeline/proposal.md:536-569`), Flux no-helm-controller guard
  (`infra/tests/validate_platform_bootstrap.sh:291-323`), INIT-116 scoped RBAC
  handoff (`.pipeline/proposal.md:551-558`).

### SLICE-103.04 - Bootstrap Boundary And Identity Script

- Files added: `gitops/bootstrap/infisical-server-bootstrap.enc.yaml`,
  `infra/scripts/bootstrap-infisical-identity.sh`,
  `infra/tests/test_sops_boundary_infisical.py`.
- Files modified: `gitops/channels/local/infisical/server/kustomization.yaml`,
  `infra/scripts/lint-sops-boundary.py`,
  `infra/scripts/bring-up-local-channel.sh`
  (`.pipeline/proposal.md:677-706`).
- Files deleted: none.
- Adjacent surfaces: `.sops.yaml:1-7`,
  `infra/scripts/lint-sops-boundary.py:14-22`,
  `infra/scripts/install-flux-for-channel.sh:175-187`,
  `infra/scripts/bring-up-local-channel.sh:223-230`.

### SLICE-103.05 - Channel Schema And Sample InfisicalSecret

- Files added:
  `infra/tests/test_platform_channel_infisical_schema.py`,
  `gitops/channels/local/infisical/sample/kustomization.yaml`,
  `gitops/channels/local/infisical/sample/namespace.yaml`,
  `gitops/channels/local/infisical/sample/infisical-local-sample.yaml`.
- Files modified: `infra/schemas/platform-channel.schema.json`,
  `infra/schemas/platform-channel-resolved.schema.json`,
  `infra/channels/local.yaml`, `infra/channels/fixtures/local-child.yaml`,
  `infra/scripts/resolve_platform_channel.py`,
  `infra/scripts/validate_platform_channels.py`
  (`.pipeline/proposal.md:708-740`).
- Files deleted: none.
- Adjacent surfaces: strict source/resolved schema
  (`infra/schemas/platform-channel.schema.json:5-50`,
  `infra/schemas/platform-channel-resolved.schema.json:5-47`), resolver deep
  merge (`infra/scripts/resolve_platform_channel.py:148-208`), dev omission
  (`infra/channels/dev.yaml:8-28`).

### SLICE-103.06 - Local Runtime Harness

- Files added: `infra/tests/validate_infisical_runtime.sh`.
- Files modified: `infra/tests/validate_platform_bootstrap.sh`,
  `infra/README.md` (`.pipeline/proposal.md:742-785`).
- Files deleted: none.
- Adjacent surfaces: existing cluster harness flow
  (`infra/tests/validate_platform_bootstrap.sh:710-848`), Flux wait points
  (`infra/tests/validate_platform_bootstrap.sh:742-752`), local kubeconfig
  proof (`infra/tests/validate_platform_bootstrap.sh:724-740`).

### SLICE-103.07 - Documentation And INIT-104 Handoff

- Files added: none.
- Files modified: `gitops/README.md`, `infra/README.md`,
  `.pipeline/implementation.md` (`.pipeline/proposal.md:787-811`).
- Files deleted: none.
- Adjacent surfaces: current INIT-103 handoff content in
  `.pipeline/implementation.md:61-82`, GitOps runtime-secret note
  (`gitops/README.md:12-16`), infra runtime-secret note
  (`infra/README.md:188-190`).

## 6. Implementation Blockers

B-001. Helm and Infisical CLI are not installed in the current shell.

- Observed: `helm=MISSING`, `infisical=MISSING`.
- Self-resolving: SLICE-103.01 extends the installer to install/check both
  tools (`.pipeline/proposal.md:571-620`).

B-002. SOPS linter must change before the new encrypted file can pass.

- Current linter permits exactly one file and rejects `infisical`/`password`
  shaped path components or keys (`infra/scripts/lint-sops-boundary.py:15-22`,
  `infra/scripts/lint-sops-boundary.py:67-90`).
- Proposed bootstrap file and keys require the exact allowlist/key whitelist
  extension (`.pipeline/proposal.md:395-437`).

B-003. Channel schema/local YAML changes must be atomic in SLICE-103.05.

- Strict schemas currently reject unknown top-level properties and require only
  `gitops` for local (`infra/schemas/platform-channel.schema.json:5-83`,
  `infra/schemas/platform-channel-resolved.schema.json:5-67`).
- If schema changes land without `infra/channels/local.yaml`, validation will
  fail; if local YAML lands before schema changes, validation will also fail.

B-004. Infisical CLI download URL must use the `Infisical/cli` repository.

- Working asset verified:
  `https://github.com/Infisical/cli/releases/download/v0.43.78/cli_0.43.78_linux_amd64.tar.gz`.
- `Infisical/infisical` release URLs for this CLI asset returned 404. The
  proposal names the asset and checksum but not the repository URL
  (`.pipeline/proposal.md:577-590`).

B-005. `.pipeline/implementation.md` is stale for INIT-103.

- Current file is an INIT-101/102 implementation artifact
  (`.pipeline/implementation.md:1-17`, `.pipeline/implementation.md:61-82`).
- SLICE-103.07 acceptance requires INIT-103 completed slices, verification
  commands, and INIT-104 handoff (`.pipeline/proposal.md:787-801`).

Not blockers:

- Proposed new Infisical manifest/test/script files are currently missing, but
  each is introduced by an earlier planned slice before use.
- PostgreSQL and Redis mirror images are accessible from `mirror.gcr.io`.
- Both referenced Helm charts are present in the Cloudsmith index.
- `dev.yaml` omits `infisical` by design in INIT-103.

Implementation blocker count: 5.

## 7. Cross-INIT Impact

INIT-104 handoff:

- Proposal names the object-storage interface: project `platform-storage`,
  environment from `channel.infisical.environment`, path `/object-storage`,
  UA auth, operator namespace from `channel.infisical.operator_namespace`,
  and consumer namespace expected as `minio-system` locally
  (`.pipeline/proposal.md:979-993`).
- Local keys: `/object-storage/MINIO_ROOT_USER` and
  `/object-storage/MINIO_ROOT_PASSWORD` (`.pipeline/proposal.md:995-1000`).
- Remote keys: `/object-storage/VULTR_OS_ACCESS_KEY` and
  `/object-storage/VULTR_OS_SECRET_KEY` (`.pipeline/proposal.md:1002-1007`).
- INIT-104 owns its own `InfisicalSecret` CRs and must not put storage
  credentials in `gitops/bootstrap/` or any SOPS-encrypted file
  (`.pipeline/proposal.md:1009-1011`).

INIT-115 / INIT-116 handoff:

- INIT-115 owns Infisical access policy, admin model, credential rotation,
  break-glass, age key rotation, and Operator credential lifecycle
  (`.pipeline/proposal.md:961-962`).
- INIT-116 owns tenant isolation, namespace delegation, scoped Operator RBAC,
  per-tenant paths, and multi-tenant project policy
  (`.pipeline/proposal.md:963-964`).
- INIT-103 explicitly accepts cluster-wide Operator watch/write for the local
  proof and defers scoping (`.pipeline/proposal.md:551-558`,
  `.pipeline/proposal.md:926-934`).

## Output Counts

- Reuse-point count: 15
- Collision count: 7 total: 2 high, 3 medium, 2 low
- Deletion candidate count: 0
- Implementation blocker count: 5
