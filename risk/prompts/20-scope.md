# Risk Assessment: Scope Risk — Settings Module

## Task
Assess the SCOPE RISK of the proposal in `proposals/20-settings.md`.

## What to evaluate
1. Does the proposal stay within its stated scope?
2. Does it avoid over-engineering for the scaffold stage?
3. Does it introduce unnecessary complexity?
4. Does it create future coupling or constraints?
5. Is the anti-scope reasonable and complete?

## Inputs
- `proposals/20-settings.md` — the proposal
- `research/20-settings.md` — research findings
- `research/20-settings-needs.md` — synthesized needs
- `AGENTS.md` — project rules

## Deliverable
Write `risk/20-scope.md` with:
- Risk level: LOW, MEDIUM, or HIGH
- Findings (numbered, each with its own risk level)
- Recommendations if any finding is MEDIUM or HIGH

## Rules
- Scope creep includes both too much AND too little
- A finding is MEDIUM if it would require rework later
- A finding is HIGH if it blocks other work
