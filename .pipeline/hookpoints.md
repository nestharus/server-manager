# INIT-104 Phase 5 Hookpoint Research

Binding spec: `.pipeline/proposal.md` (1006 lines). Supporting context:
`.pipeline/synthesis.md` D1..D12, INIT-103 handoff outputs in
`../init-103-infisical-runtime-secrets/`, and the current INIT-101/102 substrate
already present in this worktree.

Research only. No implementation code changed.

## 1. Reuse Points

R1. INIT-103 Infisical runtime-secret substrate.

- INIT-103 is complete and reconciles Infisical server, Operator, sample
  `InfisicalSecret`, bootstrap-only server Secret, and
  `Secret/infisical-operator-auth` (`../init-103-infisical-runtime-secrets/.pipeline/implementation.md:23-40`).
- INIT-104's binding explicitly consumes the local endpoint, environment,
  Operator namespace, UA Secret name/namespace, and `/object-storage/<channel>/`
  path convention (`../init-103-infisical-runtime-secrets/.pipeline/implementation.md:66-112`).
- Current `infra/channels/local.yaml` already has the strict `infisical` block
  INIT-104 must reuse (`infra/channels/local.yaml:33-42`).
- Reuse action: storage `InfisicalSecret` should reference
  `Secret/infisical-operator-auth` in `infisical-system`, not create a second
  UA Secret, matching proposal AUDIT-001 (`.pipeline/proposal.md:531-546`).

R2. INIT-103 sample `InfisicalSecret` CR shape.

- The sample CR uses `secrets.infisical.com/v1alpha1`, `hostAPI`, Universal Auth
  `credentialsRef`, `secretsScope`, `syncConfig.resyncInterval`, and
  `managedSecretReference` (`gitops/channels/local/infisical/sample/infisicalsecret.yaml:22-47`).
- Proposal's storage CR is the same shape with storage-specific project/path and
  target Secret (`.pipeline/proposal.md:548-577`).
- Reuse action: copy the CR pattern into
  `gitops/channels/local/object-storage/infisical/minio-root-infisicalsecret.yaml`
  while changing only ownership namespace, target Secret, project, and path.

R3. INIT-103 Infisical identity bootstrap script patterns.

- `bootstrap-infisical-identity.sh` already resolves channel Infisical fields
  from `resolve_platform_channel.py` (`../init-103-infisical-runtime-secrets/infra/scripts/bootstrap-infisical-identity.sh:129-144`).
- It already has idempotent project/environment/folder creation helpers and
  secret seeding (`../init-103-infisical-runtime-secrets/infra/scripts/bootstrap-infisical-identity.sh:259-335`).
- It already validates and applies the UA Secret through kubectl without writing
  credentials to Git (`../init-103-infisical-runtime-secrets/infra/scripts/bootstrap-infisical-identity.sh:410-445`).
- Reuse action: `bootstrap-infisical-storage.sh` should be a sibling script that
  reuses these patterns for `platform-storage` and `/object-storage/local/`,
  then verifies the existing UA Secret instead of rotating or replacing it.

R4. INIT-102/103 local Flux overlay.

- The local overlay currently applies namespace, generated marker, bootstrap
  encrypted files, then Infisical server, Operator, and sample resources
  (`gitops/channels/local/kustomization.yaml:1-10`).
- Proposal adds exactly one subtree, `object-storage/`, under the same overlay
  (`.pipeline/proposal.md:54-98`, `.pipeline/proposal.md:99-125`).
- Reuse action: add `object-storage` after the Infisical entries so the new
  manifests stay in the existing Flux-owned local channel.

R5. INIT-102 GitOps snapshot and Flux install path.

- `render-gitops-source.py` copies the entire `gitops/` tree into the local
  snapshot (`infra/scripts/render-gitops-source.py:74-80`) and renders source
  manifests plus the snapshot marker (`infra/scripts/render-gitops-source.py:197-209`).
- `install-flux-for-channel.sh` seeds that snapshot into the in-cluster Git
  daemon and applies the generated Flux source CRs
  (`infra/scripts/install-flux-for-channel.sh:156-213`).
- Reuse action: no new Git source, Flux source, or Kustomization is needed for
  object storage; the subtree rides the existing local source.

R6. INIT-103 Flux post-install sequencing.

- The Flux installer already resolves Infisical channel fields, applies Flux,
  seeds Git, ensures the SOPS age Secret, applies source CRs, waits for
  Infisical server, bootstraps UA, waits for Operator/sample, and then waits
  for final reconciliation (`infra/scripts/install-flux-for-channel.sh:379-418`).
- Reuse action: insert storage bootstrap after `bootstrap_infisical_identity`
  and before object-storage readiness checks; `bring-up-local-channel.sh`
  should remain the outer local cluster entrypoint
  (`infra/scripts/bring-up-local-channel.sh:221-228`, `infra/scripts/bring-up-local-channel.sh:230-311`).

R7. Channel schema and resolver substrate.

- Source and resolved schemas are strict top-level objects that already expose
  `gitops` and `infisical` (`infra/schemas/platform-channel.schema.json:16-53`,
  `infra/schemas/platform-channel-resolved.schema.json:17-50`).
- Local `k3d-local` currently requires `gitops` and `infisical`
  (`infra/schemas/platform-channel.schema.json:69-85`,
  `infra/schemas/platform-channel-resolved.schema.json:52-69`).
- The resolver deep-merges parent/child maps generically and explicitly avoids
  defaulting GitOps/Infisical fields (`infra/scripts/resolve_platform_channel.py:148-156`,
  `infra/scripts/resolve_platform_channel.py:198-208`).
- Reuse action: add `object_storage` as a sibling strict block and let inheritance
  use the existing deep-merge path.

R8. Channel YAML hooks.

- `local.yaml` already carries local cluster, state, GitOps, and Infisical
  concrete blocks (`infra/channels/local.yaml:1-42`).
- `dev.yaml` is currently a Vultr VM plan channel and explicitly omits GitOps
  (`infra/channels/dev.yaml:1-28`).
- Child fixtures currently inherit all concrete parent fields from `local` and
  `dev` without overriding platform blocks
  (`infra/channels/fixtures/local-child.yaml:1-7`,
  `infra/channels/fixtures/dev-child.yaml:8-14`).
- Reuse action: land the required `object_storage` block in `local.yaml`.
  `dev.yaml` is per-target conditional: optional in INIT-104, but if present it
  must be Vultr-shaped and must not imply remote Flux or remote Infisical.

R9. Tool installer pattern.

- `install-cluster-tools.sh` already centralizes pinned tool versions and
  checksums (`infra/scripts/install-cluster-tools.sh:4-15`).
- It has per-tool installed-version probes, check functions, verified downloads,
  and idempotent install orchestration (`infra/scripts/install-cluster-tools.sh:202-338`,
  `infra/scripts/install-cluster-tools.sh:473-548`).
- Reuse action: add `mc` beside the existing tools. Do not create a second host
  installer or require AWS CLI.

R10. Local harness pattern.

- The bootstrap harness already has pass/fail helpers and a `--cluster` mode
  (`infra/tests/validate_platform_bootstrap.sh:1-56`).
- It already checks channel validation, GitOps rendering, SOPS boundary, and
  Infisical schema/sample surfaces (`infra/tests/validate_platform_bootstrap.sh:124-180`,
  `infra/tests/validate_platform_bootstrap.sh:272-325`,
  `infra/tests/validate_platform_bootstrap.sh:327-360`).
- Proposal binds a new object-storage harness invoked from `--cluster`
  (`.pipeline/proposal.md:827-865`).
- Reuse action: add `validate_object_storage_local.sh` as a focused child
  harness and call it from the existing cluster path.

R11. Documentation handoff points.

- `gitops/README.md` already states the local GitOps layout, raw-manifest
  pattern, bootstrap-only SOPS boundary, and INIT-104 object-storage handoff
  (`gitops/README.md:14-45`).
- `infra/README.md` already lists the local toolchain and Infisical runtime
  secret flow (`infra/README.md:78-95`, `infra/README.md:177-219`).
- Reuse action: update these docs in place; do not add a new docs root.

R12. Existing state-backend object-storage Terraform is separate.

- `infra/bootstrap/state-backend/main.tf` uses `vultr_object_storage` only for
  Terraform state bootstrap (`infra/bootstrap/state-backend/main.tf:22-49`).
- Proposal anti-scope forbids adding Vultr Object Storage subscription/bucket
  resources for the INIT-104 application object layer (`.pipeline/proposal.md:686-693`,
  `.pipeline/proposal.md:947-948`).
- Reuse action: leave state-backend Terraform alone; INIT-104's remote surface is
  schema/docs/handoff only.

Reuse-point count: 12.

## 2. Collision Points

C1 [HIGH]. Proposal image digests do not match the registry manifests observed
on 2026-04-26.

- Proposal pins MinIO server digest
  `sha256:5fa6d6eb3204468b7898bbdbf7dd2169217831cdce8f85833bf89f2d21020e41`
  and `mc` digest
  `sha256:7a740f5dbc9c1ea04512a86eb27714b3ed025dd1825aa958aaae0c2298b54398`
  (`.pipeline/proposal.md:271-275`).
- Registry verification succeeded, but current manifest-list digests are
  `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z` =
  `sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e`
  and `quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z` =
  `sha256:a7fe349ef4bd8521fb8497f55c6042871b2ae640607cf99d9bede5e9bdf11727`.
- Required resolution: update the binding digest pins or explicitly bind
  architecture-specific digests before implementation tests encode them.

C2 [HIGH]. Strict schemas currently reject `object_storage`.

- Both schemas are `additionalProperties: false` and currently define only
  `gitops` and `infisical` as platform add-ons
  (`infra/schemas/platform-channel.schema.json:5-53`,
  `infra/schemas/platform-channel-resolved.schema.json:5-50`).
- Proposal requires a new strict top-level `object_storage` block and requires it
  for `k3d-local` (`.pipeline/proposal.md:127-151`,
  `.pipeline/proposal.md:167-238`).
- Required resolution: schema, `local.yaml`, fixtures, resolver tests, and
  validation tests must land together in SLICE-104.01.

C3 [MEDIUM]. Synthesis field names and proposal field names diverge.

- Synthesis D7 uses `provider: ["minio", "vultr-os"]`, `addressing_style`,
  `infisical_environment`, `infisical_secrets_path`, and storage-specific UA
  fields (`.pipeline/synthesis.md:311-333`).
- Proposal binds `provider: ["minio", "vultr-object-storage"]`,
  `infisical_project`, `infisical_path`, and shared INIT-103 UA reuse
  (`.pipeline/proposal.md:220-235`, `.pipeline/proposal.md:531-546`).
- Required resolution: implementation should follow the proposal as binding and
  add negative tests for the rejected synthesis-era aliases. No compatibility
  fields are allowed under the no-backwards-compatibility convention
  (`/home/nes/ai/conventions/no-backwards-compatibility.md:1-40`).

C4 [MEDIUM]. `dev.yaml` optionality can collide with current harness language.

- Current `dev.yaml` omits GitOps and Infisical entirely
  (`infra/channels/dev.yaml:24-28`).
- Current harness asserts dev resolves without `gitops`
  (`infra/tests/validate_platform_bootstrap.sh:272-285`).
- Proposal table says `dev.yaml` is modified with an optional aspirational
  Vultr block, while schema text says Vultr `object_storage` is optional
  (`.pipeline/proposal.md:79-80`, `.pipeline/proposal.md:132-138`,
  `.pipeline/proposal.md:240-260`).
- Required resolution: tests must cover both shapes or choose one concrete
  `dev.yaml` shape. Do not make remote storage required until remote Flux and
  Infisical exist.

C5 [MEDIUM]. Flux apply ordering is not readiness ordering.

- Root Kustomization resource order can express ownership order, but Flux still
  reconciles one local Kustomization from a Git source
  (`gitops/channels/local/kustomization.yaml:1-10`,
  `infra/scripts/render-gitops-source.py:197-209`).
- Proposal says namespace, InfisicalSecret, MinIO, and bucket Job are ordered in
  Kustomize but actual readiness is handled by probes, InfisicalSecret condition,
  and Job command (`.pipeline/proposal.md:121-125`).
- Required resolution: bucket Job and harness must tolerate delayed
  `Secret/minio-root`; do not rely on Kustomize order alone.

C6 [LOW]. `object_storage` naming already appears in state-backend Terraform.

- Existing names `object_storage_cluster_id`, `object_storage_tier_id`, and
  `vultr_object_storage.state` are state-backend-specific
  (`infra/bootstrap/state-backend/main.tf:22-49`).
- Proposal's channel `object_storage` block is application object-storage
  contract, not Terraform state bootstrap (`.pipeline/proposal.md:31-42`,
  `.pipeline/proposal.md:686-693`).
- Required resolution: docs and tests should distinguish state backend object
  storage from app/storage-contract object storage.

C7 [LOW]. Host `mc` is not in the installer today.

- Tool installer has k3d, flux, helm, sops, age, and infisical only
  (`infra/scripts/install-cluster-tools.sh:4-15`,
  `infra/scripts/install-cluster-tools.sh:327-338`).
- Proposal requires pinned host `mc` install/check
  (`.pipeline/proposal.md:742-753`).
- Required resolution: add `mc` to the same script; no second installer.

Collision count: 7 (HIGH: 2, MEDIUM: 3, LOW: 2).

## 3. Deletion Candidates

None identified.

- Existing Infisical sample resources remain the INIT-103 runtime proof and are
  not replaced by object storage (`gitops/channels/local/infisical/sample/infisicalsecret.yaml:22-47`).
- Existing SOPS bootstrap files remain required for Infisical server bootstrap
  and Flux decryption (`gitops/channels/local/kustomization.yaml:6-7`,
  `.sops.yaml:1-9`).
- Existing state-backend Terraform remains separate from INIT-104's app object
  storage contract (`infra/bootstrap/state-backend/main.tf:22-49`).

Deletion candidate count: 0.

## 4. Channel YAML Hooks

Local hook:

- Add the concrete `object_storage` block from the proposal to
  `infra/channels/local.yaml` after the existing `infisical` block
  (`infra/channels/local.yaml:33-42`, `.pipeline/proposal.md:139-151`).
- Required fields: `provider: minio`, in-cluster MinIO endpoint,
  `region: us-east-1`, `bucket: humility-local-sample`,
  `credentials_secret_name: minio-root`,
  `credentials_secret_namespace: minio-system`,
  `infisical_project: platform-storage`, and
  `infisical_path: /object-storage/local/`.

Dev hook:

- `infra/channels/dev.yaml` currently remains a remote VM plan channel with no
  GitOps block (`infra/channels/dev.yaml:1-28`).
- Per D7/D8, `object_storage` is optional for `vultr-vms`; if present it must be
  Vultr-shaped, endpoint `https://ewr1.vultrobjects.com`, and documentation only
  in INIT-104 (`.pipeline/synthesis.md:335-381`,
  `.pipeline/synthesis.md:385-435`, `.pipeline/proposal.md:153-165`).
- Resolver may compute Vultr endpoint from `cluster.vultr_vms.region` before
  resolved-schema validation (`.pipeline/proposal.md:253-262`,
  `infra/scripts/resolve_platform_channel.py:202-208`).

## 5. Slice-by-Slice Surface Map

SLICE-104.01 - Object Storage Channel Schema

- Modify: `infra/schemas/platform-channel.schema.json`,
  `infra/schemas/platform-channel-resolved.schema.json`,
  `infra/channels/local.yaml`, optionally `infra/channels/dev.yaml`,
  `infra/channels/fixtures/local-child.yaml`,
  `infra/channels/fixtures/dev-child.yaml`,
  `infra/scripts/resolve_platform_channel.py`,
  `infra/scripts/validate_platform_channels.py`.
- Add: `infra/tests/test_platform_channel_object_storage.py`.
- Hookpoints: strict schemas (`infra/schemas/platform-channel.schema.json:1-53`),
  k3d-local conditionals (`infra/schemas/platform-channel.schema.json:69-85`),
  deep merge (`infra/scripts/resolve_platform_channel.py:148-156`), active
  registry validation (`infra/scripts/validate_platform_channels.py:87-104`).

SLICE-104.02 - Pinned `mc` Toolchain

- Modify: `infra/scripts/install-cluster-tools.sh`,
  `infra/tests/validate_platform_bootstrap.sh`, `infra/README.md`.
- Hookpoints: tool constants/checks/install orchestration
  (`infra/scripts/install-cluster-tools.sh:4-15`,
  `infra/scripts/install-cluster-tools.sh:202-338`,
  `infra/scripts/install-cluster-tools.sh:473-548`).

SLICE-104.03 - Infisical Storage Bootstrap

- Add: `infra/scripts/bootstrap-infisical-storage.sh`,
  `gitops/channels/local/object-storage/infisical/kustomization.yaml`,
  `gitops/channels/local/object-storage/infisical/minio-root-infisicalsecret.yaml`.
- Modify: `infra/scripts/bring-up-local-channel.sh` or
  `infra/scripts/install-flux-for-channel.sh` for sequencing.
- Hookpoints: INIT-103 bootstrap patterns
  (`../init-103-infisical-runtime-secrets/infra/scripts/bootstrap-infisical-identity.sh:129-144`,
  `../init-103-infisical-runtime-secrets/infra/scripts/bootstrap-infisical-identity.sh:259-335`,
  `../init-103-infisical-runtime-secrets/infra/scripts/bootstrap-infisical-identity.sh:410-445`)
  and Flux post-install sequencing (`infra/scripts/install-flux-for-channel.sh:409-416`).

SLICE-104.04 - Raw MinIO Local Manifests

- Add: `gitops/channels/local/object-storage/kustomization.yaml`,
  `gitops/channels/local/object-storage/namespace.yaml`,
  `gitops/channels/local/object-storage/minio/kustomization.yaml`,
  `serviceaccount.yaml`, `pvc.yaml`, `deployment.yaml`, `service.yaml`.
- Modify: `gitops/channels/local/kustomization.yaml`.
- Hookpoints: existing overlay (`gitops/channels/local/kustomization.yaml:1-10`)
  and proposal manifest contract (`.pipeline/proposal.md:264-428`).

SLICE-104.05 - Bucket Job

- Add: `gitops/channels/local/object-storage/buckets/kustomization.yaml`,
  `serviceaccount.yaml`, `create-sample-bucket-job.yaml`.
- Hookpoints: proposal Job contract, stable name, no TTL, and
  `mc mb --ignore-existing` (`.pipeline/proposal.md:430-512`).

SLICE-104.06 - S3 Round Trip Script

- Add: `infra/scripts/sample-s3-roundtrip.py`,
  `infra/scripts/object-storage-requirements.txt`,
  `infra/tests/validate_object_storage_local.sh`.
- Modify: `infra/README.md`.
- Hookpoints: five-env-var SDK contract and pinned dependency list
  (`.pipeline/proposal.md:610-666`).

SLICE-104.07 - Local Harness And Documentation

- Modify: `infra/tests/validate_platform_bootstrap.sh`, `gitops/README.md`,
  `infra/README.md`, `.pipeline/implementation.md`.
- Extend: `infra/tests/validate_object_storage_local.sh`.
- Hookpoints: local proof assertions (`.pipeline/proposal.md:827-865`), existing
  harness entrypoint (`infra/tests/validate_platform_bootstrap.sh:1-56`), and
  docs handoff (`gitops/README.md:14-45`, `infra/README.md:177-219`).

## 6. Implementation Blockers

B1 [HIGH]. Binding digest mismatch.

- Quay registry access is verified, but current manifest-list digests differ from
  proposal digest pins; see C1. This blocks tests that assert proposal digests
  verbatim.

B2 [MEDIUM]. Binding-vs-synthesis field drift must be intentionally closed.

- Proposal is the binding spec, but D7 still lists earlier names and provider
  literal `vultr-os` (`.pipeline/synthesis.md:320-333`) while proposal uses
  `vultr-object-storage` and fewer fields (`.pipeline/proposal.md:220-235`).
- Implementation must not accept both sets.

B3 [MEDIUM]. Decide concrete `dev.yaml` shape for SLICE-104.01 tests.

- Proposal allows optional `dev` object storage and also lists `dev.yaml` as
  modified (`.pipeline/proposal.md:79-80`, `.pipeline/proposal.md:240-248`).
- Tests need one committed source of truth: omitted or present. Both can be
  covered with fixtures, but active `dev.yaml` can only be one shape.

B4 [MEDIUM]. Storage bootstrap must be wired into the post-Flux sequence without
duplicating INIT-103 UA lifecycle.

- Current post-install bootstrap is inside `install-flux-for-channel.sh`
  (`infra/scripts/install-flux-for-channel.sh:409-416`), while proposal mentions
  `bring-up-local-channel.sh` as the modified entrypoint
  (`.pipeline/proposal.md:87-90`).
- Implementation must choose the hook that preserves the existing idempotent
  local entrypoint and avoids a second UA Secret.

Blocker count: 4.

## 7. Cross-INIT Impact

INIT-105 - TLS, DNS, cert-manager.

- INIT-104 deliberately leaves local MinIO as plain HTTP on ClusterIP
  (`.pipeline/proposal.md:955-975`).
- INIT-105 can add DNS/TLS/Ingress later without reshaping object-storage
  credentials. Do not add placeholder HTTPS fields or certificate stubs in
  INIT-104.

INIT-106 - Vultr bucket creation.

- INIT-104 defines the remote Vultr Object Storage contract only; it does not
  provision subscriptions or buckets (`.pipeline/proposal.md:668-719`,
  `.pipeline/proposal.md:947-948`).
- Existing state-backend `vultr_object_storage` Terraform is not the app bucket
  provisioning path (`infra/bootstrap/state-backend/main.tf:22-49`).
- INIT-106 owns any future Crossplane/provider config/claim or break-glass
  bucket creation path; INIT-104 should only document the handoff.

## 8. Registry Verification

Verified on 2026-04-26 from this worktree:

- `docker manifest inspect quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z`
  succeeded.
- `docker manifest inspect quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z`
  succeeded.
- `docker buildx imagetools inspect` reported manifest-list digests:
  MinIO server `sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e`;
  `mc` `sha256:a7fe349ef4bd8521fb8497f55c6042871b2ae640607cf99d9bede5e9bdf11727`.
- Host `mc` binary URL
  `https://dl.min.io/client/mc/release/linux-amd64/archive/mc.RELEASE.2025-08-13T08-35-41Z`
  reached HTTP 200 after redirects.

## 9. Summary Counts

- Reuse points: 12
- Collision points: 7 (HIGH: 2, MEDIUM: 3, LOW: 2)
- Deletion candidates: 0
- Blockers: 4
