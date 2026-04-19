# Skeleton: Executive Roadmap

## Heading Outline
- Executive Roadmap
  - Executive Summary
  - Strategic Narrative
  - Phase Structure
    - Phase 0: Foundations (engineering-defined)
    - Phase 1: Governance Foundation
    - Phase 2: Core Operational Workflows
    - Phase 3: Operational Depth
    - Phase 4: Operational Maturity
  - Competitive Positioning
  - Risk Register
  - Approval Package
  - Opportunity Cost Summary
  - Deferred Subsystems
  - Appendix
    - A. Scoring Methodology
    - B. Decomposition Targets
    - C. Value Slice Inventory
      - VS-001: Member onboarding with initial trust assessment
      - VS-002: Scoped authority with enforcement
      - VS-003: Audit trail with causal correlation
      - VS-004: Policy versioning with configuration safety
      - VS-005: Chapter provisioning from templates
      - VS-006: Structured application intake with reviewer ownership
      - VS-007: Ticket creation and case lifecycle
      - VS-008: Permission intent and drift detection
      - VS-009: Configurable operator notifications
      - VS-010: Advanced trust management
      - VS-011: Roster management with role lifecycle
      - VS-012: Application interview and waitlist handling
      - VS-013: SLA enforcement for tickets
      - VS-014: Temporary permission management
      - VS-015: Cross-subsystem operational views
      - VS-016: Compliance rule evaluation with evidence
      - VS-017: Chapter governance lifecycle
      - VS-018: Leadership succession with context transfer
    - D. Per-Slice Scoring Detail
      - Phase 1
        - VS-001: Member onboarding with initial trust assessment
        - VS-003: Audit trail with causal correlation
        - VS-004: Policy versioning with configuration safety
        - VS-002: Scoped authority with enforcement
      - Phase 2
        - VS-007: Ticket creation and case lifecycle
        - VS-006: Structured application intake with reviewer ownership
        - VS-005: Chapter provisioning from templates
        - VS-008: Permission intent and drift detection
        - VS-009: Configurable operator notifications
        - VS-015: Cross-subsystem operational views
        - VS-010: Advanced trust management
      - Phase 3
        - VS-011: Roster management with role lifecycle
        - VS-013: SLA enforcement for tickets
        - VS-014: Temporary permission management
        - VS-012: Application interview and waitlist handling
      - Phase 4
        - VS-016: Compliance rule evaluation with evidence
        - VS-018: Leadership succession with context transfer
        - VS-017: Chapter governance lifecycle

## First Sentence of Each Paragraph
1.1.1 **Strategic outcome.** Deliver a Discord-native guild management platform that treats identity/trust, intake, case management, sub-community lifecycle, activity/compliance, permissions, and governance as one unified operational system with causal auditability across subsystems.
1.1.2 **Why this sequence now.**
1.1.3 **Vendors are departing while market gaps remain unfilled.** Gather is deprecated and Guilded is shut down.
1.1.4 **Operational harm is active, not hypothetical.** Seven of the fourteen problem axes describe active-harm patterns that worsen as communities delay, including audit gaps past Discord's 45-day cap (`problem.md` §4) and permission drift compounding from crisis exceptions (`problem.md` §7).
1.1.5 **Dependency order is structurally fixed.** The scoring analysis (see Appendix) finds that dependency-driven phasing is sound and ordering is stable under alternative market readings (`plans/risk/executive-dependency-trap.md` F-4, F-5, F-7; `plans/risk/executive-market-misread.md` F-8).
1.1.6 **Approval ask.** Commit contributor effort and resource attention to the four-phase sequence as scoped: Phase 0 (engineering foundations), Phase 1 (governance foundation), Phase 2 (core operational workflows), Phase 3 (operational depth), Phase 4 (operational maturity).
1.1.7 **Value realization by phase.**
1.1.8 **After Phase 1:** Every member carries a computed trust level that reviewers can inspect, and authority grants operate within scoped boundaries with automatic enforcement.
1.1.9 **After Phase 2:** Operators run structured applications with reviewer ownership and manage tickets through category-specific state machines.
1.1.10 **After Phase 3:** Officers manage rosters and enforce SLAs with graduated consequences.
1.1.11 **After Phase 4:** Chapters have full governance lifecycle (probation, archival) with leadership succession and evidence-based compliance evaluation.
1.1.12 **Top risks and management posture.**
1.1.13 **Dependency bottleneck at chapter provisioning (VS-005).** A single Phase 1 slice transitively blocks roster provisioning, with compliance and succession cascading from there (`plans/risk/executive-dependency-trap.md` F-1).
1.1.14 **Phase 0 scope ambiguity.** Phase 0 is a one-sentence engineering placeholder; Phase 1 implicitly depends on foundations (`plans/risk/executive-completeness.md` F-2).
1.1.15 **Market misread risk (competitor enters intent model).** All `gap` classifications assume no competitor has shipped a declared-intent-vs-actual control plane with policy versioning, or a cross-subsystem causal audit (`plans/risk/executive-market-misread.md` What LOW requires #2).
1.1.16 **Scope creep into non-goals.** Pressure to add bot-framework breadth or moderation-first features would dilute differentiation, with AI-driven decisions carrying the same risk (`proposal.md` Non-goals).
1.1.17 **Adoption friction from absent migration tooling.** Permission migration tooling is deferred; adopting communities inherit all existing Discord permissions as "unintended" drift (see Deferred Subsystems).
1.2.1 The four phases are a single sequence, not four independent tracks.
1.2.2 **Phase 1. Buy defensibility first.** Before operator workflows, the system needs trust profiles, scoped authority, immutable causal audit, and preview-confirm policy changes.
1.2.3 **Phase 2. Reach parity on the operational workflows competitors already monetize.** With the governance substrate in place, Phase 2 builds the workflows that eight application tools and nine ticket tools monetize today, along with eight multi-unit suites competing on chapter management (`market research.md` §2, §3, §4).
1.2.4 **Phase 3. Close the willingness-to-pay package.** Roster management, SLA enforcement, temporary permissions, and application interview/waitlist handling complete the integrated roster-and-activity package six market research sources identify as the integration operators most readily pay for, analytics included (`market research.md` §5).
1.2.5 **Phase 4. Close the operational lifecycle.** Compliance evaluation against submitted evidence is the anchoring capability.
1.2.6 **What this roadmap deliberately does not pursue.** The proposal's Non-goals hold throughout the roadmap (`proposal.md` Non-goals):
1.2.7 **Not a general-purpose bot framework.** No scripting or arbitrary-automation surface.
1.2.8 **Not moderation-first.** Moderation is one ticket category among many, not the organizing center.
1.2.9 **Not feature-parity with existing bots.** Leveling, reaction-role UX depth, DKP/loot systems, raid composition tools, and event-scheduling depth belong to specialized products (`market research.md` §5, §6 Differentiation opportunities).
1.2.10 **No AI-driven operational decisions.** AI is used only for OCR and data extraction.
1.2.11 **No real-time game integration.** Game APIs are ingested where available; real-time synchronization is not promised.
1.2.12 **No full-server cloning or backup/restore.** Xenon-style cloning is out of scope (`market research.md` §6 Differentiation opportunities).
1.2.13 **No public community-surface features.** No website/forums/event pages of the kind Gamer Launch, Shivtr, and Guild Manager offer (`market research.md` §4 Differentiation opportunities).
1.3.1.1 **Business outcome.** A reliable and portable runtime that isolates subsystems, letting every downstream value slice ship without each re-inventing platform infrastructure.
1.3.1.2 **Success condition.** Engineering has defined acceptance criteria for the four cross-cutting concerns (Cross-workflow State Coherence, Platform Boundary, Graceful Degradation, Data Portability) and the shared schemas (AuditEntry, PolicyVersion, PermissionIntent, AuthorityGrant) are in place before Phase 1 slices begin (`plans/risk/executive-dependency-trap.md` F-3; `plans/risk/executive-completeness.md` F-2).
1.3.1.3 **Value realization window.** Prerequisite.
1.3.1.4 **Confidence.** Committed (engineering-scoped).
1.3.1.5 **Investment ask.** Contributor time on foundational infrastructure; no additional external dependencies beyond Discord API access.
1.3.1.6 **Phase-specific risk.** Phase 0 scope is currently a one-sentence placeholder.
1.3.1.7 The engineering layer determines what technical foundations are needed before value slices can begin.
1.3.1.8 Database schema and migration framework
1.3.1.9 Discord gateway connection and platform boundary layer
1.3.1.10 Subsystem isolation and graceful degradation mechanics
1.3.1.11 Deferred effect queue infrastructure
1.3.1.12 Base API framework
1.3.1.13 This phase also encompasses data portability design (documented, exportable formats for all schema objects) and platform assumption verification at startup.
1.3.2.1 **Business outcome.** A defensible governance substrate no reviewed competitor offers: persistent trust profiles, scoped authority enforcement, causal audit across subsystems, and preview-confirm policy versioning on a live server.
1.3.2.2 **User/community pain relieved.** Officers no longer rely on memory and Discord role presence to decide trust (`problem.md` §1).
1.3.2.3 **Success condition (qualitative).** An operator can:
1.3.2.4 View any member's trust level with the signals that produced it
1.3.2.5 Grant or revoke authority scoped to a specific area with automatic enforcement
1.3.2.6 Reconstruct any past decision months later from immutable audit entries with causal chain
1.3.2.7 Change policy on a live server with preview-confirm and optimistic concurrency protection
1.3.2.8 **Value realization window.** Foundational.
1.3.2.9 **Confidence.** Committed.
1.3.2.10 **Investment ask.** Contributor time.
1.3.2.11 **Phase-specific risks.**
1.3.2.12 **Chapter-provisioning slot (VS-005) is the highest-fanout bottleneck** (note: VS-005 is Phase 1-eligible by dependency depth but sequenced with other Phase 1 governance slices; delay here cascades to three later slices).
1.3.2.13 **Shared-schema coordination between VS-004 (policy versioning) and VS-005 (chapter provisioning)**.
1.3.2.14 **Capability gained:** The system registers members with computed trust levels and enforces scoped authority boundaries.
1.3.2.15 **Workflows enabled:**
1.3.2.16 Member onboarding with automatic trust computation from platform signals
1.3.2.17 Authority grant and revoke with scope enforcement
1.3.2.18 Audit trail queries across any operational domain
1.3.2.19 Policy preview-confirm with optimistic concurrency protection
1.3.2.20 **Not yet built:**
1.3.2.21 Operational workflows (applications, tickets, chapters)
1.3.2.22 Discord resource management
1.3.2.23 Compliance evaluation
1.3.2.24 Notifications
1.3.2.25 Roster management
1.3.2.26 Permission management
1.3.2.27 **Prerequisites:** Phase 0
1.3.2.28 **Slices in this phase:** VS-001 (member onboarding with initial trust), VS-002 (scoped authority with enforcement), VS-003 (audit trail with causal correlation), VS-004 (policy versioning with configuration safety).
1.3.3.1 **Business outcome.** Operational parity with the eight application tools and nine ticket tools that define today's reviewed competition.
1.3.3.2 **User/community pain relieved.** Officers stop duplicating review effort on the same application (`problem.md` §2, §9), and harassment reports and appeals leave DMs for durable state with ownership tracking (`problem.md` §3).
1.3.3.3 **Success condition (qualitative).** Operators can:
1.3.3.4 Run a complete application review from submission to decision with exclusive reviewer ownership and mandatory reasons
1.3.3.5 Open tickets with category-specific state machines and privacy controls
1.3.3.6 Provision chapters from templates through an approval gate
1.3.3.7 Declare intended permissions and see where Discord reality has drifted
1.3.3.8 Configure notifications with causal grouping to prevent cascade fatigue
1.3.3.9 Query cross-subsystem operational history
1.3.3.10 **Value realization window.** Operational value visible to communities considering a switch.
1.3.3.11 **Confidence.** Likely.
1.3.3.12 **Investment ask.** Contributor time.
1.3.3.13 **Phase-specific risks.**
1.3.3.14 **Competitive-window erosion.** If the operational-workflow markets (tickets, applications, permissions) consolidate around a new entrant during Phase 1, Phase 2 starts in a more contested market.
1.3.3.15 **Adoption onboarding cost.** Permission migration tooling is deferred; communities adopting in Phase 2 see all existing Discord permissions as "unintended" drift until manually classified.
1.3.3.16 **Capability gained:**
1.3.3.17 Officers process structured applications with single-reviewer ownership
1.3.3.18 Each ticket category has its own state machine with privacy controls
1.3.3.19 New chapters are provisioned from templates through approval gates
1.3.3.20 Operators declare intended permission state and detect drift
1.3.3.21 Officers receive configurable notifications
1.3.3.22 Trust computation is customizable with officer-managed signals
1.3.3.23 Cross-subsystem history is queryable through materialized views
1.3.3.24 **Workflows enabled:**
1.3.3.25 Application intake (submit → queue → claim → review → decide with mandatory reasons)
1.3.3.26 Ticket lifecycle (create → triage → assign → resolve → close with category-specific states)
1.3.3.27 Chapter provisioning (propose → approve → provision → activate)
1.3.3.28 Permission reconciliation (declare intent → detect drift → resolve)
1.3.3.29 Trust signal recording by officers with scoped computation configuration
1.3.3.30 Notification configuration with causal grouping
1.3.3.31 **Not yet built:**
1.3.3.32 Direct roster management beyond application-created entries (officer direct adds, status changes, role reassignment)
1.3.3.33 Compliance evaluation
1.3.3.34 SLA enforcement for tickets
1.3.3.35 Application interview or waitlist handling
1.3.3.36 Temporary permission expiration
1.3.3.37 Chapter probation or archival
1.3.3.38 Leadership succession
1.3.3.39 **Prerequisites:** Phase 1
1.3.3.40 **Slices in this phase:** VS-005 (chapter provisioning from templates), VS-006 (structured application intake with reviewer ownership), VS-007 (ticket creation and case lifecycle), VS-008 (permission intent and drift detection), VS-009 (configurable operator notifications), VS-010 (advanced trust management), VS-015 (cross-subsystem operational views).
1.3.4.1 **Business outcome.** The integrated roster-and-activity package with analytics that six sources identify as the integration operators most readily pay for (`market research.md` §5).
1.3.4.2 **User/community pain relieved.** Chapter membership records stop living in spreadsheets with no lifecycle tracking (`problem.md` §5); cases stop silently aging with no time-based accountability (`problem.md` §3); temporary permission overrides stop silently becoming permanent baselines (`problem.md` §7); interviews stop happening in untracked DMs and waitlisted applicants stop being managed informally (`problem.md` §2).
1.3.4.3 **Success condition (qualitative).** Officers manage full roster lifecycles, adding and transitioning members through status changes with role reassignment requiring reasons.
1.3.4.4 **Value realization window.** Completes the willingness-to-pay package.
1.3.4.5 **Confidence.** Likely for VS-011 (roster) and VS-013 (SLA) given strong competitive pressure and direct dependency chains.
1.3.4.6 **Investment ask.** Contributor time.
1.3.4.7 **Phase-specific risks.**
1.3.4.8 **Dependency-chain length.** VS-013 (SLA) has a transitive dependency depth of 5; a delay in any upstream slice cascades.
1.3.4.9 **Pain severity reassessment.** VS-012 (interview/waitlist) carries the lowest composite in this phase; communities have workable DM-based alternatives.
1.3.4.10 **Capability gained:**
1.3.4.11 Full roster lifecycle with officer direct management
1.3.4.12 Application process supports interviews and waitlists
1.3.4.13 Tickets enforce time-based SLA with graduated consequences
1.3.4.14 Temporary permissions auto-expire
1.3.4.15 **Workflows enabled:**
1.3.4.16 Roster management (officer direct adds, status transitions, role reassignment with reasons)
1.3.4.17 SLA monitoring with proportional escalation (notify → flag → escalate)
1.3.4.18 Interview thread provisioning and waitlist reactivation
1.3.4.19 Temporary permission intent with expiration tracking
1.3.4.20 **Not yet built:**
1.3.4.21 Compliance evaluation
1.3.4.22 Chapter governance lifecycle (probation, archival)
1.3.4.23 Leadership succession with context transfer
1.3.4.24 **Prerequisites:** Phase 2
1.3.4.25 **Slices in this phase:** VS-011 (roster management with role lifecycle), VS-012 (application interview and waitlist handling), VS-013 (SLA enforcement for tickets), VS-014 (temporary permission management).
1.3.5.1 **Business outcome.** Evidence-based compliance evaluation is the anchoring capability.
1.3.5.2 **User/community pain relieved.** Officers stop spending hours daily on repetitive enforcement work explicitly identified as the primary source of volunteer burnout: manual data entry and spreadsheet cross-referencing for threshold checks (`problem.md` §6).
1.3.5.3 **Success condition (qualitative).** At Phase 4 completion:
1.3.5.4 Compliance evaluation runs on schedule with OCR-parsed evidence and graduated consequences
1.3.5.5 Probation and archival become formal chapter states with defined transitions
1.3.5.6 Leadership succession preserves pending work and authority with predecessor-linked grants
1.3.5.7 **Value realization window.** Officers move off manual compliance work as the headline outcome.
1.3.5.8 **Confidence.** Aspirational.
1.3.5.9 **Investment ask.** Contributor time.
1.3.5.10 **Phase-specific risks.**
1.3.5.11 **Completeness risk for compliance scope.** Seasonal rules (time-windowed rule activation) are deferred; cross-game evidence correlation and evidence analytics are deferred, along with bulk evidence import.
1.3.5.12 **Succession pain-severity reassessment.** VS-018 (succession) pain severity is 3 with moderate evidence; if communities increase leadership turnover rates or explicit operator demand surfaces, re-evaluate priority.
1.3.5.13 **Capability gained:**
1.3.5.14 Compliance evaluation runs on schedule with OCR-supported evidence processing and graduated consequences
1.3.5.15 Chapters have full governance lifecycle with probation and archival
1.3.5.16 Leadership transitions preserve operational context through succession chains
1.3.5.17 **Workflows enabled:**
1.3.5.18 Scheduled compliance evaluation (collect evidence → apply rules → generate results → trigger consequences)
1.3.5.19 Evidence submission with OCR extraction and confidence scoring
1.3.5.20 Chapter probation entry and reinstatement
1.3.5.21 Chapter archival with member notification and preservation of pending work and state
1.3.5.22 Leadership succession with authority transfer and pending work handoff
1.3.5.23 **Prerequisites:** Phase 3
1.3.5.24 **Slices in this phase:** VS-016 (compliance rule evaluation with evidence), VS-017 (chapter governance lifecycle), VS-018 (leadership succession with context transfer).
1.4.1 **Alternatives communities use today.** The reviewed market spans 50 products across six categories (`market research.md` Methodology):
1.4.2 **General bots** (Dyno, Carl-bot, YAGPDB, MEE6, Arcane, Quark): moderation, roles, leveling, logs.
1.4.3 **Intake tools** (Gather, Appy, Application Bot, ApplicationForms, Google Forms stacks, Typeform stacks): form submission and lightweight review.
1.4.4 **Ticketing** (Ticket Tool, Helper.gg, SCNX, Discord Tickets, Modmail, ticket.pm, Mava, Oapps, DiscoDesk): ticket creation, claims, transcripts.
1.4.5 **Activity/roster** (Apollo, Suivix, Raid-Helper, Guild Manager, GuildForger, Throney, GuildBro, Guilds of WoW, TL Guild Manager, CoGM): attendance, event tracking, game-specific operations.
1.4.6 **Permission/security** (Wick, Security Bot, Double Counter, Xenon): verification, anti-nuke, backup/restore.
1.4.7 **Broader suites** (Guildbase, TL Guild Manager, CoGM, Gamer Launch, Shivtr, Wick Bot, CommunityOne).
1.4.8 **Where the current market is weak.** The market research identifies four structural gaps consistent across every subsystem report:
1.4.9 **No shared causal chain.** Audit is "fragmented and local"; the market "repeatedly fails to offer a single decision chain spanning intake, cases, chapters, permissions, and compliance" (`market research.md` Cross-cutting Findings).
1.4.10 **No declared-intent control plane.** "Direct-mutation dashboards remain the norm"; no reviewed product offers policy versioning, preview-confirm edits, compare-and-swap, or permission-intent reconciliation (`market research.md` §6, §7).
1.4.11 **No lifecycle-grade chapter administration.** Multi-guild products treat groups as static containers; provisioning and archival are missing even in premium suites, with succession equally absent (`market research.md` §4).
1.4.12 **No general-purpose compliance engine.** Outside game-specific Throney examples, no product evaluates configurable rules against structured evidence with consequence workflows (`market research.md` §5).
1.4.13 **Distinctive advantage this sequence creates.** The Phase 1 governance substrate (trust, authority, audit, policy versioning) is the floor no competitor offers.
1.4.14 **Why timing matters now.**
1.4.15 **Vendor instability is actively pushing communities to look.** Gather is deprecated and Guilded is defunct.
1.4.16 **Premium gating concentrates around ownership and retention.** Claiming, transcripts, log history, exports, alliance support, and backups are frequently paid features, reinforcing vendor lock-in and migration pain (`market research.md` Cross-cutting Findings).
1.4.17 **Market gaps are documented, not speculative.** Every `gap` classification in the scoring traces to an explicit "Gap Analysis" section in the source research (`plans/risk/executive-market-misread.md` F-3).
1.5.1 Top risks carried through the three executive risk assessments (`plans/risk/executive-market-misread.md`, `plans/risk/executive-dependency-trap.md`, `plans/risk/executive-completeness.md`).
1.6.1 **What leadership is being asked to approve.**
1.6.2 **The phase sequence.** The four-phase ordering (Phase 0 foundations → Phase 1 governance foundation → Phase 2 core operational workflows → Phase 3 operational depth → Phase 4 operational maturity) as structurally required by dependency analysis (`plans/risk/executive-dependency-trap.md` F-4, F-5, F-7) and stable under alternative market readings (`plans/risk/executive-market-misread.md` F-8).
1.6.3 **The 18 value slices in their current phase assignments.** Slice composition and phase placement are not to be changed without re-running the dependency analysis and market misread risk gate.
1.6.4 **The scope exclusions.** The Non-goals (general-purpose bot framework, moderation-first design, feature parity, AI-driven operational decisions, real-time game integration) hold throughout the roadmap.
1.6.5 **The risk posture.** All three executive risk assessments rate LOW; the Risk Register above surfaces the seven specific findings with trigger indicators.
1.6.6 **What remains flexible.**
1.6.7 **Engineering decomposition of Phase 0.** The executive roadmap intentionally leaves Phase 0 scope to engineering; acceptance criteria are engineering-defined.
1.6.8 **Intra-phase ordering.** Within Phase 1 (up to four parallel slices), Phase 2 (up to four), and Phase 3 (up to two), slice ordering is not load-bearing (`plans/risk/executive-dependency-trap.md` F-4).
1.6.9 **Specific feature variants inside slice scope.** Anti-scope boundaries are explicit for each slice; within those boundaries, feature-level choices are delivery-team decisions.
1.6.10 **Exact timing.** No calendar dates are committed.
1.6.11 **Review cadence.**
1.6.12 **At each phase boundary:** re-run the market misread risk gate using fresh market data and confirm no new competitor has reclassified a `gap` as `parity` or `table-stakes`.
1.6.13 **If market evidence changes materially:** re-evaluate affected slice pain severity and competitive classification (triggered by Risk #3 in the Risk Register).
1.6.14 **If proposal Non-goals are pressured:** treat as an explicit executive escalation (Risk #4).
1.6.15 **If VS-005 delivery risk materializes:** re-evaluate downstream cascade and communication to affected operator segments (Risk #1).
1.8.1 No proposal subsystem is fully deferred.
1.8.2 **Data portability export tooling.** The proposal specifies that export paths exist for all data categories in documented formats.
1.8.3 **Emergency override workflow.** VS-002 delivers scope enforcement.
1.8.4 **Permission migration tooling.** VS-008 delivers intent-vs-actual drift detection, but a community adopting the system inherits a full history of unmanaged permission decisions: all existing Discord permissions initially appear as "unintended" drift.
1.8.5 **Seasonal compliance rules.** VS-016 delivers compliance evaluation but defers the season field (time-windowed rule activation).
1.8.6 **Graceful degradation mechanics.** The proposal specifies four graceful-degradation mechanics as engineering-layer responsibilities:
1.8.7 Deferred execution classification
1.8.8 Consequence-graduated retry
1.8.9 Precondition validation on recovery
1.8.10 Audit-blocks-consequential-actions policy
1.8.11 These are structurally required for a production system but do not deliver operator-visible value independently.
1.9.1.1 **Pain severity (1–5):** How much does this address a problem operators vocally care about?
1.9.1.2 **Competitive position:** gap (no competitor offers this; weight 1.5) / parity (1–2 competitors offer similar but limited; weight 1.0) / table-stakes (3+ competitors offer this, must-have; weight 2.0).
1.9.1.3 **Dependency depth:** Count of all upstream value slices (transitive) that must be complete before this slice can function.
1.9.1.4 **Operational risk of delay:** active-harm (problem worsening while unbuilt; weight 1.5) / static-gap (problem exists but stable; weight 1.0) / future-risk (problem emerges later; weight 0.7).
1.9.1.5 **Composite formula:** `pain_severity × competitive_weight × delay_risk_weight / (dependency_depth + 1)`
1.9.2.1 **Seven subsystems:** Identity and Trust, Intake and Adjudication, Case Management, Sub-community Lifecycle, Activity and Compliance, Permission Management, Governance.
1.9.2.2 **Four cross-cutting concerns:** Cross-workflow State Coherence, Platform Boundary, Graceful Degradation, Data Portability.
1.9.3.1.1 **Subsystem(s):** Identity and Trust **Capability delivered:** Operators see every new member with a computed, inspectable trust level derived from platform signals.
1.9.3.1.2 Officer-managed signals (identity_verification, officer_endorsement)
1.9.3.1.3 Per-chapter trust profiles
1.9.3.1.4 Trust computation customization
1.9.3.1.5 Signal decay management
1.9.3.2.1 **Subsystem(s):** Governance **Capability delivered:** Officers receive explicit authority grants for defined scopes; the system denies out-of-scope operations with clear explanations.
1.9.3.2.2 Succession chain (predecessor_grant_id)
1.9.3.2.3 Emergency override workflow
1.9.3.2.4 Automatic authority from ChapterRole assignment
1.9.3.3.1 **Subsystem(s):** Governance (cross-cutting) **Capability delivered:** Every operational decision is recorded immutably with actor, context, policy version, and causal chain identifiers.
1.9.3.3.2 CQRS read model materialization
1.9.3.3.3 Retention management interface
1.9.3.3.4 Export tooling
1.9.3.3.5 Operator dashboard for audit queries
1.9.3.4.1 **Subsystem(s):** Governance **Capability delivered:** Configuration changes are versioned with preview-confirm workflow and optimistic concurrency; in-flight operations are protected from mid-stream rule changes.
1.9.3.4.2 Rollback automation
1.9.3.4.3 Bulk policy migration
1.9.3.4.4 Cross-scope policy comparison
1.9.3.4.5 Policy diff visualization
1.9.3.5.1 **Subsystem(s):** Sub-community Lifecycle **Capability delivered:** Operators create new chapters from configurable templates; Discord resources (channels and roles with their categories) are provisioned through an approval gate.
1.9.3.5.2 Probation or archival states
1.9.3.5.3 Succession
1.9.3.5.4 Chapter-scoped compliance rules
1.9.3.5.5 Roster management
1.9.3.5.6 Chapter configuration editing
1.9.3.6.1 **Subsystem(s):** Intake and Adjudication; Identity and Trust (trust context in review) **Capability delivered:** Members submit structured applications, and a single reviewer claims and evaluates each one with trust context and mandatory decision reasons.
1.9.3.6.2 Interview flow
1.9.3.6.3 Waitlist
1.9.3.6.4 Form branching logic
1.9.3.6.5 Chapter application support depends on chapters existing (VS-005 or equivalent)
1.9.3.7.1 **Subsystem(s):** Case Management **Capability delivered:** Officers create and manage tickets with category-specific state machines and privacy controls; assignment tracks ownership and resolution requires mandatory reasons.
1.9.3.7.2 SLA enforcement
1.9.3.7.3 Cross-ticket linking (related_ticket_ids)
1.9.3.7.4 Cross-ticket pattern detection
1.9.3.8.1 **Subsystem(s):** Permission Management **Capability delivered:** Operators declare intended permission state with reasons; the system detects when Discord permissions diverge and surfaces drift for explicit resolution.
1.9.3.8.2 Temporary permission expiration
1.9.3.8.3 Migration tooling for existing unmanaged Discord permissions
1.9.3.8.4 Automated reconciliation scheduling
1.9.3.9.1 **Subsystem(s):** Governance **Capability delivered:** Operators configure notification triggers, scoped recipients, delivery channels, actionable vs. informational distinction, and causal grouping to prevent notification fatigue.
1.9.3.9.2 Notification analytics
1.9.3.9.3 Digest scheduling
1.9.3.9.4 Notification muting or snooze
1.9.3.9.5 Notification templates beyond structured content
1.9.3.10.1 **Subsystem(s):** Identity and Trust **Capability delivered:** Officers record trust signals (identity verification and endorsements, plus compliance history).
1.9.3.10.2 Automated cross-chapter trust recognition
1.9.3.10.3 Trust signal expiration management UI
1.9.3.10.4 Trust analytics or trending
1.9.3.11.1 **Subsystem(s):** Sub-community Lifecycle **Capability delivered:** Officers manage chapter rosters.
1.9.3.11.2 Compliance-triggered status changes
1.9.3.11.3 Succession workflow
1.9.3.11.4 Automated roster cleanup
1.9.3.11.5 Cross-chapter roster comparison
1.9.3.12.1 **Subsystem(s):** Intake and Adjudication **Capability delivered:** Reviewers request interviews with system-provisioned private threads; applications can be waitlisted and reactivated by reviewers.
1.9.3.12.2 Automated waitlist prioritization
1.9.3.12.3 Bulk waitlist management
1.9.3.12.4 Interview scheduling
1.9.3.13.1 **Subsystem(s):** Case Management **Capability delivered:** Per-category SLA rules with graduated time-based thresholds trigger proportional consequences:
1.9.3.13.2 Notify owner
1.9.3.13.3 Notify scope
1.9.3.13.4 Flag for review
1.9.3.13.5 Auto-escalate
1.9.3.13.6 **Schema objects:** TicketCategory (sla_rules extension), AuditEntry (action_type: sla_triggered) **State transitions:** SLA-triggered transitions within category state machines (e.g., assigned → escalated) **Anti-scope:**
1.9.3.13.7 SLA analytics dashboard
1.9.3.13.8 SLA template library
1.9.3.13.9 Custom SLA consequence actions
1.9.3.14.1 **Subsystem(s):** Permission Management **Capability delivered:** Operators create time-limited permission intents; expired overrides automatically surface as drift, preventing "temporary becomes permanent."
1.9.3.14.2 Automated permission rotation
1.9.3.14.3 Bulk temporary grant management
1.9.3.14.4 Temporary permission renewal workflow
1.9.3.15.1 **Subsystem(s):** Governance (cross-cutting) **Capability delivered:** Operators query operational history across all subsystems through materialized read models, including causal chain views and scope-filtered projections.
1.9.3.15.2 Custom query builder
1.9.3.15.3 Export from read model
1.9.3.15.4 Analytics or aggregation beyond operational history
1.9.3.15.5 Real-time streaming
1.9.3.16.1 **Subsystem(s):** Activity and Compliance **Capability delivered:** Chapter-scoped compliance rules evaluate members on schedule against submitted evidence (OCR-parsed screenshots and structured feeds from game APIs or manual reports); violations trigger graduated consequences.
1.9.3.16.2 Seasonal rules (season field deferred)
1.9.3.16.3 Cross-game evidence correlation
1.9.3.16.4 Evidence analytics
1.9.3.16.5 Bulk evidence import
1.9.3.17.1 **Subsystem(s):** Sub-community Lifecycle **Capability delivered:** Chapters can enter probation (governance concerns) and proceed through archival with member notification and pending work resolution, preserving state throughout.
1.9.3.17.2 Automated inactivity detection triggering probation
1.9.3.17.3 Chapter health scoring
1.9.3.17.4 Cross-chapter governance dashboard
1.9.3.18.1 **Subsystem(s):** Sub-community Lifecycle; Governance **Capability delivered:** When a succession-triggering role holder departs, pending decisions and open work are identified, and authority transfers to the successor with a predecessor link.
1.9.3.18.2 Automated successor selection
1.9.3.18.3 Succession scheduling or term limits
1.9.3.18.4 Cross-chapter succession coordination
1.9.4.1.1.1 **Pain severity:** 4.
1.9.4.1.1.2 **Competitive position:** gap.
1.9.4.1.1.3 **Dependency depth:** 0.
1.9.4.1.1.4 **Operational risk of delay:** active-harm.
1.9.4.1.1.5 **Composite priority:** 9.0
1.9.4.1.1.6 **Opportunity cost:** By not building this yet, officers continue making trust decisions about members based on personal memory and Discord role presence, which breaks across chapter boundaries and on staff turnover (Problem §1).
1.9.4.1.2.1 **Pain severity:** 4.
1.9.4.1.2.2 **Competitive position:** gap.
1.9.4.1.2.3 **Dependency depth:** 0.
1.9.4.1.2.4 **Operational risk of delay:** active-harm.
1.9.4.1.2.5 **Composite priority:** 9.0
1.9.4.1.2.6 **Opportunity cost:** By not building this yet, decisions become unreconstructable after Discord's 45-day audit log expires, and officers cannot prove what happened or what policy governed a disputed decision (Problem §4).
1.9.4.1.3.1 **Pain severity:** 4.
1.9.4.1.3.2 **Competitive position:** gap.
1.9.4.1.3.3 **Dependency depth:** 0.
1.9.4.1.3.4 **Operational risk of delay:** active-harm.
1.9.4.1.3.5 **Composite priority:** 9.0
1.9.4.1.3.6 **Opportunity cost:** By not building this yet, configuration changes can silently corrupt in-flight operations.
1.9.4.1.4.1 **Pain severity:** 3.
1.9.4.1.4.2 **Competitive position:** gap.
1.9.4.1.4.3 **Dependency depth:** 0.
1.9.4.1.4.4 **Operational risk of delay:** static-gap.
1.9.4.1.4.5 **Composite priority:** 4.5
1.9.4.1.4.6 **Opportunity cost:** By not building this yet, communities rely on Discord's ranked hierarchy model, pushing officers toward either over-centralization or over-granting because the platform cannot express "only within your chapter" (Problem §10).
1.9.4.2.1.1 **Pain severity:** 5.
1.9.4.2.1.2 **Competitive position:** table-stakes.
1.9.4.2.1.3 **Dependency depth:** 3.
1.9.4.2.1.4 **Operational risk of delay:** active-harm.
1.9.4.2.1.5 **Composite priority:** 3.75
1.9.4.2.1.6 **Opportunity cost:** By not building this yet, sensitive case workflows live in ephemeral DM threads without durable state or ownership tracking (Problem §3).
1.9.4.2.2.1 **Pain severity:** 5.
1.9.4.2.2.2 **Competitive position:** table-stakes.
1.9.4.2.2.3 **Dependency depth:** 4.
1.9.4.2.2.4 **Operational risk of delay:** active-harm.
1.9.4.2.2.5 **Composite priority:** 3.0
1.9.4.2.2.6 **Opportunity cost:** By not building this yet, officers duplicate review effort on the same applications and all admission decisions lack mandatory rationale.
1.9.4.2.3.1 **Pain severity:** 4.
1.9.4.2.3.2 **Competitive position:** table-stakes.
1.9.4.2.3.3 **Dependency depth:** 3.
1.9.4.2.3.4 **Operational risk of delay:** active-harm.
1.9.4.2.3.5 **Composite priority:** 3.0
1.9.4.2.3.6 **Opportunity cost:** By not building this yet, officers manually provision chapter infrastructure, accumulating inconsistent structures and untracked cleanup cost for every new sub-community (Problem §5).
1.9.4.2.4.1 **Pain severity:** 4.
1.9.4.2.4.2 **Competitive position:** gap.
1.9.4.2.4.3 **Dependency depth:** 3.
1.9.4.2.4.4 **Operational risk of delay:** active-harm.
1.9.4.2.4.5 **Composite priority:** 2.25
1.9.4.2.4.6 **Opportunity cost:** By not building this yet, permission drift silently accumulates with no concept of intended state against which actual state can be audited (Problem §7).
1.9.4.2.5.1 **Pain severity:** 3.
1.9.4.2.5.2 **Competitive position:** gap.
1.9.4.2.5.3 **Dependency depth:** 2.
1.9.4.2.5.4 **Operational risk of delay:** active-harm.
1.9.4.2.5.5 **Composite priority:** 2.25
1.9.4.2.5.6 **Opportunity cost:** By not building this yet, officers either miss events requiring action or receive cascading notifications for every downstream effect of a single decision, eroding volunteer attention budgets (Problem §9).
1.9.4.2.6.1 **Pain severity:** 3.
1.9.4.2.6.2 **Competitive position:** gap.
1.9.4.2.6.3 **Dependency depth:** 1.
1.9.4.2.6.4 **Operational risk of delay:** static-gap.
1.9.4.2.6.5 **Composite priority:** 2.25
1.9.4.2.6.6 **Opportunity cost:** By not building this yet, answering "what is this member's full operational history?" requires manually checking multiple systems and correlating events by hand (Problem §12).
1.9.4.2.7.1 **Pain severity:** 3.
1.9.4.2.7.2 **Competitive position:** gap.
1.9.4.2.7.3 **Dependency depth:** 4.
1.9.4.2.7.4 **Operational risk of delay:** static-gap.
1.9.4.2.7.5 **Composite priority:** 0.9
1.9.4.2.7.6 **Opportunity cost:** By not building this yet, trust assessment remains a coarse verification check rather than a nuanced gradient informed by officer observations and chapter-specific compliance signals (Problem §1).
1.9.4.3.1.1 **Pain severity:** 4.
1.9.4.3.1.2 **Competitive position:** table-stakes.
1.9.4.3.1.3 **Dependency depth:** 4.
1.9.4.3.1.4 **Operational risk of delay:** active-harm.
1.9.4.3.1.5 **Composite priority:** 2.4
1.9.4.3.1.6 **Opportunity cost:** By not building this yet, chapter membership records live in spreadsheets or Discord role presence, with no lifecycle tracking or auditable role history (Problem §5).
1.9.4.3.2.1 **Pain severity:** 4.
1.9.4.3.2.2 **Competitive position:** gap.
1.9.4.3.2.3 **Dependency depth:** 5.
1.9.4.3.2.4 **Operational risk of delay:** active-harm.
1.9.4.3.2.5 **Composite priority:** 1.5
1.9.4.3.2.6 **Opportunity cost:** By not building this yet, cases silently age in assigned states with no time-based accountability.
1.9.4.3.3.1 **Pain severity:** 3.
1.9.4.3.3.2 **Competitive position:** gap.
1.9.4.3.3.3 **Dependency depth:** 4.
1.9.4.3.3.4 **Operational risk of delay:** active-harm.
1.9.4.3.3.5 **Composite priority:** 1.35
1.9.4.3.3.6 **Opportunity cost:** By not building this yet, every temporary permission override requires manual tracking and manual cleanup, and forgotten overrides silently become permanent baseline (Problem §7).
1.9.4.3.4.1 **Pain severity:** 3.
1.9.4.3.4.2 **Competitive position:** gap.
1.9.4.3.4.3 **Dependency depth:** 5.
1.9.4.3.4.4 **Operational risk of delay:** static-gap.
1.9.4.3.4.5 **Composite priority:** 0.75
1.9.4.3.4.6 **Opportunity cost:** By not building this yet, interviews happen in untracked DMs and waitlisted applicants are managed informally, with no system visibility into who is waiting or why (Problem §2).
1.9.4.4.1.1 **Pain severity:** 5.
1.9.4.4.1.2 **Competitive position:** table-stakes.
1.9.4.4.1.3 **Dependency depth:** 6.
1.9.4.4.1.4 **Operational risk of delay:** active-harm.
1.9.4.4.1.5 **Composite priority:** 2.14
1.9.4.4.1.6 **Opportunity cost:** By not building this yet, officers spend hours daily on manual data entry and spreadsheet cross-referencing for threshold checks, the primary source of volunteer burnout (Problem §6).
1.9.4.4.2.1 **Pain severity:** 3.
1.9.4.4.2.2 **Competitive position:** gap.
1.9.4.4.2.3 **Dependency depth:** 5.
1.9.4.4.2.4 **Operational risk of delay:** static-gap.
1.9.4.4.2.5 **Composite priority:** 0.75
1.9.4.4.2.6 **Opportunity cost:** By not building this yet, when a chapter leader departs, pending decisions are orphaned, operational context is lost, and the successor must reconstruct governance state from memory (Problem §5).
1.9.4.4.3.1 **Pain severity:** 3.
1.9.4.4.3.2 **Competitive position:** gap.
1.9.4.4.3.3 **Dependency depth:** 5.
1.9.4.4.3.4 **Operational risk of delay:** future-risk.
1.9.4.4.3.5 **Composite priority:** 0.525
1.9.4.4.3.6 **Opportunity cost:** By not building this yet, inactive or troubled chapters accumulate without formal governance intervention, and archival is an ad-hoc manual process that risks losing operational history (Problem §5).

## Border List
- Executive Summary -> Strategic Narrative
  Last: *Managed by* flagging this as a known Phase 2 onboarding cost and scoping the one-time migration tool inside VS-008's engineering work.
  First: The four phases are a single sequence, not four independent tracks.
  Note: clear: the summary hands off from the decision snapshot to the reasoning behind the sequence.
- Strategic Narrative -> Phase Structure
  Last: **No public community-surface features.** No website/forums/event pages of the kind Gamer Launch, Shivtr, and Guild Manager offer (`market research.md` §4 Differentiation opportunities).
  First: <no standalone prose>
  Note: weak: the narrative closes on non-goals, then the memo drops into the phase template without a bridge sentence.
- Phase Structure -> Phase 0: Foundations (engineering-defined)
  Last: <no standalone prose>
  First: **Business outcome.** A reliable and portable runtime that isolates subsystems, letting every downstream value slice ship without each re-inventing platform infrastructure.
  Note: weak: one side is a container heading with no standalone prose, so the border is purely structural.
- Phase 0: Foundations (engineering-defined) -> Phase 1: Governance Foundation
  Last: This phase also encompasses data portability design (documented, exportable formats for all schema objects) and platform assumption verification at startup.
  First: **Business outcome.** A defensible governance substrate no reviewed competitor offers: persistent trust profiles, scoped authority enforcement, causal audit across subsystems, and preview-confirm policy versioning on a live server.
  Note: clear: foundations lead naturally into the first operator-visible phase.
- Phase 1: Governance Foundation -> Phase 2: Core Operational Workflows
  Last: Detailed scoring rationale and opportunity cost per slice is in the Appendix.
  First: **Business outcome.** Operational parity with the eight application tools and nine ticket tools that define today's reviewed competition.
  Note: weak: each phase ends on the same appendix pointer, so the handoff feels mechanical rather than argued.
- Phase 2: Core Operational Workflows -> Phase 3: Operational Depth
  Last: Detailed scoring rationale and opportunity cost per slice is in the Appendix.
  First: **Business outcome.** The integrated roster-and-activity package with analytics that six sources identify as the integration operators most readily pay for (`market research.md` §5).
  Note: weak: each phase ends on the same appendix pointer, so the handoff feels mechanical rather than argued.
- Phase 3: Operational Depth -> Phase 4: Operational Maturity
  Last: Detailed scoring rationale and opportunity cost per slice is in the Appendix.
  First: **Business outcome.** Evidence-based compliance evaluation is the anchoring capability.
  Note: weak: each phase ends on the same appendix pointer, so the handoff feels mechanical rather than argued.
- Phase 4: Operational Maturity -> Competitive Positioning
  Last: Detailed scoring rationale and opportunity cost per slice is in the Appendix.
  First: **Alternatives communities use today.** The reviewed market spans 50 products across six categories (`market research.md` Methodology):
  Note: weak: the roadmap walkthrough ends on a slice list, then competitive positioning starts after the fact.
- Competitive Positioning -> Risk Register
  Last: **Market gaps are documented, not speculative.** Every `gap` classification in the scoring traces to an explicit "Gap Analysis" section in the source research (`plans/risk/executive-market-misread.md` F-3).
  First: Top risks carried through the three executive risk assessments (`plans/risk/executive-market-misread.md`, `plans/risk/executive-dependency-trap.md`, `plans/risk/executive-completeness.md`).
  Note: clear: after asserting market advantage, the memo moves directly to what could break that claim.
- Risk Register -> Approval Package
  Last: All three assessments rate LOW overall; this register surfaces the specific findings executives should monitor.
  First: **What leadership is being asked to approve.**
  Note: clear: the risk inventory feeds naturally into the approval decision and review posture.
- Approval Package -> Opportunity Cost Summary
  Last: **If VS-005 delivery risk materializes:** re-evaluate downstream cascade and communication to affected operator segments (Risk #1).
  First: <no standalone prose>
  Note: weak: the approval prose drops straight into a table with no sentence preparing that move.
- Opportunity Cost Summary -> Deferred Subsystems
  Last: <no standalone prose>
  First: No proposal subsystem is fully deferred.
  Note: weak: the table-only summary has no exit sentence, so the move into deferred items is abrupt.
- Deferred Subsystems -> Appendix
  Last: The engineering layer addresses these within Phase 0 infrastructure.
  First: <no standalone prose>
  Note: weak: the memo ends and the appendix begins without a handoff sentence.
- Appendix -> A. Scoring Methodology
  Last: <no standalone prose>
  First: **Pain severity (1–5):** How much does this address a problem operators vocally care about?
  Note: weak: one side is a container heading with no standalone prose, so the border is purely structural.
- A. Scoring Methodology -> B. Decomposition Targets
  Last: **Composite formula:** `pain_severity × competitive_weight × delay_risk_weight / (dependency_depth + 1)`
  First: **Seven subsystems:** Identity and Trust, Intake and Adjudication, Case Management, Sub-community Lifecycle, Activity and Compliance, Permission Management, Governance.
  Note: clear: scoring rules hand off cleanly to the objects being scored.
- B. Decomposition Targets -> C. Value Slice Inventory
  Last: **Four cross-cutting concerns:** Cross-workflow State Coherence, Platform Boundary, Graceful Degradation, Data Portability.
  First: <no standalone prose>
  Note: weak: the taxonomy section jumps to the inventory without any lead-in prose.
- C. Value Slice Inventory -> VS-001: Member onboarding with initial trust assessment
  Last: <no standalone prose>
  First: **Subsystem(s):** Identity and Trust **Capability delivered:** Operators see every new member with a computed, inspectable trust level derived from platform signals.
  Note: weak: the container heading has no setup sentence; the inventory starts cold.
- VS-001: Member onboarding with initial trust assessment -> VS-002: Scoped authority with enforcement
  Last: Signal decay management
  First: **Subsystem(s):** Governance **Capability delivered:** Officers receive explicit authority grants for defined scopes; the system denies out-of-scope operations with clear explanations.
  Note: clear: this is appendix inventory material, so a mechanical item-to-item border is acceptable.
- VS-002: Scoped authority with enforcement -> VS-003: Audit trail with causal correlation
  Last: Automatic authority from ChapterRole assignment
  First: **Subsystem(s):** Governance (cross-cutting) **Capability delivered:** Every operational decision is recorded immutably with actor, context, policy version, and causal chain identifiers.
  Note: clear: this is appendix inventory material, so a mechanical item-to-item border is acceptable.
- VS-003: Audit trail with causal correlation -> VS-004: Policy versioning with configuration safety
  Last: Operator dashboard for audit queries
  First: **Subsystem(s):** Governance **Capability delivered:** Configuration changes are versioned with preview-confirm workflow and optimistic concurrency; in-flight operations are protected from mid-stream rule changes.
  Note: clear: this is appendix inventory material, so a mechanical item-to-item border is acceptable.
- VS-004: Policy versioning with configuration safety -> VS-005: Chapter provisioning from templates
  Last: Policy diff visualization
  First: **Subsystem(s):** Sub-community Lifecycle **Capability delivered:** Operators create new chapters from configurable templates; Discord resources (channels and roles with their categories) are provisioned through an approval gate.
  Note: clear: this is appendix inventory material, so a mechanical item-to-item border is acceptable.
- VS-005: Chapter provisioning from templates -> VS-006: Structured application intake with reviewer ownership
  Last: Chapter configuration editing
  First: **Subsystem(s):** Intake and Adjudication; Identity and Trust (trust context in review) **Capability delivered:** Members submit structured applications, and a single reviewer claims and evaluates each one with trust context and mandatory decision reasons.
  Note: clear: this is appendix inventory material, so a mechanical item-to-item border is acceptable.
- VS-006: Structured application intake with reviewer ownership -> VS-007: Ticket creation and case lifecycle
  Last: Chapter application support depends on chapters existing (VS-005 or equivalent)
  First: **Subsystem(s):** Case Management **Capability delivered:** Officers create and manage tickets with category-specific state machines and privacy controls; assignment tracks ownership and resolution requires mandatory reasons.
  Note: clear: this is appendix inventory material, so a mechanical item-to-item border is acceptable.
- VS-007: Ticket creation and case lifecycle -> VS-008: Permission intent and drift detection
  Last: Cross-ticket pattern detection
  First: **Subsystem(s):** Permission Management **Capability delivered:** Operators declare intended permission state with reasons; the system detects when Discord permissions diverge and surfaces drift for explicit resolution.
  Note: clear: this is appendix inventory material, so a mechanical item-to-item border is acceptable.
- VS-008: Permission intent and drift detection -> VS-009: Configurable operator notifications
  Last: Automated reconciliation scheduling
  First: **Subsystem(s):** Governance **Capability delivered:** Operators configure notification triggers, scoped recipients, delivery channels, actionable vs. informational distinction, and causal grouping to prevent notification fatigue.
  Note: clear: this is appendix inventory material, so a mechanical item-to-item border is acceptable.
- VS-009: Configurable operator notifications -> VS-010: Advanced trust management
  Last: Notification templates beyond structured content
  First: **Subsystem(s):** Identity and Trust **Capability delivered:** Officers record trust signals (identity verification and endorsements, plus compliance history).
  Note: clear: this is appendix inventory material, so a mechanical item-to-item border is acceptable.
- VS-010: Advanced trust management -> VS-011: Roster management with role lifecycle
  Last: Trust analytics or trending
  First: **Subsystem(s):** Sub-community Lifecycle **Capability delivered:** Officers manage chapter rosters.
  Note: clear: this is appendix inventory material, so a mechanical item-to-item border is acceptable.
- VS-011: Roster management with role lifecycle -> VS-012: Application interview and waitlist handling
  Last: Cross-chapter roster comparison
  First: **Subsystem(s):** Intake and Adjudication **Capability delivered:** Reviewers request interviews with system-provisioned private threads; applications can be waitlisted and reactivated by reviewers.
  Note: clear: this is appendix inventory material, so a mechanical item-to-item border is acceptable.
- VS-012: Application interview and waitlist handling -> VS-013: SLA enforcement for tickets
  Last: Interview scheduling
  First: **Subsystem(s):** Case Management **Capability delivered:** Per-category SLA rules with graduated time-based thresholds trigger proportional consequences:
  Note: clear: this is appendix inventory material, so a mechanical item-to-item border is acceptable.
- VS-013: SLA enforcement for tickets -> VS-014: Temporary permission management
  Last: Custom SLA consequence actions
  First: **Subsystem(s):** Permission Management **Capability delivered:** Operators create time-limited permission intents; expired overrides automatically surface as drift, preventing "temporary becomes permanent."
  Note: clear: this is appendix inventory material, so a mechanical item-to-item border is acceptable.
- VS-014: Temporary permission management -> VS-015: Cross-subsystem operational views
  Last: Temporary permission renewal workflow
  First: **Subsystem(s):** Governance (cross-cutting) **Capability delivered:** Operators query operational history across all subsystems through materialized read models, including causal chain views and scope-filtered projections.
  Note: clear: this is appendix inventory material, so a mechanical item-to-item border is acceptable.
- VS-015: Cross-subsystem operational views -> VS-016: Compliance rule evaluation with evidence
  Last: Real-time streaming
  First: **Subsystem(s):** Activity and Compliance **Capability delivered:** Chapter-scoped compliance rules evaluate members on schedule against submitted evidence (OCR-parsed screenshots and structured feeds from game APIs or manual reports); violations trigger graduated consequences.
  Note: clear: this is appendix inventory material, so a mechanical item-to-item border is acceptable.
- VS-016: Compliance rule evaluation with evidence -> VS-017: Chapter governance lifecycle
  Last: Bulk evidence import
  First: **Subsystem(s):** Sub-community Lifecycle **Capability delivered:** Chapters can enter probation (governance concerns) and proceed through archival with member notification and pending work resolution, preserving state throughout.
  Note: clear: this is appendix inventory material, so a mechanical item-to-item border is acceptable.
- VS-017: Chapter governance lifecycle -> VS-018: Leadership succession with context transfer
  Last: Cross-chapter governance dashboard
  First: **Subsystem(s):** Sub-community Lifecycle; Governance **Capability delivered:** When a succession-triggering role holder departs, pending decisions and open work are identified, and authority transfers to the successor with a predecessor link.
  Note: clear: this is appendix inventory material, so a mechanical item-to-item border is acceptable.
- VS-018: Leadership succession with context transfer -> D. Per-Slice Scoring Detail
  Last: Cross-chapter succession coordination
  First: <no standalone prose>
  Note: weak: the inventory ends and the scoring appendix starts with no bridge.
- D. Per-Slice Scoring Detail -> Phase 1
  Last: <no standalone prose>
  First: <no standalone prose>
  Note: weak: this is a container-to-container handoff, not a rhetorical transition.
- Phase 1 -> VS-001: Member onboarding with initial trust assessment
  Last: <no standalone prose>
  First: **Pain severity:** 4.
  Note: weak: the phase bucket heading is structural only and does not transition into the next entry.
- VS-001: Member onboarding with initial trust assessment -> VS-003: Audit trail with causal correlation
  Last: **Opportunity cost:** By not building this yet, officers continue making trust decisions about members based on personal memory and Discord role presence, which breaks across chapter boundaries and on staff turnover (Problem §1).
  First: **Pain severity:** 4.
  Note: clear: this is scoring detail in catalog form, so sequential handoffs are acceptable.
- VS-003: Audit trail with causal correlation -> VS-004: Policy versioning with configuration safety
  Last: **Opportunity cost:** By not building this yet, decisions become unreconstructable after Discord's 45-day audit log expires, and officers cannot prove what happened or what policy governed a disputed decision (Problem §4).
  First: **Pain severity:** 4.
  Note: clear: this is scoring detail in catalog form, so sequential handoffs are acceptable.
- VS-004: Policy versioning with configuration safety -> VS-002: Scoped authority with enforcement
  Last: Changing an application form mid-review can alter the meaning of pending submissions without any error signal (Problem §13).
  First: **Pain severity:** 3.
  Note: clear: this is scoring detail in catalog form, so sequential handoffs are acceptable.
- VS-002: Scoped authority with enforcement -> Phase 2
  Last: **Opportunity cost:** By not building this yet, communities rely on Discord's ranked hierarchy model, pushing officers toward either over-centralization or over-granting because the platform cannot express "only within your chapter" (Problem §10).
  First: <no standalone prose>
  Note: weak: one side is a container heading with no standalone prose, so the border is purely structural.
- Phase 2 -> VS-007: Ticket creation and case lifecycle
  Last: <no standalone prose>
  First: **Pain severity:** 5.
  Note: weak: the phase bucket heading is structural only and does not transition into the next entry.
- VS-007: Ticket creation and case lifecycle -> VS-006: Structured application intake with reviewer ownership
  Last: **Opportunity cost:** By not building this yet, sensitive case workflows live in ephemeral DM threads without durable state or ownership tracking (Problem §3).
  First: **Pain severity:** 5.
  Note: clear: this is scoring detail in catalog form, so sequential handoffs are acceptable.
- VS-006: Structured application intake with reviewer ownership -> VS-005: Chapter provisioning from templates
  Last: Making appeals unreconstructable (Problem §2, §9).
  First: **Pain severity:** 4.
  Note: clear: this is scoring detail in catalog form, so sequential handoffs are acceptable.
- VS-005: Chapter provisioning from templates -> VS-008: Permission intent and drift detection
  Last: **Opportunity cost:** By not building this yet, officers manually provision chapter infrastructure, accumulating inconsistent structures and untracked cleanup cost for every new sub-community (Problem §5).
  First: **Pain severity:** 4.
  Note: clear: this is scoring detail in catalog form, so sequential handoffs are acceptable.
- VS-008: Permission intent and drift detection -> VS-009: Configurable operator notifications
  Last: **Opportunity cost:** By not building this yet, permission drift silently accumulates with no concept of intended state against which actual state can be audited (Problem §7).
  First: **Pain severity:** 3.
  Note: clear: this is scoring detail in catalog form, so sequential handoffs are acceptable.
- VS-009: Configurable operator notifications -> VS-015: Cross-subsystem operational views
  Last: **Opportunity cost:** By not building this yet, officers either miss events requiring action or receive cascading notifications for every downstream effect of a single decision, eroding volunteer attention budgets (Problem §9).
  First: **Pain severity:** 3.
  Note: clear: this is scoring detail in catalog form, so sequential handoffs are acceptable.
- VS-015: Cross-subsystem operational views -> VS-010: Advanced trust management
  Last: **Opportunity cost:** By not building this yet, answering "what is this member's full operational history?" requires manually checking multiple systems and correlating events by hand (Problem §12).
  First: **Pain severity:** 3.
  Note: clear: this is scoring detail in catalog form, so sequential handoffs are acceptable.
- VS-010: Advanced trust management -> Phase 3
  Last: **Opportunity cost:** By not building this yet, trust assessment remains a coarse verification check rather than a nuanced gradient informed by officer observations and chapter-specific compliance signals (Problem §1).
  First: <no standalone prose>
  Note: weak: one side is a container heading with no standalone prose, so the border is purely structural.
- Phase 3 -> VS-011: Roster management with role lifecycle
  Last: <no standalone prose>
  First: **Pain severity:** 4.
  Note: weak: the phase bucket heading is structural only and does not transition into the next entry.
- VS-011: Roster management with role lifecycle -> VS-013: SLA enforcement for tickets
  Last: **Opportunity cost:** By not building this yet, chapter membership records live in spreadsheets or Discord role presence, with no lifecycle tracking or auditable role history (Problem §5).
  First: **Pain severity:** 4.
  Note: clear: this is scoring detail in catalog form, so sequential handoffs are acceptable.
- VS-013: SLA enforcement for tickets -> VS-014: Temporary permission management
  Last: A harassment report stalling for a week has no automated escalation path (Problem §3).
  First: **Pain severity:** 3.
  Note: clear: this is scoring detail in catalog form, so sequential handoffs are acceptable.
- VS-014: Temporary permission management -> VS-012: Application interview and waitlist handling
  Last: **Opportunity cost:** By not building this yet, every temporary permission override requires manual tracking and manual cleanup, and forgotten overrides silently become permanent baseline (Problem §7).
  First: **Pain severity:** 3.
  Note: clear: this is scoring detail in catalog form, so sequential handoffs are acceptable.
- VS-012: Application interview and waitlist handling -> Phase 4
  Last: **Opportunity cost:** By not building this yet, interviews happen in untracked DMs and waitlisted applicants are managed informally, with no system visibility into who is waiting or why (Problem §2).
  First: <no standalone prose>
  Note: weak: one side is a container heading with no standalone prose, so the border is purely structural.
- Phase 4 -> VS-016: Compliance rule evaluation with evidence
  Last: <no standalone prose>
  First: **Pain severity:** 5.
  Note: weak: the phase bucket heading is structural only and does not transition into the next entry.
- VS-016: Compliance rule evaluation with evidence -> VS-018: Leadership succession with context transfer
  Last: **Opportunity cost:** By not building this yet, officers spend hours daily on manual data entry and spreadsheet cross-referencing for threshold checks, the primary source of volunteer burnout (Problem §6).
  First: **Pain severity:** 3.
  Note: clear: this is scoring detail in catalog form, so sequential handoffs are acceptable.
- VS-018: Leadership succession with context transfer -> VS-017: Chapter governance lifecycle
  Last: **Opportunity cost:** By not building this yet, when a chapter leader departs, pending decisions are orphaned, operational context is lost, and the successor must reconstruct governance state from memory (Problem §5).
  First: **Pain severity:** 3.
  Note: clear: this is scoring detail in catalog form, so sequential handoffs are acceptable.

## Structural Issues Identified

### Visible templates
- Mild: `Strategic Narrative` names rhetorical mode more than subject matter. The rest of the major headings are acceptable for an executive roadmap / decision memo.

### Missing narrative steps
- The strategic-opportunity hook is weak in the opening. The memo starts with the finished-system outcome before it gives the reader the opportunity/timing tension.
- The key reframe, `value ordering reveals what to build first`, is present but delayed. It does not arrive immediately after the opening claim.
- The first concrete anchor comes after abstraction. Vendor exits and active-harm examples appear in the second cluster of summary bullets instead of grounding the opener.
- The felt problem is distributed across several bullets and later phase sections rather than crystallized early in one memorable operating pain.

### Weak borders
- `Strategic Narrative -> Phase Structure` is the biggest main-body break. The memo moves from non-goals to the phase template without a sentence explaining why the reader is now switching from argument to operating structure.
- `Phase 1 -> Phase 2`, `Phase 2 -> Phase 3`, and `Phase 3 -> Phase 4` all end on the same appendix pointer. That repeated landing sentence flattens momentum between phases.
- `Approval Package -> Opportunity Cost Summary` and `Opportunity Cost Summary -> Deferred Subsystems` are abrupt because the table section has no intro or exit prose.
- The appendix has several structural-only borders (`Appendix`, `C. Value Slice Inventory`, `D. Per-Slice Scoring Detail`, and the phase buckets under scoring), so readers repeatedly hit headings with no prose handoff.

### Other structural concerns
- The document has two modes: executive memo and reference appendix. The appendix is so large that it can overpower the memo’s narrative spine.
- Phase sections are highly templated. They are clear, but the repeated scaffold (`Business outcome`, `Success condition`, `Value realization window`, and so on) makes the skeleton visible.
- `Phase Structure`, `Opportunity Cost Summary`, `Appendix`, `C. Value Slice Inventory`, and `D. Per-Slice Scoring Detail` function as containers more than prose-bearing sections. That creates empty structural nodes in the outline.
- Competitive positioning lands after the full phase walkthrough, so part of the `why this ordering` case reads as if it is being substantiated after the roadmap is already asserted.
