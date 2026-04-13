# Proposal: bot-activity command for discord_cli.py

## Context

Read these files first:
- `/home/nes/discord/worktrees/bot-activity/research/09-bot-activity.md` — problem research
- `/home/nes/discord/worktrees/bot-activity/research/09-bot-activity-needs.md` — needs synthesis
- `/home/nes/discord/worktrees/bot-activity/discord_cli.py` — existing CLI

## Goal

Propose a design for adding a `bot-activity` subcommand to `discord_cli.py`.

The command scans every readable text-like channel in the guild for
messages authored by a supplied bot ID, counts matches per channel,
tracks the last-seen timestamp, and returns a compact JSON payload.

## Requirements

1. **Handler**: `async def fetch_bot_activity(guild, args)` following
   existing patterns.

2. **Scanning**: Iterate `combined_channels(guild)`, filter to
   history-capable types (text, news, voice, stage, thread — exclude
   categories and forums). For each, call `channel.history(limit=per_channel_limit)`,
   filter messages by `author.id == bot_id`.

3. **Error handling**: Catch `discord.Forbidden` per channel and skip
   it silently (or report in a `skipped` list). Do NOT abort the scan.

4. **Output schema**:
   ```json
   {
     "bot_id": 123,
     "total_messages_seen": 15,
     "last_seen": "2023-12-23T04:56:53+00:00",
     "per_channel": [
       {"channel_id": 456, "channel_name": "admin-chat", "count": 15, "last_seen": "..."}
     ],
     "samples": [<serialized messages, limited count>]
   }
   ```

5. **Argparse**: Positional `bot_id` (type=int), optional
   `--per-channel-limit` (type=int, default=100).

6. **Registration**: Add to `command_specs()` and `build_parser()`.

7. **No new dependencies**. Use existing helpers: `combined_channels`,
   `serialize_message`, `serialize_channel`, `iso_or_none`.

## Constraints

- Follow the existing CLI handler pattern exactly
- No compatibility shims
- No deferred stubs
- Do NOT implement — only propose the design

## Output

Write the proposal to `proposals/09-bot-activity.md`. Include:
- Architecture / function signatures
- Data flow description
- Anti-scope (what this does NOT do)
- Tradeoffs considered
