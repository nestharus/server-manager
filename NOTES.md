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

## Applications Research

- Research note `research/18-applications.md` captures the current applications-subsystem problem space for the planned `daemon/applications.py` module without proposing an implementation.
- Current Discord docs and installed `discord.py 2.7.1` no longer support the old assumption that modals are text-only: the newer component docs and local library source both document select components inside modals, even though `docs/DAEMON_DESIGN.md` still describes selects as follow-up-only.
- Discord’s interaction callback rules do not allow `MODAL` as a direct response to `MODAL_SUBMIT`, so the design doc’s `modal -> select menus -> modal -> etc.` language is only valid when the later modal is opened from a subsequent component interaction rather than directly from the modal submission itself.
- Discord’s thread creation APIs treat message-attached threads as public or announcement threads; private threads are created without a source message. That conflicts with the current design phrase "private thread off that message".
- `daemon/applications.py` now exists with the smoke-test contract: `ApplicationModal`, `ApplicationReviewView`, and async `setup_applications(bot)`.
- `ApplicationReviewView(submission_id)` is implemented as a persistent `timeout=None` view with four direct buttons using `app:<action>:<submission_id>` custom IDs for `claim`, `interview`, `approve`, and `deny`.
- `daemon/db.py` now exposes the application-flow helpers the proposal expects: `create_submission(...) -> int`, `update_submission_refs(...)`, `transition_submission_status(...) -> bool`, `load_active_submission_ids()`, and `has_active_submission()`.

## Package Entry Research

- Research note `research/19-daemon-main.md` captures the package-entry problem space for moving the deleted root `daemon.py` behavior into `daemon/__main__.py` without proposing an implementation.
- Hookpoint note `research/19-hookpoints.md` narrows the exact port surface: carry forward the deleted `daemon.py` constants, import-time `.env` load, `RuntimeConfig`, `get_runtime_config()`, `build_intents()`, bot-owned startup state, `/ping`, and `main()` orchestration into `daemon/__main__.py`, with only three intended changes: `BASE_PATH/ENV_PATH` shift to `parent.parent`, `HumilityDaemonBot` renames to `HumilityBot`, and `setup_hook()` must call `setup_applications(self)` before guild sync.
- The only remaining live coupling to the deleted root `daemon.py` is `tests/test_daemon_entry.py` loading it by filesystem path; there are no other runtime imports of the old root file, while live code now points at `daemon.__main__` through the `TYPE_CHECKING` import in `daemon.applications`.
- The current live import pressure is `daemon.applications` type-checking against `from daemon.__main__ import HumilityBot`; the old deleted class name was `HumilityDaemonBot`, but the visible old tests only require exactly one `commands.Bot` subclass and do not constrain its name.
- Local Python 3.12.3 runtime checks confirmed that `python -m daemon` executes `daemon/__main__.py` with `__name__ == "__main__"` and `__package__ == "daemon"`.
- The same local checks also confirmed a subtle hazard: during `python -m daemon`, a later runtime import of `daemon.__main__` can execute the file a second time under the module name `daemon.__main__`, producing a second module instance and re-running top-level side effects such as `load_dotenv()`.
- `docs/DAEMON_DESIGN.md` and its Railway start example still describe the old root-file launch path (`daemon.py`, `python daemon.py`); those references remain useful as behavior documentation but are stale as the final execution path.
