# INIT-005: Chapter Operations

## Strategic Context

**Subsystem:** Sub-community Lifecycle
**Phase:** Phase 2 entry; continues through Phases 3 and 4
**Executive priority:** Phase 2 co-anchor — VS-005 is tied #2 at composite 3.0; extended by VS-011 (2.4), VS-017 (0.525), and VS-018 (0.75).

## Justification Chain

### Market Signal
**Finding:** Chapter and alliance research shows strong demand for multi-unit organization and willingness to switch away from spreadsheet-plus-bot sprawl, but lifecycle-grade provisioning, archival, and succession remain weakly served or absent.
**Evidence strength:** moderate
**Competitor landscape:** Guild Manager, GuildForger, Throney, Guilds of WoW, TL Guild Manager, CoGM, Gamer Launch, and Shivtr validate multi-unit demand, but they treat groups as static containers more than full lifecycle objects.

### Problem Axis
**Axis:** §5 — Sub-community Provisioning and Lifecycle
**Core difficulty:** Every subgroup created today increases future governance and cleanup cost, and leadership change is a transfer-of-context problem, not just a role toggle.

### Proposal Mechanism
**Design reference:** proposal.md, Sub-community Lifecycle; Operational Workflows -> Chapter Lifecycle
**Schema objects:** ChapterTemplate, Chapter, ChapterTransition, ChapterRole, RosterEntry, RosterTransition
**Operational workflows:** chapter provision, roster lifecycle, chapter probation/archive, leadership succession and work handoff

### Executive Priority
**Pain severity:** 4 — manual chapter provisioning and roster maintenance are active operational costs today, while archival and succession are lower-frequency but still roadmap-critical lifecycle gaps.
**Competitive position:** table-stakes at entry, gap on mature lifecycle — chapter support is required for multi-unit communities, while governance lifecycle and succession remain differentiated.
**Dependency depth:** 3 at entry; later lifecycle work deepens the same chapter substrate after rosters, governance, and read models exist.
**Operational risk of delay:** active-harm now, future-risk later — manual provisioning and spreadsheet rosters cost time immediately, and succession/archival debt compounds as chapter count grows.
**Opportunity cost:** Operators keep hand-building chapter infrastructure, maintaining rosters in spreadsheets, and losing operational context every time chapter leadership changes.

### Engineering Assessment
**Effort:** VS-005 -> L-XL (leans L); VS-011 -> L; VS-017 -> M-L (leans M); VS-018 -> M-L (leans M)
**Prototyping:** VS-005 -> yes; VS-011 -> conditional; VS-017 -> no; VS-018 -> no
**Risk:** High overall
**Risk factors:** Live Discord resource creation is the highest-fanout roadmap bottleneck; roster sync and archive execution both cross subsystem boundaries; succession spans authority, chapter, roster, and open-work transfer.
**Foundation dependencies:** Phase 0 chapter/roster core schemas, deferred effects, test harnesses, and the Discord/API runtime shell.

## Scope

**Value slices:** SLICE-013, SLICE-018, SLICE-023, SLICE-024
**Dependencies:** INIT-001, INIT-002 at entry; INIT-003 and INIT-004 for the archival and succession follow-on slices
**Delivers:** Operators can create chapters from stored templates and move them through explicit lifecycle states instead of hand-assembling Discord resources; Chapter roster state, role transitions, and chapter governance transitions are durable and auditable rather than spreadsheet or role-presence only.

## Acceptance Criteria

- [ ] Operators can create chapters from stored templates and move them through explicit lifecycle states instead of hand-assembling Discord resources.
- [ ] Chapter roster state, role transitions, and chapter governance transitions are durable and auditable rather than spreadsheet or role-presence only.
- [ ] Archive and succession planning surfaces pending work before execution and preserves causal history during transfer or closure.
- [ ] Discord-visible chapter and roster changes either complete through the published APIs or queue consequential deferred work for explicit recovery.
