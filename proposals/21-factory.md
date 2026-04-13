# Proposal: `services/api/app/core/factory.py`

Date: 2026-04-13

## Goal

Define `services/api/app/core/factory.py` as the API service's single
application-construction module.

Its job is to turn the already-implemented `Settings` model into one
importable `FastAPI` application instance, so the service has a stable
startup boundary before routers, middleware, and infrastructure wiring
exist.

At this scaffold stage, the module should stay intentionally small. It
should create the app, apply core metadata from settings, attach the
settings object to app state, and return the app. It should not begin
composing subsystems that the repo does not yet implement.

This proposal is design only. It does not include implementation code.

## Design

The module should expose one public factory function:

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    ...
```

### Factory behavior

The function should follow this sequence:

1. Resolve the settings object.
   - If `settings` is provided, use it as-is.
   - If `settings` is `None`, instantiate `Settings()`.
2. Construct the `FastAPI` application with metadata drawn from the
   resolved settings object:
   - `title=settings.app_name`
   - `version=settings.app_version`
   - `debug=settings.debug`
3. Store the resolved settings object on `app.state.settings`.
4. Return the app instance unchanged.

### Construction shape

The intended design is:

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        debug=resolved_settings.debug,
    )
    app.state.settings = resolved_settings
    return app
```

That snippet is the contract shape, not implementation approval to add
extra behavior.

### Public surface

- Public export: `create_app`
- Private responsibility: settings resolution and app construction
- No additional setup helpers are required yet unless implementation
  clarity benefits from a private helper for settings resolution

### Startup ownership

The factory should not prepare the environment itself.

- No `load_dotenv()`
- No repo-root file discovery
- No fallback env-file policy

If process startup needs dotenv loading, that belongs in the caller,
launcher, or deployment environment, not in `core.factory`.

### Defaults and omissions

The factory should rely on FastAPI defaults for everything not
explicitly required by the current scaffold. That means:

- Keep default docs and OpenAPI endpoint behavior
- Keep default response class behavior
- Do not register routes merely to prove the app boots

This keeps the module aligned with the current evidence instead of
copying mature-service behavior from the reference implementation.

## Architecture

`core.factory` is the API service's composition root.

In the layered pattern, it should sit at the application boundary:

- `core.settings` defines runtime configuration.
- `core.factory` consumes `Settings` and constructs the `FastAPI` app.
- Future `api/` routers, dependency wiring, middleware, and lifespan
  hooks are attached from this boundary when those modules exist.
- Lower layers such as `services`, `repositories`, and
  `infrastructure` should not instantiate `Settings()` themselves.

This yields a clean startup path:

- `app.main` imports `create_app`
- `app = create_app()`
- tests can inject `Settings(...)` directly through
  `create_app(settings=...)`

That arrangement preserves two important properties:

- Production entry points get one canonical place to build the app
- Tests can control configuration without mutating global process state

Storing settings on `app.state.settings` also gives future dependency
functions a shared handoff point without introducing a global singleton
or repeated settings instantiation throughout the stack.

## Tradeoffs

- Optional settings injection vs zero-argument-only factory
  Allowing `settings: Settings | None = None` keeps the production call
  site simple while preserving explicit test control. A strict
  zero-argument factory would force tests to manipulate environment
  variables instead of passing validated settings directly.
- `app.state.settings` vs module-level singleton
  App state keeps configuration attached to the application instance
  that owns it. A module-level singleton would make tests and multiple
  app instances harder to reason about.
- Minimal factory vs reference-style composition
  The reference factory wires routers, handlers, middleware, lifespan,
  and OpenAPI customization because that repo already has those
  subsystems. Copying that pattern here would create premature
  coupling to modules that do not yet exist.
- FastAPI defaults vs early policy decisions
  Leaving docs URLs, OpenAPI wiring, and response-class behavior at
  framework defaults avoids encoding API policy before the service has
  routes or response contracts that justify those choices.
- Caller-owned env preparation vs factory-owned dotenv loading
  Keeping env preparation outside the factory avoids hidden startup
  behavior and prevents the module from assuming a repo layout or env
  file policy.

## Anti-scope

This module should explicitly exclude:

- Router registration
  No `api_router`, no health route, and no prefix mounting yet.
- Middleware registration
  No CORS, gzip, HTTPS redirect, request ID, logging, metrics, or rate
  limiting.
- Lifespan or startup/shutdown resource management
  No database pools, external clients, caches, or async resource setup.
- Exception-handler registration
  No domain error mapping, validation handlers, or generic internal
  exception handler wiring.
- OpenAPI customization
  No schema mutation, custom error-schema registration, or docs-url
  policy changes.
- Dotenv ownership
  No `load_dotenv()`, env-file discovery, or repo-specific startup
  assumptions.
- Cross-layer dependency construction
  No service container assembly, repository instantiation, or
  infrastructure client wiring.
