# Proposal: Phase 1 — Foundation Bootstrap

## Hard rules
YOU are the proposal-writing agent. Write the proposal to
`plans/proposals/phase1-foundation.md`. Do not modify other files.
Do not spawn other agents.

## Objective
Write the Phase 1 proposal for the minimum infrastructure bootstrap
required to run the platform on `Hetzner` using `k3s` via
`kube-hetzner`, with `Flux CD`, secrets management, and provider-native
object storage wired up.

## Read for context
- `plans/unified-platform-index.md`
- `plans/platform-decisions-overlay.md`
- `plans/research/hetzner-vs-vultr.md`
- `plans/research/buildkite-capabilities.md`
- `plans/research/self-hosted-s3.md`
- `plans/research/pomerium-smallstep.md`

## Locked decisions to respect
- Hosting: `Hetzner Cloud`
- Kubernetes: `k3s` via `kube-hetzner`
- Object storage: `Hetzner Object Storage`
- Postgres: self-managed on cluster or external Postgres
- Identity: `Authentik`
- Authorization: `OPAL/Cedar`
- Access proxy: `Pomerium`
- `Smallstep`: conditional only if broader PKI/CA scope is required
- CI: `Buildkite`
- GitOps: `Flux CD`
- IaC: `OpenTofu` + `kube-hetzner`
- Ingress: `Kong`
- S3 fallback: `SeaweedFS`

## Deliverable
Write a proposal with these sections:
1. Executive summary
2. Scope of Phase 1
3. Architecture and component choices
4. What Phase 1 delivers
5. What is explicitly out of scope
6. Risks and open questions
7. Exit criteria

## Anti-goals
- Do not implement anything
- Do not write Terraform/OpenTofu, Kubernetes, or Flux code
- Do not redesign already locked platform decisions
- Do not block on the still-running `Logto` or `OpenTofu provider`
  research unless they are required to state an open question cleanly
