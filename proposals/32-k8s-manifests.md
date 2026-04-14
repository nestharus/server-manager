# Proposal: K8s GitOps Manifests — Phase 1 Foundation

Date: 2026-04-14

## Goal

Define the Phase 1 manifest layer for the bootstrap platform stack in a
way that is explicit, pinned, and small-cluster-safe.

This batch should establish exactly four files:

1. A file-level Kustomize root for the `flux-system` bootstrap path
2. A `HelmRelease` for `kube-prometheus-stack`
3. A `HelmRelease` for `sealed-secrets`
4. A staging overlay that patches only environment-specific deltas

The proposal stays within Phase 1 foundation scope. It does not add
application workloads, alternate controllers, or production overlay
design.

## Design

This manifest batch should keep the two Kustomization layers separate:

- File-level Kustomize manifests use
  `kustomize.config.k8s.io/v1beta1`
- Flux-managed Helm installs use `helm.toolkit.fluxcd.io/v2`
- Existing `HelmRepository` objects remain the source objects and stay
  on `source.toolkit.fluxcd.io/v1`

The base layer should own stable platform defaults. The staging overlay
should only patch capacity and iteration-speed differences. It should
not fork structure or redefine the chart layout.

The intended ownership split is:

- `k8s/base/flux-system/kustomization.yaml`
  Bootstrap-facing file root that aggregates Flux bootstrap artifacts
  plus the two Phase 1 platform bases
- `k8s/base/monitoring/helmrelease.yaml`
  Base monitoring install with pinned version and explicit small-cluster
  budgets
- `k8s/base/secrets/helmrelease.yaml`
  Minimal bootstrap-only secrets controller install
- `k8s/overlays/staging/kustomization.yaml`
  Thin overlay that references the two bases and patches only staging
  deltas

## Manifest-by-Manifest Decisions

### 1. `k8s/base/flux-system/kustomization.yaml`

This file should be a file-level Kustomize manifest, not a Flux
`Kustomization` CRD.

Its shape should be:

- `apiVersion: kustomize.config.k8s.io/v1beta1`
- `kind: Kustomization`
- no `metadata` block
- `resources:` in this order:
  - `gotk-components.yaml`
  - `gotk-sync.yaml`
  - `../secrets`
  - `../monitoring`

The important point is that this directory remains the bootstrap root
for Flux-managed controller artifacts while also composing the Phase 1
platform bases. That keeps bootstrap-local files canonical and avoids a
second “root” directory for the same cluster bootstrapping concern.

This file should not:

- reference remote bases
- reference application workload trees
- contain inline patches
- try to define Flux reconciliation policy itself

Flux reconciliation policy belongs in Flux `Kustomization` CRDs
elsewhere. This file only describes the local manifest tree.

### 2. `k8s/base/monitoring/helmrelease.yaml`

This file should define one `HelmRelease`:

- `apiVersion: helm.toolkit.fluxcd.io/v2`
- `kind: HelmRelease`
- `metadata.name: kube-prometheus-stack`
- `metadata.namespace: monitoring`

`spec` should be shaped as follows:

- `releaseName: kube-prometheus-stack`
- `targetNamespace: monitoring`
- `interval: 30m`
- `timeout: 10m`
- `install.createNamespace: false`
- `install.remediation.retries: 3`
- `upgrade.remediation.retries: 3`
- `upgrade.cleanupOnFail: true`
- `chart.spec.chart: kube-prometheus-stack`
- `chart.spec.version: 83.4.1`
- `chart.spec.sourceRef.kind: HelmRepository`
- `chart.spec.sourceRef.name: prometheus-community`
- `chart.spec.sourceRef.namespace: monitoring`

The existing `HelmRepository` manifest in this base remains the source
object and should stay on `source.toolkit.fluxcd.io/v1`.

The `values` block should be intentionally small-cluster-biased rather
than chart-default-biased.

#### Prometheus values

The base should explicitly set:

- `prometheus.prometheusSpec.replicas: 1`
- `prometheus.prometheusSpec.retention: 10d`
- `prometheus.prometheusSpec.resources.requests.cpu: 250m`
- `prometheus.prometheusSpec.resources.requests.memory: 512Mi`
- `prometheus.prometheusSpec.resources.limits.cpu: 500m`
- `prometheus.prometheusSpec.resources.limits.memory: 1Gi`
- `prometheus.prometheusSpec.storageSpec.emptyDir: {}`
- `prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues: false`
- `prometheus.prometheusSpec.podMonitorSelectorNilUsesHelmValues: false`
- `prometheus.prometheusSpec.probeSelectorNilUsesHelmValues: false`
- `prometheus.prometheusSpec.ruleSelectorNilUsesHelmValues: false`

That gives Phase 1 an explicit single-replica bootstrap posture,
bounded memory, and ephemeral storage instead of silently inheriting
open-ended defaults.

#### Grafana values

The base should explicitly set:

- `grafana.persistence.enabled: false`
- `grafana.resources.requests.cpu: 50m`
- `grafana.resources.requests.memory: 128Mi`
- `grafana.resources.limits.cpu: 200m`
- `grafana.resources.limits.memory: 256Mi`
- `grafana.service.type: ClusterIP`

This keeps Grafana internal-only and disposable in Phase 1. Durable
Grafana state belongs in the later storage/persistence phase, not here.

#### Alertmanager values

The base should explicitly set:

- `alertmanager.alertmanagerSpec.replicas: 1`
- `alertmanager.alertmanagerSpec.retention: 120h`
- `alertmanager.alertmanagerSpec.resources.requests.cpu: 25m`
- `alertmanager.alertmanagerSpec.resources.requests.memory: 128Mi`
- `alertmanager.alertmanagerSpec.resources.limits.cpu: 100m`
- `alertmanager.alertmanagerSpec.resources.limits.memory: 256Mi`

Phase 1 should leave Alertmanager non-durable. Do not add persistent
storage or HA replicas in this batch.

#### Supporting component caps

Because the upstream chart leaves several component resource blocks
unset, the base should also cap the supporting controllers instead of
leaving them open-ended:

- `prometheusOperator.resources`
  - requests: `50m` CPU, `128Mi` memory
  - limits: `200m` CPU, `256Mi` memory
- `kubeStateMetrics.resources`
  - requests: `50m` CPU, `64Mi` memory
  - limits: `100m` CPU, `128Mi` memory
- `nodeExporter.resources`
  - requests: `25m` CPU, `32Mi` memory
  - limits: `100m` CPU, `64Mi` memory

This file should not introduce ingress, PVCs, external dashboards,
Alertmanager routing policy, or Grafana auth customization.

### 3. `k8s/base/secrets/helmrelease.yaml`

This file should define one `HelmRelease`:

- `apiVersion: helm.toolkit.fluxcd.io/v2`
- `kind: HelmRelease`
- `metadata.name: sealed-secrets`
- `metadata.namespace: sealed-secrets`

`spec` should be shaped as follows:

- `releaseName: sealed-secrets`
- `targetNamespace: sealed-secrets`
- `interval: 30m`
- `timeout: 5m`
- `install.createNamespace: false`
- `install.remediation.retries: 3`
- `upgrade.remediation.retries: 3`
- `upgrade.cleanupOnFail: true`
- `chart.spec.chart: sealed-secrets`
- `chart.spec.version: 2.18.5`
- `chart.spec.sourceRef.kind: HelmRepository`
- `chart.spec.sourceRef.name: sealed-secrets`
- `chart.spec.sourceRef.namespace: sealed-secrets`

The existing `HelmRepository` manifest in this base remains the source
object and should stay on `source.toolkit.fluxcd.io/v1`.

The `values` block should stay intentionally narrow:

- `resources.requests.cpu: 25m`
- `resources.requests.memory: 64Mi`
- `resources.limits.cpu: 100m`
- `resources.limits.memory: 128Mi`
- `metrics.serviceMonitor.create: false`

Everything else should stay at the chart’s safe defaults for Phase 1:

- keep the default non-root security posture
- keep default service account and RBAC creation
- keep ingress disabled
- keep network policy disabled
- keep automatic key renewal at the chart/project default
- do not add custom controller args

The proposal should treat this controller as temporary bootstrap
infrastructure. The manifest’s job is stable install, not long-term
secrets-platform tuning.

### 4. `k8s/overlays/staging/kustomization.yaml`

This file should also be a file-level Kustomize manifest:

- `apiVersion: kustomize.config.k8s.io/v1beta1`
- `kind: Kustomization`
- no `metadata` block
- `resources:`
  - `../../base/monitoring`
  - `../../base/secrets`

Because this batch only creates one overlay file, staging-specific
changes should be carried as inline `patches:` entries rather than
separate patch files.

The overlay should contain two patches, one per HelmRelease.

#### Patch target: monitoring HelmRelease

The first patch should target:

- `kind: HelmRelease`
- `name: kube-prometheus-stack`
- `namespace: monitoring`

This patch should reduce staging footprint and increase iteration speed:

- `spec.interval: 10m`
- `spec.timeout: 5m`
- `spec.values.prometheus.prometheusSpec.retention: 3d`
- `spec.values.prometheus.prometheusSpec.resources.requests.cpu: 150m`
- `spec.values.prometheus.prometheusSpec.resources.requests.memory: 256Mi`
- `spec.values.prometheus.prometheusSpec.resources.limits.cpu: 300m`
- `spec.values.prometheus.prometheusSpec.resources.limits.memory: 512Mi`
- `spec.values.grafana.resources.requests.cpu: 25m`
- `spec.values.grafana.resources.requests.memory: 96Mi`
- `spec.values.grafana.resources.limits.cpu: 100m`
- `spec.values.grafana.resources.limits.memory: 192Mi`
- `spec.values.alertmanager.alertmanagerSpec.retention: 48h`
- `spec.values.alertmanager.alertmanagerSpec.resources.requests.cpu: 15m`
- `spec.values.alertmanager.alertmanagerSpec.resources.requests.memory: 64Mi`
- `spec.values.alertmanager.alertmanagerSpec.resources.limits.cpu: 50m`
- `spec.values.alertmanager.alertmanagerSpec.resources.limits.memory: 128Mi`
- reduced caps for `prometheusOperator`, `kubeStateMetrics`, and
  `nodeExporter` to match the smaller staging node budget

The patch should change values only. It should not alter chart identity,
namespace identity, or release naming.

#### Patch target: sealed-secrets HelmRelease

The second patch should target:

- `kind: HelmRelease`
- `name: sealed-secrets`
- `namespace: sealed-secrets`

This patch should keep staging small and faster to reconcile:

- `spec.interval: 10m`
- `spec.timeout: 3m`
- `spec.values.resources.requests.cpu: 10m`
- `spec.values.resources.requests.memory: 32Mi`
- `spec.values.resources.limits.cpu: 50m`
- `spec.values.resources.limits.memory: 64Mi`

This patch should not change the chart version, source reference,
security defaults, or metrics posture.

## Tradeoffs

- Bootstrap root in `k8s/base/flux-system`
  Keeping the bootstrap artifacts and base composition in one file
  follows the repo’s chosen layout and avoids a second cluster-root
  convention.
- Explicit resource budgets over chart defaults
  The upstream charts do not provide a 1-3 node k3s sizing profile.
  Explicit budgets are safer than uncapped defaults on Hetzner staging
  and production nodes.
- Ephemeral monitoring storage in Phase 1
  Using `emptyDir` for Prometheus and leaving Grafana and Alertmanager
  non-persistent keeps bootstrap simple, but it accepts data loss on pod
  reschedule. That is the right trade for Phase 1 foundation work.
- Thin staging overlay over parallel staging tree
  Inline patches keep staging as an environment delta rather than a
  second manifest system. That reduces Flux ownership confusion and
  prune risk.
- Conservative remediation settings
  A few install/upgrade retries make transient chart or repository
  failures less noisy without turning failed upgrades into silent drift.
- Minimal sealed-secrets scope
  Treating sealed-secrets as temporary bootstrap infrastructure avoids
  overinvesting in a controller that the project already intends to
  replace with Infisical.

## Anti-scope

This batch should explicitly exclude:

- any application workload manifests
- Flux `Kustomization` CRDs that reconcile overlays or clusters
- production overlay design
- ingress exposure for Grafana or Alertmanager
- durable PVC design for Prometheus, Grafana, or Alertmanager
- Alertmanager receiver/routing policy
- Grafana auth, dashboards, or datasources customization
- sealed-secrets key backup workflow automation
- Infisical integration or migration work
- alternative monitoring or secrets tools
