# NOTES.md - agent-maintained log of discovered facts

Last updated: 2026-04-13

## Guild

- Name: Humility
- ID: `900000000000000001`
- Owner: `nestharus` (user id `900000000000000002`)
- Created: 2022-04-04
- Member count during the original sweep: 83
- Premium tier: 1

## Ticketing

- `ticketsbot.net` was discontinued on `2025-03-05`.
- `panel.ticketsbot.net` returned `404` for the user during this investigation.
- `#support` contains a `2023-12-22` HumilityTicketBot embed titled `Click to open a ticket`.
- `#panels` contains a `2022-04-04` HumilityTicketBot embed titled `General Support`.
- `#ticket-logs` contains only a small number of historical tickets, including ticket `3` on `2025-04-11` opened by `nestharus`.
- `#templates` was empty during the sweep.

## Bot Activity Audit

- Hydra (`547905866255433758`): zero visible messages across the scanned channels.
- Gather (`868195275464900618`): zero visible messages across the scanned channels.
- Apollo (`475744554910351370`): zero visible messages across the scanned channels.
- sesh (`616754792965865495`): 2 visible messages, both in `#moderation-commands`, both promotional/premium notices.
- Zira (`275813801792634880`): 15 visible messages, all in `#admin-chat`, consisting of old setup actions and premium notices.

## Roles and Structure

- The staff stack starts with `Administrator`, `Moderator`, `Staff`, and `Trial Mod`.
- The chapter stack includes `Chapter Officer`, `Chapter Member`, `Chapter Guild War`, `Chapter Applicant`, `Chapter`, and `Chapter Public`.
- There are two separate `Robots` roles; one functions as the effective permissions container for bots and one is used as a hoisted visual separator.

## Chapter Scaffolding

- The `GUILD TEMPLATE` category is hidden from `@everyone` and exposed to chapter roles such as `Chapter Officer`.
- The category contains structure for chapter operations, but the template channels are empty.
- No evidence was found that real chapter applications or populated chapter spaces have ever been used.

## Working Conclusions

- The user wants bot-consolidation planning but does not want to rotate the bot token right now.
- `Hydra`, `Apollo`, and `sesh` appear unused from Discord-visible evidence.
- `Gather` has no Discord-visible activity, but it may still have external dashboard configuration.
- A first-party applications subsystem should replace Gather only after the flow is designed and tested.

## Daemon Config Design

- Proposed `daemon/config.py` as a pure YAML loader/validator with immutable dataclasses, deterministic form step planning, and no cached globals.
- `chapters.yaml` remains the active chapter registry; chapter forms resolve from `forms/<slug>.yaml` rather than being auto-discovered.

## Daemon DB Research

- `docs/DAEMON_DESIGN.md` defines `daemon/db.py` as the owner of SQLite schema bootstrap, migrations, and query helpers for `chapters`, `submissions`, `tickets`, and `chapter_blacklist`.
- The current DB problem space is one Railway-backed file at `/data/discord.db`, shared by the long-running daemon and one-shot CLI commands.
- Local runtime checks found `sqlite3.threadsafety == 3`, but default `check_same_thread=True` still rejects cross-thread use of the same connection with `ProgrammingError`.
- Research note `research/15-db.md` captures the current sqlite3/WAL/bootstrap/migration/query-helper facts without proposing an implementation.
- Hookpoint note `research/15-hookpoints.md` maps the current insertion points: `daemon/config.py` is the local style baseline, `discord_cli.py` parser/dispatch is the live seam for future DB-backed CLI commands, and SQLite must complement rather than replace `chapters.yaml`.

## Claim Visibility Research

- Research note `research/16-claim.md` captures the current claim-visibility problem space for the planned `daemon/claim.py` module without proposing an implementation.
- Official Discord docs treat private-thread visibility as explicit membership plus a moderator bypass for users with effective `MANAGE_THREADS`; removing a user from thread membership alone does not hide the thread from members who still retain `manage_threads` on the parent channel.
- Official Discord docs also say thread posting is controlled by `SEND_MESSAGES_IN_THREADS`, not `SEND_MESSAGES`; this matters to the current Trial Mod read-only design note.

## Daemon Entry Research

- Research note `research/17-daemon-entry.md` captures the current daemon-entry problem space for the planned top-level `daemon.py` file without proposing an implementation.
- Local runtime inspection on `2026-04-13` resolved `discord.py 2.7.1`; the installed docs/runtime confirm `Client.start()` is `login + connect`, `Client.run()` is the blocking loop-owning helper, `Client.close()` closes the Discord connection, and `setup_hook()` runs after login but before the websocket connects.
- The planned daemon features directly imply the `guilds` and `members` intents. The current design does not directly imply `message_content`, even though `discord_cli.py` enables it for read-only inspection commands.
- `discord.py` slash commands live on `app_commands.CommandTree`; the local docs say `CommandTree.sync()` must be called for commands to appear, and `app_commands.guilds(...)` determines whether commands sync as guild commands rather than global ones.
- The current env split is: `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID` are loaded in `discord_cli.py` via `.env`, `DATABASE_PATH` is resolved in `daemon/db.py`, and repo YAML remains separate in `daemon/config.py`.
