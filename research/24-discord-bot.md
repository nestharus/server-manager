# Research: Discord Bot Module

Date: 2026-04-13

## Scope

This note documents the problem space for the initial Discord bot
module at `services/discord/app/core/bot.py`.

It is limited to:

- upstream `discord.py` 2.x bot, intents, and application-command facts
- the current monorepo evidence relevant to a Discord gateway adapter
- the smoke-test construction requirement for `HumilityBot(settings)`
- the question of whether object construction alone has network side
  effects

It does not propose an implementation, class design, or migration plan.

## Primary Sources

### Local repo

- [services/discord/pyproject.toml](/home/nes/discord/services/discord/pyproject.toml:1)
- [services/discord/app/core/settings.py](/home/nes/discord/services/discord/app/core/settings.py:1)
- [services/discord/tests/test_settings.py](/home/nes/discord/services/discord/tests/test_settings.py:1)
- [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:1)
- [daemon/config.py](/home/nes/discord/daemon/config.py:1)
- [daemon/applications.py](/home/nes/discord/daemon/applications.py:381)
- [daemon/claim.py](/home/nes/discord/daemon/claim.py:40)

### External documentation

- `discord.py` commands API:
  https://discordpy.readthedocs.io/en/stable/ext/commands/api.html
- `discord.py` interactions API:
  https://discordpy.readthedocs.io/en/stable/interactions/api.html
- `discord.py` intents primer:
  https://discordpy.readthedocs.io/en/stable/intents.html

### Local runtime inspection

On 2026-04-13, the local `services/discord/.venv` contained
`discord.py 2.7.1`. In that environment:

- `hasattr(discord, "Bot")` was `False`
- `discord.ext.commands.Bot` existed
- `commands.Bot` was a subclass of `discord.Client`
- constructing `commands.Bot(...)` produced a bot with `user is None`
  and a pre-attached `CommandTree`

## Local Baseline

The new Discord service package already depends on `discord.py>=2.3`
([services/discord/pyproject.toml](/home/nes/discord/services/discord/pyproject.toml:6)).

The new package already has a `Settings` model with the smoke-test
fields `discord_bot_token`, `discord_guild_id`, and `supabase_db_url`
([services/discord/app/core/settings.py](/home/nes/discord/services/discord/app/core/settings.py:5)).
Its tests already verify direct-constructor usage with:

```python
Settings(
    discord_bot_token="test-token",
    discord_guild_id=1,
    supabase_db_url="postgresql://test",
)
```

([services/discord/tests/test_settings.py](/home/nes/discord/services/discord/tests/test_settings.py:7)).

Within `services/discord/app/core/`, there is currently a `settings.py`
module but no `bot.py` file.

The existing root daemon already defines a `HumilityBot` subclass in
`daemon/__main__.py`:

- it subclasses `commands.Bot`
- it stores custom state on instance attributes
- it registers slash commands in `setup_hook()`
- it starts only inside `main()` via `await bot.start(runtime.token)`

([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:74),
[daemon/__main__.py](/home/nes/discord/daemon/__main__.py:90),
[daemon/__main__.py](/home/nes/discord/daemon/__main__.py:102)).

## 1. `discord.Client` vs `discord.Bot` vs `commands.Bot`

### `discord.Client`

The upstream docs describe `discord.Client` as the base client
connection that interacts with the Discord WebSocket and API. Intents
are passed to `Client` or its subclasses.

Evidence:

- `Client` is the base class referred to by the intents primer:
  https://discordpy.readthedocs.io/en/stable/intents.html
  (`Intents` are passed to `Client` or its subclasses)
- `commands.Bot` docs state that `commands.Bot` is a subclass of
  `discord.Client`:
  https://discordpy.readthedocs.io/en/stable/ext/commands/api.html
  (`Bot` "is a subclass of `discord.Client`")

### `commands.Bot`

Upstream `discord.py` documents `discord.ext.commands.Bot` as a
subclass of `discord.Client` plus `GroupMixin`. The same docs state
that unlike `discord.Client`, it does not require manually setting a
`CommandTree`; the tree is created when the bot is instantiated.

Evidence:

- `discord.ext.commands.Bot` class docs:
  https://discordpy.readthedocs.io/en/stable/ext/commands/api.html
- the docs explicitly say:
  - it subclasses `discord.Client`
  - it subclasses `GroupMixin`
  - its `CommandTree` is automatically set on instantiation

The current daemon follows that pattern. Its `HumilityBot` subclasses
`commands.Bot` and uses `self.tree` inside `setup_hook()`
([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:74),
[daemon/__main__.py](/home/nes/discord/daemon/__main__.py:93),
[daemon/__main__.py](/home/nes/discord/daemon/__main__.py:99)).

### `discord.Bot`

Upstream `discord.py` stable docs do not document a top-level
`discord.Bot` class. In the installed local `discord.py 2.7.1`,
`hasattr(discord, "Bot")` was `False`.

Evidence:

- local runtime inspection on 2026-04-13 in
  `services/discord/.venv`
- upstream bot docs are under `discord.ext.commands.Bot`, not
  `discord.Bot`:
  https://discordpy.readthedocs.io/en/stable/ext/commands/api.html

### Current repo alignment for the gateway adapter

The current repo’s gateway adapter is already built around
`commands.Bot`, not bare `discord.Client`. The concrete reason visible
in the code is slash-command handling via `self.tree` and
`app_commands`, which the upstream docs tie directly to `Bot`’s
auto-created `CommandTree`.

Evidence:

- [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:84)
- [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:93)
- [daemon/applications.py](/home/nes/discord/daemon/applications.py:387)
- `Bot` docs:
  https://discordpy.readthedocs.io/en/stable/ext/commands/api.html

## 2. Intents configuration

### What the current daemon enables

The existing daemon builds intents with:

- `discord.Intents.default()`
- `guilds = True`
- `members = True`
- `message_content = False`

([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:66)).

### What the docs say about intent selection

The intents primer states that required intents depend on the events and
cache behavior the bot uses. It also states that privileged intents
must be enabled both in the developer portal and in code.

Evidence:

- intent choice is bot-specific:
  https://discordpy.readthedocs.io/en/stable/intents.html
- privileged intents require both portal enablement and code enablement:
  https://discordpy.readthedocs.io/en/stable/intents.html

### Members intent

The docs list the member intent as relevant when the bot:

- tracks member joins/leaves
- tracks nickname or role changes
- requests the guild member list via `Guild.chunk()` or
  `Guild.fetch_members()`
- wants high-accuracy member cache under `Guild.members`

Evidence:

- member intent checklist:
  https://discordpy.readthedocs.io/en/stable/intents.html

The current repo has member-oriented access patterns:

- `interaction.guild.get_member(...)`
  ([daemon/applications.py](/home/nes/discord/daemon/applications.py:362))
- `guild.get_member(...)`
  ([daemon/claim.py](/home/nes/discord/daemon/claim.py:172))
- `guild.fetch_member(...)`
  ([daemon/claim.py](/home/nes/discord/daemon/claim.py:177))
- `thread.fetch_members()`
  ([daemon/claim.py](/home/nes/discord/daemon/claim.py:48),
  [daemon/claim.py](/home/nes/discord/daemon/claim.py:83))

The intents primer also states that accurate member cache maintenance
requires `Intents.members`, and notes `MemberCacheFlags` plus
`chunk_guilds_at_startup` as separate cache/startup controls.

Evidence:

- member cache discussion:
  https://discordpy.readthedocs.io/en/stable/intents.html
- `Client` options summary including `member_cache_flags` and
  `chunk_guilds_at_startup`:
  https://discordpy.readthedocs.io/en/stable/api.html

### Message content intent

The docs list message-content intent as relevant when the bot reads:

- `Message.content`
- attachments
- embeds
- components
- polls
- or uses the commands extension with a non-mentioning prefix

Evidence:

- message-content checklist:
  https://discordpy.readthedocs.io/en/stable/intents.html

The current daemon explicitly disables `message_content`
([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:70)).
The same module uses `command_prefix=commands.when_mentioned`, not a
non-mentioning prefix
([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:84)).
Repo-wide search in `daemon/` and `services/discord/` did not find
`on_message` handlers or `Message.content` reads.

### Presence intent

The docs list the presence intent as relevant when the bot reads
`Member.status`, `Member.activity`, or `Member.activities`.

Evidence:

- presence-intent checklist:
  https://discordpy.readthedocs.io/en/stable/intents.html

Repo-wide search in `daemon/` and `services/discord/` did not find
current usage of member status/activity APIs.

### Guild intent

Slash commands, guild-scoped command registration, and guild objects all
depend on guild context. The current daemon uses `discord.Object` with a
guild ID for command scoping and sync.

Evidence:

- [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:91)
- [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:99)
- [daemon/applications.py](/home/nes/discord/daemon/applications.py:385)

## 3. Command tree and slash commands in `discord.py` 2.x

### `CommandTree`

The interactions docs define `discord.app_commands.CommandTree` as the
application-command registry. The documented methods include
`add_command`, `copy_global_to`, and `sync`.

Evidence:

- `CommandTree` section:
  https://discordpy.readthedocs.io/en/stable/interactions/api.html

The `commands.Bot` docs also state that a `CommandTree` is attached
automatically when a `Bot` is instantiated.

### Local add vs remote registration

The interactions docs state:

- `add_command(...)` adds the command only locally
- `sync(...)` must be called for commands to appear in Discord

Evidence:

- `CommandTree.add_command()`:
  https://discordpy.readthedocs.io/en/stable/interactions/api.html
- `CommandTree.sync()`:
  https://discordpy.readthedocs.io/en/stable/interactions/api.html

The current daemon matches that flow:

- `/ping` is declared with `@self.tree.command(...)`
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:94))
- application commands are added with `bot.tree.add_command(...)`
  ([daemon/applications.py](/home/nes/discord/daemon/applications.py:391))
- `self.tree.sync(guild=guild)` is called in `setup_hook()`
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:99))

### Guild-specific vs global commands

The interactions docs distinguish guild and global commands:

- `add_command(..., guild=..., guilds=...)`
  adds guild-scoped commands
- if `guild`/`guilds` are omitted, the command is global
- `sync(guild=...)` syncs guild commands
- `sync(guild=None)` syncs global commands

Evidence:

- `CommandTree.add_command()` parameter docs:
  https://discordpy.readthedocs.io/en/stable/interactions/api.html
- `CommandTree.sync()` parameter docs:
  https://discordpy.readthedocs.io/en/stable/interactions/api.html

The `@app_commands.guilds(...)` decorator sets default guilds for a
command when it is later added to a tree.

Evidence:

- `app_commands.guilds()` decorator docs:
  https://discordpy.readthedocs.io/en/stable/interactions/api.html

The current daemon is guild-scoped, not global:

- `/ping` is decorated with `@app_commands.guilds(guild)`
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:93))
- `/apply` is also decorated with `@app_commands.guilds(guild)`
  ([daemon/applications.py](/home/nes/discord/daemon/applications.py:389))
- sync is performed with `guild=...`
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:99))

### Development helper: `copy_global_to`

The interactions docs describe `copy_global_to(*, guild)` as mainly a
development aid for copying global commands into a test guild.

Evidence:

- `CommandTree.copy_global_to()` docs:
  https://discordpy.readthedocs.io/en/stable/interactions/api.html

The current daemon code does not use this helper.

## 4. Settings injection and custom state

### Smoke-test settings shape already exists

The new Discord service already has a `BaseSettings` model with the
exact constructor fields used in the smoke-test requirement
([services/discord/app/core/settings.py](/home/nes/discord/services/discord/app/core/settings.py:5)).
Its tests show two loading modes:

- direct constructor kwargs
- environment-backed construction

([services/discord/tests/test_settings.py](/home/nes/discord/services/discord/tests/test_settings.py:7),
[services/discord/tests/test_settings.py](/home/nes/discord/services/discord/tests/test_settings.py:92)).

### What `discord.py` exposes in the bot constructor

The upstream `Bot` constructor is for library options such as:

- `command_prefix`
- `tree_cls`
- `description`
- `allowed_contexts`
- `allowed_installs`
- `intents`

Evidence:

- `Bot` signature:
  https://discordpy.readthedocs.io/en/stable/ext/commands/api.html
- local runtime inspection in `discord.py 2.7.1` reported:
  `commands.Bot.__init__(self, command_prefix, *, help_command, tree_cls, description, allowed_contexts, allowed_installs, intents, **options)`

### Existing custom-state pattern in this repo

The current daemon subclasses `commands.Bot` and accepts extra
constructor parameters:

- `guild_id`
- `config`
- `conn`
- `intents`
- `base_path`

It then stores custom state directly on `self`:

- `self.guild_id`
- `self.config`
- `self.conn`
- `self.base_path`

([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:75),
[daemon/__main__.py](/home/nes/discord/daemon/__main__.py:85)).

`daemon/applications.py` also assumes this direct-attribute pattern. It
reads `bot.guild_id`, `bot.tree`, `bot.config`, and `bot.conn`
([daemon/applications.py](/home/nes/discord/daemon/applications.py:381)).

## 5. No side effects on construction

### What the docs separate

The `commands.Bot` docs distinguish object construction from runtime
connection methods:

- `run(...)` is a blocking call
- `start(...)` is shorthand for `login()` + `connect()`
- `setup_hook()` runs during `login()`, before websocket connection

Evidence:

- `run()` docs:
  https://discordpy.readthedocs.io/en/stable/ext/commands/api.html
- `start()` docs:
  https://discordpy.readthedocs.io/en/stable/ext/commands/api.html
- `setup_hook()` docs:
  https://discordpy.readthedocs.io/en/stable/ext/commands/api.html

Those docs place connection behavior in `run`/`start`/`login`/`connect`,
not in the constructor.

### Local runtime evidence

In local runtime inspection with `discord.py 2.7.1`, constructing
`commands.Bot(...)` without calling `run`, `start`, `login`, or
`connect` resulted in:

- a normal bot object
- `user is None`
- an attached `CommandTree`

That is consistent with "constructed but not logged in".

### Current daemon behavior

The existing daemon constructs the bot first and only connects later in
`main()` via `await bot.start(runtime.token)`
([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:109),
[daemon/__main__.py](/home/nes/discord/daemon/__main__.py:117)).

So the current repo already separates:

- bot object construction
- gateway login/connect

## 6. Existing daemon patterns in `daemon/`

### `daemon/__main__.py`

Current behavior:

- loads `.env` at import time
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:28),
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:31))
- reads runtime env into a `RuntimeConfig`
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:34),
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:42))
- builds intents in a dedicated helper
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:66))
- subclasses `commands.Bot`
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:74))
- registers commands in `setup_hook()`
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:90))
- starts the bot only inside `main()`
  ([daemon/__main__.py](/home/nes/discord/daemon/__main__.py:102))

### `daemon/config.py`

Current config loading is separate from bot construction. The module
defines frozen dataclasses for daemon config and chapter/form config,
and exposes `load_config(base_path) -> DaemonConfig`
([daemon/config.py](/home/nes/discord/daemon/config.py:48),
[daemon/config.py](/home/nes/discord/daemon/config.py:117)).

That means the current daemon shape is already:

- environment/runtime config in `__main__`
- repo YAML config in `daemon.config`
- bot receives already-loaded config objects

### `daemon/applications.py`

The application-command subsystem expects a bot-like object with
custom state already attached:

- `bot.guild_id`
- `bot.tree`
- `bot.config`
- `bot.conn`

Evidence:

- [daemon/applications.py](/home/nes/discord/daemon/applications.py:381)
- [daemon/applications.py](/home/nes/discord/daemon/applications.py:385)
- [daemon/applications.py](/home/nes/discord/daemon/applications.py:387)

## Findings Summary

1. In upstream `discord.py`, the documented bot class is
   `discord.ext.commands.Bot`, not top-level `discord.Bot`. The local
   installed `discord.py 2.7.1` also has no `discord.Bot`.
2. The current repo already uses `commands.Bot` because it needs
   `self.tree` and `app_commands` slash-command registration.
3. Current code evidences `guilds` and `members` usage. It explicitly
   disables `message_content`, and there is no current repo evidence for
   `presences`.
4. Slash commands in `discord.py 2.x` are managed through
   `CommandTree`; adding is local, `sync()` publishes to Discord, and
   the current daemon uses guild-scoped registration.
5. The repo’s current custom-state pattern is constructor injection into
   a `commands.Bot` subclass followed by direct instance attributes.
6. Object construction alone is separate from network connection in the
   library docs and in the current daemon. Connection occurs when
   `start()` / `login()` / `connect()` / `run()` are called.
