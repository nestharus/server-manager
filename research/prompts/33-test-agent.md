# Test Agent: Backend Cleanup Validation

## Your role

You are a test-writing agent. You ONLY write tests. You do NOT modify
`infra/main.tf` or create `.tfbackend` files.

## Context

Read the proposal at `proposals/33-backend-cleanup.md` for the
contract being tested. The proposal says:

1. `infra/main.tf` backend block should NOT contain `bucket`, `key`, or
   `endpoints` as hardcoded values
2. `infra/main.tf` backend block SHOULD contain `region` and skip flags
3. Per-environment `.tfbackend` files should exist at:
   - `infra/environments/staging/backend.tfbackend`
   - `infra/environments/production/backend.tfbackend`
4. Each `.tfbackend` file should contain `bucket`, `key`, and `endpoints`
5. The `key` values should differ between staging and production

## Deliverable

Add test cases to the existing `infra/tests/validate_terraform.sh`
that verify the backend cleanup contract:

1. Test that `main.tf` does NOT contain a hardcoded `bucket =` line
   (other than a comment)
2. Test that `main.tf` does NOT contain a hardcoded `key =` line
   (other than a comment)
3. Test that `main.tf` DOES contain `region` in the backend block
4. Test that staging `.tfbackend` file exists and contains required keys
5. Test that production `.tfbackend` file exists and contains required keys
6. Test that staging and production use different state file keys

## Anti-goals

- Do NOT modify `infra/main.tf`
- Do NOT create `.tfbackend` files
- Do NOT read or depend on implementation code

## Output

Edit `infra/tests/validate_terraform.sh` to add the new test functions.
