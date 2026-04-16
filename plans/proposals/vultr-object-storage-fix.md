# Vultr Object Storage Bucket — Bug Fix Proposal

Date: 2026-04-15
Research: [plans/research/vultr-object-storage-fix.md](../research/vultr-object-storage-fix.md)

## Problem

`infra/bootstrap/state-backend/main.tf` declares a `vultr_object_storage_bucket` resource
(lines 52-56) that does not exist in Vultr Terraform provider v2.30.x. Running `tofu init`
or `tofu plan` fails with `"vultr_object_storage_bucket" is not a valid resource type`.

The `bucket_name` output (lines 58-60) references this non-existent resource, compounding
the failure.

## Recommended fix: Option A — bump provider version constraint

The `vultr_object_storage_bucket` resource is already merged to the provider's `master`
branch (commit d64fdb9, March 30, 2026) and will ship in the next release (expected
v2.31.0). The resource schema matches the code in `main.tf` exactly. The fix is a
one-line version constraint change.

### Change 1: `infra/bootstrap/state-backend/main.tf` line 17

```diff
-      version = "~> 2.30"
+      version = "~> 2.31"
```

This is the only code change. The `vultr_object_storage_bucket` resource block (lines
52-56) and all outputs (lines 58-74) are correct as written and require no modification.

### Change 2: `infra/bootstrap/state-backend/.terraform.lock.hcl`

After updating the version constraint, regenerate the lock file:

```sh
cd infra/bootstrap/state-backend
tofu init -upgrade
```

This is a generated file, not a manual edit.

### Change 3: `infra/tests/validate_platform_bootstrap.sh` line 204

```diff
-assert_grep 'version\s*=\s*"~>\s*2\.30"' "$BS" \
-  "provider version constraint ~> 2.30"
+assert_grep 'version\s*=\s*"~>\s*2\.31"' "$BS" \
+  "provider version constraint ~> 2.31"
```

The test asserts the exact version string. It must match the updated constraint.

## Does `vultr_object_storage` need changes?

No. The `vultr_object_storage.state` resource (lines 46-50) uses `cluster_id`, `tier_id`,
and `label` — all valid attributes in v2.30+ and unchanged in the upcoming release. Its
exported attributes (`s3_hostname`, `s3_access_key`, `s3_secret_key`) remain the same.

## Do `backend.tfbackend` files need changes?

No. The three backend config files (`infra/environments/{dev,staging,production}/backend.tfbackend`)
reference `bucket = "humility-tfstate"` — a literal string matching the `bucket_name`
variable default. They do not reference the `vultr_object_storage_bucket` resource or
any of its outputs. The `bucket_name` output exists for operator convenience; the backend
configs use a hardcoded value. No changes needed.

## Scope summary

| File | Change | Lines affected |
|------|--------|----------------|
| `infra/bootstrap/state-backend/main.tf` | Version constraint `~> 2.30` → `~> 2.31` | 1 line (line 17) |
| `infra/bootstrap/state-backend/.terraform.lock.hcl` | Regenerate via `tofu init -upgrade` | Generated |
| `infra/tests/validate_platform_bootstrap.sh` | Version assertion `2\.30` → `2\.31` | 2 lines (lines 204-205) |

Total: 1 line of production code + 1 test assertion update + 1 lock file regeneration.

## Precondition

This fix can only be applied after the Vultr provider publishes a release containing the
`vultr_object_storage_bucket` resource (expected v2.31.0). Until then, `tofu init -upgrade`
will fail because no published version satisfies `~> 2.31`.

If the fix must land before that release, Option B from the research (AWS provider with
custom S3 endpoint) is the fallback. That approach is significantly more invasive and
should be treated as a separate proposal if needed.
