# Hookpoint Research: Discord Bot Module

Date: 2026-04-13

## Scope

This note maps
[proposals/24-discord-bot.md](/home/nes/discord/proposals/24-discord-bot.md:1)
onto the current repository.

It is hookpoint-only research. It answers:

- what exists today under `services/discord/app/core/`
- what reusable patterns already exist under `services/discord/tests/`
- what the live daemon entrypoint in `daemon/__main__.py` already does
- what parts of the old daemon are the real integration seam for a
  future `services/discord/app/core/bot.py`
- what mismatches or anti-scope need to stay out of the minimal bot
  module

It does not include implementation code.

## Primary Sources

- Proposal:
  [proposals/24-discord-bot.md](/home/nes/discord/proposals/24-discord-bot.md:1)
- Problem-space research:
  [research/24-discord-bot.md](/home/nes/discord/research/24-discord-bot.md:1)
- Needs synthesis:
  [research/24-discord-bot-needs.md](/home/nes/discord/research/24-discord-bot-needs.md:1)
- Discord service package metadata:
  [services/discord/pyproject.toml](/home/nes/discord/services/discord/pyproject.toml:1)
- Existing Discord service core package:
  [services/discord/app/core/__init__.py](/home/nes/discord/services/discord/app/core/__init__.py)
  [services/discord/app/core/settings.py](/home/nes/discord/services/discord/app/core/settings.py:1)
- Existing Discord service tests:
  [services/discord/tests/test_settings.py](/home/nes/discord/services/discord/tests/test_settings.py:1)
- Live daemon entrypoint:
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:1)
- Current daemon workflow/config seams:
  [daemon/config.py](/home/nes/discord/daemon/config.py:1)
  [daemon/db.py](/home/nes/discord/daemon/db.py:1)
  [daemon/applications.py](/home/nes/discord/daemon/applications.py:1)
  [daemon/claim.py](/home/nes/discord/daemon/claim.py:1)

## 1. What exists today in `services/discord/app/core/`

### `core` already contains validated settings, but no bot module

`services/discord/app/core/` currently contains:

- [services/discord/app/core/__init__.py](/home/nes/discord/services/discord/app/core/__init__.py)
- [services/discord/app/core/settings.py](/home/nes/discord/services/discord/app/core/settings.py:1)

`__init__.py` is empty. The only real module is `settings.py`, which
already defines:

- `Settings(BaseSettings)`
- `discord_bot_token: str = Field(repr=False)`
- `discord_guild_id: int`
- `supabase_db_url: str = Field(repr=False)`

([services/discord/app/core/settings.py](/home/nes/discord/services/discord/app/core/settings.py:5))

There is no existing:

- `bot.py`
- `HumilityBot` symbol under `services/discord/app/core/`
- local bot factory
- Discord-service startup module under `services/discord/app/`

So proposal 24's target file,
`services/discord/app/core/bot.py`, is greenfield inside the service
package. The direct in-package hookpoint is only the already-approved
`Settings` class.

### The service package already has the required runtime dependency

`services/discord` already depends on `discord.py>=2.3`
([services/discord/pyproject.toml](/home/nes/discord/services/discord/pyproject.toml:6)).
That means proposal 24 does not need a dependency or packaging change
to add a local bot module.

## 2. What test patterns already exist in `services/discord/tests/`

### The current Discord-service tests are narrow settings unit tests

Today `services/discord/tests/` contains one real test module:

- [services/discord/tests/test_settings.py](/home/nes/discord/services/discord/tests/test_settings.py:1)

There are no existing bot tests, no async Discord interaction tests,
and no integration harness for `commands.Bot`. That means proposal 24
will not be plugging into a pre-existing bot-test scaffold. The only
local test style evidence comes from the settings tests.

### Established patterns from `test_settings.py`

The current test file uses a very small, flat `pytest` style:

- function-style tests only, no test classes
- direct object construction at the call site
- direct field assertions
- one behavior per test
- `pytest.raises(ValidationError)` for negative construction paths
- `monkeypatch` for environment manipulation
- explicit checks for secret redaction in `repr(...)`

Concrete examples:

- direct constructor use:
  [services/discord/tests/test_settings.py](/home/nes/discord/services/discord/tests/test_settings.py:7)
- negative validation checks:
  [services/discord/tests/test_settings.py](/home/nes/discord/services/discord/tests/test_settings.py:30)
- env-driven construction:
  [services/discord/tests/test_settings.py](/home/nes/discord/services/discord/tests/test_settings.py:92)

### Why those patterns matter for proposal 24

Proposal 24's acceptance criteria are also constructor-focused:

- construct `HumilityBot(Settings(...))`
- assert `bot.settings`
- assert internal intent flags
- assert no login side effects at construction time

That aligns well with the existing local test style. The strongest
hookpoint from the current tests is the pattern of testing the public
constructor contract directly, without helper factories and without
networked integration setup.

### What is not yet evidenced in local tests

The Discord service's dev dependencies already include:

- `pytest-asyncio`
- `pytest-mock`

([services/discord/pyproject.toml](/home/nes/discord/services/discord/pyproject.toml:18))

But `services/discord/tests/` does not currently use either one. So
there is no local precedent yet for:

- async bot lifecycle tests
- Discord object mocks
- patching `commands.Bot` internals
- command-tree assertions beyond plain object inspection

That absence matters because proposal 24 is intentionally narrow. The
best local fit is still small constructor-contract tests rather than
startup or gateway tests.

## 3. What `daemon/__main__.py` already does

### It owns the live daemon startup path today

The current root daemon entrypoint is still the active composition
root. It does all of the following:

- loads `.env` from the repo root with `load_dotenv(...)`
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:31))
- reads `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, and `DATABASE_PATH`
  directly from environment variables
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:42))
- parses `DISCORD_GUILD_ID` to `int`
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:52))
- derives a default SQLite path when `DATABASE_PATH` is absent
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:57))
- loads daemon YAML config with `load_config(...)`
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:104))
- opens SQLite with `open_database(...)`
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:105))
- sets `PRAGMA busy_timeout = 5000`
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:108))
- constructs the current bot
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:109))
- starts the Discord gateway with `await bot.start(runtime.token)`
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:117))
- closes the database in `finally`
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:119))

So `daemon/__main__.py` is not just a tiny launcher. It currently owns
configuration loading, infrastructure setup, bot construction, startup,
and shutdown.

### It already contains a legacy `HumilityBot(commands.Bot)`

`daemon/__main__.py` already defines a `HumilityBot` subclass:

- class definition:
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:74)
- base-class init call:
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:84)

The current constructor is not the proposal 24 contract. It requires:

- `guild_id`
- `config`
- `conn`
- `intents`
- `base_path`

([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:75))

It then stores those values on custom attributes:

- `self.guild_id`
- `self.config`
- `self.conn`
- `self.base_path`

([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:85))

This is important hookpoint evidence because the repo already has a
working `commands.Bot` subclass, but its boundary is much wider than
proposal 24 allows.

### The current daemon already has a bot-local intents helper

The entry module defines:

```python
def build_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True
    intents.message_content = False
    return intents
```

([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:66))

That is the clearest direct code hookpoint for proposal 24's
module-owned intent policy. The key mismatch is that proposal 24 wants:

- `guilds = True`
- `members = True`
- `message_content = True`
- `presences = False`

while the live daemon currently sets `message_content = False` and does
not mention `presences`.

So the hookpoint is the shape of the helper, not its exact policy.

### `setup_hook()` already owns slash-command registration and sync

The current bot's `setup_hook()` performs visible runtime behavior:

- creates a guild object from `self.guild_id`
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:91))
- registers a guild-scoped `/ping` command
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:93))
- calls `setup_applications(self)`
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:98))
- syncs the command tree to the guild
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:99))

Proposal 24 explicitly excludes:

- slash-command registration
- `setup_hook()`
- `tree.sync()`
- event handlers and task wiring

([proposals/24-discord-bot.md](/home/nes/discord/proposals/24-discord-bot.md:110))

That means `setup_hook()` is a downstream lifecycle seam, not part of
the future minimal `core.bot` contract.

## 4. Direct hookpoints and mismatches for proposal 24

### The strongest direct hookpoint is `Settings`

Proposal 24 wants:

```python
HumilityBot(Settings(...))
```

The repo already has the exact `Settings` module and field names needed
for that constructor contract
([services/discord/app/core/settings.py](/home/nes/discord/services/discord/app/core/settings.py:5)).

This is the cleanest existing seam because it keeps the new bot module
inside `services/discord/app/core/` and avoids copying the old daemon's
broader runtime shape.

### The existing daemon bot is a reference implementation, not a direct API

What is reusable from `daemon/__main__.py`:

- subclassing `commands.Bot`
- using `command_prefix=commands.when_mentioned`
- keeping intent construction local to the bot boundary
- deferring gateway connection until `start(...)`

What is only evidence and should not be preserved as the new API:

- constructor injection of `guild_id`, `config`, `conn`, and `base_path`
- storing runtime infrastructure directly on the bot instance
- `setup_hook()` registration work
- command syncing during construction/startup composition
- dotenv loading and manual env reads

So the hookpoint is "extract the minimal bot construction boundary from
the old entrypoint shape", not "reuse the old constructor surface".

### The old runtime config is not the right abstraction to preserve

`daemon/__main__.py` also defines `RuntimeConfig` with:

- `token`
- `guild_id`
- `base_path`
- `database_path`

([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:34))

That dataclass is evidence for current startup ownership, but it is not
the proposal 24 contract. Proposal 24 centers the already-validated
service `Settings` object instead. So `RuntimeConfig` is a legacy
bootstrap wrapper, not a hookpoint for the new bot module.

## 5. Surrounding daemon code that proves why the bot module must stay narrow

### Application and claim workflows already depend on the wider old bot shape

The current daemon code outside `__main__.py` expects the legacy bot to
carry more than just settings:

- application flow helpers inspect `bot.config` and attach ephemeral
  session state to the bot object
  ([daemon/applications.py](/home/nes/discord/daemon/applications.py:381))
- claim visibility helpers assume guild/member workflows handled by the
  running daemon stack
  ([daemon/claim.py](/home/nes/discord/daemon/claim.py:40))

This is useful hookpoint evidence because it shows why proposal 24
stops at pure construction. If `core.bot` tried to absorb current
workflow wiring now, it would pull daemon configuration, database, and
interaction concerns into a module that is supposed to stay smoke-test
friendly.

### Database and config setup remain outside the proposed module

The current daemon still relies on:

- YAML-backed daemon config
  ([daemon/config.py](/home/nes/discord/daemon/config.py:95))
- SQLite database bootstrapping
  ([daemon/db.py](/home/nes/discord/daemon/db.py:79))

Those are live runtime seams, but they are not hookpoints for proposal
24's `core.bot` file. They belong to a later startup/composition phase.

## 6. File-level mapping implied by the current tree

### Required new code file

- `services/discord/app/core/bot.py`

Nothing in `services/discord/app/core/` currently satisfies proposal
24's bot contract.

### Existing file that is the direct local dependency

- [services/discord/app/core/settings.py](/home/nes/discord/services/discord/app/core/settings.py:1)

That file is the only current service-local dependency the proposed bot
module should need.

### Existing file that is the real migration seam

- [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:1)

That file currently owns the bot subclass, intents, startup, and
registration path. It is the main source to mine for behavior during a
later implementation phase.

### Existing test file that defines the nearest local testing style

- [services/discord/tests/test_settings.py](/home/nes/discord/services/discord/tests/test_settings.py:1)

That file does not test Discord runtime behavior, but it does establish
the preferred local style for constructor-contract tests.

## Decision-Relevant Summary

Proposal 24 maps cleanly onto the current tree as a new
`services/discord/app/core/bot.py` module with one direct local
dependency, `app.core.settings.Settings`.

The main reusable evidence already exists, but it is split across two
places:

- `services/discord/app/core/settings.py` supplies the correct service
  configuration object
- `daemon/__main__.py` proves the repo already uses
  `commands.Bot`, `commands.when_mentioned`, a local `build_intents()`
  helper, and deferred startup via `bot.start(...)`

The main implementation risk to avoid later is copying too much of the
legacy daemon boundary into the new module. `setup_hook()`, config/db
injection, dotenv loading, runtime config parsing, and command sync are
all current daemon responsibilities, but they are not hookpoints for
the minimal bot-construction module approved in proposal 24.
