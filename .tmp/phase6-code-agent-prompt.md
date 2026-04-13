# Phase 6: Code Agent — Discord CLI Tool

## Objective
Implement `discord_cli.py` to make all tests pass. You have access to both the contracts and the test files.

## Input — Read these files:
- `proposals/05-discord-cli.md` — the approved proposal
- `research/05-hookpoints.md` — hookpoint analysis of existing code
- `tests/test_discord_cli.py` — the test file you must make pass
- `discord_cli.py` — the existing code to modify/replace

## Implementation Requirements

Based on the proposal, implement `discord_cli.py` as a single-file CLI tool with:

1. **Config loading** from `.env` (DISCORD_BOT_TOKEN, DISCORD_GUILD_ID)
2. **JSON utilities** (json_default for datetime, print_json)
3. **One-shot gateway runner** (run_gateway_command with reconnect=False)
4. **6 subcommand handlers**:
   - `overview` — guild metadata snapshot
   - `bots` — list bot members
   - `channels` — list all channels with type/category
   - `find-channel` — name-based channel search (substring, case-insensitive)
   - `read` — message history from a channel (with --limit)
   - `integrations` — list guild integrations
5. **argparse CLI** with subcommands

## Key Design Points from Proposal
- One-shot: connect, run, print JSON, exit
- Guard against duplicate `on_ready` calls
- Flat JSON serialization (no raw discord.py model dumps)
- Exit codes: 0 success, 1 config error, 2 runtime error

## After Implementation
Run the tests:
```bash
cd /home/nes/discord && .venv/bin/python -m pytest tests/ -v
```

Fix any failures until all tests pass.

## Rules
- Modify `discord_cli.py` in place
- Do NOT modify test files
- Keep it as a single file
- Follow the proposal's design, not your own preferences
