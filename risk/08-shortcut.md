# Shortcut Risk Assessment: Bots No-Chunking Verification

## Risk Level: LOW

## Findings

1. **"No changes needed" conclusion is justified** (NONE)
   The original task was to remove manual `guild.chunk()` calls from bot
   enumeration. Code inspection confirms: no `guild.chunk()`,
   `guild.fetch_members()`, or `guild.query_members()` calls exist
   anywhere in `discord_cli.py`. `fetch_bots()` reads only
   `guild.members`, which is a cache proxy (`self._members.values()`),
   not an API fetch. The verification conclusion is correct — there is no
   manual chunking to remove.

2. **Implicit startup chunking acknowledged but correctly scoped out** (LOW)
   The research identifies that `run_gateway_command()` creates a
   `discord.Client` with `Intents.members=True`, which causes discord.py
   2.7.1 to default `chunk_guilds_at_startup=True`. This means the
   framework still chunks at startup before `on_ready` fires. The
   proposal explicitly scopes this out as a framework-level behavior
   separate from the `fetch_bots` verification target. This is a
   reasonable boundary: disabling startup chunking would break
   `fetch_bots` (empty cache, triggering the `CLIError`) without
   compensating logic. The research notes this as a remaining concern,
   and the proposal does not hide it. Not a shortcut — it is a conscious
   scope decision documented in both the research and proposal.

3. **Partial-cache scenario unaddressed — inherited** (LOW)
   Same issue as finding #2 in risk/05-shortcut. If the member cache is
   partially populated (e.g., for a guild exceeding the 1000-member
   chunking threshold), `fetch_bots()` would return an incomplete bot
   list without error. The empty-cache check only catches a fully empty
   cache. This is an inherited limitation from the original
   implementation, not something introduced or worsened by this proposal.
   Acceptable for the current single-guild scope (~88 members).

4. **Error message references intent enablement, not cache population** (LOW)
   The `CLIError` message says "enable the members intent for this bot",
   but `build_intents()` already enables `Intents.members`. If a future
   change disabled startup chunking, the empty-cache error would fire
   with a misleading message — the intent would be enabled but the cache
   unpopulated. This is a minor inaccuracy in the existing code, not
   something introduced by this proposal. Flagged for awareness only.

5. **No deferred work or hidden TODOs** (NONE)
   The proposal does not create follow-up items, placeholder stubs, or
   deferred work. It closes the verification task cleanly. The anti-scope
   list is explicit and well-bounded.

## Recommendation

**Accept.** The verification conclusion is sound — `fetch_bots()` does
not perform manual chunking and the code matches the stated goal. The
proposal is transparent about the implicit startup chunking dependency
and correctly scopes it as a framework behavior. All findings are LOW or
NONE and are inherited from the existing codebase. No changes are
required before closing this task.
