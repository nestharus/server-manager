# GitOps Foundation — Synthesis (Research → Implementation)

## Purpose

Bridges the Phase 1 research (`plans/research/gitops-foundation.md`) and
the approved proposal (`plans/proposals/gitops-foundation.md`) into
concrete needs that drove the 38-file `k8s/` implementation. Each need
traces back to a research finding and forward to specific implementation
files.

## Need 1 — Three-layer Kustomize structure

**Research finding**: Section 3 establishes the `base → overlays →
clusters` Kustomize layering pattern as the right fit for path-based
multi-environment GitOps.

**Proposal source**: §3 "Repository shape" defines the canonical layout.

**Need**: The implementation must create `k8s/base/`, `k8s/overlays/`,
and `k8s/clusters/` with clear separation of concerns — shared intent in
base, environment variation in overlays, cluster-specific Flux wiring in
clusters.

**Implementation**: `k8s/base/kustomization.yaml` orchestrates platform,
controllers, namespaces, and policies. Overlays reference base via
relative paths. Cluster roots reference overlays.

## Need 2 — Per-cluster Flux root with GitRepository + Kustomization

**Research finding**: Section 1 documents the Flux reconciliation model —
each cluster runs its own controllers and reconciles only its own path.

**Proposal source**: §3 "Per-cluster Flux roots" — no cluster
reconciles a parent directory spanning multiple clusters.

**Need**: Each cluster directory must contain a `gotk-sync.yaml` with a
`GitRepository` (source polling) and a `Kustomization` (path-scoped
reconciliation) pair. The Kustomization path must point to that
cluster's manifests directory, not a shared parent.

**Implementation**: Six `gotk-sync.yaml` files under
`k8s/clusters/{dev,staging,production}/{app-cluster,control-cluster}/`,
each scoped to `./k8s/clusters/<env>/<cluster>/manifests`.

## Need 3 — Environment separation via path isolation

**Research finding**: Section 2 evaluates branch-based, path-based, and
repo-based separation and recommends path-based for this project's scale
and team size.

**Proposal source**: §3 "Environment separation" — dev, staging,
production as distinct directories.

**Need**: Three complete environment paths must exist under both
`overlays/` and `clusters/`, with no shared Flux root spanning multiple
environments.

**Implementation**: `k8s/overlays/{dev,staging,production}/` and
`k8s/clusters/{dev,staging,production}/` each with control-cluster and
app-cluster subdirectories.

## Need 4 — Two-tier cluster model (control + app)

**Research finding**: Section 1 references the per-cluster installation
model. The proposal preserves the locked two-tier split.

**Proposal source**: §3 "Control cluster vs app cluster" — separate
failure and lifecycle boundaries.

**Need**: Every environment must have both a `control-cluster` root
(platform control-plane) and an `app-cluster` root (application
workloads), each with independent Flux reconciliation.

**Implementation**: Six cluster roots total — two per environment. Each
has independent GitRepository + Kustomization with distinct names and
paths.

## Need 5 — Hard CI/CD boundary (Buildkite validates, Flux reconciles)

**Research finding**: Section 1 documents Flux's pull-based model where
no external system pushes to clusters.

**Proposal source**: §3 "Git as desired state, Flux as sole reconciler"
— Buildkite does not own kubectl apply, helm upgrade, or flux reconcile.

**Need**: The implementation must encode this boundary declaratively.
No CI-triggered cluster mutation paths should exist in the k8s/
structure.

**Implementation**: `k8s/base/policies/kustomization.yaml` generates a
`gitops-boundary-policy` ConfigMap with
`buildkiteClusterMutation=disallowed` and
`promotionModel=path-based-git-change`. The acceptance test validates
this literal.

## Need 6 — Platform metadata as ConfigMaps with stable names

**Research finding**: Section 3 documents the `configMapGenerator` with
`disableNameSuffixHash: true` pattern for explicit naming.

**Need**: All metadata ConfigMaps (platform defaults, controller
contracts, boundary policies, overlay metadata, cluster-root contracts)
must use `disableNameSuffixHash: true` so names are deterministic and
inspectable.

**Implementation**: Every Kustomization file in the tree uses
`generatorOptions: { disableNameSuffixHash: true }` and generates named
ConfigMaps carrying `gitops.foundation.*` literals.

## Need 7 — Crossplane claim topology slot

**Proposal source**: §3 "Interfaces to adjacent initiatives" — Crossplane
ClusterClaim resources land under control-cluster roots.

**Need**: Control-cluster manifests must include a `claims/` directory
as the topology slot for Application Cluster Provisioning.

**Implementation**: `k8s/clusters/{dev,staging,production}/control-cluster/manifests/claims/kustomization.yaml`
with ConfigMap declaring `gitops.foundation.slot=crossplane-cluster-claims`.

## Need 8 — Bootstrap slot for app clusters

**Proposal source**: §3 "Interfaces to adjacent initiatives" — per-cluster
Flux root bootstrap for newly provisioned downstream clusters.

**Need**: App-cluster manifests must include a `bootstrap/` directory as
the topology slot for Flux-root bootstrapping onto new clusters.

**Implementation**: `k8s/clusters/{dev,staging,production}/app-cluster/manifests/bootstrap/kustomization.yaml`
with ConfigMap declaring `gitops.foundation.slot=flux-root-bootstrap`.

## Need 9 — Reconciliation cadence alignment

**Research finding**: Section 5 specifies GitRepository at 1m,
Kustomization at 10m, timeout at 5m.

**Need**: All `gotk-sync.yaml` files must use consistent intervals
matching the researched cadence decisions.

**Implementation**: All six gotk-sync files use `interval: 1m0s` for
GitRepository, `interval: 10m0s` for Kustomization, `timeout: 5m0s` for
Kustomization.

## Need 10 — Acceptance test coverage

**Need**: An acceptance test must validate the structural invariants:
layering, environment paths, two-tier model, Flux scoping, Buildkite
boundary, and manifest file presence.

**Implementation**: `k8s/tests/test_gitops_foundation.sh` (256 lines)
validates all structural invariants with `set -euo pipefail` and clear
failure messages.

## Summary

| # | Need | Research § | Proposal § | Key implementation files |
|---|------|-----------|------------|------------------------|
| 1 | Three-layer Kustomize | §3 | §3 repo shape | base/, overlays/, clusters/ |
| 2 | Per-cluster Flux root | §1 | §3 Flux roots | gotk-sync.yaml × 6 |
| 3 | Path-based env separation | §2 | §3 env separation | {dev,staging,production}/ dirs |
| 4 | Two-tier cluster model | §1 | §3 control vs app | control-cluster/ + app-cluster/ × 3 |
| 5 | Hard CI/CD boundary | §1 | §3 Git/Flux/CI | base/policies/kustomization.yaml |
| 6 | Stable ConfigMap names | §3 | — | disableNameSuffixHash across tree |
| 7 | Crossplane claim slot | — | §3 interfaces | claims/kustomization.yaml × 3 |
| 8 | Bootstrap slot | — | §3 interfaces | bootstrap/kustomization.yaml × 3 |
| 9 | Reconciliation cadence | §5 | — | gotk-sync.yaml intervals |
| 10 | Acceptance tests | — | §7 exit criteria | test_gitops_foundation.sh |
