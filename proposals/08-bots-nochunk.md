# Proposal: Bots Command — Verify No Manual Chunking

Date: 2026-04-13

## Status: NO CHANGES REQUIRED

## Goal

Verify the original goal for `cmd_bots`: remove any `guild.chunk()`
dependency from bot enumeration so the command does not manually chunk
the guild just to list bots.

This proposal is a verification pass only. It does not propose any code
changes.

## Summary

The current implementation already satisfies the stated goal.
`fetch_bots()` reads the cached `guild.members` collection, filters by
`member.bot`, and raises a `CLIError` when the member cache is fully
empty while `guild.member_count` indicates the guild has members.

No explicit `guild.chunk()` calls exist anywhere in `discord_cli.py`,
and no other manual member-fetching path is used for the `bots`
command.

## Architecture

The current `bots` path is already aligned with the desired design:

- `run_gateway_command()` connects the one-shot Discord client and hands
  the resolved guild to the command handler.
- `fetch_bots()` performs a cache read over `guild.members`.
- The handler filters cached members with `getattr(member, "bot",
  False)`.
- The handler returns JSON-safe bot entries via
  `serialize_bot_member(...)`.
- If the member cache is fully empty but `guild.member_count` is
  non-zero, the handler raises `CLIError("intent_error", ...)` instead
  of attempting a manual chunk.

Current implementation:

```python
async def fetch_bots(guild: discord.Guild, _: argparse.Namespace) -> dict[str, Any]:
    members = list(getattr(guild, "members", []))
    if not members and getattr(guild, "member_count", 0):
        raise CLIError(
            "intent_error",
            "Guild member cache is empty; enable the members intent for this bot",
        )

    bots = [serialize_bot_member(member) for member in members if getattr(member, "bot", False)]
    return {
        "count": len(bots),
        "bots": bots,
    }
```

## What Was Verified

- No `guild.chunk()` calls exist anywhere in `discord_cli.py`.
- No explicit `guild.fetch_members()` calls exist anywhere in
  `discord_cli.py`.
- No explicit `guild.query_members()` calls exist anywhere in
  `discord_cli.py`.
- `fetch_bots()` enumerates bots from cached `guild.members`, not from a
  manual fetch path.
- `fetch_bots()` raises a clear `CLIError` when the member cache is
  empty and `guild.member_count` is non-zero.
- The command returns a simple cache-derived payload:

```json
{
  "count": 12,
  "bots": []
}
```

## Why No Changes

The original task was to remove a manual `guild.chunk()` call from bot
enumeration. The current implementation already does that.

There is no repo-local manual chunking logic to delete, and replacing
the current handler would not improve behavior. Any broader discussion
about Discord client's startup cache population is separate from this
verification target and is not required to satisfy the original goal.

## Tradeoffs

- Keeping the current design means `bots` remains dependent on the
  member cache being populated before the handler runs.
- The current error path is explicit for a fully empty cache, which is
  preferable to silently attempting a manual chunk in this command.
- This verification pass preserves the existing one-shot CLI behavior
  and avoids unnecessary churn in a code path that already meets the
  stated requirement.

## Anti-scope

This proposal explicitly does not include:

- changing `fetch_bots()`
- changing `run_gateway_command()`
- disabling or reworking framework-level startup cache behavior
- adding fallback member fetch logic
- adding partial-cache detection
- changing bot output fields or JSON shape
- modifying any other command
- any Discord write or mutation behavior

## Decision

Do not change code. Record that `fetch_bots()` already satisfies the
goal of avoiding manual `guild.chunk()` for bot enumeration, and treat
this task as closed by verification.
