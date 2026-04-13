# Phase 3: Proposal — Discord CLI Tool

## Objective
Propose a design for `discord_cli.py` — a one-shot CLI tool that wraps discord.py for inspecting and managing the Humility guild. Include architecture, tradeoffs, and anti-scope. Do NOT implement.

## Input
Read the following files for context:
- `research/05-discord-cli.md` — problem space research
- `research/05-discord-cli-needs.md` — synthesized user needs

## Requirements (from user context)
1. Load `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID` from `.env`
2. Use `discord.py` with intents for members and message content
3. One-shot behavior: connect to gateway, resolve configured guild, run the requested subcommand, print JSON to stdout, exit
4. Subcommands needed immediately:
   - `overview` — guild summary (name, id, owner, member count, channels, roles, boosts, creation date)
   - `bots` — list bot members
   - `channels` — list all channels with type, category, position
   - `find-channel <name>` — find channel by name substring
   - `read <channel> [--limit N]` — read messages from a channel
   - `integrations` — list guild integrations
5. Output must be JSON for downstream processing
6. CLI uses argparse with subcommands

## Design Constraints
- Single file (`discord_cli.py`) — this is a lightweight tool, not a framework
- No database, no persistent state
- No backwards-compatibility shims
- No feature flags
- Each subcommand is a self-contained async handler

## Deliverable
Write your proposal to `proposals/05-discord-cli.md`. Include:
1. Architecture (how the CLI is structured)
2. Subcommand specifications (inputs, outputs, discord.py APIs used)
3. Error handling strategy
4. Anti-scope (what this tool is NOT)
5. Tradeoffs considered

## Rules
- Do NOT write implementation code
- Do NOT create stubs or placeholder files
- Focus on the design document only
