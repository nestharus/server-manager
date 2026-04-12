# Buildkite capabilities vs legacy CI platform

Date checked: 2026-04-11

## Executive summary

Buildkite can replace most of the legacy platform's CI orchestration layer, but not the whole custom control plane.

The clearest shift is this:

- Buildkite replaces the Dagger-centric pipeline scheduler, job fan-out, step dependencies, matrix execution, trigger chaining, artifact passing, and much of the "run builds on isolated workers" story.
- Flux CD replaces Argo CD in the GitOps/CD layer: reconciliation, image automation, webhook-driven source refresh, and cluster sync.
- What remains custom is the platform-specific state model around environments, preview environment lifecycle, approvals/governance beyond Buildkite's built-ins, cross-system event durability, and any domain-level API that treats "environment" as a first-class business object rather than just "a commit in a GitOps repo."

In other words, Buildkite is a strong replacement for the custom CI execution backbone, but it is not a drop-in replacement for Kafka, Debezium, Redis, Elasticsearch/Kibana, or a bespoke environment-management API. Some of those can be eliminated outright; others only disappear if the product scope is simplified.

## Bottom-line mapping

| Legacy responsibility | Buildkite / Flux native coverage | Still custom? |
|---|---|---|
| Parallel build execution | Yes. Parallel steps, dependencies, matrices, trigger steps, dynamic pipelines | No, for normal CI orchestration |
| Container/job isolation | Partly. Buildkite orchestrates; isolation comes from hosted agents, Docker plugins, or `agent-stack-k8s` pods | No separate orchestration layer, but you still own runtime isolation choices |
| Agent fleet on Kubernetes | Yes. `agent-stack-k8s` runs jobs as Kubernetes Jobs/Pods on your cluster | Cluster autoscaling/infrastructure policy still yours |
| Event-driven CI triggers | Partly. Outgoing webhooks, incoming pipeline triggers, REST API, trigger steps | Yes, if you need a durable multi-consumer event backbone |
| CDC from Postgres via Debezium | No | Yes, if DB change streams are still a requirement |
| Redis ephemeral state/counters | Small amount only via Buildkite metadata, artifacts, queues | Yes, if you need shared atomic state beyond one build |
| Artifact storage | Yes for short-lived artifacts; Package Registries for longer-lived packages | Maybe external registry/cache still needed |
| Log UI / pipeline observability | Yes, plus Waterfall, queue metrics, cluster insights, observability integrations | Maybe external observability/search still needed for cross-system analysis |
| GitOps CD | Flux covers reconciliation, webhooks, image automation, Git-driven deploys | No extra CD orchestrator needed |
| Environment CRUD API | No | Yes, if you still want dynamic environments as first-class managed objects |

## 1. Buildkite pipeline orchestration

Buildkite natively covers the main pipeline-graph features the legacy spec previously modeled around Dagger. Its YAML model supports:

- parallel execution through multiple runnable steps
- explicit dependencies with `depends_on`
- concurrency controls with `concurrency` and `concurrency_group`
- matrix builds for fan-out across dimensions like OS, architecture, or test shard
- trigger steps to chain pipelines together
- dynamic pipelines, where one step generates and uploads more steps during the same build

That is enough to replace a large amount of custom "workflow engine" logic.

Two details matter for design:

First, Buildkite's matrix support is first-class, but it is still Buildkite's step model, not a general-purpose container DAG language. You get excellent CI workflow primitives, not something equivalent to Dagger's programmable container graph abstraction.

Second, Buildkite's dynamic pipelines are flexible, but the dynamically generated steps are uploaded from a running step and "run on the same Buildkite agent, as part of the same pipeline build." That means dynamic pipelines are an orchestration extension inside Buildkite's build model, not a separate workflow runtime. This is usually fine, but it is a different operational model from a fully custom scheduler.

Does this replace Dagger's container-based isolation? Not by itself.

Buildkite handles scheduling and orchestration. Isolation depends on how jobs are executed:

- on Buildkite hosted agents
- on self-hosted agents
- inside Docker via the official Docker or Docker Compose plugins
- or, most relevant here, as Kubernetes Jobs/Pods via `agent-stack-k8s`

So the right conclusion is: Buildkite replaces Dagger as the orchestrator, but container isolation is provided by the agent runtime you choose, not by Buildkite's control plane alone.

For a Kubernetes-based design, this is probably acceptable. Buildkite plus `agent-stack-k8s` gives isolated per-job pods, custom images, pod templates, and pod-spec patches. That is a strong substitute for "each build runs in an isolated container environment," even though the abstraction boundary is different from Dagger.

## 2. Buildkite agents on Kubernetes

Buildkite's agent model is explicitly designed around self-hosted execution. A build agent runs one job at a time, polls Buildkite for work, executes the command, streams logs back, and uploads artifacts. Buildkite's newer "clusters" and "queues" features are the main control surface for organizing agent pools.

For Kubernetes, the relevant product is Agent Stack for Kubernetes (`agent-stack-k8s`). Buildkite documents it as a Kubernetes controller that watches the Agent API for scheduled jobs assigned to its queue. When it finds a matching job, it creates a Kubernetes Job containing a single Pod with the containers needed to acquire and run the Buildkite job.

That means yes: Buildkite agents can absolutely run on the same Kubernetes cluster as the workloads they build or deploy, if you want that topology. Buildkite also explicitly notes that a Buildkite "cluster" is a logical Buildkite construct and is unrelated to a Kubernetes cluster, which is useful for avoiding conceptual confusion.

Queues are the main way to build agent pools. Buildkite recommends organizing queues by infrastructure traits like architecture, machine size, and OS type. In practice that gives you pools such as:

- `linux-amd64-small`
- `linux-arm64-large`
- `mac-silicon`
- `deploy`
- `gpu`

This replaces much of the custom "worker-class routing" logic that teams often build for themselves.

What Buildkite does not provide is the full infrastructure autoscaling layer for your Kubernetes cluster. `agent-stack-k8s` will turn queued Buildkite work into Kubernetes Jobs, but cluster capacity management is still on you. If the cluster must scale from zero or burst aggressively, you still need the normal Kubernetes-side machinery such as Cluster Autoscaler, Karpenter, node pools, taints/tolerations, storage classes, and image caching strategy.

So the split is:

- Buildkite handles CI job scheduling, queue assignment, and pipeline state
- Kubernetes handles pod scheduling and underlying compute capacity

That is much simpler than a custom CI control plane, but it is still not "Buildkite manages the whole worker fleet for me" unless you switch to Buildkite hosted agents instead of self-hosting on Kubernetes.

## 3. Buildkite eventing

Buildkite provides multiple event and trigger surfaces:

- outgoing webhooks for build, job, and agent events
- incoming pipeline triggers, which are webhook endpoints that create builds
- REST APIs for creating and inspecting builds, pipelines, artifacts, and more
- trigger steps for pipeline-to-pipeline chaining
- build metadata for passing key/value state between steps and across agents inside one build

This is enough to replace a lot of ad hoc event glue in a CI system. If the legacy Kafka backbone mostly existed so that "CI finished" could trigger "deploy pipeline starts," "notify service," or "record build outcome," Buildkite can cover a substantial part of that natively.

But it is not a Kafka replacement in the architectural sense.

The limitations are important:

- Buildkite webhooks are notifications, not a durable event stream
- pipeline triggers are still fairly constrained: public preview, no API management, no selective triggering based on payload content, no access to request headers inside the pipeline, and no API/UI support for listing builds created from a trigger
- webhook delivery is not a general event-log system with replay, partitioning, offsets, consumer groups, or long-term retention semantics
- Buildkite has no CDC concept comparable to Debezium streaming Postgres row changes as ordered events

So if the old design truly depended on a platform-wide asynchronous event bus used by multiple downstream consumers, Buildkite does not replace Kafka. If instead the event layer was mostly serving CI/CD fan-out and lifecycle notifications, you can likely collapse that complexity into Buildkite webhooks, trigger steps, and a smaller integration service.

My recommendation from the docs is:

- eliminate Kafka for CI-native transitions unless there is a proven non-CI consumer ecosystem that still needs durable events
- do not assume Buildkite events are sufficient if you still need replayable domain events, environment lifecycle projections, or database-originated event streams

## 4. Artifacts, caching, and ephemeral state

Buildkite has first-class artifacts and several caching options, but they are opinionated and narrower than a full custom caching subsystem.

Artifacts:

- Buildkite Pipelines supports build artifacts directly
- the pricing page says short-lived artifact storage is included up to 5 GB per artifact with six-month retention
- artifacts can be passed between steps and retrieved later for debugging or downstream jobs

Longer-lived packages:

- Buildkite Package Registries is the product for longer-lived package and artifact management
- it supports multiple ecosystems and can use Buildkite-managed storage or private S3/GCS-backed storage

Caching:

- Buildkite hosted agents support cache volumes
- Buildkite explicitly describes those cache volumes as best-effort and non-deterministic
- Git mirror caching is available
- Docker cache plugins and registry-backed layer caches are available
- Buildkite recommends external remote caches for some deterministic cross-machine cases, such as Bazel-style caching

This is enough to replace a lot of hand-rolled artifact handling and "temporary file shuttle" logic.

What it does not replace cleanly:

- a generalized Redis layer for atomic counters, locks, leases, or ephemeral cross-build workflow state
- a content-addressable remote build cache if your build system depends on one
- arbitrary shared state machines spanning multiple builds and services

Buildkite metadata is useful, but limited. It is a small key/value store for one build, values are capped at 100 KB, and Buildkite explicitly says not to store secrets there. That can replace tiny bits of orchestration state inside a build, but not a serious shared-state subsystem.

So Redis likely goes away only if the product scope is simplified to "Buildkite pipeline state plus GitOps state is enough." If you still want a platform service that tracks counters, TTLs, preview-environment leases, approval windows, or distributed orchestration locks, Redis or another state store remains a real requirement.

## 5. Buildkite + Flux CD

Buildkite and Flux fit together cleanly, but they occupy different layers:

- Buildkite is CI and workflow orchestration
- Flux is reconciliation-driven CD / GitOps

The standard integration pattern is:

1. Buildkite runs tests and builds artifacts/images.
2. Buildkite pushes the image to a registry.
3. Either Buildkite updates the GitOps repo directly, or Flux image automation updates Git based on registry state.
4. Flux reconciles Git to the cluster.

Flux's notification controller and receivers are the key pieces for event-driven refresh. Flux documents that the notification controller handles inbound events from external systems and can notify GitOps toolkit controllers about source changes. Flux receivers can accept webhook events and request reconciliation of referenced resources. Flux also documents image-update workflows where registry webhooks notify Flux image automation about new tags.

That means Buildkite does not need to "be" the deploy engine in a Flux-based system. It only needs to produce the desired state transition:

- push image
- optionally commit manifest/tag update to Git
- optionally call a Flux receiver or run `flux reconcile` to accelerate convergence

For strict GitOps, the cleanest pattern is still "Buildkite writes Git, Flux deploys from Git." If Buildkite directly mutates the cluster, you are no longer getting the full value of Flux as the source of truth.

Where the legacy "hybrid GitOps" idea still matters is dynamic environments. Flux is excellent when environments are represented as Git-managed desired state. It is much less of a productized answer to "I need an API that provisions and destroys preview environments on demand, tracks ownership, TTL, and metadata, and presents them as business objects."

So static environments map well to Flux. Dynamic environments may still need a custom API layer that generates Git state or Kubernetes objects on demand.

## 6. What Buildkite still does not do

Even with Buildkite plus Flux, the following are still outside native coverage:

### 6.1 Postgres CDC and domain events

Buildkite does not replace Debezium. If your platform still depends on "state changes in Postgres become events for other systems," that remains a separate concern.

If the old design used CDC mainly because the custom CI platform had invented too many internal state transitions, the better move may be to delete that requirement rather than re-implement it.

### 6.2 Environment management as a product surface

Buildkite has pipelines and builds. Flux has sources and reconciliation. Neither gives you a native environment-management API equivalent to a bespoke FastAPI service that can do things like:

- create preview env X for PR Y
- assign owner/team
- enforce quota and TTL
- expose environment status/history via API
- implement custom approval or promotion semantics

If the product still needs "environment" to be a first-class managed concept, a custom service is still needed.

### 6.3 Durable asynchronous orchestration

Webhooks and triggers are enough for many CI/CD integrations, but not for a true asynchronous platform bus. If you still need replay, backpressure handling, many independent consumers, or event sourcing, Kafka-class infrastructure remains separate.

### 6.4 Shared mutable workflow state

Buildkite metadata and artifacts are not substitutes for distributed counters, leases, and atomic ephemeral state. If the design still requires those semantics, Redis or another fit-for-purpose store remains necessary.

### 6.5 Cross-system observability and search

Buildkite has job logs, Waterfall view, queue metrics, cluster insights, audit logs, build exports, and observability integrations including EventBridge and OpenTelemetry. That is far better than "just raw logs in a CI UI."

But it is still CI-centric observability, not a general replacement for Elasticsearch/Kibana if you want:

- unified search across CI, deployer, environment API, and cluster events
- long-retention full-text log analytics
- cross-system incident forensics in one place

If the new platform collapses enough custom services, the need for Elasticsearch may disappear. If multiple custom services remain, an external observability stack is still justified.

## 7. Pricing

As of 2026-04-11, Buildkite's pricing page shows:

- Personal: $0, free forever, 1 user, 3 concurrent jobs total, 90-day build retention
- Pro: $30 USD per active user per month, unlimited users, 1-year retention, first 10 self-hosted agents included, then $2.50 USD per concurrent self-hosted agent per month
- Enterprise: custom pricing, volume discounts, audit logs, build exports, pipeline templates, advanced governance

Hosted agents are separate pay-as-you-go compute:

- Linux Small, 2 vCPU / 4 GB: $0.013/min
- Linux Medium, 4 vCPU / 16 GB: $0.026/min
- Linux Large, 8 vCPU / 32 GB: $0.052/min
- Mac M4 Medium, 6 vCPU / 28 GB: $0.18/min
- Mac M4 Large, 12 vCPU / 56 GB: $0.36/min

The pricing FAQ also says self-hosted concurrent agent usage is billed using a 95th-percentile method, which matters for bursty workloads. Buildkite hosted agents are not subject to the self-hosted concurrent-agent fee model.

The practical implication is:

- if you run self-hosted agents on Kubernetes, Buildkite is mainly a control-plane subscription plus per-user/per-agent economics
- if you use hosted agents, Buildkite pricing becomes much closer to "SaaS control plane plus per-minute compute"

## Conclusion

The legacy spec can be simplified substantially.

Buildkite should be treated as the native CI workflow engine and execution scheduler. Flux should be treated as the native GitOps reconciler. With those two choices, the old Dagger-plus-custom-control-plane architecture is probably overbuilt unless the product still genuinely needs:

- environment lifecycle as a first-class API
- durable platform events beyond CI notifications
- database CDC as a core feature
- shared mutable orchestration state
- cross-system observability across several custom services

If those needs are dropped or reduced, the replacement architecture becomes much smaller:

- Buildkite for CI orchestration and agent dispatch
- Kubernetes for job/runtime isolation and autoscaling
- registry plus artifacts/package storage for outputs
- Flux for CD and reconciliation
- optionally one thin custom service only for preview-environment or policy workflows

That is the key answer to the legacy-platform comparison: Buildkite replaces the bespoke CI backbone far more than it replaces the bespoke platform layer.

## Sources

- Buildkite dynamic pipelines: https://buildkite.com/docs/pipelines/configure/dynamic-pipelines
- Buildkite step dependencies: https://buildkite.com/docs/pipelines/configure/dependencies
- Buildkite matrix builds: https://buildkite.com/docs/pipelines/configure/workflows/build-matrix
- Buildkite trigger steps: https://buildkite.com/docs/pipelines/trigger-step
- Buildkite Agent Stack for Kubernetes overview: https://buildkite.com/docs/agent/self-hosted/agent-stack-k8s
- Buildkite Agent Stack for Kubernetes running builds: https://buildkite.com/docs/agent/self-hosted/agent-stack-k8s/running-builds
- Buildkite clusters and queues: https://buildkite.com/docs/pipelines/security/clusters
- Buildkite outgoing webhooks: https://buildkite.com/docs/apis/webhooks/pipelines
- Buildkite incoming pipeline triggers: https://buildkite.com/docs/apis/webhooks/incoming/pipeline-triggers
- Buildkite Builds API: https://buildkite.com/docs/apis/rest-api/builds
- Buildkite metadata: https://buildkite.com/docs/builds/build-meta-data
- Buildkite caching guidance: https://buildkite.com/docs/pipelines/best-practices/caching
- Buildkite Package Registries: https://buildkite.com/docs/package-registries
- Buildkite observability overview: https://buildkite.com/docs/pipelines/integrations/observability/overview
- Buildkite build exports: https://buildkite.com/docs/pipelines/governance/build-exports
- Buildkite pricing: https://buildkite.com/pricing/
- Flux notification controller: https://fluxcd.io/flux/components/notification/
- Flux notification API reference (`Receiver`): https://fluxcd.io/flux/components/notification/api/v1/
- Flux image update guide: https://fluxcd.io/flux/guides/image-update/
