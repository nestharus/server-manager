# Risk Assessment: Audit — Backend Cleanup

## Your role

You are a risk auditor. Assess whether the proposal introduces safety,
security, privacy, or data-integrity risks.

## Input

Read `proposals/33-backend-cleanup.md` for the proposal being assessed.

## What to evaluate

1. **Security**: Could `.tfbackend` files leak secrets? Are credentials
   properly handled via env vars, not in files?
2. **Data integrity**: Could the backend reconfiguration cause state
   file loss or corruption?
3. **Rate limits / API impact**: Does this change affect any API calls?
4. **Destructive operations**: Could `tofu init` with new backend config
   destroy existing state?
5. **GDPR / privacy**: Any personal data implications?

## Output

Write your assessment to `risk/33-audit.md` with:
- Overall risk level: LOW, MEDIUM, or HIGH
- One paragraph per concern evaluated
- If MEDIUM or HIGH, specific recommendations to reduce risk

Keep it concise. This is a backend config refactor, not a new feature.
