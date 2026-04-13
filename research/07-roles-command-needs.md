# Synthesis: Roles Command — Humility Context

## What We Need

A `roles` subcommand for `discord_cli.py` that returns role metadata
for the Humility guild without depending on `guild.chunk()` or
`Role.members`.

## Mapping Research to Humility

### Guild Context
- Humility has 35 roles (from overview command output)
- All roles are available from `guild.roles` via GUILD_CREATE
- `Intents.guilds` is already enabled in `build_intents()`
- No chunking needed — roles are guild-level cache, not member cache

### Required Role Fields
Based on the research, the serialized role should include:
- `id` — int, direct
- `name` — str, direct
- `color` — int (from `Colour.value`), for display purposes
- `hoist` — bool, whether role appears separately in member list
- `position` — int, hierarchy position
- `permissions` — int (from `Permissions.value`), raw permission bits
- `managed` — bool, whether managed by an integration/bot
- `mentionable` — bool
- `is_default` — bool (from `is_default()`)
- `is_bot_managed` — bool (from `is_bot_managed()`)
- `is_integration` — bool (from `is_integration()`)
- `is_premium_subscriber` — bool (boost role)
- `created_at` — ISO 8601 string

### Explicitly Excluded
- `Role.members` — requires chunk, not metadata
- `member_count` per role — requires chunk
- `display_icon` / `unicode_emoji` — nice-to-have but not essential
  for an inspection tool; can add later
- `tags` sub-object — the boolean helpers above cover the useful bits

### Pattern Consistency
The function should follow the existing handler pattern:
- Async function: `fetch_roles(guild, args) -> dict`
- Returns `{"count": N, "roles": [...]}`
- Registered in `command_specs()` and `build_parser()`
- JSON output via `print_json(success_payload(...))`

## Gaps

None. The research confirms all needed fields are available from the
cached `guild.roles` without chunking.

## Decision

Proceed with adding `fetch_roles` using only cached guild role
attributes. No `guild.chunk()`, no `Role.members`, no member counts.
