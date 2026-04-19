# Guildies: One Platform for the Whole Operation

*A unified guild-management system that replaces fragmented bot stacks and manual spreadsheets with durable, auditable operational workflows.*

---

## The Problem

> It's Monday morning. You open Discord and start your weekly compliance check. You pull up your chapter's attendance spreadsheet and open three different screenshot channels. Cross-referencing names against thresholds eats the rest of the morning. Two hours later, you've identified six members who are behind on activity requirements. You DM each one individually. By Wednesday, you can't remember which members you already contacted. Meanwhile, a harassment report has been sitting in a ticket bot for four days. Nobody knows if it was claimed because the bot's dashboard was down yesterday. An officer approved an applicant, but so did another officer who didn't know the first had already started reviewing. A temporary permission override from last month's event is still active, and nobody remembers who set it or why.

Officers running gaming communities on Discord live this every week. A few patterns keep repeating:

- **Compliance tracking is manual labor.** Officers spend hours every week copying activity data from screenshots into spreadsheets and comparing each row against chapter-specific thresholds. Members behind on their activity requirements get chased down individually by DM. The repetitive cross-referencing drives volunteer burnout.

- **Cases disappear into ad hoc channels.** Harassment reports and appeals live in DM threads or third-party dashboards without durable ownership or time-based accountability. Recruitment issues end up in the same channels, with no privacy guarantees for sensitive exchanges. A stalled harassment report erodes community trust. A stalled appeal leaves a member in limbo.

- **Applications collide.** When multiple officers can review the same intake queue, two reviewers independently evaluate the same application without knowing the other has started, duplicating scarce volunteer effort. If they reach different conclusions, resolving the conflict burns even more attention.

- **Permissions drift invisibly.** Every urgent exception during a crisis becomes tomorrow's inherited baseline. Over time, no single person can explain whether Discord's actual permission state matches what was intended. There is no concept of "intended state" to audit against.

- **Volunteer attention is the scarcest resource.** Every mandatory review step and every duplicate notification competes for the same limited officer time. Manual data entry piles on top. When the system requires constant human arbitration to stay coherent, officers burn out and leave.

The shared failure across these patterns is that no tool owns the operational record. Operational state lives as vendor-held fragments distributed across bots and spreadsheets that cannot be reassembled into a single lifecycle. None of them can reconstruct the whole history of a member or a case. Operator-owned durable state is the structural answer.

---

## The Current Landscape

Officers today solve these problems by stitching together five or more disconnected tools:

- a ticket bot for case creation
- an application bot for intake
- a moderation-log bot for infraction history
- a reaction-role bot for permission assignment
- a spreadsheet for compliance tracking
- DMs for everything that doesn't fit

Each tool solves one thing. Nothing connects.

**Ticket bots** like Ticket Tool, Helper.gg, Discord Tickets, and Modmail handle case creation and transcripts, but their workflows are action-based (open, claim, close) rather than lifecycle-based. Per-category escalation rules and time-based accountability are rare or absent, and mandatory resolution reasons do not appear as first-class concepts in a transcript-first model. Transcript storage is the dominant audit model, not structured decision chains.

**Application tools** like Appy, Application Bot, and ApplicationForms provide form submission and dashboard review, but reviewer collision prevention is essentially absent across the field. Waitlists and structured decision rationale are explicitly called out as rare. External form stacks like Google Forms push applicants and reviewers into fragmented off-Discord workflows.

**Activity and roster tools** like Throney, Guild Manager, and Raid-Helper track attendance and participation, but a general-purpose compliance engine is still missing. Configurable rules and automatic consequence workflows do not appear in the reviewed field, and chapter-specific thresholds still live in officer-maintained spreadsheets. Officers still edit attendance in spreadsheets and stitch manual proof handling across Discord and bots, with optional support from guild websites.

**Permission and security bots** like Wick, Dyno, Carl-bot, and Xenon automate roles and monitor dangerous permissions. Xenon additionally backs up server state. Governance visibility stops at logs or backups. No reviewed product exposes a declared-intent-versus-actual control plane for permissions. Xenon can restore what was previously backed up, but restore is not the same as live reconciliation.

**Audit lives in feature silos.** Tickets are transcript-first and permissions are event-log-first. Broader platforms expose local workflow history rather than a chain that follows one decision from intake through every downstream consequence. No existing tool answers the question: "What is this member's full operational history?"

---

## Why Now

The conditions that make an integrated guild-operations platform viable did not exist two years ago. Several independent timing shifts have opened an opportunity that will compress as incumbents adapt.

**Incumbents are exiting the market.** Gather (the one reviewed application product that had form versioning and a richer submission lifecycle) is deprecated and no longer viable for active operations (`market research.md` §2). Guilded, once a cross-platform alternative, is shut down (`market research.md` §7). SCNX documentation shows rollout lag, and multiple other products have stale or outdated surfaces (`market research.md` §7). Communities are evaluating replacements now.

**No competitor ships a cross-subsystem audit chain.** The cross-cutting market research finds that the field "repeatedly fails to offer a single decision chain spanning intake, cases, chapters, permissions, and compliance" (`market research.md` Cross-cutting Findings). Five sources describe declared-state reconciliation as under-served; eight sources monetize role automation and security without providing an intent-vs-actual control plane (`market research.md` §6, §7). Every subsystem gap the proposal targets is cataloged with evidence strength in the research, not inferred.

**The API and OCR pieces cleared their blockers recently.** Discord's interaction APIs (slash commands, components v2, modal select components in `discord.py` 2.7+) now support the intake and review UX the proposal requires, along with reconciliation flows that were either missing or unstable before. Classical OCR with a vision-LLM fallback (Google Cloud Vision `DOCUMENT_TEXT_DETECTION` primary, Gemini 3 Flash Preview fallback) makes screenshot-based compliance evaluation affordable at the per-image cost structure communities can support (`DECISIONS.md` D5, D6). The OCR pipeline was the missing piece for replacing the weekly spreadsheet ritual.

**Premium gating has pushed lock-in past operators' tolerance.** Premium tiers gate exactly the capabilities operators need most, from claim workflow through backup/restore (`market research.md` Cross-cutting Findings). That gating reinforces vendor lock-in and makes migration painful exactly when communities want to leave. Community-owned data is a credible counter-position at this moment in a way it would not have been before vendor departures made the risk concrete.

**Gap classifications are time-bounded.** Every `gap` classification in the market research will expire: if an incumbent ships an intent-vs-actual control plane or a cross-subsystem causal audit, those gaps reclassify as `parity` or `table-stakes` and the differentiation compresses (`executive roadmap.md` Risk Register #3). The research refresh cadence is built into the roadmap, but the current classifications will not hold forever.

---

## Market Opportunity

A viable window only matters if someone is ready to buy inside it. The first buyers are a specific segment; adjacent segments sharing the same operational profile come later.

### TAM / SAM / SOM

Bottoms-up sizing anchored to public disclosures rather than top-down "fraction of all Discord servers" claims (`research/market-economics.md` §1; `research/pitch-deck-communication.md` Market Opportunity Communication).

| Layer | Value | Basis |
|---|---:|---|
| **TAM** (Discord bot software ceiling) | **$1.1B-$2.3B** | `19M weekly active servers × 1 paid bot × $5-$10/mo`, using [CNBC's 19M weekly active servers figure](https://www.cnbc.com/2021/05/08/what-is-discord-chat-service-fosters-community-expands-beyond-gaming.html) and the visible per-bot pricing band from [MEE6](https://mee6.xyz/en/pro), [Dyno](https://dyno.gg/premium), [Carl-bot](https://carl.gg/get-premium), and [Ticket Tool](https://tickettool.xyz/billing) |
| **SAM** (guild-management wedge, base case) | **~$150M** (modeled range $46M-$274M) | `190k-570k addressable guilds × $240-$480/year`; guild share derived from Discord's gaming skew, [Guilds FAQ](https://support.discord.com/hc/en-us/articles/23187611406999-Guilds-FAQ), and the [500-member Server Insights threshold](https://support.discord.com/hc/en-us/articles/360032807371-Server-Insights-FAQ) (`research/market-economics.md` §1 SAM calculation) |
| **SOM** (realistic 3-year capture) | **~$720k ARR** at ~2,000 paying guilds | About `0.47%` of base-case SAM; consistent with the year-3 scenario in the economics research (`research/market-economics.md` §2) |

The SAM estimate deliberately stays inside the guild-management category rather than claiming "the whole Discord ops market." Annual willingness-to-pay is anchored to the cost of the 3-5 premium bots operators already run (`market research.md` §4), cross-checked against [Guild Manager's $19.99-$49.99/mo tiers](https://guildmanager.app/pricing) and legacy guild-hosting precedents like [Shivtr](https://shivtr.com/plans) and [Gamer Launch](https://www.gamerlaunch.com/order/d/comparison/). The upper-bound TAM is a software-spend ceiling, not a realistic near-term revenue pool; it is included for scale context, not to justify the raise.

**Market-cap feasibility: HYBRID.** The gaming-guild wedge alone can support a solid SaaS business and a small team (a $600k-$720k annual burn represents about `0.39%-0.47%` of base-case SAM). True VC-scale outcomes require expansion beyond guilds into adjacent coordination-heavy communities, which the roadmap positions for but does not deliver in Phase 1 (`research/market-economics.md` §4 Market-cap feasibility check).

### The First Wedge: Coordination-Heavy Gaming Guilds

**Who buys first.** Gaming guilds with roughly 50–500 members that run multi-officer chapter operations, handling intake and compliance on the same volunteer team. Humility (the design reference community) had 83 members during the original operational sweep (`NOTES.md`). These communities share a common profile:

- Multiple officers share responsibility for intake, compliance, and cases
- Three to five Discord bots plus at least one spreadsheet compose the operational stack (`market research.md` §4 Community Management Workarounds: "the common workaround is `Discord + Google Sheets/Excel + one or more bots + optional guild website`")
- Chapter-specific activity thresholds, intake rules, and authority boundaries exist but are enforced manually
- Officer turnover creates repeated onboarding loss

**What they spend today.** Two compounding costs:

1. **Officer time.** The weekly compliance ritual of transcribing screenshots into a spreadsheet and DMing each member behind on thresholds is the single largest recurring volunteer-time cost identified in the research (`market research.md` §5 User Pain Signals; `problem.md` §6). Officers also lose attention to ticket triage without SLA visibility (`problem.md` §3) and reviewer-collision reconciliation in intake (`problem.md` §2). Permission-drift forensics comes up after the fact as a slower but recurring cost (`problem.md` §7). Officer attention is the scarcest resource (`problem.md` §9), and officer burnout is the dominant churn mechanism.

2. **Bot subscription fees.** Premium gating concentrates around exactly the features operators need most, from claim workflow through backup/restore (`market research.md` §3, §6, §7 Cross-cutting Findings). Operators typically pay $20-$40/mo across 3-5 premium bots for subsets of this functionality, with heavier custom or security stacks running higher: [MEE6 Premium](https://mee6.xyz/en/premium) at $5.99/mo per server, [Ticket Tool Premium](https://tickettool.xyz/premium) at $7.99/mo per server, [Dyno](https://dyno.gg/premium) at $5.99-$12.99/mo, [Carl-bot](https://carl.gg/get-premium) at $7.99-$35.99/mo depending on server count, and [Arcane](https://arcane.bot/premium) at $7/mo.

**Why the first wedge is painful enough to drive adoption.** Three of the fourteen problem axes describe active-harm patterns that compound as communities delay:

- **§5 Chapter lifecycle**: every subgroup created today increases future cleanup cost
- **§6 Activity tracking**: the weekly spreadsheet ritual is a primary burnout driver
- **§3 Case routing**: stalled harassment reports erode community trust, stalled appeals leave members in limbo

Communities feel this pain weekly. The research finds evidence-strong demand across all three surfaces (`market research.md` §2, §3, §5: strong evidence rating).

### Adjacent Expansion

After the gaming-guild wedge, adjacent coordination-heavy community types share the same operational profile:

- **Creator teams** coordinating moderators, editors, and contributors across Discord
- **Mod teams** for large servers running intake, appeals, and compliance on volunteer staff
- **Fandom communities** with officer hierarchies, chapter-style groupings, and event coordination
- **Esports organizations** with roster management, tryouts, and compliance across multiple teams

Each adjacent segment shares the same operational primitives that the gaming-guild wedge exercises first.

**Scope.** The wedge *is* the market for the foreseeable first milestone. A top-down "fraction of all Discord servers" projection lacks credibility at this stage, and the research explicitly warns against that framing (`research/pitch-deck-communication.md` Market Opportunity Communication).

Across the wedge and the adjacent segments, the operational profile resolves to a single architectural requirement: one audit chain that spans every subsystem.

---

## Operator-Owned Durable State Replaces Vendor Lock-In

Every operational decision is recorded once, and every subsystem consumes from the same causal chain. Guildies replaces the fragmented bot stack with a single system whose subsystems share a unified audit chain, from intake through governance. Instead of manually reconstructing what happened across five disconnected tools, officers work within a system that already knows how the pieces fit together.

Six structural commitments distinguish the design in the competitive field:

- **Durable operational state.** The system's database holds the operational record; Discord is the interaction surface. When the two diverge, system state is authoritative and Discord is reconciled (`proposal.md` Design Principles). Competing products treat Discord or a vendor dashboard as authoritative, which is why operational history evaporates when the vendor does.

- **Reconstructable decisions.** Every operational decision is recorded alongside the actor and its inputs, against prior state under the policy version active at transition time (`proposal.md` Design Principles). This is the causal chain the market research finds no competitor offers (`market research.md` Cross-cutting Findings).

- **Declarative intent with reconciliation.** Operators declare intended permission state and chapter structure, with compliance rules expressed in the same declarative form. The system compares intent against reality and surfaces drift (`proposal.md` Design Principles). No reviewed product exposes this control plane (`market research.md` §6 Gap Analysis).

- **Scoped authority.** Authority is granted per-scope, not per-rank. Chapter officers manage their chapter's operations inside defined boundaries with full audit visibility at central staff (`proposal.md` Design Principles). Discord's role hierarchy cannot express this; no reviewed product enforces it at the operation level (`market research.md` §6).

- **Attention-justified process.** Every mandatory human touchpoint has a named risk it mitigates. Routine state transitions automate; judgment calls are surfaced with grouped notifications rather than cascade alerts (`proposal.md` Design Principles; `problem.md` §9).

- **Platform boundary isolation.** The operational model is expressed in its own terms; the Discord layer translates. When Discord changes a feature, or when a community wants to export their operational history, neither the workflows nor the data are locked in a vendor-specific format (`proposal.md` Design Principles).

---

## How It Works

Three workflows drive the bulk of weekly burnout. The walkthroughs below contrast what officers do today with what Guildies does, so the shared audit chain shows up behaving the same way across different subsystems.

### Application Review Without Collisions

**Today:** An applicant submits a form. Three officers see it in a shared channel. Without coordinating, two of them start reviewing the same application. One DMs the applicant for more information, the other adds notes in a spreadsheet. Neither knows the other is working on it. When they reach different conclusions, a third officer has to sort it out.

**With Guildies:** The applicant submits through a versioned intake form. The application enters a queue routed to officers with authority over the target chapter. When an officer claims it, the system locks ownership so no one else can start a parallel review. The reviewer sees the applicant's trust profile and prior applications in one view, alongside the chapter's current roster state. Reviewers add notes or request an interview as needed, and can waitlist the applicant if a decision isn't ready. Final adjudication is approval or denial with a mandatory reason. Every transition is recorded. The form version is pinned at submission time, so even if the form is updated later, the submitted responses are evaluated against the questions originally asked.

Context stays with the application from submission through final resolution.

### Compliance Tracking Without Spreadsheets

**Today:** Every week, an officer pulls screenshots from the submission channel and transcribes the activity data into a spreadsheet. Each member is compared against chapter-specific thresholds, and violators are DMed individually. This process takes hours, is error-prone, and is the single largest source of volunteer burnout.

**With Guildies:** Members submit screenshot evidence through the system. Automated text extraction pulls structured activity data from the images and attaches a confidence score. The system evaluates each member against the chapter's configured compliance rules (such as attendance minimums and activity thresholds) on a scheduled basis. Clear-cut compliance cases process without human intervention. Violations and low-confidence extractions are routed to officers with enough context to confirm or override, and the officer can request more evidence when the screenshot is ambiguous. The officer spends time on judgment calls, not data entry.

The original screenshot is always preserved alongside extracted data. Officers can correct extraction errors, and corrections are stored with attribution. The system never auto-confirms compliance. It provides structured data, and officers make the final call on contested cases.

### Permission Governance Instead of Permission Guesswork

**Today:** An officer grants a temporary permission override during a crisis event. Two months later, nobody remembers who set it or why. Fifteen more ad hoc changes accumulate. A new admin looks at the permission configuration and can't tell which permissions are intentional and which are accidents.

**With Guildies:** Officers declare what permissions should exist and why. The system periodically compares the declared intent against Discord's actual permission state and surfaces every discrepancy. For each drift event, an officer can reconcile (apply the intent to Discord) or accept (update the intent to match reality). A third option is to acknowledge the drift as known and defer resolution for later. Temporary overrides have explicit expiration dates. When they expire, the system flags them for resolution instead of letting them silently become permanent.

Every resolution is recorded. At any point, an officer can explain why each permission exists: intentional grants are distinguishable from accepted exceptions, and anything still under review appears separately.

---

## Competitive Positioning

Officers do not buy Guildies against a single rival. They buy it against four classes of existing alternative, each with specific weaknesses the design addresses.

| Alternative | What it does well | Where it breaks | Guildies' position |
|---|---|---|---|
| **Manual status quo** (spreadsheets + DMs + memory) | Zero subscription cost, infinite flexibility | Breaks at roughly 100+ active members; compliance review, case routing, and permission audit all become volunteer-hour sinks (`problem.md` §6, §3, §7) | Automates routine state transitions; reserves officer attention for judgment calls |
| **Generic Discord bots** (MEE6, Dyno, Carl-bot, YAGPDB, Arcane) | Moderation, roles, logs, leveling, lightweight automation at scale | No persistent trust profiles, no policy versioning, no cross-workflow audit, no lifecycle-grade intake or compliance (`market research.md` §1, §7 Cross-Bot Gaps) | Unified operational model across all subsystems, not a collection of independent feature lanes |
| **Point tools** (Ticket Tool, Gather, Appy, Throney, Xenon, Guild Manager, etc.) | Deep feature in one lane: tickets, forms, attendance thresholds, backups, or roster | Each tool is local to its feature family; no shared causal chain; vendor instability (Gather deprecated, Guilded defunct) breaks operational continuity (`market research.md` §2, §7) | One audit chain spans applications, tickets, rosters, permissions, and compliance with community-owned durable state |
| **Potential incumbent feature overlap** (any bot adds, e.g., claim-lock or drift detection) | Can copy isolated features; distribution advantage | Cannot copy the integrated substrate, because a feature add sits next to the existing tool's data model without inheriting shared audit, scoped authority, policy versioning, or declared intent | Integration is the structural advantage incumbents cannot retrofit: the Phase 1 governance substrate is the floor every other subsystem consumes (`executive roadmap.md` Competitive Positioning) |

**Why the integration is harder to copy than any single feature.** Any incumbent can ship a claim-lock and add a drift detector without rewriting their core; mandatory resolution reasons are another common add. What they cannot ship incrementally is:

1. **A shared causal chain** that correlates one application approval with its downstream roster entry and permission grant as a single queryable sequence (`market research.md` Cross-cutting Findings).
2. **A declared-intent control plane** that spans permissions and compliance rules with preview-confirm edits and compare-and-swap semantics (`market research.md` §6, §7 Gap Analysis).
3. **Scoped authority enforced at the operation level**, not as a role-hierarchy capability set (`market research.md` §6).
4. **Lifecycle-first objects** like applications and tickets, with state machines governed by the policy version active at transition time (`proposal.md` Design Principles).

Each of those four is an architectural decision that has to be made before the first workflow ships. Incumbents that shipped workflows first cannot retrofit the substrate without re-architecting their product.

---

## Business Model

A defense built into the architecture, not into proprietary features, calls for pricing that reflects operational value, not feature count. Operators are paying for operational continuity and consolidated workflows, not a cheaper bot.

### Current Stage

**Pre-product.** No revenue. No paying users. The design and strategic roadmap are complete, with problem definition and competitive landscape documented alongside. Implementation is beginning (`executive roadmap.md` Phase 0: Foundations). The reference community is Humility itself (83 members during the operational sweep, per `NOTES.md`).

### Pricing Architecture

Two-tier SaaS pricing, anchored to the cost of the 3-5 premium bots operators already replace with Guildies (`research/market-economics.md` §2; `research/pricing-data.md`):

| Tier | Price | Target buyer |
|---|---:|---|
| **Individual guild** | **$29/mo** | Single-chapter gaming guilds, 50-500 members, running 3-5 premium bots plus spreadsheets today |
| **Multi-chapter org / alliance / esports org** | **$79/mo** | Coordination across multiple chapters, rosters, or teams with a shared governance substrate |
| **Design-partner tier** (time-limited) | **$50/mo** | Only offered with white-glove onboarding, migration, and prioritized roadmap access (`research/market-economics.md` §2) |

**Why these price points.** `$29/mo` sits above generic-bot premium pricing ([Carl-bot $5/mo](https://carl.gg/get-premium), [Dyno $5.99-$12.99/mo](https://dyno.gg/premium), [Ticket Tool $9.99/mo](https://tickettool.xyz/billing)) and below purpose-built guild software ([Guild Manager $19.99-$49.99/mo](https://guildmanager.app/pricing)), because Guildies consolidates 3-5 separate subscriptions into one bill while adding the audit chain those tools cannot offer. `$79/mo` sits below broader community operating systems ([Circle $89-$199/mo](https://circle.so/pricing), [Mighty Networks $79-$179/mo](https://www.mightynetworks.com/pricing)) and is the natural tier for multi-chapter organizations where Guildies' scoped authority and cross-subsystem audit chain earn their price (`research/market-economics.md` §2 Pricing benchmarks).

### ARR Trajectory

Bottom-up, wedge-first trajectory with explicit assumptions. These are not category-stretch goals; they are small fractions of existing Discord tooling's install base (`research/market-economics.md` §2 Plausible trajectory).

| Year | Paying guilds | Blended price | ARR | Assumptions |
|---|---:|---:|---:|---|
| **Year 1** | 50-100 | $20-$50/mo | **$25k-$60k** | Realistic for MVP + founder-led sales; 100 true design partners is possible but aggressive without pre-existing distribution |
| **Year 2** | 300-800 | $20-$25/mo | $72k-$240k | Achievable if the product clearly replaces multiple bots and wins a repeatable guild-admin use case |
| **Year 3** | 1,000-2,000 | $30/mo blended | **$360k-$720k** | Plausible if the company expands from single guilds into larger orgs and multi-chapter communities |

Year-1 and Year-2 ARR come entirely from the gaming-guild wedge described in the Market Opportunity section. Year-3's upper end depends on expansion into the adjacent coordination-heavy segments documented above, whose operational profile exercises the same primitives. That expansion is Phase 4+ roadmap territory, not Phase 1.

### Cost Structure

Infrastructure cost buckets from the committed decisions (`DECISIONS.md` D2, D5, D6). OCR figures assume **2,000 screenshots per community per month across 100 communities (200,000 screenshots/month)**; the blended per-screenshot rate is about $0.00160-$0.00168.

| Bucket | Driver | Estimate |
|---|---|---|
| **Vultr VKE infrastructure** | Continuously running service, durable storage, managed Kubernetes | ~$80-$130/mo for a realistic Phase 0 stack ([VKE cost doc](https://docs.vultr.com/support/products/vke/how-much-does-the-vultr-kubernetes-engine-cost), [Vultr pricing](https://www.vultr.com/pricing/), [Vultr Object Storage](https://www.vultr.com/products/object-storage/)) |
| **OCR pipeline (Google Cloud Vision primary)** | Per-image `DOCUMENT_TEXT_DETECTION` on 200,000 screenshots/mo | ~$299/mo after the 1,000-image free tier ([Google Cloud Vision pricing](https://cloud.google.com/vision/pricing)) |
| **OCR fallback (Gemini 3 Flash Preview paid tier)** | Vision-LLM fallback on ~5% of screenshots | ~$21-$36/mo ([Vertex AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)) |
| **Blended OCR total** | Vision primary + Gemini fallback | ~$320-$336/mo |
| **Discord API** | Gateway connection, HTTP API | $0 (free tier) |
| **Founder / engineering time** | Solo founder at current burn | Accounts for the remainder of monthly burn below |

### Burn, Runway, and Milestones

- **Current monthly burn:** **$9,500/mo**. Solo founder, self-funded via contract work covering the current burn
- **Current capacity on this project:** ~0.3-0.5 FTE (remainder of founder time on contract work)
- **Runway under proposed $300k-$500k pre-seed raise:** **24-36 months** at current burn plus modest scale-up (first UI hire triggered by MRR milestones, not calendar date)
- **Next de-risking milestone:** **MVP ship + 20-50 design partners + $15k MRR by month 12.** This validates willingness-to-pay and is the gate that justifies full-time founder commitment and the first UI hire.
- **Phase 2 validation milestone:** Once Phase 2 ships, the system runs structured applications and per-category ticket state machines alongside chapter provisioning and drift detection. The operational core that eight application tools, nine ticket tools, and eight multi-unit suites compete on today (`executive roadmap.md` Value Realization by Phase).

### Team Expansion Plan

Hire triggers are MRR-gated, not date-gated. Cash cost estimates use Kruze and Pave benchmarks (`research/market-economics.md` §4):

| Hire | Trigger | Approximate cash cost |
|---|---|---:|
| **Founder full-time commitment** | $15k-$25k MRR OR pre-seed close (whichever comes first) | Founder salary at current $9.5k/mo burn |
| **First UI engineer** | $15k-$25k MRR | ~$15.5k-$20.8k/mo ([Pave](https://www.pave.com/blog-posts/how-much-comp-should-the-first-engineer-get)) |
| **Product / technical product partner** | $25k-$40k MRR | ~$15.8k-$21.3k/mo ([Carta](https://carta.com/data/startup-compensation-h1-2025/)) |
| **Marketing / growth hire** | $35k-$50k MRR AND repeatable acquisition loop | ~$11.4k-$16.7k/mo ([TopStartups](https://topstartups.io/startup-salary-equity-database/?title=Marketing%20manager)) |
| **Full 4-person team** | $60k-$75k MRR | ~$52.5k-$68.5k/mo combined |

A 4-person team burn represents `0.39%-0.47%` of base-case SAM, which is feasible on the gaming-guild wedge alone. Classic VC-scale outcomes (`$10M ARR`) require `4.9%-9.8%` of modeled SAM and are not reachable without expansion into adjacent community-ops segments. Investors should read the hybrid verdict explicitly: the wedge supports a solid small-team business; VC-scale returns depend on the expansion bet (`research/market-economics.md` §4 Market-cap feasibility check).

---

## Risks and Mitigation

Four operational risks matter most to investors, and one market-cap risk sits beside them. The executive roadmap covers three additional risks with trigger indicators (`executive roadmap.md` Risk Register).

### Risk 1: Competitive window closure

**The scenario.** An incumbent (MEE6, Carl-bot, a guild suite, or a new entrant) ships an intent-vs-actual control plane with policy versioning, or a cross-subsystem causal audit, before Guildies does. Every `gap` classification in the market research is time-bounded to the current market snapshot (`executive roadmap.md` Risk Register #3).

**Why it matters.** Multiple differentiation claims depend on these capabilities remaining absent in the field. If they land elsewhere first, `gap` reclassifies as `parity` or `table-stakes` and the timing advantage compresses.

**Mitigation.** Re-run the market-misread risk gate at each phase boundary using fresh research. Phase 1 is explicitly a substrate investment in scoped authority and causal audit with policy versioning underneath, so that Phase 2+ workflows inherit a floor competitors cannot retrofit without re-architecting (`executive roadmap.md` Strategic Narrative, Phase 1).

**Milestone that proves the risk is contained.** Phase 1 completion. Once the governance substrate ships, new workflow features inherit the substrate and no feature-level incumbent response can copy the integration without their own substrate rebuild.

### Risk 2: Adoption friction from migration cost

**The scenario.** Communities adopting Guildies inherit all existing Discord permissions as "unintended" drift until classified. Operators experience first-run classification burden as a blocker (`executive roadmap.md` Risk Register #5).

**Why it matters.** Permission migration tooling is currently deferred. The onboarding cost is not yet scoped into a user-facing slice, and the switching-cost invisibility documented in `problem.md` §8 applies in reverse: communities undervalue the migration effort until they are in it.

**Mitigation.** Scope a one-time migration tool inside VS-008 (permission intent) engineering work. First-run classification is flagged as a known onboarding cost in Phase 2 go-to-market communication. Early design partners come from communities with explicit operator capacity for the initial classification pass.

**Milestone that proves the risk is contained.** First three design-partner communities complete first-run classification and are running Phase 2 workflows on the managed permission set without reported abandonment.

### Risk 3: OCR pipeline cost and quality uncertainty

**The scenario.** Screenshot-based compliance evaluation depends on OCR extraction being accurate enough to reduce officer review load rather than create a new review queue of low-confidence extractions. Cost per image also scales with community adoption.

**Why it matters.** The compliance workflow is the second-largest operator pain axis (`problem.md` §6, `market research.md` §5). If the OCR pipeline delivers quality below the threshold where officers trust it, the weekly spreadsheet ritual does not get replaced. It gets augmented with a new review queue.

**Mitigation.** The architecture decision commits to a mixed pipeline: classical OCR (Google Cloud Vision `DOCUMENT_TEXT_DETECTION`) as primary, vision-LLM (Gemini 3 Flash Preview paid) as fallback on low-confidence or ambiguous extractions (`DECISIONS.md` D6). Original screenshots are always preserved. When officers correct extractions, the corrections are stored with attribution. The system never auto-confirms compliance. Officers make the final call on contested cases.

**Milestone that proves the risk is contained.** Phase 4 VS-016 completion at the reference community: the weekly compliance ritual is measurably replaced by scheduled automated checks, with the low-confidence review queue small enough that total officer attention cost is lower than the spreadsheet baseline.

### Risk 4: Solo-founder execution capacity

**The scenario.** Guildies is currently a solo-founder project from Oulipoly. The founder is ~0.3-0.5 FTE on the project (remainder on contract work covering the $9,500/mo burn). If the founder cannot transition to full-time commitment by mid-2026, the Phase 1 → Phase 2 schedule slips and the timing-advantage risk (Risk 1) compounds in the background.

**Why it matters.** The strategic narrative assumes sustained engineering effort across Phase 0 → Phase 4. A solo founder at part-time capacity cannot ship Phase 2 on the timeline incumbent response will force.

**Mitigation.** Full-time founder commitment is explicitly gated on `$15k-$25k MRR` OR pre-seed close. Each phase is scoped to deliver operator-facing value on its own (`executive roadmap.md` Value Realization by Phase), so constrained capacity produces a coherent stopping point instead of a half-built substrate. The first UI hire triggers at $15k-$25k MRR once founder bandwidth is the binding constraint.

**Milestone that proves the risk is contained.** Phase 1 ships on schedule with founder full-time, and the first $15k MRR milestone triggers the first UI hire within 60 days.

### Risk 5: Market-cap capacity (hybrid outcome)

**The scenario.** The gaming-guild wedge alone does not support classic VC-scale returns. `$10M ARR` would require `4.9%-9.8%` of the modeled SAM (`research/market-economics.md` §4 Market-cap feasibility check), which is unlikely on the pure guild-management wedge. VC-scale outcomes require expansion into the adjacent coordination-heavy communities documented in Market Opportunity.

**Why it matters.** Investors sizing for VC-scale returns need to understand that this is a hybrid bet, not a guaranteed VC-scale wedge. The wedge can support a solid small-team business at $360k-$720k ARR. Expansion into broader Discord community operations is the path to larger outcomes, but that expansion is not Phase 1 scope.

**Mitigation.** The Phase 1 governance substrate (scoped authority, declared intent, causal audit) is explicitly designed as adjacent-community portable. The same primitives serve mod teams and esports orgs as readily as they serve gaming guilds. Expansion into those segments is Phase 4+ roadmap territory, explicitly positioned but not delivered until the wedge is proven. Investors should read the ask as: "fund the wedge; the expansion bet is optional upside that depends on wedge validation."

**Milestone that proves the risk is contained.** Year-3 ARR at the upper end of the modeled band ($720k) with at least one adjacent-segment design partner validating the expansion hypothesis.

---

## Roadmap

The governance substrate lands first so every later workflow inherits an audit chain and scoped authority. Each phase ships operator-facing value on its own, which means if contributor capacity or scope changes, the project has a coherent stopping point instead of a half-built substrate.

### Phase 1: Establish Operational Control

- Open and assign private cases with durable ownership, privacy guarantees, and category-specific routing
- Detect permission drift by declaring intended state and seeing where Discord reality has diverged
- Change live policies safely with previews, confirmation gates, and protection for in-flight work
- Provision new chapters consistently from templates with standard spaces, roles, and default policies
- Screen newcomers with a persistent trust profile built from transparent, inspectable signals

*After Phase 1, you can:* Run your most urgent operations through the system. Cases stay visible instead of disappearing into DMs. Against declared intent, permission audits run automatically and chapter creation follows templates. When live policies change, in-flight work is protected instead of broken.

*What still hurts:* Application review is not yet in the system. Compliance tracking is still manual. Cases can be opened and assigned but don't yet have escalation, SLA monitoring, or mandatory resolution workflows.

### Phase 2: Add Ownership and Local Operations

- Claim and review applications with exclusive ownership: no more duplicate reviews
- Enforce category-specific case escalation with SLA thresholds, mandatory reasons, and accountability
- Resolve permission drift explicitly by reconciling, accepting, or acknowledging each discrepancy
- Manage chapter rosters and leadership transitions with preserved authority and operational context

*After Phase 2, you can:* Run intake and case management with clear ownership and accountability. Officers resolve permission drift instead of ignoring it. Chapter leadership changes preserve pending decisions and operational history rather than dropping them.

*What still hurts:* Applications can be claimed and reviewed but don't yet support interviews, waitlists, or final adjudication decisions. Compliance is still evaluated outside the system.

### Phase 3: Close Admission and Monitoring Loops

- Decide applications with full adjudication: interviews, waitlists, approvals, denials, and mandatory reasons
- Evaluate chapter compliance from real evidence instead of spreadsheet transcription. Screenshots and game APIs feed the compliance engine directly, with manual reports handled through the same intake for exceptional cases

*After Phase 3, you can:* Run the complete intake lifecycle from submission through adjudication. Compliance evaluation processes evidence automatically and routes only the cases that need judgment to officers. The daily spreadsheet ritual is replaced by scheduled automated checks.

*What still hurts:* Compliance can identify violations but doesn't yet apply graduated consequences automatically. Officers still manually convert every detected violation into a roster action.

### Phase 4: Automate Graduated Enforcement

- Apply proportional compliance consequences (notification for minor cases, probation for repeat violations) with officer confirmation or override for ambiguous cases. Mid-severity events get flagged for review

*After Phase 4, you can:* Run compliance end-to-end. Routine violations are handled automatically with proportional responses. Officers focus on contested cases and overrides rather than processing every violation by hand.

*What's deferred:* Advanced chapter lifecycle operations (probation and archival automation), cross-ticket pattern detection, deep anti-nuke recovery, and richer trust signals beyond onboarding. These capabilities build on the foundations laid in earlier phases and will be prioritized based on community feedback.

---

## Team / Why Us

The governance substrate has to be designed by someone who has actually sat in the operator seat. Its architectural commitments (scoped authority and declared intent under causal audit) map to specific operator failure modes that abstract product design misses.

**Current team: solo founder.** No additional team members are committed. The founder self-funds runway via contract work at a current burn of **$9,500/mo** and spends approximately **0.3-0.5 FTE** on this project.

**Full-time founder commitment is gated on:** reaching **$15k-$25k MRR** OR **pre-seed close**, whichever comes first. That gate is stated explicitly: a solo founder burning $9,500/mo on contract-work-funded runway cannot go full-time until revenue or a close makes it feasible.

**Why this community.** Humility is the design reference community: 83 members during the original operational sweep (`NOTES.md`), with real chapter scaffolding and applications history against the exact operator pain profile the proposal targets. The design grew out of the daily operational work of running this community, not out of abstract theorizing.

**Founder background.**

- **nestharus** — founder of Oulipoly, solo builder of Guildies
- Humility server operator since 2022-04-04, running the community through the exact operator pain profile the product addresses
- Producing the strategic artifacts cited throughout this deck as the solo founder, including problem definition, competitive landscape across 50 products, executive roadmap, system design proposal, and economics research
- Implementation work on the `daemon/` package and API service underway, grounded in the design the deck references

**Team expansion plan.** Hire triggers are MRR-gated (see Business Model → Team Expansion Plan):

- **UI engineer:** triggered at $15k-$25k MRR, once founder bandwidth is the binding constraint on frontend delivery
- **Product / technical product partner:** triggered at $25k-$40k MRR
- **Marketing / growth hire:** triggered at $35k-$50k MRR AND a repeatable acquisition loop exists

The gaming-guild wedge supports a sustainable small-team business at Year-3 ARR of $360k-$720k. VC-scale returns require expansion beyond the wedge into adjacent coordination-heavy communities (creator, mod, fandom, esports). That expansion is Phase 4+ and depends on wedge validation (`research/market-economics.md` §4 Market-cap feasibility check).

**What the founder has already produced solo.**

- A complete problem definition across fourteen operational axes (`product-strategy/problem.md`)
- A competitive landscape analysis spanning 50 products across six categories (`product-strategy/market research.md`)
- An 18-value-slice executive roadmap with risk register and approval package (`product-strategy/executive roadmap.md`)
- A system design proposal with data model, subsystem boundaries, and operational semantics (`product-strategy/proposal.md`)
- Economics research with TAM/SAM/SOM, pricing, and raise structure (`product-strategy/research/market-economics.md`)
- Initial implementation beginning with `daemon/` package (applications subsystem live, DB helpers in place per `NOTES.md`)

The strategic artifacts cover roughly two quarters of foundation work that shapes the implementation, produced at ~0.3-0.5 FTE.

---

## The Ask

**Pre-seed raise, not seed.** A solo founder at $9,500/mo burn, pre-product, with no traction yet raises a **pre-seed round of $300k-$500k**, not a seed round. This is the size the economics justify (`research/market-economics.md` §3 Recommended raise size). It covers 24-36 months of runway at current burn plus modest scale-up, and it does not force the company into a premature team build before the wedge is validated.

### The Raise

- **Amount:** **$400k**
- **Structure (preferred):** SAFE with **$7.5M-$10M post-money cap**, the standard pre-seed benchmark ([Carta 2025 pre-seed benchmarks](https://carta.com/data/state-of-pre-seed-2025/): $7.5M median cap for rounds under $250k, $10M for $250k-$1M rounds). [90% of Carta pre-seed rounds in Q1 2025 were SAFEs](https://carta.com/learn/startups/fundraising/convertible-securities/pre-money-vs-post-money-safes/).
- **Structure (alternative):** Priced round at **$4M-$8M pre-money**, consistent with typical 15-25% first-round dilution ([Rebel Fund dilution benchmarks](https://www.rebelfund.vc/blog-posts/founder-dilution-benchmarks-seed-2025-stay-under-18-percent)).
- **Runway this buys:** **24-36 months** at current $9,500/mo burn, with scale-up to small team when MRR milestones trigger.

### What This Unlocks

Most of the raise extends the solo founder's runway to MVP and first design-partner validation. A small portion funds infrastructure and the first UI hire if MRR milestones trigger during the round:

- **Months 1-12:** Solo founder full-time, MVP delivery (Phase 1 + partial Phase 2), first 20-50 design-partner communities, first $15k MRR
- **Months 13-24:** First UI hire triggered at $15k-$25k MRR, Phase 2 completion, initial revenue scaling
- **Months 25-36 (upside window):** Product partner hire if $25k-$40k MRR, marketing hire if $35k-$50k MRR with repeatable acquisition loop
- **Infrastructure:** ~$400-$470/mo committed cost at 100-community scale (Vultr VKE + blended OCR)

### First Milestone (Month 12)

**MVP ship + 20-50 design partners + $15k MRR.** This milestone validates willingness-to-pay and justifies full-time founder commitment plus the first UI hire. At Phase 2, the platform runs structured applications and per-category ticket state machines alongside chapter provisioning and drift detection. The operational core that eight application tools and nine ticket tools monetize today.

### Hybrid Market-Cap Framing

The economics research verdict is **hybrid**, not pure VC-scale (`research/market-economics.md` §4 Market-cap feasibility check). Investors should understand what they are funding:

- **The gaming-guild wedge alone** supports a solid SaaS business at Year-3 ARR of `$360k-$720k` and a sustainable small team (1-4 people). A 4-person team burn represents `0.39%-0.47%` of base-case SAM, which is feasible on the wedge.
- **VC-scale returns** (`$10M ARR` = `4.9%-9.8%` of modeled SAM) are not reachable on the pure gaming-guild wedge. They require expansion into the adjacent coordination-heavy communities documented in Market Opportunity.

This is a hybrid bet. The wedge is solid; the expansion bet is real but unfunded in Phase 1. The Phase 1 governance substrate is deliberately designed as adjacent-community portable (scoped authority and declared intent work identically across these segments), so the expansion bet is structurally supported by the architecture even though it is Phase 4+ roadmap territory. Investors sizing for classic VC returns should weight the expansion probability explicitly rather than assuming it comes free with the wedge.

---

## Appendix / Q&A Preparation

Q&A material documented in the underlying strategy artifacts:

- **Detailed phase breakdown and value slices**: `product-strategy/executive roadmap.md` Phase Structure, Appendix C (18 value slices with scoring detail)
- **Full risk register** (7 risks with trigger indicators, beyond the 4 surfaced above): `product-strategy/executive roadmap.md` Risk Register
- **Competitive research methodology** (50 products across 6 categories, evidence strength per subsystem): `product-strategy/market research.md`
- **Problem axes** (14 operational difficulties with compounding consequences): `product-strategy/problem.md`
- **System design details** (data model, subsystem boundaries, cross-workflow semantics): `product-strategy/proposal.md`
- **Locked infrastructure decisions** (Vultr VKE, Google Cloud Vision primary + Gemini 3 Flash Preview fallback, cloud-hosted architecture): `DECISIONS.md`
