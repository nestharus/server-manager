# Scope Risk Assessment: bot-activity

## Risk Level: LOW

## Findings

1. **Proposal aligns with the stated need** (no issue)
   The need is a bot footprint audit for consolidation: determine which
   bots have visible message footprints across the guild's channels to
   separate actively used bots from merely installed ones. The proposal
   delivers exactly this — a read-only command that scans history-capable
   channels for messages from a specific bot ID, returns per-channel
   counts, aggregate last-seen timestamps, and a small sample set. Every
   output field maps directly to an audit question: "where does this bot
   post?" (per_channel), "is it still active?" (last_seen), "how much
   does it post?" (total_messages_seen), "what does it do?" (samples).

2. **No unnecessary features detected** (no issue)
   The command accepts two arguments: a required `bot_id` and an
   optional `--per-channel-limit`. Both are justified by the needs
   synthesis, which confirms the original session used limits of 100,
   500, and 2000. The proposal does not add channel filtering flags,
   sample count flags, sorting options, output format switches, or any
   other configurability beyond what the audit use case requires. The
   hardcoded sample cap of 10 is a reasonable default that avoids
   introducing another flag while keeping the payload compact.

3. **Complexity is proportionate** (no issue)
   The implementation adds one handler function (`fetch_bot_activity`),
   one small predicate (`is_history_capable_channel`), and standard
   parser/registration boilerplate. It introduces no new infrastructure,
   no new dependencies, no new serializers, no new error types, and no
   changes to the gateway wrapper or existing commands. The predicate
   helper is a type-check one-liner that prevents `.history()` calls on
   categories and forum containers — a necessary guard, not an
   abstraction for its own sake.

4. **Follows existing CLI patterns exactly** (no issue)
   The handler uses the same `async def fetch_*(guild, args)` signature
   as every other command. Registration goes through `command_specs()`
   and `build_parser()` identically to existing commands. Serialization
   reuses `serialize_message`, `serialize_channel`, and `iso_or_none`.
   Error handling uses `CLIError` with the established pattern. Channel
   iteration uses `combined_channels(guild)`. No new patterns are
   introduced.

5. **Intentional divergence from MAX_READ_LIMIT is justified** (LOW risk)
   The `read` command clamps `--limit` to `MAX_READ_LIMIT` (200). The
   proposal recommends not clamping `--per-channel-limit` to this
   constant, allowing values like 500 or 2000. The rationale is sound:
   `read` is an interactive message dump where large payloads are
   unwieldy, while `bot-activity` is an audit command where deeper scan
   windows are the primary value. The needs synthesis confirms the
   original session used `--per-channel-limit 2000`. This is a
   deliberate, documented design choice rather than an oversight.

6. **Upper bound of 10000 is well-scoped** (no issue)
   The revised proposal adds `args.per_channel_limit <= 10000` as a
   hard ceiling, enforced via `CLIError` following the existing
   validation pattern (`fetch_read` rejects `--limit <= 0` the same
   way). The rationale is clearly stated: values like `100000` would
   produce thousands of paginated API requests across 40+ channels with
   no practical benefit over the cap. The bound is high enough to
   accommodate the deepest audit windows confirmed in the needs
   synthesis (2000) with substantial headroom, while preventing
   effectively-unbounded scans. The revision is minimal and targeted —
   it addresses exactly the concern flagged by the prior shortcut
   assessment without introducing any additional features or complexity.

7. **Anti-scope section is thorough** (no issue)
   The proposal explicitly excludes 13 categories of work including
   mutations, new dependencies, full-history scans, archived-thread
   discovery, forum reads, new serializers, additional CLI flags, shim
   layers, caching, and webhook-vs-bot disambiguation. Each exclusion
   corresponds to a plausible extension that could have inflated scope.
   The tradeoffs section acknowledges limitations (bounded scan window,
   no archived threads, silent Forbidden skipping) without proposing
   fixes, deferring them to future iterations if needed. The upper bound
   addition does not conflict with any anti-scope item.

8. **Silent Forbidden skipping is acceptable for v1** (LOW risk)
   Silently skipping channels where `discord.Forbidden` is raised means
   the output could reflect partial coverage without the caller knowing.
   However, the needs synthesis confirms the bot has Administrator
   permissions on the target guild, making this a defensive guard rather
   than an expected path. The proposal documents this as a known
   tradeoff and identifies a `skipped` field as the clean extension
   point. This is proportionate for a v1 audit tool.

## Recommendation

Accept. The proposal is tightly scoped to the bot footprint audit use
case, follows existing CLI patterns without introducing new
infrastructure, and explicitly excludes adjacent concerns that could
have expanded scope. The revised upper bound of 10000 on
`--per-channel-limit` cleanly addresses the prior shortcut assessment's
MEDIUM finding without expanding scope — the validation uses the
existing `CLIError` pattern and the ceiling is well-justified. No
findings require changes before implementation.
