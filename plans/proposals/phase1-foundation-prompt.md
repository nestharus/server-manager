# Proposal: Phase 1 — Foundation Bootstrap

## Hard rules
YOU are the proposal-writing agent. Write the proposal to
`plans/proposals/phase1-foundation.md`.

- **DO** use your Read/Bash/Grep tools to read the input files listed below
- **DO** write the output file using your Write tool
- **DO NOT** modify any file other than `plans/proposals/phase1-foundation.md`
- **DO NOT** spawn or delegate to other agents

## Context

Read these files for full context:
- `plans/unified-platform-index.md` — the merged platform index (focus on Phase 1 and the critical path in §6)
- `plans/platform-decisions-overlay.md` — locked decisions that override parts of the unified index
- `plans/research/hetzner-vs-vultr.md` — Hetzner is the chosen provider
- `plans/research/buildkite-capabilities.md` — Buildkite is the CI engine
- `plans/research/self-hosted-s3.md` — Hetzner Object Storage is the default S3
- `plans/research/pomerium-smallstep.md` — auth layer context
- `AGENTS.md` — workflow rules and project context

## What Phase 1 delivers

Phase 1 is the **Foundation Bootstrap** — the minimum infrastructure
that must exist before any application (including the Discord bot)
can be deployed.

After Phase 1 completes:
- A production k3s cluster runs on Hetzner Cloud
- OpenTofu manages the infrastructure declaratively
- Flux CD watches a Git repo and reconciles cluster state
- A secrets manager is deployed (Infisical or sealed-secrets)
- Hetzner Object Storage is wired up for artifacts and state
- A base monitoring stack exists (Prometheus + Grafana minimum)
- The cluster can accept Helm charts and Kustomize overlays via Flux

## Locked decisions for Phase 1

- **Provider**: Hetzner Cloud
- **K8s**: k3s via `kube-hetzner` (terraform-hcloud-kube-hetzner OpenTofu module)
- **IaC**: OpenTofu
- **GitOps**: Flux CD
- **Object storage**: Hetzner Object Storage (S3-compatible)
- **Secrets**: Research needed — Infisical (from legacy specs) vs sealed-secrets vs external-secrets-operator. Pick the simplest that works.
- **Ingress**: Kong (confirmed, but may be Phase 2 if the bot doesn't need external ingress)
- **CI**: Buildkite (agents need to run somewhere — on this cluster or external?)

## Required sections

### 1. Executive summary (≤300 words)

### 2. Infrastructure components
For each: what it is, why it's needed, how it's deployed, what it depends on.

### 3. kube-hetzner cluster specification
- Node count and sizing (minimum for the full platform, not just Phase 1)
- HA control plane configuration
- Network: private networking, firewall rules
- Load balancer configuration
- Storage: volumes for stateful workloads

### 4. OpenTofu structure
- Module layout (adapt from RFQ's infra/ pattern)
- Remote state (where to store — Hetzner Object Storage?)
- Variables and secrets management
- Environment separation (staging vs production)

### 5. Flux CD setup
- Source: Git repository structure for manifests
- Kustomization hierarchy: base → overlays → environments
- How Flux watches and reconciles
- How Helm charts are managed (HelmRepository + HelmRelease)

### 6. Secrets management
- Evaluate: Infisical vs sealed-secrets vs external-secrets-operator
- Pick one for Phase 1 and justify
- How secrets flow from management to pods

### 7. Base observability
- Prometheus (metrics)
- Grafana (dashboards)
- Loki or equivalent (logs) — or defer to Phase 2?
- Alertmanager (minimum alerts: node down, pod crash loop)

### 8. Buildkite agent deployment
- Can Buildkite agents run on this cluster?
- Agent pool sizing
- Docker-in-Docker or Kubernetes executor?
- How agents connect to Buildkite's control plane

### 9. Cost model
- Hetzner compute: control plane nodes + workers
- Hetzner Object Storage
- Hetzner Load Balancer
- Buildkite pricing (per-agent)
- Total monthly estimate

### 10. Definition of done
What specific tests prove Phase 1 is complete?
- Cluster responds to kubectl
- Flux reconciles a test manifest from Git
- A secret is created and readable by a test pod
- Prometheus scrapes node metrics
- Grafana dashboard loads
- Object storage is reachable from a test pod

### 11. Risks

### 12. What Phase 2 needs from Phase 1
List exactly what Phase 2 (Bot Production Baseline) expects to exist after Phase 1.

## Output
Write to `plans/proposals/phase1-foundation.md`. 3000-5000 words.
