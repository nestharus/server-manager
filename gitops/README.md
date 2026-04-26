# GitOps

Reader's guide for the local GitOps substrate.

## Layout

- `gitops/flux/` - pinned Flux `v2.8.6` component manifests. INIT-102 installs
  source-controller and kustomize-controller only.
- `gitops/sources/local/` - local Git source support, including the
  git-daemon Deployment. Rendered `GitRepository` and source-side
  `Kustomization` manifests are generated from the channel contract.
- `gitops/channels/local/` - the local channel overlay, namespace, bootstrap
  sentinel reference, generated snapshot marker, and runtime Infisical subtree.
- `gitops/channels/local/infisical/` - INIT-103 runtime-secret management for
  the local channel. `server/` and `operator/` contain committed raw YAML
  rendered from pinned Helm charts. `sample/` contains the authored
  `InfisicalSecret/infisical-local-sample` proof that syncs
  `Secret/infisical-local-sample` into `infisical-sample`.
- `gitops/bootstrap/` - SOPS+age bootstrap-only encrypted secrets. Runtime
  application secrets do not live here; they move through Infisical in
  INIT-103.

`gitops/channels/local/infisical/` is part of the Flux-reconciled local
channel. It does not introduce Helm controller, `HelmRelease`, `OCIRepository`,
or runtime chart fetching. Helm is used only by
`infra/scripts/render-infisical-manifests.sh` to refresh committed raw
manifests.

SOPS+age remains bootstrap-only. The Infisical server bootstrap Secret is
allowed under `gitops/bootstrap/`; Operator Universal Auth credentials and all
downstream runtime secrets are created outside Git and consumed through
Infisical plus `InfisicalSecret` resources.

INIT-104 must add its own object-storage `InfisicalSecret` resources in the
owning application namespace. It must not place MinIO or Vultr Object Storage
credentials in `gitops/bootstrap/` or any SOPS-encrypted file.

## Generated Artifacts

- `.tmp/gitops-source/local/` - rendered local GitOps snapshot used to seed the
  in-cluster Git daemon during local bring-up and harness runs.
- `gitops/channels/local/generated/` - committed channel overlay artifacts that
  are generated from the local source snapshot contract.

The canonical acceptance harness is:

```bash
bash infra/tests/validate_platform_bootstrap.sh
bash infra/tests/validate_platform_bootstrap.sh --cluster
```
