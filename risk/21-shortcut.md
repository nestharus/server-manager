# Shortcut Risk: Factory Module

**Overall risk level: LOW**

The proposal is a deliberately minimal factory that constructs a FastAPI
application from the existing Settings model. It avoids the most common
factory-module shortcut — copying mature-service wiring from the reference
implementation before the local scaffold has the modules to justify it.
The design decisions are well-justified, the anti-scope is thorough, and
the few deferral decisions are all non-breaking to revisit later. No
finding rises above LOW.

## Findings

### 1. `ORJSONResponse` default deferred despite existing dependency (LOW)

The research document identifies `orjson` as an already-declared
dependency (`services/api/pyproject.toml`) and notes that the factory is
"the natural place to set the application-wide default response policy."
The reference factory sets `default_response_class=ORJSONResponse`
(`.refs/ai-workflow/app/core/factory.py:204`). The proposal explicitly
defers this, relying on FastAPI's default `JSONResponse` instead.

This is a valid deferral. Changing `default_response_class` later is a
non-breaking, single-line addition to the FastAPI constructor call. There
are no routes yet that would benefit from `orjson` serialization
performance. The decision can be revisited when the first router module
is introduced, at which point the response-class policy will have actual
endpoints to justify it.

**Severity:** LOW — deferring a performance optimization with no current
consumers is appropriate. The change path is trivial and non-breaking.

**Recommendation:** None required. The decision to defer is correct for
this scaffold stage.

### 2. Settings instantiation failure not discussed (LOW)

The factory's `settings or Settings()` fallback means that when called
without arguments in production, `Settings()` will attempt to load
required environment variables (`discord_bot_token`, `discord_guild_id`,
`supabase_db_url`, `supabase_service_key`). If those variables are
missing, Pydantic will raise a `ValidationError` that propagates through
`create_app()` uncaught.

The proposal does not discuss this failure mode. However, the behavior is
correct — a factory that cannot resolve its configuration should fail
loudly at startup, not silently produce a misconfigured application. The
existing Settings tests already verify that missing required fields raise
`ValidationError` (`services/api/tests/test_settings.py`). No special
error handling in the factory is needed or desirable.

**Severity:** LOW — the failure behavior is correct by default. Wrapping
the `Settings()` call in try/except would be the actual shortcut (hiding
startup failures), and the proposal correctly avoids it.

**Recommendation:** None required. The implicit propagation is the right
behavior.

### 3. No `app/main.py` coordination specified (LOW)

The proposal describes the intended import pattern — `app.main` imports
`create_app` and calls `app = create_app()` — but does not specify when
`app/main.py` will be created. Without `main.py`, the factory is testable
but not runnable as a production service.

This is not a shortcut. The factory module and the entry point module are
separate concerns with separate proposals. The factory can be fully
implemented and tested in isolation. The proposal correctly limits its
scope to the factory's responsibilities without reaching into the
caller's domain.

**Severity:** LOW — the factory is self-contained and testable. The
production entry point is a downstream concern.

**Recommendation:** None required. The entry point module is a separate
proposal.

### 4. `api_prefix` setting exists but is unused (LOW)

The Settings model defines `api_prefix: str = "/api/v1"`
(`services/api/app/core/settings.py:9`), but the factory proposal does
not reference it. The reference factory uses `settings.api_prefix` as
the router mount prefix (`.refs/ai-workflow/app/core/factory.py:208`).

This is correct behavior, not a shortcut. Router mounting is explicitly
in the anti-scope because no router module exists yet. The `api_prefix`
field is stored on `app.state.settings` and will be available when router
mounting is introduced. Using it now would require importing a router
that does not exist.

**Severity:** LOW — the setting is preserved on app state and accessible
when needed. No information is lost by not consuming it in the factory
constructor.

**Recommendation:** None required.

### 5. Factory pattern is trivially extensible (LOW — positive finding)

The proposal's minimal factory creates a clean extension path. Adding
routers, middleware, lifespan hooks, and exception handlers later
requires only appending lines to `create_app()` — no refactoring of the
existing function shape, no signature changes, no breaking of existing
test contracts. The `settings: Settings | None = None` signature
satisfies both the zero-argument production call site and the explicit
test injection pattern without requiring overloads or wrapper functions.

This is not a risk finding but worth noting: the proposal avoids the
common shortcut of building an over-engineered factory with extension
points, hooks, or plugin registration. The simplest possible function
is also the most extensible one.

**Severity:** LOW — the pattern is sound and future-proof without being
speculative.

**Recommendation:** None required.
