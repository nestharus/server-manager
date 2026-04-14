# Phase 1 Proposal — Foundation Bootstrap

## 1. Executive summary

Phase 1 establishes the minimum infrastructure required to run the
platform on `Hetzner Cloud` with self-managed Kubernetes. The phase is
not about shipping Humility application features. It is about creating
the substrate that later phases can trust: reproducible infrastructure,
a working `k3s` cluster via `kube-hetzner`, a single GitOps path via
`Flux CD`, a minimal secrets workflow, a baseline ingress path via
`Kong`, and provider-native object storage wired into the cluster.

The locked decisions already define the shape of that substrate.
`Hetzner` is the host, `k3s` via `kube-hetzner` is the cluster path,
`OpenTofu` is the IaC entrypoint, `Flux CD` is the reconciler,
`Buildkite` is CI rather than a deployment engine, `Kong` is ingress,
and `Hetzner Object Storage` is the default S3-compatible object layer.
`SeaweedFS` remains only a fallback. `Smallstep` remains conditional and
is not part of the minimum bootstrap.

The proposal therefore keeps Phase 1 narrow. It should deliver one
production-capable platform foundation in a single Hetzner region with
clear rebuild semantics and without prematurely introducing later-phase
identity, authorization, database, or eventing systems.

## 2. Scope of Phase 1

Phase 1 covers only the foundation bootstrap needed to host later
services safely and repeatedly.

In scope:

- Provision the minimum `Hetzner Cloud` infrastructure needed by
  `kube-hetzner` and the ingress path: private networking, cluster
  nodes, load-balancing, and supporting cloud primitives required for a
  production-capable `k3s` cluster.
- Use `OpenTofu` as the canonical operator entrypoint for the Hetzner
  substrate and the cluster bootstrap seam.
- Bootstrap `k3s` through `kube-hetzner` rather than assembling a
  custom cluster stack from raw VMs and scripts.
- Install `Flux CD` and make it the only reconciler for in-cluster
  baseline state.
- Establish a secrets path that is compatible with GitOps and safe for
  bootstrap. The default recommendation for this phase is `SOPS` with
  `age`, reconciled by `Flux`.
- Install `Kong` as the north-south ingress layer and validate traffic
  from public entry to in-cluster services.
- Provision `Hetzner Object Storage` and wire bucket credentials into
  cluster workloads through the chosen secrets path.
- Define the boundary between `Buildkite` and `Flux` so CI prepares and
  validates changes while cluster mutation remains Git-driven and
  reconciler-driven.

Phase 1 explicitly does not attempt to complete the broader platform.
It is the bootstrap layer only.

## 3. Architecture and component choices

### Platform shape

The target shape for Phase 1 is a single-region Hetzner platform with a
self-managed `k3s` cluster created by `kube-hetzner`. This is the
minimum shape that respects the locked decisions without inventing a new
platform abstraction layer. It accepts the tradeoff that the team owns
cluster lifecycle, upgrades, and recovery from day 1, in exchange for a
lower-cost Kubernetes substrate and a straightforward OpenTofu-driven
bootstrap path.

This phase should optimize for reproducibility and operational clarity,
not for maximum platform breadth. One well-understood cluster with a
clean GitOps path is more valuable than an ambitious foundation that
also tries to solve identity, authorization, CI execution, database
hosting, and policy orchestration in the first pass.

### Infrastructure control plane

`OpenTofu` is the canonical infrastructure control surface. For
Hetzner, that does not mean OpenTofu will own every concern through the
first-party `hcloud` provider alone. The research shows a practical
boundary: `OpenTofu` cleanly owns the cloud substrate and the
`kube-hetzner` bootstrap seam, but Hetzner object storage automation may
cross a provider boundary because S3-style object storage is not covered
by the core `hcloud` resource set.

That is acceptable in Phase 1. The goal is not a perfect single-provider
graph; the goal is a reproducible bootstrap with explicit seams. The
proposal should therefore treat OpenTofu as the single operator
entrypoint while documenting that some Hetzner object-storage handling
may rely on a secondary provider path until the implementation details
are finalized.

### Kubernetes substrate

`k3s` via `kube-hetzner` is the required Kubernetes path. The research
supports treating `kube-hetzner` as the correct production bootstrap
module for self-managed Hetzner Kubernetes rather than writing a custom
cluster layer. It already encodes much of the operational baseline that
would otherwise be reimplemented poorly: cluster topology, Hetzner cloud
integration, storage integration, and recovery-oriented defaults.

Phase 1 should use that opinionated path and avoid parallel bootstrap
systems. The cluster should be sized for the foundation layer only:
control plane, ingress, GitOps, and a small set of baseline services.
It should not become the dumping ground for every locked platform
component during bootstrap.

### GitOps and delivery model

`Flux CD` is the only in-cluster deployment reconciler. This is a hard
architectural boundary, not just a tooling preference. The Buildkite
research is clear that `Buildkite` should own CI control-plane duties,
while `Flux` owns deployment reconciliation. Phase 1 should therefore
adopt the following operating model:

- `Buildkite` validates changes, builds artifacts, and prepares release
  inputs when later phases require that.
- Git is the source of truth for cluster state.
- `Flux CD` is the only system that reconciles that cluster state.

This prevents the most common bootstrap failure in this type of stack:
two competing mutation paths, one from CI and one from GitOps.

### Secrets management

Phase 1 needs a secrets system that is small, auditable, GitOps-native,
and deployable before the rest of the platform exists. The most
pragmatic choice is `SOPS` with `age` keys and `Flux` decryption support.

That choice is intentionally narrow. It does not try to solve the final
secret-management story for the whole platform. It solves the bootstrap
problem cleanly:

- secrets stay encrypted in git
- `Flux` can reconcile them into Kubernetes objects
- bootstrap does not depend on an additional always-on secrets service
- later phases can replace or augment the approach if operational needs
  justify it

Phase 1 should use this path for the secrets that the foundation layer
actually needs: object-storage credentials, bootstrap tokens,
ingress-related credentials, and any baseline service credentials
required before a fuller secret platform is warranted.

### Ingress and edge access

`Kong` is the ingress layer for Phase 1. Its role in this phase is
strictly north-south traffic management into the cluster. It should not
be overloaded with identity, authorization, or operator-access
responsibilities that belong to later layers.

`Pomerium` remains the locked access proxy, but the Pomerium research
argues for keeping it narrow: human and operator access to internal
apps, admin surfaces, `kubectl`, or SSH-style flows. None of that is
required to prove the minimum bootstrap. Phase 1 should therefore stop
at `Kong` unless a concrete operator-access requirement forces an early
Pomerium introduction in the next phase.

### Object storage

`Hetzner Object Storage` is the primary object-storage choice for Phase
1, consistent with the locked provider-native S3 direction and the
research conclusion that self-hosted S3 should be deferred unless the
provider offering proves insufficient. The bootstrap requirement here is
not broad storage architecture. It is simply that the platform has an
S3-compatible bucket target available for platform use cases such as:

- backups and exports
- artifact or blob storage needed by later services
- any baseline workload that expects S3-compatible object storage

`SeaweedFS` is explicitly out of scope in this phase. It remains the
fallback only if Hetzner Object Storage later fails on capability,
operational fit, or economics.

### Deferred platform layers

Several locked decisions remain important, but they are not foundation
bootstrap work:

- `Authentik` is the identity provider
- `OPAL/Cedar` is the authorization direction
- `Pomerium` is the access proxy
- `Postgres` is still open between self-managed in-cluster and external
- `Smallstep` is conditional only if broader PKI or workload identity is
  actually required

Phase 1 should preserve room for these systems without deploying them.
The foundation only needs to make later adoption straightforward. It
does not need to solve those concerns now.

## 4. What Phase 1 delivers

At the end of Phase 1, the project should have a minimum usable platform
foundation with these outcomes:

- a reproducible `Hetzner` infrastructure baseline created from
  `OpenTofu`
- a running `k3s` cluster bootstrapped through `kube-hetzner`
- `Flux CD` installed and reconciling baseline cluster state from git
- a working encrypted-secrets workflow suitable for GitOps bootstrap
- `Kong` installed as the baseline ingress entrypoint
- `Hetzner Object Storage` provisioned and reachable through
  S3-compatible credentials managed through the secrets workflow
- a documented CI/CD boundary where `Buildkite` does not mutate the
  cluster directly and `Flux` is the sole reconciler
- a clear rebuild story for the foundation layer without undocumented
  manual steps

In practical terms, this phase delivers the first platform environment
that later application, identity, and policy services can be deployed
onto without first re-arguing the infrastructure base.

## 5. What is explicitly out of scope

The following are not Phase 1 deliverables:

- deployment of the API service, Discord daemon, or web application
- production rollout of `Authentik`
- production rollout of `OPAL/Cedar`
- production rollout of `Pomerium`
- final implementation of `Postgres`, whether in-cluster or external
- `Buildkite` agent deployment as a required part of the bootstrap
- eventing or integration infrastructure such as `Kafka`, `Debezium`, or
  `Redis`
- self-hosted object storage such as `SeaweedFS`
- `Smallstep` deployment without a separately accepted PKI scope
- multi-region, multi-provider, or disaster-recovery expansion beyond
  the minimum rebuild story
- broad observability, policy, or internal platform-service expansion
  beyond what the bootstrap strictly needs

## 6. Risks and open questions

### Risks

- `Hetzner` plus `k3s` via `kube-hetzner` is a self-managed Kubernetes
  choice. Control-plane lifecycle, upgrades, and recovery are team-owned
  from the first day.
- The `kube-hetzner` path includes a bootstrap seam outside plain cloud
  CRUD. If that seam is not treated as part of the official bootstrap,
  the platform will drift into undocumented setup.
- `Hetzner Object Storage` is the right minimum-path object layer, but
  it is not the same thing as a complete DR plan. Offsite copy strategy,
  retention, and restore drills remain later work.
- Secrets bootstrap is a high-leverage failure point. If key custody,
  encryption workflow, or decryption permissions are weak in Phase 1,
  later phases inherit insecure defaults.
- The biggest architectural failure mode is scope creep: trying to host
  identity, authorization, CI execution, access proxying, and stateful
  services inside the bootstrap before the cluster foundation is stable.

### Open questions

- `Postgres`: should the first production database land inside the
  cluster or outside it? This remains open because it affects backup
  design, failure domains, and operational burden in later phases.
- Hetzner object-storage automation: should bucket provisioning be
  handled through a secondary S3-compatible provider path from day 1, or
  is a narrower bootstrap acceptable until that automation seam is
  finalized?
- `Buildkite` placement: should the first self-hosted agents run inside
  the cluster, on dedicated Hetzner machines, or only after the first
  application deployment phase?
- Secrets evolution: is `SOPS + age` sufficient beyond bootstrap, or
  should a later phase introduce an external secrets manager once the
  platform baseline is stable?
- Access timing: does the next phase require `Pomerium` earlier for
  operator-facing surfaces, or can the bootstrap remain limited to
  `Kong` plus direct operator access?
- PKI timing: is there any concrete near-term need for workload
  certificates or mTLS that would justify pulling `Smallstep` forward,
  or can it remain deferred cleanly?

## 7. Exit criteria

Phase 1 is complete when all of the following are true:

- `OpenTofu` can create the Hetzner substrate and the `kube-hetzner`
  bootstrap from a clean environment.
- the `k3s` cluster is up, reachable, and stable enough to host baseline
  platform components
- `Flux CD` is installed and successfully reconciling the baseline
  cluster state from git
- the secrets workflow is operational: encrypted secrets can live in git
  and be reconciled into usable in-cluster secrets without repository
  plaintext
- `Kong` is installed and serving as the baseline ingress layer through
  the Hetzner networking and load-balancer path
- `Hetzner Object Storage` is provisioned, reachable through its
  S3-compatible interface, and consumable by workloads through the
  chosen secrets workflow
- the CI/GitOps boundary is explicit and enforced: `Buildkite` is not
  performing out-of-band cluster mutation, and `Flux` is the sole
  reconciler of cluster state
- the foundation can be rebuilt without relying on undocumented manual
  changes
