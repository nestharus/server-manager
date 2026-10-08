# Proposal: `discord_cli.py`

Date: 2026-04-12

## Goal

Define `discord_cli.py` as a thin, one-shot CLI around `discord.py` for inspecting the Humility guild (`<guild id>`).

The tool should:

- load `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID` from `.env`
- connect once to the Discord gateway
- resolve the configured guild
- run exactly one subcommand
- print exactly one JSON document to stdout
- exit

This proposal is intentionally limited to design. It does not include implementation code.

## Architecture

### Overall structure

Keep `discord_cli.py` as a single file with four layers:

1. `argparse` CLI definition
2. configuration and JSON utilities
3. one-shot Discord session runner
4. per-subcommand async handlers

The file stays function-oriented rather than becoming a package or framework. A small `discord.Client` subclass is acceptable if it simplifies one-shot lifecycle control, but the default shape should remain lightweight and readable.

### Recommended control flow

1. `main()` builds the parser and validates arguments.
2. Config loader reads `.env`, requiring:
   - `DISCORD_BOT_TOKEN`
   - `DISCORD_GUILD_ID`
3. Intents are built once:
   - `guilds=True`
   - `members=True`
   - `message_content=True`
4. A generic `run_gateway_command()` helper starts a client with `reconnect=False`, wrapped in `asyncio.wait_for()` with a 30-second default timeout. If the gateway does not reach readiness within the timeout, the client is closed and a `timeout_error` is returned.
5. On readiness:
   - resolve the configured guild from cache
   - reject unavailable or missing guild state
   - call the selected async handler
   - capture the result
   - close the client
6. `main()` prints a single JSON envelope to stdout and exits with status code `0` on success or non-zero on failure.

### Why this shape

- It matches the one-shot requirement cleanly.
- It keeps subcommands isolated and testable as pure async handlers over `(guild, args)`.
- It avoids building a daemon, shared state layer, or command framework that the repo does not need.

### Lifecycle details

`on_ready()` is only a readiness signal, not a business-logic home by itself. The runner should guard against duplicate execution even though reconnects are disabled, because `discord.py` documents that `on_ready()` is not guaranteed to fire only once.

Design expectation:

- disable reconnects
- wrap the gateway session in `asyncio.wait_for()` with a 30-second default timeout
- keep a `has_run` boolean or event guard
- always close the client in `finally`

### JSON contract

Use a consistent top-level envelope for every command:

```json
{
  "ok": true,
  "command": "overview",
  "guild_id": <guild id>,
  "data": {}
}
```

For failures:

```json
{
  "ok": false,
  "command": "read",
  "guild_id": <guild id>,
  "error": {
    "type": "channel_not_found",
    "message": "No channel matched 'support'",
    "details": {}
  }
}
```

This is preferable to raw dict-per-command output because downstream tools can parse one stable schema regardless of subcommand.

### Serialization rules

Flatten Discord model objects into JSON-safe primitives only:

- IDs as integers
- timestamps as ISO 8601 strings
- enums/types as strings
- nested model references reduced to small objects with stable identifiers

Do not attempt generic object dumping of `discord.py` models. Each handler should explicitly shape its own payload.

## Subcommand Specifications

## `overview`

### Purpose

Return a compact guild health snapshot.

### Inputs

- no positional arguments

### Output

`data` should contain:

- `name`
- `id`
- `owner`
- `member_count`
- `channel_count`
- `role_count`
- `boost_tier`
- `boost_count`
- `created_at`
- `unavailable`

Recommended owner shape:

```json
{
  "id": 123,
  "name": "owner#1234",
  "display_name": "Owner"
}
```

### Discord APIs

- `Client.get_guild()`
- `Guild.owner` with fallback to `Guild.fetch_member(Guild.owner_id)` if needed
- `Guild.channels`
- `Guild.roles`
- `Guild.member_count`
- `Guild.premium_tier`
- `Guild.premium_subscription_count`
- `Guild.created_at`
- `Guild.unavailable`

### Notes

`member_count` is accepted as cache-derived metadata. This is sufficient for an admin inspection CLI and avoids turning `overview` into a full member enumeration.

## `bots`

### Purpose

List bot members currently in the guild.

### Inputs

- no positional arguments

### Output

`data` should contain:

- `count`
- `bots`

Each bot entry should include:

- `id`
- `username`
- `display_name`
- `nick`
- `joined_at`
- `role_ids`
- `role_names`

### Discord APIs

- `Guild.members`
- `Member.bot`
- `Member.roles`
- `Member.joined_at`
- `Member.display_name`

### Notes

This command depends on `Intents.members`. If the privileged intent is not enabled, fail explicitly instead of returning partial data.

## `channels`

### Purpose

Expose the guild’s channel structure in a machine-readable form.

### Inputs

- no positional arguments

### Output

`data` should contain two collections:

- `channels`
- `threads`

`channels` entries should include the fields the user asked for:

- `id`
- `name`
- `type`
- `category_id`
- `category_name`
- `position`

Recommended additional fields:

- `parent_id` as `null` for normal guild channels
- `nsfw` when present
- `topic` for text/forum channels when present

`threads` should be separate because Discord models them differently from guild channels. Each thread entry should include:

- `id`
- `name`
- `type`
- `parent_id`
- `parent_name`
- `category_id`
- `category_name`

### Discord APIs

- `Guild.channels`
- `Guild.threads`
- channel attributes such as `id`, `name`, `position`, `category`, `type`

### Notes

Separating `threads` from `channels` keeps the primary output aligned with Discord’s guild channel tree while still surfacing thread state for later automation.

## `find-channel <name>`

### Purpose

Find channels or threads by case-insensitive name substring.

### Inputs

- required positional `name`

### Output

`data` should contain:

- `query`
- `count`
- `matches`

Each match should include:

- `id`
- `name`
- `type`
- `kind` with value `channel` or `thread`
- `category_id`
- `category_name`
- `parent_id`
- `parent_name`
- `position` when applicable

### Match behavior

- case-insensitive substring search
- scan both `Guild.channels` and `Guild.threads`
- sort exact case-insensitive matches first, then substring matches, then by position/name

### Discord APIs

- `Guild.channels`
- `Guild.threads`

### Notes

This command is intentionally a discovery tool, not a strict resolver. It should return multiple matches rather than failing on ambiguity.

## `read <channel> [--limit N]`

### Purpose

Read recent message history from a target channel or thread.

### Inputs

- required positional `channel`
- optional `--limit N`

### Channel resolution

Resolve in this order:

1. if `channel` parses as an integer, try direct lookup by ID
2. exact case-insensitive name match across channels and threads
3. substring match across channels and threads
4. fail with `channel_not_found` or `channel_ambiguous`

If ambiguous, return a structured error that includes candidate matches. Do not silently pick one.

### Limit behavior

- default: `50`
- reject `N <= 0`
- cap at a modest upper bound such as `200` to keep JSON output predictable

### Output

`data` should contain:

- `channel`
- `limit`
- `message_count`
- `messages`

`channel` should include:

- `id`
- `name`
- `type`
- `category_id`
- `category_name`
- `parent_id`
- `parent_name`

Each message should include:

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

Recommended author shape:

```json
{
  "id": 123,
  "name": "user#1234",
  "display_name": "User",
  "bot": false
}
```

Recommended attachment shape:

- `id`
- `filename`
- `content_type`
- `size`
- `url`

For `embeds`, return a summary only:

- `title`
- `url`
- `type`

### Ordering

Fetch with `history(limit=N)` and return messages oldest-to-newest within the selected window. Chronological output is easier for downstream analysis than Discord’s default newest-first iterator order.

### Discord APIs

- `Guild.get_channel()`, `Guild.get_thread()` or equivalent lookup against cached collections
- `abc.Messageable.history()`
- `Message.author`
- `Message.attachments`
- `Message.embeds`
- `Message.jump_url`

### Notes

The gathered docs do not establish `message_content` intent as a requirement for `history()`, but keeping it enabled is still reasonable because the user explicitly wants that intent on the bot and it reduces future surprises.

## `integrations`

### Purpose

List guild integrations for diagnosis of broken or stale configuration.

### Inputs

- no positional arguments

### Output

`data` should contain:

- `count`
- `integrations`

Each integration entry should include:

- `id`
- `name`
- `type`
- `enabled`
- `account`
- `user`
- `application_id` when available

Recommended account shape:

```json
{
  "id": "external-account-id",
  "name": "support"
}
```

Recommended user shape:

- `id`
- `name`

### Discord APIs

- `Guild.integrations()`
- `Integration.id`
- `Integration.name`
- `Integration.type`
- `Integration.enabled`
- `Integration.account`
- `Integration.user`

### Notes

`enabled` is useful but not sufficient to explain every broken integration. This command should present state, not diagnose root cause.

## Error Handling Strategy

### Principles

- print exactly one JSON object to stdout on every exit path
- use exit codes for shell-level success/failure
- do not print mixed human logs alongside JSON
- convert common Discord failures into stable CLI error types

### Error categories

Recommended error mapping:

- `config_error`
  - missing token
  - missing guild ID
  - non-integer guild ID
- `login_error`
  - bad token
  - gateway authentication failure
- `timeout_error`
  - gateway did not reach readiness within the configured timeout (default 30s)
- `intent_error`
  - privileged intents not enabled
  - invalid/disallowed intents
- `guild_not_found`
  - bot is not in the configured guild
- `guild_unavailable`
  - guild exists but is temporarily unavailable
- `permission_denied`
  - missing Discord permissions such as `manage_guild` or `read_message_history`
- `channel_not_found`
  - no match for `read` target
- `channel_ambiguous`
  - multiple plausible matches for `read` target
- `http_error`
  - Discord API failures not covered above
- `internal_error`
  - unexpected exceptions

### Error payload shape

At minimum:

- `type`
- `message`
- `details`

Examples of useful `details`:

- Discord HTTP status code
- Discord resource code when available
- requested channel selector
- candidate matches for ambiguity

### Exit codes

Keep exit codes simple:

- `0` success
- `1` configuration or usage failure
- `2` Discord/auth/permission/runtime failure

This is enough for shell automation without inventing a large exit-code taxonomy.

## Anti-Scope

This tool is not:

- a long-running daemon
- a multi-guild management layer
- a general Discord SDK wrapper
- a database-backed cache
- an interactive REPL or TUI
- a job queue or background worker
- a full moderation framework
- a write-heavy admin console in the first version
- a compatibility layer for prior CLI output formats

It should also not:

- persist guild state locally
- hide ambiguity by guessing
- emit human-oriented prose by default
- add feature flags to toggle behavior that can be expressed directly in code

## Tradeoffs Considered

### One-shot gateway session vs daemon

Chosen: one-shot session.

Reason:

- simpler operational model
- easier to trust in agent sessions
- no background process management
- matches the user’s explicit preference for a local CLI, not a persistent service

Cost:

- each invocation pays connection startup latency
- repeated calls are less efficient than a resident process

### Single file vs package layout

Chosen: single file.

Reason:

- the command set is small
- the repo explicitly wants a lightweight tool
- lower navigation overhead for future agent sessions

Cost:

- less room for deep abstraction
- handlers and serializers must stay disciplined to avoid clutter

### Stable JSON envelope vs per-command ad hoc output

Chosen: stable envelope.

Reason:

- easier downstream automation
- success and error paths become uniform
- future subcommands can extend `data` without breaking shell glue

Cost:

- slightly more verbose output
- humans reading stdout see one extra wrapper object

### Cached guild state vs fetch-heavy design

Chosen: mostly cached state, with explicit fetches only where needed.

Reason:

- `overview`, `bots`, `channels`, and `find-channel` naturally fit cached guild data after readiness
- `integrations()` and message history are already explicit API calls
- this keeps the tool predictable and avoids unnecessary HTTP traffic

Cost:

- some values such as `member_count` are only as accurate as Discord’s cache semantics
- owner resolution may still need a fallback fetch

### Name-friendly selectors vs ID-only selectors

Chosen: support both, with explicit ambiguity errors.

Reason:

- names are ergonomic for interactive admin use
- IDs are precise for automation
- ambiguity reporting is safer than implicit guesses

Cost:

- resolver logic is slightly more complex
- users must disambiguate some common names manually

### Enabling `message_content` intent now

Chosen: yes.

Reason:

- it is already a stated requirement
- the user enabled it in the bot configuration
- it avoids future confusion if the CLI later expands into message inspection beyond `history()`

Cost:

- privileged scope is broader than the minimum established by the current `read` design

## Proposed Outcome

`discord_cli.py` should remain a small, explicit, one-shot admin CLI with:

- one parser
- one config path
- one gateway runner
- one JSON envelope
- one async handler per subcommand

That gives the repo a reusable inspection surface without committing it to a larger architecture than the problem warrants.
