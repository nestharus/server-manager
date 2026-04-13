# Hookpoint Research: Roles Command

## Task

Map the roles command proposal to existing code in `discord_cli.py`.
Identify what's reusable, what's parallel, and what hooks into existing
patterns. Write findings to `research/07-hookpoints.md`.

## Context

Read these files:
- `proposals/07-roles-command.md` — the approved proposal
- `discord_cli.py` — current implementation
- `research/05-hookpoints.md` — reference for hookpoint format

## What to Map

1. **Handler registration**: Where does `fetch_roles` get added to
   `command_specs()` (line ~417)?

2. **Parser registration**: Where does the `roles` subparser get added
   in `build_parser()` (line ~441)?

3. **Serialization helpers**: Are there existing helpers that can be
   reused? Check `iso_or_none()`, `safe_str()`, etc.

4. **Return shape**: Confirm the `{"count": N, "roles": [...]}` pattern
   matches existing commands like `fetch_bots` and `fetch_integrations`.

5. **Test patterns**: What test patterns exist that should be followed
   for the new command? Check `test_discord_cli.py`.

## Output

Write to `research/07-hookpoints.md`. Include specific line numbers
and function names. Do NOT implement — just map where changes go.
