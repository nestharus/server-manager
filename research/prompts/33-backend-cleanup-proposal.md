# Proposal: Terraform Backend Configuration Cleanup

## Scope

Write a proposal to clean up the `infra/main.tf` backend block by
splitting environment-specific values into per-environment `.tfbackend`
files.

## Context

Read these files for context:
- `research/33-backend-cleanup.md` — problem research
- `research/33-backend-cleanup-needs.md` — Humility-specific synthesis
- `infra/main.tf` — current backend configuration
- `infra/environments/staging/terraform.tfvars` — existing staging env
- `infra/environments/production/terraform.tfvars` — existing prod env

## Requirements

The proposal should specify:

1. **What stays in `main.tf`**: The `backend "s3"` block retains only
   environment-independent attributes (region, skip flags) and a comment
   explaining the `.tfbackend` pattern.

2. **What goes in `.tfbackend` files**: `bucket`, `key`, and `endpoints`
   as per-environment partial backend configs at
   `infra/environments/<env>/backend.tfbackend`.

3. **Usage pattern**: `tofu init -backend-config=environments/<env>/backend.tfbackend`

4. **File content**: Exact HCL content for the cleaned `main.tf` and
   both `.tfbackend` files.

## Anti-goals

- Do NOT implement the changes (just propose)
- Do NOT add CI/CD automation
- Do NOT change any other Terraform files
- Do NOT add new providers or modules

## Output path

Write your proposal to: `proposals/33-backend-cleanup.md`
