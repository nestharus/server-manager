# Proposal: Initiative — Application Cluster Provisioning

## 1. Executive summary

Application Cluster Provisioning defines the cluster-fleet layer that
turns a platform/control cluster into a provisioning control plane for
downstream application clusters. The initiative keeps the two-tier model
intact: the control cluster is provisioned separately, remains outside
Crossplane claims, and then provisions distinct application clusters for
named environments through `Crossplane` `XRD`s, compositions, and
environment claims.

`Crossplane` is selected as the cluster-fleet control plane because the
platform requires a Kubernetes-native, declarative mechanism for
provisioning and managing downstream clusters from within the control
cluster. The alternative — driving application cluster lifecycle through
`OpenTofu` — would either collapse the two-tier model (one OpenTofu root
managing both tiers) or require an external orchestration layer to
bridge OpenTofu applies into the control cluster's desired-state model.
Crossplane keeps cluster provisioning inside Kubernetes, composable with
Flux-reconciled Git state, and aligned with the per-cluster GitOps root
model. This choice should be recorded in `platform-decisions-overlay.md`
as a locked decision alongside Flux, Buildkite, and the auth stack.

This initiative is deliberately narrower than the older
`base-application` pattern. It keeps the useful seam, namely
"pre-existing control plane provisions child clusters," and drops the
parts that created control-plane overlap: bucket-watched Flux,
event-driven claim buses, self-provisioning the platform cluster, and
claims that try to own both infrastructure and application rollout. The
goal here is simple and explicit: an operator or GitOps system creates a
cluster claim in the control cluster, Crossplane provisions the
downstream cluster and its required cloud primitives, and the system
publishes a standard readiness and connection contract for the next
initiative to consume.

The result is not a general platform abstraction layer. It is a bounded
fleet-provisioning subsystem with clear handoff points to Platform
Bootstrap on the upstream side and GitOps Foundation on the downstream
side.

## 2. Scope of Application Cluster Provisioning

This initiative covers only the machinery required for the control
cluster to provision separate application clusters.

In scope:

- Install `Crossplane` core (controller and CRDs), the required provider
  package, and baseline `ProviderConfig` on the control cluster as a
  day-zero prerequisite. This initiative owns the Crossplane installation
  because Platform Bootstrap is scoped to substrate only and explicitly
  excludes cluster-fleet management logic.
- Define the `Crossplane` API surface for downstream cluster requests:
  one composite resource plus one namespaced claim type for application
  environments.
- Define the supported claim parameters for cluster provisioning:
  environment identity, cluster class, region/provider selection hooks,
  Kubernetes version channel, and bounded worker-pool inputs.
- Implement provider-backed compositions that create the downstream
  cluster and only the supporting cloud resources required for that
  cluster to exist, such as network attachments, node pools, and
  kubeconfig publication.
- Standardize the readiness contract exported by successful claims:
  cluster identifier, API endpoint, connection secret reference,
  provider metadata, and condition semantics that operators can trust.
- Define the lifecycle contract for update, drift, and deletion of
  provisioned application clusters, including explicit deletion-policy
  behavior with a default posture that protects production-class claims.
- Define the operational boundary for provider credentials, connection
  secrets, and the namespaces in which claims and published secrets may
  live, including RBAC controls on claim authoring and connection-secret
  access.
- Produce the runbook-level control-plane model: who creates a claim,
  what Crossplane owns, what status indicates readiness, and where the
  next phase picks up.

This initiative starts only after the platform/control cluster exists
and has a working baseline Kubernetes control plane. It ends when a
downstream application cluster can be requested and provisioned from
that control cluster with a documented handoff contract.

## 3. Architecture and control-plane choices

### Control-plane boundary

The control cluster is upstream of this initiative — it is not created by
the same `Crossplane` claims that it hosts. Platform Bootstrap owns the
existence of the control cluster and the bootstrap credential path
required to reach it. This initiative owns the Crossplane installation
baseline: core controller, CRDs, provider package, and `ProviderConfig`
bootstrap on the control cluster. This split keeps Platform Bootstrap
scoped to substrate only while giving this initiative full ownership of
the tooling it depends on.

Application Cluster Provisioning begins at the point where a stable
control cluster already exists and installs Crossplane as its own
day-zero step before defining `XRD`s and compositions.

This removes the circular pattern found in the legacy corpus, where the
platform cluster was both the provisioning host and a provisioned claim.
The platform cluster is the operator substrate. Application clusters are
the only resources this initiative provisions.

### Tool boundary: Crossplane and OpenTofu

`OpenTofu` and `Crossplane` operate at different tiers with a hard
boundary between them. `OpenTofu` owns cloud primitives at the platform
substrate level: VPC networking, object storage, VKE cluster creation,
and per-environment state isolation. `Crossplane` owns downstream
application-cluster lifecycle from within the control cluster:
cluster provisioning, node-pool attachment, and connection-secret
publication for child clusters only.

Crossplane compositions must not reproduce cloud primitives that
`OpenTofu` already manages in the platform tier (VPCs, shared
networking, state storage). If a cloud resource is owned by a Platform
Bootstrap OpenTofu root, Crossplane references it by ID or imports it
as a data source — it does not recreate it. This boundary prevents
split-ownership of the same infrastructure resource across two control
planes.

### Resource model

The provisioning API should stay intentionally small:

- One composite type representing a provisioned application cluster.
- One namespaced claim type used by operators or a later GitOps layer to
  request that cluster.

The claim should model only infrastructure-level inputs that the
composition can truly honor. It should not expose a large pseudo-DSL for
future node-pool types, service bundles, or application concerns. The
legacy `base-application` pattern is a warning here: broad
environment-type schemas become misleading when the composition does not
actually enforce them.

The recommended contract is:

- `environmentName`: stable environment identifier such as `dev`,
  `staging`, or `production`
- `clusterClass`: a bounded provisioning profile chosen from a small
  supported set
- `providerRef` or equivalent composition-selection hook tied to the
  provider locked by the foundation initiative
- `kubernetesChannel`: bounded version or upgrade channel input
- `nodePools`: a small, explicitly supported structure for worker pools,
  only if the underlying composition really patches it through
- `deletionPolicy`: explicit lifecycle choice for claim removal

Everything else stays out until a later initiative proves it belongs in
the infrastructure contract.

### Composition strategy

Compositions are provider-specific implementations behind a stable claim
surface. The initiative should not pretend that one abstract schema
magically normalizes every provider. Instead:

- the `XRD` stays narrow and provider-aware
- the selected composition is allowed to reflect the locked hosting
  substrate
- unsupported provider features are not modeled as fake generic fields

This keeps operator expectations honest. If the platform locks `Vultr`,
the first composition targets `Vultr`. If it locks `Hetzner`, the first
composition targets `Hetzner`. Multi-provider portability is not a goal
for the first accepted version of this subsystem.

### Claim submission seam

The claim itself is a Kubernetes resource in the control cluster. This
initiative defines that resource and how Crossplane reconciles it. It
does not decide whether the claim arrives through `Flux`, manual
operator application, or a later API workflow. That submission path is a
separate ownership concern. Manual `kubectl apply` of claims is
acceptable only as a bootstrap-only seam; the first accepted
implementation must land in coordination with GitOps Foundation so that
the GitOps submission path replaces the operator-only path promptly.

This is the key seam with GitOps Foundation:

- GitOps Foundation owns where cluster claims live in git (under the
  control-cluster root), how they are reconciled into the control
  cluster, and how per-cluster Flux roots are bootstrapped onto newly
  provisioned downstream clusters.
- Application Cluster Provisioning owns what the claim means once it
  exists in the control cluster and what infrastructure outputs it
  publishes.

### Handoff contract to downstream cluster bootstrap

Successful reconciliation must publish a standard connection contract,
not an implicit operator ritual. At minimum, each ready cluster claim
must expose:

- a stable cluster ID
- provider-specific external identifier
- API server endpoint
- a referenced kubeconfig or equivalent connection secret
- readiness conditions with failure reasons that are actionable
- enough metadata for the next phase to bind a per-cluster GitOps root

This initiative stops there. It does not install `Flux` into the child
cluster, choose the child cluster's repo path, or deploy platform
services onto it. It hands off a real cluster plus a real connection
contract.

### Lifecycle and operator clarity

Operator clarity matters more than maximal automation. The initial model
should therefore prefer:

- persistent named environment clusters over dynamic preview fleets
- explicit claim creation and deletion over hidden event pipelines
- clear deletion policy over automatic TTL cleanup
- direct Crossplane status conditions over auxiliary controller glue

That keeps failure ownership visible. When a cluster is stuck, the
operator should be able to inspect one claim, one composite resource,
and the provider-managed children, rather than reconstructing state
across Git, buckets, Kafka topics, and custom deployer services.

## 4. What this initiative delivers

This initiative delivers a standalone provisioning subsystem for
application clusters with the following outputs:

- an accepted `Crossplane` `XRD` and namespaced claim contract for
  requesting application clusters from the control cluster
- one or more provider-specific compositions that provision downstream
  clusters and the minimal prerequisite cloud resources they need
- a documented namespace, secret, and credential model for claims and
  published cluster connection data
- a standard readiness and failure-status contract that operators and
  later automation can consume
- a documented handoff contract from "cluster requested" to "cluster is
  ready for child-cluster GitOps bootstrap"
- tested lifecycle semantics for create, update, and delete within the
  defined claim surface
- operator runbooks that explain the provisioning path, failure
  inspection points, and deletion behavior

## 5. What is explicitly out of scope

The following are not part of Application Cluster Provisioning:

- provisioning the platform/control cluster itself
- deciding or implementing the authoritative GitOps topology for claims,
  per-cluster roots, or application manifests
- installing `Flux` or other workload controllers into downstream
  clusters after they are created
- deploying applications, Helm releases, namespaces, ingress, secrets,
  databases, or other runtime services onto child clusters
- turning `Crossplane` into a general replacement for `OpenTofu`,
  `Flux`, or application packaging
- CI/CD orchestration, release promotion, or image automation
- runtime data services such as `Postgres`, `Kafka`, `Debezium`,
  `Redis`, or object-storage-backed claim buses
- dynamic preview-environment APIs, TTL cleanup workflows, or custom
  platform deployer services
- broad product-surface concerns such as tenant models, application
  authorization, or end-user environment management UI
- collapsing this initiative back into Platform Bootstrap or GitOps
  Foundation just because the interfaces touch

## 6. Risks and open questions

### Risks

- `Crossplane` can easily create split ownership if the claim surface is
  allowed to overlap with platform bootstrap, GitOps topology, or
  application deployment. The seam must stay hard. Crossplane
  compositions must not reproduce cloud primitives that OpenTofu already
  manages in the platform tier.
- Provider support may force a narrower first composition than the
  schema initially suggests. The proposal should follow provider reality,
  not idealized portability. The first accepted composition cannot land
  until the hosting decision is locked in `platform-decisions-overlay.md`.
- Connection-secret handling is a security boundary. Published
  kubeconfigs must live in a dedicated, RBAC-restricted namespace with a
  default-deny posture and explicit allow-lists. A documented
  rotation/revocation path must exist even if initially manual.
- Deletion semantics are dangerous when child clusters later host real
  workloads. Production-class claims must default to a protective
  `deletionPolicy` (such as `Orphan` with explicit operator unlock)
  from the first version.
- Claim-authoring RBAC is part of this initiative's operational contract.
  Only a named group may create or delete production-class claims;
  dev-class claims may have a wider authoring group. This does not
  depend on the locked auth stack — it is native Kubernetes RBAC on the
  control cluster.
- Oversized claim schemas are a recurring trap. If the claim carries
  inputs that the composition does not truly honor, operators will make
  decisions against a false contract.

### Open questions

- Which provider and managed-cluster path will the first accepted
  composition target once the hosting decision is locked? The first
  composition is gated on this decision. Implementation complexity
  differs significantly between the Vultr path (managed VKE, first-party
  cluster API) and the Hetzner path (self-managed k3s, no managed-cluster
  API — composition would need a provider-terraform wrapper).
- What is the minimum supported set of `clusterClass` values for the
  first release: only persistent `dev/staging/production`, or a slightly
  broader set?
- Should the first version support any node-pool overrides beyond a
  small class-based default, or should worker topology be fully class
  driven to keep the contract honest?

## 7. Exit criteria

This initiative is complete when all of the following are true:

- `Crossplane` core (controller, CRDs), the required provider package,
  and baseline `ProviderConfig` are installed on the control cluster as
  this initiative's day-zero deliverable
- Crossplane is recorded as a locked decision in
  `platform-decisions-overlay.md` alongside the justification against
  OpenTofu-driven app-cluster provisioning
- the control cluster can host the accepted `Crossplane` API surface for
  application cluster provisioning without also trying to provision
  itself
- a documented namespaced claim type exists for requesting application
  clusters, and its supported fields are no broader than the underlying
  composition behavior
- for every field in the claim schema, at least one test demonstrates
  that changing the field produces the corresponding change in the
  provisioned resource
- at least one provider-specific composition exists for the locked
  hosting substrate and can provision a downstream application cluster
  from a clean claim
- successful claims publish a standardized readiness and connection
  contract, including endpoint and connection-secret reference
- published connection secrets live in a dedicated, RBAC-restricted
  namespace with a default-deny posture and explicit allow-lists
- a documented rotation/revocation path exists for connection-secret
  credentials, even if initially manual
- production-class claims default to a protective `deletionPolicy`
  (such as `Orphan` with explicit operator unlock) that prevents
  destructive reconciliation without a deliberate policy change
- a minimum RBAC posture for claim CRUD is defined: only a named
  group may create or delete production-class claims; dev-class claims
  may have a wider authoring group
- failed claims surface actionable conditions and failure reasons
  without requiring a separate custom controller to interpret them
- create, update, and delete behavior are documented and verified for
  the supported claim surface
- the handoff from provisioned cluster to child-cluster GitOps bootstrap
  is documented as an explicit interface, without this initiative owning
  that bootstrap itself
- operator runbooks exist for claim submission expectations, status
  inspection, failure triage, and deletion behavior
