# INIT-102 Phase 5 Hookpoint Research

Inputs verified:

- Current worktree: `/home/nes/projects/server-manager/worktrees/init-102-gitops-substrate`
- Current branch: `feat/init-102-gitops-substrate`
- Current HEAD: `d9e4a9d1c0832cfa54703e161a044fc5d8c46ae0`
- Binding proposal: `.pipeline/proposal.md`, 1059 lines
- Synthesis: `.pipeline/synthesis.md`, 486 lines, D1 through D11
- INIT-101 reference worktree: `/home/nes/projects/server-manager/worktrees/init-101-k3s-control-cluster`, HEAD `d9e4a9d1c0832cfa54703e161a044fc5d8c46ae0`
- INIT-009 archived reference: `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate`, HEAD `027b3b669afd80cccdbfce0e95c0681ccc81b336`

Scope rule: INIT-101 is the active substrate to extend. INIT-009 is archived
reference only; do not copy files forward. The current top-level `k8s/` tree is
stale and must be deleted, not reshaped or moved.

## 1. Reuse Points

R1. Extend the INIT-101 tool installer in place:

- Path: `infra/scripts/install-cluster-tools.sh`
- Evidence: current k3d-only pin and install target at lines 4-5; CLI shape at
  lines 14-25; k3d checksum dispatch at lines 68-78; k3d version check and
  install path at lines 99-170.
- Extension point: add pinned `flux v2.8.6`, `sops v3.12.2`, `age v1.3.1`,
  and `age-keygen v1.3.1` beside the existing `K3D_VERSION` constant. Keep
  `--check`, `--install`, `--no-color`, and `~/.local/bin`.
- Proposal binding: `.pipeline/proposal.md:651-681`, `.pipeline/proposal.md:687-698`.

R2. Extend local bring-up rather than adding a parallel cluster lifecycle:

- Path: `infra/scripts/bring-up-local-channel.sh`
- Evidence: repo/resolver/tool installer wiring at lines 4-7; current CLI at
  lines 11-21; resolver field extraction at lines 78-105; preflight and channel
  resolution at lines 211-239; cluster create/existing-cluster flow at lines
  242-285.
- Extension point: add `--cluster-only`; after the k3d cluster exists, the
  kubeconfig is written, and nodes are Ready, call
  `infra/scripts/install-flux-for-channel.sh --channel "$CHANNEL_ID"` unless
  `--cluster-only` is set.
- Important collision inside this reuse point: an existing matching cluster
  exits at lines 264-269. The Flux install call must run before that exit, or a
  pre-existing INIT-101 cluster will never receive Flux.
- Proposal binding: `.pipeline/proposal.md:324-378`, `.pipeline/proposal.md:748-766`.

R3. Extend local deletion cleanup before deleting k3d:

- Path: `infra/scripts/delete-local-channel.sh`
- Evidence: current resolver/channel wiring at lines 4-6; current CLI at lines
  8-17; target/kubeconfig resolution at lines 59-77 and 84-101; k3d and
  kubeconfig deletion at lines 103-121.
- Extension point: when the kubeconfig is reachable, delete Flux local resources
  first: Flux custom resources, `git-system`, `humility-gitops-sentinel`, and
  `flux-system` via `flux uninstall` or equivalent rollback sequence. Then
  delete the k3d cluster and kubeconfig as INIT-101 already does.
- Proposal binding: `.pipeline/proposal.md:89-95`, `.pipeline/proposal.md:959-970`.

R4. Extend `local.yaml` with the concrete `gitops` block:

- Path: `infra/channels/local.yaml`
- Evidence: local is active channel id at lines 1-7; target is `k3d-local` at
  lines 8-15; state key is `channels/local/terraform.tfstate` at lines 16-19.
- Extension point: append top-level `gitops:` after `state:`. Required values
  are listed in `.pipeline/proposal.md:288-300`.
- Proposal binding: `.pipeline/proposal.md:181-312`, `.pipeline/synthesis.md:227-269`.

R5. Preserve `dev.yaml` without `gitops`:

- Path: `infra/channels/dev.yaml`
- Evidence: dev is active channel id at lines 1-7; target is `vultr-vms` at
  lines 8-23; state key is `channels/dev/terraform.tfstate` at lines 24-27.
- Extension point: no field addition in INIT-102. The source and resolved
  schemas must accept this absence because remote Flux install is out of scope.
- Proposal binding: `.pipeline/proposal.md:302-312`, `.pipeline/synthesis.md:423-456`.

R6. Extend the source channel JSON schema:

- Path: `infra/schemas/platform-channel.schema.json`
- Evidence: strict top-level `additionalProperties: false` and properties at
  lines 5-47; root-channel conditional at lines 48-62; cluster target shape at
  lines 80-127; existing `$defs` area at lines 63-248.
- Extension point: add top-level `gitops` under `properties`, add a second
  `allOf` conditional requiring `gitops` when `cluster.target == k3d-local`,
  and add `$defs.gitops`.
- Proposal binding: `.pipeline/proposal.md:181-286`.

R7. Extend the resolved channel JSON schema:

- Path: `infra/schemas/platform-channel-resolved.schema.json`
- Evidence: required top-level fields at lines 7-16; strict properties at
  lines 17-43; cluster target shape at lines 62-109; existing `$defs` area at
  lines 45-230.
- Extension point: add `gitops` to properties and require it conditionally for
  resolved `k3d-local` channels. Do not require it for `vultr-vms`.
- Proposal binding: `.pipeline/proposal.md:181-286`.

R8. Extend the resolver's inheritance and defaulting path:

- Path: `infra/scripts/resolve_platform_channel.py`
- Evidence: source/resolved schema validation at lines 91-115; load and id
  validation at lines 117-145; recursive deep merge at lines 148-156 and
  179-195; resolved finalization at lines 198-208; CLI at lines 221-237.
- Extension point: allow `gitops` to deep-merge like other top-level maps, then
  materialize `sops_age_secret_name=sops-age` and
  `decryption_secret_namespace=flux-system` before resolved-schema validation.
  Add target-specific checks here if the JSON Schema cannot express the error
  clearly enough.
- Proposal binding: `.pipeline/proposal.md:283-312`, `.pipeline/synthesis.md:227-305`.

R9. Extend the registry validator:

- Path: `infra/scripts/validate_platform_channels.py`
- Evidence: active/fixture discovery at lines 34-42; source validation at
  lines 55-66; active resolve validation and state-key assertion at lines
  68-85; registry validation loop at lines 87-104.
- Extension point: after resolving active channels, assert local/k3d channels
  carry valid `gitops` fields and dev/vultr-vms channels are still valid without
  them. Keep fixtures in coverage so invalid `source_kind`, URL, and path tests
  have a natural place.
- Proposal binding: `.pipeline/proposal.md:85-88`, `.pipeline/proposal.md:732-747`.

R10. Preserve OpenTofu tfvars ownership and explicitly exclude GitOps:

- Path: `infra/scripts/generate_channel_tfvars.py`
- Evidence: `tfvars_payload()` emits cluster/state-facing variables only at
  lines 77-139; local target returns at lines 89-102; remote target returns at
  lines 104-133.
- Extension point: no Flux variable should be emitted. Add tests around this if
  necessary so `gitops` remains script-owned and does not leak into OpenTofu.
- Proposal binding: `.pipeline/proposal.md:307-312`.

R11. Extend the INIT-101 validation harness for toolchain and no-`k8s/` checks:

- Path: `infra/tests/validate_platform_bootstrap.sh`
- Evidence: generic assertions at lines 58-104; current installer check at
  lines 384-398; no-cluster script checks at lines 400-423; cluster proof at
  lines 426-529; slice validation body at lines 531-660.
- Extension point: in SLICE-102.01, expand the installer assertion to include
  Flux/SOPS/age. In SLICE-102.02, add a hard failure if top-level `k8s/` exists.
  In SLICE-102.06, either chain or preserve this harness while adding the new
  `validate_gitops_substrate.sh`.
- Proposal binding: `.pipeline/proposal.md:687-786`, `.pipeline/proposal.md:879-929`.

R12. Extend operator docs:

- Path: `infra/README.md`
- Evidence: INIT-101 overview at lines 5-15; prereqs at lines 16-30; layout at
  lines 31-50; channel/bring-up docs at lines 56-109; verification docs at
  lines 147-168; anti-scope says GitOps is INIT-102 at lines 170-179.
- Extension point: update from INIT-101 substrate-only to INIT-102 local
  GitOps substrate. Preserve remote `dev` plan-only messaging.
- Proposal binding: `.pipeline/proposal.md:687-786`, `.pipeline/proposal.md:992-1033`.

R13. Reuse `.gitignore` generated-output policy:

- Path: `.gitignore`
- Evidence: generated workspace ignores at lines 25-32, including `.tmp/`,
  `worktrees/`, `infra/channels/*/.generated/`, and `**/.terraform/`.
- Extension point: `.tmp/gitops-source/<channel>/` is already covered by
  `.tmp/`. Add only narrow ignores if implementation creates generated content
  outside `.tmp/` or outside operator home.
- Proposal binding: `.pipeline/proposal.md:420-461`, `.pipeline/proposal.md:895-901`.

R14. Preserve channel OpenTofu template boundary:

- Path: `infra/templates/platform-channel/main.tf`
- Evidence: target dispatch to `platform-cluster-k3d` at lines 15-26 and
  `platform-cluster-vms` at lines 28-44.
- Extension point: do not add `infra/modules/platform-flux/` or Kubernetes
  provider mutation to this template. Flux belongs to post-install scripts.
- Proposal binding: `.pipeline/proposal.md:313-323`, `.pipeline/synthesis.md:270-305`.

## 2. Collision Points

C1 [HIGH]. Top-level `k8s/` exists, but proposal requires it absent.

- Current evidence: `k8s/` exists and contains 38 files / 717 total lines.
  Examples: `k8s/base/kustomization.yaml:1-7`,
  `k8s/clusters/dev/control-cluster/gotk-sync.yaml:1-25`,
  `k8s/tests/test_gitops_foundation.sh:1-256`.
- Proposal target: delete `k8s/**` in SLICE-102.02
  (`.pipeline/proposal.md:96-100`, `.pipeline/proposal.md:700-713`).
- Resolution: delete, do not migrate.

C2 [HIGH]. Existing hard-environment Flux CRs conflict with local-channel Flux
shape.

- Current evidence: `k8s/clusters/dev/control-cluster/gotk-sync.yaml:1-25`
  defines `GitRepository/dev-control-cluster-root` and path
  `./k8s/clusters/dev/control-cluster/manifests`; app-cluster equivalent is
  `k8s/clusters/dev/app-cluster/gotk-sync.yaml:1-25`.
- Proposal target: one local source/sync pair under
  `gitops/sources/local/*`, named `humility-local`, pointing at
  `./gitops/channels/local` (`.pipeline/proposal.md:72-76`,
  `.pipeline/proposal.md:732-747`).
- Resolution: delete old CRs with the `k8s/` tree.

C3 [HIGH]. Existing app-cluster/Crossplane placeholders conflict with INIT-102
anti-scope.

- Current evidence: `k8s/clusters/dev/control-cluster/manifests/claims/kustomization.yaml:1-11`
  names Crossplane cluster claims; `k8s/clusters/dev/app-cluster/manifests/bootstrap/kustomization.yaml:1-11`
  names downstream Flux bootstrap.
- Proposal anti-scope: app-cluster provisioning, Crossplane, and downstream
  app workloads are future initiatives (`.pipeline/proposal.md:992-1033`).
- Resolution: delete, do not salvage.

C4 [MEDIUM]. Current bring-up idempotency exits before any future Flux
post-install would run.

- Current evidence: existing matching cluster path exits at
  `infra/scripts/bring-up-local-channel.sh:264-269`.
- Proposal target: default bring-up installs Flux after a ready INIT-101
  cluster (`.pipeline/proposal.md:371-378`, `.pipeline/proposal.md:752-766`).
- Resolution: put the Flux post-install call on both create and already-up
  paths unless `--cluster-only` is set.

C5 [MEDIUM]. Current tool installer semantics are k3d-only, while proposal
reuses the same public script for GitOps tools.

- Current evidence: `K3D_VERSION` is the only tool pin at
  `infra/scripts/install-cluster-tools.sh:4`; `main()` checks only k3d at
  lines 157-170.
- Proposal target: same script checks/installs k3d, flux, sops, age, and
  age-keygen (`.pipeline/proposal.md:651-681`).
- Resolution: extend in place; no `install-gitops-tools.sh` compatibility
  wrapper.

C6 [MEDIUM]. Proposal kubeconfig examples conflict with INIT-101 generated
kubeconfig location.

- Current evidence: bring-up defaults to `~/.kube/humility-<id>.yaml` at
  `infra/scripts/bring-up-local-channel.sh:100-101`; README documents
  `~/.kube/humility-local.yaml` at `infra/README.md:95-109`.
- Proposal evidence: post-install signature example mentions
  `~/.kube/humility-local.yaml`
  (`.pipeline/proposal.md:324-340`), and local proof says assertions run
  against that path (`.pipeline/proposal.md:879-929`).
- Resolution required before implementation: choose one path. Given INIT-101
  is the active substrate, prefer preserving `~/.kube/humility-local.yaml` and
  update INIT-102 scripts/tests accordingly, unless the proposal is amended.

C7 [LOW]. No direct script name collision for new INIT-102 scripts, but there
are nearby names.

- Current evidence: current `infra/scripts/` contains only
  `bring-up-local-channel.sh`, `delete-local-channel.sh`,
  `generate_channel_backend.py`, `generate_channel_tfvars.py`,
  `install-cluster-tools.sh`, `resolve_platform_channel.py`,
  `spawn_platform_channel.py`, and `validate_platform_channels.py`.
- Proposal new names: `install-flux-for-channel.sh`,
  `bootstrap-sops-age-key.sh`, `render-gitops-source.py`,
  `seed-local-git-source.sh`.
- Resolution: create those exact names; do not revive INIT-009
  `gitops/scripts/*`.

C8 [LOW]. No existing top-level `gitops` schema field collides by name.

- Current evidence: `rg -n 'gitops:' infra/channels infra/schemas infra/scripts`
  returns no matches. Schemas are strict and currently lack a `gitops`
  property at `infra/schemas/platform-channel.schema.json:16-47` and
  `infra/schemas/platform-channel-resolved.schema.json:17-43`.
- Resolution: additive schema extension with `schema_version: 1`, as proposal
  binds at `.pipeline/proposal.md:181-186`.

## 3. Deletion Candidates

D1. Delete `k8s/base/**`.

- Current evidence: `k8s/base/kustomization.yaml:1-7` composes platform,
  controllers, namespaces, and policies; `k8s/base/platform/kustomization.yaml:1-11`
  encodes old `gitops.foundation.*` metadata.
- Reason: stale hard-environment GitOps tree. Do not move under `gitops/`.

D2. Delete `k8s/overlays/**`.

- Current evidence: overlays exist for dev/staging/production and both
  app/control clusters; representative labels are in
  `k8s/overlays/dev/control-cluster/kustomization.yaml:1-13`.
- Reason: proposal ships only `gitops/channels/local/`.

D3. Delete `k8s/clusters/**`.

- Current evidence: hard-env roots and Flux CRs under
  `k8s/clusters/dev/control-cluster/gotk-sync.yaml:1-25` and app-cluster peers.
- Reason: conflicts with local-channel source/sync naming and remote/app
  anti-scope.

D4. Delete `k8s/tests/test_gitops_foundation.sh`.

- Current evidence: render/topology test assumes `k8s/` at
  `k8s/tests/test_gitops_foundation.sh:217-254`.
- Reason: superseded by `infra/tests/validate_gitops_substrate.sh`.

D5. Do not bring forward INIT-009 `gitops/scripts/bootstrap-flux.sh`.

- Archived evidence:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/gitops/scripts/bootstrap-flux.sh:4-23`
  uses kind/dev assumptions; lines 65-76 create kind and switch global kubectl
  context; lines 178-188 reconciles the dev channel.
- Reason: INIT-102 uses k3d/local and INIT-101 bring-up.

D6. Do not bring forward INIT-009 `gitops/scripts/install-tools.sh`.

- Archived evidence:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/gitops/scripts/install-tools.sh:4-38`
  pins flux 2.8.0, kind, sops 3.10.0, age 1.3.0, and standalone kustomize.
- Reason: INIT-102 extends `infra/scripts/install-cluster-tools.sh` with newer
  pins and no standalone kustomize.

D7. Do not bring forward INIT-009 `gitops/tests/validate_gitops.sh`.

- Archived evidence:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/gitops/tests/validate_gitops.sh:43-55`
  exposes wrong modes; lines 223-237 expect dev/crossplane/cert-manager bases.
- Reason: old proof is wrong-shaped and too broad.

D8. Do not bring forward INIT-009 Flux base artifacts.

- Archived evidence:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/gitops/bases/flux-system/gotk-components.yaml:1-4`
  was generated by Flux v2.8.0 with all six controllers; lines from `rg`
  show helm/notification/image controller resources.
- Reason: INIT-102 requires Flux v2.8.6 and source/kustomize controllers only.

D9. Do not bring forward INIT-009 `gitops/channels/dev/**`.

- Archived evidence:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/gitops/channels/dev/kustomization.yaml:1-20`
  wires dev overlay plus crossplane, cert-manager, external-dns, cluster
  security, and dev secrets.
- Reason: INIT-102 ships local overlay only.

D10. Do not bring forward INIT-009 `gitops/secrets/dev/**`.

- Archived evidence:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/gitops/secrets/dev/.sops.yaml:17-24`
  contains a placeholder recipient; `bootstrap-creds.enc.yaml:1-11` is
  placeholder plaintext/empty `stringData`.
- Reason: INIT-102 owns a local bootstrap-only SOPS sentinel.

## 4. Channel YAML Hooks

`infra/channels/local.yaml` gets the INIT-102 `gitops` block.

- Current placement: append after `state.region` at
  `infra/channels/local.yaml:16-19`.
- Bound block:

```yaml
gitops:
  source_kind: git
  git_url: http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git
  git_ref: refs/heads/main
  path: ./gitops/channels/local
  kustomization_name: humility-local
  kustomization_namespace: flux-system
  sops_age_secret_name: sops-age
  decryption_secret_namespace: flux-system
  interval: 1m
  retry_interval: 1m
  prune: true
  wait: true
```

`infra/channels/dev.yaml` deliberately omits `gitops`.

- Current evidence: file ends at `state.region` on
  `infra/channels/dev.yaml:24-27`; no `gitops` block exists.
- This matches the proposal's single-channel posture:
  `.pipeline/proposal.md:302-306` and `.pipeline/proposal.md:732-747`.
- Conflict to watch: source/resolved schemas must reject missing `gitops` only
  for `cluster.target: k3d-local`, not for `vultr-vms`.

## 5. Slice-By-Slice Surface Map

### SLICE-102.01 - Pinned GitOps Toolchain

Files added:

- None.

Files modified:

- `infra/scripts/install-cluster-tools.sh` - extend k3d-only installer
  (`infra/scripts/install-cluster-tools.sh:4-170`) with flux/sops/age pins and
  SHA256-verified install/check helpers.
- `infra/tests/validate_platform_bootstrap.sh` - update installer check at
  lines 384-398 to assert GitOps tool versions.
- `infra/README.md` - update prereqs at lines 16-30 and verification docs at
  lines 84-109.

Files deleted:

- None.

Adjacent blast radius:

- `~/.local/bin` installation behavior.
- Network downloads for pinned release assets.
- Existing k3d check contract used by `bring-up-local-channel.sh:214-218`.

### SLICE-102.02 - GitOps Layout and Flux Lockfile

Files added:

- `gitops/README.md`
- `gitops/flux/gotk-components.yaml`
- `gitops/bases/gitops-sentinel/namespace.yaml`
- `gitops/bases/gitops-sentinel/configmap.yaml`
- `gitops/bases/gitops-sentinel/kustomization.yaml`
- `gitops/channels/local/kustomization.yaml`
- `gitops/channels/local/patches/gitops-sentinel-channel.yaml`

Files modified:

- `infra/tests/validate_platform_bootstrap.sh` - add hard absence check for
  top-level `k8s/`.

Files deleted:

- `k8s/base/**`
- `k8s/overlays/**`
- `k8s/clusters/**`
- `k8s/tests/test_gitops_foundation.sh`

Adjacent blast radius:

- Any docs or plan files that refer to `k8s/` as active should be treated as
  stale unless they are historical plans.
- `kubectl kustomize gitops/channels/local` becomes the local render check.

### SLICE-102.03 - SOPS+age Bootstrap Sentinel

Files added:

- `.sops.yaml`
- `gitops/bootstrap/sops-sentinel.enc.yaml`
- `infra/scripts/bootstrap-sops-age-key.sh`

Files modified:

- `gitops/channels/local/kustomization.yaml` - include encrypted sentinel.
- `infra/README.md` - document local age key location and bootstrap-only
  boundary.

Files deleted:

- None.

Adjacent blast radius:

- Operator-local key file `~/.config/sops/age/local.txt`.
- Cluster Secret `sops-age` in namespace `flux-system`.
- No runtime secrets may enter `gitops/**/*.enc.yaml`.

### SLICE-102.04 - Channel Schema and Rendering

Files added:

- `infra/scripts/render-gitops-source.py`
- `gitops/sources/local/gitrepository.yaml`
- `gitops/sources/local/kustomization.yaml`
- `gitops/sources/local/kustomization.kustomize.yaml`
- `infra/tests/test_platform_channel_gitops.py`
- `infra/tests/test_gitops_rendering.py`

Files modified:

- `infra/schemas/platform-channel.schema.json`
- `infra/schemas/platform-channel-resolved.schema.json`
- `infra/channels/local.yaml`
- `infra/scripts/resolve_platform_channel.py`
- `infra/scripts/validate_platform_channels.py`
- `infra/scripts/generate_channel_tfvars.py` only if needed to assert
  `gitops` exclusion.

Files deleted:

- None.

Adjacent blast radius:

- Channel fixture inheritance under `infra/channels/fixtures/*.yaml`.
- Resolver CLI output consumed by bring-up/delete/generator scripts.
- Strict schema `additionalProperties: false`; every new field must be
  declared in both source and resolved schemas.

### SLICE-102.05 - Local Git Source and Flux Post-Install

Files added:

- `gitops/local-git-server/namespace.yaml`
- `gitops/local-git-server/pvc.yaml`
- `gitops/local-git-server/deployment.yaml`
- `gitops/local-git-server/service.yaml`
- `gitops/local-git-server/kustomization.yaml`
- `infra/scripts/install-flux-for-channel.sh`
- `infra/scripts/seed-local-git-source.sh`

Files modified:

- `infra/scripts/bring-up-local-channel.sh`
- `infra/scripts/delete-local-channel.sh`
- `infra/README.md`

Files deleted:

- None.

Adjacent blast radius:

- Live local cluster namespaces `flux-system`, `git-system`, and
  `humility-gitops-sentinel`.
- `.tmp/gitops-source/local/last-seed.json`.
- In-cluster anonymous Git service on HTTP 8080, ClusterIP only.

### SLICE-102.06 - End-to-End Harness and Documentation

Files added:

- `infra/tests/validate_gitops_substrate.sh`

Files modified:

- `infra/tests/validate_platform_bootstrap.sh`
- `infra/README.md`
- `.pipeline/implementation.md` if slice status is recorded there.

Files deleted:

- None beyond SLICE-102.02 deletion verification.

Adjacent blast radius:

- Full local k3d lifecycle.
- Flux CRDs and controller uninstall order.
- SOPS decrypt lint and runtime-secret-shaped key scan.
- Git daemon Pod restart recovery.

## 6. Implementation Blockers

B1 [HIGH]. Kubeconfig path inconsistency must be resolved before tests are
written.

- Current INIT-101 path: `~/.kube/humility-local.yaml`
  (`infra/scripts/bring-up-local-channel.sh:100-101`,
  `infra/README.md:95-109`).
- Proposal example/path: `~/.kube/humility-local.yaml`
  (`.pipeline/proposal.md:324-340`, `.pipeline/proposal.md:879-929`).
- Recommendation: preserve INIT-101 path and adjust INIT-102 implementation
  scripts/tests to read the resolved kubeconfig default.

B2 [MEDIUM]. Existing bring-up "already up" path will skip Flux unless edited
carefully.

- Evidence: `infra/scripts/bring-up-local-channel.sh:264-269`.
- Required resolution: post-install must run on create and already-up paths.

B3 [MEDIUM]. Existing harness assertion expects second bring-up to be a no-op
string match.

- Evidence: `infra/tests/validate_platform_bootstrap.sh:488-498`.
- Required resolution: INIT-102 default bring-up may reapply Flux and reseed;
  update harness expectations in the same slice that changes bring-up.

B4 [MEDIUM]. Exact SHA256 pins for new downloadable tools are not present in
current code.

- Evidence: current installer has k3d SHA256 only at
  `infra/scripts/install-cluster-tools.sh:68-78`.
- Required resolution: SLICE-102.01 must add pinned SHA256 values for flux,
  sops, and age release assets before any installer test can pass.

B5 [LOW]. No `gitops/` directory exists yet.

- Evidence: current tree has no `gitops/` root; top-level `k8s/` exists
  instead.
- Not a blocker by itself because SLICE-102.02 creates the directory, but all
  later slices depend on that exact creation order.

B6 [LOW]. Proposal references generated snapshot marker path that must remain
  generated, not committed.

- Evidence: marker is written to
  `gitops/channels/local/generated/gitops-snapshot-marker.yaml` inside the
  temporary snapshot algorithm (`.pipeline/proposal.md:435-443`).
- Required resolution: keep generated marker in `.tmp/gitops-source/...` output
  only; do not create a committed `gitops/channels/local/generated/` tree.

## Counts

- Reuse-point count: 14
- Collision count: 8 total - high 3, medium 3, low 2
- Deletion candidate count: 10
- Implementation blocker count: 6 - B1 through B6
