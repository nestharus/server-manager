# Scope Risk Assessment: Shared API Test Fixtures (`services/api/tests/conftest.py`)

## Overall: LOW

The proposal defines a minimal pytest conftest delivering three
fixtures — test settings (env vars via monkeypatch), a test app
(factory + v1 router), and a TestClient — with no database, no
mocks, no authentication, and no async client. The scope matches
the current codebase exactly: the existing tests in `test_factory.py`
and `test_settings.py` each duplicate the same four required env var
definitions, and no shared test harness exists. The anti-scope
explicitly fences out five categories of expansion. The fixture
surface is proportionate to a single conftest file in a single PR.

Note: this assessment was performed against the proposal prompt
(`prompt-28-proposal.md`) and the current codebase state because
the formal research and proposal artifacts (`research/28-conftest.md`,
`research/28-conftest-needs.md`, `proposals/28-conftest.md`) have not
yet been generated. The proposal intent is sufficiently narrow that
the scope risk evaluation is not materially affected.

## Findings

### Finding 1: Proposal stays within anti-scope
- Severity: LOW
- Description: The anti-scope excludes five categories: database
  fixtures, mock injection, authentication, async client, and custom
  test runners. The current codebase has no database layer, no auth
  middleware, and no custom test runner. The only async test usage is
  in `test_contracts_base.py` (which uses `httpx.AsyncClient` with
  `ASGITransport` for its own in-process versioned-entity app), but
  this is self-contained and unrelated to the conftest's sync
  `TestClient` fixture. There are no imports, dependencies, or code
  paths in the proposal prompt that would cross any anti-scope boundary.
  The proposal targets exactly the HTTP harness layer — env vars,
  app factory, `TestClient` — and nothing else.

### Finding 2: Scope is appropriate for a single PR
- Severity: LOW
- Description: The conftest introduces roughly three fixtures totaling
  20-30 lines of code:
  1. Session-scoped env var setup via `monkeypatch_session` (4 env
     vars: `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `SUPABASE_DB_URL`,
     `SUPABASE_SERVICE_KEY`)
  2. A test app fixture calling `create_app()` with the v1 router
     mounted
  3. A `TestClient` wrapping that app

  Even if the PR also refactors `test_factory.py` to consume the shared
  fixtures (eliminating its local `REQUIRED_ENV_VARS` dict and
  `_set_required_env` / `_clear_required_env` helpers), the total diff
  is small. `test_settings.py` should NOT be refactored in the same PR
  because its tests specifically exercise missing-env-var paths and
  need fine-grained per-test env control — this is correctly outside
  the conftest's concern. The PR is well within single-PR size.

### Finding 3: Fixture setup is not over-engineered
- Severity: LOW
- Description: The proposal specifies `monkeypatch_session` for env
  vars, which is a standard pytest pattern for session-scoped env
  fixtures (a 3-4 line custom fixture wrapping `MonkeyPatch`). This
  is the only non-trivial pattern. The app fixture calls the existing
  `create_app()` factory and mounts the existing v1 router — no custom
  app builder, no middleware injection, no startup/shutdown hooks. The
  `TestClient` fixture is a single-line wrapper. No parametrization,
  no fixture factories, no conditional logic. The three-fixture stack
  (env → app → client) is the minimal viable test harness for HTTP
  endpoint tests.

  One design consideration: session-scoped env vars persist across all
  tests. Tests that need to verify missing-env-var behavior (like
  `test_settings.py`) would need their own function-scoped
  `monkeypatch.delenv()` calls to override the session state. This
  works correctly — function-scoped monkeypatch operates independently
  and reverts after each test — but should be documented in the
  conftest so future contributors understand the interaction. This is
  a minor clarity concern, not over-engineering.

### Finding 4: No critical missing fixtures identified
- Severity: LOW
- Description: The three proposed fixtures cover the immediate need:
  HTTP-level endpoint testing without a database. Examining the
  existing test files:
  - `test_factory.py` — needs env vars + `create_app`. Directly
    served by conftest.
  - `test_settings.py` — needs fine-grained env var control. Correctly
    remains self-managed; conftest does not attempt to absorb it.
  - `test_contracts_base.py` — pure Pydantic schema tests plus its own
    self-contained versioned-entity app. No conftest dependency needed.
  - `test_contracts_chapters.py` — pure Pydantic contract tests. No
    conftest dependency needed.

  Future endpoint tests (chapters CRUD, health) are the primary
  consumers. The v1 router currently exposes only the health endpoint;
  chapter endpoints will be added later. The conftest mounts the router
  so any future endpoint registered under `v1/` is automatically
  reachable — no conftest changes needed as endpoints grow.

  Database fixtures, repository mocks, and auth fixtures are correctly
  deferred to later proposals. The conftest can be extended
  incrementally when those layers exist.

## Recommendations

None. The proposal is well-scoped for a single conftest file in a
single PR. No changes required.
