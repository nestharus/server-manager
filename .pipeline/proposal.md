# INIT-117 Phase 3 Proposal

## Overview
Deliver seven implementation slices that add the observability stack and close Phase 5.

## Slice 1: pipeline artifacts
- Replace stale INIT-108 pipeline notes with INIT-117 research, synthesis, proposal, risk, hookpoints, and implementation records.

## Slice 2: channel contract
- Add `observability` to source and resolved channel schemas.
- Add the local observability contract with component images, ServiceMonitor names, dashboard names, alert names, tenant label, and MinIO-backed Loki storage.

## Slice 3: core metrics and alerts
- Add `observability-system`, ServiceMonitor CRD, Infisical secrets, Prometheus, and Alertmanager raw manifests.
- Add basic alert rules for Pod crash loops, cluster-down detection, and certificate expiry.

## Slice 4: logs, traces, and dashboards
- Add Loki backed by MinIO, OTel Collector DaemonSet, Grafana datasources, and dashboard ConfigMaps.

## Slice 5: scrape contracts and network access
- Add ServiceMonitor resources for all required platform components.
- Add NetworkPolicies that allow observability traffic without changing component ownership.

## Slice 6: app metrics and harness
- Add `/api/v1/metrics` to the API.
- Add static/runtime observability validation and Buildkite static step coverage.

## Slice 7: Phase 5 wrap-up
- Mark all INIT-100 through INIT-117 rows done.
- Add `docs/phase-5-complete.md`.
- Update `infra/README.md` for the completed local substrate and post-INIT-117 deployment boundary.

## Rollback
Revert INIT-117 commits in reverse order. Removing `gitops/channels/local/observability` and the channel `observability` block fully detaches the stack.

## Anti-Scope
- No helm-controller.
- No production SLI/SLO program.
- No incident-response automation.
- No third-party alert integrations.
