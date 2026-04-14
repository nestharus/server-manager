# Phase 1 Foundation — environments, benchmarking, and Vultr deployment

## 1. Executive summary

The local draft has already drifted away from the approved Hetzner proposal in substantive ways, not cosmetic ones. `infra/` now targets `Vultr Kubernetes Engine (VKE)` through the first-party `vultr` provider, validates `dev`, `staging`, and `production` as the only environment names, and sizes `dev` as the persistent low-cost cluster while sizing `staging` and `production` identically for production-shaped runs (`infra/main.tf`, `infra/cluster.tf`, `infra/variables.tf`, `infra/environments/*/terraform.tfvars`). The proposal and risk artifacts still describe a different problem: self-managed `k3s` on Hetzner via `kube-hetzner`, Hetzner-specific networking/storage risks, and a two-environment frame.

For a one-person-plus-agents workflow, the corrected problem is not "how to keep a second always-on QA cluster around." It is "how to keep one persistent iteration environment, one stable live environment, and one reproducible benchmark environment without multiplying operator burden." The repo already encodes that shape in comments and sizing, but it does not yet define the benchmark contract, the promotion criteria, or the environment-selection mechanism in Flux.

Several visible pieces are directionally correct:

- Separate per-environment state keys already exist for `dev`, `staging`, and `production`.
- The Terraform resource uses VKE's managed control plane instead of the old `kube-hetzner` path.
- The Kubernetes overlays already express a three-tier resource profile: smallest for `dev`, medium for `staging`, base values for `production`.

Several visible assumptions are now invalid or unproven:

- The proposal and risk docs still reason about Hetzner-specific failure modes that do not map directly to VKE.
- `k8s/base/monitoring/helmrelease.yaml` still hard-codes `hcloud-volumes`, which is a Hetzner storage-class name and cannot be correct on Vultr.
- `infra/tests/validate_terraform.sh` still validates `hcloud`, `kube-hetzner`, `location = "fsn1"`, and old variable names, so the current test contract describes the previous platform, not the current one.
- Flux bootstrap currently syncs `./k8s/base/flux-system`, not an environment-specific overlay, so the current GitOps path does not yet express cluster isolation between `dev`, `staging`, and `production`.

The biggest missing definition is benchmarking. The repo says `staging` is for "benchmarks, load tests, performance regression" and that it should be production-equivalent, but it does not define which workloads count, which metrics matter, what baseline is being compared, or what threshold blocks promotion. Until that is defined, `staging` is a label for an environment shape, not an actual release gate.

Evidence from official Vultr docs confirms that the operational problem has changed with the move to VKE. VKE uses a managed control plane, supports HA control planes and managed firewalls in the Terraform resource, provisions Vultr load balancers from Kubernetes `Service` objects, uses Calico as the default CNI, does not ship an ingress controller, supports block and file CSI storage classes, and handles ETCD backup/encryption at the provider layer rather than requiring cluster-side ETCD backup work.[^vke-terraform][^vke-ccm][^vke-networking][^vke-ingress][^vke-storage][^vke-etcd]

## 2. Environment model

### Observed local model

The current repo already encodes a three-environment model:

- `dev` is persistent and always on. Its stated purpose is "application dev, E2E tests, LLM video QA, fast iteration" and it uses the smallest worker plan with a 1-2 node range (`infra/environments/dev/terraform.tfvars`).
- `staging` is explicitly on-demand and ephemeral. Its stated purpose is "benchmarks, load tests, performance regression," with production-equivalent worker sizing and a destroy-after-use comment (`infra/environments/staging/terraform.tfvars`).
- `production` is the long-lived live environment, currently sized the same as staging (`infra/environments/production/terraform.tfvars`).

The Kubernetes overlays line up with that intent. `k8s/overlays/dev/kustomization.yaml` reduces monitoring retention and requests/limits for a cheap always-on cluster. `k8s/overlays/staging/kustomization.yaml` uses a middle profile. `k8s/overlays/production/kustomization.yaml` treats the base as the production profile.

### Role of each environment in a one-person-plus-agents workflow

For this project shape, the correct division of labor is narrow and asymmetric:

- `dev` is the default agent and human workbench. It exists to absorb rapid mutation, debugging, E2E iteration, and exploratory workflows that would be too noisy or too expensive to run through an ephemeral benchmark cluster every time. The local draft already places LLM video QA here, which matches the "persistent fast-iteration target" requirement better than an on-demand release-validation environment.
- `staging` is not a second development environment. Its value comes from being short-lived, reproducible, and production-shaped enough to answer a release question. If it becomes a general-purpose QA sandbox, it duplicates `dev` while also adding continuous operator cost and drift management.
- `production` is the boring environment. Its job is not experimentation, but to represent the actual live surface. In this repo's context, that matters doubly because the project operates on a real Discord guild with real users and visible actions need explicit approval.

This means the practical workflow is:

- Default iteration target: `dev`
- Release-candidate and regression check target: `staging`
- Live serving target: `production`

What is still missing is the control surface that makes those roles enforceable. The current Flux bootstrap skeleton syncs `./k8s/base/flux-system` (`k8s/base/flux-system/gotk-sync.yaml`) rather than an environment-specific overlay, so the repo has environment-specific manifests without an environment-specific reconciliation path yet.

### Implications for LLM video QA

The local evidence points to `dev`, not `staging`, as the default home for LLM video QA:

- `infra/environments/dev/terraform.tfvars` names it directly.
- The role of `staging` is framed around production-shaped benchmark validation, not general iterative testing.
- Nothing in the current Phase 1 tree defines a benchmark protocol for video QA, a staging-only data set, or a release gate based on video-QA outcomes.

So the present state is:

- Persistent `dev` is the only environment explicitly assigned to LLM video QA.
- Moving video QA into `staging` would require a policy decision that the project has not yet made.
- Treating video QA as a mandatory Phase 1 staging requirement would currently be scope expansion, because the repo does not yet define the workload, metrics, or gate.

## 3. Benchmarking definition

### What "benchmarking" can mean in this phase

The repo currently defines `staging` as a benchmark environment but does not define the benchmark. Because Phase 1 is still foundation work, benchmarking cannot honestly mean full product-load validation of the API, Discord daemon, and web app. Those services are explicitly out of scope in the current proposal draft, and the current `k8s/` tree does not deploy them.

For this phase, benchmarking only has a coherent meaning if it focuses on foundation-path workloads:

- Cluster bring-up and readiness
- Flux bootstrap and reconciliation
- Baseline add-on install time and steady-state resource cost
- Ingress path behavior through a VKE load balancer and the chosen ingress controller
- Persistent volume provisioning and attach behavior for the storage classes the platform intends to rely on
- Autoscaling or node-capacity behavior under controlled synthetic load

Anything broader is later-phase application benchmarking, not Phase 1 foundation benchmarking.

### Metrics that matter

The current draft does not define a metric set. To be operationally meaningful, a benchmark in this platform would need to record at least:

- Time-to-cluster-ready from apply to reachable cluster
- Time-to-GitOps-ready from cluster creation to baseline add-ons reconciled
- Time-to-ingress-ready from deploy to externally reachable ingress endpoint
- Request latency and error rate for a fixed ingress test workload
- Resource saturation for the worker pool during the benchmark window
- PVC provisioning latency and success rate for the chosen storage class
- Flux reconciliation failures or degraded states during and after the run

The existing monitoring overlays are directionally useful here because they at least imply a metric-collection substrate. But the repo does not yet connect those overlays to a benchmark contract, a dashboard, or a pass/fail rule.

### Baseline and threshold problem

The most underspecified part is not workload generation but comparison logic.

There are three different baseline shapes hidden inside the word "benchmark":

- Compare `staging` against the current `production` environment.
- Compare a new `staging` run against the last accepted benchmark on the same shape.
- Compare results against an absolute target budget.

Each answers a different release question. The repo currently answers none of them.

The same is true for thresholds. A release gate needs a rule of the form "promote only if X stays within Y." Today the local draft only says `staging` is for benchmarks and that it is production-equivalent. It does not define:

- which benchmark scenarios are mandatory
- how many runs constitute evidence
- whether the gate is relative or absolute
- which regressions are tolerated
- who can override a failed benchmark

Without that, "benchmarking" is only a good intention.

### Foundation-specific constraint on pass/fail thresholds

Vultr's own storage guidance is useful as a floor for this discussion, but not as a release gate by itself. Vultr documents target upper limits of roughly `10000 IOPS / 400 MiB/s` for NVMe block storage and `500 IOPS / 100 MiB/s` for HDD block storage, and explicitly says these are upper targets rather than guaranteed minimums.[^vultr-storage-perf] That means provider figures can inform interpretation, but a Phase 1 pass/fail threshold still has to be project-defined and workload-specific.

The current local tree also does not yet pin which storage class is canonical. That matters because the minimum valid PVC size differs materially by class:

- `vultr-block-storage`: minimum `10Gi`
- `vultr-block-storage-hdd`: minimum `40Gi`
- `vultr-vfs-storage`: shared RWX option for different workload shapes[^vke-storage]

That is relevant immediately because the current monitoring base requests `20Gi` for Prometheus and `5Gi` for Grafana/Alertmanager but still uses the old `hcloud-volumes` class. If those claims later map to HDD-backed storage, some of the declared sizes are below Vultr's documented minima. If they map to NVMe-backed storage, the size floor is acceptable but the current class name is still wrong.

## 4. Vultr/VKE implications

### Cluster lifecycle

The move from Hetzner + `kube-hetzner` to VKE changes the lifecycle burden materially.

Local evidence:

- `infra/cluster.tf` uses `resource "vultr_kubernetes"` directly.
- The file comment explicitly says "managed control plane" and "No kube-hetzner needed."

Official Vultr evidence:

- The Terraform resource supports `ha_controlplanes`, `enable_firewall`, `vpc_id`, and a default node pool, and exposes a managed kubeconfig/endpoint.[^vke-terraform]
- VKE performs ETCD backup and encryption at the provider layer.[^vke-etcd]
- VKE upgrades are split: Vultr handles control-plane upgrades, while worker-node upgrades remain an operator concern and can replace nodes, changing node IPs.[^vke-upgrades]

Implication: several risks in the old audit stop being central Phase 1 concerns in a VKE foundation. The Packer seam, self-managed ETCD backup requirement, and `kube-hetzner` bootstrap reproducibility issue are artifacts of the old design, not of the current Terraform shape. Worker-node replacement, workload tolerance to rescheduling, and environment bootstrap repeatability remain relevant, but they are different problems.

### Load balancers and ingress

VKE does not ship an ingress controller. Vultr documents that you bring your own ingress controller and that VKE integrates with Vultr load balancers through Kubernetes `Service` objects, especially `type: LoadBalancer`.[^vke-ingress][^vke-ccm][^vke-lb]

Implications for the current draft:

- The old proposal's general "baseline ingress" concept still survives the hosting change.
- The specific Hetzner load-balancer reasoning does not.
- The current `k8s/` tree does not yet include any ingress-controller manifests at all, so ingress is still a conceptual Phase 1 requirement rather than a visible draft implementation.

### Storage classes and persistent volumes

VKE's current storage model is not a drop-in replacement for Hetzner assumptions.

Official Vultr evidence:

- Block and file storage are exposed through CSI on VKE.[^vke-storage]
- The documented storage classes include `vultr-block-storage`, `vultr-block-storage-hdd`, and `vultr-vfs-storage`.[^vke-storage]
- Calico is the default CNI and supports Kubernetes `NetworkPolicy` enforcement.[^vke-networking]

Implications for the current draft:

- `hcloud-volumes` in `k8s/base/monitoring/helmrelease.yaml` is invalid on Vultr.
- The current monitoring PVC sizes need to be interpreted against a real Vultr storage-class decision instead of being carried forward mechanically.
- The old Hetzner-specific firewall discussion should be replaced with a VKE/Calico/network-policy discussion, because the underlying network control surface is different.

### Object storage backend and Terraform state

The local Terraform backend has already shifted to Vultr Object Storage:

- `infra/main.tf` declares an S3 backend with Vultr-specific compatibility flags.
- Per-environment backend files set `key = "infra/<env>/terraform.tfstate"` and point to `https://ewr1.vultrobjects.com`.

Official Vultr evidence confirms the general direction:

- Vultr Object Storage is a managed S3-compatible service and is directly supported by the Terraform provider as `vultr_object_storage`.[^vultr-object-storage]
- Vultr's own Terraform-state guide uses Object Storage with S3-compatible credentials and environment variables, and explicitly says each environment should use a different state key.[^vultr-state]

One important constraint remains unresolved:

- Vultr's Object Storage guide says the service "does not provide file locking" and advises procedural single-writer control.[^vultr-state]
- The local backend enables `use_lockfile = true`.

That does not prove the current backend is wrong, but it does mean the effective locking semantics for this exact backend combination are not established by the current repo evidence. For a one-person-plus-agents workflow, state mutation discipline is a real foundation concern because concurrent agent runs are otherwise easy to create accidentally.

### Environment isolation

The current Terraform layout does encode environment isolation at the cluster/state layer:

- Separate env names are validated in `variables.tf`.
- Separate tfvars and backend keys exist for all three envs.
- The cluster label and worker label include the environment name.

The current Kubernetes layout only partially encodes isolation:

- Separate overlays exist.
- Flux sync does not yet target an environment-specific overlay path.

So the repo currently expresses "three cluster definitions exist" more clearly than "each cluster will reconcile the correct cluster-specific workload set."

## 5. Scope assessment

### What belongs in Phase 1

Based on the corrected local model, these concerns still belong in Phase 1 foundation research and later proposal work:

- The role split between persistent `dev`, ephemeral benchmark `staging`, and live `production`
- The minimal Vultr/VKE cluster shape for each environment
- The environment-specific GitOps bootstrap path
- The baseline storage-class decision needed to make stateful platform add-ons valid on Vultr
- The minimum benchmark contract for foundation-path workloads
- The minimum observability surface needed to judge benchmark runs and environment health

These are foundation concerns because they define how the platform is exercised and trusted before application phases expand the surface area.

### What reads as scope creep

The following items do not appear justified as Phase 1 foundation requirements from the current evidence:

- A permanently running `staging` QA environment in addition to persistent `dev`
- Full application-load benchmarking for services that Phase 1 does not yet deploy
- A finalized promotion-policy automation system
- Production-grade LLM video-QA policy tied to release gates
- Full ingress, identity, database, and policy expansion under the banner of "benchmark realism"
- Broad observability platform work beyond what is needed to assess cluster health and benchmark runs

The current repo only supports the narrower claim that `staging` should be production-shaped enough to answer a benchmark/regression question when invoked. It does not support an always-on QA interpretation.

### Visible draft pieces: directionally correct vs invalid

Directionally correct:

- `infra/cluster.tf`: managed VKE cluster instead of self-managed `kube-hetzner`
- `infra/environments/*`: explicit `dev` / `staging` / `production` split
- `k8s/overlays/*`: three distinct resource-retention profiles
- `k8s/base/secrets/*` and `k8s/base/monitoring/*`: baseline add-on categories that a foundation phase plausibly needs
- `k8s/base/flux-system/README.md`: explicit acknowledgment that Flux bootstrap is a real bootstrap seam

Invalid or stale:

- `plans/proposals/phase1-foundation.md`: still frames Phase 1 as Hetzner + `k3s` + `kube-hetzner`
- `plans/risk/phase1-audit.md`, `phase1-scope.md`, `phase1-shortcut.md`: still evaluate the old Hetzner proposal
- `infra/tests/validate_terraform.sh`: still asserts `hcloud`, `kube-hetzner`, `location`, `control_plane_count`, and old state assumptions
- `k8s/base/monitoring/helmrelease.yaml`: still hard-codes `hcloud-volumes`
- `k8s/base/flux-system/gotk-sync.yaml`: still syncs only the base path, not an environment-specific overlay

### LLM video QA in scope terms

Local evidence makes LLM video QA a `dev` concern today, not a `staging` requirement. That means the Phase 1 foundation question is not "build staging for video QA." It is "ensure the persistent development environment is capable of hosting that workflow later." Whether video QA also becomes a staging gate is a later policy decision unless a future proposal defines a benchmarkable release artifact and acceptance threshold for it.

## 6. Open questions

1. What exact benchmark scenarios make `staging` worth creating?
   The current repo names benchmarks, load tests, and performance regression, but not the concrete workloads.

2. What baseline is each benchmark compared against?
   Current production, previous accepted staging run, or a fixed target budget each imply a different promotion policy.

3. What threshold actually blocks promotion?
   The repo currently has no declared error budget, latency budget, reconciliation budget, or storage benchmark threshold.

4. Which Vultr storage class is the Phase 1 default for stateful add-ons?
   This has immediate consequences for valid PVC sizes, cost, and interpretation of monitoring manifests.

5. How is Flux meant to select `dev` vs `staging` vs `production` overlays per cluster?
   The overlays exist, but the current sync skeleton points only at the base path.

6. Is the current Terraform backend locking model accepted for a one-person-plus-agents workflow?
   Vultr's own object-storage guidance warns that Object Storage itself does not provide file locking, while the local backend enables `use_lockfile`.

7. Is `enable_firewall` intentionally omitted from the VKE cluster resource, or is that simply unfinished drift?
   The official Terraform resource supports it, but the local cluster resource does not set it.

8. Does Phase 1 require ingress manifests now, or only the environment model that will host them?
   The old proposal treated ingress as foundation-critical, but the current `k8s/` tree does not yet implement that layer.

9. Is LLM video QA merely a supported `dev` workload, or a future release gate?
   The current evidence supports the first reading only.

[^vke-terraform]: Vultr Terraform resource reference for `vultr_kubernetes`: https://docs.vultr.com/reference/terraform/resources/kubernetes
[^vke-ccm]: Vultr support doc on cloud-controller-manager behavior: https://docs.vultr.com/support/products/vke/what-role-does-the-vultr-cloud-controller-manager-play-in-kubernetes-integration
[^vke-networking]: Vultr support doc on default VKE networking/Calico: https://docs.vultr.com/support/products/vke/what-is-the-default-networking-solution-in-a-vultr-kubernetes-engine-cluster
[^vke-ingress]: Vultr support doc on ingress-controller expectations: https://docs.vultr.com/support/products/vke/does-vke-come-with-an-ingress-controller
[^vke-storage]: Vultr guide on PVCs and VKE storage classes: https://docs.vultr.com/how-to-provision-persistent-volume-claims-on-vultr-kubernetes-engine
[^vke-etcd]: Vultr support doc on ETCD backup/encryption: https://docs.vultr.com/support/products/vke/is-etcd-backed-up-and-encrypted
[^vke-upgrades]: Vultr support doc on VKE upgrades: https://docs.vultr.com/support/products/vke/how-does-vultr-kubernetes-engine-cluster-handle-upgrades
[^vke-lb]: Vultr guide on load balancers with VKE: https://docs.vultr.com/how-to-use-a-vultr-load-balancer-with-vke
[^vultr-object-storage]: Vultr Terraform resource reference for Object Storage: https://docs.vultr.com/reference/terraform/resources/object_storage
[^vultr-state]: Vultr guide on Terraform state in Object Storage: https://docs.vultr.com/how-to-store-terraform-state-in-vultr-object-storage
[^vultr-storage-perf]: Vultr support doc on block-storage performance expectations: https://docs.vultr.com/support/products/storage/what-are-the-performance-expectations-for-block-storage
