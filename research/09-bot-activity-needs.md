# Synthesis: bot-activity needs for Humility

## Context

The `bot-activity` command serves the Humility server's bot-consolidation
investigation. The user wants to audit which bots have visible message
footprints across the guild's ~42 channels to determine which bots are
actively used vs. merely installed.

## Mapping research to Humility's needs

### 1. Channel scanning scope

The research confirms `combined_channels(guild)` includes both channels
and threads, but also includes non-history-capable objects (categories,
forums). The command needs a filter that excludes categories and forum
containers while including text, news, voice, stage channels, and threads.

For Humility specifically: the guild has 42 channels including the
`GUILD TEMPLATE` category (which is hidden from `@everyone`). The bot
has Administrator permissions so it can read all channels. The scan
should include all history-capable surfaces.

### 2. Per-channel message limit

The research notes `history()` paginates in 100-message batches. For
the bot audit use case, scanning recent messages per channel is
sufficient — we don't need to scan entire channel histories. A
configurable `--per-channel-limit` with a reasonable default (e.g., 100)
lets the user increase coverage for deeper scans without unbounded
iteration.

The replay task requires the CLI accept `--per-channel-limit 500` and
`--per-channel-limit 2000` arguments as used in the original session.

### 3. Permission errors

The research confirms `discord.Forbidden` is raised when the bot can't
read a channel's history. Since the bot has Administrator on Humility
this shouldn't trigger, but the command should gracefully skip
forbidden channels and report them in the output rather than aborting
the entire scan. This makes the command robust for future use on
guilds where the bot has restricted permissions.

### 4. Output schema

The required payload matches the audit use case:
- `bot_id`: identifies which bot was scanned
- `total_messages_seen`: aggregate count across all channels
- `last_seen`: most recent timestamp — tells if the bot is active
- `per_channel`: breakdown by channel — shows where the bot posts
- `samples`: representative messages — shows what the bot does

The `per_channel` entries should include `channel_id`, `channel_name`,
`count`, and `last_seen`. The samples should be serialized using the
existing `serialize_message()` helper for consistency.

### 5. Argparse interface

The command needs:
- Positional `bot_id` argument (the Discord user ID of the bot to scan)
- Optional `--per-channel-limit` with a default value

### 6. No gaps identified

The research covers all the APIs needed. The existing CLI patterns
(handler shape, argparse registration, gateway wrapper, serialization
helpers) are sufficient building blocks. No external dependencies or
new infrastructure is required.

## Summary

The `bot-activity` command is a read-only inspection tool that fits
naturally into the existing CLI pattern. It scans all history-capable
channels for messages from a specific bot, aggregates counts and
timestamps, and returns a compact JSON payload. The only new
functionality beyond existing CLI patterns is multi-channel scanning
with graceful per-channel error handling.
