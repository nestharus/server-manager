# Hookpoint Research — Phase 1 Foundation Terraform Infrastructure

Date: 2026-04-14

## Summary

- Git branch is `feat/phase1-foundation`.
- `infra/` already exists, but it contains no tracked Terraform/OpenTofu
  files yet.
- The directory skeleton requested by the proposal already exists:
  `infra/environments/staging`, `infra/environments/production`, and
  `infra/modules/`.
- The Terraform work is currently isolated from the existing application
  code. No references to `infra/`, Terraform/OpenTofu, `hcloud`, or
  `kube-hetzner` were found in `daemon/`, `docs/`, `forms/`, or
  `discord_cli.py`.
- The main hookpoints are planning artifacts, research artifacts, and
  existing environment naming conventions, not reusable infrastructure
  code.

## Existing `infra/` State

### Present directories

- `infra/`
- `infra/environments/`
- `infra/environments/staging/`
- `infra/environments/production/`
- `infra/modules/`
- `infra/modules/cluster/`
- `infra/modules/networking/`
- `infra/modules/storage/`

### Present files

- None. `find infra -type f` returned no tracked files.

## Existing Files That Interact With The New Terraform Files

These are the current files that define, constrain, or directly refer
to the Terraform work:

### Primary task artifacts

- `proposals/31-phase1-terraform.md`
  - Validated file set and root-module shape for:
    `infra/main.tf`, `infra/variables.tf`, `infra/cluster.tf`, and the
    two environment `terraform.tfvars` files.
- `research/31-phase1-terraform.md`
  - Research backing for provider pinning, backend shape,
    `kube-hetzner` module wiring, and environment-file placement.
- `research/31-phase1-terraform-needs.md`
  - Synthesized constraints for the replayed file structure and the
    provider/version mismatch note.

### Phase 1 platform context

- `plans/proposals/phase1-foundation.md`
  - Overarching Phase 1 context: Hetzner, OpenTofu, `kube-hetzner`,
    Flux, Kong, and Hetzner Object Storage.
- `plans/platform-decisions-overlay.md`
  - Locked planning direction relevant to Terraform scope:
    Buildkite/Flux split and provider-native object storage preference.
- `plans/research/opentofu-providers.md`
  - Directly applicable to Terraform implementation:
    `hcloud` plus `kube-hetzner`, the non-`hcloud` object-storage
    provider boundary, and the Packer/bootstrap seam.
- `plans/research/self-hosted-s3.md`
  - Directly applicable to the remote-state/object-storage posture:
    provider-native object storage first, self-hosted S3 deferred.
- `plans/research/buildkite-capabilities.md`
  - Relevant as a boundary file: Buildkite is CI control plane, not the
    deployment reconciler. This confirms the Terraform files should stay
    focused on infrastructure/bootstrap, not CI mutation paths.
- `plans/risk/phase1-scope.md`
  - Confirms the object-storage provider boundary and `kube-hetzner`
    Packer seam as implementation-time realities.
- `plans/risk/phase1-shortcut.md`
  - Repeats the same two hookpoints as constraints:
    documented Packer seam and explicit secondary provider path.

### Workflow files that already reference the exact future paths

- `research/prompts/31-code-agent.md`
- `research/prompts/31-test-agent.md`
- `research/prompts/31-pr-review.md`

These already name the exact future files under `infra/`, so they are
workflow hookpoints for later implementation and validation.

## Files And Areas That Should Not Be Touched

Confirmed unaffected by this Terraform phase:

- `daemon/`
- `discord_cli.py`
- `forms/`
- `docs/`

Additional adjacent areas that should remain untouched for this task:

- `services/`
- `apps/`
- `packages/`
- `tests/`
- `k8s/`

Notes:

- `daemon/`, `docs/`, `forms/`, and `discord_cli.py` currently contain
  no Terraform/OpenTofu or `infra/` references.
- `k8s/` is a neighboring platform directory, not a current Terraform
  hookpoint. Its current role is naming/context alignment only.

## Naming And Convention Patterns To Follow

- Environment names are lowercase and standardized as `staging` and
  `production`.
- The environment split already exists in both:
  `infra/environments/{staging,production}` and
  `k8s/overlays/{staging,production}`.
- Infrastructure concerns are separated at the top level:
  `infra/` for infrastructure bootstrapping and `k8s/` for cluster
  manifests/overlays.
- Phase research/proposal files use the numeric `31-...` naming pattern;
  the Terraform files themselves do not. They should follow standard
  Terraform filenames exactly as defined in the proposal.
- The existing `infra/modules/{cluster,networking,storage}` directories
  are empty and read as future reusable-module slots, not current root
  module locations.

## Recommendations For File Placement

- Place the Phase 1 root-module files directly in `infra/`:
  - `infra/main.tf`
  - `infra/variables.tf`
  - `infra/cluster.tf`
- Place environment-specific values in the already-existing environment
  directories:
  - `infra/environments/staging/terraform.tfvars`
  - `infra/environments/production/terraform.tfvars`
- Do not place the Phase 1 root files inside `infra/modules/`; that
  directory is already shaped like a reusable-module area and is not the
  location described by the validated proposal.
- Keep the environment naming aligned with the existing `k8s/overlays/`
  naming so staging/production stay consistent across infra and cluster
  layout.

## Pre-Existing Code To Preserve

- Preserve `daemon/`, `discord_cli.py`, `forms/`, and `docs/` exactly as
  they are for this Terraform task.
- There is no current code-level conflict between those areas and the
  planned Terraform files.
- The existing infrastructure skeleton under `infra/` should be
  preserved and filled in, not replaced.

## Git State

- Current branch: `feat/phase1-foundation`
- Current worktree state is not clean: it contains untracked planning
  and risk artifacts plus local runtime files such as `.refs/` and
  `discord.db*`.
- No tracked `infra/` files exist yet, so the Terraform implementation
  will be additive within the existing directory skeleton.
