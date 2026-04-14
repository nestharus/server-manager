# Phase 1 Foundation v2 — Vultr VKE with a three-environment model

## 1. Executive summary

Phase 1 Foundation v2 defines the minimum production-ready platform
substrate on `Vultr Kubernetes Engine (VKE)` for Humility. It replaces
the superseded Hetzner-based Phase 1 proposal while preserving the parts
of the original scope that were still correct: bootstrap the platform,
do not ship application features yet, keep the GitOps path singular, and
leave later identity, policy, and application phases room to land
cleanly.

The correct environment model for this repo is not "one live cluster and
one always-on QA cluster." It is one persistent iteration environment,
one persistent production environment, and one on-demand environment for
release-candidate benchmarking. The repo already points in that
direction: `infra/` validates `dev`, `staging`, and `production`;
`dev` is cheap and persistent; `staging` is production-shaped and
ephemeral; `production` is persistent. What is missing is the formal
contract that ties those pieces together.

This proposal sets that contract. Phase 1 will use `VKE` because it
provides a managed control plane at no extra charge and removes the
self-managed `k3s` and `kube-hetzner` burden from the foundation layer.
It formalizes a promotion flow of `dev -> production` for normal
functional changes, and `dev -> staging -> production` only when the
change is infrastructure-heavy or performance-sensitive. It keeps
benchmarking defined but non-blocking in Phase 1, and it keeps LLM video
QA as a `dev` proof-of-concept rather than a CI or release gate.

The proposal also closes the exact gaps identified by current research
and repository state: remove Hetzner storage-class assumptions, stop
treating Flux as a single bootstrap path, make per-cluster GitOps roots
explicit, and replace vague autoscaling intent with concrete node-pool
policies. The result is a narrow Phase 1 that is credible, operational,
and directly implementable.

## 2. Environment model

### Environment roles

Phase 1 uses three environments with deliberately different roles.

`dev`

- Persistent and always on.
- Default target for human iteration, agent iteration, E2E checks,
  exploratory testing, and the LLM video QA proof-of-concept.
- Cheap by design. It is not meant to mirror production perfectly; it is
  meant to be the lowest-friction safe place to change the platform.

`staging`

- On-demand and destroyed after use.
- Used only for release candidates that need production-shaped
  validation: benchmark runs, infrastructure changes, ingress changes,
  storage changes, or changes likely to affect scaling, reconciliation,
  or network behavior.
- Not a second dev cluster and not a permanent QA environment.

`production`

- Persistent and boring.
- Used only for the live platform serving real traffic and the real
  Humility Discord surface.
- Must avoid experimental configuration drift.

### Lifecycle, sizing, purpose, and cost

| Environment | Lifecycle | Purpose | Baseline sizing | Baseline monthly cost |
| --- | --- | --- | --- | --- |
| `dev` | Persistent | Fast iteration, E2E, LLM video QA POC | `1 x vc2-1c-2gb`, autoscale `1-2` | about `$23/mo` |
| `staging` | On-demand | RC benchmarks and infra validation | `3 x vc2-2c-4gb`, autoscale `3-6` | about `$74/mo` while running |
| `production` | Persistent | Live service | `3 x vc2-2c-4gb`, autoscale `3-6` | about `$77/mo` |

Cost assumptions are explained in section 10. The important operational
point is that only `dev` and `production` are always on. `staging`
exists to answer a release question, then disappears.

### Promotion flow

The promotion flow is intentionally asymmetric.

Default flow for functional changes:

`dev -> production`

Use this path when the change is primarily application logic, UI logic,
Discord command behavior, validation, authz policy, or another
functional concern that does not materially change platform
characteristics.

Required flow for infra-heavy or performance-sensitive changes:

`dev -> staging -> production`

Staging is required when any of the following are true:

- The change touches `infra/` or `k8s/` in a way that affects worker
  sizing, storage classes, ingress, Flux topology, or reconciliation.
- The change is expected to alter API latency, pipeline latency, DB
  latency, pod readiness, Flux reconciliation time, or Discord gateway
  reconnect behavior.
- The change introduces new persistent volumes, new `LoadBalancer`
  services, or new environment-specific secret wiring.
- The change modifies autoscaling assumptions or resource requests in a
  way that could change cluster packing or node pressure.

Staging is not required for routine feature work just because the repo
has a staging environment. If every change must traverse staging, the
project pays the operational cost of a third environment without
actually narrowing any real risk.

### Configuration differences

Environment differences are explicit, not incidental.

Secrets:

- Every environment gets distinct secrets.
- No shared database passwords, API keys, bot tokens, or object-storage
  credentials across environments.
- `dev` and `staging` point to sandbox or non-production third-party
  credentials where such credentials exist.

DNS:

- `production` uses the canonical public root domain.
- `dev` uses a dedicated development subdomain.
- `staging` uses a dedicated staging subdomain that only exists while
  the environment exists.

Feature flags:

- `dev` may enable experimental flags.
- `staging` mirrors `production` flags unless a benchmark-specific flag
  is required for measurement.
- `production` only enables accepted release flags.

External endpoints:

- `dev` points at sandbox integrations and non-production callback URLs.
- `staging` points at staging-specific callback URLs and benchmark-safe
  integrations.
- `production` points at live integrations only.

### Discord bot integration

Discord integration must respect the Live Server Principle.

- `production` uses the production bot token and the live Humility guild
  id: `900000000000000001`.
- `dev` uses a separate Discord application, a separate bot token, and a
  dedicated sandbox guild id. It must never connect to the live Humility
  guild.
- `staging` uses its own bot token and sandbox guild id as well. It is
  brought online only for RC validation or gateway-related benchmarks and
  is never pointed at the live guild.

This is not optional hygiene. Non-production environments must not share
bot identity or guild targeting with production.

## 3. Vultr VKE specification

### Per-environment cluster specification

`dev`

- Region: `ewr`
- Control plane: managed VKE control plane, non-HA
- Worker plan: `vc2-1c-2gb`
- Node pool: minimum `1`, maximum `2`
- Purpose of autoscaling: absorb short bursts from E2E runs, agent work,
  and video QA without permanently paying for a second node

`staging`

- Region: `ewr`
- Control plane: managed VKE control plane, non-HA
- Worker plan: `vc2-2c-4gb`
- Node pool: minimum `3`, maximum `6`
- Purpose of autoscaling: benchmark realistic node-pool growth and test
  infrastructure changes against production-shaped worker capacity

`production`

- Region: `ewr`
- Control plane: managed VKE control plane, HA enabled
- Worker plan: `vc2-2c-4gb`
- Node pool: minimum `3`, maximum `6`
- Purpose of autoscaling: support normal production growth without
  making Phase 1 dependent on a larger baseline footprint

### Autoscaling policy

Phase 1 supports only node-pool autoscaling. It does not introduce
`HPA`, `KEDA`, custom metrics autoscaling, or queue-driven scaling.

That is intentional. The current repo already encodes min/max node
counts, but without a proposal they read like mechanical placeholders.
In v2 they become a narrow contract:

- VKE node-pool autoscaling is enabled wherever `max_nodes > min_nodes`.
- `dev` scales for transient convenience.
- `staging` and `production` scale for cluster capacity, not because
  application-level autoscaling has been solved.
- Workload autoscaling belongs in later application phases, after the
  platform foundation is trustworthy.

### VKE networking

VKE uses Vultr's managed Kubernetes control plane and the default VKE
networking stack. The default CNI is `Calico`.

Implications:

- Phase 1 does not need to bolt on a second CNI.
- Future network-policy work should use the Calico-backed policy surface
  already present in VKE rather than planning a later "Calico adoption"
  project that would duplicate what VKE already ships.
- Later zero-trust and policy work can layer on top of this foundation
  instead of re-platforming networking.

### Storage classes

Phase 1 recognizes the VKE storage classes explicitly:

- `vultr-block-storage`
- `vultr-block-storage-hdd`

The Phase 1 default for stateful add-ons is `vultr-block-storage`.

Reasons:

- It matches the current low-volume, operationally important workloads
  better than HDD-backed storage.
- It has a lower minimum size floor than HDD-backed volumes.
- It avoids dragging old Hetzner assumptions into the Vultr platform.

`vultr-block-storage-hdd` remains defined and available, but it is not
the default in Phase 1. Using it as the default would force larger
minimum PVC sizes while also weakening storage performance for the very
few stateful platform services Phase 1 actually needs.

### Load balancer behavior

VKE integrates with the `Vultr Cloud Controller Manager`. Any Kubernetes
service declared as `type: LoadBalancer` provisions a Vultr load
balancer.

Phase 1 relies on that behavior directly:

- One public ingress path per active environment is allowed.
- `dev` gets a load balancer because it needs externally reachable E2E
  and video QA flows.
- `staging` gets a load balancer only while the environment exists.
- `production` gets a persistent load balancer.

VKE does not provide an ingress controller by default. That is fine for
Phase 1. The cluster foundation must support a chosen ingress
controller; it does not need to conflate that with the environment model
itself.

## 4. OpenTofu structure

Phase 1 should stop treating `infra/` as one flat environment-agnostic
directory with comments standing in for topology.

Target structure:

```text
infra/
  modules/
    vke-cluster/
    object-storage/
  environments/
    common.tfvars
    dev/
      main.tf
      terraform.tfvars
      backend.tfbackend
    staging/
      main.tf
      terraform.tfvars
      backend.tfbackend
    production/
      main.tf
      terraform.tfvars
      backend.tfbackend
```

### Module layout

- `modules/vke-cluster` owns the Vultr cluster, node-pool config, and
  shared tags/labels.
- `modules/object-storage` owns the shared benchmark and artifact bucket
  used across environments.
- Environment roots wire those modules together with per-environment
  inputs.

### Backend state isolation

State is isolated per environment. Each environment keeps its own
backend file and its own state key.

- `infra/dev/terraform.tfstate`
- `infra/staging/terraform.tfstate`
- `infra/production/terraform.tfstate`

The current backend direction is correct: one remote state bucket and
one key per environment. What must become explicit in the proposal is
the operational rule that follows from Vultr Object Storage semantics:
one writer per environment at a time. Phase 1 should not pretend remote
state locking is magically solved just because the backend uses
`use_lockfile`.

### Variable hierarchy

The variable hierarchy is:

1. shared defaults in `common.tfvars`
2. environment-specific overrides in `environments/<env>/terraform.tfvars`
3. secrets and operator-specific values from environment variables or
   secure input

That keeps common decisions centralized:

- region default
- default storage-class choice
- naming conventions
- shared tags

And keeps environment-specific choices local:

- node plan
- min/max nodes
- HA control plane policy
- environment labels

## 5. Flux CD multi-environment structure

The current Flux skeleton is not enough. It points at one bootstrap
path, which means the repo has environment overlays without a clean
per-cluster reconciliation story.

Phase 1 v2 uses path-based per-cluster roots.

Target structure:

```text
k8s/
  base/
    monitoring/
    secrets/
    flux-system/
  overlays/
    dev/
    staging/
    production/
  clusters/
    dev/
      kustomization.yaml
      flux-system/
    staging/
      kustomization.yaml
      flux-system/
    production/
      kustomization.yaml
      flux-system/
```

### Base -> overlays -> environment pattern

- `base/` contains shared manifests with no environment-specific values.
- `overlays/dev`, `overlays/staging`, and `overlays/production` patch
  retention, resources, feature flags, ingress hosts, and secret names.
- `clusters/<env>/kustomization.yaml` is the cluster root that points to
  the matching overlay and any cluster-specific bootstrap resources.

### How each environment watches its own path

Each cluster bootstraps Flux against its own cluster root.

- `dev` watches `./k8s/clusters/dev`
- `staging` watches `./k8s/clusters/staging`
- `production` watches `./k8s/clusters/production`

That means the current single-path `gotk-sync.yaml` pattern is replaced
by three cluster-specific sync roots. The repo still has one source of
truth, but each cluster reconciles only the manifests intended for it.

### Promotion model

Promotion is Git movement, not out-of-band mutation.

- Shared fixes land in `base/` and affect all environments once promoted
  through normal Git flow.
- Environment-specific config remains in the environment overlay.
- A manifest change is promoted by moving the corresponding patch,
  image tag, or configuration delta from `overlays/dev` to
  `overlays/production`, with `staging` participating only when required
  by the promotion rules in section 2.

This preserves one reconciler and one source of truth without forcing
every environment to read the same path.

## 6. Secrets management

Phase 1 uses `sealed-secrets` for bootstrap.

Reasons:

- It is already the direction implied by the current `k8s/base/secrets`
  manifests.
- It is compatible with GitOps bootstrap.
- It avoids introducing a full-time secrets control plane before the
  platform base exists.

### Bootstrap path

- Install the Sealed Secrets controller first.
- Generate sealed secrets per environment.
- Commit only encrypted manifests.
- Never commit plaintext bootstrap secrets.

### Per-environment secret strategy

Every environment gets separate values for:

- database passwords
- API credentials
- Discord bot tokens
- object storage credentials
- OAuth callback secrets
- monitoring admin credentials

The secret naming convention should include the environment to avoid
cross-environment ambiguity. Production secret names must never be reused
in non-production namespaces.

### Migration path to Infisical

Phase 2 and later should migrate long-lived secret management to
`Infisical`.

Phase 1 only needs the migration path, not the full migration.

- Bootstrap stays on sealed secrets.
- Runtime secret retrieval, rotation workflows, and richer secret audit
  move to Infisical later.
- No compatibility shim should keep both systems as co-equal permanent
  truth sources.

The clean migration rule is: sealed secrets bootstraps the platform,
Infisical becomes the long-term runtime secret manager later, and the
old path is removed when the new path is accepted.

## 7. Observability

Phase 1 observability is `Prometheus + Grafana + Alertmanager`.

That stack is already represented in `k8s/base/monitoring`; the Phase 1
task is to make it valid on Vultr and appropriately sized per
environment.

### Storage class correction

All monitoring PVCs must use `vultr-block-storage`, not
`hcloud-volumes`.

This is one of the concrete defects in the current repo and must be
fixed as part of the foundation implementation that follows this
proposal.

### Per-environment sizing

`dev`

- Prometheus retention: `24h`
- Prometheus PVC: `10Gi`
- Grafana PVC: `10Gi`
- Alertmanager PVC: `10Gi`
- Resource requests stay minimal to preserve the low-cost purpose of the
  cluster

`staging`

- Prometheus retention: `3d`
- Prometheus PVC: `20Gi`
- Grafana PVC: `10Gi`
- Alertmanager PVC: `10Gi`
- Sized to support benchmark windows, not long-lived trend analysis

`production`

- Prometheus retention: `30d`
- Prometheus PVC: `50Gi`
- Grafana PVC: `10Gi`
- Alertmanager PVC: `10Gi`
- Sized for operational continuity and meaningful baseline comparison

This is intentionally modest. Phase 1 is not building a full metrics
warehouse. It is building enough visibility to know whether the platform
is healthy and whether a staging benchmark run means anything.

### Alerting surface

Phase 1 alerting is narrow:

- cluster not ready
- Flux reconciliation degraded
- Prometheus target down
- excessive pod restart rate for baseline components
- ingress/load-balancer path unavailable

Anything broader belongs in later phases when real services exist.

## 8. Benchmarking plan

Phase 1 defines benchmarking. It does not turn benchmarking into a
mandatory merge gate yet.

### Metrics to measure

The benchmark contract defines these metrics:

- API latency
- pipeline latency
- DB latency
- pod readiness time
- Flux reconciliation time
- Discord reconnection time

Because Phase 1 is still foundation work, these metrics split into two
groups.

Runnable in Phase 1:

- pod readiness
- Flux reconciliation
- ingress-path or synthetic API latency
- Discord reconnect timing when the staging bot is intentionally brought
  online for an RC validation run

Defined now, fully exercised later:

- pipeline latency
- DB latency
- full application API latency against the real service surface

This is acceptable because the Phase 1 deliverable is the contract, the
runner choice, and the storage path, not a complete benchmark suite.

### Tool choice

Phase 1 uses `k6`.

Why `k6`:

- It is lightweight enough for a foundation phase.
- It is strong on HTTP/API latency measurement, which is the first
  benchmark dimension that will matter as services land.
- It can live comfortably in CI or be run ad hoc against the on-demand
  staging environment.
- It is a better fit than `Locust` for a minimal Phase 1 because it does
  not require committing to a Python load-test harness.
- It is a better fit than `vegeta` because the benchmark contract needs
  more structure than raw request blasting.

### Where results are stored

Benchmark results are stored in shared Vultr Object Storage under a
dedicated prefix, for example:

`s3://<benchmark-bucket>/phase1-benchmarks/<env>/<yyyy-mm-dd>/<git-sha>/`

Each run stores:

- runner metadata
- environment metadata
- cluster sizing metadata
- raw benchmark output
- normalized summary JSON
- pass/fail evaluation output

The summary JSON becomes the baseline source for later comparison.

### When benchmarks run

Benchmarks run on `staging` for release candidates only when the change
meets the staging-required rules from section 2.

Typical triggers:

- infra changes
- storage changes
- ingress changes
- autoscaling changes
- changes expected to move latency or readiness characteristics

### Pass/fail gate model

The future gate model is regression-vs-baseline, not absolute fantasy
numbers.

Baseline:

- compare against the last accepted run for the same benchmark suite on
  the same environment shape

Default thresholds:

- fail if p95 API latency regresses by more than `20%`
- fail if DB latency regresses by more than `20%`
- fail if pipeline latency regresses by more than `20%`
- fail if median pod readiness regresses by more than `25%`
- fail if Flux reconciliation time regresses by more than `25%`
- fail if Discord reconnect time regresses by more than `20%`
- fail on materially increased error rate even if latency stays inside
  threshold

Phase 1 status:

- thresholds are defined
- results are recorded
- the outcome is visible
- the result is not CI-blocking yet

That is enough foundation without pretending the benchmark program is
already mature.

## 9. LLM video QA plan

Phase 1 includes a dev-facing proof-of-concept only.

Workflow:

1. `Playwright` drives a form-based flow in `dev`.
2. The run records a video.
3. The captured video and a structured intent statement are sent to
   `Gemini` for analysis.
4. The output is stored as an inspection artifact for a human or agent
   to review.

### What "intent" means for a form-based UI

Intent is not vague prose such as "make sure the form works."

Intent is a structured expected-behavior statement, for example:

- which form is under test
- which user role is acting
- which fields are required
- what valid and invalid input examples are used
- what success state should appear
- what validation errors should appear
- whether any side effect should occur after submit

That structure matters because a video model can only judge behavior
well if it is told what correct behavior looks like.

### Scope rule

- This is a `dev` workflow.
- It is not a CI gate in Phase 1.
- It does not participate in production promotion in Phase 1.
- It exists to prove that the workflow is viable on the platform
  foundation.

### Model choice

For this workflow, `Gemini` is treated as the only viable video-QA model
currently worth wiring into the platform. Phase 1 does not attempt a
multi-model abstraction layer around video QA.

## 10. Cost model

All figures below are approximate monthly costs based on the current
worker sizing in the repo and current public pricing for Vultr and
Buildkite. Staging is hourly in practice because it is destroyed after
use.

### Assumptions

- `vc2-1c-2gb` worker node: about `$10/mo`
- `vc2-2c-4gb` worker node: about `$20/mo`
- Vultr load balancer: starts at `$10/mo`
- Vultr Object Storage standard tier: `$18/mo`
- Vultr NVMe block storage: `$1/mo` per `10Gi`
- Buildkite Personal can remain `$0/mo` for a one-user Phase 1; Pro is
  `$30` per active user per month if later needed

### Dev

Assumptions:

- `1 x vc2-1c-2gb` baseline worker = `$10`
- one public load balancer = `$10`
- `30Gi` NVMe block storage for monitoring = `$3`

Dev persistent total:

`$23/mo`

Peak if autoscaled to two nodes for a full month:

`$33/mo`

### Production

Assumptions:

- `3 x vc2-2c-4gb` workers = `$60`
- one public load balancer = `$10`
- `70Gi` NVMe block storage for monitoring = `$7`

Production persistent total:

`$77/mo`

Peak if autoscaled to six nodes for a full month:

`$137/mo`

### Staging

Assumptions while active:

- `3 x vc2-2c-4gb` workers = `$60`
- one load balancer = `$10`
- `40Gi` NVMe block storage = `$4`

Staging cost while running:

`$74/mo` equivalent

Amortized assumption:

- four 24-hour RC runs per month
- Vultr hourly billing capped monthly at the monthly rate

Amortized staging spend:

about `$11/mo`

### Shared services

- Vultr Object Storage standard tier for benchmarks and artifacts:
  `$18/mo`
- Buildkite platform: `$0/mo` on Personal at Phase 1 scale, or `$30/mo`
  if upgraded to Pro

### Total

Steady-state total with Buildkite Personal and staging amortized:

- `dev` `$23`
- `production` `$77`
- `staging` amortized `$11`
- object storage `$18`
- Buildkite `$0`

Estimated ongoing monthly total:

`$129/mo`

If Buildkite Pro is required later:

`$159/mo`

This proposal intentionally keeps the baseline low by making `staging`
ephemeral. If staging becomes permanent, the real baseline rises by
roughly another `$63/mo` over the amortized assumption.

## 11. Definition of done

Phase 1 Foundation v2 is complete when all of the following are true:

- `dev` and `production` VKE clusters respond successfully.
- `staging` can be created and destroyed repeatably from OpenTofu.
- each cluster bootstraps Flux against its own cluster-specific path.
- Flux reconciles the intended overlay for each environment.
- sealed secrets bootstrap works in each environment.
- monitoring loads successfully in each environment.
- monitoring PVCs use valid Vultr storage classes.
- benchmark definitions exist for the metric set in section 8.
- the benchmark runner exists and writes results to the agreed storage
  path.
- one benchmark run has been executed successfully on `staging`.
- the Playwright -> video capture -> Gemini proof-of-concept has run
  once successfully on `dev`.
- the production Discord bot is wired only to guild
  `900000000000000001`.
- non-production Discord bots are isolated to sandbox guilds.

## 12. What Phase 2 needs from Phase 1

Phase 2 depends on Phase 1 providing a stable substrate, not a pile of
loosely related experiments.

Phase 2 specifically needs:

- a reliable per-environment OpenTofu layout
- a per-cluster Flux topology that does not conflate environments
- a valid secrets bootstrap path
- correct Vultr storage-class usage
- observability good enough to diagnose regressions
- benchmark metadata and result storage already defined
- a working dev environment that supports API, web, and Discord service
  development
- a clear rule that the platform is API-first: every feature must have
  an API surface, and the UI remains a client of that API rather than
  becoming the only control plane

Without those guarantees, Phase 2 would have to spend time re-litigating
the platform instead of building on it.

## 13. Risks

### 1. Staging drift risk

If staging is left running, hand-edited, or repurposed as a general QA
cluster, the project pays the cost of a third environment without
preserving the benefit of a reproducible benchmark target.

Mitigation:

- staging is on-demand only
- destroy after RC validation
- never use staging as the default dev target

### 2. Flux topology risk

If Flux continues to watch a single base path, the environment overlays
remain only partially real and cluster isolation is ambiguous.

Mitigation:

- per-cluster sync roots
- cluster root directories committed in Git

### 3. Storage invalidity risk

The current `hcloud-volumes` usage is invalid on Vultr, and the current
PVC sizes are not safe to carry forward mechanically.

Mitigation:

- standardize on `vultr-block-storage`
- set explicit per-environment PVC sizes that satisfy Vultr constraints

### 4. False benchmark confidence risk

If Phase 1 advertises benchmarking without a baseline, threshold, or
result store, the project gains ceremony but not real signal.

Mitigation:

- define the metric contract now
- choose the runner now
- store run outputs now
- keep the gate non-blocking until the benchmark program is mature

### 5. Discord safety risk

If non-production bots share production identity or guild targeting, a
platform bootstrap mistake becomes user-visible damage on the live
server.

Mitigation:

- separate bot tokens
- separate Discord applications
- separate sandbox guild ids
- no non-production connection to Humility production guild

### 6. Scope expansion risk

Foundation work can easily sprawl into ingress, identity, policy,
database, eventing, and application delivery under the banner of
"realism."

Mitigation:

- Phase 1 stays focused on clusters, GitOps topology, secrets,
  observability, and the benchmark contract
- later phases consume this substrate instead of being smuggled into it

### 7. State concurrency risk

Remote state stored in Vultr Object Storage still requires disciplined
single-writer behavior. A one-person-plus-agents workflow can violate
that accidentally if the rule is not explicit.

Mitigation:

- one writer per environment at a time
- isolated environment roots
- no concurrent infra mutation against the same state

