# Phase 1: Problem Research — Discord CLI Tool

## Objective
Document the problem space for building a Discord guild inspection and management CLI tool. Do NOT design solutions — only research and document the problem space with evidence.

## Context
- We are building a one-shot CLI tool (`discord_cli.py`) that wraps `discord.py` to inspect and manage the "Humility" Discord guild (ID: `<guild id>`).
- The tool uses a bot token and guild ID from a `.env` file.
- It needs to support subcommands for: overview, listing bots, listing channels, finding channels by name, reading messages from channels, and listing integrations.
- Each subcommand opens a gateway session, runs once, prints JSON to stdout, and exits.
- The server has several bots, broken integrations, templates, and roles that need inspection.
- HumilityTicketBot is a custom-named bot (likely Tickets/ticketsbot.net) behind slash commands.
- The `support` integration is broken.

## Research Questions
1. What discord.py APIs are needed for each subcommand (overview, bots, channels, find-channel, read, integrations)?
2. What gateway intents are required for each operation?
3. What are the data structures returned by discord.py for guilds, channels, members, roles, and integrations?
4. What are the error modes (rate limiting, missing permissions, unavailable guilds)?
5. What is the best pattern for one-shot CLI tools with discord.py (connect, run, exit)?
6. How should JSON output be structured for each subcommand to be useful for downstream processing?

## Deliverable
Write your findings to `research/05-discord-cli.md`. Include evidence from discord.py documentation and API behavior. Structure the report by subcommand.

## Rules
- Do NOT propose solutions or designs
- Do NOT write implementation code
- Focus on documenting the problem space with evidence
- Reference discord.py API methods and their return types
