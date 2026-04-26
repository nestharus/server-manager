# INIT-114 Risk Gate: Audit

Result: LOW

## Findings

- confirmed-fact: Authentik uses the existing CNPG substrate instead of the
  chart-bundled PostgreSQL path, aligning with INIT-111 and avoiding a second
  database pattern.
- confirmed-fact: Kong remains the only ingress controller; new hosts are
  ordinary Kong `Ingress` resources.
- risk LOW: Pomerium's Helm chart is older than the current Pomerium install
  preference. The risk is contained by pinning the chart version, committing
  rendered YAML, and limiting INIT-114 to local-first proof.

## Gate

LOW. Proceed to hookpoint research.
