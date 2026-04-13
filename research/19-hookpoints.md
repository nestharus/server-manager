# Hookpoint Research: `daemon/__main__.py`

Date: 2026-04-13

## Scope

This note maps
[proposals/19-daemon-main.md](/home/nes/discord/proposals/19-daemon-main.md:1)
onto the current codebase.

It is hookpoint-only research. It answers:

- what must be ported from the deleted `daemon.py`
- how `daemon/applications.py` references the bot class
- what `tests/test_daemon_entry.py` must move from `daemon.py` to
  `daemon.__main__`
- whether any live imports of the old `daemon.py` remain elsewhere

It does not include implementation code.

## Primary Sources

- Proposal:
  [proposals/19-daemon-main.md](/home/nes/discord/proposals/19-daemon-main.md:1)
- Current config loader:
  [daemon/config.py](/home/nes/discord/daemon/config.py:98)
- Current DB helpers:
  [daemon/db.py](/home/nes/discord/daemon/db.py:79),
  [daemon/db.py](/home/nes/discord/daemon/db.py:95),
  [daemon/db.py](/home/nes/discord/daemon/db.py:101),
  [daemon/db.py](/home/nes/discord/daemon/db.py:107)
- Current applications module:
  [daemon/applications.py](/home/nes/discord/daemon/applications.py:17),
  [daemon/applications.py](/home/nes/discord/daemon/applications.py:381)
- Current entry-point tests:
  [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:18)
- Deleted entry point recovered from git:
  `git show 16d5ae6:daemon.py`

## 1. What from the deleted `daemon.py` needs to be ported exactly?

The deleted file is small and concrete. Proposal 19 is a direct port of
that file into `daemon/__main__.py`, not a redesign.

Exact runtime surface to carry forward:

- module constants:
  `ENV_PATH`, `BASE_PATH`
- import-time env loading:
  `load_dotenv(ENV_PATH)`
- frozen `RuntimeConfig` with:
  `token`, `guild_id`, `base_path`, `database_path`
- `get_runtime_config()` owning env parsing and validation
- `build_intents()` calling `discord.Intents.default()` and then setting:
  `guilds = True`, `members = True`, `message_content = False`
- one `commands.Bot` subclass owning startup state on the instance:
  `guild_id`, `config`, `conn`, `base_path`
- `setup_hook()` as the daemon-owned registration seam
- a guild-scoped `/ping` command registered inside `setup_hook()`
- async `main()` orchestrating:
  `get_runtime_config()`, `load_config(...)`, `open_database(...)`,
  `conn.execute("PRAGMA busy_timeout = 5000;")`, bot construction,
  `async with bot:`, `await bot.start(token)`, and `finally:
  close_database(conn)`

Current support modules already match that orchestration split:

- config loading belongs in
  [daemon/config.py](/home/nes/discord/daemon/config.py:98)
- DB ownership belongs in
  [daemon/db.py](/home/nes/discord/daemon/db.py:95),
  [daemon/db.py](/home/nes/discord/daemon/db.py:101),
  [daemon/db.py](/home/nes/discord/daemon/db.py:107)

What changes relative to the deleted file are intentionally narrow:

- `BASE_PATH` and `ENV_PATH` must move from repo-root-file semantics to
  package-file semantics:
  `BASE_PATH = Path(__file__).resolve().parent.parent`,
  `ENV_PATH = BASE_PATH / ".env"`
- the bot class name changes from `HumilityDaemonBot` to `HumilityBot`
- `setup_hook()` gains exactly one new call:
  `await setup_applications(self)` before `self.tree.sync(guild=guild)`

What should not be ported:

- the old class name `HumilityDaemonBot`
- any dependency on `daemon.db.resolve_database_config()`
- a root-level compatibility shim `daemon.py`

## 2. How does `daemon/applications.py` reference the bot class?

The reference is type-only, not a runtime import.

The concrete hookpoint is:

- [daemon/applications.py](/home/nes/discord/daemon/applications.py:17)
  guards `from daemon.__main__ import HumilityBot` under
  `if TYPE_CHECKING:`
- [daemon/applications.py](/home/nes/discord/daemon/applications.py:381)
  annotates `setup_applications(bot: "HumilityBot") -> None`

Practical meaning:

- `daemon.__main__` must export a top-level name `HumilityBot`
- the import does not run at runtime today, because it is behind
  `TYPE_CHECKING`
- the applications module is effectively duck-typing the bot object and
  expects at least:
  `guild_id`, `tree`, `config`, `conn`, and `add_view(...)`

This is why the rename pressure comes from `daemon/applications.py`, not
from `tests/test_daemon_entry.py`. The visible tests only require
exactly one bot subclass; the live type reference requires the name
`HumilityBot`.

## 3. What tests need updating from `daemon.py` to `daemon.__main__`?

All of `tests/test_daemon_entry.py` is still wired to the deleted root
file path, so every test in that file needs at least import-path
rewriting.

Direct file-coupled hooks to update:

- [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:18)
  `DAEMON_ENTRY_PATH = ... / "daemon.py"`
- [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:19)
  `EXPECTED_ENV_PATH = DAEMON_ENTRY_PATH.with_name(".env")`
- [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:20)
  `EXPECTED_BASE_PATH = DAEMON_ENTRY_PATH.resolve().parent`
- [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:28)
  through
  [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:50),
  which import the module by file path via
  `importlib.util.spec_from_file_location(...)`
- all failure messages and helper text that still say `daemon.py`

Behavioral expectations that should stay, but move to
`daemon.__main__`:

- import-time `load_dotenv(EXPECTED_ENV_PATH)`
- runtime-config validation for `DISCORD_BOT_TOKEN` and
  `DISCORD_GUILD_ID`
- `build_intents()` behavior
- exactly one exported `commands.Bot` subclass
- async `setup_hook()`
- `main()` loading config from repo base, preferring env
  `DATABASE_PATH`, defaulting to repo-root `discord.db`, setting
  `busy_timeout`, starting the bot, and always closing the DB
- the explicit prohibition on using
  `daemon.db.resolve_database_config()`

Concrete expectation changes needed in the rewrite:

- import `daemon.__main__` instead of loading `daemon.py` by path
- compute expected paths relative to `daemon/__main__.py`, so
  `EXPECTED_BASE_PATH` becomes the repo root via `parent.parent`
- `EXPECTED_ENV_PATH` becomes `EXPECTED_BASE_PATH / ".env"`
- if the tests choose to assert the class name explicitly, they should
  now expect `HumilityBot`, not `HumilityDaemonBot`

Coverage gap the proposal adds beyond the current test file:

- `setup_hook()` should now be tested for call order:
  register `/ping`, call `setup_applications(self)`, then
  `tree.sync(guild=...)`

The current file does not test that order at all, so that is not just a
rename; it is a new behavioral assertion required by proposal 19.

## 4. What imports of the old `daemon.py` exist elsewhere?

There are no live Python imports elsewhere that import the deleted root
`daemon.py` as a module.

What exists instead:

- the only live code artifact still coupled to the deleted root file is
  [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:18),
  which loads it by filesystem path
- the live code import pressure points at `daemon.__main__`, not
  `daemon.py`, via the `TYPE_CHECKING` import in
  [daemon/applications.py](/home/nes/discord/daemon/applications.py:18)
- [daemon/applications.py](/home/nes/discord/daemon/applications.py:14)
  uses `from daemon import claim, db`, but that is importing the
  package, not the old root entry file

There are still stale textual references to `daemon.py`, but they are
not runtime imports:

- [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:3)
- [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:10)
- [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:169)
- several existing `research/` and `risk/` notes that document the old
  entry-point shape

## Bottom Line

Proposal 19 maps cleanly onto the current codebase because the deleted
`daemon.py` was already a thin orchestration module. The only exact port
work is to recreate that surface in `daemon/__main__.py`, adjust
base-path semantics for the package location, rename the bot class to
`HumilityBot`, and wire `setup_applications(self)` into
`setup_hook()` before guild sync. The only live old-entry coupling is
`tests/test_daemon_entry.py`; there are no remaining runtime imports of
root `daemon.py` elsewhere.
