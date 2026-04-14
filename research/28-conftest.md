# Research: Shared API Test Fixtures (`conftest.py`)

Date: 2026-04-13

## Scope

This note documents the problem space for shared pytest fixtures in
`services/api/tests/`.

It is limited to:

- pytest `conftest.py` fixture discovery and scope behavior
- FastAPI test-client patterns for factory-built apps
- test-only settings injection via environment variables
- current router-mounting behavior in local tests and runtime entrypoints
- mock-friendly seams for API tests when no real database is allowed

It does not propose a final `conftest.py` layout, fixture set, or
implementation plan.

## Local Baseline

- There is currently no `conftest.py` under `services/api/tests/`
  (`find services/api/tests -name 'conftest.py'` returned no files).
- The current API tests pass as-is: `uv run --project services/api pytest services/api/tests -q`
  reported `82 passed in 0.27s`.
- Environment setup is duplicated today:
  - [test_factory.py](/home/nes/discord/services/api/tests/test_factory.py:15)
  - [test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:7)
  - [test_endpoints_chapters_stubs.py](/home/nes/discord/services/api/tests/test_endpoints_chapters_stubs.py:16)
- The factory accepts an optional injected `Settings` object, builds a
  `FastAPI` app, and stores settings on `app.state`, but it does not
  mount any routers
  ([factory.py](/home/nes/discord/services/api/app/core/factory.py:6)).
- The v1 router already exists and aggregates both `chapters` and
  `health`
  ([router.py](/home/nes/discord/services/api/app/api/v1/router.py:13)).
- The runtime entrypoint currently does only `app = create_app()`
  without including the v1 router
  ([main.py](/home/nes/discord/services/api/app/main.py:1)).
- `rg -n "api\\.v1\\.router|include_router\\(" services/api/app services/api/tests`
  shows only three relevant inclusions:
  - the v1 aggregator includes `chapters` and `health`
  - the chapter endpoint test manually mounts the chapter router
- The repository, service, and infrastructure packages are currently
  placeholders only
  ([repositories/__init__.py](/home/nes/discord/services/api/app/repositories/__init__.py:1),
  [services/__init__.py](/home/nes/discord/services/api/app/services/__init__.py:1),
  [infrastructure/__init__.py](/home/nes/discord/services/api/app/infrastructure/__init__.py:1)).
- `Settings` is a `BaseSettings` model with required Discord and
  Supabase fields plus optional provider keys
  ([settings.py](/home/nes/discord/services/api/app/core/settings.py:5)).

## Primary Sources

- Local repo:
  - [services/api/app/core/factory.py](/home/nes/discord/services/api/app/core/factory.py:1)
  - [services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:1)
  - [services/api/app/api/v1/router.py](/home/nes/discord/services/api/app/api/v1/router.py:1)
  - [services/api/app/api/v1/endpoints/health.py](/home/nes/discord/services/api/app/api/v1/endpoints/health.py:1)
  - [services/api/app/api/v1/endpoints/chapters.py](/home/nes/discord/services/api/app/api/v1/endpoints/chapters.py:1)
  - [services/api/app/main.py](/home/nes/discord/services/api/app/main.py:1)
  - [services/api/tests/test_factory.py](/home/nes/discord/services/api/tests/test_factory.py:1)
  - [services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:1)
  - [services/api/tests/test_endpoints_chapters_stubs.py](/home/nes/discord/services/api/tests/test_endpoints_chapters_stubs.py:1)
  - [services/api/tests/test_contracts_base.py](/home/nes/discord/services/api/tests/test_contracts_base.py:142)
  - [services/api/tests/test_contracts_chapters.py](/home/nes/discord/services/api/tests/test_contracts_chapters.py:234)
- Official pytest docs:
  - How to use fixtures:
    https://docs.pytest.org/en/stable/how-to/fixtures.html
  - Fixtures reference:
    https://docs.pytest.org/en/9.0.x/reference/fixtures.html
  - Monkeypatch:
    https://docs.pytest.org/en/stable/how-to/monkeypatch.html
- Official FastAPI docs:
  - Testing:
    https://fastapi.tiangolo.com/tutorial/testing/
  - Bigger Applications:
    https://fastapi.tiangolo.com/tutorial/bigger-applications/
  - Testing events / lifespan:
    https://fastapi.tiangolo.com/advanced/testing-events/
  - Testing dependencies with overrides:
    https://fastapi.tiangolo.com/advanced/testing-dependencies/
  - Async tests:
    https://fastapi.tiangolo.com/advanced/async-tests/
- Official Pydantic Settings docs:
  - BaseSettings API:
    https://pydantic.dev/docs/validation/latest/api/pydantic_settings/

## 1. `pytest` `conftest.py` patterns

### `conftest.py` is pytest’s directory-level fixture mechanism

The pytest fixtures reference states that `conftest.py` provides
fixtures for an entire directory, that those fixtures are
auto-discovered without imports, and that nested directories can add
their own `conftest.py` files on top of parent ones.

Source:

- pytest fixtures reference, lines 227-230:
  `conftest.py` serves as a means of providing fixtures for an entire
  directory, and nested test directories can layer additional
  `conftest.py` files
  https://docs.pytest.org/en/9.0.x/reference/fixtures.html

The same page also states that fixture lookup is directional: tests can
search upward through parent scopes, but not downward into sibling or
child scopes, and the first matching fixture found is the one used.

Source:

- pytest fixtures reference, lines 283-285:
  upward search is allowed, downward search is not, and nearer fixtures
  can override broader ones
  https://docs.pytest.org/en/9.0.x/reference/fixtures.html

This matters locally because `services/api/tests/` currently has only
module-local helpers and fixtures, so nothing in that tree is shared by
pytest discovery yet.

### Fixture scopes are explicit and include `package`

The pytest fixture guide states that fixtures are created when first
requested and destroyed according to scope. The documented scope values
are:

- `function`
- `class`
- `module`
- `package`
- `session`

Source:

- pytest fixture guide, lines 389-399
  https://docs.pytest.org/en/stable/how-to/fixtures.html
- pytest fixture guide, lines 318-320
  https://docs.pytest.org/en/stable/how-to/fixtures.html

The same docs state that higher-scoped fixtures execute before
lower-scoped fixtures.

Source:

- pytest fixtures reference, lines 344-380
  https://docs.pytest.org/en/9.0.x/reference/fixtures.html

### Reuse, autouse, and teardown behavior

Pytest documents fixtures as reusable, cached per test request, and
shareable via `conftest.py`. It also documents `autouse=True` fixtures
as executing automatically for every reachable test in their scope.

Source:

- pytest fixture guide, lines 173-175, 289-293
  https://docs.pytest.org/en/stable/how-to/fixtures.html
- pytest fixtures reference, lines 444-449
  https://docs.pytest.org/en/9.0.x/reference/fixtures.html

For teardown, pytest documents `yield` fixtures as the cleaner and more
straightforward option compared with direct finalizers.

Source:

- pytest fixture guide, lines 491-498
  https://docs.pytest.org/en/stable/how-to/fixtures.html

Research implication from the docs, not a design proposal: broad
autouse fixtures affect every reachable test in scope, while explicit
fixtures keep the dependency surface visible at the test call site.

## 2. FastAPI `TestClient` fixture patterns

### FastAPI’s documented sync test path is `TestClient(app)`

FastAPI’s testing guide states that a `TestClient` is created by
passing the FastAPI application object, and then used like `httpx` from
normal synchronous `def` tests.

Source:

- FastAPI testing guide, lines 271-303
  https://fastapi.tiangolo.com/tutorial/testing/

This matches the current local chapter endpoint tests, which build a
real app object and use `with TestClient(app) as client:`
([test_endpoints_chapters_stubs.py](/home/nes/discord/services/api/tests/test_endpoints_chapters_stubs.py:55)).

### `with TestClient(app)` is the documented pattern when lifespan matters

FastAPI’s testing-events guide states that if tests need `lifespan`
startup/shutdown behavior, `TestClient` should be used as a context
manager. The docs show the app state being initialized inside the
`with TestClient(app)` block and torn down when the block exits.

Source:

- FastAPI testing-events guide, lines 236-275
  https://fastapi.tiangolo.com/advanced/testing-events/

The local API factory does not currently define lifespan hooks, but the
existing chapter endpoint tests already use the context-manager form
([test_endpoints_chapters_stubs.py](/home/nes/discord/services/api/tests/test_endpoints_chapters_stubs.py:81)).

### Factory-built apps already fit the documented testing model

Locally, `create_app(settings=...)` returns a concrete `FastAPI`
instance and stores the resolved settings on `app.state`
([factory.py](/home/nes/discord/services/api/app/core/factory.py:6)).

`test_create_app_with_provided_settings_uses_same_object_and_skips_settings_init`
verifies that when a `Settings` object is supplied, the factory uses
that exact object and does not instantiate `Settings()` again
([test_factory.py](/home/nes/discord/services/api/tests/test_factory.py:39)).

That is relevant evidence for reusable client fixtures because the app
factory already exposes an injected-settings seam.

### Async tests are a separate documented path

FastAPI’s async-tests guide states that once the test itself becomes
`async def`, `TestClient` is no longer the tool to use inside that
test; the documented pattern is `httpx.AsyncClient` with
`ASGITransport(app=app)`.

Source:

- FastAPI async-tests guide, lines 252-264 and 287-346
  https://fastapi.tiangolo.com/advanced/async-tests/

The local suite already uses that pattern in
[test_contracts_base.py](/home/nes/discord/services/api/tests/test_contracts_base.py:147).

## 3. Test settings injection without polluting the real environment

### `monkeypatch.setenv` / `delenv` are the documented pytest tools

Pytest’s monkeypatch docs explicitly list `setenv()` and `delenv()` for
environment-variable changes during tests, and state that all
modifications are undone after the requesting test function or fixture
finishes.

Source:

- pytest monkeypatch guide, lines 86-101 and 231-279
  https://docs.pytest.org/en/stable/how-to/monkeypatch.html

The same docs also show that this environment setup can be moved into
fixtures and shared across tests.

Source:

- pytest monkeypatch guide, lines 261-279
  https://docs.pytest.org/en/stable/how-to/monkeypatch.html

This is exactly the local duplication pattern today:

- [test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:24)
- [test_factory.py](/home/nes/discord/services/api/tests/test_factory.py:23)
- [test_endpoints_chapters_stubs.py](/home/nes/discord/services/api/tests/test_endpoints_chapters_stubs.py:32)

### Local `Settings` already reads from env at instantiation time

`Settings` inherits from `BaseSettings`
([settings.py](/home/nes/discord/services/api/app/core/settings.py:2)).

The Pydantic Settings API describes `BaseSettings` as a base class that
allows values to be overridden by environment variables.

Source:

- Pydantic Settings API, lines 585-592
  https://pydantic.dev/docs/validation/latest/api/pydantic_settings/

The local tests confirm that behavior:

- `Settings()` succeeds when required env vars are set
  ([test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:37))
- missing required vars raise `ValidationError`
  ([test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:45))
- explicit environment overrides change parsed settings values
  ([test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:170))

### Current API tests do not touch a real database despite DB-shaped env vars

The current tests set `SUPABASE_DB_URL` and `SUPABASE_SERVICE_KEY` to
dummy values, but the suite still passes without any running database.
That is consistent with the current code: the settings model validates
those fields as strings, but no repository or infrastructure code uses
them yet.

Relevant local evidence:

- required settings fields:
  [settings.py](/home/nes/discord/services/api/app/core/settings.py:11)
- placeholder repository layer only:
  [repositories/__init__.py](/home/nes/discord/services/api/app/repositories/__init__.py:1)
- passing suite:
  `82 passed in 0.27s`

## 4. Router mounting in tests

### The v1 router exists, but the factory does not mount it

The local router composition is split in two layers:

- endpoint modules define routers with concrete `/api/v1/...` prefixes
  ([health.py](/home/nes/discord/services/api/app/api/v1/endpoints/health.py:11),
  [chapters.py](/home/nes/discord/services/api/app/api/v1/endpoints/chapters.py:11))
- `app/api/v1/router.py` aggregates those endpoint routers
  ([router.py](/home/nes/discord/services/api/app/api/v1/router.py:13))

But `create_app()` does not include that v1 router
([factory.py](/home/nes/discord/services/api/app/core/factory.py:6)),
and `app/main.py` currently only calls `create_app()`
([main.py](/home/nes/discord/services/api/app/main.py:5)).

`rg` also shows no other inclusion site for `app.api.v1.router`.

### Current endpoint tests compensate by mounting routers manually

The chapter endpoint tests build an app with the factory and then
manually attach the chapter router:

- `_build_test_app()` calls `create_app(settings=settings)`
- then `app.include_router(_load_chapters_router(), tags=["chapters"])`

Source:

- [test_endpoints_chapters_stubs.py](/home/nes/discord/services/api/tests/test_endpoints_chapters_stubs.py:55)

This is current observed behavior, not an inference:

- factory-built apps do not currently expose the v1 route tree on their
  own
- tests that need chapter routes are attaching them explicitly

### FastAPI’s documented router pattern is inclusion into the main app or another router

FastAPI’s “Bigger Applications” docs describe `APIRouter` as the unit
for grouped path operations and document two composition steps:

- include routers in the main `FastAPI` app
- or include one `APIRouter` inside another

Source:

- FastAPI bigger-applications guide, lines 335-399
  `APIRouter` is the grouped endpoint unit
  https://fastapi.tiangolo.com/tutorial/bigger-applications/
- FastAPI bigger-applications guide, lines 988-992
  routers can be included in other routers before inclusion in the app
  https://fastapi.tiangolo.com/tutorial/bigger-applications/

Relative to those docs, the local code has the router composition layer
but not yet the final app-mount step.

## 5. Mock vs real database in tests

### The current API surface has no repository seam wired into endpoints yet

The prompt says API tests must not use a real database and should mock
the repository layer. In the current codebase, that repository layer is
not yet connected to the FastAPI endpoints:

- `repositories/`, `services/`, and `infrastructure/` only contain
  package markers
- `chapters` endpoints are still `501 Not Implemented` stubs
  ([chapters.py](/home/nes/discord/services/api/app/api/v1/endpoints/chapters.py:14))
- `health` reads only `request.app.state.settings`
  ([health.py](/home/nes/discord/services/api/app/api/v1/endpoints/health.py:15))
- `rg -n "Depends\\(|dependency_overrides|Repository|repository"` in
  `services/api/app` finds no dependency-injected repository objects

So the repository-mocking requirement is ahead of the current endpoint
implementation surface.

### FastAPI’s documented test seam for replacing collaborators is dependency overrides

FastAPI’s testing-overrides guide documents `app.dependency_overrides`
as the mechanism for replacing dependencies during tests. The docs say:

- overrides are stored in `app.dependency_overrides`, a simple `dict`
- keys are original dependency callables
- values are test replacements
- overrides can be reset by assigning `{}` again

Source:

- FastAPI testing-overrides guide, lines 247-268 and 374-379
  https://fastapi.tiangolo.com/advanced/testing-dependencies/

The same page states that these overrides can replace dependencies used
in path operation functions, decorators, and even `.include_router()`
calls.

Source:

- FastAPI testing-overrides guide, lines 369-376
  https://fastapi.tiangolo.com/advanced/testing-dependencies/

That is the framework-level mock seam documented by FastAPI. Locally,
that seam is available in principle, but no API dependency currently
exposes a repository object through it.

### Existing local tests already prefer in-process fakes over external state

Two current test modules already use in-memory collaborators instead of
external services:

- `test_contracts_chapters.py` defines a local `_ChapterStore` and
  exposes it through a fixture
  ([test_contracts_chapters.py](/home/nes/discord/services/api/tests/test_contracts_chapters.py:234))
- `test_contracts_base.py` defines a small in-memory FastAPI app and
  drives it through `httpx.AsyncClient`
  ([test_contracts_base.py](/home/nes/discord/services/api/tests/test_contracts_base.py:142))

Those tests are not repository-layer tests, but they are clear local
evidence that the current suite already prefers process-local fakes and
does not require a real database.

## Summary of Constraints Surfaced

- Shared fixtures are a pytest-native pattern via directory-level
  `conftest.py`; nothing under `services/api/tests/` uses that pattern
  yet.
- The local FastAPI factory already supports injected settings, which is
  a usable testing seam.
- Env setup duplication is real and currently handled with
  `monkeypatch`; pytest documents moving exactly that pattern into
  fixtures.
- The v1 router tree exists, but the factory and runtime entrypoint do
  not mount it today; current endpoint tests therefore mount routers
  manually.
- No real database is touched by the current API tests, and no
  repository dependency is wired into the FastAPI layer yet; the
  documented FastAPI seam for future collaborator replacement is
  `app.dependency_overrides`.
