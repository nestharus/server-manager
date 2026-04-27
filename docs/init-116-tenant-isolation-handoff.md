# INIT-116 Handoff: Tenant and Channel Isolation

## Delivered

- `tenant_isolation` channel contract for namespace, RBAC, NetworkPolicy, Cedar,
  and Infisical naming conventions.
- Local tenant GitOps proof:
  - `sample-local`
  - `sample-dev`
  - `other-local`
- Tenant RBAC with namespaced `Role/tenant-operator` and
  `RoleBinding/tenant-operators`.
- Tenant NetworkPolicies with default-deny, DNS egress, and same-tenant
  cross-channel ingress/egress.
- Per-tenant Infisical projects through `InfisicalSecret/tenant-runtime` using
  `tenant-<tenant>-<channel>`.
- Cedar tenant principals:
  - `Tenant::"sample"` can access `TenantChannel::"sample:local"`.
  - `Tenant::"sample"` can access `TenantChannel::"sample:dev"`.
  - `Tenant::"sample"` is denied `TenantChannel::"other:local"`.
- `spawn_platform_channel.py --tenant <id>` writes tenant resource manifests
  under `.tmp/<spawn>/tenant-resources`.

## Validation

Static:

```bash
pytest infra/tests/test_tenant_isolation_contract.py infra/tests/test_access_policy_contract.py
infra/tests/validate_tenant_isolation_local.sh --static-only
infra/tests/validate_access_policy_local.sh --static-only
```

Runtime:

```bash
infra/tests/validate_tenant_isolation_local.sh
infra/tests/validate_access_policy_local.sh
```

## INIT-117 Handoff

INIT-117 should add observability for tenant isolation without changing the
authorization model: policy decision telemetry, NetworkPolicy/RBAC drift
alerts, Infisical sync health, and tenant namespace dashboarding.
