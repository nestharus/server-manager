# Risk Assessment: conftest.py (`services/api/tests/conftest.py`)

Date: 2026-04-13

Proposal: `proposals/28-conftest.md` (not yet written — audit based on
existing test files and `Settings`/`create_app` contracts)

## Verdict: LOW

The conftest.py is a test-infrastructure concern with low blast radius.
All four assessment criteria pass. Three findings are recorded below;
none are blocking but F1 and F2 should be addressed in the
implementation.

## Findings

### F1. Duplicated env-var dicts will drift when Settings grows — Severity: MEDIUM

`test_factory.py` and `test_settings.py` each define their own copy of
the required env vars and their own `_set_required_env` /
`_clear_required_env` helpers. The two dicts are currently consistent
(both set `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `SUPABASE_DB_URL`,
`SUPABASE_SERVICE_KEY`), but nothing enforces this. When a new required
field is added to `Settings`, only one file may be updated, causing one
test suite to pass with an incomplete environment and the other to fail —
or worse, both to silently read a stale `.env` file value for the
missing field.

A conftest.py must centralize the canonical required-env-var dict into a
single source of truth. The fixture should cover all four current
required fields:

| Settings field         | Env var              | Required |
|------------------------|----------------------|----------|
| `discord_bot_token`    | `DISCORD_BOT_TOKEN`  | yes      |
| `discord_guild_id`     | `DISCORD_GUILD_ID`   | yes      |
| `supabase_db_url`      | `SUPABASE_DB_URL`    | yes      |
| `supabase_service_key` | `SUPABASE_SERVICE_KEY` | yes    |

The remaining 9 Settings fields have defaults or are optional and do not
need env vars set for baseline test execution. This matches the current
`Settings` model exactly.

### F2. `sys.path.insert` hack is fragile and inconsistent — Severity: MEDIUM

`test_factory.py` and `test_contracts_base.py` contain
`sys.path.insert(0, str(Path(__file__).resolve().parents[1]))` at module
top level. `test_settings.py` and `test_contracts_chapters.py` import
`app.*` without the hack, meaning they depend on CWD being
`services/api/` or the package being installed.

This inconsistency means:
- Running `pytest` from the repo root will fail for some tests.
- The `sys.path` mutation is a module-scope side effect that is never
  reverted.

A root-level `conftest.py` at `services/api/tests/conftest.py` (or
`services/api/conftest.py`) should handle path setup once, eliminating
the per-file hack. Alternatively, adding `[tool.pytest.ini_options]
pythonpath = ["."]` to `services/api/pyproject.toml` would let pytest
handle it natively.

### F3. pydantic-settings `.env` file loading is not disabled — Severity: LOW

`Settings` extends `BaseSettings` without configuring
`model_config = SettingsConfigDict(env_file=None)`. By default,
pydantic-settings will read a `.env` file if one exists in the working
directory. If a developer has a `.env` with real credentials, test
execution could accidentally instantiate `Settings` with production
values if `monkeypatch.setenv` is missed for a field.

The current test pattern (monkeypatch all required vars, then
instantiate) is safe because `monkeypatch.setenv` takes precedence. But
the conftest.py should defensively clear all known Settings env vars
before setting test values (the pattern already used in
`test_settings.py:_clear_settings_env`), and the conftest fixture should
document that `.env` files may contribute values for optional fields.

This is informational — the monkeypatch approach is correct and
sufficient.

## Criteria Assessment

### 1. Do test env vars match what Settings requires?

The four required fields in `Settings` (those using `Field(...)` or
lacking defaults) are:

- `discord_bot_token` — `DISCORD_BOT_TOKEN`
- `discord_guild_id` — `DISCORD_GUILD_ID`
- `supabase_db_url` — `SUPABASE_DB_URL`
- `supabase_service_key` — `SUPABASE_SERVICE_KEY`

Both `test_factory.py:REQUIRED_ENV_VARS` and
`test_settings.py:_set_required_env` set exactly these four. The values
are safe test placeholders (`test-token-value`,
`900000000000000001`, `postgresql://user:pass@localhost:5432/db`,
`test-service-key`). None are real credentials.

`test_settings.py:ALL_SETTINGS_ENV_VARS` lists all 13 env vars
recognized by `Settings`, and `_clear_settings_env` deletes all of them
before setting test values — a belt-and-suspenders approach.

**Pass.** Env vars match. A conftest.py should adopt the
clear-then-set pattern from `test_settings.py`.

### 2. Is there any risk of test fixtures leaking into production?

No. The production entry point (`app/main.py:app = create_app()`)
instantiates `Settings()` from the real environment at import time.
Test code:

- Uses `monkeypatch.setenv` (function-scoped, auto-reverted by pytest).
- Never writes to disk (no `.env` file creation).
- Never touches the module-level `app` object from `main.py`.
- `httpx.AsyncClient` with `ASGITransport` runs in-process with no
  network listener.

The only side effect is `sys.path.insert` (see F2), which affects the
test process only and has no production consequence.

**Pass.** No leakage vector exists.

### 3. Are fixture scopes correct (no state leakage)?

All existing fixtures use function scope (pytest default):

- `test_contracts_base.py:versioned_app` — `@pytest.fixture()` —
  creates a fresh `FastAPI` app with a new in-memory `store` dict per
  test. No cross-test state.
- `test_contracts_chapters.py:chapter_store` — `@pytest.fixture()` —
  creates a fresh `_ChapterStore` per test. No cross-test state.
- `monkeypatch` — always function-scoped by pytest.

A conftest.py should keep the `settings` and `app` fixtures at function
scope. Session-scoped `Settings` would be unsafe because:

- Different tests may need different env var overrides.
- `monkeypatch` cannot be used with session-scoped fixtures (pytest
  limitation — `monkeypatch` is function-scoped).

**Pass.** Current scopes are correct. Conftest must preserve function
scope for env-dependent fixtures.

### 4. Is the TestClient usage safe?

Tests currently use `httpx.AsyncClient` with `httpx.ASGITransport`:

```python
async with httpx.AsyncClient(
    transport=httpx.ASGITransport(app=versioned_app),
    base_url="http://test",
) as client:
```

This is the recommended pattern for async FastAPI testing:

- No real TCP socket is opened (`base_url="http://test"` is a
  placeholder, never contacted).
- The `async with` context manager ensures proper cleanup.
- Each test gets its own client and transport instance via the
  function-scoped fixture.
- `httpx` is already a dev dependency in `pyproject.toml`.

A conftest.py providing a `client` fixture should follow this same
pattern. Using `fastapi.testclient.TestClient` (which wraps `httpx`
synchronously) is also acceptable but would lose async test support.

**Pass.** Client usage is safe and idiomatic.

## Recommendations

1. **Centralize env-var helpers** in conftest.py to eliminate the
   duplication identified in F1. Use the clear-then-set pattern from
   `test_settings.py`.
2. **Remove `sys.path.insert` hacks** from individual test files once
   conftest.py or `pyproject.toml` handles path setup (F2).
3. **Keep all env-dependent fixtures at function scope.** Do not use
   session scope for `Settings` or `app` fixtures.
4. **Provide a `client` fixture** using the existing
   `httpx.AsyncClient` + `ASGITransport` pattern, function-scoped.
