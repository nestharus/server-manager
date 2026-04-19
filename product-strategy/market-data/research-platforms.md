# Full Guild Management Platforms — Research Findings

## Multi-Function Discord Bots

### Wick Bot
#### Subsystem Coverage
| Subsystem | Coverage | Depth |
|---|---|---|
| Identity/Trust | Yes | Captcha verification, join-gate screening, suspicious-account filtering. |
| Intake | Partial | Intake is limited to verification and raid defense, not applications. |
| Cases | Yes | Saves moderation actions as editable/freezable/restorable cases. |
| Chapters | No | Single-server security tool, not sub-community management. |
| Activity/Compliance | Partial | Staff activity monitoring, join-raid detection, detailed logs. |
| Permissions | Partial | Lockdowns, quarantine, and dangerous-permission monitoring. |
| Governance | Partial | Strong audit and anti-nuke controls, but no broader policy/workflow model. |

#### Integration Model
Discord bot plus OAuth dashboard.

#### Unified vs Siloed
Unified inside the moderation/security domain; not a broader guild ops system.

#### Audit/Governance
One of the stronger audit trails in the bot category for moderation actions, but the model stops at security operations.

#### Target Audience
Large or security-sensitive Discord communities. Official site claims `922K` servers.

#### Pricing
Premium available. Official pricing search result exposed a starting point of `$14.99 every 3 months`.

#### Status
Active. Homepage links a v5 changelog release and publishes large operating metrics.

#### Limitations & User Complaints
Excellent for trust/security, weak for recruitment, chapters, and cross-feature operational governance. It is a security suite, not a full guild operating system.

Sources:
- https://wickbot.com/
- https://wickbot.com/premium
- https://wicks.bot/en/pricing
- https://docs.wick.bot/changelog/v5.x/5.0.0/

### Appy
#### Subsystem Coverage
| Subsystem | Coverage | Depth |
|---|---|---|
| Identity/Trust | Partial | Can gate outcomes through accept/deny/restricted roles, but identity is mostly Discord-native. |
| Intake | Yes | Strong application forms, questionnaires, panels, and tickets. |
| Cases | Partial | Application history/insights and ticket state exist, but not full disciplinary case management. |
| Chapters | No | No meaningful sub-community or multi-unit operations model. |
| Activity/Compliance | No | Not built for attendance, analytics, or compliance workflows. |
| Permissions | Partial | Manager roles and role-routing exist around applications/tickets. |
| Governance | Partial | Some dashboard logging/history, but no policy or end-to-end audit chain. |

#### Integration Model
Discord bot plus web dashboard and docs.

#### Unified vs Siloed
Unified around intake/support; narrow beyond that.

#### Audit/Governance
Operational history is centered on applications and tickets rather than org-wide governance.

#### Target Audience
Communities processing a high volume of applications, forms, and support tickets. Official site claims `776,600` servers and `1,445,581` total applications.

#### Pricing
Free tier plus `Premium x1 £4.99/month`, `Premium x3 £8.99/month`, and `Custom Bot £9.99/month`.

#### Status
Active. Homepage copyright runs through `2026`; docs remain live. The premium docs page says "Last updated 2 years ago", which suggests some documentation lag.

#### Limitations & User Complaints
Very strong on intake, weak almost everywhere else. Good replacement for Google Forms inside Discord, but not a shared operational model for cases, chapters, activity, or governance.

Sources:
- https://appy.bot/
- https://appy.bot/premium?ref=website-footer
- https://docs.appy.bot/resources/premium
- https://www.reddit.com/r/discordbots/comments/1pr8dmf/helppp_with_verification_system/

### CommunityOne
#### Subsystem Coverage
| Subsystem | Coverage | Depth |
|---|---|---|
| Identity/Trust | No | No identity graph or trust workflow is visible in product positioning. |
| Intake | No | Not positioned around applications or adjudication. |
| Cases | No | No case-management model. |
| Chapters | No | No chapter or sub-community authority model. |
| Activity/Compliance | Yes | Strong analytics, engagement quests, sentiment, and moderator performance tracking. |
| Permissions | Partial | Role analytics and moderator performance exist, but not deep permission governance. |
| Governance | Partial | AI recommendations and analytics can inform governance, but there is no shared audit chain. |

#### Integration Model
Discord bot plus analytics and management dashboards.

#### Unified vs Siloed
Unified growth/engagement stack; not a guild ops stack.

#### Audit/Governance
Analytics-heavy rather than audit-heavy.

#### Target Audience
Community managers, founders, and growth teams. Official site claims `11,488` servers and `17,756,087` users.

#### Pricing
Free tier. `Spark AI $14.99/month`, `Hype Engine $14.99/month`, analytics tiers from `Core $18.99/month` to `Ultra $150/month`, plus `Enterprise $199/month`.

#### Status
Active. Official changelog search result shows updates dated `March 17, 2026`.

#### Limitations & User Complaints
This is a community-growth product, not an adjudication/governance platform. It improves support and engagement but does not unify recruitment, cases, permissions, and chapter operations.

Sources:
- https://communityone.io/
- https://communityone.io/pricing/
- https://communityone.io/analytics/
- https://communityone.io/changelog/

### Central Bot
#### Subsystem Coverage
| Subsystem | Coverage | Depth |
|---|---|---|
| Identity/Trust | Partial | Welcome flows and autoroles exist, but identity trust is shallow. |
| Intake | Partial | Suggestions and planned sessions/events exist, but not serious intake/adjudication. |
| Cases | Yes | Infraction tracking is a first-class moderation feature. |
| Chapters | No | No real multi-unit or chapter model. |
| Activity/Compliance | Partial | Session planning, LOA tracking, and some staff-management processes. |
| Permissions | Yes | Staff ranks and server-management controls are core. |
| Governance | Partial | Staff feedback, LOA tracking, and moderation controls help local governance, but not with a shared audit chain. |

#### Integration Model
Discord bot plus dashboard.

#### Unified vs Siloed
Reasonably unified for roleplay-server staff ops; still narrow outside that use case.

#### Audit/Governance
Good for infractions and staff process, weak for formal governance across multiple operational domains.

#### Target Audience
Roleplay communities. Official site claims `30,000+` active servers.

#### Pricing
Premium tiers are sold as `500`, `800`, and `1000` Robux for 1, 2, or 3 guilds.

#### Status
Active. Status page is live; homepage publishes uptime. Premium page itself says `Last updated: 31 July 2024`.

#### Limitations & User Complaints
Very roleplay-specific. It bundles moderation, planning, and economy, but still does not produce a shared operational model across recruitment, cases, chapters, and governance.

Sources:
- https://centralbot.xyz/
- https://centralbot.xyz/premium
- https://centralbot.xyz/status
- https://top.gg/bot/1173444104684847116

## Web-Based Platforms

### Guild Manager
#### Subsystem Coverage
| Subsystem | Coverage | Depth |
|---|---|---|
| Identity/Trust | Yes | Character profiles, member identities, and bidirectional Discord role sync. |
| Intake | Yes | Customizable applications with voting and review workflow. |
| Cases | Partial | Strong audit history, but not a dedicated sanction/case object model. |
| Chapters | Yes | Alliance support, multiple guilds, and multi-game support. |
| Activity/Compliance | Yes | Scheduling, RSVP, check-ins, attendance history, analytics, reward metrics. |
| Permissions | Yes | Hierarchical roles with `40+` granular permissions. |
| Governance | Yes | Audit trail, retention tiers, exports planned, and admin dashboard. |

#### Integration Model
Web platform with deep Discord integration, role sync, notifications, and guild-specific commands.

#### Unified vs Siloed
Closest thing in this set to a shared model across roster, applications, activities, metrics, and audit.

#### Audit/Governance
Stronger than most guild tools because audit is not just a moderation afterthought; it is part of the product plan and pricing model.

#### Target Audience
MMO guild leaders and officers across multiple games. Official site claims trust from `4,065+` gaming communities.

#### Pricing
`Free $0`, `Core $19.99/month`, `Elite $29.99/month`, `Mythic $49.99/month`.

#### Status
Active. Official feature page says `97% complete & production-ready` and "actively maintained and constantly improving."

#### Limitations & User Complaints
Very strong on guild operations, but still mostly guild-centric rather than platform-boundary-agnostic. Cases are mostly audit history, not an explicit adjudication object shared across all subsystems.

Sources:
- https://guildmanager.app/features
- https://guildmanager.app/pricing
- https://guildmanager.app/comparison
- https://guildmanager.app/

### Guildbase
#### Subsystem Coverage
| Subsystem | Coverage | Depth |
|---|---|---|
| Identity/Trust | Partial | Discord linking, role sync, and AI risk flags on applications. |
| Intake | Yes | One of the strongest intake stacks: application builder, workflows, tickets, transcripts. |
| Cases | Yes | Review history, ticket transcripts, ratings, and risk analysis. |
| Chapters | Partial | Can span multiple guilds and linked Discord servers, but mostly as intake containers. |
| Activity/Compliance | Partial | Operational stats exist, but mostly for applications/tickets rather than full guild compliance. |
| Permissions | Yes | Team management with role-based access and granular reviewer capabilities. |
| Governance | Partial | Workflow stages and transcripts help governance, but only inside intake/support lanes. |

#### Integration Model
Web platform with Discord bot integration, notifications, roles, webhooks, API, and FiveRoster sync.

#### Unified vs Siloed
Unified around applications and support; not a full community operating system.

#### Audit/Governance
Ticket transcripts and workflow history are useful, but governance is still scoped to intake/support rather than cross-system authority.

#### Target Audience
Online communities that need serious application workflow management, especially Discord-first communities and RP/FiveM-style admin teams.

#### Pricing
`Free £0`, `Pro £9.99/month`, `Ultimate £79.99/month`.

#### Status
Active. Pricing/features pages are live and the official blog includes 2026 comparison content.

#### Limitations & User Complaints
Deeper than typical Discord application bots, but still mostly an intake/helpdesk platform. It does not unify member lifecycle, chapters, compliance, and governance into one object model.

Sources:
- https://guildbase.gg/features
- https://guildbase.gg/pricing
- https://guildbase.gg/blogs
- https://guildbase.gg/feature-comparison

### Gamer Launch
#### Subsystem Coverage
| Subsystem | Coverage | Depth |
|---|---|---|
| Identity/Trust | Partial | User profiles, roster imports, character data. |
| Intake | Yes | Advanced applications and recruiting flows. |
| Cases | No | No meaningful case-management model. |
| Chapters | Partial | Multi-game, teams, tournaments, voice hosting. |
| Activity/Compliance | Yes | Calendars, newsletters, DKP, raid tracking, attendance, progression. |
| Permissions | Yes | Definable permissions and admin controls. |
| Governance | Partial | Admin notes and controls exist, but not a modern operational audit chain. |

#### Integration Model
Discord-independent guild website platform with game API imports and optional voice server products.

#### Unified vs Siloed
Historically broad: forums, recruiting, DKP, calendars, rosters, and widgets sit on one website. It is integrated, but website-first.

#### Audit/Governance
Admin controls exist, but governance is still mostly "site admin" rather than a formal operational model.

#### Target Audience
Traditional MMORPG guilds, clan sites, and esports teams.

#### Pricing
`Free`, `Essential $7.49/month`, `Premium $15.99/month`, `Ultimate $23.99/month`.

#### Status
Active. Pricing and feature pages are live in 2026. Product copy still references an admin dashboard released in `May 2012`, which signals an older architecture generation.

#### Limitations & User Complaints
The core weakness is structural: this is a separate web property that asks communities to maintain another venue outside Discord. That problem is part of why these platforms lost mindshare once Discord became the day-to-day command surface.

Sources:
- https://www.gamerlaunch.com/product/feature-list/
- https://www.gamerlaunch.com/order/d/comparison/
- https://www.gamerlaunch.com/
- https://www.reddit.com/r/wow/comments/wtl22/do_you_like_guild_websites_what_features_would/

### Shivtr
#### Subsystem Coverage
| Subsystem | Coverage | Depth |
|---|---|---|
| Identity/Trust | Partial | Member rosters, character profiles, and game-linked data. |
| Intake | Yes | Customizable application forms for recruitment. |
| Cases | Partial | Site audit log exists, but not moderation/adjudication casework. |
| Chapters | Yes | Alliances, groups, and multi-game support. |
| Activity/Compliance | Yes | Events calendar, attendance, DKP, progressions, activity feeds. |
| Permissions | Yes | Advanced permission system across site features. |
| Governance | Partial | Site audit logs and polls help, but there is no broader operational state model. |

#### Integration Model
Hosted guild website with API access, Twitter sharing, and game integrations. Not Discord-native.

#### Unified vs Siloed
Integrated for an older guild-site model: forums, chat, events, DKP, rosters, and alliances share one site.

#### Audit/Governance
Notable for an older platform because it includes an audit log and recoverability for site actions.

#### Target Audience
Guilds, clans, and gaming communities that still want a dedicated website.

#### Pricing
Free beginner plan plus paid tiers (`Epic`, `Mythic`, `Legendary`). The rendered plan page exposed storage/log windows clearly, but not every live monthly price during this pass.

#### Status
Active. Official site shows `Copyright © 2026` and the public site directory still has `52` pages of sites.

#### Limitations & User Complaints
Same strategic weakness as Gamer Launch: it is another surface to keep alive outside Discord. The product is richer than a forum, but still website-first and older in interaction model.

Sources:
- https://shivtr.com/features
- https://shivtr.com/plans
- https://shivtr.com/sites
- https://www.reddit.com/r/wow/comments/wtl22/do_you_like_guild_websites_what_features_would/

### Guilded
#### Subsystem Coverage
| Subsystem | Coverage | Depth |
|---|---|---|
| Identity/Trust | Partial | Guilded historically had its own member/role model, but not a trust workflow comparable to modern guild ops tools. |
| Intake | No | Not built around application adjudication. |
| Cases | No | No meaningful case layer. |
| Chapters | Partial | Historically supported richer server organization than Discord, including built-in calendars/forums. |
| Activity/Compliance | Partial | Event calendars and native organizational tools existed. |
| Permissions | Yes | As a full chat platform, it had its own role/permission surface. |
| Governance | Partial | Better than plain chat, but still not a shared governance/audit chain across guild workflows. |

#### Integration Model
Discord-independent platform and former competitor, not a Discord-connected management layer.

#### Unified vs Siloed
Historically more unified than a bot stack because chat, forums, and calendars lived in one platform.

#### Audit/Governance
Not the product's main differentiator.

#### Target Audience
Gaming communities wanting a full Discord alternative.

#### Pricing
Historically free; the current official landing page is only a shutdown notice.

#### Status
Defunct. The official site now states "Guilded is no longer available" and redirects users toward Roblox Communities.

#### Limitations & User Complaints
The biggest limitation is existential platform risk: communities cannot build governance on a surface that disappears. Reddit search results also surfaced user complaints about bugs, lack of traction, and the shutdown itself.

Sources:
- https://www.guilded.gg/
- https://www.reddit.com/r/guilded/comments/1nubppe/guilded_is_shutting_down/
- https://www.reddit.com/r/guilded/comments/11hg6zx/guilded_really_isnt_gaining_heavy_traction_heres/
- https://www.pcmag.com/comparisons/discord-vs-guilded-which-chat-app-builds-better-gamer-communities

## Game-Specific Tools

### GuildHall
#### Subsystem Coverage
| Subsystem | Coverage | Depth |
|---|---|---|
| Identity/Trust | Yes | Battle.net sync plus addon-backed attendance, roster, loot, and bank data. |
| Intake | Yes | Public guild profile and custom applications that open private Discord threads. |
| Cases | Partial | Strong history for recruitment, loot, attendance, and guild bank, but not broader casework. |
| Chapters | Partial | Supports multiple teams, but not a broad chapter federation. |
| Activity/Compliance | Yes | Events, signups, raid comps, attendance reconciliation, AI raid reports. |
| Permissions | Yes | Owner/Officer/Moderator/Raider/Member model with granular edit rights. |
| Governance | Partial | Strong operational history, but mostly raid-night governance rather than org governance. |

#### Integration Model
Web app plus in-game addon, Battle.net sync, Discord bot, and WarcraftLogs integration.

#### Unified vs Siloed
Very unified for raid operations; one of the best examples of "single source of truth" in a game-specific tool.

#### Audit/Governance
Good operational history for attendance, loot, and bank events, but the scope is raid ops rather than a full community constitution.

#### Target Audience
Serious World of Warcraft guilds. Official site currently shows `9 / 100 guilds` in early access.

#### Pricing
Free during beta.

#### Status
Active early beta.

#### Limitations & User Complaints
Narrow by design: excellent for raid ops, weaker for broader community/governance problems outside WoW.

Sources:
- https://guildhall.run/
- https://addons.wago.io/addons/guildhall-addon
- https://www.reddit.com/r/wowaddons/comments/1sdwdgf/guildhall_a_lightweight_guild_management_addon/

### Guilds of WoW
#### Subsystem Coverage
| Subsystem | Coverage | Depth |
|---|---|---|
| Identity/Trust | Yes | Deep Battle.net and WoW API integration, addon, and character tracking. |
| Intake | Yes | Recruitment listings, custom applications, officer review/voting, applicant chat. |
| Cases | Partial | Bans, notes, and applicant threads exist, but not a universal case object. |
| Chapters | Yes | Teams, guild pages, and multiple Discord channel/webhook connections. |
| Activity/Compliance | Yes | RSVP sync, audits, guild reports, spreadsheets, WCL integrations, reminders. |
| Permissions | Yes | Discord role engine, nickname manager, team/guild controls. |
| Governance | Partial | Strong reports/audits, still bounded to WoW and event/recruitment operations. |

#### Integration Model
Web platform plus Discord app/bot, in-game addon, spreadsheets, and APIs.

#### Unified vs Siloed
Integrated far better than most WoW guild tools because recruitment, events, Discord, addon, and reports all connect.

#### Audit/Governance
Audit/reporting is unusually mature, but still not a generalized governance model across all guild objects.

#### Target Audience
World of Warcraft guilds. Official site claims `12,000` guilds and `150,000` accounts.

#### Pricing
Patreon-style tiers from `$1/month` to `$25/month`.

#### Status
Active. Homepage includes 2025 season patch notes and an ongoing changelog stream.

#### Limitations & User Complaints
Deeply tied to WoW and still comfortable exporting to spreadsheets, which is useful but also signals incomplete replacement of officer tooling.

Sources:
- https://guildsofwow.com/
- https://guildsofwow.com/features
- https://guildsofwow.com/install-applications
- https://discord.com/invite/guildsofwow

### TL Guild Manager
#### Subsystem Coverage
| Subsystem | Coverage | Depth |
|---|---|---|
| Identity/Trust | Partial | Tracks members, gear screenshots/scores, wishlist items, and voice presence; identity remains game/Discord bound. |
| Intake | Yes | Recruitment links and application handling are core features. |
| Cases | Partial | Audit system exists, but not a generalized disciplinary case model. |
| Chapters | Yes | Supports multiple in-game guilds and subguilds. |
| Activity/Compliance | Yes | Events, attendance, voice activity, VOD reviews, participation stats. |
| Permissions | Yes | Explicit permissions management is part of premium. |
| Governance | Partial | Complete audit system helps guild transparency, but governance stays within guild operations. |

#### Integration Model
Web app plus Discord bot, Discord voice attendance tracking, and game-specific guild workflows.

#### Unified vs Siloed
Strong single-service approach. The official testimonials explicitly position TLGM as a replacement for several bots and spreadsheets.

#### Audit/Governance
Better than most loot/DKP tools because audit is explicit and user-visible.

#### Target Audience
Throne and Liberty guilds. Official site claims trust from `4494` guilds.

#### Pricing
`Free`, `Premium Quarterly` effective `from $14.99/month`, and `Premium $19.99/month`.

#### Status
Active. Testimonials on the homepage describe near-weekly updates and strong support responsiveness.

#### Limitations & User Complaints
Game-specific and raid/guild-ops centric. Strong operational audit, but not a broader governance or platform-boundary model.

Sources:
- https://tlgm.app/
- https://discord.com/discovery/applications/1197274411728904192
- https://www.reddit.com/r/throneandliberty/comments/1gtryri/official_launch_free_lootmanager_a_complete_guild/

### CoGM
#### Subsystem Coverage
| Subsystem | Coverage | Depth |
|---|---|---|
| Identity/Trust | Partial | Roster, OCR gear extraction, per-game stats, but not a deep trust/adjudication layer. |
| Intake | Yes | Recruitment and announcements are part of the free core. |
| Cases | Partial | Audit logs exist, but there is no broad case-management object. |
| Chapters | Yes | Multi-guild and multi-game management are part of the pitch. |
| Activity/Compliance | Yes | Events, attendance, analytics, party builder, DKP, loot auctions. |
| Permissions | Yes | `130+` granular permissions. |
| Governance | Partial | Audit logs and granular permissions help, but still no shared lifecycle-first governance model. |

#### Integration Model
Web platform plus Discord bot. Multi-game positioning across BDO, WoW Classic, FFXIV, Albion, Warframe, and others.

#### Unified vs Siloed
Ambitious shared model across multiple games, closer to the target vision than many peers.

#### Audit/Governance
Good operational controls for an early-stage product, still mostly around guild administration.

#### Target Audience
Multi-game MMO communities and officers who want one tool across several games.

#### Pricing
`Free`, `Pro $10/guild/month`.

#### Status
Active but still early-stage. The site simultaneously advertises live usage (`50+ guilds managed`) and a waitlist/launch framing, which suggests rollout is still in progress.

#### Limitations & User Complaints
Promising shape, but not yet mature. Product messaging mixes "live" and "join waitlist," which is a risk signal for adoption confidence.

Sources:
- https://cogm.app/
- https://cogm.app/games/final-fantasy-xiv/discord-bot
- https://throney.gg/

## Community Management Workarounds

Communities still appear to assemble operations from multiple surfaces rather than buy one true suite.

- The most common workaround pattern is `Discord + Google Sheets/Excel + one or more bots + optional guild website`.
- GuildHall's core pitch is explicitly "stop juggling spreadsheets" and "your raid night runs itself," which only works as marketing if spreadsheet sprawl is common.
- TL Guild Manager testimonials repeatedly describe replacing `4-5 Discord bots` and Excel-like admin overhead with one service.
- Guilds of WoW still treats spreadsheets as a first-class companion surface rather than something obsolete, which is revealing: even advanced suites still keep export-shaped workflows alive.
- Older website builders like Gamer Launch and Shivtr remain active, but their strategic weakness is the extra surface area. Communities must keep a separate website socially alive while Discord handles the real-time command layer.

Representative sources:
- https://guildhall.run/
- https://tlgm.app/
- https://guildsofwow.com/
- https://www.reddit.com/r/classicwow/comments/bxwf51/guild_managers_what_tools_are_you_using_to_manage/
- https://www.reddit.com/r/classicwowtbc/comments/1sktegh/i_built_an_allinone_guild_management_tool_for_wow/
- https://www.reddit.com/r/MMORPG/comments/1r4h5uq/i_built_a_guild_management_platform_and_i_need/

## Gap Analysis

### What the market does cover
- Recruitment plus applications is well covered. Appy, Guildbase, Guild Manager, Guilds of WoW, TLGM, and CoGM all do this credibly.
- Raid/event operations are also well covered, especially in game-specific tools like GuildHall, Guilds of WoW, and TLGM.
- Moderation/security is mature on the Discord-bot side, especially with Wick.
- Permissions are present almost everywhere, but usually as role toggles or admin rights, not as scoped authority over lifecycle objects.

### What the market does not cover
- **Unified operational model across all 7 subsystems**: every strong product clusters around only 2-4 subsystems. Bots skew security or intake. Web suites skew recruitment plus events. Game tools skew raid ops. None deeply spans identity, intake, cases, chapters, activity, permissions, and governance together.
- **Shared audit chain across intake, cases, chapters, activity**: several products have logs, transcripts, or audit pages, but they are local to one feature family. No product in this pass exposed a single chain of causality from application -> adjudication -> permission grant -> chapter placement -> activity enforcement -> governance review.
- **Platform-boundary isolation**: nearly all products remain tightly bound to Discord, a specific game, or both. Even the stronger suites treat Discord roles, in-game APIs, or addon data as the primary operational identity, rather than projecting an independent domain model outward.
- **Declarative intent with reconciliation**: current tools are imperative. Officers click actions, bots mutate state, and dashboards show results. I did not find a product centered on desired state plus reconciler behavior for permissions, rosters, chapter membership, or governance rules.
- **Scoped authority instead of rank-based authority**: almost every tool exposes hierarchical roles, admin permissions, or staff ranks. Fine-grained permissions exist, but they are still mostly person/rank-based, not scoped to bounded operational authority over a case, chapter, or lifecycle phase.
- **Lifecycle-first objects with explicit state machines**: Guildbase comes closest with multi-stage applications; Guild Manager comes close with applications plus audit; TLGM gets close with events/audits. But the market still lacks a general platform where applications, cases, chapter memberships, compliance findings, and governance proposals are all explicit objects with state transitions, guards, and audit semantics.

### Closest analogs to the target direction
- **Guild Manager** is the closest broad guild suite. It meaningfully connects roster, activity, permissions, applications, and audit, but still stops short of explicit case/governance objects and platform-boundary independence.
- **Guildbase** is the closest intake-first governance surface. It has workflow stages, transcripts, and risk analysis, but it remains centered on applications/tickets rather than the full guild operating model.
- **GuildHall / Guilds of WoW / TLGM** are the closest examples of a genuinely shared operational model inside a narrow domain. They prove users value a single source of truth once the scope is constrained to one game or one operational slice.

### Strategic takeaway
- The competitive gap is not "more features than a bot."
- The gap is a **shared object model** that survives Discord boundaries, keeps a **single audit chain**, and gives officers **scoped authority over lifecycle objects** instead of just more server-admin toggles.
- That is the space where the proposed platform is differentiated.
