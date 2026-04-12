# Platform Initiative Map

This map consolidates the current platform planning corpus into discrete initiatives that can each run through the project’s required `research -> proposal -> risk -> implement` pipeline. It normalizes older material where needed:

- The user’s locked decisions override older open questions in `plans/unified-platform-index.md`, `plans/platform-decisions-overlay.md`, and the legacy decomposition indexes.
- `plans/legacy/base-application-index.md` is treated as the structural reference for the two-tier model: one platform cluster plus separately provisioned application clusters.
- `plans/proposals/phase1-foundation-v2.md` is treated as a partial Phase 1 proposal, not as the final canonical foundation plan, because it predates the current locked stack and still carries bootstrap choices like sealed-secrets that no longer match the target.
- The older Dagger/GitLab/JFrog/MinIO/object-storage-Flux patterns are preserved as historical inputs, but they are not promoted forward unless they still fit the locked decisions.

The result is intentionally more decomposed than the old unified index. The legacy docs tried to carry too much in a single “platform” proposal. The current plan separates stable foundation work from optional later complexity, especially around dynamic environments, AIOps, and application expansion.

## Normalization Rules

The old corpus does not describe one clean architecture. It describes several partially overlapping attempts:

- a legacy Dagger/GitLab/JFrog/MinIO platform shape
- a later Crossplane-plus-Flux multi-cluster direction
- a current Vultr/VKE environment-and-benchmark proposal
- application-specific Humility research that assumes a simpler Railway/Supabase execution model

This map resolves those overlaps by normalizing the source material into a smaller number of durable planning rules.

### Retained from the older documents

These patterns are kept because they still fit the locked decisions and still show up repeatedly across the corpus:

- The two-tier control-plane pattern from `plans/legacy/base-application-index.md`: one platform cluster controls separately provisioned application clusters.
- Git-reviewed desired state and per-environment reconciliation paths from the GitOps and base-application material.
- Environment asymmetry from `plans/research/phase1-environments-and-benchmarks.md`: `dev` is persistent, `staging` is on-demand, `production` is persistent.
- The split between public ingress concerns and operator-access concerns from the auth and platform indexes: Kong and Cloudflare own north-south traffic; Pomerium and Smallstep own internal/operator access.
- The requirement that applications are clients of a shared API surface, not alternate sources of truth. This is present implicitly in the legacy FastAPI control-plane material and is now explicit in the locked API-first decision.

### Explicitly retired or downgraded

These patterns appear in the old material but are not promoted into current initiatives except as historical context:

- Dagger as the canonical CI engine. It is treated as reference history only; Buildkite is the actual initiative target.
- GitLab Runner as the primary execution plane. The Buildkite research directly replaces it.
- JFrog Artifactory as the default registry. Harbor is the locked artifact-plane decision, so the older JFrog content is useful only as a reminder that registry work is a first-class initiative, not as a product choice.
- MinIO as the default object-storage layer. `plans/research/self-hosted-s3.md` and the locked decisions make provider-native object storage the default, with self-hosted S3 only as an explicit exception.
- Bucket-sourced Flux as the authoritative GitOps model. The older platform and base-application material used bucket-watched Flux paths, but the current plan treats Git paths as the desired-state source and reserves object storage for artifacts, backups, and possibly generated release manifests.
- Bastion-plus-Ansible as the long-term operating model. A small imperative bootstrap bridge may still exist, but it is not elevated into a strategic initiative. The old “Terraform -> local-exec -> Ansible -> more Ansible” chain is reference material, not target state.
- Managed Postgres as the platform answer. Vultr managed Postgres was part of the older provider comparison, but the locked decision now requires self-managed Postgres on Kubernetes.
- Elastic/VictoriaMetrics as the default observability answer. Those older assumptions are useful for understanding the need for structured telemetry contracts, but the actual initiative must target Prometheus, Grafana, Alertmanager, and Loki.

### Why the initiative boundaries look different from the old unified index

The old `plans/unified-platform-index.md` was directionally right but still too monolithic. It mixed persistent foundation work, application delivery, dynamic environments, security add-ons, and later optimization layers into one long dependency chain. That shape makes planning look cleaner than it really is, but it hides the fact that some branches can and should move independently.

This map deliberately separates:

- **Application Cluster Provisioning** from **Dynamic Environments**. The old docs treated them as one continuous Crossplane story. In practice, persistent app clusters are foundational, while ephemeral environments are optional later complexity.
- **Artifact Management** from **CI/CD Pipeline** and **Release Management**. The older documents often bundled them together, but the external RFQ distribution work makes clear that registry design, pipeline execution, and release-promotion semantics are different problems.
- **Observability** from **AIOps**. The legacy platform index collapsed alert buses and automation into the same story as telemetry. That is backwards for execution order. Good automation depends on good signals.
- **Application API Foundation** from the actual product initiatives. The Humility proposal currently carries platform substrate, workflow logic, OCR, tickets, and provisioning in one large scope. This map makes the shared API a platform/application boundary initiative of its own.

### Status interpretation

The status fields below use a stricter reading than the older unified plan:

- `Research status` asks whether the initiative itself has enough current evidence, not whether related ideas appear somewhere in the legacy docs.
- `Proposal status` is marked `needs revision` whenever the existing proposal materially conflicts with the locked decisions or still carries an over-broad scope.
- `Risk status` only counts as effectively green when an initiative-specific proposal has cleared a current risk pass. Older mixed-scope risk docs are useful, but they do not automatically authorize implementation of a narrower or differently-shaped initiative.
- `Implementation status` treats “draft exists” as a warning label, not a sign of readiness. The current repo contains many partial structures whose main value is exposing shape and failure points.

## Initiative List

### Initiative: Platform Bootstrap

**Scope**: Deliver the irreducible substrate for the platform cluster itself: Vultr account shape, VKE platform cluster, base networking, per-environment OpenTofu roots, object-storage backing, and the first reproducible bootstrap path. This is the bottom layer every other initiative stands on.
**Dependencies**: None.
**Blocked by**: None beyond operator inputs such as Vultr account governance, credentials, and chosen regions.
**Components**: Vultr, VKE, OpenTofu, VPC/networking, object storage, environment roots.
**Research status**: Strong. `plans/research/hetzner-vs-vultr.md`, `plans/research/opentofu-providers.md`, `plans/research/phase1-environments-and-benchmarks.md`, and `plans/legacy/base-application-index.md` cover provider fit, IaC surface, environment asymmetry, and bootstrap layering. Still needed: current state-backend choice, final VKE version pin, and exact OpenTofu module boundaries.
**Proposal status**: Needs revision. `plans/proposals/phase1-foundation-v2.md` covers much of this initiative, but it assumes a narrower bootstrap and still reflects pre-lock secret/bootstrap decisions.
**Risk status**: Assessed, but not approved. `plans/risk/phase1v2-audit.md` is MEDIUM; `phase1v2-scope.md` and `phase1v2-shortcut.md` are LOW. The initiative needs a revised proposal and a fresh all-LOW pass.
**Implementation status**: Draft exists. `infra/` and `k8s/` are present, but they are partial and still contain provider-migration residue.
**Estimated units**: L
**Phase**: Phase 1 — Foundation Control Plane

### Initiative: GitOps Foundation

**Scope**: Establish Flux CD as the canonical reconciler for the platform, with Git as the source of truth, per-cluster roots, base-plus-overlays layout, and environment-specific reconciliation paths. This initiative also resolves legacy ambiguity between bucket-watched Flux, custom GitOps controllers, and platform-generated claims.
**Dependencies**: Platform Bootstrap.
**Blocked by**: A working platform cluster, a finalized repo topology, and the decision that Flux roots are Git-path based rather than object-storage sourced.
**Components**: Flux CD, Git repositories, Kustomize structure, image automation entry points, repo layout.
**Research status**: Strong. `plans/legacy/gitops-index.md`, `plans/unified-platform-index.md`, `plans/research/buildkite-capabilities.md`, `plans/research/phase1-environments-and-benchmarks.md`, and `plans/legacy/base-application-index.md` all describe the GitOps control surface and the current failure points. Still needed: a clean initiative-level design for Git-only Flux sources and ownership boundaries with Crossplane and release automation.
**Proposal status**: Needs writing. Current foundation material references this work, but no dedicated proposal isolates GitOps as its own initiative.
**Risk status**: Needs assessment.
**Implementation status**: Draft exists. `k8s/base/flux-system` and `k8s/overlays/*` exist, but the current shape is still effectively single-cluster.
**Estimated units**: M
**Phase**: Phase 1 — Foundation Control Plane

### Initiative: Application Cluster Provisioning

**Scope**: Turn the base-application two-tier pattern into a real control-plane contract: Crossplane provider config, XRDs/compositions, environment profiles, child-cluster kubeconfig wiring, and child Flux bootstrap. This initiative is about provisioning persistent application clusters cleanly, not about ephemeral environments yet.
**Dependencies**: Platform Bootstrap, GitOps Foundation, Secret Management.
**Blocked by**: Crossplane provider credentials, final XRD/composition contract, working child-cluster bootstrap secret flow, and agreed environment profile inputs for `dev`, `staging`, and `production`.
**Components**: Crossplane, provider-vultr, XRDs, compositions, cluster claims, child Flux bootstrap, environment profiles.
**Research status**: Moderate-to-strong. `plans/legacy/platform-v2-index.md` and `plans/legacy/base-application-index.md` define the pattern well and expose the current breaks. Still needed: current provider maturity validation for the exact Crossplane/VKE path and a trimmed claim model aligned with the locked architecture.
**Proposal status**: Needs writing. Older material covers the pattern, but no current initiative-level proposal closes the broken secret/kubeconfig/bootstrap edges.
**Risk status**: Needs assessment.
**Implementation status**: Draft exists. The `base-application` pattern is clear, but the repo’s Crossplane path is incomplete and mismatched in several places.
**Estimated units**: L
**Phase**: Phase 1 — Foundation Control Plane

### Initiative: Secret Management

**Scope**: Deploy Infisical as the canonical secret authority, define the bootstrap-to-runtime secret flow, and standardize how platform services and applications receive secrets across the platform and application clusters. This initiative replaces the legacy split across sealed-secrets, ad hoc bootstrap jobs, and example-only secret subscribers.
**Dependencies**: Platform Bootstrap, GitOps Foundation.
**Blocked by**: Bootstrap credential flow, operator or sync mechanism choice, secret namespace model, and recovery/rotation policy.
**Components**: Infisical, Kubernetes secret sync path, runtime secret consumption, bootstrap credentials, secret recovery.
**Research status**: Weak-to-moderate. The legacy corpus mentions Infisical heavily, especially in `plans/legacy/auth-v5-index.md`, `plans/legacy/platform-v2-index.md`, and the expansion appendix, but there is no focused current research artifact for the locked Infisical-first design.
**Proposal status**: Needs writing.
**Risk status**: Needs assessment.
**Implementation status**: Not started. Current local code has bootstrap-era secret patterns and examples, not a ratified platform secret design.
**Estimated units**: M
**Phase**: Phase 1 — Foundation Control Plane

### Initiative: Artifact Management

**Scope**: Stand up Harbor as the shared artifact plane for container images, Helm charts, PyPI/npm artifacts, OCI bundles, and Trivy-on-push scanning, backed by Vultr Object Storage where appropriate. This initiative also owns the internal package-distribution and third-party mirroring strategy instead of leaving package flow as an implicit side effect of CI.
**Dependencies**: Platform Bootstrap, GitOps Foundation, Secret Management.
**Blocked by**: Harbor deployment model, backing storage layout, auth integration, package-registry scope, and the choice of how selective third-party mirroring lands in the artifact plane.
**Components**: Harbor, Trivy on push, Vultr Object Storage, package registries, third-party mirrors.
**Research status**: Moderate. `plans/legacy/platform-v2-index.md` and `plans/unified-platform-index.md` preserve the old registry role; `plans/research/self-hosted-s3.md` covers object-store tradeoffs; the external RFQ proposals on supply-chain security and third-party mirroring provide strong precedent for Trivy, lockfile-driven mirroring, and immutable artifacts. Still needed: Harbor-specific package layout and mirror workflow.
**Proposal status**: Needs writing.
**Risk status**: Needs assessment.
**Implementation status**: Not started. The older JFrog pattern in `base-application` is explicitly not carried forward as-is.
**Estimated units**: M
**Phase**: Phase 2 — Delivery and Shared Services

### Initiative: CI/CD Pipeline

**Scope**: Replace the legacy Dagger/GitLab execution model with Buildkite agents, queue design, reusable pipelines, and cluster-aware execution rules. This initiative owns build/test/publish behavior, agent placement, and the path from source commit to immutable artifact, but not promotion policy itself.
**Dependencies**: GitOps Foundation, Secret Management, Artifact Management, Application Cluster Provisioning.
**Blocked by**: Buildkite agent deployment model, queue taxonomy, registry credentials, and the contract for how CI feeds Flux-compatible release outputs.
**Components**: Buildkite, self-hosted agents on Kubernetes, queues, pipelines, tests, artifact publication.
**Research status**: Strong. `plans/research/buildkite-capabilities.md` is directly relevant, and the legacy Dagger/GitLab material in `plans/legacy/gitops-index.md`, `plans/legacy/platform-v2-index.md`, and `plans/legacy/base-application-index.md` makes clear what is being replaced.
**Proposal status**: Needs writing.
**Risk status**: Needs assessment.
**Implementation status**: Not started.
**Estimated units**: M
**Phase**: Phase 2 — Delivery and Shared Services

### Initiative: Release Management

**Scope**: Define how immutable artifacts become deployable releases across `dev`, `staging`, and `production`: Harbor tags, Flux image automation, promotion semantics, release-channel rules, and rollback boundaries. This initiative also absorbs the multi-image and manifest-commit concepts from the RFQ distribution work so that promotion remains atomic at the release level even when one logical release spans multiple artifacts.
**Dependencies**: GitOps Foundation, Artifact Management, CI/CD Pipeline.
**Blocked by**: Harbor tag taxonomy, Flux image automation layout, promotion commit model, and a single authoritative release pointer or manifest contract.
**Components**: Harbor tags, Flux image automation, release channels, manifests, rollback metadata.
**Research status**: Moderate. `plans/unified-platform-index.md` and the legacy GitOps/platform indexes define the old promotion model; the external `design-multi-image-promotion.md` proposal gives a strong modern pattern for atomic promotion; the locked decisions already choose Harbor tags plus Flux watches. Still needed: an in-repo proposal tailored to Harbor plus Flux.
**Proposal status**: Needs writing.
**Risk status**: Needs assessment.
**Implementation status**: Not started.
**Estimated units**: M
**Phase**: Phase 2 — Delivery and Shared Services

### Initiative: Database Platform

**Scope**: Choose and implement the self-managed Postgres substrate for the platform and applications using CloudNativePG or the Zalando operator, including storage classes, backups, credentials, and operational envelopes. This initiative replaces the older assumption of managed Postgres and turns database hosting into an explicit platform capability.
**Dependencies**: Application Cluster Provisioning, Secret Management, GitOps Foundation.
**Blocked by**: Operator choice, storage-class policy, backup policy, and the decision about where platform versus application databases live across the two-tier cluster model.
**Components**: PostgreSQL, CloudNativePG or Zalando operator, storage classes, credentials, backups, schemas.
**Research status**: Weak. The legacy material consistently assumes PostgreSQL as the system of record, but there is no focused current research pass for the operator choice or its fit on Vultr VKE.
**Proposal status**: Needs writing.
**Risk status**: Needs assessment.
**Implementation status**: Not started.
**Estimated units**: M
**Phase**: Phase 2 — Delivery and Shared Services

### Initiative: Observability

**Scope**: Deliver the locked observability stack: Prometheus, Grafana, Alertmanager, Loki, and the telemetry contracts that make platform, application, and Discord operational behavior debuggable. This initiative replaces the older Elastic- and VictoriaMetrics-heavy assumptions with the currently locked stack while preserving the cross-system correlation principle.
**Dependencies**: Platform Bootstrap, GitOps Foundation, Secret Management, Application Cluster Provisioning.
**Blocked by**: Final stack topology, collector/log-ingest path, retention policy, and required telemetry attributes for shared services and applications.
**Components**: Prometheus, Grafana, Alertmanager, Loki, OpenTelemetry contracts, dashboards, alerts.
**Research status**: Moderate but mismatched. `plans/legacy/platform-v2-index.md`, `plans/legacy/expansion-plan-index.md`, `plans/unified-platform-index.md`, and `plans/proposals/phase1-foundation-v2.md` cover observability as a concept, but much of the concrete detail assumes Elastic or VictoriaMetrics instead of the locked Loki-based stack. New initiative-specific research is still needed.
**Proposal status**: Needs writing.
**Risk status**: Needs assessment.
**Implementation status**: Draft exists. `k8s/base/monitoring` shows a partial monitoring baseline, but it still contains provider drift and does not reflect the full locked stack.
**Estimated units**: M
**Phase**: Phase 2 — Delivery and Shared Services

### Initiative: Edge & Networking

**Scope**: Define and deploy the north-south edge and cluster networking baseline: Cloudflare at the edge, Kong as ingress/API gateway, origin lockdown, load-balancer exposure rules, and Calico-driven network policy posture. This initiative owns the edge contract for public APIs and UIs, but not the higher-level identity policies that run through it.
**Dependencies**: Platform Bootstrap, GitOps Foundation, Secret Management, Application Cluster Provisioning.
**Blocked by**: Kong deployment topology, Cloudflare origin restriction model, load-balancer policy, and the minimum viable Calico policy set.
**Components**: Cloudflare, Kong, Vultr load balancers, Calico, network policies, DNS, TLS boundaries.
**Research status**: Strong. `plans/legacy/expansion-plan-index.md`, `plans/legacy/platform-v2-index.md`, `plans/legacy/base-application-index.md`, and the user’s locked decisions give a clear component set. Still needed: a modern proposal that drops the older HAProxy/Gateway API comparison noise and resolves rollout order for default-deny networking.
**Proposal status**: Needs writing.
**Risk status**: Needs assessment.
**Implementation status**: Draft exists. Kong manifests exist in the reference material, but the edge and Calico model are not ratified in the current repo.
**Estimated units**: M
**Phase**: Phase 3 — Secure Access and Edge

### Initiative: Identity & Access

**Scope**: Build the full identity-aware access plane: Authentik as IdP, Pomerium for operator/internal access, OPAL/Cedar for fine-grained authorization, Smallstep for PKI, and the app-facing enforcement contracts that let services and UIs use the same identity model. This is one of the largest initiatives because it spans both human access and application authorization.
**Dependencies**: Secret Management, Edge & Networking, Observability.
**Blocked by**: Secret delivery, Kong/public-edge contract, log/metric sinks for auth components, and a current compatibility design for Authentik/Pomerium/OPAL/Cedar/step-ca on the locked stack.
**Components**: Authentik, Pomerium, OPAL, Cedar, Smallstep step-ca, Kong header contract, auth logs and alerts.
**Research status**: Strong but legacy-shaped. `plans/legacy/auth-v5-index.md` is the deepest decomposition in the corpus, and `plans/research/pomerium-smallstep.md` plus `plans/research/logto-rls-pagination.md` close important design questions. What is still missing is a current proposal that trims old assumptions like Terraform-controller-centric auth rollout and refreshes the operational model.
**Proposal status**: Needs writing.
**Risk status**: Needs assessment.
**Implementation status**: Not started.
**Estimated units**: XL
**Phase**: Phase 3 — Secure Access and Edge

### Initiative: Security Hardening

**Scope**: Add the non-foundational but required hardening layers: Trivy in CI and in-cluster, Falco, Calico default-deny completion, Velero backups, Sigstore signing, dependency-update policy, and the minimum supply-chain controls that turn the platform from “works” into “defensible.” This initiative deliberately follows core delivery, because most of its value is in hardening real workloads rather than empty clusters.
**Dependencies**: Artifact Management, Observability, Edge & Networking, Database Platform.
**Blocked by**: Registry/image flow, alert sinks, network boundaries, backup targets, and signing key management.
**Components**: Trivy, Falco, Calico, Velero, Sigstore, Dependabot, Renovate, backup storage.
**Research status**: Strong on the legacy side. `plans/legacy/expansion-plan-index.md` gives the right component list and rollout shape, while the external `design-supply-chain-security.md` proposal supplies current guidance for Trivy, update bots, and Sigstore. Still needed: one integrated proposal aligned with Harbor and the locked stack.
**Proposal status**: Needs writing.
**Risk status**: Needs assessment.
**Implementation status**: Not started.
**Estimated units**: L
**Phase**: Phase 6 — Dynamic Operations and Hardening

### Initiative: AIOps

**Scope**: Implement the alert-to-action automation plane with StackStorm and `droid` (z.ai GLM), fed by the observability stack and bounded by explicit runbooks. This initiative is intentionally downstream of basic observability and hardening because it only becomes useful once there are meaningful alerts, incidents, and safe remediation boundaries.
**Dependencies**: Observability, Security Hardening.
**Blocked by**: Alert schema, event routing, action catalog, approval boundaries, and the `droid` integration model.
**Components**: StackStorm, droid, alert bus, remediation workflows, operator notifications.
**Research status**: Weak-to-moderate. `plans/legacy/platform-v2-index.md` and `plans/unified-platform-index.md` preserve the StackStorm branch, but the locked `droid` addition is not researched in the current corpus.
**Proposal status**: Needs writing.
**Risk status**: Needs assessment.
**Implementation status**: Not started.
**Estimated units**: M
**Phase**: Phase 6 — Dynamic Operations and Hardening

### Initiative: Benchmarking & QA

**Scope**: Build the non-functional validation lane: `staging` benchmark rules, `k6` or Locust execution, baseline storage, advisory LLM video QA, and release-candidate performance gates. This initiative turns the current environment model into a measured release process rather than a structural idea.
**Dependencies**: Observability, Release Management, Application API Foundation.
**Blocked by**: Stable API surfaces to measure, artifact storage path, benchmark runner choice, and one real UI flow for video QA.
**Components**: Staging environment policy, `k6`, Playwright, Gemini-based video QA, benchmark artifacts, pass/fail rules.
**Research status**: Strong. `plans/research/phase1-environments-and-benchmarks.md` is directly about this initiative, and `plans/proposals/phase1-foundation-v2.md` already incorporates a concrete first pass.
**Proposal status**: Needs revision. The current foundation proposal covers this initiative as part of Phase 1, but it should be split into its own proposal once the foundation substrate is separated from non-functional QA work.
**Risk status**: Assessed, but not initiative-isolated. The current risk docs cover benchmarking and video QA only as part of the broader foundation proposal.
**Implementation status**: Not started.
**Estimated units**: M
**Phase**: Phase 6 — Dynamic Operations and Hardening

### Initiative: Dynamic Environments

**Scope**: Deliver on-demand ephemeral clusters and short-lived test environments, including the environment API or equivalent declarative interface, TTL cleanup, claim generation, and teardown. This initiative is deliberately later than the persistent cluster substrate because the legacy material consistently shows it as complexity-heavy and easy to overbuild.
**Dependencies**: Application Cluster Provisioning, Release Management, Identity & Access, Benchmarking & QA.
**Blocked by**: Stable cluster-claim contract, release artifact semantics, environment ownership/auth model, and a decision on how much of the legacy Postgres/Debezium/Kafka environment API still survives under the locked architecture.
**Components**: Crossplane cluster claims, TTL cleanup, environment API, ephemeral cluster bootstrap, preview/test environment workflows.
**Research status**: Moderate but unresolved. `plans/legacy/gitops-index.md`, `plans/legacy/platform-v2-index.md`, and `plans/legacy/base-application-index.md` all describe the old dynamic-environment model, but they also expose how much custom machinery it carried. New research is needed to trim it to the locked Crossplane-plus-Flux architecture.
**Proposal status**: Needs writing.
**Risk status**: Needs assessment.
**Implementation status**: Draft exists in concept only.
**Estimated units**: XL
**Phase**: Phase 6 — Dynamic Operations and Hardening

### Initiative: Application API Foundation

**Scope**: Build the shared FastAPI control surface that the Discord bot, the web UI, and later automation all consume. This initiative is the implementation expression of the locked API-first principle: every meaningful action has an API endpoint, and Discord/UI surfaces are clients, not privileged alternate control planes.
**Dependencies**: Database Platform, Release Management, Observability, Secret Management.
**Blocked by**: Postgres/operator baseline, deployment path to app clusters, shared telemetry/auth conventions, and a first-pass service skeleton.
**Components**: FastAPI, shared API contracts, service auth, background jobs, data access layer, health and telemetry.
**Research status**: Moderate. The legacy platform docs assume a FastAPI control plane, and the Humility app proposal in `proposals/01-v1-scope.md` presumes a shared daemon-plus-DB substrate. Still needed: a dedicated proposal that separates platform API foundation from the Discord feature payload.
**Proposal status**: Needs writing.
**Risk status**: Needs assessment.
**Implementation status**: Not started. There is a service skeleton in `services/api`, but not a ratified initiative-level design.
**Estimated units**: L
**Phase**: Phase 4 — Application Core

### Initiative: Application: Discord Bot

**Scope**: Deliver the Humility Discord bot itself as a production workload on the new platform, including applications, tickets, chapter operations, and bot-specific operational behavior. This initiative is the first real consumer of the platform and is the shortest path to proving the platform with live value.
**Dependencies**: Application API Foundation, Database Platform, Release Management, Application Cluster Provisioning, Observability.
**Blocked by**: Deployed API service, Discord token/guild secret path, production application cluster, and a ratified v1 scope trimmed to fit the platform phases.
**Components**: discord.py daemon, Discord interaction handlers, application/ticket workflows, chapter commands, audit events.
**Research status**: Strong. `research/01-problem-space.md`, `research/02-humility-needs.md`, `NOTES.md`, and `AGENTS.md` define the real pain and the current live-server constraints.
**Proposal status**: Exists, but needs revision. `proposals/01-v1-scope.md` is substantial, but `risk/01-scope.md` is MEDIUM and explicitly calls for trimming the subsystem mix and schema surface before implementation.
**Risk status**: Assessed, but not approved. `risk/01-audit.md` and `risk/01-shortcut.md` are LOW; `risk/01-scope.md` is MEDIUM.
**Implementation status**: Not started as a ratified feature build. Current service code is skeletal.
**Estimated units**: XL
**Phase**: Phase 4 — Application Core

### Initiative: Application: Activity Tracking

**Scope**: Implement screenshot-driven activity ingestion, OCR extraction, roster mapping, and threshold-based flagging as a separate application initiative rather than burying it inside the whole Discord bot scope. This should stay distinct because it has different technical dependencies, accuracy risk, and iteration cadence from tickets or applications.
**Dependencies**: Application API Foundation, Application: Discord Bot, Benchmarking & QA.
**Blocked by**: Stable ingest endpoints, roster/data model contract, accepted OCR backend strategy, and a review workflow for low-confidence parses.
**Components**: OCR pipeline, screenshot ingestion, validation/review UI or command flow, activity rules, activity logs, flags.
**Research status**: Strong. `research/04-ocr-backends.md` is dedicated to this problem, and `research/02-humility-needs.md` confirms it is a primary daily pain.
**Proposal status**: Exists, but needs revision. `proposals/01-v1-scope.md` includes the subsystem, but it should be re-cut into a narrower initiative with its own proposal and gates.
**Risk status**: Assessed, but not initiative-isolated. The current proposal’s overall scope risk is MEDIUM, and the OCR fallback architecture is explicitly a later gate.
**Implementation status**: Not started.
**Estimated units**: L
**Phase**: Phase 5 — Product Surfaces

### Initiative: Application: Web UI

**Scope**: Build the TanStack Start web UI that uses the shared API for officer/admin workflows, activity review, and later platform operations. This initiative depends on the API-first rule being real; the UI should not become a shadow control plane or a separate backend.
**Dependencies**: Application API Foundation, Identity & Access, Edge & Networking, Release Management.
**Blocked by**: Stable browser-auth contract, public ingress/TLS, finalized API surfaces, and frontend release/deploy path.
**Components**: TanStack Start, browser auth, officer/admin dashboards, activity review UI, deployment path.
**Research status**: Moderate. The platform research treats the web UI as a future consumer, and `plans/research/phase1-environments-and-benchmarks.md` already anticipates Playwright-plus-video-QA for it. But there is no dedicated UI research or proposal yet.
**Proposal status**: Needs writing.
**Risk status**: Needs assessment.
**Implementation status**: Not started.
**Estimated units**: L
**Phase**: Phase 5 — Product Surfaces

## Dependency Graph

### Critical path to “Discord bot running in production”

The shortest defensible path is:

`Platform Bootstrap -> GitOps Foundation -> Secret Management -> Application Cluster Provisioning -> Artifact Management -> CI/CD Pipeline -> Release Management -> Database Platform -> Observability -> Application API Foundation -> Application: Discord Bot`

That path is intentionally narrower than “full platform complete.” It assumes:

- the bot and API can launch without the full dynamic-environment control plane
- the first production bot release does not require the full public web UI
- edge identity and operator-access polish can lag the first internal service release if the initial API surface stays internal or Discord-only

### Parallel lanes after the foundation control plane exists

- `Artifact Management`, `Database Platform`, and `Observability` can start in parallel once `Platform Bootstrap`, `GitOps Foundation`, `Secret Management`, and `Application Cluster Provisioning` are real.
- `Edge & Networking` can run in parallel with `Artifact Management` and `Database Platform`; it is not on the minimum bot path unless the first API/UI release needs public ingress immediately.
- `Identity & Access` can start once `Edge & Networking`, `Secret Management`, and `Observability` are stable. It should not block the earliest internal bot/API release, but it does block the full officer-facing web UI and secure operator experience.
- `Security Hardening` can run after `Artifact Management`, `Observability`, and `Edge & Networking` exist. It should harden real release paths rather than hypothetical ones.

### Later serial or complexity-heavy branches

- `Dynamic Environments` is intentionally downstream of `Application Cluster Provisioning`, `Release Management`, `Identity & Access`, and `Benchmarking & QA`. The older platform docs made this branch central too early; it should now be explicitly later.
- `AIOps` depends on both `Observability` and `Security Hardening`. Without reliable alerts and runbooks, it degenerates into noisy automation theater.
- `Application: Activity Tracking` and `Application: Web UI` both depend on `Application API Foundation`; they can then proceed in parallel.

### Not on the minimum bot path

These initiatives are valuable, but they do not block the first production bot release:

- `Edge & Networking` if the bot/API first release remains internal
- `Identity & Access` beyond the minimal internal service auth needed for the API
- `Dynamic Environments`
- `AIOps`
- the full `Security Hardening` program
- `Application: Web UI`

## Phase Mapping

### Phase 1 — Foundation Control Plane

Initiatives:

- Platform Bootstrap
- GitOps Foundation
- Secret Management
- Application Cluster Provisioning

Milestone:

- A platform cluster exists on Vultr VKE, Git is the reconciliation source, Infisical-backed secrets have a defined delivery path, and the platform can provision and bootstrap persistent application clusters from the control plane.

### Phase 2 — Delivery and Shared Services

Initiatives:

- Artifact Management
- CI/CD Pipeline
- Release Management
- Database Platform
- Observability

Milestone:

- Buildkite can build and publish immutable artifacts into Harbor, Flux can promote them by environment, PostgreSQL is available on-cluster, and the shared telemetry stack can observe releases and runtime failures.

### Phase 3 — Secure Access and Edge

Initiatives:

- Edge & Networking
- Identity & Access

Milestone:

- Public and operator access surfaces are routed through the intended edge and identity planes: Cloudflare and Kong for ingress, Authentik and Pomerium for identity-aware access, OPAL/Cedar for fine-grained policy, and Smallstep for PKI.

### Phase 4 — Application Core

Initiatives:

- Application API Foundation
- Application: Discord Bot

Milestone:

- The shared FastAPI control surface exists, the Discord bot is deployed through the platform release path, and the first real application proves the platform in production.

### Phase 5 — Product Surfaces

Initiatives:

- Application: Activity Tracking
- Application: Web UI

Milestone:

- The operator-facing web UI and the screenshot/OCR activity workflow both run against the shared API and data model, expanding the product beyond the Discord-only surface.

### Phase 6 — Dynamic Operations and Hardening

Initiatives:

- Benchmarking & QA
- Dynamic Environments
- Security Hardening
- AIOps

Milestone:

- The platform can create and tear down on-demand environments, measure release candidates in staging, restore from backup, sign and scan release artifacts, enforce stronger runtime controls, and automate bounded responses to incidents.

## What’s Ready to Start NOW

These initiatives have enough evidence and decision clarity to start proposal writing immediately:

- `Platform Bootstrap`
  Existing research is strong and there is already a partial proposal to revise.
- `GitOps Foundation`
  The problem is well-understood and the current repo already exposes the exact structural failures that need a proposal.
- `Application Cluster Provisioning`
  The two-tier architecture is locked, and the `base-application` analysis gives a concrete starting pattern.
- `Artifact Management`
  Harbor is locked, and the external distribution/security proposals already cover the hard questions around immutability, Trivy, and mirroring.
- `CI/CD Pipeline`
  Buildkite research is already complete and the replacement target is clear.
- `Release Management`
  Harbor-tag plus Flux-image-automation is locked, and the external multi-image promotion proposal gives a ready precedent.
- `Edge & Networking`
  Component choice is locked and the legacy expansion research is already enough to frame the proposal.
- `Identity & Access`
  This is a large initiative, but the auth decomposition plus Pomerium/Smallstep and Logto research are already substantial enough to begin proposal work.
- `Benchmarking & QA`
  Dedicated research already exists; it mainly needs separation from the foundation proposal.

These initiatives need more research before proposal writing:

- `Secret Management`
  Infisical is locked, but there is no focused current research artifact for bootstrap, sync, and recovery.
- `Database Platform`
  The self-managed Postgres decision is locked, but operator choice and storage/backup shape are not researched yet.
- `Observability`
  The locked stack differs materially from the legacy Elastic/VictoriaMetrics assumptions; it needs a fresh pass.
- `Dynamic Environments`
  The old design is too heavy to carry forward blindly and needs a fresh simplification pass.
- `AIOps`
  `droid` is a locked choice with little current research in the repo.
- `Application API Foundation`
  The principle is locked, but the initiative still needs a platform-specific proposal that separates shared API substrate from Discord features.

These initiatives are already researched enough to support proposal revision once the platform substrate is decomposed, rather than brand-new problem research:

- `Application: Discord Bot`
- `Application: Activity Tracking`

Both already have substantial Humility-specific research, and the bot already has a proposal plus risk passes. The work needed is narrowing and splitting scope, not rediscovering the problem.
