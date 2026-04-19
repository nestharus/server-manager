# Activity Tracking & Roster Management — Research Findings

Research date: April 16, 2026.

Method: Firecrawl search, map, extract, and scrape across vendor sites, documentation, GitHub, and public discussion threads surfaced by search. This pass focused on products that were publicly indexable and had enough feature detail to compare against the Humility proposal.

## Discord Bots

### Apollo
#### Activity Tracking
Apollo is primarily an event and attendance bot. Its public site emphasizes event creation, attendee and waitlist views, and attendance/history that can be reviewed in a browser. This is event-centric attendance, not broad member activity tracking.

#### Roster Management
Apollo exposes attendee and waitlist detail per event, but I did not find persistent roster segmentation, join/leave state management, or per-subgroup status workflows in the public docs.

#### Compliance/Thresholds
I did not find minimum attendance rules, automatic member compliance evaluation, or consequence workflows in the public pages reviewed.

#### Chapter/Clan Management
I did not find chapter or clan lifecycle management, channel provisioning, or officer hierarchy tooling beyond normal event administration.

#### Reporting
Apollo exposes event history. The free tier keeps event history for 2 months; premium makes history unlimited.

#### Pricing
$5.99/month or $49.99/year, with a 7-day refund policy.

#### Limitations & User Complaints
Apollo looks strong for scheduling and attendance, but weak for guild compliance operations. Public plan limits show free-tier friction: limited-capacity events, only 1 reminder per event, only 5 active recurring events, and only 2 months of event history. I did not find native roster-state or chapter-management features in the reviewed material.

Sources:
- https://apollo.fyi/
- https://apollo.fyi/premium
- https://docs.apollo.fyi/creating_events
- https://docs.apollo.fyi/commands

### Suivix
#### Activity Tracking
Suivix is narrowly focused on taking attendance in Discord voice calls. It can check the presence of selected roles and handle groups split across multiple voice channels.

#### Roster Management
I did not find persistent roster management, subgroup membership history, or status tracking.

#### Compliance/Thresholds
I did not find minimum activity thresholds, alerts for non-compliance, or automatic actions.

#### Chapter/Clan Management
I did not find chapter/clan structures, channel provisioning, or officer hierarchy support.

#### Reporting
Suivix generates a chart and/or Excel file for each attendance run and poll, which is useful for officer workflows that still pivot through spreadsheets.

#### Pricing
I did not find public pricing on the pages captured in this pass.

#### Limitations & User Complaints
Suivix appears intentionally lightweight: attendance plus polls plus exports. That makes it useful as a narrow attendance utility, but not as a roster/compliance platform. I did not find public evidence of roster states, threshold rules, or chapter administration.

Sources:
- https://suivix.xyz/
- https://discord.com/discovery/applications/929676077771677717

### Raid-Helper
#### Activity Tracking
Raid-Helper is an event-signup and raid-organization bot with attendance statistics. Event profiles can count toward attendance, and admins can query attendance with `/attendance`. It also supports automatic DKP payouts attached to event settings.

#### Roster Management
Its roster handling is event-scoped rather than guild-scoped. It supports allowed roles, banned roles, signup limits, benches, queues, alternate names, temporary roles, and temporary voice channels, but I did not find persistent guild roster-state management.

#### Compliance/Thresholds
It has useful event controls such as lower signup limits, allowed/banned roles, and automatic cancellation of under-subscribed events, but I did not find an ongoing minimum-participation engine for members over time.

#### Chapter/Clan Management
Raid-Helper can create Discord events, threads, temporary voice channels, and temporary roles per event. I did not find persistent clan/chapter provisioning or archival workflows.

#### Reporting
Attendance statistics are available through the attendance system, and overview embeds summarize current events. Reporting appears centered on events rather than holistic member lifecycle.

#### Pricing
Premium exists, but I did not find a publicly visible price in the accessible pages captured during this pass.

#### Limitations & User Complaints
Raid-Helper is a strong event bot, but it still looks like an event bot. Public docs show many premium-gated conveniences such as Discord event creation, vacuum cleanup, signup-response DMs, and temporary roles. I did not find public support for roster-state workflows, audit trails for disputes, or chapter lifecycle management.

Sources:
- https://raid-helper.xyz/
- https://raid-helper.xyz/documentation/commands
- https://raid-helper.xyz/documentation/advanced
- https://raid-helper.xyz/premium/

## Web-Based Guild Management Tools

### Guild Manager
#### Activity Tracking
Guild Manager is the broadest cross-game suite I found. It combines participation history with smart scheduling, RSVP management, analytics, and a check-in system that explicitly supports PIN, screenshot, manual, and Discord voice check-ins.

#### Roster Management
It supports multiple characters per member, hierarchical roles with 40+ permissions, applications with voting/review workflow, and organized groups inside the guild. Pricing also exposes alliance support across multiple guilds.

#### Compliance/Thresholds
I did not find a public description of configurable minimum-attendance rules or automatic compliance consequences. It clearly has metrics, participation tracking, custom point systems, and analytics, but not an explicit compliance engine in the reviewed pages.

#### Chapter/Clan Management
This is one of the closest matches to multi-chapter operations. It supports groups within the guild, alliance support across 2/4/8 guilds depending plan, and deep Discord integration with role sync and custom commands.

#### Reporting
Strong reporting footprint: participation rates, attendance patterns, event success metrics, transaction history, admin dashboard, and audit trail/history.

#### Pricing
Free for 1 guild up to 25 members. Core is $19.99/month, Elite is $29.99/month, Mythic is $49.99/month. Higher tiers increase member counts, guild counts, alliance capacity, storage, reward metrics, and audit-log retention.

#### Limitations & User Complaints
Guild Manager covers a lot, but several important surfaces are still not fully mature in public docs. Member management is labeled beta, recurring events are beta, loot council and item management are coming soon, and API/data export are also coming soon. It supports screenshot check-ins, but I did not find public evidence that screenshots are OCR-parsed into structured activity records. I also did not find explicit per-chapter threshold rules or automatic sanctions.

Sources:
- https://guildmanager.app/features
- https://guildmanager.app/pricing
- https://guildmanager.app/comparison
- https://wiki.guildmanager.app/docs/00-getting-started/key-concepts

### GuildForger
#### Activity Tracking
GuildForger positions itself as an all-in-one guild command center. Public pages describe raid attendance, event participation, contribution tracking, sign-up tracking, reminders, progression systems, and built-in analytics.

#### Roster Management
Roster tooling is strong on paper: rich member profiles, custom fields, raid history, roles, availability, Discord/spreadsheet imports, officer tiers, and team divisions.

#### Compliance/Thresholds
GuildForger has automatic points, level progression, rank-ups, achievements, and a restriction system that can evaluate user attributes, levels, achievements, and custom criteria. I did not find explicit minimum attendance thresholds or a compliance workflow focused on membership enforcement.

#### Chapter/Clan Management
It supports team divisions by game, role, or region, which maps fairly well to chapters or sub-communities. It also supports granular permissions and officer tiers.

#### Reporting
GuildForger advertises built-in analytics and engagement tracking, plus an analytics dashboard and export tools on the homepage.

#### Pricing
The homepage states there is a free Starter plan, plus Pro and Enterprise plans, and that Pro/Enterprise include features like custom domains and dedicated support. I did not find public numeric pricing in the pages captured during this pass.

#### Limitations & User Complaints
GuildForger is broad, but it reads more like a standalone guild portal or Discord alternative than a Discord-native compliance bot. I did not find public OCR or screenshot-proof workflows, and I did not find explicit chapter provisioning/archival flows. Numeric pricing also was not discoverable from the public pages captured here.

Sources:
- https://guildforger.online/
- https://guildforger.online/features

## Game-Specific Tools

### Throney
#### Activity Tracking
Throney is the strongest direct analogue for the proposed activity/compliance system, but it is game-specific to Throne and Liberty. It supports automatic attendance from Discord voice channels via `/attendance`, exportable records, automatic DKP awards, gear progression tracking, and AI gear recognition from screenshot uploads.

#### Roster Management
It supports multi-guild alliance management from one Discord server, linked member profiles, web-dashboard editing, war-party composition, and cross-guild data sharing.

#### Compliance/Thresholds
Throney explicitly supports minimum attendance thresholds in the dashboard. Its own examples include 80% siege-war attendance for core members and 50% attendance for active members. This is the clearest public threshold/compliance feature I found in the market.

#### Chapter/Clan Management
Throney manages up to 4 guilds in one alliance from a single Discord server, with shared or separate point pools, cross-guild visibility, and alliance coordination. This is a meaningful chapter analog for games where one community runs multiple guilds.

#### Reporting
It has a guild analytics dashboard with attendance rates, class distribution, average combat power, gear progression, and roster gaps. Members can view their own attendance via `/stats`, and officers can filter attendance by date range, event type, and member.

#### Pricing
Free tier: 1 guild up to 20 players, with automated gear tracking and basic attendance tracking. Pro: $7.50/month for up to 4 guilds, full dashboard integration, dynamic events/signups, war-party management, DKP/loot distribution, and advanced analytics.

#### Limitations & User Complaints
Throney is impressive, but specialized. It is explicitly for Throne and Liberty, not a general gaming-community layer. Its attendance model is a voice-channel snapshot, so multi-channel events require repeated `/attendance` runs or manual dashboard correction. Free tier is also small. This is the closest product to the proposal's compliance direction, but it still does not expose a generalized screenshot-proof-to-compliance pipeline for arbitrary activity evidence.

Sources:
- https://throney.gg/
- https://docs.throney.gg/introduction
- https://docs.throney.gg/frequently-asked-questions
- https://throney.gg/guides/attendance-tracking

### GuildBro
#### Activity Tracking
GuildBro is a Throne and Liberty guild-management web app with Discord integration. Its public site describes event/activity management, automatic attendance tracking for raids and events, and DKP-linked loot distribution.

#### Roster Management
It includes member management, roster tracking, role assignment, activity monitoring, party management, and automatic role assignment for Discord and TeamSpeak when someone is accepted into the guild.

#### Compliance/Thresholds
I did not find public threshold rules, compliance alerts, or automatic consequences in the pages reviewed.

#### Chapter/Clan Management
GuildBro supports smaller-group organization for boss fights and special missions, but I did not find a chapter lifecycle model comparable to provisioning or archival.

#### Reporting
I did not find a clearly documented analytics or reporting surface beyond attendance and activity management.

#### Pricing
7-day free trial, $14.99/month, or $39.99/quarter.

#### Limitations & User Complaints
GuildBro is clearly useful for T&L officer operations, but it is game-specific and lighter on publicly described compliance/reporting features than Throney. I did not find explicit threshold rules, audit trails, or dispute workflows.

Sources:
- https://guildbro.io/

### Guilds of WoW
#### Activity Tracking
Guilds of WoW combines Battle.net, Warcraft Logs, Raider.IO, Discord, and an in-game addon. It supports Discord-assisted attendance tracking, native Discord events support, attendance history, and recurring-event tooling.

#### Roster Management
It has strong guild and team tooling: roster management, inclusion of non-guild members, automatic guild-data refresh from official WoW APIs, recruitment workflows, permissions, bans, and team configuration.

#### Compliance/Thresholds
I did not find a general-purpose minimum participation rules engine. It does expose audit preferences for team audits, event attendance history, auto-lock attendance, role-engine rules, recruitment restrictions, and bans, which suggests strong operational control without a broad compliance layer.

#### Chapter/Clan Management
Teams are the nearest analog to chapters. Paid tiers increase the number of teams, team size, Discord channels/webhooks, and role-engine rules. It is still WoW-specific rather than a general Discord chapter-management layer.

#### Reporting
Very strong reporting footprint: guild, player, and audit reports; weekly analysis; visual charts; spreadsheet integration; combat-log refreshes; and API access with higher limits on paid tiers.

#### Pricing
Free core service, with Patreon-backed premium tiers from $1/month to $25/month. Paid tiers expand team counts, event recurrence windows, Discord channels/webhooks, rule counts, spreadsheet counts, and API limits.

#### Limitations & User Complaints
Guilds of WoW is a mature operating layer for WoW guilds, but it remains deeply game-specific and still embraces spreadsheets as a first-class companion surface rather than replacing them entirely. I did not find public evidence of cross-game chapter provisioning, OCR-based activity verification, or a generalized member-compliance rules engine.

Sources:
- https://guildsofwow.com/
- https://guildsofwow.com/faq
- https://guildsofwow.com/install-applications

### Guild Roster Manager (GRM)
#### Activity Tracking
GRM is a World of Warcraft addon, not a Discord bot. It tracks roster-change activity such as join/rejoin, kick, promotions/demotions, name changes, inactivity notifications, and level-ups.

#### Roster Management
Roster management is its core strength: alt/main relationships, custom roster grouping, mouseover player details, join dates, anniversaries, and synchronization across guild members using the addon.

#### Compliance/Thresholds
It has rank-based controls over what can sync, but I did not find a real participation-threshold or compliance workflow.

#### Chapter/Clan Management
Its scope is roster synchronization inside a WoW guild. I did not find chapter/sub-community provisioning or Discord structure management.

#### Reporting
Reporting is mostly operational logging and notifications about guild changes rather than officer dashboards or compliance summaries.

#### Pricing
No paid pricing was surfaced in the captured source; this appears to be a free addon distribution.

#### Limitations & User Complaints
GRM is helpful for roster history, but it is not a Discord-native management layer and it does not solve screenshot evidence, officer workflows, or chapter lifecycle management. It looks complementary rather than sufficient.

Sources:
- https://www.curseforge.com/wow/addons/guild-roster-manager

## Screenshot/OCR Approaches

### 1. Manual screenshot evidence is common, but usually not structured
Guild Manager explicitly supports screenshot check-ins alongside PIN, manual, and Discord voice check-ins. That is useful, but the public pages do not describe OCR extraction from screenshots into structured activity records. This suggests many tools still treat screenshots as evidence or a check-in mode, not as an ingest pipeline.

Sources:
- https://guildmanager.app/features

### 2. Generic Discord OCR bots exist, but they stop at text extraction
The generic pattern is straightforward: user posts an image, bot reads the attachment URL, runs OCR, then replies with recognized text. The Medium tutorial uses `tesseract.js`; the open-source OCR-Discord-Bot is an implementation of the same idea; the UI.Vision forum post describes a Discord bot backed by OCR.space's API. These tools prove OCR in Discord is feasible, but they are not guild-compliance systems.

Notable limitations from these sources:
- OCR accuracy is explicitly not guaranteed.
- The example GitHub bot has to split long OCR results because Discord messages cap at 2,000 characters.
- None of these sources describe domain-specific parsing of gaming screenshots into structured attendance/compliance events.

Sources:
- https://medium.com/@arushnath28/creating-a-text-recognition-discord-bot-ocr-using-discord-js-ae45668a64b7
- https://github.com/rifqifazzam/OCR-Discord-Bot
- https://forum.ui.vision/t/ocrbot-a-discord-bot-that-does-ocr/6980

### 3. Game-specific screenshot parsing is emerging
Throney goes beyond generic OCR by using screenshot uploads to extract gear and combat-power information from Throne and Liberty character screens. This is the closest public example I found of screenshot ingestion being used as structured guild data rather than plain text transcription.

Important limitation: this is still a game-specific parsing flow tied to character stats, not a general-purpose "activity proof screenshot -> compliance record" pipeline.

Sources:
- https://throney.gg/
- https://throney.gg/guides/attendance-tracking

## Gap Analysis

### What the market does reasonably well
- Event attendance inside Discord is well served. Apollo, Suivix, and Raid-Helper all reduce friction around signups and attendance collection.
- Game-specific guild suites can go much further. Throney and Guilds of WoW show that once a tool is game-aware, it can tie together attendance, loot, reports, and officer workflows.
- Broad guild portals exist. Guild Manager and GuildForger both show the appetite for replacing "Discord + spreadsheets + several bots" with a more integrated operating layer.

### What no tool does well enough yet
- **Per-chapter configurable activity thresholds**
  Only Throney clearly advertises minimum attendance thresholds, and it does so in a game-specific alliance context. I did not find a cross-game Discord guild tool with first-class per-chapter threshold policies, chapter-specific rule definitions, and officer workflows around those rules.

- **Screenshot -> OCR -> automatic activity recording**
  The market splits here. Generic OCR bots can read screenshots, but they are just transcription utilities. Guild-management suites support screenshot check-ins or game-specific image recognition, but I did not find a general product that turns arbitrary activity screenshots into validated activity records automatically.

- **Compliance evaluation with configurable rules**
  I found attendance stats, points, restrictions, and some thresholding, but not a robust configurable compliance engine that evaluates evidence against chapter-specific policies and then drives review states or actions.

- **Integrated roster + activity + compliance in one system**
  The closest products are Guild Manager and Throney. Guild Manager is broader but weaker on explicit compliance automation. Throney is stronger on attendance thresholds and automation, but narrow to Throne and Liberty. I did not find a clean cross-game system that unifies roster states, activity evidence, compliance decisions, and reporting.

- **Chapter lifecycle management: provisioning and archival**
  I did not find a researched tool that publicly describes Discord chapter lifecycle automation at the level of provisioning channels/roles, maintaining chapter configuration, and archiving old chapters. Tools talk about groups, teams, guilds, and alliances, but not full lifecycle orchestration.

- **Audit trail for activity disputes**
  Guild Manager has an audit trail. Guilds of WoW has audit reports. But I did not find a dispute-grade chain that ties original evidence, extracted record, human review, final compliance decision, and later appeal/reversal into one coherent history. That is still a gap.

### Why this gap matters
- Public search snippets from gaming-community threads keep pointing to the same operational pain:
- Officers stitching together Discord, Google Sheets, and manual process.
- Attendance still being edited in spreadsheets because the bot layer is too shallow.
- Loot and participation decisions still depending on screenshots, uploads, or ad hoc rules.

Representative discussion URLs surfaced in search:
- https://www.reddit.com/r/WhereWindsMeet/comments/1qffieg/i_built_a_free_guild_management_tool_for_wwm/
- https://www.reddit.com/r/wowaddons/comments/1r4zku1/guildkit_guild_management_looking_for_beta_guilds/
- https://www.reddit.com/r/CompetitiveWoW/comments/6x6t3z/tracking_raid_attendance/
- https://www.reddit.com/r/classicwow/comments/bxwf51/guild_managers_what_tools_are_you_using_to_manage/
- https://www.reddit.com/r/throneandliberty/comments/1djq555/loot_distribution_for_throne_and_liberty/

### Bottom line for the Humility proposal
- The proposal is differentiated if it treats chapters as first-class objects rather than just roles or teams.
- The clearest white space is: evidence ingestion, compliance evaluation, and chapter lifecycle in one system.
- The strongest competitor pattern to learn from is Throney's automation and thresholding.
- The strongest platform pattern to learn from is Guild Manager's all-in-one surface plus audit trail.
- The market still leaves a real opening for a Discord-native system that replaces spreadsheet compliance work instead of merely exporting to spreadsheets faster.
