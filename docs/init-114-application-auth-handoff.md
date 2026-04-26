# INIT-114 Handoff: Auth Stack

INIT-114 adds the local-first auth stack under
`gitops/channels/local/auth`.

## Delivered

- Authentik `2026.2.2` rendered from `authentik/authentik`.
- Authentik uses CNPG `Cluster/authentik-postgres` instead of bundled
  PostgreSQL.
- Pomerium `34.0.1` rendered from `pomerium/pomerium`.
- OPAL `0.0.29` rendered from `permitio/opal`, with
  `permitio/opal-client-cedar:0.7.12`.
- Kong hosts:
  - `auth.local.humility.local`
  - `authenticate.local.humility.local`
  - `protected-api.local.humility.local`
- API proof endpoint:
  - `GET /api/v1/protected/authz-proof`
  - requires Pomerium identity headers
  - calls Cedar Agent at `http://opal-client.auth-system.svc.cluster.local:8180`
  - allows `sample@local.humility.local` for the sample rule

## Secrets

Bootstrap local auth secrets after Infisical identity bootstrap:

```bash
infra/scripts/bootstrap-infisical-auth.sh \
  --channel local \
  --kubeconfig ~/.kube/humility-local.yaml
```

The script creates or reuses Infisical project `platform-auth`, environment
`local`, and paths:

- `/auth/local/authentik`
- `/auth/local/pomerium`

It seeds missing values only; reruns do not rotate existing credentials.

## Validation

Static:

```bash
infra/tests/validate_auth_stack_local.sh --static-only
```

Runtime:

```bash
infra/tests/validate_auth_stack_local.sh \
  --channel local \
  --kubeconfig ~/.kube/humility-local.yaml
```

Runtime proof checks:

- `Cluster/authentik-postgres` Ready.
- Authentik server and worker available.
- Pomerium proxy and authenticate deployments available.
- OPAL server/client available and Cedar sample policy bootstrap complete.
- Cedar returns Allow for the sample user and Deny for a non-sample user.
- `protected-api.local.humility.local/api/v1/protected/authz-proof` requires
  authentication through Pomerium.
- Authentik admin and sample-user credential keys are synced from Infisical.

## INIT-115 Handoff

INIT-115 should own production policy authoring and real OIDC federation:

- Create and manage the Authentik OIDC application/provider for Pomerium.
- Replace the sample Cedar policy with a versioned policy repository and review
  workflow.
- Decide claim-to-policy mapping for Discord operators, services, and future UI
  users.
- Harden remote-channel route, TLS, and logout behavior.
