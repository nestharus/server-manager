# Risk Assessment: Shortcut Risk — Settings Module

## Task
Assess the SHORTCUT RISK of the proposal in `proposals/20-settings.md`.

## What to evaluate
1. Does the proposal take shortcuts that could cause problems?
2. Does it introduce technical debt?
3. Does it skip validation that should exist?
4. Does it defer decisions that should be made now?
5. Does it create patterns that will be hard to change?

## Inputs
- `proposals/20-settings.md` — the proposal
- `research/20-settings.md` — research findings
- `research/20-settings-needs.md` — synthesized needs
- `AGENTS.md` — project rules

## Deliverable
Write `risk/20-shortcut.md` with:
- Risk level: LOW, MEDIUM, or HIGH
- Findings (numbered, each with its own risk level)
- Recommendations if any finding is MEDIUM or HIGH

## Rules
- A shortcut is only risky if it has real consequences
- Deferring decisions is often correct at scaffold stage
- A finding is MEDIUM if the shortcut will cause bugs
- A finding is HIGH if the shortcut blocks progress
