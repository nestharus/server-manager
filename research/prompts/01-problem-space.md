# Research prompt — Discord guild management problem space

You are a research agent investigating a problem space for a
community-management project. **Document problems. Do not propose
solutions.** A separate phase will write proposals.

## Scope

Discord servers ("guilds") run by volunteer community owners and
moderators. Primary interest: **gaming communities and multi-chapter
communities** (e.g. an umbrella community with sub-divisions for
different games), ranging from 50 members to roughly 10,000 members.
Exclude: corporate / employee chat, crypto/NFT/airdrop communities,
adult/NSFW servers, Discord's own developer advocacy.

Primary personas:
- **Owner** — runs the server, makes structural decisions, pays for bots
- **Moderator / Staff** — enforces rules, handles user reports, answers questions
- **Applicant / prospective member** — wants to join a chapter, fill out an application
- **Active member** — participates in chat, events, voice
- **Chapter officer** — leader/operator of a sub-community within a larger server

## Deliverable

A structured markdown report at `research/01-problem-space.md` in this
repo. The report must contain:

### 1. Problem taxonomy (required)

Categorize the problems Discord community managers actually run into.
Suggested top-level categories (use your judgment, add/remove as the
evidence supports):

- Onboarding, verification, gating (bot checks, captchas, rules agree)
- Applications and recruitment (forms, interviews, approvals, blacklists)
- Moderation (auto-mod, reports, appeals, warnings, bans, audit trails)
- Support tickets (user → staff inquiries, claim/assignment, transcripts)
- Events and scheduling (calendars, RSVPs, reminders, timezones)
- Engagement and retention (leveling, roles, XP, custom achievements)
- Announcements and content distribution (news, role-gated DMs)
- Role management (self-assignment, hierarchy, reaction roles)
- Sub-community structure (chapters, divisions, nested categories)
- Cross-server coordination (shared staff, unified bans, federated channels)
- Spam, scam, and raid defense (token stealers, phish links, join-raids)
- Privacy, data retention, GDPR/DSR compliance
- Analytics and reporting (growth, activity, engagement metrics)
- Accessibility (screen-reader compat, color, motion, language)
- Localization / multilingual servers
- Bot sprawl and reliability (bots dying, going closed-source, being acquired)

For each category, document:

- **What the problem actually is** — not a vague summary, the specific
  user complaints
- **Who feels it** — which personas, at what scale
- **Evidence** — 3–8 concrete references per category: Reddit threads
  (r/discordapp, r/Discord_Bots, r/discordservers), Discord Feedback,
  GitHub issues on popular bots, bot store reviews, forum posts, blog
  writeups. Inline links with brief quotes.
- **Severity** — how often it shows up, how much pain it causes,
  whether workarounds exist
- **Scale effects** — how the problem changes at 50 / 500 / 5000 members

### 2. Existing solutions map (required)

For the popular Discord bots in the community space, document what
each one solves well and what it misses. Cover at minimum:

- **Carl-bot** — reaction roles, automod, logging
- **Dyno** — moderation, automod
- **MEE6** — leveling, welcome, moderation
- **Ticket Tool** — tickets
- **Tickets (tickets.bot)** — tickets, formerly ticketsbot.net
- **Modmail** — DM-based tickets
- **Application Bot** / **AppyBot** — application forms
- **Gather (gather.sh)** — application forms (NOTE: as of 2026-04, this
  service is offline)
- **Sapphire** — modern alternative
- **Zeppelin** — self-hosted moderation
- **Discord built-ins** — onboarding flow, forum channels, threads, AutoMod
- Any other major bots you find in your research

For each, produce a small matrix: **problem categories addressed /
partially addressed / missed**. Note lock-in risks, hosting model
(SaaS vs self-hosted), pricing, EOL risk (historical shutdowns count).

### 3. Platform constraints (required)

Document what Discord's API, permission model, and interaction
primitives actually let you build. Focus on:

- Slash command limits (characters, options, guild vs global scope)
- Modal constraints (5 components max, text inputs only — no selects inside modals)
- Component v2 vs v1 (buttons, selects, modals, ActionRow limits)
- Message formatting limits (embed field counts, character totals)
- Role count cap (~250 per server), channel count cap (500 per server,
  50 per category), thread limits, active thread limits
- Rate limits on messages, role mutations, channel creation
- Permission model quirks (channel overwrites, category inheritance,
  Administrator overrides, role hierarchy vs manage-roles)
- What requires Privileged Intents (members, presence, message content)
- Audit log retention (~45 days) and its implications
- Webhook capabilities and limits
- Gateway vs HTTP interactions endpoint tradeoffs
- Interactions SLA (3-second initial response, 15-minute followup)
- Private thread vs public thread semantics, thread member management
- OAuth2 scopes relevant to server management (`bot`,
  `applications.commands`, `identify`, `guilds`, `guilds.members.read`)

### 4. Multi-sub-community patterns (required)

The user operates a server with a "chapter" abstraction — sub-communities
with their own roles, channels, officers, and application flows.
Research how other multi-chapter, multi-division, or "federation" Discord
servers structure themselves:

- How do they encode sub-community membership (per-chapter roles, per-chapter categories, hybrid)?
- How do they handle chapter creation and archival?
- How do per-chapter permissions interact with server-wide staff?
- Common failure modes: role explosion, category explosion, unclaimed abandoned chapters, disputed chapter ownership
- Examples from the wild: gaming guild umbrella servers, esports orgs, MMO alliance servers, university org servers

### 5. Cross-cutting concerns (required)

- **Bot reliability and EOL risk** — history of bots shutting down,
  getting acquired and enshittified, going paid-only, or silently
  breaking (ticketsbot.net and Gather are two recent examples)
- **Data portability** — when a bot dies, what happens to the data it
  held? How do owners typically recover?
- **Hosting and cost** — at what scale do communities typically need to
  self-host vs use SaaS bots? What are the typical monthly costs?
- **Privacy and trust** — what happens when a popular bot is acquired
  by a company that changes data handling?
- **Moderation fatigue** — what burns out volunteer moderators, and
  which tooling actually helps vs makes it worse?

### 6. Open questions

Any questions the research raised that would need user input to resolve.
Do not answer them — flag them for the next phase.

## Anti-goals for this research

- **Do not propose features or solutions.** Problems only.
- **Do not design an architecture.** That's the proposal phase.
- **Do not recommend which bots this user should adopt.** Document the
  space; let the synthesizer decide.
- **Do not fall back to generic advice** ("use a good onboarding
  flow"). Cite specific evidence.
- **Do not speculate without evidence.** If the research didn't find
  evidence, say so and list what you looked at.

## Evidence quality bar

- Links must resolve — verify each before including
- Quote user/mod complaints verbatim (short quotes) when possible
- Prefer primary sources (actual users complaining) over summary articles
- Tag each evidence link with the date it was posted if visible
- When a piece of evidence is ambiguous or contradicts others, flag it

## Output format

Markdown with clear headings, nested bullets for evidence, and a short
executive summary at the top (≤ 300 words). Target length: 3000–6000
words total. Bibliographic footnotes allowed but inline links preferred.

Write the report to `research/01-problem-space.md` (this repo —
project path will be passed via the `-p` flag).
