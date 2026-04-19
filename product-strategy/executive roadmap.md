# Executive Roadmap

## Executive Summary

**The moment.** The competitive window is open because incumbent vendors are exiting, and it is narrow because the harm communities experience compounds with delay.

- **Vendors are departing while market gaps remain unfilled.** Gather is deprecated and Guilded is shut down. Five-plus sources describe declared-state reconciliation as "under-served" across a ticketing and permissions market that is crowded but shallow (`market research.md` §2, §3, §6, §7, Cross-cutting Findings). Vendor instability is actively pushing communities to look for new platforms.
- **Operational harm is active, not hypothetical.** Seven of the fourteen problem axes describe active-harm patterns that worsen as communities delay, including audit gaps past Discord's 45-day cap (`problem.md` §4) and permission drift compounding from crisis exceptions (`problem.md` §7). Configuration corruption mid-operation and volunteer burnout from manual enforcement follow the same pattern (`problem.md` §6, §9, §13).

**Value ordering reveals what to build first.** The problems above are structural rather than tactical, so the right response is not a feature wishlist but an ordered sequence derived from where value compounds across subsystems. The scoring analysis (see Appendix) finds that dependency-driven phasing is sound and ordering is stable under alternative market readings (`plans/risk/executive-dependency-trap.md` F-4, F-5, F-7; `plans/risk/executive-market-misread.md` F-8).

**Strategic outcome.** Deliver a Discord-native guild management platform that treats identity/trust, intake, case management, sub-community lifecycle, activity/compliance, permissions, and governance as one unified operational system with causal auditability across subsystems. This closes the structural gap no reviewed competitor addresses (`market research.md` cross-cutting: "the market repeatedly fails to offer a single decision chain spanning intake, cases, chapters, permissions, and compliance"). The system treats community data as community-owned and exportable by design, with queryable schemas throughout (`proposal.md` Non-goals; `market research.md` §7: "Retention and export are uneven or gated").

**Approval ask.** Commit contributor effort and resource attention to the four-phase sequence as scoped: Phase 0 (engineering foundations), Phase 1 (governance foundation), Phase 2 (core operational workflows), Phase 3 (operational depth), Phase 4 (operational maturity). This approves the 18 value slices in their current phase assignments. It also locks the scope exclusions listed in `proposal.md` Non-goals (bot-framework breadth, moderation-first design, AI-driven operational decisions, real-time game integration) and commits to the review cadence defined in the Approval Package section.

**Value realization by phase.**

- **After Phase 1:** Every member carries a computed trust level that reviewers can inspect, and authority grants operate within scoped boundaries with automatic enforcement. Decisions are recorded immutably with causal correlation, and configuration changes on a live server carry preview-confirm safety. This foundation alone closes the governance gap that all reviewed suites miss (`market research.md` §7).
- **After Phase 2:** Operators run structured applications with reviewer ownership and manage tickets through category-specific state machines. Chapter provisioning works from templates. Permission drift becomes detectable, and notifications support causal grouping to prevent cascade fatigue. This is the operational core that eight application tools and nine ticket tools compete on today, alongside eight multi-unit suites targeting chapter management (`market research.md` §2, §3, §4).
- **After Phase 3:** Officers manage rosters and enforce SLAs with graduated consequences. Interviews and waitlists gain structure, and temporary permissions are tracked with expiration. This completes the integrated roster-and-activity package six sources identify as the integration operators most readily pay for (`market research.md` §5).
- **After Phase 4:** Chapters have full governance lifecycle (probation, archival) with leadership succession and evidence-based compliance evaluation.

**Top risks and management posture.**

1. **Dependency bottleneck at chapter provisioning (VS-005).** This Phase 2 slice transitively blocks roster, compliance, chapter governance, and succession (`plans/risk/executive-dependency-trap.md` F-1). *Managed by* keeping VS-005 scope tight (Phase 2, depth 3 via VS-001, VS-002, VS-003) and tracking it as the primary schedule risk.
2. **Phase 0 scope ambiguity.** Phase 0 is a one-sentence engineering placeholder; Phase 1 implicitly depends on foundations (`plans/risk/executive-completeness.md` F-2). *Managed by* requiring engineering to define Phase 0 acceptance criteria before Phase 1 begins.
3. **Market misread risk (competitor enters intent model).** All `gap` classifications assume no competitor has shipped a declared-intent-vs-actual control plane with policy versioning, or a cross-subsystem causal audit (`plans/risk/executive-market-misread.md` What LOW requires #2). *Managed by* re-running the risk gate at each phase boundary using fresh market data.
4. **Scope creep into non-goals.** Pressure to add bot-framework breadth or moderation-first features would dilute differentiation, with AI-driven decisions carrying the same risk (`proposal.md` Non-goals). *Managed by* treating Non-goals as an approval gate: any proposed addition that crosses a Non-goals line requires explicit executive re-approval.
5. **Adoption friction from absent migration tooling.** Permission migration tooling is deferred; adopting communities inherit all existing Discord permissions as "unintended" drift (see Deferred Subsystems). *Managed by* flagging this as a known Phase 2 onboarding cost and scoping the one-time migration tool inside VS-008's engineering work.

---

## Strategic Narrative

The four phases are a single sequence, not four independent tracks. Each phase unlocks operational leverage the prior phase did not deliver and reduces a class of risk the prior phase did not contain.

**Phase 1. Buy defensibility first.** Before operator workflows, the system needs trust profiles, scoped authority, immutable causal audit, and preview-confirm policy changes. These four capabilities are not features; they are the governance substrate every subsystem consumes. The market confirms they are missing across the reviewed field: no product offers "persistent, inspectable trust signals with deterministic recomputation," "scoped grants," "an intent-vs-actual control plane," or "policy versioning with compare-and-swap edits" (`market research.md` §1, §6, §7). Building the substrate first is both the competitive bet (differentiated floor no competitor offers) and the risk-containment bet (decisions made in Phase 2 onward are auditable and reversible as soon as each workflow ships).

**Phase 2. Reach parity on the operational workflows competitors already monetize.** With the governance substrate in place, Phase 2 builds the workflows that eight application tools and nine ticket tools monetize today, along with eight multi-unit suites competing on chapter management (`market research.md` §2, §3, §4). Competing on features these markets already serve requires the Phase 1 substrate to distinguish the product. Application intake with reviewer ownership plus structured audit is a different product from application intake with shared-dashboard review.

**Phase 3. Close the willingness-to-pay package.** Roster management, SLA enforcement, temporary permissions, and application interview/waitlist handling complete the integrated roster-and-activity package six market research sources identify as the integration operators most readily pay for, analytics included (`market research.md` §5). These capabilities replace the spreadsheet-plus-multi-bot stacks communities cobble together today (`market research.md` §4 Community Management Workarounds).

**Phase 4. Close the operational lifecycle.** Compliance evaluation against submitted evidence is the anchoring capability. It ships alongside chapter governance lifecycle (probation and archival) and leadership succession with context transfer. These capabilities answer problems the market has not addressed ("general-purpose compliance engine is still missing"; "succession and delegated-local-authority continuity remain implicit rather than modeled") (`market research.md` §4, §5).

**What this roadmap deliberately does not pursue.** The proposal's Non-goals hold throughout the roadmap (`proposal.md` Non-goals):

- **Not a general-purpose bot framework.** No scripting or arbitrary-automation surface. Every capability is a deliberate subsystem, not a toolkit primitive.
- **Not moderation-first.** Moderation is one ticket category among many, not the organizing center. Anti-nuke, anti-raid, panic-mode, and turnkey anti-alt heuristics (where Wick and Security Bot specialize) are out of scope (`market research.md` §1 Differentiation opportunities: "Competitors have specialized anti-raid and anti-abuse surfaces the proposal does not directly cover").
- **Not feature-parity with existing bots.** Leveling, reaction-role UX depth, DKP/loot systems, raid composition tools, and event-scheduling depth belong to specialized products (`market research.md` §5, §6 Differentiation opportunities). Duplicating them would dilute focus.
- **No AI-driven operational decisions.** AI is used only for OCR and data extraction. Approve/deny and promote/demote remain human decisions with system-provided context, as do flag/escalate calls.
- **No real-time game integration.** Game APIs are ingested where available; real-time synchronization is not promised.
- **No full-server cloning or backup/restore.** Xenon-style cloning is out of scope (`market research.md` §6 Differentiation opportunities).
- **No public community-surface features.** No website/forums/event pages of the kind Gamer Launch, Shivtr, and Guild Manager offer (`market research.md` §4 Differentiation opportunities).

---

## Phase Structure

The narrative above explained why this sequence. The phase structure below explains how each phase operates, naming the business outcome and success condition alongside the investment ask and phase-specific risks so contributors and approvers share a single view of what ships and what it enables.

### Phase 0: Foundations (engineering-defined)

**Business outcome.** A reliable and portable runtime that isolates subsystems, letting every downstream value slice ship without each re-inventing platform infrastructure.

**Success condition.** Engineering has defined acceptance criteria for the four cross-cutting concerns (Cross-workflow State Coherence, Platform Boundary, Graceful Degradation, Data Portability) and the shared schemas (AuditEntry, PolicyVersion, PermissionIntent, AuthorityGrant) are in place before Phase 1 slices begin (`plans/risk/executive-dependency-trap.md` F-3; `plans/risk/executive-completeness.md` F-2).

**Value realization window.** Prerequisite. No direct operator-facing value; unblocks Phase 1.

**Confidence.** Committed (engineering-scoped).

**Investment ask.** Contributor time on foundational infrastructure; no additional external dependencies beyond Discord API access.

**Phase-specific risk.** Phase 0 scope is currently a one-sentence placeholder. If Phase 0 ships incomplete, Phase 1 slices inherit hidden infrastructure dependencies (`plans/risk/executive-completeness.md` F-2; `plans/risk/executive-dependency-trap.md` What LOW requires #2).

The engineering layer determines what technical foundations are needed before value slices can begin. Likely candidates include:

- Database schema and migration framework
- Discord gateway connection and platform boundary layer
- Subsystem isolation and graceful degradation mechanics
- Deferred effect queue infrastructure
- Base API framework

This phase also encompasses data portability design (documented, exportable formats for all schema objects) and platform assumption verification at startup.

---

### Phase 1: Governance Foundation

**Business outcome.** A defensible governance substrate no reviewed competitor offers: persistent trust profiles, scoped authority enforcement, causal audit across subsystems, and preview-confirm policy versioning on a live server.

**User/community pain relieved.** Officers no longer rely on memory and Discord role presence to decide trust (`problem.md` §1). Decisions that used to vanish after Discord's 45-day audit window persist with causal context (`problem.md` §4), and configuration changes on a live server no longer silently corrupt in-flight operations (`problem.md` §13). Authority leaves the ranked-hierarchy model that forces over-centralization or over-granting (`problem.md` §10).

**Success condition (qualitative).** An operator can:

- View any member's trust level with the signals that produced it
- Grant or revoke authority scoped to a specific area with automatic enforcement
- Reconstruct any past decision months later from immutable audit entries with causal chain
- Change policy on a live server with preview-confirm and optimistic concurrency protection

**Value realization window.** Foundational. Delivers defensible differentiation before any operational workflow. Capability visible as each slice ships.

**Confidence.** Committed. All four Phase 1 slices have dependency depth 0 and stable composite scores under alternative market readings (`plans/risk/executive-market-misread.md` F-8).

**Investment ask.** Contributor time. Phase 1 has maximum parallelism (up to four concurrent zero-dependency slices) (`plans/risk/executive-dependency-trap.md` F-5).

**Phase-specific risks.**

- **Chapter-provisioning slot (VS-005) is the highest-fanout bottleneck** (note: VS-005 sits in Phase 2 at dependency depth 3, inheriting from VS-001, VS-002, and VS-003; delay here cascades to four later slices in Phases 3–4). Managed by keeping VS-005 scope tight; other Phase 2 tracks proceed regardless (`plans/risk/executive-dependency-trap.md` F-1).
- **Shared-schema coordination between VS-004 (policy versioning) and VS-005 (chapter provisioning)**. Both consume `PolicyVersion`; Phase 0 must define the schema so the two slices do not block each other (`plans/risk/executive-dependency-trap.md` F-3).

**Capability gained:** The system registers members with computed trust levels and enforces scoped authority boundaries. Every operational decision is recorded immutably with causal chains, and configuration changes on a live server apply with preview-confirm safety.

**Workflows enabled:**

- Member onboarding with automatic trust computation from platform signals
- Authority grant and revoke with scope enforcement
- Audit trail queries across any operational domain
- Policy preview-confirm with optimistic concurrency protection

**Not yet built:**

- Operational workflows (applications, tickets, chapters)
- Discord resource management
- Compliance evaluation
- Notifications
- Roster management
- Permission management

**Prerequisites:** Phase 0

**Slices in this phase:** VS-001 (member onboarding with initial trust), VS-002 (scoped authority with enforcement), VS-003 (audit trail with causal correlation), VS-004 (policy versioning with configuration safety). Shipping the substrate first lets Phase 2 workflows inherit causal audit and scoped authority from day one rather than retrofit them later. Detailed scoring rationale and opportunity cost per slice is in the Appendix.

---

### Phase 2: Core Operational Workflows

**Business outcome.** Operational parity with the eight application tools and nine ticket tools that define today's reviewed competition. Eight multi-unit suites add another cluster competing on chapter management. Differentiation comes from the Phase 1 governance substrate none of them offer (`market research.md` §2, §3, §4).

**User/community pain relieved.** Officers stop duplicating review effort on the same application (`problem.md` §2, §9), and harassment reports and appeals leave DMs for durable state with ownership tracking (`problem.md` §3). Chapter infrastructure moves off the hand-assembled Discord-plus-spreadsheet stack (`problem.md` §5). Permission drift becomes detectable instead of silently accumulating from crisis exceptions (`problem.md` §7), and notification volume stops being a distinct burnout mechanism from process rigor (`problem.md` §9).

**Success condition (qualitative).** Operators can:

- Run a complete application review from submission to decision with exclusive reviewer ownership and mandatory reasons
- Open tickets with category-specific state machines and privacy controls
- Provision chapters from templates through an approval gate
- Declare intended permissions and see where Discord reality has drifted
- Configure notifications with causal grouping to prevent cascade fatigue
- Query cross-subsystem operational history

**Value realization window.** Operational value visible to communities considering a switch. This is the phase that makes the system viable as a replacement for current stacks.

**Confidence.** Likely. Phase 2 depends exclusively on Phase 1 outputs; no intra-phase ordering constraints (`plans/risk/executive-dependency-trap.md` F-4). Ordering within Phase 2 is not load-bearing.

**Investment ask.** Contributor time. Up to four concurrent slices (`plans/risk/executive-dependency-trap.md` F-5).

**Phase-specific risks.**

- **Competitive-window erosion.** If the operational-workflow markets (tickets, applications, permissions) consolidate around a new entrant during Phase 1, Phase 2 starts in a more contested market. Managed by re-running the risk gate at each phase boundary (`plans/risk/executive-market-misread.md` What LOW requires #2).
- **Adoption onboarding cost.** Permission migration tooling is deferred; communities adopting in Phase 2 see all existing Discord permissions as "unintended" drift until manually classified. Managed by scoping the one-time migration tool inside VS-008 engineering (see Deferred Subsystems).

**Capability gained:**
- Officers process structured applications with single-reviewer ownership
- Each ticket category has its own state machine with privacy controls
- New chapters are provisioned from templates through approval gates
- Operators declare intended permission state and detect drift
- Officers receive configurable notifications
- Trust computation is customizable with officer-managed signals
- Cross-subsystem history is queryable through materialized views

**Workflows enabled:**

- Application intake (submit → queue → claim → review → decide with mandatory reasons)
- Ticket lifecycle (create → triage → assign → resolve → close with category-specific states)
- Chapter provisioning (propose → approve → provision → activate)
- Permission reconciliation (declare intent → detect drift → resolve)
- Trust signal recording by officers with scoped computation configuration
- Notification configuration with causal grouping

**Not yet built:**

- Direct roster management beyond application-created entries (officer direct adds, status changes, role reassignment)
- Compliance evaluation
- SLA enforcement for tickets
- Application interview or waitlist handling
- Temporary permission expiration
- Chapter probation or archival
- Leadership succession

**Prerequisites:** Phase 1

**Slices in this phase:** VS-005 (chapter provisioning from templates), VS-006 (structured application intake with reviewer ownership), VS-007 (ticket creation and case lifecycle), VS-008 (permission intent and drift detection), VS-009 (configurable operator notifications), VS-010 (advanced trust management), VS-015 (cross-subsystem operational views). With the operational core in place, Phase 3 extends each workflow into the depth operators pay for rather than opening new subsystems. Detailed scoring rationale and opportunity cost per slice is in the Appendix.

---

### Phase 3: Operational Depth

**Business outcome.** The integrated roster-and-activity package with analytics that six sources identify as the integration operators most readily pay for (`market research.md` §5).

**User/community pain relieved.**

- Chapter membership records move out of spreadsheets and into a system with formal lifecycle tracking (`problem.md` §5)
- Cases become time-accountable rather than silently aging (`problem.md` §3)
- Temporary permission overrides acquire explicit expirations rather than drifting into permanent baselines (`problem.md` §7)
- Interviews move into tracked private threads and waitlisted applicants acquire formal reactivation paths (`problem.md` §2)

**Success condition (qualitative).** Officers manage full roster lifecycles, adding and transitioning members through status changes with role reassignment requiring reasons. SLA rules enforce graduated consequences on aging cases, and temporary permissions auto-expire, surfacing as drift when they pass their deadline. Interviews occur in system-provisioned private threads; waitlists are reactivatable.

**Value realization window.** Completes the willingness-to-pay package. Communities can substantively replace their multi-surface stacks (`market research.md` §4 Community Management Workarounds).

**Confidence.** Likely for VS-011 (roster) and VS-013 (SLA) given strong competitive pressure and direct dependency chains. Aspirational for VS-012 (interview/waitlist): pain severity is 3, static-gap, with the widest dependency chain in the phase (composite 0.75).

**Investment ask.** Contributor time. Two concurrent slices possible (`plans/risk/executive-dependency-trap.md` F-5).

**Phase-specific risks.**

- **Dependency-chain length.** VS-013 (SLA) has a transitive dependency depth of 5; a delay in any upstream slice cascades. Managed by dependency discipline. No intra-phase dependencies mean slice parallelism is preserved (`plans/risk/executive-dependency-trap.md` F-4).
- **Pain severity reassessment.** VS-012 (interview/waitlist) carries the lowest composite in this phase; communities have workable DM-based alternatives. If competitive pressure increases or operator feedback shifts, re-evaluate whether VS-012 remains Phase 3 or moves to Phase 4.

**Capability gained:**
- Full roster lifecycle with officer direct management
- Application process supports interviews and waitlists
- Tickets enforce time-based SLA with graduated consequences
- Temporary permissions auto-expire

**Workflows enabled:**

- Roster management (officer direct adds, status transitions, role reassignment with reasons)
- SLA monitoring with proportional escalation (notify → flag → escalate)
- Interview thread provisioning and waitlist reactivation
- Temporary permission intent with expiration tracking

**Not yet built:**
- Compliance evaluation
- Chapter governance lifecycle (probation, archival)
- Leadership succession with context transfer

**Prerequisites:** Phase 2

**Slices in this phase:** VS-011 (roster management with role lifecycle), VS-012 (application interview and waitlist handling), VS-013 (SLA enforcement for tickets), VS-014 (temporary permission management). Completing the willingness-to-pay package here frees Phase 4 to focus on operational-maturity work that has no direct competitor yet depends on every prior phase. Detailed scoring rationale and opportunity cost per slice is in the Appendix.

---

### Phase 4: Operational Maturity

**Business outcome.** Evidence-based compliance evaluation is the anchoring capability. It ships with chapter governance lifecycle (probation and archival) and leadership succession with context transfer. The reviewed market has not addressed any of these capabilities.

**User/community pain relieved.**

- Officers recover hours daily from repetitive enforcement work explicitly identified as the primary source of volunteer burnout: manual data entry and spreadsheet cross-referencing for threshold checks (`problem.md` §6)
- Inactive or troubled chapters move through formal governance states rather than accumulating informally, and operational context transfers to new leadership rather than being lost (`problem.md` §5)

**Success condition (qualitative).** At Phase 4 completion:

- Compliance evaluation runs on schedule with OCR-parsed evidence and graduated consequences
- Probation and archival become formal chapter states with defined transitions
- Leadership succession preserves pending work and authority with predecessor-linked grants

**Value realization window.** Officers move off manual compliance work as the headline outcome. Chapters gain formal lifecycle states, and leadership transitions preserve operational context.

**Confidence.** Aspirational. Pain severity for VS-016 (compliance) is 5, the highest individual score in the roadmap, but the dependency depth (6) makes delivery timing uncertain. VS-017 (chapter governance) and VS-018 (succession) have moderate market evidence (2 sources for lifecycle administration; succession "remains implicit") (`market research.md` §4; `plans/risk/executive-market-misread.md` F-4).

**Investment ask.** Contributor time. Three slices with some intra-phase independence (compliance is prerequisite for consequences-on-compliance but not for chapter archival or succession).

**Phase-specific risks.**

- **Completeness risk for compliance scope.** Seasonal rules (time-windowed rule activation) are deferred; cross-game evidence correlation and evidence analytics are deferred, along with bulk evidence import. Managed by delivering core compliance first; schema already supports seasons (see Deferred Subsystems).
- **Succession pain-severity reassessment.** VS-018 (succession) pain severity is 3 with moderate evidence; if communities increase leadership turnover rates or explicit operator demand surfaces, re-evaluate priority.

**Capability gained:**
- Compliance evaluation runs on schedule with OCR-supported evidence processing and graduated consequences
- Chapters have full governance lifecycle with probation and archival
- Leadership transitions preserve operational context through succession chains

**Workflows enabled:**

- Scheduled compliance evaluation (collect evidence → apply rules → generate results → trigger consequences)
- Evidence submission with OCR extraction and confidence scoring
- Chapter probation entry and reinstatement
- Chapter archival with member notification and preservation of pending work and state
- Leadership succession with authority transfer and pending work handoff

**Prerequisites:** Phase 3

**Slices in this phase:** VS-016 (compliance rule evaluation with evidence), VS-017 (chapter governance lifecycle), VS-018 (leadership succession with context transfer). Phase 4 closes the proposal scope; no additional subsystem remains unaddressed within the committed Non-goals. Detailed scoring rationale and opportunity cost per slice is in the Appendix.

---

## Competitive Positioning

**Alternatives communities use today.** The reviewed market spans 50 products across six categories (`market research.md` Methodology):

- **General bots** (Dyno, Carl-bot, YAGPDB, MEE6, Arcane, Quark): moderation, roles, leveling, logs. None offer persistent trust profiles, policy versioning, or cross-workflow audit (`market research.md` §1, §7 Cross-Bot Gaps).
- **Intake tools** (Gather, Appy, Application Bot, ApplicationForms, Google Forms stacks, Typeform stacks): form submission and lightweight review. Claim-lock single-owner queuing with mandatory decision reasons is absent, and waitlist handling is equally missing (`market research.md` §2 Gap Analysis). *Gather is deprecated*.
- **Ticketing** (Ticket Tool, Helper.gg, SCNX, Discord Tickets, Modmail, ticket.pm, Mava, Oapps, DiscoDesk): ticket creation, claims, transcripts. Per-category configurable state machines with typed transitions and mandatory resolution reasons are absent across the reviewed field (`market research.md` §3 Gap Analysis).
- **Activity/roster** (Apollo, Suivix, Raid-Helper, Guild Manager, GuildForger, Throney, GuildBro, Guilds of WoW, TL Guild Manager, CoGM): attendance, event tracking, game-specific operations. No reviewed product offers a general-purpose compliance engine with chapter-scoped rules and dispute-grade audit (`market research.md` §5 Gap Analysis).
- **Permission/security** (Wick, Security Bot, Double Counter, Xenon): verification, anti-nuke, backup/restore. Declared-intent-vs-actual reconciliation is missing across the category (`market research.md` §6 Gap Analysis).
- **Broader suites** (Guildbase, TL Guild Manager, CoGM, Gamer Launch, Shivtr, Wick Bot, CommunityOne). Combine multiple surfaces but remain local to feature families. *Guilded is defunct*.

**Where the current market is weak.** The market research identifies four structural gaps consistent across every subsystem report:

1. **No shared causal chain.** Audit is "fragmented and local"; the market "repeatedly fails to offer a single decision chain spanning intake, cases, chapters, permissions, and compliance" (`market research.md` Cross-cutting Findings).
2. **No declared-intent control plane.** "Direct-mutation dashboards remain the norm"; no reviewed product offers policy versioning, preview-confirm edits, compare-and-swap, or permission-intent reconciliation (`market research.md` §6, §7).
3. **No lifecycle-grade chapter administration.** Multi-guild products treat groups as static containers; provisioning and archival are missing even in premium suites, with succession equally absent (`market research.md` §4).
4. **No general-purpose compliance engine.** Outside game-specific Throney examples, no product evaluates configurable rules against structured evidence with consequence workflows (`market research.md` §5).

**Distinctive advantage this sequence creates.** The Phase 1 governance substrate (trust, authority, audit, policy versioning) is the floor no reviewed competitor offers. Every Phase 2+ workflow inherits that defensibility. Structured applications carry mandatory reasons and causal audit, making them a different product from shared-dashboard review. Tickets inherit typed transitions tied to versioned policy, and permissions become declared intent with drift detection. Both require the Phase 1 substrate that competitors' action-centric claim flows and role-hierarchy automation lack.

**Why timing matters now.**

- **Vendor instability is actively pushing communities to look.** Gather is deprecated and Guilded is defunct. Several products also show documentation lag (`market research.md` §7, §2). Communities are currently evaluating replacements.
- **Premium gating concentrates around ownership and retention.** Claiming, transcripts, log history, exports, alliance support, and backups are frequently paid features, reinforcing vendor lock-in and migration pain (`market research.md` Cross-cutting Findings). The proposal's community-owned data model directly answers this.
- **Gap claims trace to explicit research and are time-bounded to that snapshot.** Every `gap` classification in the scoring traces to a "Gap Analysis" section in the source research; the phase-boundary risk gate (Risk Register #3) refreshes these claims against fresh market data at each phase transition (`plans/risk/executive-market-misread.md` F-3).

---

## Risk Register

This register translates the three executive risk assessments (`plans/risk/executive-market-misread.md`, `plans/risk/executive-dependency-trap.md`, `plans/risk/executive-completeness.md`) into operational monitoring. All three assessments rate LOW overall, so the argument the table makes is about monitoring rather than prediction: each row names a condition that would move the rating up and the trigger indicator that signals it firing. The Trigger indicator column is what monitoring watches for, and the Phase most affected column names where a fired trigger would land.

| # | Risk | Category | Why it matters | Mitigation / sequencing | Trigger indicator | Phase most affected |
|---|------|----------|----------------|-------------------------|-------------------|----------------------|
| 1 | **Chapter-provisioning bottleneck (VS-005).** A single slice transitively blocks roster (VS-011), compliance (VS-016), chapter governance (VS-017), and succession (VS-018). | Execution / dependency | VS-005 is the highest-fanout node; delay cascades to four downstream slices while other subsystem tracks proceed (`plans/risk/executive-dependency-trap.md` F-1). | Keep VS-005 scope tight (depth 3, Phase 2) and track it as the primary schedule risk. Other subsystem tracks continue unaffected regardless of VS-005 status. | VS-005 engineering scope expands beyond template-driven provisioning; VS-005 delivery slips >1 phase without upstream cause. | Phases 2–4 (sub-community track only). |
| 2 | **Phase 0 scope ambiguity.** Phase 0 is a one-sentence placeholder; Phase 1 implicitly depends on shared schemas (AuditEntry, PolicyVersion, PermissionIntent, AuthorityGrant). | Execution / completeness | If Phase 0 ships incomplete, Phase 1 slices inherit hidden infrastructure dependencies and intra-phase ordering constraints appear (`plans/risk/executive-completeness.md` F-2; `plans/risk/executive-dependency-trap.md` F-3). | Require engineering to publish Phase 0 acceptance criteria and shared-schema definitions before Phase 1 begins. | Phase 1 slice work begins before Phase 0 is declared complete; Phase 1 slices discover schema contracts during build. | Phase 1 (all slices); cascades. |
| 3 | **Market misread. Competitor enters with an intent-vs-actual control plane that includes policy versioning, or a cross-subsystem causal audit.** | Market / competitive | Multiple `gap` classifications depend on the absence of these capabilities in the reviewed field (`plans/risk/executive-market-misread.md` What LOW requires #2). A new competitor would reclassify gaps as `parity` or `table-stakes` and compress the competitive window. | Re-run market risk gate at each phase boundary using fresh research; treat competitive positioning as a time-bounded claim. | Any reviewed or new product publishes declared-intent reconciliation, cross-subsystem causal audit, or policy preview-confirm semantics. | All phases. |
| 4 | **Scope creep into Non-goals.** Pressure to add bot-framework breadth, moderation-first features, AI-driven operational decisions, or real-time game integration. | Strategic / scope | The four-phase differentiation depends on Non-goals holding (`proposal.md` Non-goals). Crossing any Non-goals line dilutes the integration-pattern advantage described in Competitive Positioning. | Treat Non-goals as an approval gate; any addition that crosses a Non-goals line requires explicit executive re-approval. | A proposed scope item requires moderation-first framing, AI decision-making, or general-purpose bot primitives. | All phases. |
| 5 | **Migration-tooling adoption friction.** Communities adopting the system inherit existing Discord permissions as "unintended" drift until classified. | Operational / adoption | Permission migration tooling is deferred. Adopting community first-run experience is a one-time onboarding cost not currently scoped into a user-facing slice (see Deferred Subsystems). | Scope the one-time migration tool inside VS-008 (permission intent) engineering work; flag onboarding cost in Phase 2 go-to-market communication. | Operator feedback describes first-run classification burden as a blocker; onboarding abandonment at VS-008 surface. | Phase 2 (VS-008 rollout). |
| 6 | **Pain-severity drift at Phase 4.** VS-017 (chapter governance) and VS-018 (succession) have moderate evidence (2 sources for lifecycle; succession "remains implicit rather than modeled"). | Market / prioritization | If Phase 4 pain severity is lower than assumed, or communities adopt workable manual alternatives, Phase 4 ROI weakens (`plans/risk/executive-market-misread.md` F-4; `market research.md` §4). | Re-evaluate Phase 4 composition at the Phase 3 → Phase 4 boundary; confirm pain severity has not declined. | Operator feedback in Phase 3 reports that manual succession/archival workarounds are acceptable; no new competitor pressure emerges. | Phase 4. |
| 7 | **Depth-metric ambiguity for VS-012 and VS-016.** The roadmap's dependency depth counts direct upstream, understating transitive depth for these slices. | Execution / methodology | Cosmetic only. Ordinal rankings and phase assignments unaffected (`plans/risk/executive-dependency-trap.md` F-6). Matters only if new slices are added downstream and composite scores are recomputed. | Clarify depth definition to "direct upstream" in scoring methodology; re-examine if new downstream slices are proposed. | A new proposed slice depends on VS-012 or VS-016 and inherits an artificially inflated composite score. | Phases 3–4 only if scope expands. |

---

## Approval Package

**What leadership is being asked to approve.**

1. **The phase sequence.** The four-phase ordering (Phase 0 foundations → Phase 1 governance foundation → Phase 2 core operational workflows → Phase 3 operational depth → Phase 4 operational maturity) as structurally required by dependency analysis (`plans/risk/executive-dependency-trap.md` F-4, F-5, F-7) and stable under alternative market readings (`plans/risk/executive-market-misread.md` F-8).
2. **The 18 value slices in their current phase assignments.** Slice composition and phase placement are not to be changed without re-running the dependency analysis and market misread risk gate.
3. **The scope exclusions.** The Non-goals (general-purpose bot framework, moderation-first design, feature parity, AI-driven operational decisions, real-time game integration) hold throughout the roadmap. The Deferred Subsystems (permission migration tooling as one-time engineering concern, seasonal compliance rules as schema-supported enhancement, emergency override UX within VS-002, graceful degradation mechanics in Phase 0, data portability export tooling as schema-design property) remain deferred per their documented rationale.
4. **The risk posture.** All three executive risk assessments rate LOW; the Risk Register above surfaces the seven specific findings with trigger indicators. Executive commitment includes acting on those trigger indicators when they fire.

**What remains flexible.**

- **Engineering decomposition of Phase 0.** The executive roadmap intentionally leaves Phase 0 scope to engineering; acceptance criteria are engineering-defined.
- **Intra-phase ordering.** Within Phase 1 (up to four parallel slices), Phase 2 (up to four), and Phase 3 (up to two), slice ordering is not load-bearing (`plans/risk/executive-dependency-trap.md` F-4).
- **Specific feature variants inside slice scope.** Anti-scope boundaries are explicit for each slice; within those boundaries, feature-level choices are delivery-team decisions.
- **Exact timing.** No calendar dates are committed. Value realization is expressed by phase completion, not by date, per the research recommendation to label confidence explicitly rather than commit to hard dates (`research/exec-roadmap-communication.md` Risk Communication: "explicitly labeling roadmap confidence so executives can distinguish current commitments from lower-certainty future plans").

**Review cadence.**

- **At each phase boundary:** re-run the market misread risk gate using fresh market data and confirm no new competitor has reclassified a `gap` as `parity` or `table-stakes`. Phase 4 composition gets a specific re-evaluation at the Phase 3 → Phase 4 boundary.
- **If market evidence changes materially:** re-evaluate affected slice pain severity and competitive classification (triggered by Risk #3 in the Risk Register).
- **If proposal Non-goals are pressured:** treat as an explicit executive escalation (Risk #4).
- **If VS-005 delivery risk materializes:** re-evaluate downstream cascade and communication to affected operator segments (Risk #1).

---

## Opportunity Cost Summary

The Approval Package above names what leadership is committing to; the table below names what stays broken while the roadmap executes. Rows group value slices by the operational concern they address, and each entry traces the harm back to the problem-document section where operators describe the pattern in their own terms.

| Initiative | Opportunity Cost |
|---|---|
| Identity & Trust (VS-001, VS-010) | Officers make admission and governance decisions without systematic evidence, relying on personal memory and Discord role presence, which breaks on staff turnover and across chapter boundaries (Problem §1) |
| Structured Intake (VS-006, VS-012) | Officers duplicate review effort on the same applications, and all admission decisions lack mandatory rationale, making appeals unreconstructable and producing volunteer burnout from coordination overhead (Problem §2, §9) |
| Case Management (VS-007, VS-013) | Harassment reports and appeals age silently in DM threads without durable state or ownership tracking, and disputes follow the same pattern. None carry time-based accountability, so community trust erodes when sensitive cases stall (Problem §3) |
| Governance Infrastructure (VS-002, VS-003, VS-004, VS-009, VS-015) | Decisions become unreconstructable after 45 days and configuration changes can silently corrupt in-flight operations. No system enforces scoped authority, so officers either have too much power or too little (Problem §4, §10, §13) |
| Chapter Operations (VS-005, VS-011, VS-017, VS-018) | Officers manually provision chapter infrastructure and manage rosters in spreadsheets, losing operational context on every leadership change, with cleanup cost accumulating for every chapter created (Problem §5) |
| Activity & Compliance (VS-016) | Officers spend hours daily on repetitive, error-prone enforcement work, primarily spreadsheet cross-referencing for threshold checks, explicitly the primary source of volunteer burnout (Problem §6) |
| Permission Management (VS-008, VS-014) | Permission drift silently accumulates as temporary overrides become permanent baselines, with no operator able to reason about the aggregate effect of hundreds of accumulated permission decisions (Problem §7) |

Every row above maps to operator testimony in the problem document, so the costs are observed rather than projected. The next section lists capabilities that sit outside this accounting because they are deferred beyond roadmap scope by design.

---

## Deferred Subsystems

No proposal subsystem is fully deferred. All seven subsystems appear in at least one value slice. The following capabilities within subsystems are deferred beyond the roadmap's scope or left to the engineering layer:

**Data portability export tooling.** The proposal specifies that export paths exist for all data categories in documented formats. This is a design property of the data model (community-owned schemas that are queryable and well-documented) rather than a discrete operator-facing feature. The engineering layer delivers this as a property of the Phase 0 schema design and extends it as each subsystem ships.

**Emergency override workflow.** VS-002 delivers scope enforcement. The enhanced audit trail for emergency overrides (where central staff override scope restrictions with increased visibility) is structurally available once VS-002 and VS-003 ship, but the specific UX workflow (justification capture, enhanced audit display) is not scoped into any value slice. Rationale: emergency overrides are rare events that do not warrant a dedicated value slice; the engineering layer includes this capability within the authority grant implementation.

**Permission migration tooling.** VS-008 delivers intent-vs-actual drift detection, but a community adopting the system inherits a full history of unmanaged permission decisions: all existing Discord permissions initially appear as "unintended" drift. Tooling to bulk-classify and import existing permissions into the declared-intent model is not scoped into a value slice. Rationale: migration tooling is a one-time adoption enabler, not an ongoing operational capability; the engineering layer addresses this as part of VS-008's implementation.

**Seasonal compliance rules.** VS-016 delivers compliance evaluation but defers the season field (time-windowed rule activation). Rationale: core compliance evaluation delivers the majority of value; seasonal activation adds complexity with moderate incremental value. The schema supports seasons from the start; the evaluation logic adds season awareness in a follow-on enhancement.

**Graceful degradation mechanics.** The proposal specifies four graceful-degradation mechanics as engineering-layer responsibilities:

- Deferred execution classification
- Consequence-graduated retry
- Precondition validation on recovery
- Audit-blocks-consequential-actions policy

These are structurally required for a production system but do not deliver operator-visible value independently. The engineering layer addresses these within Phase 0 infrastructure.

---

## Appendix

The appendix holds the methodology and per-slice detail supporting the phase assignments above. Approvers do not need to read it to evaluate the proposal. Reviewers auditing the ordering will find composite scores, dependency depths, and opportunity-cost language for every slice here.

### A. Scoring Methodology

**Pain severity (1–5):** How much does this address a problem operators vocally care about? Scored from market research evidence strength (5 = strong signal + active harm, 1 = speculative value).

**Competitive position:** gap (no competitor offers this; weight 1.5) / parity (1–2 competitors offer similar but limited; weight 1.0) / table-stakes (3+ competitors offer this, must-have; weight 2.0).

**Dependency depth:** Count of all upstream value slices (transitive) that must be complete before this slice can function.

**Operational risk of delay:** active-harm (problem worsening while unbuilt; weight 1.5) / static-gap (problem exists but stable; weight 1.0) / future-risk (problem emerges later; weight 0.7).

**Composite formula:** `pain_severity × competitive_weight × delay_risk_weight / (dependency_depth + 1)`

### B. Decomposition Targets

**Seven subsystems:** Identity and Trust, Intake and Adjudication, Case Management, Sub-community Lifecycle, Activity and Compliance, Permission Management, Governance.

**Four cross-cutting concerns:** Cross-workflow State Coherence, Platform Boundary, Graceful Degradation, Data Portability.

### C. Value Slice Inventory

This inventory catalogs every value slice referenced in the phase structure, naming the subsystem it belongs to, the capability it delivers, its schema objects, its state transitions, and its anti-scope boundaries. Reviewers use it to confirm phase composition; engineers use it to confirm slice boundaries before beginning build.

#### VS-001: Member onboarding with initial trust assessment

**Subsystem(s):** Identity and Trust
**Capability delivered:** Operators see every new member with a computed, inspectable trust level derived from platform signals.
**Schema objects:** Member, TrustProfile, TrustSignal (platform_metadata type)
**State transitions:** Member status lifecycle (active → suspended → active/departed; active → departed; departed → active)
**Anti-scope:**

- Officer-managed signals (identity_verification, officer_endorsement)
- Per-chapter trust profiles
- Trust computation customization
- Signal decay management

#### VS-002: Scoped authority with enforcement

**Subsystem(s):** Governance
**Capability delivered:** Officers receive explicit authority grants for defined scopes; the system denies out-of-scope operations with clear explanations.
**Schema objects:** AuthorityGrant
**State transitions:** Grant/revoke lifecycle; scope check on every operational action
**Anti-scope:**

- Succession chain (predecessor_grant_id)
- Emergency override workflow
- Automatic authority from ChapterRole assignment

#### VS-003: Audit trail with causal correlation

**Subsystem(s):** Governance (cross-cutting)
**Capability delivered:** Every operational decision is recorded immutably with actor, context, policy version, and causal chain identifiers. Reconstructable months later.
**Schema objects:** AuditEntry (with correlation_id, causation_id)
**State transitions:** Append-only; no state machine
**Anti-scope:**

- CQRS read model materialization
- Retention management interface
- Export tooling
- Operator dashboard for audit queries

#### VS-004: Policy versioning with configuration safety

**Subsystem(s):** Governance
**Capability delivered:** Configuration changes are versioned with preview-confirm workflow and optimistic concurrency; in-flight operations are protected from mid-stream rule changes.
**Schema objects:** PolicyVersion
**State transitions:** Version creation with supersedes chain; preview → confirm lifecycle
**Anti-scope:**

- Rollback automation
- Bulk policy migration
- Cross-scope policy comparison
- Policy diff visualization

#### VS-005: Chapter provisioning from templates

**Subsystem(s):** Sub-community Lifecycle
**Capability delivered:** Operators create new chapters from configurable templates; Discord resources (channels and roles with their categories) are provisioned through an approval gate.
**Schema objects:** ChapterTemplate, Chapter, ChapterTransition
**State transitions:** proposed → provisioning → active
**Anti-scope:**

- Probation or archival states
- Succession
- Chapter-scoped compliance rules
- Roster management
- Chapter configuration editing

#### VS-006: Structured application intake with reviewer ownership

**Subsystem(s):** Intake and Adjudication; Identity and Trust (trust context in review)
**Capability delivered:** Members submit structured applications, and a single reviewer claims and evaluates each one with trust context and mandatory decision reasons. Reviewer collisions are prevented by the claim lock.
**Schema objects:** FormDefinition, Application, ApplicationReview
**State transitions:** submitted → queued → claimed → in_review → approved / denied; any pre-decision state → withdrawn
**Anti-scope:**

- Interview flow
- Waitlist
- Form branching logic
- Chapter application support depends on chapters existing (VS-005 or equivalent)

#### VS-007: Ticket creation and case lifecycle

**Subsystem(s):** Case Management
**Capability delivered:** Officers create and manage tickets with category-specific state machines and privacy controls; assignment tracks ownership and resolution requires mandatory reasons.
**Schema objects:** TicketCategory, Ticket, TicketMessage, TicketTransition
**State transitions:** Category-defined (default: open → triaged → assigned → resolved → closed; escalation path)
**Anti-scope:**

- SLA enforcement
- Cross-ticket linking (related_ticket_ids)
- Cross-ticket pattern detection

#### VS-008: Permission intent and drift detection

**Subsystem(s):** Permission Management
**Capability delivered:** Operators declare intended permission state with reasons; the system detects when Discord permissions diverge and surfaces drift for explicit resolution.
**Schema objects:** PermissionIntent, PermissionDrift
**State transitions:** Drift lifecycle (detected → acknowledged / reconciled / accepted)
**Anti-scope:**

- Temporary permission expiration
- Migration tooling for existing unmanaged Discord permissions
- Automated reconciliation scheduling

#### VS-009: Configurable operator notifications

**Subsystem(s):** Governance
**Capability delivered:** Operators configure notification triggers, scoped recipients, delivery channels, actionable vs. informational distinction, and causal grouping to prevent notification fatigue.
**Schema objects:** NotificationRule
**State transitions:** None (configuration object; triggers fire on AuditEntry events)
**Anti-scope:**

- Notification analytics
- Digest scheduling
- Notification muting or snooze
- Notification templates beyond structured content

#### VS-010: Advanced trust management

**Subsystem(s):** Identity and Trust
**Capability delivered:** Officers record trust signals (identity verification and endorsements, plus compliance history). Operators configure trust computation per scope (weights and thresholds with decay rules), and chapter configurations override global defaults.
**Schema objects:** TrustSignal (all types), TrustComputationConfig
**State transitions:** TrustProfile recomputation on signal change or config change; trust level transitions audited
**Anti-scope:**

- Automated cross-chapter trust recognition
- Trust signal expiration management UI
- Trust analytics or trending

#### VS-011: Roster management with role lifecycle

**Subsystem(s):** Sub-community Lifecycle
**Capability delivered:** Officers manage chapter rosters. They add members directly and assign chapter-defined roles, managing status lifecycle (active, on_leave, under_review, removed) with mandatory reasons.
**Schema objects:** ChapterRole, RosterEntry, RosterTransition
**State transitions:** RosterEntry status (active → on_leave / under_review / removed; on_leave → active / removed; under_review → active / removed)
**Anti-scope:**

- Compliance-triggered status changes
- Succession workflow
- Automated roster cleanup
- Cross-chapter roster comparison

#### VS-012: Application interview and waitlist handling

**Subsystem(s):** Intake and Adjudication
**Capability delivered:** Reviewers request interviews with system-provisioned private threads; applications can be waitlisted and reactivated by reviewers.
**Schema objects:** Application (additional states: interview, waitlisted), ApplicationReview (additional actions: request_interview, waitlist)
**State transitions:** in_review → interview → approved / denied / waitlisted; waitlisted → claimed
**Anti-scope:**

- Automated waitlist prioritization
- Bulk waitlist management
- Interview scheduling

#### VS-013: SLA enforcement for tickets

**Subsystem(s):** Case Management
**Capability delivered:** Per-category SLA rules with graduated time-based thresholds trigger proportional consequences:

- Notify owner
- Notify scope
- Flag for review
- Auto-escalate

**Schema objects:** TicketCategory (sla_rules extension), AuditEntry (action_type: sla_triggered)
**State transitions:** SLA-triggered transitions within category state machines (e.g., assigned → escalated)
**Anti-scope:**

- SLA analytics dashboard
- SLA template library
- Custom SLA consequence actions

#### VS-014: Temporary permission management

**Subsystem(s):** Permission Management
**Capability delivered:** Operators create time-limited permission intents; expired overrides automatically surface as drift, preventing "temporary becomes permanent."
**Schema objects:** PermissionIntent (temporary, expires_at fields), PermissionDrift (expired override detection)
**State transitions:** Intent expiration → drift entry creation cycle
**Anti-scope:**

- Automated permission rotation
- Bulk temporary grant management
- Temporary permission renewal workflow

#### VS-015: Cross-subsystem operational views

**Subsystem(s):** Governance (cross-cutting)
**Capability delivered:** Operators query operational history across all subsystems through materialized read models, including causal chain views and scope-filtered projections.
**Schema objects:** Read model projections from AuditEntries (no new write-path schema)
**State transitions:** None (read-only materialized views; updated asynchronously from event stream)
**Anti-scope:**

- Custom query builder
- Export from read model
- Analytics or aggregation beyond operational history
- Real-time streaming

#### VS-016: Compliance rule evaluation with evidence

**Subsystem(s):** Activity and Compliance
**Capability delivered:** Chapter-scoped compliance rules evaluate members on schedule against submitted evidence (OCR-parsed screenshots and structured feeds from game APIs or manual reports); violations trigger graduated consequences.
**Schema objects:** ComplianceRule, EvidenceSubmission, ComplianceEvaluation
**State transitions:** Evaluation results trigger RosterEntry status changes per consequence level (notification_only / flag_for_review / auto_probation)
**Anti-scope:**

- Seasonal rules (season field deferred)
- Cross-game evidence correlation
- Evidence analytics
- Bulk evidence import

#### VS-017: Chapter governance lifecycle

**Subsystem(s):** Sub-community Lifecycle
**Capability delivered:** Chapters can enter probation (governance concerns) and proceed through archival with member notification and pending work resolution, preserving state throughout.
**Schema objects:** Chapter (additional states: probation, archiving, archived), ChapterTransition
**State transitions:** active → probation → active / archiving → archived
**Anti-scope:**

- Automated inactivity detection triggering probation
- Chapter health scoring
- Cross-chapter governance dashboard

#### VS-018: Leadership succession with context transfer

**Subsystem(s):** Sub-community Lifecycle; Governance
**Capability delivered:** When a succession-triggering role holder departs, pending decisions and open work are identified, and authority transfers to the successor with a predecessor link. Operational context is preserved throughout.
**Schema objects:** AuthorityGrant (predecessor_grant_id), ChapterRole (triggers_succession)
**State transitions:** Departure detection → successor grant creation → pending work transfer/flagging
**Anti-scope:**

- Automated successor selection
- Succession scheduling or term limits
- Cross-chapter succession coordination

### D. Per-Slice Scoring Detail

Scoring detail accompanies each slice inside its phase bucket so reviewers can audit the composite priority that placed it. The four inputs (pain severity, competitive position, dependency depth, and operational risk of delay) follow the methodology in Section A, and the opportunity cost language mirrors the Opportunity Cost Summary table so the two views can be cross-checked.

#### Phase 1

The four Phase 1 slices share dependency depth 0 and all evaluate as structural gaps; scoring ranks them by the severity and velocity of the pain each leaves unaddressed.

##### VS-001: Member onboarding with initial trust assessment

- **Pain severity:** 4. Reviewers rarely see trust context where decisions happen; three independent source categories (applications and general-bot reports, plus platforms) confirm the gap. False-positive complaints in Wick and Double Counter show active harm from coarse screening. (`market research.md` §1: "Reviewers rarely see trust context where decisions happen". Strong evidence; false-positive complaints. Moderate evidence)
- **Competitive position:** gap. No reviewed competitor offers persistent, inspectable trust profiles with deterministic recomputation. The market research calls the proposal's first-class trust subsystem a structural difference from every reviewed product (`market research.md` §1 differentiation).
- **Dependency depth:** 0. No upstream value slices
- **Operational risk of delay:** active-harm. False positives in current verification tools actively reject legitimate users. Officers make admission decisions without systematic evidence, which degrades across staff turnover and chapter boundaries. (Problem §1: "calibrating and maintaining them across organizational boundaries, staff turnover, and time")
- **Composite priority:** 9.0
- **Opportunity cost:** By not building this yet, officers continue making trust decisions about members based on personal memory and Discord role presence, which breaks across chapter boundaries and on staff turnover (Problem §1).

##### VS-003: Audit trail with causal correlation

- **Pain severity:** 4. Audit is fragmented and local across the market: tickets are transcript-first and permissions are event-log-first. Platforms expose local history rather than cross-subsystem chains. Retention is gated or limited across Quark, Dyno, MEE6, YAGPDB, and Guild Manager. (`market research.md` §7: "Audit is fragmented and local". Strong evidence; §3: "Audit remains transcript-first instead of action-stream first". Strong evidence, 5 sources; §7: "Retention and export are uneven or gated". Strong evidence)
- **Competitive position:** gap. "The market repeatedly fails to offer a single decision chain spanning intake, cases, chapters, permissions, and compliance." No competitor has causal correlation across subsystem boundaries. (`market research.md` cross-cutting findings)
- **Dependency depth:** 0. No upstream value slices
- **Operational risk of delay:** active-harm. Discord's 45-day audit log cap means disputes that resurface after two months have no evidence trail. Officers cannot prove what happened or what policy governed a past decision, and past inputs are similarly lost. (Problem §4: "45-day retention cap, which is too short for seasonal guild operations, officer misconduct reviews, or disputes that resurface months later")
- **Composite priority:** 9.0
- **Opportunity cost:** By not building this yet, decisions become unreconstructable after Discord's 45-day audit log expires, and officers cannot prove what happened or what policy governed a disputed decision (Problem §4).

##### VS-004: Policy versioning with configuration safety

- **Pain severity:** 4. No reviewed product offers policy versioning, diff previews, compare-and-swap edits, or last-known-version enforcement. Most dashboards apply settings directly with no temporal protection for in-flight operations. (`market research.md` §7: "no public evidence of policy versioning, diff previews, compare-and-swap edits, or last-known-version enforcement". Strong evidence; "Direct-mutation dashboards remain the norm". Strong evidence)
- **Competitive position:** gap. No competitor offers preview-confirm workflows or version pinning for operational configuration, with optimistic concurrency equally absent. (`market research.md` §7 governance gap analysis)
- **Dependency depth:** 0. No upstream value slices
- **Operational risk of delay:** active-harm. Configuration changes on a live server can silently corrupt in-flight operations. A form change mid-review alters the meaning of pending submissions. Concurrent operator edits produce decisions made against phantom state. (Problem §13: "a configuration change on a live system can silently corrupt the semantic integrity of in-flight operations"; "the change succeeds silently")
- **Composite priority:** 9.0
- **Opportunity cost:** By not building this yet, configuration changes can silently corrupt in-flight operations. Changing an application form mid-review can alter the meaning of pending submissions without any error signal (Problem §13).

##### VS-002: Scoped authority with enforcement

- **Pain severity:** 3. Guild Manager and TL Guild Manager offer 40+ granular permissions, but these operate as role/admin capability sets rather than scoped authority grants. The permissions gap analysis confirms scoped grants are absent. Demand for governance control is strong but scoped authority specifically is a moderate signal. (`market research.md` §6: "scoped grants...are absent across the reviewed field" within strong governance gap analysis; §6: Guild Manager, TL Guild Manager, CoGM offer granular permissions but not scoped delegation)
- **Competitive position:** gap. "Drift detection, preview-confirm changes, scoped grants, and optimistic concurrency are absent across the reviewed field." No competitor expresses authority as scoped delegation rather than ranked hierarchy. (`market research.md` §6 permissions gap analysis)
- **Dependency depth:** 0. No upstream value slices
- **Operational risk of delay:** static-gap. Communities work around the limitation using Discord's ranked role hierarchy, pushing toward either over-centralization or over-granting. The problem is stable. Officer access patterns don't worsen over time absent new chapters. (Problem §10: "often pushes communities toward either over-centralization or over-granting")
- **Composite priority:** 4.5
- **Opportunity cost:** By not building this yet, communities rely on Discord's ranked hierarchy model, pushing officers toward either over-centralization or over-granting because the platform cannot express "only within your chapter" (Problem §10).

#### Phase 2

These seven slices inherit Phase 1 capabilities and compete on markets where existing products already operate, so scoring weighs competitive pressure against the dependency cost carried from Phase 1.

##### VS-007: Ticket creation and case lifecycle

- **Pain severity:** 5. Time/status rigor is shallow across the market: the gap analysis confirms per-category configurable state machines are effectively missing, and mandatory resolution reasons are rare across Ticket Tool, Helper.gg, Discord Tickets, and SCNX. Assignment is brittle or paywalled. (`market research.md` §3: "per-category configurable state machines are effectively missing". Strong evidence; "mandatory resolution reasons are rare". Strong evidence; "Assignment is brittle or paywalled". Moderate evidence)
- **Competitive position:** table-stakes. Nine sources compete (Ticket Tool, Helper.gg, SCNX, Discord Tickets, Modmail, ticket.pm, Mava, Oapps, DiscoDesk). Not having case management makes the system non-viable for communities that handle appeals, harassment reports, and disputes. (`market research.md` §3: 9 competing sources)
- **Dependency depth:** 3. VS-001 (reporters/subjects are members), VS-002 (officer authority for assignment/escalation), VS-003 (transitions generate audit entries)
- **Operational risk of delay:** active-harm. Harassment reports and appeals live in ephemeral DM threads with no durable state or ownership tracking, and disputes follow the same pattern. Stalled reports erode community trust; stalled appeals leave members in limbo. (Problem §3: "A stalled harassment report erodes community trust; a stalled appeal leaves a member in limbo")
- **Composite priority:** 3.75
- **Opportunity cost:** By not building this yet, sensitive case workflows live in ephemeral DM threads without durable state or ownership tracking (Problem §3).

##### VS-006: Structured application intake with reviewer ownership

- **Pain severity:** 5. Reviewer collision prevention is essentially absent; Gather, Appy, Application Bot, and ApplicationForms all lack published claim-lock or single-owner queueing. Waitlists and appeals remain rare across the reviewed market. Mandatory decision reasons are similarly absent, and Discord-native review breaks down on platform constraints. (`market research.md` §2: "Reviewer collision prevention is essentially absent". Strong evidence; "Waitlists, appeals, and required decision reasons remain rare". Strong evidence; "Discord-native review breaks down". Strong evidence)
- **Competitive position:** table-stakes. Eight sources compete (Gather, Appy, Application Bot, ApplicationForms, Google Forms stacks, Typeform stacks, Guildbase, Guild Manager). Structured intake is a core requirement for guild management. (`market research.md` §2: 8 competing sources; "Demand for better application tooling is very well validated")
- **Dependency depth:** 4. VS-001 (applicant trust context), VS-002 (reviewer authority over target scope), VS-003 (transitions generate audit entries), VS-004 (form definition versioning)
- **Operational risk of delay:** active-harm. Two reviewers independently evaluate the same application without knowing the other started, duplicating scarce volunteer effort. Conflicting decisions require additional coordination. (Problem §2: "concurrent access introduces a mutual-exclusion problem"; Problem §9: "every duplicated review or conflicting decision is attention spent on coordination overhead")
- **Composite priority:** 3.0
- **Opportunity cost:** By not building this yet, officers duplicate review effort on the same applications and all admission decisions lack mandatory rationale. Making appeals unreconstructable (Problem §2, §9).

##### VS-005: Chapter provisioning from templates

- **Pain severity:** 4. Chapter lifecycle automation is still missing; the activity report and general-bot report explicitly confirm this gap. Communities assemble subgroup operations from Discord alongside a patchwork of spreadsheets and bots. (`market research.md` §4: "Chapter lifecycle automation is still missing". Strong evidence; "Communities still assemble subgroup operations from multiple surfaces". Strong evidence)
- **Competitive position:** table-stakes. Eight sources compete on multi-unit management (Guild Manager, GuildForger, Throney, Guilds of WoW, TL Guild Manager, CoGM, Gamer Launch, Shivtr). A guild management platform without chapter support cannot serve organizations running multiple chapters. (`market research.md` §4: 8 competing sources)
- **Dependency depth:** 3. VS-001 (actors are members), VS-002 (approval authority at parent scope), VS-003 (transitions generate audit entries)
- **Operational risk of delay:** active-harm. Officers manually create channels with their categories and roles for each new chapter, accumulating inconsistent structures and untracked cleanup cost. Every new chapter increases future governance complexity. (Problem §5: "every subgroup created today increases future cleanup cost")
- **Composite priority:** 3.0
- **Opportunity cost:** By not building this yet, officers manually provision chapter infrastructure, accumulating inconsistent structures and untracked cleanup cost for every new sub-community (Problem §5).

##### VS-008: Permission intent and drift detection

- **Pain severity:** 4. Declared-state reconciliation is under-served despite repeated gap analysis across five source categories. Governance visibility stops at logs or backups. Xenon can restore but not reconcile live state against declared intent. (`market research.md` §6: "Declared-state reconciliation appears under-served". Strong evidence, 5 sources; "Governance visibility stops at logs or backups". Strong evidence)
- **Competitive position:** gap. No reviewed competitor offers an intent-vs-actual reconciliation model. Xenon offers backup/restore but not declared-intent drift detection. Guild suites offer granular permissions but not audit-grade intent tracking. (`market research.md` §6: "none expose an intent-vs-actual control plane"; Xenon comparison)
- **Dependency depth:** 3. VS-001 (actors are members), VS-002 (authority over affected scope), VS-003 (drift resolutions generate audit entries)
- **Operational risk of delay:** active-harm. Permission drift silently accumulates as temporary overrides become inherited baselines. Every urgent crisis exception increases the gap between intended and actual state. (Problem §7: "every urgent exception during a crisis becomes tomorrow's inherited baseline"; "accumulated unreviewed history")
- **Composite priority:** 2.25
- **Opportunity cost:** By not building this yet, permission drift silently accumulates with no concept of intended state against which actual state can be audited (Problem §7).

##### VS-009: Configurable operator notifications

- **Pain severity:** 3. Notification volume is explicitly identified as a distinct burnout mechanism from process rigor. Current products either over-notify (cascading alerts per downstream effect) or under-notify (no alert when action is needed). Market products have fixed notification patterns rather than configurable triggers. (`market research.md` §7: notification behavior embedded in various products but not as configurable system; Problem §9: "notification volume is a distinct burnout mechanism from process rigor")
- **Competitive position:** gap. No competitor offers causal grouping of notifications (per_root_cause batching) or configurable trigger-recipient-channel rules with actionable vs. informational distinction. (`market research.md` §7: products embed notifications but none market a configurable notification plane)
- **Dependency depth:** 2. VS-002 (authority scopes determine recipients), VS-003 (audit events serve as triggers)
- **Operational risk of delay:** active-harm. Officers either receive no system-generated awareness of events requiring action, or receive cascading independent notifications for every downstream effect of a single decision. Both patterns erode attention budgets. (Problem §9: "notification volume from automated cascades is an attention cost that exists independently of how many decisions require human involvement")
- **Composite priority:** 2.25
- **Opportunity cost:** By not building this yet, officers either miss events requiring action or receive cascading notifications for every downstream effect of a single decision, eroding volunteer attention budgets (Problem §9).

##### VS-015: Cross-subsystem operational views

- **Pain severity:** 3. The market repeatedly fails to offer a single decision chain spanning intake, cases, chapters, permissions, and compliance. Audit is fragmented and local. Operators piece together history across multiple bots and dashboards, with spreadsheets filling the gaps. (`market research.md` cross-cutting: "the market repeatedly fails to offer a single decision chain"; §7: "Audit is fragmented and local". Strong evidence)
- **Competitive position:** gap. No competitor offers cross-subsystem materialized operational views. Cross-workflow visibility is a documented gap across all six market research reports. (`market research.md` cross-cutting findings; §7 governance gap)
- **Dependency depth:** 1. VS-003 (audit entries provide the event stream to materialize)
- **Operational risk of delay:** static-gap. Operators currently piece together member history from multiple sources. Painful but stable. The workaround functions, just slowly. Value increases as more subsystems generate events. (Problem §12: "no single system can answer 'what is this member's full operational history?'")
- **Composite priority:** 2.25
- **Opportunity cost:** By not building this yet, answering "what is this member's full operational history?" requires manually checking multiple systems and correlating events by hand (Problem §12).

##### VS-010: Advanced trust management

- **Pain severity:** 3. Demand for a richer operator trust view is present across five source categories, but officer-managed signals specifically have moderate direct evidence. The gap is real but less urgent than initial screening (VS-001). (`market research.md` §1: "Demand for a richer operator trust view is present but indirect". Strong evidence, 5 sources; "none of them expose inspectable trust signals, deterministic trust recomputation, or chapter-specific trust portability")
- **Competitive position:** gap. No competitor offers configurable trust computation with per-scope signal weights and decay rules, let alone operator-visible derivation. (`market research.md` §1 differentiation: durable, inspectable, scope-specific, auditable through recomputation history)
- **Dependency depth:** 4. VS-001 (trust profiles exist), VS-002 (officer authority to record signals), VS-003 (signal recording and trust recomputation generate audit entries), VS-004 (policy versioning governs TrustComputationConfig changes)
- **Operational risk of delay:** static-gap. Trust calibration is a persistent challenge, but communities have workarounds (manual officer judgment, role-based indicators). The gap does not worsen rapidly absent new chapters. (Problem §1: existing verification tools provide coarse filtering)
- **Composite priority:** 0.9
- **Opportunity cost:** By not building this yet, trust assessment remains a coarse verification check rather than a nuanced gradient informed by officer observations and chapter-specific compliance signals (Problem §1).

#### Phase 3

Slice placement here reflects the willingness-to-pay pressure that makes the integrated roster-and-activity package the phase to close, with composite scores compressed by longer dependency chains inherited from Phase 2.

##### VS-011: Roster management with role lifecycle

- **Pain severity:** 4. Communities still assemble subgroup operations from multiple surfaces. Six sources identify the integrated roster-and-activity package with analytics as the integration operators most readily pay for. Officers manage rosters in spreadsheets, losing context on every staff change. (`market research.md` §4: "Communities still assemble subgroup operations from multiple surfaces". Strong evidence; §5: "strongest willingness-to-pay signal is for integrated roster plus activity plus analytics". Strong evidence, 6 sources)
- **Competitive position:** table-stakes. Guild Manager, Throney, GuildForger, and TL Guild Manager all offer roster management. Not having roster management makes the chapter system non-functional for day-to-day operations. (`market research.md` §4: 8 sources compete on multi-unit management; §5: 6 sources package activity with roster administration)
- **Dependency depth:** 4. VS-001 (members), VS-002 (officer authority for roster actions), VS-003 (transitions generate audit entries), VS-005 (chapters must exist)
- **Operational risk of delay:** active-harm. Chapter membership records live in spreadsheets or Discord role presence, without lifecycle tracking or role-assignment history, and with no auditable status transitions either. Officer time spent on manual roster maintenance is a recurring cost. (Problem §5: "succession problem is not just 'transfer a role'. It is 'transfer operational context'")
- **Composite priority:** 2.4
- **Opportunity cost:** By not building this yet, chapter membership records live in spreadsheets or Discord role presence, with no lifecycle tracking or auditable role history (Problem §5).

##### VS-013: SLA enforcement for tickets

- **Pain severity:** 4. Cases can age in assigned states with no systemic visibility. The ticketing gap analysis explicitly notes shallow time/status rigor and the absence of per-category response time requirements. Stalled harassment reports erode community trust. (`market research.md` §3: "per-category configurable state machines are effectively missing". Strong evidence; implicit in gap analysis: no time-based enforcement; Problem §3: "cases silently age without accountability")
- **Competitive position:** gap. No competitor offers per-category SLA rules with graduated time-based consequences. SCNX has timeout features but not configurable graduated escalation tied to category state machines. (`market research.md` §3: gap analysis; no product offers operator-configured SLA thresholds with proportional consequences)
- **Dependency depth:** 5. VS-001, VS-002, VS-003 (through VS-007), VS-007 (tickets must exist), VS-009 (SLA triggers use notification system)
- **Operational risk of delay:** active-harm. Cases silently age with no automated accountability. A harassment report stalling for a week has no escalation path. Time-based monitoring is entirely manual, competing for the same officer attention SLAs would protect. (Problem §3: "A stalled harassment report erodes community trust"; "time-based monitoring introduces its own attention cost")
- **Composite priority:** 1.5
- **Opportunity cost:** By not building this yet, cases silently age in assigned states with no time-based accountability. A harassment report stalling for a week has no automated escalation path (Problem §3).

##### VS-014: Temporary permission management

- **Pain severity:** 3. Governance visibility stops at logs or backups, and the permissions gap analysis confirms no product tracks permission temporality. The specific pain of forgotten temporary overrides is a subset of the broader drift problem. (`market research.md` §6: "Governance visibility stops at logs or backups". Strong evidence; Problem §7: temporary overrides becoming permanent)
- **Competitive position:** gap. No competitor offers temporary permission intents with automatic expiration tracking. This extends the gap already identified in declared-intent models. (`market research.md` §6: no product offers intent-vs-actual reconciliation, let alone temporal intent tracking)
- **Dependency depth:** 4. VS-001, VS-002, VS-003 (through VS-008), VS-008 (permission intents must exist)
- **Operational risk of delay:** active-harm. Every temporary permission override that lacks an explicit expiration date becomes a permanent fixture. The accumulation actively worsens permission state complexity over time. (Problem §7: "every urgent exception during a crisis becomes tomorrow's inherited baseline")
- **Composite priority:** 1.35
- **Opportunity cost:** By not building this yet, every temporary permission override requires manual tracking and manual cleanup, and forgotten overrides silently become permanent baseline (Problem §7).

##### VS-012: Application interview and waitlist handling

- **Pain severity:** 3. Waitlists and appeals remain rare across the application market, with required decision reasons equally scarce. The gap analysis explicitly calls out missing waitlist handling. Communities, however, work around this with DMs for interviews and informal tracking for waitlists. (`market research.md` §2: "Waitlists, appeals, and required decision reasons remain rare". Strong evidence; gap analysis)
- **Competitive position:** gap. No competitor offers structured waitlist with reactivation or system-provisioned interview threads. Gather is the closest with richer state models but is deprecated. (`market research.md` §2 gap analysis; Gather deprecated)
- **Dependency depth:** 5. VS-001, VS-002, VS-003, VS-004 (through VS-006), VS-006 (application intake must exist)
- **Operational risk of delay:** static-gap. Officers handle interviews via DMs and waitlists via informal tracking. Functional but not systematic. The workaround does not worsen over time. (Problem §2: interview and waitlist are part of the application lifecycle)
- **Composite priority:** 0.75
- **Opportunity cost:** By not building this yet, interviews happen in untracked DMs and waitlisted applicants are managed informally, with no system visibility into who is waiting or why (Problem §2).

#### Phase 4

This phase carries the deepest operational work and the longest dependency chains; scoring trades the headline pain severity of compliance against the delivery timing risk that dependency depth introduces.

##### VS-016: Compliance rule evaluation with evidence

- **Pain severity:** 5. Spreadsheet and manual-process fatigue is a core recurring complaint, and outside game-specific tools a general-purpose compliance engine is still missing. Screenshot evidence is common but under-structured, with dispute-grade audit chains for compliance equally rare. (`market research.md` §5: "Spreadsheet and manual-process fatigue is a core recurring complaint". Strong evidence; "A general-purpose compliance engine is still missing". Strong evidence; "Screenshot evidence is common but under-structured". Strong evidence; "Dispute-grade audit chains for compliance are rare". Strong evidence)
- **Competitive position:** table-stakes. Nine sources compete on activity tracking (Apollo, Suivix, Raid-Helper, Guild Manager, GuildForger, Throney, GuildBro, Guilds of WoW, TL Guild Manager). Activity tracking is a core requirement for guild management. (`market research.md` §5: 9 competing sources)
- **Dependency depth:** 6. VS-001, VS-002, VS-003, VS-005 (through VS-011), VS-004 (rule versioning via PolicyVersion), VS-011 (roster entries identify who to evaluate)
- **Operational risk of delay:** active-harm. Officers spend hours daily on manual data entry and spreadsheet cross-referencing for threshold checks. This is explicitly identified as the primary source of volunteer burnout. (Problem §6: "officer time spent on data entry, cross-referencing, and threshold checks. Work that is repetitive, error-prone, and a primary source of volunteer burnout")
- **Composite priority:** 2.14
- **Opportunity cost:** By not building this yet, officers spend hours daily on manual data entry and spreadsheet cross-referencing for threshold checks, the primary source of volunteer burnout (Problem §6).

##### VS-018: Leadership succession with context transfer

- **Pain severity:** 3. Succession and delegated-local-authority continuity remain implicit rather than modeled across the market. Multi-guild products support team management but not stateful transfer of pending work and authority. (`market research.md` §4: "Succession and delegated-local-authority continuity remain implicit rather than modeled". Moderate evidence)
- **Competitive position:** gap. No reviewed product models succession as a first-class operation with predecessor-linked authority grants and pending work transfer. (`market research.md` §4: no product offers stateful succession)
- **Dependency depth:** 5. VS-001, VS-002, VS-003, VS-005 (through VS-011), VS-011 (roster identifies succession-triggering role holders)
- **Operational risk of delay:** static-gap. Leadership transitions are handled manually. Functional but context-lossy. The successor must reconstruct governance state from memory and scattered records. The problem is stable unless leadership turnover increases. (Problem §5: "transfer operational context, pending decisions, and member trust without a gap in governance")
- **Composite priority:** 0.75
- **Opportunity cost:** By not building this yet, when a chapter leader departs, pending decisions are orphaned and the successor must reconstruct governance state from memory without access to the prior operator's accumulated context (Problem §5).

##### VS-017: Chapter governance lifecycle

- **Pain severity:** 3. Lifecycle-grade chapter administration is under-monetized; provisioning and archival are missing even in premium suites, with lifecycle governance equally absent. The market signal is moderate; only two sources directly evidence the gap. (`market research.md` §4: "lifecycle-grade chapter administration itself is under-monetized". Moderate evidence, 2 sources; gap analysis)
- **Competitive position:** gap. No competitor offers probation and archival as explicit lifecycle states with governance transitions. Multi-guild products treat groups as static containers. (`market research.md` §4: "provisioning, archival, and lifecycle governance are missing even in premium suites")
- **Dependency depth:** 5. VS-001, VS-002, VS-003, VS-005 (through VS-011), VS-011 (rosters must exist for archival member notification and pending work resolution)
- **Operational risk of delay:** future-risk. Chapter governance becomes relevant as the community ages and chapters naturally decline. Currently, dead channels accumulate without formal governance. The problem grows with community age and chapter count but is not actively harmful today. (Problem §5: "every subgroup created today increases future cleanup cost")
- **Composite priority:** 0.525
- **Opportunity cost:** By not building this yet, inactive or troubled chapters accumulate without formal governance intervention, and archival is an ad-hoc manual process that risks losing operational history (Problem §5).
