# Synthesized Needs: Discord CLI Tool

## Context
The user is bootstrapping a bot-backed interface to inspect and manage the Humility guild (ID `<guild id>`). The server has several bots, broken integrations (notably `support`), templates, and roles. HumilityTicketBot is a custom-named bot (likely Tickets/ticketsbot.net). The user chose Python and wants a local CLI tool — not a persistent daemon.

## Mapping Research to Humility's Needs

### 1. `overview` — Guild Health Check
**Need**: Quick snapshot of guild state to verify bot connectivity and get baseline numbers.
**Research confirms**: Guild metadata (name, id, owner, member count, channel count, role count, boost level, creation date) is available via cache after `on_ready()` with `Intents.guilds`. Owner fetch may need `Guild.fetch_member()`.
**Gap**: None. Straightforward cache read.

### 2. `bots` — Bot Inventory
**Need**: The server has "several bots" and the user needs to understand what's running. HumilityTicketBot needs identification.
**Research confirms**: Bot enumeration requires `Intents.members` (privileged). Filter `Guild.members` by `Member.bot == True`. Each bot's name, ID, roles, and join date are available.
**Gap**: None. Standard member filtering.

### 3. `channels` — Server Structure
**Need**: Understanding the channel layout for a server with templates and organizational structure.
**Research confirms**: `Guild.channels` provides the full channel tree. `by_category()` gives hierarchical grouping. Threads are a separate collection. Channel type discrimination (text, voice, category, forum, stage) is available.
**Gap**: None. Cache-based with `Intents.guilds`.

### 4. `find-channel` — Targeted Channel Lookup
**Need**: User mentioned looking for "support" specifically (broken integration). Quick name-based search is needed.
**Research confirms**: No native name-lookup API — must scan `Guild.channels` + `Guild.threads` by substring match. Names are not unique; multiple results possible.
**Gap**: None. Collection scan with substring match.

### 5. `read` — Message History Inspection
**Need**: Admin chat contains commands previously run; user needs to read channel history to understand past actions and bot documentation.
**Research confirms**: `abc.Messageable.history()` with `read_message_history` permission. The `message_content` intent is NOT required for HTTP history fetches per the docs. Limit parameter controls how many messages to fetch.
**Gap**: Channel resolution — need to accept channel by name or ID, then resolve to a Messageable object.

### 6. `integrations` — Broken Integration Diagnosis
**Need**: The `support` integration is broken. User needs to see all integrations and their state.
**Research confirms**: `Guild.integrations()` requires `manage_guild` permission. Returns `Integration` objects with `type`, `enabled`, `account`, and `user` fields. The `enabled` field is the closest proxy for "broken" state.
**Gap**: The `enabled` field may not fully capture "broken" state. A disabled integration vs a misconfigured one may look the same. The user will need to interpret the output.

## Open Questions (Answered)
1. **Do we need `message_content` intent?** Research says no for `history()` — it's an HTTP fetch, not a gateway event. Keep it enabled anyway since the user already enabled it in the Developer Portal and it may be useful later.
2. **Should `find-channel` search threads too?** Yes — threads are separate from `Guild.channels` and a support thread could exist.
3. **Should `read` accept channel names or just IDs?** Names are more ergonomic for CLI use. Accept both — try int parse first (ID), fall back to name search.

## Priority Order
For the immediate use case (inspecting Humility):
1. `overview` — verify connectivity
2. `bots` — identify what's running
3. `channels` — understand structure
4. `integrations` — diagnose broken support
5. `read` — inspect admin chat history
6. `find-channel` — convenience helper

All six should ship in the initial CLI since they're all needed for the inspection workflow.
