# Phase 4: Risk Assessment — Scope Risk

## Objective
Assess the SCOPE RISK of the discord_cli.py proposal. Does the proposal try to do too much? Does it stay focused on the stated requirements?

## Input
Read these files:
- `proposals/05-discord-cli.md` — the proposal
- `research/05-discord-cli.md` — problem research
- `research/05-discord-cli-needs.md` — synthesized needs

## Assessment Criteria
1. **Feature creep** — Does the proposal add features beyond the stated requirements?
2. **Abstraction level** — Is the design appropriately simple for a single-file CLI tool?
3. **Dependency scope** — Does it introduce unnecessary dependencies?
4. **Future-proofing** — Does it over-engineer for hypothetical future needs?
5. **Single responsibility** — Does each subcommand do one thing well?

## Deliverable
Write your assessment to `risk/05-scope.md` with this structure:
```
# Scope Risk Assessment: discord_cli.py

## Risk Level: LOW | MEDIUM | HIGH

## Findings
[numbered list of findings with severity]

## Recommendation
[accept / revise with specific changes needed]
```

## Rules
- The tool is explicitly a lightweight CLI wrapper — complexity is a risk
- A single-file tool with 6 subcommands is a reasonable scope
- Flag anything that belongs in a different tool or service
