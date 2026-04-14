# Hookpoint Research: VersionedMixin (contracts/base.py)

## Objective

Map the proposal in `proposals/22-contracts-base.md` to existing code.
Find what's reusable, what's parallel, and what needs to be created.

## Context

- Proposal: `proposals/22-contracts-base.md`
- Target file: `services/api/app/contracts/base.py`
- Already imported by: `services/api/app/contracts/__init__.py`
- Existing tests: `services/api/tests/test_settings.py`, `services/api/tests/test_factory.py`
- The module defines `VersionedMixin` as a Pydantic BaseModel subclass
  with a `version: int = Field(ge=0)` field

## Research Questions

1. What exists in `services/api/app/contracts/` currently?
2. What test patterns are used in `services/api/tests/`?
3. Is there any existing version-related code in the codebase?
4. What's the import structure needed for the contracts package?

## Output

Write findings to `research/22-hookpoints.md`. Include:
- Existing file listing and what can be reused
- Test patterns to follow
- Import paths that need to work
- Any parallel systems to avoid

## Rules

- Do NOT implement — research only
- Do NOT write code files
