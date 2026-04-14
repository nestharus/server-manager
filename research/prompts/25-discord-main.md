# Research prompt — Discord service package entry point (`app/__main__.py`)

YOU are the researcher. YOU do the research yourself. Do NOT delegate
to sub-agents or launch subprocesses.

## Task

Research the design space for a Discord service package entry point
(`services/discord/app/__main__.py`) that allows running the service
with `cd services/discord && uv run python -m app`.

## Context

The Humility Discord server management project has a three-service
architecture (API, Discord daemon, Web frontend). The Discord service
already has:

- `app/core/settings.py` — `Settings(BaseSettings)` with
  `discord_bot_token`, `discord_guild_id`, `supabase_db_url`
- `app/core/bot.py` — `HumilityBot(commands.Bot)` with settings
  injection, configured intents (members=True, message_content=True,
  presences=False)

The `__main__.py` should be the minimal entry point that:
1. Loads settings from environment variables
2. Constructs the HumilityBot
3. Wires clean shutdown (SIGINT, SIGTERM)
4. Starts the bot gateway connection
5. Uses `logging` for structured output

## Research questions

1. What is the standard pattern for `__main__.py` in Python packages
   that run as daemons? How does `python -m app` invoke it?
2. How does discord.py handle bot startup (`bot.start()` vs
   `bot.run()`)? Which is appropriate for a `__main__.py` entry point?
3. What are the correct signal handling patterns for graceful shutdown
   of a discord.py bot? How do you handle SIGINT and SIGTERM properly?
4. How should logging be configured at the entry point level for a
   discord.py daemon?
5. What error handling is needed at the entry point? (token validation,
   connection failures, etc.)

## Deliverables

Write your findings to `research/25-discord-main.md`. Include:
- Standard `__main__.py` patterns for Python package entry points
- discord.py startup/shutdown lifecycle
- Signal handling best practices
- Logging configuration at entry point
- Error handling requirements
- Relevant discord.py API references

## Rules

- Do NOT propose solutions or write code
- Do NOT modify any files other than `research/25-discord-main.md`
- Do NOT inspect the live Discord server
- Output only the research report
