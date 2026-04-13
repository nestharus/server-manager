# Proposal: `daemon.py`

Date: 2026-04-13

## Goal

Define the design for `daemon.py` as the daemon entry point for the
Humility Discord bot.

This proposal is design only. It does not include implementation code.

## Summary

`daemon.py` should be a thin orchestration module around a small
`discord.ext.commands.Bot` subclass.

Its job is:

- load local environment variables from `.env`
- validate `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID`
- load repo-managed config from `chapters.yaml` plus `forms/<slug>.yaml`
- resolve and open the SQLite database
- boot a long-running Discord gateway client with the required intents
- register and sync one minimal guild-scoped slash command
- shut down cleanly and close the database connection

The entry point should not contain application flow logic, ticket
workflow logic, chapter provisioning, or any broad service framework.
It is an orchestration boundary, not a feature module.

## Runtime Shape

`daemon.py` should own exactly one runtime path:

1. Resolve repo-local environment and base paths.
2. Load config.
3. Open the database.
4. Construct the bot.
5. Register minimal application-command scaffolding.
6. Start the gateway connection.
7. On termination, close the bot and database cleanly.

The file should stay small and top-level. It should import reusable
behavior from `daemon.config` and `daemon.db` rather than reimplementing
those concerns.

## Environment And Paths

The entry point should follow the same local environment convention as
`discord_cli.py`.

### Environment file

- load `.env` from `Path(__file__).with_name(".env")`
- require `DISCORD_BOT_TOKEN`
- require `DISCORD_GUILD_ID`
- treat `DATABASE_PATH` as optional; when unset, default to
  `base_path / "discord.db"` (see Database Path Resolution)

Validation rules:

- missing token is a startup error
- missing guild ID is a startup error
- non-integer guild ID is a startup error

### Base path for repo-managed config

`daemon.py` should resolve the config base path as the repository root,
not from the current working directory.

Concretely, it should use:

- `Path(__file__).resolve().parent`

That base path is then passed to `daemon.config.load_config()`, which
already owns loading `chapters.yaml` and the chapter-linked
`forms/<slug>.yaml` files.

This keeps startup stable whether the daemon is launched from the repo
root, from Railway, or from another working directory.

## Bot Surface

The daemon entry point should use `discord.ext.commands.Bot`, not a raw
`discord.Client`.

Reasoning:

- the requirements explicitly call for a Bot entry point
- slash-command support is part of the bot surface already
- the daemon will eventually own interactions, even though this scaffold
  only registers a minimal command

The bot should still be slash-first:

- no text-command feature work
- no message event handlers
- no application/ticket modules loaded yet
- use a benign required prefix such as `commands.when_mentioned`, while
  treating prefix commands as unsupported

### Minimal subclass

The cleanest shape is a small bot subclass dedicated to startup-owned
state.

It should carry:

- `guild_id: int`
- loaded daemon config
- opened SQLite connection
- optionally the repo base path if later modules need it

The subclass should also own `setup_hook()` so command registration and
guild sync happen in the Discord client lifecycle rather than in module
top-level code.

This keeps runtime state explicit and avoids globals such as
`BOT = ...`, `DB = ...`, or `CONFIG = ...`.

## Intents

The daemon should build intents from `discord.Intents.default()` and
then enable:

- `guilds = True`
- `members = True`

It should not enable `message_content` in this scaffold.

### Why `guilds`

The daemon is scoped to one guild and is built around guild channels,
threads, and slash commands. `guilds` is the baseline intent for that
surface.

### Why `members`

The planned daemon design already depends on member-aware behavior:

- thread membership changes in `daemon.claim`
- chapter role work later in applications and provisioning
- handler/member resolution for future queue flows

Even though this scaffold does not implement those workflows yet, the
daemon entry point should start with the member intent enabled so its
runtime shape matches the planned feature set.

### Why not `message_content`

The scaffold entry point only needs:

- gateway connection
- slash commands
- config loading
- database access

No current scaffold requirement depends on reading message bodies or
handling `on_message`. Enabling only the intents directly implied by the
daemon design keeps the initial bot closer to least privilege.

If a later partition adds message-command or message-content-driven
behavior, enabling `message_content` then is a small, isolated change.

## Startup Order

Startup should be strict and fail fast.

### Recommended sequence

1. Load `.env`.
2. Read and validate `DISCORD_BOT_TOKEN`.
3. Read and parse `DISCORD_GUILD_ID`.
4. Resolve the repo base path as `Path(__file__).resolve().parent`.
5. Call `daemon.config.load_config(base_path)`.
6. Resolve the database path: if `DATABASE_PATH` is set, use it
   directly; otherwise use `base_path / "discord.db"` to keep the
   default anchored to the repo root, not the process cwd.
7. Open the database with `daemon.db.open_database(db_path)`. This
   sets WAL mode AND `busy_timeout = 5000` (see Shared SQLite
   Concurrency Policy).
8. Construct the bot with the resolved intents and startup-owned state.
9. Start the bot and block on the Discord connection.
10. On `on_ready`, validate guild reachability and members intent (see
    Guild Readiness Validation).

### Failure behavior

- config load failure should abort before any Discord connection attempt
- database open/bootstrap failure should abort before any Discord
  connection attempt
- bot login/connect failures should still trigger database cleanup if
  the connection has already been opened

That order keeps startup deterministic and prevents a half-booted daemon
from connecting to Discord without validated local state.

## Slash Command Scaffolding

The scaffold should register exactly one minimal slash command so the
daemon can prove it is alive and synced.

### Command shape

Recommended command:

- `/ping`

Recommended behavior:

- reply ephemerally with a small success message such as "pong" or
  "daemon is alive"

The command should remain intentionally narrow. It is a readiness check,
not a feature surface.

### Guild scoping

Commands should be scoped to the configured Humility guild rather than
registered globally.

That means:

- bind the command to `discord.Object(id=guild_id)` or the equivalent
  guild-scoped app-command API
- sync the tree for that guild in `setup_hook()`

Guild-only sync is the correct default here because:

- the repo is explicitly single-guild
- guild-scoped commands propagate quickly
- there is no need to publish global commands for a one-guild daemon

## Lifecycle And Shutdown

`daemon.py` should manage the asyncio lifecycle itself instead of using
`bot.run(...)` as the entire control plane.

### Why not `bot.run()`

`bot.run()` is convenient, but the daemon entry point has a concrete
resource-cleanup requirement: the SQLite connection must be closed
reliably.

A small explicit async `main()` is a better fit because it gives the
entry point:

- deterministic startup ordering
- an obvious `try`/`finally` boundary around the database connection
- a place to install graceful termination behavior

### Recommended runtime wrapper

The proposal should use:

- `asyncio.run(main())` at process entry
- `async with bot:` plus `await bot.start(token)` inside `main()`
- `try`/`finally` so `daemon.db.close_database(conn)` always runs after
  the bot stops, if the DB was opened successfully

### Signal handling

The entry point should support graceful termination for normal daemon
hosting.

Recommended behavior:

- install `SIGINT` and `SIGTERM` handlers when the platform allows it
- on signal, request bot shutdown rather than hard-exiting immediately
- let shutdown flow through normal Discord client close semantics
- then close the database in `finally`

This is enough for the scaffold. It does not need a broader supervisor,
task registry, or background-worker shutdown protocol.

## Logging And Error Reporting

The entry point should emit clear operator-facing startup failures, but
it does not need a full logging subsystem in the first pass.

Minimum expectation:

- startup errors should identify whether failure came from env parsing,
  config loading, DB initialization, or Discord startup
- failures should exit non-zero

Detailed structured logging and metrics are outside the scaffold scope.

## Production Health Signal

### Decided: process liveness is sufficient for all scaffold-era partitions

Railway restarts containers when the process exits. For the scaffold and
all partitions where the daemon is stateless beyond the gateway
connection (no background tasks, no queues, no timers), process
liveness IS the health signal:

- Process running + gateway connected = healthy
- Process exited = Railway restarts it

No HTTP health endpoint is needed while the daemon has no background
work that can fail silently. The gateway connection itself is the
liveness probe — if the bot disconnects, discord.py's `reconnect=True`
retries; if reconnection fails permanently, the process exits, and
Railway restarts it.

### When HTTP health becomes required

The first partition that adds background work which can fail without
crashing the process (a queue consumer, a scheduled task, a polling
loop) must add an HTTP health endpoint that reports whether that work
is alive. This is a blocking prerequisite for that partition, not a
follow-up. Until then, process liveness is the decided health model.

## Guild Readiness Validation

The scaffold should validate that the configured guild is reachable and
that the `members` intent is functional. This validation belongs in
`on_ready`, not `setup_hook`, because the gateway must be connected and
the guild cache populated before the check is meaningful.

### Validation behavior

In `on_ready`, the bot should:

1. Look up the guild via `bot.get_guild(guild_id)`.
2. If the guild is not in cache, log a clear error identifying that the
   bot either lacks access or the guild ID is wrong, then shut down.
3. If the guild is in cache, check `guild.chunked`. If not chunked and
   `guild.member_count` is available, request chunking via
   `guild.chunk()`.
4. Log a startup-complete message with the guild name and member count.

This catches three operational traps early:

- Bot invited to wrong guild or guild ID misconfigured
- `members` intent not approved in the Discord developer portal
- Gateway not delivering member data despite intent being set in code

Without this check, the daemon could pass `/ping` while being silently
broken for every future handler that needs member resolution.

## Tradeoffs

### Benefits

- Keeps `daemon.py` narrowly focused on orchestration.
- Reuses `daemon.config` and `daemon.db` instead of duplicating logic.
- Uses the correct `Bot` surface for slash-command growth.
- Starts with the minimal intents required by the planned daemon shape.
- Uses guild-scoped slash-command sync, which fits the single-guild
  repo design.
- Makes database cleanup explicit and reliable.
- Makes binding architectural decisions (concurrency, async DB, health)
  up front instead of deferring them.
- Validates guild and members intent at startup, catching
  misconfiguration before real handlers land.

### Costs

- A custom async `main()` is slightly more code than `bot.run(...)`.
- A `Bot` subclass introduces a small amount of structure up front.
- Not enabling `message_content` means future message-driven features
  will need one intent change later.
- The scaffold exposes only a health-style slash command, so it does not
  yet prove any real application or ticket workflow.
- `on_ready` guild validation adds a small amount of startup logic
  beyond the minimum `/ping` scaffold.

Those costs are acceptable because the goal of this partition is a clean
entry-point scaffold that makes its architectural commitments explicit
rather than deferring them.

## Prerequisites

This partition depends on modules and config files that must already
exist in the tree before `daemon.py` can be implemented:

- `daemon/__init__.py` — package marker (partition 13)
- `daemon/config.py` — config loader (partition 14)
- `daemon/db.py` — database layer (partition 15)
- `daemon/claim.py` — claim helpers (partition 16)
- `chapters.yaml` — chapter registry at repo root (partition 10)
- `forms/dark-nemesis.yaml` — at least one form file (partition 10)

All of these exist in the current working tree.

## Database Path Resolution

When `DATABASE_PATH` is not set, `daemon.db.resolve_database_config()`
defaults to a cwd-relative `discord.db`. For the daemon entry point,
the default path should be anchored to the repo base path rather than
the process working directory.

`daemon.py` should resolve the default database path as:

- `base_path / "discord.db"` where `base_path` is
  `Path(__file__).resolve().parent`

This ensures that the daemon creates or opens the database in the same
location regardless of how the process is launched.

**Important:** `daemon.py` must NOT call `daemon.db.resolve_database_config()`
for the unset case. That helper returns a cwd-relative `Path("discord.db")`
which would silently break the repo-root anchoring. Instead, the daemon
should read `os.environ.get("DATABASE_PATH")` directly:

- if set, use the value as the database path
- if unset, use `base_path / "discord.db"`

Then pass the resolved path to `daemon.db.open_database(db_path)`.

## Shared SQLite Concurrency Policy

The daemon design specifies that `daemon.py` and `discord_cli.py` share
one SQLite database. This section states the concurrency decisions that
govern all partitions, not just this scaffold.

### Decided: WAL + busy_timeout in the DB layer

`open_database()` already enables WAL mode. This proposal requires
`open_database()` to also set `PRAGMA busy_timeout = 5000` immediately
after enabling WAL. This makes the DB layer safe for concurrent readers
and short-duration write contention by default — every caller that opens
through `open_database()` inherits the timeout. No individual module
needs to remember to set it.

### Decided: single-writer constraint

Until an explicit multi-writer policy is designed and risk-assessed,
only one process may hold an open write transaction at a time. In
practice, this means:

- The CLI performs provisioning writes while the daemon is not running,
  OR
- The daemon performs writes during normal operation while the CLI is
  limited to read-only queries.

The first partition that requires true concurrent writes from both
processes must specify transaction boundaries, commit ownership, and
retry semantics before implementation. This is a blocking prerequisite,
not a follow-up.

### Decided: async wrapping for interaction handlers

All DB calls from interaction handlers (slash commands, buttons, modals)
MUST use `asyncio.to_thread(fn, ...)` to avoid blocking the event loop.
This is the architectural decision — not a question to resolve later.
The scaffold does not invoke any DB helpers from handlers (`/ping` does
not touch the database), so no wrapping is needed yet. But the pattern
is set: when the first handler partition lands, it wraps DB calls in
`asyncio.to_thread()`.

### Scaffold write posture

In this partition, the daemon performs exactly one write operation: the
schema bootstrap (`CREATE TABLE IF NOT EXISTS`) inside `open_database()`.
This runs at startup before the bot connects to the gateway, so there is
no concurrent-access window with the CLI. After startup, the daemon
holds the connection open but does not call any `daemon.db` write
helpers — it serves `/ping` only.

## Anti-scope

`daemon.py` should not implement any of the following in this partition:

- application submission flow
- ticket flow
- chapter provisioning
- button views or modal classes
- claim orchestration beyond importing shared helpers later
- SQLite workflow queries beyond opening and closing the connection
- config hot-reload
- background tasks, schedulers, or polling loops
- admin CLI commands
- message-command handlers
- message-content event handlers

In particular, the database is opened and ready, but this scaffold does
not need to read or write `submissions`, `tickets`, or `chapter_blacklist`
records yet.

## Decision

`daemon.py` should be implemented as a thin async entry point around a
small `commands.Bot` subclass.

It should:

- load `.env` from the repo root
- validate the Discord token and guild ID
- load repo-managed YAML config via `daemon.config.load_config()`
- resolve and open SQLite via `daemon.db` (which sets WAL +
  `busy_timeout = 5000`)
- boot a bot with `guilds` and `members` intents
- register and guild-sync one `/ping` slash command
- validate guild reachability and members intent in `on_ready`
- run until terminated, relying on process liveness as the health signal
- always close the SQLite connection on shutdown

Architectural decisions made in this proposal that bind future partitions:

- **Single-writer constraint**: only one process writes at a time until
  a multi-writer policy is designed and risk-assessed
- **Async DB wrapping**: all DB calls from interaction handlers use
  `asyncio.to_thread()`
- **Process liveness health**: no HTTP endpoint until background work
  that can fail silently is added
- **`busy_timeout` in DB layer**: `open_database()` sets it, not callers

That design satisfies the scaffold requirements while making the
architectural decisions that prevent deferred shortcuts from accumulating
in future partitions.
