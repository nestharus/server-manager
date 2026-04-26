# INIT-101 Phase 5 Hookpoint Research

Inputs verified:
- Current worktree: `/home/nes/projects/server-manager/worktrees/init-101-k3s-control-cluster`
- Branch: `feat/init-101-k3s-control-cluster`
- Base visible in log: `feat/init-100-phase-5-reset` at `eb2e434`
- Proposal: `.pipeline/proposal.md`, 927 lines, SLICE-101.01 through SLICE-101.06
- Synthesis: `.pipeline/synthesis.md`, D1 through D12
- Research: `.pipeline/research.md`
- Reference only: `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/`
- No-backwards-compatibility convention: `~/ai/conventions/no-backwards-compatibility.md`

Scope rule: INIT-008 is a shape reference only. Do not merge the branch. Do not
park VKE artifacts in-tree. Delete retired files from this worktree.

## Current Repo State

The current `infra/` tree is the old origin-main shape:

```text
infra/
  README.md
  bootstrap/state-backend/main.tf
  environments/dev/backend.tfbackend
  environments/dev/main.tf
  environments/production/backend.tfbackend
  environments/production/main.tf
  environments/staging/backend.tfbackend
  environments/staging/main.tf
  modules/platform-cluster/main.tf
  modules/platform-network/main.tf
  tests/validate_platform_bootstrap.sh
```

The worktree does not contain INIT-008 channel roots, schemas, templates, or
scripts. Those concepts must be recreated from scratch using the reference
worktree as a template.

Current reusable files:

| Path | Disposition | Evidence |
|---|---|---|
| `infra/bootstrap/state-backend/main.tf` | REUSE | Same Object Storage subscription root shape. Diff from INIT-008 is comment-only; current file is active in this branch. |
| `infra/modules/platform-network/main.tf` | REUSE | Byte-identical to INIT-008 `platform-network/main.tf`; uses `vultr_vpc`. |
| `infra/tests/validate_platform_bootstrap.sh` | REWRITE | Active harness asserts VKE and hard env roots. Keep helper structure only. |
| `infra/README.md` | REWRITE | Active README names VKE module and `infra/environments/dev`. |

Current retired files:

| Path | Why retired |
|---|---|
| `infra/modules/platform-cluster/main.tf` | VKE module; declares `resource "vultr_kubernetes" "platform"`. |
| `infra/environments/dev/main.tf` | Hard environment root; calls `../../modules/platform-cluster`. |
| `infra/environments/dev/backend.tfbackend` | Hard environment backend; state key `infra/dev/terraform.tfstate`. |
| `infra/environments/staging/main.tf` | Hard environment root; calls `../../modules/platform-cluster`. |
| `infra/environments/staging/backend.tfbackend` | Hard environment backend; state key `infra/staging/terraform.tfstate`. |
| `infra/environments/production/main.tf` | Hard environment root; calls `../../modules/platform-cluster`. |
| `infra/environments/production/backend.tfbackend` | Hard environment backend; state key `infra/production/terraform.tfstate`. |

## BLOCKS_IMPLEMENTATION

Two naming/shape conflicts must be resolved before implementation starts:

1. `.pipeline/proposal.md` ships both `infra/channels/local.yaml` and
   `infra/channels/dev.yaml`, plus `infra/roots/channels/local/` and
   `infra/roots/channels/dev/`. The requested Phase 5 hookpoint output says the
   post-INIT-101 tree should show `infra/channels/dev.yaml` and
   `infra/roots/channels/dev/` only. This is not a codebase fact; it is a
   proposal-vs-instruction conflict. Implementation must choose whether the
   real local k3d channel id is `local` or `dev`.
2. `.pipeline/proposal.md` names the idempotent teardown script
   `infra/scripts/delete-local-channel.sh`. The requested final tree names
   `infra/scripts/tear-down-local-channel.sh`. Implementation must choose one
   public script path before tests are written.

Everything else maps cleanly to existing files and deletions.

## SLICE-101.01 - Discard VKE substrate and introduce k3s channel contract

Proposal dependencies: INIT-100 only.

| Path | Action | Rationale | Existing content notes |
|---|---|---|---|
| `infra/schemas/platform-channel.schema.json` | CREATE | New source channel contract with k3s-shaped fields. | Absent in current branch; INIT-008 schema is VKE-shaped and accepts `cluster.kubernetes_version`, `node_pools`, `ha_controlplanes`, `enable_firewall`. |
| `infra/schemas/platform-channel-resolved.schema.json` | CREATE | New resolved channel contract after inheritance. | Absent in current branch; INIT-008 resolved schema is VKE-shaped. |
| `infra/channels/local.yaml` | CREATE | Proposal's local k3d done-state channel. | Absent. Conflicts with requested final tree if `dev.yaml` is intended to be the local channel. |
| `infra/channels/dev.yaml` | CREATE | Remote Vultr VM plan channel, or local channel if conflict resolves that way. | Absent. INIT-008 `dev.yaml` is VKE-shaped; rewrite completely. |
| `infra/channels/fixtures/local-child.yaml` | CREATE | Fixture for local inheritance/ephemeral behavior. | Absent; INIT-008 fixture names differ and payloads are VKE-shaped. |
| `infra/channels/fixtures/dev-child.yaml` | CREATE | Fixture for dev inheritance/ephemeral behavior. | Absent; rewrite from INIT-008 inheritance fixture shape. |
| `infra/channels/fixtures/ephemeral-disabled.yaml` | CREATE | Negative fixture for child spawning. | INIT-008 has same concept but VKE payload; copy structure only. |
| `infra/channels/fixtures/missing-parent.yaml` | CREATE | Negative fixture for resolver errors. | INIT-008 file can be copied structurally; parent field remains the useful part. |
| `infra/channels/fixtures/circular-a.yaml` | CREATE | Negative fixture for cycle detection. | INIT-008 file can be copied structurally. |
| `infra/channels/fixtures/circular-b.yaml` | CREATE | Negative fixture for cycle detection. | INIT-008 file can be copied structurally. |
| `infra/scripts/resolve_platform_channel.py` | CREATE | Channel inheritance, validation, and resolved JSON output. | Absent; INIT-008 resolver structure is useful but CLI currently takes `--channel`, while proposal examples also use a path form. Pick one contract and update tests. |
| `infra/scripts/validate_platform_channels.py` | CREATE | Validates active and fixture channels. | Absent; INIT-008 validator shape useful, forbidden files and assertions need k3s update. |
| `infra/modules/platform-cluster/main.tf` | DELETE | Delete VKE substrate, no forwarding module. | Active file declares `vultr_kubernetes`, VKE outputs, VKE variables. |
| `infra/environments/dev/main.tf` | DELETE | Delete hard environment root. | Active file calls `../../modules/platform-cluster`. |
| `infra/environments/dev/backend.tfbackend` | DELETE | Delete hard environment backend. | Active file uses `infra/dev/terraform.tfstate`. |
| `infra/environments/staging/main.tf` | DELETE | Delete hard environment root. | Active file calls `../../modules/platform-cluster`. |
| `infra/environments/staging/backend.tfbackend` | DELETE | Delete hard environment backend. | Active file uses `infra/staging/terraform.tfstate`. |
| `infra/environments/production/main.tf` | DELETE | Delete hard environment root. | Active file calls `../../modules/platform-cluster`. |
| `infra/environments/production/backend.tfbackend` | DELETE | Delete hard environment backend. | Active file uses `infra/production/terraform.tfstate`. |
| `infra/README.md` | MODIFY | Remove VKE and hard environment instructions. | Current README names `platform-cluster/` and `infra/environments/dev`. |
| `.gitignore` | MODIFY | Ignore generated channel material. | Must cover `infra/channels/*/.generated/` without ignoring committed roots/lockfiles. |

File count: CREATE 12, MODIFY 2, DELETE 7.

## SLICE-101.02 - k3d local cluster module, scripts, and reachability harness

Proposal dependencies: SLICE-101.01.

| Path | Action | Rationale | Existing content notes |
|---|---|---|---|
| `infra/modules/platform-cluster-k3d/main.tf` | CREATE | OpenTofu local/k3d surface. | Absent; must not call VKE or create render-only stand-ins. |
| `infra/modules/platform-cluster-k3d/variables.tf` | CREATE | Contract for channel id, cluster name, k3s version, server/agent counts, ports/volumes. | Absent. |
| `infra/modules/platform-cluster-k3d/outputs.tf` | CREATE | Expose cluster name and kubeconfig path data consumed by scripts/template. | Absent. |
| `infra/modules/platform-cluster-k3d/versions.tf` | CREATE | Provider/version requirements for local module. | Absent. |
| `infra/scripts/install-cluster-tools.sh` | CREATE | A-7 closure; idempotent installer/checker for k3d `v5.8.3`. | Absent. Must report missing `k3d` today. |
| `infra/scripts/bring-up-local-channel.sh` | CREATE | Creates real local k3d cluster and writes channel kubeconfig. | Absent. Must not mutate global kubectl context. |
| `infra/scripts/delete-local-channel.sh` | CREATE | Proposal teardown path; delete `humility-local` and generated kubeconfig. | Absent. Conflicts with requested `tear-down-local-channel.sh` name. |
| `infra/scripts/tear-down-local-channel.sh` | CREATE? | Requested final tree path for teardown. | Absent. Only create this instead of `delete-local-channel.sh` if conflict is resolved that way. |
| `infra/tests/validate_platform_bootstrap.sh` | MODIFY | Replace VKE/env assertions with toolchain, k3d, kubeconfig, and reachability checks. | Current harness asserts `modules/platform-cluster/main.tf`, `environments/dev`, and `vultr_kubernetes`. |
| `infra/README.md` | MODIFY | Document local channel bring-up and teardown commands. | Current README is environment-root oriented. |
| `.gitignore` | MODIFY | Ignore generated kubeconfig and transient channel artifacts. | Confirm generated paths do not hide committed roots. |

File count if proposal path is kept: CREATE 7, MODIFY 3, DELETE 0.
If requested teardown name supersedes proposal: CREATE 7, MODIFY 3, DELETE 0,
but the created script path is `tear-down-local-channel.sh`, not
`delete-local-channel.sh`.

## SLICE-101.03 - Vultr VM module and cloud-init k3s bootstrap plan surface

Proposal dependencies: SLICE-101.01.

| Path | Action | Rationale | Existing content notes |
|---|---|---|---|
| `infra/modules/platform-cluster-vms/main.tf` | CREATE | Remote plan surface using `vultr_instance`, not VKE. | Absent. Must not preserve old VKE variable aliases. |
| `infra/modules/platform-cluster-vms/variables.tf` | CREATE | Remote VM variable contract. | Absent. Risk notes require `os_id`/cloud-init image handling and sensitive marking for user-data material. |
| `infra/modules/platform-cluster-vms/outputs.tf` | CREATE | Expose server ids, addresses, and remote kubeconfig path. | Absent. |
| `infra/modules/platform-cluster-vms/versions.tf` | CREATE | Vultr provider constraint `~> 2.30`. | Absent. |
| `infra/modules/platform-cluster-vms/cloud-init/k3s-server.yaml.tftpl` | CREATE | Cloud-init template for official k3s installer. | Absent. Must use strict failure behavior, not silent `runcmd` success. |
| `infra/modules/platform-network/main.tf` | MODIFY | Reuse VPC module but adjust environment wording to channel wording if needed. | Current content is byte-identical to INIT-008 and says "one VPC per environment". |
| `infra/modules/platform-network/versions.tf` | CREATE | Add provider constraint separated from `main.tf`. | Absent in current branch; copy verbatim from INIT-008 if still valid. |
| `infra/templates/platform-channel/main.tf` | CREATE | Template needs conditional target dispatch to k3d or Vultr VM modules. | Absent; INIT-008 template calls VKE module and must be rewritten. |
| `infra/templates/platform-channel/variables.tf` | CREATE | Variables for k3s-shaped channel payload. | Absent; INIT-008 variables are VKE-shaped. |
| `infra/templates/platform-channel/outputs.tf` | CREATE | Channel-scoped outputs such as kubeconfig path and endpoint references. | Absent; INIT-008 outputs expose VKE endpoint/id. |
| `infra/templates/platform-channel/versions.tf` | CREATE | Required providers and OpenTofu version. | Absent; copy structure, preserve Vultr `~> 2.30`. |
| `infra/roots/channels/dev/main.tf` | CREATE | Generated/committed dev channel root for remote plan validation. | Absent. INIT-008 root is VKE-shaped. |
| `infra/roots/channels/dev/backend.tfbackend` | CREATE | Generated backend config for dev channel state. | Absent; INIT-008 key shape `channels/dev/terraform.tfstate` survives. |
| `infra/roots/channels/dev/channel.auto.tfvars.json` | CREATE | Generated k3s/Vultr VM tfvars. | Absent; INIT-008 tfvars contain VKE fields. |
| `infra/roots/channels/dev/.terraform.lock.hcl` | CREATE | Committed provider lock for dev root. | Absent in current branch; INIT-008 lockfile is a provider-lock shape reference only. |
| `infra/tests/validate_platform_bootstrap.sh` | MODIFY | Add remote plan-surface checks. | Current harness validates old `environments/dev`. |

File count: CREATE 14, MODIFY 2, DELETE 0.

## SLICE-101.04 - Channel template and generated root rewrite

Proposal dependencies: SLICE-101.01 and SLICE-101.03.

| Path | Action | Rationale | Existing content notes |
|---|---|---|---|
| `infra/templates/platform-channel/main.tf` | MODIFY | Finalize target dispatch and module calls after both modules exist. | Created in 101.03 if proposal order is followed; otherwise CREATE here. |
| `infra/templates/platform-channel/variables.tf` | MODIFY | Finalize variable surface from resolved channel JSON. | Must exclude VKE names. |
| `infra/templates/platform-channel/outputs.tf` | MODIFY | Finalize outputs for local and remote consumers. | Must not expose VKE-only outputs. |
| `infra/templates/platform-channel/versions.tf` | MODIFY | Ensure provider constraints and no backend/provider blocks in module template. | INIT-008 version file is structurally useful. |
| `infra/roots/channels/local/main.tf` | CREATE | Proposal local generated root for k3d target. | Absent; conflicts with requested final tree if no local root should exist. |
| `infra/roots/channels/local/backend.tfbackend` | CREATE | Proposal local backend config. | Absent. Need confirm whether local root uses local state or S3 backend. |
| `infra/roots/channels/local/channel.auto.tfvars.json` | CREATE | Proposal local generated tfvars. | Absent. |
| `infra/roots/channels/local/.terraform.lock.hcl` | CREATE | Proposal local root lockfile. | Absent. |
| `infra/roots/channels/dev/main.tf` | MODIFY | Generated/committed dev root should be byte-identical after generator. | Absent now; created in 101.03 if proposal order is followed. |
| `infra/roots/channels/dev/backend.tfbackend` | MODIFY | Generated backend drift target. | Absent now. |
| `infra/roots/channels/dev/channel.auto.tfvars.json` | MODIFY | Generated tfvars drift target. | Absent now. |
| `infra/roots/channels/dev/.terraform.lock.hcl` | MODIFY | Provider lockfile committed and drift-checked. | Absent now. |
| `infra/scripts/generate_channel_backend.py` | CREATE | Render backend config from resolved channel. | Absent; INIT-008 generator structure survives. |
| `infra/scripts/generate_channel_tfvars.py` | CREATE | Render k3s-shaped `channel.auto.tfvars.json`. | Absent; INIT-008 generator emits VKE tfvars and must be rewritten. |
| `infra/scripts/spawn_platform_channel.py` | CREATE | Spawn ephemeral child channel under `.tmp/`. | Absent; INIT-008 safety shape is reusable. |
| `infra/tests/validate_platform_bootstrap.sh` | MODIFY | Add generator drift checks for committed roots. | Current harness has no channel generator checks. |

File count: CREATE 7, MODIFY 9, DELETE 0.

## SLICE-101.05 - Local k3d bootstrap end-to-end verification

Proposal dependencies: SLICE-101.02 and SLICE-101.04.

| Path | Action | Rationale | Existing content notes |
|---|---|---|---|
| `infra/scripts/bring-up-local-channel.sh` | MODIFY | Harden idempotency, stale generated-state detection, and real API reachability. | Created in 101.02. |
| `infra/scripts/delete-local-channel.sh` | MODIFY | Harden no-op second teardown. | Created in 101.02 if proposal name wins. |
| `infra/scripts/tear-down-local-channel.sh` | MODIFY? | Harden no-op second teardown if requested name wins. | Do not keep both teardown scripts as compatibility aliases. |
| `infra/tests/validate_platform_bootstrap.sh` | MODIFY | Must prove `kubectl get nodes` against channel kubeconfig and expected node shape. | Current harness must be replaced, not extended. |
| `infra/tests/README.md` | CREATE | Optional, only if harness usage needs local test documentation. | Absent. Do not create if `infra/README.md` is sufficient. |
| `infra/README.md` | MODIFY | Document done-state proof and cleanup. | Current README is stale. |
| `.gitignore` | MODIFY | Confirm generated kubeconfig/state ignores. | No compatibility exceptions. |

File count with optional test README: CREATE 1, MODIFY 5, DELETE 0.
Minimum file count without optional README: CREATE 0, MODIFY 5, DELETE 0.

## SLICE-101.06 - Documentation and INIT-102 handoff

Proposal dependencies: SLICE-101.05.

| Path | Action | Rationale | Existing content notes |
|---|---|---|---|
| `infra/README.md` | MODIFY | Final operator documentation for k3s/k3d channel pattern. | Current README names VKE and hard environments. |
| `docs/deployment-substrate.md` | CREATE? | Only if existing docs need a stable substrate reference beyond infra README. | No exact file exists today. If created, keep it concise and point to D8. |
| `.pipeline/implementation.md` | MODIFY | Record slice status if implementation stage uses it. | Exists today; not inspected for hookpoint ownership. |
| `DECISIONS.md` | MODIFY? | Only for a mechanical D8 cross-reference, no new decision expected. | D8 already exists and names k3s/k3d/Vultr VMs. |

File count if docs page is added and DECISIONS is untouched: CREATE 1,
MODIFY 2, DELETE 0. Minimum count: CREATE 0, MODIFY 2, DELETE 0.

## INIT-008 Reference Salvage

Use INIT-008 for structure, not content. Equivalent INIT-101 paths are in this
worktree.

| INIT-008 path or concept | Disposition | INIT-101 equivalent | Notes |
|---|---|---|---|
| `infra/README.md` | DISCARD | `infra/README.md` | VKE/channel text is stale. Rewrite around D8, local k3d, remote plan-only boundary. |
| `infra/bootstrap/state-backend/main.tf` | COPY-AND-MODIFY | `infra/bootstrap/state-backend/main.tf` | Branch already has this root. INIT-008 differs only in comment wording; keep active branch root unless docs wording is corrected. |
| `infra/bootstrap/state-backend/.terraform.lock.hcl` | COPY-AND-MODIFY | `infra/bootstrap/state-backend/.terraform.lock.hcl` | Current branch lacks lockfile. Generate with current OpenTofu/provider, do not blindly copy if provider hashes differ. |
| `infra/channels/dev.yaml` | DISCARD CONTENT, COPY SHAPE | `infra/channels/dev.yaml` | YAML layout survives; VKE fields do not. |
| `infra/channels/fixtures/circular-a.yaml` | COPY-AND-MODIFY | `infra/channels/fixtures/circular-a.yaml` | Cycle concept survives; ensure required source schema fields match k3s schema. |
| `infra/channels/fixtures/circular-b.yaml` | COPY-AND-MODIFY | `infra/channels/fixtures/circular-b.yaml` | Same as circular-a. |
| `infra/channels/fixtures/dev-pr-123.yaml` | COPY-AND-MODIFY | `infra/channels/fixtures/dev-child.yaml` or equivalent | Ephemeral child fixture shape survives; name should match new fixture scheme. |
| `infra/channels/fixtures/e2e-from-dev.yaml` | COPY-AND-MODIFY | `infra/channels/fixtures/dev-child.yaml` | Inheritance override concept survives; VKE cluster label override does not. |
| `infra/channels/fixtures/e2e-pr-1234.yaml` | COPY-AND-MODIFY | `infra/channels/fixtures/local-child.yaml` or dev child fixture | Tenant child concept survives. |
| `infra/channels/fixtures/ephemeral-disabled.yaml` | COPY-AND-MODIFY | `infra/channels/fixtures/ephemeral-disabled.yaml` | Negative spawn fixture survives; rewrite cluster payload. |
| `infra/channels/fixtures/missing-parent.yaml` | COPY-AND-MODIFY | `infra/channels/fixtures/missing-parent.yaml` | Missing-parent concept survives. |
| `infra/modules/platform-cluster/main.tf` | DISCARD | none | VKE module using `vultr_kubernetes`. Deleted, replaced by k3d and VM modules. |
| `infra/modules/platform-cluster/versions.tf` | DISCARD | none | Do not keep forwarding module or VKE provider lock surface. |
| `infra/modules/platform-network/main.tf` | COPY-VERBATIM / REUSE | `infra/modules/platform-network/main.tf` | Current file is byte-identical. Optional comments may shift from environment to channel. |
| `infra/modules/platform-network/versions.tf` | COPY-VERBATIM | `infra/modules/platform-network/versions.tf` | Current branch lacks it; provider constraint remains `~> 2.30`. |
| `infra/roots/channels/dev/main.tf` | DISCARD CONTENT, COPY SHAPE | `infra/roots/channels/dev/main.tf` | Root module wrapper shape survives; VKE variables do not. |
| `infra/roots/channels/dev/backend.tfbackend` | COPY-AND-MODIFY | `infra/roots/channels/dev/backend.tfbackend` | State key shape survives; generated by new backend generator. |
| `infra/roots/channels/dev/channel.auto.tfvars.json` | DISCARD CONTENT, COPY SHAPE | `infra/roots/channels/dev/channel.auto.tfvars.json` | Must emit k3s/Vultr VM fields, not VKE fields. |
| `infra/roots/channels/dev/.terraform.lock.hcl` | COPY-AND-MODIFY | `infra/roots/channels/dev/.terraform.lock.hcl` | Generate with current root/provider graph. |
| `infra/schemas/platform-channel.schema.json` | DISCARD CONTENT, COPY SHAPE | `infra/schemas/platform-channel.schema.json` | JSON Schema structure survives; VKE fields removed. |
| `infra/schemas/platform-channel-resolved.schema.json` | DISCARD CONTENT, COPY SHAPE | `infra/schemas/platform-channel-resolved.schema.json` | Same as source schema. |
| `infra/scripts/resolve_platform_channel.py` | COPY-AND-MODIFY | `infra/scripts/resolve_platform_channel.py` | Keep structured errors, inheritance, fixture lookup; update CLI if path-based invocation is required. |
| `infra/scripts/validate_platform_channels.py` | COPY-AND-MODIFY | `infra/scripts/validate_platform_channels.py` | Keep active/fixture registry checks; update assertions for k3s targets. |
| `infra/scripts/generate_channel_backend.py` | COPY-AND-MODIFY | `infra/scripts/generate_channel_backend.py` | Keep backend render pattern; update input contract if resolver accepts channel YAML directly. |
| `infra/scripts/generate_channel_tfvars.py` | COPY-AND-MODIFY | `infra/scripts/generate_channel_tfvars.py` | Rewrite payload completely; old `cluster_kubernetes_version`, `node_plan`, `node_quantity`, `ha_controlplanes`, `enable_firewall` are forbidden. |
| `infra/scripts/spawn_platform_channel.py` | COPY-AND-MODIFY | `infra/scripts/spawn_platform_channel.py` | Keep `.tmp/` safety and no writes under active `infra/channels` or `infra/roots`. |
| `infra/templates/platform-channel/main.tf` | DISCARD CONTENT, COPY SHAPE | `infra/templates/platform-channel/main.tf` | Rewrite module calls to `platform-cluster-k3d` and `platform-cluster-vms`. |
| `infra/templates/platform-channel/variables.tf` | DISCARD CONTENT, COPY SHAPE | `infra/templates/platform-channel/variables.tf` | Rewrite variable names and validations. |
| `infra/templates/platform-channel/outputs.tf` | DISCARD CONTENT, COPY SHAPE | `infra/templates/platform-channel/outputs.tf` | Rewrite outputs for k3d/k3s VM surfaces. |
| `infra/templates/platform-channel/versions.tf` | COPY-AND-MODIFY | `infra/templates/platform-channel/versions.tf` | Keep OpenTofu/provider shape, but provider set may differ for local module. |
| `infra/tests/validate_platform_bootstrap.sh` | COPY-AND-MODIFY | `infra/tests/validate_platform_bootstrap.sh` | Keep helper style and sections; rewrite assertions around k3s channel contract and real local cluster. |
| `infra/tests/conftest.py` and API/Discord runtime tests | COPY-VERBATIM / LEAVE | Existing same paths in current branch | These are service tests unrelated to infra substrate. Do not churn them. |

## Origin-Main Artifact Deletion Plan

| Path | Delete owner | Active references to update |
|---|---|---|
| `infra/modules/platform-cluster/main.tf` | SLICE-101.01 | `infra/tests/validate_platform_bootstrap.sh`, `infra/README.md`, and hard env roots. |
| `infra/modules/platform-cluster/` | SLICE-101.01 | Remove directory after file deletion. No forwarding replacement. |
| `infra/environments/dev/main.tf` | SLICE-101.01 | Current root calls VKE module and VKE variables. |
| `infra/environments/dev/backend.tfbackend` | SLICE-101.01 | Current key is `infra/dev/terraform.tfstate`; channels use `channels/<id>/terraform.tfstate`. |
| `infra/environments/staging/main.tf` | SLICE-101.01 | Current root calls VKE module. |
| `infra/environments/staging/backend.tfbackend` | SLICE-101.01 | Current key is `infra/staging/terraform.tfstate`. |
| `infra/environments/production/main.tf` | SLICE-101.01 | Current root calls VKE module. |
| `infra/environments/production/backend.tfbackend` | SLICE-101.01 | Current key is `infra/production/terraform.tfstate`. |
| `infra/environments/` | SLICE-101.01 | Remove empty directory after child roots are deleted. |

Origin-main deletion count: 7 tracked files plus 2 now-empty directories
(`infra/modules/platform-cluster/` and `infra/environments/`).

## Cross-Reference Grep

Command used:

```bash
grep -rn "platform-cluster\|vultr_kubernetes\|infra/environments\|environments/dev\|environments/staging\|environments/production\|kubernetes_version\|node_pools\|ha_controlplanes\|enable_firewall" infra .pipeline docs DECISIONS.md README.md 2>/dev/null
```

Active infra hits that require implementation updates:

| Hit | Owner | Required handling |
|---|---|---|
| `infra/modules/platform-cluster/main.tf` VKE variables/resources/outputs | SLICE-101.01 | Delete file and directory. |
| `infra/environments/dev/main.tf` VKE module call and VKE variables | SLICE-101.01 | Delete root. |
| `infra/environments/staging/main.tf` VKE module call and VKE variables | SLICE-101.01 | Delete root. |
| `infra/environments/production/main.tf` VKE module call and VKE variables | SLICE-101.01 | Delete root. |
| `infra/tests/validate_platform_bootstrap.sh` old file list, VKE assertions, env validation | SLICE-101.02 through 101.05 | Rewrite harness; do not leave old assertions. |
| `infra/README.md` VKE module and env-root instructions | SLICE-101.01, final in 101.06 | Rewrite. |

Pipeline docs, risk docs, synthesis, research, proposal, and `DECISIONS.md`
also contain VKE terms as historical evidence. Those are not active code
references. SLICE-101.06 docs grep must avoid false failures by scoping
forbidden terms to active infra/docs where appropriate.

## Toolchain Prerequisite Verification

| Tool | Status | Evidence | Slice owner |
|---|---|---|---|
| `tofu` | PRESENT | `OpenTofu v1.11.5` | Existing prerequisite. |
| `kubectl` | PRESENT | client `v1.34.1`; embedded `kustomizeVersion: v5.7.1` | Existing prerequisite. |
| standalone `kustomize` | MISSING | `kustomize: command not found` | Not required for INIT-101 if kubectl embedded kustomize is the intended surface. |
| `docker` | PRESENT | `Docker version 29.4.0` | Existing prerequisite for k3d. |
| `k3d` | MISSING | `k3d: command not found` | SLICE-101.02 installer/check owns this. |
| `k3s` binary | MISSING | `k3s: command not found` | Not required locally; real Linux VM bootstrap installs it through cloud-init. |

## New `infra/` Shape After INIT-101

Proposal-derived shape, with conflicts annotated:

```text
infra/
  README.md
  bootstrap/state-backend/
    main.tf
    .terraform.lock.hcl
  modules/
    platform-network/
      main.tf
      versions.tf
    platform-cluster-k3d/
      main.tf
      variables.tf
      outputs.tf
      versions.tf
    platform-cluster-vms/
      main.tf
      variables.tf
      outputs.tf
      versions.tf
      cloud-init/k3s-server.yaml.tftpl
  templates/platform-channel/
    main.tf
    variables.tf
    outputs.tf
    versions.tf
  channels/
    local.yaml        # proposal; conflicts with requested dev-only shape
    dev.yaml
    fixtures/
      local-child.yaml
      dev-child.yaml
      ephemeral-disabled.yaml
      missing-parent.yaml
      circular-a.yaml
      circular-b.yaml
  schemas/
    platform-channel.schema.json
    platform-channel-resolved.schema.json
  roots/channels/
    local/            # proposal; conflicts with requested tree if omitted
      main.tf
      backend.tfbackend
      channel.auto.tfvars.json
      .terraform.lock.hcl
    dev/
      main.tf
      backend.tfbackend
      channel.auto.tfvars.json
      .terraform.lock.hcl
  scripts/
    install-cluster-tools.sh
    resolve_platform_channel.py
    spawn_platform_channel.py
    validate_platform_channels.py
    generate_channel_backend.py
    generate_channel_tfvars.py
    bring-up-local-channel.sh
    delete-local-channel.sh       # proposal name
    tear-down-local-channel.sh    # requested name; choose one, not both
  tests/
    validate_platform_bootstrap.sh
```

Required absences after INIT-101:

```text
infra/environments/
infra/modules/platform-cluster/
gitops/
secrets handling
object storage workloads
cert-manager / DNS
Crossplane
```

## Risk-Deferred LOW Observations

Risk files present in this worktree:
- `plans/risk/init-101-audit.md`: gate status LOW, no audit findings.
- `plans/risk/init-101-scope.md`: gate status LOW, soft observation that
  post-INIT-117 remote deployment work lacks a concrete successor INIT id.
- `plans/risk/init-101-shortcut.md`: gate status LOW, implementation-tightening
  notes S1 through S7.

Track these during hookpoint-to-implementation handoff:

| ID | Severity in file | Implementation handling |
|---|---|---|
| S1 | MEDIUM | Cloud-init install path must fail hard; do not allow `curl` failure followed by successful `cp`/`chmod`. |
| S2 | MEDIUM | Document accepted upstream installer integrity tradeoff or implement installer verification. |
| S3 | LOW | Prefer "deployment" wording over "verification" where the local channel is the done state. |
| S4 | LOW | Add `os_id` or equivalent cloud-init-capable image selection to remote VM contract. |
| S5 | LOW | Name the successor for first real remote k3s apply/kubeconfig retrieval, or list constituent successors consistently. |
| S6 | LOW | Resolve `bootstrap.token` asymmetry: omit for INIT-101 or define schema/module/template handling. |
| S7 | LOW | Mark user-data/bootstrap variables sensitive where applicable and prevent plan/log leakage. |

These observations do not block hookpoint mapping, but S1/S2/S4/S6/S7 belong
to SLICE-101.03, S3/S5 belong to SLICE-101.06, and script/test language in
SLICE-101.05 should avoid fake-completion framing.

## Implementation DAG

Proposal DAG:

```text
INIT-100
  -> SLICE-101.01
      -> SLICE-101.02
      -> SLICE-101.03
          -> SLICE-101.04
      -> SLICE-101.04
          -> SLICE-101.05
              -> SLICE-101.06
```

Verified order:

1. SLICE-101.01 must run first. It deletes active VKE/env artifacts and creates
   the k3s channel contract so later slices cannot depend on old names.
2. SLICE-101.02 can run after 101.01 because it needs the local channel
   contract and writes the k3d module/scripts.
3. SLICE-101.03 can run after 101.01 because it needs the k3s channel contract
   and owns remote VM module shape.
4. SLICE-101.04 depends on both 101.01 and 101.03. It needs schema and remote
   module variables before generators can emit final roots.
5. SLICE-101.05 depends on 101.02 and 101.04. It needs scripts plus generated
   local root/channel artifacts before real local bootstrap proof.
6. SLICE-101.06 depends on 101.05 because docs must describe the proven local
   done state, not the intended one.

DAG conflicts:
- No cycle or missing dependency found.
- File ownership overlap is intentional for `infra/tests/validate_platform_bootstrap.sh`,
  `infra/README.md`, and `infra/templates/platform-channel/*.tf`; each later
  slice refines checks or docs after new substrate exists.
- The local-channel naming conflict and teardown-script naming conflict above
  must be resolved before test/code agent separation, because contracts/tests
  need stable public paths.

## Summary Counts

Per-slice file counts:

| Slice | CREATE | MODIFY | DELETE |
|---|---:|---:|---:|
| SLICE-101.01 | 12 | 2 | 7 |
| SLICE-101.02 | 7 | 3 | 0 |
| SLICE-101.03 | 14 | 2 | 0 |
| SLICE-101.04 | 7 | 9 | 0 |
| SLICE-101.05 | 0-1 | 5 | 0 |
| SLICE-101.06 | 0-1 | 2 | 0 |

Origin-main deletion count: 7 tracked files, plus removal of the retired
`infra/modules/platform-cluster/` and `infra/environments/` directories after
their tracked files are gone.

BLOCKS_IMPLEMENTATION flags:
- `BLOCKS_IMPLEMENTATION: local channel id/root conflict`
- `BLOCKS_IMPLEMENTATION: teardown script path conflict`

Toolchain status:
- `tofu`: present, `1.11.5`
- `kubectl`: present, `1.34.1`
- embedded kustomize: present, `5.7.1`
- standalone `kustomize`: missing
- `docker`: present, `29.4.0`
- `k3d`: missing; SLICE-101.02 owns installer/check
- `k3s`: missing; not required for local k3d
