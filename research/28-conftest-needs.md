# Synthesis: Shared API Test Fixtures — Humility Needs

## Purpose

Map the research in `research/28-conftest.md` to Humility's specific
requirements for a shared test fixture file.

## What Humility needs

A minimal `conftest.py` in `services/api/tests/` that:

1. **Provides test-specific environment variables** — sets
   `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `SUPABASE_DB_URL`, and
   `SUPABASE_SERVICE_KEY` to test values so individual tests don't
   need to set them manually.

2. **Creates a configured FastAPI test app** — uses the factory
   pattern (`create_app(settings)`) with test settings, and includes
   the v1 router so all endpoints are reachable.

3. **Provides a TestClient fixture** — a `client` fixture that
   yields a configured `TestClient` for HTTP-level testing.

4. **No real database** — tests mock the repository layer. The
   conftest provides the HTTP harness only, not DB connections.

### Key decisions

1. **Auto-set env vars via autouse fixture** — a session-scoped
   `monkeypatch` that sets required env vars before any test runs.
   This removes the need for individual tests to call `monkeypatch.setenv()`.

2. **Mount v1 router in test app** — the factory currently doesn't
   auto-mount the v1 router, so the conftest should do it.

3. **Function-scoped client** — each test gets a fresh client to
   avoid state leakage.

4. **Synchronous TestClient** — consistent with existing test
   patterns in the project. The existing 82 tests all use sync.

### What's NOT in scope

- Database fixtures (no DB yet)
- Mock/stub injection for services/repositories (no services yet)
- Authentication fixtures (no auth yet)
- Async client setup (not needed for current sync patterns)

### Gaps

None. The conftest is straightforward wiring.
