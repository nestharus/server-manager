# Non-negotiable Violations: Executive Roadmap

**Total violations: 193**

## Violations

### V-1. Em dashes

**Category:** Em dash characters  
**Fix guidance:** Replace each em dash with a period, colon, parentheses, or a structurally different sentence break.

- Line 5: **Strategic outcome.** Deliver a Discord-native guild management platform that treats identity/trust, intake, case management, sub-community lifecycle, activity/compliance, permissions, and governance as one unified operational system with causal auditability across subsystems — the structural gap that no reviewed competitor closes (`market research.md` cross-cutting: "the market repeatedly fails to offer a single decision chain spanning intake, cases, chapters, permissions, and compliance"). The system treats community data as community-owned, queryable, and exportable by design (`proposal.md` Non-goals; `market research.md` §7: "Retention and export are uneven or gated").
- Line 9: - **Competitive window is open.** Gather is deprecated, Guilded is shut down, and ticketing and permissions markets are crowded but shallow — assignment is "brittle or paywalled," audit is "fragmented and local," and "declared-state reconciliation appears under-served" across 5+ sources (`market research.md` §2, §3, §6, §7, Cross-cutting Findings). Vendor instability is actively pushing communities to look for new platforms.
- Line 13: **Approval ask.** Commit contributor effort and resource attention to the four-phase sequence as scoped — Phase 0 (engineering foundations), Phase 1 (governance foundation), Phase 2 (core operational workflows), Phase 3 (operational depth), Phase 4 (operational maturity). This means endorsing the 18 value slices in their current phase assignments, accepting the explicit scope exclusions (bot-framework breadth, moderation-first design, AI-driven operational decisions, real-time game integration — `proposal.md` Non-goals), and honoring the review cadence defined in the Approval Package section.
- Line 18: - **After Phase 2:** Operators can run structured applications with reviewer ownership, manage tickets through category-specific state machines, provision chapters from templates, detect permission drift, and configure notifications — the operational core that eight application tools, nine ticket tools, and eight multi-unit suites compete on today (`market research.md` §2, §3, §4).
- Line 19: - **After Phase 3:** Officers can manage rosters, enforce SLAs with graduated consequences, handle interviews and waitlists, and track temporary permissions — the integrated-roster-plus-activity package that "six sources" show as the strongest willingness-to-pay signal (`market research.md` §5).
- Line 20: - **After Phase 4:** Chapters have full governance lifecycle (probation, archival) with leadership succession and evidence-based compliance evaluation — the complete proposal scope.
- Line 34: The four phases tell one coherent story — not four independent tracks but a single sequence in which each phase unlocks operational leverage the prior phase could not deliver and reduces a class of risk the prior phase could not contain.
- Line 36: **Phase 1 — buy defensibility first.** Before operator workflows, the system needs trust profiles, scoped authority, immutable causal audit, and preview-confirm policy changes. These four capabilities are not features; they are the governance substrate every subsystem consumes. The market confirms they are missing across the reviewed field: no product offers "persistent, inspectable trust signals with deterministic recomputation," "scoped grants," "an intent-vs-actual control plane," or "policy versioning with compare-and-swap edits" (`market research.md` §1, §6, §7). Building the substrate first is both the competitive bet (differentiated floor no competitor offers) and the risk-containment bet (decisions made in Phase 2 onward are reconstructable, reversible, and auditable from day one).
- Line 38: **Phase 2 — capture the operational table-stakes crowd.** With the governance substrate in place, Phase 2 builds the workflows that eight application tools, nine ticket tools, and eight multi-unit suites monetize today (`market research.md` §2, §3, §4). Competing on features these markets already serve requires the Phase 1 substrate to distinguish the product — application intake with reviewer ownership plus structured audit is a different product from application intake with shared-dashboard review. This is where operational value becomes visible to communities considering a switch.
- Line 40: **Phase 3 — close the willingness-to-pay package.** Roster management, SLA enforcement, temporary permissions, and application interview/waitlist handling complete the "integrated roster plus activity plus analytics" package that the market research identifies as the strongest willingness-to-pay signal (`market research.md` §5). Phase 3 is where communities can substantively replace their current spreadsheet-plus-multi-bot stack (`market research.md` §4 Community Management Workarounds).
- Line 42: **Phase 4 — close the operational lifecycle.** Compliance evaluation against submitted evidence, chapter governance lifecycle (probation, archival), and leadership succession with context transfer. These capabilities answer problems the market has not meaningfully addressed ("general-purpose compliance engine is still missing"; "succession and delegated-local-authority continuity remain implicit rather than modeled") (`market research.md` §4, §5). Phase 4 completes the proposal scope.
- Line 47: - **Not moderation-first.** Moderation is one ticket category among many, not the organizing center. Anti-nuke, anti-raid, panic-mode, and turnkey anti-alt heuristics — where Wick and Security Bot specialize — are out of scope (`market research.md` §1 Differentiation opportunities: "Competitors have specialized anti-raid and anti-abuse surfaces the proposal does not directly cover").
- Line 64: **Value realization window.** Prerequisite — no direct operator-facing value; unblocks Phase 1.
- Line 84: **Value realization window.** Foundational — delivers defensible differentiation before any operational workflow. Capability visible as each slice ships.
- Line 109: **Business outcome.** Operational parity with — and differentiation from — the eight application tools, nine ticket tools, and eight multi-unit suites competing today, built on the Phase 1 governance substrate that none of them offer (`market research.md` §2, §3, §4).
- Line 115: **Value realization window.** Operational value visible to communities considering a switch — this is the phase that makes the system viable as a replacement for current stacks.
- Line 146: **Value realization window.** Completes the willingness-to-pay package — communities can substantively replace their multi-surface stacks (`market research.md` §4 Community Management Workarounds).
- Line 148: **Confidence.** Likely for VS-011 (roster) and VS-013 (SLA) — table-stakes or gap pain with clear dependency chain. Aspirational for VS-012 (interview/waitlist) — pain severity is 3, static-gap, with the widest dependency chain in the phase (composite 0.75).
- Line 154: - **Dependency-chain length.** VS-013 (SLA) has a transitive dependency depth of 5; a delay in any upstream slice cascades. Managed by dependency discipline — no intra-phase dependencies mean slice parallelism is preserved (`plans/risk/executive-dependency-trap.md` F-4).
- Line 171: **Business outcome.** Evidence-based compliance evaluation, chapter governance lifecycle (probation, archival), and leadership succession with context transfer — the capabilities the reviewed market has not addressed and that complete the proposal scope.
- Line 173: **User/community pain relieved.** Officers stop spending hours daily on manual data entry, cross-referencing spreadsheets, and threshold checks — explicitly the primary source of volunteer burnout (`problem.md` §6); inactive or troubled chapters stop accumulating without formal governance (`problem.md` §5); operational context stops being lost on every leadership change (`problem.md` §5).
- Line 179: **Confidence.** Aspirational. Pain severity for VS-016 (compliance) is 5 — the highest individual score in the roadmap — but the dependency depth (6) makes delivery timing uncertain. VS-017 (chapter governance) and VS-018 (succession) have moderate market evidence (2 sources for lifecycle administration; succession "remains implicit") (`market research.md` §4; `plans/risk/executive-market-misread.md` F-4).
- Line 204: - **General bots** (Dyno, Carl-bot, YAGPDB, MEE6, Arcane, Quark) — moderation, roles, leveling, logs. None offer persistent trust profiles, policy versioning, or cross-workflow audit (`market research.md` §1, §7 Cross-Bot Gaps).
- Line 205: - **Intake tools** (Gather, Appy, Application Bot, ApplicationForms, Google Forms stacks, Typeform stacks) — form submission and lightweight review. None offer claim-lock single-owner queuing, waitlist handling, or mandatory decision reasons (`market research.md` §2 Gap Analysis). *Gather is deprecated*.
- Line 206: - **Ticketing** (Ticket Tool, Helper.gg, SCNX, Discord Tickets, Modmail, ticket.pm, Mava, Oapps, DiscoDesk) — ticket creation, claims, transcripts. None offer per-category configurable state machines with typed transitions and mandatory resolution reasons (`market research.md` §3 Gap Analysis).
- Line 207: - **Activity/roster** (Apollo, Suivix, Raid-Helper, Guild Manager, GuildForger, Throney, GuildBro, Guilds of WoW, TL Guild Manager, CoGM) — attendance, event tracking, game-specific operations. None offer a general-purpose compliance engine with chapter-scoped rules and dispute-grade audit (`market research.md` §5 Gap Analysis).
- Line 208: - **Permission/security** (Wick, Security Bot, Double Counter, Xenon) — verification, anti-nuke, backup/restore. None offer declared-intent-vs-actual reconciliation (`market research.md` §6 Gap Analysis).
- Line 209: - **Broader suites** (Guildbase, TL Guild Manager, CoGM, Gamer Launch, Shivtr, Wick Bot, CommunityOne) — combine multiple surfaces but remain local to feature families. *Guilded is defunct*.
- Line 218: **Distinctive advantage this sequence creates.** The Phase 1 governance substrate (trust, authority, audit, policy versioning) is the floor no competitor offers. Building it first means every Phase 2+ workflow inherits defensibility: structured applications with mandatory reasons and causal audit is a different product from shared-dashboard review; tickets with typed transitions tied to versioned policy is a different product from action-centric claim flows; permissions as declared intent with drift detection is a different product from role-hierarchy automation. The proposal's differentiation is not any single feature — it is the integration pattern, and the integration pattern requires the Phase 1 substrate to exist first.
- Line 224: - **Market gaps are documented, not speculative.** Every `gap` classification in the scoring traces to an explicit "Gap Analysis" section in the source research (`plans/risk/executive-market-misread.md` F-3). The window exists because the market has not closed it — not because no one has tried.
- Line 236: \| 3 \| **Market misread — competitor enters with an intent-vs-actual control plane, policy versioning, or cross-subsystem causal audit.** \| Market / competitive \| Multiple `gap` classifications depend on the absence of these capabilities in the reviewed field (`plans/risk/executive-market-misread.md` What LOW requires #2). A new competitor would reclassify gaps as `parity` or `table-stakes` and compress the competitive window. \| Re-run market risk gate at each phase boundary using fresh research; treat competitive positioning as a time-bounded claim. \| Any reviewed or new product publishes declared-intent reconciliation, cross-subsystem causal audit, or policy preview-confirm semantics. \| All phases. \|
- Line 240: \| 7 \| **Depth-metric ambiguity for VS-012 and VS-016.** The roadmap's dependency depth counts direct upstream, understating transitive depth for these slices. \| Execution / methodology \| Cosmetic only — ordinal rankings and phase assignments unaffected (`plans/risk/executive-dependency-trap.md` F-6). Matters only if new slices are added downstream and composite scores are recomputed. \| Clarify depth definition to "direct upstream" in scoring methodology; re-examine if new downstream slices are proposed. \| A new proposed slice depends on VS-012 or VS-016 and inherits an artificially inflated composite score. \| Phases 3–4 only if scope expands. \|
- Line 273: \| Identity & Trust (VS-001, VS-010) \| Officers make admission and governance decisions without systematic evidence, relying on personal memory and Discord role presence — which breaks on staff turnover and across chapter boundaries (Problem §1) \|
- Line 274: \| Structured Intake (VS-006, VS-012) \| Officers duplicate review effort on the same applications, and all admission decisions lack mandatory rationale — making appeals unreconstructable and producing volunteer burnout from coordination overhead (Problem §2, §9) \|
- Line 275: \| Case Management (VS-007, VS-013) \| Harassment reports, appeals, and disputes age silently in DM threads with no durable state, no ownership tracking, and no time-based accountability — eroding community trust when sensitive cases stall (Problem §3) \|
- Line 276: \| Governance Infrastructure (VS-002, VS-003, VS-004, VS-009, VS-015) \| Decisions become unreconstructable after 45 days, configuration changes can silently corrupt in-flight operations, and no system enforces scoped authority — officers either have too much power or too little (Problem §4, §10, §13) \|
- Line 277: \| Chapter Operations (VS-005, VS-011, VS-017, VS-018) \| Officers manually provision chapter infrastructure, manage rosters in spreadsheets, and lose operational context on every leadership change — with cleanup cost accumulating for every chapter created (Problem §5) \|
- Line 278: \| Activity & Compliance (VS-016) \| Officers spend hours daily on manual data entry, cross-referencing spreadsheets, and threshold checks — work that is repetitive, error-prone, and explicitly the primary source of volunteer burnout (Problem §6) \|
- Line 285: No proposal subsystem is fully deferred — all seven subsystems appear in at least one value slice. The following capabilities within subsystems are deferred beyond the roadmap's scope or left to the engineering layer:
- Line 289: **Emergency override workflow.** VS-002 delivers scope enforcement. The enhanced audit trail for emergency overrides — where central staff override scope restrictions with increased visibility — is structurally available once VS-002 and VS-003 ship, but the specific UX workflow (justification capture, enhanced audit display) is not scoped into any value slice. Rationale: emergency overrides are rare events that do not warrant a dedicated value slice; the engineering layer includes this capability within the authority grant implementation.
- Line 291: **Permission migration tooling.** VS-008 delivers intent-vs-actual drift detection. But a community adopting the system inherits a full history of unmanaged permission decisions — all existing Discord permissions initially appear as "unintended" drift. Tooling to bulk-classify and import existing permissions into the declared-intent model is not scoped into a value slice. Rationale: migration tooling is a one-time adoption enabler, not an ongoing operational capability; the engineering layer addresses this as part of VS-008's implementation.
- Line 340: **Capability delivered:** Every operational decision is recorded immutably with actor, context, policy version, and causal chain identifiers — reconstructable months later.
- Line 471: - **Pain severity:** 4 — Reviewers rarely see trust context where decisions happen; three independent source categories (applications, general-bot, platforms reports) confirm the gap. False-positive complaints in Wick and Double Counter show active harm from coarse screening. (`market research.md` §1: "Reviewers rarely see trust context where decisions happen" — strong evidence; false-positive complaints — moderate evidence)
- Line 472: - **Competitive position:** gap — No reviewed competitor offers persistent, inspectable trust profiles with deterministic recomputation. "The proposal differs from every reviewed product by making trust a first-class subsystem with persistent Member, TrustProfile, and TrustSignal objects." (`market research.md` §1 differentiation)
- Line 473: - **Dependency depth:** 0 — no upstream value slices
- Line 474: - **Operational risk of delay:** active-harm — False positives in current verification tools actively reject legitimate users. Officers make admission decisions without systematic evidence, which degrades across staff turnover and chapter boundaries. (Problem §1: "calibrating and maintaining them across organizational boundaries, staff turnover, and time")
- Line 480: - **Pain severity:** 4 — Audit is fragmented and local across the market; tickets are transcript-first, permissions are event-log-first, and platforms expose local history rather than cross-subsystem chains. Retention is gated or limited across Quark, Dyno, MEE6, YAGPDB, and Guild Manager. (`market research.md` §7: "Audit is fragmented and local" — strong evidence; §3: "Audit remains transcript-first instead of action-stream first" — strong evidence, 5 sources; §7: "Retention and export are uneven or gated" — strong evidence)
- Line 481: - **Competitive position:** gap — "The market repeatedly fails to offer a single decision chain spanning intake, cases, chapters, permissions, and compliance." No competitor has causal correlation across subsystem boundaries. (`market research.md` cross-cutting findings)
- Line 482: - **Dependency depth:** 0 — no upstream value slices
- Line 483: - **Operational risk of delay:** active-harm — Discord's 45-day audit log cap means disputes that resurface after two months have no evidence trail. Officers cannot prove what happened, what inputs were available, or what policy governed a past decision. (Problem §4: "45-day retention cap, which is too short for seasonal guild operations, officer misconduct reviews, or disputes that resurface months later")
- Line 489: - **Pain severity:** 4 — No reviewed product offers policy versioning, diff previews, compare-and-swap edits, or last-known-version enforcement. Most dashboards apply settings directly with no temporal protection for in-flight operations. (`market research.md` §7: "no public evidence of policy versioning, diff previews, compare-and-swap edits, or last-known-version enforcement" — strong evidence; "Direct-mutation dashboards remain the norm" — strong evidence)
- Line 490: - **Competitive position:** gap — No competitor offers preview-confirm, version pinning, or optimistic concurrency for operational configuration. (`market research.md` §7 governance gap analysis)
- Line 491: - **Dependency depth:** 0 — no upstream value slices
- Line 492: - **Operational risk of delay:** active-harm — Configuration changes on a live server can silently corrupt in-flight operations. A form change mid-review alters the meaning of pending submissions. Concurrent operator edits produce decisions made against phantom state. (Problem §13: "a configuration change on a live system can silently corrupt the semantic integrity of in-flight operations"; "the change succeeds silently")
- Line 494: - **Opportunity cost:** By not building this yet, configuration changes can silently corrupt in-flight operations — changing an application form mid-review can alter the meaning of pending submissions without any error signal (Problem §13).
- Line 498: - **Pain severity:** 3 — Guild Manager and TL Guild Manager offer 40+ granular permissions, but these operate as role/admin capability sets rather than scoped authority grants. The permissions gap analysis confirms scoped grants are absent. Demand for governance control is strong but scoped authority specifically is a moderate signal. (`market research.md` §6: "scoped grants...are absent across the reviewed field" within strong governance gap analysis; §6: Guild Manager, TL Guild Manager, CoGM offer granular permissions but not scoped delegation)
- Line 499: - **Competitive position:** gap — "Drift detection, preview-confirm changes, scoped grants, and optimistic concurrency are absent across the reviewed field." No competitor expresses authority as scoped delegation rather than ranked hierarchy. (`market research.md` §6 permissions gap analysis)
- Line 500: - **Dependency depth:** 0 — no upstream value slices
- Line 501: - **Operational risk of delay:** static-gap — Communities work around the limitation using Discord's ranked role hierarchy, pushing toward either over-centralization or over-granting. The problem is stable — officer access patterns don't worsen over time absent new chapters. (Problem §10: "often pushes communities toward either over-centralization or over-granting")
- Line 509: - **Pain severity:** 5 — Time/status rigor is shallow across the market: the gap analysis confirms per-category configurable state machines are effectively missing, and mandatory resolution reasons are rare across Ticket Tool, Helper.gg, Discord Tickets, and SCNX. Assignment is brittle or paywalled. (`market research.md` §3: "per-category configurable state machines are effectively missing" — strong evidence; "mandatory resolution reasons are rare" — strong evidence; "Assignment is brittle or paywalled" — moderate evidence)
- Line 510: - **Competitive position:** table-stakes — Nine sources compete (Ticket Tool, Helper.gg, SCNX, Discord Tickets, Modmail, ticket.pm, Mava, Oapps, DiscoDesk). Not having case management makes the system non-viable for communities that handle appeals, harassment reports, and disputes. (`market research.md` §3: 9 competing sources)
- Line 511: - **Dependency depth:** 3 — VS-001 (reporters/subjects are members), VS-002 (officer authority for assignment/escalation), VS-003 (transitions generate audit entries)
- Line 512: - **Operational risk of delay:** active-harm — Harassment reports, appeals, and disputes live in ephemeral DM threads with no durable state or ownership tracking. Stalled reports erode community trust; stalled appeals leave members in limbo. (Problem §3: "A stalled harassment report erodes community trust; a stalled appeal leaves a member in limbo")
- Line 518: - **Pain severity:** 5 — Reviewer collision prevention is essentially absent; Gather, Appy, Application Bot, and ApplicationForms all lack published claim-lock or single-owner queueing. Waitlists, appeals, and mandatory decision reasons remain rare. Discord-native review breaks down on platform constraints. (`market research.md` §2: "Reviewer collision prevention is essentially absent" — strong evidence; "Waitlists, appeals, and required decision reasons remain rare" — strong evidence; "Discord-native review breaks down" — strong evidence)
- Line 519: - **Competitive position:** table-stakes — Eight sources compete (Gather, Appy, Application Bot, ApplicationForms, Google Forms stacks, Typeform stacks, Guildbase, Guild Manager). Structured intake is a core requirement for guild management. (`market research.md` §2: 8 competing sources; "Demand for better application tooling is very well validated")
- Line 520: - **Dependency depth:** 4 — VS-001 (applicant trust context), VS-002 (reviewer authority over target scope), VS-003 (transitions generate audit entries), VS-004 (form definition versioning)
- Line 521: - **Operational risk of delay:** active-harm — Two reviewers independently evaluate the same application without knowing the other started, duplicating scarce volunteer effort. Conflicting decisions require additional coordination. (Problem §2: "concurrent access introduces a mutual-exclusion problem"; Problem §9: "every duplicated review or conflicting decision is attention spent on coordination overhead")
- Line 523: - **Opportunity cost:** By not building this yet, officers duplicate review effort on the same applications and all admission decisions lack mandatory rationale — making appeals unreconstructable (Problem §2, §9).
- Line 527: - **Pain severity:** 4 — Chapter lifecycle automation is still missing; the activity report and general-bot report explicitly confirm this gap. Communities assemble subgroup operations from Discord plus Google Sheets plus multiple bots. (`market research.md` §4: "Chapter lifecycle automation is still missing" — strong evidence; "Communities still assemble subgroup operations from multiple surfaces" — strong evidence)
- Line 528: - **Competitive position:** table-stakes — Eight sources compete on multi-unit management (Guild Manager, GuildForger, Throney, Guilds of WoW, TL Guild Manager, CoGM, Gamer Launch, Shivtr). A guild management platform without chapter support is non-viable for multi-chapter organizations. (`market research.md` §4: 8 competing sources)
- Line 529: - **Dependency depth:** 3 — VS-001 (actors are members), VS-002 (approval authority at parent scope), VS-003 (transitions generate audit entries)
- Line 530: - **Operational risk of delay:** active-harm — Officers manually create channels, categories, and roles for each new chapter, accumulating inconsistent structures and untracked cleanup cost. Every new chapter increases future governance complexity. (Problem §5: "every subgroup created today increases future cleanup cost")
- Line 536: - **Pain severity:** 4 — Declared-state reconciliation is under-served despite repeated gap analysis across five source categories. Governance visibility stops at logs or backups. Xenon can restore but not reconcile live state against declared intent. (`market research.md` §6: "Declared-state reconciliation appears under-served" — strong evidence, 5 sources; "Governance visibility stops at logs or backups" — strong evidence)
- Line 537: - **Competitive position:** gap — No reviewed competitor offers an intent-vs-actual reconciliation model. Xenon offers backup/restore but not declared-intent drift detection. Guild suites offer granular permissions but not audit-grade intent tracking. (`market research.md` §6: "none expose an intent-vs-actual control plane"; Xenon comparison)
- Line 538: - **Dependency depth:** 3 — VS-001 (actors are members), VS-002 (authority over affected scope), VS-003 (drift resolutions generate audit entries)
- Line 539: - **Operational risk of delay:** active-harm — Permission drift silently accumulates as temporary overrides become inherited baselines. Every urgent crisis exception increases the gap between intended and actual state. (Problem §7: "every urgent exception during a crisis becomes tomorrow's inherited baseline"; "accumulated unreviewed history")
- Line 545: - **Pain severity:** 3 — Notification volume is explicitly identified as a distinct burnout mechanism from process rigor. Current products either over-notify (cascading alerts per downstream effect) or under-notify (no alert when action is needed). Market products have fixed notification patterns rather than configurable triggers. (`market research.md` §7: notification behavior embedded in various products but not as configurable system; Problem §9: "notification volume is a distinct burnout mechanism from process rigor")
- Line 546: - **Competitive position:** gap — No competitor offers causal grouping of notifications (per_root_cause batching) or configurable trigger-recipient-channel rules with actionable vs. informational distinction. (`market research.md` §7: products embed notifications but none market a configurable notification plane)
- Line 547: - **Dependency depth:** 2 — VS-002 (authority scopes determine recipients), VS-003 (audit events serve as triggers)
- Line 548: - **Operational risk of delay:** active-harm — Officers either receive no system-generated awareness of events requiring action, or receive cascading independent notifications for every downstream effect of a single decision. Both patterns erode attention budgets. (Problem §9: "notification volume from automated cascades is an attention cost that exists independently of how many decisions require human involvement")
- Line 554: - **Pain severity:** 3 — The market repeatedly fails to offer a single decision chain spanning intake, cases, chapters, permissions, and compliance. Audit is fragmented and local. Operators piece together history from multiple bots, dashboards, and spreadsheets. (`market research.md` cross-cutting: "the market repeatedly fails to offer a single decision chain"; §7: "Audit is fragmented and local" — strong evidence)
- Line 555: - **Competitive position:** gap — No competitor offers cross-subsystem materialized operational views. Cross-workflow visibility is a documented gap across all six market research reports. (`market research.md` cross-cutting findings; §7 governance gap)
- Line 556: - **Dependency depth:** 1 — VS-003 (audit entries provide the event stream to materialize)
- Line 557: - **Operational risk of delay:** static-gap — Operators currently piece together member history from multiple sources. Painful but stable — the workaround functions, just slowly. Value increases as more subsystems generate events. (Problem §12: "no single system can answer 'what is this member's full operational history?'")
- Line 563: - **Pain severity:** 3 — Demand for a richer operator trust view is present across five source categories, but officer-managed signals specifically have moderate direct evidence. The gap is real but less urgent than initial screening (VS-001). (`market research.md` §1: "Demand for a richer operator trust view is present but indirect" — strong evidence, 5 sources; "none of them expose inspectable trust signals, deterministic trust recomputation, or chapter-specific trust portability")
- Line 564: - **Competitive position:** gap — No competitor offers configurable trust computation with per-scope signal weights, decay rules, and operator-visible derivation. (`market research.md` §1 differentiation: durable, inspectable, scope-specific, auditable through recomputation history)
- Line 565: - **Dependency depth:** 4 — VS-001 (trust profiles exist), VS-002 (officer authority to record signals), VS-003 (signal recording and trust recomputation generate audit entries), VS-004 (policy versioning governs TrustComputationConfig changes)
- Line 566: - **Operational risk of delay:** static-gap — Trust calibration is a persistent challenge, but communities have workarounds (manual officer judgment, role-based indicators). The gap does not worsen rapidly absent new chapters. (Problem §1: existing verification tools provide coarse filtering)
- Line 574: - **Pain severity:** 4 — Communities still assemble subgroup operations from multiple surfaces. The strongest willingness-to-pay signal is for integrated roster plus activity plus analytics (6 sources). Officers manage rosters in spreadsheets, losing context on every staff change. (`market research.md` §4: "Communities still assemble subgroup operations from multiple surfaces" — strong evidence; §5: "strongest willingness-to-pay signal is for integrated roster plus activity plus analytics" — strong evidence, 6 sources)
- Line 575: - **Competitive position:** table-stakes — Guild Manager, Throney, GuildForger, and TL Guild Manager all offer roster management. Not having roster management makes the chapter system non-functional for day-to-day operations. (`market research.md` §4: 8 sources compete on multi-unit management; §5: 6 sources package activity with roster administration)
- Line 576: - **Dependency depth:** 4 — VS-001 (members), VS-002 (officer authority for roster actions), VS-003 (transitions generate audit entries), VS-005 (chapters must exist)
- Line 577: - **Operational risk of delay:** active-harm — Chapter membership records live in spreadsheets or Discord role presence with no lifecycle tracking, no role assignment history, and no auditable status transitions. Officer time spent on manual roster maintenance is a recurring cost. (Problem §5: "succession problem is not just 'transfer a role' — it is 'transfer operational context'")
- Line 583: - **Pain severity:** 4 — Cases can age in assigned states with no systemic visibility. The ticketing gap analysis explicitly notes shallow time/status rigor and the absence of per-category response time requirements. Stalled harassment reports erode community trust. (`market research.md` §3: "per-category configurable state machines are effectively missing" — strong evidence; implicit in gap analysis: no time-based enforcement; Problem §3: "cases silently age without accountability")
- Line 584: - **Competitive position:** gap — No competitor offers per-category SLA rules with graduated time-based consequences. SCNX has timeout features but not configurable graduated escalation tied to category state machines. (`market research.md` §3: gap analysis; no product offers operator-configured SLA thresholds with proportional consequences)
- Line 585: - **Dependency depth:** 5 — VS-001, VS-002, VS-003 (through VS-007), VS-007 (tickets must exist), VS-009 (SLA triggers use notification system)
- Line 586: - **Operational risk of delay:** active-harm — Cases silently age with no automated accountability. A harassment report stalling for a week has no escalation path. Time-based monitoring is entirely manual, competing for the same officer attention SLAs would protect. (Problem §3: "A stalled harassment report erodes community trust"; "time-based monitoring introduces its own attention cost")
- Line 588: - **Opportunity cost:** By not building this yet, cases silently age in assigned states with no time-based accountability — a harassment report stalling for a week has no automated escalation path (Problem §3).
- Line 592: - **Pain severity:** 3 — Governance visibility stops at logs or backups, and the permissions gap analysis confirms no product tracks permission temporality. The specific pain of forgotten temporary overrides is a subset of the broader drift problem. (`market research.md` §6: "Governance visibility stops at logs or backups" — strong evidence; Problem §7: temporary overrides becoming permanent)
- Line 593: - **Competitive position:** gap — No competitor offers temporary permission intents with automatic expiration tracking. This extends the gap already identified in declared-intent models. (`market research.md` §6: no product offers intent-vs-actual reconciliation, let alone temporal intent tracking)
- Line 594: - **Dependency depth:** 4 — VS-001, VS-002, VS-003 (through VS-008), VS-008 (permission intents must exist)
- Line 595: - **Operational risk of delay:** active-harm — Every temporary permission override that lacks an explicit expiration date becomes a permanent fixture. The accumulation actively worsens permission state complexity over time. (Problem §7: "every urgent exception during a crisis becomes tomorrow's inherited baseline")
- Line 601: - **Pain severity:** 3 — Waitlists, appeals, and required decision reasons remain rare across the application market. The gap analysis explicitly calls out missing waitlist handling. However, communities work around this with DMs for interviews and informal tracking for waitlists. (`market research.md` §2: "Waitlists, appeals, and required decision reasons remain rare" — strong evidence; gap analysis)
- Line 602: - **Competitive position:** gap — No competitor offers structured waitlist with reactivation or system-provisioned interview threads. Gather is the closest with richer state models but is deprecated. (`market research.md` §2 gap analysis; Gather deprecated)
- Line 603: - **Dependency depth:** 5 — VS-001, VS-002, VS-003, VS-004 (through VS-006), VS-006 (application intake must exist)
- Line 604: - **Operational risk of delay:** static-gap — Officers handle interviews via DMs and waitlists via informal tracking. Functional but not systematic. The workaround does not worsen over time. (Problem §2: interview and waitlist are part of the application lifecycle)
- Line 612: - **Pain severity:** 5 — Spreadsheet and manual-process fatigue is a core recurring complaint. A general-purpose compliance engine is still missing outside game-specific tools. Screenshot evidence is common but under-structured. Dispute-grade audit chains for compliance are rare. (`market research.md` §5: "Spreadsheet and manual-process fatigue is a core recurring complaint" — strong evidence; "A general-purpose compliance engine is still missing" — strong evidence; "Screenshot evidence is common but under-structured" — strong evidence; "Dispute-grade audit chains for compliance are rare" — strong evidence)
- Line 613: - **Competitive position:** table-stakes — Nine sources compete on activity tracking (Apollo, Suivix, Raid-Helper, Guild Manager, GuildForger, Throney, GuildBro, Guilds of WoW, TL Guild Manager). Activity tracking is a core requirement for guild management. (`market research.md` §5: 9 competing sources)
- Line 614: - **Dependency depth:** 6 — VS-001, VS-002, VS-003, VS-005 (through VS-011), VS-004 (rule versioning via PolicyVersion), VS-011 (roster entries identify who to evaluate)
- Line 615: - **Operational risk of delay:** active-harm — Officers spend hours daily on manual data entry, cross-referencing spreadsheets, and threshold checks. This is explicitly identified as the primary source of volunteer burnout. (Problem §6: "officer time spent on data entry, cross-referencing, and threshold checks — work that is repetitive, error-prone, and a primary source of volunteer burnout")
- Line 617: - **Opportunity cost:** By not building this yet, officers spend hours daily on manual data entry, cross-referencing spreadsheets, and threshold checks — the primary source of volunteer burnout (Problem §6).
- Line 621: - **Pain severity:** 3 — Succession and delegated-local-authority continuity remain implicit rather than modeled across the market. Multi-guild products support team management but not stateful transfer of pending work and authority. (`market research.md` §4: "Succession and delegated-local-authority continuity remain implicit rather than modeled" — moderate evidence)
- Line 622: - **Competitive position:** gap — No reviewed product models succession as a first-class operation with predecessor-linked authority grants and pending work transfer. (`market research.md` §4: no product offers stateful succession)
- Line 623: - **Dependency depth:** 5 — VS-001, VS-002, VS-003, VS-005 (through VS-011), VS-011 (roster identifies succession-triggering role holders)
- Line 624: - **Operational risk of delay:** static-gap — Leadership transitions are handled manually. Functional but context-lossy — the successor must reconstruct governance state from memory and scattered records. The problem is stable unless leadership turnover increases. (Problem §5: "transfer operational context, pending decisions, and member trust without a gap in governance")
- Line 630: - **Pain severity:** 3 — Lifecycle-grade chapter administration is under-monetized; provisioning, archival, and lifecycle governance are missing even in premium suites. But the market signal is moderate — only two sources directly evidence the gap. (`market research.md` §4: "lifecycle-grade chapter administration itself is under-monetized" — moderate evidence, 2 sources; gap analysis)
- Line 631: - **Competitive position:** gap — No competitor offers probation and archival as explicit lifecycle states with governance transitions. Multi-guild products treat groups as static containers. (`market research.md` §4: "provisioning, archival, and lifecycle governance are missing even in premium suites")
- Line 632: - **Dependency depth:** 5 — VS-001, VS-002, VS-003, VS-005 (through VS-011), VS-011 (rosters must exist for archival member notification and pending work resolution)
- Line 633: - **Operational risk of delay:** future-risk — Chapter governance becomes relevant as the community ages and chapters naturally decline. Currently, dead channels accumulate without formal governance. The problem grows with community age and chapter count but is not actively harmful today. (Problem §5: "every subgroup created today increases future cleanup cost")

### V-2. Banned openers

**Category:** Sentences starting with banned openers  
**Fix guidance:** Start the sentence on the underlying claim, or fold the contrast into the prior sentence.

- Line 291: `But a community adopting the system inherits a full history of unmanaged permission decisions — all existing Discord permissions initially appear as "unintended" drift.`
- Line 601: `However, communities work around this with DMs for interviews and informal tracking for waitlists.`
- Line 630: `But the market signal is moderate — only two sources directly evidence the gap.`

### V-3. Triads in prose

**Category:** Triads in prose  
**Fix guidance:** Break the inline list into an actual list, or split it into two unequal sentences so the prose stops reading as a template.

- Line 5: `identity/trust, intake, case management, sub-community lifecycle, activity/compliance, permissions, and governance`
- Line 10: `audit gaps past Discord's 45-day cap ...; permission drift ...; unreconstructable configuration changes ...; volunteer burnout ...`
- Line 13: `Phase 0 (engineering foundations), Phase 1 (governance foundation), Phase 2 (core operational workflows), Phase 3 (operational depth), Phase 4 (operational maturity)`
- Line 13: `bot-framework breadth, moderation-first design, AI-driven operational decisions, real-time game integration`
- Line 17: `register members with computed trust, enforce scoped authority, record every decision with causal correlation, and change configuration safely`
- Line 18: `run structured applications with reviewer ownership, manage tickets through category-specific state machines, provision chapters from templates, detect permission drift, and configure notifications`
- Line 19: `manage rosters, enforce SLAs with graduated consequences, handle interviews and waitlists, and track temporary permissions`
- Line 36: `trust profiles, scoped authority, immutable causal audit, and preview-confirm policy changes`
- Line 42: `Compliance evaluation against submitted evidence, chapter governance lifecycle (probation, archival), and leadership succession with context transfer`
- Line 47: `Anti-nuke, anti-raid, panic-mode, and turnkey anti-alt heuristics`
- Line 48: `Leveling, reaction-role UX depth, DKP/loot systems, raid composition tools, and event-scheduling depth`
- Line 72: `database schema and migration framework, Discord gateway connection and platform boundary layer, subsystem isolation and graceful degradation mechanics, deferred effect queue infrastructure, and base API framework`
- Line 78: `persistent trust profiles, scoped authority enforcement, causal audit across subsystems, and preview-confirm policy versioning`
- Line 109: `the eight application tools, nine ticket tools, and eight multi-unit suites competing today`
- Line 171: `Evidence-based compliance evaluation, chapter governance lifecycle (probation, archival), and leadership succession with context transfer`
- Line 173: `manual data entry, cross-referencing spreadsheets, and threshold checks`
- Line 223: `Claiming, transcripts, log history, exports, alliance support, and backups`
- Line 276: `Decisions become unreconstructable after 45 days, configuration changes can silently corrupt in-flight operations, and no system enforces scoped authority`
- Line 277: `Officers manually provision chapter infrastructure, manage rosters in spreadsheets, and lose operational context on every leadership change`
- Line 278: `manual data entry, cross-referencing spreadsheets, and threshold checks`

### V-4. Pseudo lists from parallel clauses

**Category:** Pseudo lists from parallel clauses  
**Fix guidance:** Rebuild these into one main claim plus one supporting sentence, or convert them into a real list.

- Line 9: `assignment is "brittle or paywalled," audit is "fragmented and local," and "declared-state reconciliation appears under-served"`
- Line 82: `view any member's trust level ... grant/revoke authority ... reconstruct any past decision ... change policy on a live server`
- Line 97: `Member onboarding with automatic trust computation ...; authority grant and revoke ...; audit trail queries ...; policy preview-confirm ...`
- Line 113: `Operators can run ...; open tickets ...; provision chapters ...; declare intended permissions ...; configure notifications ...; query cross-subsystem operational history.`
- Line 159: `Roster management ...; SLA monitoring ...; interview thread provisioning and waitlist reactivation; temporary permission intent with expiration tracking.`
- Line 175: `Compliance evaluation runs ...; chapters enter probation and archival ...; leadership succession preserves ...`
- Line 190: `Scheduled compliance evaluation ...; evidence submission ...; chapter probation ...; chapter archival ...; leadership succession ...`
- Line 218: `structured applications ... is a different product ...; tickets ... is a different product ...; permissions ... is a different product ...`
- Line 262: `re-run the market misread risk gate ...; confirm no new competitor ...; re-evaluate Phase 4 composition ...`

### V-5. Three consecutive sentences with the same opening word

**Category:** Three consecutive sentences with the same opening word  
**Fix guidance:** Vary the openings, combine adjacent sentences, or change the sentence shape so the run stops sounding templated.

- Line 99: `No operational workflows ... No Discord resource management. No compliance evaluation.`
- Line 130: `No direct roster management ... No compliance evaluation. No SLA enforcement for tickets.`
- Line 161: `No compliance evaluation. No chapter governance lifecycle ... No leadership succession with context transfer.`
- Lines 204-208: `None offer persistent trust profiles ... None offer claim-lock single-owner queuing ... None offer per-category configurable state machines ... None offer a general-purpose compliance engine ... None offer declared-intent-vs-actual reconciliation.`
- Line 327: `No officer-managed signals ... No per-chapter trust profiles. No trust computation customization.`
- Line 335: `No succession chain ... No emergency override workflow. No automatic authority from ChapterRole assignment.`
- Line 343: `No CQRS read model materialization. No retention management interface. No export tooling.`
- Line 351: `No rollback automation. No bulk policy migration. No cross-scope policy comparison.`
- Line 359: `No probation or archival states. No succession. No chapter-scoped compliance rules.`
- Line 367: `No interview flow. No waitlist. No form branching logic.`
- Line 375: `No SLA enforcement. No cross-ticket linking ... No cross-ticket pattern detection.`
- Line 383: `No temporary permission expiration. No migration tooling ... No automated reconciliation scheduling.`
- Line 391: `No notification analytics. No digest scheduling. No notification muting or snooze.`
- Line 399: `No automated cross-chapter trust recognition. No trust signal expiration management UI. No trust analytics or trending.`
- Line 407: `No compliance-triggered status changes. No succession workflow. No automated roster cleanup.`
- Line 415: `No automated waitlist prioritization. No bulk waitlist management. No interview scheduling.`
- Line 423: `No SLA analytics dashboard. No SLA template library. No custom SLA consequence actions.`
- Line 431: `No automated permission rotation. No bulk temporary grant management. No temporary permission renewal workflow.`
- Line 439: `No custom query builder. No export from read model. No analytics or aggregation beyond operational history.`
- Line 447: `No seasonal rules ... No cross-game evidence correlation. No evidence analytics.`
- Line 455: `No automated inactivity detection triggering probation. No chapter health scoring. No cross-chapter governance dashboard.`
- Line 463: `No automated successor selection. No succession scheduling or term limits. No cross-chapter succession coordination.`

### V-6. Three consecutive sentences with the same grammatical frame

**Category:** Three consecutive sentences with the same grammatical frame  
**Fix guidance:** Change the subject-verb pattern, combine one sentence into the next, or recast one item into explanation instead of another template sentence.

- Line 126: `Officers process structured applications with single-reviewer ownership. Tickets progress through category-specific state machines with privacy controls. New chapters are provisioned from templates through approval gates.`
- Line 188: `Compliance evaluation runs on schedule with OCR-parsed evidence and graduated consequences; chapters enter probation and archival with formal state transitions; leadership succession preserves pending work and authority with predecessor-linked grants.`

### V-7. Cliches

**Category:** Cliches  
**Fix guidance:** Replace the phrase with a plain, direct observation.

- Line 9: `Competitive window is open.`
- Line 34: `one coherent story`
- Line 38: `table-stakes crowd`
- Line 40: `strongest willingness-to-pay signal`
- Line 140: `strongest willingness-to-pay signal in the market`
- Line 574: `strongest willingness-to-pay signal`

### V-8. Moralizing or status language

**Category:** Moralizing or status language  
**Fix guidance:** Replace status-signaling jargon with a concrete operational claim.

- Line 148: `table-stakes or gap pain`
- Line 510: `table-stakes`
- Line 519: `table-stakes`
- Line 528: `non-viable for multi-chapter organizations`
- Line 575: `table-stakes`
- Line 613: `table-stakes`

### V-9. Performative intent sentences

**Category:** Performative intent sentences  
**Fix guidance:** Delete the sentence or replace it with evidence, mechanism, or a concrete implication.

- Line 20: `the complete proposal scope`
- Line 42: `Phase 4 completes the proposal scope.`
- Line 72: `The executive roadmap identifies this phase but does not detail its contents.`
- Line 177: `Completes proposal scope.`
- Line 192: `All proposal capabilities are delivered at Phase 4 completion.`
- Line 218: `The proposal's differentiation is not any single feature — it is the integration pattern, and the integration pattern requires the Phase 1 substrate to exist first.`
- Line 224: `The window exists because the market has not closed it — not because no one has tried.`

## Summary by Category

| Category | Count |
|----------|-------|
| Em dashes | 118 |
| Banned openers | 3 |
| Triads | 20 |
| Pseudo lists | 9 |
| Three consecutive sentences with same opening word | 22 |
| Three consecutive sentences with same grammatical frame | 2 |
| Vague modal hedges | 0 |
| Throat clearing phrases | 0 |
| Posturing frames | 0 |
| Cliches | 6 |
| Moralizing or status language | 6 |
| Performative intent sentences | 7 |
