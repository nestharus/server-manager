# Proposal: Phase 1 Foundation — Terraform Infrastructure Files

## Context

You are writing a technical proposal for the specific Terraform/OpenTofu
files needed to bootstrap the Phase 1 Foundation infrastructure on
Hetzner Cloud.

Read the following files for context:
- `research/31-phase1-terraform.md` — problem research findings
- `research/31-phase1-terraform-needs.md` — synthesized needs
- `plans/proposals/phase1-foundation.md` — the overarching Phase 1 proposal

## Scope

Propose the exact file structure and content design for these 5 files:

1. `infra/main.tf` — Root Terraform entrypoint
   - `terraform {}` block with required_version `>= 1.6.0`
   - `hcloud` provider from `hetznercloud/hcloud` version `~> 1.49`
   - Remote state backend using Hetzner Object Storage (S3-compatible)
   - Provider configuration block

2. `infra/variables.tf` — Variable declarations
   - `hcloud_token` (string, sensitive)
   - `ssh_key_ids` (list of string)
   - `environment` (string)
   - `cluster_name` (string)
   - `location` (string, default `fsn1`)
   - `control_plane_count` (number)
   - `worker_count` (number)
   - Control plane and worker server types
   - Any other variables referenced by `kube-hetzner` module

3. `infra/cluster.tf` — kube-hetzner module instantiation
   - Module source and version
   - Control plane configuration with HA (embedded etcd)
   - Worker node configuration
   - Private networking
   - Load balancer / ingress seam
   - Environment-driven sizing via variables

4. `infra/environments/staging/terraform.tfvars` — Staging values
   - `environment = "staging"`
   - `cluster_name = "humility"`
   - `location = "fsn1"`
   - `control_plane_count = 1` (no HA for staging)
   - Smaller worker count and server types

5. `infra/environments/production/terraform.tfvars` — Production values
   - `environment = "production"`
   - `cluster_name = "humility"`
   - `location = "fsn1"`
   - `control_plane_count = 3` (full HA)
   - Larger worker count and server types

## Deliverable

Write your proposal to `proposals/31-phase1-terraform.md`.

Include:
- File-by-file design with key decisions
- Architecture notes (why these choices)
- Tradeoffs acknowledged
- Anti-scope (what these files do NOT cover)

## Anti-goals

- Do NOT write implementation code — only propose the design
- Do NOT change locked decisions (Hetzner, kube-hetzner, OpenTofu)
- Do NOT include Flux CD, Kong, secrets, or Buildkite config

## Output path

`proposals/31-phase1-terraform.md`
