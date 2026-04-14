# Risk Assessment: Shortcut — K8s GitOps Manifests

## Verdict: LOW

## Findings

1. **Chart versions are fully pinned — no floating tags (LOW)**
   Both HelmReleases pin exact chart versions (`83.4.1` for
   kube-prometheus-stack, `2.18.5` for sealed-secrets). No version
   ranges, `~` constraints, or `latest` references. This eliminates the
   most common K8s manifest shortcut: inheriting whatever upstream
   publishes next.

2. **Resource budgets are explicit for every component (LOW)**
   Upstream chart defaults leave resource requests and limits empty for
   most components. The proposal fills in explicit budgets for
   Prometheus, Alertmanager, Grafana, kube-state-metrics, node-exporter,
   Prometheus Operator, and the config reloader — in both base and
   staging. This avoids the "rely on chart defaults" shortcut that causes
   unbounded resource consumption on small clusters.

3. **Ephemeral storage is a documented tradeoff, not a masked shortcut (LOW)**
   Prometheus uses `emptyDir: {}`, Alertmanager uses `storage: {}`, and
   Grafana has `persistence.enabled: false`. Each is explicitly called
   out in both the design decisions and the tradeoffs section, with
   durable PVC-backed storage listed as follow-on work. This is a
   deliberate Phase 1 scoping decision, not a silent omission.

4. **Base/overlay separation is clean — no structural duplication (LOW)**
   The staging overlay patches only environment-specific deltas
   (intervals, retention, resource budgets) via strategic-merge patches.
   It does not redefine base structure, re-declare object metadata, or
   duplicate non-delta fields. The overlay references bases via relative
   paths rather than copying manifests. This is standard Kustomize
   practice with no shortcut patterns.

5. **Source-vs-artifact distinction is explicit throughout (LOW)**
   The proposal repeatedly distinguishes file-level Kustomize
   `kustomization.yaml` (the on-disk composition tool) from Flux
   `Kustomization` CRDs (the controller reconciliation object). The
   bootstrap root aggregates both generated Flux artifacts
   (`gotk-components.yaml`, `gotk-sync.yaml`) and hand-authored platform
   bases, and the proposal acknowledges this mixing as an acceptable
   Phase 1 tradeoff rather than pretending the two layers are identical.

6. **Staging overlay patches HelmRepository intervals alongside HelmRelease intervals (LOW)**
   Four separate strategic-merge patches each change `spec.interval` to
   `15m` for their respective objects. While this looks duplicative, it
   is inherent to Kustomize patching of distinct objects in distinct
   namespaces — there is no cleaner mechanism. The proposal explains the
   intent: staging sees both chart index refreshes and release
   reconciliation faster.

7. **No manifest validation or linting step mentioned (LOW)**
   The proposal does not reference `kustomize build` dry-run validation,
   kubeconform, or CI-level linting for the new manifests. However,
   "authoring the actual YAML manifests" is listed as anti-scope — the
   proposal is a design document, not an implementation pipeline
   specification. Validation tooling is a CI concern, not a manifest
   design shortcut.

8. **Sealed-secrets scoped tightly as bootstrap-only (LOW)**
   The proposal avoids over-engineering sealed-secrets: no
   `fullnameOverride`, no custom `commandArgs`, no metrics integration,
   no ingress. The header comment explicitly labels it as "temporary
   until Infisical." This prevents the "fix one shortcut by adding
   another" pattern — the controller stays minimal rather than accruing
   configuration debt that later complicates removal.

9. **Namespace creation handled by pre-existing base resources (LOW)**
   Both HelmReleases set `install.createNamespace: false` and rely on
   the existing `namespace.yaml` files already present in the monitoring
   and secrets bases. The base `kustomization.yaml` files list
   `namespace.yaml` before `helmrelease.yaml` in their resource
   ordering. This is correct Kustomize practice — no hardcoded namespace
   creation workaround.

10. **Monitor selectors are explicitly permissive by design (LOW)**
    The proposal sets `serviceMonitorSelector: {}`,
    `podMonitorSelector: {}`, and `probeSelector: {}` with the
    corresponding `NilUsesHelmValues: false` flags. This is a deliberate
    extensibility choice documented in the design decisions, not a "select
    everything because configuring selectors is hard" shortcut. The
    tradeoffs section acknowledges the wider discovery surface.

## Justification

The proposal introduces no shortcuts. Every design choice that could
appear to be a shortcut — ephemeral storage, permissive selectors,
minimal sealed-secrets configuration, inline staging patches — is
explicitly documented as a deliberate Phase 1 scoping decision with
clear rationale. Chart versions are pinned, resource budgets are
explicit across all components, the base/overlay layering is clean, and
the source-vs-artifact distinction is maintained throughout.

The closest thing to a concern is the absence of a manifest validation
step, but that falls outside the proposal's stated scope (design, not
CI pipeline). No hardcoded values lack justification, no logic is
duplicated unnecessarily, and no workarounds mask underlying problems.
The proposal's anti-scope section is precise about what it defers rather
than silently omitting it.
