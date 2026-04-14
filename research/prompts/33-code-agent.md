# Code Agent: Backend Cleanup Implementation

## Your role

You are an implementation agent. You write code that makes tests pass.
You do NOT modify test files.

## Context

Read these files:
- `proposals/33-backend-cleanup.md` — the design
- `research/33-hookpoints.md` — what exists and what needs to change
- `infra/tests/validate_terraform.sh` — the tests you must satisfy
- `infra/main.tf` — the file to modify
- `infra/environments/staging/terraform.tfvars` — existing staging env
- `infra/environments/production/terraform.tfvars` — existing prod env

## Deliverable

1. **Modify `infra/main.tf`**: Replace the current `backend "s3"` block
   with a cleaned version that:
   - Removes `bucket`, `key`, `endpoint`, and `force_path_style`
   - Keeps `region = "eu-central-1"` (or appropriate value)
   - Keeps all `skip_*` flags
   - Adds a comment explaining the `.tfbackend` pattern
   - Keeps the `required_version`, `required_providers`, and `provider`
     blocks unchanged

2. **Create `infra/environments/staging/backend.tfbackend`** with:
   - `bucket = "server-manager-tfstate"`
   - `key = "infra/staging/terraform.tfstate"`
   - `endpoints = { s3 = "https://fsn1.your-objectstorage.com" }`
   - A comment showing the init command

3. **Create `infra/environments/production/backend.tfbackend`** with:
   - `bucket = "server-manager-tfstate"`
   - `key = "infra/production/terraform.tfstate"`
   - `endpoints = { s3 = "https://fsn1.your-objectstorage.com" }`
   - A comment showing the init command

4. Run `bash infra/tests/validate_terraform.sh` to verify all tests pass.

## Anti-goals

- Do NOT modify test files
- Do NOT change `variables.tf` or `cluster.tf`
- Do NOT add new Terraform providers or modules
