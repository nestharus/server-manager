# Platform Initiative Map

## Normalization Rules

1. Newer current artifacts outrank older merged and legacy corpora. In practice:
   - `plans/platform-decisions-overlay.md`
   - current `plans/research/*.md`
   - `plans/proposals/phase1-foundation-v2.md`
   - current `plans/risk/*.md`
   beat `plans/unified-platform-index.md` and the recovered legacy indexes when they disagree.
2. `base-application` is treated as a structural reference, not a literal stack:
   - keep the two-tier model of a platform/control cluster plus separately provisioned application clusters
   - do not copy its Dagger, JFrog, MinIO claim-bus, bucket-watched Flux, or bastion-heavy bootstrap patterns
3. Git is the authoritative desired-state source. `Flux CD` is the reconciler. The normalized baseline drops:
   - bucket-watched Flux
   - DB-backed static GitOps
   - Dagger/GitLab/JFrog as the canonical control plane
4. Locked current decisions that survive normalization:
   - identity: `Authentik`
   - authorization engine: `OPAL/Cedar`
   - human access proxy: `Pomerium`
   - CI control plane: `Buildkite`
   - GitOps reconciler: `Flux CD`
   - IaC entrypoint: `OpenTofu`
   - object storage direction: provider-native S3-compatible storage first
   - `Smallstep` only if later PKI scope justifies it
5. Hosting is still open at the decision layer. Current repo drift and the freshest proposal point to `Vultr VKE`, but Phase 1 is not implementation-ready until the rewritten foundation proposal clears all three risk gates at `LOW`.
6. Kafka, Debezium, Redis, Crossplane cluster-fleet automation, and other heavy control-plane machinery are normalized out of the minimum bot path. They only come back if a later initiative proves a real runtime need.
7. Estimated units below are normalized implementation slices, not calendar time. They are meant to keep future work initiative-sized rather than phase-sized.
8. Phase status is initiative-local:
   - `Research`
   - `Proposal`
   - `Risk`
   - `Implementation`
   A proposal with any `MEDIUM` or `HIGH` risk remains in proposal/risk revision, not implementation-ready.
9. Discord isolation is non-negotiable:
   - production uses the live Humility guild only
   - non-production uses separate bot apps, tokens, and sandbox guilds only

## Initiative List

### I1. Platform Control Cluster Foundation
- Scope: choose and lock the hosting substrate, bootstrap the platform/control cluster, define the OpenTofu entrypoint, remote state backend, base provider networking, and the provider-native object-storage/state pattern.
- Anti-scope: application cluster overlays, Flux topology, app deployment, identity, authorization, benchmarking, and runtime data services.
- Dependencies: none.
- Blocked by: unresolved host decision (`Hetzner` vs `Vultr`), conflict between stale Hetzner Phase 1 and current Vultr repo drift, and current Phase 1 risk findings.
- Components: `OpenTofu`, provider networking, managed Kubernetes or self-managed bootstrap path, remote state/object storage, provider firewall posture.
- Research status: current but conflicting. Fresh research favors `Vultr`; older proposal/risk artifacts still anchor on `Hetzner`.
- Proposal status: conflicted. `phase1-foundation.md` is superseded by `phase1-foundation-v2.md`, but v2 is not yet accepted.
- Risk status: not `LOW`. `phase1-audit.md` is `MEDIUM`; `phase1v2-audit.md` is `MEDIUM`; `phase1v2-shortcut.md` is `MEDIUM`.
- Implementation status: partial repo scaffolding exists, but it drifts from the older accepted proposal and is not backed by an accepted hookpoint plan.
- Estimated units: 4
- Phase: Proposal revision + risk rerun

### I2. Application Cluster Topology and GitOps Roots
- Scope: define the application-cluster layout, the `dev/staging/production` role split, per-cluster Flux roots, and the `base -> overlays -> clusters/<env>` GitOps topology.
- Anti-scope: bucket-watched Flux, permanent staging, dynamic-environment APIs, CI-driven cluster mutation, and application-level autoscaling.
- Dependencies: I1.
- Blocked by: I1 provider/cluster decision, ingress controller/TLS decision, and unresolved v2 audit items around public `dev` exposure and Flux bootstrap credentials.
- Components: `Flux CD`, Kustomize overlays, cluster roots, per-environment state keys, `dev/staging/production` application clusters.
- Research status: fresh and aligned. `phase1-environments-and-benchmarks.md` and `base-application-index.md` support this split.
- Proposal status: current draft embedded in `phase1-foundation-v2.md`.
- Risk status: not `LOW`. `phase1v2-audit.md` and `phase1v2-shortcut.md` still flag Flux credentials, stale bootstrap output, and topology residue.
- Implementation status: partial. Base/overlay manifests exist; per-cluster roots and correct Flux sync paths do not.
- Estimated units: 5
- Phase: Proposal revision + risk rerun

### I3. Bootstrap Secrets and Provider Credential Discipline
- Scope: define the bootstrap secret mechanism, per-environment credential boundaries, provider API key handling, Flux deploy credentials, and Terraform/OpenTofu state-concurrency controls.
- Anti-scope: long-term runtime secret management (`Infisical`), workload PKI, service-to-service mTLS, or a permanent dual-secret-system compatibility layer.
- Dependencies: I1, I2.
- Blocked by: unresolved choice between the v1 `SOPS + age` path and the v2 `sealed-secrets` path, plus open audit findings on provider credentials, Flux credentials, and locking.
- Components: `sealed-secrets` or `SOPS + age`, provider API keys, object-storage access keys, Flux deploy keys/PATs, state lock discipline.
- Research status: partial. Current artifacts describe the problem well but do not close the bootstrap-secret choice or the locking model.
- Proposal status: embedded in the competing Phase 1 proposals; no stable standalone proposal exists.
- Risk status: not `LOW`. Current audit findings are medium on credential scoping, Flux credentials, and state locking.
- Implementation status: partial manifests exist, but governance and rotation do not.
- Estimated units: 3
- Phase: Proposal revision + risk rerun

### I4. Baseline Observability and Benchmark Evidence
- Scope: stand up the minimum monitoring surface, fix provider-invalid storage classes, define benchmark metrics and storage, and make benchmark evidence reproducible enough to compare releases later.
- Anti-scope: full logs/traces/APM, hard CI benchmark gates, application SLO governance, and LLM video QA as a release gate.
- Dependencies: I1, I2, I3.
- Blocked by: storage-class choice, benchmark bucket ACL/versioning policy, and the unresolved ingress/TLS story for externally reachable tests.
- Components: `Prometheus`, `Grafana`, `Alertmanager`, valid provider storage classes, `k6`, benchmark result storage, minimal cluster/Flux alerts.
- Research status: current and useful. `phase1-environments-and-benchmarks.md` gives a real benchmark contract.
- Proposal status: current draft embedded in `phase1-foundation-v2.md`.
- Risk status: not `LOW`. Benchmark baseline integrity and public `dev` exposure remain open in the v2 audit.
- Implementation status: partial. Monitoring manifests exist, but they still contain stale `hcloud-volumes`; benchmark harness does not exist.
- Estimated units: 4
- Phase: Proposal revision + risk rerun

### I5. Delivery Supply Chain and Release Promotion
- Scope: define the CI/CD control plane around `Buildkite`, choose the OCI registry path, formalize image build/publish/promote flow, enforce PR-time vulnerability checks, and make multi-image promotion atomic at the release-pointer level.
- Anti-scope: Dagger as canonical CI, GitLab-runner assumptions, Kafka/Redis build orchestration as a default, mutable `latest` tags as correctness, and JFrog as a required baseline.
- Dependencies: I1 for implementation; proposal work can start now.
- Blocked by: registry decision and how much of the promotion model should live in Git versus object-storage pointers.
- Components: `Buildkite`, OCI registry, `Flux` release handoff, release manifests/pointers, `Trivy`, `Dependabot` or `Renovate`, later `Sigstore`.
- Research status: fresh enough for proposal work now. `buildkite-capabilities.md` plus the external supply-chain and multi-image promotion references cover the core decisions.
- Proposal status: none.
- Risk status: not run.
- Implementation status: none in this repo.
- Estimated units: 6
- Phase: Proposal

### I6. Runtime Data Plane
- Scope: choose the Phase 2 data substrate for platform workloads, especially `Postgres`, migrations, backup posture, `pg_stat_statements`, and how provider-native object storage is consumed by workloads.
- Anti-scope: Kafka/Debezium/Redis by default, dynamic-environment CDC, self-hosted S3 as the primary store, and full DR hardening.
- Dependencies: I1, I2, I3.
- Blocked by: unresolved Postgres placement, backup model, and whether the first production data path is managed or self-hosted.
- Components: `Postgres`, migrations, `pg_stat_statements`, provider-native object storage, backup/restore hooks.
- Research status: partial/open. The corpus frames the need, but there is no fresh dedicated data-plane research or proposal.
- Proposal status: none.
- Risk status: not run.
- Implementation status: none.
- Estimated units: 5
- Phase: Research

### I7. Edge Ingress and TLS
- Scope: pick the ingress controller and TLS path that sit behind the provider load balancer, define public hostnames, and make the public edge safe for real HTTP surfaces.
- Anti-scope: full identity/header propagation, `Pomerium`, app authorization, or Cloudflare hardening beyond the minimum ingress path.
- Dependencies: I1, I2, I3.
- Blocked by: the current proposal leaves the ingress controller unselected and public `dev` exposure under-specified.
- Components: provider load balancer, ingress controller, `cert-manager` or equivalent TLS automation, public subdomains, optional future `Kong` integration if re-justified.
- Research status: legacy-heavy and incomplete. Older corpora discuss `Kong`, but the fresh v2 work leaves the actual ingress-controller choice open.
- Proposal status: none. The issue is only mentioned as a dependency and risk.
- Risk status: not run as a standalone initiative.
- Implementation status: no accepted ingress implementation.
- Estimated units: 4
- Phase: Research

### I8. Identity and Human Access
- Scope: deploy the identity plane and human/operator access layer: `Authentik`, `Pomerium`, workforce OIDC/MFA, and `Smallstep` only if the platform later proves it needs PKI beyond Pomerium-backed access.
- Anti-scope: application business authorization, service-to-service policy, runtime secret management, and Cloudflare Access duplication.
- Dependencies: I1, I2, I3, I7.
- Blocked by: stale legacy coupling to VKE/Crossplane/terraform-controller assumptions and the lack of a fresh current-state auth proposal.
- Components: `Authentik`, `Pomerium`, OIDC, MFA, optional `Smallstep`.
- Research status: partial. `auth-v5-index.md` is detailed but stale; `pomerium-smallstep.md` is fresh and useful.
- Proposal status: none current.
- Risk status: not run.
- Implementation status: none.
- Estimated units: 6
- Phase: Research

### I9. Application Authorization Plane
- Scope: deliver the platform’s fine-grained app authorization layer around `OPAL/Cedar`, Authentik attribute sync, and app-side policy enforcement points.
- Anti-scope: identity provider choice, ingress auth, Logto reconsideration, and pretending the auth engine solves pagination or query-shaping by itself.
- Dependencies: I6, I8.
- Blocked by: lack of a fresh app-authorization design that is detached from the stale legacy control-plane assumptions.
- Components: `OPAL`, `Cedar`, Authentik sync, PEP contract, application-side auth checks.
- Research status: partial/legacy. `logto-rls-pagination.md` confirms the heavier auth plane still makes sense, but there is no current subsystem research for the actual app contract.
- Proposal status: none.
- Risk status: not run.
- Implementation status: none.
- Estimated units: 4
- Phase: Research

### I10. Runtime Hardening, Backup, and Cost Controls
- Scope: land the later hardening layers that survive normalization: network policy, runtime detection, backup/restore, edge lockdown, and cost visibility.
- Anti-scope: making `Cloudflare`, `Falco`, `Calico`, `Velero`, or `OpenCost` part of the minimum bot cutover path; self-hosted storage-platform work (`Ceph`, `MinIO`) as baseline.
- Dependencies: I1, I2, I5, I7.
- Blocked by: foundation stability and ingress/provider choices.
- Components: `Cloudflare`, `Calico`, `Falco`, `Velero`, `OpenCost`, later supply-chain signing.
- Research status: partial. The legacy expansion plan is useful, and the external supply-chain reference strengthens the CI/security slice, but the initiative still needs a current proposal.
- Proposal status: none.
- Risk status: not run.
- Implementation status: none.
- Estimated units: 6
- Phase: Research

### I11. Dynamic Environment Control Plane
- Scope: decide whether the platform actually needs API-driven preview environments, TTL cleanup, and cluster-claim automation beyond static GitOps application clusters.
- Anti-scope: defaulting back to the legacy Kafka/Debezium/Redis build bus, bucket-watched claim files, or Crossplane cluster-fleet automation without a proven need.
- Dependencies: I1, I2, I6.
- Blocked by: lack of evidence that Humility needs dynamic environments before the Discord bot is on the real platform, plus stale legacy assumptions about CDC and claim buses.
- Components: environment API, TTL cleanup, optional Crossplane, optional CDC/eventing, application-cluster claims.
- Research status: legacy-heavy/stale. The old gitops/platform-v2 material is informative but no longer trustworthy as a baseline.
- Proposal status: none.
- Risk status: not run.
- Implementation status: none.
- Estimated units: 6
- Phase: Research

### I12. Discord Workload Migration
- Scope: move the real Humility bot workload onto the platform using the minimum required runtime surfaces, keeping production and non-production Discord identities fully isolated.
- Anti-scope: forcing the full web/admin product, dynamic environments, or the full identity/authorization plane onto the minimum bot cutover path if the bot can run safely without them.
- Dependencies: I2, I3, I4, I5, I6, and I7 only if the cutover includes public HTTP surfaces.
- Blocked by: no accepted platform substrate, no accepted data-plane proposal, and no dedicated migration proposal for the Discord daemon/API boundary.
- Components: Discord daemon, required API surfaces, manifests, non-production bot apps/guilds, production token/guild isolation.
- Research status: minimal. The corpus states the destination architecture and Discord safety rules, but it does not yet contain a dedicated migration research artifact.
- Proposal status: none.
- Risk status: not run.
- Implementation status: none.
- Estimated units: 4
- Phase: Research

## Dependency Graph

### Minimum bot critical path

`I1 -> I2 -> I3 -> I4 -> I5 -> I6 -> I12`

Add `I7` into the critical path only if the first bot cutover also requires public HTTP endpoints for the API or web surfaces.

### Explicit dependency edges

- `I1 -> I2`
- `I1 -> I3`
- `I1 -> I4`
- `I1 -> I6`
- `I1 -> I7`
- `I2 -> I3`
- `I2 -> I4`
- `I2 -> I7`
- `I2 -> I12`
- `I3 -> I4`
- `I3 -> I12`
- `I4 -> I12`
- `I5 -> I10`
- `I5 -> I12`
- `I6 -> I9`
- `I6 -> I11`
- `I6 -> I12`
- `I7 -> I8`
- `I7 -> I10`
- `I7 -> I12` only if HTTP surfaces are in the first cut
- `I8 -> I9`

### Parallel lanes

- After I1 is reframed, I2, I3, and I4 can be revised in parallel as separate Phase 1 sub-initiatives instead of one monolithic proposal.
- I5 proposal work can run in parallel with the I1-I4 proposal rewrite because the Buildkite and release-promotion research is already current.
- I6 and I7 research can run in parallel once I1 is locked.
- I8 research can run in parallel with I6/I7, but it is not on the minimum bot path.
- I10 and I11 are explicitly off the minimum bot cutover path.

### What is not on the minimum bot path

- I8 Identity and Human Access
- I9 Application Authorization Plane
- I10 Runtime Hardening, Backup, and Cost Controls
- I11 Dynamic Environment Control Plane

Those initiatives matter for the long platform, but the corpus consistently points to them as later than the minimum path required to host the bot safely.

## Phase Mapping

### Proposal revision + risk rerun

- I1 Platform Control Cluster Foundation
- I2 Application Cluster Topology and GitOps Roots
- I3 Bootstrap Secrets and Provider Credential Discipline
- I4 Baseline Observability and Benchmark Evidence

These are really the current Phase 1 monolith split into smaller initiatives. None is implementation-ready because the current proposal package still has `MEDIUM` findings.

### Ready for first proposal now

- I5 Delivery Supply Chain and Release Promotion

The research corpus is current enough that this can move directly into proposal writing without another broad research pass.

### Needs research first

- I6 Runtime Data Plane
- I7 Edge Ingress and TLS
- I8 Identity and Human Access
- I9 Application Authorization Plane
- I10 Runtime Hardening, Backup, and Cost Controls
- I11 Dynamic Environment Control Plane
- I12 Discord Workload Migration

### Nothing is in implementation

No initiative has:
- a current accepted proposal
- all three risk gates at `LOW`
- hookpoint research

So the map contains no implementation-ready initiative yet.

## What’s Ready to Start NOW

1. Rewrite the current Phase 1 package as four separate initiatives: I1 through I4.
   - This is the highest-leverage immediate move.
   - The work is not new research; it is normalization, proposal tightening, and risk closure.
   - The target is clear: get all four to `LOW` instead of keeping foundation, GitOps, secrets, and benchmarks fused into one draft.

2. Start proposal writing for I5 Delivery Supply Chain and Release Promotion.
   - Current research is sufficient.
   - It is independent enough to run while I1 through I4 are being revised.
   - It is on the bot critical path and currently has no platform-specific proposal.

3. Start research for I6 Runtime Data Plane and I7 Edge Ingress and TLS.
   - Those are the next blockers after the foundation rewrite.
   - They are both closer to the minimum bot cutover path than identity, authorization, or dynamic environments.

4. Defer I8, I9, I10, and I11 until after the minimum bot path is stable.
   - They are important platform initiatives.
   - They are not the fastest path to getting the Discord bot onto the real platform.

5. Do not start implementation on any initiative yet.
   - The current corpus has no initiative that has cleared `research -> proposal -> risk` cleanly.
   - The immediate next step is proposal organization and risk closure, not coding.
