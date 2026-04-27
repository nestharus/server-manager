# INIT-115 Problem Research

The INIT-114 auth stack proves Cedar can guard a protected API route, but the
policy source is a one-off sample ConfigMap. INIT-115 needs a reviewed policy
repo layout, machine identities, rotation cadence, and break-glass procedures
without introducing tenant isolation or policy decision observability.

Relevant existing substrate:

- `gitops/channels/local/auth/opal-cedar/` already deploys OPAL/Cedar and a
  bootstrap job that writes policy JSON to the OPAL client.
- `infra/channels/local.yaml` already holds channel-local auth, GitOps,
  Infisical, object-storage, and Crossplane contracts.
- `gitops/channels/local/app-clusters/` deploys Crossplane and provider
  runtime config; the rendered Crossplane chart includes a broad
  `crossplane-admin` binding.
- Bootstrap scripts already use dry-run-safe patterns and resolve channel
  contracts before mutating anything.

Problem boundaries:

- Policies must be structured by channel and service so INIT-116 can add tenant
  isolation without rewriting the repo shape.
- Service identities must be claim based and map to Cedar `Service` principals,
  distinct from human `User` principals.
- Recovery scripts must have dry-run proof paths because break-glass actions are
  exceptional and should be rehearsed locally.
