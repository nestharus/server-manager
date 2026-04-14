# Proposal: `services/discord/app/core/settings.py`

Date: 2026-04-13

## Goal

Define `services/discord/app/core/settings.py` as the Discord daemon
service's runtime configuration module.

Its job is to encode the minimal daemon settings contract already
evidenced by the current entry path and the repo-wide environment
surface, while keeping configuration ownership local to the Discord
service package.

This proposal is design only. It does not include implementation code.

## Design

The module should export one public settings class:

```python
class Settings(BaseSettings):
    discord_bot_token: str = Field(..., repr=False)
    discord_guild_id: int
    supabase_db_url: str = Field(..., repr=False)
```

### Field inventory

- `discord_bot_token: str = Field(..., repr=False)`
  Required bot credential. It is sensitive and should not appear in the
  model repr.
- `discord_guild_id: int`
  Required primary guild identifier for the daemon. It must be exposed
  directly as `settings.discord_guild_id`.
- `supabase_db_url: str = Field(..., repr=False)`
  Required PostgreSQL connection string for the daemon database. It is
  sensitive because it may embed credentials.

### Settings behavior

- `Settings` should inherit directly from `pydantic_settings.BaseSettings`.
- The module should remain independent from
  `services/api/app/core/settings.py`. The two services may share env
  var names, but they should not share a Python settings class.
- Field names should rely on normal `BaseSettings` env resolution, which
  maps cleanly onto the existing unprefixed repo env names:
  `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, and `SUPABASE_DB_URL`.
- Constructor keyword arguments must override environment values so this
  smoke-test shape works exactly:

```python
Settings(
    discord_bot_token="test",
    discord_guild_id=1,
    supabase_db_url="postgresql://test",
)
```

- The module should not auto-load dotenv files. Do not set
  `env_file` in `model_config`, and do not call `load_dotenv()` inside
  `settings.py`.
- Validation should stay narrow:
  - required presence for all three fields
  - integer coercion/validation for `discord_guild_id`
  - no custom token validators
  - no DB URL scheme validator beyond the plain string contract

## Architecture

`settings.py` belongs under `services/discord/app/core/` because it is
application-boundary configuration, not Discord client logic and not
business workflow code.

Recommended ownership:

- `core.settings` defines the daemon runtime contract.
- The daemon startup path instantiates `Settings()` once.
- Bot construction, intents, and client options consume that settings
  object; they do not live inside `settings.py`.

This keeps the configuration surface small and prevents the settings
module from becoming a second startup framework.

## Tradeoffs

- Separate daemon settings class instead of importing the API settings
  class
  This duplicates a small amount of field naming, but it preserves the
  service boundary and avoids coupling the Discord daemon package to API
  runtime concerns it does not own.
- `supabase_db_url: str` instead of `PostgresDsn`
  Keeping the field as `str` matches the synthesized requirement
  directly and avoids adding stricter URL-policy validation into an
  early settings module. The downside is that malformed non-Postgres
  URLs are not rejected here.
- No dotenv auto-loading
  This matches the API settings pattern and avoids the monorepo `.env`
  pitfalls where unrelated keys can affect settings parsing. The cost is
  that entry points or tests that want dotenv behavior must opt into it
  explicitly.
- `repr=False` instead of `SecretStr`
  `repr=False` satisfies the immediate leak-prevention requirement
  without adding secret-wrapper ergonomics to every consumer. The
  downside is that the fields remain plain strings at runtime.
- Minimal three-field surface
  This keeps the daemon contract anchored to what the research actually
  proves today. The cost is that future runtime needs will require
  additive changes instead of pre-reserved placeholders.

## Anti-scope

This module should explicitly exclude:

- API metadata fields such as `app_name`, `app_version`, `debug`, or
  `api_prefix`
- `discord_staging_guild_id`
- `supabase_service_key`
- OCR / LLM provider keys
- API base URLs or other cross-service transport settings not yet used
  by the daemon
- Discord client constructor options such as intents, member cache
  flags, or chunking flags
- nested settings models, env prefixes, or compatibility aliases
- dotenv ownership, secrets-directory loading, or repo file discovery
- custom validators for token shape, guild range, or DB URL format
- singleton helpers, cached global settings accessors, or other startup
  orchestration logic

## Test Contract

The eventual implementation should be accepted only if tests encode
this contract:

- `Settings(discord_bot_token="test", discord_guild_id=1, supabase_db_url="postgresql://test")`
  constructs successfully.
- The constructed object exposes `settings.discord_guild_id == 1`.
- `Settings()` reads `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, and
  `SUPABASE_DB_URL` from the environment with no prefix configuration.
- Explicit constructor kwargs override environment values.
- Missing any of the three required fields raises `ValidationError`.
- `discord_guild_id` is validated/coerced as an integer.
- `repr(settings)` does not reveal `discord_bot_token` or
  `supabase_db_url`.
- Tests must not encode implicit dotenv loading. If env vars are absent,
  the presence of a `.env` file alone must not make `Settings()`
  succeed.
- Tests must not require DSN-specific rejection behavior beyond the
  accepted smoke-test value `postgresql://test`.

## Decision

Keep the Discord daemon settings module intentionally small: one
service-local `BaseSettings` class with exactly three fields, no dotenv
auto-loading, and no broader runtime policy embedded in configuration.
