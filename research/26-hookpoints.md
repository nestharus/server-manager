# Hookpoint Research — Chapter contracts

## Existing code inventory

### `services/api/app/contracts/chapters.py`

- Does not exist today.
- `services/api/app/contracts/` currently contains only:
  - `base.py`
  - `__init__.py`
- This means the chapter contract module will be the first domain-
  specific contract module in the API package.

### `services/api/app/contracts/base.py`

- Defines a single reusable contract mixin:
  - `VersionedMixin(BaseModel)` with `version: int = Field(ge=0)`
- The docstring already matches the proposal's intended ownership:
  read/update contracts include it, create contracts do not.

### `services/api/app/contracts/__init__.py`

- Currently re-exports only `VersionedMixin`.
- The module-level docstring describes the package as the API boundary
  surface, but it does not establish a stronger convention that every
  contract module must be re-exported from the package root.

### `services/api/tests/test_contracts_base.py`

- Covers four current patterns:
  - package export checks (`from app.contracts import VersionedMixin`)
  - direct Pydantic validation behavior
  - JSON schema assertions via `model_json_schema()`
  - optimistic-locking contract tests through a minimal in-process
    FastAPI app using `httpx.ASGITransport`
- This is the only contract-focused test file in `services/api/tests/`.

### Adjacent code that overlaps chapter shape

- There is no existing API-layer chapter service, repository, or route
  code under `services/api/app/`.
- The only existing chapter data shape in the repo lives in the daemon:
  - `daemon/config.py`
  - `daemon/db.py`
- Those files are not direct hookpoints for `services/api/app/contracts/
  chapters.py`, but they do show current naming and lifecycle
  assumptions that may later need translation.

## Reusable components

### `VersionedMixin` is reusable as-is

- `ChapterRead` can inherit `VersionedMixin` directly.
- `ChapterUpdate` can inherit `VersionedMixin` directly.
- `ChapterCreate` should remain a plain `BaseModel`.
- No change is required in `VersionedMixin` to support the proposal:
  - it already makes `version` required
  - it already enforces `>= 0`
  - its current semantics align with the existing optimistic-locking
    tests

### Existing package export pattern is reusable, but optional

- `contracts/__init__.py` already demonstrates the re-export pattern for
  `VersionedMixin`.
- That pattern can be extended to chapter symbols if the implementation
  wants `from app.contracts import ChapterRead` style imports.
- It does not strictly need to be updated for proposal compliance,
  because no existing code depends on package-root chapter exports and
  the proposal explicitly keeps package-wide re-export strategy outside
  the chapter module's scope.

### Existing validation test style is reusable

- `test_contracts_base.py` uses straightforward `pytest.raises(
  ValidationError)` assertions for invalid inputs.
- It asserts JSON schema shape directly from `model_json_schema()`.
- It verifies inheritance by defining a small subclass of
  `VersionedMixin`.
- These patterns are a good fit for future chapter contract tests.

### Existing optimistic-locking HTTP tests are reusable

- The in-process FastAPI app in `test_contracts_base.py` already encodes
  the AGENTS.md contract:
  - create returns version `0`
  - read returns current version
  - update with current version succeeds and increments
  - stale update returns `409`
- Those tests already cover the shared versioning contract, so chapter-
  specific tests would not need to duplicate that entire HTTP fixture
  unless chapter endpoints add behavior beyond base version semantics.

## New components needed

### New contract module

- Add `services/api/app/contracts/chapters.py` with exactly four public
  symbols:
  - `ChapterStatus`
  - `ChapterCreate`
  - `ChapterRead`
  - `ChapterUpdate`

### New field-level validation inside `chapters.py`

- `name` needs trimming plus non-empty/max-length validation.
- `slug` needs regex/max-length validation.
- Discord snowflake fields need `int | None` with `gt=0` when present.
- `created_at` and `id` are new read-only fields not represented in
  current API contracts.
- `status` is a new enum not represented anywhere in the current API
  package.

### Likely new tests

- There is no existing `services/api/tests/test_contracts_chapters.py`.
- A new test file will likely be needed to cover:
  - importability
  - enum values
  - required vs omitted fields
  - trimmed `name` behavior
  - slug regex behavior
  - nullable/positive Discord ID behavior
  - JSON schema shape for create/read/update models
  - omission vs explicit `null` behavior on `ChapterUpdate`

## Test infrastructure notes

### Patterns to follow from `test_contracts_base.py`

- Keep tests at the contract boundary, not service/repository level.
- Use `ValidationError` assertions for model validation.
- Use `model_json_schema()` for OpenAPI-facing expectations.
- Keep small helper models local to the test file when validating
  inheritance or HTTP behavior.
- Prefer direct, single-purpose tests over a large parametrized matrix;
  that is the current repo style.

### Specific note for `ChapterUpdate`

- The proposal requires omission and explicit `null` to remain
  distinguishable.
- Pydantic v2 supports this through unset tracking (`model_fields_set`
  and `exclude_unset=True`), not through any special behavior in
  `VersionedMixin`.
- Future tests should assert both:
  - omitted field is absent from `exclude_unset=True`
  - explicitly provided `null` is present in `model_fields_set`

### Import/bootstrap quirk

- `test_contracts_base.py` manually inserts `services/api` onto
  `sys.path` before importing `app.*`.
- `test_settings.py` does not do this.
- That inconsistency is not a blocker, but it is a small surprise in
  current test infrastructure and should be kept consistent when adding
  new contract tests.

## Conflicts or surprises

### No direct conflict inside the current API package

- There is no existing `chapters.py`, no existing chapter contracts, and
  no existing API chapter endpoints.
- Adding the contract module is additive within `services/api/app/`.

### Current daemon chapter shape does not match the proposed API shape

- `daemon/config.py` and `daemon/db.py` use `display_name`, while the
  proposal uses `name`.
- The daemon uses `category_id`, `officer_role_id`, and
  `member_role_id`, while the proposal uses `discord_category_id`,
  `discord_officer_role_id`, and `discord_member_role_id`.
- The daemon schema requires those IDs immediately; the proposal allows
  them to be `None` during provisioning.
- The daemon models chapter lifecycle via `archived_at` and surrounding
  provisioning assumptions; the proposal introduces an explicit
  `ChapterStatus` enum with `active`, `archived`, and `provisioning`.
- The daemon chapter row is keyed by `slug`; the proposal's read model
  introduces a server-assigned integer `id`.

These are not conflicts for this contract module itself, but they are
real translation gaps for any later API/service/repository layer that
tries to bridge old daemon data and the new API contracts.

### `VersionedMixin` coercion is currently permissive

- Existing tests explicitly expect `"7"` to coerce to `7`.
- The proposal only requires "integer, `>= 0`" and does not demand
  strict integer parsing, so this is compatible today.
- If the project later wants strict integer-only request parsing, that
  would be a separate contract-wide decision and would affect existing
  tests in `test_contracts_base.py`.

## Direct answers to the task questions

1. Does `contracts/chapters.py` already exist?
   - No.
2. Does `VersionedMixin` need changes to support the proposed contracts?
   - No. Current behavior is sufficient.
3. Does `contracts/__init__.py` need updating to re-export chapter
   types?
   - Not strictly. Only if the implementation wants package-root
     imports for chapter symbols.
4. What test patterns exist in `test_contracts_base.py` to follow?
   - ValidationError checks, JSON schema assertions, inheritance checks,
     and a minimal FastAPI/httpx optimistic-locking fixture.
5. Any conflicts with existing code?
   - No direct API-package conflicts. The only notable mismatch is with
     older daemon chapter naming/lifecycle fields, which will need
     translation later.
