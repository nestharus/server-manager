# Test Agent: Phase 1 Foundation — Terraform Infrastructure Validation

## Context

You are the test-writing agent for the Phase 1 Foundation Terraform
infrastructure files. You ONLY write validation/test files.

Read the following for context:
- `proposals/31-phase1-terraform.md` — the validated proposal
- `plans/proposals/phase1-foundation.md` — overarching Phase 1 context
- `research/31-hookpoints.md` — hookpoint findings

## What to write

Create a validation script at `infra/tests/validate_terraform.sh` that:

1. Checks that all required files exist:
   - `infra/main.tf`
   - `infra/variables.tf`
   - `infra/cluster.tf`
   - `infra/environments/staging/terraform.tfvars`
   - `infra/environments/production/terraform.tfvars`

2. Validates Terraform syntax (if `tofu` or `terraform` is available):
   - `tofu validate` or `terraform validate` on the `infra/` directory

3. Checks structural requirements:
   - `main.tf` declares the `hcloud` provider with version constraint
   - `main.tf` has a `terraform {}` block with `required_version`
   - `variables.tf` declares `hcloud_token` as sensitive
   - `variables.tf` declares core variables (environment, cluster_name,
     location, control_plane_count, worker_count, ssh_key_ids)
   - `cluster.tf` references the `kube-hetzner` module
   - Staging tfvars sets `control_plane_count = 1`
   - Production tfvars sets `control_plane_count = 3`
   - Both tfvars set `cluster_name = "humility"` and `location = "fsn1"`

4. Checks security requirements:
   - `hcloud_token` variable is marked `sensitive = true`
   - No hardcoded tokens or secrets in any `.tf` or `.tfvars` file
   - Remote state backend is configured (S3-compatible)

Make the script executable. Use `grep`-based checks for structural
validation (no Terraform installation required for basic checks).

## Rules

- You ONLY write tests/validation — do NOT write any implementation files
- Do NOT create `main.tf`, `variables.tf`, `cluster.tf`, or tfvars files
- Do NOT modify any existing implementation files
- Make the test script self-contained and runnable with `bash`

## Output

Write to: `infra/tests/validate_terraform.sh`
Create the directory if needed: `mkdir -p infra/tests`
