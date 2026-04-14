# Research: Terraform Backend Configuration Cleanup

Date: 2026-04-14

## Scope

This note documents the current `infra/main.tf` backend configuration
and the problem space around hardcoded environment-specific values in
Terraform/OpenTofu backend blocks.

It is limited to:

- the exact `backend "s3"` block currently checked into `infra/main.tf`
- backend configuration limitations in Terraform and OpenTofu
- the documented partial-backend / `-backend-config` pattern
- which current backend attributes are environment-independent versus
  environment-specific

It does not:

- propose a design or migration plan
- write new HCL or shell commands for the repo
- discuss CI/CD integration
- recommend broader tooling changes

## Executive Findings

- `infra/main.tf` currently hardcodes four concrete backend locator
  values in source: `bucket`, `key`, `region`, and `endpoint`.
- The `key` value is not actually parameterized today. The string
  `humility/ENVIRONMENT/terraform.tfstate` is a literal placeholder in
  source, not a variable interpolation that Terraform/OpenTofu will
  resolve during backend initialization.
- Terraform’s language rules are strict: the `terraform` block only
  accepts constant values and backend blocks cannot refer to named
  objects such as input variables or resources.
- OpenTofu’s current documentation, as accessed on 2026-04-14, is more
  permissive than Terraform’s: it allows variables and locals in
  backend configuration only when they can be fully resolved during
  `tofu init`, before any state is available. It still forbids
  references to state-derived values and provider-defined functions.
- Both Terraform and OpenTofu document partial backend configuration via
  `init -backend-config=...` as the standard way to keep dynamic or
  sensitive backend arguments outside the checked-in backend block.
- In this repository’s current `s3` backend, the S3-compatibility flags
  are backend-behavior settings, while `bucket`, `key`, `region`, and
  `endpoint` identify a concrete state location and therefore carry the
  environment coupling.

## Primary Sources

- Local source:
  - `infra/main.tf`
- Official Terraform docs:
  - https://developer.hashicorp.com/terraform/language/block/terraform
  - https://developer.hashicorp.com/terraform/language/backend
  - https://developer.hashicorp.com/terraform/cli/commands/init
  - https://developer.hashicorp.com/terraform/language/backend/s3
- Official OpenTofu docs:
  - https://opentofu.org/docs/language/settings/backends/configuration/
  - https://opentofu.org/docs/language/settings/backends/s3/
- Community usage examples:
  - https://discuss.hashicorp.com/t/backend-config-flag-not-working/37674
  - https://discuss.hashicorp.com/t/greenfield-project-with-terraform-best-practices-for-structure/37565
  - https://stackoverflow.com/questions/48783690/terraform-using-a-config-file-for-referencing-backend-data

## 1. Current State

`infra/main.tf` currently contains this backend block:

```hcl
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.49"
    }
  }

  # Hetzner Object Storage is S3-compatible, so the standard s3 backend works
  # here. Keep concrete bucket keys and credentials outside source and pass them
  # during `tofu init` with environment-specific backend config.
  backend "s3" {
    bucket = "humility-terraform-state"
    key    = "humility/ENVIRONMENT/terraform.tfstate"
    region = "fsn1"

    endpoint = "https://fsn1.your-objectstorage.com"

    force_path_style            = true
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
  }
}
```

Hardcoded values present today:

| Attribute | Current value | Why it matters |
|---|---|---|
| `bucket` | `humility-terraform-state` | Selects the concrete object-store bucket that holds state |
| `key` | `humility/ENVIRONMENT/terraform.tfstate` | Selects the concrete object path for the state file |
| `region` | `fsn1` | Selects the backend region value expected by the S3 backend |
| `endpoint` | `https://fsn1.your-objectstorage.com` | Points the S3 backend at a specific S3-compatible API endpoint |
| `force_path_style` | `true` | S3-compatibility behavior, not environment identity |
| `skip_credentials_validation` | `true` | S3-compatibility behavior, not environment identity |
| `skip_metadata_api_check` | `true` | S3-compatibility behavior, not environment identity |
| `skip_region_validation` | `true` | S3-compatibility behavior, not environment identity |
| `skip_requesting_account_id` | `true` | S3-compatibility behavior, not environment identity |

Two observations from the checked-in file:

- The comment above the block already describes the desired operating
  model: keep concrete backend details outside source and supply them at
  `tofu init` time.
- The HCL does not actually do that yet. The backend still contains
  concrete storage-location values, and `ENVIRONMENT` is a literal
  string, not a backend-time variable mechanism.

## 2. Terraform/OpenTofu Backend Limitations

### Terraform

Terraform’s `terraform` block reference is explicit: only constant
values are allowed in the `terraform` block, and arguments there cannot
refer to named objects such as resources or input variables. That rule
applies to nested backend configuration as well.

Operational consequence: in Terraform, a backend block cannot be
parameterized with normal `var.*`, `local.*`, resource attributes, or
functions. Backend configuration must be known during `terraform init`,
before ordinary planning and evaluation begin.

### OpenTofu

OpenTofu’s backend documentation currently differs from Terraform’s.
The current docs say:

- only one backend block may be declared
- backend config cannot refer to state-derived values
- variables and locals may be used, but only if all values can be
  resolved during `tofu init`
- provider-defined functions are not allowed in backend configuration

This is narrower than normal Terraform-language evaluation. Even under
OpenTofu’s more permissive model, backend configuration still has an
init-time constraint: it must be fully determined before state-backed
evaluation is possible.

### How the community handles this

The recurring community pattern is partial backend configuration:

- declare the backend type in source
- omit some or all concrete backend arguments from the checked-in HCL
- supply the remaining values via `terraform init -backend-config=...`
  or `tofu init -backend-config=...`

This is visible in:

- HashiCorp Discuss threads where operators keep one shared codebase and
  swap per-environment `*.tfbackend` files at init time
- Stack Overflow answers describing partial backend configuration as the
  practical answer when backend values cannot live as normal module
  inputs

The common driver is the same one present here: backend identity has to
be selected before normal variable-driven graph evaluation.

## 3. The `.tfbackend` File Pattern

Terraform and OpenTofu both document partial backend configuration.

Documented mechanics:

- the checked-in root module declares the backend type
- some backend arguments may be omitted from source
- the omitted arguments are supplied during initialization with one or
  more `-backend-config` inputs
- command-line values are merged with values present in the HCL backend
  block
- the merged backend configuration is written into `.terraform/`

File shape:

- the backend config file contains only the backend arguments as
  top-level attributes
- it does not wrap them in `terraform {}` or `backend "s3" {}`

Naming:

- both Terraform and OpenTofu recommend the
  `*.backendname.tfbackend` convention, for example
  `config.s3.tfbackend`
- neither tool requires that exact filename pattern; it is a documented
  convention rather than a parser requirement

Minimum checked-in requirement:

- Terraform requires at least an empty backend block in source so the
  CLI knows which backend type the external config applies to
- OpenTofu documents the same minimum requirement

This is why the backend problem is typically split into two layers:

- HCL source declares backend type and any truly static settings
- `.tfbackend` files carry the concrete per-environment location data

## 4. What Stays in `main.tf`

Under the documented partial-backend model, the following attributes are
environment-independent in the current file and naturally belong to the
checked-in backend HCL:

- `backend "s3"` itself, because the backend type must still be declared
  in source
- `force_path_style = true`, because it controls S3 URL style for the
  object-storage API rather than selecting an environment
- `skip_credentials_validation = true`, because it changes validation
  behavior for S3-compatible backends without STS
- `skip_metadata_api_check = true`, because it changes how the backend
  probes AWS metadata APIs
- `skip_region_validation = true`, because it disables AWS-region-name
  validation for non-AWS-compatible region strings such as `fsn1`
- `skip_requesting_account_id = true`, because it avoids AWS account-ID
  lookups on S3-compatible backends without IAM/STS support

These values describe how to talk to a Hetzner-style S3-compatible
backend at all. They do not identify staging versus production on their
own.

A stricter interpretation of the official docs is also possible:

- only the backend type must remain in source
- even static non-secret flags may be supplied externally if the team
  chooses

But from the current problem framing, the key distinction is that these
five flags describe backend behavior, not backend environment identity.

## 5. What Moves to `.tfbackend`

The following current attributes are the environment-coupled part of
the backend configuration and are the values that map most directly to a
per-environment `.tfbackend` file:

- `bucket`
- `key`
- `region`
- `endpoint`

Why these are the environment-coupled values:

- `bucket` selects the backing container where a given environment’s
  state is stored
- `key` selects the exact object path for the state file; this is the
  most obviously environment-specific field because different
  environments need distinct state paths
- `region` identifies the target storage region expected by the backend
- `endpoint` points to the concrete S3-compatible API hostname for the
  object store

In this repository, `key` is the clearest example of the problem.
Staging and production cannot safely share the same state object path,
and the current checked-in string does not solve that because
`ENVIRONMENT` is not dynamically substituted by Terraform during backend
initialization.

`bucket`, `region`, and `endpoint` are also currently baked into source.
Whether they differ between staging and production depends on the final
storage topology, but they are still concrete backend-location values,
not portable backend behavior flags.

## Closing Problem Statement

The backend block currently mixes two different concerns:

- backend behavior needed to make the S3 backend work against Hetzner
  Object Storage
- concrete location values that bind the root module to one specific
  remote state layout

Terraform’s configuration model, and the standard partial-backend
pattern documented by both Terraform and OpenTofu, separates those
concerns by keeping backend type and static behavior in source while
supplying concrete backend-location values during initialization.
