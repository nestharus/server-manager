# Hookpoint research — Discord service `app/__main__.py`

YOU are the researcher. YOU do the research yourself. Do NOT delegate.

## Task

Map the proposal for `services/discord/app/__main__.py` to the existing
codebase. Find what exists, what can be reused, and what is new.

## Input files

- `proposals/25-discord-main.md` — the validated proposal
- `services/discord/app/core/settings.py` — Settings class
- `services/discord/app/core/bot.py` — HumilityBot class
- `services/discord/app/__init__.py` — package marker

## Questions to answer

1. Does `app/__main__.py` already exist? If so, what does it contain?
2. Does the existing `HumilityBot` class need any changes to support
   the proposed entry point? (e.g., does it have `close()` method?)
3. Does the existing `Settings` class support the proposed
   construction pattern?
4. Is `discord.utils.setup_logging` available in the installed
   discord.py version?
5. Are there any existing test files that would need updating?
6. What is the test runner configuration for this service?

## Deliverables

Write findings to `research/25-hookpoints.md`:
- Existing code inventory relevant to this file
- Reusable components (what's already done)
- New components needed (just the `__main__.py` file)
- Test infrastructure available
- Any surprises or conflicts

## Rules

- Do NOT modify any files other than `research/25-hookpoints.md`
- Do NOT write code
- Do NOT inspect the live Discord server
