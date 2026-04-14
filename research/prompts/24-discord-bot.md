# Research: Discord Bot Module

## Objective

Research the problem space for the initial Discord bot module at
`services/discord/app/core/bot.py`.

## Context

This module lives in the Discord daemon service of a monorepo for
Discord server management (Humility guild). The bot is the gateway
adapter translating Discord interactions into API calls or direct DB
writes.

The module must support this construction pattern (used in smoke tests):
```python
from app.core.bot import HumilityBot
from app.core.settings import Settings

settings = Settings(
    discord_bot_token="test",
    discord_guild_id=1,
    supabase_db_url="postgresql://test",
)
bot = HumilityBot(settings)
assert bot.settings.discord_guild_id == 1
```

This must work without any network side effects (no gateway connection).

## Research Questions

1. **discord.py Bot class hierarchy**: What's the difference between
   `discord.Client`, `discord.Bot`, and `commands.Bot`? Which is
   appropriate for a minimal gateway adapter?

2. **Intents configuration**: What intents does the Humility bot need?
   Members, message content, presences? How are they configured?

3. **Command tree and slash commands**: How does discord.py 2.x handle
   slash command registration? `CommandTree`? Guild-specific vs global?

4. **Settings injection**: How should the bot receive settings? Constructor
   parameter? What pattern does discord.py use for custom state?

5. **No side effects on construction**: How to ensure creating the bot
   object doesn't trigger gateway connection? Just avoid calling
   `start()` or `run()`?

6. **Existing daemon patterns**: What does the existing `daemon/` code
   use? (`daemon/__main__.py`, `daemon/config.py`)

## Output

Write your findings to `research/24-discord-bot.md`. Document each
question with evidence. Do NOT propose solutions.

## Rules

- Do your own research — do not delegate
- Do NOT propose implementations or designs
- Reference existing code in the project where relevant
- Output must be a standalone markdown report
