# Hookpoint Research: API Factory Module

Date: 2026-04-13

## Scope

This note maps
[proposals/21-factory.md](/home/nes/discord/proposals/21-factory.md:1)
onto the current repository.

It is hookpoint-only research. It answers:

- what existing code is reusable
- what new files are actually required
- what imports and dependencies the module needs
- what parts of the `ai-workflow` reference apply here
- how the future `app.main` integration should attach to the factory

It does not include implementation code.

## Primary Sources

- Proposal:
  [proposals/21-factory.md](/home/nes/discord/proposals/21-factory.md:1)
- Problem-space research:
  [research/21-factory.md](/home/nes/discord/research/21-factory.md:1)
- Reference implementation:
  [.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:1)
- Existing settings module:
  [services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:1)
- Target package seam:
  [services/api/app/core/__init__.py](/home/nes/discord/services/api/app/core/__init__.py)
- API package metadata:
  [services/api/app/__init__.py](/home/nes/discord/services/api/app/__init__.py:1)
- API package dependencies:
  [services/api/pyproject.toml](/home/nes/discord/services/api/pyproject.toml:1)

## 1. What existing code can be reused

### `services/api/app/core/settings.py` is the direct reusable input

The proposal assumes the settings model already exists, and that is now
true. The local `Settings` class already exposes the exact fields the
factory needs for scaffold-stage app construction:

- `app_name`
- `app_version`
- `debug`

([services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:5))

Those fields map directly onto the proposed `FastAPI(...)` constructor
arguments in proposal 21
([proposals/21-factory.md](/home/nes/discord/proposals/21-factory.md:38)).

The same module also proves that settings resolution belongs at the API
boundary, not in lower layers: it is already a single `BaseSettings`
entry point under `app/core/`
([services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:1)).

### `api_prefix` exists but is not a current factory hookpoint

`Settings` also exposes `api_prefix`
([services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:9)),
but proposal 21 explicitly excludes router registration and prefix
mounting at this phase
([proposals/21-factory.md](/home/nes/discord/proposals/21-factory.md:153)).

Practical meaning:

- reuse `app_name`, `app_version`, and `debug` now
- do not wire `api_prefix` into `factory.py` yet

### `services/api/app/core/__init__.py` is an empty insertion seam

The `core/` package already exists and its `__init__.py` is empty, so
`factory.py` can be added cleanly under that package without needing to
refactor existing imports first
([services/api/app/core/__init__.py](/home/nes/discord/services/api/app/core/__init__.py)).

### `services/api/app/__init__.py` is package metadata only

The service package already documents that this package is the FastAPI
mutation gateway and follows the layered `api -> services ->
repositories -> infrastructure` shape
([services/api/app/__init__.py](/home/nes/discord/services/api/app/__init__.py:1)).

That supports the proposal's framing of `core.factory` as the
composition root, but it does not provide reusable startup code by
itself.

### `services/api/pyproject.toml` already has the required dependencies

The API package already declares `fastapi` and `pydantic-settings`
([services/api/pyproject.toml](/home/nes/discord/services/api/pyproject.toml:6)).
No dependency edit is required to add the minimal factory module.

`orjson` is also present
([services/api/pyproject.toml](/home/nes/discord/services/api/pyproject.toml:11)),
but proposal 21 deliberately keeps FastAPI's default response-class
behavior, so that dependency is not a required hookpoint for this phase
([proposals/21-factory.md](/home/nes/discord/proposals/21-factory.md:85)).

## 2. What files need to be created

### Required new code file

- `services/api/app/core/factory.py`

This is the only new code file proposal 21 requires. The current API
package contains `core/settings.py` and no other app-construction
module, router tree, or main entrypoint
([services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:1),
[services/api/app/__init__.py](/home/nes/discord/services/api/app/__init__.py:1)).

### Files that do not need to change in this phase

- `services/api/app/core/__init__.py`
- `services/api/app/__init__.py`

Neither file needs a re-export or package-level wiring to satisfy the
proposal. The approved import surface is direct module import from
`app.core.factory`, not package re-export indirection
([proposals/21-factory.md](/home/nes/discord/proposals/21-factory.md:67)).

### Files that are future integration points, not current hookpoints

- `services/api/app/main.py`

The proposal describes `app.main` as the future caller of the factory
([proposals/21-factory.md](/home/nes/discord/proposals/21-factory.md:110)),
but that file does not exist in the current scaffold. It should be
handled in the later startup-entrypoint phase, not bundled into this
factory hookpoint task.

## 3. What imports are needed

### Required runtime imports for `services/api/app/core/factory.py`

The approved minimal factory only needs these imports:

```python
from fastapi import FastAPI

from app.core.settings import Settings
```

Why these are sufficient:

- `FastAPI` is the only framework object the proposal constructs
- `Settings` is the only local dependency the proposal consumes
- Python `>=3.12` is already required by the package, so
  `Settings | None` syntax does not require `typing.Optional`
  or `from __future__ import annotations`
  ([services/api/pyproject.toml](/home/nes/discord/services/api/pyproject.toml:5))

### Imports that should not be copied from the reference

Proposal 21 excludes the reference module's mature-service imports.
That means no:

- `ORJSONResponse`
- router imports such as `api_router` or `health_check`
- exception types or handlers
- middleware imports
- lifespan helpers or infrastructure clients
- `get_openapi`
- `TYPE_CHECKING`, `Callable`, `TypeAdapter`, or other support for
  omitted subsystems
- `dotenv.load_dotenv`

These imports appear in the reference because that app already has
middleware, handlers, routes, and infrastructure resources
([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:13)),
while the approved Humility proposal explicitly excludes them
([proposals/21-factory.md](/home/nes/discord/proposals/21-factory.md:149)).

## 4. What patterns from the reference apply

### Patterns to copy

- one dedicated `create_app(...) -> FastAPI` entry point
- factory ownership of `FastAPI(...)` construction in one module
- storing resolved settings on `app.state.settings`
- keeping any optional helper private to the module

These patterns come directly from the reference factory's role as the
composition root
([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:190),
[.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:207),
[.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:59))
and align with the approved proposal
([proposals/21-factory.md](/home/nes/discord/proposals/21-factory.md:24),
[proposals/21-factory.md](/home/nes/discord/proposals/21-factory.md:43),
[proposals/21-factory.md](/home/nes/discord/proposals/21-factory.md:67)).

### Patterns to adapt

The reference signature is `create_app(settings: Settings) -> FastAPI`
([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:190)).
Proposal 21 changes that to optional injection:

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    ...
```

([proposals/21-factory.md](/home/nes/discord/proposals/21-factory.md:27))

That adaptation is the key local hookpoint because it preserves both:

- zero-argument production startup through `create_app()`
- explicit settings injection for tests through `create_app(settings=...)`

### Patterns to leave out entirely

Do not port these reference behaviors into the Humility factory yet:

- `default_response_class=ORJSONResponse`
- `docs_url` and `redoc_url` policy
- router registration
- exception-handler registration
- middleware registration
- lifespan resource management
- OpenAPI schema customization
- health-route registration

Those are all present in the reference
([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:199),
[.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:208)),
but proposal 21 keeps FastAPI defaults and excludes mature-service
composition until those modules actually exist
([proposals/21-factory.md](/home/nes/discord/proposals/21-factory.md:83),
[proposals/21-factory.md](/home/nes/discord/proposals/21-factory.md:151)).

## 5. Integration with `main.py`

### Intended future integration

The proposal's startup path is:

```python
from app.core.factory import create_app

app = create_app()
```

([proposals/21-factory.md](/home/nes/discord/proposals/21-factory.md:108))

That means the future `services/api/app/main.py` should depend on the
factory module directly, not instantiate `Settings()` on its own and
not rebuild app-construction logic locally.

### Division of responsibility

Once `factory.py` exists, responsibility should split like this:

- `app.core.factory` resolves `Settings()` when no settings object is
  supplied, constructs the `FastAPI` app, and stores
  `app.state.settings`
- `app.main` imports `create_app` and binds `app = create_app()`
- caller or deployment environment owns any dotenv or process startup
  preparation outside the factory

That division follows proposal 21's composition-root design and its
explicit rule that `core.factory` must not own `load_dotenv()` or repo
file discovery
([proposals/21-factory.md](/home/nes/discord/proposals/21-factory.md:72)).

## Bottom Line

Proposal 21 maps cleanly onto the current codebase because the local API
surface is still minimal. The only reusable local code is
`services/api/app/core/settings.py`; the only required new code file is
`services/api/app/core/factory.py`; the only required runtime imports
are `FastAPI` and `Settings`; and the only future integration seam is a
later `app.main` module that imports `create_app()` and does not
duplicate factory behavior.
