# Scope risk assessment — proposals/31-phase1-terraform.md

Date: 2026-04-14
Assessor: claude-opus (scope)

## Verdict

**LOW**

The proposal is appropriately scoped for the Terraform bootstrap layer. It stays within the five-file boundary, has a clear anti-scope section that correctly excludes later-phase concerns (Flux CD, Kong, Buildkite, secrets, Packer), and differentiates staging and production environments reasonably. The one notable gap — SSH key material mismatch between the proposed root variable surface and the upstream module's required inputs — is already acknowledged in the proposal text and the needs synthesis, and is resolvable during implementation without changing the design's scope or shape. No findings justify escalation to MEDIUM overall.

## Findings

### Finding 1 — SSH key material gap in variable surface

- **Severity**: MEDIUM
- **Section of proposal**: `infra/variables.tf` — Required Variables; `infra/cluster.tf` — Module Inputs
- **Description**: The proposal declares `ssh_key_ids` (list of Hetzner SSH key identifiers) as the root variable and passes it directly to the module as `ssh_key_ids = var.ssh_key_ids`. However, the research (`research/31-phase1-terraform.md`, section 3) documents that the upstream `kube-hetzner` module requires `ssh_public_key` (string) and `ssh_private_key` (sensitive string) as its actual inputs, and does not mention `ssh_key_ids` as a module input at all. The needs synthesis explicitly flagged this: "SSH keys need `ssh_public_key` (string) and `ssh_private_key` (sensitive string), not just `ssh_key_ids`" and recommended "The implementation should include both interfaces."
- **Why it matters**: As designed, the `cluster.tf` module call cannot satisfy the upstream module's SSH key requirements. The module instantiation would fail at `tofu plan` because the required `ssh_public_key` and `ssh_private_key` inputs would be missing. The proposal acknowledges the mismatch (line 138-140) but does not resolve it in the variable surface or the module inputs section.
- **Recommendation**: Either add `ssh_public_key` and `ssh_private_key` to the root variable surface and the module inputs, or document explicitly in the cluster.tf design that the `ssh_key_ids` root variable will be translated into the module's expected SSH key material inputs in the locals block. The current design does neither — it acknowledges the gap but passes through the incompatible interface unchanged.

### Finding 2 — Traefik ingress controller vs Phase 1 Kong plan

- **Severity**: LOW
- **Section of proposal**: `infra/variables.tf` — Required Variables (ingress_controller default); both tfvars files
- **Description**: The proposal defaults `ingress_controller = "traefik"` and both environment tfvars files set it to `"traefik"`. The Phase 1 foundation plan (`plans/proposals/phase1-foundation.md`, section 3) specifies Kong as the baseline ingress layer. While the proposal correctly excludes Kong deployment from its own scope, the decision to install traefik through `kube-hetzner` creates a component that will either need to be replaced by Kong later (wasted bootstrap work and potential conflict) or coexist with Kong (added complexity).
- **Why it matters**: This is not a scope violation — the proposal correctly defers Kong to a later concern. But it is a downstream friction point. If the next Terraform-adjacent proposal installs Kong, the operator will need to decide whether to remove traefik, disable it in kube-hetzner, or run both. The ingress_controller variable makes this changeable, so the blast radius is small.
- **Recommendation**: No change needed in this proposal. Consider adding a brief note in the Architecture Notes that the `ingress_controller` value is a kube-hetzner bootstrap default and is expected to be revisited when Kong is deployed. This prevents a future implementer from assuming traefik is the permanent choice.

### Finding 3 — Module version deferred without compatibility baseline

- **Severity**: LOW
- **Section of proposal**: `infra/cluster.tf` — Module Shape
- **Description**: The proposal requires an explicit `kube-hetzner` module version pin but defers the exact version to implementation: "The exact release number belongs in implementation after compatibility verification." Given the documented mismatch between `hcloud ~> 1.49` and the upstream module's current provider floor (`>= 1.59.0` in docs, `>= 1.51.0` in example), there is a real possibility that no current `kube-hetzner` release is compatible with the locked provider constraint without modification.
- **Why it matters**: If the implementation discovers no compatible module version exists, the scope of this proposal changes — either the provider pin must be updated (locked decision change) or a fork/older release of kube-hetzner must be used (additional maintenance burden). The proposal handles this correctly at the design level by documenting the mismatch and requiring explicit pinning, but the deferred verification means the implementation could hit a wall.
- **Recommendation**: No change needed. The proposal correctly identifies this as a known risk in the Tradeoffs section. The deferral to implementation is appropriate for a design document. The important thing is that the risk is visible, and it is.

### Finding 4 — State locking unavailable at declared version floor

- **Severity**: LOW
- **Section of proposal**: `infra/main.tf` — Key Decisions
- **Description**: The proposal sets `required_version = ">= 1.6.0"` for the OpenTofu CLI. The research documents that S3-native state locking (`use_lockfile = true`) requires OpenTofu 1.10+. Hetzner Object Storage does not provide DynamoDB, so there is no alternative locking mechanism. This means concurrent `tofu apply` operations against the same state could corrupt state files if the operator is running a CLI version between 1.6.0 and 1.9.x.
- **Why it matters**: For a single-operator bootstrap, this is not a practical risk. It becomes relevant if CI or multiple operators run concurrent applies. The proposal does not mention state locking at all.
- **Recommendation**: No change needed to the scope. The version floor is a locked task input. Consider adding a brief note in the Architecture Notes or main.tf design section that state locking requires OpenTofu >= 1.10 and that concurrent applies should be operationally prevented until that floor is established.

### Finding 5 — Environment sizing is appropriately differentiated

- **Severity**: LOW (positive finding)
- **Section of proposal**: Both tfvars files
- **Description**: Staging (1 CP / 1 worker / cpx21 / no API LB / OS upgrades off) and production (3 CP / 3 workers / cpx31 / API LB on / OS upgrades on) are meaningfully differentiated. Staging is the minimum viable shape that still preserves the control-plane-versus-worker topology. Production is the minimum HA shape. Neither environment is oversized for Phase 1 foundation needs.
- **Why it matters**: Good environment parity reduces the risk that staging doesn't catch production issues, while appropriate differentiation keeps costs proportional.
- **Recommendation**: None. The sizing choices are well-reasoned and aligned with upstream module guidance.

## Overall assessment

The proposal is well-scoped for its stated goal: a thin Terraform bootstrap wrapper around `kube-hetzner` expressed in five files. The anti-scope section is comprehensive and correctly excludes concerns belonging to later phases. The variable surface is intentionally smaller than the full module input list, which is the right design choice for a foundation bootstrap. Environment differentiation is reasonable.

The only finding above LOW severity is the SSH key material gap (Finding 1). The proposal acknowledges the mismatch between `ssh_key_ids` and the upstream module's `ssh_public_key`/`ssh_private_key` requirements, but the cluster.tf module inputs section passes `ssh_key_ids` through without translation, leaving the module call structurally incomplete. This is a real gap, but it is a known gap — both the proposal and the needs synthesis document it — and it is resolvable during implementation by adding the missing variables or adding a translation layer in locals.

The remaining findings (traefik/Kong tension, deferred module version, state locking gap) are all LOW and are correctly handled by the proposal's design choices and explicit documentation of tradeoffs. None of them represent scope creep, scope omission, or downstream lock-in that would be hard to change later.

Verdict remains **LOW**. The proposal is appropriately sized for the problem.
