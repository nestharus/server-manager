# Proposal: Initiative — Platform Bootstrap

## 1. Executive summary

Platform Bootstrap establishes the minimum reproducible substrate for
Humility's platform tier on `Vultr VKE`. It is not the full platform
program and it is not the beginning of application deployment. Its job
is narrower: lock the provider and cluster shape, define the base
network and state backing, split infrastructure ownership by
environment, and prove the first clean bootstrap path from git to a
running platform cluster.

This initiative supersedes the substrate direction of the earlier
`phase1-foundation.md`, which targeted Hetzner Cloud with self-managed
k3s via kube-hetzner. The provider comparison research recommends Vultr
as the stronger platform host. Acceptance of this proposal requires
updating `platform-decisions-overlay.md` to lock Vultr as the hosting
decision and marking `phase1-foundation.md` as superseded by the
three-initiative split (Platform Bootstrap, GitOps Foundation,
Application Cluster Provisioning).

The initiative should preserve the two-tier model already normalized by
the planning work: one platform cluster per environment as the control
substrate, with application clusters provisioned separately later. `Git`
remains the desired-state source and `Flux CD` remains the reconciler
direction, but this initiative stops before GitOps bootstrap. The
deliverable is the substrate that later GitOps, platform services, and
application clusters can consume without re-arguing hosting,
networking, or state layout.

The preferred shape is straightforward. `OpenTofu` is the canonical
operator entrypoint. `Vultr VKE` is the Kubernetes substrate. `Vultr`
native VPC/networking primitives define the platform-cluster network
boundary. `Vultr Object Storage` provides the first S3-compatible remote
state and bootstrap artifact backing. The result should be one
documented, repeatable bootstrap path that can create a fresh platform
environment without hidden manual infrastructure steps.

## 2. Scope of Platform Bootstrap

This initiative covers only the platform/control-cluster substrate.

In scope:

- Confirm `Vultr VKE` as the platform-cluster substrate, consistent with
  the existing provider comparison and OpenTofu coverage research.
- Preserve the two-tier platform shape: platform clusters are provisioned
  here; separate application clusters remain a later initiative.
- Define the base network layout for a platform environment using
  provider-native `Vultr` primitives: VPC attachment, public/private
  boundaries, and the minimum firewall/load-balancer-ready posture
  needed for a managed Kubernetes platform.
- Define the provider-native S3-compatible object-storage backing for
  infrastructure state and bootstrap artifacts before any self-hosted
  storage is considered.
- Define per-environment `OpenTofu` roots so each environment owns its
  own cluster, network, and state boundary.
- Define the first reproducible bootstrap path from a clean operator or
  CI environment to a running `VKE` platform cluster with remote state.
- Define the handoff seam to later GitOps work so a subsequent
  initiative can install `Flux` against a known-good cluster and repo
  layout.

This initiative does not broaden into platform services. It exists to
make later initiatives start from a stable substrate instead of an
unfinished infrastructure argument.

## 3. Architecture and component choices

### Platform shape

The platform should keep the structural split inherited from the
base-application reference: a platform cluster is the control substrate,
and application clusters are provisioned separately. Platform Bootstrap
therefore provisions only the platform cluster for each environment. It
does not collapse the control plane and workload plane into one shared
cluster model, and it does not attempt to pre-provision the later
cluster fleet.

The immediate target is one reproducible platform cluster in the first
environment, with the layout designed so the same pattern can be
repeated for additional environments by changing only the environment
root and its variables.

### Provider and cluster path

`Vultr VKE` is the correct substrate for this initiative because it is
the cleanest first-party managed Kubernetes path in the current research
set. That matters here because Platform Bootstrap is specifically about
reducing bootstrap burden. The initiative should not recreate a
self-managed cluster stack on top of raw compute when `VKE` already lets
`OpenTofu` own the cluster lifecycle more directly.

The cluster shape should stay minimal and control-oriented:

- one `VKE` cluster per environment
- managed control plane
- explicitly defined worker pools sized for platform services rather
  than application workloads
- region-local network attachment through `Vultr` VPC primitives
- no attempt to absorb application scheduling policy, fleet management,
  or multi-cluster orchestration

This proposal assumes the platform cluster is the home for later
control-plane services, not the universal home for all runtime
workloads.

### Base networking

The networking deliverable is a platform-cluster boundary, not a full
network program. The baseline shape should be:

- a provider-native private network boundary per environment using
  `Vultr` VPC constructs
- the `VKE` cluster attached to that boundary in-region
- a clear public-entry seam for later ingress and access layers, without
  deploying those layers yet
- firewall rules and exposure rules defined as infrastructure, not as
  ad hoc console state
- DNS and address management only where required to make the bootstrap
  path reproducible

This initiative should stop at the network substrate. It should not
pull in ingress-controller policy, identity-aware access, service mesh,
or cross-environment networking design. Those depend on later
initiatives and would blur the boundary of the bootstrap work.

### Object-storage state backing

Provider-native object storage comes before self-hosted storage. The
correct first step is `Vultr Object Storage` as the S3-compatible backing
for infrastructure state and bootstrap artifacts.

The important decision is not just "use object storage." It is to use it
with explicit separation:

- each environment gets its own state boundary
- state storage is separate from future application object-storage needs
- bootstrap artifacts, if retained, are stored separately from state
- no self-hosted S3 layer is introduced into the bootstrap path

This keeps the bootstrap problem small. The platform does not need
`SeaweedFS`, `MinIO`, or any other in-cluster storage system to create
its own substrate. Managed object storage removes that early dependency
and keeps state external to the cluster being created.

### OpenTofu ownership model

`OpenTofu` should be the canonical operator entrypoint for this
initiative. The practical boundary is:

- `OpenTofu` owns cloud primitives, cluster creation, and remote-state
  configuration
- `OpenTofu` does not become the long-term owner of in-cluster platform
  applications
- later GitOps work owns baseline in-cluster reconciliation

To enforce that boundary, the repository should use per-environment
roots rather than one shared mutable root. The proposal direction is:

- a shared module layer for reusable `Vultr` components
- one `OpenTofu` root per platform environment
- each root pointing at environment-specific remote state in
  provider-native object storage
- environment variables or tfvars carrying only environment-specific
  inputs such as region, cluster name, node-pool sizing, and state
  naming

The important architectural result is isolation. A plan or apply for
one environment should not implicitly own another environment's cluster
or state.

### Bootstrap handoff to GitOps

`Git` as desired state and `Flux CD` as reconciler are locked decisions,
but they are not the implementation target of this initiative. Platform
Bootstrap should end at the handoff seam:

- the environment root can create the network, storage backing, and
  `VKE` cluster reproducibly
- the resulting cluster is reachable via a published kubeconfig or
  connection-secret reference stored in a defined, access-controlled
  location outside the cluster itself
- the handoff contract specifies: the API server endpoint, the
  kubeconfig or connection-secret storage path, who may retrieve it,
  whether the credential is encrypted at rest, and whether a short-lived
  or long-lived credential model is used
- the repository layout is stable enough for a later `Flux` bootstrap
  initiative to attach cleanly

That is the right stopping point. Installing `Flux`, defining
cluster-reconciliation repositories, or introducing Crossplane-based
cluster-fleet logic would pull this proposal past substrate and into the
next initiative. Crossplane installation is explicitly outside this
initiative's boundary; Application Cluster Provisioning owns the
Crossplane core install as its own day-zero prerequisite.

## 4. What this initiative delivers

At completion, Platform Bootstrap should deliver:

- a locked substrate choice of `Vultr VKE` for the platform cluster
- a documented platform-cluster shape that preserves the separate
  application-cluster model
- a base `Vultr` network pattern for a platform environment, including
  private boundary, cluster attachment, and infrastructure-defined
  exposure rules
- provider-native `Vultr Object Storage` selected and structured as the
  remote backing for infrastructure state and bootstrap artifacts
- per-environment `OpenTofu` roots for platform environments, with clear
  ownership and isolation boundaries
- a first reproducible bootstrap path that can create a fresh platform
  environment from a clean starting point
- an explicit handoff seam to later GitOps work, with no ambiguity about
  where substrate ownership ends and reconciliation ownership begins

In practical terms, this initiative delivers the first platform
environment substrate, not the first fully configured platform.

## 5. What is explicitly out of scope

The following are explicitly out of scope for Platform Bootstrap:

- installing or configuring `Flux CD`
- GitOps repository design beyond the minimum handoff seam needed for
  later work
- Crossplane or any cluster-fleet management logic (owned by
  Application Cluster Provisioning as its day-zero prerequisite)
- CI/CD pipeline design or `Buildkite` execution flow
- identity, access proxy, or authorization systems such as
  `Authentik`, `Pomerium`, `OPAL`, or `Cedar`
- application deployment for the API, Discord daemon, or web app
- database provisioning and data-service topology
- observability stack rollout
- ingress-controller, service-mesh, or edge-policy implementation
- self-hosted object storage such as `SeaweedFS`, `MinIO`, or `Ceph`
- redesigning the broader platform roadmap or absorbing later
  initiatives into this proposal

## 6. Risks and open questions

### Risks

- The main failure mode is scope creep. If this initiative starts
  installing GitOps, identity, CI, or application services, it stops
  being a bootstrap substrate and becomes an unbounded foundation phase.
- `VKE` is the right managed-cluster direction, but the current research
  notes some ambiguity around `VKE` and `VPC` terminology. That must be
  verified on a throwaway cluster before committing the per-environment
  network topology — this is a gating pre-implementation task, not
  general diligence.
- S3-compatible state backing is the right first move. State locking,
  object versioning, and restore procedures are first-class exit
  criteria, not assumed defaults. Concurrent applies without working
  lock acquisition can corrupt state; a corrupted foundation-layer state
  file is effectively unrecoverable without manual import.
- Provider credential custody is a bootstrap-phase concern because no
  secrets platform exists yet. The Vultr API token must have a defined
  storage location, access-control boundary, backup procedure, and
  per-environment scoping before the first bootstrap run.
- If per-environment roots are not enforced cleanly, the project will
  drift into shared-state infrastructure where one plan can affect the
  wrong environment.
- If bootstrap requires undocumented provider-console steps, the
  initiative fails its reproducibility goal even if the first cluster
  comes up once.

### Open questions

- Which environment should be the first validated bootstrap target:
  a non-production platform environment first, or production directly?
- What is the exact region and node-pool baseline for the first
  platform-cluster environment?
- Should environment state live in separate object-storage instances,
  separate buckets, or a stricter prefix-plus-policy split within the
  same provider account?
- Which DNS records, if any, must be owned by the bootstrap layer rather
  than by later ingress or GitOps work?
- Does the first bootstrap path need a minimal reserved public endpoint
  for later platform services, or is cluster reachability plus network
  attachment sufficient for this initiative?

## 7. Exit criteria

Platform Bootstrap is complete when all of the following are true:

- the platform-cluster substrate is explicitly defined around
  `Vultr VKE`, not left as a provider-open design
- `platform-decisions-overlay.md` is updated to lock Vultr as the
  hosting decision, citing the provider comparison research as the
  ratification basis, and `phase1-foundation.md` is marked as superseded
  by the three-initiative split
- the two-tier model is preserved: platform cluster here, separate
  application clusters later
- each declared platform environment has its own `OpenTofu` root and
  isolated remote-state boundary
- the remote-state backend provides working lock acquisition,
  demonstrated by an intentional concurrent-plan test
- object versioning is enabled on the state bucket
- a documented state-restore procedure exists and has been exercised at
  least once
- a minimum credential-custody procedure is defined as a deliverable:
  where the Vultr API token lives outside Git, who can access it, how it
  is backed up, and whether per-environment tokens are enforced
- provider-native S3-compatible object storage is defined as the backing
  for infrastructure state before any self-hosted storage path
- VKE/VPC attachment behavior is verified on a throwaway cluster before
  the per-environment network topology is committed to the repository
- a clean bootstrap run can create the base network, remote-state
  backing, and first `VKE` platform cluster for the initial environment
  without hidden manual infrastructure steps
- the resulting cluster is reachable via a published handoff contract
  that specifies: API server endpoint, kubeconfig or connection-secret
  storage path, retrieval access control, encryption-at-rest posture,
  and credential lifetime model
- the handoff boundary is explicit: this initiative ends with substrate
  readiness, while `Flux`, cluster-fleet logic, CI/CD, identity, and
  application rollout remain separate work
