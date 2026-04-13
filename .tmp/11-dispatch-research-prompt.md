# Research: bot-activity command dispatch verification

## Goal

Verify that `discord_cli.py` already has the `bot-activity` command
dispatch correctly wired in the command router.

## What to investigate

1. Read `/home/nes/discord/discord_cli.py`
2. Check `command_specs()` — does it include `"bot-activity": fetch_bot_activity`?
3. Check `run_command()` — does it dispatch through `command_specs()[command]`?
4. Verify the handler receives `args.bot_id` and `args.per_channel_limit`

## Constraints

- Do NOT propose changes unless something is actually wrong
- Document current state only

## Output

Write findings to `research/11-dispatch-verification.md`.
