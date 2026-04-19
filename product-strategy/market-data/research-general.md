# General Guild Management Bots — Research Findings

Pricing and feature pages were verified on April 16, 2026. Complaint sections summarize user-reported issues from review/community sources; treat them as recurring signals, not audited facts.

## MEE6

### Features
- Moderation tools: automated moderation and filters to keep the server safe. **Subsystem mapping:** Case Management; Permissions. Source: https://mee6.xyz/
- Advanced custom commands: configurable commands for automation and repeated messaging. **Subsystem mapping:** Governance; Permissions. Source: https://mee6.xyz/
- Welcome messages: automated onboarding and rule reminders for new members. **Subsystem mapping:** Intake/Adjudication. Source: https://mee6.xyz/
- Reaction roles: self-assigned roles through message reactions. **Subsystem mapping:** Permissions. Source: https://mee6.xyz/
- Social alerts: Twitch and other social-media notifications. **Subsystem mapping:** Activity/Compliance. Source: https://mee6.xyz/
- Leveling and XP: activity-based progression and rewards. **Subsystem mapping:** Activity/Compliance. Source: https://mee6.xyz/
- Giveaways, polls, and surveys: engagement tooling for lightweight community coordination. **Subsystem mapping:** Governance; Activity/Compliance. Source: https://mee6.xyz/
- Ticketing plugin: support-style tickets for member issues. **Subsystem mapping:** Case Management. Source: https://mee6.xyz/

### Pricing
- Free: installable with a limited free surface, but MEE6's own support article says Premium is what unlocks moderation tools, welcome messages, and custom commands for a server. Sources: https://help.mee6.xyz/support/solutions/articles/101000539351-understanding-mee6-services-from-premium-to-ai-to-pro , https://wiki.mee6.xyz/premium
- Premium: monthly `$5.99`, yearly `$24.99` for the first year then `$49.99`, lifetime `$44.99`; applies to one server, but can be transferred to another server. Source: https://mee6.xyz/en/premium
- Pro: separate personal plan, not a server-management plan; monthly `$3.49`, yearly `$1.99` per month, lifetime `$42.49`, focused on XP boost and rank-card cosmetics. Sources: https://mee6.xyz/en/pro , https://help.mee6.xyz/support/solutions/articles/101000539351-understanding-mee6-services-from-premium-to-ai-to-pro

### Limitations
- Premium is per-server, not account-wide, which increases operating cost for multi-guild organizations. Sources: https://mee6.xyz/en/premium , https://wiki.mee6.xyz/premium
- MEE6's own support docs frame key operational features such as moderation, welcome messages, and custom commands as Premium features. Source: https://help.mee6.xyz/support/solutions/articles/101000539351-understanding-mee6-services-from-premium-to-ai-to-pro
- Official feature surfaces emphasize moderation, engagement, tickets, and automation, but do not show native trust profiles, application adjudication pipelines, chapter/roster lifecycle management, OCR-backed compliance, scoped authority grants, or policy versioning. This gap is inferred from the official homepage and premium/wiki pages. Sources: https://mee6.xyz/ , https://wiki.mee6.xyz/premium

### User Complaints
- Paywall creep: recent Reddit complaints argue that features once treated as basic or free are now behind a paywall. Sources: https://www.reddit.com/r/discordapp/comments/19dppos/the_shameful_state_mee6_has_turned_into/ , https://www.reddit.com/r/discordapp/comments/1kon2am/literally_everything_mee6_is_used_for_is_now/
- Poor value for free-tier operators: a Reddit thread describes MEE6 as leaving servers "frozen" because free settings can no longer be meaningfully changed. Source: https://www.reddit.com/r/discordapp/comments/19dppos/the_shameful_state_mee6_has_turned_into/
- Support and functionality frustrations: Trustpilot reviews surface recurring complaints about pricing, feature removals/restrictions, functionality issues, and weak customer support. Source: https://www.trustpilot.com/review/mee6.xyz

## Carl-bot

### Features
- Reaction roles: up to 250 roles on the main feature page, with multiple modes such as unique and verify. **Subsystem mapping:** Permissions. Source: https://carl.gg/
- Logging: deleted messages, member updates, and server changes can be split across channels. **Subsystem mapping:** Case Management; Governance. Source: https://carl.gg/
- Moderation and automod: modlogs, bulk role management, anti-spam, and punishments for bad links or inappropriate content. **Subsystem mapping:** Case Management; Permissions. Source: https://carl.gg/
- Suggestions: members can submit ideas, vote, and receive decision notifications. **Subsystem mapping:** Intake/Adjudication; Governance. Source: https://carl.gg/
- Granular permission system: command-by-command rule management and output control. **Subsystem mapping:** Permissions; Governance. Source: https://carl.gg/
- Custom commands and welcome/farewell messages: automation for routine server operations. **Subsystem mapping:** Governance; Intake/Adjudication. Source: https://carl.gg/
- Starboards, post counts, and user info: lightweight engagement tooling. **Subsystem mapping:** Activity/Compliance. Source: https://carl.gg/

### Pricing
- Free: broad free feature set across reaction roles, logging, automod, custom commands, suggestions, and welcomes. Source: https://carl.gg/
- Basic: `$5.00` monthly for 1 server, including custom avatar/banner and full leveling/XP. Source: https://carl.gg/get-premium
- Standard: `$10.00` monthly for 3 servers, adding sticky messages and up to 1000 reaction roles. Source: https://carl.gg/get-premium
- Premium: `$20.00` monthly for unlimited servers, adding immediate auto-feeds and higher purge limits. Source: https://carl.gg/get-premium

### Limitations
- A number of useful operational capabilities are packaged as higher limits rather than new workflows, for example more weblog entries, more reaction roles, higher purge limits, timed reaction roles, temporary channels, and richer feeds. Source: https://carl.gg/get-premium
- Carl-bot is strong on moderation and role operations, but the official feature set does not show native application review queues, case lifecycles, trust profiling, chapter rosters, OCR/compliance tooling, or policy/config versioning. This is inferred from the homepage and premium page. Sources: https://carl.gg/ , https://carl.gg/get-premium
- Suggestion handling is lightweight intake, not adjudication: the feature supports ideas and voting, but not multi-step review workflows, evidence collection, or durable decision records. Inference from official feature copy. Source: https://carl.gg/

### User Complaints
- Support and staff quality: Top.gg shows a relatively weak `3.12` rating from `590` reviews and surfaces "terrible staff and dev" as a visible complaint theme. Source: https://top.gg/bot/235148962103951360
- Reliability concerns: recent Reddit comments mention Carl-bot "having a few issues lately" and going down often. Sources: https://www.reddit.com/r/discordbots/comments/1h3ahpu/can_anyone_help_me_with_carl_bot_reaction_roles/ , https://www.reddit.com/r/discordapp/comments/1izj5k2/am_i_not_understanding_whats_going_on_or_are/
- Friction with maintainers: a long-running Reddit criticism argues Carl-bot's team is combative or dismissive when users report bugs. Source: https://www.reddit.com/r/discordapp/comments/z4fan1/stop_suggesting_carl_bot_and_yagpdb_as/

## Dyno

### Features
- Moderation and automod: mod logs, timed mutes/bans, anti-spam, and configurable moderation modules. **Subsystem mapping:** Case Management; Permissions. Sources: https://dyno.gg/bot , https://dyno.gg/
- Web dashboard: centralized browser-based configuration for modules and server operations. **Subsystem mapping:** Governance; Permissions. Source: https://dyno.gg/bot
- Announcements: automated server announcements. **Subsystem mapping:** Governance. Source: https://dyno.gg/bot
- Custom commands, tags, reminders, and AFK status: operational automation and utility commands. **Subsystem mapping:** Governance. Source: https://dyno.gg/bot
- Autoroles and joinable ranks: automatic and self-selected role assignment. **Subsystem mapping:** Permissions. Source: https://dyno.gg/bot
- Logging: event logs for server activity. **Subsystem mapping:** Case Management; Governance. Source: https://dyno.gg/bot
- Forms: configurable forms for collecting information from members. **Subsystem mapping:** Intake/Adjudication. Source: https://dyno.gg/bot

### Pricing
- Free: core bot, dashboard, moderation, automod, autoroles, custom commands, logging, forms, and related modules are advertised on the public bot page. Source: https://dyno.gg/bot
- Standard: `$5.99` monthly for one server, adding unlimited commands/modules, advanced automod, advanced starboard, autopurge, slowmode, voice-text linking, and avatar options. Source: https://dyno.gg/premium
- Premium: `$7.99` monthly for one server, adding Twitch, YouTube, TikTok, Reddit, and Kick integrations. Source: https://dyno.gg/premium
- Custom: `$12.99` monthly for a fully hosted custom Dyno Premium instance, adding uploadable avatar, custom username, custom status, and higher performance/uplink guarantees. Source: https://dyno.gg/premium

### Limitations
- Premium is priced per server for Standard and Premium tiers. Source: https://dyno.gg/premium
- Dyno's "Forms" feature helps with intake, but official marketing does not show reviewer queues, decision states, appeal flows, or durable adjudication records. This limitation is inferred from the public feature description. Source: https://dyno.gg/bot
- Official product copy is strong on moderation and utility, but does not surface native trust profiles, chapter/roster management, OCR compliance, scoped authority grants, or policy versioning. This gap is inferred from the public bot and premium pages. Sources: https://dyno.gg/bot , https://dyno.gg/premium

### User Complaints
- Outdated product feel: Top.gg visible review themes include "bot is stuck in the 2017 meta of Discord," "modules and features are outdated," and "devs are out of touch with the community." Source: https://top.gg/bot/155149108183695360
- Reliability complaints: Top.gg also surfaces outage-oriented complaints such as "suddenly died without saying anything" and "outage every single day," while a recent Reddit thread asked why Dyno was no longer working and why the support server was locked down. Sources: https://top.gg/bot/155149108183695360 , https://www.reddit.com/r/Dynodiscord/comments/1npvkgf/whats_going_on_with_dyno/
- Paywall complaints: visible review text on Top.gg includes "u gotta pay for most other features." Source: https://top.gg/bot/155149108183695360

## YAGPDB

### Features
- Feeds: Reddit, YouTube, Twitch, and RSS feeds, plus join/leave messages and direct messages on join. **Subsystem mapping:** Activity/Compliance; Intake/Adjudication. Source: https://yagpdb.xyz/
- Self-assignable roles: command-driven or menu-based self-role management with multiple groups. **Subsystem mapping:** Permissions. Source: https://yagpdb.xyz/
- Automatic moderation: configurable automod that can mute, kick, or ban after repeated violations. **Subsystem mapping:** Case Management; Permissions. Source: https://yagpdb.xyz/
- General moderation: kick, ban, timed mute, modlogs, and warnings. **Subsystem mapping:** Case Management. Source: https://yagpdb.xyz/
- Custom commands: flexible triggered commands and automated answers. **Subsystem mapping:** Governance; Permissions. Source: https://yagpdb.xyz/
- Premium perks extend tickets, feeds, roles, and custom-command capacity; premium can also enable private-thread tickets. **Subsystem mapping:** Case Management; Permissions; Governance. Source: https://yagpdb.xyz/premium-perks

### Pricing
- Free: core moderation, feeds, self-roles, and custom commands are advertised on the main site. Source: https://yagpdb.xyz/
- Premium pricing is not shown directly on the premium-perks page, which only links users to Patreon or Discord purchases. Source: https://yagpdb.xyz/premium-perks
- Patreon pricing currently shows `1 Premium` for `$5/month`, `2 Premium` for `$8.99/month`, `3 Premium` for `$12.99/month`, and `5 Premium` for `$16.99/month`. Source: https://www.patreon.com/yagpdb/membership

### Limitations
- Pricing transparency is weak on the official perks page because the page lists benefits without listing the actual prices. Source: https://yagpdb.xyz/premium-perks
- Many premium benefits are limit removals rather than new workflows: more feeds, longer message cache, more custom commands, more voice roles, and higher automod/custom-command thresholds. Source: https://yagpdb.xyz/premium-perks
- YAGPDB is extremely configurable, but the public feature set still does not show native trust profiles, formal application adjudication, chapter rosters, OCR-backed activity checks, scoped authority grants, or versioned policy/config management. This gap is inferred from the main site and premium-perks page. Sources: https://yagpdb.xyz/ , https://yagpdb.xyz/premium-perks

### User Complaints
- Complexity and learning curve: Reddit comments repeatedly describe YAGPDB as powerful but too complex, especially for custom commands. Sources: https://www.reddit.com/r/discordapp/comments/f3s3tr/yagpdb_vs_auttaja/ , https://www.reddit.com/r/discordapp/comments/z4fan1/stop_suggesting_carl_bot_and_yagpdb_as/
- Support quality: Top.gg surfaces "Bad support," "inadequate answers from moderators," and "lack of response to queries" as visible negative themes. Source: https://top.gg/bot/204255221017214977
- Premium friction: the perks page explicitly notes that premium slots are not transferable between Patreon and Discord purchases, which can be painful for operators who switch billing channels. Source: https://yagpdb.xyz/premium-perks

## Arcane

### Features
- Leveling and role rewards: activity-based leveling, role rewards, and leaderboards. **Subsystem mapping:** Activity/Compliance; Permissions. Source: https://arcane.bot/
- Voice leveling: voice participation can earn XP, with filters for AFK, mute, and idle users. **Subsystem mapping:** Activity/Compliance. Source: https://arcane.bot/
- Channel counters: member, boost, and goal counters for server stats. **Subsystem mapping:** Activity/Compliance; Governance. Source: https://arcane.bot/
- YouTube notifications: creator alerts into Discord. **Subsystem mapping:** Activity/Compliance. Source: https://arcane.bot/
- Advanced logging and auto moderation: join/leave logs and moderation actions such as warn, kick, mute, and ban. **Subsystem mapping:** Case Management; Permissions. Source: https://arcane.bot/
- Custom commands and reaction roles: workflow automation and self-service role assignment. **Subsystem mapping:** Governance; Permissions. Source: https://arcane.bot/
- Custom bot identity: premium customization of name, avatar, banner, and about-me. **Subsystem mapping:** Governance. Sources: https://arcane.bot/ , https://arcane.bot/premium

### Pricing
- Free: leveling, logging, custom commands, counters, reaction roles, and moderation are marketed on the public homepage. Source: https://arcane.bot/
- Premium: monthly `$7/mo` or yearly `$75/y`; includes Bot Customizer and lifted limits across role rewards, leaderboards, counters, logging retention, reaction roles, auto roles, YouTube alerts, and custom commands. Source: https://arcane.bot/premium

### Limitations
- Voice XP is premium-only and requires the Premium bot in the server. Source: https://docs.arcane.bot/plugins/leveling/setup/xp-options
- Arcane's public positioning is much more engagement/leveling-centric than operations-centric; the official feature set does not show native applications, support tickets, trust profiles, chapter rosters, OCR compliance, scoped authority grants, or policy versioning. This gap is inferred from the homepage, premium page, and docs. Sources: https://arcane.bot/ , https://arcane.bot/premium , https://docs.arcane.bot/plugins/leveling/setup/xp-options
- Premium mostly expands limits inside the existing Arcane model rather than adding deeper governance or workflow capabilities. Source: https://arcane.bot/premium

### User Complaints
- Support and usability complaints: Top.gg shows a strong overall rating (`4.67`, `4,049` reviews) but still surfaces visible negative themes including "poor customer service" and "difficult to use." Source: https://top.gg/bot/437808476106784770
- Feature/reliability complaints: Top.gg also surfaces "not enough features" and "performance issues" as visible criticisms. Source: https://top.gg/bot/437808476106784770
- Paywall and workflow complaints: a recent Reddit discussion about XP bots groups Arcane among tools that hide important capabilities behind a paywall or lack a satisfactory dashboard. Source: https://www.reddit.com/r/Discord_Bots/comments/1mwqi9w/any_good_levellingxp_bots_without_a_paywall/
- Operational bugs: a 2024 Reddit thread reports Arcane level roles not being assigned reliably when members hit configured milestones. Source: https://www.reddit.com/r/Discord_Bots/comments/1bzbcqv/arcane_level_roles_not_working_details_below/

## Cross-Bot Gaps

- Identity/Trust: none of the five bots markets persistent trust profiles, trust signals, reputation graphs, alt-account heuristics, or operator-facing member dossiers. They mostly stop at roles, warnings, and XP. Sources: https://mee6.xyz/ , https://carl.gg/ , https://dyno.gg/bot , https://yagpdb.xyz/ , https://arcane.bot/
- Intake/Adjudication: Dyno Forms, Carl suggestions, MEE6 tickets, and YAGPDB private-thread tickets provide intake primitives, but none of these products advertises a full application-review workflow with reviewer queues, evidence attachments, decision states, and appeals. Inference from official feature pages. Sources: https://dyno.gg/bot , https://carl.gg/ , https://mee6.xyz/ , https://yagpdb.xyz/premium-perks , https://arcane.bot/
- Case Management: these bots do moderation logs, warnings, tickets, and punishments, but not durable case records with ownership, SLAs, status transitions, evidence bundles, or follow-up tasks. Inference from official feature pages. Sources: https://mee6.xyz/ , https://carl.gg/ , https://dyno.gg/bot , https://yagpdb.xyz/ , https://arcane.bot/
- Chapters: none of the five bots markets sub-community roster management, chapter lifecycle workflows, or inter-chapter organization. Sources: https://mee6.xyz/ , https://carl.gg/ , https://dyno.gg/bot , https://yagpdb.xyz/ , https://arcane.bot/
- Activity/Compliance: the market is strong on XP, feeds, counters, alerts, and basic participation metrics, but not on evidence-backed compliance checks such as screenshot OCR, rule thresholds, exception handling, or officer review workflows. Sources: https://mee6.xyz/ , https://dyno.gg/bot , https://arcane.bot/ , https://yagpdb.xyz/ , https://carl.gg/
- Permissions: reaction roles, autoroles, joinable ranks, and command rules are common, but scoped authority grants, temporary delegated powers with auditability, and approval-based role changes are not. Sources: https://mee6.xyz/ , https://carl.gg/ , https://dyno.gg/bot , https://yagpdb.xyz/ , https://arcane.bot/
- Governance: every bot offers some combination of logs, dashboards, and custom commands, but none markets versioned policy/config management, migration history, formal audit trails tied to human actors, or structured change control. Sources: https://carl.gg/ , https://dyno.gg/bot , https://mee6.xyz/ , https://yagpdb.xyz/ , https://arcane.bot/
