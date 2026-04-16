# Risk Shortcut — Vultr Object Storage Bug Fix

Date: 2026-04-15
Proposal: [plans/proposals/vultr-object-storage-fix.md](../proposals/vultr-object-storage-fix.md)

## Category: Shortcuts and Workarounds

### 1. Is this a proper fix or a workaround?

This is a proper fix. The root cause is that the code was written against a provider
resource (`vultr_object_storage_bucket`) that had not yet been released. The research
confirms the resource is merged to the provider's `master` branch (commit d64fdb9,
March 30, 2026) and the schema matches the code exactly.

Bumping the version constraint to `~> 2.31` makes the provider resolve to the release
that includes this resource. This is the canonical way to adopt a new resource — not a
workaround, not a hack.

**Risk: LOW** — this is the intended fix path.

### 2. Does it defer necessary work?

No. After the version bump:

- The `vultr_object_storage_bucket` resource will be valid and plannable
- The `bucket_name` output will resolve correctly
- `tofu init` and `tofu plan` will succeed
- The bootstrap module will work as originally designed

There is no follow-up work implied by this fix.

**Risk: LOW** — no deferred work.

### 3. Does it bypass safety mechanisms?

No. The fix:

- Does not disable any Terraform/OpenTofu validation
- Does not use `-upgrade` flags in production (only for lock file regeneration during
  development)
- Does not add `skip_*` flags or override checks
- Does not suppress errors or warnings
- Preserves the `~>` pessimistic constraint operator (prevents major version drift)
- Preserves `enable_versioning = true` on the bucket
- Preserves `sensitive = true` on credential outputs

**Risk: LOW** — no safety mechanisms bypassed.

### 4. Alternative approaches considered

The research evaluated four options:

| Option | Approach | Why not chosen |
|--------|----------|---------------|
| A (chosen) | Version bump | Proper fix, minimal change |
| B | AWS provider with custom S3 endpoint | 400 MB dependency for one resource; workaround |
| C | local-exec shell script | Not idempotent; bucket not in state; workaround |
| D | Remove bucket from Terraform | Breaks single-command bootstrap design |

Options B, C, and D are workarounds of increasing severity. The proposal correctly
chose Option A — the only non-workaround option.

**Risk: LOW** — best option selected; alternatives are documented but appropriately rejected.

### 5. Precondition dependency

The proposal correctly notes a precondition: the fix requires Vultr provider v2.31.0 to
be published. This is not a shortcut — it is an explicit, documented dependency. The
proposal also identifies Option B as a fallback if the release timeline slips.

**Risk: LOW** — dependency is acknowledged and a fallback exists.

## Verdict: LOW

The fix takes no shortcuts. It is the canonical, minimal, proper resolution to a version
mismatch. Alternative approaches were evaluated and the least-workaround option was
chosen. No safety mechanisms are bypassed and no work is deferred.
