# INIT-001: Governance Infrastructure

## Strategic Context

**Subsystem:** Governance; Governance (cross-cutting)
**Phase:** Phase 1 anchor; extended in Phase 2
**Executive priority:** Phase 1 anchor — tied #1 composite at 9.0 via VS-003 and VS-004, with VS-002 at 4.5 and Phase 2 extensions VS-009 and VS-015 at 2.25.

## Justification Chain

### Market Signal
**Finding:** Governance research shows audit is fragmented and local, direct-mutation dashboards remain the norm, and scoped grants plus policy versioning are absent across the reviewed field.
**Evidence strength:** strong
**Competitor landscape:** Dyno, Carl-bot, Quark, Wick, Guild Manager, Guildbase, TL Guild Manager, and CoGM monetize logs and dashboards, but none expose one causal governance plane spanning authority, policy, notifications, and cross-workflow history.

### Problem Axis
**Axis:** §4 — Audit Trail and Long-term Accountability
**Core difficulty:** Governance only becomes trustworthy when authority, policy, and audit remain reconstructable under live-server change instead of being scattered across local logs and silent dashboard writes.

### Proposal Mechanism
**Design reference:** proposal.md, Governance; Governance Mechanisms; Cross-cutting Concerns
**Schema objects:** AuthorityGrant, PolicyVersion, AuditEntry, NotificationRule, event-projected read models
**Operational workflows:** policy preview-confirm, authority grant/revoke and enforcement, audit chain query, causally grouped notifications, cross-subsystem operational views

### Executive Priority
**Pain severity:** 4 — Phase 1 governance slices all land in active-harm or structural-gap territory, with unreconstructable decisions and silent live-config corruption called out explicitly in the executive roadmap.
**Competitive position:** gap — the reviewed field offers logs and dashboards, not scoped authority, causal audit, preview-confirm policy changes, or cross-subsystem governance views.
**Dependency depth:** 0 at entry; later follow-on governance slices depend on the Phase 1 substrate they extend.
**Operational risk of delay:** active-harm — without this initiative, decisions remain unreconstructable, policy edits stay unsafe on a live server, and volunteer attention is spent compensating for missing governance controls.
**Opportunity cost:** Decisions become unreconstructable after Discord's 45-day audit window, configuration changes silently corrupt in-flight work, and officers still operate through over-broad hierarchy grants instead of scoped authority.

### Engineering Assessment
**Effort:** VS-002 -> L; VS-003 -> M; VS-004 -> M-L (leans M); VS-009 -> M-L (leans M); VS-015 -> M-L (leans M)
**Prototyping:** VS-002 -> conditional; VS-003 -> no; VS-004 -> no; VS-009 -> conditional; VS-015 -> no
**Risk:** High overall
**Risk factors:** Authority mistakes have system-wide blast radius; audit consistency must hold across subsystems; policy activation and stale-preview handling must stay correct under concurrent operator changes; notification fan-out and projection freshness become correctness constraints once multiple workflows emit events.
**Foundation dependencies:** Phase 0 shared schemas and runtime substrate, especially AuditEntry, PolicyVersion, AuthorityGrant, notification events, scheduler, and the Discord/API integration shell.

## Scope

**Value slices:** SLICE-008, SLICE-009, SLICE-010, SLICE-015, SLICE-017
**Dependencies:** none at Phase 1 entry; INIT-006 for the Phase 2 operational-views extension
**Delivers:** Operators can grant and revoke scoped authority and see enforcement failures explained at the mutation boundary; Operators can reconstruct a full causal decision chain months later from immutable audit entries and correlated downstream effects.

## Acceptance Criteria

- [ ] Operators can grant and revoke scoped authority and see enforcement failures explained at the mutation boundary.
- [ ] Operators can reconstruct a full causal decision chain months later from immutable audit entries and correlated downstream effects.
- [ ] Operators can preview and confirm live policy changes without silently mutating in-flight work or accepting stale decisions.
- [ ] Operators can configure notification and read-view behavior from stored governance state rather than code or Discord-local conventions.
