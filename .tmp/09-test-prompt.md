# Test Agent: bot-activity command

## Your Role

You are the TEST WRITER. You write tests that encode the contract's
expected behavior. You do NOT see or write implementation code.

## Contract

The `bot-activity` command for `discord_cli.py` has this contract:

### Handler signature
```python
async def fetch_bot_activity(
    guild: discord.Guild,
    args: argparse.Namespace,
) -> dict[str, Any]:
```

### Arguments (via argparse)
- `args.bot_id: int` — positional, the Discord user ID of the bot
- `args.per_channel_limit: int` — optional, default 100

### Predicate helper
```python
def is_history_capable_channel(channel: Any) -> bool:
```
Returns `True` for `TextChannel`, `VoiceChannel`, `StageChannel`, `Thread`.
Returns `False` for `CategoryChannel`, `ForumChannel`, and anything else.

### Output schema
```json
{
  "bot_id": 123,
  "total_messages_seen": 15,
  "last_seen": "2023-12-23T04:56:53+00:00",
  "per_channel": [
    {"channel_id": 456, "channel_name": "admin-chat", "count": 15, "last_seen": "..."}
  ],
  "samples": [<serialize_message() output>]
}
```

### Behavior rules
1. Scans `combined_channels(guild)` filtered by `is_history_capable_channel`
2. For each eligible channel, reads `channel.history(limit=per_channel_limit)`
3. Filters messages where `message.author.id == bot_id`
4. If `per_channel_limit <= 0`, raises `CLIError("usage_error", ...)`
5. If bot has zero matches, returns `total_messages_seen: 0`, `last_seen: null`, empty lists
6. Catches `discord.Forbidden` per channel and skips silently
7. `samples` limited to 10 most recent matching messages
8. `per_channel` sorted by count descending, then last_seen descending
9. `last_seen` at top level is the newest `created_at` across all matches

### Argparse registration
- Subparser named `bot-activity`
- Positional `bot_id` with `type=int`
- Optional `--per-channel-limit` with `type=int, default=100`
- Sets `func=run_command`

### Existing helpers you can import
```python
from discord_cli import (
    is_history_capable_channel,
    fetch_bot_activity,
    build_parser,
    command_specs,
    CLIError,
    serialize_message,
    iso_or_none,
)
```

## Existing test file

Read `/home/nes/discord/worktrees/bot-activity/tests/test_discord_cli.py`
for existing test patterns, fixtures, and mock strategies.

## Tests to write

Add new tests to the EXISTING test file. Do NOT create a new file.

Required test cases:
1. `test_bot_activity_subparser_exists` — parser recognizes `bot-activity`
2. `test_bot_activity_handler_is_async` — handler is a coroutine function
3. `test_bot_activity_in_command_specs` — registered in command_specs()
4. `test_is_history_capable_text_channel` — TextChannel returns True
5. `test_is_history_capable_voice_channel` — VoiceChannel returns True
6. `test_is_history_capable_stage_channel` — StageChannel returns True
7. `test_is_history_capable_thread` — Thread returns True
8. `test_is_history_capable_category_excluded` — CategoryChannel returns False
9. `test_is_history_capable_forum_excluded` — ForumChannel returns False
10. `test_bot_activity_zero_results` — bot with no messages returns zeros
11. `test_bot_activity_finds_messages` — bot with messages returns correct counts
12. `test_bot_activity_forbidden_channel_skipped` — Forbidden doesn't abort scan
13. `test_bot_activity_invalid_limit` — per_channel_limit <= 0 raises CLIError
14. `test_bot_activity_samples_limited` — samples capped at 10
15. `test_bot_activity_per_channel_sorted` — per_channel sorted by count desc

## Rules
- Use pytest
- Use existing mock patterns from the test file
- Do NOT write implementation code
- Write ONLY to `/home/nes/discord/worktrees/bot-activity/tests/test_discord_cli.py`
