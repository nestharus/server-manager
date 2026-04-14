# Shortcut risk assessment — `services/discord/app/__main__.py`

YOU are the shortcut assessor. Assess shortcut risk for the proposal.

## Input files

- `proposals/25-discord-main.md` — the proposal to assess
- `research/25-discord-main.md` — research findings
- `research/25-discord-main-needs.md` — synthesis

## Assessment criteria

Evaluate these shortcut concerns:

1. Does the proposal introduce any compatibility shims or fallbacks?
2. Does it hardcode values that should be configurable?
3. Does it duplicate logic that exists elsewhere?
4. Does it skip proper error handling in favor of catch-all?
5. Does it defer important decisions as TODOs instead of resolving them?
6. Does it use `bot.run()` when `bot.start()` is more appropriate?
7. Does it introduce any backwards-compatibility patterns?

## Output

Write your assessment to `risk/25-shortcut.md` with:
- Overall verdict: LOW, MEDIUM, or HIGH
- Each finding with severity and explanation
- Recommendations if not LOW

## Rules

- Do NOT modify any files other than `risk/25-shortcut.md`
- Do NOT write code
- Do NOT inspect the live Discord server
