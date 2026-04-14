# Scope risk assessment — `services/discord/app/__main__.py`

YOU are the scope assessor. Assess scope risk for the proposal.

## Input files

- `proposals/25-discord-main.md` — the proposal to assess
- `research/25-discord-main.md` — research findings
- `research/25-discord-main-needs.md` — synthesis

## Assessment criteria

Evaluate these scope concerns:

1. Is the proposal appropriately sized for a package entry point?
2. Does it include business logic that belongs elsewhere?
3. Is there any feature creep beyond what a `__main__.py` should do?
4. Are the error handling and shutdown logic proportionate?
5. Does it create unnecessary coupling to implementation details?
6. Is the anti-scope clear and sufficient?

## Output

Write your assessment to `risk/25-scope.md` with:
- Overall verdict: LOW, MEDIUM, or HIGH
- Each finding with severity and explanation
- Recommendations if not LOW

## Rules

- Do NOT modify any files other than `risk/25-scope.md`
- Do NOT write code
- Do NOT inspect the live Discord server
