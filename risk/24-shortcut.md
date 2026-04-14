# Shortcut Risk Assessment: Discord Bot

## Overall: LOW

## Findings

### Finding 1: `message_content = True` enables a privileged intent with no current consumer
- Severity: LOW
- Description: The existing daemon explicitly disables `message_content`
  (`daemon/__main__.py:70`), and the research found no `on_message`
  handlers or `Message.content` reads anywhere in `daemon/` or
  `services/discord/`. The proposal enables it based on "synthesized
  Humility needs" for moderation-oriented message inspection. This could
  appear to be a speculative addition that pulls in a privileged intent
  before any code exercises it, deferring the actual moderation
  implementation while pre-committing to the portal configuration cost.
  However, the proposal documents this explicitly in the Tradeoffs
  section, explains why it diverges from the current daemon, and ties
  the decision to the intended service scope rather than the current
  code surface. The intent flag is additive — enabling it now does not
  create technical debt, and the portal configuration is an operational
  step that must happen regardless of timing. If moderation needs change,
  flipping the flag back to `False` is a one-line change with no
  downstream breakage.
- Recommendation: None. The divergence from the current daemon is
  deliberate, documented, and trivially reversible.

### Finding 2: No `MemberCacheFlags` or `chunk_guilds_at_startup` configuration
- Severity: LOW
- Description: The research identifies `MemberCacheFlags` and
  `chunk_guilds_at_startup` as separate controls related to the members
  intent (research section 2, citing the intents primer). The proposal
  enables `members = True` but does not specify cache flags or chunking
  behavior. This could appear to defer cache-correctness decisions to
  a later module. However, these are runtime startup concerns, not
  construction concerns. The proposal's scope is object construction
  only, and the anti-scope explicitly excludes "bot startup or shutdown
  logic." The `commands.Bot` base class provides sensible defaults for
  both settings. When the lifecycle entrypoint is designed, it can
  configure chunking behavior based on actual guild size and member
  access patterns.
- Recommendation: None. The omission aligns with the proposal's
  construction-only scope, and the defaults are safe for a single-guild
  daemon.

### Finding 3: Lifecycle boundary is deferred but fully specified
- Severity: LOW
- Description: The proposal does not define how the bot token reaches
  `bot.start()`, how `setup_hook()` is implemented, or how shutdown is
  handled. This could appear to defer significant complexity. However,
  the proposal explicitly documents the ownership split: "A later
  entrypoint or factory owns lifecycle actions such as `async with bot`,
  `bot.start(...)`, and shutdown handling." The architecture section
  specifies that `bot.settings.discord_bot_token` is available at the
  lifecycle boundary. The anti-scope lists startup, shutdown, and
  `setup_hook()` as excluded. The existing daemon already demonstrates
  this exact separation — construction in the class definition,
  `start()` in `main()` (`daemon/__main__.py:117`). The deferred work
  is additive and does not require changing the bot class interface.
- Recommendation: None. The deferral is explicit, the interface
  contract supports the future lifecycle module, and the pattern is
  already proven in the existing daemon.

### Finding 4: Hardcoded intents with no override mechanism
- Severity: LOW
- Description: The proposal builds intents inside the module via a
  private `build_intents()` function with no caller-supplied override.
  The anti-scope explicitly excludes "caller-configurable intent
  overrides, feature flags, or dual support for multiple bot shapes."
  This could appear to be a shortcut that avoids designing a flexible
  intent API. However, for a single-guild daemon with a known feature
  set, intent configuration is a code-owned policy decision, not a
  runtime variable. The proposal's Tradeoffs section acknowledges the
  reduced per-call flexibility and explains why it is acceptable. If
  future requirements demand configurable intents (e.g., feature-gated
  moderation), the constructor can accept an optional intents parameter
  without breaking existing callers.
- Recommendation: None. The rigidity is a deliberate design choice
  for a single-guild daemon, not deferred flexibility.
