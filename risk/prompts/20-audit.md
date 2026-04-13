# Risk Assessment: Audit Risk — Settings Module

## Task
Assess the AUDIT RISK of the proposal in `proposals/20-settings.md`.

## What to evaluate
1. Does the proposal introduce security vulnerabilities?
2. Does it handle sensitive data appropriately?
3. Are there information disclosure risks?
4. Does it follow secure configuration practices?

## Inputs
- `proposals/20-settings.md` — the proposal
- `research/20-settings.md` — research findings
- `research/20-settings-needs.md` — synthesized needs
- `AGENTS.md` — project rules

## Deliverable
Write `risk/20-audit.md` with:
- Risk level: LOW, MEDIUM, or HIGH
- Findings (numbered, each with its own risk level)
- Recommendations if any finding is MEDIUM or HIGH

## Rules
- Be thorough but proportionate to the scaffold stage
- A finding is MEDIUM if it could cause harm in production
- A finding is HIGH if it could cause harm immediately
