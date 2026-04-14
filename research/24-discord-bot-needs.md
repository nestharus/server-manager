# Synthesis: Discord Bot Module Needs for Humility

## Context Mapping

### 1. Bot class: commands.Bot

The bot should use `discord.ext.commands.Bot` (not `discord.Client`)
because it needs slash command registration via `CommandTree`. This
is what the existing `daemon/__main__.py` already uses.

### 2. Intents

For Humility's needs (applications, tickets, moderation):
- `default()` intents (includes guilds)
- `members = True` (member management, role changes)
- `message_content = True` (reading message content for moderation)
- `presences = False` (not needed)

### 3. Settings injection

`HumilityBot` takes `Settings` in the constructor and stores it as
`self.settings`. This allows `bot.settings.discord_guild_id` access
without network side effects.

### 4. No side effects on construction

`discord.ext.commands.Bot.__init__()` does NOT connect to the gateway.
Only `start()` or `run()` triggers connection. So construction is safe.

### 5. Minimal initial module

The bot module should only define the class with settings injection
and intents. Slash commands, event handlers, and gateway logic will
be added in later partitions.

## Gaps

None. The research covers the class hierarchy, intents, and
construction safety.
