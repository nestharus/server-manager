# Research: Roles Command

## Scope

This note documents what `discord.Role` metadata is available from
`guild.roles` without calling `guild.chunk()` or relying on
`guild.members`.

Evidence below comes from the installed `discord.py` in this repo's
`.venv` (`2.7.1`, while `pyproject.toml` allows `>=2.3`).

Primary sources consulted:

- [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:52)
- [guild.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/guild.py:575)
- [state.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/state.py:230)
- [flags.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/flags.py:835)

## 1. `discord.Role` metadata available from `guild.roles`

`Guild._from_data()` constructs `Role` objects directly from the guild
payload's `roles` field, storing them in `self._roles`
([guild.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/guild.py:594)).
`Guild.roles` then returns those cached roles in hierarchy order
([guild.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/guild.py:1026)).

The `Role` class documents these public attributes and properties:

| Field | Type / shape | Evidence | Notes |
| --- | --- | --- | --- |
| `id` | `int` | [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:169), [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:232) | Stored directly from role payload. |
| `name` | `str` | [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:171), [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:279) | Stored directly from role payload. |
| `hoist` | `bool` | [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:175), [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:283) | Stored directly from role payload. |
| `position` | `int` | [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:177), [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:281) | Stored directly from role payload. |
| `permissions` | `Permissions` object | [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:280), [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:363) | Derived from stored `_permissions` integer. |
| `colour` / `color` | `Colour` object | [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:282), [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:368), [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:373) | Alias properties for the role's primary colour. |
| `managed` | `bool` | [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:201), [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:286) | Stored directly from role payload. |
| `mentionable` | `bool` | [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:204), [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:287) | Stored directly from role payload. |
| `unicode_emoji` | `str \| None` | [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:189), [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:285) | Stored directly from role payload. |
| `display_icon` | `Asset \| str \| None` | [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:379), [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:395) | Returns `self.icon or self.unicode_emoji`. |
| `created_at` | `datetime` | [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:402) | Derived from the snowflake ID, not stored as a payload field. |
| `tags` | `RoleTags \| None` | [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:206), [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:288) | Built from the optional `tags` payload. |
| `is_default()` | `bool` | [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:298) | True when `role.id == guild.id`. |
| `is_bot_managed()` | `bool` | [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:302) | Delegates to `RoleTags.is_bot_managed()`. |
| `is_integration()` | `bool` | [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:316) | Delegates to `RoleTags.is_integration()`. |
| `is_premium_subscriber()` | `bool` | [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:309) | Delegates to `RoleTags.is_premium_subscriber()`. |
| `is_assignable()` | `bool` | [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:323), [guild.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/guild.py:734) | Computed from `guild.me`, role state, and role hierarchy. |

`RoleTags` exposes these public fields and helpers
([role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:52)):

- `bot_id`
- `integration_id`
- `subscription_listing_id`
- `is_bot_managed()`
- `is_integration()`
- `is_premium_subscriber()`
- `is_available_for_purchase()`
- `is_guild_connection()`

One nuance: `is_assignable()` is not pure payload metadata. It depends
on the current bot member (`guild.me`), whether the role is managed or
default, and whether the bot's top role outranks the role
([role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:323)).
`Guild.me` is documented in source as "always cached"
([guild.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/guild.py:734)),
so this method does not depend on a full guild member chunk.

## 2. `guild.roles` availability and required intents

`parse_guild_create()` creates or updates the `Guild` from the
`GUILD_CREATE` gateway event before any optional chunking happens
([state.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/state.py:1314)).
Inside `Guild._from_data()`, the library immediately iterates
`guild.get('roles', [])` and populates `self._roles`
([guild.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/guild.py:594)).

This means `guild.roles` is guild-state cache, not member-cache state.

Intent evidence:

- `Intents.guilds` corresponds to `Guild` and "all its attributes"
  ([flags.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/flags.py:845)).
- `Intents.default()` disables `presences`, `members`, and
  `message_content`, but does not disable `guilds`
  ([flags.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/flags.py:835)).
- `Intents.members` corresponds to member cache features such as
  `Guild.chunk`, `Guild.fetch_members`, `Guild.get_member`, and
  `Guild.members`
  ([flags.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/flags.py:874)).

Conclusion from source: `guild.roles` is populated from `GUILD_CREATE`
without calling `guild.chunk()`. The relevant gateway intent is
`Intents.guilds`. `Intents.members` is not required for the role list
itself.

## 3. Why `Role.members` is the pitfall to avoid

`Role.members` does not come from the role payload. It is computed by
filtering the guild member cache:

- `Role.members` starts with `list(self.guild._members.values())`
  ([role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:413)).
- `Guild.members` is just a proxy over `self._members.values()`
  ([guild.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/guild.py:997)).
- `Guild.chunk()` is the websocket operation that requests all members,
  requires `Intents.members`, and is documented as slow
  ([guild.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/guild.py:4432)).

`Guild._from_data()` only adds members from the initial guild payload
when caching rules allow it, or when the member is the client itself, or
when voice-state caching applies
([guild.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/guild.py:649)).
Without chunking or other member-cache population, `_members` is empty
or partial, so `Role.members` is also empty or partial.

For the default `@everyone` role the behavior is especially direct:
`Role.members` returns `all_members` from the current cache without any
extra lookup
([role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:416)).

## 4. Serialization considerations

Several `Role` fields are plain scalars and need no special treatment:
`id`, `name`, `hoist`, `position`, `managed`, `mentionable`,
`unicode_emoji`, `is_default()`, `is_bot_managed()`, `is_integration()`,
`is_premium_subscriber()`, and `is_assignable()`.

These fields are object-valued or derived and are not plain JSON
scalars as returned by the library:

- `permissions` is a `Permissions` object, not an `int`
  ([role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:363),
  [permissions.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/permissions.py:195)).
- `colour` / `color` is a `Colour` object wrapping a raw integer value
  ([role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:368),
  [colour.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/colour.py:80)).
- `created_at` is a `datetime`
  ([role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:402)).
- `display_icon` can be either an `Asset`, a Unicode emoji `str`, or
  `None`
  ([role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:395)).
- `Asset.__str__()` returns the CDN URL string, but the raw `Asset`
  itself is still a library object
  ([asset.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/asset.py:368)).
- `tags` is a `RoleTags` object or `None`
  ([role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:206),
  [role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:288)).

For `tags`, the public surface is partly fields and partly methods:
`bot_id`, `integration_id`, `subscription_listing_id`,
`is_bot_managed()`, `is_integration()`, `is_premium_subscriber()`,
`is_available_for_purchase()`, and `is_guild_connection()`
([role.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/role.py:63)).
