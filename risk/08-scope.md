# Scope Risk Assessment: Bots No-Chunking Verification

## Risk Level: LOW

## Findings

1. **Proposal matches the original goal** (no issue)
   The stated goal was to verify that `fetch_bots()` does not call
   `guild.chunk()` for bot enumeration. The proposal confirms this by
   showing the handler reads cached `guild.members`, filters by
   `member.bot`, and raises `CLIError` on an empty cache rather than
   attempting a manual chunk. The research independently verified no
   `guild.chunk()`, `guild.fetch_members()`, or `guild.query_members()`
   calls exist anywhere in `discord_cli.py`.

2. **No scope creep detected** (no issue)
   The proposal is a verification pass that proposes zero code changes.
   It does not introduce new helpers, new flags, new error paths, or
   refactors. The "Status: NO CHANGES REQUIRED" header and the decision
   section both reinforce that this is a close-by-verification outcome.
   This is the narrowest possible scope for a proposal.

3. **Anti-scope is thorough and reasonable** (no issue)
   The anti-scope section lists 8 explicit exclusions covering changes
   to `fetch_bots()`, `run_gateway_command()`, framework-level cache
   behavior, fallback fetch logic, partial-cache detection, output
   shape changes, other commands, and write/mutation behavior. Each
   exclusion corresponds to a plausible direction that a reviewer might
   ask about, particularly the framework startup-chunking concern
   raised in the research.

4. **Research nuance handled correctly** (no issue)
   The research identified that discord.py's `chunk_guilds_at_startup`
   default still causes implicit startup chunking. The proposal
   correctly scopes this out: the original goal was about removing
   explicit `guild.chunk()` from `fetch_bots()`, not about disabling
   the framework's automatic cache population. The needs synthesis
   confirms this is a framework-level behavior that benefits all
   member-dependent commands. The proposal avoids inflating scope to
   address a concern outside the verification target.

5. **No unaddressed gaps** (no issue)
   The research and needs documents identify three verified properties
   (no explicit chunk call, cache-based enumeration, clear empty-cache
   error). The proposal addresses all three. The partial-cache edge
   case noted in the research is acknowledged implicitly via the
   anti-scope exclusion of "partial-cache detection" rather than being
   silently ignored.

## Recommendation

Accept. The proposal is correctly scoped as a verification-only pass.
It confirms the existing implementation satisfies the original goal,
proposes no changes, and explicitly excludes adjacent concerns that
could have inflated scope.
