# Permission & Role Management — Research Findings

This scan focuses on Discord bots and dashboards that touch permissions, roles, security, auditability, and server-state management. A recurring pattern is that most products are strong in one lane only:

- security bots focus on raid/nuke prevention
- logging bots focus on event visibility
- role bots focus on assignment automation
- backup tools focus on restore/sync

I did not find a mature product that unifies permissions, audit, and configuration governance as a single control plane.

Discord itself remains the hard platform boundary: roles are hierarchical, channel permissions are override-based, and audit logs store administrative actions for 45 days. Every reviewed bot sits on top of that model rather than replacing it.

Platform sources:
- https://support.discord.com/hc/en-us/articles/214836687-Discord-Roles-and-Permissions
- https://docs.discord.com/developers/resources/audit-log

## Security Bots

### Wick
#### Permission Management
- Wick exposes bot-specific moderator authorities such as `Wick Ban`, `Wick Quarantine`, and `Wick Verify`, alongside server-owner buckets like `Extra Owners` and `Trusted Admins`.
- Setup also centers on protected role sets such as `Main Roles` and a `Quarantine Role`.
- This is more granular than raw Discord `Administrator`, but it is still role/command-based. I found no public evidence of per-scope authority grants where an operation is allowed only on a specific object scope.

#### Security Features
- Anti-Nuke watches dangerous channel, role, ban, and webhook activity.
- Panic Mode can lock the server down during an attack.
- Verification and Join Gate screen new members by signals like account age, avatar presence, and bot status.
- Quarantine and Quarantine Hold are designed to contain dangerous users and protect sensitive roles.
- Wick also documents regular server imaging/backups for recovery scenarios.

#### Audit/Logging
- Wick logs moderation actions like bans, quarantines, and verifies into `#wick-logs`, `#modlogs`, and Discord audit logs.
- Docs also describe anti-nuke and restore-related logging around destructive changes.

#### Configuration Management
- Wick uses a setup wizard and dashboard-style configuration across Anti-Nuke, Auto Mod, Join Gate, Verification, and Quarantine Hold.
- Imaging/backups are the closest thing to configuration safety, but I found no public evidence of versioned policy changes, preview-confirm flows, or drift detection between intended policy and live Discord state.

#### Role Management
- Verification grants roles after a user passes checks.
- Quarantine uses a dedicated restrictive role.
- Protected role groups are central to Wick's safety model.

#### Pricing
- Free tier plus Premium.
- The public premium page in this scrape did not expose a numeric price.

#### Limitations & User Complaints
- Reddit search snippets show complaints about false positives from account-age or alt-detection style checks causing legitimate users to be rejected.
- Recovery value depends on backups/imaging being enabled ahead of time.
- Public docs do not show policy diffs, change previews, or config reconciliation.

Sources:
- https://docs.wickbot.com/intro/features/
- https://docs.wickbot.com/setup/
- https://docs.wickbot.com/commands/moderation/ban/
- https://docs.wickbot.com/commands/moderation/quarantine/
- https://docs.wickbot.com/commands/moderation/verify/
- https://wickbot.com/premium
- https://www.reddit.com/r/discordapp/comments/159ipgv/why_am_i_being_rejected_by_pretty_much_every/

### Security Bot
#### Permission Management
- Security Bot is the closest reviewed product to a delegated authority system. Its docs say users can act through Security's custom permissions even without the corresponding native Discord permissions.
- Docs also say those users cannot bypass Anti-Nuke limits and can only use specifically granted commands.
- Security Bot separately treats granting dangerous permissions such as `Administrator`, `Manage Roles`, `Manage Channels`, `Manage Webhooks`, `Ban Members`, and `Kick Members` as monitored events.
- This is still command-grant oriented, not a scope-intersection model tied to specific resources.

#### Security Features
- Anti-Nuke monitors dangerous actions with configurable thresholds and punishments.
- Premium adds advanced anti-nuke, spam detection, automatic recovery, whitelisting, and higher operational limits.
- Whitelisting exempts specific entities from Anti-Nuke monitoring.

#### Audit/Logging
- Dangerous permission grants can be logged when logging is enabled.
- Docs emphasize incident detection and punishments more than deep historical search or cross-incident investigation.

#### Configuration Management
- The dashboard exposes current Anti-Nuke configuration, action triggers, limits, and punishments.
- I found no public evidence of versioned configuration, preview-confirm rollout, or optimistic concurrency controls on dashboard changes.

#### Role Management
- Security Bot is not primarily a role-menu product.
- Its role handling is mainly around whitelists and command authority, not large-scale self-assignable role UX.

#### Pricing
- `Security Premium`: $3.49/month.
- `Security Premium+`: $11.99/month.

#### Limitations & User Complaints
- Based on the docs, the model is threshold-heavy and whitelist-heavy, so bad tuning can create blind spots. This is an inference from the product design, not a quoted vendor limitation.
- I found far less community complaint volume than for Wick/Dyno/Carl-bot; the product appears more specialized and less discussed.
- Public docs do not show config diffing, rollback history, or reconciliation between intended and actual Discord permissions.

Sources:
- https://docs.securitybot.gg/anti-nuke/anti-nuke
- https://docs.securitybot.gg/anti-nuke/anti-nuke/dangerous-permissions
- https://docs.securitybot.gg/other-modules/moderation
- https://securitybot.gg/premium
- https://www.reddit.com/r/discordbots/comments/yv54v7/security_bot_features/

### Double Counter
#### Permission Management
- Double Counter is centered on onboarding verification rather than broad server governance.
- Dashboard access requires the server owner or a role with `Admin`/`Manage Server`.
- It uses a `verified role`, `unverified role`, `staff role`, and optional ping role for incident handling and manual verification.
- This is scoped to entry/verification flow, not general permission governance across channels, roles, and operations.

#### Security Features
- Core positioning is anti-alt, anti-VPN, anti-bot, and anti-raid protection.
- Docs describe invisible captcha, cross-database checks, automated alerts, device/fingerprint-based detection, minimum account age rules, and optional staff-assisted verification.
- Pro marketing adds deeper member detail and right-click contextual security actions.

#### Audit/Logging
- Docs expose successful verification logs, alerting, and detailed member information in Pro.
- Pro marketing emphasizes fingerprint-driven logs and member detail rather than broad operational audit of admin changes.

#### Configuration Management
- All configuration is dashboard-based; setup commands are documented as non-functional.
- Settings include verification mode, minimum account age, VPN-only blocking, DM requirements, staff role, log-success toggles, and integrations like InviteLogger.
- I found no public evidence of version history, approval workflows, or declared-intent-versus-actual-state reconciliation.

#### Role Management
- Verified/unverified roles drive access control after member screening.
- Staff role grants manual verification and related support actions without broad server staff elevation.

#### Pricing
- Free base bot.
- Paid Pro exists and is sold through Discord.
- The public pages scraped did not expose a numeric Pro price.

#### Limitations & User Complaints
- Community snippets raise privacy concerns about aggressive fingerprinting and device-style checks.
- Community snippets also report VPN/shared-network false positives.
- The public site notes ads on verification pages unless you upgrade to Pro.

Sources:
- https://doublecounter.gg/
- https://doublecounter.gg/features-and-settings/
- https://doublecounter.gg/double-counter-pro/
- https://docs.doublecounter.gg/
- https://docs.doublecounter.gg/double-counter-en/setup
- https://docs.doublecounter.gg/double-counter-en/configuration-cont.
- https://docs.doublecounter.gg/double-counter-en/pro-version
- https://www.reddit.com/r/discordapp/comments/16z0as5/double_counter_advice/
- https://www.reddit.com/r/privacy/comments/1npitp1/this_popular_discord_bot_is_a_privacy_nightmare/
- https://www.reddit.com/r/discordapp/comments/1lu99md/isnt_this_a_privacy_invasion/

## Logging/Audit Bots

### Dyno
#### Permission Management
- Dyno's governance model is mostly standard Discord administration plus a web dashboard.
- Dyno logs are created when a user with `Administrator` changes a bot setting in the dashboard.
- I found no separate first-class authority system for scoping actions by resource; the product relies on Discord role order and dashboard access.

#### Security Features
- Dyno is a general moderation bot with anti-spam and automod features, but it is not positioned as a deep anti-nuke or permission-governance system.
- Premium adds advanced automod and operational extras like autopurge and slower-channel tooling.

#### Audit/Logging
- Dashboard logs record settings changes with time, user ID, and change details.
- Moderation logs track case number, action, and target user.
- Automod logs record filter hits.
- Command logs record command usage and message content.
- Action Log can capture message deletes/edits, bulk deletes, invites, joins/leaves, role adds/removals, timeouts, bans, role create/delete/update, channel create/update/delete, and voice movement.

#### Configuration Management
- Dyno has useful bot-settings logging in the dashboard, but this is still operational history, not policy versioning.
- I found no public evidence of preview-confirm workflows, config rollback semantics, or drift detection between intended settings and live Discord state.

#### Role Management
- Dyno supports autoroles and joinable ranks.
- Non-premium servers can have at most three autoroles.
- Timed autoroles exist, with longer delay limits on premium.

#### Pricing
- `Standard`: $5.99/month.
- `Premium`: $7.99/month.
- `Custom`: $12.99/month.

#### Limitations & User Complaints
- Deleted-message visibility depends on cache depth: 10 messages per channel on free, 100 on premium.
- Dyno docs say deleted messages beyond cache are not logged, and bot-authored deleted messages are not logged.
- Community threads frequently surface role-hierarchy misconfiguration as the reason autoroles or reaction-style role flows fail.

Sources:
- https://dyno.gg/premium
- https://docs.dyno.gg/en/dashboard/logs
- https://docs.dyno.gg/modules/actionlog
- https://docs.dyno.gg/modules/autoroles
- https://www.reddit.com/r/Dynodiscord/comments/gzc185/autorole_not_working_with_new_members/
- https://www.reddit.com/r/Dynodiscord/comments/lxzcgt/reaction_roles_module_not_working/

### Carl-bot
#### Permission Management
- Carl-bot advertises a granular permission system with per-command rules, global rules, output redirection, muted output, and bulk command management on the website.
- That is more governance-aware than most general-purpose bots, but it is still command-rule based, not scope-grant based.

#### Security Features
- Automod supports rule-specific punishments for spam, links, attachments, mentions, and bad words.
- Roles and channels can be whitelisted to bypass specific automod rules.
- Moderation features include sticky roles, drama channels, bulk role management, and infraction history.

#### Audit/Logging
- Carl-bot logs deleted, edited, and purged messages; invite links; joins/leaves; role, nickname, and avatar changes; bans/unbans; and server updates to channels, roles, and emojis.
- Logs can be split across multiple channels to reduce clutter.
- Modlogs include moderator responsibility and past infractions.

#### Configuration Management
- Carl-bot has a strong browser dashboard for command permissions, automod, logging, autoroles, sticky roles, welcome/farewell flows, starboard, and custom commands.
- I found no public evidence of policy versioning, config diff previews, or safety controls like optimistic concurrency on dashboard edits.

#### Role Management
- One of the strongest role-management products in the scan.
- Reaction roles support modes like unique, verify, reversed, binding, and temporary.
- Carl-bot supports whitelist/blacklist role gating for who can pick up what role.
- It also supports autoroles, delayed autoroles, sticky roles, timed reaction roles, and bulk role management.

#### Pricing
- Premium is sold on Patreon and through Discord.
- The scraped public premium page exposed features but not a numeric price.

#### Limitations & User Complaints
- Carl-bot still inherits Discord permission and hierarchy friction; reaction roles fail if the bot cannot manage the target role or lacks channel permissions.
- Community snippets include complaints about outages/support quality and general frustration with the bot's UX.
- Despite strong role tooling, I found no evidence of reconciliation between intended role policy and actual live Discord state.

Sources:
- https://carl.gg/
- https://carl.gg/about
- https://carl.gg/get-premium
- https://www.patreon.com/carlbot/membership?l=fr
- https://www.reddit.com/r/Discord_Bots/comments/1dz6xdg/carl_bot_reaction_roles_not_working/
- https://www.reddit.com/r/discordapp/comments/1izj5k2/am_i_not_understanding_whats_going_on_or_are/
- https://www.reddit.com/r/discordapp/comments/z4fan1/stop_suggesting_carl_bot_and_yagpdb_as/

### Quark Logger
#### Permission Management
- Quark is primarily an observability product.
- It logs role audits and permission changes, but I did not find a first-class delegated authority or role-governance model for deciding who may perform which action.

#### Security Features
- Quark is strongest as a forensics and accountability layer, not as a prevention product.
- It can surface bot actions, role changes, channel operations, voice moderation changes, and mod actions with reason fields.

#### Audit/Logging
- Strong logging coverage: bans, kicks, timeouts, moderator identity and reason, nickname changes, role updates, role permission changes, channel creates/deletes/updates, message logging, and voice mute/deafen tracking.
- Paid tiers add longer message-history logging and more advanced bot/action visibility.

#### Configuration Management
- Quark supports customizable log format, color, per-log-type channels, and dashboard-based setup.
- Subscriptions increase retention and logging limits.
- I found no evidence of policy versioning or change-approval workflows; it is a logging plane rather than a governance plane.

#### Role Management
- Quark is not a role assignment product.
- Its role support is audit-centric, especially around role updates and permission changes.

#### Pricing
- Free tier.
- `Quark Pro Lite`: $30/year.
- `Quark Pro`: $60/year.

#### Limitations & User Complaints
- Logging depth and retention are materially gated by paid tiers.
- The product improves observability, but not prevention or permission-safe change management.
- I did not find notable complaint volume in quick community searches; the more obvious limitation is scope, not quality.

Sources:
- https://quark.bot/
- https://docs.quark.bot/subscriptions/overview
- https://quark.bot/pro

## Role Management Bots

Carl-bot and Dyno both have meaningful role-management capability, but I kept their full writeups in the logging/audit section because that is where they are more differentiated. YAGPDB is the clearest role-first bot in this scan.

### YAGPDB
#### Permission Management
- YAGPDB is heavily Discord-native in its permission model.
- Role menu commands require `MANAGE_GUILD`, and the bot must have `Manage Roles` with its top role above the target role.
- This gives admins a lot of flexibility, but it is not a scoped governance system.

#### Security Features
- YAGPDB is not mainly a security bot.
- Its most governance-relevant security feature is that autorole can wait for Discord Membership Screening before assigning a role.

#### Audit/Logging
- YAGPDB's logging is on-demand rather than continuous comprehensive audit.
- It captures recent channel history, including deleted messages from cache, and stores timestamps, user IDs, usernames, and message contents.
- Deleted messages are cached for 1 hour on free and 12 hours on premium.

#### Configuration Management
- Logs are viewed online rather than sent back into Discord channels.
- Control panel permissions decide who can view logs.
- Premium adds retroactive autorole scan/assignment and bulk role assignment/removal.
- I found no evidence of config versioning, preview-confirm, or drift detection.

#### Role Management
- YAGPDB is strong here: self-assignable roles, reaction role menus, autorole conditions, membership-screening gates, premium retroactive scan, and premium bulk role assignment/removal.
- Role menus are constrained by Discord's 20-reaction ceiling per message.

#### Pricing
- Premium is sold through Discord and Patreon.
- The scraped public premium page did not expose a numeric price.

#### Limitations & User Complaints
- Role menus are capped at 20 roles due to Discord reactions.
- Logs expire after 30 days and must be viewed on the web.
- Hierarchy and permission mistakes are a common operational constraint because the bot must sit above the roles it assigns.

Sources:
- https://help.yagpdb.xyz/docs/moderation/logging/
- https://help.yagpdb.xyz/docs/roles/self-assignable-roles/
- https://help.yagpdb.xyz/docs/roles/autorole/
- https://yagpdb.xyz/premium-perks
- https://www.reddit.com/r/discordapp/comments/lb63qe/making_my_first_discord_and_would_love_advice/

## Backup / Configuration / Server State Tools

### Xenon
#### Permission Management
- Xenon is the strongest reviewed tool for server-state capture and restore.
- By default, loading a backup is restricted to the server owner, and the site/docs describe administrator-only restore flows plus a `/settings permissions` control path.
- The API docs also mention checking whether a user has permission to restore settings from a specified guild.

#### Security Features
- Xenon is a recovery tool more than a prevention tool.
- Backups are linked to the Discord account that created them, and premium adds more complete server-state recovery/synchronization features.

#### Audit/Logging
- Xenon is not a primary audit-log product.
- Its value is snapshotting, restore, cloning, and synchronization rather than a searchable operational audit chain.

#### Configuration Management
- This is Xenon's strongest area: backups, templates, cloning, synchronization, interval backups, message and ban sync, role-assignment sync, and API loader events for post-restore actions.
- Premium tiers scale backup counts, intervals, message retention in backups, thread/forum backup, member data backup, and chatlog capacity.
- Even so, I found no public evidence of declared-intent-versus-actual reconciliation, preview-confirm policy rollout, or optimistic concurrency on config changes.

#### Role Management
- Xenon can save/load role assignments and nicknames with premium.
- It can also synchronize role assignments across servers.

#### Pricing
- Free base tier.
- `Premium 1`: $5.99/month.
- `Premium 2`: $10.99/month.
- `Premium 3`: $15.99/month.

#### Limitations & User Complaints
- Xenon can only restore what was actually backed up; community snippets note that paying later does not recover already-lost messages retroactively.
- Community snippets also note that even premium recovery is not a perfect substitute for native historical restoration.
- Xenon is strong at rollback/restore, but it is not an integrated permission-governance or audit-decision system.

Sources:
- https://xenon.bot/
- https://wiki.xenon.bot/
- https://wiki.xenon.bot/premium
- https://wiki.xenon.bot/en/api
- https://www.reddit.com/r/discordbots/comments/1re9p1t/will_subscribing_to_xenon_mean_i_can_restore/
- https://www.reddit.com/r/discordapp/comments/trxxmi/server_recovery_backup_export/

## Gap Analysis

- Scoped authority grants:
  The closest products are Security Bot's custom command permissions, Carl-bot's per-command rules, and Wick's bot-specific permissions. None of them expose a grant model where authority is the intersection of actor grants and operation scope. They are still role, command, or whitelist driven.

- Permission reconciliation:
  I found no reviewed bot that models declared permission intent separately from live Discord state and then reconciles drift. Xenon and Wick can restore from saved state; that is not the same as continuous intent-versus-actual reconciliation.

- Policy versioning with preview-confirm:
  None of the reviewed products publicly expose versioned policy objects, diffs before apply, staged rollout, or explicit preview-confirm UX for permission/config changes. Most dashboards appear to apply settings directly.

- Comprehensive operational audit chain:
  Dyno, Carl-bot, Quark, and Wick all log useful events. Discord itself offers 45-day audit logs. But I did not find a tool that ties together: who authored a governance policy, who approved it, who executed it, what Discord state changed, and whether the outcome matched intent.

- Configuration drift detection:
  Xenon is strongest at backup/sync and Security Bot/Wick are strongest at recovery/protection, but none surfaced a drift detector for channel permission overrides, role grants, or admin changes that silently diverge from an intended policy baseline.

- Configuration safety / optimistic concurrency:
  I found no public evidence of compare-and-swap style config edits, revision IDs, edit conflicts, or last-known-version enforcement on dashboard changes. The likely operating model is direct mutation and last-write-wins.

- Cross-concern governance:
  The market is fragmented:
  security bots prevent raids and destructive actions
  logging bots record what happened
  role bots automate assignments
  backup tools restore state
  What is missing is a unified governance layer for permissions, audit, and configuration management as one system.

- What appears under-served for this proposal:
  A product that treats permissions as policy, not just bot settings, would be differentiated if it shipped:
  per-scope grants instead of pure rank/role gates
  declared-intent versus actual-state reconciliation
  preview-confirm and versioned policy rollout
  end-to-end decision audit, not just event logs
  optimistic concurrency on config changes
  one governance surface that spans permissions, role operations, audit, and restore/sync
