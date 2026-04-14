# Research prompt — Kubernetes GitOps manifests (`k8s/*`)

YOU are the researcher. YOU do the research yourself. Do NOT delegate
to sub-agents or launch subprocesses.

## Task

Research the Kubernetes manifest layer for a Phase 1 foundation
deployment using Flux CD as the GitOps controller. The target cluster
is k3s on Hetzner Cloud, provisioned by kube-hetzner via OpenTofu.

The goal is to document the problem space around four manifest entry
points that this repo will add or complete:

1. `k8s/base/flux-system/kustomization.yaml`
2. `k8s/base/monitoring/helmrelease.yaml`
3. `k8s/base/secrets/helmrelease.yaml`
4. `k8s/overlays/staging/kustomization.yaml`

This is Phase 1 research only. Do not design the manifests.

## Repo context

The repository already contains these related files:

- `k8s/base/monitoring/kustomization.yaml`
- `k8s/base/monitoring/namespace.yaml`
- `k8s/base/monitoring/helmrepository.yaml`
- `k8s/base/secrets/kustomization.yaml`
- `k8s/base/secrets/namespace.yaml`
- `k8s/base/secrets/helmrepository.yaml`

The repository also already has directories for:

- `k8s/base/flux-system/`
- `k8s/overlays/staging/`
- `k8s/overlays/production/`

The stack is locked:

- GitOps controller: Flux CD
- Cluster distro: k3s
- Infra provisioning: kube-hetzner via OpenTofu
- Monitoring: kube-prometheus-stack
- Bootstrap secrets: Bitnami sealed-secrets
- Future secret management: Infisical (not part of this phase)

## Research questions

### 1. Flux system bootstrap kustomization

For `k8s/base/flux-system/kustomization.yaml`, document:

- How Flux bootstraps itself through a root Kustomization
- Which resources the root entry point typically references in a
  GitOps repo
- Namespace best practices for `flux-system`
- Reconciliation and dependency patterns relevant to the root entry
  point

### 2. Monitoring stack HelmRelease

For `k8s/base/monitoring/helmrelease.yaml`, document:

- The current stable `kube-prometheus-stack` chart version from the
  official source
- Which categories of values are typically required or high-impact for
  Prometheus, Grafana, and Alertmanager in a Flux `HelmRelease`
- Resource requests and limits appropriate for a small k3s cluster
  with 1-3 nodes
- Retention settings, PVC/storage implications, and small-cluster
  tradeoffs

### 3. Sealed-secrets HelmRelease

For `k8s/base/secrets/helmrelease.yaml`, document:

- The current stable Bitnami `sealed-secrets` chart version from the
  official source
- Controller configuration categories relevant to a dedicated
  `sealed-secrets` namespace
- Key renewal, key rotation, and backup/restore considerations
- What belongs in Phase 1 bootstrap scope given that sealed-secrets is
  temporary and will later be replaced by Infisical

### 4. Staging overlay kustomization

For `k8s/overlays/staging/kustomization.yaml`, document:

- How Kustomize overlays reference and compose base manifests
- Staging-specific patch/use-case categories such as reduced
  resources, shorter reconciliation intervals, or smaller retention
  windows
- Flux-compatible overlay patterns and any constraints that matter
  when Flux renders/apply overlays

## Deliverable shape

Write `research/32-k8s-manifests.md` with these sections:

1. Scope and context
2. Flux bootstrap root kustomization
3. Monitoring HelmRelease research
4. Sealed-secrets HelmRelease research
5. Staging overlay research
6. Cross-cutting constraints and open questions
7. Sources

Within each technical section:

- Separate confirmed facts from inference when you need to infer
- Cite specific official documents, chart repositories, or chart docs
- Prefer tables when comparing options or listing required value
  categories

## Evidence quality bar

- Use official Flux documentation for Flux bootstrap, Kustomization,
  and Helm controller behavior
- Use official chart repositories/docs for chart version references:
  `prometheus-community/kube-prometheus-stack` and Bitnami
  sealed-secrets
- If you cite chart versions, include the exact version and the source
  page you got it from
- Use primary sources first; use secondary sources only if the primary
  source is silent, and label that clearly
- Include sizing or retention guidance relevant to small clusters; if
  upstream docs do not give direct 1-3 node guidance, say that
  explicitly and identify where you had to infer from defaults or
  production-oriented guidance

## Anti-goals

- Do NOT design solutions
- Do NOT write or suggest YAML manifests
- Do NOT recommend alternative tools or replace the locked stack
- Do NOT cover Terraform/OpenTofu details
- Do NOT cover application workloads, app charts, ingress, or Phase 2+
  platform work
- Do NOT modify any files other than `research/32-k8s-manifests.md`

## Output

Write only the research report to `research/32-k8s-manifests.md`.
