# INIT-114 Hookpoint Research

## Existing Surfaces

- `gitops/channels/local/kustomization.yaml` is the local Flux root.
- `gitops/channels/local/applications/server-manager` owns the INIT-113 API
  deployment and Kong ingress.
- `gitops/channels/local/ingress` owns Kong and default service proofs.
- `infra/channels/local.yaml` and `infra/schemas/platform-channel*.schema.json`
  own channel-level substrate contracts.
- `infra/tests/validate_application_workloads_local.sh` is the runtime harness
  pattern for local app proof.
- `services/api/app/api/v1/router.py` is the v1 endpoint registration point.
- `services/api/app/core/settings.py` is the runtime settings source.

## Reuse

- Reuse CNPG for Authentik Postgres.
- Reuse the Infisical Operator pattern from INIT-103/111/113.
- Reuse Kong ingress annotations and local DNS aliasing from INIT-110/113.
- Reuse shell harness pass/fail/skip convention from INIT-110/113.

## Implementation Slices

1. API contract and Cedar proof endpoint.
2. Channel/schema contract for auth stack pins and hosts.
3. Authentik CNPG, InfisicalSecret, Helm values/render, ingress.
4. Pomerium InfisicalSecret, Helm values/render, ingress.
5. OPAL/Cedar Helm values/render, sample policy, bootstrap job.
6. Auth stack network policies and root kustomization wiring.
7. Infisical auth bootstrap script and static/runtime harness.
8. Handoff docs and Buildkite/static validation wiring.
