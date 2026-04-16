# Risk Scope — Vultr Object Storage Bug Fix

Date: 2026-04-15
Proposal: [plans/proposals/vultr-object-storage-fix.md](../proposals/vultr-object-storage-fix.md)

## Category: Scope Appropriateness

### 1. Problem-to-fix ratio

The problem: `vultr_object_storage_bucket` is not a valid resource in provider v2.30.x,
so `tofu init` / `tofu plan` fails on the bootstrap module.

The fix: change one version constraint (`~> 2.30` → `~> 2.31`), regenerate the lock
file, update one test assertion.

This is a 1:1 mapping between problem and fix. The version bump is the minimum change
that resolves the failure. No logic changes, no restructuring, no new abstractions.

**Risk: LOW** — fix is minimally scoped to the root cause.

### 2. File count

| File | Nature of change |
|------|-----------------|
| `infra/bootstrap/state-backend/main.tf` | 1 line: version string |
| `infra/bootstrap/state-backend/.terraform.lock.hcl` | Regenerated (generated file) |
| `infra/tests/validate_platform_bootstrap.sh` | 2 lines: version assertion string |

Three files touched, one of which is auto-generated. The two manual changes total 3
lines of diff.

**Risk: LOW** — minimal blast radius.

### 3. Unintended scope expansion

Verified that the fix does NOT touch:

- Environment root modules (`dev`, `staging`, `production`) — their `~> 2.30` constraint
  is independent and correct (they don't use `vultr_object_storage_bucket`)
- `backend.tfbackend` files — they use hardcoded bucket names, not resource references
- Module files (`platform-network`, `platform-cluster`) — completely unrelated
- Any outputs consumed by downstream modules — `s3_hostname`, `s3_access_key`,
  `s3_secret_key` come from `vultr_object_storage.state`, not the bucket resource
- The test assertion at line 250 (`environments/dev/main.tf` version check) — correctly
  left unchanged since environments keep `~> 2.30`

**Risk: LOW** — no scope creep into unrelated files.

### 4. Missing scope

The proposal's test update covers the bootstrap version assertion (line 204) but does
not need to change the environments/dev version assertion (line 250) because the
environments correctly stay on `~> 2.30`. This is correct scoping.

The `vultr_object_storage_bucket` resource block (lines 52-56) and `bucket_name` output
(lines 58-60) are confirmed to match the upcoming provider schema exactly. No changes
needed there.

**Risk: LOW** — nothing missing from the fix scope.

## Verdict: LOW

The fix is appropriately scoped: one version constraint change plus its mechanical
consequences (lock file regeneration, test assertion update). No scope creep, no
missing items, minimal blast radius.
