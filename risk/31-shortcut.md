# Shortcut risk assessment — proposals/31-phase1-terraform.md

Date: 2026-04-14
Assessor: claude-opus (shortcut)

## Verdict

**LOW**

The proposal takes a disciplined, variable-driven approach to Terraform root-module design with a proper translation layer between simple root inputs and the richer upstream `kube-hetzner` module interface. No hardcoded hacks, no duplicated module calls, and no workarounds that would need to be undone. Three minor findings exist but none rise above LOW individually.

## Findings

### Finding 1 — SSH key variable surface is incomplete relative to upstream requirements

- **Severity**: LOW
- **Section of proposal**: `infra/variables.tf` — Required Variables; `infra/cluster.tf` — Module Inputs
- **Description**: The proposal declares `ssh_key_ids` (list of Hetzner SSH key identifiers) as the only SSH-related root variable and passes it directly to the module as `ssh_key_ids = var.ssh_key_ids`. However, the research (`research/31-phase1-terraform.md`, section 4) documents that the upstream `kube-hetzner` module requires `ssh_public_key` (string) and `ssh_private_key` (sensitive string) as mandatory inputs. The needs synthesis (`research/31-phase1-terraform-needs.md`, Gap #2) explicitly flags this: "upstream `kube-hetzner` requires `ssh_public_key` and `ssh_private_key` strings. The implementation should include both interfaces." The proposal does not incorporate that guidance into its variable table or module inputs section.
- **Why it matters**: If the implementation follows the proposal literally, it will omit required module inputs. This could lead to an implementation-time workaround (empty strings, placeholder values, or an undocumented variable addition) rather than a clean design-time decision. The gap is small — two additional variables — but leaving it unaddressed in the proposal pushes the decision to the code agent without design guidance.
- **Recommendation**: Add `ssh_public_key` (string, sensitive) and `ssh_private_key` (string, sensitive) to the variables table and include them in the module inputs section of `cluster.tf`. The existing `ssh_key_ids` can coexist with these since the upstream module accepts both.

### Finding 2 — Tfvars files repeat default values verbatim

- **Severity**: LOW
- **Section of proposal**: `infra/environments/staging/terraform.tfvars` — Proposed Values
- **Description**: The staging tfvars file explicitly sets 12 values that are identical to the defaults already declared in `variables.tf`: `location`, `network_zone`, `control_plane_server_type`, `worker_server_type`, `use_control_plane_lb`, `control_plane_lb_enable_public_interface`, `ingress_controller`, `load_balancer_type`, `load_balancer_location`, `create_kubeconfig`, `automatically_upgrade_os`, and `placement_group_disable`. Production repeats 7 of those same defaults. This means staging could express its entire unique configuration in just 4 lines (`environment`, `cluster_name`, `control_plane_count`, `worker_count`).
- **Why it matters**: This is not a DRY violation in the traditional sense — Terraform tfvars files are commonly written to be self-documenting and fully explicit per environment. The redundancy is a style choice, not a maintenance hazard. It becomes a minor concern only if defaults change later and the tfvars files are not updated in sync, silently overriding the new defaults with stale values.
- **Recommendation**: No change required. This is acceptable Terraform practice. If desired, the tfvars files could omit values that match defaults and add a comment noting which defaults are inherited, but that is a style preference, not a shortcut fix.

### Finding 3 — Module version pin deferred to implementation

- **Severity**: LOW
- **Section of proposal**: `infra/cluster.tf` — Module Shape
- **Description**: The proposal states that the `kube-hetzner` module version should be "a deliberately pinned release compatible with the replayed provider line" but says "the exact release number belongs in implementation after compatibility verification." This defers a design decision to the code agent. Given the documented mismatch between `hcloud ~> 1.49` and upstream's `hcloud >= 1.59.0` floor, finding a compatible module release is a non-trivial compatibility exercise.
- **Why it matters**: If no `kube-hetzner` release is actually compatible with `hcloud ~> 1.49`, the implementation would be forced into an undocumented workaround (bumping the provider pin, using an unreleased module version, or forking). The proposal acknowledges the mismatch clearly and states the design rule (explicit pin, not floating latest), which is the right principle. The risk is that the deferred verification discovers an incompatibility after the design is accepted.
- **Recommendation**: No change to the proposal structure needed. The design rule (explicit pin) is correct. The compatibility verification is implementation work, not design work, and the proposal correctly identifies it as such. If the mismatch proves irreconcilable, the implementation should surface that as a blocking finding rather than silently working around it.

## Overall assessment

The proposal is well-structured and avoids the common Terraform shortcuts: no hardcoded credentials, no magic numbers without variables, no duplicated module calls between environments, no inline workarounds for the S3-compatible backend, and no "for now" hacks that would need unwinding. The translation layer in `cluster.tf` (locals converting flat variables to rich nodepool objects) is the correct abstraction level for Phase 1. The backend design follows the standard partial-configuration pattern for non-AWS object stores.

The three findings are all LOW severity. Finding 1 (SSH key gap) is the most actionable — it is a small omission that the needs synthesis already flagged, and addressing it in the proposal would prevent an ad-hoc implementation-time decision. Findings 2 and 3 are observations rather than problems: explicit tfvars are normal Terraform style, and deferring version verification to implementation is reasonable given the proposal is design-only.

The proposal does not introduce technical debt, hacks, or workarounds. Verdict: **LOW**.
