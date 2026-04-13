# Shortcut Risk Assessment: bot-activity

## Overall: LOW

No blocking issues. Two findings warrant attention during implementation
but neither requires proposal changes before proceeding.

## Findings

### Finding 1: No upper bound on `--per-channel-limit`

- Risk level: MEDIUM
- Description: The proposal validates `per_channel_limit > 0` but
  explicitly recommends no upper clamp. A value like `100000` is
  effectively `limit=None` in terms of API load. With 40+ scannable
  channels, that translates to thousands of paginated `/messages`
  requests per run. `discord.py` handles rate-limit backoff internally,
  so this will not cause 429 bans, but total wall-clock time could
  stretch to minutes or longer with no feedback to the caller.
- Recommendation: Not a proposal-level issue — the tradeoff is
  intentional for audit depth. During implementation, consider logging a
  one-line stderr warning when `per_channel_limit > 1000` so the caller
  knows the scan may be slow. No hard clamp needed; the warning is
  sufficient.

### Finding 2: `Forbidden` raised during async iteration, not at call time

- Risk level: LOW
- Description: The proposal says to "catch `discord.Forbidden` around
  each `channel.history(...)` call." In `discord.py 2.7.1`,
  `channel.history()` returns an async iterator; the actual HTTP request
  fires on the first `__anext__()`, not at construction time. A
  `Forbidden` can also surface on any subsequent page if permissions
  change mid-scan. The catch must therefore wrap the full `async for`
  loop (or the list comprehension materializing it), not just the
  `.history()` call itself.
- Recommendation: Implementation detail only. Wrap the entire iteration
  in the try/except, e.g.:

  ```python
  try:
      messages = [m async for m in channel.history(limit=...)]
  except discord.Forbidden:
      continue
  ```

  The proposal's intent is correct; just ensure the scope of the catch
  is the iteration, not the iterator construction.

### Finding 3: Silent `Forbidden` skipping hides scan coverage gaps

- Risk level: LOW
- Description: When the bot lacks `read_message_history` on a channel,
  that channel is silently dropped from results. The caller has no way
  to distinguish "bot was never active there" from "we couldn't look."
  This is explicitly acknowledged in the proposal's tradeoff section
  with a clean extension path (future `skipped` field).
- Recommendation: Acceptable for v1. The extension path is
  backward-compatible. No action needed before implementation.

### Finding 4: `combined_channels` excludes archived threads

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

### Finding 5: No API misuse or undocumented behavior

- Risk level: LOW
- Description: The `is_history_capable_channel` predicate uses
  `isinstance()` against four documented `Messageable` guild types
  (`TextChannel`, `VoiceChannel`, `StageChannel`, `Thread`). This
  matches the `discord.py 2.7.1` type hierarchy exactly and does not
  rely on duck typing, private attributes, or undocumented behavior.
  The `channel.history(limit=N)` call follows the standard documented
  API.
- Recommendation: None.

### Finding 6: No compatibility shims or backward-compat hacks

- Risk level: LOW
- Description: The proposal explicitly excludes compatibility shims in
  its anti-scope section. No adapter layers, feature flags, or
  deprecation wrappers are introduced. The command follows the identical
  registration and handler pattern used by all existing commands.
- Recommendation: None.
