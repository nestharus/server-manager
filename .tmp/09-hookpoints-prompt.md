# Hookpoint Research: bot-activity command

## Context

Read these files:
- `/home/nes/discord/worktrees/bot-activity/proposals/09-bot-activity.md` — approved proposal
- `/home/nes/discord/worktrees/bot-activity/discord_cli.py` — existing code

## Goal

Map the proposal to existing code. For each proposed change, identify:

1. **What's reusable**: existing functions, helpers, patterns that the
   implementation should use directly
2. **What's parallel**: similar code that can serve as a reference
3. **What to add**: new code that doesn't exist yet
4. **Insertion points**: exact locations in the file where new code goes

## Specific questions

1. Where exactly does `fetch_bot_activity` go in the file? After which
   existing handler?
2. Where does `is_history_capable_channel` go? With other helpers or
   near the handler?
3. What existing serializers are reusable as-is?
4. Where in `command_specs()` does the new entry go?
5. Where in `build_parser()` does the new subparser go?
6. Are there any existing patterns that should change to avoid
   duplication?

## Constraints

- Do NOT implement code
- Focus on mapping proposal to existing file structure
- Be specific about line numbers and function names

## Output

Write your findings to `research/09-hookpoints.md`.
