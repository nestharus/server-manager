# Code Agent: bot-activity command

## Your Role

You are the CODE WRITER. Implement the `bot-activity` command in
`discord_cli.py` to make all tests pass.

## Files to Read

1. `/home/nes/discord/worktrees/bot-activity/proposals/09-bot-activity.md` — approved design
2. `/home/nes/discord/worktrees/bot-activity/research/09-hookpoints.md` — insertion points
3. `/home/nes/discord/worktrees/bot-activity/tests/test_discord_cli.py` — tests to pass
4. `/home/nes/discord/worktrees/bot-activity/discord_cli.py` — existing code to extend

## What to implement

1. **`is_history_capable_channel(channel)`** helper:
   - Returns True for TextChannel, VoiceChannel, StageChannel, Thread
   - Returns False for everything else
   - Place it near other helper functions

2. **`fetch_bot_activity(guild, args)`** handler:
   - Validate `args.per_channel_limit > 0`
   - Iterate `combined_channels(guild)`, filter by `is_history_capable_channel`
   - For each eligible channel, read `channel.history(limit=args.per_channel_limit)`
   - Catch `discord.Forbidden` per channel and skip
   - Filter messages by `message.author.id == args.bot_id`
   - Track per-channel counts, last_seen, and collect samples (max 10)
   - Return the specified output schema
   - Place after `fetch_read()` and before `fetch_integrations()`

3. **Register in `command_specs()`**: Add `"bot-activity": fetch_bot_activity`

4. **Register in `build_parser()`**: Add subparser with positional `bot_id`
   (type=int) and optional `--per-channel-limit` (type=int, default=100)

## Constraints

- Follow existing code style exactly
- Use existing helpers: `combined_channels`, `serialize_message`, `iso_or_none`, `CLIError`
- No new dependencies
- No compatibility shims
- Run tests after implementation: `cd /home/nes/discord/worktrees/bot-activity && uv run pytest tests/ -v`

## Output

Edit `/home/nes/discord/worktrees/bot-activity/discord_cli.py` and verify
all tests pass. Report the test results.
