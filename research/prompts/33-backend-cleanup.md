# Research: Terraform Backend Configuration Cleanup

## Scope

Investigate the current `infra/main.tf` backend configuration and
document the problem space around hardcoded environment-specific values
in OpenTofu/Terraform backend blocks.

## Context

The project has an `infra/main.tf` that currently hardcodes backend
values (bucket name, key path, region, endpoint) directly in the
`backend "s3"` block. This is problematic because:

1. Backend blocks in Terraform/OpenTofu cannot use variables
2. Different environments (staging, production) need different state
   file paths
3. The current approach bakes a single environment's config into source

The standard solution is per-environment `.tfbackend` files passed via
`tofu init -backend-config=<path>`.

## Deliverable

Write `research/33-backend-cleanup.md` with:

1. **Current state**: Document the exact backend block in `infra/main.tf`
   and what values are hardcoded
2. **Terraform/OpenTofu backend limitations**: Why variables cannot be
   used in backend blocks, and how the community handles this
3. **`.tfbackend` file pattern**: How partial backend configs work with
   `-backend-config` flag
4. **What stays in `main.tf`**: Which backend attributes are
   environment-independent and should remain in the HCL source
5. **What moves to `.tfbackend`**: Which attributes are
   environment-specific and should be externalized

## Anti-goals

- Do NOT propose a solution or design
- Do NOT write code or HCL
- Do NOT make recommendations about tooling changes
- Do NOT discuss CI/CD pipeline integration

## Evidence quality bar

Reference official Terraform/OpenTofu documentation for backend
configuration limitations. Cite real patterns from community usage.

## Output path

Write your findings to: `research/33-backend-cleanup.md`
