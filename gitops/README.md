# GitOps

Reader's guide for the INIT-102 GitOps substrate.

## Layout

- `gitops/flux/` - pinned Flux `v2.8.6` component manifests. INIT-102 installs
  source-controller and kustomize-controller only.
- `gitops/sources/local/` - local Git source support, including the
  git-daemon Deployment. Rendered `GitRepository` and source-side
  `Kustomization` manifests are generated from the channel contract.
- `gitops/channels/local/` - the local channel overlay, namespace, bootstrap
  sentinel reference, and generated snapshot marker.
- `gitops/bootstrap/` - SOPS+age bootstrap-only encrypted secrets. Runtime
  application secrets do not live here; they move through Infisical in
  INIT-103.

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
