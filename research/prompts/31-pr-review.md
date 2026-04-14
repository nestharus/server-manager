# PR Review: Phase 1 Foundation — Terraform Infrastructure Files

## Hard rules

**YOU are the PR reviewer. YOU do the review yourself.
Do not launch, spawn, dispatch, or report on any other agent.**

Your deliverable is review feedback written to stdout.

## What you're reviewing

Review the diff on the current branch (`feat/phase1-foundation`)
against `main`. The changes should include:

1. `infra/main.tf` — Root Terraform entrypoint
2. `infra/variables.tf` — Variable declarations
3. `infra/cluster.tf` — kube-hetzner module wiring
4. `infra/environments/staging/terraform.tfvars` — Staging values
5. `infra/environments/production/terraform.tfvars` — Production values
6. `infra/tests/validate_terraform.sh` — Validation script

## Review criteria

### Multi-concern check

1. **Security**: Are sensitive values properly handled? No hardcoded
   secrets? State backend security?
2. **Correctness**: Do the files form a valid Terraform configuration?
   Are provider/module references correct?
3. **Consistency**: Do staging and production tfvars share the same
   variable surface? Are naming conventions consistent?
4. **Scope**: Do the files stay within the Phase 1 Foundation scope?
   No Flux CD, Kong, secrets, or Buildkite configuration?
5. **Idiomatic**: Is the HCL idiomatic? Proper use of variables,
   descriptions, types, defaults?

### Justification check

For each file, verify:
- Every variable has a description
- Sensitive variables are marked sensitive
- Module sources are version-pinned
- Comments explain non-obvious architectural choices

## Output

If the review is clean, output:
```
REVIEW: CLEAN
No blocking issues found.
```

If issues exist, list them with severity and file:line references.
