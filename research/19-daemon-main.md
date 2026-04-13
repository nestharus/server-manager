# Research: `daemon/__main__.py`

Date: 2026-04-13

## Scope

This note documents the current problem space for moving the deleted
root `daemon.py` entry point into `daemon/__main__.py`.

It is limited to:

- the behavior the deleted entry point owned
- the current repo-local callers and tests that constrain a package
  entry point
- Python package execution behavior for `python -m daemon`
- import behavior for `from daemon.__main__ import HumilityBot`

It does not propose an implementation.

## Primary Sources

- Architecture:
  [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:3)
- Current daemon config loader:
  [daemon/config.py](/home/nes/discord/daemon/config.py:48),
  [daemon/config.py](/home/nes/discord/daemon/config.py:117)
- Current SQLite helpers:
  [daemon/db.py](/home/nes/discord/daemon/db.py:11),
  [daemon/db.py](/home/nes/discord/daemon/db.py:79),
  [daemon/db.py](/home/nes/discord/daemon/db.py:101),
  [daemon/db.py](/home/nes/discord/daemon/db.py:107)
- Current applications subsystem:
  [daemon/applications.py](/home/nes/discord/daemon/applications.py:17),
  [daemon/applications.py](/home/nes/discord/daemon/applications.py:381)
- Old entry-point tests:
  [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:18)
- Deleted entry point recovered from git:
  `git show 16d5ae6:daemon.py`
- Local runtime inspection on 2026-04-13 with Python `3.12.3`

## Local Baseline

The architecture doc still describes a root `daemon.py` as the daemon
entry point and still shows Railway starting it with
`uv run python daemon.py`
([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:10),
[docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:169)).
Those references are stale with respect to the package-entry goal, but
they still define the owned behavior: boot the daemon, load config,
register handlers, and hold the long-running Discord connection
([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:3),
[docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:193)).

The current repo already has the support modules the entry point is
expected to orchestrate:

- `load_config(base_path)` returns a `DaemonConfig` rooted at the repo
  base path
  ([daemon/config.py](/home/nes/discord/daemon/config.py:48),
  [daemon/config.py](/home/nes/discord/daemon/config.py:117)).
- `open_database(path)` bootstraps SQLite, and `close_database(conn)`
  closes it
  ([daemon/db.py](/home/nes/discord/daemon/db.py:95),
  [daemon/db.py](/home/nes/discord/daemon/db.py:101),
  [daemon/db.py](/home/nes/discord/daemon/db.py:107)).
- `setup_applications(bot)` expects a bot object with at least
  `guild_id`, `tree`, `config`, and `conn`, and its type annotation is a
  forward reference to `HumilityBot` from `daemon.__main__`
  ([daemon/applications.py](/home/nes/discord/daemon/applications.py:17),
  [daemon/applications.py](/home/nes/discord/daemon/applications.py:140),
  [daemon/applications.py](/home/nes/discord/daemon/applications.py:381)).

## Deleted `daemon.py` Behavior

The deleted file in commit `16d5ae6` defined exactly the boot surface
the prompt describes:

- `ENV_PATH = Path(__file__).with_name(".env")`
- `BASE_PATH = Path(__file__).resolve().parent`
- top-level `load_dotenv(ENV_PATH)`
- `RuntimeConfig(token, guild_id, base_path, database_path)`
- `get_runtime_config()`
- `build_intents()` with `guilds=True`, `members=True`,
  `message_content=False`
- one `commands.Bot` subclass named `HumilityDaemonBot`
- `setup_hook()` registering guild-scoped `/ping`
- `main()` loading config, opening DB, setting SQLite `busy_timeout`,
  starting the bot, and always closing the DB in `finally`

The deleted file did not call `setup_applications(bot)`.

## Current Test Contract

The visible tests still target the deleted root file path
`/home/nes/discord/daemon.py`
([tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:18)).
That means they are currently a behavior spec for the old entry point,
not a passing test suite for the package-entry layout.

What those tests still concretely specify:

- importing the entry module should call `load_dotenv()` with repo-local
  `.env`
  ([tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:99)).
- runtime config loading must require `DISCORD_BOT_TOKEN` and
  `DISCORD_GUILD_ID`, and `DISCORD_GUILD_ID` must parse as `int`
  ([tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:105),
  [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:117),
  [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:129)).
- the module must expose exactly one `commands.Bot` subclass with an
  async `setup_hook()`
  ([tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:76),
  [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:141)).
- intents must come from `discord.Intents.default()`, with `guilds` and
  `members` enabled and `message_content` left disabled
  ([tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:151)).
- `main()` must load config from repo base, default the DB path to
  `base_path / "discord.db"`, set `PRAGMA busy_timeout = 5000`, start the
  bot with the token, prefer `DATABASE_PATH` when present, and always
  close the DB
  ([tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:174),
  [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:240)).
- the entry point must not delegate default DB-path resolution to
  `daemon.db.resolve_database_config()`
  ([tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:194)).

The tests do not pin the bot class name. They only require that there be
exactly one bot subclass.

## 1. How `__main__.py` works for package execution

For a package, `python -m daemon` executes `daemon/__main__.py`.

Local Python 3.12.3 runtime checks with a throwaway package showed:

- `python3 -m demo` runs `demo/__main__.py`
- inside that file, `__name__ == "__main__"`
- inside that file, `__package__ == "demo"`

That means package execution gives `__main__.py` package context for
imports, while still treating it as the top-level executable module.

Relevant consequence for this repo:

- `python -m daemon` is the package-execution replacement for the old
  `python daemon.py`
- `if __name__ == "__main__": ...` still works inside `daemon/__main__.py`
- absolute imports like `from daemon.config import ...` remain valid
  during package execution

## 2. Import considerations for `from daemon.__main__ import HumilityBot`

`from daemon.__main__ import HumilityBot` is a normal import path as
long as `daemon/__main__.py` exists and binds `HumilityBot` at module
top level.

Two import details matter here.

First, importing `daemon` does not import `daemon.__main__`. The package
module and the package entry module are separate. So making
`daemon.__main__` importable requires an actual `daemon/__main__.py`
module; it is not implied by [daemon/__init__.py](/home/nes/discord/daemon/__init__.py:1).

Second, `python -m daemon` and `import daemon.__main__` are not the same
module identity inside one process. Local runtime checks showed that
when `demo/__main__.py` is executed via `python -m demo`, a later
runtime import of `demo.__main__` causes the file to execute again under
the name `demo.__main__`. The executed `__main__` module object and the
imported `demo.__main__` module object were distinct.

That creates a concrete hazard:

- unguarded runtime imports of `daemon.__main__` from within the daemon
  process can re-run top-level module code
- top-level side effects in the entry module, such as `load_dotenv()`,
  would run again
- class objects defined in the second load would not be the same objects
  as the ones created during `python -m daemon`

Current repo impact:

- the `applications.py` back-reference is inside `if TYPE_CHECKING:`,
  so it does not create this double-import behavior at runtime
  ([daemon/applications.py](/home/nes/discord/daemon/applications.py:17)).
- if that back-reference ever became an unconditional runtime import, it
  would change the behavior materially during `python -m daemon`.

## 3. Bot naming pressure: `HumilityDaemonBot` vs `HumilityBot`

The deleted file used the class name `HumilityDaemonBot`.

The current live repo reference is different:

- [daemon/applications.py](/home/nes/discord/daemon/applications.py:18)
  names the type as `HumilityBot`
- [daemon/applications.py](/home/nes/discord/daemon/applications.py:381)
  uses that same name in the `setup_applications(bot: "HumilityBot")`
  signature

The visible old tests do not care about the class name, only that there
is exactly one `commands.Bot` subclass
([tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:76)).

So the current repo has two separate naming facts:

- history used `HumilityDaemonBot`
- the live import expectation in `applications.py` is `HumilityBot`

The import requirement is the stricter one. If `daemon.__main__` does
not export a top-level name `HumilityBot`, the current
`TYPE_CHECKING` import target is wrong even though the old visible tests
would still be satisfied by some other subclass name.

## Other Compatibility Findings

### `setup_hook()` is the integration seam

The deleted entry point already used `setup_hook()` for guild-scoped
`/ping`. The current applications module is designed around being wired
into that same startup seam via `setup_applications(bot)`
([daemon/applications.py](/home/nes/discord/daemon/applications.py:381)).

### `/ping` remains entry-point-owned

The only command the deleted file owned itself was a guild-scoped
ephemeral `/ping`. Nothing in the current applications module replaces
that responsibility, so the entry module still has its own command
surface in addition to application wiring.

### The design docs still describe the old launch path

The architecture document and Railway note still say `daemon.py` and
`python daemon.py`
([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:10),
[docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:169)).
Those references are useful for behavior, but not for the final import
or execution path.

## Direct Answers

### 1. How does Python `__main__.py` work for package execution?

For `python -m daemon`, Python imports the `daemon` package and then
executes `daemon/__main__.py` as the top-level executable module. In
that execution context, `__name__` is `"__main__"` and `__package__` is
`"daemon"`.

### 2. What are the import considerations for `from daemon.__main__ import HumilityBot`?

It is a valid import path, but it requires a real
`daemon/__main__.py`. Importing `daemon` alone is not enough. Also,
during `python -m daemon`, a later runtime import of `daemon.__main__`
can execute the file a second time under a different module identity, so
runtime back-imports of the entry module are materially different from
type-only references.

### 3. How should the bot class be named?

The old file used `HumilityDaemonBot`, but the live repo reference now
points at `HumilityBot` through the `TYPE_CHECKING` import in
`applications.py`. The visible old tests do not constrain the class
name; the live import surface does.
