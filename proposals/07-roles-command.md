# Proposal: Roles Command

Date: 2026-04-12

## Goal

Add a read-only `roles` subcommand to `discord_cli.py` that exposes the
Humility guild's cached role metadata as JSON.

This command should:

- follow the existing per-command handler pattern
- use `guild.roles` only
- return JSON-safe primitives only
- avoid any dependency on member chunking or member-cache-derived role
  membership

This proposal is design only. It does not include implementation code.

## Handler Shape

Define a new async handler matching the existing command pattern:

```python
async def fetch_roles(guild, args) -> dict:
    ...
```

Recommended typed shape, consistent with the current file:

```python
async def fetch_roles(
    guild: discord.Guild,
    _: argparse.Namespace,
) -> dict[str, Any]:
    ...
```

The handler should iterate the cached `guild.roles` collection and
serialize each `discord.Role` into a plain dict.

## Output Contract

`data` should contain:

- `count`
- `roles`

Return shape:

```json
{
  "count": 35,
  "roles": []
}
```

Each role entry should include exactly these fields:

- `id` as `int`
- `name` as `str`
- `color` as `int`, from `role.color.value`
- `hoist` as `bool`
- `position` as `int`
- `permissions` as `int`, from `role.permissions.value`
- `managed` as `bool`
- `mentionable` as `bool`
- `is_default` as `bool`, from `role.is_default()`
- `is_bot_managed` as `bool`, from `role.is_bot_managed()`
- `is_integration` as `bool`, from `role.is_integration()`
- `is_premium_subscriber` as `bool`, from `role.is_premium_subscriber()`
- `created_at` as ISO 8601 string

Recommended serialized shape:

```json
{
  "id": 123,
  "name": "Helper",
  "color": 3447003,
  "hoist": true,
  "position": 7,
  "permissions": 104188992,
  "managed": false,
  "mentionable": true,
  "is_default": false,
  "is_bot_managed": false,
  "is_integration": false,
  "is_premium_subscriber": false,
  "created_at": "2024-01-02T03:04:05+00:00"
}
```

## Serialization Rules

The handler should preserve the current `guild.roles` order rather than
introducing a second sort. `discord.py` already exposes this collection
in role hierarchy order, which is the most useful default for inspection
and later automation.

Object-valued `discord.py` fields should be flattened explicitly:

- `role.color.value` for `color`
- `role.permissions.value` for `permissions`
- `role.created_at.isoformat()` or the existing `iso_or_none()` helper
  for `created_at`

The command should remain a pure metadata export. It should not infer or
derive role usage from member state.

## Registration

Register the new command in both existing command wiring points.

### `command_specs()`

Add:

```python
"roles": fetch_roles,
```

### `build_parser()`

Add a no-argument subparser for `roles`, alongside the existing simple
inspection commands such as `overview`, `bots`, `channels`, and
`integrations`.

Recommended help text:

```python
("roles", "List guild roles")
```

No positional arguments or optional flags are needed for the first
version.

## Why This Shape

- It matches the current dispatch model exactly: command name to async
  handler to JSON payload.
- It uses guild-level cached state that is already available from
  `GUILD_CREATE`.
- It keeps the command read-only and inexpensive.
- It avoids misleading outputs that would come from partial member cache
  inspection.

## Tradeoffs

- Returning raw `permissions` bits is compact and stable, but less
  immediately readable than expanding named permission flags.
- Omitting `tags` keeps the schema small and stable, but means consumers
  only get the derived booleans rather than the full tag payload.
- Omitting icon-related fields keeps the first version simple, but does
  not expose role display decoration metadata.
- Preserving `guild.roles` order is practical for inspection, but it
  means the command does not offer alternate sort modes such as name or
  creation time.

## Anti-scope

This proposal explicitly does not include:

- any `guild.chunk()` call
- any `Role.members` access
- any per-role member counts
- any `display_icon` field
- any `unicode_emoji` field
- any `tags` sub-object
- any permission bit expansion into named booleans
- any filters, search, or alternate sort flags
- any write or mutation behavior
- any backwards-compatibility shim layer

## Decision

Proceed with a minimal `roles` inspection command backed only by
`guild.roles`, returning:

```json
{
  "count": N,
  "roles": [...]
}
```

with the serialized role schema defined above.
