# Phase 5 Complete

Phase 5 rebuilt the Humility deployment substrate around one rule: local is the first deployment target. The local channel now runs the same platform shape expected remotely.

Infrastructure includes self-managed k3s, Flux GitOps, MinIO object storage, TLS/DNS automation, Crossplane app-cluster contracts, container delivery, and Buildkite CI/CD. Data and application services include Kong ingress, CloudNativePG/Atlas, backup/restore, server-manager workloads, and application workload contracts. Security and operations include Infisical runtime secrets, security boundaries, Authentik/Pomerium/OPAL-Cedar auth, access policy, tenant isolation, and observability.

## What Runs Locally

- `humility-local` k3d control cluster with Flux reconciliation from this repo.
- SOPS+age only for bootstrap secrets; Infisical owns runtime secrets.
- MinIO for S3-compatible object storage, including backups and Loki object storage.
- cert-manager with local step-ca issuer and local CoreDNS aliases.
- Crossplane providers and local AppCluster proof.
- NetworkPolicies, pod-security labels, RBAC boundaries, service identity, and tenant namespace samples.
- Local image registry and pull-through caches.
- Buildkite local pipeline runner and agent manifests.
- Kong ingress for local service routes.
- CloudNativePG Postgres clusters, Atlas migrations, backups, and restore drills.
- Server-manager API and Discord daemon workloads.
- Authentik, Pomerium, OPAL/Cedar, policy bundles, and break-glass runbooks.
- Prometheus, Grafana, Alertmanager, OpenTelemetry Collector, and Loki under `observability-system`.

## Deferred To Post-INIT-117 Deployment Work

INIT-117 is the observability expansion and local substrate validation milestone that closes Phase 5.

- First remote channel apply and remote kubeconfig retrieval.
- Remote DNS records, production ACME issuance, and Vultr load balancer registration.
- Production SLI/SLO definitions, incident routing, and third-party alert integrations.
- Remote HA hardening beyond the existing VM module contract.
- Live credential supply for remote provider credentials and runtime services.

The Phase 5 result after INIT-117 is a complete local substrate and a remote contract. Remote onboarding should now be channel configuration plus credential supply, not a re-architecture.
