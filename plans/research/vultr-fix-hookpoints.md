# Hookpoint Research — Vultr Object Storage Bug Fix

Date: 2026-04-15
Proposal: [plans/proposals/vultr-object-storage-fix.md](../proposals/vultr-object-storage-fix.md)

## Purpose

Map all existing code that this fix touches or depends on, to verify there are no
unaccounted-for downstream effects.

## Primary target: `infra/bootstrap/state-backend/main.tf`

### Provider block (line 14-19)

```hcl
required_providers {
  vultr = {
    source  = "vultr/vultr"
    version = "~> 2.30"          # ← line 17, changed to "~> 2.31"
  }
}
```

**Dependents of this constraint:**
- `infra/bootstrap/state-backend/.terraform.lock.hcl` — generated from this constraint
  via `tofu init`. Must be regenerated after the version change.
- No other root module shares this provider block. The environment roots
  (`dev`, `staging`, `production`) each declare their own independent `required_providers`
  with `~> 2.30`, which is correct for their resource usage.

### `vultr_object_storage` resource (lines 46-50)

```hcl
resource "vultr_object_storage" "state" {
  cluster_id = var.object_storage_cluster_id
  tier_id    = var.object_storage_tier_id
  label      = var.object_storage_label
}
```

**Not changed by this fix.** This resource exists in v2.30 and continues to exist in
v2.31 with the same schema. Its exported attributes (`s3_hostname`, `s3_access_key`,
`s3_secret_key`) are consumed by:

- `vultr_object_storage_bucket.tfstate` (line 53) — via `.id`
- Output `s3_hostname` (line 63) — via `.s3_hostname`
- Output `s3_access_key` (line 67) — via `.s3_access_key`
- Output `s3_secret_key` (line 71) — via `.s3_secret_key`

All internal to this module. No cross-module references.

### `vultr_object_storage_bucket` resource (lines 52-56)

```hcl
resource "vultr_object_storage_bucket" "tfstate" {
  object_storage_id = vultr_object_storage.state.id
  name              = var.bucket_name
  enable_versioning = true
}
```

**Not changed by this fix** — already correct, just needs the provider version that
includes this resource type. Its exported attribute `.name` is consumed by:

- Output `bucket_name` (line 59) — via `.name`

No other file references `vultr_object_storage_bucket`.

### Outputs (lines 58-74)

| Output | Source | Consumed by |
|--------|--------|-------------|
| `bucket_name` | `vultr_object_storage_bucket.tfstate.name` | Operator reference only (not used in other Terraform code) |
| `s3_hostname` | `vultr_object_storage.state.s3_hostname` | Operator reference only |
| `s3_access_key` | `vultr_object_storage.state.s3_access_key` | Operator reference only (sensitive) |
| `s3_secret_key` | `vultr_object_storage.state.s3_secret_key` | Operator reference only (sensitive) |

None of these outputs are consumed by other Terraform modules via `terraform_remote_state`
or `data` sources. The bootstrap module uses local state (no backend block), so these
outputs exist for operators to copy into `backend.tfbackend` files manually.

## `backend.tfbackend` files

Three files, all with identical structure differing only in the `key` path:

| File | `bucket` value | `key` value |
|------|---------------|-------------|
| `infra/environments/dev/backend.tfbackend` | `"humility-tfstate"` | `"infra/dev/terraform.tfstate"` |
| `infra/environments/staging/backend.tfbackend` | `"humility-tfstate"` | `"infra/staging/terraform.tfstate"` |
| `infra/environments/production/backend.tfbackend` | `"humility-tfstate"` | `"infra/production/terraform.tfstate"` |

**No changes needed.** These files use hardcoded string values, not Terraform output
references. The `bucket` value `"humility-tfstate"` matches the `bucket_name` variable
default but is not dynamically linked to it.

## Test file: `infra/tests/validate_platform_bootstrap.sh`

### Assertions affected by this fix

| Line(s) | Assertion | Impact |
|---------|-----------|--------|
| 198-199 | `resource\s+"vultr_object_storage_bucket"` exists in bootstrap `main.tf` | **Not changed** — resource block stays |
| 204-205 | `version\s*=\s*"~>\s*2\.30"` in bootstrap `main.tf` | **Must update** to `2\.31` |

### Assertions NOT affected

| Line(s) | Assertion | Why unaffected |
|---------|-----------|----------------|
| 195-196 | `vultr_object_storage` resource exists | Resource unchanged |
| 201-202 | `enable_versioning = true` | Attribute unchanged |
| 207-208 | `required_version >= 1.8.0` | OpenTofu version unchanged |
| 250 | `version\s*=\s*"~>\s*2\.30"` in `environments/dev/main.tf` | Environment keeps `~> 2.30` |

### Structural validation (lines 140-187)

The test runs `tofu validate` on the bootstrap module (line 141: `"bootstrap/state-backend"`).
After the fix, this validation will succeed because the provider version will resolve
`vultr_object_storage_bucket`. Before the fix (and before the provider is published),
this validation fails — which is the bug this fix addresses.

## `.terraform.lock.hcl`

Generated file. Must be regenerated via `tofu init -upgrade` after the version constraint
change. Contains provider checksums and version pins. No manual editing.

## Environment root modules

| File | Has `~> 2.30`? | Needs change? | Why |
|------|---------------|---------------|-----|
| `infra/environments/dev/main.tf` | Yes | No | Does not use `vultr_object_storage_bucket` |
| `infra/environments/staging/main.tf` | Yes | No | Does not use `vultr_object_storage_bucket` |
| `infra/environments/production/main.tf` | Yes | No | Does not use `vultr_object_storage_bucket` |

## `infra/README.md`

Contains `~> 2.30` in documentation. Not part of this fix — the README documents the
current environment configuration, not the bootstrap module. If desired, a follow-up
could update the README, but it is not required for correctness.

## Dependency graph summary

```
Fix: version "~> 2.30" → "~> 2.31" (main.tf:17)
 ├── .terraform.lock.hcl     → regenerate (generated file)
 ├── test assertion (line 204) → update version string
 └── all other files          → no changes needed

vultr_object_storage_bucket.tfstate (main.tf:52-56)
 ├── depends on: vultr_object_storage.state.id (main.tf:46)
 └── consumed by: output "bucket_name" (main.tf:58-60)
     └── consumed by: nothing (operator reference only)

backend.tfbackend files
 └── "humility-tfstate" hardcoded → no dependency on any resource or output
```

## Verdict: LOW

All hookpoints are mapped. The fix touches exactly three files with well-understood
dependencies. No hidden consumers, no cross-module references, no downstream breakage
paths. The dependency graph is shallow and fully contained within the bootstrap module.
