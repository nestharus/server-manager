# Test Agent: Platform Bootstrap Infrastructure Validation

## Scope

You are a **test-only** agent. You must NOT modify any `.tf` or `.tfbackend` files. Your job is to write a validation script that checks the Platform Bootstrap infrastructure files for correctness.

## Context

The Platform Bootstrap implementation created 5 infrastructure files:

1. `infra/bootstrap/state-backend/main.tf` — one-time Vultr Object Storage bootstrap (local state)
2. `infra/modules/platform-network/main.tf` — VPC module (one per environment)
3. `infra/modules/platform-cluster/main.tf` — VKE cluster module (one per environment)
4. `infra/environments/dev/main.tf` — dev environment root composing both modules
5. `infra/environments/dev/backend.tfbackend` — S3 backend config for dev

## Task

Write a validation script at `infra/tests/validate_platform_bootstrap.sh` that performs the following checks:

### Formatting checks
- Run `tofu fmt -check -recursive infra/` (or `terraform fmt -check -recursive infra/` if tofu is unavailable)
- If neither tool is available, use `grep`-based heuristics for indentation consistency

### Structural validation
- Run `tofu validate` in each root directory (`infra/bootstrap/state-backend/`, `infra/environments/dev/`) after `tofu init -backend=false`
- If tofu is unavailable, do structural checks with grep/awk

### Content assertions (always run, no tool dependency)
- `infra/bootstrap/state-backend/main.tf` declares `vultr_object_storage` and `vultr_object_storage_bucket` resources
- `infra/bootstrap/state-backend/main.tf` has `enable_versioning = true`
- `infra/modules/platform-network/main.tf` declares `vultr_vpc` resource
- `infra/modules/platform-cluster/main.tf` declares `vultr_kubernetes` resource
- `infra/modules/platform-cluster/main.tf` exposes `kube_config` output marked sensitive
- `infra/environments/dev/main.tf` uses `backend "s3" {}`
- `infra/environments/dev/main.tf` references both `../../modules/platform-network` and `../../modules/platform-cluster`
- `infra/environments/dev/backend.tfbackend` contains bucket `humility-tfstate`
- Provider version constraint `~> 2.30` appears in both roots
- OpenTofu version constraint `>= 1.8.0` appears in both roots

### Module isolation assertions
- Modules (`platform-network`, `platform-cluster`) must NOT contain `terraform {}` or `provider` blocks
- Modules must NOT contain hardcoded environment names (no literal `"dev"`, `"staging"`, `"production"`)

### Security assertions
- No hardcoded credentials, API keys, or tokens in any `.tf` file
- Sensitive outputs (`s3_access_key`, `s3_secret_key`, `kube_config`) are marked `sensitive = true`
- `backend.tfbackend` does not contain actual credentials

### Script requirements
- The script must be `#!/usr/bin/env bash` with `set -euo pipefail`
- Print a clear PASS/FAIL for each check
- Exit 0 only if all checks pass, exit 1 otherwise
- Run from the repo root (`/home/nes/discord`)

Write ONLY the test script. Do not modify any other files.
