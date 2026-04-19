# Ticketing Bots — Research Findings

Method note: this report prioritizes official product/docs pages, open-source issue trackers, and marketplace listings. Firecrawl could not scrape Reddit threads directly, so "user complaints" are strongest where public GitHub issues or marketplace ratings exist; otherwise they are mostly product-imposed limitations visible in official docs.

## Ticket Tool

### Ticket Workflow
- Tickets are created from Discord panels with buttons, and the product also supports forms before ticket creation and command-style tickets like `$new`. The reviewed lifecycle is mostly fixed around `open -> close -> reopen/delete`, with optional close requests and escalation to another panel. Sources: https://tickettool.xyz/ , https://docs.tickettool.xyz/general/commands

### Categorization
- Ticket Tool is panel-centric. Each panel can create tickets into a configured open category, move closed tickets into a closed category, and spill into overflow categories when Discord's 50-channel-per-category limit is reached. Sources: https://docs.tickettool.xyz/dashboard/panel-configs/category-options , https://tickettool.xyz/

### Assignment
- Claiming exists, but it is a Premium feature. Claimed tickets can rename or move the channel, restrict actions to the claimer, and change support-team permissions or ticket-owner roles. Sources: https://docs.tickettool.xyz/dashboard/panel-configs/claiming-options , https://tickettool.xyz/premium

### Transcript/Audit
- Ticket Tool can save transcripts to a Discord channel, DM them to the ticket creator, and store them on Google Drive. The transcript system is capped at 1,000 messages and Premium unlocks broader transcript usage and larger attachment embedding. Sources: https://docs.tickettool.xyz/dashboard/panel-configs/transcript-options

### Moderation Integration
- The docs reviewed show ticket operations, escalation, permissions, and transcripts, but I did not find first-party warn/ban tracking or a moderation case ledger. This is an inference from the product docs rather than an explicit vendor statement. Sources: https://docs.tickettool.xyz/general/commands , https://docs.tickettool.xyz/dashboard/panel-configs/category-options , https://docs.tickettool.xyz/dashboard/panel-configs/claiming-options

### Pricing
- Standard is free. Premium is listed at `$7.99/month` per server and unlocks claiming, automation, DM flows, and fuller customization. Source: https://tickettool.xyz/premium

### Limitations & User Complaints
- Transcript history is capped at 1,000 messages. Source: https://docs.tickettool.xyz/dashboard/panel-configs/transcript-options
- Claiming and a meaningful share of assignment workflow are paywalled. Sources: https://docs.tickettool.xyz/dashboard/panel-configs/claiming-options , https://tickettool.xyz/premium
- The free plan is rate-limited to `10 tickets a minute` on the pricing page. Source: https://tickettool.xyz/premium
- I did not find a strong public issue tracker for operator complaints; the clearest constraints are official product limits, not public bug reports.

## Helper.gg

### Ticket Workflow
- Helper.gg is built around a central web panel. Operators can create tickets with `-ticket`, close them with or without a reason, shadow-close them, change status, claim/unclaim, and run timed closes. Staff can also respond directly from the panel. Sources: https://helper.gg/ , https://helper.gg/features

### Categorization
- Helper.gg supports multiple "TicketTag Departments", per-tag messages, creation-channel restrictions, and per-tag transcript destinations. It is more tag/department driven than explicit workflow-state driven. Sources: https://helper.gg/features

### Assignment
- The product supports claim/unclaim, support roles, staff sub-accounts, and panel-based staff permissions. Sources: https://helper.gg/ , https://helper.gg/features

### Transcript/Audit
- Helper.gg markets unlimited ticket logging with every message viewable in the panel or a transcript. Premium adds HTML and JSON transcripts sent by email, to a Discord channel, or to the ticket creator via DM. Sources: https://helper.gg/ , https://helper.gg/features

### Moderation Integration
- I did not find first-party moderation case tracking, warn history, or ban history in the reviewed pages. The tool looks optimized for support workflows, not a broader moderation record system. Sources: https://helper.gg/ , https://helper.gg/features

### Pricing
- Free: `$0/month`. Premium: `$4.90/month`. Supreme is listed as a `$3.90/month` Premium add-on for white-label style customization. Source: https://helper.gg/pricing

### Limitations & User Complaints
- Several useful transcript-delivery and customization features are paid. Sources: https://helper.gg/features , https://helper.gg/pricing
- The product surface is command/tag/panel heavy; I did not find evidence of configurable state machines or typed case actions. Source: https://helper.gg/features
- I did not find a public docs portal or public issue tracker with high-signal complaints, so the clearest limitations here are product-shape limitations rather than operator bug reports.

## SCNX Support Bot

### Ticket Workflow
- SCNX bundles two support modes in one product: a channel-based Ticket System and a DM-based Modmail flow. The documented lifecycle is user opens ticket -> private channel/thread is created -> staff responds -> close confirmation runs -> transcript is saved -> feedback is collected -> analytics update. Sources: https://scnx.xyz/support-bot , https://scnx.xyz/support-bot/ticket-system , https://docs.scnx.xyz/docs/modmail/basics/

### Categorization
- SCNX supports topic categories, buttons and dropdown panels, forms, FAQ topics, and multiple panels. The Ticket System page advertises up to 25 buttons per panel; the feature comparison shows per-topic limits, colors, and required roles on the Ticket System side. Sources: https://scnx.xyz/support-bot/ticket-system , https://docs.scnx.xyz/it/docs/support-bot/feature-comparison/

### Assignment
- SCNX supports manual claiming and auto-assignment, plus hold/pause, capacity monitoring, queueing, and per-topic routing signals. Sources: https://scnx.xyz/support-bot , https://docs.scnx.xyz/it/docs/support-bot/feature-comparison/

### Transcript/Audit
- SCNX saves transcripts automatically, supports log channels, supports transcript delivery on close, and advertises AI summaries plus analytics. The feature comparison also references `modmail.net` transcript integration. Sources: https://scnx.xyz/support-bot , https://scnx.xyz/support-bot/ticket-system , https://docs.scnx.xyz/docs/modmail/basics/ , https://docs.scnx.xyz/it/docs/support-bot/feature-comparison/

### Moderation Integration
- SCNX is closer to moderation-adjacent workflows than most hosted ticket bots: it supports blocklists with duration and reason, anonymous staff messaging, and use cases like ban appeals. I still did not find a first-party warn/ban case ledger comparable to moderation-case systems. Sources: https://docs.scnx.xyz/docs/modmail/basics/ , https://scnx.xyz/support-bot/ticket-system

### Pricing
- The SCNX Starter plan is free, but ad-supported. Unlimited is `€4.99/month`; Professional is `€7.99/month`. Eligible servers can start a free trial without payment information. Sources: https://docs.scnx.xyz/docs/scnx/guilds/plans/ , https://scnx.xyz/support-bot

### Limitations & User Complaints
- The free plan requires periodic dashboard video-ad check-ins to keep bots running, which is a real operational cost even though the plan is "free." Source: https://docs.scnx.xyz/docs/scnx/guilds/plans/
- The old Modmail V2 docs are explicitly marked outdated, and some feature docs are incomplete. The ticket-claiming doc page still says "Coming soon." Sources: https://docs.scnx.xyz/docs/modmail/basics/ , https://docs.scnx.xyz/docs/modmail/advanced-features/ticket-claiming
- The feature comparison says close reasons exist in Modmail but not in the Ticket System, which matters for case-resolution rigor. Source: https://docs.scnx.xyz/it/docs/support-bot/feature-comparison/

## Discord Tickets

### Ticket Workflow
- Discord Tickets supports ticket creation from panels, `/new`, context-menu reporting from a message, and "create a ticket for user" prompts. Closing can be reciprocal via `/close`, or bypassed by staff using `/force-close`; the bot also supports moving, transferring, changing priority, claiming, and releasing. Sources: https://discordtickets.app/ , https://discordtickets.app/commands/

### Categorization
- Categories are first-class objects with descriptions, emoji, required roles, staff roles, cooldowns, member limits, total limits, required topics, and channel naming rules. Sources: https://discordtickets.app/configuration/categories/

### Assignment
- Claiming is configured per category and can expose `/claim` and `/release` plus a claim button. The claim behavior is opinionated: claiming removes other staff from the ticket channel. The bot also supports move and transfer actions. Sources: https://discordtickets.app/configuration/categories/ , https://discordtickets.app/commands/

### Transcript/Audit
- Discord Tickets markets encrypted archives for messages, attachments, and avatars, plus a portal web app to read historical tickets. `/transcript` returns a markdown transcript file. Sources: https://discordtickets.app/ , https://discordtickets.app/commands/ , https://github.com/discord-tickets/bot

### Moderation Integration
- This was the strongest moderation-adjacent feature I found in the ticket-bot cohort: the context-menu action "Create a ticket from message" is explicitly described as useful for reporting messages and their senders. I still did not find a warn/ban case ledger in the reviewed docs. Source: https://discordtickets.app/commands/

### Pricing
- The public site says there is no premium plan and "everyone gets everything for free." The open-source repo additionally offers three deployment modes: public bot, managed bot, or self-hosting. Sources: https://discordtickets.app/ , https://github.com/discord-tickets/bot

### Limitations & User Complaints
- Assignment is fairly aggressive: per-category claiming removes other staff from the channel. Source: https://discordtickets.app/configuration/categories/
- The workflow is still action-based rather than admin-defined state-machine based. This is an inference from the commands and category model. Sources: https://discordtickets.app/commands/ , https://discordtickets.app/configuration/categories/
- If you want more than the public branded bot, you take on managed/self-hosted operational choices. Source: https://github.com/discord-tickets/bot

## Modmail

### Ticket Workflow
- Modmail is a shared-inbox model rather than a panel-first ticket system. Users DM the bot; the bot creates a thread channel, relays messages between staff and the user, supports snippets, and generates logs when a thread closes. Sources: https://docs.modmail.dev/ , https://docs.modmail.dev/installation , https://github.com/modmail-dev/Modmail

### Categorization
- Modmail is less category/state oriented than ticket bots. Its organizing primitives are thread channels, snippets, aliases, permissions, account-age/guild-age gates, and optionally separate staff-server routing. Sources: https://docs.modmail.dev/ , https://docs.modmail.dev/installation

### Assignment
- Modmail's default assignment model is "shared inbox" rather than a dashboard queue. In practice, assignment appears less first-class than dashboard bots: recent repo activity explicitly replaced a prior claim plugin because it was "fundamentally broken." Source: https://github.com/modmail-dev/Modmail

### Transcript/Audit
- Modmail's strongest differentiator is audit/search: Logviewer generates log links, `?logs` shows a user's past logs, and `?logs search` supports text search. Discord-auth-protected logs are available as a paid extra. Sources: https://docs.modmail.dev/ , https://github.com/modmail-dev/Modmail

### Moderation Integration
- Modmail is moderation-friendly in the conversational sense: shared inbox, anonymous replies, blocklists, account-age and guild-age gates, and separate staff-server routing. But it is still not a general moderation case ledger with warn/ban/case history in the reviewed core docs. Sources: https://docs.modmail.dev/ , https://docs.modmail.dev/installation , https://github.com/modmail-dev/Modmail

### Pricing
- The software is free and self-hosted. There is no public invite. The project also offers managed hosting at roughly `$4-5/month`, while other hosting methods introduce their own infra costs. Sources: https://docs.modmail.dev/installation , https://github.com/modmail-dev/Modmail

### Limitations & User Complaints
- There is no public bot invite; each server needs its own dedicated self-hosted bot plus Logviewer for the full experience. Sources: https://docs.modmail.dev/installation , https://github.com/modmail-dev/Modmail
- Operators explicitly requested import/export settings because repeated setup is tedious and easy to get wrong; that request was still open in the reviewed issue. Source: https://github.com/modmail-dev/Modmail/issues/3248
- A confirmed bug caused `?delete` to remove a message from the staff thread while leaving it in the recipient's DMs until fixed. Source: https://github.com/modmail-dev/Modmail/issues/3041
- The repo's latest history also indicates claim functionality had enough trouble that the team replaced the claim plugin in March 2026. Source: https://github.com/modmail-dev/Modmail

## ticket.pm

### Ticket Workflow
- ticket.pm is not a full ticket workflow product. It is transcript infrastructure: host, share, search, and export Discord transcripts, with dashboard and API upload paths. Sources: https://ticket.pm/ , https://ticket.pm/docs , https://discord.com/discovery/applications/1230456972776570911

### Categorization
- I did not find ticket-category or panel workflow concepts. The product appears to categorize at the transcript/dashboard layer rather than the ticket-lifecycle layer. Sources: https://ticket.pm/ , https://ticket.pm/docs

### Assignment
- No claim, routing, team assignment, or staff-workload model was surfaced in the reviewed pages. Sources: https://ticket.pm/ , https://ticket.pm/docs

### Transcript/Audit
- This is where ticket.pm is strongest: attachment saving, a searchable dashboard, a transcript viewer, exports as JSON/Markdown/plain text, and direct `/v2` transcript/media APIs. Sources: https://ticket.pm/ , https://ticket.pm/docs

### Moderation Integration
- None found beyond transcript retention/search. It looks complementary to a ticket bot, not a replacement for one. Sources: https://ticket.pm/ , https://ticket.pm/docs

### Pricing
- I did not find public pricing on the homepage or docs reviewed. The Discord App Directory listed the app in `417 servers` at scrape time, but not a separate pricing table. Sources: https://ticket.pm/ , https://ticket.pm/docs , https://discord.com/discovery/applications/1230456972776570911

### Limitations & User Complaints
- ticket.pm solves transcript retention and search, not ticket lifecycle, categorization, or assignment. Sources: https://ticket.pm/ , https://ticket.pm/docs
- Public pricing was not discoverable in the reviewed pages.

## Mava

### Ticket Workflow
- Mava is an omnichannel support platform rather than a Discord-only bot. It routes Discord, Telegram, Slack, web chat, and email support into one shared inbox, with AI able to answer in public channels and private tickets before handing off to humans. Sources: https://www.mava.app/ , https://www.mava.app/ticket-bot

### Categorization
- The reviewed material emphasizes conversational forms, categories/tags/agents, status tracking, custom views, and cross-channel routing. It is more like a support platform than a Discord bot. Sources: https://www.mava.app/ticket-bot , https://www.mava.app/blog/how-to-integrate-zendesk-with-discord

### Assignment
- Mava centers assignment in the shared inbox and platform automations. It also supports unlimited seats on all plans. Sources: https://www.mava.app/ , https://www.mava.app/pricing

### Transcript/Audit
- Mava offers analytics, ticket and user attributes, support metrics, CSAT, AI training sources, and automations. Its audit model is richer than simple transcript files, but it is still support-platform oriented rather than Discord moderation-case oriented. Sources: https://www.mava.app/ , https://www.mava.app/pricing

### Moderation Integration
- I did not find warn/ban tracking or Discord moderation-case integration. Mava is clearly positioned as customer/community support rather than moderation enforcement. Sources: https://www.mava.app/ , https://www.mava.app/ticket-bot

### Pricing
- Starter: `$0` for `100 support requests/month`. Paid tiers are `$99`, `$199`, and `$599` per workspace monthly, with annual discounts. Sources: https://www.mava.app/pricing

### Limitations & User Complaints
- It is materially more expensive than server-specific ticket bots once ticket volume grows. Source: https://www.mava.app/pricing
- Mava's own Zendesk comparison article says adopting Mava as the "native integration" path effectively means switching away from Zendesk to Mava's suite. Source: https://www.mava.app/blog/how-to-integrate-zendesk-with-discord
- The product is optimized for community/customer support, not moderation-case management. Sources: https://www.mava.app/ , https://www.mava.app/ticket-bot

## Discord Connect for Zendesk (Oapps)

### Ticket Workflow
- Oapps turns Discord discussion threads into Zendesk tickets. The official workflow is: `@mention` the bot for a public comment, use `/help` to create a private thread, receive that message as a Zendesk ticket, then reply via Zendesk. Source: https://oapps.io/products/zendesk/discord

### Categorization
- Ticket creation can be customized through tags, subject prefixes, separate views, and routing based on tags inside Zendesk. Sources: https://oapps.io/products/zendesk/discord

### Assignment
- Assignment is effectively Zendesk-native rather than Discord-native: routing and views live in Zendesk, not in Discord channel claims. Source: https://oapps.io/products/zendesk/discord

### Transcript/Audit
- The integration syncs Discord-originated conversations into Zendesk tickets. Existing Discord history is left untouched; it starts creating Zendesk tickets from new messages after integration. Source: https://oapps.io/products/zendesk/discord

### Moderation Integration
- None found. This is a help-desk bridge, not a moderation case system. Source: https://oapps.io/products/zendesk/discord

### Pricing
- Standard is `$49/month`; Enterprise is `$99/month`. Both tiers include private threads, public threads, unlimited messages, unlimited agents, and unlimited server connections. Source: https://oapps.io/products/zendesk/discord

### Limitations & User Complaints
- Oapps says proactive messaging from Zendesk to Discord clients is not available yet. Source: https://oapps.io/products/zendesk/discord
- A Mava comparison article argues that command-based intake and limited triaging are weaker than chatbot/form-first flows. That is competitor analysis, not Oapps' own statement, but it matches the more minimal workflow described on the Oapps page. Source: https://www.mava.app/blog/how-to-integrate-zendesk-with-discord

## DiscoDesk (Freshdesk)

### Ticket Workflow
- DiscoDesk is not a ticket bot. It maps a Freshdesk Group to a Discord channel webhook and posts Discord notifications when tickets are created or assigned to that group in Freshdesk. Source: https://www.freshworks.com/apps/discodesk/

### Categorization
- Categorization stays in Freshdesk Groups, with a Discord channel mapped to each target group. Source: https://www.freshworks.com/apps/discodesk/

### Assignment
- Assignment remains Freshdesk-native. The Discord side is notification delivery, not claim/assignment workflow. Source: https://www.freshworks.com/apps/discodesk/

### Transcript/Audit
- I did not find two-way transcripts, searchable Discord archives, or Discord-native audit features. The product is a lightweight notification bridge. Source: https://www.freshworks.com/apps/discodesk/

### Moderation Integration
- None found. Source: https://www.freshworks.com/apps/discodesk/

### Pricing
- The Freshworks Marketplace lists DiscoDesk as `Free`. Source: https://www.freshworks.com/apps/discodesk/

### Limitations & User Complaints
- The marketplace description is explicitly lightweight and notification-oriented; it does not create private Discord-native ticket threads or let users open tickets from Discord. Source: https://www.freshworks.com/apps/discodesk/
- The marketplace rating was low at scrape time: `2.1/5` from `7` ratings. Source: https://www.freshworks.com/apps/discodesk/

## Gap Analysis

- Inference: no reviewed product does per-category configurable state machines well. The dominant pattern is fixed action sets like `open`, `claim`, `hold`, `move`, `close`, `delete`, and maybe `feedback`, but not admin-defined states with typed transitions. This is visible in Ticket Tool, Discord Tickets, SCNX, and Modmail docs. Sources: https://docs.tickettool.xyz/general/commands , https://discordtickets.app/commands/ , https://docs.scnx.xyz/it/docs/support-bot/feature-comparison/ , https://docs.modmail.dev/

- Scope-based assignment is mostly absent. Tools assign by support role, claimer, Freshdesk group, or shared inbox, but I did not find a strong concept of chapter-level vs server-level queues with inherited scope rules. Sources: https://docs.tickettool.xyz/dashboard/panel-configs/claiming-options , https://discordtickets.app/configuration/categories/ , https://docs.scnx.xyz/it/docs/support-bot/feature-comparison/ , https://www.mava.app/

- Audit is still transcript-first, not action-stream first. Even the better systems emphasize transcript files, searchable logs, analytics, or ticket histories; they generally do not expose a typed, append-only case action stream where every assignment, status change, escalation, and resolution reason is a first-class audited event. ticket.pm deepens transcript storage/search, but still at the transcript layer. Sources: https://docs.tickettool.xyz/dashboard/panel-configs/transcript-options , https://docs.modmail.dev/ , https://ticket.pm/ , https://www.mava.app/

- Integration with broader case management is weak. Some tools can start from moderation-adjacent inputs like message reports or ban-appeal categories, and SCNX/Modmail add blocklists, but I did not find first-party warn/ban tracking, shared actor history, or a unified support-plus-moderation case chain. Sources: https://discordtickets.app/commands/ , https://docs.scnx.xyz/docs/modmail/basics/ , https://docs.modmail.dev/

- Mandatory resolution reasons are rare. SCNX's comparison shows close reasons for Modmail but not the Ticket System; Ticket Tool, Helper.gg, and Discord Tickets expose optional reasons, not mandatory policy gates. I did not find strong evidence of "cannot resolve without reason" enforcement. Sources: https://docs.scnx.xyz/it/docs/support-bot/feature-comparison/ , https://helper.gg/features , https://docs.tickettool.xyz/general/commands , https://discordtickets.app/commands/

- Cross-ticket pattern detection is still shallow. Mava and SCNX offer analytics and AI summaries; Discord Tickets offers stats; Modmail offers searchable logs. None of the reviewed systems clearly advertises first-class pattern detection across tickets, users, or moderators in the way a real case-management system would need for abuse rings, repeat offenders, or systemic support failures. Sources: https://www.mava.app/ , https://docs.scnx.xyz/it/docs/support-bot/feature-comparison/ , https://github.com/discord-tickets/bot , https://docs.modmail.dev/

- The market splits into three clusters:
  - Discord-native hosted bots: Ticket Tool, Helper.gg, SCNX.
  - Open/self-hosted infrastructure: Discord Tickets, Modmail.
  - Support-platform or transcript-adjacent tooling: Mava, Oapps/Zendesk, DiscoDesk/Freshdesk, ticket.pm.

- Product opportunity for Humility:
  - Discord-native intake UX plus a real case object.
  - Per-category state machines instead of fixed open/close flows.
  - Scope-aware assignment across chapter/server boundaries.
  - Typed action stream tied into the audit chain, not just transcript export.
  - Mandatory resolution reasons and richer closure policy.
  - Cross-ticket and cross-case pattern detection across support and moderation.
