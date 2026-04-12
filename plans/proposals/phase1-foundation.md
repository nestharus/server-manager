# Phase 1 Proposal: Foundation Bootstrap

## 1. Executive summary

Phase 1 establishes the minimum durable platform substrate required to run any later workload on the new Hetzner-based stack. Its job is not to ship the Discord bot, Harbor, PostgreSQL, Authentik, Pomerium, or the broader policy plane. Its job is to create the production cluster, the declarative control surface around that cluster, the secret-delivery path, the object-storage baseline, and enough observability to prove the foundation is healthy before Phase 2 starts layering real applications onto it.

The recommended Phase 1 shape is:

- Hetzner Cloud as the infrastructure provider.
- A production k3s cluster created by the `kube-hetzner` OpenTofu module.
- OpenTofu as the single infrastructure control plane.
- Flux CD as the cluster reconciler for add-ons and future workloads.
- Hetzner Object Storage as the S3-compatible bucket surface for OpenTofu state backups, later artifacts, and backup destinations.
- `sealed-secrets` as the Phase 1 secret-management mechanism because it is the smallest working GitOps-native option.
- `kube-prometheus-stack` as the minimum observability substrate, with Grafana and Alertmanager included.
- Kong deferred to Phase 2 unless an externally reachable Phase 1 service proves necessary.
- Buildkite agents designed to run on the cluster, but not treated as required bootstrap blockers.

The main architectural discipline in this phase is scope control. The unified index still contains many later systems that are valid eventually but are not bootstrap requirements: Harbor, PostgreSQL, Authentik, Pomerium, OPAL/Cedar, Kafka, Debezium, Loki, Cloudflare, Calico hardening, and the optional custom event plane. Pulling those into Phase 1 would turn “foundation bootstrap” into “half the platform,” which is exactly how bootstrap phases fail.

Phase 1 is complete when operators can provision the cluster from OpenTofu, Flux can reconcile both Kustomize and Helm resources from Git, secrets can flow into pods, Prometheus and Grafana can confirm cluster health, and test workloads can reach Hetzner Object Storage.

## 2. Infrastructure components

| Component | What it is | Why it is needed | How it is deployed | Depends on |
|---|---|---|---|---|
| Hetzner Cloud base | Cloud servers, private network, firewalling, load balancer integration, volumes | Provides the raw infrastructure for the platform | OpenTofu manages Hetzner primitives directly and invokes `kube-hetzner` for cluster bring-up | Hetzner account, API token, DNS domain |
| k3s via `kube-hetzner` | The production Kubernetes cluster | All later platform services and workloads need a runtime substrate | OpenTofu module deployment with pinned module/provider versions | Hetzner base infra |
| OpenTofu | Canonical IaC engine | Keeps infrastructure declarative, reviewable, and reproducible | Run from CI and operator workstations against remote state in object storage | Hetzner Object Storage, secrets for API access |
| Flux CD | GitOps reconciler | Turns Git into the source of truth for cluster add-ons and later apps | Bootstrapped after cluster creation; then self-managed via Git | Working cluster, Git repository access |
| GitOps manifests repo | Desired state for namespaces, add-ons, Helm releases, and overlays | Separates cluster desired state from imperative operator actions | Plain Git repository watched by Flux | Flux bootstrap |
| `sealed-secrets` | GitOps-friendly secret encryption controller | Gives Phase 1 a low-friction way to move runtime secrets into Kubernetes without introducing another stateful service | HelmRelease via Flux | Flux, cluster public key distribution |
| Hetzner Object Storage | S3-compatible external bucket service | Used for OpenTofu state snapshots, later artifacts/backups, and pod S3 connectivity | Provisioned outside the cluster, credentials stored as sealed secret | Hetzner account |
| Hetzner Cloud Controller + CSI | Kubernetes integration for load balancers, networking, and block volumes | Required for service exposure and persistent volumes | Installed as cluster add-ons via Flux | Working cluster, Hetzner API secret |
| Base observability | Prometheus, Alertmanager, Grafana, node exporters, kube-state-metrics | Proves the cluster is healthy before application onboarding begins | `kube-prometheus-stack` HelmRelease via Flux | Flux, persistent volumes |
| Kong ingress path | Shared ingress/gateway layer | Needed later for public HTTP surfaces, but not for a Discord bot with no public API in bootstrap | Prepared in repo structure, deferred from active deployment unless required | Flux, load balancer support |
| Buildkite-on-Kubernetes pattern | Self-hosted CI execution on cluster | Needed in Phase 2 for builds and deployment automation | Planned through `agent-stack-k8s`, but activated after Phase 1 foundation is stable | Cluster, Flux, secret delivery, spare worker capacity |

The important dependency cut is this: Flux, secret delivery, object storage, and observability are Phase 1 essentials. Kong and Buildkite are Phase 2 consumers of the foundation and should not block cluster bootstrap.

## 3. kube-hetzner cluster specification

### Recommended minimum topology

This proposal uses a minimum cluster sized for the expected non-optional platform, not merely for the empty Phase 1 shell:

- 3 control-plane nodes: `CPX21` each, 3 vCPU / 4 GB RAM / 80 GB SSD.
- 3 worker nodes: `CPX31` each, 4 vCPU / 8 GB RAM / 160 GB SSD.

Why this size:

- Three control-plane nodes are the minimum sane HA shape for embedded etcd and k3s server quorum.
- Three workers allow one node failure without collapsing all schedulable capacity.
- `CPX31` workers give enough headroom for Prometheus, Grafana, Alertmanager, Flux, future Harbor, PostgreSQL, Kong, Pomerium, Authentik, and the `server-manager` workload without immediately forcing a resize in Phase 2.
- The conditional advanced event plane from Phase 7 is not included in this “minimum full platform” assumption. If Kafka-heavy later phases survive unchanged, more workers will be required.

### HA control plane

The cluster should use:

- k3s with embedded etcd across the 3 control-plane nodes.
- Placement groups or equivalent anti-affinity so the control-plane nodes are not co-located on the same host.
- Automated replacement disabled for control-plane nodes unless a documented rolling maintenance path exists; control-plane churn should be explicit and serialized.
- Module-pinned upgrades: no drifting to whatever `kube-hetzner` or k3s publishes next.

This is the right compromise for Hetzner. Hetzner has no first-party managed Kubernetes control plane, so the proposal should optimize for a small, boring, known HA layout instead of inventing custom control-plane logic.

### Network

The cluster should run entirely on a Hetzner private network for east-west traffic.

Public access policy:

- `6443/tcp` Kubernetes API: allow only from operator/admin CIDRs.
- `22/tcp` SSH: allow only from operator/admin CIDRs during bootstrap and break-glass maintenance; later phases can reduce this further.
- `80/tcp` and `443/tcp`: not opened until an ingress service exists.
- All intra-cluster traffic: allowed on the private network.
- NodePort exposure: disabled by policy; do not use public NodePorts as an operations shortcut.

Firewall intent:

- default deny on unsolicited public inbound except approved management ports;
- explicit allow for private-network node-to-node traffic;
- normal outbound internet access for image pulls, Flux Git sync, and Buildkite agent connections later.

### Load balancer configuration

Phase 1 should prepare the cluster for Hetzner load balancers through the cloud controller and service annotations, but it should not force creation of a public load balancer until a real `LoadBalancer` service exists.

That means:

- the cluster is LB-capable on day one;
- the first shared public load balancer is created when Kong or another justified public service lands;
- Grafana and early operator surfaces are accessed initially via `kubectl port-forward`, internal-only exposure, or tightly scoped allowlisted access rather than by creating public endpoints just to satisfy symmetry.

This keeps costs down and avoids introducing public attack surface before Phase 2 or 3 actually needs it.

### Storage

Persistent storage strategy:

- Use Hetzner CSI-backed persistent volumes for all stateful cluster workloads.
- Reserve local-path storage for disposable workloads only.
- Separate PVC classes by usage where helpful: small durable volumes for controllers, medium volumes for Prometheus and Grafana, larger future volumes for PostgreSQL and Harbor.

Expected Phase 1 persistent consumers:

- Prometheus TSDB
- Grafana persistent settings
- Alertmanager state

Future consumers already accounted for in node sizing:

- Harbor registry storage
- PostgreSQL data
- possible Loki if later enabled

Longhorn, Rook, or other in-cluster storage systems are intentionally out of scope for Phase 1. Hetzner volumes are the simpler bootstrap answer.

## 4. OpenTofu structure

The OpenTofu layout should separate provider infrastructure from Kubernetes desired state and should support production-first rollout without collapsing staging support in the codebase.

Recommended structure:

```text
infra/
  modules/
    hcloud-foundation/
    kube-hetzner-cluster/
    object-storage/
  live/
    production/
      foundation/
        backend.hcl
        main.tf
        providers.tf
        variables.tf
        outputs.tf
        production.tfvars
    staging/
      foundation/
        backend.hcl
        main.tf
        providers.tf
        variables.tf
        outputs.tf
        staging.tfvars
```

Principles behind this shape:

- `modules/` holds reusable infrastructure building blocks.
- `live/<env>/foundation` is the environment-specific instantiation of those modules.
- The foundation stack owns Hetzner primitives, object-storage buckets for the platform, and the cluster bootstrap inputs.
- Flux-managed manifests do not live inside the OpenTofu stack; they belong in a GitOps repo watched by Flux.

### Remote state

Remote state should live in a dedicated Hetzner Object Storage bucket, with one state key per environment and stack.

Recommended pattern:

- bucket: `humility-platform-tfstate`
- keys:
  - `production/foundation.tfstate`
  - `staging/foundation.tfstate`

Why Hetzner Object Storage is the right state backend here:

- it is already the chosen S3-compatible storage for the platform on Hetzner;
- OpenTofu state is low-throughput and backup-shaped, which matches Hetzner Object Storage’s strengths;
- it avoids introducing a second storage vendor just for state.

State safety rules:

- serialize applies per environment;
- take automated versioned backups or snapshots of state objects;
- never share one state file across production and staging;
- no manual object edits.

### Variables and secrets

Non-secret environment differences belong in `*.tfvars` files or equivalent environment-specific configuration.

Sensitive bootstrap values should not be committed:

- Hetzner API token
- Git deploy key or Git HTTPS token for Flux bootstrap
- object-storage access key and secret
- later Buildkite agent token

Those secrets should enter OpenTofu through CI environment variables or operator shell environment, not through committed files.

### Environment separation

Phase 1 should create `production` first, but the code layout should contain both `production` and `staging` from day one.

That gives three benefits:

- environment drift is reduced because both layouts evolve together;
- later staging creation is a provisioning decision, not a repo refactor;
- GitOps overlays can already target `clusters/production` and `clusters/staging`.

The staging environment does not need to be provisioned during Phase 1 if cost control matters. The important part is that the structure exists now.

## 5. Flux CD setup

Flux should manage cluster add-ons and future workloads from a dedicated GitOps repository rather than from the OpenTofu repository.

Recommended Git structure:

```text
gitops/
  clusters/
    production/
      flux-system/
      kustomization.yaml
      infrastructure.yaml
      observability.yaml
      secrets.yaml
    staging/
      flux-system/
      kustomization.yaml
  infrastructure/
    base/
      namespaces/
      sources/
      sealed-secrets/
      monitoring/
    overlays/
      production/
      staging/
  apps/
    base/
    overlays/
      production/
      staging/
```

### Kustomization hierarchy

The hierarchy should be:

- `base`: reusable definitions with no environment-specific values.
- `overlays/<env>`: environment-specific patches.
- `clusters/<env>`: top-level Flux entrypoint wiring together the environment.

This keeps Flux readable. Operators should be able to answer “what is supposed to run in production?” by reading `clusters/production`, not by tracing several unrelated repos.

### Reconciliation model

Flux watches the Git repository on a short interval and reconciles:

- `GitRepository` source objects for manifest fetch;
- `Kustomization` resources for plain YAML and Kustomize overlays;
- `HelmRepository` and `HelmRelease` resources for chart-driven add-ons.

Phase 1 should explicitly prove both delivery modes:

- one simple Kustomize-managed workload or namespace;
- one simple HelmRelease-managed add-on.

### Helm management

Helm charts should be managed only through Flux objects:

- `HelmRepository` defines the chart source;
- `HelmRelease` defines chart version, values, and install/upgrade behavior.

Do not install platform add-ons with ad hoc `helm install` commands and then pretend Flux owns them. That creates split-brain ownership immediately.

## 6. Secrets management

### Evaluation

**Infisical**

- Strengths: real secret-management product, better long-term UX, strong fit once multiple humans, services, and rotation workflows exist.
- Weaknesses for Phase 1: more moving parts, more bootstrap complexity, and usually another stateful dependency before the cluster baseline is stable.

**sealed-secrets**

- Strengths: smallest working GitOps-native solution, easy to reason about, no separate database, no extra external dependency, good fit for a small number of Kubernetes runtime secrets.
- Weaknesses: not a full secret-management platform, no rich rotation workflow, weaker fit once non-Kubernetes consumers or many rotating secrets exist.

**external-secrets-operator**

- Strengths: good sync engine when an external source of truth already exists.
- Weaknesses: not actually a secret manager by itself, so it does not solve the bootstrap problem unless Infisical or another manager already exists.

### Phase 1 choice

Pick **`sealed-secrets`** for Phase 1.

Why:

- it is the simplest thing that satisfies the actual bootstrap requirement;
- it aligns naturally with Flux and Git-reviewed desired state;
- it avoids introducing an additional stateful service before the cluster is proven healthy;
- it is good enough for the small secret set required before Phase 2.

Why not Infisical yet:

- Infisical may still be the right later-platform answer, but it is not the simplest bootstrap answer on Hetzner;
- bootstrapping a secret manager before the cluster, storage, observability, and GitOps loop are stable is backwards.

### Secret flow

The Phase 1 secret flow should be:

1. Operator or CI obtains the cluster’s `sealed-secrets` public certificate.
2. Sensitive values are encrypted into `SealedSecret` manifests offline.
3. Flux reconciles the encrypted manifests into the cluster.
4. The controller unseals them into ordinary Kubernetes `Secret` objects in the target namespace.
5. Pods consume those secrets through environment variables, mounted files, or chart values.

Bootstrap caveat:

- secrets needed before `sealed-secrets` exists, such as the Hetzner token and Flux bootstrap Git credential, remain outside the cluster and are provided through CI/operator environment.

That is acceptable. Phase 1 only needs a working in-cluster secret-delivery path, not a universal enterprise secret product.

## 7. Base observability

Phase 1 should install **`kube-prometheus-stack`** and stop there for observability minimum scope.

Included:

- Prometheus for metrics collection
- node-exporter and kube-state-metrics
- Alertmanager
- Grafana

Alert baseline:

- node down
- Kubernetes node not ready
- pod crash loop / repeated restart
- Prometheus target missing for node exporters
- low persistent-volume free space where applicable

Why this is enough:

- it proves the cluster is healthy;
- it gives operators immediate visibility into saturation and failures;
- it is the minimum needed before application onboarding.

### Loki decision

Defer **Loki** or any centralized log stack to Phase 2.

Reason:

- before workloads exist, centralized logs add stateful cost and operational surface with limited value;
- `kubectl logs` is sufficient for bootstrap debugging;
- once the bot, Harbor, or Buildkite agents land, log aggregation becomes worthwhile.

This is an intentional scope cut, not a rejection of logs as a concept.

## 8. Buildkite agent deployment

### Can Buildkite agents run on this cluster?

Yes. The recommended path is **Buildkite Agent Stack for Kubernetes** on the same Hetzner k3s cluster.

That fits the merged platform direction:

- Buildkite remains the CI control plane.
- Kubernetes supplies isolated execution as Jobs/Pods.
- Flux can manage the agent-stack installation like any other add-on.

### Agent pool sizing

Do not treat Buildkite agents as a Phase 1 hard dependency. Treat them as a planned Phase 2 consumer of the foundation.

Initial Phase 2 pool recommendation:

- `general` queue: 2 concurrent job pods
- `deploy` queue: 1 serialized job pod

This is enough for one-person operation without letting CI starve platform services. If CI pressure grows, add a fourth worker node before raising concurrency aggressively.

### Execution model

Choose the **Kubernetes executor model**, not Docker-in-Docker.

That means:

- each Buildkite job becomes a Kubernetes Job/Pod;
- image builds should use in-pod BuildKit, Kaniko, or another container-native builder rather than privileged Docker daemons on nodes;
- queue isolation, resource requests, and taints can separate CI work from platform services later if needed.

Docker-in-Docker adds operational and security mess for little gain in a cluster that already gives isolated pods.

### Buildkite control-plane connectivity

Buildkite agents connect outbound over HTTPS to Buildkite’s SaaS control plane using an agent token stored as a sealed secret.

The cluster therefore needs:

- outbound internet access;
- a namespace for Buildkite agents;
- a sealed secret containing the agent token;
- queue definitions and resource limits.

That contract should be designed in Phase 1 even if the actual agents are not deployed until Phase 2.

## 9. Cost model

This estimate is intentionally for the foundation footprint, using the proposed minimum cluster size.

### Hetzner compute

- 3 x `CPX21` control-plane nodes at **EUR 9.99/mo** each = **EUR 29.97/mo**
- 3 x `CPX31` worker nodes at **EUR 17.99/mo** each = **EUR 53.97/mo**

Compute subtotal: **EUR 83.94/mo**

### Hetzner Object Storage

- 1 TB included tier: **EUR 7.72/mo**

Object-storage subtotal: **EUR 7.72/mo**

### Hetzner Load Balancer

- one shared load balancer, when first needed: about **EUR 8.64/mo** at `EUR 0.012/hr`

Because Kong is deferred, this can also be treated as a near-term optional cost rather than an immediate day-one cost.

### Buildkite pricing

From the current research input:

- Buildkite Pro: **USD 30 per active user per month**
- first 10 self-hosted agents included
- extra self-hosted agents only matter after that threshold

For the expected one-person operator footprint, the practical initial Buildkite line item is **USD 30/mo**.

### Monthly total

Foundation steady state, before the first public load balancer:

- **EUR 91.66/mo** plus **USD 30/mo** for Buildkite

Foundation steady state, once one shared public load balancer exists:

- **EUR 100.30/mo** plus **USD 30/mo** for Buildkite

Not included in the subtotal:

- persistent-volume consumption charges
- DNS/domain costs
- later Phase 2 services such as Harbor and PostgreSQL
- later log aggregation if Loki or another log backend is added

## 10. Definition of done

Phase 1 is complete only when the following checks pass in production:

1. **Cluster access**
   `kubectl get nodes` succeeds from an approved operator workstation and shows all control-plane and worker nodes as `Ready`.

2. **OpenTofu reproducibility**
   A no-op `tofu plan` against production returns cleanly after the initial apply, showing that remote state is readable and the environment is declarative.

3. **Flux Git reconciliation**
   A test Kustomization from Git creates or updates a harmless namespaced resource, and Flux reports it as reconciled.

4. **Flux Helm reconciliation**
   A test `HelmRelease` installs or upgrades a simple chart successfully, proving Helm delivery is operational through Flux rather than through manual commands.

5. **Secrets path**
   A `SealedSecret` is committed, reconciled, unsealed into a Kubernetes `Secret`, and consumed successfully by a test pod.

6. **Prometheus health**
   Prometheus shows node-exporter and kube-state-metrics targets as healthy and is scraping node metrics.

7. **Grafana access**
   Grafana loads successfully and displays at least one node or cluster dashboard backed by live Prometheus data.

8. **Alert path**
   Alertmanager receives at least one deliberately triggered low-risk test alert or validated synthetic rule.

9. **Object-storage connectivity**
   A test pod using sealed credentials can reach Hetzner Object Storage, list a bucket, and write/read a small object.

10. **Persistent-volume path**
    A sample stateful workload can bind a PVC through Hetzner CSI and survive a pod restart without data loss.

If any of these fail, Phase 1 is not done, even if the cluster technically exists.

## 11. Risks

- **Self-managed control plane risk**: Hetzner does not provide a managed Kubernetes control plane, so cluster lifecycle and upgrade discipline remain the team’s responsibility. The proposal mitigates this by choosing a small HA layout and pinning versions, but the burden is real.
- **Secrets maturity tradeoff**: `sealed-secrets` is the simplest working answer, not the richest one. If secret count, rotation frequency, or non-Kubernetes secret consumers grow quickly, a later migration to Infisical may be justified.
- **Under-sized workers once Phase 2 lands**: the proposed cluster is a reasonable minimum, but Harbor, PostgreSQL, observability growth, and Buildkite execution can consume worker memory quickly. Scaling by one additional worker should be expected rather than treated as a failure.
- **GitOps split-brain risk**: manual `helm` or `kubectl apply` usage outside Flux will undermine the foundation immediately. Ownership boundaries must be enforced from the first day.
- **Hetzner Object Storage feature limits**: the service is good for state, backups, and moderate artifact workloads, but its S3 surface is narrower than full AWS S3. That is acceptable for Phase 1, but later higher-frequency artifact patterns should be validated explicitly.
- **Public-surface creep**: exposing Grafana, Flux webhooks, or early services publicly before Kong and the auth stack exist would create avoidable risk. The proposal avoids that by default.

## 12. What Phase 2 needs from Phase 1

Phase 2, Bot Production Baseline, should be able to assume all of the following already exist:

- a production Hetzner k3s cluster with HA control plane and stable worker capacity;
- OpenTofu-managed provider and cluster infrastructure with remote state and repeatable plans;
- Flux bootstrapped and reconciling from the GitOps repo;
- a repository structure that already supports `base`, `overlays`, and `clusters/production`;
- `sealed-secrets` installed and proven so the Discord token, database credentials, Harbor credentials, and Buildkite agent token can be delivered safely;
- Hetzner CSI and cloud-controller integration working for PVCs and future load balancers;
- Hetzner Object Storage reachable from workloads and available for later artifacts, backups, and state-adjacent uses;
- Prometheus, Grafana, and Alertmanager running so new Phase 2 services do not launch blind;
- the cluster prepared for Buildkite agent-stack deployment, even if agent pods are not live yet;
- the decision that Kong is deferred unless a public HTTP surface is introduced in Phase 2.

In short, Phase 2 should inherit a boring foundation: cluster, GitOps, secrets, storage, and observability already work. Phase 2 then adds the first real platform consumers of that foundation: PostgreSQL, Harbor, Buildkite execution, release promotion, minimum app observability, and the `server-manager` bot.
