# Risk Audit — Vultr Object Storage Bug Fix

Date: 2026-04-15
Proposal: [plans/proposals/vultr-object-storage-fix.md](../proposals/vultr-object-storage-fix.md)

## Category: Safety / Security / Data Integrity

### 1. Security surface

The fix changes a provider version constraint from `~> 2.30` to `~> 2.31`. This is a
minor-version bump within the same provider (`vultr/vultr`). No new providers, no new
authentication paths, no new secret handling.

The `vultr_object_storage_bucket` resource that this fix unblocks was already present in
the codebase — the fix does not introduce it, it makes it resolvable. The resource
creates a bucket with versioning enabled, which is a security-positive configuration
(versioning protects against accidental state file deletion or overwrites).

No credentials are added. The existing `sensitive = true` markings on `s3_access_key`
and `s3_secret_key` outputs are unchanged.

**Risk: NONE**

### 2. Data integrity

The `enable_versioning = true` flag on the bucket resource preserves prior versions of
the tfstate file, protecting against corruption or accidental overwrites. This is
unchanged by the fix.

The three `backend.tfbackend` files use a hardcoded `bucket = "humility-tfstate"` string,
not a Terraform output reference. They are unaffected by any change to the bucket
resource or its outputs.

The bootstrap module uses local state (`terraform { }` with no backend block), so the
version bump cannot affect any existing remote state.

**Risk: NONE**

### 3. Provider upgrade risk

The `~>` operator allows only patch-level updates within the minor version. Moving from
`~> 2.30` (allows 2.30.x) to `~> 2.31` (allows 2.31.x) is a controlled semver window.
The bootstrap module uses only two resources:

- `vultr_object_storage` — stable since v2.25, unchanged in v2.31
- `vultr_object_storage_bucket` — new in v2.31, schema matches code exactly

No deprecated attributes, no breaking changes to existing resources.

**Risk: LOW**

### 4. Cross-module version divergence

The environment roots (`dev`, `staging`, `production`) retain `~> 2.30`. The bootstrap
module moves to `~> 2.31`. This is safe because:

- Bootstrap and environments are completely separate root modules with independent state
- They share no provider configuration at runtime
- The environments do not use `vultr_object_storage_bucket`

**Risk: NONE**

## Verdict: LOW

The fix is a one-line semver constraint bump that enables an already-written resource
block. No new security surface, no credential changes, no data-integrity risk. The only
non-zero risk is the inherent risk of any provider version bump, which is mitigated by
the `~>` constraint limiting to patch versions within 2.31.x.
