# Audit risk assessment — proposals/31-phase1-terraform.md

Date: 2026-04-14
Assessor: claude-opus (audit)

## Verdict

**LOW**

The proposal follows standard Terraform credential hygiene: the API token is marked sensitive, backend credentials are excluded from source, and kubeconfig generation is disabled. The public Kubernetes API surface in production is explicitly acknowledged as a Phase 1 tradeoff with hardening deferred. No finding rises to the level of a concrete exploit path or data-integrity failure that would block implementation.

## Findings

### Finding 1 — Terraform state contains sensitive values in plaintext

- **Severity**: LOW
- **Section of proposal**: `infra/main.tf` — backend configuration; Architecture Notes — Remote State
- **Description**: Terraform state files inherently store resource attributes in plaintext, including values marked `sensitive = true` in variable declarations. The `hcloud_token` will appear in the state file stored in Hetzner Object Storage. The proposal specifies an S3-compatible backend but does not mention server-side encryption or any state-at-rest protection.
- **Why it matters**: If the Object Storage bucket permissions are misconfigured or access keys are leaked, the state file exposes the Hetzner API token and any other sensitive resource attributes. The blast radius is full control of the Hetzner project resources.
- **Recommendation**: Note in the backend design that the state bucket should use server-side encryption if Hetzner Object Storage supports it, or document that state-at-rest encryption is an accepted deferral with the bucket ACL as the primary control. This is a documentation clarification, not a blocking design change — Terraform state containing sensitive values is standard, and the mitigation is bucket access control, which the proposal correctly defers to operational convention.

### Finding 2 — Public Kubernetes API in production

- **Severity**: LOW
- **Section of proposal**: `infra/environments/production/terraform.tfvars` — `control_plane_lb_enable_public_interface = true`
- **Description**: The production environment exposes the Kubernetes API server on a public IP via the control-plane load balancer. Any entity on the internet can attempt to authenticate against the API endpoint.
- **Why it matters**: A public kube-apiserver is the most common attack surface for Kubernetes clusters. Credential stuffing, token theft, or a future RBAC misconfiguration could grant cluster access. The blast radius is full cluster compromise.
- **Recommendation**: The proposal already acknowledges this as a deliberate Phase 1 tradeoff (Tradeoffs section: "Public API Surface in Production") and defers hardening to a later proposal. This is acceptable for Phase 1 bootstrap because the alternative — a private-only API with VPN or bastion access — requires infrastructure not yet in scope. The finding is recorded so the hardening is not forgotten.

### Finding 3 — No state locking below OpenTofu 1.10

- **Severity**: LOW
- **Section of proposal**: `infra/main.tf` — `required_version = ">= 1.6.0"`; backend configuration
- **Description**: The proposal sets the OpenTofu floor at `>= 1.6.0`, but S3-native state locking (`use_lockfile = true`) requires OpenTofu 1.10+. Hetzner Object Storage does not provide DynamoDB, so there is no alternative locking mechanism for older CLI versions. Concurrent `tofu apply` runs against the same state could corrupt it.
- **Why it matters**: State corruption requires manual recovery (importing resources, rewriting state). In Phase 1 with a small team this is unlikely but not impossible — an operator running apply while CI also runs apply would hit this. The blast radius is state file corruption requiring manual intervention, not data loss in Hetzner resources.
- **Recommendation**: Either raise the effective operator floor to `>= 1.10.0` (which the research already recommends for locking) or document that concurrent applies are prohibited by convention until the floor is raised. This is an operational process concern, not a design flaw — the research document already flagged it.

### Finding 4 — Module version deferred to implementation

- **Severity**: LOW
- **Section of proposal**: `infra/cluster.tf` — Module Shape
- **Description**: The proposal requires an explicit module version pin for `kube-hetzner` but states "The exact release number belongs in implementation after compatibility verification." Until the pin is set, there is a window where `tofu init` could pull the latest module release, which may contain unexpected changes.
- **Why it matters**: A supply-chain attack on the `kube-hetzner` module between proposal and implementation could introduce malicious code. The practical likelihood is very low — the module is well-known and registry-hosted, and `.terraform.lock.hcl` (which the research recommends committing) pins the actual hash after first init.
- **Recommendation**: The design rule is correct. Implementation should pin the version on first `tofu init` and commit `.terraform.lock.hcl` immediately. No proposal change needed — the supply-chain control is already specified, just deferred to the right phase.

### Finding 5 — SSH key interface mismatch with upstream module

- **Severity**: LOW
- **Section of proposal**: `infra/variables.tf` — `ssh_key_ids`
- **Description**: The proposal declares `ssh_key_ids` as `list(string)` (Hetzner SSH key identifiers). The research notes that upstream `kube-hetzner` requires `ssh_public_key` (string) and `ssh_private_key` (sensitive string) — actual key material, not just IDs. The synthesis document flags this gap but the proposal does not resolve it.
- **Why it matters**: If the implementation later adds `ssh_private_key` as a variable to bridge this gap, that introduces SSH private key material flowing through Terraform state (same plaintext-in-state concern as Finding 1, but with higher-severity key material). If the implementation uses only `ssh_key_ids` and the module doesn't accept that input, the bootstrap will fail at apply time.
- **Recommendation**: The proposal should clarify how SSH key material reaches the module. If `ssh_private_key` is needed, it should be declared with `sensitive = true` and the state-at-rest concern from Finding 1 applies with greater weight. This is a design gap that implementation will need to resolve, but it does not create an active security vulnerability in the proposal as written.

## Overall assessment

All five findings are LOW severity. The proposal follows standard Terraform security practices: sensitive variables are marked, credentials are excluded from source, kubeconfig generation is disabled for unattended runs, and module pinning is required by design rule. The public API surface and state encryption gaps are explicitly acknowledged tradeoffs appropriate for a Phase 1 bootstrap with a small operator team. No finding represents a concrete exploit path or data-integrity failure that would require proposal revision before implementation.
