# INIT-116 Research

INIT-116 needs tenant isolation across the local Kubernetes substrate and Cedar
policy bundle without changing the INIT-115 service identity issuer shape.

Existing hookpoints:

- Channel contracts already carry `security`, `infisical`, `access_policy`, and
  `app_cluster` blocks in `infra/channels/local.yaml`.
- INIT-107 default-deny NetworkPolicies are static Kustomize resources and can
  be extended with tenant namespace-local policies.
- INIT-115 Cedar bundles are channel/service-scoped JSON policy files reconciled
  through `ConfigMap/cedar-access-policy-bundle`.
- `infra/scripts/spawn_platform_channel.py` already owns ephemeral child channel
  creation under `.tmp/`.

Required design constraints:

- Tenant namespaces use the deterministic `<tenant>-<channel>` pattern.
- Same-tenant cross-channel access is intentional; cross-tenant access is denied.
- Tenant runtime secrets come from per-tenant Infisical projects named
  `tenant-<tenant>-<channel>`.
- Tenant RBAC is namespaced with `Role` and `RoleBinding`; no tenant
  `ClusterRoleBinding` is required.
