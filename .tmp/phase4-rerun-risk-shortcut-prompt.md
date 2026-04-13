# Phase 4 (Re-run): Risk Assessment — Shortcut Risk

## Context
The proposal was revised after the initial risk gate found a MEDIUM shortcut risk (no gateway connection timeout). The proposal now includes `asyncio.wait_for()` with a 30-second default timeout and a `timeout_error` error category. Per process rules, all three risk assessments must be re-run against the revised proposal.

## Objective
Assess the SHORTCUT RISK of the revised discord_cli.py proposal. Does the proposal introduce shortcuts that will cause problems later?

## Input
Read these files:
- `proposals/05-discord-cli.md` — the revised proposal
- `research/05-discord-cli.md` — problem research
- `research/05-discord-cli-needs.md` — synthesized needs

## Assessment Criteria
1. **Technical debt** — Does the design take shortcuts that will need to be undone later?
2. **Error handling shortcuts** — Does it silently swallow errors or ignore edge cases that matter?
3. **Data format shortcuts** — Is the JSON output format well-structured, or will it need rework?
4. **Gateway lifecycle** — Does the one-shot pattern handle connection lifecycle properly, including the new timeout?
5. **Missing validation** — Are there inputs that should be validated but aren't?
6. **Hardcoded assumptions** — Are there assumptions baked in that will break in foreseeable scenarios?

## Deliverable
Write your assessment to `risk/05-shortcut.md` with this structure:
```
# Shortcut Risk Assessment: discord_cli.py

## Risk Level: LOW | MEDIUM | HIGH

## Findings
[numbered list of findings with severity]

## Recommendation
[accept / revise with specific changes needed]
```

## Rules
- This is a local CLI tool, not production infrastructure — calibrate accordingly
- Some shortcuts are acceptable for a tool of this scope
- Flag shortcuts that would make the tool unreliable or its output untrustworthy
- This is a re-run after proposal revision — the previous MEDIUM finding (no gateway timeout) has been addressed in the revised proposal. Assess the proposal as it stands now.
