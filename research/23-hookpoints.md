# Hookpoint Research: Discord Settings Module

Date: 2026-04-13

## Scope

This note maps
[proposals/23-discord-settings.md](/home/nes/discord/proposals/23-discord-settings.md:1)
onto the current repository.

It is hookpoint-only research. It answers:

- what exists today under `services/discord/app/core/`
- what surrounding Discord-side code is the real integration seam
- what test patterns already exist under `services/api/tests/`
- what parts of the API settings implementation are reusable as shape
  only
- what parallel systems or mismatched runtime code must be avoided

It does not include implementation code.

## Primary Sources

- Proposal:
  [proposals/23-discord-settings.md](/home/nes/discord/proposals/23-discord-settings.md:1)
- Problem-space research:
  [research/23-discord-settings.md](/home/nes/discord/research/23-discord-settings.md:1)
- Needs synthesis:
  [research/23-discord-settings-needs.md](/home/nes/discord/research/23-discord-settings-needs.md:1)
- Target package seam:
  [services/discord/app/core/__init__.py](/home/nes/discord/services/discord/app/core/__init__.py)
- Discord service package metadata:
  [services/discord/pyproject.toml](/home/nes/discord/services/discord/pyproject.toml:1)
- Current repo env surface:
  [.env.example](/home/nes/discord/.env.example:1)
- Live daemon entry path:
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:1)
- Current Discord-side database seam:
  [daemon/db.py](/home/nes/discord/daemon/db.py:1)
- Closest implementation reference:
  [services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:1)
- Existing API test patterns:
  [services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:1)
  [services/api/tests/test_factory.py](/home/nes/discord/services/api/tests/test_factory.py:1)
  [services/api/tests/test_contracts_base.py](/home/nes/discord/services/api/tests/test_contracts_base.py:1)

## 1. What exists today in `services/discord/app/core/`

### The package exists, but it is only an empty seam

Today `services/discord/app/core/` contains exactly one tracked file:

- [services/discord/app/core/__init__.py](/home/nes/discord/services/discord/app/core/__init__.py)

That file is empty. There is no:

- `settings.py`
- factory module
- startup helper
- package-level re-export
- existing `Settings` symbol to preserve

The surrounding service package is also mostly scaffold-only right now:

- [services/discord/app/__init__.py](/home/nes/discord/services/discord/app/__init__.py)
- `services/discord/app/commands/`
- `services/discord/app/handlers/`
- `services/discord/app/tasks/`

Those directories exist, but there is no live Discord-service runtime
code under `services/discord/app/` yet. That means proposal 23's target
module is mostly greenfield inside the service package.

### The Discord service already has the required dependencies

`services/discord` already depends on both `pydantic` and
`pydantic-settings`
([services/discord/pyproject.toml](/home/nes/discord/services/discord/pyproject.toml:5)).

That matters because proposal 23 only needs a direct
`BaseSettings`-based module
([proposals/23-discord-settings.md](/home/nes/discord/proposals/23-discord-settings.md:42)).
No dependency edit is required to add `services/discord/app/core/settings.py`.

## 2. The real current integration seam is outside `services/discord/app/core/`

### `daemon/__main__.py` is the live daemon-side configuration owner today

The active Discord daemon still gets runtime configuration from the old
top-level daemon entry module, not from `services/discord/app/core/`.

Concrete evidence:

- module-level dotenv loading:
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:28)
- manual env reads for `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID`:
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:42)
- integer parsing for `DISCORD_GUILD_ID`:
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:52)
- startup instantiates runtime config once and passes values into bot
  construction:
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:102)

So the future `services/discord/app/core/settings.py` does not have an
existing in-package caller to plug into yet. The current caller seam is
the old daemon entry path.

### `discord_bot_token` and `discord_guild_id` map to live code; `supabase_db_url` does not

Proposal 23's three fields are:

- `discord_bot_token`
- `discord_guild_id`
- `supabase_db_url`

([proposals/23-discord-settings.md](/home/nes/discord/proposals/23-discord-settings.md:21))

Only the first two have a direct live Discord-side consumer today:

- `DISCORD_BOT_TOKEN`:
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:43)
- `DISCORD_GUILD_ID`:
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:44)

The database side is currently a different system entirely. The daemon
still uses SQLite path configuration:

- `DATABASE_PATH` env read:
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:45)
- default SQLite database path:
  [daemon/db.py](/home/nes/discord/daemon/db.py:11)
- `resolve_database_config(...)` based on `DATABASE_PATH`:
  [daemon/db.py](/home/nes/discord/daemon/db.py:79)

That means `supabase_db_url` is not a hookpoint into existing
Discord-service runtime code yet. It is currently evidenced by the
shared env surface and the API service, not by a Discord-side consumer.

### `.env.example` is the naming hookpoint for the proposal

The repo-wide env file already exposes exactly the three names proposal
23 wants to rely on:

- `DISCORD_BOT_TOKEN`
- `DISCORD_GUILD_ID`
- `SUPABASE_DB_URL`

([.env.example](/home/nes/discord/.env.example:1))

This is the clean field-name hookpoint for the new settings module.
It also reinforces the proposal's requirement to use normal
`BaseSettings` env resolution with no prefix layer
([proposals/23-discord-settings.md](/home/nes/discord/proposals/23-discord-settings.md:46)).

## 3. What code is reusable, and what is only a reference

### `services/api/app/core/settings.py` is a structural reference, not a shared dependency

The API service already has a working `Settings(BaseSettings)` model
with flat typed fields and `Field(..., repr=False)` on sensitive values
([services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:5)).

The reusable part is its shape:

- one public `Settings` class
- direct `BaseSettings` inheritance
- flat class attributes
- `repr=False` for secret-bearing strings

The non-reusable part is just as important:

- API metadata fields such as `app_name`, `app_version`, `debug`,
  `api_prefix`
- Discord staging guild support
- Supabase service key
- OCR / LLM provider keys

([services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:6))

Proposal 23 explicitly excludes those broader API/runtime concerns
([proposals/23-discord-settings.md](/home/nes/discord/proposals/23-discord-settings.md:111)).
So the hookpoint is "copy the architecture locally", not "import the
API settings class into the Discord service".

### The current daemon `RuntimeConfig` is evidence, not a reusable target abstraction

The old daemon entry module already has a `RuntimeConfig` dataclass
([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:34)),
but it is not the same contract as proposal 23:

- it stores `token`, not `discord_bot_token`
- it stores `database_path`, not `supabase_db_url`
- it carries path/bootstrap concerns the proposal excludes

So it is evidence for current startup ownership, but it is not the
abstraction proposal 23 should preserve.

## 4. Files and integration points implied by the current tree

### Required new code file

- `services/discord/app/core/settings.py`

That is the direct target and the main new file. Nothing under
`services/discord/app/core/` currently satisfies the proposal.

### File that may stay unchanged in this phase

- [services/discord/app/core/__init__.py](/home/nes/discord/services/discord/app/core/__init__.py)

There is no evidence yet that a package-level re-export is required.
The proposal asks for a public `Settings` class in the module, not for
an `app.core` package API
([proposals/23-discord-settings.md](/home/nes/discord/proposals/23-discord-settings.md:19)).

### Existing caller that will eventually need adaptation

When proposal 23 is implemented, the most direct existing caller seam is
still the old daemon entry path:

- runtime loading in
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:42)
- startup composition in
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:102)

That is where the current manual env logic lives. There is no
Discord-service-local startup module yet under `services/discord/app/`.

## 5. Test patterns already established in `services/api/tests/`

### The dominant style is small, flat `pytest` unit tests

Across the current API tests, the pattern is consistent:

- function-style tests only, no test classes
- one behavior per test
- top-of-file helpers for shared setup
- direct object construction
- direct assertions on fields or metadata
- `pytest.raises(ValidationError)` for negative paths

Examples:

- env helper functions plus direct `Settings()` construction in
  [services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:24)
- direct error checks for missing required env vars in
  [services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:45)
- direct object assertions in
  [services/api/tests/test_factory.py](/home/nes/discord/services/api/tests/test_factory.py:38)
- direct Pydantic model/schema assertions in
  [services/api/tests/test_contracts_base.py](/home/nes/discord/services/api/tests/test_contracts_base.py:15)

This fits proposal 23 well. A Discord settings test file should not
need endpoint tests, fixtures, or framework-heavy scaffolding.

### Environment setup pattern: explicit `monkeypatch` control

The API settings tests already use the exact pattern proposal 23 needs
for env-driven settings behavior:

- clear env with `monkeypatch.delenv(...)`
- set only the required env vars with `monkeypatch.setenv(...)`
- instantiate `Settings()`
- assert field values or validation failures

The clearest examples are:

- `_clear_settings_env(...)` in
  [services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:24)
- `_set_required_env(...)` in
  [services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:29)
- required-field failure checks in
  [services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:45)

This is the direct reusable test pattern for:

- reading `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `SUPABASE_DB_URL`
  from env
- validating missing fields
- validating guild-id integer coercion

### Sensitive `repr(...)` assertions already have a local precedent

Proposal 23 requires `repr(settings)` not to leak secrets
([proposals/23-discord-settings.md](/home/nes/discord/proposals/23-discord-settings.md:143)).

The API settings tests already encode exactly that style of check:

- token redaction:
  [services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:114)
- DB URL redaction:
  [services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:122)

Those tests are a direct pattern match for the Discord settings module.

### Constructor-injection precedence already has a local pattern

Proposal 23 requires explicit constructor kwargs to override env values
([proposals/23-discord-settings.md](/home/nes/discord/proposals/23-discord-settings.md:49)).

The API settings tests already verify environment reads on the settings
model
([services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:170)),
and the API factory tests verify the broader project pattern of
"provided object wins; do not instantiate a replacement" by patching
`Settings` to fail if called
([services/api/tests/test_factory.py](/home/nes/discord/services/api/tests/test_factory.py:46)).

The exact constructor-over-env assertion does not already exist in
`services/api/tests/test_settings.py`, but the surrounding test style
for explicit injection and explicit environment control does.

### Import-path pattern matters

The API tests import from package root `app...`, not from filesystem
paths under `services.api...`:

- direct `app.core.settings` import:
  [services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:4)
- `sys.path` adjustment plus `app.core.factory` import:
  [services/api/tests/test_factory.py](/home/nes/discord/services/api/tests/test_factory.py:8)

That means any future Discord-service tests should expect the packaged
import root to be `app`, consistent with
`services/discord/pyproject.toml`
([services/discord/pyproject.toml](/home/nes/discord/services/discord/pyproject.toml:26)).

### One proposal-required test has no current API precedent

Proposal 23 says tests must prove there is no implicit dotenv loading
inside `settings.py`
([proposals/23-discord-settings.md](/home/nes/discord/proposals/23-discord-settings.md:145)).

There is no existing API test for that. A repo search found no
`dotenv`, `load_dotenv`, `env_file`, or `.env` assertions under
`services/api/tests/` or `services/api/app/core/`.

That gap matters because the closest existing daemon-side behavior is
the opposite: `daemon/__main__.py` intentionally calls `load_dotenv(...)`
at import time
([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:31)).

So for proposal 23:

- reuse the API settings test style
- do not reuse the daemon entry's dotenv-loading behavior
- add a new Discord-settings-specific no-dotenv test because there is
  no existing API precedent to copy

## 6. Reusable hookpoints summary

- The direct module hookpoint is a new file:
  `services/discord/app/core/settings.py`.
- The package seam already exists, but it is empty:
  [services/discord/app/core/__init__.py](/home/nes/discord/services/discord/app/core/__init__.py).
- The live startup integration seam is still the old daemon entry path:
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:42).
- `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID` have live daemon-side
  evidence; `SUPABASE_DB_URL` currently does not. Discord-side DB
  runtime code still points at `DATABASE_PATH` and SQLite
  ([daemon/db.py](/home/nes/discord/daemon/db.py:79)).
- The best reusable test patterns come from
  [services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:1)
  and
  [services/api/tests/test_contracts_base.py](/home/nes/discord/services/api/tests/test_contracts_base.py:1):
  flat `pytest`, explicit `monkeypatch` env control, direct model
  construction, `ValidationError` checks, and repr-redaction asserts.
- The main duplicate system to avoid is importing or subclassing the API
  settings model. Proposal 23 wants a separate Discord-service-local
  `BaseSettings` class sharing env names, not a shared Python settings
  object
  ([proposals/23-discord-settings.md](/home/nes/discord/proposals/23-discord-settings.md:43)).
