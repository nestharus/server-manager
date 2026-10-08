# Shortcut risk assessment — proposals/28-conftest.md

Date: 2026-04-13
Assessor: claude-opus (shortcut)

## Verdict

**LOW**

The proposal defines five fixtures with fully resolved scopes,
dependencies, and teardown behavior. No backward-compatibility shims,
no deferred stubs, no problematic hardcoded values, and no hidden dual
code paths. The v1 router mounting in the test harness is an explicit,
documented compensation for a known gap in the runtime entrypoint — it
mirrors what existing tests already do and is not a compatibility shim.
The env var test values are standard pytest practice, not configurable
parameters masquerading as literals. Anti-scope is cleanly drawn and
matches the actual codebase state.

## Findings

### Finding 1 — No backward-compatibility shims

- **Severity**: LOW
- **Criterion**: 1 (backward-compatibility shims)
- **Description**: There is no existing `conftest.py` under
  `services/api/tests/`. This is a greenfield file. The proposal
  introduces no deprecated aliases, re-exports, feature flags for old
  behavior, or transitional code paths. The anti-scope section
  explicitly excludes "compatibility aliases for old helper names." The
  existing per-module helpers (`_set_required_env`, `_build_test_app`,
  `REQUIRED_ENV_VARS` in `test_factory.py` and
  `test_endpoints_chapters_stubs.py`) are not preserved as
  backward-compatible wrappers — the proposal replaces the pattern with
  shared fixtures. Existing test files that assert negative env
  behavior (missing vars, validation errors) continue to use their own
  local `monkeypatch` and are not forced through the shared harness.
- **Recommendation**: Accept. Clean greenfield fixture module with no
  compatibility layer.

### Finding 2 — No deferred stubs or TODOs

- **Severity**: LOW
- **Criterion**: 2 (deferred stubs or TODOs)
- **Description**: All five fixtures (`monkeypatch_session`,
  `required_env`, `test_settings`, `app`, `client`) are fully specified
  with scope, dependency chain, and behavior. No fixture is described
  as "placeholder" or "to be implemented later." The anti-scope
  excludes database fixtures, repository mocks,
  `app.dependency_overrides` wiring, auth helpers, async clients, and
  custom plugins — but these exclusions are correct because the
  corresponding production code does not exist yet:
  `repositories/__init__.py`, `services/__init__.py`, and
  `infrastructure/__init__.py` are all package markers with no
  implementation. The proposal does not create empty fixture stubs for
  these future concerns. Each exclusion matches the actual codebase
  state, not a deferred obligation.
- **Recommendation**: Accept. Nothing is stubbed or deferred.

### Finding 3 — Hardcoded test env values are appropriate

- **Severity**: LOW
- **Criterion**: 3 (hardcoded values that should be configurable)
- **Description**: The `required_env` fixture sets four env vars to
  fixed test values: `DISCORD_BOT_TOKEN="test-token-value"`,
  `DISCORD_GUILD_ID="<guild id>"`,
  `SUPABASE_DB_URL="postgresql://user:pass@localhost:5432/db"`,
  `SUPABASE_SERVICE_KEY="test-service-key"`. These are test-only
  dummy values that satisfy `Settings` validation. They are not
  configurable parameters — they exist solely to make `Settings()`
  instantiation succeed without a real environment. The existing tests
  (`test_factory.py:15-21`, `test_settings.py:29-34`,
  `test_endpoints_chapters_stubs.py:16-21`) already use these exact
  same values, so the conftest centralizes rather than introduces them.
  Making test env values configurable (via env vars that configure
  other env vars) would add indirection with no benefit.
- **Recommendation**: Accept. Test fixture constants are the correct
  pattern for dummy env values.

### Finding 4 — V1 router mounting is not a dual code path

- **Severity**: LOW
- **Criterion**: 4 (dual code paths)
- **Description**: The `app` fixture calls `create_app(settings=...)`
  then includes the v1 router via `app.include_router(v1_router)`. The
  runtime entrypoint (`app/main.py:8`) calls only `create_app()` and
  does not mount the v1 router. This creates a divergence between test
  and runtime app composition. However, this is not a dual code path
  or compatibility shim — it is the same pattern the existing test
  suite already uses. `test_endpoints_chapters_stubs.py:59` manually
  mounts the chapters router after `create_app()`. The conftest
  improves on that by mounting the aggregated v1 router (which includes
  all endpoint routers) instead of individual routers, which is closer
  to the correct runtime composition. The proposal explicitly documents
  this as a "current architecture gap" compensation and states it
  "does not change factory behavior, runtime wiring, or router prefix
  strategy." The function-scoped `app` fixture means each test gets a
  fresh app, so when `create_app()` is eventually updated to include
  the v1 router, the conftest mount will produce duplicate routes in
  that single test app — but that is a straightforward one-line fix
  in `conftest.py` at that time, not a hidden maintenance trap.
- **Recommendation**: Accept. Documented compensating fixture that
  mirrors and improves existing test behavior.

### Finding 5 — Session-scoped env does not create ambient shortcuts

- **Severity**: LOW
- **Criterion**: 4 (dual code paths — env scoping)
- **Description**: The proposal uses a session-scoped
  `monkeypatch_session` for env var setup while the existing tests use
  function-scoped `monkeypatch`. This could create a dual-scoping
  pattern where session env bleeds into tests that expect a clean
  environment. The proposal addresses this directly: `required_env` is
  explicit (not `autouse=True`), so it only activates for tests that
  request it through the fixture dependency chain. Tests that assert
  missing-env behavior (e.g., `test_settings.py`) continue to use
  function-scoped `monkeypatch.delenv()` to clear specific vars,
  which overrides the session-level values. The research confirms this
  interaction is safe: "tests that assert missing env already clear env
  vars explicitly with function-scoped monkeypatch." No ambient
  shortcut is created because the harness is opt-in.
- **Recommendation**: Accept. Explicit fixture dependency prevents
  ambient env pollution.

## Overall assessment

All four shortcut criteria were evaluated against the proposal text,
research document, needs synthesis, existing test files
(`test_factory.py`, `test_settings.py`,
`test_endpoints_chapters_stubs.py`), and the source code they exercise
(`factory.py`, `settings.py`, `router.py`, `main.py`). No shortcut
pattern was found at MEDIUM or HIGH severity. The proposal creates a
minimal, fully specified fixture set that centralizes existing
duplicated patterns without introducing compatibility shims, deferred
stubs, problematic hardcoded values, or hidden dual code paths. The
one compensating behavior (v1 router mounting) is explicitly
documented, mirrors existing test behavior, and is a clean fixture
concern — not a runtime workaround.
