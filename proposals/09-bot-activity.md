# Proposal: `bot-activity` Command

Date: 2026-04-13

## Goal

Add a read-only `bot-activity` subcommand to `discord_cli.py` that
scans the guild's history-capable channel surfaces for messages from one
supplied bot user ID and returns a compact JSON summary.

This proposal is design only. It does not include implementation code.

## Summary

The command should follow the existing CLI pattern exactly:

- register a new `fetch_bot_activity(guild, args)` async handler
- wire it into `command_specs()`
- add a `bot-activity` argparse subparser in `build_parser()`
- reuse existing helpers: `combined_channels`, `serialize_message`,
  `serialize_channel`, and `iso_or_none`

The handler should scan the existing combined channel/thread surface,
filter it down to history-capable types only, read bounded recent
history per channel, aggregate matches for `author.id == args.bot_id`,
and return a compact payload with totals, last-seen timestamps,
per-channel counts, and a small recent sample set.

## Architecture

### Primary handler

Add a new handler matching the current typed pattern:

```python
async def fetch_bot_activity(
    guild: discord.Guild,
    args: argparse.Namespace,
) -> dict[str, Any]:
    ...
```

Recommended `args` fields:

- `args.bot_id: int`
- `args.per_channel_limit: int`

### Optional small helper

To keep the handler readable, add one small predicate helper:

```python
def is_history_capable_channel(channel: Any) -> bool:
    ...
```

Recommended type check:

```python
isinstance(
    channel,
    (
        discord.TextChannel,
        discord.VoiceChannel,
        discord.StageChannel,
        discord.Thread,
    ),
)
```

This covers:

- text channels
- announcement/news channels, via `discord.TextChannel`
- voice channels with text history
- stage channels with text history
- threads

It excludes:

- categories
- forums/media containers

No extra discovery path is needed for v1. The command should iterate
`combined_channels(guild)` and filter that list in-process.

### Parser and command registration

Add the handler to `command_specs()`:

```python
"bot-activity": fetch_bot_activity,
```

Add a new subparser in `build_parser()`:

```python
bot_activity_parser = subparsers.add_parser(
    "bot-activity",
    help="Scan channels for activity by a bot",
)
bot_activity_parser.add_argument("bot_id", type=int)
bot_activity_parser.add_argument(
    "--per-channel-limit",
    type=int,
    default=100,
)
bot_activity_parser.set_defaults(func=run_command)
```

## Data Flow

### 1. Argument handling

`run_command()` and `run_gateway_command()` should remain unchanged.
`fetch_bot_activity()` receives the resolved guild plus parsed args.

The handler should validate:

- `args.per_channel_limit > 0`
- `args.per_channel_limit <= 10000`

On invalid input, raise:

```python
CLIError("usage_error", "--per-channel-limit must be between 1 and 10000", exit_code=1)
```

Recommendation: do not clamp `--per-channel-limit` to `MAX_READ_LIMIT`
(200), but do enforce 10000 as a hard upper bound. `read` is an
interactive message dump command; `bot-activity` is an audit command and
should accept deeper scan windows such as `500` or `2000` when
explicitly requested. The 10000 ceiling prevents effectively-unbounded
scans (e.g. `100000`) that would produce thousands of paginated API
requests across 40+ channels with no practical benefit over the cap.

### 2. Eligible channel selection

The handler should iterate:

```python
for channel in combined_channels(guild):
    ...
```

For each entry:

- skip immediately if `is_history_capable_channel(channel)` is false
- otherwise attempt `channel.history(limit=args.per_channel_limit)`

This keeps the scan aligned with the repo's existing broad channel
surface while preventing `.history()` calls on categories and forum
containers.

### 3. Per-channel scan behavior

For each eligible channel:

1. Read bounded recent history with
   `channel.history(limit=args.per_channel_limit)`.
2. Filter messages where `message.author.id == args.bot_id`.
3. Compute:
   - per-channel match count
   - per-channel `last_seen` from the newest matching
     `message.created_at`
4. If the channel has at least one match, append one entry to
   `per_channel`.

Recommended `per_channel` entry shape:

```json
{
  "channel_id": 456,
  "channel_name": "admin-chat",
  "count": 15,
  "last_seen": "2023-12-23T04:56:53+00:00"
}
```

`serialize_channel(...)` should still be used as the source of channel
identity data, with the output flattened to the required compact fields.
That avoids duplicating channel naming and thread/channel-kind handling
logic.

### 4. Aggregate tracking

The handler should maintain these aggregates across the scan:

- `total_messages_seen`: sum of all per-channel match counts
- `last_seen`: newest `created_at` across all matches
- `per_channel`: one entry per channel with at least one match
- `samples`: a compact list of recent matching messages

Recommended response shape:

```json
{
  "bot_id": 123,
  "total_messages_seen": 15,
  "last_seen": "2023-12-23T04:56:53+00:00",
  "per_channel": [
    {
      "channel_id": 456,
      "channel_name": "admin-chat",
      "count": 15,
      "last_seen": "2023-12-23T04:56:53+00:00"
    }
  ],
  "samples": []
}
```

If the bot has no matches in the scanned window, return:

- `total_messages_seen: 0`
- `last_seen: null`
- `per_channel: []`
- `samples: []`

That should be treated as a normal result, not an error.

### 5. Sample selection

Use `serialize_message(message)` for samples exactly as the rest of the
CLI serializes message objects.

Recommendation:

- keep a fixed small sample cap in the handler, e.g. `10`
- collect the most recent matching messages across the whole scan
- sort samples newest-first before serializing

This keeps the payload compact without adding another CLI flag in v1.
The sample list is informational only; the authoritative summary is the
aggregate count plus per-channel breakdown.

### 6. Error handling

Per-channel history access must not abort the scan.

Recommended behavior:

- catch `discord.Forbidden` around each `channel.history(...)` call
- skip that channel and continue scanning
- do not raise a command-level error

For v1, keep the payload minimal and skip forbidden channels silently.
If partial-scan visibility becomes important later, a `skipped` list can
be added as a backward-compatible extension.

Non-permission failures should still surface normally. In particular:

- `discord.HTTPException` other than `Forbidden` should abort
- programming errors such as a bad type assumption should abort

That keeps the command robust to permission gaps without masking real
runtime failures.

## Output Contract

The command should return `data` shaped as:

```json
{
  "bot_id": 123,
  "total_messages_seen": 15,
  "last_seen": "2023-12-23T04:56:53+00:00",
  "per_channel": [
    {
      "channel_id": 456,
      "channel_name": "admin-chat",
      "count": 15,
      "last_seen": "2023-12-23T04:56:53+00:00"
    }
  ],
  "samples": [
    {}
  ]
}
```

Field semantics:

- `bot_id`: the requested Discord user ID
- `total_messages_seen`: total matches inside the bounded scan window
- `last_seen`: newest matching message timestamp in the bounded scan
  window
- `per_channel`: only channels with one or more matches
- `samples`: recent matching messages serialized with
  `serialize_message(...)`

## Tradeoffs

- Bounded scans keep the command fast and predictable, but
  `total_messages_seen` and `last_seen` are only authoritative within
  the chosen per-channel window, not the entire lifetime of the guild.
- Reusing `combined_channels(guild)` keeps the design consistent with
  the rest of the CLI, but it only sees threads already present in
  `guild.threads`; it does not discover archived threads.
- Silent `discord.Forbidden` skipping keeps the command resilient and
  simple, but it can hide partial coverage. A future `skipped` field is
  the clean extension point if that becomes a problem.
- A fixed small sample cap keeps JSON compact, but it means the command
  is optimized for auditability rather than exhaustive export.
- Using `serialize_message(...)` preserves existing message formatting,
  but samples remain broader than a purpose-built "snippet" schema.
- Sorting `per_channel` by descending `count` is best for footprint
  analysis; sorting by descending `last_seen` is better for recency
  analysis. Recommendation: sort by `count` descending, then
  `last_seen` descending.

## Anti-scope

This proposal explicitly does not include:

- any Discord mutation or write behavior
- any new dependency
- any full-history scan via `limit=None`
- any archived-thread discovery via `active_threads()` or
  `archived_threads()`
- any forum-container history reads
- any new generic serializer for author-activity summaries
- any new CLI flag for sample count, sorting, or channel filtering
- any compatibility shim layer
- any caching or persistence outside the command result
- any attempt to distinguish webhook-authored messages from normal bot
  users beyond `author.id == bot_id`

## Decision

Proceed with a minimal read-only `bot-activity` command that:

- accepts `bot_id` and `--per-channel-limit`
- scans `combined_channels(guild)` filtered to history-capable types
- skips `discord.Forbidden` per channel without aborting
- returns aggregate counts, aggregate `last_seen`, per-channel
  breakdowns, and a small recent sample set

This fits the current CLI architecture without adding new infrastructure
or broadening the repo's scope.
