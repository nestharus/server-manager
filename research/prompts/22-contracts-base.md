# Research: Base Contract Module (VersionedMixin)

## Objective

Research the problem space for a base contract module that provides a
`VersionedMixin` for Pydantic schemas supporting optimistic locking.

## Context

This module lives at `services/api/app/contracts/base.py` in a FastAPI
monorepo for Discord server management (Humility guild). The project
follows patterns from `java-interview-setup` which uses:
- `VersionedEntity` base class with optimistic locking via version column
- `AuditInfo` / `AuditorContextHolder` for audit trails
- Entity validators at the domain layer
- Mapper pattern for entity <-> DTO conversion

The contracts package is the API boundary — what the outside world sees.
Internal service/repository types may differ.

## Research Questions

1. **Optimistic locking in Pydantic**: How should a version field be
   represented in Pydantic v2 schemas? What type (int)? What default
   for creation vs update?

2. **Mixin pattern in Pydantic v2**: What's the correct way to define
   a mixin that can be composed with other Pydantic models? Should it
   be a plain class, a BaseModel subclass, or use model_config?

3. **Version field semantics**: In the java-interview-setup pattern,
   reads return version N; updates must provide version N and get back
   N+1; stale writes (wrong version) return 409 Conflict. How should
   the contract express this — required field? Optional with None for
   creation?

4. **Discord platform considerations**: Are there any Discord-specific
   entities that would use versioned contracts? (Submissions,
   applications, tickets, etc.)

5. **Pydantic v2 best practices**: Field validators, model_config
   settings, JSON schema generation considerations for OpenAPI.

## Output

Write your findings to `research/22-contracts-base.md`. Document each
question with evidence and examples. Do NOT propose solutions — only
document the problem space.

## Rules

- Do your own research — do not delegate
- Do NOT propose implementations or designs
- Reference existing code in the project where relevant
- Output must be a standalone markdown report
