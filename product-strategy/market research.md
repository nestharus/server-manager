# Market Research Synthesis

## Methodology

This synthesis uses six pre-gathered market reports in `market-data/`, covering 50 product profiles across general Discord bots, intake/application tools, ticketing systems, activity/roster tools, permission/security bots, and broader guild-management platforms. The source reports normalize complaint material into recurring pain signals rather than a raw per-review census, so this document counts independent product sources when classifying evidence strength. Pricing, plan shape, and gap-analysis sections across all six reports were used as value indicators.

## Findings by Subsystem

### 1. Identity and Trust

**Competitive landscape:**
- Wick, Security Bot, and Double Counter all address trust at the server edge through verification, join gating, suspicious-account filtering, anti-alt signals, and limited custom moderator authorities, but they stop at role-, command-, or whitelist-driven controls rather than durable per-scope trust records. Source: `research-permissions.md`, Wick; Security Bot; Double Counter.
- Guild Manager and Guildbase add identity-linked profiles or application-side risk signals, and Wick Bot is one of the few broader suites that explicitly covers verification plus moderation cases, but none of them expose inspectable trust signals, deterministic trust recomputation, or chapter-specific trust portability. Source: `research-platforms.md`, Guild Manager; Guildbase; Wick Bot.
- Intake products such as Gather and Appy can collect identity fields and gate outcomes through roles, but trust remains attached to the application workflow rather than to a persistent member dossier that survives later reviews or chapter transfers. Source: `research-applications.md`, Gather; Appy.
- The general bot cohort mostly stops at roles, warnings, leveling, and verification-style affordances; the report's cross-bot gap section explicitly calls out the absence of persistent trust profiles, trust signals, reputation graphs, and operator-facing member dossiers. Source: `research-general.md`, Cross-Bot Gaps.

**User pain signals:**
- False positives are a recurring pain in verification-heavy products: Wick surfaces complaints about legitimate users being rejected by account-age or alt-detection style checks, and Double Counter surfaces VPN/shared-network false positives. Evidence strength: moderate. Source: `research-permissions.md`, Wick — Limitations & User Complaints; Double Counter — Limitations & User Complaints.
- Privacy tradeoffs are visible wherever identity confidence depends on aggressive evidence collection: Double Counter draws privacy criticism for fingerprinting-style checks, while form platforms surface file-upload and identity-linking concerns. Evidence strength: moderate. Source: `research-permissions.md`, Double Counter — Limitations & User Complaints; `research-applications.md`, Google Forms + Discord Automation — Limitations & User Complaints; Typeform + Discord Automation — Decision Tracking.
- Reviewers rarely see trust context where decisions happen. The applications report explicitly calls out missing prior-application context and trust-profile integration, the general-bot report says current bots stop at roles and warnings, and the platforms report shows risk flags at most rather than a shared trust model. Evidence strength: strong. Source: `research-applications.md`, Gap Analysis; `research-general.md`, Cross-Bot Gaps; `research-platforms.md`, Guildbase — Subsystem Coverage; Gap Analysis.

**Value indicators:**
- Demand for newcomer screening and risk scoring is strong. Evidence count: 6 sources. Strength: strong. Operators are already paying for join gates, anti-alt checks, suspicious-account filtering, and application-side risk analysis in Wick, Security Bot, Double Counter, Wick Bot, Guild Manager, and Guildbase. Source: `research-permissions.md`, Wick; Security Bot; Double Counter; `research-platforms.md`, Wick Bot; Guild Manager; Guildbase.
- Demand for a richer operator trust view is present but indirect. Evidence count: 5 sources. Strength: strong. The signal comes from repeated gaps rather than from a mature standalone product category: Gather/Appy-class intake tools, the general bot cohort, and the platforms scan all note the absence of trust-profile context in review flows. Source: `research-applications.md`, Gap Analysis; `research-general.md`, Cross-Bot Gaps; `research-platforms.md`, Gap Analysis.
- Users appear willing to switch when screening either rejects legitimate users or leaves reviewers blind. Evidence count: 3 sources. Strength: moderate. The strongest concrete evidence is the combination of false-positive complaints in verification products plus the repeated request for richer reviewer context in intake tooling. Source: `research-permissions.md`, Wick — Limitations & User Complaints; Double Counter — Limitations & User Complaints; `research-applications.md`, Gap Analysis.

**Differentiation opportunities:**
- The proposal differs from every reviewed product by making trust a first-class subsystem with persistent `Member`, `TrustProfile`, and `TrustSignal` objects instead of treating trust as a side effect of verification roles, application outcomes, or moderation flags.
- Products like Guildbase and Wick prove demand for risk signals, but the proposal improves on them by making those signals durable, inspectable, scope-specific, and auditable through recomputation history rather than opaque vendor-side heuristics.
- Competitors have specialized anti-raid and anti-abuse surfaces the proposal does not directly cover in this subsystem, especially Wick/Security Bot-style panic mode, anti-nuke recovery, and turnkey anti-alt screening heuristics.

**Overall evidence strength:** moderate

### 2. Intake and Adjudication

**Competitive landscape:**
- Gather, Appy, Application Bot, and ApplicationForms all provide Discord-connected application workflows with dashboard review, but their state models generally stop around submit/accept/deny/archive, with Gather as the main exception because it preserves a snapshot of the submitted form and exposes a slightly richer submission lifecycle. Source: `research-applications.md`, Gather; Appy; Application Bot; ApplicationForms.
- Guildbase and Guild Manager show that application workflows can live inside broader management suites, combining applications with review workflow, tickets, or guild operations, but even these products remain centered on intake/support rather than a wider adjudication model. Source: `research-platforms.md`, Guildbase; Guild Manager.
- Google Forms and Typeform outperform bot-native products on form-builder sophistication, including branching, rich question types, and file upload, but adjudication remains fragmented across external form tools, Sheets, Zapier, and Discord notifications. Source: `research-applications.md`, Google Forms + Discord Automation; Typeform + Discord Automation.
- Dyno, Carl-bot, and MEE6 offer intake primitives such as forms, suggestions, or welcome flows, but the general-bot scan explicitly frames them as lightweight intake rather than durable review workflow. Source: `research-general.md`, Dyno; Carl-bot; MEE6; Cross-Bot Gaps.

**User pain signals:**
- Reviewer collision prevention is essentially absent in the reviewed market. Gather, Appy, Application Bot, and ApplicationForms all rely on shared dashboards, role-based review permissions, or logging channels rather than a published claim-lock or single-owner queueing model. Evidence strength: strong. Source: `research-applications.md`, Gather — Review Features; Appy — Review Features; Application Bot — Review Features; ApplicationForms — Review Features; Gap Analysis.
- Discord-native review breaks down on platform and delivery constraints. Appy documents both the 6,000-character embed limit and DM-delivery failures; external form stacks push applicants and reviewers into fragmented off-Discord workflows. Evidence strength: strong. Source: `research-applications.md`, Appy — Limitations & User Complaints; Google Forms + Discord Automation — Limitations & User Complaints; Typeform + Discord Automation — Limitations & User Complaints.
- Operators report brittle review UX in weaker products: Application Bot has repeated dashboard-discovery and dashboard-access complaints, while Gather is deprecated and no longer viable for active operations despite its stronger model. Evidence strength: moderate. Source: `research-applications.md`, Application Bot — Limitations & User Complaints; Gather — Limitations & User Complaints.
- Waitlists, appeals, and required decision reasons remain rare. The applications gap analysis explicitly calls out the lack of waitlist handling, structured audit trails, and review ownership across the field. Evidence strength: strong. Source: `research-applications.md`, Gap Analysis.

**Value indicators:**
- Demand for better application tooling is very well validated. Evidence count: 8 sources. Strength: strong. Gather, Appy, Application Bot, ApplicationForms, Google Forms stacks, Typeform stacks, Guildbase, and Guild Manager all compete here, and multiple products sell premium tiers explicitly around application capacity, review roles, or dashboard workflow. Source: `research-applications.md`, Gather; Appy; Application Bot; ApplicationForms; Google Forms + Discord Automation; Typeform + Discord Automation; `research-platforms.md`, Guildbase; Guild Manager.
- Operators will pay for richer Discord-native review even when form builders are weaker. Evidence count: 5 sources. Strength: strong. Appy, Application Bot, Guildbase, Guild Manager, and Gather all monetize or differentiate around keeping reviewer workflow close to Discord and a management dashboard instead of forcing spreadsheets alone. Source: `research-applications.md`, Gather; Appy; Application Bot; `research-platforms.md`, Guildbase; Guild Manager.
- Immutable form contracts are differentiated but under-served. Evidence count: 1 source. Strength: weak. Gather is the only reviewed product that explicitly snapshots submitted forms; the rest of the market mostly omits versioning. Source: `research-applications.md`, Gather — Application Workflow; Gap Analysis.

**Differentiation opportunities:**
- The proposal differs by combining versioned `FormDefinition`, lifecycle-rich `Application` states, explicit reviewer ownership, interview/waitlist/withdrawal handling, and downstream effects tied into the rest of the system.
- Gather proves that immutable in-flight contracts matter, but the proposal improves on Gather by pairing form pinning with review ownership, decision rationale, trust context, and cross-subsystem auditability.
- Competitors still lead on public form-builder ergonomics in some areas. Google Forms and Typeform offer richer branching, broader question-type libraries, and mature public intake UX that the proposal does not explicitly define.

**Overall evidence strength:** strong

### 3. Case Management

**Competitive landscape:**
- Ticket Tool, Helper.gg, SCNX, Discord Tickets, and Modmail all cover core ticket creation, claims, transcripts, and staff coordination, but their dominant model is still action-centric (`open`, `claim`, `move`, `close`) rather than admin-defined state machines with typed transitions and category-specific rules. Source: `research-tickets.md`, Ticket Tool; Helper.gg; SCNX Support Bot; Discord Tickets; Modmail.
- Mava, Oapps for Zendesk, and DiscoDesk show a separate cluster of helpdesk-style products where Discord becomes just one inbox surface among many, with assignment, analytics, or routing centered in an external support suite rather than in Discord-native case objects. Source: `research-tickets.md`, Mava; Discord Connect for Zendesk (Oapps); DiscoDesk (Freshdesk).
- ticket.pm deepens transcript storage, export, and search, but it is transcript infrastructure rather than lifecycle management, reinforcing that most market depth is still on message retention rather than case semantics. Source: `research-tickets.md`, ticket.pm.
- Wick Bot and Central Bot show that moderation products can preserve infractions or moderation cases, but those cases remain bounded to the moderation/security lane rather than a general case-management substrate. Source: `research-platforms.md`, Wick Bot; Central Bot.

**User pain signals:**
- Assignment is brittle or paywalled. Ticket Tool hides meaningful claim workflow behind Premium, Modmail had to replace a broken claim plugin, and Discord Tickets uses a claim behavior that removes other staff from the ticket channel. Evidence strength: moderate. Source: `research-tickets.md`, Ticket Tool — Assignment; Limitations & User Complaints; Modmail — Assignment; Limitations & User Complaints; Discord Tickets — Assignment; Limitations & User Complaints.
- Audit remains transcript-first instead of action-stream first. Ticket Tool has a 1,000-message transcript cap, Helper.gg and SCNX emphasize transcript delivery, ticket.pm is transcript infrastructure, and the ticketing gap analysis explicitly calls out the absence of append-only case action streams. Evidence strength: strong. Source: `research-tickets.md`, Ticket Tool — Transcript/Audit; Helper.gg — Transcript/Audit; SCNX Support Bot — Transcript/Audit; ticket.pm — Transcript/Audit; Gap Analysis.
- Time/status rigor is shallow. The report's gap analysis says per-category configurable state machines are effectively missing, and it separately notes that mandatory resolution reasons are rare across Ticket Tool, Helper.gg, Discord Tickets, and SCNX. Evidence strength: strong. Source: `research-tickets.md`, Gap Analysis; Ticket Tool — Ticket Workflow; Helper.gg — Ticket Workflow; SCNX Support Bot — Limitations & User Complaints; Discord Tickets — Ticket Workflow.
- Cross-ticket pattern detection and moderation-case linkage are under-served. Mava, SCNX, Discord Tickets, and Modmail add analytics or logs, but the report explicitly says they do not expose first-class pattern detection across tickets, users, or moderators. Evidence strength: strong. Source: `research-tickets.md`, Gap Analysis.

**Value indicators:**
- Demand for ticket workflow depth is strong. Evidence count: 9 sources. Strength: strong. The category includes premium Discord bots, self-hosted bots, transcript tools, and full support platforms, and products monetize claiming, automation, transcripts, analytics, and external integrations. Source: `research-tickets.md`, Ticket Tool; Helper.gg; SCNX Support Bot; Discord Tickets; Modmail; ticket.pm; Mava; Discord Connect for Zendesk (Oapps); DiscoDesk (Freshdesk).
- Operators pay specifically for assignment, transcript delivery, and inbox analytics. Evidence count: 6 sources. Strength: strong. Ticket Tool, Helper.gg, SCNX, Mava, Oapps, and Modmail all monetize some combination of claiming, transcript handling, search, analytics, or agent workflow. Source: `research-tickets.md`, Ticket Tool — Pricing; Helper.gg — Pricing; SCNX Support Bot — Pricing; Mava — Pricing; Discord Connect for Zendesk (Oapps) — Pricing; Modmail — Pricing.
- Moderation-grade case fidelity is still under-supplied despite heavy ticket spend. Evidence count: 5 sources. Strength: strong. The repeated signal is that even mature ticket tools do not expose warn/ban ledgers, typed case histories, mandatory reasons, or unified actor history. Source: `research-tickets.md`, Ticket Tool — Moderation Integration; Helper.gg — Moderation Integration; Discord Tickets — Moderation Integration; Modmail — Moderation Integration; Gap Analysis.

**Differentiation opportunities:**
- The proposal differs by making `TicketCategory`, `Ticket`, `TicketMessage`, and `TicketTransition` explicit lifecycle objects with category-specific state machines, privacy levels, SLA rules, and typed transitions.
- Existing ticket products prove demand for claims, transcripts, and searchable history, but the proposal improves on them by turning assignment, escalation, and resolution into first-class audited actions correlated with the rest of the operational model.
- Competitors have adjacent features the proposal does not directly address, especially omnichannel shared inbox support and native helpdesk bridges outside Discord in Mava, Oapps, and DiscoDesk.

**Overall evidence strength:** strong

### 4. Sub-community Lifecycle (Chapters)

**Competitive landscape:**
- Guild Manager, GuildForger, Throney, TL Guild Manager, CoGM, and Guilds of WoW all show meaningful demand for multi-guild, team, division, or alliance operations, often with role sync, subgroup organization, and roster segmentation. Source: `research-activity.md`, Guild Manager; GuildForger; Throney; Guilds of WoW; `research-platforms.md`, TL Guild Manager; CoGM.
- Older website-first platforms such as Gamer Launch and Shivtr also support alliances, groups, rosters, events, and recruitment across multiple units, but they require communities to maintain a separate social surface outside Discord. Source: `research-platforms.md`, Gamer Launch; Shivtr.
- None of the general-purpose Discord bot cohort markets chapter lifecycle management at all, and the full-platform scan says even strong suites usually stop at teams/guilds/alliances rather than provisioning, probation, succession, and archival as explicit objects. Source: `research-general.md`, Cross-Bot Gaps; `research-platforms.md`, Gap Analysis.
- Guild Manager and Throney are the closest operational analogs: Guild Manager supports alliance capacity and organized groups inside a guild, while Throney supports up to four guilds in one alliance with shared visibility and attendance logic. Source: `research-activity.md`, Guild Manager; Throney.

**User pain signals:**
- Chapter lifecycle automation is still missing. The activity report explicitly says it could not find researched tools that describe provisioning channels/roles, maintaining chapter configuration, and archiving old chapters; the general-bot report likewise says none of the big bots market chapter lifecycle workflows. Evidence strength: strong. Source: `research-activity.md`, Gap Analysis; `research-general.md`, Cross-Bot Gaps.
- Communities still assemble subgroup operations from multiple surfaces. The platforms scan says the common workaround is `Discord + Google Sheets/Excel + one or more bots + optional guild website`, while GuildHall and TLGM market themselves by promising to replace spreadsheet sprawl and multi-bot stacks. Evidence strength: strong. Source: `research-platforms.md`, Community Management Workarounds; `research-activity.md`, Why this gap matters.
- Succession and delegated-local-authority continuity remain implicit rather than modeled. The platforms and activity reports surface multi-guild/team tooling, but not stateful transfer of pending work, local authority, and roster context when leaders change. Evidence strength: moderate. Source: `research-platforms.md`, Gap Analysis; `research-activity.md`, Guild Manager — Chapter/Clan Management; Throney — Chapter/Clan Management.

**Value indicators:**
- Demand for multi-unit organization is strong. Evidence count: 8 sources. Strength: strong. Guild Manager, GuildForger, Throney, Guilds of WoW, TL Guild Manager, CoGM, Gamer Launch, and Shivtr all sell alliance/team/multi-guild capacity. Source: `research-activity.md`, Guild Manager; GuildForger; Throney; Guilds of WoW; `research-platforms.md`, TL Guild Manager; CoGM; Gamer Launch; Shivtr.
- Users are willing to switch to reduce spreadsheet and multi-bot sprawl. Evidence count: 5 sources. Strength: strong. This is visible in the workaround section plus testimonials and product pitches for GuildHall, TLGM, Guild Manager, and broader guild-suite messaging. Source: `research-platforms.md`, Community Management Workarounds; `research-activity.md`, Bottom line for the Humility proposal.
- Lifecycle-grade chapter administration itself is under-monetized. Evidence count: 2 sources. Strength: moderate. Many products monetize teams or alliances, but the reports repeatedly note that provisioning, archival, and lifecycle governance are missing even in premium suites. Source: `research-activity.md`, Gap Analysis; `research-platforms.md`, Gap Analysis.

**Differentiation opportunities:**
- The proposal differs by making `Chapter`, `RosterEntry`, and chapter-scoped governance first-class lifecycle objects with provisioning templates, probation/archival states, succession-linked authority, and roster transitions.
- Existing alliance/team tools prove the need for multi-unit management, but the proposal improves on them by connecting chapter state to intake, permissions, compliance, and governance instead of treating groups as static containers.
- Competitors have adjacent features the proposal does not address directly, especially website/community-surface features like public guild pages, forums, and event-site UX in Gamer Launch, Shivtr, Guild Manager, and Guilds of WoW.

**Overall evidence strength:** moderate

### 5. Activity and Compliance

**Competitive landscape:**
- Apollo, Suivix, and Raid-Helper are strong on event attendance, scheduling, and participation tracking, but they remain event-centric rather than compliance-centric. Source: `research-activity.md`, Apollo; Suivix; Raid-Helper.
- Guild Manager, GuildForger, Guilds of WoW, Throney, TL Guild Manager, and CoGM go much further, combining attendance, roster data, analytics, and game-specific operations; Throney is the clearest example of explicit attendance thresholds, while Guild Manager is the clearest example of screenshot-based check-ins in a broader suite. Source: `research-activity.md`, Guild Manager; GuildForger; Throney; Guilds of WoW; `research-platforms.md`, TL Guild Manager; CoGM.
- General bots such as MEE6, Arcane, YAGPDB, and Carl-bot cover leveling, alerts, counters, and lightweight activity metrics, but the general-bot report explicitly says the market is still weak on evidence-backed compliance checks, threshold rules, and officer review workflows. Source: `research-general.md`, MEE6; Arcane; YAGPDB; Carl-bot; Cross-Bot Gaps.
- Generic OCR bots prove screenshot text extraction is feasible in Discord, but the activity report says they stop at transcription, while Throney is the only strong public example of screenshot parsing being used as structured guild data. Source: `research-activity.md`, Screenshot/OCR Approaches.

**User pain signals:**
- Spreadsheet and manual-process fatigue is a core recurring complaint. The activity report's gap analysis and supporting discussion links describe officers still editing attendance in spreadsheets, stitching together Discord plus manual proof handling, and spending time on repetitive threshold checks. Evidence strength: strong. Source: `research-activity.md`, Why this gap matters; Bottom line for the Humility proposal; `research-platforms.md`, Community Management Workarounds.
- A general-purpose compliance engine is still missing. Outside Throney's game-specific threshold examples, the reports repeatedly say reviewed products do not expose configurable rule evaluation, chapter-specific thresholds, or automatic consequence workflows. Evidence strength: strong. Source: `research-activity.md`, Throney — Compliance/Thresholds; Gap Analysis; `research-general.md`, Cross-Bot Gaps.
- Screenshot evidence is common but under-structured. Guild Manager supports screenshot check-ins without public OCR parsing detail, generic OCR bots only transcribe, and Throney's structured parsing is still game-specific. Evidence strength: strong. Source: `research-activity.md`, Guild Manager — Activity Tracking; Screenshot/OCR Approaches; Gap Analysis.
- Dispute-grade audit chains for compliance are rare. The activity report says it could not find tools that tie original evidence, extracted record, human review, final compliance decision, and later reversal into one history. Evidence strength: strong. Source: `research-activity.md`, Gap Analysis.

**Value indicators:**
- Demand for attendance, analytics, and participation tracking is strong. Evidence count: 9 sources. Strength: strong. Apollo, Suivix, Raid-Helper, Guild Manager, GuildForger, Throney, GuildBro, Guilds of WoW, and TL Guild Manager all compete or monetize around activity tracking. Source: `research-activity.md`, Apollo; Suivix; Raid-Helper; Guild Manager; GuildForger; Throney; GuildBro; Guilds of WoW; `research-platforms.md`, TL Guild Manager.
- Operators are willing to pay for threshold automation and richer officer reporting when a product makes it concrete. Evidence count: 5 sources. Strength: strong. Throney monetizes attendance thresholds and analytics, Guild Manager monetizes attendance history and analytics tiers, and broader suites sell dashboards, exports, and reward metrics. Source: `research-activity.md`, Throney — Compliance/Thresholds; Pricing; Guild Manager — Reporting; Pricing; `research-platforms.md`, TL Guild Manager — Reporting.
- The strongest willingness-to-pay signal is for integrated roster plus activity plus analytics, not for OCR alone. Evidence count: 6 sources. Strength: strong. Guild Manager, Throney, Guilds of WoW, GuildForger, TL Guild Manager, and CoGM all package activity depth together with roster and guild administration. Source: `research-activity.md`, Guild Manager; GuildForger; Throney; Guilds of WoW; `research-platforms.md`, TL Guild Manager; CoGM.

**Differentiation opportunities:**
- The proposal differs by treating compliance as a lifecycle with `ComplianceRule`, `EvidenceSubmission`, and `ComplianceEvaluation` objects, including evidence provenance, OCR confidence, scheduled evaluations, and consequence application.
- Throney and Guild Manager show that automation and screenshot-backed evidence matter, but the proposal improves on them by being cross-game, chapter-scoped, and tied into roster state, governance, and audit.
- Competitors have adjacent features the proposal does not cover directly, especially event scheduling depth, DKP/loot systems, raid composition, and richer event-ops UX in Raid-Helper, Throney, GuildBro, Guilds of WoW, and TL Guild Manager.

**Overall evidence strength:** strong

### 6. Permission Management

**Competitive landscape:**
- Wick, Security Bot, and Double Counter cover verification, dangerous-permission monitoring, anti-nuke protection, quarantine, and custom moderator authorities, but they still express authority through roles, whitelists, and product-specific command grants rather than through scope-bound permission objects. Source: `research-permissions.md`, Wick; Security Bot; Double Counter.
- Dyno, Carl-bot, YAGPDB, MEE6, and Arcane cover reaction roles, autoroles, granular command permissions, and logging, making them strong on role automation but still dependent on Discord hierarchy and overwrite mechanics. Source: `research-permissions.md`, Dyno; Carl-bot; YAGPDB; `research-general.md`, MEE6; Arcane.
- Xenon is the strongest reviewed tool for backup, clone, and restore of Discord server state, but the permissions report is explicit that snapshot/restore is not the same as declared-intent-versus-actual reconciliation. Source: `research-permissions.md`, Xenon; Gap Analysis.
- Guild Manager, TL Guild Manager, and CoGM show that broader suites can offer 40+ or 130+ granular permissions, but those permissions still operate as role/admin capability sets, not as auditable intent-plus-drift models. Source: `research-activity.md`, Guild Manager; `research-platforms.md`, TL Guild Manager; CoGM.

**User pain signals:**
- Hierarchy friction breaks real workflows. Dyno and Carl-bot community threads surface role-order and permission misconfiguration as common causes of autorole or reaction-role failures, and YAGPDB hard-limits role menus to 20 roles because of Discord reactions. Evidence strength: strong. Source: `research-permissions.md`, Dyno — Limitations & User Complaints; Carl-bot — Limitations & User Complaints; YAGPDB — Limitations & User Complaints.
- Verification-heavy products create false-positive and privacy backlash. Wick surfaces legitimate-user rejection complaints, while Double Counter draws privacy criticism for fingerprinting and shared-network/VPN detection. Evidence strength: moderate. Source: `research-permissions.md`, Wick — Limitations & User Complaints; Double Counter — Limitations & User Complaints.
- Governance visibility stops at logs or backups. The permissions gap analysis says drift detection, preview-confirm changes, scoped grants, and optimistic concurrency are absent across the reviewed field; Xenon can only restore what was previously backed up, and restore is not equivalent to live reconciliation. Evidence strength: strong. Source: `research-permissions.md`, Gap Analysis; Xenon — Limitations & User Complaints.

**Value indicators:**
- Demand for role automation, security, and restore depth is strong. Evidence count: 8 sources. Strength: strong. Wick, Security Bot, Double Counter, Dyno, Carl-bot, YAGPDB, Xenon, and Guild Manager all monetize meaningful permission/security surfaces. Source: `research-permissions.md`, Wick; Security Bot; Double Counter; Dyno; Carl-bot; YAGPDB; Xenon; `research-activity.md`, Guild Manager.
- Operators are already paying for reduced manual role handling and incident recovery. Evidence count: 6 sources. Strength: strong. Premium tiers cluster around stronger automod, more reaction-role capacity, better backups, sync, or advanced moderation controls. Source: `research-permissions.md`, Wick — Pricing; Security Bot — Pricing; Dyno — Pricing; Carl-bot — Pricing; YAGPDB — Pricing; Xenon — Pricing.
- Declared-state reconciliation appears under-served despite repeated gap analysis. Evidence count: 5 sources. Strength: strong. Multiple product categories address permissions after the fact through logging or recovery, but none expose an intent-vs-actual control plane. Source: `research-permissions.md`, Gap Analysis; `research-general.md`, Cross-Bot Gaps; `research-platforms.md`, Gap Analysis.

**Differentiation opportunities:**
- The proposal differs by modeling intended permission state explicitly and then surfacing `PermissionDrift` when Discord reality diverges, instead of treating permissions as a collection of one-off bot settings or logs.
- Existing tools prove demand for reaction-role UX, anti-nuke defense, and restore workflows, but the proposal improves on them by making permission decisions auditable, reasoned, and reconcilable over time.
- Competitors have features the proposal does not directly address in this subsystem, especially high-end anti-nuke recovery, consumer-facing self-role UX, and Xenon-style full-server cloning/restore.

**Overall evidence strength:** strong

### 7. Governance

**Competitive landscape:**
- Dyno, Carl-bot, Quark, and Wick all provide useful logs, dashboards, and moderation/audit visibility, but the permissions report is explicit that these are still operational histories, not policy versioning, preview-confirm flows, or end-to-end governance chains. Source: `research-permissions.md`, Dyno; Carl-bot; Quark Logger; Wick.
- Guild Manager, Guildbase, TL Guild Manager, and CoGM push further by combining audit pages, workflow history, reviewer permissions, or audit retention inside broader suites, but these histories remain local to a feature family rather than a shared causal chain across all operational domains. Source: `research-platforms.md`, Guild Manager; Guildbase; TL Guild Manager; CoGM.
- Xenon contributes restore and synchronization governance, and CommunityOne contributes analytics and recommendation layers, but neither closes the gap around policy authorship, decision integrity, or cross-workflow accountability. Source: `research-permissions.md`, Xenon; `research-platforms.md`, CommunityOne.
- The general-bot scan says every major bot offers some combination of logs, dashboards, and custom commands, but none of them markets versioned policy/config management, migration history, formal audit trails tied to human actors, or structured change control. Source: `research-general.md`, Cross-Bot Gaps.

**User pain signals:**
- Audit is fragmented and local. Tickets are transcript-first, permissions are event-log-first, and broader platforms expose local workflow history rather than a chain that follows one decision across application, roster, permission, and compliance consequences. Evidence strength: strong. Source: `research-tickets.md`, Gap Analysis; `research-permissions.md`, Gap Analysis; `research-platforms.md`, Gap Analysis.
- Direct-mutation dashboards remain the norm. The permissions report explicitly says it found no public evidence of policy versioning, diff previews, compare-and-swap edits, or last-known-version enforcement; most dashboards appear to apply settings directly. Evidence strength: strong. Source: `research-permissions.md`, Gap Analysis.
- Retention and export are uneven or gated. Quark, Dyno, MEE6, and YAGPDB gate retention or history depth behind paid tiers or limits, and Guild Manager still lists API/data export as "coming soon." Evidence strength: strong. Source: `research-permissions.md`, Quark Logger — Pricing; Dyno — Limitations & User Complaints; YAGPDB — Limitations & User Complaints; `research-general.md`, MEE6 — Pricing; `research-activity.md`, Guild Manager — Limitations & User Complaints.
- Vendor maturity is part of governance risk. Gather is deprecated, Guilded is shut down, SCNX docs are partly outdated, and some products show documentation lag or mixed rollout signals, which makes operational governance depend on unstable vendor surfaces. Evidence strength: strong. Source: `research-applications.md`, Gather — Limitations & User Complaints; `research-platforms.md`, Guilded — Status; CoGM — Limitations & User Complaints; `research-tickets.md`, SCNX Support Bot — Limitations & User Complaints.

**Value indicators:**
- Demand for auditability, dashboards, and governance visibility is strong. Evidence count: 9 sources. Strength: strong. Dyno, Carl-bot, Quark, Wick, Xenon, Guild Manager, Guildbase, TL Guild Manager, and CoGM all invest or monetize around logs, audit history, restore/sync, or workflow visibility. Source: `research-permissions.md`, Dyno; Carl-bot; Quark Logger; Wick; Xenon; `research-platforms.md`, Guild Manager; Guildbase; TL Guild Manager; CoGM.
- Operators pay for retention, history, and admin control, but not yet for a shared governance plane. Evidence count: 7 sources. Strength: strong. The monetized surfaces are longer log retention, richer dashboards, premium moderation controls, export depth, and restore/sync capacity rather than policy-version semantics. Source: `research-permissions.md`, Dyno; Quark Logger; Xenon; Wick; `research-platforms.md`, Guild Manager; Guildbase; TL Guild Manager.
- Switching pressure rises when governance is trapped inside one vendor lane. Evidence count: 6 sources. Strength: strong. This comes from the repeated workaround pattern, transcript-local products, and shutdown/deprecation signals in Gather and Guilded. Source: `research-platforms.md`, Community Management Workarounds; Guilded — Status; `research-applications.md`, Gather — Limitations & User Complaints; `research-tickets.md`, ticket.pm — Limitations & User Complaints.

**Differentiation opportunities:**
- The proposal differs by joining `PolicyVersion`, `AuditEntry`, scoped authority, causal correlation, and notification semantics into a single governance model instead of leaving governance as a thin logging layer.
- Existing platforms prove that officers value logs, workflow history, and dashboards, but the proposal improves on them by making decision authorship, governing policy version, prior state, new state, and downstream effects queryable in one append-only chain.
- Competitors have adjacent governance features the proposal does not directly cover, especially backup cloning/synchronization, community-growth analytics, and white-label/admin-branding surfaces.

**Overall evidence strength:** strong

## Cross-cutting Findings

- The market clusters around 2-4 subsystems at a time, not all 7. General bots skew toward moderation, roles, and lightweight automation; intake products skew toward forms and tickets; guild suites skew toward recruitment plus events; game-specific tools skew toward roster plus attendance. Source: `research-general.md`, Cross-Bot Gaps; `research-applications.md`, Bottom Line For Humility; `research-tickets.md`, Gap Analysis; `research-platforms.md`, Gap Analysis.
- Strong competitors are usually either Discord-bound or game-bound. The best unified products are still narrow: Wick is security-first, Guildbase is intake-first, and Guild Manager / TL Guild Manager / Guilds of WoW / Throney are strong because they narrow scope to guild ops or one game family. That supports the proposal's platform-boundary differentiation. Source: `research-platforms.md`, Closest analogs to the target direction; `research-activity.md`, Bottom line for the Humility proposal.
- Premium gating consistently concentrates around ownership, retention, analytics, multi-guild capacity, and recovery. Claiming, transcripts, log history, exports, alliance support, reaction-role scale, and backups are frequently paid features, which reinforces vendor lock-in and migration pain. Source: `research-tickets.md`, Ticket Tool — Pricing; Helper.gg — Pricing; `research-permissions.md`, Dyno — Pricing; Quark Logger — Pricing; Xenon — Pricing; `research-platforms.md`, Guild Manager — Pricing.
- Audit depth is usually local and transcript/event oriented rather than cross-workflow and causal. Tickets emphasize transcripts, security products emphasize logs, and guild suites emphasize local workflow pages; the market repeatedly fails to offer a single decision chain spanning intake, cases, chapters, permissions, and compliance. Source: `research-tickets.md`, Gap Analysis; `research-permissions.md`, Gap Analysis; `research-platforms.md`, Gap Analysis.
- Graceful-degradation and portability concerns are validated by real market instability. Gather is deprecated, Guilded is defunct, and several categories rely on external dashboards, helpdesk bridges, or export-light products, all of which strengthen the proposal's emphasis on community-owned data and reduced dependence on vendor-local state. Source: `research-applications.md`, Gather — Limitations & User Complaints; `research-platforms.md`, Guilded — Status; Gap Analysis.
- No moderate-confidence market surface clearly escaped the existing problem definition. The recurring market pains mapped back to existing axes, especially §1, §3, §8, §9, §12, §13, and §14 in `problem.md`.

## Evidence Gaps

- Identity and Trust has only partial direct market coverage. Most evidence comes from verification/security products and intake-side risk signals rather than from full trust-management competitors. Source: `research-permissions.md`, Wick; Security Bot; Double Counter; `research-platforms.md`, Guildbase; Guild Manager.
- Chapter succession, archival, and delegated local-governance transfer are under-documented in the market inputs. Multi-guild capacity is well covered; full chapter lifecycle failure modes are not. Source: `research-activity.md`, Gap Analysis; `research-platforms.md`, Gap Analysis.
- Governance evidence is strong on vendor docs and plan matrices, but weaker on normalized operator-complaint volume for some products. Several reports note that community complaint evidence was sparse or stale for specific tools. Source: `research-tickets.md`, Method note; Helper.gg — Limitations & User Complaints; `research-applications.md`, Gather — Limitations & User Complaints.
- Pricing transparency is incomplete for several products, especially where premium sales are routed through Discord, Patreon, or app marketplaces rather than a public price page. Source: `research-general.md`, YAGPDB — Pricing; `research-permissions.md`, Wick — Pricing; Carl-bot — Pricing; `research-activity.md`, Raid-Helper — Pricing; GuildForger — Pricing.
- The research set is strongest on gaming-community and Discord-first tools. It provides less coverage for non-gaming volunteer communities or enterprise-grade governance products that might share adjacent workflow concepts without sharing the Discord constraint.
