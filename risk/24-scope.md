# Scope Risk Assessment: Discord Bot

## Overall: LOW

The proposal defines one `commands.Bot` subclass with one constructor
parameter, module-owned intents, and no network side effects at
construction time. Every design choice traces back to research evidence
or synthesized service needs. The anti-scope section explicitly fences
out fifteen categories of potential expansion, and the implementation
surface is a single class with a single private helper.

## Findings

### Finding 1: No scope creep detected
- Severity: LOW
- Description: The research identified six problem-space areas: bot
  class hierarchy (`commands.Bot` vs `discord.Client`), intents
  configuration, command tree mechanics, settings injection pattern,
  construction side-effect safety, and existing daemon patterns. The
  synthesis distilled these into five concrete needs: use `commands.Bot`,
  enable guilds/members/message_content intents while disabling
  presences, inject `Settings` and store as `self.settings`, ensure no
  side effects on construction, and keep the module minimal. The proposal
  delivers exactly those five needs — one class, one constructor, one
  intent builder, no extras. The anti-scope section (proposal lines
  145-159) explicitly excludes startup logic, env loading, command
  registration, event handlers, cogs, database wiring, singleton
  accessors, compatibility aliases, and caller-configurable intent
  overrides. Nothing in the proposal extends beyond what the research
  and synthesis surfaced.

### Finding 2: message_content divergence is justified
- Severity: LOW
- Description: The research documented that the current daemon sets
  `message_content = False` (research lines 237-243) and found no
  existing `on_message` handlers or `Message.content` reads. The
  proposal sets `message_content = True`, which is a departure from
  current daemon behavior. However, the synthesis explicitly identifies
  this as a forward-looking service need for moderation-oriented message
  inspection (synthesis line 8). The proposal's tradeoffs section
  (proposal lines 127-131) openly acknowledges this divergence and
  explains the rationale. This is a deliberate, reasoned scope decision
  rather than creep — it adds one boolean flag backed by documented
  service intent, at the cost of requiring privileged-intent portal
  configuration (an operational concern outside this module).

### Finding 3: Complexity is proportional
- Severity: LOW
- Description: The implementation surface is one class inheriting
  `commands.Bot` with a single `Settings` parameter and one private
  `build_intents()` helper. The constructor calls `super().__init__()`
  with `command_prefix` and `intents`, then stores `self.settings`. The
  test contract (proposal lines 162-184) enumerates thirteen verifiable
  properties but requires no test infrastructure beyond standard
  `commands.Bot` assertions and `Settings` construction — the same
  pattern already used in `services/discord/tests/test_settings.py`.
  Document length is in reasoning, tradeoffs, and guardrails, not code
  surface.

### Finding 4: No new dependency surface
- Severity: LOW
- Description: The proposal depends on `discord.ext.commands.Bot` and
  `discord.Intents`, both provided by `discord.py>=2.3` already declared
  in `services/discord/pyproject.toml:6`. The `Settings` class is
  already implemented at `services/discord/app/core/settings.py`. No new
  packages are introduced. The research confirmed via local runtime
  inspection that `discord.py 2.7.1` provides the exact API surface
  the proposal consumes (research lines 43-50).

### Finding 5: Anti-scope coverage is thorough
- Severity: LOW
- Description: The anti-scope section (proposal lines 145-159)
  enumerates fifteen explicit exclusions: startup/shutdown logic, env
  reading, `load_dotenv()`, slash-command registration, `setup_hook()`,
  `tree.sync()`, event handlers, cogs, background tasks, API client
  wiring, database connections, repository construction, service
  injection, alternate constructors/singletons, compatibility aliases
  for `bot.guild_id`/`bot.config`, and caller-configurable intent
  overrides. Each exclusion maps to a real expansion path visible in the
  existing daemon: `daemon/__main__.py` performs `load_dotenv()` at
  import time (research lines 467-468), registers commands in
  `setup_hook()` (research lines 477-478), and stores `guild_id`,
  `config`, `conn`, and `base_path` as direct attributes (research
  lines 393-405). The anti-scope fence prevents migration of those
  daemon patterns into this minimal construction module.

### Finding 6: Minimal future burden
- Severity: LOW
- Description: The module is new with no migration path to manage. The
  architecture section (proposal lines 89-104) explicitly delegates
  lifecycle, command registration, and handler attachment to later
  modules. The only ongoing obligation is that future modules must
  attach behavior to the bot after construction rather than inside
  `HumilityBot.__init__()`, which is the standard `discord.py`
  pattern already followed by the existing daemon. If service intent
  needs change, intents can be updated in the single `build_intents()`
  function without altering the class contract.
