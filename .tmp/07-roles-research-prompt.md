# Research: Roles Command for discord_cli.py

## Task

Investigate what a `roles` subcommand for `discord_cli.py` should
return, focusing on role metadata available WITHOUT calling
`guild.chunk()` or depending on `guild.members`.

## Context

`discord_cli.py` is a one-shot Discord inspection CLI for the Humility
guild (ID <guild id>). It connects to Discord's gateway, runs a
command handler, and prints JSON output. Current commands: overview,
bots, channels, find-channel, read, integrations.

The CLI previously had `guild.chunk()` calls that caused hangs on
large guilds. We need to add a `roles` command that avoids this
pattern entirely.

## What to Research

1. **discord.py Role object attributes**: What metadata is available on
   `discord.Role` objects from `guild.roles`? Document: id, name, color,
   hoist, position, permissions, managed, mentionable, created_at,
   display_icon, unicode_emoji, is_default, is_bot_managed,
   is_integration, is_premium_subscriber, is_assignable, tags.

2. **guild.roles availability**: Confirm that `guild.roles` is populated
   from the GUILD_CREATE gateway event without needing `guild.chunk()`.
   What intents are required?

3. **Role.members pitfall**: Document why `Role.members` requires
   chunking — it filters `guild.members` which is empty without chunk.
   This is the pattern to AVOID.

4. **Serialization considerations**: What Role attributes need special
   handling? (e.g., Permissions object, Color object, datetime, tags)

## Output

Write findings to `research/07-roles-command.md` in the project root.
Include evidence from discord.py documentation or source code.
Do NOT propose solutions or designs — research only.
