# INIT-007: Activity and Compliance

## Strategic Context

**Subsystem:** Activity and Compliance
**Phase:** Phase 4
**Executive priority:** Phase 4 highest-priority initiative — VS-016 ranks #1 at composite 2.14.

## Justification Chain

### Market Signal
**Finding:** Activity/compliance research shows strong willingness to pay for integrated roster plus activity plus analytics, while a general-purpose evidence-backed compliance engine with dispute-grade audit remains missing.
**Evidence strength:** strong
**Competitor landscape:** Apollo, Suivix, Raid-Helper, Guild Manager, GuildForger, Throney, GuildBro, Guilds of WoW, TL Guild Manager, and CoGM validate the category, but mostly through event attendance or game-specific tooling.

### Problem Axis
**Axis:** §6 — Activity Tracking and Compliance Enforcement
**Core difficulty:** Compliance rules are chapter-specific and evidence-driven, so the system must ingest external proof, evaluate configurable rules, and route proportionate consequences without becoming another spreadsheet workload.

### Proposal Mechanism
**Design reference:** proposal.md, Activity and Compliance; Operational Workflows -> Compliance Evaluation
**Schema objects:** ComplianceRule, EvidenceSubmission, ComplianceEvaluation
**Operational workflows:** rule management, evidence submission and OCR extraction, evaluation review, scheduled compliance enforcement

### Executive Priority
**Pain severity:** 5 — the executive roadmap calls manual threshold checking the primary source of volunteer burnout and treats compliance automation as Phase 4's headline pain reliever.
**Competitive position:** table-stakes at category level, differentiated in mechanism — activity tracking is required, while cross-game evidence-backed compliance with auditable consequences remains under-supplied.
**Dependency depth:** 6 — the initiative sits on the deepest roadmap chain because it relies on governance, chapters, rosters, scheduler, and evidence handling.
**Operational risk of delay:** active-harm — officers keep spending hours on repetitive data entry and spreadsheet cross-referencing instead of using evidence-backed scheduled evaluation.
**Opportunity cost:** Officers continue spending hours on repetitive threshold checks and spreadsheet reconciliation, the roadmap's clearest burnout driver.

### Engineering Assessment
**Effort:** VS-016 -> XL
**Prototyping:** VS-016 -> yes
**Risk:** High overall
**Risk factors:** External OCR/evidence uncertainty, scheduled evaluation correctness, and cross-subsystem consequence routing all converge here.
**Foundation dependencies:** Phase 0 persistence, scheduler, audit, runtime shell, and later chapter/roster substrates from prior phases.

## Scope

**Value slices:** SLICE-022
**Dependencies:** INIT-001, INIT-002, INIT-005
**Delivers:** Operators can create scoped compliance rules and store evidence before extraction completes; OCR extraction and officer correction preserve evidence provenance instead of overwriting raw submissions.

## Acceptance Criteria

- [ ] Operators can create scoped compliance rules and store evidence before extraction completes.
- [ ] OCR extraction and officer correction preserve evidence provenance instead of overwriting raw submissions.
- [ ] Evaluation review and scheduled enforcement apply graduated consequences through durable, auditable workflow state.
- [ ] Compliance runs remain idempotent for the same member, rule, and period and do not silently duplicate consequences.
