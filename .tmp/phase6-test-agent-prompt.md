# Phase 6: Test Agent — Discord CLI Tool

## Objective
Write tests for `discord_cli.py` based on the contracts (proposal and specifications) ONLY. Do NOT read the implementation code.

## Input — Read these files:
- `proposals/05-discord-cli.md` — the approved proposal with subcommand specs
- `research/05-discord-cli-needs.md` — synthesized user needs

## Do NOT read:
- `discord_cli.py` — the implementation (you must not see it)

## Test Requirements

Write tests to `tests/test_discord_cli.py` using pytest. The tests should verify:

### 1. Configuration
- Missing `DISCORD_BOT_TOKEN` raises RuntimeError
- Missing `DISCORD_GUILD_ID` raises RuntimeError
- Non-integer `DISCORD_GUILD_ID` raises RuntimeError

### 2. JSON serialization
- `datetime` objects are serialized to ISO 8601 strings
- The `json_default` helper raises TypeError for unsupported types

### 3. Argument parsing
- `build_parser()` recognizes all 6 subcommands: overview, bots, channels, find-channel, read, integrations
- Unknown subcommands are rejected
- `read` subcommand accepts a channel argument and optional `--limit`

### 4. Subcommand handlers (mock discord.py objects)
- `overview` returns expected fields (name, id, owner, member_count, etc.)
- `bots` filters members by `bot == True`
- `channels` returns channel info with type, name, id
- `find-channel` matches by substring (case-insensitive)
- `find-channel` returns empty list when no match
- `read` returns message content with author info
- `integrations` returns integration info with type and enabled status

### 5. Gateway lifecycle
- `run_gateway_command` calls `client.close()` in all paths
- Errors from handlers are propagated, not swallowed

## Rules
- Use `unittest.mock` to mock discord.py objects (Guild, Member, Channel, etc.)
- Use `pytest` fixtures for common setup
- Tests encode the CONTRACT, not the implementation
- Do NOT import or read `discord_cli.py` source — only import its public API
- Write to `tests/test_discord_cli.py`
