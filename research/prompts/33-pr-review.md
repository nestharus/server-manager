# PR Review: Backend Cleanup

## Your role

You are a PR reviewer. Evaluate the backend cleanup changes for
correctness, completeness, and adherence to the proposal.

## Context

Read these files:
- `proposals/33-backend-cleanup.md` — the proposal
- `infra/main.tf` — modified to remove hardcoded backend values
- `infra/environments/staging/backend.tfbackend` — new file
- `infra/environments/production/backend.tfbackend` — new file
- `infra/tests/validate_terraform.sh` — updated with backend tests

## What to evaluate

1. **Correctness**: Does the implementation match the proposal?
2. **Completeness**: Are all proposed changes implemented?
3. **Security**: Are there any secrets or sensitive values exposed?
4. **Consistency**: Do the files follow consistent patterns?
5. **Decomposition**: Should this be split into multiple PRs?

## Output

Write your review to `risk/33-pr-review.md`.

If the review is clean:
```
REVIEW: CLEAN
No blocking issues found.
```

If there are issues, list them with severity and file:line references.
