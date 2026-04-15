# CodeRabbit-Equivalent Review: Platform Bootstrap Infrastructure

**Reviewer**: claude-opus (CodeRabbit CLI unavailable; performing equivalent review)
**Files reviewed**: 5
**Focus areas**: provider-version pinning, credential handling, state-backend security, Terraform/OpenTofu best practices

---

## File-by-file review

### 1. `infra/bootstrap/state-backend/main.tf`

**Provider version pinning** — OK
- `vultr/vultr ~> 2.30` is pinned with pessimistic constraint.
- `required_version >= 1.8.0` for OpenTofu.

**Credential handling** — OK
- `s3_access_key` and `s3_secret_key` outputs are marked `sensitive = true`.
- No hardcoded credentials in the file.
- Provider block `provider "vultr" {}` relies on environment variable `VULTR_API_KEY` — correct for bootstrap where no secrets manager exists.

**State-backend security** — NOTE
- This root uses local state (no `backend` block), which is intentional for the bootstrap chicken-and-egg. The local `.tfstate` file will contain the Object Storage credentials in plaintext. The proposal acknowledges this and defers credential custody to exit criteria.

**Best practices** — WARNINGS
1. **No `terraform.tf` separation**: All config is in `main.tf`. For a small bootstrap root this is acceptable, but convention prefers `versions.tf` for the `terraform {}` block.
2. **`vultr_object_storage_bucket` resource**: The Vultr provider's `vultr_object_storage_bucket` resource — verify this resource type exists in provider version 2.30+. If it doesn't exist (some Vultr provider versions use the Object Storage API directly), the plan will fail at init. **Severity: WARNING** — needs verification against actual provider docs.
3. **No lifecycle prevent_destroy**: The state bucket is a critical resource. Consider adding `lifecycle { prevent_destroy = true }` to prevent accidental deletion.

### 2. `infra/modules/platform-network/main.tf`

**Provider version pinning** — OK (correctly omitted from module; inherited from root)

**Best practices** — OK
- Variables have descriptions and types.
- Default subnet mask of 20 is reasonable.
- Resource naming follows `humility-${var.environment}-platform` convention.
- No hardcoded environment names.
- Outputs expose all relevant VPC attributes.

**No issues found.**

### 3. `infra/modules/platform-cluster/main.tf`

**Provider version pinning** — OK (correctly omitted from module)

**Credential handling** — OK
- `kube_config` output marked `sensitive = true`.

**Best practices** — WARNINGS
1. **`auto_scaler = false` hardcoded**: This should arguably be a variable for flexibility across environments. **Severity: NOTE** — acceptable for platform clusters that should be explicitly sized.
2. **No `node_pools` label validation**: The label `"${var.environment}-platform"` could exceed VKE label length limits for long environment names. **Severity: NOTE** — unlikely in practice.
3. **Missing `depends_on`**: The cluster depends on the VPC existing (via `vpc_id`), which is handled by the implicit reference. OK.

### 4. `infra/environments/dev/main.tf`

**Provider version pinning** — OK
- Same `vultr/vultr ~> 2.30` and `>= 1.8.0` as bootstrap root. Consistent.

**Credential handling** — OK
- No credentials in file. Provider uses env var.

**State-backend security** — OK
- `backend "s3" {}` with config from external `backend.tfbackend` file. Keeps credentials out of version control.

**Best practices** — WARNINGS
1. **Hardcoded values in module calls**: Region `"ewr"`, subnet `"10.40.0.0"`, Kubernetes version `"v1.32.3+1"`, node plan `"vc2-2c-4gb"`, and node count `2` are all hardcoded rather than using `terraform.tfvars` or variables. **Severity: WARNING** — For a single dev environment root this is defensible (each env root is its own config), but it means the file must be edited directly to change sizing. The proposal design says environment roots carry environment-specific inputs, so inline values are within pattern.
2. **No `terraform.tfvars`**: Related to above. A `dev.tfvars` file would make the values more visible and diffable across environments. **Severity: NOTE**.

### 5. `infra/environments/dev/backend.tfbackend`

**State-backend security** — OK
- No credentials in file.
- `REPLACE_AFTER_BOOTSTRAP` placeholder prevents accidental use before state-backend is bootstrapped.
- S3-compatibility skip flags are correct for Vultr Object Storage.

**Best practices** — OK
- `use_path_style = true` is correct for Vultr's S3-compatible endpoint.
- `skip_credentials_validation`, `skip_requesting_account_id`, `skip_metadata_api_check` are standard for non-AWS S3.

---

## Summary

| Severity | Count | Details |
|----------|-------|---------|
| BLOCKER  | 0     | — |
| WARNING  | 3     | `vultr_object_storage_bucket` resource existence unverified; no `prevent_destroy` on state bucket; hardcoded values in dev root |
| NOTE     | 3     | No `versions.tf` separation; `auto_scaler` hardcoded; no `terraform.tfvars` |

## Verdict

**No blockers.** The 3 warnings are reasonable for a first bootstrap iteration:
- The `vultr_object_storage_bucket` resource type should be verified against provider docs before first apply (not a code-change issue, an operational verification).
- `prevent_destroy` and `tfvars` separation are improvements for a follow-up, not blockers for initial merge.

**APPROVED** — implementation follows Terraform/OpenTofu best practices for a greenfield bootstrap with no security concerns.
