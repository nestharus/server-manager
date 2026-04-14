# Proposal Prompt: K8s GitOps Manifests Foundation

## Task
Write a proposal for the Kubernetes manifest layer of the Phase 1
foundation deployment.

## Inputs
- `research/32-k8s-manifests.md` — problem-space research
- `research/32-k8s-manifests-needs.md` — Humility-specific synthesis
- `k8s/base/monitoring/kustomization.yaml` — existing monitoring base
- `k8s/base/secrets/kustomization.yaml` — existing secrets base
- `AGENTS.md` — project rules

## Deliverable
Return markdown only to stdout for `proposals/32-k8s-manifests.md`.
Do not attempt to write files directly. The orchestrator will persist
the output verbatim.

The proposal must contain:
1. **Goal** — what this manifest batch establishes for Phase 1
2. **Design** — the exact intended content and structure for each of
   these four files:
   - `k8s/base/flux-system/kustomization.yaml`
   - `k8s/base/monitoring/helmrelease.yaml`
   - `k8s/base/secrets/helmrelease.yaml`
   - `k8s/overlays/staging/kustomization.yaml`
3. **Manifest-by-manifest decisions** — fields, chart versions,
   intervals, namespaces, values, and patch shapes to include
4. **Tradeoffs** — why these choices fit Phase 1 and a small k3s
   cluster
5. **Anti-scope** — what this batch explicitly does not cover

## Constraints
- All manifests must use Flux CD v2 API versions.
- `HelmRelease` must use `helm.toolkit.fluxcd.io/v2`.
- `HelmRepository` references must use `source.toolkit.fluxcd.io/v1`.
- File-level `Kustomization` manifests must use
  `kustomize.config.k8s.io/v1beta1`.
- Chart versions must be pinned; no floating tags.
- The monitoring base already has `kustomization.yaml`,
  `namespace.yaml`, and `helmrepository.yaml` for
  `prometheus-community`.
- The secrets base already has `kustomization.yaml`,
  `namespace.yaml`, and `helmrepository.yaml` for
  `sealed-secrets` from `bitnami-labs`.
- `k8s/base/flux-system/kustomization.yaml` must be the root Kustomize
  entry point for Flux bootstrap and must reference the monitoring and
  secrets bases.
- `k8s/base/monitoring/helmrelease.yaml` must define a
  `kube-prometheus-stack` `HelmRelease`, pin chart version `83.4.1`,
  configure Phase 1 base values for Prometheus, Grafana, and
  Alertmanager, and set explicit small-cluster resource requests and
  limits.
- `k8s/base/secrets/helmrelease.yaml` must define a
  `sealed-secrets` `HelmRelease`, pin chart version `2.18.5`, and keep
  scope minimal for Phase 1 bootstrap.
- `k8s/overlays/staging/kustomization.yaml` must reference the
  monitoring and secrets bases and include staging-specific patches for
  reduced resources and shorter intervals/retention.

## Requirements for the proposal
- Propose the exact object layout per file: document headers,
  resources, metadata naming, namespaces, and major `spec` fields.
- Be explicit about how the staging overlay patches the base manifests.
- Keep the distinction clear between file-level Kustomize manifests and
  Flux `Kustomization` CRDs.
- Keep the design aligned with Phase 1 bootstrap scope only.
- Assume a small Hetzner-backed k3s cluster; resource choices should be
  conservative, explicit, and defensible.

## Anti-goals
- Do NOT write the actual YAML files.
- Do NOT propose alternative tools or controllers.
- Do NOT cover application workloads.
- Do NOT expand scope into production overlay design beyond noting
  follow-on work where necessary.
- Do NOT implement; this is design only.

## Rules
- Use the research and synthesis as the grounding source.
- Prefer concrete manifest structure over generic GitOps commentary.
- Return only the final markdown proposal body, with no preamble or
  commentary outside the document.
