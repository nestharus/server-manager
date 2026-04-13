# Shortcut Risk Assessment: bot-activity

## Overall: LOW

No blocking issues. The revised 10000 upper bound on `--per-channel-limit`
resolves the prior MEDIUM finding. One implementation gap requires
attention: the existing code does not yet enforce the upper bound that
the proposal specifies.

## Findings

### Finding 1: Upper bound on `--per-channel-limit` (revised)

- Risk level: LOW (previously MEDIUM)
- Description: The prior assessment flagged the lack of an upper bound
  on `--per-channel-limit`. The revised proposal adds a hard ceiling of
  10000 with explicit validation (`args.per_channel_limit <= 10000`) and
  a clear error message. At 10000 per channel with ~42 scannable
  surfaces, the worst case is `ceil(10000 / 100) × 42 = 4200` paginated
  API requests. `discord.py` handles rate-limit backoff internally, so
  this will not cause 429 bans. Wall-clock time at that depth would be
  noticeable but bounded, and the user must explicitly request it (the
  default remains 100). The 10000 cap prevents the prior concern about
  values like 100000 acting as effectively-unbounded scans.
- Recommendation: The 10000 ceiling is adequate. No further proposal
  change needed.

### Finding 2: Implementation now enforces the 10000 upper bound

- Risk level: LOW (previously MEDIUM — resolved)
- Description: The implementation now validates both bounds:
  `per_channel_limit <= 0 or per_channel_limit > 10000` triggers an
  error exit with the message `"--per-channel-limit must be between 1
  and 10000"`. This matches the proposal's specification and closes
  the prior gap.
- Recommendation: None. Resolved.

### Finding 3: `Forbidden` raised during async iteration, not at call time

- Risk level: LOW
- Description: The proposal says to "catch `discord.Forbidden` around
  each `channel.history(...)` call." In `discord.py 2.7.1`,
  `channel.history()` returns an async iterator; the actual HTTP request
  fires on the first `__anext__()`, not at construction time. The
  existing implementation correctly wraps the full async list
  comprehension in the try/except (`discord_cli.py:459-465`), so the
  catch scope is correct.
- Recommendation: None. Implementation matches intent.

### Finding 4: Silent `Forbidden` skipping hides scan coverage gaps

- Risk level: LOW
- Description: When the bot lacks `read_message_history` on a channel,
  that channel is silently dropped from results. The caller has no way
  to distinguish "bot was never active there" from "we couldn't look."
  This is explicitly acknowledged in the proposal's tradeoff section
  with a clean extension path (future `skipped` field).
- Recommendation: Acceptable for v1. The extension path is
  backward-compatible. No action needed before implementation.

### Finding 5: `combined_channels` excludes archived threads

- Risk level: LOW
- Description: `guild.threads` only contains threads the client can
  currently see (active, non-archived). Archived threads require
  separate `TextChannel.archived_threads()` or
  `ForumChannel.archived_threads()` calls. A bot that was only active in
  now-archived threads will show zero results even though messages exist.
  The proposal documents this in both its tradeoffs and anti-scope
  sections.
- Recommendation: Acceptable for v1. The limitation is clearly scoped
  and documented. If archived-thread coverage becomes important, it is
  an additive feature, not a redesign.

### Finding 6: No API misuse or undocumented behavior

- Risk level: LOW
- Description: The `is_history_capable_channel` predicate uses
  `isinstance()` against four documented `Messageable` guild types
  (`TextChannel`, `VoiceChannel`, `StageChannel`, `Thread`). This
  matches the `discord.py 2.7.1` type hierarchy exactly and does not
  rely on duck typing, private attributes, or undocumented behavior.
  The `channel.history(limit=N)` call follows the standard documented
  API.
- Recommendation: None.

### Finding 7: No compatibility shims or backward-compat hacks

- Risk level: LOW
- Description: The proposal explicitly excludes compatibility shims in
  its anti-scope section. No adapter layers, feature flags, or
  deprecation wrappers are introduced. The command follows the identical
  registration and handler pattern used by all existing commands.
- Recommendation: None.
