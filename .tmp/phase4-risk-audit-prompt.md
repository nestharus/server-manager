# Phase 4: Risk Assessment — Audit Risk

## Objective
Assess the AUDIT RISK of the discord_cli.py proposal. Does the proposal introduce security vulnerabilities, data exposure, or operational risks?

## Input
Read these files:
- `proposals/05-discord-cli.md` — the proposal
- `research/05-discord-cli.md` — problem research
- `research/05-discord-cli-needs.md` — synthesized needs

## Assessment Criteria
1. **Token handling** — Is the bot token handled securely? Could it be leaked via logs, error messages, or stdout?
2. **Permission model** — Does the tool request only necessary intents/permissions?
3. **Data exposure** — Could message content or member data be inadvertently exposed?
4. **Input validation** — Are CLI inputs validated before being passed to discord.py?
5. **Error handling** — Do error messages avoid leaking sensitive information?
6. **Rate limiting** — Does the design account for Discord API rate limits?

## Deliverable
Write your assessment to `risk/05-audit.md` with this structure:
```
# Audit Risk Assessment: discord_cli.py

## Risk Level: LOW | MEDIUM | HIGH

## Findings
[numbered list of findings with severity]

## Recommendation
[accept / revise with specific changes needed]
```

## Rules
- Be thorough but fair — this is a local CLI tool, not a public-facing service
- Focus on realistic risks, not theoretical edge cases
- A tool that reads from .env and prints to stdout has a fundamentally small attack surface
