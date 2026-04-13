# Research: cmd_bots chunking removal in discord_cli.py

## Task
Investigate the `fetch_bots` function in `/home/nes/discord/discord_cli.py` (lines 371-383) to determine whether it calls `guild.chunk()` or otherwise depends on chunking to enumerate bot members.

## Context
The original session had a `cmd_bots` function that called `guild.chunk()` before listing bots. The goal was to rework it so it no longer depends on chunking — instead using the already-available guild member cache, and failing with a clear error if the cache is empty.

## What to investigate
1. Read `discord_cli.py` and find the `fetch_bots` function
2. Check whether it calls `guild.chunk()` anywhere
3. Check whether it accesses `guild.members` (cached) vs fetching members
4. Check what happens when the member cache is empty
5. Document what the current implementation does and whether any chunking dependency exists

## Output
Write your findings to `research/08-bots-nochunk.md` with:
- Current implementation analysis
- Whether `guild.chunk()` is called (anywhere in the file, not just fetch_bots)
- Whether the current implementation already satisfies the goal of no-chunking bot enumeration
- Any remaining concerns
