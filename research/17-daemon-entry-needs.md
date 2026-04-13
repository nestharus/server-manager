# Synthesis: daemon.py Needs

Date: 2026-04-13

## Humility-Specific Needs

1. **Entry point**: `daemon.py` boots the bot, loads config, initializes DB, then runs the discord.py event loop indefinitely.

2. **Environment variables**: DISCORD_BOT_TOKEN (required), DISCORD_GUILD_ID (required), DATABASE_PATH (optional, defaults to discord.db).

3. **Intents**: Need members (for role checking), message_content (for future message reading), guilds. Use `discord.Intents.default()` plus members + message_content.

4. **Config loading**: Call `daemon.config.load_config()` on startup. On failure, exit with error.

5. **DB initialization**: Call `daemon.db.open_database()` on startup. 

6. **Slash command scaffolding**: Register a minimal health-check or `/ping` command to confirm the bot is working. Actual `/apply`, `/ticket` etc. come in later partitions.

7. **Graceful shutdown**: Close DB connection on shutdown.

8. **Skeleton only**: No applications, tickets, provisioning. Just boot → config → db → gateway → wait.

## Gaps
None. The scaffold requirements are straightforward.
