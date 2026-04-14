# Risk Assessment: Shortcut — Backend Cleanup

## Your role

You are a shortcut risk assessor. Evaluate whether the proposal
introduces shortcuts — hacks, hardcoded values, duplicated logic,
workarounds, or symptom-masking fixes.

## Input

Read `proposals/33-backend-cleanup.md` for the proposal being assessed.

## What to evaluate

1. **Hardcoded values**: Does the proposal replace one set of hardcoded
   values with another?
2. **Duplicated logic**: Is any configuration duplicated across files
   unnecessarily?
3. **Workarounds**: Does the proposal work around a problem rather than
   solving it?
4. **TODO markers**: Are there placeholder values that should be real
   values?
5. **Pattern consistency**: Does the `.tfbackend` approach follow
   established Terraform/OpenTofu patterns?

## Output

Write your assessment to `risk/33-shortcut.md` with:
- Overall risk level: LOW, MEDIUM, or HIGH
- One paragraph per concern evaluated
- If MEDIUM or HIGH, specific recommendations to reduce risk
