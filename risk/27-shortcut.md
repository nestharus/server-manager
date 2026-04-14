# Shortcut Risk Assessment: Chapter Endpoint Stubs (Proposal 27)

Date: 2026-04-13

## Evaluation Criteria

### 1. Backward-compatibility shims — LOW

The proposal introduces a new module
(`services/api/app/api/v1/endpoints/chapters.py`) with no pre-existing
code to replace. There are no re-exports, deprecated aliases,
transitional paths, or dual-support patterns. The module follows the
exact construction of the existing `health.py` endpoint. Nothing is
being wrapped, shimmed, or kept alive for compatibility.

### 2. 501 stubs intentional and documented — LOW

All five endpoints raise `HTTPException(status_code=HTTPStatus.NOT_IMPLEMENTED)`.
This is explicitly documented in three places:

- The proposal's route table includes a "Current stub behavior" column
  stating `raises 501 Not Implemented` for every route.
- The "Exact Module Structure" section shows the literal code with
  `raise HTTPException(status_code=HTTPStatus.NOT_IMPLEMENTED)` in
  each handler.
- The needs synthesis confirms the purpose: "The endpoints exist only
  to provide a stable HTTP surface for the test agent to target."

These stubs are the declared intent of the proposal, not accidental
debt. They exist to lock the HTTP contract (methods, paths, request/
response shapes, success status codes) before service and repository
layers are built. The implementation pipeline (AGENTS.md phases 5-6)
is the mechanism that replaces them.

### 3. Hardcoded values that should be configurable — LOW

No hardcoded magic numbers, config values, or constants that should be
externalized. Specifics:

- Router prefix `"/api/v1/chapters"` follows the established pattern
  (`"/api/v1/health"`). Version prefixing is structural, not
  configurable.
- Status codes use `HTTPStatus` enum constants, not raw integers.
- Path parameter `chapter_id: int` is a type declaration, not a
  hardcoded value.
- No environment-specific strings, timeouts, or limits.

### 4. Dual code paths or feature flags — LOW

Each handler has exactly one code path: raise 501. No conditional
logic, no environment checks, no feature flags, no `if settings.X`
branching. The proposal explicitly avoids premature structure: "Use
plain synchronous `def` handlers for now, matching `health.py` and
avoiding premature async structure before service calls exist."

### 5. TODO markers or placeholder comments — LOW

The proposal's code sample contains no TODO, FIXME, or "will be
implemented later" inline comments. The module docstring
(`"""Chapter endpoint stubs."""`) accurately describes the current
content. The anti-scope section cleanly delineates what is out of
scope at the proposal level without creating inline debt markers in
the code.

The statement "The central v1 router should later include it" in the
Architecture section refers to implementation-phase wiring (phase 6),
not an in-code placeholder. This is standard pipeline sequencing.

## Additional Observations

- **No shared helper for stubs**: The proposal raises `HTTPException`
  directly in each handler rather than creating a `_not_implemented()`
  helper. For five small stubs this is the right call — no premature
  abstraction.
- **Contract reuse is clean**: The proposal imports `ChapterCreate`,
  `ChapterRead`, and `ChapterUpdate` directly from the existing
  contracts module. No re-wrapping, no endpoint-local type aliases.
- **Archive as POST action**: Using `POST /{chapter_id}/archive`
  instead of overloading `PATCH` with status mutation is a deliberate
  design choice with documented rationale, not a shortcut.

## Overall Risk: LOW

The proposal is a clean, minimal endpoint stub module that follows the
existing codebase patterns exactly. It introduces no backward-
compatibility shims, no dual code paths, no feature flags, no
hardcoded configurables, and no undocumented debt. The 501 stubs are
the explicit purpose of the proposal and are fully documented. No
changes are required before implementation.
