# INIT-117 Phase 5 Hookpoints

## Existing Surfaces
- `infra/channels/local.yaml` and `infra/schemas/*.json` own channel contracts.
- `gitops/channels/local/kustomization.yaml` is the local GitOps root.
- `gitops/channels/local/*` subtrees are raw Kustomize component boundaries.
- `infra/tests/validate_*_local.sh` scripts provide static/runtime local proof patterns.
- `.buildkite/pipeline.yml` runs static INIT validation in local Buildkite mode.
- `services/api/app/api/v1/router.py` owns API route mounting.

## Reuse
- Reuse MinIO from INIT-104 as the Loki S3 backend.
- Reuse InfisicalSecret patterns from INIT-103/109/113/114 for runtime credentials.
- Reuse INIT-116 tenant labels for dashboard variables.
- Reuse Kustomize raw manifests and local validation harness patterns.

## Delete/Avoid
- Do not add helm-controller resources.
- Do not add local filesystem-only Loki persistence.
- Do not commit Grafana admin or object-storage credentials.
- Do not add incident routing integrations.

## Parallel Work
Schema/channel, core stack manifests, dashboard/logging manifests, ServiceMonitor/network policies, API metrics/tests, and docs are separable implementation slices.
