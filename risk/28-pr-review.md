# PR Review: `services/api/tests/conftest.py`

Date: 2026-04-13

## Multi-concern check

**Result: single concern — no decomposition needed.**

The PR adds two files:

- `services/api/tests/conftest.py` — shared test fixtures
- `services/api/tests/test_conftest.py` — tests verifying those fixtures

These are a single atomic unit. `test_conftest.py` exists solely to
validate `conftest.py`. Splitting them would produce a fixture file
with no proof it works. No decomposition is warranted.

## Justification check

### What belongs in this PR

**conftest.py fixtures 1–4 of 5** — `monkeypatch_session`,
`required_env`, `app`, `client`. These are the minimal shared HTTP
harness described in the proposal. They centralize duplicated env
setup, app construction, router mounting, and client lifecycle.

**test_conftest.py tests 1–4 of 5** —
`test_test_settings_fixture_produces_valid_settings_object`,
`test_app_fixture_returns_fastapi_instance`,
`test_app_fixture_has_v1_router_mounted`,
`test_client_fixture_can_make_http_requests`. These validate that
each fixture produces the correct type and that the harness is
wired end-to-end.

### What does not belong — or deviates from the approved proposal

#### F1. `test_settings` is session-scoped — proposal and audit say function-scoped

- **Severity**: MEDIUM
- **Location**: `services/api/tests/conftest.py:29`
- **Proposal**: `test_settings` scope is `function`
  (`proposals/28-conftest.md:55`)
- **Audit**: "A conftest.py should keep the `settings` and `app`
  fixtures at function scope. Session-scoped `Settings` would be
  unsafe." (`risk/28-audit.md:139-142`)
- **Implementation**: `scope="session"`
- **Impact**: A session-scoped `Settings` object is shared across all
  tests. If any test mutates `app.state.settings` (which points to
  this same object), the mutation leaks to every subsequent test in
  the session. Function-scoped `app` mitigates this partially — each
  test gets a new app with a new `app.state.settings` reference — but
  the underlying `Settings` instance is still shared. More critically,
  the proposal chose function scope so that individual tests could
  override env vars with function-scoped `monkeypatch` and get a
  `Settings` that reflects those overrides. With session scope,
  `test_settings` is frozen at first request and ignores later env
  changes.
- **Recommendation**: Change to `scope="function"` per the proposal.
  `Settings()` construction is cheap (validated in the proposal:
  "Settings() creation is cheap, so there is no value in widening the
  scope just to reuse the same object").

#### F2. `client` uses async `httpx.AsyncClient` — proposal specifies sync `TestClient`

- **Severity**: MEDIUM
- **Location**: `services/api/tests/conftest.py:41-45`
- **Proposal**: "Yield `TestClient(app)` for sync HTTP tests"
  (`proposals/28-conftest.md:55`). Anti-scope explicitly excludes
  "async client fixtures" (`proposals/28-conftest.md:271`).
- **Needs synthesis**: "Synchronous TestClient — consistent with
  existing test patterns in the project."
  (`research/28-conftest-needs.md:39`)
- **Research**: "`TestClient` is the correct choice for this file
  because the scope is a minimal synchronous HTTP harness."
  (`proposals/28-conftest.md:258`)
- **Implementation**: `pytest_asyncio.fixture()` yielding
  `httpx.AsyncClient` with `ASGITransport`
- **Impact**: All consumer tests must be `async def` with
  `@pytest.mark.asyncio()`. This changes the ergonomics for the
  primary use case (endpoint HTTP tests) and contradicts the proposal's
  explicit decision to keep sync and async paths separate. The existing
  82-test suite is entirely sync. The async pattern is valid on its own
  merits, but it was explicitly evaluated and rejected during proposal
  design.
- **Recommendation**: Either revert to sync `TestClient` per the
  proposal, or formally amend the proposal with justification for
  switching to async. Do not silently override a deliberate design
  decision.

#### F3. Chapter endpoint parametrized test duplicates existing coverage

- **Severity**: MEDIUM
- **Location**: `services/api/tests/test_conftest.py:57-78`
- **Duplicate of**: `services/api/tests/test_endpoints_chapters_stubs.py:63-85`
- **Description**: `test_chapter_endpoint_stubs_are_reachable_via_client`
  tests the same 5 chapter routes with the same methods, bodies, and
  `NOT_IMPLEMENTED` assertion as `test_chapter_stub_routes_exist_and_return_not_implemented`
  in the existing endpoint test file. The parametrize tuples are
  identical. This is endpoint behavior testing, not fixture validation.
- **Impact**: Duplicated test coverage across two files. When the PR
  to migrate `test_endpoints_chapters_stubs.py` to the shared harness
  lands, the duplication becomes exact. Meanwhile, a change to chapter
  endpoint behavior requires updating assertions in two places.
- **Recommendation**: Remove this test from `test_conftest.py`. The
  router-mounting validation is already covered by
  `test_app_fixture_has_v1_router_mounted` (which hits
  `/api/v1/health`). If additional router-mounting confidence is
  desired, a single non-parametrized chapter route assertion is
  sufficient — the full parametrized matrix belongs in the endpoint
  test file.

#### F4. `sys.path.insert` hack in `test_conftest.py`

- **Severity**: LOW
- **Location**: `services/api/tests/test_conftest.py:9`
- **Audit**: F2 flagged `sys.path.insert` as fragile and recommended
  conftest.py or `pyproject.toml` handle path setup once
  (`risk/28-audit.md:44-61`)
- **Description**: `conftest.py` itself does not have the hack (it
  works because pytest discovers it in the test directory). But
  `test_conftest.py` re-introduces the same
  `sys.path.insert(0, str(Path(__file__).resolve().parents[1]))` that
  the audit identified as a problem in existing test files.
- **Impact**: Low — the import on line 10 (`from app.core.settings
  import Settings`) could instead reference the `test_settings` fixture
  type without a direct import, or the path issue could be solved via
  `pyproject.toml` `pythonpath` config. The hack works but perpetuates
  the pattern the conftest was partly meant to address.
- **Recommendation**: Either configure `[tool.pytest.ini_options]
  pythonpath = ["."]` in `services/api/pyproject.toml`, or accept this
  as deferred cleanup. Not blocking.

## Summary

| # | Finding | Severity | Verdict |
|---|---------|----------|---------|
| F1 | `test_settings` session scope vs proposed function scope | MEDIUM | Change to function scope |
| F2 | Async client vs proposed sync TestClient | MEDIUM | Revert or amend proposal |
| F3 | Duplicated chapter endpoint test coverage | MEDIUM | Remove from test_conftest.py |
| F4 | `sys.path.insert` in test_conftest.py | LOW | Accept or defer |

**Overall**: The fixture structure and dependency chain are sound. The
three MEDIUM findings are all cases where the implementation deviates
from decisions that were explicitly evaluated and documented in the
proposal and risk artifacts. F1 and F2 are specification violations —
the proposal considered both alternatives and chose the opposite of
what was implemented. F3 is scope creep — test_conftest.py should
validate fixture mechanics, not re-test endpoint behavior that has
dedicated coverage elsewhere.

None of the findings indicate architectural risk. All are addressable
with small, localized changes.
