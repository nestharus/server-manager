# Hookpoint Research: GitOps Foundation Implementation

## Purpose

Documents what existing code, infrastructure, and decisions the GitOps
Foundation implementation (38 files under `k8s/`) touches or depends on.
This is a greenfield `k8s/` tree, but it hooks into platform clusters
from `infra/`, locked architectural decisions, and forward contracts with
adjacent initiatives.

## Hookpoint 1 — Platform clusters from infra/ (VKE clusters Flux will target)

**Source**: `infra/modules/platform-cluster/main.tf`,
`infra/environments/dev/main.tf`.

**Constraint**: The VKE clusters provisioned by Platform Bootstrap are
the deployment targets for Flux reconciliation. The platform-cluster
module exposes `endpoint` and `kube_config` (sensitive) outputs. When
Flux is bootstrapped onto these clusters, it will consume those outputs
to establish the initial connection.

**Files affected**:
- `infra/modules/platform-cluster/main.tf` (output contract)
- `infra/environments/dev/main.tf` (dev cluster: `humility-dev-platform`,
  v1.32.3+1, vc2-2c-4gb, 2 nodes, EWR region)

**Implication**: The `gotk-sync.yaml` files under `k8s/clusters/` assume
a cluster exists at the endpoint provisioned by Platform Bootstrap. The
GitOps Foundation defines the desired-state structure; Platform Bootstrap
provides the substrate. The two initiatives share a handoff seam at
cluster `endpoint` + `kube_config` outputs.

**Risk if violated**: If the platform-cluster module output interface
changes (e.g., `endpoint` renamed), the Flux bootstrap path breaks.

## Hookpoint 2 — SealedSecrets controller installation

**Source**: `plans/proposals/gitops-foundation.md` §3 "Interfaces to
adjacent initiatives" — secrets management must provide encrypted or
referenced inputs consumable from cluster roots.

**Constraint**: The `k8s/base/controllers/kustomization.yaml` currently
defines a `gitops-controller-contract` ConfigMap declaring
`reconciler=flux` and `remoteReconciliation=disallowed`. The SealedSecrets
controller will be added as a resource in this directory (or as a Flux
HelmRelease in cluster roots) when the secrets initiative is implemented.

**Files affected**:
- `k8s/base/controllers/kustomization.yaml` (future SealedSecrets
  controller resource)
- `k8s/clusters/*/manifests/` (future SealedSecret resources)

**Implication**: The base controllers directory is the structural slot
for cluster-wide controller installations. Adding SealedSecrets must not
break the existing controller-contract ConfigMap or introduce a second
reconciliation path.

**Constraint from proposal**: "A cluster root may rely on at most one
secret-reconciliation path at any one time; changing the path is a
topology-affecting change."

## Hookpoint 3 — Existing discord app services deployment path

**Source**: `services/api/` (FastAPI application), existing chapter
service and repository code.

**Constraint**: The `k8s/clusters/<env>/app-cluster/manifests/` path is
where application workload manifests will land. The current discord app
(`services/api/`) does not yet have Kubernetes manifests, but the GitOps
Foundation creates the topology slot for them.

**Files affected**:
- `k8s/clusters/<env>/app-cluster/manifests/kustomization.yaml` —
  currently references the overlay and bootstrap slot; will later include
  application workload resources
- `k8s/clusters/<env>/app-cluster/manifests/bootstrap/kustomization.yaml`
  — topology slot for Flux-root bootstrapping

**Implication**: When the discord API service gets Kubernetes manifests
(Deployment, Service, Ingress), they will be added under the app-cluster
manifests path. The overlay layer will handle environment-specific
configuration (replica count, resource limits, image tags).

**Deployment model**: Application releases will be expressed as Git
changes to manifest files or image tags in the appropriate environment
path, then reconciled by Flux. Buildkite will build and push images but
will not kubectl-apply anything.

## Hookpoint 4 — Crossplane and Application Cluster Provisioning

**Source**: `plans/proposals/gitops-foundation.md` §3 "Interfaces to
adjacent initiatives" — Crossplane ClusterClaim resources land under
control-cluster roots.

**Constraint**: The control-cluster manifests include a `claims/`
directory as the topology slot for Crossplane cluster claims. The
`gitops.foundation.slot=crossplane-cluster-claims` ConfigMap declares
this slot's purpose and ownership.

**Files affected**:
- `k8s/clusters/<env>/control-cluster/manifests/claims/kustomization.yaml`
- `plans/proposals/app-cluster-provisioning.md` (consuming initiative)

**Implication**: Application Cluster Provisioning will add Crossplane
XRD/XRC resources to the claims directory. The GitOps Foundation
implementation ensures the directory exists and is reconciled by Flux,
but it does not contain actual claim resources yet.

## Hookpoint 5 — Platform decisions overlay (locked decisions)

**Source**: `plans/platform-decisions-overlay.md`.

**Locked decisions affecting this implementation**:

| Decision | Implementation alignment |
|----------|------------------------|
| Flux CD (GitOps reconciler) | All gotk-sync.yaml files use Flux v1 APIs |
| Buildkite (canonical CI/CD) | base/policies ConfigMap bars cluster mutation |
| Two-tier cluster model | control-cluster + app-cluster per environment |

**Constraint**: These decisions are locked and may not be changed by
the implementation. Any implementation choice that conflicts with a
locked decision requires re-running the risk assessment pipeline.

## Hookpoint 6 — Risk assessments (all LOW)

**Source**: `plans/risk/gitops-foundation-{audit,scope,shortcut}.md`.

**State**: All three risk assessments completed with LOW verdict. Nine
findings total (F-1 through F-9), all LOW. Two prior findings (secrets
single-path, cross-cluster dependency) were CLOSED after proposal
revisions.

**Implication**: The implementation proceeded with no MEDIUM or HIGH
findings blocking it. The LOW findings (production path protection,
multi-cluster naming, bootstrap sequencing, promotion workflow, incident
escape hatch) are deferred to implementation-time resolution.

## Summary

The GitOps Foundation implementation hooks into:
- Platform Bootstrap infrastructure (VKE cluster outputs as handoff seam)
- SealedSecrets controller slot (future addition to base/controllers)
- Discord app service deployment path (future workload manifests in
  app-cluster)
- Crossplane claim topology slot (control-cluster claims directory)
- Locked platform decisions (Flux CD, Buildkite, two-tier model)
- Completed risk assessments (all LOW, no blockers)
