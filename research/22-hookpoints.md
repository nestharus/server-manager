# Hookpoint Research: `VersionedMixin` (`contracts/base.py`)

Date: 2026-04-13

## Scope

This note maps
[proposals/22-contracts-base.md](proposals/22-contracts-base.md:1)
onto the current repository.

It is hookpoint-only research. It answers:

- what already exists under `services/api/app/contracts/`
- what test patterns exist under `services/api/tests/`
- whether any version-related implementation already exists
- what import paths and package seams the contracts module must satisfy

It does not include implementation code.

## Primary Sources

- Proposal:
  [proposals/22-contracts-base.md](proposals/22-contracts-base.md:1)
- Prior research:
  [research/22-contracts-base.md](research/22-contracts-base.md:1)
- Needs synthesis:
  [research/22-contracts-base-needs.md](research/22-contracts-base-needs.md:1)
- Current contracts package seam:
  [services/api/app/contracts/__init__.py](services/api/app/contracts/__init__.py:1)
- Current test files:
  [services/api/tests/test_settings.py](services/api/tests/test_settings.py:1)
  [services/api/tests/test_factory.py](services/api/tests/test_factory.py:1)
- Existing API package/import structure:
  [services/api/app/main.py](services/api/app/main.py:1)
  [services/api/app/core/factory.py](services/api/app/core/factory.py:1)
  [services/api/pyproject.toml](services/api/pyproject.toml:1)

## 1. Existing contracts package state

### Current file listing

Under `services/api/app/contracts/`, there is currently exactly one
tracked source file:

- [services/api/app/contracts/__init__.py](services/api/app/contracts/__init__.py:1)

There is no `services/api/app/contracts/base.py` yet.

### What is reusable

The existing `__init__.py` is already the intended package seam for the
proposal:

- it documents that contracts are the public API boundary
- it states that optimistic-locking-capable contracts use
  `VersionedMixin`
- it already re-exports `VersionedMixin` from `app.contracts.base`
  ([services/api/app/contracts/__init__.py](services/api/app/contracts/__init__.py:1))

That means the package-level export surface is already chosen. The main
missing hookpoint is the target module itself:

- `services/api/app/contracts/base.py`

Practical implication:

- `__init__.py` should be reused rather than replaced
- the future `base.py` only needs to satisfy the import that already
  exists at line 8
- there is no evidence of any other contracts package structure that
  needs preserving

### Current gap

Because `__init__.py` already does `from app.contracts.base import
VersionedMixin`, `import app.contracts` is currently a broken path until
`base.py` exists
([services/api/app/contracts/__init__.py](services/api/app/contracts/__init__.py:8)).

That is useful for hookpoint planning:

- no extra re-export wiring is needed
- the new module must land at exactly `app/contracts/base.py`
- adding a differently named module would create a parallel system
  instead of satisfying the existing seam

## 2. Existing test patterns to follow

There are currently only two API test files:

- [services/api/tests/test_settings.py](services/api/tests/test_settings.py:1)
- [services/api/tests/test_factory.py](services/api/tests/test_factory.py:1)

### Patterns already used

The current tests are small, direct `pytest` unit tests with these
consistent traits:

- flat function-style tests, no test classes
- descriptive `test_...` names stating one expected behavior each
- local helper functions at top of file for shared setup
- direct assertions on object state or metadata
- `pytest.raises(...)` for validation/error-path checks
- no fixtures in `conftest.py`
- no parametrization

Examples:

- `test_settings.py` uses helper functions to set and clear env vars,
  then asserts one behavior per test with direct model construction and
  `ValidationError` checks
  ([services/api/tests/test_settings.py](services/api/tests/test_settings.py:24),
  [services/api/tests/test_settings.py](services/api/tests/test_settings.py:37),
  [services/api/tests/test_settings.py](services/api/tests/test_settings.py:49))
- `test_factory.py` follows the same flat style and uses one explicit
  import-surface assertion plus direct object assertions
  ([services/api/tests/test_factory.py](services/api/tests/test_factory.py:33),
  [services/api/tests/test_factory.py](services/api/tests/test_factory.py:38),
  [services/api/tests/test_factory.py](services/api/tests/test_factory.py:67))

### Implications for future `VersionedMixin` tests

The proposal's module-level contract tests
([proposals/22-contracts-base.md](proposals/22-contracts-base.md:181))
fit the current style well:

- instantiate the model directly
- assert accepted and rejected values directly
- use `pytest.raises(ValidationError)` for omitted/negative cases
- inspect `model_json_schema()` directly without spinning up FastAPI

There is no existing pattern here for API-schema tests, HTTP tests, or
fixture-heavy contract testing. For this module, the existing local
style points toward pure Pydantic unit tests rather than endpoint tests.

### Import-path pattern in tests

One detail matters for package imports:

- `test_settings.py` imports directly from `app.core.settings`
  ([services/api/tests/test_settings.py](services/api/tests/test_settings.py:4))
- `test_factory.py` also uses `app...` imports and additionally inserts
  `services/api` onto `sys.path` at runtime
  ([services/api/tests/test_factory.py](services/api/tests/test_factory.py:8),
  [services/api/tests/test_factory.py](services/api/tests/test_factory.py:10))

That means contract tests should assume the package import root is
`app`, not `services.api.app`.

## 3. Existing version-related code

### What exists today

Inside `services/api`, the only current runtime uses of the word
`version` are application/package metadata, not optimistic-locking
contracts:

- `Settings.app_version`
  ([services/api/app/core/settings.py](services/api/app/core/settings.py:7))
- FastAPI app metadata wired from settings
  ([services/api/app/core/factory.py](services/api/app/core/factory.py:8))
- package version in `pyproject.toml`
  ([services/api/pyproject.toml](services/api/pyproject.toml:3))

The only optimistic-locking-specific runtime mention in API code is the
commentary and re-export stub in `app.contracts.__init__`
([services/api/app/contracts/__init__.py](services/api/app/contracts/__init__.py:3)).

### What does not exist yet

There is currently no implementation in `services/api` for:

- a versioned entity contract
- optimistic-lock request validation
- stale-write conflict handling
- `409 Conflict` translation
- service/repository/domain version comparison logic
- downstream entity schemas that would inherit `VersionedMixin`

The optimistic-locking behavior exists only as project guidance and
research/proposal material at this stage:

- proposal anti-scope says `contracts/base.py` should not implement
  stale-write checks or `409 Conflict` mapping
  ([proposals/22-contracts-base.md](proposals/22-contracts-base.md:158))
- project instructions require future entity tests to verify `read ->
  N`, `update with N -> N+1`, and `stale -> 409 Conflict`
  ([AGENTS.md](AGENTS.md:146))

### Hookpoint consequence

There is no existing optimistic-locking subsystem to integrate with.
This task is establishing the first contract-layer primitive. That
reduces coupling risk, but it also means implementation should not
invent adjacent abstractions that the current tree does not need yet.

## 4. Import structure that must work

### Physical file location vs import path

The file will live at:

- `services/api/app/contracts/base.py`

But the import surface must be package-root `app.*`, not filesystem-path
`services.api.app.*`.

Evidence:

- the wheel packages `app`
  ([services/api/pyproject.toml](services/api/pyproject.toml:26))
- `app.main` imports `create_app` via `from app.core.factory import
  create_app`
  ([services/api/app/main.py](services/api/app/main.py:6))
- the existing contracts package already expects
  `from app.contracts.base import VersionedMixin`
  ([services/api/app/contracts/__init__.py](services/api/app/contracts/__init__.py:8))

### Import paths that should work after the module exists

These are the stable paths implied by the current package layout:

- `from app.contracts.base import VersionedMixin`
- `from app.contracts import VersionedMixin`

The second path is already encoded by `__all__`
([services/api/app/contracts/__init__.py](services/api/app/contracts/__init__.py:10)).

### Import structure to avoid

Avoid introducing alternate public paths such as:

- `from services.api.app.contracts.base import VersionedMixin`
- `from app.contracts.versioned import VersionedMixin`
- package-level indirection outside `app.contracts.__init__`

None of those surfaces exist today, and creating them would add a
parallel import story for a module that already has a chosen package
entrypoint.

## 5. Parallel systems to avoid

### Avoid a second contract-base abstraction

The proposal is intentionally one model with one field
([proposals/22-contracts-base.md](proposals/22-contracts-base.md:63)).
The current tree has no shared contract base class, no helper module,
and no alternate contracts package layout. Adding extra layers now would
be parallel structure rather than reuse.

Concretely, avoid introducing:

- a second base module such as `versioned.py` or `mixins.py`
- a plain Python mixin plus a separate `BaseModel` wrapper
- a broader shared contract base carrying unrelated fields
- schema helper functions or validators that go beyond the proposal

### Avoid conflating optimistic-lock version with app metadata version

The only live `version` fields in API code today are `app_version` and
FastAPI/OpenAPI metadata
([services/api/app/core/settings.py](services/api/app/core/settings.py:7),
[services/api/app/core/factory.py](services/api/app/core/factory.py:10)).
Those are unrelated to optimistic locking and should not become a
design precedent for contract-layer version handling.

### Avoid bundling downstream concurrency behavior into this module

The proposal explicitly excludes:

- create-schema behavior
- stale-write checking
- `409 Conflict` mapping
- unrelated shared fields
- backward-compatibility shims

([proposals/22-contracts-base.md](proposals/22-contracts-base.md:158))

That matters because there is currently no downstream versioned entity
implementation to reuse. If `contracts/base.py` starts carrying service
logic, it will become the first parallel system rather than the thin
contract primitive the proposal approved.

## 6. Reusable hookpoints summary

### Reuse as-is

- [services/api/app/contracts/__init__.py](services/api/app/contracts/__init__.py:1)
  as the package-level export seam
- current `app.*` absolute import style shown across API modules
  ([services/api/app/main.py](services/api/app/main.py:6),
  [services/api/app/core/factory.py](services/api/app/core/factory.py:3))
- current flat `pytest` style from `test_settings.py` and
  `test_factory.py`

### Create in the future implementation phase

- `services/api/app/contracts/base.py`
- a focused contract test file under `services/api/tests/` for
  `VersionedMixin` module behavior and package import behavior

### No existing parallel system to preserve

There is no current optimistic-locking implementation in `services/api`
beyond the re-export stub and planning docs. The main hookpoint is to
satisfy the already-declared `app.contracts` seam without introducing
extra package structure or contract abstractions.
