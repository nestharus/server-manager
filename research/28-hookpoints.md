# Hookpoint Research — `conftest.py`

## Existing code that can be replaced by `conftest.py` fixtures

### `services/api/tests/test_endpoints_chapters_stubs.py`

- This is the clearest current hookpoint for the proposed shared
  fixtures.
- The file duplicates all of the setup the proposal wants to
  centralize:
  - required env values in `REQUIRED_ENV_VARS`
    (`services/api/tests/test_endpoints_chapters_stubs.py:16`)
  - env bootstrap in `_set_required_env(...)`
    (`services/api/tests/test_endpoints_chapters_stubs.py:32`)
  - `Settings()` construction plus `create_app(settings=...)` in
    `_build_test_app(...)`
    (`services/api/tests/test_endpoints_chapters_stubs.py:55`)
  - `TestClient(app)` lifecycle inside the endpoint assertions
    (`services/api/tests/test_endpoints_chapters_stubs.py:79`)
- Under the proposal, this file can stop building its own app/client
  harness and instead consume:
  - `client` for request/response tests
  - `app` for route-shape inspection
- The file-specific router-loading helpers
  (`_load_chapters_endpoint_module`, `_load_chapters_router`) become
  much less necessary once the shared `app` fixture mounts the
  aggregated v1 router.

### `services/api/tests/test_factory.py`

- This file reuses the same required env values and local env helpers:
  - `REQUIRED_ENV_VARS` (`services/api/tests/test_factory.py:15`)
  - `_set_required_env(...)` (`services/api/tests/test_factory.py:23`)
  - `_clear_required_env(...)` (`services/api/tests/test_factory.py:28`)
- Only the positive-path env bootstrap overlaps with the proposed
  fixture set.
- The negative-path test
  `test_create_app_without_args_raises_validation_error_when_required_env_vars_are_missing`
  depends on direct control over missing env state
  (`services/api/tests/test_factory.py:62`), so that part should remain
  local.
- The proposal explicitly keeps targeted factory tests outside the
  shared HTTP harness boundary, so this file has only partial,
  optional fixture reuse.

### `services/api/tests/test_settings.py`

- This file also duplicates required env setup via `_set_required_env`
  (`services/api/tests/test_settings.py:29`).
- Unlike the endpoint test, most of this module is about validation
  behavior under precise env mutations:
  - deleting one required variable at a time
  - overriding type/optional values
  - asserting default behavior
- Because those tests depend on function-local control of the process
  environment, this file is not a primary consumer of the proposed
  shared fixtures.
- At most, the happy-path `Settings()` test cases could reuse a shared
  `test_settings` fixture, but the proposal does not require that
  change.

## Test files that benefit from the shared fixtures

### Immediate beneficiary

- `services/api/tests/test_endpoints_chapters_stubs.py`
  - It is already an HTTP-level test file.
  - It currently duplicates the full harness the proposal describes.
  - It is the only existing test file in `services/api/tests/` that
    clearly needs `client` and `app`.

### Partial or optional beneficiaries

- `services/api/tests/test_factory.py`
  - Some positive-path tests could consume `test_settings` instead of
    rebuilding `Settings()` after local env setup.
  - It should not adopt `client` or shared app/router mounting because
    it is testing `create_app()` directly, not the HTTP surface.

- `services/api/tests/test_settings.py`
  - A small subset of happy-path tests could theoretically consume
    `required_env` or `test_settings`.
  - In practice, most of the module benefits more from staying
    self-contained because its assertions are about env parsing and env
    failures.

### No meaningful benefit

- `services/api/tests/test_contracts_base.py`
- `services/api/tests/test_contracts_chapters.py`

- These files do not exercise `Settings`, `create_app`, router
  mounting, or `TestClient`, so the proposed `conftest.py` is outside
  their scope.

## Does any existing code need modification?

### Application code

- `services/api/app/core/factory.py`: no modification required.
  - The proposal intentionally preserves the current seam:
    `create_app(settings=...)` already returns a fresh `FastAPI` app and
    stores the provided settings on `app.state`
    (`services/api/app/core/factory.py:6`).
  - `conftest.py` can call this factory and then mount the v1 router in
    the fixture layer, exactly as the proposal describes.

- `services/api/app/api/v1/router.py`: no modification required.
  - The aggregated v1 router already exists and already includes the
    endpoint modules that should be reachable in tests
    (`services/api/app/api/v1/router.py:13`).
  - The proposal's `app` fixture can import this router and include it
    directly; there is no need to change router composition.

### Test code

- `services/api/tests/test_endpoints_chapters_stubs.py`: yes, this is
  the main file that should be modified to consume shared fixtures.
- `services/api/tests/test_factory.py`: maybe, but only for selective
  positive-path cleanup.
- `services/api/tests/test_settings.py`: maybe, but only if the team
  wants limited happy-path fixture reuse; most tests should remain
  local.

## What can be reused as-is?

### Reusable values and setup shape

- The canonical required env values already match the proposal in both
  existing env-aware test modules:
  - `DISCORD_BOT_TOKEN=test-token-value`
  - `DISCORD_GUILD_ID=900000000000000001`
  - `SUPABASE_DB_URL=postgresql://user:pass@localhost:5432/db`
  - `SUPABASE_SERVICE_KEY=test-service-key`
  (`services/api/tests/test_endpoints_chapters_stubs.py:16`,
  `services/api/tests/test_factory.py:15`,
  `services/api/tests/test_settings.py:29`)
- Those values can be reused directly in a shared `required_env`
  fixture without inventing a new baseline.

### Reusable factory seam

- `create_app(settings=...)` is already the correct construction seam
  for the proposed `app` fixture
  (`services/api/app/core/factory.py:6`).
- No wrapper or alternate factory is needed.

### Reusable router aggregation

- `app.api.v1.router.router` is already the correct router object for
  the proposed `app` fixture to mount
  (`services/api/app/api/v1/router.py:13`).
- This lets `conftest.py` use the top-level v1 composition layer
  instead of reaching into individual endpoint modules.

### Reusable client pattern

- The `with TestClient(app) as client:` pattern already exists in
  `test_endpoints_chapters_stubs.py` and can be lifted directly into a
  shared `client` fixture
  (`services/api/tests/test_endpoints_chapters_stubs.py:81`).

## Direct answers

1. What existing test env-var setup code can be replaced by `conftest.py` fixtures?
   - Definitely: the duplicated required-env bootstrap in
     `test_endpoints_chapters_stubs.py`.
   - Partially: the happy-path env bootstrap in `test_factory.py` and
     `test_settings.py`.
   - Not safely: the negative-path env manipulation in `test_factory.py`
     and `test_settings.py`, which should stay local.

2. What test files will benefit from the shared fixtures?
   - Primary: `services/api/tests/test_endpoints_chapters_stubs.py`.
   - Secondary/optional: selective positive-path tests in
     `services/api/tests/test_factory.py` and
     `services/api/tests/test_settings.py`.
   - No benefit: the contract-only test files.

3. Does any existing code need modification?
   - Application code: no.
   - Test code: yes, mainly `services/api/tests/test_endpoints_chapters_stubs.py`.

4. What can be reused as-is?
   - The current required env values.
   - `create_app(settings=...)` in `services/api/app/core/factory.py`.
   - The aggregated `router` in `services/api/app/api/v1/router.py`.
   - The existing `TestClient` context-manager pattern.

## Boundary note

- `research/28-conftest-needs.md` describes autouse env setup, while
  `proposals/28-conftest.md` specifies an explicit `required_env`
  dependency. The hookpoint mapping above assumes the proposal is the
  source of truth, because that is the artifact this phase was asked to
  map onto code.
