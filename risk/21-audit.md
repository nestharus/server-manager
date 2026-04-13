# Audit Risk Assessment: `services/api/app/core/factory.py`

Date: 2026-04-13
Assessor: claude-opus (audit)

## Verdict

**LOW**

The proposal defines a minimal factory function that constructs a
FastAPI instance from an already-validated Settings model. The attack
surface is extremely small: no routes, no middleware, no lifespan hooks,
no user input handling. The three metadata fields passed to the FastAPI
constructor (`app_name`, `app_version`, `debug`) contain no secrets.
Sensitive settings fields are already marked `repr=False` in the
Settings model, preventing accidental leakage through string
representation. The factory does not introduce any new credential
handling, network exposure, or data persistence paths.

## Findings

### Finding 1 — OpenAPI and docs endpoints enabled by default

- **Severity**: LOW
- **Section of proposal**: Defaults and omissions
- **Description**: The proposal explicitly defers to FastAPI defaults,
  which enables `/docs`, `/redoc`, and `/openapi.json`. These endpoints
  expose the application's title, version, and full route schema. At
  this scaffold stage the schema is empty (no routes exist), so
  information disclosure is negligible. However, as routes are added in
  future partitions, these endpoints will expose the full API surface
  unless explicitly disabled or protected.
- **Why it matters**: In production, unauthenticated OpenAPI endpoints
  reveal endpoint signatures, parameter types, and error contracts to
  any caller. This is a standard concern for any FastAPI service, not
  specific to this proposal.
- **Recommendation**: Accept as written. The proposal correctly notes
  that OpenAPI customization is anti-scope at this scaffold stage.
  Disabling or protecting docs endpoints is a future middleware/security
  concern that belongs in a later partition when routes exist.

### Finding 2 — Settings object on `app.state` exposes secrets to all handlers

- **Severity**: LOW
- **Section of proposal**: Construction shape / Architecture
- **Description**: Storing the full Settings object on
  `app.state.settings` means any code with access to the `request`
  object or `app` instance can read `discord_bot_token`,
  `supabase_service_key`, `supabase_db_url`, and the optional API keys.
  This is the standard FastAPI pattern and matches the reference
  implementation. The Settings model already marks all secret fields
  with `repr=False` (settings.py:11, 15-16, 18-21), which prevents
  them from appearing in `repr()`, `str()`, or default logging output.
- **Why it matters**: If a future exception handler or middleware
  serializes `request.app.state.settings` directly (rather than calling
  `repr()`), secrets could appear in logs or error responses. The
  `repr=False` guard is a Pydantic convention, not a hard access
  control.
- **Recommendation**: Accept as written. The `repr=False` protection
  is appropriate for this stage. When exception handlers and logging
  middleware are added in future partitions, their audit assessments
  should verify they do not serialize the settings object or access
  secret fields.

### Finding 3 — `debug=True` enables detailed error tracebacks

- **Severity**: LOW
- **Section of proposal**: Factory behavior, step 2
- **Description**: The factory passes `debug=settings.debug` to the
  FastAPI constructor. When `debug=True`, FastAPI returns detailed
  stack traces in error responses, which can reveal internal file
  paths, library versions, and local variable state. The Settings model
  defaults `debug` to `False` (settings.py:8), and the value is
  controlled by an environment variable.
- **Why it matters**: If a production deployment sets `DEBUG=true` by
  mistake, error responses would leak implementation details. This is
  a standard concern for any web framework, not specific to this
  proposal.
- **Recommendation**: Accept as written. The default is `False`, and
  debug mode is a standard development convenience. Production
  deployment controls (environment configuration, not the factory)
  are the correct place to ensure debug is disabled.

### Finding 4 — No secrets passed to FastAPI constructor metadata

- **Severity**: LOW (positive finding)
- **Section of proposal**: Factory behavior
- **Description**: The proposal specifies exactly three settings fields
  for the FastAPI constructor: `app_name`, `app_version`, and `debug`.
  None of these are secrets. The constructor metadata flows into the
  OpenAPI schema, which is served publicly. The proposal does not pass
  `api_prefix`, `discord_bot_token`, `supabase_db_url`, or any other
  sensitive field to the constructor.
- **Recommendation**: No action required. This is correct behavior.

### Finding 5 — Caller-owned env preparation prevents hidden startup behavior

- **Severity**: LOW (positive finding)
- **Section of proposal**: Startup ownership
- **Description**: The proposal explicitly excludes `load_dotenv()`,
  repo-root file discovery, and fallback env-file policy from the
  factory. This means the factory cannot accidentally load a stale or
  incorrect `.env` file, and cannot override environment variables set
  by a deployment platform. The caller (e.g., `app/main.py` or a test
  runner) owns env preparation.
- **Recommendation**: No action required. This is correct separation
  of concerns.

### Finding 6 — Settings resolution via `settings or Settings()` is safe

- **Severity**: LOW
- **Section of proposal**: Construction shape
- **Description**: The expression `settings or Settings()` uses Python
  truthiness to decide whether to use the provided settings or create
  a new instance. A Pydantic `BaseSettings` object is always truthy
  (it is a regular Python object, not a numeric or collection type),
  so a valid Settings instance will never be incorrectly treated as
  falsy. If an invalid value (e.g., `0`, `""`, `False`) were passed,
  the type annotation `Settings | None` combined with any type checker
  would catch it before runtime.
- **Recommendation**: Accept as written. The truthiness check is safe
  for this type. An explicit `if settings is None` check would be
  marginally more precise but is not a security concern.

## Overall Assessment

All findings are LOW severity. The proposal's attack surface is
minimal: a single function that maps three non-secret configuration
values into a FastAPI constructor and stores the settings object on
app state. The Settings model's existing `repr=False` guards on secret
fields provide adequate protection at this scaffold stage.

The two forward-looking concerns (OpenAPI exposure in Finding 1 and
settings serialization in Finding 2) are correctly deferred to future
partitions where routes and error handling are introduced. Those
future partitions' audit assessments are the appropriate place to
evaluate those risks in detail.

No proposal changes are required. The verdict is **LOW**.
