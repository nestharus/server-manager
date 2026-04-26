# INIT-114 Needs Synthesis

## Humility Context

INIT-113 exposes the API through Kong at `api.local.humility.local` with no
authentication. INIT-114 must add a protected path without breaking the
existing health, readiness, migration, database, and Discord workload proofs.

## User Needs

- Local operators need an Authentik login surface with bootstrap admin and
  sample-user credentials stored in Infisical, not Git.
- Protected browser/API traffic needs to enter through Kong, then Pomerium, then
  the existing API service.
- The API needs one demonstrable Cedar-backed authorization decision that is
  easy to test locally and hand off to INIT-115.
- The unauthenticated `/api/v1/health` and `/api/v1/ready` surfaces need to
  remain usable for operational probes.
- Runtime proof needs to distinguish authentication from authorization:
  unauthenticated requests should redirect or fail at Pomerium, while
  authenticated requests can still be denied by Cedar.

## Gaps Deferred to INIT-115

- Final Authentik OIDC client/provider federation.
- Production Cedar policy taxonomy and authoring workflow.
- Role/group-to-policy mapping beyond the sample user rule.
- Pomerium route hardening for remote channels.
