# INIT-006: Permission Management

## Strategic Context

**Subsystem:** Permission Management
**Phase:** Phase 2 anchor; extended in Phase 3
**Executive priority:** Phase 2 mid-pack — VS-008 is tied #4 at composite 2.25; VS-014 extends it in Phase 3 at 1.35.

## Justification Chain

### Market Signal
**Finding:** Permission/security research shows strong demand for role automation, security, and restore depth, but declared intent versus actual reconciliation and temporal permission tracking are absent across the reviewed field.
**Evidence strength:** strong
**Competitor landscape:** Wick, Security Bot, Double Counter, Dyno, Carl-bot, YAGPDB, Xenon, Guild Manager, TL Guild Manager, and CoGM all address parts of the space, but none provide an auditable intent-plus-drift control plane.

### Problem Axis
**Axis:** §7 — Permission Model and State Explosion
**Core difficulty:** Discord lets operators set permissions but not reason about accumulated intent, orphaned state, or when a temporary override has silently become permanent.

### Proposal Mechanism
**Design reference:** proposal.md, Permission Management; Operational Workflows -> Permission Reconciliation
**Schema objects:** PermissionIntent, PermissionDrift
**Operational workflows:** permission intent management, reconciliation run and drift resolution, temporary permission renewal and expiry

### Executive Priority
**Pain severity:** 4 at entry — silent permission drift is active harm, and the temporary-intent extension deepens the same unresolved lifecycle.
**Competitive position:** gap — the reviewed field offers logs, backups, and role automation, not declared intent and drift reconciliation.
**Dependency depth:** 3 at entry; the temporary-permission extension builds on the same intent/drift substrate in Phase 3.
**Operational risk of delay:** active-harm — every urgent exception or manual override keeps widening the gap between intended and actual permission state.
**Opportunity cost:** Permission drift continues accumulating silently, and temporary overrides keep hardening into permanent baseline access.

### Engineering Assessment
**Effort:** VS-008 -> XL; VS-014 -> M-L (leans M)
**Prototyping:** VS-008 -> yes; VS-014 -> no
**Risk:** High overall
**Risk factors:** This is the most novel control-plane model in the core workflow phase; reconciliation correctness, orphaned-state handling, and temporal expiry must all stay idempotent and explainable.
**Foundation dependencies:** Phase 0 permission intent/drift schemas, audit and policy substrate, scheduler/deferred effects, and the Discord/API runtime shell.

## Scope

**Value slices:** SLICE-014, SLICE-020
**Dependencies:** INIT-001
**Delivers:** Operators can declare intended permission state with reasons and see drift between intended and actual Discord state in one control plane; Drift resolution preserves optimistic locking and distinguishes intent-linked from orphaned Discord state.

## Acceptance Criteria

- [ ] Operators can declare intended permission state with reasons and see drift between intended and actual Discord state in one control plane.
- [ ] Drift resolution preserves optimistic locking and distinguishes intent-linked from orphaned Discord state.
- [ ] Discord snapshot and expiry flows communicate through the published reconciliation contracts rather than mutating permission state locally.
- [ ] Temporary permission intents remain explicitly time-bounded instead of silently becoming permanent baseline access.
