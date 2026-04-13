# Proposal: `services/api/app/core/settings.py`

Date: 2026-04-13

## Goal

Define `services/api/app/core/settings.py` as the API service's single
runtime configuration module.

Its job is to encode the environment contract already evidenced in
`.env.example`, expose the minimal application metadata the FastAPI
factory will need, and centralize startup-time validation in one
`BaseSettings` object.

This proposal is design only. It does not include implementation code.

## Design

The module should export one public settings class:

```python
class Settings(BaseSettings):
    app_name: str = "server-manager-api"
    app_version: str = "0.1.0"
    debug: bool = False
    api_prefix: str = "/api/v1"

    discord_bot_token: str = Field(..., repr=False)
    discord_guild_id: int
    discord_staging_guild_id: int | None = None

    supabase_db_url: str = Field(..., repr=False)
    supabase_service_key: str = Field(..., repr=False)

    google_cloud_vision_key: str | None = Field(default=None, repr=False)
    gemini_api_key: str | None = Field(default=None, repr=False)
    z_ai_api_key: str | None = Field(default=None, repr=False)
    minimax_api_key: str | None = Field(default=None, repr=False)
```

### Field inventory

- `app_name: str = "server-manager-api"`
  Default matches the API package name already declared in
  `services/api/pyproject.toml`.
- `app_version: str = "0.1.0"`
  Default matches the current package version.
- `debug: bool = False`
  Minimal scaffold flag for local development vs normal runtime.
- `api_prefix: str = "/api/v1"`
  Default versioned API mount prefix.
- `discord_bot_token: str = Field(..., repr=False)`
  Required runtime credential for Discord access.
- `discord_guild_id: int`
  Required primary guild identifier.
- `discord_staging_guild_id: int | None = None`
  Optional staging guild identifier for deployments that have one.
- `supabase_db_url: str = Field(..., repr=False)`
  Required database connection string. Marked sensitive because it may
  embed credentials.
- `supabase_service_key: str = Field(..., repr=False)`
  Required privileged Supabase API credential.
- `google_cloud_vision_key: str | None = Field(default=None, repr=False)`
  Optional provider credential.
- `gemini_api_key: str | None = Field(default=None, repr=False)`
  Optional provider credential.
- `z_ai_api_key: str | None = Field(default=None, repr=False)`
  Optional provider credential.
- `minimax_api_key: str | None = Field(default=None, repr=False)`
  Optional provider credential.

### Validation

Validation should stay intentionally narrow.

- Required presence is enforced by making
  `discord_bot_token`, `discord_guild_id`, `supabase_db_url`, and
  `supabase_service_key` required fields with no defaults.
- Integer validation for guild IDs is enforced by typing
  `discord_guild_id` as `int` and `discord_staging_guild_id` as
  `int | None`.
- No custom validator should be added for token shape, API key shape,
  URL scheme, password complexity, or environment mode.

This means the module relies on normal `BaseSettings` coercion and
validation instead of adding bespoke validators that the current
scaffold does not need yet.

### Settings behavior

- Follow the `ai-workflow` pattern by using a single
  `BaseSettings`-derived class in `app/core/`.
- Sensitive fields use `repr=False`.
- Do not configure `env_file` in `model_config`.
- Do not enable nested env parsing.
- Do not add deployment-only fields such as `RAILWAY_TOKEN`.

If `model_config` is defined at all, it should remain minimal and must
not include `env_file`, `env_nested_delimiter`, or secrets-directory
configuration. Omitting `model_config` entirely is acceptable for this
phase.

## Architecture

`Settings` belongs in `services/api/app/core/` because it is a
cross-cutting runtime concern, not business logic and not infrastructure
implementation.

In the layered pattern, it should fit like this:

- `core.settings` defines the runtime contract.
- The future app factory instantiates `Settings()` once at startup.
- The factory uses `settings.app_name`, `settings.app_version`, and
  `settings.debug` when constructing the FastAPI app.
- The factory mounts API routers under `settings.api_prefix`.
- The factory stores the settings object in one shared startup-owned
  location, such as `app.state.settings`, or wires it through
  dependency injection.
- Services, repositories, and infrastructure modules receive the
  settings object or the specific values they need from the factory or
  dependency layer; they do not instantiate `Settings()` themselves.

This keeps configuration ownership at the application boundary.

The module must not call `load_dotenv()` or read repo files directly.
Environment preparation belongs to the caller or process launcher. That
keeps the settings module usable in tests, local CLI entry points, and
hosted runtime environments without assuming a repo-root `.env`.

## Tradeoffs

- `repr=False` instead of `SecretStr`
  `repr=False` meets the immediate requirement to avoid leaking secrets
  in object representations without adding `.get_secret_value()`
  friction throughout the early scaffold. `SecretStr` can be adopted
  later if secret-handling needs become stricter.
- Flat fields instead of nested provider config
  The current env contract is flat, and there is no existing runtime
  need for grouped provider settings objects. Flat fields keep startup
  simple and match `.env.example`.
- Opaque `supabase_db_url: str` instead of DSN-specific validation
  The repo only proves that a DB URL is required, not that startup
  should reject every non-Postgres variant with custom logic. Keeping it
  as `str` avoids premature database-policy validation.
- No dotenv auto-loading
  The repo-root `.env` contains keys outside the API runtime surface,
  including `RAILWAY_TOKEN`. The settings module should not assume file
  location, dotenv policy, or permissive handling of unrelated keys.
- Hardcoded metadata defaults instead of dynamic package introspection
  Using `"server-manager-api"` and `"0.1.0"` as defaults matches current
  package metadata without adding file I/O or packaging lookups to the
  settings module.

## Anti-scope

This module should explicitly exclude:

- `RAILWAY_TOKEN`
  It is deployment tooling, not API runtime configuration.
- Middleware and HTTP server settings
  No CORS, gzip, allowed hosts, request logging, rate limiting, or
  similar flags belong here yet because the API scaffold does not expose
  those behaviors.
- Nested config objects
  No `discord=...`, `supabase=...`, or `providers=...` submodels, and
  no nested env delimiters.
- Credential-shape validation
  No regex rules, length policies, DSN scheme checks, or provider-key
  format checks should be added at this phase.
- Dotenv ownership
  The settings module does not discover `.env`, pick an env file path,
  or manage secrets directories.
- Runtime behavior beyond configuration loading
  No FastAPI factory logic, dependency functions, client construction,
  or provider enablement logic should live in `settings.py`.
