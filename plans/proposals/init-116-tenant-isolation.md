# INIT-116 Proposal

## Design

Add a `tenant_isolation` channel contract with namespace naming, label keys,
RBAC conventions, NetworkPolicy behavior, Cedar principal/resource types, and
Infisical project naming.

Commit a local proof set under `gitops/channels/local/tenants`:

- `sample-local` and `sample-dev` demonstrate same-tenant cross-channel access.
- `other-local` gives the denial target for cross-tenant proof.
- Every tenant namespace has restricted PSS labels, default-deny NetworkPolicy,
  DNS egress, same-tenant namespace egress/ingress, tenant-scoped RBAC, and a
  per-tenant `InfisicalSecret`.

Extend `spawn_platform_channel.py` so local child-channel spawn also writes the
tenant-scoped resource tree under `.tmp/<spawn>/tenant-resources`.

Extend the INIT-115 Cedar bundle with `Tenant` principals and `TenantChannel`
resource selectors. The sample tenant can access `sample:local` and
`sample:dev`; it has no permit for `other:local`.

## Anti-Scope

- No observability, metrics, dashboards, or policy decision telemetry.
- No helm-controller.
- No new credential material.
- No Discord-visible mutations.
