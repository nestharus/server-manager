# Proposal: `daemon/__main__.py`

Date: 2026-04-13

## Goal

Define the design for `daemon/__main__.py` as the package entry point
for the Humility daemon.

This proposal is design only. It does not include implementation code.

## Source Note

The requested input file `research/19-daemon-main.md` is not present in
the repo. This proposal is synthesized from:

- `research/19-daemon-main-needs.md`
- `docs/DAEMON_DESIGN.md`
- the current `daemon/` modules
- the deleted `daemon.py` implementation in `HEAD`
- `tests/test_daemon_entry.py`, which still documents the old entry
  point contract

## Summary

`daemon/__main__.py` should replace the deleted top-level `daemon.py`
as the daemon's only entry point.

It should remain a thin orchestration module with the same basic startup
shape as the old file:

- load repo-local `.env`
- validate runtime env vars
- load daemon config from the repo root
- open the SQLite database
- construct a bot subclass that owns startup state
- register and sync guild-scoped slash commands in `setup_hook()`
- start the Discord gateway
- always close the database in `finally`

This is a direct port, with three intentional changes only:

1. The file lives at `daemon/__main__.py`, so repo-root path resolution
   must move up one extra directory.
2. The bot class is renamed from `HumilityDaemonBot` to `HumilityBot`.
3. `setup_hook()` must call `await setup_applications(self)` before
   guild sync.

No compatibility shim for `daemon.py` should be added.

## Module Surface

`daemon/__main__.py` should export exactly the runtime surface needed by
the old tests, the applications module, and `python -m daemon`.

### Constants

- `BASE_PATH = Path(__file__).resolve().parent.parent`
- `ENV_PATH = BASE_PATH / ".env"`

These are exact requirements, not approximate guidance. Because the
module now lives inside the `daemon/` package, `parent.parent` is the
repo root.

### Import-time behavior

The module should load the repo-local env file at import time with
`load_dotenv(ENV_PATH)`, matching the old entry point behavior.

That import-time work is acceptable because it does not open the DB,
construct a bot, or start the event loop. Importing
`daemon.__main__` for `TYPE_CHECKING` or tests must remain safe.

### RuntimeConfig

Keep a small frozen dataclass:

- `token: str`
- `guild_id: int`
- `base_path: Path`
- `database_path: Path`

### `get_runtime_config()`

`get_runtime_config()` should continue to own runtime env parsing and
validation.

Required behavior:

- require `DISCORD_BOT_TOKEN`
- require `DISCORD_GUILD_ID`
- reject non-integer `DISCORD_GUILD_ID`
- treat `DATABASE_PATH` as optional
- when `DATABASE_PATH` is unset, default to
  `BASE_PATH / "discord.db"`

This should remain independent of `daemon.db.resolve_database_config()`.
That helper defaults to cwd-relative `Path("discord.db")`, which is not
the desired behavior for the daemon entry point.

### `build_intents()`

`build_intents()` should remain a narrow helper around
`discord.Intents.default()` and explicitly set:

- `guilds = True`
- `members = True`
- `message_content = False`

This matches the old `daemon.py` contract and the current entry-point
tests. No broader intent changes belong in this partition.

## Bot Class

The module should export `HumilityBot`, a `commands.Bot` subclass.

### Rename decision

Use `HumilityBot`, not `HumilityDaemonBot`.

Reason:

- `daemon/applications.py` already uses
  `from daemon.__main__ import HumilityBot` under `TYPE_CHECKING`
- the new package entry point should expose the class name the package
  now expects

No alias for `HumilityDaemonBot` should be kept. The prompt explicitly
rules out backward compatibility with the old `daemon.py`.

### Owned runtime state

`HumilityBot` should keep the same startup-owned state on the instance:

- `guild_id`
- `config`
- `conn`
- `base_path`

That keeps the bot instance as the runtime handoff point for
subsystems, especially `daemon.applications`.

## `HumilityBot.setup_hook()`

`setup_hook()` is the correct seam for command registration and
persistent-view hydration.

Required order:

1. Build `guild = discord.Object(id=self.guild_id)`.
2. Register a guild-scoped `/ping` command.
3. Call `await setup_applications(self)`.
4. Call `await self.tree.sync(guild=guild)`.

### `/ping`

`/ping` remains the minimal daemon-owned health command from the old
entry point. It should stay guild-scoped and remain intentionally
small.

### Applications wiring

`setup_applications(self)` is the only new startup hook added by this
proposal. It is responsible for application-specific registration and
persistent review-view hydration.

It must run before `tree.sync(...)` so the `/apply` command and any
related application commands are included in the synced guild command
set.

### Why `setup_hook()`

This work belongs in `setup_hook()`, not in `main()`, because:

- slash commands must be registered before sync
- persistent views must be attached to the live bot instance during
  startup
- this preserves the old entry point's lifecycle boundary instead of
  inventing a second startup pipeline

## `main()` Runtime Flow

`main()` should remain an async entry point, not a `bot.run(...)`
wrapper.

Recommended runtime sequence:

1. `runtime = get_runtime_config()`
2. `config = load_config(runtime.base_path)`
3. `conn = open_database(runtime.database_path)`
4. `conn.execute("PRAGMA busy_timeout = 5000;")`
5. construct `HumilityBot(...)`
6. `async with bot:`
7. `await bot.start(runtime.token)`
8. `finally: close_database(conn)`

### Cleanup contract

The `try`/`finally` around DB ownership is required. If config loads and
the DB opens successfully, the DB connection must always close even if:

- bot construction fails
- login fails
- gateway startup fails
- the daemon later exits due to an exception

This preserves the old `daemon.py` contract and matches the intent of
the existing entry-point tests.

## Execution And Import Model

`daemon/__main__.py` must support both package execution and direct
import.

### Package execution

Support:

- `python -m daemon`

with the normal guard:

- `if __name__ == "__main__": asyncio.run(main())`

### Import support

Support:

- `import daemon.__main__`
- `from daemon.__main__ import HumilityBot`

This is required for `TYPE_CHECKING` in `daemon/applications.py` and for
test imports.

The guard must ensure that importing the module does not start the
daemon process.

## Test Impact

`tests/test_daemon_entry.py` currently targets the deleted
`daemon.py` file path. This proposal does not preserve that shape.

The follow-up test rewrite should:

- import `daemon.__main__` instead of loading `daemon.py` by path
- assert `BASE_PATH == Path(__file__).resolve().parent.parent` relative
  to `daemon/__main__.py`
- assert `ENV_PATH == BASE_PATH / ".env"`
- expect the exported bot subclass to be named `HumilityBot`
- verify that `setup_hook()` calls `setup_applications(self)` before
  `tree.sync(guild=...)`
- keep the existing runtime-config, intents, default-DB-path, and DB
  cleanup expectations

The important point is behavioral continuity, not file-path continuity.

## Out Of Scope

This proposal does not add:

- new daemon features
- ticket wiring
- provisioning wiring
- new slash commands beyond `/ping`
- compatibility aliases for `HumilityDaemonBot`
- a `daemon.py` shim
- any new startup abstraction beyond the direct port plus applications
  wiring

That matches the prompt's anti-scope: port the old entry point into the
package form and wire in `daemon.applications`, nothing more.
