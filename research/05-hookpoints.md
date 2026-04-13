# Hookpoint Research: Discord CLI Tool

Date: 2026-04-12

## 1. Existing code inventory

`discord_cli.py` already exists and is the only Python file in the repo.

What is implemented now:

- CLI entrypoint with `argparse` subparsers in `build_parser()` ([discord_cli.py](/home/nes/discord/discord_cli.py:119)).
- `.env` loading at import time via `load_dotenv(ENV_PATH)` with a hardcoded absolute path to `/home/nes/discord/.env` ([discord_cli.py](/home/nes/discord/discord_cli.py:22), [discord_cli.py](/home/nes/discord/discord_cli.py:24)).
- Config validation for `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID` in `get_config()` ([discord_cli.py](/home/nes/discord/discord_cli.py:37)).
- Shared intent construction in `build_intents()` with `members=True` and `message_content=True`; `guilds` is implicitly on through `Intents.default()` ([discord_cli.py](/home/nes/discord/discord_cli.py:54)).
- One-shot gateway execution in `run_gateway_command()` using `discord.Client`, `on_ready()`, cached guild lookup, handler invocation, and client shutdown ([discord_cli.py](/home/nes/discord/discord_cli.py:61)).
- One working handler path for `overview`: `cmd_overview()` -> `run_gateway_command(fetch_overview)` -> JSON print ([discord_cli.py](/home/nes/discord/discord_cli.py:88), [discord_cli.py](/home/nes/discord/discord_cli.py:108)).

What is stubbed:

- `bots`
- `channels`
- `find-channel`
- `read`
- `integrations`

All five stubs route to `cmd_not_yet_implemented()`, which prints the JSON string `"not yet implemented"` and exits `0` ([discord_cli.py](/home/nes/discord/discord_cli.py:114), [discord_cli.py](/home/nes/discord/discord_cli.py:126)).

What works vs the approved proposal:

- The current file already matches the intended single-file shape: CLI parser, config helpers, gateway runner, and per-command handlers.
- The current `overview` logic proves the gateway session model works for a one-shot command.
- The current output contract does not match the proposal. It prints raw command payloads rather than a stable top-level envelope, and failures print plain text to `stderr` instead of one JSON object to `stdout` ([discord_cli.py](/home/nes/discord/discord_cli.py:33), [discord_cli.py](/home/nes/discord/discord_cli.py:147)).
- The current parser does not yet model command-specific arguments such as `find-channel <name>` or `read <channel> [--limit N]`.

## 2. Reuse opportunities

Code worth keeping and extending:

- `get_config()` is a valid base for config loading and type validation. It already enforces the two required env vars and integer guild ID.
- `build_intents()` should remain the central place to define bot intents. It already aligns with the proposal's need for `members=True` and `message_content=True`.
- `run_gateway_command()` is the main hookpoint for all future subcommands. Its current responsibilities match the proposal closely: load config, create client, wait for readiness, resolve guild, invoke a handler, close the session.
- `fetch_overview()` is reusable as a starting point for the `overview` handler. The guild owner fallback through `guild.fetch_member(guild.owner_id)` is a useful pattern to preserve.
- `build_parser()` should remain the CLI definition hub. The current subparser pattern is the right structure for adding command-specific arguments and async handlers.
- `json_default()` is a useful serializer hook for `datetime` values and can stay as the default encoder entrypoint.

Patterns to preserve from the current code:

- One-shot gateway lifecycle instead of a daemon process.
- Function-oriented layout inside a single file rather than a package split.
- Shared runner plus small per-command handlers.
- JSON-only stdout for successful command execution.

Shared utility patterns that can support multiple subcommands:

- Serializer helpers for Discord objects:
  - owner/member summary
  - channel/thread summary
  - message summary
  - integration summary
- Channel/thread collection helpers:
  - iterate channels and threads together
  - resolve channel by ID or name
  - normalize category/parent metadata
- Envelope/error helpers:
  - `success_payload(command, guild_id, data)`
  - `error_payload(command, guild_id, error_type, message, details)`

## 3. Implementation gaps

Subcommands that still need real implementations:

- `bots`
- `channels`
- `find-channel`
- `read`
- `integrations`

Missing command arguments and parser behavior:

- `find-channel` needs required positional `name`.
- `read` needs required positional `channel` and optional `--limit`.
- Validation for `read --limit` does not exist yet.

Current code gaps against the approved proposal:

- No stable JSON envelope.
  - Current success output is raw command data.
  - Current failure output is plain text to `stderr`.
- No structured error taxonomy such as `config_error`, `guild_not_found`, `channel_ambiguous`, or `permission_denied`.
- No duplicate-execution guard in `on_ready()`.
  - The proposal explicitly wants a `has_run` or equivalent guard even with reconnects disabled.
- `client.start(token)` is called with the default reconnect behavior instead of `reconnect=False` ([discord_cli.py](/home/nes/discord/discord_cli.py:80)).
- No explicit `guild.unavailable` handling before business logic runs.
- `overview` payload shape diverges from the proposal:
  - uses `boost_level` instead of `boost_tier`
  - uses `created_date` instead of `created_at`
  - omits `boost_count`, `unavailable`, and `owner.display_name`
- No shared serializers yet for members, channels, threads, messages, or integrations.
- No channel/thread resolver for `find-channel` and `read`.
- No message-history shaping for `read`.
- No integration fetch path for `integrations`.

Current `.env` and configuration state:

- `discord_cli.py` loads `.env` immediately at module import from a fixed absolute path.
- The config surface is limited to:
  - `DISCORD_BOT_TOKEN`
  - `DISCORD_GUILD_ID`
- The local `.env` file currently contains both required keys.
- There is no abstraction for alternate env paths, delayed loading, or test injection.

## 4. Deletion candidates

Clear replacement targets:

- `cmd_not_yet_implemented()` should go once real handlers exist. Its `"not yet implemented"` string is not compatible with the proposal's envelope contract ([discord_cli.py](/home/nes/discord/discord_cli.py:114)).
- The stub parser loop can stay structurally, but its current `set_defaults(func=cmd_not_yet_implemented)` wiring is temporary and should be replaced per command ([discord_cli.py](/home/nes/discord/discord_cli.py:126)).
- Raw `stderr` exception printing in `main()` is a mismatch for the proposal and should be replaced by JSON error emission ([discord_cli.py](/home/nes/discord/discord_cli.py:147)).

Likely rewrite rather than preserve as-is:

- `fetch_overview()` should be kept conceptually but revised to emit the approved field names and envelope shape.
- `print_json()` likely stays, but its caller contract needs to change from "print arbitrary payload" to "print exactly one success or error envelope".
- The hardcoded `ENV_PATH` may still be acceptable locally, but it is the main configuration coupling point if the implementation wants a less rigid env-loading path later.

## 5. Parallel opportunities

Subcommands that can share the same helper layer:

- `channels`, `find-channel`, and `read` can all share one channel/thread enumeration and serialization path.
- `overview` and `bots` can share member-summary shaping, especially owner/bot display fields.
- `find-channel` and `read` can share one resolver that:
  - tries ID lookup
  - scans exact case-insensitive names
  - falls back to substring matching
  - returns ambiguity candidates in a reusable structure
- `overview`, `bots`, `channels`, and `integrations` can all reuse the same top-level success/error envelope builder.

Implementation work that can proceed independently once the shared base exists:

- `bots` handler
- `channels` handler
- `integrations` handler

Implementation work that should be sequenced after shared helpers land:

- `find-channel` after channel/thread serializer helpers exist
- `read` after channel resolution and message serialization helpers exist

Net mapping:

- Reuse the existing file structure, config loader, intent builder, gateway runner skeleton, and parser pattern.
- Replace the stub command wiring, raw payload output, and plain-text error handling.
- Build fresh shared serializers and channel resolution utilities, because those are the missing hookpoints every non-`overview` subcommand depends on.
