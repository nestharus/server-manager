# Audit risk assessment — `services/discord/app/__main__.py`

YOU are the auditor. Assess audit risk for the proposal.

## Input files

- `proposals/25-discord-main.md` — the proposal to assess
- `research/25-discord-main.md` — research findings
- `research/25-discord-main-needs.md` — synthesis
- `services/discord/app/core/settings.py` — existing Settings
- `services/discord/app/core/bot.py` — existing HumilityBot

## Assessment criteria

Evaluate these audit concerns for the `__main__.py` entry point:

1. Token handling — is the bot token handled safely? No logging of
   secrets?
2. Error information leakage — do error messages expose sensitive data?
3. Signal handler safety — is the signal handler safe (no logging from
   signal context)?
4. Process lifecycle — is cleanup guaranteed (bot.close)?
5. Exit codes — are they meaningful and consistent?
6. Logging configuration — is it safe and appropriate?

## Output

Write your assessment to `risk/25-audit.md` with:
- Overall verdict: LOW, MEDIUM, or HIGH
- Each finding with severity and explanation
- Recommendations if not LOW

## Rules

- Do NOT modify any files other than `risk/25-audit.md`
- Do NOT write code
- Do NOT inspect the live Discord server
