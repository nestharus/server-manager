# Synthesis: Backend Cleanup Needs for Humility Infrastructure

Date: 2026-04-14

## Context

This synthesis maps the backend-cleanup research against the Humility
project's specific infrastructure context: a Hetzner Cloud deployment
with S3-compatible Object Storage for Terraform state, two environments
(staging, production), and OpenTofu as the IaC tool.

## Problem

`infra/main.tf` currently hardcodes environment-specific backend values
directly in the `backend "s3"` block:

- `bucket = "humility-terraform-state"` — shared across envs but
  currently baked into source
- `key = "humility/ENVIRONMENT/terraform.tfstate"` — literal
  placeholder, not parameterized
- `region = "fsn1"` — Hetzner-specific, same across envs
- `endpoint = "https://fsn1.your-objectstorage.com"` — TODO placeholder
- `force_path_style = true` — Hetzner Object Storage requires this

OpenTofu/Terraform backend blocks cannot use variables, `locals`, or
data sources. This is a fundamental language limitation, not a
configuration oversight.

## Humility-Specific Needs

1. **Two environments, one source file**: Staging and production must
   use separate state files (`staging/terraform.tfstate` vs
   `production/terraform.tfstate`) but share the same `main.tf`.

2. **Hetzner Object Storage S3 compatibility**: The `skip_*` flags and
   `force_path_style` are required for Hetzner's S3-compatible endpoint
   and are environment-independent. These should stay in `main.tf`.

3. **Bucket endpoint is a TODO**: The current endpoint
   (`https://fsn1.your-objectstorage.com`) is a placeholder. The real
   endpoint will be known after Hetzner Object Storage bucket creation.
   The `.tfbackend` files should carry this as a TODO marker.

4. **Credentials via env vars**: `AWS_ACCESS_KEY_ID` and
   `AWS_SECRET_ACCESS_KEY` are passed via environment variables (Railway
   or local `.env`). These do NOT go in `.tfbackend` files.

5. **Existing environment structure**: `infra/environments/staging/`
   and `infra/environments/production/` already hold `terraform.tfvars`.
   The `.tfbackend` files should live alongside them for consistency.

## What Stays in `main.tf`

- `region` (same across envs for Hetzner fsn1)
- `skip_credentials_validation = true`
- `skip_metadata_api_check = true`
- `skip_region_validation = true`
- `skip_requesting_account_id = true`
- A comment explaining the `.tfbackend` pattern

## What Moves to `.tfbackend` Files

- `bucket` — the Object Storage bucket name
- `key` — environment-specific state file path
- `endpoints` — the Object Storage S3-compatible endpoint URL

## Gaps

None identified. The `.tfbackend` pattern is well-established and
directly applicable to this project's two-environment setup.
