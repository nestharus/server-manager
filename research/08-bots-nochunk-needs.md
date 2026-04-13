# Synthesis: Bots Command No-Chunking Needs

## What the research found

The `fetch_bots` function in `discord_cli.py` (lines 371-383) already:
- Does NOT call `guild.chunk()`
- Uses cached `guild.members` (a proxy over `self._members.values()`)
- Raises `CLIError("intent_error", ...)` when the cache is fully empty but `guild.member_count` is non-zero
- Filters cached members by `member.bot` and returns the result

No explicit chunking calls exist anywhere in `discord_cli.py`.

## Humility-specific context

- The guild has ~88 members and 12 bots
- With `Intents.members=True`, discord.py 2.7.1 defaults to `chunk_guilds_at_startup=True`, so members are already cached by the time `on_ready` fires
- The CLI is a one-shot tool (connect → run command → disconnect), so startup chunking for 88 members is fast enough to not be a problem
- The GATEWAY_TIMEOUT_SECONDS=30 wrapper from P0006 prevents hanging

## Gap analysis

The original task was to "rework the bots command so it no longer calls `guild.chunk()` just to list bots." The current implementation already satisfies this:
1. No `guild.chunk()` call ✓
2. Uses cached members ✓
3. Fails with clear error if cache is empty ✓

The research notes that startup chunking still happens implicitly via discord.py defaults, but this is not a `fetch_bots` concern — it's a framework-level behavior that benefits all member-dependent commands. Disabling it would break `fetch_bots` (empty cache) without compensating logic.

## Conclusion

**No changes needed.** The current `fetch_bots` implementation already satisfies the goal. The P0006 implementation built it correctly from the start.

## Open questions

None — this is a verification pass.
