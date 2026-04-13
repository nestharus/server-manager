# Research: bot-activity command for discord_cli.py

## Goal

Document the problem space for adding a `bot-activity` command to
`discord_cli.py`. This command should scan every readable text-like
channel in a guild for messages authored by a supplied bot ID, then
return a compact JSON payload.

## What to investigate

1. **discord.py channel history scanning**: How does `channel.history()`
   work? What parameters control iteration limits? How to handle
   permission errors gracefully when the bot can't read certain channels?

2. **Channel type filtering**: Which channel types support
   `history()` — text, news, voice text, forum, stage? Which should be
   excluded (categories, voice-only)?

3. **Performance considerations**: The guild has ~42 channels. Scanning
   all of them with a per-channel message limit is feasible but needs
   bounded iteration. What's the best way to cap scanning per channel?

4. **Output schema**: The command should return:
   - `bot_id`: the target bot's user ID
   - `total_messages_seen`: count across all channels
   - `last_seen`: the most recent message timestamp from this bot
   - `per_channel`: list of `{channel_id, channel_name, count, last_seen}`
   - `samples`: representative message snippets (limited count)

5. **Existing CLI patterns**: Read `discord_cli.py` to understand:
   - How commands are registered (argparse subparsers)
   - How handlers are structured (`async def fetch_*(guild, args)`)
   - How channels are iterated (`combined_channels`, `resolve_channel`)
   - How messages are serialized (`serialize_message`)
   - How errors are raised (`CLIError`)

6. **Edge cases**:
   - Bot has no messages anywhere
   - Channel that raises Forbidden on history read
   - Thread channels vs text channels

## Constraints

- Do NOT propose solutions or design the implementation
- Document what exists and what the problem requires
- Reference specific discord.py APIs with version context (v2.7.1)
- Read the existing `discord_cli.py` to understand current patterns

## Output

Write your findings to `research/09-bot-activity.md`.
