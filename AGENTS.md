# AGENTS.md

Guidance for coding agents (Claude Code, etc.) working in this repo.

## What this is

A thin local CLI around the Discord REST API for managing one specific
guild owned by the user. The CLI is the interface between an agent
session and the live Discord server.

## Rules

- This repo targets the Humility guild (`900000000000000001`).
- Read-only inspection is always safe. Any visible Discord mutation
  requires explicit user approval first.
- Prefer extending `discord_cli.py` over one-off scripts so future
  sessions have reusable commands.
- Persist discovered facts in `NOTES.md` so later sessions can resume
  work without rescanning the whole guild.
- Keep secrets in `.env`; never hardcode the bot token.
- Keep the setup local and simple: one CLI, one bot token, one guild.
