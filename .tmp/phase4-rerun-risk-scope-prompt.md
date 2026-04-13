# Phase 4 (Re-run): Risk Assessment — Scope Risk

## Context
The proposal was revised after the initial risk gate found a MEDIUM shortcut risk (no gateway connection timeout). The proposal now includes `asyncio.wait_for()` with a 30-second default timeout and a `timeout_error` error category. Per process rules, all three risk assessments must be re-run against the revised proposal.

## Objective
Assess the SCOPE RISK of the revised discord_cli.py proposal. Does the proposal try to do too much? Does it stay focused on the stated requirements?

## Input
Read these files:
- `proposals/05-discord-cli.md` — the revised proposal
- `research/05-discord-cli.md` — problem research
- `research/05-discord-cli-needs.md` — synthesized needs

## Assessment Criteria
1. **Feature creep** — Does the proposal add features beyond the stated requirements?
2. **Abstraction level** — Is the design appropriately simple for a single-file CLI tool?
3. **Dependency scope** — Does it introduce unnecessary dependencies?
4. **Future-proofing** — Does it over-engineer for hypothetical future needs?
5. **Single responsibility** — Does each subcommand do one thing well?
6. **Timeout addition** — Does the added gateway timeout stay within scope or introduce unnecessary complexity?

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
- This is a re-run after proposal revision — assess the proposal as it stands now
