# Engineering Roadmap Revision Report

Date: 2026-04-16
Scope: `product-strategy/engineering roadmap.md`

This revision resolves the four MEDIUM findings called out for roadmap revision without changing any of the 18 value slices or their phase assignments.

## Addressed Findings

### 1. Feasibility F-1: VS-004 conflated ETag locking with PolicyVersion pinning

**Change made:** Re-scoped the work split instead of promoting VS-004 to L.

- Phase 0 foundation item `Shared optimistic-locking and policy-versioning primitives` now explicitly owns:
  - durable `policy_versions` table
  - `policy_type`
  - `supersedes_id`
  - pinning lookup primitives for in-flight operations
- VS-004 now focuses on:
  - policy-resolution services
  - preview/confirm APIs
  - policy-specific editors/hooks over the Phase 0 substrate

**Result:** The roadmap no longer treats chapter `ETag` proof as if it already established PolicyVersion chain semantics or pinning behavior.

### 2. Feasibility F-2: VS-007 omitted operator-configurable ticket state machines

**Change made:** Expanded VS-007 effort reasoning, risk factors, and new-work scope to explicitly include per-`TicketCategory` state-machine infrastructure.

- VS-007 now names:
  - operator-configurable per-category state-machine infrastructure
  - runtime transition validation and enforcement
  - per-category state-machine validators

**Result:** The roadmap now reflects that ticket lifecycle work includes dynamic category-local workflow infrastructure, not just static ticket CRUD and Discord flows.

### 3. Integration F-1: Phase 0 Chapter table ownership was unspecified

**Change made:** Clarified that Phase 0 owns the minimal durable `chapters` table.

- Phase 0 persistence item now explicitly includes:
  - `state`
  - `discord_resources`
  - `configuration`
  - `archived_at`
- VS-005 no longer claims ownership of the base durable chapter table.
- VS-005 is now scoped as ownership of:
  - `ChapterTemplate` schema
  - provisioning orchestration
  - approval flow
  - template validation
  - any chapter-lifecycle-extending columns beyond the Phase 0 base table

**Result:** Phase 2 slices that need chapter FK targets can rely on a Phase 0 durable `chapters` table, preserving the roadmap's Phase 2 parallelism claim.

### 4. Integration F-2: AuthorityGrant ownership split was ambiguous

**Change made:** Clarified that Phase 0 owns the durable `authority_grants` table and VS-002 owns the service/enforcement layer.

- Phase 0 authority/audit kernel now explicitly includes the durable `authority_grants` table with `predecessor_grant_id`.
- VS-002 no longer claims `AuthorityGrant` persistence ownership.
- VS-002 now focuses on:
  - scope-check services
  - override handling
  - middleware/dependencies
  - mutation-path integration over the Phase 0 table

**Result:** The roadmap now has a clean ownership boundary: Phase 0 lands the schema, VS-002 lands the enforcement path, and future VS-018 work can populate `predecessor_grant_id` without reopening table ownership.

## Preservation Checks

- No value slices were added, removed, or moved.
- No phase assignments changed.
- No new scope was introduced beyond the approved proposal and the requested ambiguity fixes.
- The executive ordering and prior LOW drift assessment remain intact.
