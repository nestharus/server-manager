# INIT-114 Auth Stack Proposal

## Design

Deploy a dedicated `auth-system` GitOps subtree:

- Authentik Helm render, configured to use a CloudNativePG `Cluster` instead of
  bundled PostgreSQL.
- Pomerium Helm render, configured with Infisical-provided config, shared
  secrets, signing key, and OIDC client values.
- OPAL Helm render, configured with the Cedar client image and Cedar policy
  store env vars.
- A Cedar bootstrap job that loads a sample policy/data set into Cedar Agent.
- Kong ingresses:
  - `auth.local.humility.local` to Authentik.
  - `authenticate.local.humility.local` to Pomerium authenticate.
  - `protected-api.local.humility.local` to Pomerium proxy.

Add one API proof endpoint:

- `GET /api/v1/protected/authz-proof`
- Requires an identity header from Pomerium.
- Calls Cedar Agent `/v1/is_authorized`.
- Allows `sample@local.humility.local` for `Action::"api:read"` on
  `Resource::"server-manager-api"`.
- Returns `401` for missing identity, `403` for Cedar deny, and `503` if the
  policy engine is unreachable.

## Credential Model

Infisical owns:

- Authentik secret key, bootstrap admin password, sample user password, and DB
  password.
- Pomerium shared secret, cookie secret, signing key, OIDC client id, and OIDC
  client secret.

No generated Helm Secret containing credential material is committed.

## Anti-Scope

- No production OIDC client federation.
- No remote-channel exposure.
- No tenant isolation.
- No backwards-compatible unauthenticated protected endpoint.
