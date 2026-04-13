# Research: bot-activity argparse subparser verification

## Goal

Verify that `discord_cli.py` already has the `bot-activity` argparse
subparser correctly wired. Document what exists and whether any changes
are needed.

## What to investigate

1. Read `/home/nes/discord/discord_cli.py` — find the `build_parser()`
   function
2. Verify a subparser named `bot-activity` exists
3. Verify it has:
   - Positional `bot_id` with `type=int`
   - Optional `--per-channel-limit` with `type=int, default=100`
   - `set_defaults(func=run_command)`
4. Verify the subparser is properly integrated with the rest of the CLI

## Constraints

- Do NOT propose changes unless something is actually wrong
- Do NOT modify any code
- Document current state only

## Output

Write findings to `research/10-parser-verification.md`.
