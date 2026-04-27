# INIT-115 Proposal

## Design

Add an `access_policy` channel contract that names the Cedar policy repo,
service identity issuer, credential rotation cadence, break-glass script,
object-storage policy, and operator RBAC narrowing.

Replace the INIT-114 inline sample policy with a `server-manager-api` bundle:

- `User::"sample@local.humility.local"` can perform `Action::"api:read"` on
  `Resource::"server-manager-api"`.
- `Service::"buildkite-agent.local"` can perform
  `Action::"api:ci:deploy"` on `Resource::"server-manager-api"`.
- `Service::"crossplane-provider.local"` can perform
  `Action::"cluster:claim:reconcile"` on `Resource::"cluster-api"`.

Add dry-run-first scripts for service identity verification, credential
rotation, break-glass SOPS recovery, and object-storage policy application.

## Anti-Scope

- No tenant-specific policy dimensions.
- No policy decision telemetry.
- No Helm controller.
- No committed credential material.
