# Synthesis: API Factory Module Needs

Date: 2026-04-13
Based on: research/21-factory.md

## Humility-Specific Context

The factory creates the FastAPI application instance. At this scaffold
stage, it needs to produce a minimal but importable app that later
partitions can extend with routers, middleware, and lifecycle hooks.

## Confirmed Needs

1. **`create_app` function** — the single public entry point.
   Signature: `create_app(settings: Settings | None = None) -> FastAPI`
   - When `settings` is None, instantiate `Settings()` from env vars
   - When provided, use the given settings (enables test injection)

2. **App metadata from settings** — pass `title`, `version`, and
   `debug` from the Settings object to the FastAPI constructor.

3. **Settings stored on app** — store the settings object on
   `app.state.settings` so downstream code can access it via
   dependency injection without re-instantiating.

4. **Minimal scaffold** — no routers, no middleware, no lifespan hooks,
   no exception handlers. The factory should produce a bare FastAPI
   instance that starts and responds to health checks (FastAPI's
   built-in OpenAPI/docs endpoints are sufficient for now).

## Anti-Scope

- No router mounting (v1 router doesn't exist yet)
- No middleware configuration (CORS, gzip, etc.)
- No lifespan/startup/shutdown hooks
- No exception handlers
- No dependency overrides
- No `load_dotenv()` — env preparation is the caller's responsibility
