# INIT-110 PR Review: Justification Check

Verdict: justified for INIT-110.

Included appropriately:

- `ingress` channel schema additions for local and dev.
- Raw Kong manifests rendered from the upstream chart.
- Explicit `IngressClass/kong`, because the chart render did not create the
  object even though KIC is configured for that class.
- MinIO sample Ingress, ExternalName DNS alias, and MinIO NetworkPolicy
  exception.
- Local harness covering schema, kustomize, Kong readiness, certificate
  readiness, DNS, and HTTPS curl.
- INIT-111 handoff.

Not included:

- Auth.
- Rate limiting.
- Kong plugin marketplace.
- Kong Manager exposure.
- Production ACME promotion.

No unrelated changes need to be removed.
