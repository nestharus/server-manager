# Engineering Roadmap Revision Report - Cycle 2

Date: 2026-04-16
Scope: `product-strategy/engineering roadmap.md`

This cycle revises the engineering roadmap for the seven requested structural fixes only. No value slice changed phase, no new features were added, and the executive ordering remains intact.

## Applied fixes

### 1. Phase 0 aggregate effort clarified as XL

Phase 0 already carried an `XL` total, but the roadmap now states that the phase itself is an XL program even when individual foundation rows are sized separately and even when some internal work can run in parallel. This removes any ambiguity that a collection of M and L foundation items could be read as an overall M-sized phase.

### 2. Phase 0 now explicitly owns the `mutate_entity()` primitive

The Phase 0 authority/audit foundation now names the canonical `mutate_entity()` write primitive and states that all entity mutations flow through it. This codifies the single-write-path discipline in the foundation instead of leaving the primitive implicitly split across Phase 1 slices.

### 3. VS-003 now explicitly consumes that single-write-path discipline

VS-003 keeps its roadmap effort at `M` because the primitive ownership moved into Phase 0. Its scope now explicitly includes adoption of the Phase 0 `mutate_entity()` path across non-chapter write flows so audit capture cannot be bypassed.

### 4. VS-004 sizing was corrected from M to L

VS-004 now reflects the real coordination cost of preview/confirm plus editor hooks across all six proposal policy families. The risk language was also tightened to call out six-policy editor coordination directly.

### 5. VS-005 was added to the Phase 2 parallelization map

The Phase 2 map now includes the pairings already described in the per-slice text:

- `VS-005 + VS-006`
- `VS-005 + VS-007`
- `VS-005 + VS-009`
- `VS-005 + VS-010`
- `VS-005 + VS-015`

The map also keeps the existing constraint that `VS-005` and `VS-008` should not start as independent streams while permission reconciliation semantics are still settling.

### 6. PermissionIntent ownership was split cleanly between Phase 0 and VS-008

Phase 0 now owns the base `permission_intents` table as part of the permission-intent foundation. VS-008 was revised so it no longer claims ownership of that base schema; it now owns the service layer, reconciliation behavior, `PermissionDrift`, and the operator-facing inspection/drift surfaces on top of the Phase 0 schema.

### 7. Phase 0 now explicitly owns the AuditEntry event-dispatch contract

The old notification/scheduling foundation line now names the shared audit-event dispatch contract, handler registration pattern, and `correlation_id` grouping primitives used by notifications and projections. This gives VS-009, VS-015, and later downstream consumers a common substrate instead of leaving the fan-out contract implicit.

## Supporting adjustments

- Phase 1 effort summary was updated to `3L + M` after the VS-004 resize.
- Total serial effort was updated to `13L + 13M + 1XL`.
- Total best-case parallel effort was updated to `1XL + 6L + 3M`.
- The critical-path text now reflects `VS-004 (L)`.
- Phase 2 dependency wording now uses `permission intent foundation` instead of the older `permission sync engine` label.

## Deferred findings

These findings were intentionally carried forward for implementation-phase research rather than addressed in this roadmap revision:

- `VS-015` CQRS sizing and fallback depth. Rationale: this is a later-slice read-model design question better resolved during slice research and hookpoint analysis.
- `VS-009` notification sizing and causal-grouping depth. Rationale: the roadmap now fixes the dispatch-contract ownership, which is the structural prerequisite; delivery semantics stay for slice-level design.
- `VS-017` and `VS-018` pending-work sizing. Rationale: the roadmap continues to acknowledge the cross-subsystem dependency, but detailed sweep/transfer scope belongs in the Phase 4 slice research.
- `VS-016` cushion and milestone split. Rationale: compliance remains the explicit `XL` critical-path slice, and any internal subdivision should come from implementation-phase proposal work rather than strategic-roadmap churn.

## Result

Cycle 2 closes the requested structural gaps while preserving low drift from the executive roadmap. The remaining MEDIUM findings are now primarily slice-design and implementation-research concerns rather than ownership ambiguities in the strategic engineering roadmap.
