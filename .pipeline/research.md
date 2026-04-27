# INIT-117 Phase 1 Research: Observability Stack

## Scope
- Deliver Prometheus, Grafana, Alertmanager, OpenTelemetry Collector, and Loki as raw manifests in the local GitOps channel.
- Expose ServiceMonitor resources for Flux, Crossplane, cert-manager, Infisical, MinIO, CNPG, Kong, Pomerium, Authentik, OPAL, server-manager API, and Buildkite agent.
- Store Grafana dashboards as ConfigMaps and make dashboard filtering tenant-aware with the INIT-116 tenant label.
- Back Loki with the INIT-104 MinIO object store. Runtime credentials come from Infisical, not SOPS or literals.
- Prove local-first operation through Pod readiness, Prometheus targets, dashboard provisioning, Alertmanager sample alert ingestion, and a Loki sample log.

## Findings
- The repository already uses raw Kustomize subtrees under `gitops/channels/local`; observability should be another channel subtree instead of a separate deployment mechanism.
- The existing channel schema is the right contract surface for component pins, object storage, ServiceMonitor names, dashboards, and alerts.
- Prometheus Operator is not otherwise installed. A minimal ServiceMonitor CRD can satisfy the API contract while raw Prometheus scrape config performs the actual local scrape proof.
- Loki can use MinIO through S3-compatible configuration and `-config.expand-env=true`, keeping access keys in an Infisical-managed Secret.
- OTel Collector can run as a DaemonSet receiving OTLP traces/logs without hostPath log scraping, which keeps the security posture compatible with the current cluster baseline.
- Grafana can load datasources and dashboards from ConfigMaps, so dashboard render proof does not require mutable UI state.

## Anti-Findings
- HelmRelease and helm-controller are unnecessary and remain out of scope.
- Production SLI/SLO definitions, incident automation, and PagerDuty-style integrations are post-deployment work.
- Kube-state-metrics is useful for richer alert semantics, but INIT-117 can land the alert contract and local proof without adding a new controller.
