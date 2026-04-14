# Hookpoint Research: Backend Cleanup

Date: 2026-04-14

## Scope

This note maps
[proposals/33-backend-cleanup.md](/home/nes/discord/proposals/33-backend-cleanup.md:1)
onto the current
[infra/](/home/nes/discord/infra)
tree.

It answers:

1. what already exists in `infra/`
2. what files need to change for proposal 33
3. what files are reusable as-is
4. what new files still need to be created
5. whether anything conflicts strongly enough to delete

It does not include implementation code.

## Primary Sources

- Proposal:
  [proposals/33-backend-cleanup.md](/home/nes/discord/proposals/33-backend-cleanup.md:1)
- Current backend root:
  [infra/main.tf](/home/nes/discord/infra/main.tf:1)
- Environment inputs:
  [infra/environments/staging/terraform.tfvars](/home/nes/discord/infra/environments/staging/terraform.tfvars:1),
  [infra/environments/production/terraform.tfvars](/home/nes/discord/infra/environments/production/terraform.tfvars:1)
- Root module wiring:
  [infra/variables.tf](/home/nes/discord/infra/variables.tf:1),
  [infra/cluster.tf](/home/nes/discord/infra/cluster.tf:1)
- Local validation:
  [infra/tests/validate_terraform.sh](/home/nes/discord/infra/tests/validate_terraform.sh:1)
- Provider lockfile:
  [infra/.terraform.lock.hcl](/home/nes/discord/infra/.terraform.lock.hcl:1)

## 1. What already exists

### Repo-tracked files in `infra/`

These are the current repo-owned files under `infra/`:

- [infra/main.tf](/home/nes/discord/infra/main.tf:1)
  is the Terraform/OpenTofu root entrypoint. Today it declares the
  required Terraform version, pins the `hcloud` provider, configures the
  `hcloud` provider block, and defines the remote `backend "s3"` block.
  The backend block currently hardcodes `bucket`, uses a literal
  `humility/ENVIRONMENT/terraform.tfstate` placeholder for `key`, and
  sets a singular `endpoint`.
- [infra/variables.tf](/home/nes/discord/infra/variables.tf:1)
  declares the root module input contract for cluster provisioning:
  environment identity, sizing, location, SSH material, and the Hetzner
  API token.
- [infra/cluster.tf](/home/nes/discord/infra/cluster.tf:1)
  is the root module implementation that shapes local nodepool data and
  instantiates the pinned `kube-hetzner` module.
- [infra/environments/staging/terraform.tfvars](/home/nes/discord/infra/environments/staging/terraform.tfvars:1)
  is the staging environment input file for root-module variables such
  as environment name, cluster name, location, and node counts.
- [infra/environments/production/terraform.tfvars](/home/nes/discord/infra/environments/production/terraform.tfvars:1)
  is the production environment input file for the same root-module
  variables, with larger production sizing.
- [infra/tests/validate_terraform.sh](/home/nes/discord/infra/tests/validate_terraform.sh:1)
  is the repo-local validation script. It checks required files, asserts
  expected patterns in `main.tf`, `variables.tf`, and the two
  `terraform.tfvars` files, performs a hardcoded-secret scan, and runs
  `tofu validate` or `terraform validate` if available.
- [infra/.terraform.lock.hcl](/home/nes/discord/infra/.terraform.lock.hcl:1)
  is the provider lockfile maintained by `tofu init`. It pins provider
  selections and hashes for reproducible initialization.

### Existing non-source material under `infra/`

There is also generated Terraform working state under
`infra/.terraform/`, plus empty or currently-unused directories such as
`infra/modules/cluster/`, `infra/modules/networking/`, and
`infra/modules/storage/`.

Those paths are not repo-tracked hookpoints for proposal 33. The
proposal is about the checked-in backend configuration layout, not about
changing generated provider/module caches or filling empty module
directories.

## 2. What needs to change

### `infra/main.tf` must be narrowed to shared backend settings

[infra/main.tf](/home/nes/discord/infra/main.tf:1) is the primary file
the proposal changes.

Per the proposal, its `backend "s3"` block should stop owning the
environment-specific locator values and keep only the shared backend
type plus stable Hetzner S3-compatibility settings. Concretely, the
current file needs these proposal-scoped adjustments:

- remove `bucket`
- remove the placeholder `key = "humility/ENVIRONMENT/terraform.tfstate"`
- remove the singular `endpoint`
- keep the shared `region` and `skip_*` / `force_path_style` settings
- update the existing backend comment so it points operators at the
  per-environment `.tfbackend` initialization pattern

No other part of `main.tf` is implicated by the proposal. The
`required_version`, `required_providers`, and `provider "hcloud"` blocks
already sit outside the backend concern and should remain as they are.

### `infra/tests/validate_terraform.sh` is a secondary hookpoint

[infra/tests/validate_terraform.sh](/home/nes/discord/infra/tests/validate_terraform.sh:1)
currently encodes the old backend shape:

- `check_main_tf` explicitly expects `(endpoint|endpoints)` inside the
  `backend "s3"` block in `main.tf`
- `check_required_files` does not know about the two new
  `backend.tfbackend` files the proposal introduces

That means the current validator will no longer describe the intended
post-proposal layout once `main.tf` is cleaned up. This script is not
part of the Terraform root module itself, but it is the only existing
repo-local file in `infra/` that materially assumes the old backend
arrangement.

## 3. What is reusable

These files can stay completely untouched because they are not part of
backend locator ownership:

- [infra/variables.tf](/home/nes/discord/infra/variables.tf:1)
  only defines root-module input variables; it does not participate in
  backend configuration.
- [infra/cluster.tf](/home/nes/discord/infra/cluster.tf:1)
  only wires cluster provisioning through the `kube-hetzner` module; it
  is unrelated to backend initialization.
- [infra/environments/staging/terraform.tfvars](/home/nes/discord/infra/environments/staging/terraform.tfvars:1)
  is reusable as-is because proposal 33 does not move or rename root
  module variables for staging.
- [infra/environments/production/terraform.tfvars](/home/nes/discord/infra/environments/production/terraform.tfvars:1)
  is reusable as-is for the same reason on production.
- [infra/.terraform.lock.hcl](/home/nes/discord/infra/.terraform.lock.hcl:1)
  can stay untouched because the proposal does not change providers or
  versions.

The existing environment directory layout is also reusable as-is. The
proposal fits the already-established pattern of
`infra/environments/<env>/` and adds backend config files beside the
existing `terraform.tfvars` files rather than introducing a new layout.

## 4. What needs to be created

The proposal adds two new checked-in backend config files:

1. [infra/environments/staging/backend.tfbackend](/home/nes/discord/infra/environments/staging)
   should be created to hold the staging backend locator values:
   `bucket`, `key`, and `endpoints`.
2. [infra/environments/production/backend.tfbackend](/home/nes/discord/infra/environments/production)
   should be created to hold the production backend locator values:
   `bucket`, `key`, and `endpoints`.

These are the only new files indicated by the proposal. No new module,
provider, environment, or wrapper-script file is part of this hookpoint
set.

## 5. Conflicts or deletions

### No tracked source file needs deletion

I did not find any tracked `infra/` file that should be deleted to make
proposal 33 fit.

This proposal is primarily a reshaping of backend ownership:

- `infra/main.tf` conflicts with the proposal only at the field level,
  because it still hardcodes `bucket`, `key`, and `endpoint`
- `infra/tests/validate_terraform.sh` conflicts only at the validation
  expectation level, because it still assumes backend endpoint data
  lives in `main.tf`

Those are modification hookpoints, not deletion targets.

### No conflict in the environment directories

The staging and production directories already exist and currently only
contain `terraform.tfvars`. There is no pre-existing `backend.tfbackend`
file to replace, and there is no competing per-environment backend
scheme under `infra/environments/`.

### Generated `.terraform/` contents are not proposal conflicts

The generated `infra/.terraform/` tree contains downloaded provider and
module cache data. It is not the source of the current backend mismatch
and does not present a proposal-level deletion target.

## Conclusion

Proposal 33 maps cleanly onto the current `infra/` tree.

The real implementation hookpoints are narrow: `infra/main.tf` is the
only Terraform source file that must change, two new
`backend.tfbackend` files must be added under the existing staging and
production environment directories, and the local
`infra/tests/validate_terraform.sh` script is the one existing
repo-local conflict that still assumes the old backend layout. The rest
of the tracked Terraform source is already reusable as-is.
