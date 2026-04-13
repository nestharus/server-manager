# Research: API Factory Module

Date: 2026-04-13

## Scope

This note documents the current problem space for implementing an
application factory module for the FastAPI service under
`services/api/`.

It is limited to:

- what the current scaffold already requires from a factory module
- what the `ai-workflow` reference factory demonstrates
- how FastAPI app construction works at the framework level
- what public surface the factory is expected to expose
- what factory responsibilities are not yet justified by the local
  scaffold

It does not propose a final implementation, startup policy, router
layout, or production runtime shape.

## Local Baseline

- The API service is explicitly intended to be the mutation gateway for
  both the web UI and Discord daemon, and it follows the layered shape
  `api -> services -> repositories -> infrastructure`
  ([services/api/app/__init__.py](/home/nes/discord/services/api/app/__init__.py:1),
  [AGENTS.md](/home/nes/discord/AGENTS.md:365)).
- Project guidance reserves `services/api/app/core/` for `factory`,
  `settings`, `dependencies`, and `middleware`
  ([AGENTS.md](/home/nes/discord/AGENTS.md:368)).
- The local API package currently evidences only package metadata plus
  `core/settings.py`; there is no local router tree, middleware module,
  exception module, infrastructure client module, or `app/main.py`
  yet. The package’s direct FastAPI-related runtime surface today is
  the `Settings` model and its tests
  ([services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:1),
  [services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:1)).
- `Settings` already provides application identity fields
  `app_name`, `app_version`, `debug`, and `api_prefix`, plus required
  Discord and Supabase configuration
  ([services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:5)).
- The settings tests show those values are intended to come from
  environment-backed `BaseSettings`, with defaults for the app identity
  fields and validation of the required runtime secrets/IDs
  ([services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:37),
  [services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:138),
  [services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:170)).
- `services/api/pyproject.toml` already declares the core framework
  dependencies that a factory would wire together: `fastapi`,
  `uvicorn`, `pydantic-settings`, and `orjson`
  ([services/api/pyproject.toml](/home/nes/discord/services/api/pyproject.toml:6)).

## Primary Sources

- Local repo files:
  - [AGENTS.md](/home/nes/discord/AGENTS.md:361)
  - [services/api/app/__init__.py](/home/nes/discord/services/api/app/__init__.py:1)
  - [services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:1)
  - [services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:1)
  - [services/api/pyproject.toml](/home/nes/discord/services/api/pyproject.toml:1)
  - [.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:1)
  - [.refs/ai-workflow/tests/unit/test_openapi_schema.py](/home/nes/discord/.refs/ai-workflow/tests/unit/test_openapi_schema.py:1)
- Installed framework source from `services/api/.venv`:
  - [fastapi/applications.py](/home/nes/discord/services/api/.venv/lib/python3.14/site-packages/fastapi/applications.py:98)
  - [starlette/datastructures.py](/home/nes/discord/services/api/.venv/lib/python3.14/site-packages/starlette/datastructures.py:668)
- Task context for this research:
  - intended import style in `app/main.py` is
    `from app.core.factory import create_app; app = create_app()`

## 1. What the factory module needs to do at this scaffold stage

At the current scaffold stage, the factory problem is much narrower
than the reference implementation.

What is already evidenced:

- There needs to be a central place that constructs a `FastAPI`
  application object for the API package. The project architecture
  reserves `core/` for that role, and the task context names
  `app.core.factory.create_app` as the import target
  ([AGENTS.md](/home/nes/discord/AGENTS.md:368)).
- The factory needs to bridge the existing settings surface into app
  construction, because the local settings model already contains the
  application identity fields that map naturally onto FastAPI
  constructor arguments: `app_name`, `app_version`, `debug`, and
  `api_prefix`
  ([services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:6)).
- The factory is the natural place to set the application-wide default
  response policy if the project intends to use `orjson`, because
  `orjson` is already a declared dependency and the reference factory
  uses `ORJSONResponse` as a top-level application default
  ([services/api/pyproject.toml](/home/nes/discord/services/api/pyproject.toml:11),
  [.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:199)).
- The factory may also need to expose application state for settings if
  downstream code is expected to read configuration from `app.state`;
  the reference does this with `app.state.settings = settings`
  ([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:207)).

What is not yet evidenced:

- No local router exists yet, so there is not yet a demonstrated need
  to mount `APIRouter` instances.
- No local middleware or exception modules exist yet, so there is not
  yet a demonstrated need to register handlers or middleware layers.
- No local infrastructure clients exist yet, so there is not yet a
  demonstrated need to allocate startup/shutdown resources in lifespan.
- No local OpenAPI customization contract exists yet beyond the generic
  FastAPI defaults.

The immediate scaffold-stage problem is therefore: provide the API with
an application-construction entry point that is consistent with the
existing settings model and the intended `app.main` import contract,
without prematurely importing subsystems that do not yet exist.

## 2. What patterns from the `ai-workflow` reference should be adopted vs. adapted

The reference factory is
[.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:1).
It mixes three different categories of behavior:

1. basic FastAPI application construction
2. reusable composition patterns for a layered app
3. app-specific wiring for a much more mature service

### Patterns that transfer cleanly

- A dedicated `create_app(...) -> FastAPI` factory entry point
  ([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:190)).
- Centralized construction of the `FastAPI` object instead of ad hoc
  initialization in multiple files
  ([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:199)).
- Treating app construction as the place where metadata, default
  response class, state, lifespan, routers, handlers, and OpenAPI
  customization can eventually be composed
  ([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:199),
  [.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:214)).
- Keeping helper concerns private to the module with `_...` helper
  functions, rather than exposing multiple setup entry points
  ([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:59),
  [.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:97),
  [.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:147)).

### Patterns that need adaptation

- The reference accepts `settings: Settings` as an explicit argument
  ([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:190)).
  The task context for Humility names a zero-argument call site in
  `app/main.py`. That is a real interface mismatch that the problem
  space must account for.
- The reference test suite depends on the injectable-settings form:
  tests construct `Settings(...)` directly and pass it into
  `create_app(test_settings)` before inspecting routes and OpenAPI
  behavior
  ([.refs/ai-workflow/tests/unit/test_openapi_schema.py](/home/nes/discord/.refs/ai-workflow/tests/unit/test_openapi_schema.py:38),
  [.refs/ai-workflow/tests/unit/test_openapi_schema.py](/home/nes/discord/.refs/ai-workflow/tests/unit/test_openapi_schema.py:141)).
  That means the reference signature is not arbitrary; it supports test
  control and startup isolation.
- The reference wires in a substantial amount of mature-app behavior:
  API routers, health endpoints, custom exception handlers, middleware,
  lifespan-managed clients, and custom OpenAPI schema generation
  ([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:23),
  [.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:97),
  [.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:147),
  [.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:208)).
  Those are application-specific integrations, not minimal factory
  requirements.
- The reference’s custom OpenAPI work exists because that app has
  custom error contracts and tests that assert them
  ([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:79),
  [.refs/ai-workflow/tests/unit/test_openapi_schema.py](/home/nes/discord/.refs/ai-workflow/tests/unit/test_openapi_schema.py:44)).
  Humility does not yet evidence any parallel error contract layer.

### Patterns that should be treated as premature for this scaffold

- middleware registration based on settings toggles
- startup resource creation for database/search/storage clients
- custom exception-handler registration
- custom OpenAPI schema mutation
- built-in health route registration

All of those patterns are valid in the reference because the
surrounding modules already exist there. The local Humility scaffold
does not yet provide the same prerequisites.

## 3. How FastAPI app construction works: metadata, state, lifespan

The installed FastAPI source makes clear that app construction is a
single `FastAPI(...)` call with many optional configuration parameters,
not just routes.

### Metadata

FastAPI exposes constructor parameters for API metadata including
`title`, `summary`, `description`, and `version`
([fastapi/applications.py](/home/nes/discord/services/api/.venv/lib/python3.14/site-packages/fastapi/applications.py:98),
 [fastapi/applications.py](/home/nes/discord/services/api/.venv/lib/python3.14/site-packages/fastapi/applications.py:119),
 [fastapi/applications.py](/home/nes/discord/services/api/.venv/lib/python3.14/site-packages/fastapi/applications.py:140),
 [fastapi/applications.py](/home/nes/discord/services/api/.venv/lib/python3.14/site-packages/fastapi/applications.py:178)).

The same constructor also exposes:

- `openapi_url`
- `docs_url`
- `redoc_url`
- `default_response_class`

([fastapi/applications.py](/home/nes/discord/services/api/.venv/lib/python3.14/site-packages/fastapi/applications.py:202),
 [fastapi/applications.py](/home/nes/discord/services/api/.venv/lib/python3.14/site-packages/fastapi/applications.py:356),
 [fastapi/applications.py](/home/nes/discord/services/api/.venv/lib/python3.14/site-packages/fastapi/applications.py:401),
 [fastapi/applications.py](/home/nes/discord/services/api/.venv/lib/python3.14/site-packages/fastapi/applications.py:425)).

This matters for the Humility scaffold because the local settings model
already contains values that map onto a subset of that metadata surface
without requiring any other subsystem to exist
([services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:6)).

### State

FastAPI exposes `app.state` as a process-wide mutable state object
([fastapi/applications.py](/home/nes/discord/services/api/.venv/lib/python3.14/site-packages/fastapi/applications.py:952)).
Its own docs in the source say this object is shared across the entire
application and does not change from request to request
([fastapi/applications.py](/home/nes/discord/services/api/.venv/lib/python3.14/site-packages/fastapi/applications.py:956)).

The underlying Starlette `State` object is just a wrapper over a dict
that allows attribute and item assignment
([starlette/datastructures.py](/home/nes/discord/services/api/.venv/lib/python3.14/site-packages/starlette/datastructures.py:668),
 [starlette/datastructures.py](/home/nes/discord/services/api/.venv/lib/python3.14/site-packages/starlette/datastructures.py:680),
 [starlette/datastructures.py](/home/nes/discord/services/api/.venv/lib/python3.14/site-packages/starlette/datastructures.py:693)).

In the reference, `app.state` is used for both settings and runtime
resources:

- `app.state.settings = settings`
- `app.state.surrealdb_pool = surreal_pool`
- `app.state.elasticsearch_client = elasticsearch_client`
- `app.state.duckdb_client = duckdb_client`

([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:155),
 [.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:159),
 [.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:163),
 [.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:207)).

So the problem-space question for Humility is not whether app state can
be used; it can. The actual question is which values are justified to
store there at this stage, given that only settings currently exist.

### Lifespan

FastAPI’s constructor exposes a `lifespan` parameter and explicitly
describes it as a context manager that replaces separate startup and
shutdown functions
([fastapi/applications.py](/home/nes/discord/services/api/.venv/lib/python3.14/site-packages/fastapi/applications.py:530)).
The same source also marks `on_startup` and `on_shutdown` as legacy in
comparison, stating that lifespan handlers should be used instead
([fastapi/applications.py](/home/nes/discord/services/api/.venv/lib/python3.14/site-packages/fastapi/applications.py:505),
 [fastapi/applications.py](/home/nes/discord/services/api/.venv/lib/python3.14/site-packages/fastapi/applications.py:517)).

The reference follows that guidance exactly: `_lifespan(settings)`
returns an `asynccontextmanager`, initializes external resources before
`yield`, and closes them in `finally`
([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:147),
 [.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:166),
 [.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:170)).

For the Humility scaffold, lifespan is therefore a framework-supported
place for future resource management, but the local codebase does not
yet evidence any resource that must be started or torn down there.

## 4. What the factory should expose

Two different interface pressures are already visible.

### Public module surface

The task context explicitly names one public import target:
`app.core.factory.create_app`.

That matches the reference, which exposes a single public constructor
function and keeps helper functions private
([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:190)).

### Return type

The reference factory returns `FastAPI`, and the reference tests use the
returned object as a normal FastAPI app for:

- schema generation via `app.openapi()`
- sync testing via `TestClient(app)`
- async testing via `httpx.ASGITransport(app=app)`

([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:190),
 [.refs/ai-workflow/tests/unit/test_openapi_schema.py](/home/nes/discord/.refs/ai-workflow/tests/unit/test_openapi_schema.py:40)).

So the return-type question is not ambiguous in the problem space: the
factory’s public product is a configured `FastAPI` application object.

### Function signature tension

This is the main interface ambiguity at the scaffold stage.

- The reference signature is `create_app(settings: Settings) -> FastAPI`
  ([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:190)).
- The task context for Humility states the intended call site in
  `app/main.py` is `app = create_app()` with no explicit settings
  argument.
- The local settings model is a `BaseSettings` subclass, so its values
  can be created from the environment without an external caller
  providing arguments
  ([services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:5)).
- But the reference tests show why an injected settings object is
  useful: tests can construct isolated settings objects directly and
  pass them to the factory
  ([.refs/ai-workflow/tests/unit/test_openapi_schema.py](/home/nes/discord/.refs/ai-workflow/tests/unit/test_openapi_schema.py:30),
  [.refs/ai-workflow/tests/unit/test_openapi_schema.py](/home/nes/discord/.refs/ai-workflow/tests/unit/test_openapi_schema.py:40)).

The problem-space conclusion is not "which signature is correct"
yet. It is that the factory needs one stable public entry point whose
signature satisfies both:

- the desired zero-argument runtime import style from `app.main`
- the testability and explicitness benefits demonstrated by the
  reference’s injected-settings pattern

## 5. What the factory should not do yet

The current local scaffold does not justify importing or wiring the
broader reference stack.

Not yet evidenced locally:

- router mounting via `app.include_router(...)`
  The reference imports `app.api.v1.router` and mounts it under
  `settings.api_prefix`
  ([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:24),
  [.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:208)).
  There is no corresponding local router module yet.
- custom health route registration
  The reference imports a concrete endpoint and registers it with
  `add_api_route`
  ([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:23),
  [.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:212)).
  There is no local health endpoint module yet.
- middleware registration
  The reference imports a dedicated middleware module and multiple
  FastAPI/Starlette middleware classes, all driven by settings flags
  ([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:15),
  [.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:32),
  [.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:97)).
  The Humility settings model does not yet define any of those HTTP
  configuration flags
  ([services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:5)).
- exception-handler registration
  The reference imports domain exception types and handler functions,
  then registers them on the app
  ([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:26),
  [.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:209)).
  No local equivalents exist yet.
- lifespan-managed infrastructure clients
  The reference allocates and tears down concrete database/search/query
  clients inside lifespan
  ([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:154),
  [.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:170)).
  The Humility scaffold does not yet contain corresponding
  infrastructure modules.
- custom OpenAPI mutation
  The reference customizes error schemas because its app has bespoke
  error contracts and tests asserting those schemas
  ([.refs/ai-workflow/app/core/factory.py](/home/nes/discord/.refs/ai-workflow/app/core/factory.py:59),
  [.refs/ai-workflow/tests/unit/test_openapi_schema.py](/home/nes/discord/.refs/ai-workflow/tests/unit/test_openapi_schema.py:44)).
  The local scaffold has no equivalent error-contract surface yet.

At this stage, those behaviors are best treated as future integration
points rather than current factory requirements. The absence of the
surrounding modules is the key evidence.
