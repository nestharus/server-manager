# Proposal: `services/discord/app/core/bot.py`

Date: 2026-04-13

## Goal

Define `services/discord/app/core/bot.py` as the Discord service's
minimal bot-construction module.

Its job is to provide one service-local bot class,
`HumilityBot(commands.Bot)`, that accepts a validated `Settings`
instance, stores it on `self.settings`, configures the bot's Discord
intents internally, and remains side-effect-free at construction time.

This proposal is design only. It does not include implementation code.

## Design

The module should export one public class:

```python
class HumilityBot(commands.Bot):
    settings: Settings

    def __init__(self, settings: Settings) -> None:
        ...
```

### Constructor contract

The constructor should take exactly one required service settings
object:

```python
bot = HumilityBot(Settings(...))
```

Required behavior:

- `settings` must be stored unchanged as `self.settings`.
- The resulting object must support
  `bot.settings.discord_guild_id`.
- Construction must not open a gateway connection, perform HTTP calls,
  sync commands, or read environment variables.
- Intents must be resolved inside the module rather than supplied by
  the caller.

The intended construction shape is:

```python
class HumilityBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=build_intents(),
        )
        self.settings = settings
```

That snippet is the contract shape, not approval to add unrelated bot
startup behavior.

### Intents policy

The bot should build intents from `discord.Intents.default()` and then
apply Humility's current service needs:

- `guilds = True`
- `members = True`
- `message_content = True`
- `presences = False`

This keeps the intent surface aligned with the synthesized needs for
applications, tickets, moderation, and role-sensitive workflows.

The code-owned policy is limited to enabling the required intent flags
on the `discord.Intents` object. Operational enablement of privileged
intents in the Discord developer portal remains outside this module.

### Public surface

The module should stay intentionally small:

- public export: `HumilityBot`
- private responsibility: bot-local intent construction
- no extra public helpers unless implementation clarity benefits from a
  private `build_intents()` function

## Architecture

`core.bot` belongs under `services/discord/app/core/` because it is
part of the daemon's application boundary, not workflow logic and not
startup orchestration.

Recommended ownership split:

- `core.settings` defines validated runtime configuration.
- `core.bot` consumes `Settings` and produces the configured bot
  instance.
- A later entrypoint or factory owns lifecycle actions such as
  `async with bot`, `bot.start(...)`, and shutdown handling.
- Later command-registration modules, handlers, and tasks attach
  behavior to the bot after construction rather than inside
  `HumilityBot.__init__()`.

This yields a clean boundary:

- tests can construct `HumilityBot(Settings(...))` with no network side
  effects
- runtime startup can read the token from `bot.settings.discord_bot_token`
  at the lifecycle boundary
- later slash-command registration can rely on the `commands.Bot`
  command tree already created by the base class

## Tradeoffs

- `commands.Bot` vs `discord.Client`
  `commands.Bot` is the correct base because Humility needs slash
  command support via the built-in command tree. A bare
  `discord.Client` would force the service to recreate machinery the
  current daemon and upstream library already provide.
- Constructor-owned intents vs caller-supplied intents
  Building intents inside the module keeps the bot contract stable and
  ensures tests and runtime use the same baseline. The cost is reduced
  per-call flexibility, which is acceptable for a single-guild daemon.
- `message_content = True` vs staying minimal to the current daemon
  The existing root daemon sets `message_content = False`, but the
  synthesized Humility needs explicitly include moderation-oriented
  message inspection. Enabling it in the new service bot matches the
  intended service scope, at the cost of requiring privileged-intent
  portal configuration.
- Store `Settings` directly vs copy selected fields
  Storing the validated settings object preserves a single source of
  runtime configuration and guarantees `bot.settings.discord_guild_id`
  works without duplicating config onto separate attributes. The cost is
  that consumers can see the full settings object, which is acceptable
  for an application-internal class.
- No startup work in `__init__()` vs eager registration
  Keeping construction side-effect-free makes smoke tests reliable and
  avoids hidden gateway behavior. The cost is that later startup code
  must perform explicit registration and lifecycle steps.

## Anti-scope

This module should explicitly exclude:

- bot startup or shutdown logic
- reading environment variables or instantiating `Settings()` internally
- `load_dotenv()` or repo-root env-file discovery
- slash-command registration, `setup_hook()`, or `tree.sync()`
- event handlers, cogs, background tasks, or API client wiring
- database connections, repository construction, or service injection
- alternate constructors, singleton accessors, or cached global bot
  instances
- compatibility aliases for old daemon attributes such as
  `bot.guild_id` or `bot.config`
- caller-configurable intent overrides, feature flags, or dual support
  for multiple bot shapes

## Test Contract

The eventual implementation should be accepted only if tests encode this
contract:

- `HumilityBot(Settings(discord_bot_token="test", discord_guild_id=1, supabase_db_url="postgresql://test"))`
  constructs successfully.
- The constructed object is an instance of `commands.Bot`.
- The constructed object exposes the original settings object on
  `bot.settings`.
- `bot.settings.discord_guild_id == 1`.
- The bot configures intents internally; tests should not need to pass
  an intents object.
- `bot.intents.guilds is True`.
- `bot.intents.members is True`.
- `bot.intents.message_content is True`.
- `bot.intents.presences is False`.
- Construction does not connect to Discord; immediately after
  construction, bot state remains pre-login and `bot.user is None`.
- Construction does not require a running event loop beyond what
  `commands.Bot` normally needs for instantiation.
- The base-class command tree exists after construction so later command
  registration can attach to `bot.tree`.
- Tests must not encode startup behavior such as calling `start()`,
  `login()`, `connect()`, or `tree.sync()`.

## Decision

Keep `services/discord/app/core/bot.py` intentionally narrow: one
`HumilityBot(commands.Bot)` class with a `Settings` constructor
dependency, module-owned intent policy, and no network or startup side
effects during object creation.
