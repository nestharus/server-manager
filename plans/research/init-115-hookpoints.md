# INIT-115 Hookpoints

Touched hookpoints:

- `infra/channels/local.yaml` and schemas for the `access_policy` contract.
- `gitops/channels/local/auth/opal-cedar/` for the OPAL policy bootstrap.
- `gitops/channels/local/access-policy/` for service identities and operator
  RBAC.
- `infra/scripts/` for dry-run-first operational scripts.
- `infra/tests/` for contract and local validation harnesses.

Reusable components:

- Existing channel resolver and schema validation.
- Existing OPAL/Cedar bootstrap job pattern.
- Existing static/runtime shell harness style.
- Existing Flux SOPS sentinel pattern.
