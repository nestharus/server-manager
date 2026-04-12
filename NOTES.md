# NOTES.md — agent-maintained log of discovered facts

Last updated: 2026-04-11

## Guild

- **Name:** Humility
- **ID:** `900000000000000001`
- **Owner:** `nestharus` (user id `900000000000000002`)
- **Created:** 2022-04-04
- **Members:** ~83
- **Features:** Community, Onboarding, AutoMod, News, Server Guide, Premium Tier 1
- **Nature:** originally planned as a multi-chapter community server. The
  "chapter" infrastructure is scaffolded (roles + GUILD TEMPLATE category)
  but **no chapters have actually been populated yet** — the template
  channels are empty and no chapter-specific categories exist.

## Channel layout (summary)

- **▬▬ Account Setup ▬▬**: `#🔐︱verification` (960634531679969290) — Captcha.bot panel
- **▬▬ Welcome & Info ▬▬**: `#🎇︱rules`, `#🪧︱welcome`, `#📗︱support` (960634531679969297), `#💡︱server-suggestions` (forum)
- **▬▬ Community ▬▬**: `#➕ Create Lobby` (voice), `#📣︱announcements` (news), `#💬︱general`, `#💬︱other-games`, `#💬︱art`, `#💬︱news`, `#💬︱off-topic`
- **▬▬ Staff ▬▬**: staff vc, punishment-book, staff-chat, scripts, moderation-commands, mod-logs, spam-logs, `ticket-logs` (960634532653060140), `panels` (960634532653060141), `templates` (960634532653060142)
- **▬▬ Admin ▬▬**: Admin vc, `admin-chat` (960634532653060145), discord-updates
- **▬▬ GUILD TEMPLATE ▬▬** (category id `960634532103610429`): create lobby (voice), create guild lobby (voice), guild-war (voice), events, guides, lobby, guild-lobby, officer-lobby, applications — **all text channels empty**.
- **▬▬ AFK ▬▬**: 🕑 AFK (voice)

## Role hierarchy (top → bottom)

| Pos | Name | Notes |
|---|---|---|
| 35 | ⚔️ Administrator | |
| 34 | ⚔️ Moderator | |
| 33 | ⚔️ Staff | broad perms |
| 32 | ⚔️ Trial Mod | hoisted |
| 31 | **Robots** (#1) | perms container for bots; NOT hoisted; id `960634531243765793` |
| 30 | Chapter Officer | id `960634531210223668` |
| 29 | Chapter Member | purple `#9b59b6` |
| 28 | Chapter Guild War | |
| 27 | Chapter Applicant | |
| 26 | Chapter | |
| 25 | Chapter Public | visible by outsiders |
| 24 | Member | hoisted |
| 23 | Guest | |
| 22–18 | Language EN/POR/JP/ES/THAI | |
| 17 | Owner | hoisted, admin=true |
| 16 | Server Booster | managed |
| 15 | Muted | applied via overwrites |
| 14–3 | (bot managed roles) | Captcha.bot, AmariBot, HumilityTicketBot, Apollo, Gather, Zira, Hydra, D29 nestharus, Midjourney, Sx Bot |
| 4 | **Robots** (#2) | hoisted separator, permissions=0; id `1187590260390109304` |
| 1 | server-manager | (us, managed) |
| 0 | @everyone | |

**Two "Robots" roles are intentional**, not a bug:
- #1 (pos 31) = permissions container (grants bots the access they need)
- #2 (pos 4) = hoisted separator for the member sidebar

All bots are members of both. Confusing but functional — leave alone.

## Chapter system (as inferred)

- A **chapter** is a sub-community. One set of `Chapter*` roles currently
  exists (not per-chapter). GUILD TEMPLATE category is the structural
  blueprint for chapter channels.
- Role flow appears to be: `Guest` → (chapter application) → `Chapter Applicant` → `Chapter Member` (purple). Leadership: `Chapter Officer`.
- `Chapter Public` = outsider-visible chapter-facing content (e.g. events).
- **Current chapter count: 0.** The template has never been cloned.
- **Open question:** when a chapter is created, do new chapter-specific
  roles get created (e.g. "Dawn Chapter Member"), or does everyone use
  the shared `Chapter Member` role? Needs user clarification.

## Bots (integrations) — consolidated

| Bot | App ID | Role pos | Activity (last 2000 msgs/channel) | Recommendation |
|---|---|---|---|---|
| Captcha.bot | `512333785338216465` | 14 | Active in #verification | **Keep** |
| AmariBot | `339254240012664832` | 13 | Leveling, no message footprint (normal) | Keep |
| **HumilityTicketBot** (ticketsbot.net) | `954933581501849610` | 11 | Dead: **service discontinued 2025-03-05**. panel.ticketsbot.net 404. Last real activity: 3 test tickets by owner. | **Remove later** — replace with alternative ticket bot (Tickety, Helper.gg, Modmail, or custom). Defer. |
| Apollo | `475744554910351370` | 10 | **0 messages**. Never used. | **Remove** (pending owner confirm) |
| Gather | `868195275464900618` | 9 | **0 messages** in all text channels. Installed but never posted. | **Keep for now** — used for the pending chapter-application workflow; decision pending replacement sketch. |
| Zira | `275813801792634880` | 8 | 15 setup msgs in admin-chat (2022) + 2 premium embeds (2023). Silent operation since — normal for reaction-role bots. | **Keep** — owner confirms "forms"/reaction-role use. |
| Hydra | `547905866255433758` | 7 | **0 messages**. Owner: "I don't know what we use hydra for." | **Remove** (pending owner confirm) |
| D29 nestharus (Auto Voice Channels) | `954482612980826172` | 6 | Powers `➕ Create Lobby` voice channels. No text footprint (normal). | Keep |
| Midjourney | `936929561302675456` | 5 | No text scan hits; invoked on demand. | Keep (user decision) |
| Sx Bot | `696870234262339614` | 3 | No text footprint visible; Twitch/emote features. | Keep (user decision) |
| sesh | `616754792965865495` | — | 2 messages, both "Sesh Premium" promos 2023-12-22. Effectively unused. | **Remove** (overlaps with Apollo; both effectively unused) |
| server-manager | `1492535248825745558` | 1 | this repo | Keep |

**Caveat:** "0 messages in channels" ≠ "completely unused." Bots can have
silent roles (auto-assignments, welcome DMs, web dashboard configs).
Before removing any bot:
1. Check the bot's web dashboard if one exists (hydra.bot, gather.sh, etc.)
2. Confirm the owner has no recollection of depending on it
3. Remove via Server Settings → Integrations (not by kicking the bot's
   member record — integrations and member records are different).

## HumilityTicketBot / ticketsbot.net

- Service discontinued 2025-03-05 per https://ticketsbot.net homepage.
- `panel.ticketsbot.net` returns 404.
- Alternative dashboard mentioned: `dashboard.ticketsbot.net` (may or may
  not still serve anything useful post-EOL).
- Data export tool: https://export.ticketsbot.net (may still be live, for
  downloading old ticket transcripts).
- Replacement options to evaluate later: **Tickety**, **Helper.gg**,
  **Modmail**, or build a custom ticket flow inside `server-manager`.
- Your current open/closed ticket history is likely stuck inside the
  ticketsbot.net backend. Only 3 historical tickets existed (all test
  tickets by owner), so there's nothing material to migrate.

## Things not yet investigated

- Exact Gather form configuration (lives on gather.sh; requires owner to
  log in via Discord OAuth).
- Whether there are any guild/category-level automations set on hydra.bot
  or gather.sh dashboards that silently affect join flow.
- Permission audit of per-channel overwrites across the whole server.
- Full content of `#server-suggestions` forum (forum-type, need dedicated
  subcommand to list threads).
