# Research: API Settings Module

Date: 2026-04-13

## Scope

This note documents the current problem space for implementing a
settings module for the FastAPI service under `services/api/`.

It is limited to:

- what configuration the API scaffold currently evidences
- what the `ai-workflow` reference settings module demonstrates
- what `pydantic-settings` documents for environment loading, dotenv
  handling, and nested config
- what security implications follow from the current env surface and
  local Pydantic behavior
- what validation is justified at the current scaffold stage

It does not propose a final settings class design, startup flow, or
future production configuration policy.

## Local Baseline

- The API service is intended to follow the same layered shape as the
  reference app: `api -> services -> repositories -> infrastructure`
  ([services/api/app/__init__.py](/home/nes/discord/services/api/app/__init__.py:1),
  [AGENTS.md](/home/nes/discord/AGENTS.md:365)).
- `services/api/` already depends on `fastapi`, `pydantic`,
  `pydantic-settings`, `orjson`, and `python-dotenv`, but the package
  itself is still just the package marker plus `core/`
  ([services/api/pyproject.toml](/home/nes/discord/services/api/pyproject.toml:6),
  [services/api/app/core/__init__.py](/home/nes/discord/services/api/app/core/__init__.py:1)).
- The repo-level environment contract currently lives in
  [.env.example](/home/nes/discord/.env.example:1), not in an
  API-specific example file.
- Existing sibling runtime code loads the repo-root `.env` by explicit
  path and treats `DISCORD_BOT_TOKEN` as required and
  `DISCORD_GUILD_ID` as a required integer
  ([discord_cli.py](/home/nes/discord/discord_cli.py:17),
  [discord_cli.py](/home/nes/discord/discord_cli.py:50),
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:27),
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:42)).
- The same token/id requirements are covered by current tests
  ([tests/test_discord_cli.py](/home/nes/discord/tests/test_discord_cli.py:371),
  [tests/test_discord_cli.py](/home/nes/discord/tests/test_discord_cli.py:387),
  [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:100),
  [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:124)).
- Real `.env` files are ignored by git while `.env.example` is kept in
  the repo
  ([.gitignore](/home/nes/discord/.gitignore:1)).

## Primary Sources

- Local repo files:
  - [.env.example](/home/nes/discord/.env.example:1)
  - [services/api/pyproject.toml](/home/nes/discord/services/api/pyproject.toml:1)
  - [services/api/app/__init__.py](/home/nes/discord/services/api/app/__init__.py:1)
  - [.refs/ai-workflow/app/core/settings.py](/home/nes/discord/.refs/ai-workflow/app/core/settings.py:1)
  - [discord_cli.py](/home/nes/discord/discord_cli.py:1)
  - [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:1)
  - [tests/test_discord_cli.py](/home/nes/discord/tests/test_discord_cli.py:371)
  - [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:100)
  - [.gitignore](/home/nes/discord/.gitignore:1)
  - [AGENTS.md](/home/nes/discord/AGENTS.md:365)
- Official Pydantic sources:
  - `pydantic-settings` docs:
    https://raw.githubusercontent.com/pydantic/pydantic-settings/main/docs/index.md
  - `SecretStr` docs:
    https://docs.pydantic.dev/latest/api/types/
- Local runtime inspection:
  - `services/api/.venv/bin/python` reports `pydantic 2.13.0` and
    `pydantic-settings 2.13.1`
  - local experiments comparing `Field(repr=False)` vs `SecretStr`
  - local `BaseSettings` experiment showing that an `env_file` with an
    unknown key raises `ValidationError` under the default dotenv
    handling

## 1. What configuration the API service needs at this scaffold stage

The current scaffold shows an environment surface, but not yet a full
runtime policy.

What is clearly evidenced now:

- Discord integration settings:
  - `DISCORD_BOT_TOKEN`
  - `DISCORD_GUILD_ID`
  - `DISCORD_STAGING_GUILD_ID`
  These are present in [.env.example](/home/nes/discord/.env.example:2).
  Sibling runtime code already requires the token and parses
  `DISCORD_GUILD_ID` as `int`
  ([discord_cli.py](/home/nes/discord/discord_cli.py:51),
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:43)).
- Data/backend settings:
  - `SUPABASE_DB_URL`
  - `SUPABASE_SERVICE_KEY`
  These are present in [.env.example](/home/nes/discord/.env.example:7).
  The names imply one database connection string and one privileged API
  credential, but the API package does not yet show how either one is
  consumed.
- Deployment/operator setting:
  - `RAILWAY_TOKEN`
  This is present in [.env.example](/home/nes/discord/.env.example:11),
  but the current API scaffold does not evidence that it is required by
  the FastAPI process itself rather than by deployment tooling.
- External provider credentials:
  - `GOOGLE_CLOUD_VISION_KEY`
  - `GEMINI_API_KEY`
  - `Z_AI_API_KEY`
  - `MINIMAX_API_KEY`
  These are present in [.env.example](/home/nes/discord/.env.example:14).
  Their presence shows planned integrations, but not whether they are
  startup-critical, feature-scoped, optional, or mutually exclusive.

What is not yet evidenced by the current scaffold:

- service-level HTTP settings such as CORS, allowed hosts, gzip,
  request logging, or rate limits
- application identity settings such as `app_name`, `debug`, or
  `api_prefix`, beyond package metadata in
  [services/api/pyproject.toml](/home/nes/discord/services/api/pyproject.toml:1)
- an environment label such as `ENVIRONMENT`, `MODE`, or a
  staging/production discriminator
- a documented secret-source policy such as direct env vars only,
  dotenv files, or file-based secrets

At this stage, the problem is therefore narrower than "what settings
does a production FastAPI service eventually need?" The immediate
problem is "how should the API encode the environment contract already
declared by the repo, while the service-specific runtime surface is
still mostly absent?"

## 2. What patterns from the `ai-workflow` reference should be adopted vs. adapted

The reference settings module is
[.refs/ai-workflow/app/core/settings.py](/home/nes/discord/.refs/ai-workflow/app/core/settings.py:1).
It demonstrates both reusable configuration patterns and stack-specific
choices.

Patterns that are directly supported by the reference:

- A single `BaseSettings`-derived runtime configuration object
  ([settings.py](/home/nes/discord/.refs/ai-workflow/app/core/settings.py:75)).
  That matches Humility's reserved `services/api/app/core/` role for
  settings
  ([AGENTS.md](/home/nes/discord/AGENTS.md:365)).
- Field-level validation using `field_validator` for settings with
  concrete invariants
  ([settings.py](/home/nes/discord/.refs/ai-workflow/app/core/settings.py:150)).
- Custom error classes for configuration failures instead of generic
  `ValueError` strings
  ([settings.py](/home/nes/discord/.refs/ai-workflow/app/core/settings.py:43)).
- Explicit treatment of sensitive fields via `repr=False`
  ([settings.py](/home/nes/discord/.refs/ai-workflow/app/core/settings.py:113)).

Patterns that need adaptation rather than reuse:

- The reference field inventory is for a different application stack:
  SurrealDB, Elasticsearch, middleware toggles, CSV paths, and
  knowledge-store directories
  ([settings.py](/home/nes/discord/.refs/ai-workflow/app/core/settings.py:92)).
  Humility's current surface is Discord, Supabase, Railway, and model
  provider credentials.
- The reference URL validators are written for `ws` / `wss` / `http` /
  `https` SurrealDB URLs and `http` / `https` Elasticsearch URLs
  ([settings.py](/home/nes/discord/.refs/ai-workflow/app/core/settings.py:150)).
  The current repo-level DB URL example is Postgres-shaped
  (`postgresql://...`) instead
  ([.env.example](/home/nes/discord/.env.example:7)).
- The reference credential complexity regex is designed for locally
  chosen usernames and passwords
  ([settings.py](/home/nes/discord/.refs/ai-workflow/app/core/settings.py:8)).
  The Humility env surface is mostly opaque third-party tokens and API
  keys, so password-complexity validation does not follow from the
  current evidence.
- The reference middleware defaults are tied to a mature HTTP service
  surface that the Humility API scaffold does not yet expose
  ([settings.py](/home/nes/discord/.refs/ai-workflow/app/core/settings.py:84)).

Evidence-based conclusion: the reference justifies adopting the
`BaseSettings` + validators + secret-aware field treatment pattern, but
it does not justify copying the reference field list or its exact
validation rules.

## 3. How `pydantic-settings` handles env loading, `.env` files, and nested config

The official `pydantic-settings` documentation defines the behavior of
`BaseSettings`.

### Base env loading and precedence

The docs state that a `BaseSettings` model reads fields not provided at
initialization time from the environment, while field defaults still
apply when no matching value exists
(`pydantic-settings` docs, lines 0-8:
https://raw.githubusercontent.com/pydantic/pydantic-settings/main/docs/index.md).

The same doc states:

- `BaseSettings` validates default values by default
  (lines 5-6)
- `env_prefix` applies to env vars, dotenv files, secrets, and other
  sources
  (lines 8-10)
- env names are case-insensitive by default unless `case_sensitive=True`
  is set
  (lines 12-16)

The documented default source priority is:

1. CLI arguments, if CLI parsing is enabled
2. `Settings(...)` initializer arguments
3. environment variables
4. dotenv values
5. secrets directory values
6. field defaults

Source:
`pydantic-settings` docs, lines 154-159:
https://raw.githubusercontent.com/pydantic/pydantic-settings/main/docs/index.md

For this repo, the practical meaning is that a checked-in
`.env.example` does not define runtime behavior by itself. Real process
env vars still outrank dotenv values, and both outrank defaults.

### Dotenv files

The docs describe two supported dotenv entry points:

- set `env_file` on `model_config`
- pass `_env_file` when instantiating the settings model

Source:
`pydantic-settings` docs, lines 33-40:
https://raw.githubusercontent.com/pydantic/pydantic-settings/main/docs/index.md

Important documented details:

- if `env_file` is a filename like `.env`, Pydantic checks only the
  current working directory, not parent directories
  (line 37)
- environment variables still override dotenv values
  (line 38)
- multiple dotenv files can be loaded, with later files overriding
  earlier ones
  (lines 39-40)
- dotenv parsing is delegated to `python-dotenv`
  (line 41)

This current repo layout makes the working-directory rule important.
Existing non-API code explicitly loads `/home/nes/discord/.env`
([discord_cli.py](/home/nes/discord/discord_cli.py:17),
 [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:27)).
By contrast, a settings model that points to `env_file='.env'` would be
dependent on the process working directory, and the repo root is not the
same as `services/api/`.

The docs also document a second repo-specific issue:

- dotenv loading honors model `extra` rules
- with the default `extra=forbid`, unknown dotenv entries raise
  `ValidationError`
- `dotenv_filtering` exists because dotenv handling loads all values
  from the file rather than only matching fields

Source:
`pydantic-settings` docs, lines 41-45:
https://raw.githubusercontent.com/pydantic/pydantic-settings/main/docs/index.md

This matters immediately here because the repo-level
[.env.example](/home/nes/discord/.env.example:1) is broader than the
current API scaffold. In a local experiment with `pydantic-settings
2.13.1`, a `BaseSettings` model pointing at an `env_file` containing an
unknown key raised `ValidationError` with `extra_forbidden`, while the
same file loaded successfully when extras were ignored.

### Nested config

The docs describe two ways to populate complex settings:

- provide a JSON-encoded string for a complex field
- configure `env_nested_delimiter` and explode values into nested
  models or dicts

Source:
`pydantic-settings` docs, lines 16-32:
https://raw.githubusercontent.com/pydantic/pydantic-settings/main/docs/index.md

Documented nested-config behavior:

- `FOO__BAR__BAZ=123` can populate nested models or dicts
  (lines 18-22)
- multiple nested values with the same structure are merged
  (line 19)
- nested env vars override top-level JSON for the same object
  (line 25)
- `env_nested_max_split` limits how far names are split
  (lines 22-25)
- partial updates to nested default objects are disabled by default
  unless `nested_model_default_partial_update=True` is set
  (lines 32-33)

The current Humility environment surface is flat, not nested. So nested
config is an available capability of `pydantic-settings`, but not yet a
current requirement evidenced by `.env.example` or the API scaffold.

### Secret files

The same docs also describe a secrets-directory source and state that
environment variables and dotenv values take priority over secrets
directory values
(`pydantic-settings` docs, lines 110 and 154-159:
https://raw.githubusercontent.com/pydantic/pydantic-settings/main/docs/index.md).

That is relevant to the problem space even though the repo does not yet
evidence a secrets-directory strategy, because it defines what would
happen if the project later mixes mounted secret files with env vars or
dotenv files.

## 4. Security considerations for sensitive fields

The current env contract includes several sensitive operational values:

- `DISCORD_BOT_TOKEN`
- `SUPABASE_SERVICE_KEY`
- `SUPABASE_DB_URL` if it contains credentials
- `RAILWAY_TOKEN`
- `GOOGLE_CLOUD_VISION_KEY`
- `GEMINI_API_KEY`
- `Z_AI_API_KEY`
- `MINIMAX_API_KEY`

`DISCORD_GUILD_ID` and `DISCORD_STAGING_GUILD_ID` are identifiers rather
than secrets, but they still affect blast radius because they select
which guild a deployment can act on.

### What the repo already protects

- Real `.env` files are excluded from git
  ([.gitignore](/home/nes/discord/.gitignore:1)).
- Existing runtime config loaders report missing or malformed settings
  without echoing the actual secret values in the error message
  ([discord_cli.py](/home/nes/discord/discord_cli.py:54),
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:48)).

### What `repr=False` protects

The reference marks sensitive fields with `repr=False`
([settings.py](/home/nes/discord/.refs/ai-workflow/app/core/settings.py:113)).

Observed local behavior with Pydantic 2.13.0:

- `repr=False` removes the field from `repr(model)`
- it does not remove the field from `model_dump()`
- it does not by itself prevent raw secret values from being serialized

So `repr=False` protects debug representation, not general
serialization.

### What `SecretStr` protects

Pydantic documents `SecretStr` as a type for sensitive information that
should not be visible in logging or tracebacks; `repr()` and `str()`
display `**********` instead of the real value
(`SecretStr` docs, lines 521-539:
https://docs.pydantic.dev/latest/api/types/).

Observed local behavior with Pydantic 2.13.0:

- `SecretStr` is masked in `repr()`
- `SecretStr` remains masked in `model_dump_json()`
- the raw value is still accessible via `get_secret_value()`

So `SecretStr` covers more surfaces than `repr=False`, but it is still
not a complete secret-handling policy. Application code can still leak
the raw value if it unwraps or logs the secret explicitly.

### DB URLs deserve special treatment

`SUPABASE_DB_URL=postgresql://...` is operationally more sensitive than
an ordinary identifier because DSNs often embed usernames, passwords,
hosts, and database names in one string
([.env.example](/home/nes/discord/.env.example:7)).

The security problem is therefore not only "is this field a secret" but
also "does one serialized string reveal multiple infrastructure details
at once?" A plain string DB URL can expose more than a single token if
it lands in logs or tracebacks.

### Source ambiguity is also a security concern

The documented source precedence means a deployment env var silently
overrides a dotenv value, and a dotenv value silently overrides a field
default
(`pydantic-settings` docs, lines 154-159:
https://raw.githubusercontent.com/pydantic/pydantic-settings/main/docs/index.md).

For this repo, that matters because the current environment surface is
shared across subsystems and deployment targets. A mis-scoped env var or
dotenv file is not only a correctness issue; it can also point a
process at the wrong guild or backend.

## 5. What validation is appropriate at this stage

The current evidence supports a narrow validation surface.

Validation that is directly evidenced now:

- required presence for settings already treated as mandatory by sibling
  runtime code:
  - `DISCORD_BOT_TOKEN`
  - `DISCORD_GUILD_ID`
- integer parsing for guild ids, because both current runtime code and
  tests already enforce that
  ([discord_cli.py](/home/nes/discord/discord_cli.py:59),
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:53),
  [tests/test_discord_cli.py](/home/nes/discord/tests/test_discord_cli.py:387),
  [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:124))
- basic structural validation for DSN-like values such as
  `SUPABASE_DB_URL`, if the API consumes them as connection strings
  rather than opaque strings
- non-empty validation for opaque tokens and API keys when those
  integrations are actually in use

Validation that is plausible but not yet evidenced strongly enough to
be treated as settled:

- whether `DISCORD_STAGING_GUILD_ID` is required at startup or only for
  specific deployment flows
- whether every provider key must exist at process startup or only when
  a related feature path is enabled
- whether `RAILWAY_TOKEN` belongs to API runtime configuration at all
  rather than to operator or CI tooling
- whether guild IDs should be validated only as integers or as positive
  integers specifically

Validation that is not evidenced at the current scaffold stage:

- password-complexity or token-shape validation for third-party issued
  secrets
- network reachability checks during settings construction
- middleware-specific rules for CORS, allowed hosts, HTTPS, request
  logging, rate limits, or compression
- cross-setting policy rules that depend on features the API scaffold
  does not yet implement

The current boundary is therefore structural and local, not behavioral
or policy-heavy: required presence, basic type parsing, and format
checks already implied by the current env contract and existing repo
behavior.

## Summary

At the scaffold stage, the API settings problem is bounded but real:

- the repo already declares a shared env surface in
  [.env.example](/home/nes/discord/.env.example:1), but the FastAPI
  package has not yet encoded it
- the `ai-workflow` reference supports `BaseSettings`, validators,
  custom config errors, and secret-aware field treatment, but its
  concrete fields are for a different stack
- `pydantic-settings` has specific documented behavior around source
  priority, working-directory-relative dotenv loading, dotenv extras,
  nested config, and secret files that materially affects this repo
- `repr=False` and `SecretStr` protect different surfaces; neither one
  alone is a full secret-handling policy
- the current evidence supports simple structural validation, not a
  larger production policy surface
