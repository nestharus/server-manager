# Research: `bot-activity` Command

## Scope

This note documents the current problem space for a future
`bot-activity` subcommand in `discord_cli.py`.

It is limited to:

- what the repo already does
- what `discord.py` `2.7.1` exposes
- what the requested JSON payload requires
- which edge cases follow from those two sources

It does not propose an implementation.

`discord.py` version context was verified from the repo-adjacent virtual
environment at `/home/nes/discord/.venv`, which reports `2.7.1`.

Primary sources consulted:

- Local repo:
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py)
- Installed `discord.py 2.7.1` source:
  `/home/nes/discord/.venv/lib/python3.14/site-packages/discord/*`
- Upstream `v2.7.1` source tag:
  `https://github.com/Rapptz/discord.py/tree/v2.7.1`
- Upstream docs root for `v2.7.1`:
  `https://discordpy.readthedocs.io/en/v2.7.1/`

Relevant upstream files/pages:

- `discord/abc.py` (`Messageable.history`)
- `discord/channel.py` (`TextChannel`, `VocalGuildChannel`,
  `VoiceChannel`, `StageChannel`, `CategoryChannel`, `ForumChannel`,
  `TextChannel.archived_threads`, `ForumChannel.archived_threads`)
- `discord/threads.py` (`Thread`)
- `discord/guild.py` (`Guild.threads`, `Guild.active_threads`)
- `discord/http.py` (`HTTPClient.logs_from`)
- `discord/errors.py` (`HTTPException`, `Forbidden`)

## 1. Existing CLI patterns in `discord_cli.py`

### Command registration and handler shape

The current CLI follows a consistent pattern:

- each public command is an `async def fetch_*(guild, args)` handler
  returning `dict[str, Any]`
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:352))
- `command_specs()` registers subcommand name to handler
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:443))
- `build_parser()` creates argparse subparsers and routes them through
  `run_command`
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:468))
- `run_command()` executes the selected handler through the gateway
  wrapper and prints the standard success envelope
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:455))

The success envelope is currently:

```json
{"ok": true, "command": "...", "guild_id": ..., "data": {...}}
```

That shape comes from `success_payload()`
([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:75)).

### Channel iteration helpers

The existing channel helpers are directly relevant:

- `combined_channels(guild)` returns `guild.channels + guild.threads`
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:246))
- `resolve_channel()` searches that combined set by ID, exact name, then
  partial name
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:262))
- `channel_kind()` only distinguishes `"thread"` vs `"channel"`
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:303))

There is no existing helper that filters the combined set down to only
history-capable objects before calling `.history()`.

### Message serialization and timestamps

`serialize_message()` currently emits:

- `id`
- `created_at`
- `edited_at`
- `author`
- `content`
- `attachments`
- `embeds`
- `pinned`
- `tts`
- `type`
- `jump_url`

Source:
[discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:187).

Datetime handling is already normalized to ISO 8601 strings or `null`
via `iso_or_none()`
([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:104)).

### Existing read-path behavior

`fetch_read()` is the closest existing analogue:

- rejects `--limit <= 0` with `CLIError("usage_error", ...)`
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:409))
- clamps the requested limit to `MAX_READ_LIMIT = 200`
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:18),
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:413))
- resolves one channel from the combined channel/thread set
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:414))
- materializes `channel.history(limit=limit)` into a list
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:416))
- reverses the list before returning it
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:417))

The current CLI does not catch per-channel history failures inside
`fetch_read()`.

## 2. How `channel.history()` works in `discord.py` `2.7.1`

`history()` is defined on `discord.abc.Messageable`
(`discord/abc.py`, upstream tag `v2.7.1`).

In `2.7.1`, it returns an async iterator of `discord.Message` objects,
not a prebuilt list.

Source-backed behavior in `2.7.1`:

- permission requirement: `Permissions.read_message_history`
- `limit` default: `100`
- `limit=None` means "retrieve every message in the channel" and is
  explicitly documented as slow
- `before`, `after`, and `around` accept a snowflake or `datetime`
- naive datetimes are treated as local time
- `oldest_first` defaults to `True` when `after` is provided, otherwise
  `False`
- `around` requires a non-`None` limit and caps that limit at `101`
- `around` with `limit=None` raises `ValueError`

Installed source:

- `/home/nes/discord/.venv/lib/python3.14/site-packages/discord/abc.py:1902`

Upstream tag:

- `https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/abc.py`

### Pagination mechanics

`history()` pages through Discord's message history REST endpoint via
`HTTPClient.logs_from()`.

Concrete mechanics visible in `2.7.1`:

- each request fetches at most `100` messages
- the route is `GET /channels/{channel_id}/messages`
- iteration stops when the requested limit is exhausted or a page comes
  back with fewer than `100` items

Installed source:

- `/home/nes/discord/.venv/lib/python3.14/site-packages/discord/abc.py:1974`
- `/home/nes/discord/.venv/lib/python3.14/site-packages/discord/http.py:1021`

That means bounded scanning is controlled first by the
`history(limit=...)` argument and then internally by 100-message pages.

### Exceptions

The `history()` contract in `2.7.1` lists:

- `discord.Forbidden` when history cannot be read
- `discord.HTTPException` for other request failures

`Forbidden` is a subclass of `HTTPException`.

Installed source:

- `/home/nes/discord/.venv/lib/python3.14/site-packages/discord/errors.py:113`
- `/home/nes/discord/.venv/lib/python3.14/site-packages/discord/errors.py:182`

## 3. Which guild channel types do and do not support `history()`

### History-capable guild objects

In `discord.py` `2.7.1`, the relevant guild-side messageable types are:

| Guild object | Evidence | Notes |
| --- | --- | --- |
| `TextChannel` | `discord/channel.py:283` | Covers both `ChannelType.text` and `ChannelType.news`. |
| `VoiceChannel` | `discord/channel.py:1456` | Inherits `VocalGuildChannel`, which inherits `Messageable`. |
| `StageChannel` | `discord/channel.py:1684` | Also inherits `VocalGuildChannel` and therefore `Messageable`. |
| `Thread` | `discord/threads.py:65` | Covers `public_thread`, `private_thread`, and `news_thread`. |

Important implications from the type hierarchy:

- announcement/news channels are still `TextChannel`
- voice and stage channels are history-capable at the library type
  level because `VocalGuildChannel` inherits `Messageable`
- thread parents can be either `TextChannel` or `ForumChannel`

### Excluded guild objects

These guild objects are not `Messageable` in `2.7.1`:

| Guild object | Evidence | Why it matters |
| --- | --- | --- |
| `CategoryChannel` | `discord/channel.py:2010` | Categories are containers only. |
| `ForumChannel` | `discord/channel.py:2363` | The forum itself is not a message history surface. |

`ForumChannel.type` can be `forum` or `media`, but both are exposed by
the same non-`Messageable` class in this version.

### Repo-level consequence of the current helpers

`combined_channels(guild)` includes all `guild.channels` plus
`guild.threads`
([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:246)).

That means the repo's broadest reusable channel iterator already mixes:

- history-capable objects
- non-history-capable containers like categories and forums
- threads

This is already visible in `fetch_read()`, which resolves from the
combined set and then immediately calls `.history()`
([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:414)).

## 4. Permission and error behavior

### What the library raises

For history reads:

- `discord.Forbidden` represents a 403 response
- `discord.HTTPException` carries the HTTP status, Discord error code,
  and response text

Installed source:

- `/home/nes/discord/.venv/lib/python3.14/site-packages/discord/errors.py:113`
- `/home/nes/discord/.venv/lib/python3.14/site-packages/discord/errors.py:182`

### What the current CLI does with those exceptions

The repo currently has two relevant error paths:

- deliberate CLI-facing failures use `CLIError`
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:25))
- uncaught Discord library exceptions fall through to `main()` as
  `runtime_error`
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:512))

`run_gateway_command()` does not transform handler exceptions; it stores
them, closes the client, then re-raises them
([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:307)).

So under current repo behavior:

- a `discord.Forbidden` from one history read aborts the whole command
  unless the handler catches it
- a non-`Messageable` object reaching `.history()` would fail as a
  normal Python attribute error, not as a Discord HTTP exception

That is the current gap between "gracefully skip unreadable channels"
and what the CLI currently does today.

## 5. Bounded scanning and performance facts

The repo already establishes one bounded history-read pattern:

- `DEFAULT_READ_LIMIT = 50`
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:19))
- `MAX_READ_LIMIT = 200`
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:18))

Because `history()` pages in batches of at most `100`, a per-channel cap
of `N` implies a worst-case upper bound of `ceil(N / 100)` history
requests for that channel.

Using the repo's current `MAX_READ_LIMIT` as a reference point:

- one channel capped at `200` messages means at most `2` history pages
- `42` scanned targets at that same cap means at most `8,400` yielded
  messages and `84` `/messages` requests

Those are upper bounds derived from the existing repo constant plus the
library's 100-message pagination rule. They do not include any extra
thread-discovery calls.

The main unbounded case is still `limit=None`, which the library
explicitly documents as slow.

`around` is not relevant to a full scan shape because the library treats
it as a special bounded window with a hard maximum of `101`.

## 6. Output schema requirements versus what exists today

The requested command output is:

- `bot_id`
- `total_messages_seen`
- `last_seen`
- `per_channel`
- `samples`

The current repo already has building blocks for part of that:

- standard command success envelope via `success_payload()`
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:75))
- channel metadata serialization via `serialize_channel()`
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:144))
- message metadata serialization via `serialize_message()`
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:187))
- ISO timestamp conversion via `iso_or_none()`
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:104))

What does not already exist in the file:

- no aggregate "activity by author" serializer
- no existing schema shaped as
  `{channel_id, channel_name, count, last_seen}`
- no compact sample-snippet serializer
- no existing command that scans many channels and reports partial
  success alongside skipped-channel failures

`serialize_message()` is also broader than the requested compact output:
it emits full content and attachment/embed metadata rather than a small
sample-oriented representation.

## 7. Thread-specific and zero-result edge cases

### No matching messages anywhere

Nothing in the current CLI forbids zero-count payloads. Existing list
commands already return counts that can be zero
([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:371),
 [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:386),
 [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:435)).

So "bot has no messages anywhere" is a normal result-shape problem, not
a library failure mode.

### Threads versus top-level channels

Threads are already first-class in this repo:

- `combined_channels()` explicitly includes them
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:246))
- `resolve_channel()` checks both `guild.get_channel()` and
  `guild.get_thread()`
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:268))
- `fetch_channels()` serializes `guild.channels` and `guild.threads`
  separately
  ([discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:386))

At the library level:

- `Guild.threads` is only "a list of threads that you have permission to
  view"
- `Guild.active_threads()` is a separate API call returning active
  threads the client can access

Installed source:

- `/home/nes/discord/.venv/lib/python3.14/site-packages/discord/guild.py:691`
- `/home/nes/discord/.venv/lib/python3.14/site-packages/discord/guild.py:2429`

The current repo does not call `active_threads()`. Its reusable helper
surface is the cached `guild.threads` property.

### Archived thread discovery boundary

`discord.py 2.7.1` exposes archived-thread iterators on both text and
forum parents:

- `TextChannel.archived_threads(...)`
- `ForumChannel.archived_threads(...)`

Those are separate surfaces from `guild.threads` and
`guild.active_threads()`.

Installed source:

- `/home/nes/discord/.venv/lib/python3.14/site-packages/discord/channel.py:979`
- `/home/nes/discord/.venv/lib/python3.14/site-packages/discord/channel.py:3121`

That matters because the repo's current reusable channel/thread helpers
do not traverse archived thread iterators at all. A scan based only on
`combined_channels(guild)` is bounded by whatever threads are already
present in `guild.threads`.

### Forum channels versus forum posts

The forum container itself is not history-capable, but the threads under
it are.

So "scan every readable text-like channel" and "include forum activity"
are not the same thing in `discord.py` terms:

- the forum itself is a `GuildChannel`
- the actual message surface is the child `Thread`

### Voice and stage channels

In `discord.py` `2.7.1`, voice and stage channels are not purely
"voice-only" objects from the library's type perspective. Both inherit
from `VocalGuildChannel`, which is `Messageable`.

That means the library-level "text-like" surface includes Discord's
text-in-voice and text-in-stage channels.

## 8. Problem boundary, stated without implementation

Based on the current repo and `discord.py` `2.7.1`, the requested
command needs to account for all of these facts at once:

- the repo's broadest reusable channel iterator includes both channels
  and threads
- not every object in that combined set supports `.history()`
- `history()` is async, paginated, and bounded by its `limit`
- unreadable history surfaces raise `discord.Forbidden`
- forum activity lives in threads, not on the forum container
- voice and stage channels are history-capable in this library version
- archived thread traversal is a separate API surface from
  `guild.threads`
- the existing serializers are message-oriented, not aggregate-oriented
- the existing CLI error model distinguishes `CLIError` from uncaught
  Discord exceptions
