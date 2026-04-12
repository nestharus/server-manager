# Phase 1 Research: Environments, Benchmarking, LLM Video QA, and Vultr VKE

Date: 2026-04-11

## Notes on inputs

The prompt names three local background files that are not present in this checkout:

- `plans/proposals/phase1-foundation.md`
- `plans/platform-decisions-overlay.md`
- `plans/unified-platform-index.md`

I was therefore not able to read them directly. For local context, this research uses the available artifacts instead:

- `plans/risk/phase1-audit.md`
- `plans/risk/phase1-scope.md`
- `plans/risk/phase1-shortcut.md`
- `.tmp/d8-platform-decisions.md`
- the current `infra/` and `k8s/` draft

Where this document cites Vultr, Flux, Buildkite, Playwright, Gemini, or MiniMax behavior, those claims are based on current official documentation or changelog material. Where this document recommends a Phase 1 shape or release gate, that is my synthesis for this platform rather than a vendor quote.

## Executive summary

The three-environment split is correct for this platform, but only if the environments are used asymmetrically. `dev` should be the default working environment and stay persistent. `production` should stay persistent and receive only reviewed promotions. `staging` should not be treated as a mini-production clone that every change must pass through; for a one-person plus agents team, that becomes cost and ceremony without enough signal. Instead, staging should be an on-demand, production-shaped validation lane used for release candidates that need benchmark, load, or infrastructure validation. The primary promotion flow should therefore be `dev -> production` for ordinary functional changes, with `dev -> staging -> production` only when a change is performance-sensitive, infra-heavy, or otherwise risky enough to justify a temporary full-size cluster.

For this platform, “benchmarking” should not mean generic microbenchmarks. It should mean repeatable release-candidate performance and resilience measurements for the parts that actually matter: FastAPI request latency and throughput, async pipeline latency for OCR and LLM-backed jobs, database latency, pod readiness time, Flux reconciliation time, and Discord daemon recovery behavior. The baseline is not something that exists today; the first useful benchmark run will establish it on production-equivalent staging hardware. The Phase 1 deliverable should therefore be the benchmark definition, runner choice, storage path, and release-policy shape, not a full benchmark suite. Meaningful benchmark enforcement belongs once real application workloads exist.

The LLM video QA pipeline is viable for the future web UI, but it should enter Phase 1 only as a dev-facing workflow, not as a hard CI gate. For a form-heavy TanStack UI, “intent” is not aesthetic critique; it is a structured statement of expected visible behavior for a scenario such as filling a form, seeing validation, navigating steps, or confirming submission state. Gemini is currently the realistic option because Google’s Gemini stack explicitly supports video understanding. I did not find comparable official MiniMax documentation for video understanding; MiniMax’s public docs show video generation, not video-evaluation capability.

On Vultr, the main provider implications are straightforward. The current local draft already moved to VKE and three environments, but it still carries Hetzner leftovers in Kubernetes storage classes and a Flux bootstrap shape that is too single-cluster-centric. Vultr VKE supports current Kubernetes releases, exposes node-pool autoscaling through min/max bounds, uses Vultr-managed cloud integration for `Service type: LoadBalancer`, and includes managed CSI support with storage classes such as `vultr-block-storage`, `vultr-block-storage-hdd`, and `vultr-vfs-storage`. The immediate local-code gap is not “more infrastructure”; it is cleaning the provider migration, fixing multi-environment GitOps structure, and deciding what Phase 1 intentionally defers.

## 1. Environment model

### Is `dev` + `staging` + `production` the right split?

Yes, but only with strict role separation.

For a one-person team, three always-on environments are usually too much. That is not the proposal here, though. The proposed shape is one cheap persistent dev cluster, one on-demand production-shaped staging cluster, and one persistent production cluster. That is a reasonable split because each environment has a different job:

- `dev`: fast iteration, integration smoke, E2E, UI development, and exploratory work
- `staging`: temporary benchmark and release-candidate validation lane on production-equivalent sizing
- `production`: real user traffic and the only environment that must remain stable over time

That split avoids the common failure mode where staging becomes an underused permanent clone that still costs money and still drifts from prod. In this model, staging is not a place people casually test features. It is a tool you instantiate when you need high-confidence answers about performance, rollout behavior, or infra changes.

### Promotion flow

The right flow is not “always dev -> staging -> production.” For this platform, the better rule is:

- Default path: `dev -> production`
- Elevated path: `dev -> staging -> production`

Use the elevated path when one or more of these are true:

- the change alters infrastructure, autoscaling, storage classes, ingress, or GitOps layout
- the change is performance-sensitive and needs a benchmark comparison
- the change affects async throughput or backpressure behavior
- the change could create production-only failure modes because it depends on realistic cluster size

This matters because the platform is not a consumer SaaS with dozens of daily deploys and a staffed release team. Adding a mandatory staging hop for every UI copy change or internal API refactor will slow the operator down without proportionate risk reduction. Staging should be a side-channel for high-value validation, not a universal gate.

### What differs between environments

Node sizing is only the visible difference. The more important environment differences are configuration and external integration boundaries.

These should differ per environment:

- secrets and API keys
- database and storage targets
- ingress hostnames and TLS material
- observability labels, alert routing, and retention
- Buildkite queue selection or agent tags
- benchmark profiles and allowed load levels
- any outbound webhook endpoints

These should usually also differ, or at minimum be isolated by namespace/account:

- Discord application credentials
- Supabase or Postgres database
- object storage bucket or prefix
- Gemini or OCR billing project labels
- Sentry environment name

The Discord point is especially important. A dev cluster that talks to the live Humility server is not really “dev”; it is another production mutation surface. If a separate Discord test guild or test application does not exist yet, that is an operational gap. It does not block all Phase 1 work, but it does mean non-production Discord integration testing is weaker than the rest of the stack.

Feature flags should not be the main environment separator. This repo’s rules already reject compatibility shims, and that discipline should continue here. Environment differences should primarily be data, credentials, endpoints, and scale characteristics, not divergent behavior toggles.

### Flux multi-environment shape

For Flux, path-based multi-environment management from one repository is the right answer. Branch-per-environment adds unnecessary merge complexity and makes environment drift harder to reason about. Separate repos are overkill at this scale and weaken the “single source of truth” property that GitOps is supposed to give you.

The pattern Flux pushes people toward is cluster- or environment-specific paths. Their docs and examples show bootstrapping a cluster to reconcile a specific repository path such as `/clusters/my-cluster/`, and their promotion examples keep staging and production manifests in separate paths while promotions are performed by changing Git content rather than hand-editing clusters.

For this repo, that implies something closer to:

- `k8s/clusters/dev/`
- `k8s/clusters/staging/`
- `k8s/clusters/production/`
- shared `k8s/infrastructure/...`
- shared or environment-specific `k8s/apps/...`

The current local draft is not there yet. It has `k8s/overlays/dev`, `staging`, and `production`, but the Flux bootstrap README points at `k8s/base/flux-system`, which is effectively a single root. That is too narrow for three clusters. Each cluster should bootstrap Flux against its own environment root path, and that root should compose the relevant shared infrastructure and environment-specific patches.

## 2. Benchmarking for this platform

### What “benchmarking” should mean here

For this platform, benchmarking should mean repeatable measurement of release-candidate behavior under controlled load on production-like hardware. It should not mean:

- Python microbenchmarks of individual functions
- one-off `hey` runs from a laptop with no stored baseline
- generic cluster stress tests with no link to user-facing outcomes

The platform has four benchmark surfaces:

1. HTTP/API performance
2. asynchronous pipeline latency
3. platform/cluster convergence behavior
4. daemon resilience and reconnect behavior

That yields a concrete benchmark taxonomy.

### Metrics that matter

Primary metrics:

- API latency: p50, p95, p99 by endpoint class
- API throughput: sustained requests per second at acceptable error rate
- error rate: especially timeout, 5xx, and 429 rates
- database query latency: p95 for critical query families
- memory and CPU usage under load: by service and by node
- pod readiness time: image pull to Ready
- rollout convergence time: deploy start to all pods healthy
- Flux reconciliation duration and failure count
- async job latency: submission to final result for OCR and LLM-backed pipelines
- Discord daemon reconnect time and event-processing lag

Secondary metrics:

- storage provisioning time for PVC-backed services
- load balancer provisioning time for new public services
- queue depth growth and drain time
- container restart count and OOM kills

For the TanStack web UI itself, raw frontend performance metrics are useful but not the first benchmark target. In this product, user risk is more about correctness of flow, submit latency, and visible state transitions than animation smoothness or FPS.

### Tooling

The most practical default is:

- `k6` for HTTP and API load tests
- Playwright for scripted end-to-end scenario timing and video capture
- Prometheus/Grafana for collecting cluster and application metrics during the run
- targeted application instrumentation for queue latency and provider-call timings

`k6` is the strongest Phase 1 candidate because it is good at HTTP workloads, integrates cleanly with Kubernetes-based execution patterns, and maps well to FastAPI request benchmarking. Locust is still viable later if you want more Python-native, user-behavior-heavy scenarios, but it should not be the first choice unless the team already wants Python-based load definitions. `pytest-benchmark` is useful for code-level microbenchmarks, but it does not solve the actual release-candidate benchmarking problem here.

### Baseline and pass/fail gate

The first staging benchmark run on production-equivalent sizing establishes the baseline. That baseline should be tied to:

- Git commit or release tag
- environment profile
- dataset shape
- benchmark scenario version

Baselines must be profile-specific. Dev numbers from a one-node `$10/mo` cluster are not comparable to staging numbers from a production-shaped cluster.

My recommended release gate is:

- critical API p95 regression must stay within 10% of baseline
- critical API p99 regression must stay within 15% of baseline
- error rate must not worsen materially under the same load shape
- async pipeline latency must stay within an agreed SLO band
- no OOM kills, crash loops, or sustained queue growth during the run

Those thresholds are not vendor defaults; they are a pragmatic starting point. Tighten them only after enough historical runs exist to know normal variance.

### Where results should live

Raw benchmark artifacts should not live in Git. Git is correct for benchmark definitions, runner config, and small summary reports, but not for repeated JSON results, time series dumps, or Playwright videos.

The simplest Phase 1 storage model is:

- store raw artifacts in object storage or Buildkite artifacts
- store a machine-readable summary alongside the release record
- optionally commit a short markdown summary for important release candidates

If Vultr object storage is already part of the platform for Terraform state and future artifacts, a separate prefix or separate bucket for benchmark results is the cleanest answer. Do not mix benchmark artifacts into the Terraform state location.

### Phase 1 or later?

Meaningful benchmarking is mostly Phase 2+, because Phase 1 has no real application workloads yet. Phase 1 should include:

- the benchmark definition
- the selected runner
- the artifact storage path
- the release-gate policy
- any minimal scaffolding needed so staging can execute benchmark jobs later

Phase 1 should not include building a large benchmark suite against imaginary endpoints. That becomes fake certainty.

## 3. LLM video QA pipeline

### How it transfers from visual-code-editor to this web UI

The transfer is conceptually sound, but the target changes. In an animation-heavy visualization product, the model is judging motion quality, continuity, and rendering correctness. In a form-driven TanStack web UI, the model should judge whether the user-visible workflow matches the intended scenario.

That means the Playwright capture remains useful, but the prompt has to change from aesthetic or animation critique to workflow validation.

For this platform, an “intent” should be a structured scenario statement like:

- starting page and viewport
- user actions performed by Playwright
- expected visible states after each action
- disallowed outcomes
- final success condition

Example intents:

- “Submitting an incomplete application form must surface inline validation near the missing fields and must not navigate away.”
- “Approving a submission from the officer dashboard must show a visible success state and remove the item from the pending list.”
- “On mobile width, the multi-step form must remain navigable without clipped buttons or overlapping text.”

That is much more precise than “does this UI look good?”

### CI or human-in-the-loop?

It can run in CI, but it should begin as advisory, not blocking. Buildkite supports block steps, which is useful for cases where you want the pipeline to pause for a human decision after artifacts and model output are available. Playwright also already gives you deterministic browser automation and video capture. That combination is enough to run the pipeline in CI.

The reason not to make it a hard gate immediately is not tooling. It is evaluation stability:

- model judgments can vary
- clips can contain noise
- low-confidence visual issues still need human arbitration
- costs rise quickly if every PR records and analyzes many videos

Recommended rollout:

- Phase 1 or early Phase 2: run in dev and optionally on selected CI jobs, advisory only
- later: gate high-risk UI changes or release candidates
- use a human unblock step when the model reports ambiguity or confidence below threshold

### Gemini vs MiniMax

Gemini is the realistic option today. Google’s Gemini stack explicitly supports video understanding, which is the core requirement here. I did not find equivalent official MiniMax documentation for video understanding or video-evaluation APIs. MiniMax’s public API docs do show video generation and a video agent, but that is a different capability. On current evidence, MiniMax is not a safe planning assumption for this QA pipeline.

### Phase 1 or later?

The full CI-gated video QA system is later than Phase 1. What belongs in Phase 1 is:

- reserving the workflow shape
- confirming the provider choice
- proving that Playwright can record the relevant flows in dev

What does not belong in Phase 1:

- broad CI enforcement
- production release gating on LLM video judgment
- large prompt libraries for many screens before the UI exists

## 4. Vultr VKE specifics

### Kubernetes versions

Vultr’s current VKE changelog shows active releases in the 1.33, 1.34, and 1.35 lines, with 1.35.2+1 called out in late March 2026. That means the local default `v1.31.0+1` in `infra/variables.tf` is stale and should not be treated as valid planning input. Phase 1 should pin to a currently supported VKE release line, then review that pin before implementation starts.

### Node pool autoscaling

The Terraform resource shape in the local draft matches the provider model: autoscaling is configured per node pool with `auto_scaler`, `min_nodes`, and `max_nodes`. That is the right primitive. The missing piece is policy.

Recommended policy:

- `dev`: do not autoscale above the budgeted floor unless there is a concrete reason
- `staging`: production-like bounds when benchmarking
- `production`: conservative min and explicit max tied to budget and expected concurrency

I did not find a clearly documented Vultr-specific scale-down grace period in the official material reviewed. Treat timing behavior as implementation-dependent and verify it empirically before relying on it as part of an SLO.

### Networking and future Calico plans

VKE currently runs with Calico in the managed stack; Vultr’s changelog entries explicitly mention Calico version updates. That means a later “introduce Calico” phase should not assume a blank slate. The platform is already getting Calico as part of VKE’s managed networking. The practical implication is: do not plan to replace the cluster CNI in Phase 1. If later phases need Calico network policy features, verify what VKE already exposes before layering additional assumptions on top.

VKE clusters also sit on Vultr VPC networking. Vultr documents that current VKE is not compatible with VPC 2.0 and uses legacy VPC-based networking. That matters mostly as a provider constraint, not a Phase 1 blocker.

### Flux integration

I did not find evidence of a Vultr-specific Flux incompatibility. The real integration work is ordinary Kubernetes GitOps:

- bootstrap Flux into each cluster
- point each cluster at its own environment path
- keep shared infrastructure in reusable bases
- promote by changing Git, not by clicking the cluster

So the Phase 1 concern is not “Does Flux work on VKE?” It does. The concern is “Is the repo structured so Flux can express three environments cleanly?” Right now, not yet.

### Load balancer behavior

Vultr provides Kubernetes cloud integration so that `Service type: LoadBalancer` provisions a Vultr Load Balancer. Recent VKE changelog entries also mention fixes around load balancer status and added UDP support in newer cluster releases. That is enough to treat Vultr CCM-backed service exposure as the standard path. Phase 1 does not need to expose public services yet, but the provider behavior is conventional.

### Persistent volumes and storage classes

VKE includes managed CSI support. Vultr’s storage documentation describes these main storage classes:

- `vultr-block-storage` for NVMe-backed RWO volumes
- `vultr-block-storage-hdd` for HDD-backed RWO volumes
- `vultr-vfs-storage` for RWX file storage in supported regions

This creates an immediate local-code issue: the current monitoring HelmRelease still uses `hcloud-volumes`, which is a Hetzner storage class and will not work on Vultr. That is not a subtle mismatch; it is a direct provider migration bug.

## 5. Scope assessment against the current draft

### What belongs in Phase 1

These belong in Phase 1:

- Vultr VKE provisioning for `dev`, `staging`, and `production`
- path-based Flux multi-environment repository layout
- secrets bootstrap sufficient for the foundation
- baseline cluster observability
- environment configuration model and promotion policy
- benchmark definition and storage plan
- a light proof that Playwright capture for UI flows works in dev

### What does not belong in Phase 1

- a mandatory benchmark gate for every release
- a large benchmark suite before real services exist
- CI-blocking LLM video QA
- production ingress, auth, and broader app-delivery surface unless Phase 1 explicitly expands scope
- replacing VKE networking with custom CNI work
- full secret-management migration beyond bootstrap needs

### Is the current `infra/` + `k8s/` draft correctly scoped?

Mostly, but it has three clear problems.

First, the provider migration is incomplete. The Terraform files are Vultr-oriented, but Kubernetes manifests still reference Hetzner storage classes.

Second, the Flux shape is too single-cluster-oriented. A three-environment platform needs per-cluster roots, not a single bootstrap path under `k8s/base/flux-system`.

Third, autoscaling and environment behavior are encoded too mechanically. `min = worker_count` and `max = worker_count * 2` everywhere is a placeholder, not an environment policy.

The draft does get some Phase 1 scoping right:

- staging is modeled as on-demand and production-shaped
- monitoring and secrets are kept foundation-level
- there is no premature public ingress stack

### What is missing from Phase 1 in the code

Missing or under-specified:

- a real Flux repository structure for three clusters
- provider-correct storage classes
- environment-specific secret and external endpoint strategy
- benchmark runner location and artifact-storage decision
- explicit Discord non-production integration story
- release promotion policy document that says when staging is required

## Conclusion

The direction is sound, but the right interpretation of the new Phase 1 is narrower and sharper than “build three full environments and benchmark them.” Build one real daily-use dev cluster, one real production cluster, and one reproducible staging profile that is instantiated only when a release candidate needs production-shaped validation. Use Flux path-based multi-environment GitOps from a single repo. Define benchmarking now, but defer meaningful benchmark enforcement until actual services exist. Treat Gemini-based video QA as a future advisory workflow, not a Phase 1 hard gate. On Vultr, fix the provider migration details first; the most immediate local issue is that the repository still contains Hetzner assumptions in Kubernetes manifests and a GitOps layout that is not yet multi-environment-native.

## Sources

- Vultr VKE changelog: https://docs.vultr.com/public/doc-assets/pdfs/collection_item/products-kubernetes-changelog.pdf
- Vultr persistent storage on VKE: https://docs.vultr.com/public/doc-assets/pdfs/article/how-to-provision-persistent-volume-claims-on-vultr-kubernetes-engine.pdf
- Vultr VKE VPC networking note: https://docs.vultr.com/support/products/vke/can-i-connect-my-vke-cluster-to-a-vpc2-network
- Flux get started / path-based bootstrap example: https://v2-0.docs.fluxcd.io/flux/get-started/
- Flux promotion example: https://fluxcd.io/flux/use-cases/gh-actions-helm-promotion/
- Buildkite block step docs: https://buildkite.com/docs/pipelines/configure/step-types/block-step
- MiniMax API docs release notes: https://platform.minimax.io/docs/release-notes/apis
