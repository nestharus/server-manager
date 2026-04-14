# Proposal: Base Contract Module (VersionedMixin)

## Objective

Write a concrete design proposal for `services/api/app/contracts/base.py`
based on the research in `research/22-contracts-base.md` and the
synthesis in `research/22-contracts-base-needs.md`.

## Context

- Module path: `services/api/app/contracts/base.py`
- Already imported by `services/api/app/contracts/__init__.py` as
  `from app.contracts.base import VersionedMixin`
- Pydantic v2 (2.13.0), FastAPI
- Must follow java-interview-setup optimistic locking pattern
- Version is a public contract field, not an internal detail

## Constraints from Research + Synthesis

1. `VersionedMixin` should be a `BaseModel` subclass (stable pattern)
2. Provides `version: int` field with `ge=0` constraint
3. Version is required in read/update schemas
4. Version starts at 0 for newly created entities
5. No config that would create MRO issues in multi-base scenarios
6. Clean JSON Schema / OpenAPI output

## Deliverable

Write the proposal to `proposals/22-contracts-base.md`. Include:
- Architecture: class hierarchy and field definitions
- Tradeoffs: why BaseModel parent vs plain class mixin
- Anti-scope: what this module does NOT do
- Test contract: what tests should verify

## Rules

- Do NOT implement — proposal only
- Do NOT write code files
- Output must be a standalone markdown document
