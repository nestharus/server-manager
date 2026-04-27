# INIT-116 Audit Risk

Risk: LOW.

The change is additive to channel contracts, local GitOps tenant resources, and
Cedar policies. Tenant RBAC stays namespaced. NetworkPolicy grants are scoped by
the tenant label and preserve default-deny. Spawn output remains confined to
`.tmp/`.
