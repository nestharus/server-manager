# Risk Assessment: Shortcut Risk — Bots No-Chunking Verification

## Your Role
You are a shortcut risk assessor. Read `proposals/08-bots-nochunk.md` and assess whether this proposal introduces shortcuts, workarounds, or technical debt.

## Context
The proposal is a verification-only pass: it confirms that `fetch_bots()` already satisfies the no-chunking goal. No code changes are proposed.

## Assessment Criteria
1. Does the proposal introduce any shortcuts or workarounds?
2. Does the proposal defer important work inappropriately?
3. Does the proposal create technical debt?
4. Is the "no changes needed" conclusion justified or is it hiding problems?

## Output
Write your assessment to `risk/08-shortcut.md` with:
- Risk level: LOW, MEDIUM, or HIGH
- Justification for the risk level
- Any findings worth noting
