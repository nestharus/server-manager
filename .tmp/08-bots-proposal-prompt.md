# Proposal: Bots Command No-Chunking Verification

## Context
Read `research/08-bots-nochunk.md` and `research/08-bots-nochunk-needs.md`.

The original task was to rework `cmd_bots` so it no longer calls `guild.chunk()` just to list bots. Research found that the current `fetch_bots` function (discord_cli.py lines 371-383) already:
- Does NOT call `guild.chunk()`
- Uses cached `guild.members`
- Raises CLIError when cache is empty
- No chunking calls exist anywhere in discord_cli.py

The synthesis concluded no changes are needed — this is a verification pass.

## Task
Write a proposal to `proposals/08-bots-nochunk.md` that:
1. States the original goal (remove guild.chunk() from bot enumeration)
2. Documents that the current implementation already satisfies this goal
3. Confirms no code changes are proposed
4. Lists what was verified (no chunk calls, cache-based enumeration, error handling)
5. Notes any anti-scope (things explicitly NOT proposed)

Use the standard proposal format with architecture, tradeoffs, and anti-scope sections.
