# INIT-114 Auth Stack Research

## Scope

Deploy a local-first auth stack for the Humility platform:

- Authentik as the OIDC identity provider.
- Pomerium as the identity-aware proxy path for protected API traffic.
- OPAL with Cedar as the authorization decision plane.
- Kong remains the platform ingress controller from INIT-110.
- The INIT-113 API workload remains the protected backend.

## Findings

- confirmed-fact: Authentik publishes an official Helm chart at
  `authentik/authentik`; the current repo search in this worktree returned
  chart/app version `2026.2.2`.
- confirmed-fact: Authentik's Kubernetes install documentation supports Helm
  and states that the chart's default PostgreSQL is for demonstration/testing;
  production-shaped deployments should use an operator-backed PostgreSQL such
  as CloudNativePG.
- confirmed-fact: Pomerium still has a Helm chart at `pomerium/pomerium`
  version `34.0.1`, app version `v0.22.0`. Pomerium's current guide notes that
  the Helm chart is no longer the preferred actively updated install path, but
  the INIT-114 constraint requires Helm template only.
- confirmed-fact: OPAL publishes a Helm chart at `permitio/opal` version
  `0.0.29`, app version `0.7.12`.
- confirmed-fact: OPAL supports `OPAL_POLICY_STORE_TYPE=cedar`, and the Cedar
  tutorial documents Cedar Agent authorization checks through
  `/v1/is_authorized`.
- inference: OPAL's Helm chart models the policy client as an OPA-compatible
  local policy store by default. For Cedar, the least invasive local deployment
  is the same chart with the client image switched to
  `permitio/opal-client-cedar` and the policy store type set to `cedar`.
- inference: Pomerium does not natively call Cedar for every route decision in
  this chart shape. To satisfy per-request Cedar authorization without adding a
  parallel proxy, the protected API endpoint should perform the Cedar
  authorization check after Pomerium authenticates and forwards identity
  headers.

## Decision Inputs

- Helm is render-time only; raw YAML is committed under `gitops/channels/local`.
- All credentials must originate in Infisical-managed Secrets.
- Health/readiness endpoints should remain available for substrate smoke tests.
- Real OIDC client federation and production policy authoring remain out of
  scope.
