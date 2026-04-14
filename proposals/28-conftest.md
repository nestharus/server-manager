# Proposal: `services/api/tests/conftest.py`

Date: 2026-04-13

## Goal

Add a shared pytest fixture module at `services/api/tests/conftest.py`
to provide the minimal HTTP test harness for API endpoint tests.

This proposal is design only. It does not include implementation code.

The file should centralize the setup that is currently duplicated in
endpoint-oriented tests:

- required settings env vars
- `Settings()` construction for tests
- factory-built FastAPI app creation
- v1 router mounting
- `TestClient` lifecycle management

It should not introduce database wiring, mocks, auth helpers, async
clients, or custom test execution behavior.

## Where It Fits

`services/api/tests/conftest.py` is the directory-level pytest fixture
entrypoint for the API test suite. Its role is narrow:

- provide a reusable HTTP harness for tests that exercise the FastAPI
  surface
- preserve the current factory seam by building apps through
  `create_app(settings=...)`
- compensate for the current architecture gap where `create_app()`
  does not mount the v1 router

It does not replace targeted unit tests of `Settings` or `create_app`.
Those tests should continue to control their own environment when they
need to assert validation failures or factory behavior without the
shared harness.

In practice:

- HTTP endpoint tests should request `client` or `app`
- tests that only need parsed settings can request `test_settings`
- negative env tests should continue to use function-scoped
  `monkeypatch` locally and should not depend on the shared HTTP
  fixtures

## Proposed Fixture Set

| Fixture | Scope | Depends on | Purpose |
|---|---|---|---|
| `monkeypatch_session` | `session` | — | Custom session-safe monkeypatch fixture for env setup |
| `required_env` | `session` | `monkeypatch_session` | Set the required API env vars once for the shared harness |
| `test_settings` | `function` | `required_env` | Build a fresh `Settings` object from the shared test env |
| `app` | `function` | `test_settings` | Build a fresh FastAPI app and mount the v1 router |
| `client` | `function` | `app` | Yield `TestClient(app)` for sync HTTP tests |

## Fixture Definitions

### `monkeypatch_session`

Define a custom session-scoped fixture named `monkeypatch_session`
because pytest’s built-in `monkeypatch` fixture is function-scoped.

Shape:

- create `pytest.MonkeyPatch()`
- `yield` it
- call `.undo()` in teardown

Reasoning:

- the proposal requirement explicitly asks for session-scoped env setup
  via `monkeypatch_session`
- this keeps the env bootstrap in pytest-native fixture machinery rather
  than in ad hoc module helpers

### `required_env`

Define a session-scoped fixture that uses `monkeypatch_session.setenv()`
to set exactly the required settings fields already used in the suite:

- `DISCORD_BOT_TOKEN`
- `DISCORD_GUILD_ID`
- `SUPABASE_DB_URL`
- `SUPABASE_SERVICE_KEY`

Recommended test values should match the existing pattern in
`test_factory.py` and `test_endpoints_chapters_stubs.py` so the suite
has one canonical baseline.

This fixture should be explicit, not `autouse=True`.

Reasoning:

- explicit dependency keeps the shared HTTP harness visible at the test
  call site
- research already surfaced that broad autouse fixtures expand their
  blast radius across the whole directory
- `test_settings.py` and negative factory tests still need direct
  control over missing-env cases

Tradeoff:

- once first requested, a session-scoped env fixture remains active for
  the rest of the test session
- that is acceptable here because tests that assert missing env already
  clear env vars explicitly with function-scoped `monkeypatch`
- the shared harness should therefore be treated as opt-in for HTTP
  tests, not as the default for env-validation tests

### `test_settings`

Define a function-scoped fixture that instantiates and returns
`Settings()` after `required_env` has established the test environment.

It should not mutate settings fields, override optional provider keys,
or inject any test-only subclassing.

Reasoning:

- a fresh `Settings` object per test avoids cross-test mutation through
  `app.state.settings`
- `Settings()` creation is cheap, so there is no value in widening the
  scope just to reuse the same object
- this follows the current local pattern where tests instantiate
  `Settings()` after env setup rather than fabricating alternate config
  objects

### `app`

Define a function-scoped fixture that:

1. calls `create_app(settings=test_settings)`
2. includes the aggregated v1 router from `app.api.v1.router`
3. returns the configured `FastAPI` app

The fixture should mount the top-level v1 router, not individual
endpoint routers.

Reasoning:

- the proposal requirement is that chapter endpoints be reachable
- mounting the aggregated v1 router mirrors the actual API composition
  layer instead of repeating per-endpoint assembly in tests
- this keeps the fixture aligned with future endpoint growth: any
  endpoint added to `app/api/v1/router.py` becomes reachable in HTTP
  tests without editing `conftest.py`
- function scope avoids route duplication, app state leakage, and
  future dependency-override residue between tests

Boundary rule:

- this fixture compensates for the current fact that `create_app()` does
  not include the v1 router
- it does not change factory behavior, runtime wiring, or router prefix
  strategy

### `client`

Define a function-scoped fixture that yields
`TestClient(app)` as a context manager:

- `with TestClient(app) as client:`
- `yield client`

Reasoning:

- this matches the current endpoint test pattern
- it stays on the synchronous FastAPI testing path requested in scope
- the context-manager form is the correct default if lifespan hooks are
  added later

This fixture is the main public entrypoint for HTTP-level API tests.

## Dependency Flow

The intended fixture graph is:

`monkeypatch_session` -> `required_env` -> `test_settings` -> `app` -> `client`

That gives the suite one canonical bootstrap path for sync API tests:

1. establish test env
2. parse settings from env
3. build app through the factory
4. mount the v1 router
5. drive requests through `TestClient`

## Usage Expectations

The shared harness is for HTTP tests only.

Examples of the intended split:

- chapter endpoint tests should request `client`
- tests that need to inspect route registration should request `app`
- tests that only care about settings parsing can request
  `test_settings`
- tests asserting missing env behavior should keep their own local
  `monkeypatch.delenv(...)` setup and avoid the shared harness

This preserves the suite’s current separation between:

- endpoint wiring tests
- settings validation tests
- factory behavior tests

## Tradeoffs Considered

### Session env fixture vs repeated per-test env setup

Session-scoped env setup removes the current duplication in HTTP tests
and gives all shared fixtures one consistent baseline. The downside is
ambient process-level state once the fixture is activated.

That tradeoff is acceptable because:

- the required env surface is small and stable
- the current env-negative tests already clear env explicitly
- the harness is intentionally minimal and explicit

### Explicit fixture dependency vs `autouse=True`

Explicit is the better fit.

`autouse=True` would hide the HTTP harness from tests that do not need
it and would blur the boundary between endpoint tests and settings
validation tests. Keeping `required_env`, `app`, and `client` opt-in
maintains clearer test intent.

### Function-scoped `app` and `client` vs broader reuse

Function scope is the right default even though it rebuilds the app more
often.

It avoids:

- shared `app.state` mutations
- duplicated router inclusion on reused app instances
- future contamination from dependency overrides or middleware state

The construction cost is negligible for the current minimal API.

### Mounting the v1 router in `conftest.py` vs changing `create_app()`

For this proposal, router mounting belongs in the test harness.

Changing `create_app()` would be an application-wiring decision, not a
test-fixture decision. The current prompt is only about shared test
fixtures, so the proposal keeps runtime architecture unchanged and makes
the test harness compensate for the current gap.

### `TestClient` vs `httpx.AsyncClient`

`TestClient` is the correct choice for this file because the scope is a
minimal synchronous HTTP harness. The suite already has separate async
testing patterns where needed; this proposal should not collapse those
two paths into one fixture set.

## Anti-Scope

The following do not belong in `services/api/tests/conftest.py` for
this proposal:

- database fixtures or live database setup
- repository, service, or infrastructure mocks
- `app.dependency_overrides` wiring
- authentication or authorization helpers
- async client fixtures
- custom pytest plugins, runners, or markers
- compatibility aliases for old helper names
- router-by-router fixture assembly
- changing `create_app()` or runtime `main.py`

## Resulting Test Architecture

After this proposal, `services/api/tests/conftest.py` becomes the
single shared bootstrap for sync API HTTP tests, while specialized
tests keep their own narrow setup when they are validating something
other than the HTTP harness itself.

That gives the API suite a clear split:

- shared fixture wiring for HTTP tests in `conftest.py`
- direct local setup in tests that are intentionally probing settings or
  factory edge cases

This is the smallest change that removes the current duplication,
exposes the real v1 route tree to tests, and stays within the project’s
current architecture.
