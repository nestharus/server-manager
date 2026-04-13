# Hookpoint Research: API Settings Module

Date: 2026-04-13

## Scope

This note maps
[proposals/20-settings.md](/home/nes/discord/proposals/20-settings.md:1)
onto the current repository.

It is hookpoint-only research. It answers:

- what existing code or references are reusable
- what new files are actually required
- what imports and dependencies the module needs
- what parts of the `ai-workflow` reference should be copied exactly
- what duplicate or parallel configuration code must be avoided

It does not include implementation code.

## Primary Sources

- Proposal:
  [proposals/20-settings.md](/home/nes/discord/proposals/20-settings.md:1)
- Problem-space research:
  [research/20-settings.md](/home/nes/discord/research/20-settings.md:1)
- Reference implementation:
  [.refs/ai-workflow/app/core/settings.py](/home/nes/discord/.refs/ai-workflow/app/core/settings.py:1)
- Target package:
  [services/api/app/core/__init__.py](/home/nes/discord/services/api/app/core/__init__.py)
- API package metadata and dependencies:
  [services/api/pyproject.toml](/home/nes/discord/services/api/pyproject.toml:1)
- Existing env-loading entrypoints:
  [discord_cli.py](/home/nes/discord/discord_cli.py:17),
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:28)
- Current env surface:
  [.env.example](/home/nes/discord/.env.example:1)

## 1. What existing code can be reused or referenced

### `services/api/pyproject.toml` already provides the required settings dependencies

The API package already declares `pydantic` and `pydantic-settings`, so
the settings module does not need any new package dependency
([services/api/pyproject.toml](/home/nes/discord/services/api/pyproject.toml:6)).

The same file also gives the exact defaults proposal 20 wants for app
metadata:

- `name = "server-manager-api"`
- `version = "0.1.0"`

Those values should be copied into `Settings.app_name` and
`Settings.app_version`, not dynamically loaded from packaging metadata
([services/api/pyproject.toml](/home/nes/discord/services/api/pyproject.toml:1),
[proposals/20-settings.md](/home/nes/discord/proposals/20-settings.md:43)).

### `.env.example` is the field inventory reference, not a runtime file hookpoint

The proposal's field list maps directly to the repo's current env
surface:

- Discord keys at
  [.env.example](/home/nes/discord/.env.example:2)
- Supabase keys at
  [.env.example](/home/nes/discord/.env.example:7)
- Provider keys at
  [.env.example](/home/nes/discord/.env.example:14)

This is the authoritative source for field names the API settings class
should encode. It also shows what to exclude: `RAILWAY_TOKEN` exists in
the repo env example, but proposal 20 explicitly excludes it from API
runtime settings
([.env.example](/home/nes/discord/.env.example:10),
[proposals/20-settings.md](/home/nes/discord/proposals/20-settings.md:154)).

### `discord_cli.py` and `daemon/__main__.py` are pattern references only

Both existing entrypoints prove two pieces of current env behavior:

- `DISCORD_BOT_TOKEN` is required
- `DISCORD_GUILD_ID` must parse as `int`

That logic lives today in
[discord_cli.py](/home/nes/discord/discord_cli.py:50) and
[daemon/__main__.py](/home/nes/discord/daemon/__main__.py:42).

Those files are useful as evidence for required fields and integer
coercion, but they are not reusable code hookpoints for the API module.
Both entrypoints own dotenv loading through module-level
`load_dotenv(...)`
([discord_cli.py](/home/nes/discord/discord_cli.py:22),
[daemon/__main__.py](/home/nes/discord/daemon/__main__.py:31)),
while proposal 20 explicitly forbids `settings.py` from owning dotenv
discovery or file reads
([proposals/20-settings.md](/home/nes/discord/proposals/20-settings.md:125)).

Practical meaning:

- reuse the env contract, not the helper functions
- do not import `get_config()` from `discord_cli.py`
- do not import `get_runtime_config()` from `daemon.__main__`
- do not copy their `load_dotenv()` pattern into the API package

### The `ai-workflow` settings module is a structural reference, not a field-level template

The reusable part of the reference is its shape:

- one `Settings(BaseSettings)` class in `app/core/`
- typed class attributes for runtime config
- sensitive fields hidden with `Field(..., repr=False)`

That structure appears at
[.refs/ai-workflow/app/core/settings.py](/home/nes/discord/.refs/ai-workflow/app/core/settings.py:75)
and
[.refs/ai-workflow/app/core/settings.py](/home/nes/discord/.refs/ai-workflow/app/core/settings.py:119).

The non-reusable parts are equally important:

- custom URL validators
- custom validation exception classes
- middleware and infrastructure fields
- credential-complexity regexes

Those are stack-specific to the reference app and would violate the
accepted scope of proposal 20
([.refs/ai-workflow/app/core/settings.py](/home/nes/discord/.refs/ai-workflow/app/core/settings.py:43),
[.refs/ai-workflow/app/core/settings.py](/home/nes/discord/.refs/ai-workflow/app/core/settings.py:150),
[proposals/20-settings.md](/home/nes/discord/proposals/20-settings.md:72)).

### `services/api/app/core/__init__.py` is an empty insertion seam

The target package exists, but it is currently empty
([services/api/app/core/__init__.py](/home/nes/discord/services/api/app/core/__init__.py)).

There are also no current imports anywhere in the repo that reference
`services/api/app/core/settings.py` or a `Settings` symbol under the API
package yet. That means the settings module can be added as a new file
without refactoring existing API call sites first.

## 2. What files need to be created

### Required new code file

- `services/api/app/core/settings.py`

This is the only required code file for proposal 20. The repository does
not currently contain any API settings module, factory, or dependency
layer, so the hookpoint is isolated to one new file under the existing
`core/` package
([services/api/app/core/__init__.py](/home/nes/discord/services/api/app/core/__init__.py),
[proposals/20-settings.md](/home/nes/discord/proposals/20-settings.md:105)).

### Files that do not need to be created in this phase

- no API factory file
- no dependency provider file
- no package-level dotenv helper
- no API-specific `.env` example

Proposal 20 says the future app factory will instantiate `Settings()`,
but the factory itself is outside this phase
([proposals/20-settings.md](/home/nes/discord/proposals/20-settings.md:111)).

### Files that may remain unchanged

- `services/api/app/core/__init__.py`
- `services/api/pyproject.toml`

`core/__init__.py` does not need a re-export yet because there are no
existing consumers and the proposal only requires the module itself to
export a public `Settings` class. Adding a package-level re-export now
would be optional, not required.

`pyproject.toml` already contains the necessary dependencies, so no
dependency edit is required for this phase.

## 3. What imports and dependencies are needed

### Imports for `services/api/app/core/settings.py`

The proposal only needs these runtime imports:

```python
from pydantic import Field
from pydantic_settings import BaseSettings
```

Those imports are sufficient for:

- required fields via `Field(..., repr=False)`
- optional sensitive fields via `Field(default=None, repr=False)`
- default `BaseSettings` env loading and type coercion

### Imports that should not be added

- no `dotenv.load_dotenv`
- no `os.getenv`
- no `field_validator`
- no `ValidationInfo`
- no `SecretStr`
- no `SettingsConfigDict` unless a minimal `model_config` is later shown
  to be necessary
- no `Path`, file I/O, or repo-root resolution helpers

This follows both the proposal's anti-scope and the research finding
that `env_file` would create working-directory coupling and unknown-key
hazards for this repo's shared `.env` surface
([research/20-settings.md](/home/nes/discord/research/20-settings.md:227),
[proposals/20-settings.md](/home/nes/discord/proposals/20-settings.md:94)).

### Project dependencies

No new dependency is required. The only relevant existing dependencies
are:

- `pydantic`
- `pydantic-settings`

Both are already present in
[services/api/pyproject.toml](/home/nes/discord/services/api/pyproject.toml:9).

`python-dotenv` also exists in the API package dependencies
([services/api/pyproject.toml](/home/nes/discord/services/api/pyproject.toml:12)),
but it is intentionally not a dependency of `settings.py` itself.

## 4. What patterns from the reference should be followed exactly

These parts of the `ai-workflow` reference should be copied exactly in
shape:

- one public `Settings` class that subclasses `BaseSettings`
- place the module at `services/api/app/core/settings.py`
- keep settings as flat typed fields on the class body
- use `Field(..., repr=False)` for required sensitive values
- use `Field(default=None, repr=False)` for optional sensitive values
- keep configuration ownership at the application boundary rather than
  inside repositories or infrastructure code

These proposal-specific constraints refine that reference and should be
followed exactly as well:

- no `env_file` in `model_config`
- no nested env parsing
- no deployment-only fields such as `RAILWAY_TOKEN`
- no custom validators for token shape, URL scheme, or provider-key
  format
- no module-level side effects such as `load_dotenv()` or package
  metadata file reads

The key point is that the API module should copy the reference's
architecture, not its SurrealDB/Elasticsearch policy surface
([.refs/ai-workflow/app/core/settings.py](/home/nes/discord/.refs/ai-workflow/app/core/settings.py:75),
[proposals/20-settings.md](/home/nes/discord/proposals/20-settings.md:89)).

## 5. What parallel or duplicate code this would create

If proposal 20 is implemented as written, it creates no parallel config
system inside the API service. The single new boundary is
`services/api/app/core/settings.py`.

The duplicate-code risks are all avoidable:

- copying `load_dotenv()` into the API package would create a second env
  ownership path alongside `discord_cli.py` and `daemon.__main__`
- copying `get_config()` or `get_runtime_config()` semantics into a new
  helper module would create a second hand-rolled parser next to
  `BaseSettings`
- adding `RAILWAY_TOKEN` or other non-API keys would turn the API
  settings module into a repo-global env registry
- adding middleware toggles or nested provider submodels now would
  create a parallel configuration surface not evidenced by the current
  API scaffold

What should exist after this phase is simpler:

- CLI code continues to own CLI dotenv loading
- daemon code continues to own daemon dotenv loading
- API code gains exactly one service-local `Settings` class for its own
  runtime contract

That is not harmful duplication; it is the intended separation of
entrypoint concerns. The thing to avoid is duplicating the mechanism for
loading and validating API settings once `core.settings.Settings`
exists.

## Bottom Line

Proposal 20 maps cleanly onto the current repository because the API
package is still mostly empty. The only required new code artifact is
`services/api/app/core/settings.py`, backed by dependencies already
present in `services/api/pyproject.toml` and by the env field inventory
already evidenced in `.env.example`. The reference app provides the
right `BaseSettings` structure, but the CLI and daemon entrypoints are
only evidence for env names and coercion rules, not reusable runtime
helpers. If the implementation stays confined to one `Settings` class
with `Field(repr=False)` on sensitive values and no dotenv ownership,
the repo will not gain a parallel configuration system.
