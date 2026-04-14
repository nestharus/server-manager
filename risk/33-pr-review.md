# PR Review: Backend Cleanup (NN33)

Date: 2026-04-14

## Files reviewed

- `infra/main.tf` (modified)
- `infra/environments/staging/backend.tfbackend` (new)
- `infra/environments/production/backend.tfbackend` (new)
- `infra/tests/validate_terraform.sh` (modified)
- `.gitignore` (modified)

## Issues

### MEDIUM — `force_path_style = true` removed from `infra/main.tf`

**File:** `infra/main.tf:14-21`

The proposal lists `force_path_style = true` as a setting that must
remain in the backend block (proposal lines 46, 116). The
implementation removes it along with the per-environment values.

Hetzner Object Storage requires path-style addressing. Without
`force_path_style = true`, the S3 client defaults to virtual-hosted
bucket URLs (`bucket.endpoint`), which Hetzner does not support.
Running `tofu init` against Hetzner will fail or resolve to the wrong
host.

**Proposed fix:** Add `force_path_style = true` back to the backend
block in `main.tf`, and add a corresponding assertion in
`validate_terraform.sh`.

### LOW — Bucket name and key prefix differ from proposal and prior code

**Files:** `infra/environments/staging/backend.tfbackend:3`,
`infra/environments/production/backend.tfbackend:3`

| Value  | Original `main.tf`           | Proposal                     | Implementation             |
|--------|------------------------------|------------------------------|----------------------------|
| bucket | `humility-terraform-state`   | `humility-terraform-state`   | `server-manager-tfstate`   |
| key    | `humility/ENV/terraform.tfstate` | `humility/ENV/terraform.tfstate` | `infra/ENV/terraform.tfstate` |

The bucket was renamed from `humility-terraform-state` to
`server-manager-tfstate` and the key prefix changed from `humility/`
to `infra/`. If this is intentional (the actual bucket is named
`server-manager-tfstate`), this is fine. If the proposal values
reflect the real infrastructure, this will point `tofu init` at a
non-existent bucket.

**Action needed:** Confirm which bucket name and key prefix are
correct for the live infrastructure.

### LOW — Test coverage gap for `force_path_style`

**File:** `infra/tests/validate_terraform.sh`

If `force_path_style` is restored to `main.tf`, the test should
assert its presence, matching the pattern used for the other `skip_*`
flags.

## Non-blocking observations

- `.gitignore` adds `infra/.terraform/` — good hygiene, prevents
  committing init state. Not in the proposal but sensible.
- `.tfbackend` files include helpful usage comments not in the
  proposal. No objection.
- Comment wording in `main.tf` differs slightly from proposal
  ("shared" vs "environment-independent"). Equivalent meaning, no
  issue.
- Test additions are thorough: backend block extraction via awk,
  absence checks for removed fields, presence checks for retained
  fields, cross-file key uniqueness validation, and secret scanning.
  Well structured.

## Validation

```
$ bash infra/tests/validate_terraform.sh
[PASS] ... (40 checks)
[PASS] tofu validate succeeds in infra/
Validation passed.
```

All 40 checks pass. `tofu validate` succeeds.

## Verdict

```
REVIEW: ISSUES FOUND
1 MEDIUM issue (force_path_style removal), 2 LOW issues.
Fix the MEDIUM before merge; confirm the LOW bucket/key question.
```
