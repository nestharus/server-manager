# Research: `daemon.py` Daemon Entry Point

Date: 2026-04-13

## Scope

This note documents the current problem space for the planned
`daemon.py` entry point.

It is limited to:

- what the repo says the entry point is responsible for
- what `discord.py` exposes for a long-running gateway client
- which gateway intents are directly implied by the planned features
- how slash commands are registered in `discord.py`
- what shutdown and environment-loading surfaces exist
- what the current one-shot CLI already does that the daemon can be
  compared against

It does not propose an implementation.

## Local Baseline

- The daemon design defines `daemon.py` as the top-level entry point
  that boots the long-running process, loads config, and registers
  handlers
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:3),
  [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:10)).
- The design says the daemon is a long-running `discord.py` process on
  Railway with a persistent gateway connection and SQLite on a Railway
  volume
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:3),
  [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:167)).
- The daemon, not the CLI, is planned to handle slash commands, buttons,
  and modals
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:193)).
- The repo already contains supporting modules for YAML config, SQLite,
  and claim visibility:
  [daemon/config.py](/home/nes/discord/daemon/config.py:1),
  [daemon/db.py](/home/nes/discord/daemon/db.py:1),
  [daemon/claim.py](/home/nes/discord/daemon/claim.py:1).
- [pyproject.toml](/home/nes/discord/pyproject.toml:5) sets Python
  `>=3.12` and depends on `discord.py>=2.3`,
  `python-dotenv`, `aiohttp`, and `PyYAML`
  ([pyproject.toml](/home/nes/discord/pyproject.toml:6)).
- Local runtime inspection in this repo on 2026-04-13 resolves
  `discord.py 2.7.1`.
- The current repo does not yet contain a top-level `daemon.py` file.

## Primary Sources

- Local repo files:
  - [AGENTS.md](/home/nes/discord/AGENTS.md:1)
  - [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:1)
  - [daemon/config.py](/home/nes/discord/daemon/config.py:1)
  - [daemon/db.py](/home/nes/discord/daemon/db.py:1)
  - [daemon/claim.py](/home/nes/discord/daemon/claim.py:1)
  - [discord_cli.py](/home/nes/discord/discord_cli.py:1)
  - [pyproject.toml](/home/nes/discord/pyproject.toml:1)
- Official `discord.py` docs:
  - `Client` lifecycle and intents:
    https://discordpy.readthedocs.io/en/latest/api.html
  - application commands:
    https://discordpy.readthedocs.io/en/latest/interactions/api.html
- Official Python docs:
  - `asyncio` event loop signal handlers:
    https://docs.python.org/3.12/library/asyncio-eventloop.html
  - `signal`:
    https://docs.python.org/3.12/library/signal.html
- Local runtime inspection:
  - `inspect.signature()` / `inspect.getdoc()` on
    `discord.Client.start`, `login`, `close`, `run`, `setup_hook`,
    `discord.app_commands.CommandTree`, `CommandTree.sync`,
    `discord.app_commands.guilds`, `discord.app_commands.command`,
    `discord.Guild.fetch_members`, and `dotenv.load_dotenv`
  - installed `discord/flags.py` source for `Intents.default`,
    `Intents.guilds`, `Intents.members`, and `Intents.message_content`

## 1. What the entry point owns in this repo

The design doc gives `daemon.py` a narrow but central role:

- boot one long-running Discord client
- load repo-managed YAML config
- initialize SQLite
- register interaction handlers
- remain connected and wait for interactions

Those responsibilities are explicit in the design’s file map and hosting
notes
([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:7),
[docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:167)).

The supporting modules already divide some of that surface:

- [daemon/config.py](/home/nes/discord/daemon/config.py:117) loads
  `chapters.yaml` and `forms/<slug>.yaml` into immutable dataclasses.
- [daemon/db.py](/home/nes/discord/daemon/db.py:79) resolves
  `DATABASE_PATH` and
  [daemon/db.py](/home/nes/discord/daemon/db.py:101) opens and
  bootstraps SQLite.
- [daemon/claim.py](/home/nes/discord/daemon/claim.py:35) and
  [daemon/claim.py](/home/nes/discord/daemon/claim.py:65) already
  expose async helpers around private-thread membership changes.

So the entry-point problem space is orchestration, process lifetime, and
Discord client lifecycle rather than YAML parsing or SQL schema details.

## 2. `discord.py` client setup for a long-running daemon

`discord.py` exposes two main client surfaces relevant here:

- `discord.Client`
- `discord.ext.commands.Bot`

The current CLI uses plain `discord.Client`
([discord_cli.py](/home/nes/discord/discord_cli.py:440)).

Local `discord.py 2.7.1` doc/runtime facts:

- `Client.start(token, reconnect=True)` is a coroutine shorthand for
  `login` plus `connect`.
- `Client.login(token)` logs in the client and calls `setup_hook`.
- `Client.connect()` owns the websocket loop and does not return until
  the websocket connection is terminated.
- `Client.close()` closes the connection to Discord.
- `Client.run(...)` is a blocking convenience wrapper that manages the
  event loop for you.
- `Client.setup_hook()` runs after login but before the websocket is
  connected, is called once, and the docs warn that waiting for websocket
  readiness there can deadlock.

The lifecycle distinction matters because the design is for a persistent
daemon rather than a one-shot command. The official `Client.run()` docs
say it is a blocking helper and should be the last call, while the
official `Client.start()` docs leave loop ownership to the caller.

`discord.ext.commands.Bot` also matters even though the current CLI does
not use it. In local `discord.py 2.7.1`, the `Bot` constructor includes
`tree_cls=<class 'discord.app_commands.tree.CommandTree'>`, which means
application-command support is part of the bot surface by default. The
lower-level alternative is the documented
`discord.app_commands.CommandTree(client)`, which takes a `Client`
instance and acts as the container for slash-command metadata.

Problem-space implication:

- the current repo baseline is a plain `Client`
- the planned daemon needs application-command handling
- `discord.py` supports that either through a `Bot` convenience surface
  or through a `Client` paired with `CommandTree`

## 3. Intents implied by the planned features

The installed `discord.py` source says `Intents.default()` enables
everything except `presences`, `members`, and `message_content`.

The three intent flags directly relevant to the daemon design are:

### `guilds`

The installed `discord.py` source says `Intents.guilds` covers guild
events, thread events, guild/channel cache, `Client.guilds`,
`Guild` objects, and `Client.get_channel`, and calls it "highly
advisable" for the bot to function.

That maps directly to the current design:

- the bot is scoped to one guild
- the design is built around channels, private threads, and slash
  commands inside that guild
- the current CLI resolves guilds, channels, and threads from cache
  ([discord_cli.py](/home/nes/discord/discord_cli.py:356),
  [discord_cli.py](/home/nes/discord/discord_cli.py:452))

### `members`

The installed `discord.py` source says `Intents.members` is what enables
member-related events plus `Guild.fetch_members`, `Guild.get_member`,
`Guild.members`, and member role/nick cache fields.

That intent is directly implied by several planned behaviors:

- queue setup adds every member of the handler role to a private thread
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:47))
- claim preserves admins and removes other explicit members
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:49))
- approvals mutate chapter roles
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:50))
- chapter provisioning clones and wires chapter-specific roles
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:65))

The existing CLI already treats member cache as an intent-sensitive
surface: [discord_cli.py](/home/nes/discord/discord_cli.py:500) raises an
`intent_error` if `guild.members` is empty while the guild still reports
members.

The official `Guild.fetch_members()` docs are explicit that
`Intents.members` must be enabled.

### `message_content`

The installed `discord.py` source says `Intents.message_content` affects
message content, attachments, embeds, and components for message events
such as `on_message`, `on_message_edit`, and `on_message_delete`, except
for some narrow cases like the bot’s own messages, DMs, and mentions.

That is narrower than the current CLI baseline, which enables
`message_content`
([discord_cli.py](/home/nes/discord/discord_cli.py:67)).

For the scaffold-only daemon described here, the design is centered on:

- slash commands
- buttons
- modals
- private threads

Those are interaction surfaces, not message-content event handlers.
Nothing in the current design doc says the daemon must implement
`on_message` or parse arbitrary guild message text.

Problem-space implication:

- `guilds` is directly implied
- `members` is directly implied
- `message_content` is part of the current CLI inspection pattern but is
  not directly implied by the interaction-first daemon design as written

No current design evidence directly points to `presences`,
`moderation`, or the message-event intents as required for the
scaffold-only entry point.

## 4. Slash-command registration in `discord.py`

The official `discord.py` application-command docs define the main
surfaces involved in slash commands:

- `discord.app_commands.command()` creates an application command from a
  regular function
- `discord.app_commands.guilds(...)` associates a command with one or
  more guilds so it is added as a guild command rather than a global one
- `discord.app_commands.CommandTree(client)` is the container for
  application-command information
- `CommandTree.sync(...)` syncs commands to Discord

The local `CommandTree.sync()` docs are explicit that it "must be called
for the application commands to show up."

The local `app_commands.guilds(...)` docs are also explicit about the
guild/global distinction:

- when guild IDs are associated with the command, those become the
  default sync targets for that command
- if no guilds are associated, the command is not synced anywhere until
  modified later through `CommandTree.add_command()`

The design doc says the daemon handles `/apply`, `/ticket`, and staff
commands such as `/chapter-blacklist`
([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:43),
[docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:81)).

That means the daemon entry point sits at the boundary where command
definitions become live Discord application commands, but the command
registration data lives in `discord.py`’s `CommandTree` surface rather
than in the current CLI parser/dispatch system.

## 5. Graceful shutdown surfaces

There are two separate shutdown layers in this problem space:

1. closing the Discord client cleanly
2. letting the hosting process react to OS termination signals

### Discord client shutdown

The local `discord.py` docs describe `Client.close()` as closing the
connection to Discord.

The current CLI pattern already relies on that surface:

- [discord_cli.py](/home/nes/discord/discord_cli.py:461) closes the
  client from `on_ready()` after the one-shot handler completes
- [discord_cli.py](/home/nes/discord/discord_cli.py:469) closes again on
  startup timeout

That current pattern is intentionally one-shot. It exists to connect,
run one handler, and disconnect.

### Process signal handling

The official Python `asyncio` docs expose
`loop.add_signal_handler(signum, callback, *args)` as the event-loop
surface for signal handling on Unix.

The official Python `signal` docs confirm `SIGTERM` is the termination
signal and that signal availability is platform-specific. On Unix,
`SIGINT` and `SIGTERM` are the typical shutdown signals for long-running
processes.

Why this matters in this repo:

- the hosting notes explicitly describe Railway restarting the process if
  it dies
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:170))
- the deployment flow is restart-based rather than zero-downtime
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:184))
- the daemon holds long-lived resources: a gateway connection and a
  SQLite connection

The graceful-shutdown problem space is therefore not only "disconnect
from Discord" but also "coordinate process termination with the event
loop and local resources."

## 6. Environment variable loading in the current repo

The design doc names three environment variables for daemon hosting:

- `DISCORD_BOT_TOKEN`
- `DISCORD_GUILD_ID`
- `DATABASE_PATH`

([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:172))

The current repo already splits env loading across two modules.

### Bot token and guild ID

[discord_cli.py](/home/nes/discord/discord_cli.py:17) points at a local
`.env` file, and [discord_cli.py](/home/nes/discord/discord_cli.py:22)
calls `load_dotenv(ENV_PATH)` at import time.

Local `python-dotenv` docs for `load_dotenv()` say it parses a `.env`
file and loads the variables into the process environment. Its default
`override=False` means system environment variables are not overwritten
unless requested explicitly.

[discord_cli.py](/home/nes/discord/discord_cli.py:50) then reads
`DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID` from `os.getenv()` and
validates that:

- the token exists
- the guild ID exists
- the guild ID parses as an integer

### Database path

[daemon/db.py](/home/nes/discord/daemon/db.py:79) resolves
`DATABASE_PATH` from an env mapping and falls back to
`Path("discord.db")` if not present.

That means the repo already has one daemon-specific env surface:

- token/guild loading currently lives in the CLI
- database-path loading already lives in `daemon/db.py`

### YAML config is separate from env config

[daemon/config.py](/home/nes/discord/daemon/config.py:117) is strictly a
repo-managed YAML loader. It does not read `DISCORD_BOT_TOKEN`,
`DISCORD_GUILD_ID`, or `DATABASE_PATH`.

So the current problem space has two different configuration domains:

- process environment for connection/runtime paths
- repo YAML for chapter/form content

## 7. Existing bot-connection pattern in `discord_cli.py`

The current CLI’s gateway helper is the closest live baseline for the
daemon entry point.

[discord_cli.py](/home/nes/discord/discord_cli.py:436) shows this
pattern:

- load token and guild ID from env
- build intents once
- create `discord.Client(intents=...)`
- register a single `on_ready()` handler
- look up the configured guild from cache
- run one async handler against `(client, guild)`
- close the client in `finally`
- wrap `client.start(token, reconnect=False)` in a 30-second
  `asyncio.wait_for(...)`

Important facts from that helper:

- `GATEWAY_TIMEOUT_SECONDS` is fixed at `30`
  ([discord_cli.py](/home/nes/discord/discord_cli.py:20))
- the CLI explicitly uses `reconnect=False`
  ([discord_cli.py](/home/nes/discord/discord_cli.py:465))
- it treats `on_ready()` as a one-time execution gate using `has_run`
  ([discord_cli.py](/home/nes/discord/discord_cli.py:442))
- it exits immediately after the requested inspection work is done

This is a deliberate mismatch with the daemon’s intended lifetime. The
CLI code is optimized for "connect once, inspect, disconnect," whereas
the daemon design is optimized for "connect once, stay resident, and
handle interactions indefinitely."

## 8. Current constraints specific to the scaffold-only daemon increment

The scaffold-only scope narrows the daemon-entry problem space in a few
useful ways:

- the design already says no applications/tickets/provisioning logic is
  part of this increment
- the daemon still needs the process-lifecycle surfaces those features
  depend on: config load, DB bootstrap, gateway connect, and interaction
  wait state
- the repo already contains the config, DB, and claim support modules,
  but no live daemon entry file yet

The result is that `daemon.py` is not blocked on feature-module
completeness. Its research surface is mostly about process structure,
Discord client lifecycle, command-tree registration mechanics, and env
boundary definition.

## Summary of Facts

- The repo’s daemon design makes `daemon.py` the long-running process
  boundary, while `discord_cli.py` remains the one-shot interface.
- `discord.py` supports the needed lifecycle through `Client`/`Bot`,
  `start`, `run`, `close`, `setup_hook`, and `app_commands.CommandTree`.
- The planned features directly imply `guilds` and `members`.
- The current daemon design does not directly imply
  `message_content`, even though the CLI enables it for inspection.
- Slash commands in `discord.py` do not appear from decorators alone;
  the official docs say `CommandTree.sync()` must run for them to show
  up.
- Graceful shutdown spans both Discord client closure and OS-signal
  handling for the long-running process.
- Env handling is currently split: bot token/guild ID in
  `discord_cli.py`, database path in `daemon/db.py`, YAML content in
  `daemon/config.py`.
