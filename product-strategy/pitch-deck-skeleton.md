# Skeleton: Pitch Deck

## Heading Outline
- `1` Humility: One Platform for the Whole Operation
- `2` The Problem
- `3` The Current Landscape
- `4` Why Now
- `5` Market Opportunity
- `5.1` The First Wedge: Coordination-Heavy Gaming Guilds
- `5.2` Adjacent Expansion
- `6` Solution
- `7` How It Works
- `7.1` Application Review Without Collisions
- `7.2` Compliance Tracking Without Spreadsheets
- `7.3` Permission Governance Instead of Permission Guesswork
- `8` Competitive Positioning
- `9` Business / Funding Model
- `9.1` Current Stage
- `9.2` Path A: Open-Source Community Project
- `9.3` Path B: Hosted SaaS (Future Consideration)
- `9.4` Cost Structure
- `9.5` Burn, Runway, and Milestone
- `10` Risks and Mitigation
- `10.1` Risk 1: Competitive window closure
- `10.2` Risk 2: Adoption friction from migration cost
- `10.3` Risk 3: OCR pipeline cost and quality uncertainty
- `10.4` Risk 4: Volunteer contributor sustainability
- `11` Roadmap
- `11.1` Phase 1: Establish Operational Control
- `11.2` Phase 2: Add Ownership and Local Operations
- `11.3` Phase 3: Close Admission and Monitoring Loops
- `11.4` Phase 4: Automate Graduated Enforcement
- `12` Team / Why Us
- `13` The Ask
- `13.1` For Investors / Financial Backers
- `13.2` For Community Sponsors (Open-Source Path)
- `13.3` For Contributors / Design Partners
- `14` Appendix / Q&A Preparation

## First Sentence of Each Paragraph
Table rows omitted; list items included because they function as paragraph blocks in the draft.

### 1. Humility: One Platform for the Whole Operation
1. `*A unified guild-management system that replaces fragmented bot stacks and manual spreadsheets with durable, auditable operational workflows.*`

### 2. The Problem
1. `> It's Monday morning.`
2. `This is the daily reality for officers running gaming communities on Discord.`
3. `- **Compliance tracking is manual labor.**`
4. `- **Cases disappear into ad hoc channels.**`
5. `- **Applications collide.**`
6. `- **Permissions drift invisibly.**`
7. `- **Volunteer attention is the scarcest resource.**`

### 3. The Current Landscape
1. `Officers today solve these problems by stitching together five or more disconnected tools: one bot for tickets, one for applications, one for moderation logs, one for reaction roles, a spreadsheet for compliance tracking, and DMs for everything that doesn't fit.`
2. `Each tool solves one thing.`
3. `**Ticket bots** like Ticket Tool, Helper.gg, Discord Tickets, and Modmail handle case creation and transcripts, but their workflows are action-based — open, claim, close — not lifecycle-based.`
4. `**Application tools** like Appy, Application Bot, and ApplicationForms provide form submission and dashboard review, but reviewer collision prevention is essentially absent across the field.`
5. `**Activity and roster tools** like Throney, Guild Manager, and Raid-Helper track attendance and participation, but a general-purpose compliance engine — configurable rules, chapter-specific thresholds, automatic consequence workflows — is still missing.`
6. `**Permission and security bots** like Wick, Dyno, Carl-bot, and Xenon automate roles, monitor dangerous permissions, and back up server state.`
7. `**The fundamental gap:** audit is fragmented and local.`

### 4. Why Now
1. `The conditions that make an integrated guild-operations platform viable did not exist two years ago.`
2. `**Incumbents are exiting the market.**`
3. `**Market gaps are documented, not speculative.**`
4. `**The technical enablers are mature.**`
5. `**Premium gating has pushed lock-in past operators' tolerance.**`
6. `**The window is finite.**`

### 5. Market Opportunity
1. `This is not a Discord-wide TAM play.`

### 5.1 The First Wedge: Coordination-Heavy Gaming Guilds
1. `**Who buys first.**`
2. `- Multiple officers share responsibility for intake, compliance, and cases`
3. `- Three to five Discord bots plus at least one spreadsheet compose the operational stack (`market research.md` §4 Community Management Workarounds: "the common workaround is \`Discord + Google Sheets/Excel + one or more bots + optional guild website\`")`
4. `- Chapter-specific activity thresholds, intake rules, and authority boundaries exist but are enforced manually`
5. `- Officer turnover creates repeated onboarding loss`
6. `**What they spend today.**`
7. `1. **Officer time.**`
8. `2. **Bot subscription fees.**`
9. `**Why the first wedge is painful enough to drive adoption.**`
10. `- **§5 Chapter lifecycle** — every subgroup created today increases future cleanup cost`
11. `- **§6 Activity tracking** — the weekly spreadsheet ritual is a primary burnout driver`
12. `- **§3 Case routing** — stalled harassment reports erode community trust, stalled appeals leave members in limbo`
13. `Communities feel this pain weekly.`

### 5.2 Adjacent Expansion
1. `After the gaming-guild wedge, adjacent coordination-heavy community types share the same operational profile:`
2. `- **Creator teams** coordinating moderators, editors, and contributors across Discord`
3. `- **Mod teams** for large servers running intake, appeals, and compliance on volunteer staff`
4. `- **Fandom communities** with officer hierarchies, chapter-style groupings, and event coordination`
5. `- **Esports organizations** with roster management, tryouts, and compliance across multiple teams`
6. `Each adjacent segment shares the core operational primitives — intake, cases, rosters, permissions, audit — that the gaming-guild wedge exercises first.`
7. `**Honest framing.**`

### 6. Solution
1. `**Operator-owned durable state replaces vendor lock-in.**`
2. `Humility replaces the fragmented bot stack with a single system where intake, cases, compliance, permissions, chapters, and governance share a unified audit chain.`
3. `The design is built on structural commitments investors can evaluate against the competitive field:`
4. `- **Durable operational state.**`
5. `- **Reconstructable decisions.**`
6. `- **Declarative intent with reconciliation.**`
7. `- **Scoped authority.**`
8. `- **Attention-justified process.**`
9. `- **Platform boundary isolation.**`

### 7.1 Application Review Without Collisions
1. `**Today:** An applicant submits a form.`
2. `**With Humility:** The applicant submits through a versioned intake form.`
3. `No duplicate reviews.`

### 7.2 Compliance Tracking Without Spreadsheets
1. `**Today:** Every week, an officer opens a screenshot channel, downloads images, manually transcribes activity data into a spreadsheet, compares each member against chapter-specific thresholds, identifies violations, and DMs members individually.`
2. `**With Humility:** Members submit screenshot evidence through the system.`
3. `The original screenshot is always preserved alongside extracted data.`

### 7.3 Permission Governance Instead of Permission Guesswork
1. `**Today:** An officer grants a temporary permission override during a crisis event.`
2. `**With Humility:** Officers declare what permissions should exist and why.`
3. `Every resolution is recorded.`

### 8. Competitive Positioning
1. `Officers do not buy Humility against a single rival.`
2. `**Why the integration is harder to copy than any single feature.**`
3. `1. **A shared causal chain** that correlates one application approval with its downstream roster entry, compliance activation, and permission grant as a single queryable sequence (\`market research.md\` Cross-cutting Findings).`
4. `2. **A declared-intent control plane** that spans permissions, policy, and compliance rules with preview-confirm edits and compare-and-swap semantics (\`market research.md\` §6, §7 Gap Analysis).`
5. `3. **Scoped authority enforced at the operation level**, not as a role-hierarchy capability set (\`market research.md\` §6).`
6. `4. **Lifecycle-first objects** (applications, tickets, chapters, members) with state machines governed by the policy version active at transition time (\`proposal.md\` Design Principles).`
7. `Each of those four is an architectural decision that has to be made before the first workflow ships.`

### 9. Business / Funding Model
1. `Humility is currently positioned as a community-driven open-source project with two potential monetization paths.`

### 9.1 Current Stage
1. `**Pre-product.**`
2. `The ask is not revenue — it is commitment to build the Phase 1 governance foundation and the Phase 2 operational workflows that first replace the bot stack for the reference community and initial design partners.`

### 9.2 Path A: Open-Source Community Project
1. `The project ships as open source with infrastructure costs covered by community funding — GitHub Sponsors, Open Collective, or equivalent.`
2. `**What backers get:**`
3. `- Operational continuity: the codebase and data model survive regardless of any single operator's involvement`
4. `- Governance influence: sponsor-priority input on roadmap sequencing within the Non-goals boundaries (\`executive roadmap.md\` Approval Package)`
5. `- Design-partner access: early operator feedback loops on Phase 1 and Phase 2 slices`

### 9.3 Path B: Hosted SaaS (Future Consideration)
1. `A managed-hosting tier for communities that want the platform without running the Vultr VKE infrastructure themselves.`
2. `**What the milestone-to-willingness-to-pay path looks like:** ship Phase 2 to design-partner communities → measure which operator features cross the threshold of "I would rather pay than re-assemble the bot stack" → decide whether to offer the hosted tier based on that evidence.`

### 9.4 Cost Structure
1. `Honest cost buckets from the committed infrastructure decisions (\`DECISIONS.md\` D2, D5, D6):`

### 9.5 Burn, Runway, and Milestone
1. `- **Current monthly burn:** [BRACKETED: user to provide]`
2. `- **Projected monthly burn under proposed commitment:** [BRACKETED: user to provide]`
3. `- **Runway under proposed raise / commitment:** [BRACKETED: user to provide; typical seed/Series-A target is 12–18 months per \`research/pitch-deck-communication.md\` Financial Communication]`
4. `- **Next de-risking milestone:** Phase 2 completion.`

### 10. Risks and Mitigation
1. `The executive roadmap's risk register names seven specific risks with trigger indicators (\`executive roadmap.md\` Risk Register).`

### 10.1 Risk 1: Competitive window closure
1. `**What could happen.**`
2. `**Why it matters.**`
3. `**Mitigation.**`
4. `**Milestone that proves the risk is contained.**`

### 10.2 Risk 2: Adoption friction from migration cost
1. `**What could happen.**`
2. `**Why it matters.**`
3. `**Mitigation.**`
4. `**Milestone that proves the risk is contained.**`

### 10.3 Risk 3: OCR pipeline cost and quality uncertainty
1. `**What could happen.**`
2. `**Why it matters.**`
3. `**Mitigation.**`
4. `**Milestone that proves the risk is contained.**`

### 10.4 Risk 4: Volunteer contributor sustainability
1. `**What could happen.**`
2. `**Why it matters.**`
3. `**Mitigation.**`
4. `**Milestone that proves the risk is contained.**`

### 11.1 Phase 1: Establish Operational Control
1. `- Open and assign private cases with durable ownership, privacy guarantees, and category-specific routing`
2. `- Detect permission drift by declaring intended state and seeing where Discord reality has diverged`
3. `- Change live policies safely with previews, confirmation gates, and protection for in-flight work`
4. `- Provision new chapters consistently from templates with standard spaces, roles, and default policies`
5. `- Screen newcomers with a persistent trust profile built from transparent, inspectable signals`
6. `*After Phase 1, you can:* Run your most urgent operations through the system — open cases without them disappearing into DMs, audit permissions against declared intent, create chapters without manual one-off setup, and change operational rules on a live server without breaking work in progress.`
7. `*What still hurts:* Application review is not yet in the system.`

### 11.2 Phase 2: Add Ownership and Local Operations
1. `- Claim and review applications with exclusive ownership — no more duplicate reviews`
2. `- Enforce category-specific case escalation with SLA thresholds, mandatory reasons, and accountability`
3. `- Resolve permission drift explicitly by reconciling, accepting, or acknowledging each discrepancy`
4. `- Manage chapter rosters and leadership transitions with preserved authority and operational context`
5. `*After Phase 2, you can:* Run intake and case management with clear ownership and accountability.`
6. `*What still hurts:* Applications can be claimed and reviewed but don't yet support interviews, waitlists, or final adjudication decisions.`

### 11.3 Phase 3: Close Admission and Monitoring Loops
1. `- Decide applications with full adjudication — interviews, waitlists, approvals, denials, and mandatory reasons`
2. `- Evaluate chapter compliance from screenshot evidence, game APIs, and manual reports instead of spreadsheets`
3. `*After Phase 3, you can:* Run the complete intake lifecycle from submission through adjudication.`
4. `*What still hurts:* Compliance can identify violations but doesn't yet apply graduated consequences automatically.`

### 11.4 Phase 4: Automate Graduated Enforcement
1. `- Apply proportional compliance consequences — notification, flag for review, or automatic probation — with officer confirmation or override for ambiguous cases`
2. `*After Phase 4, you can:* Run compliance end-to-end.`
3. `*What's deferred:* Advanced chapter lifecycle operations (probation and archival automation), cross-ticket pattern detection, deep anti-nuke recovery, and richer trust signals beyond onboarding.`

### 12. Team / Why Us
1. `[BRACKETED: This section to be completed by the user. Suggested structure below.]`
2. `**Why this community.**`
3. `**Why now is the right moment for this team.**`
4. `- [BRACKETED: Founder / lead maintainer name and relevant experience — e.g., years operating the Humility community, prior software engineering experience, domain expertise in community operations or platform design]`
5. `- [BRACKETED: Additional contributors or advisors if applicable — roles and what they bring]`
6. `- [BRACKETED: Specific experience with Discord's platform, operational workflows, or relevant technical domains (OCR, distributed systems, community governance)]`
7. `**What this team has already produced.**`
8. `- A complete problem definition across fourteen operational axes (\`product-strategy/problem.md\`)`
9. `- A competitive landscape analysis spanning 50 products across six categories (\`product-strategy/market research.md\`)`
10. `- A 18-value-slice executive roadmap with risk register and approval package (\`product-strategy/executive roadmap.md\`)`
11. `- A system design proposal with data model, subsystem boundaries, and operational semantics (\`product-strategy/proposal.md\`)`
12. `- Initial implementation beginning with \`daemon/\` package (applications subsystem live, DB helpers in place per \`NOTES.md\`)`
13. `The strategic artifacts represent the work a well-capitalized team would otherwise spend its first two quarters producing before writing implementation code.`

### 13.1 For Investors / Financial Backers
1. `**Ask:** [BRACKETED: specific commitment amount — user to fill based on cost structure and target runway]`
2. `**What this unlocks:**`
3. `- Delivery of Phase 1 (governance foundation) and Phase 2 (core operational workflows)`
4. `- Infrastructure runway for [BRACKETED: months] at the projected burn`
5. `- Design-partner engagement with [BRACKETED: target count] initial communities beyond Humility as the reference`
6. `**Milestone this funds:** Phase 2 completion.`

### 13.2 For Community Sponsors (Open-Source Path)
1. `**Ask:** [BRACKETED: monthly sponsorship range or per-tier amount — user to fill after GitHub Sponsors / Open Collective setup]`
2. `**What sponsors get:**`
3. `- Operational continuity — a community-owned alternative to vendor-dependent bot stacks that have already deprecated or shut down`
4. `- Governance influence within the documented Non-goals boundaries (\`executive roadmap.md\` Approval Package)`
5. `- Recognition and sponsor visibility per the open-source funding patterns that work in practice (\`research/pitch-deck-communication.md\` Open Source / Community Project Patterns)`

### 13.3 For Contributors / Design Partners
1. `**Ask:** Time, feedback, and early adoption.`
2. `This is the stage where community input has the most leverage.`
3. `- **Review the roadmap** and tell us what's missing or misordered`
4. `- **Describe your worst operational pain point** — the thing that makes you dread logging in`
5. `- **Test Phase 1 and Phase 2 builds** against your community's actual workflows and tell us where the system doesn't match how you operate`
6. `The goal is a platform that earns adoption by solving real problems for the people who do the work.`

### 14. Appendix / Q&A Preparation
1. `The main deck above addresses the core investor spine.`
2. `- **Detailed phase breakdown and value slices** — \`product-strategy/executive roadmap.md\` Phase Structure, Appendix C (18 value slices with scoring detail)`
3. `- **Full risk register** (7 risks with trigger indicators, beyond the 4 surfaced above) — \`product-strategy/executive roadmap.md\` Risk Register`
4. `- **Competitive research methodology** (50 products across 6 categories, evidence strength per subsystem) — \`product-strategy/market research.md\``
5. `- **Problem axes** (14 operational difficulties with compounding consequences) — \`product-strategy/problem.md\``
6. `- **System design details** (data model, subsystem boundaries, cross-workflow semantics) — \`product-strategy/proposal.md\``
7. `- **Locked infrastructure decisions** (Vultr VKE, Google Cloud Vision primary + Gemini 3 Flash Preview fallback, cloud-hosted architecture) — \`DECISIONS.md\``

## Border List
- `1 -> 2` Last: `*A unified guild-management system that replaces fragmented bot stacks and manual spreadsheets with durable, auditable operational workflows.*` First: `> It's Monday morning.` Note: `clear` — the subtitle promises operational pain and the next move cashes it out with a concrete scene.
- `2 -> 3` Last: `When the system requires constant human arbitration to stay coherent, officers burn out and leave.` First: `Officers today solve these problems by stitching together five or more disconnected tools: one bot for tickets, one for applications, one for moderation logs, one for reaction roles, a spreadsheet for compliance tracking, and DMs for everything that doesn't fit.` Note: `clear` — the border explains burnout, then immediately identifies the fragmented stack causing it.
- `3 -> 4` Last: `No existing tool answers the question: "What is this member's full operational history?"` First: `The conditions that make an integrated guild-operations platform viable did not exist two years ago.` Note: `clear` — the deck moves from market gap to timing window with a recognizable why-now handoff.
- `4 -> 5` Last: `The research refresh cadence is built into the roadmap, but the moment to start is now.` First: `This is not a Discord-wide TAM play.` Note: `weak` — urgency hands off to market sizing abruptly; the reader has to infer why the next move is market framing.
- `5 -> 5.1` Last: `This is not a Discord-wide TAM play.` First: `**Who buys first.**` Note: `clear` — the section promise is narrow market framing, and the subsection immediately defines the wedge.
- `5.1 -> 5.2` Last: `Communities feel this pain weekly.` First: `After the gaming-guild wedge, adjacent coordination-heavy community types share the same operational profile:` Note: `clear` — the deck moves from painful initial wedge to expansion logic directly.
- `5.2 -> 6` Last: `A top-down "fraction of all Discord servers" projection would not be credible for this stage, and the research explicitly warns against that framing (\`research/pitch-deck-communication.md\` Market Opportunity Communication).` First: `**Operator-owned durable state replaces vendor lock-in.**` Note: `weak` — the move from market framing to product thesis relies on the heading, not on a sentence that links buyer pain to the proposed system.
- `6 -> 7.1` Last: `When Discord changes a feature — or when a community wants to export their operational history — neither the workflows nor the data are locked in a vendor-specific format.` First: `**Today:** An applicant submits a form.` Note: `clear` — the abstract thesis gives way to a concrete workflow example, which is the right next move.
- `7.1 -> 7.2` Last: `No duplicate reviews.` First: `**Today:** Every week, an officer opens a screenshot channel, downloads images, manually transcribes activity data into a spreadsheet, compares each member against chapter-specific thresholds, identifies violations, and DMs members individually.` Note: `clear` — the deck is still in example mode, and it clearly switches to the next workflow pain point.
- `7.2 -> 7.3` Last: `The system never auto-confirms compliance — it provides structured data, and officers make the final call on contested cases.` First: `**Today:** An officer grants a temporary permission override during a crisis event.` Note: `clear` — both sections stay inside the "how it works" frame and change only the subsystem.
- `7.3 -> 8` Last: `At any point, an officer can explain exactly which permissions are intentional, which are under review, and which were accepted as exceptions.` First: `Officers do not buy Humility against a single rival.` Note: `clear` — the last workflow claim becomes the setup for competitive comparison.
- `8 -> 9` Last: `Incumbents that shipped workflows first cannot retrofit the substrate without re-architecting their product.` First: `Humility is currently positioned as a community-driven open-source project with two potential monetization paths.` Note: `weak` — the move from moat to business model is standard deck logic, but no bridge sentence explains why this positioning follows from the product thesis.
- `9 -> 9.1` Last: `Humility is currently positioned as a community-driven open-source project with two potential monetization paths.` First: `**Pre-product.**` Note: `clear` — the intro promises monetization-path framing and the subsection begins with present-stage status.
- `9.1 -> 9.2` Last: `The ask is not revenue — it is commitment to build the Phase 1 governance foundation and the Phase 2 operational workflows that first replace the bot stack for the reference community and initial design partners.` First: `The project ships as open source with infrastructure costs covered by community funding — GitHub Sponsors, Open Collective, or equivalent.` Note: `clear` — the current-stage paragraph tees up the first monetization path directly.
- `9.2 -> 9.3` Last: `- Design-partner access: early operator feedback loops on Phase 1 and Phase 2 slices` First: `A managed-hosting tier for communities that want the platform without running the Vultr VKE infrastructure themselves.` Note: `weak` — the switch from sponsor benefits to hosted SaaS has no explicit comparison or rationale sentence.
- `9.3 -> 9.4` Last: `**What the milestone-to-willingness-to-pay path looks like:** ship Phase 2 to design-partner communities → measure which operator features cross the threshold of "I would rather pay than re-assemble the bot stack" → decide whether to offer the hosted tier based on that evidence.` First: `Honest cost buckets from the committed infrastructure decisions (\`DECISIONS.md\` D2, D5, D6):` Note: `clear` — willingness-to-pay naturally hands off to cost structure.
- `9.4 -> 9.5` Last: `Honest cost buckets from the committed infrastructure decisions (\`DECISIONS.md\` D2, D5, D6):` First: `- **Current monthly burn:** [BRACKETED: user to provide]` Note: `weak` — the table-to-bullets transition is functional, but there is no sentence-level bridge.
- `9.5 -> 10` Last: `Reaching Phase 2 validates that the Phase 1 governance substrate delivers integrated workflows, not just primitives.` First: `The executive roadmap's risk register names seven specific risks with trigger indicators (\`executive roadmap.md\` Risk Register).` Note: `weak` — milestone and risk register belong near each other, but the narrative handoff is mechanical.
- `10 -> 10.1` Last: `The four most material to investors are surfaced here with mitigation plans and the milestone that demonstrates each risk is contained.` First: `**What could happen.**` Note: `clear` — the intro explicitly sets up the risk subsections.
- `10.1 -> 10.2` Last: `Once the governance substrate ships, new workflow features inherit the substrate and no feature-level incumbent response can copy the integration without their own substrate rebuild.` First: `**What could happen.**` Note: `weak` — the repetition of the same subsection template obscures the transition.
- `10.2 -> 10.3` Last: `First three design-partner communities complete first-run classification and are running Phase 2 workflows on the managed permission set without reported abandonment.` First: `**What could happen.**` Note: `weak` — same template repetition; the reader moves because the heading changes, not because the prose does.
- `10.3 -> 10.4` Last: `Phase 4 VS-016 completion at the reference community: the weekly compliance ritual is measurably replaced by scheduled automated checks, with the low-confidence review queue small enough that total officer attention cost is lower than the spreadsheet baseline.` First: `**What could happen.**` Note: `weak` — same issue; the risk cadence is structurally visible.
- `10.4 -> 11.1` Last: `A reproducible contribution loop reduces single-point-of-failure risk.` First: `- Open and assign private cases with durable ownership, privacy guarantees, and category-specific routing` Note: `weak` — the deck jumps from risk mitigation to roadmap bullets with no sentence explaining the shift to execution sequencing.
- `11.1 -> 11.2` Last: `Cases can be opened and assigned but don't yet have escalation, SLA monitoring, or mandatory resolution workflows.` First: `- Claim and review applications with exclusive ownership — no more duplicate reviews` Note: `clear` — the phase gap becomes the next phase's first item.
- `11.2 -> 11.3` Last: `Compliance is still evaluated outside the system.` First: `- Decide applications with full adjudication — interviews, waitlists, approvals, denials, and mandatory reasons` Note: `clear` — the "what still hurts" mechanic cleanly hands off to the next phase.
- `11.3 -> 11.4` Last: `Officers still manually convert every detected violation into a roster action.` First: `- Apply proportional compliance consequences — notification, flag for review, or automatic probation — with officer confirmation or override for ambiguous cases` Note: `clear` — the unresolved pain becomes the next phase's content.
- `11.4 -> 12` Last: `These capabilities build on the foundations laid in earlier phases and will be prioritized based on community feedback.` First: `[BRACKETED: This section to be completed by the user. Suggested structure below.]` Note: `weak` — the move from roadmap to credibility is already abrupt, and the placeholder makes the break harsher.
- `12 -> 13.1` Last: `That work is already done.` First: `**Ask:** [BRACKETED: specific commitment amount — user to fill based on cost structure and target runway]` Note: `weak` — "why us" should earn the ask, but the placeholder-heavy team section prevents a confident bridge.
- `13.1 -> 13.2` Last: `**Milestone this funds:** Phase 2 completion.` First: `**Ask:** [BRACKETED: monthly sponsorship range or per-tier amount — user to fill after GitHub Sponsors / Open Collective setup]` Note: `clear` — the deck is explicitly cycling through ask variants.
- `13.2 -> 13.3` Last: `- Recognition and sponsor visibility per the open-source funding patterns that work in practice (\`research/pitch-deck-communication.md\` Open Source / Community Project Patterns)` First: `**Ask:** Time, feedback, and early adoption.` Note: `clear` — the move from money ask to contribution ask is obvious.
- `13.3 -> 14` Last: `Your experience is the input that makes that possible.` First: `The main deck above addresses the core investor spine.` Note: `clear` — the deck closes the main narrative, then explicitly shifts into appendix/Q&A mode.

## Structural Issues Identified

### Visible templates
- `## The Problem`
- `## Solution`
- `## Business / Funding Model`
- `## Risks and Mitigation`
- `## Team / Why Us`
- `## The Ask`
- `## Appendix / Q&A Preparation`

### Missing narrative steps
- The core hypothesis is delayed. The opening gives hook, reframe, and pain, but the confident thesis about operator-owned durable state does not arrive until `## Solution`.
- The lens shift is late. The deck spends a long time describing fragmented tools before fully naming the deeper reframe: the missing thing is a shared operational substrate with a causal audit chain.
- The "why this team can execute now" beat is structurally present but functionally absent because `## Team / Why Us` is still bracketed and incomplete.
- The later funding story cannot fully close because the concrete financial ask and economics are still placeholders, so the narrative reaches `## The Ask` without a finished commitment shape.

### Weak borders
- `Why Now -> Market Opportunity` shifts from urgency to sizing without a sentence that explains why the next move is buyer definition.
- `Adjacent Expansion -> Solution` jumps from segment framing to product thesis with no explicit bridge from buyer pain to the system claim.
- `Competitive Positioning -> Business / Funding Model` moves from moat to monetization as a deck slot change rather than a prose-driven transition.
- `Risk 4 -> Roadmap` drops from risk mitigation into execution bullets without a sentence that reframes the roadmap as the answer to those risks.
- `Phase 4 -> Team / Why Us` is abrupt, and the placeholder at the top of the team section makes the handoff feel even more unfinished.
- `Team / Why Us -> The Ask` should feel earned, but the incomplete team section weakens the causal move into funding.

### Other structural concerns
- The skeleton is highly visible because many major headings name pitch-deck functions rather than the specific claim being advanced.
- Several container headings have no framing prose of their own: `## How It Works`, `## Roadmap`, and `## The Ask` rely on subheads to do the actual narrative work.
- The repeated subsection template inside `## Risks and Mitigation` (`What could happen / Why it matters / Mitigation / Milestone`) makes the structure conspicuous.
- The deck reads more like a thorough memo than a tight pitch narrative; the skeleton shows long report-style coverage before the thesis fully lands.
- Bracketed placeholders in `## Team / Why Us`, `### Cost Structure`, `### Burn, Runway, and Milestone`, and `## The Ask` create structural holes, not just missing facts.
