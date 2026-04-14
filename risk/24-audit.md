# Audit Risk Assessment: Discord Bot

## Overall: LOW

The proposal is well-grounded in upstream `discord.py` documentation,
local runtime evidence, and the existing daemon patterns. No blocking
issues were identified. The design is intentionally narrow, the
tradeoffs are explicitly documented, and the test contract covers the
right boundaries. Implementation can proceed as designed.

## Findings

### Finding 1: `guilds=True` and `presences=False` are redundant after `Intents.default()`
- Severity: LOW
- Description: `discord.Intents.default()` returns all non-privileged
  intents enabled. The guilds intent is not privileged, so `default()`
  already sets `guilds=True`. Similarly, `presences` is privileged, so
  `default()` already sets `presences=False`. The proposal lists all four
  flags (`guilds=True`, `members=True`, `message_content=True`,
  `presences=False`) as "Humility's current service needs," but only
  `members` and `message_content` actually modify the defaults. The
  redundant assignments are harmless — they make the intent surface
  self-documenting and protect against upstream default changes. This is a
  documentation-accuracy concern, not a functional one.
- Recommendation: No change needed. The explicit listing improves
  readability for developers unfamiliar with the `default()` baseline.
  If the implementation adds a comment noting which flags modify defaults
  vs. which are declarative, that would improve clarity further, but is
  not required.

### Finding 2: `message_content=True` is an intentional deviation requiring portal configuration
- Severity: LOW
- Description: The current daemon explicitly disables `message_content`
  ([daemon/__main__.py:70](/home/nes/discord/daemon/__main__.py:70)).
  The proposal enables it based on synthesized moderation needs. This is
  a privileged intent: it requires enablement in both the code and the
  Discord developer portal. If not enabled in the portal, the bot will
  connect successfully but receive empty message content, leading to
  silent failures in moderation workflows. The proposal correctly scopes
  this: "Operational enablement of privileged intents in the Discord
  developer portal remains outside this module." The research confirms
  this two-step requirement
  ([research/24-discord-bot.md:177](/home/nes/discord/research/24-discord-bot.md:177)).
  The tradeoff is sound — the service bot's scope explicitly includes
  moderation, which the daemon's scope did not.
- Recommendation: No change to the proposal. When the bot is deployed,
  portal configuration of `message_content` and `members` privileged
  intents should be verified as a deployment checklist item, not a code
  concern.

### Finding 3: Constructor contract is side-effect-free as claimed
- Severity: LOW
- Description: The proposal claims construction does not open a gateway
  connection, perform HTTP calls, sync commands, or read environment
  variables. The research confirms this from three independent sources:
  (1) upstream docs place connection behavior in `run`/`start`/`login`/
  `connect`, not the constructor
  ([research/24-discord-bot.md:425](/home/nes/discord/research/24-discord-bot.md:425));
  (2) local runtime inspection with `discord.py 2.7.1` showed
  `user is None` and an attached `CommandTree` after construction without
  any connection call
  ([research/24-discord-bot.md:439](/home/nes/discord/research/24-discord-bot.md:439));
  (3) the current daemon already separates construction from
  `await bot.start(runtime.token)`
  ([daemon/__main__.py:117](/home/nes/discord/daemon/__main__.py:117)).
  The test contract encodes this expectation (`bot.user is None` after
  construction). No additional verification is needed.
- Recommendation: None. The side-effect-free property is well-evidenced.

### Finding 4: Settings passthrough stores the full object, not a copy
- Severity: LOW
- Description: The proposal stores the `Settings` instance directly on
  `self.settings` rather than copying individual fields. This means any
  code with a reference to the bot can access all settings fields,
  including credentials (`discord_bot_token`, `supabase_db_url`). The
  proposal explicitly addresses this tradeoff: "consumers can see the
  full settings object, which is acceptable for an application-internal
  class." The alternative — copying fields to separate attributes — would
  duplicate state and create the maintenance burden of keeping two
  sources synchronized. Since `Settings` uses `repr=False` on credential
  fields
  ([services/discord/app/core/settings.py:8](/home/nes/discord/services/discord/app/core/settings.py:8)),
  the repr-leakage path is already closed. Direct-access leakage
  (e.g., logging `bot.settings.discord_bot_token`) is the same risk
  identified in the settings audit (Finding 1 of `risk/23-audit.md`) and
  accepted at the project level.
- Recommendation: None. The passthrough pattern matches the current
  daemon's direct-attribute pattern and keeps configuration in a single
  validated object.

### Finding 5: Test contract covers the critical boundaries
- Severity: LOW
- Description: The proposal's test contract encodes 13 verification
  points: construction success, `commands.Bot` isinstance, settings
  passthrough, `discord_guild_id` access, four intent flag checks
  (guilds, members, message_content, presences), no-connection
  verification (`bot.user is None`), no event-loop requirement,
  command tree existence (`bot.tree`), and two negative constraints
  (no startup behavior, no caller-supplied intents). These boundaries
  match the module's responsibilities. The constructor smoke-test values
  (`discord_bot_token="test"`, `discord_guild_id=1`,
  `supabase_db_url="postgresql://test"`) are consistent with the
  existing settings test suite
  ([services/discord/tests/test_settings.py:8](/home/nes/discord/services/discord/tests/test_settings.py:8)).
  The anti-scope list (15 exclusions) guards against scope creep in
  implementation.
- Recommendation: None. The test boundaries are comprehensive for the
  module's scope.
