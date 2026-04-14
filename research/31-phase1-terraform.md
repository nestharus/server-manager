# Research: Phase 1 Foundation — Terraform Infrastructure Files

Date: 2026-04-14

## Scope

This note documents the Terraform/OpenTofu root-module structure needed
to bootstrap a Hetzner Cloud k3s cluster with the `kube-hetzner`
module.

It is limited to:

- root-module file layout for Phase 1 infrastructure
- `kube-hetzner` module inputs and instantiation shape
- Hetzner Cloud provider requirements relevant to bootstrap
- staging and production variable-file shape
- Hetzner Object Storage as an S3-compatible remote state backend

It does not design:

- Flux CD
- Kong
- application secrets
- non-Hetzner providers
- broader platform changes

## Executive Findings

- The upstream `kube-hetzner` quick start is intentionally minimal: it
  creates a project directory with a single Terraform file named
  `kube.tf` plus a Packer file named
  `hcloud-microos-snapshots.pkr.hcl`. That is the canonical bootstrap
  entrypoint from the module’s own documentation.
- For a maintainable root module in this repository, the Terraform/OpenTofu
  sources should be split by concern into conventional files
  such as `versions.tf`, `providers.tf`, `backend.tf`, `variables.tf`,
  `main.tf`, and optional `outputs.tf`. Terraform/OpenTofu treats all
  `.tf` files in one directory as a single module, so this split is a
  maintenance convention rather than a semantic requirement.
- The current upstream `kube-hetzner` documentation does not match the
  locked provider decision `hcloud ~> 1.49`. The generated module docs
  currently require `hcloud >= 1.59.0`, and the example root module
  bundled with the repo still declares `hcloud >= 1.51.0`. That means a
  root module pinned to `~> 1.49` is below the current upstream floor.
- The current OpenTofu `s3` backend supports native S3 locking via
  `use_lockfile = true`, but that capability arrived in OpenTofu 1.10.
  If this project truly allows any CLI `>= 1.6.0`, Hetzner Object
  Storage can serve as remote state storage across that range, but
  S3-native state locking is only available once the operator floor is
  effectively `>= 1.10.0`.

## Primary Sources

- `kube-hetzner` README:
  https://github.com/kube-hetzner/terraform-hcloud-kube-hetzner
- `kube-hetzner` example root file:
  https://raw.githubusercontent.com/kube-hetzner/terraform-hcloud-kube-hetzner/master/kube.tf.example
- `kube-hetzner` generated Terraform input docs:
  https://raw.githubusercontent.com/kube-hetzner/terraform-hcloud-kube-hetzner/master/docs/terraform.md
- Hetzner Cloud provider README:
  https://github.com/hetznercloud/terraform-provider-hcloud
- OpenTofu backend configuration docs:
  https://opentofu.org/docs/language/settings/backends/configuration/
- OpenTofu S3 backend docs:
  https://opentofu.org/docs/language/settings/backends/s3/
- OpenTofu state locking docs:
  https://opentofu.org/docs/language/state/locking/
- OpenTofu 1.10 release notes:
  https://opentofu.org/docs/v1.10/intro/whats-new/
- OpenTofu lock file docs:
  https://opentofu.org/docs/language/files/dependency-lock/
- Terraform files/module structure docs:
  https://developer.hashicorp.com/terraform/language/files
- Terraform style guide:
  https://developer.hashicorp.com/terraform/language/syntax/style
- Hetzner Object Storage overview:
  https://docs.hetzner.com/storage/object-storage/overview/
- Hetzner Object Storage bucket creation via MinIO provider:
  https://docs.hetzner.com/storage/object-storage/getting-started/creating-a-bucket-minio-terraform/

## 1. Canonical Root-Module File Structure

### Upstream bootstrap shape

The `kube-hetzner` quick start uses a very small working directory:

- `kube.tf`
- `hcloud-microos-snapshots.pkr.hcl`

The upstream `create.sh` helper downloads exactly those two files,
builds the MicroOS snapshot with Packer, and then expects the operator
to run `terraform init` and `terraform apply` from that directory.

Research implication: the absolute minimum working bootstrap is one root
Terraform file plus the Packer template. Nothing in upstream requires a
multi-file split.

### Maintainable root-module shape for this repository

Terraform’s file-structure docs state that a module is the set of `.tf`
files in one directory, and splitting blocks across files is purely an
organizational choice. The Terraform style guide also calls out a
dedicated backend file as the idiomatic layout.

For Phase 1, the smallest maintainable root module should be:

- `versions.tf`
  `terraform` block, `required_version`, `required_providers`, and the
  `backend "s3"` block
- `providers.tf`
  configured `hcloud` provider instance
- `variables.tf`
  root inputs for secrets, environment identity, location, and sizing
- `main.tf`
  `module "kube-hetzner"` call plus any small root-level locals needed
  to translate simple variables into `control_plane_nodepools` and
  `agent_nodepools`
- `outputs.tf`
  optional, only if the root wants to re-export selected module outputs
  such as kubeconfig path, network id, or load balancer IPs
- `.terraform.lock.hcl`
  generated by `tofu init`; OpenTofu recommends reviewing and committing
  it
- `hcloud-microos-snapshots.pkr.hcl`
  required by the upstream bootstrap path before the first apply

Environment-specific values should live outside the root files:

- `environments/staging/terraform.tfvars`
- `environments/production/terraform.tfvars`
- optionally `environments/staging/backend.hcl`
- optionally `environments/production/backend.hcl`

Why separate `backend.hcl` files matter here: OpenTofu only allows
constant values in the `terraform` block. Backend configuration is
therefore not a good place for ordinary input variables when the project
floor is only `>= 1.6.0`. Static backend blocks plus per-environment
`-backend-config` files are the stable pattern.

## 2. Provider Configuration and Version Constraints

### What the root module must configure

The upstream example root module wires the child module explicitly to an
`hcloud` provider instance:

- `providers = { hcloud = hcloud }`

For this Phase 1 root, the required provider shape is:

- OpenTofu CLI version constraint in the root `terraform` block
- `required_providers.hcloud` with source `hetznercloud/hcloud`
- `provider "hcloud"` configured with the Hetzner API token

The root module does not need to manually configure the child module’s
internal helper providers such as `local`, `github`, `ssh`, `random`,
or `cloudinit`; those are declared by the module itself.

### Version constraints supported by current upstream docs

Current upstream evidence is inconsistent but clearly newer than the
locked `~> 1.49` decision:

- `docs/terraform.md` currently lists `hcloud >= 1.59.0`
- `kube.tf.example` still contains a sample root `required_providers`
  block with `hcloud >= 1.51.0`
- the module’s own generated docs currently list Terraform
  `>= 1.10.1`

Research implication: for current upstream `kube-hetzner`, an
appropriate root provider constraint is in the `1.51+` to `1.59+`
family, not `~> 1.49`.

### Locked-decision mismatch

This is a factual compatibility issue, not a proposal:

- locked platform decision: `hcloud ~> 1.49`
- current upstream module docs: `hcloud >= 1.59.0`
- bundled example root file: `hcloud >= 1.51.0`

Therefore, a Phase 1 root module cannot honestly claim both "current
upstream `kube-hetzner`" and "`hcloud ~> 1.49`" at the same time. One
of these must anchor the eventual implementation:

- either a deliberately older `kube-hetzner` release compatible with the
  1.49 provider line
- or a newer `hcloud` provider constraint compatible with current
  upstream

That is the most important research finding in this note.

## 3. Root Variables the Bootstrap Module Should Declare

The root module should not expose every `kube-hetzner` input directly.
The upstream module expects rich `control_plane_nodepools` and
`agent_nodepools` objects, but the project scope only needs a simpler
bootstrap surface.

The root should declare at least these variables:

- `hcloud_token`
  sensitive string; maps to module input `hcloud_token`
- `ssh_public_key`
  string; maps to required module input `ssh_public_key`
- `ssh_private_key`
  sensitive string; maps to required module input `ssh_private_key`
- `environment`
  string such as `staging` or `production`; useful for naming and state
  pathing
- `cluster_name`
  string; maps to module input `cluster_name`
- `location`
  string such as `fsn1`; used when building both nodepool lists and load
  balancer placement
- `network_region`
  string; defaults to `eu-central` for `fsn1`
- `control_plane_server_type`
  string such as `cx23`
- `control_plane_count`
  number; the root translates this into one control-plane nodepool
- `worker_server_type`
  string such as `cx23` or `cx33`
- `worker_count`
  number; the root translates this into one worker nodepool
- `use_control_plane_lb`
  bool; separate seam for Kubernetes API high availability
- `control_plane_lb_enable_public_interface`
  bool; public versus private API endpoint exposure
- `ingress_controller`
  string; default upstream value is `traefik`
- `load_balancer_type`
  string; default upstream value is `lb11`
- `load_balancer_location`
  string; should follow the chosen Hetzner location
- `create_kubeconfig`
  bool; upstream default is `true`, but docs explicitly say it should be
  disabled for automatic runs
- `automatically_upgrade_os`
  bool; upstream default is `true`, but upstream docs say it must be
  disabled for non-HA clusters with fewer than 3 control planes
- `placement_group_disable`
  bool; upstream default is `false`

The root may also declare these only if it intends to override upstream
defaults:

- `existing_network_id`
- `network_ipv4_cidr`
- `cluster_ipv4_cidr`
- `service_ipv4_cidr`
- `etcd_s3_backup`

Important shape detail from the upstream module docs: each nodepool
object requires `name`, `server_type`, `location`, `labels`, `taints`,
and `count`. Even when labels and taints are unused, they still need to
be represented as empty lists when the root builds nodepool objects.

## 4. How `kube-hetzner` Module Instantiation Works

### Minimal module call

At minimum, the module call needs:

- `source = "kube-hetzner/kube-hetzner/hcloud"`
- explicit version pin to a chosen module release
- provider wiring `hcloud = hcloud`
- `hcloud_token`
- `ssh_public_key`
- `ssh_private_key`
- `control_plane_nodepools`
- `agent_nodepools`

The upstream docs still use the module source above as the canonical
registry source and note that version pinning is optional but supported.

### Control plane HA

The module’s own docs are explicit:

- HA starts at 3 control planes
- the count must be odd, never even
- single-node mode is supported for development
- for fewer than 3 control planes, automatic OS upgrades should be
  turned off

The control-plane topology is not a separate HA flag. It is encoded in
the total number of control-plane nodes across
`control_plane_nodepools`.

### Worker nodes

Worker capacity is encoded in `agent_nodepools`.

Key module behavior:

- the list may contain multiple worker pools with different sizes
- scale is usually expressed through each pool’s `count`
- a `nodes` map can replace `count` for fine-grained per-node control
- upstream says at least one control-plane nodepool and one agent
  nodepool are required before initial cluster creation
- a single-node cluster is the exception: one control-plane nodepool can
  have `count = 1` and one agent nodepool can have `count = 0`

For the Phase 1 staging and production shapes described in this prompt,
the normal path is still one worker nodepool with `count >= 1`.

### Private networking

The module creates a Hetzner private network by default. Relevant
inputs:

- `network_region`
- `network_ipv4_cidr`
- `cluster_ipv4_cidr`
- `service_ipv4_cidr`

If the root creates the network outside the module, it can pass
`existing_network_id`, but the module docs warn that the network CIDR
settings must then be kept consistent manually.

Private-only exposure is controlled separately from private networking:

- nodepools can disable public IPv4 and/or IPv6
- `control_plane_lb_enable_public_interface = false` makes the API load
  balancer private-only
- `load_balancer_disable_public_network = true` removes the public
  network from the ingress load balancer
- `nat_router` is the extra seam for a fully private cluster with
  outbound egress via a bastion/NAT node

### Load balancer and ingress seam

The upstream docs draw a clear separation between two load-balancing
concerns:

- `use_control_plane_lb`
  dedicated Kubernetes API load balancer on port 6443
- `ingress_controller` plus `load_balancer_*`
  ingress path for HTTP/HTTPS traffic

This matters for Phase 1 because "API HA" and "ingress exposure" are
different decisions:

- `use_control_plane_lb = true` stabilizes the kube-apiserver endpoint
  for multi-control-plane clusters
- `ingress_controller` chooses the in-cluster ingress implementation;
  upstream default is `traefik`
- `load_balancer_type` and `load_balancer_location` size and place the
  ingress load balancer
- `load_balancer_disable_public_network` is the ingress public/private
  toggle

### Etcd backup seam

The module supports S3-backed etcd snapshots through
`etcd_s3_backup`. The upstream example shows the expected map keys:

- `etcd-s3-endpoint`
- `etcd-s3-access-key`
- `etcd-s3-secret-key`
- `etcd-s3-bucket`
- `etcd-s3-region`

That is the direct seam between the cluster bootstrap and Hetzner
Object Storage, but it is separate from OpenTofu remote state.

## 5. What Staging vs Production `terraform.tfvars` Should Look Like

These are research baselines for the root-module variables described
above, not final implementation files.

### Staging baseline

Use staging as a minimal, non-HA cluster:

```hcl
environment                     = "staging"
cluster_name                    = "humility-staging"
location                        = "fsn1"
network_region                  = "eu-central"
control_plane_server_type       = "cx23"
control_plane_count             = 1
worker_server_type              = "cx23"
worker_count                    = 1
use_control_plane_lb            = false
ingress_controller              = "traefik"
load_balancer_type              = "lb11"
load_balancer_location          = "fsn1"
create_kubeconfig               = false
automatically_upgrade_os        = false
placement_group_disable         = false
control_plane_lb_enable_public_interface = true
```

Why this shape matches upstream guidance:

- one control plane is explicitly non-HA and acceptable for development
- upstream says automatic OS upgrades should be disabled when control
  planes are fewer than 3
- a separate worker pool remains present, which keeps staging aligned
  with the "single control plane, minimal workers" requirement rather
  than shifting to upstream’s special single-node exception

### Production baseline

Use production as a same-location HA cluster:

```hcl
environment                     = "production"
cluster_name                    = "humility-production"
location                        = "fsn1"
network_region                  = "eu-central"
control_plane_server_type       = "cx23"
control_plane_count             = 3
worker_server_type              = "cx33"
worker_count                    = 2
use_control_plane_lb            = true
control_plane_lb_enable_public_interface = true
ingress_controller              = "traefik"
load_balancer_type              = "lb11"
load_balancer_location          = "fsn1"
create_kubeconfig               = false
automatically_upgrade_os        = true
placement_group_disable         = false
```

Why this shape matches upstream guidance:

- three control planes is the module’s own HA recommendation
- API access is fronted by the dedicated control-plane load balancer
- workers are separated from control planes
- automatic OS upgrades remain enabled because the control plane is HA

Research constraint: the exact server types above are only a bootstrap
baseline. The upstream example repeatedly uses `cx23` as the minimum
supported x86 instance and also shows larger agent pools such as `cx33`.
The docs do not define a Humility-specific workload sizing model.

## 6. Remote State on Hetzner Object Storage

### What the backend must do

OpenTofu’s S3 backend requires:

- `bucket`
- `key`
- `region`

The backend docs also say this assumes the bucket already exists.

Because Hetzner Object Storage is S3-compatible rather than AWS S3, the
backend also needs S3-compatible endpoint handling. Current OpenTofu
docs expose that through endpoint settings plus path-style and
validation-skip options for non-AWS object stores.

### Hetzner-specific endpoint facts

Hetzner’s Object Storage overview documents these endpoints:

- Falkenstein: `fsn1.your-objectstorage.com`
- Nuremberg: `nbg1.your-objectstorage.com`
- Helsinki: `hel1.your-objectstorage.com`

For this project’s locked location, the S3 endpoint is:

- `https://fsn1.your-objectstorage.com`

Hetzner’s own Terraform example for bucket management uses:

- endpoint `fsn1.your-objectstorage.com`
- region `fsn1`
- S3 credentials `access_key` and `secret_key`

### Recommended backend shape

For a Hetzner-backed remote state config, the research-backed shape is:

- backend type `s3`
- bucket name already created out-of-band
- key path namespaced by environment, for example
  `humility/staging/terraform.tfstate` and
  `humility/production/terraform.tfstate`
- region `fsn1`
- S3 endpoint `https://fsn1.your-objectstorage.com`
- path-style enabled
- AWS-specific validation/account lookups disabled for S3-compatible use

Illustrative backend fragment:

```hcl
terraform {
  backend "s3" {}
}
```

Illustrative `backend.hcl` values:

```hcl
bucket                      = "humility-tofu-state"
key                         = "staging/terraform.tfstate"
region                      = "fsn1"
endpoints                   = { s3 = "https://fsn1.your-objectstorage.com" }
use_path_style              = true
skip_credentials_validation = true
skip_region_validation      = true
skip_metadata_api_check     = true
skip_requesting_account_id  = true
```

### Credentials handling

OpenTofu’s backend docs warn against hardcoding backend credentials in
source because backend settings can be persisted into `.terraform/` and
plan files. The docs recommend using partial configuration and
environment variables for sensitive values.

Research implication: Hetzner Object Storage credentials should be
provided via environment variables or `-backend-config`, not committed
into `backend.tf`.

### Locking constraint with OpenTofu version floor

Current OpenTofu docs recommend native S3 locking via:

- `use_lockfile = true`

However, OpenTofu’s 1.10 release notes identify native S3 locking as a
1.10 feature. That creates a second compatibility seam:

- if the project truly supports any OpenTofu version `>= 1.6.0`, remote
  state storage works, but native S3 locking is not guaranteed
- if the operator floor is effectively standardized to `>= 1.10.0`,
  Hetzner Object Storage can provide both remote state storage and
  native S3 lockfiles without DynamoDB

Since Hetzner Object Storage does not provide DynamoDB, this matters for
the actual implementation plan.

## Direct Answers to the Six Research Questions

### 1. Canonical file structure

Direct answer:

- upstream minimum: `kube.tf` plus `hcloud-microos-snapshots.pkr.hcl`
- maintainable root-module minimum:
  `versions.tf`, `providers.tf`, `variables.tf`, `main.tf`,
  optional `outputs.tf`, generated `.terraform.lock.hcl`, plus the
  Packer file
- environment values should live in separate `terraform.tfvars` files,
  and backend overrides should live in separate `backend.hcl` files

### 2. Provider configuration

Direct answer:

- root config needs `required_version`, `required_providers.hcloud`,
  and a configured `provider "hcloud"`
- current upstream `kube-hetzner` documentation expects newer `hcloud`
  versions than `~> 1.49`

### 3. Root variables

Direct answer:

- declare simple root variables for token, SSH material, environment,
  cluster identity, location/network region, control-plane sizing, and
  worker sizing
- translate those into the richer upstream nodepool objects inside the
  root module

### 4. Module instantiation

Direct answer:

- instantiate `source = "kube-hetzner/kube-hetzner/hcloud"`
- pass `hcloud_token`, SSH keys, and nodepool lists
- control-plane HA is encoded by odd control-plane count, not a
  separate switch
- private networking is the module default; public/private exposure is
  controlled by LB and node networking flags
- API LB and ingress LB are separate seams

### 5. Staging vs production tfvars

Direct answer:

- staging should be one control plane, one minimal worker, no API LB,
  automatic OS upgrades disabled
- production should be three control planes, multiple workers, API LB
  enabled, automatic OS upgrades enabled

### 6. Remote state on Hetzner Object Storage

Direct answer:

- use OpenTofu `backend "s3"` against
  `https://fsn1.your-objectstorage.com`
- pre-create the bucket
- keep credentials out of source
- use S3-compatible endpoint and validation-skip settings
- only rely on `use_lockfile = true` if the operator floor is
  effectively OpenTofu 1.10+
