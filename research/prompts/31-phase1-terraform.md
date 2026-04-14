# Research: Phase 1 Foundation — Terraform Infrastructure Files

## Scope

Research the specific Terraform/OpenTofu file structure needed to
bootstrap a Hetzner Cloud k3s cluster using the `kube-hetzner` module.

This is Phase 1 infrastructure code — not application code. The platform
decision is already locked:

- **Provider**: Hetzner Cloud (`hcloud` provider `~> 1.49`)
- **Cluster**: k3s via `kube-hetzner` Terraform module
- **IaC tool**: OpenTofu (Terraform-compatible, `>= 1.6.0`)
- **Remote state**: Hetzner Object Storage (S3-compatible)
- **Environments**: staging (minimal) and production (HA)
- **Region**: `fsn1` (Falkenstein)

## Deliverable

Write your findings to `research/31-phase1-terraform.md`.

## Questions to answer

1. What is the canonical file structure for a root Terraform module that
   uses `kube-hetzner`? What files are needed at minimum?
2. What provider configuration does `kube-hetzner` require? What version
   constraints are appropriate?
3. What variables should the root module declare for Hetzner bootstrap?
   Include: API token, SSH keys, environment name, cluster name,
   location, node sizing, control plane count, worker count.
4. How does `kube-hetzner` module instantiation work? What are the key
   parameters for: control plane HA (embedded etcd), worker nodes,
   private networking, load balancer/ingress seam?
5. What should staging vs production `terraform.tfvars` look like?
   Staging: single control plane, minimal workers. Production: 3
   control planes (HA), more workers.
6. How should remote state be configured for Hetzner Object Storage
   (S3-compatible backend)?

## Anti-goals

- Do NOT design the Flux CD, Kong, or secrets layers — those are separate.
- Do NOT propose changes to the overall architecture — decisions are locked.
- Do NOT write implementation code — only research findings.
- Do NOT recommend alternative providers or tools.

## Evidence quality

Cite `kube-hetzner` module documentation, Terraform/OpenTofu docs,
and Hetzner Cloud provider docs. Prefer primary sources.

## Output path

`research/31-phase1-terraform.md`
