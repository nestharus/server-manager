# SLICE-001: Persistence and mutation substrate

## Parent

**Initiative:** Phase 0 foundation slice
**Phase:** Phase 0

## What Changes for the Operator

Deployment operators can stand up a durable API write path with migrations, versioned reads, and a single optimistic-locking mutation primitive instead of per-feature storage conventions. This is the first point where the system can promise community-owned state instead of draft-only in-memory behavior.

## Justification Chain

**Market signal:** Cross-cutting market findings show portability and vendor-instability concerns are real; communities need durable state they control rather than vendor-local histories.
**Problem axis:** §14 — Consolidated Failure Risk and Operational Availability
**Proposal mechanism:** proposal.md, Cross-cutting Concerns -> Data Portability; Governance Mechanisms -> Configuration Safety
**Philosophy principles:** Principle 2: Live-Server Safety, Principle 5: Low Lock-in, Principle 10: Durable State over Ephemeral State

## Technical Specification

**Schema objects:**
- PersistenceSubstrateRead / MigrationRevisionRead: database revision visibility and migration status
- VersionedRead / MutationRequest / MutationResult: shared version, ETag, expected-version mutation contract

**API endpoints:**
- GET /api/v1/system/migrations/current -> MigrationRevisionRead

**Discord interactions:**
- none

**State transitions:**
- database schema: previous revision -> current Alembic head
- versioned entity mutation: version N -> version N+1; stale expected_version -> 412 Precondition Failed

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-001 | Persistence Substrate With Migrations | `services/api/app/contracts/persistence.py` | migrations/env.py, migrations/script.py.mako, migrations/versions/wu-001_persistence.py, services/api/app/contracts/persistence.py, services/api/app/repositories/db.py, services/api/app/api/v1/endpoints/system.py, services/api/tests/test_persistence.py |
| WU-002 | Mutation Primitive And Versioned Base Contracts | `services/api/app/contracts/base.py` | services/api/app/contracts/base.py, services/api/app/contracts/mutations.py, services/api/app/services/mutations.py, services/api/app/repositories/mutations.py, services/api/tests/test_mutations.py |

## Dependencies

**Upstream slices:** none
**Foundation dependencies:** none
**Parallelizable with:** SLICE-005

## Acceptance Criteria

- [ ] A clean database upgrades to the current Alembic head with no manual steps.
- [ ] The migration-status surface returns the live applied revision from the running database.
- [ ] Read with version N, update with expected_version N, then retry with stale N returns 412 Precondition Failed.
- [ ] Failed writes roll back cleanly and leave no partial rows committed.

## Engineering Notes

**Effort:** Persistence substrate with migrations -> L-XL (leans L); Single write-path mutation primitive -> M-L (leans M)
**Prototyping:** Persistence substrate with migrations -> no; Single write-path mutation primitive -> no
**Risk:** Medium — Phase 0 completeness risk is concentrated here because every later authoritative mutation assumes durable storage and one mutation primitive.
**Existing code:** Reuse the current `services/api/` layered proof point and its optimistic-locking patterns as the shape for durable repositories and endpoint surfaces.
**Known challenges:** Turning an in-memory proof point into a durable substrate without leaking feature-specific write paths into later slices.
