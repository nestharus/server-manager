# Code Agent: Phase 1 Foundation — Terraform Infrastructure Files

## Context

You are the implementation agent for the Phase 1 Foundation Terraform
infrastructure. You write code that makes the validation tests pass.

Read the following for context:
- `proposals/31-phase1-terraform.md` — the validated proposal
- `plans/proposals/phase1-foundation.md` — overarching Phase 1 context
- `research/31-phase1-terraform.md` — problem research
- `research/31-phase1-terraform-needs.md` — synthesized needs
- `research/31-hookpoints.md` — hookpoint findings
- `infra/tests/validate_terraform.sh` — the validation tests to satisfy

## What to implement

Create the following 5 Terraform/OpenTofu files:

### 1. `infra/main.tf`

Root Terraform entrypoint:
- `terraform {}` block:
  - `required_version = ">= 1.6.0"`
  - `required_providers` with `hcloud` from `hetznercloud/hcloud`
    version `~> 1.49`
  - Remote state backend using S3-compatible Hetzner Object Storage
    (use `backend "s3"` with placeholder endpoint/bucket config and
    comments explaining it's Hetzner Object Storage)
- `provider "hcloud"` block using `var.hcloud_token`

### 2. `infra/variables.tf`

Variable declarations:
- `hcloud_token` — string, sensitive, Hetzner Cloud API token
- `ssh_key_ids` — list(number), SSH key IDs to inject into nodes
- `environment` — string, environment name (staging/production)
- `cluster_name` — string, cluster identifier
- `location` — string, Hetzner region, default `"fsn1"`
- `control_plane_count` — number, control plane node count
- `worker_count` — number, worker node count
- `control_plane_server_type` — string, Hetzner server type for CP,
  default `"cpx21"`
- `worker_server_type` — string, Hetzner server type for workers,
  default `"cpx21"`
- `network_zone` — string, Hetzner network zone, default `"eu-central"`

### 3. `infra/cluster.tf`

kube-hetzner module instantiation:
- Module `cluster` sourced from `kube-hetzner/terraform-hcloud-kube-hetzner`
  (or the GitHub path) with an appropriate version
- Control plane configuration:
  - Count from `var.control_plane_count`
  - Server type from `var.control_plane_server_type`
  - Location from `var.location`
- Worker node configuration:
  - Count from `var.worker_count`
  - Server type from `var.worker_server_type`
- Private networking enabled
- SSH keys from `var.ssh_key_ids`
- Cluster name from `var.cluster_name`
- Comments describing: HA embedded etcd, private networking,
  load balancer/ingress seam

### 4. `infra/environments/staging/terraform.tfvars`

Staging values:
- `environment = "staging"`
- `cluster_name = "humility"`
- `location = "fsn1"`
- `control_plane_count = 1`
- `worker_count = 1`
- `control_plane_server_type = "cpx21"`
- `worker_server_type = "cpx21"`

### 5. `infra/environments/production/terraform.tfvars`

Production values:
- `environment = "production"`
- `cluster_name = "humility"`
- `location = "fsn1"`
- `control_plane_count = 3`
- `worker_count = 3`
- `control_plane_server_type = "cpx31"`
- `worker_server_type = "cpx31"`

## Rules

- Do NOT modify test files — make the tests pass as-is
- Follow idiomatic Terraform/HCL conventions
- Add comments where the architecture is non-obvious
- Mark sensitive variables as `sensitive = true`
- No secrets or tokens in any file — use variables
- Keep files clean and minimal — no over-engineering

## Verification

After writing all files, run `bash infra/tests/validate_terraform.sh`
to verify your implementation passes the tests.
