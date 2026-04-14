# Proposal: K8s GitOps Manifests — Phase 1 Foundation

## Context

You are writing a proposal for the Kubernetes manifest layer of a
Phase 1 foundation deployment. Read the research at
`research/32-k8s-manifests.md` and the synthesis at
`research/32-k8s-manifests-needs.md`.

## Scope

Propose the exact content and structure for these 4 manifest files:

1. **`k8s/base/flux-system/kustomization.yaml`**
   - Root Kustomization entry point for Flux bootstrap
   - Must reference the monitoring and secrets bases

2. **`k8s/base/monitoring/helmrelease.yaml`**
   - HelmRelease for kube-prometheus-stack
   - Pin a specific chart version
   - Configure base values for Prometheus, Grafana, Alertmanager
   - Appropriate resource limits for a small k3s cluster

3. **`k8s/base/secrets/helmrelease.yaml`**
   - HelmRelease for sealed-secrets controller
   - Pin a specific chart version
   - Phase 1 bootstrap scope

4. **`k8s/overlays/staging/kustomization.yaml`**
   - Reference monitoring and secrets bases
   - Include staging-specific patches (reduced resources, shorter intervals)

## Constraints

- All manifests must use Flux CD v2 API versions
- HelmRelease uses `helm.toolkit.fluxcd.io/v2`
- HelmRepository uses `source.toolkit.fluxcd.io/v1`
- Kustomization uses `kustomize.config.k8s.io/v1beta1`
- Chart versions must be pinned (no floating tags)
- The monitoring base already has: kustomization.yaml, namespace.yaml,
  helmrepository.yaml (prometheus-community)
- The secrets base already has: kustomization.yaml, namespace.yaml,
  helmrepository.yaml (sealed-secrets from bitnami-labs)

## Anti-goals

- Do NOT write the actual YAML files (that's the implementation phase)
- Do NOT propose alternative tools
- Do NOT cover application workloads

## Output

Write the proposal to `proposals/32-k8s-manifests.md`.
