# Phase 1 Foundation v2 — Vultr VKE with 3-environment model

Date: 2026-04-11

Input note: `plans/proposals/phase1-foundation.md`, `plans/platform-decisions-overlay.md`, and `plans/unified-platform-index.md` were not present in this checkout when this proposal was written. This proposal is grounded in `plans/research/phase1-environments-and-benchmarks.md`, `.tmp/d8-platform-decisions.md`, `.tmp/beta-guild.txt`, the current `infra/` and `k8s/` drafts, and current official Vultr, Buildkite, and Google Gemini documentation as of April 11, 2026.

## 1. Executive summary

Phase 1 Foundation v2 defines the minimum platform substrate for a production-ready Humility stack on Vultr Kubernetes Engine (VKE). It replaces the earlier Hetzner-based foundation shape with a managed-Kubernetes design that keeps the control plane free, uses Vultr-managed cloud integrations for load balancers and block storage, and treats multi-environment GitOps as a first-class concern instead of a later retrofit.

The environment model is asymmetric by design. `dev` is persistent and cheap, and becomes the default daily integration lane for API, Discord daemon, UI, end-to-end checks, and advisory LLM video QA. `production` is persistent and conservative. `staging` exists as an on-demand, production-shaped benchmark lane rather than a permanently running clone. The default promotion path is `dev -> production`. The elevated path is `dev -> staging -> production`, used only for performance-sensitive, infra-heavy, or otherwise production-shape-dependent changes.

This proposal keeps Phase 1 narrow. It includes Vultr VKE provisioning, OpenTofu layout for three isolated environments, Flux CD restructured around per-cluster roots, sealed-secrets bootstrap, basic observability with Prometheus/Grafana/Alertmanager, benchmark definition plus runner selection, and a single proof-of-concept Playwright-to-Gemini video QA run in dev. It does not include a full benchmark suite, CI-blocking video QA, Infisical, or a broad public ingress surface.

Two repo-level corrections are mandatory in this version. First, Kubernetes manifests still contain Hetzner storage-class assumptions such as `hcloud-volumes`; these must be replaced with Vultr storage classes. Second, the current Flux bootstrap path is effectively single-cluster-centric (`k8s/base/flux-system`); it must move to per-cluster roots so each environment reconciles its own path.

This proposal also adopts the locked API-first principle as a cross-cutting platform rule: every product capability is exposed through an API endpoint, and both the web UI and Discord daemon are clients of that API. Phase 1 does not implement the application surface, but it must not make later API-first delivery harder.

## 2. Environment model

The correct environment shape for this platform is three environments with different jobs, not three identical clusters. The repository already points in this direction in `infra/environments/`, and the research confirms the operational rule: one cheap persistent dev cluster, one persistent production cluster, and one production-shaped staging profile that is instantiated only when a release candidate needs it.

### Dev

`dev` is persistent. It is the daily integration target for the API, Discord daemon, future TanStack web UI, Flux changes, observability checks, and the first advisory LLM video QA workflow. Its purpose is not to emulate production perfectly; its purpose is to provide a stable place where the whole stack runs together without turning every test into a live production mutation. Because it persists, it accumulates the operational knowledge that ephemeral preview environments do not.

The dev cluster should be the smallest configuration that still runs Flux, sealed-secrets, and `kube-prometheus-stack` without constant churn. In the current draft that means a single `vc2-1c-2gb` worker. That is a valid Phase 1 floor. Dev should have short metrics retention, lower storage requests, and non-production integrations only.

### Staging

`staging` is on-demand. It exists for release-candidate validation, benchmarks, and infrastructure-heavy rehearsals. It should not be left running by default. It is the answer to questions such as: does this change alter p95 latency, does a storage-class change reconcile cleanly on production-shaped hardware, does the autoscaler behave sensibly under realistic load, and does the Discord daemon reconnect fast enough when the cluster rolls.

Staging should use production-equivalent worker sizing so its benchmark results mean something. If staging is much smaller than production, it stops being a benchmark lane and becomes just another dev cluster with more ceremony. When the benchmark window is over, staging should be destroyed and later recreated from the same OpenTofu and Flux definitions.

### Production

`production` is persistent and conservative. It is where the real Discord guild integration, real API endpoints, and eventually the real web surface live. Production gets longer retention, stricter secret hygiene, real alert routing, and no experimental integrations. Production is not the place to discover whether a cluster layout works.

### Promotion flow

The default promotion path is:

`dev -> production`

Use this path for ordinary functional changes such as API endpoint additions, internal refactors, application logic changes, UI fixes that do not materially change runtime shape, or secret rotations that do not alter cluster behavior.

The elevated promotion path is:

`dev -> staging -> production`

Staging is required when one or more of the following are true:

- the change alters OpenTofu-managed infrastructure, node sizing, autoscaling bounds, or networking
- the change changes storage classes, PVC behavior, or reconciliation order
- the change is performance-sensitive and needs a baseline comparison
- the change materially affects async pipeline throughput or backpressure behavior
- the change relies on production-like cluster shape to reveal failure modes
- the change introduces or revises benchmarking logic itself

This is the key discipline that keeps the three-environment model affordable. Staging is a special lane, not a mandatory hop for every release.

### Configuration differences

Environment differences must be explicit and boring. They should live in credentials, endpoints, DNS, and retention policies, not in compatibility shims or behavior forks.

The following must differ per environment:

- database credentials and database names
- Discord bot token and guild ID
- object-storage prefixes and artifact paths
- TLS certificates and hostnames
- alert routing, Grafana credentials, and retention
- API base URLs and external webhook endpoints
- benchmark profiles and allowed load levels
- any future feature flags used for true environment safety, not legacy behavior

The following should be kept structurally identical wherever possible:

- namespace layout
- core chart set
- Kustomization composition pattern
- controller versions
- API contract shape

### Discord bot integration per environment

Discord isolation is part of the environment model, not an afterthought. A dev cluster pointed at the live Humility guild is not meaningfully dev.

The environment mapping should be:

- `production`: production bot token + Humility guild ID `900000000000000001`
- `staging`: non-production bot token or the same application with a separate staging token path, plus staging guild ID `1492663622458151003`
- `dev`: separate dev bot token and a non-production guild; if a separate dev guild does not exist yet, dev must not silently target production

At minimum, staging already has a known guild target from `.tmp/beta-guild.txt`. Phase 1 should formalize environment variables so each deployment has its own `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID`. This is also where the API-first rule matters: the Discord daemon should be an environment-specific client of the API, not a special path that bypasses environment boundaries.

## 3. Vultr VKE specification

VKE is the correct provider choice for this phase because it gives a managed control plane at no extra charge, exposes node-pool autoscaling, includes the Vultr Cloud Controller Manager (CCM) and CSI integration, and avoids a large amount of kube bootstrap work that would distract from the real platform problem.

### Per-environment cluster configuration

Phase 1 should standardize on the following worker shapes:

- `dev`: 1 x `vc2-1c-2gb`
- `staging`: 3 x `vc2-2c-4gb`
- `production`: 3 x `vc2-2c-4gb`

These match the current draft in `infra/environments/` and are directionally correct. The current mechanical autoscaling placeholder of “max = current count * 2” should be replaced with explicit per-environment policy:

- `dev`: min 1, max 2
- `staging`: min 3, max 6
- `production`: min 3, max 5

That is still conservative, but it stops pretending that every environment wants the same multiplier. Dev only needs enough headroom for short spikes and controller restarts. Staging wants room for benchmark-induced pressure. Production wants bounded elasticity that stays inside budget.

VKE versioning must also be corrected. The draft default `v1.31.0+1` in `infra/variables.tf` is stale. Vultr’s official VKE changelog, updated March 23, 2026, lists current supported lines in 1.33.x, 1.34.x, and 1.35.x, with `v1.35.2+1` current in March 2026. Phase 1 should pin to a currently supported line at implementation start rather than inheriting the stale default from draft code. The proposal recommendation is:

- initial target: VKE `1.35.x`, specifically the current supported patch at implementation start
- fallback target: `1.34.x` only if implementation-time validation finds a provider or chart incompatibility

### VKE networking

VKE uses Calico as its default CNI. That has two implications.

First, Phase 1 should not plan to “introduce Calico later” as though the cluster were currently neutral. Calico is already there in the managed stack. Later phases can decide whether to use more of Calico’s network-policy surface, but they should not assume a blank slate or attempt to replace the cluster CNI during the foundation phase.

Second, this keeps the networking story simple for Phase 1. VKE’s managed networking plus Calico is enough for a first production substrate. The proposal explicitly rejects custom CNI work in Phase 1.

VKE also remains on Vultr’s legacy VPC networking model rather than VPC 2.0. This is a provider constraint, not a blocker. It matters for future network design, but it does not change the Phase 1 cluster shape.

### Storage classes

The current repo still has a direct provider migration bug: monitoring manifests reference `hcloud-volumes`. On Vultr, the relevant storage classes are:

- `vultr-block-storage` for NVMe-backed block storage
- `vultr-block-storage-hdd` for HDD-backed block storage
- `vultr-vfs-storage` for Vultr File System, available in newer VKE lines but not needed for this phase

Phase 1 should use `vultr-block-storage` for Prometheus, Grafana, and Alertmanager PVCs. The reasons are simple:

- NVMe block volumes have a 10 GB minimum, while HDD volumes start at 40 GB
- Prometheus benefits from lower-latency storage
- the monitoring footprint in Phase 1 is small, so HDD does not save money

`vultr-block-storage-hdd` should remain available for future, colder, larger-capacity workloads, but it should not be the default storage class for observability in Phase 1.

### Load balancer behavior

VKE includes the Vultr Cloud Controller Manager. When a Kubernetes `Service` of type `LoadBalancer` is created, the CCM provisions and manages a Vultr Load Balancer and wires traffic to the backing pods. This is the conventional cloud-native path and should be the only Phase 1 load-balancer strategy.

Phase 1 does not need a broad public ingress surface, but it must keep that path clean:

- do not hand-build external load balancers outside Kubernetes
- do not invent a second exposure mechanism beside `Service type: LoadBalancer`
- do not bake ingress assumptions into the cluster before a real API/UI public surface exists

The design rule is: when a service needs public exposure later, it goes through the Vultr CCM path and is represented in GitOps-managed manifests.

## 4. OpenTofu structure

The current `infra/` draft already demonstrates the correct instincts: environment-specific `terraform.tfvars`, per-environment backend keys, and a Vultr provider. The missing piece is making the structure intentionally multi-environment instead of a single root with environment files attached to it.

The recommended OpenTofu layout is:

```text
infra/
  modules/
    vke-cluster/
    object-storage/
  environments/
    dev/
      main.tf
      backend.tfbackend
      terraform.tfvars
    staging/
      main.tf
      backend.tfbackend
      terraform.tfvars
    production/
      main.tf
      backend.tfbackend
      terraform.tfvars
```

`modules/vke-cluster` owns the reusable cluster logic: provider settings, VKE cluster definition, node pools, outputs, and shared labels or tagging conventions. `modules/object-storage` can own the S3-compatible bucket definitions used for state and artifacts if the provider coverage is sufficient at implementation time. Each environment directory is its own root module and state boundary.

### Per-environment backend isolation

State isolation must be per environment. The current backend keys already point the right way:

- `infra/dev/terraform.tfstate`
- `infra/staging/terraform.tfstate`
- `infra/production/terraform.tfstate`

That pattern should remain. Each environment should be initialized independently against the same object-storage bucket or state bucket set, with distinct keys and distinct credentials scopes where possible.

The proposal recommendation is one shared state bucket with separate keys in Phase 1, plus:

- server-side encryption if supported
- credentials restricted to named operators and CI
- single-writer discipline per environment

The current draft uses `use_lockfile = true` for the S3 backend. That is directionally correct. Implementation should verify the behavior against Vultr Object Storage and document the operational guarantee rather than assuming AWS-native semantics.

### Variable hierarchy

Variable handling should be three-tiered:

1. Common defaults in shared module variables
2. Environment-specific overrides in `environments/*/terraform.tfvars`
3. Sensitive values injected at runtime via environment variables or secret files outside Git

The common layer should own:

- cluster naming convention
- default region
- default supported Kubernetes version line
- label and tagging conventions

The environment layer should own:

- worker plan
- min/max autoscaler bounds
- environment name
- any DNS naming prefixes

Sensitive runtime inputs should own:

- Vultr API key
- state bucket credentials
- future DNS provider credentials

This structure keeps the environment contract explicit and prevents the root module from degenerating into a pile of conditionals.

## 5. Flux CD multi-environment structure

This is the biggest structural correction in v2. The current repo has `k8s/overlays/dev`, `staging`, and `production`, but Flux bootstrap documentation still points at `k8s/base/flux-system`. That is effectively a single-cluster root. It does not scale cleanly to three independent clusters.

The recommended Flux layout is:

```text
k8s/
  clusters/
    dev/
      flux-system/
      kustomization.yaml
      infrastructure.yaml
      apps.yaml
    staging/
      flux-system/
      kustomization.yaml
      infrastructure.yaml
      apps.yaml
    production/
      flux-system/
      kustomization.yaml
      infrastructure.yaml
      apps.yaml
  infrastructure/
    base/
      secrets/
      monitoring/
    overlays/
      dev/
      staging/
      production/
  apps/
    base/
    overlays/
      dev/
      staging/
      production/
```

### Path-based per-cluster roots

Each cluster bootstraps Flux against its own path:

- dev Flux watches `k8s/clusters/dev`
- staging Flux watches `k8s/clusters/staging`
- production Flux watches `k8s/clusters/production`

That means each cluster has its own generated `gotk-*` files under its own `flux-system` directory and its own root Kustomization. No cluster watches the generic base path. This is the correct GitOps boundary.

### Base -> overlays -> environment

Shared platform components such as sealed-secrets and monitoring live under `k8s/infrastructure/base`. Environment-specific tuning lives under `k8s/infrastructure/overlays/{env}`. The cluster root pulls in the right overlay.

This gives a clean composition chain:

- common manifests define shared objects once
- overlays patch retention, storage sizes, alert routing, secrets names, and environment labels
- cluster roots decide which infrastructure and app overlays to include

The current `k8s/overlays/*` content can survive conceptually, but it should stop being the thing Flux watches directly. It becomes infrastructure overlay material consumed by cluster roots.

### Promotion workflow

Promotion is a Git operation, not a cluster operation. A change moves from dev to production when the manifest change that is already running in dev is copied or cherry-picked into the production overlay or shared base.

The promotion rules are:

- if a change is environment-neutral, move it from `base` after it has validated in dev
- if a change is environment-specific, copy the relevant patch or version bump from `apps/overlays/dev` to `apps/overlays/production`
- if staging is required, promote dev to staging first, validate, then promote the same manifest change to production

Flux does not “promote” between clusters by itself. Each cluster watches its own path. Promotion means changing Git so another cluster path now declares the same desired state.

## 6. Secrets management

Phase 1 should use sealed-secrets for bootstrap. This remains the correct call even after the provider shift from Hetzner to Vultr.

The reason is practical: the cluster needs a working secret path before a more feature-rich secret system can be bootstrapped. sealed-secrets solves the first problem cleanly:

- secrets can live in Git as encrypted manifests
- decryption happens in-cluster
- the bootstrap dependency chain is small

Phase 1 secret categories include:

- Grafana admin credentials
- future API signing keys
- Discord bot tokens per environment
- database credentials per environment
- object-storage credentials where needed
- external API keys for OCR and Gemini

### Per-environment secret strategy

Secrets must be different per environment. That includes:

- different bot tokens
- different guild IDs in environment configuration
- different database passwords
- different external API keys where rate or billing isolation matters
- different webhook signing secrets

There should be no “shared dev/staging/prod secret because it is easier.” That defeats the purpose of environment separation.

Each environment should therefore have its own sealed secret manifests, typically under its own overlay path. Production secrets should never be referenced from dev or staging overlays.

### Migration path to Infisical

Infisical remains the correct longer-term target, but it should not be a Phase 1 bootstrap blocker. The migration path is:

1. Bootstrap sealed-secrets in all environments
2. Use sealed secrets for the first foundation set
3. Introduce Infisical in Phase 2+
4. Move application and operator secrets to Infisical-backed delivery
5. Reduce sealed-secrets to bootstrap-only or retire it if Phase 2 proves stable

Phase 1 should, however, include one operational requirement learned from earlier risk work: back up the sealed-secrets controller key securely immediately after bootstrap. If the controller key is lost, recovery is painful. This is a bootstrap operation, not a scope expansion.

## 7. Observability

Phase 1 observability is Prometheus, Grafana, and Alertmanager via `kube-prometheus-stack`. That is already reflected in the current `k8s/base/monitoring` draft, and it remains the right baseline.

What changes in v2 is provider correctness and environment sizing discipline.

### Per-environment sizing

Recommended Phase 1 observability sizing:

- `dev`: Prometheus retention 3d, small PVCs, no long-term dashboards, basic health visibility only
- `staging`: Prometheus retention 7d, enough history for benchmark windows and rollout inspection
- `production`: Prometheus retention 30d, real Alertmanager configuration, conservative storage headroom

The current overlays already start this pattern for Prometheus retention, but they should be extended to cover all PVCs and environment labels cleanly rather than only patching one or two fields.

### Correct Vultr storage classes

This proposal explicitly requires replacing `hcloud-volumes` with `vultr-block-storage` on:

- Grafana persistence
- Prometheus PVC template
- Alertmanager PVC template

This is not an optimization. It is a provider migration fix required for the manifests to work on Vultr.

### What observability does in Phase 1

Phase 1 observability is for:

- cluster health
- controller health
- reconciliation failures
- pod restart visibility
- benchmark telemetry
- rollout timing

It is not for:

- full long-term log analytics
- deep tracing
- full cost attribution

Loki, Tempo, and broader telemetry expansion can wait. The definition of done here is that monitoring loads, persists on the right storage class, and gives enough signal to run the platform safely.

## 8. Benchmarking plan

Benchmarking in this platform means repeatable release-candidate measurement on production-shaped staging hardware. It does not mean synthetic microbenchmarks or an elaborate suite against imaginary endpoints.

### Metrics to measure

Phase 1 should define these benchmark families:

- API latency: p50, p95, p99 by critical endpoint
- pipeline latency: submission to completion for async jobs
- database latency: p95 for key query families
- pod readiness time: schedule to Ready
- Flux reconciliation time and failure count
- Discord daemon reconnection time and event lag after restart or rollout

These are the metrics from research that actually describe whether the platform is behaving.

### Tool choice

Phase 1 should standardize on `k6`.

Why `k6` over Locust or vegeta:

- it is strong for API and HTTP benchmarking, which is the first benchmark surface this platform will have
- it has a clean scripting model for reproducible scenarios
- it is easier to treat as a benchmark runner artifact in Git than ad hoc shell tools
- it pairs well with Prometheus/Grafana for observing the cluster during a run

Locust is still a valid later choice if Phase 2 needs richer Python-native multi-user behavior models. vegeta is fine for smaller focused loads, but too narrow to be the default platform benchmark runner.

### Result storage

Raw benchmark artifacts should live in object storage, not Git. The recommended path is a dedicated prefix such as:

`s3://server-manager-artifacts/benchmarks/<environment>/<date>/<git-sha>/`

Each run should store:

- raw `k6` output
- run metadata
- summarized markdown or JSON
- any related Grafana snapshots or exported charts

Do not store benchmark artifacts in the Terraform state bucket or prefix.

### When benchmarks run

Benchmarks run on release candidates in staging, not on every commit. The trigger rule aligns with the promotion policy:

- infra-heavy change: benchmark on staging
- performance-sensitive change: benchmark on staging
- ordinary functional change: no benchmark required in Phase 1

### Pass/fail gate

The future benchmark gate is a regression-vs-baseline rule, not an absolute target invented before workloads exist. The starting policy is:

- critical API p95 must remain within 10% of baseline
- critical API p99 must remain within 15% of baseline
- error rate must not materially worsen
- async pipeline latency must stay inside agreed SLO bands
- no OOM kills, crash loops, or sustained queue growth during the run

Phase 1 defines this gate but does not enforce it as a release blocker yet. The deliverable is definition, runner, storage path, and release policy shape. The platform should not pretend to have a meaningful benchmark suite before the real API and pipeline exist.

## 9. LLM video QA plan

Phase 1 includes a proof-of-concept LLM video QA workflow in dev only. It is advisory and non-blocking.

The workflow is:

1. Playwright drives a deterministic UI scenario
2. the run records video
3. the clip is uploaded to Gemini for video understanding
4. Gemini evaluates the clip against an explicit intent statement
5. the result is reviewed by a human and stored as a dev artifact

### What “intent” means here

For a form-based UI, intent is not a vague statement like “looks good.” It is a structured expected-behavior contract containing:

- starting route and viewport
- user actions performed
- expected visible state after each step
- forbidden states
- success condition

Examples:

- incomplete form submission shows inline validation and does not navigate away
- approval action removes an item from the pending list and shows success feedback
- mobile layout keeps the next-step control visible and usable

This makes the model judge workflow correctness, not aesthetics.

### Why Gemini

Gemini is the only viable Phase 1 planning assumption for this workflow. Google’s official Gemini documentation explicitly supports video understanding, file uploads for video, timestamp-aware prompting, and custom frame-rate handling. Current public MiniMax documentation does not provide equivalent evidence for video evaluation. The Phase 1 plan therefore standardizes on Gemini.

### Why this is not a CI gate yet

The workflow should not block CI in Phase 1 because:

- model judgment is still advisory
- the platform does not yet have stable enough UI flows to justify hard gating
- cost and variance are better handled with selective dev runs first

Definition of done is one successful proof-of-concept run in dev against a real recorded flow, not fleet-wide CI enforcement.

## 10. Cost model

The cost model below uses official Vultr and Buildkite pricing verified on April 11, 2026, plus the current Phase 1 environment shapes proposed above.

### Environment costs

`dev` persistent:

- 1 x `vc2-1c-2gb` worker: $10/mo
- monitoring block storage on NVMe: about $3/mo
  - Prometheus 1 minimum 10 GB volume
  - Grafana 1 minimum 10 GB volume
  - Alertmanager 1 minimum 10 GB volume

Dev total: **$13/mo**

`production` persistent:

- 3 x `vc2-2c-4gb` workers: $60/mo
- monitoring block storage on NVMe: about $4/mo
  - Prometheus 20 GB volume: $2/mo
  - Grafana 10 GB minimum volume: $1/mo
  - Alertmanager 10 GB minimum volume: $1/mo

Production total: **$64/mo**

`staging` on-demand:

- if left up full month at production shape: about $64/mo
- if used twice per month for 3-day benchmark windows: about $13/mo amortized

Staging amortized planning number: **~$13/mo**

That amortized figure assumes staging is actually treated as on-demand. If it becomes a de facto permanent environment, budget it like production.

### Shared platform costs

Object storage:

- 1 TB standard object storage: **$18/mo**

This covers Terraform state plus benchmark and video QA artifacts at Phase 1 scale. State and artifacts should use separate prefixes, and ideally separate buckets later, but the minimum billed footprint is still the 1 TB storage product.

Load balancer:

- Vultr load balancer: **$10/mo** each

Phase 1 baseline assumes no always-on public `LoadBalancer` service yet, so steady-state budget is **$0/mo** here. The moment production exposes a public service through the CCM path, add **$10/mo**. If staging exposes one during a benchmark window, add the prorated amount for that window.

Buildkite:

- Personal plan: **$0/mo** for one user, free forever, max 3 concurrent jobs
- Pro plan: **$30 per active user/mo**, with 10 self-hosted agents included and $2.50/agent/mo beyond that

Phase 1 baseline assumes **$0/mo** on Buildkite Personal because Buildkite agents are not yet a platform dependency in this phase. If the operator wants Pro features immediately, add at least **$30/mo**.

### Total

Phase 1 baseline steady-state total:

- dev $13
- production $64
- staging amortized $13
- object storage $18
- load balancer $0
- Buildkite $0

Baseline total: **~$108/mo**

Operationally realistic total once the first production public load balancer exists:

**~$118/mo**

If staging is accidentally left running full time, the steady-state total becomes roughly:

**~$159/mo** without a load balancer, or **~$169/mo** with one production load balancer

The entire environment model depends on not letting staging become permanent by inertia.

## 11. Definition of done

Phase 1 is complete when all of the following are true:

- dev and production VKE clusters are provisioned and reachable
- staging can be provisioned and destroyed from the same OpenTofu and Flux definitions
- each cluster bootstraps Flux against its own `k8s/clusters/<env>` root path
- sealed-secrets reconciles successfully in each environment
- environment-specific secret material works, including distinct Discord configuration per environment
- monitoring loads in dev and production with Vultr storage classes, not Hetzner leftovers
- Prometheus, Grafana, and Alertmanager persist correctly on their PVCs
- the benchmark definition exists, `k6` is chosen, and an artifact storage path is defined
- the staging promotion rule is documented and specific
- one Playwright-recorded dev flow is analyzed by Gemini successfully as an advisory proof of concept

Phase 1 is not complete merely because a cluster exists. The GitOps path, secret path, monitoring path, and environment boundary story must all be real.

## 12. What Phase 2 needs from Phase 1

Phase 2 depends on Phase 1 to supply a stable substrate, not a half-finished scaffold.

Specifically, Phase 2 needs:

- a working multi-environment VKE foundation
- a per-cluster Flux model that can safely deploy app workloads
- a secret bootstrap path that can later migrate to Infisical
- environment-specific Discord configuration already solved
- object-storage patterns for artifacts and benchmark output
- baseline observability so application regressions are visible
- the benchmark contract, even if the suite is still small
- a proven dev workflow for advisory video QA

With that in place, Phase 2 can focus on the application platform proper: API service delivery, Discord daemon integration, web delivery, managed database decisions, public ingress, CI expansion, and stronger secret management. Without this foundation, Phase 2 would spend its time untangling environment drift and provider mismatches instead of shipping product.

## 13. Risks

### 1. Staging drifts from “on-demand” into “always on”

This is the most likely operational failure mode. If staging is left running by habit, the cost model changes and the team starts treating it as a second production environment without explicitly paying for or governing that choice.

Mitigation: define staging as ephemeral in both OpenTofu workflow and release policy, and track when it is created and destroyed.

### 2. Discord non-production isolation remains incomplete

The presence of a staging guild ID is good, but Phase 1 still depends on proper token and guild separation. If dev or staging silently points at production, the environment model becomes cosmetic.

Mitigation: require environment-specific `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID` before calling an environment complete.

### 3. sealed-secrets key management is neglected

sealed-secrets is acceptable for bootstrap, but only if the controller key is backed up and treated like critical infrastructure.

Mitigation: make key backup part of the bootstrap runbook and definition of operational completion.

### 4. Draft autoscaling assumptions are treated as truth

VKE autoscaling is real, but the existing draft bounds are mechanical placeholders. The January 2026 VKE release notes also show autoscaler fixes landed recently, which is a reminder to verify real behavior rather than assuming it.

Mitigation: pin explicit per-environment min/max bounds and validate them in staging during the first infra-heavy rehearsal.

### 5. Flux remains root-path single-cluster by inertia

This is the primary structural risk in the current repo. If implementation keeps Flux bootstrapped at `k8s/base/flux-system`, the repository will carry a multi-environment illusion on top of a single-environment root.

Mitigation: make per-cluster root paths a hard implementation requirement, not an optional cleanup.

### 6. Provider migration leaves more Hetzner residue than storage classes alone

The obvious bug is `hcloud-volumes`, but provider residue can hide in documentation, secret names, bootstrap instructions, or future controller assumptions.

Mitigation: treat “no Hetzner leftovers in Vultr paths” as an implementation checklist item and verify all cluster-facing manifests and docs accordingly.

### 7. Cost assumptions drift with provider pricing or usage patterns

Vultr pricing is relatively straightforward, but location-specific pricing exists, and Buildkite cost depends on plan choice and agent usage. The cost numbers in this proposal are therefore dated to April 11, 2026.

Mitigation: re-verify pricing immediately before implementation and again before enabling any permanent public load balancer or paid Buildkite tier.

## References

- Vultr Kubernetes pricing overview: https://docs.vultr.com/support/products/vke/how-much-does-the-vultr-kubernetes-engine-cost
- Vultr pricing: https://www.vultr.com/pricing/
- Vultr Kubernetes product docs: https://docs.vultr.com/products/kubernetes
- Vultr Kubernetes changelog: https://docs.vultr.com/products/kubernetes/changelog
- Vultr default networking (Calico): https://docs.vultr.com/support/products/vke/what-is-the-default-networking-solution-in-a-vultr-kubernetes-engine-cluster
- Vultr persistent storage: https://docs.vultr.com/support/products/vke/how-does-vultr-kubernetes-engine-handle-persistent-data-storage
- Vultr minimum VKE block storage sizes: https://docs.vultr.com/support/products/vke/what-is-the-minimum-size-block-storage-volume-i-can-deploy-to-a-vke-cluster
- Vultr CCM integration: https://docs.vultr.com/support/products/vke/what-role-does-the-vultr-cloud-controller-manager-play-in-kubernetes-integration
- Buildkite pricing: https://buildkite.com/pricing/
- Gemini video understanding: https://ai.google.dev/gemini-api/docs/video-understanding
