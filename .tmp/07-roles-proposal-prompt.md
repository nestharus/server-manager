# Proposal: Add `roles` Subcommand to discord_cli.py

## Context

Read these files for context:
- `research/07-roles-command.md` — research on discord.Role metadata
- `research/07-roles-command-needs.md` — synthesis of needs
- `discord_cli.py` — current implementation (examine handler patterns)
- `proposals/05-discord-cli.md` — reference for proposal format

## Task

Write a proposal for adding a `roles` subcommand to `discord_cli.py`.
Save it to `proposals/07-roles-command.md`.

## Requirements

The proposal must:

1. **Define the `fetch_roles` handler** — async function matching the
   existing pattern: `async def fetch_roles(guild, args) -> dict`

2. **Specify the serialized role schema** — each role should include:
   - id (int)
   - name (str)
   - color (int — from Colour.value)
   - hoist (bool)
   - position (int)
   - permissions (int — from Permissions.value)
   - managed (bool)
   - mentionable (bool)
   - is_default (bool — from is_default())
   - is_bot_managed (bool — from is_bot_managed())
   - is_integration (bool — from is_integration())
   - is_premium_subscriber (bool — from is_premium_subscriber())
   - created_at (ISO 8601 string)

3. **Specify the return shape**: `{"count": N, "roles": [...]}`

4. **Explicitly NOT include**:
   - No `guild.chunk()` call
   - No `Role.members` access
   - No per-role member counts
   - No `display_icon`, `unicode_emoji`, or `tags` sub-object

5. **Registration**: Add to `command_specs()` and `build_parser()`

6. **Include tradeoffs and anti-scope sections**

## Rules

- Do NOT implement code — proposal only
- Do NOT add backwards compatibility shims
- Follow the existing proposal format in the project
