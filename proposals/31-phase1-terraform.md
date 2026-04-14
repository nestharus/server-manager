# Proposal: Phase 1 Foundation — Terraform Infrastructure Files

Date: 2026-04-14

## Goal

Define the Phase 1 Terraform/OpenTofu root-module layout for bootstrapping
the Hetzner-hosted `k3s` cluster through `kube-hetzner`.

This proposal is design only. It does not include implementation code.

The file set is intentionally narrow and matches the requested replay
shape:

- `infra/main.tf`
- `infra/variables.tf`
- `infra/cluster.tf`
- `infra/environments/staging/terraform.tfvars`
- `infra/environments/production/terraform.tfvars`

The design keeps the root surface small and environment-driven. The
root module should translate simple sizing inputs into the richer
`kube-hetzner` nodepool objects rather than exposing the entire module
surface directly.

## Design Summary

The root should be a thin bootstrap wrapper around `kube-hetzner`:

- `main.tf` owns OpenTofu versioning, provider pinning, remote-state
  backend shape, and the configured `hcloud` provider.
- `variables.tf` owns the small, stable input surface for Humility’s
  environments.
- `cluster.tf` owns the translation layer from simple root variables to
  `kube-hetzner` inputs such as control-plane and worker nodepools,
  private networking, and load-balancer settings.
- Environment differences live in `terraform.tfvars`, not in duplicated
  module calls.

This is not the most idiomatic long-term Terraform layout. A later
cleanup could split `versions.tf`, `providers.tf`, and `backend.tf`.
For this task, the proposal follows the requested three-root-file
structure exactly.

## File-by-File Design

### `infra/main.tf`

### Purpose

`main.tf` is the operator entrypoint for the root module. It should
contain the top-level `terraform {}` block and the configured
`provider "hcloud"` block.

### Block Layout

`main.tf` should contain these blocks in this order:

1. `terraform {}` with `required_version = ">= 1.6.0"`
2. `required_providers` containing `hcloud`
3. `backend "s3"` for Hetzner Object Storage remote state
4. `provider "hcloud"` configured from `var.hcloud_token`

### Key Decisions

- Keep the `hcloud` source pinned to `hetznercloud/hcloud` with version
  `~> 1.49` because that is the locked replay requirement for this task.
- Add a short inline note that current upstream `kube-hetzner`
  documentation expects a newer `hcloud` provider floor. The proposal
  does not change that locked decision, but it should not hide the
  mismatch either.
- Use `backend "s3"` because Hetzner Object Storage is S3-compatible.
- Keep the backend configuration partial and environment-agnostic in
  source. The backend block should describe:
  - bucket and key placeholders
  - region `fsn1`
  - Hetzner endpoint placeholder for `fsn1.your-objectstorage.com`
  - path-style and non-AWS validation-skip settings
- Do not put backend credentials in source. The backend cannot consume
  ordinary input variables, and credentials should be supplied via
  operator environment or `-backend-config`.
- Keep the provider block minimal: only the token input belongs here.

### Content Design

The `terraform {}` block should express four things:

- the OpenTofu/Terraform CLI floor
- the required `hcloud` provider source and pin
- the existence of an S3-compatible backend
- comments that the concrete backend values are Hetzner Object Storage
  values and are expected to be overridden per environment during
  `init`

The backend should not attempt to interpolate `var.environment` into the
state key. Backend settings are evaluated before normal variable
loading. The design should therefore keep environment namespacing as an
operational convention, for example:

- `humility/staging/terraform.tfstate`
- `humility/production/terraform.tfstate`

### `infra/variables.tf`

### Purpose

`variables.tf` should declare the small root input surface that the
environment files populate and `cluster.tf` consumes.

### Required Variables

The file should declare at least these variables:

| Variable | Type | Default | Purpose |
|---|---|---|---|
| `hcloud_token` | `string` | none | Hetzner API token; marked `sensitive = true` |
| `ssh_key_ids` | `list(string)` | none | Hetzner SSH key identifiers injected into nodes |
| `environment` | `string` | none | Deployment environment name |
| `cluster_name` | `string` | none | Human cluster identifier |
| `location` | `string` | `"fsn1"` | Hetzner location for nodes and load balancer |
| `network_zone` | `string` | `"eu-central"` | Hetzner private-network region corresponding to `fsn1` |
| `control_plane_count` | `number` | none | Number of control-plane nodes |
| `worker_count` | `number` | none | Number of worker nodes |
| `control_plane_server_type` | `string` | `"cpx21"` | Control-plane node size |
| `worker_server_type` | `string` | `"cpx21"` | Worker node size |
| `use_control_plane_lb` | `bool` | `false` | Whether to front the Kubernetes API with the dedicated LB |
| `control_plane_lb_enable_public_interface` | `bool` | `true` | Whether the API LB has a public interface |
| `ingress_controller` | `string` | `"traefik"` | In-cluster ingress controller selected through `kube-hetzner` |
| `load_balancer_type` | `string` | `"lb11"` | Hetzner LB tier for ingress |
| `load_balancer_location` | `string` | `"fsn1"` | Hetzner LB location |
| `create_kubeconfig` | `bool` | `false` | Disable local kubeconfig generation for unattended runs |
| `automatically_upgrade_os` | `bool` | `false` | Environment-specific OS auto-upgrade toggle |
| `placement_group_disable` | `bool` | `false` | Whether to disable placement groups |

### Key Decisions

- Keep `ssh_key_ids` in the root interface because that is the task’s
  requested contract, even though the upstream module documentation also
  discusses SSH key material in a different shape.
- Use `environment` as a first-class variable even though both tfvars
  files set `cluster_name = "humility"`. `cluster.tf` should use
  `environment` to derive unique deployment identity and labels.
- Keep the variable surface intentionally smaller than the full
  `kube-hetzner` input list. Phase 1 does not need direct exposure of
  CIDR tuning, NAT-router controls, existing-network reuse, or etcd S3
  backup configuration.
- Put sensible defaults only on stable bootstrap knobs. Counts and
  environment identity should remain explicit in tfvars.

### Validation Expectations

The proposal does not require custom validation expressions, but the
implementation should treat these as contract assumptions:

- `control_plane_count` is either `1` for non-HA staging or `3` for HA
  production
- `worker_count` is at least `1`
- `location = "fsn1"` and `network_zone = "eu-central"` stay aligned

### `infra/cluster.tf`

### Purpose

`cluster.tf` should instantiate the `kube-hetzner` module and translate
the flat root variables into the richer module input objects.

### Module Shape

The file should contain:

1. small `locals` for translated values
2. one `module "cluster"` block

The module source should use the registry form:

- `source = "kube-hetzner/kube-hetzner/hcloud"`

The module call should also pin an explicit module version. Because the
research found a real mismatch between the locked `hcloud ~> 1.49`
constraint and the current upstream module floor, the version should be
described as:

- a deliberately pinned release compatible with the replayed provider
  line
- not the floating latest release

The exact release number belongs in implementation after compatibility
verification. The proposal requirement is the design rule: explicit pin,
not implicit latest.

### Local Translation Layer

`cluster.tf` should define locals that keep the root interface simple:

- `local.cluster_id`
  derived from `cluster_name` and `environment`, for example
  `humility-staging` and `humility-production`
- `local.control_plane_nodepools`
  a single-element list that builds the module’s required control-plane
  nodepool object
- `local.agent_nodepools`
  a single-element list that builds the worker nodepool object

Each nodepool object should include the fields the upstream module
expects:

- `name`
- `server_type`
- `location`
- `labels`
- `taints`
- `count`

Labels should carry at least environment and role identity. Taints can
remain empty for Phase 1.

### Module Inputs

The module block should be designed to pass:

- provider wiring through `providers = { hcloud = hcloud }`
- `hcloud_token = var.hcloud_token`
- the derived cluster identifier
- `ssh_key_ids = var.ssh_key_ids`
- `control_plane_nodepools = local.control_plane_nodepools`
- `agent_nodepools = local.agent_nodepools`
- `network_region = var.network_zone`
- `use_control_plane_lb = var.use_control_plane_lb`
- `control_plane_lb_enable_public_interface = var.control_plane_lb_enable_public_interface`
- `ingress_controller = var.ingress_controller`
- `load_balancer_type = var.load_balancer_type`
- `load_balancer_location = var.load_balancer_location`
- `create_kubeconfig = var.create_kubeconfig`
- `automatically_upgrade_os = var.automatically_upgrade_os`
- `placement_group_disable = var.placement_group_disable`

### Architecture Notes

- HA is driven by `control_plane_count`, not by a separate HA flag.
  Staging stays non-HA at `1`. Production becomes embedded-etcd HA at
  `3`.
- The root should use one control-plane pool and one worker pool for
  Phase 1. That keeps the bootstrap easy to reason about and avoids
  premature heterogeneous pool design.
- Private networking should remain module-managed. This proposal does
  not create a separate `infra/modules/networking` dependency chain for
  the cluster bootstrap path.
- The load-balancer seam should stay explicit:
  - `use_control_plane_lb` controls Kubernetes API access
  - `ingress_controller` and `load_balancer_*` control north-south HTTP
    ingress

### `infra/environments/staging/terraform.tfvars`

### Purpose

The staging file should define the smallest non-HA footprint that still
looks like the production topology shape.

### Proposed Values

The file should set:

- `environment = "staging"`
- `cluster_name = "humility"`
- `location = "fsn1"`
- `network_zone = "eu-central"`
- `control_plane_count = 1`
- `worker_count = 1`
- `control_plane_server_type = "cpx21"`
- `worker_server_type = "cpx21"`
- `use_control_plane_lb = false`
- `control_plane_lb_enable_public_interface = true`
- `ingress_controller = "traefik"`
- `load_balancer_type = "lb11"`
- `load_balancer_location = "fsn1"`
- `create_kubeconfig = false`
- `automatically_upgrade_os = false`
- `placement_group_disable = false`

### Why This Shape

- One control plane keeps staging intentionally non-HA.
- One worker preserves the same control-plane-versus-worker separation
  as production instead of collapsing staging into a single-node
  exception.
- `automatically_upgrade_os = false` aligns with the upstream guidance
  for clusters with fewer than three control planes.
- No dedicated API load balancer keeps staging cheaper and simpler.

### `infra/environments/production/terraform.tfvars`

### Purpose

The production file should express the minimum HA shape for the Phase 1
foundation.

### Proposed Values

The file should set:

- `environment = "production"`
- `cluster_name = "humility"`
- `location = "fsn1"`
- `network_zone = "eu-central"`
- `control_plane_count = 3`
- `worker_count = 3`
- `control_plane_server_type = "cpx31"`
- `worker_server_type = "cpx31"`
- `use_control_plane_lb = true`
- `control_plane_lb_enable_public_interface = true`
- `ingress_controller = "traefik"`
- `load_balancer_type = "lb11"`
- `load_balancer_location = "fsn1"`
- `create_kubeconfig = false`
- `automatically_upgrade_os = true`
- `placement_group_disable = false`

### Why This Shape

- Three control planes is the minimum embedded-etcd HA shape supported
  by the module guidance.
- Three workers is still modest, but large enough to avoid making the
  foundation depend on the control plane for all scheduling capacity.
- `cpx31` is a deliberate step up from staging without overcommitting to
  later application workload sizing.
- Enabling the dedicated API load balancer creates a stable Kubernetes
  API entrypoint for the HA control plane.

## Architecture Notes

### Thin Root, Opinionated Translation

The root should stay thin. It should not expose every upstream
`kube-hetzner` toggle directly. The Phase 1 bootstrap only needs a
small set of identity, sizing, networking, and load-balancer controls.

### Environment Values Drive Topology

The two `terraform.tfvars` files are the primary environment seam:

- staging chooses non-HA, smaller node sizes, and no API LB
- production chooses HA, larger node sizes, and the API LB

That keeps the `.tf` files stable while the environment files express
capacity and availability policy.

### Cluster Identity Should Be Unique Per Environment

Both environment files set `cluster_name = "humility"` to preserve the
requested external input contract. The module instantiation should still
derive unique internal names from `cluster_name` plus `environment` so
that staging and production do not collide when they live in the same
Hetzner account.

### Remote State Is Separate From Cluster Storage

The Hetzner Object Storage backend in `main.tf` is only for Terraform
state. This proposal intentionally keeps that separate from any later
cluster storage concerns such as etcd S3 backups or application object
storage wiring.

## Tradeoffs

### Three Root Files vs Conventional Split

Combining versions, providers, and backend config into `main.tf` is not
the cleanest long-term Terraform layout. It is the right choice here
because the task explicitly wants a five-file replay centered on
`main.tf`, `variables.tf`, and `cluster.tf`.

### Locked Provider Pin vs Upstream Compatibility

The proposal keeps `hcloud ~> 1.49` because that is the locked task
input. The tradeoff is that the current upstream `kube-hetzner`
documentation expects a newer provider line. The design should therefore
pin the module version explicitly and document why it is not floating to
latest.

### Simple Variable Surface vs Full Module Exposure

A flat variable surface is easier to operate and easier to test. The
tradeoff is reduced flexibility. This proposal intentionally defers
multi-pool workers, custom taints, CIDR customization, and advanced
network modes until they are actually needed.

### Public API Surface in Production

Setting `control_plane_lb_enable_public_interface = true` keeps the API
reachable without introducing a more complex private-access story in
Phase 1. The tradeoff is a broader exposed surface. Hardening that path
belongs in a later access-focused proposal, not in these bootstrap
files.

## Anti-Scope

This file set does not cover:

- `Flux CD`, `Kong`, `Buildkite`, or secrets configuration
- `hcloud-microos-snapshots.pkr.hcl` or other Packer assets
- object-storage bucket provisioning or backend credential management
- per-environment `backend.hcl` files
- Terraform outputs
- separate root modules for networking or storage
- custom CIDR planning, NAT-router topology, or existing-network reuse
- etcd S3 backup configuration
- multi-region or multi-cluster orchestration
- any application, database, or GitOps manifests
