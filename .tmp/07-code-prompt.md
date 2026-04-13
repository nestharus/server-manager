# Code Agent: Roles Command Implementation

## Task

Implement the `fetch_roles` handler in `discord_cli.py` to make the
tests in `tests/test_discord_cli.py` pass.

## Context

Read these files:
- `proposals/07-roles-command.md` — the approved proposal
- `research/07-hookpoints.md` — where to add code
- `tests/test_discord_cli.py` — the tests you must make pass
- `discord_cli.py` — the file to modify

## What to Implement

1. **Add `fetch_roles` handler** — async function that:
   - Takes `(guild: discord.Guild, _: argparse.Namespace)`
   - Returns `{"count": N, "roles": [serialized_role, ...]}`
   - Iterates `guild.roles` (cached, no chunking)
   - Serializes each role with: id, name, color (from `.color.value`),
     hoist, position, permissions (from `.permissions.value`), managed,
     mentionable, is_default (from `.is_default()`), is_bot_managed
     (from `.is_bot_managed()`), is_integration (from `.is_integration()`),
     is_premium_subscriber (from `.is_premium_subscriber()`),
     created_at (ISO 8601 via `iso_or_none()`)

2. **Register in `command_specs()`** — add `"roles": fetch_roles`

3. **Register in `build_parser()`** — add `("roles", "List guild roles")`
   to the simple subcommand loop

## Rules

- Do NOT modify tests — they encode the contract
- Do NOT add `guild.chunk()` or access `Role.members`
- Do NOT add backwards compatibility shims
- Follow existing code patterns exactly
- Run `uv run pytest tests/test_discord_cli.py -v` to verify all tests pass
