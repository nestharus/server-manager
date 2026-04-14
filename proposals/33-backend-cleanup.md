# Proposal: Terraform Backend Configuration Cleanup

Date: 2026-04-14

## Goal

Move environment-specific backend locator values out of
`infra/main.tf` and into per-environment `.tfbackend` files so the
checked-in root module stays environment-agnostic while staging and
production each initialize against an explicit state location.

This proposal is design only. It does not implement the change.

## Design Summary

The backend should be split into two layers:

- `infra/main.tf` keeps the `backend "s3"` declaration, the
  environment-independent Hetzner S3-compatibility settings, and a
  short comment explaining that concrete backend values come from
  per-environment `.tfbackend` files.
- `infra/environments/staging/backend.tfbackend` owns the staging state
  bucket/key/endpoint values.
- `infra/environments/production/backend.tfbackend` owns the production
  state bucket/key/endpoint values.

This matches the current repository shape:

- one shared root module
- two existing environment directories
- OpenTofu initialization performed per environment

It also fixes the current mismatch where `infra/main.tf` says backend
values should be supplied externally but still hardcodes them in source.

## File Ownership

### What stays in `infra/main.tf`

The checked-in backend block should retain only values that are stable
across environments and are part of the Hetzner Object Storage backend
behavior rather than the identity of a particular state file:

- `region = "fsn1"`
- `force_path_style = true`
- `skip_credentials_validation = true`
- `skip_metadata_api_check = true`
- `skip_region_validation = true`
- `skip_requesting_account_id = true`
- a short comment documenting the `.tfbackend` pattern

The backend block should not keep:

- `bucket`
- `key`
- `endpoint`

For this proposal, the per-environment files should use the current
OpenTofu `endpoints` map form rather than the deprecated singular
`endpoint` argument.

### What goes in `.tfbackend` files

Each environment-specific backend file should contain only the concrete
locator values for that environment:

- `bucket`
- `key`
- `endpoints`

The bucket stays duplicated across the two files even if the value is
currently the same, because it is still part of the concrete backend
selection and belongs with the rest of the per-environment backend
inputs.

## Usage Pattern

Operators should initialize from the `infra/` directory with the
environment-specific backend file:

```bash
tofu init -backend-config=environments/<env>/backend.tfbackend
```

Concrete examples:

```bash
tofu init -backend-config=environments/staging/backend.tfbackend
tofu init -backend-config=environments/production/backend.tfbackend
```

This proposal does not add wrapper scripts, CI automation, or any other
operator workflow changes.

## Exact File Content

### `infra/main.tf`

```hcl
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.49"
    }
  }

  # Hetzner Object Storage is S3-compatible. Keep only environment-
  # independent backend settings here and pass bucket/key/endpoints via
  # `tofu init -backend-config=environments/<env>/backend.tfbackend`.
  backend "s3" {
    region = "fsn1"

    force_path_style            = true
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
  }
}

provider "hcloud" {
  token = var.hcloud_token
}
```

### `infra/environments/staging/backend.tfbackend`

```hcl
bucket = "humility-terraform-state"
key    = "humility/staging/terraform.tfstate"

endpoints = {
  s3 = "https://fsn1.your-objectstorage.com"
}
```

### `infra/environments/production/backend.tfbackend`

```hcl
bucket = "humility-terraform-state"
key    = "humility/production/terraform.tfstate"

endpoints = {
  s3 = "https://fsn1.your-objectstorage.com"
}
```

## Rationale

This design keeps backend concerns cleanly separated:

- `main.tf` declares backend type and stable compatibility settings
- each environment file selects a concrete state location

That removes the current literal `ENVIRONMENT` placeholder from source
and replaces it with explicit backend initialization per environment.

The proposal intentionally does not:

- change any other Terraform files
- add CI/CD initialization logic
- introduce new providers or modules
- move credentials into `.tfbackend` files

Credentials should continue to come from environment variables such as
`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, not from checked-in
backend configuration.

## Expected Outcome

After implementation of this proposal, the repository will have one
shared backend declaration in `main.tf` and two explicit backend config
files beside the existing environment `terraform.tfvars` files. The
operator will choose staging or production state at `tofu init` time
without editing source or relying on a fake placeholder in the backend
key.
