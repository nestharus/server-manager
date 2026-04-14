# Research: Discord Daemon Settings Module

## Objective

Research the problem space for a Discord daemon settings module at
`services/discord/app/core/settings.py`.

## Context

This module lives in the Discord daemon service of a monorepo for
Discord server management (Humility guild). The daemon connects to the
Discord gateway and may call the API service for mutations.

The API service already has its own settings module at
`services/api/app/core/settings.py` using pydantic-settings. The
Discord daemon shares some env vars with the API but only reads what
the daemon needs.

The settings module must support this construction pattern (used in
smoke tests):
```python
Settings(
    discord_bot_token="test",
    discord_guild_id=1,
    supabase_db_url="postgresql://test",
)
```

And expose `discord_guild_id` on the resulting object.

## Research Questions

1. **pydantic-settings for Discord bots**: What fields does a Discord
   daemon need? Bot token, guild ID, API base URL (to call the API
   service), database URL. What types and validation?

2. **Shared vs separate settings**: How should the daemon settings
   relate to the API settings? Complete duplication? Import shared
   base? Independent?

3. **Environment variable naming**: What prefix/naming conventions work
   for a multi-service monorepo sharing a single `.env` file?

4. **discord.py integration**: Does discord.py have any settings/config
   patterns? Intents configuration?

5. **Supabase connection string**: What format does `supabase_db_url`
   take? PostgreSQL connection string?

## Output

Write your findings to `research/23-discord-settings.md`. Document each
question with evidence. Do NOT propose solutions.

## Rules

- Do your own research — do not delegate
- Do NOT propose implementations or designs
- Reference existing code in the project where relevant
- Output must be a standalone markdown report
