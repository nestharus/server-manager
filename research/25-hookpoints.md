# Hookpoint Research: Discord Service `app.__main__`

Date: 2026-04-13

## Scope

This note maps
[proposals/25-discord-main.md](/home/nes/discord/proposals/25-discord-main.md:1)
onto the current `services/discord` codebase.

It is hookpoint-only research for
`services/discord/app/__main__.py`.

It answers:

1. whether `app/__main__.py` already exists
2. whether `HumilityBot` needs changes for the proposed entry point
3. whether `Settings` supports the proposed construction pattern
4. whether `discord.utils.setup_logging` exists in the installed
   `discord.py`
5. whether any existing tests need updating
6. what test runner configuration exists for this service

It does not include implementation code.

## Primary Sources

- Proposal:
  [proposals/25-discord-main.md](/home/nes/discord/proposals/25-discord-main.md:1)
- Package marker:
  [services/discord/app/__init__.py](/home/nes/discord/services/discord/app/__init__.py:1)
- Settings:
  [services/discord/app/core/settings.py](/home/nes/discord/services/discord/app/core/settings.py:1)
- Bot:
  [services/discord/app/core/bot.py](/home/nes/discord/services/discord/app/core/bot.py:1)
- Service package metadata:
  [services/discord/pyproject.toml](/home/nes/discord/services/discord/pyproject.toml:1)
- Existing service tests:
  [services/discord/tests/test_settings.py](/home/nes/discord/services/discord/tests/test_settings.py:1)
  [services/discord/tests/test_bot.py](/home/nes/discord/services/discord/tests/test_bot.py:1)
- Existing root daemon entrypoint for comparison:
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:1)
- Root pytest config:
  [pyproject.toml](/home/nes/discord/pyproject.toml:1)

## Existing Code Inventory Relevant To `app.__main__`

### `services/discord/app/__main__.py` does not exist

`services/discord/app/` currently contains only:

- [services/discord/app/__init__.py](/home/nes/discord/services/discord/app/__init__.py:1)
- `commands/`
- `core/`
- `handlers/`
- `tasks/`

There is no existing
`[services/discord/app/__main__.py](/home/nes/discord/services/discord/app/__main__.py)`.

Operationally, that means the proposal target command currently fails:

`cd services/discord && ./.venv/bin/python -m app`

Observed result:

`No module named app.__main__; 'app' is a package and cannot be directly executed`

So proposal 25 is greenfield for the service package itself.

### The package marker is minimal and non-blocking

[services/discord/app/__init__.py](/home/nes/discord/services/discord/app/__init__.py:1)
is only a docstring package marker. There are no exports, startup side
effects, or import contracts that the new entrypoint has to preserve.

### `Settings` already exists and already matches the bootstrap boundary

[services/discord/app/core/settings.py](/home/nes/discord/services/discord/app/core/settings.py:5)
already defines a `BaseSettings` model:

- `discord_bot_token: str = Field(repr=False)`
- `discord_guild_id: int = Field(gt=0)`
- `supabase_db_url: str = Field(repr=False)`

Its model config is:

- `SettingsConfigDict(env_file=None)`
  [services/discord/app/core/settings.py](/home/nes/discord/services/discord/app/core/settings.py:6)

This is an exact fit for the proposal's "construct validated runtime
settings inside `main()`" requirement:

- explicit constructor use already works
- environment-backed construction already works
- invalid or missing values raise `pydantic.ValidationError`
- sensitive fields are already redacted from `repr(...)`

The existing tests confirm env-backed construction:
[services/discord/tests/test_settings.py](/home/nes/discord/services/discord/tests/test_settings.py:88).

### `HumilityBot` already exists and is intentionally thin

[services/discord/app/core/bot.py](/home/nes/discord/services/discord/app/core/bot.py:7)
already defines:

- `class HumilityBot(commands.Bot)`
- constructor signature `HumilityBot(settings: Settings)`

The constructor:

- creates intents locally
  [services/discord/app/core/bot.py](/home/nes/discord/services/discord/app/core/bot.py:9)
- sets `members = True`
  [services/discord/app/core/bot.py](/home/nes/discord/services/discord/app/core/bot.py:10)
- sets `message_content = True`
  [services/discord/app/core/bot.py](/home/nes/discord/services/discord/app/core/bot.py:11)
- sets `presences = False`
  [services/discord/app/core/bot.py](/home/nes/discord/services/discord/app/core/bot.py:12)
- calls `commands.Bot(...)` with `when_mentioned`
  [services/discord/app/core/bot.py](/home/nes/discord/services/discord/app/core/bot.py:14)
- stores the passed `Settings` object on `self.settings`
  [services/discord/app/core/bot.py](/home/nes/discord/services/discord/app/core/bot.py:15)

There is no startup side effect in `__init__`, which is exactly what
proposal 25 wants before `await bot.start(...)`.

### There is already a separate legacy daemon entrypoint elsewhere

The repo still has a root-level daemon entrypoint at
[daemon/__main__.py](/home/nes/discord/daemon/__main__.py:1).

That module currently owns a much wider boundary:

- reads env vars directly
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:42)
- opens the database
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:105)
- defines a different `HumilityBot`
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:74)
- starts the bot with `async with bot: await bot.start(...)`
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:116)

This is not a direct hookpoint for the new file, but it is a nearby
integration seam and the main potential source of confusion: the repo
already has "a daemon main", just not inside `services/discord/app/`.

## Reusable Components

### `Settings()` can be reused as-is

For proposal 25's construction pattern:

```python
settings = Settings()
```

the current class already supports everything needed:

- env-driven loading via `BaseSettings`
- validation errors on missing/invalid fields
- no `.env` side effects because `env_file=None`
- secret redaction for the token and database URL

No changes are required in
[services/discord/app/core/settings.py](/home/nes/discord/services/discord/app/core/settings.py:1)
to support bootstrap.

### `HumilityBot(settings)` can be reused as-is

For proposal 25's construction pattern:

```python
bot = HumilityBot(settings)
```

the current class is already compatible:

- constructor accepts `Settings`
- construction is local-only and network-free
- intents are already encapsulated in the bot
- `self.settings` gives the entrypoint access to validated config only
  through the bot instance if needed later

Shutdown support also already exists through inheritance.
Runtime inspection against the installed `discord.py` showed:

- `HumilityBot.close` exists
- `commands.Bot.close` is an async coroutine
- `commands.Bot.is_closed` exists

So the proposed `finally` shape with `await bot.close()` guarded by
`bot.is_closed()` is already supported by the current bot class. No
custom `close()` override is needed.

### `discord.utils.setup_logging` is available in the installed version

The service virtualenv currently has `discord.py 2.7.1` installed.
Runtime inspection confirmed:

- `hasattr(discord.utils, "setup_logging") == True`
- signature:
  `(*, handler=..., formatter=..., level=..., root=True) -> None`

That matches the proposal's intended usage. No compatibility fallback
is needed for the installed dependency set.

## New Components Needed

Only one new service file is needed for proposal 25:

- `services/discord/app/__main__.py`

Everything else the proposal depends on already exists:

- package marker:
  [services/discord/app/__init__.py](/home/nes/discord/services/discord/app/__init__.py:1)
- validated settings:
  [services/discord/app/core/settings.py](/home/nes/discord/services/discord/app/core/settings.py:5)
- bot type:
  [services/discord/app/core/bot.py](/home/nes/discord/services/discord/app/core/bot.py:7)
- package dependency on `discord.py`:
  [services/discord/pyproject.toml](/home/nes/discord/services/discord/pyproject.toml:6)

No proposal-driven edits are required in `Settings`, `HumilityBot`, or
`__init__.py` based on the current code.

## Existing Tests And Whether They Need Updating

### Current service tests

The Discord service currently has exactly two real test modules:

- [services/discord/tests/test_settings.py](/home/nes/discord/services/discord/tests/test_settings.py:1)
- [services/discord/tests/test_bot.py](/home/nes/discord/services/discord/tests/test_bot.py:1)

Their coverage is narrow and stable:

- `test_settings.py` checks model construction, missing-field
  validation, secret redaction, and environment loading
  [services/discord/tests/test_settings.py](/home/nes/discord/services/discord/tests/test_settings.py:7)
- `test_bot.py` checks importability, construction, stored settings,
  intent flags, and `commands.Bot` inheritance
  [services/discord/tests/test_bot.py](/home/nes/discord/services/discord/tests/test_bot.py:31)

### Do existing tests need updating?

Not based on the current proposal.

Proposal 25 adds a new package entrypoint, but it does not change:

- the `Settings` field contract
- the `HumilityBot` constructor contract
- the current intent configuration in `bot.py`

So the current `test_settings.py` and `test_bot.py` should remain valid
without edits.

What is missing is new coverage for the new file, likely as a new test
module rather than edits to the existing ones. The existing tests do
not currently exercise:

- `python -m app` entry behavior
- `main() -> int`
- logging bootstrap
- signal registration
- exit-code translation for bootstrap/runtime failures

## Test Infrastructure Available

### Service-local test tooling

[services/discord/pyproject.toml](/home/nes/discord/services/discord/pyproject.toml:17)
already declares:

- `pytest`
- `pytest-asyncio`
- `pytest-cov`
- `pytest-mock`

So the service already has enough tooling to test:

- sync constructor/validation behavior
- async `main()` behavior
- patched bot startup/shutdown flows
- signal-handler registration logic

### Actual current collection behavior

From `services/discord/`, this works today:

`./.venv/bin/pytest --collect-only -q`

Observed result: 15 tests collected under `services/discord/tests/`.

From the repo root, path-targeted collection also works today:

`services/discord/.venv/bin/pytest services/discord/tests/test_bot.py --collect-only -q`

Observed result: 8 tests collected.

### Configuration shape

There is no service-local `[tool.pytest.ini_options]` stanza in
[services/discord/pyproject.toml](/home/nes/discord/services/discord/pyproject.toml:1).

That means the Discord service currently relies on:

- default pytest discovery under `tests/`
- the working directory / explicit test path used at invocation time

The repo root does have a pytest stanza:
[pyproject.toml](/home/nes/discord/pyproject.toml:22)

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

But that is root-repo config, not a dedicated service-level config.
For this service, the practical runner remains:

`cd services/discord && uv run pytest`

or equivalent direct use of `services/discord/.venv/bin/pytest`.

## Surprises Or Conflicts

### 1. `python -m app` is currently broken for the service, as expected

This is not a design conflict, but it is a concrete starting-state
fact: proposal 25 is fixing a missing entrypoint, not revising an
existing one.

### 2. `Settings()` requires `supabase_db_url` even though `app.__main__` will not use it directly

This is the main bootstrap surprise.

`Settings` currently requires:

- bot token
- guild id
- Supabase DB URL

([services/discord/app/core/settings.py](/home/nes/discord/services/discord/app/core/settings.py:8))

So proposal 25's `Settings()` bootstrap step will still fail fast
unless `SUPABASE_DB_URL` is present, even though the proposed
`__main__.py` itself does not open a database or wire repositories yet.

That is still consistent with the proposal because the entrypoint is
supposed to construct the full validated runtime settings object. It is
just worth calling out so implementation does not mistake the DB URL
requirement for a regression.

### 3. The repo has two bot entrypoint worlds right now

There is a legacy root daemon path in
[daemon/__main__.py](/home/nes/discord/daemon/__main__.py:102)
and the proposed service-package path in `services/discord/app/`.

That is not a blocker, but it means naming and documentation need to be
precise during implementation and later migration. The new file should
not import or preserve behavior from the old root daemon beyond general
operational patterns.

## Bottom Line

The hookpoint map is clean:

- `services/discord/app/__main__.py` does not exist yet
- `Settings()` already supports proposal 25's bootstrap pattern
- `HumilityBot(settings)` already supports proposal 25's construction
  and shutdown pattern
- `discord.utils.setup_logging` is available in installed
  `discord.py 2.7.1`
- no existing service tests need updating
- the only code addition needed for this proposal is the new
  `services/discord/app/__main__.py` file plus new tests for that file

The only notable operational surprise is that `Settings()` still
requires `SUPABASE_DB_URL` even though the proposed entrypoint will not
use that value directly.
