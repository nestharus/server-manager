# Audit Risk Assessment: Bots No-Chunking Verification

## Risk Level: LOW

## Findings

1. **Verification confirmed: `fetch_bots()` does not call `guild.chunk()` (severity: none)**
   The `fetch_bots()` function at `discord_cli.py:371-383` reads from `guild.members` via `getattr(guild, "members", [])` and filters for `member.bot`. No call to `guild.chunk()`, `guild.query_members()`, `guild.fetch_members()`, or any other member-fetching API exists in the function or anywhere in `discord_cli.py`. The proposal's claim is correct.

2. **Cache-only behavior depends on `members` intent being enabled (severity: low, already mitigated)**
   The `guild.members` cache is populated from the `GUILD_CREATE` gateway event only when the `members` privileged intent is enabled. `build_intents()` at line 70 sets `intents.members = True`, satisfying this requirement. Additionally, `fetch_bots()` includes a defensive check: if `members` is empty but `member_count` is non-zero, it raises a `CLIError("intent_error", ...)` rather than silently returning an empty list. This is correct behavior.

3. **No code changes proposed (severity: none)**
   This is a verification-only proposal. No files are created, modified, or deleted. No new behavior is introduced. The existing code is left unchanged.

4. **Cache completeness assumption is documented but worth noting (severity: informational)**
   Without chunking, the member cache contains only members delivered in the `GUILD_CREATE` payload. For large guilds (>250 members without `GUILD_MEMBERS` chunk requests), this cache may be incomplete — some bot members could be absent from the output. This is an existing behavior characteristic, not a risk introduced by this proposal. The proposal correctly identifies this as the current state and does not attempt to change it.

5. **No new network surface, write operations, or data exposure (severity: none)**
   Since no code changes are made, no new API calls, rate-limit exposure, error paths, or data leakage vectors are introduced. The security and reliability posture of `discord_cli.py` is unchanged.

## Recommendation

**Accept.** This is a zero-change verification pass. The audit confirms that `fetch_bots()` relies exclusively on the cached `guild.members` list with no chunking call, exactly as claimed. The `members` intent is enabled, and a defensive empty-cache check is already in place. No code is modified, so no new risk is introduced. The only informational note — that the cache may be incomplete for large guilds without chunking — is an existing characteristic, not a regression.
