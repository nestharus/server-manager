# Proposal: Initiative — GitOps Foundation

## 1. Executive summary

The `GitOps Foundation` initiative defines the cluster-state topology
for the platform. Its job is not to ship application features or to
implement Flux manifests. Its job is to make the deployment model
unambiguous: Git is the desired-state system, `Flux CD` is the only
reconciler, and every environment and cluster has a clear root in the
repository.

The proposal adopts a path-based multi-environment layout:
`base -> overlays -> clusters/<env>`. The reusable platform defaults
live in `base/`. Environment and cluster-role composition lives in
`overlays/`. Each physical cluster gets a thin root under
`clusters/<env>/...`, and that root is the only path its local Flux
instance reconciles.

This proposal also preserves the locked two-tier model from
`base-application`: each environment is split into a `control-cluster`
and an `app-cluster`. The control cluster hosts platform control-plane
services. The app cluster hosts runtime workloads. Both clusters remain
Git-driven and self-reconciling through their own Flux roots. `Buildkite`
stays on the CI side of the boundary: it validates, renders, tests, and
publishes artifacts, but it does not mutate clusters.

## 2. Scope of GitOps Foundation

This initiative defines the GitOps topology and ownership boundaries for
cluster state.

In scope:

- define the canonical repository layering:
  `base -> overlays -> clusters/<env>`
- define environment separation for `dev`, `staging`, and `production`
- define the two-tier per-environment cluster model:
  `control-cluster` and `app-cluster`
- define the per-cluster Flux root model so each cluster reconciles only
  its own path
- define the Git/Flux/CI boundary, including what `Buildkite` may and
  may not do
- define the promotion model between environments at the Git level
- define the interfaces that later initiatives must target when adding
  secrets, ingress, platform services, or application workloads

This initiative does not decide application architecture, business
features, or cluster bootstrap implementation details. It establishes
the deployment topology those later concerns must plug into.

## 3. Topology and component choices

### Repository shape

The desired-state repository should follow this structure:

```text
base/
  platform/
  controllers/
  namespaces/
  policies/

overlays/
  dev/
    control-cluster/
    app-cluster/
  staging/
    control-cluster/
    app-cluster/
  production/
    control-cluster/
    app-cluster/

clusters/
  dev/
    control-cluster/
    app-cluster/
  staging/
    control-cluster/
    app-cluster/
  production/
    control-cluster/
    app-cluster/
```

The layers have different responsibilities:

- `base/` contains reusable, environment-neutral building blocks. These
  are the shared definitions that should not know whether they are being
  used in `dev`, `staging`, or `production`.
- `overlays/` compose those bases for a specific environment and cluster
  role. This is where environment-specific wiring, scale, feature
  enablement, and role-specific composition live.
- `clusters/<env>/...` contains the thin cluster root for a real
  cluster. It should mostly select the right overlay set, establish
  ordering, and host Flux root objects for that cluster.

This keeps the layering honest. Shared intent belongs in `base/`.
Environment and role variation belongs in `overlays/`. Real-cluster
entrypoints belong in `clusters/`.

### Per-cluster Flux roots

Each physical cluster gets its own local Flux installation and its own
root path under `clusters/<env>/<cluster-name>`.

That means:

- the `dev` control cluster reconciles only `clusters/dev/control-cluster`
- the `dev` app cluster reconciles only `clusters/dev/app-cluster`
- the `staging` clusters reconcile only their `staging` roots
- the `production` clusters reconcile only their `production` roots

No cluster should reconcile a parent directory such as `clusters/`,
`clusters/dev/`, or the whole repository. That would blur environment
boundaries and create accidental cross-cluster blast radius. The root
path must always map to one cluster.

This initiative also keeps the reconciler model local. The
`control-cluster` is not a second deployment engine for remote clusters.
It is just another cluster with its own Flux root. Cross-cluster
platform dependencies may exist later, but reconciliation still happens
inside each target cluster through that cluster's own Flux controllers.

### Environment separation

Environment separation is path-based, not branch-based.

`dev`, `staging`, and `production` should exist as distinct directories
under both `overlays/` and `clusters/`. Promotion happens by changing
Git in the target environment path, then letting Flux reconcile the
merged result.

That gives the platform these properties:

- `dev` can move quickly without implicitly changing `staging` or
  `production`
- `staging` can mirror production shape while remaining independently
  promotable
- `production` remains isolated behind its own Git history, approvals,
  and Flux roots

The important boundary is that environment promotion is still a Git
change. It is not a CI job calling `kubectl`, `helm upgrade`, or
`flux reconcile` against a live cluster.

### Control cluster vs app cluster

The two-tier model remains intact in every environment:

- `control-cluster` holds platform control-plane components, shared
  operational services, and the platform surfaces that manage or support
  workloads
- `app-cluster` holds the application runtime workloads and their
  environment-specific dependencies

This split matters even before the exact workload list is finalized. It
creates the right failure and lifecycle boundary now:

- platform control-plane changes do not have to share the same root path
  or cadence as application runtime changes
- application rollouts do not require the control cluster to become a
  central mutator
- later initiatives can place components cleanly without re-arguing the
  cluster boundary

### Git as desired state, Flux as sole reconciler

This proposal makes the operating boundary explicit.

Git owns:

- the cluster topology
- the selected bases and overlays for each cluster
- image references, chart references, and declarative release inputs
- ordering and dependency declarations inside a cluster root

`Flux CD` owns:

- observing the desired-state repository
- reconciling that desired state into the target cluster
- drift correction for objects declared in Git

`Buildkite` owns:

- validation, rendering, linting, policy checks, and tests
- artifact and image production
- optional Git-facing automation such as opening a PR or preparing a
  promotion change for review

`Buildkite` does not own:

- direct cluster mutation
- `kubectl apply`
- `helm upgrade`
- `flux reconcile`
- any alternate deployment loop competing with Flux

This is a hard boundary, not a preference. There is no bucket-watched
Flux source, no CI-driven cluster mutation path, and no second
deployment engine next to Flux.

### Interfaces to adjacent initiatives

This initiative defines where adjacent work lands without absorbing that
work into scope.

- Secrets management must provide encrypted or referenced inputs that
  can be consumed from the appropriate overlay or cluster root. The
  secret system itself is not redesigned here. A cluster root may rely
  on at most one secret-reconciliation path at any one time; changing
  the path is a topology-affecting change.
- Ingress work must attach to the control-cluster or app-cluster roots
  defined here. Ingress product choices are not revisited here.
- Application delivery must express releases as Git changes consumed by
  Flux. App-level business behavior is not part of this initiative.
- Cluster bootstrap may create the initial Flux installation, but once a
  cluster is rooted, ongoing state changes flow through Git and Flux.
- Crossplane cluster claims and downstream-cluster Flux bootstrap:
  `Crossplane` `ClusterClaim` resources for application cluster
  provisioning land under the control-cluster root in the appropriate
  environment path (e.g., `clusters/<env>/control-cluster/`). When
  Application Cluster Provisioning creates a new downstream cluster,
  the per-cluster Flux root for that cluster is bootstrapped into the
  `clusters/<env>/app-cluster/` path following the same per-cluster
  root model defined above. This initiative defines the topology slot;
  the claim content and provisioning logic are owned by Application
  Cluster Provisioning.
- Cross-cluster platform dependencies are expressed as independent
  declarations in each cluster root with a shared source of truth in
  `base/`, not as one cluster reconciling on behalf of another.

## 4. What this initiative delivers

This initiative delivers:

- a canonical multi-environment GitOps topology for `dev`, `staging`,
  and `production`
- a canonical two-tier cluster topology in each environment:
  `control-cluster` plus `app-cluster`
- a per-cluster Flux root model with one reconciler scope per real
  cluster
- a clear rule that environment promotion is path-based Git change, not
  live-cluster mutation from CI
- a clear operating boundary where Git is the desired-state system and
  `Flux CD` is the sole reconciler
- a stable interface for later secrets, ingress, platform-service, and
  application initiatives to target

## 5. What is explicitly out of scope

The following are not part of `GitOps Foundation`:

- writing Flux manifests, `Kustomization` objects, or bootstrap code
- writing `Buildkite` pipelines or CI automation
- provisioning clusters or implementing the infrastructure bootstrap
- redesigning secrets management, ingress, or identity decisions
- defining app-level service topology or business features
- selecting concrete workload placement for every future platform
  component
- introducing image automation, release automation, or promotion bots as
  part of this initiative
- any deployment path that bypasses Git or competes with Flux

## 6. Risks and open questions

### Risks

- The main structural risk is overlay sprawl. If too much logic moves
  into `overlays/`, the repository becomes copy-paste by environment
  rather than shared intent plus controlled variation.
- Per-cluster roots improve safety, but they also create repetition. The
  implementation phase will need conventions that keep roots thin and
  prevent each cluster directory from turning into bespoke logic.
- The two-tier model is clean architecturally, but it increases the
  number of roots, promotion paths, and bootstrap sequences that must be
  kept consistent.
- If CI is later allowed to hold live cluster credentials, the boundary
  in this proposal collapses quickly. The initiative depends on keeping
  Buildkite on the Git side of the wall.

### Open questions

- Should the topology live in a dedicated desired-state repository, or
  in a dedicated GitOps subtree of a broader platform repo? The topology
  itself is the same, but repository ownership and review boundaries
  differ.
- What promotion mechanism should be standard across environments:
  direct PRs against target paths only, or a more structured promotion
  workflow that still lands as reviewed Git changes?
- Does the first implementation phase bootstrap all three environments
  immediately, or define the full topology now and phase physical
  cluster rollout afterward? The topology should assume all three; the
  rollout sequence may still be staged.
- Which shared platform controllers belong in the control cluster base
  from day one, versus being introduced by later initiatives once the
  topology is in place?

## 7. Exit criteria

The `GitOps Foundation` initiative is complete when all of the
following are true:

- the desired-state repository has a defined `base/`, `overlays/`, and
  `clusters/<env>/...` layout for `dev`, `staging`, and `production`
- each environment has both a `control-cluster` root and an
  `app-cluster` root
- each physical cluster has exactly one Flux root path, and no Flux root
  targets a shared parent path spanning multiple clusters or
  environments
- the operating rule is explicit that Git holds desired state and
  `Flux CD` is the sole reconciler of in-cluster state
- the CI boundary is explicit that `Buildkite` validates and prepares
  Git changes but does not mutate clusters directly
- a defined topology slot exists for `Crossplane` cluster claims under
  the control-cluster root, and a defined bootstrap path exists for
  wiring per-cluster Flux roots onto newly provisioned downstream
  clusters under `clusters/<env>/app-cluster/`
- later initiatives have a clear contract for where their manifests and
  overlays land without redefining the topology
