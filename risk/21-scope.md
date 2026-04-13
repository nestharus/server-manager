# Scope Risk: `services/api/app/core/factory.py`

**Overall risk level: LOW**

The proposal defines a minimal factory module whose responsibilities
are strictly bounded by what the scaffold currently evidences: a
`Settings` model and no other subsystems. The construction shape uses
exactly three metadata fields, stores settings on app state, and
returns. The anti-scope is comprehensive and directly traceable to the
research findings. No scope creep in either direction.

## Findings

### 1. Factory responsibilities match the current scaffold surface exactly

**Severity: INFO**

The factory consumes `Settings` — the only module that currently exists
in `core/` — and produces a configured `FastAPI` instance. The
construction shape uses three fields from settings (`app_name`,
`app_version`, `debug`), all of which are present on the implemented
`Settings` model (`services/api/app/core/settings.py:6-8`). The fourth
settings field relevant to app construction, `api_prefix`, is correctly
not consumed because no routers exist to mount under it.

No invented dependencies. No imports from modules that don't exist yet.

### 2. The `Settings | None = None` signature resolves the interface tension cleanly

**Severity: INFO**

The research (research/21-factory.md §4) identifies an interface
tension: the intended production call site is `app = create_app()`
(zero arguments), but test control requires settings injection. The
proposal resolves this with `settings: Settings | None = None`,
defaulting to `Settings()` when called without arguments. This matches
the `BaseSettings` contract — `Settings()` reads from the environment
— while preserving the injectable test pattern demonstrated by the
reference (`create_app(test_settings)`).

The tradeoff is explicitly documented in the proposal's Tradeoffs
section, with the reasoning that a strict zero-argument factory would
force tests to manipulate environment variables.

### 3. `app.state.settings` is the correct handoff mechanism

**Severity: INFO**

The proposal stores settings on `app.state.settings`, matching the
reference pattern. The research (research/21-factory.md §3) confirms
that `app.state` is Starlette's process-wide mutable state object,
shared across the application without per-request overhead. This
creates a single handoff point for future dependency functions without
introducing a module-level singleton or requiring downstream modules to
instantiate `Settings()` themselves — consistent with the architecture
rule that lower layers receive settings via injection
(AGENTS.md:371-372).

### 4. FastAPI defaults are correctly preserved

**Severity: INFO**

The proposal explicitly defers decisions about `default_response_class`,
`docs_url`, `redoc_url`, and `openapi_url`, relying on FastAPI's
built-in defaults. This is the correct call at this scaffold stage:

- `orjson` is a declared dependency, but there are no routes or
  response contracts that would benefit from `ORJSONResponse` yet.
- Docs URL policy is premature without routes to document.
- OpenAPI configuration has no local error contracts to customize.

The "Defaults and omissions" section explicitly states the reasoning:
"This keeps the module aligned with the current evidence instead of
copying mature-service behavior from the reference implementation."

### 5. Startup ownership boundary is correctly drawn

**Severity: INFO**

The proposal explicitly excludes `load_dotenv()`, repo-root file
discovery, and fallback env-file policy from the factory. The research
(research/21-factory.md §1) documents why: the repo-root `.env` lives
outside `services/api/`, making `env_file='.env'` working-directory-
dependent, and the `.env` contains keys outside the API surface that
would cause `ValidationError`. Environment preparation is correctly
left to the caller.

### 6. Anti-scope is comprehensive and traceable to research

**Severity: INFO**

The anti-scope excludes seven categories, each directly supported by
the research's "What the factory should not do yet" section
(research/21-factory.md §5):

| Anti-scope category | Research evidence |
|---|---|
| Router registration | No local router module exists |
| Middleware registration | Settings model has no HTTP config flags |
| Lifespan/startup/shutdown | No infrastructure clients to manage |
| Exception handlers | No domain error types defined locally |
| OpenAPI customization | No error contracts to register |
| Dotenv ownership | Working-directory and extra-keys hazards |
| Cross-layer dependency construction | No service/repository/infrastructure modules |

No categories of premature complexity are left unaddressed.

### 7. The proposal does not create hidden future constraints

**Severity: INFO**

The design leaves all future integration points open:

- Routers can be added via `app.include_router()` without changing the
  factory signature or return type.
- Middleware can be registered after construction or via a future
  private helper, same pattern as the reference.
- Lifespan can be introduced by adding a `lifespan` parameter to the
  `FastAPI()` constructor call — no structural change needed.
- `default_response_class` can be set when routes exist to benefit
  from it.
- The `settings` parameter accepts the full `Settings` type, so new
  settings fields are automatically available to the factory without
  signature changes.

No architectural decisions in this proposal foreclose future options.

### 8. "Design only" boundary is clearly stated

**Severity: INFO**

The proposal explicitly says "This proposal is design only. It does not
include implementation code." The code snippet is labeled as "the
contract shape, not implementation approval to add extra behavior."
This prevents scope expansion during implementation by establishing
that the snippet is a ceiling, not a floor.

## Recommendations

None. The proposal is appropriately scoped for the scaffold stage.
