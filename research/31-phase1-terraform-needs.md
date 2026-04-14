# Synthesis: Phase 1 Foundation — Terraform Infrastructure Needs

Date: 2026-04-14
Synthesized by: claude-opus (orchestrator)

## Context

This document maps the research findings from
`research/31-phase1-terraform.md` to the Humility project's specific
needs for Phase 1 Foundation Terraform infrastructure.

## Key Research Findings Mapped to Project Needs

### 1. Provider Version Mismatch — CRITICAL

The research found that the locked decision (`hcloud ~> 1.49`) is
below the current upstream `kube-hetzner` floor:

- Module docs require `hcloud >= 1.59.0`
- Example root file requires `hcloud >= 1.51.0`

**Project decision needed**: For the replay implementation, use a
provider version compatible with current upstream `kube-hetzner`. The
locked `~> 1.49` decision predates the module version research. Use
`~> 1.49` as specified in the archived prefix since this is a replay
reproducing the original session's files, but note the mismatch in
comments.

### 2. File Structure Adaptation

The task specifies 3 root files: `main.tf`, `variables.tf`, `cluster.tf`.
The research recommends 5: `versions.tf`, `providers.tf`, `variables.tf`,
`main.tf`, `outputs.tf`.

**Project decision**: Use the task's 3-file structure to match the
archived original session. The `main.tf` combines the version/provider
blocks. `cluster.tf` handles module instantiation (what research calls
`main.tf`).

### 3. Variable Surface

The research reveals that `kube-hetzner` requires richer inputs than
simple count variables:

- SSH keys need `ssh_public_key` (string) and `ssh_private_key`
  (sensitive string), not just `ssh_key_ids`
- Nodepools are objects with `name`, `server_type`, `location`,
  `labels`, `taints`, and `count`

**Project decision**: The task description specifies `ssh_key_ids`
(matching the archived prefix). Use that interface for the root
variables, and translate to module inputs in `cluster.tf`. This
keeps the root variable surface simple while the module call handles
the richer upstream interface.

### 4. Remote State Backend

Hetzner Object Storage is S3-compatible. The research confirms:

- Endpoint: `https://fsn1.your-objectstorage.com`
- Region: `fsn1`
- Needs path-style, skip validation flags
- Credentials via env vars, not in source

**Project decision**: Use `backend "s3"` with placeholder config and
comments. Backend credentials handled externally via `-backend-config`.

### 5. OpenTofu Version Floor

The archived prefix says `required_version = ">= 1.6.0"`. Research
notes that S3 native locking requires 1.10+.

**Project decision**: Keep `>= 1.6.0` as specified in the archived
prefix. State locking is a later operational concern, not a bootstrap
blocker.

### 6. Environment Differentiation

Research baseline:
- Staging: 1 CP, 1 worker, no API LB, OS upgrades disabled
- Production: 3 CP, 2+ workers, API LB, OS upgrades enabled

**Project decision**: Match the task's archived prefixes:
- Staging: `control_plane_count = 1`, minimal workers
- Production: `control_plane_count = 3`, more workers

## Gaps Identified

1. **Packer template**: The research notes `kube-hetzner` requires
   `hcloud-microos-snapshots.pkr.hcl` for MicroOS node images. This
   file is NOT in the task scope (P0474-P0478). It would be needed
   before `tofu apply` but is not a blocker for file creation.

2. **SSH key material**: The archived prefix uses `ssh_key_ids`
   (list of Hetzner SSH key IDs), but upstream `kube-hetzner`
   requires `ssh_public_key` and `ssh_private_key` strings. The
   implementation should include both interfaces.

3. **Backend config files**: Research recommends separate
   `backend.hcl` per environment. Not in task scope but noted for
   future work.

## Summary

The 5 Terraform files can be created with the archived structure and
prefixes. The provider version mismatch should be noted in comments
but not corrected (this is a replay). The variable surface should
match the task description while being structurally compatible with
`kube-hetzner` module requirements.
