# Hookpoint Research: `bot-activity` Command

Date: 2026-04-13

## 1. Primary handler hookpoint

The new handler should follow the existing async guild-handler block in
[discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:352).

Recommended insertion point:

- add `fetch_bot_activity(guild, args)` immediately after
  `fetch_read()` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:409)
  and before `fetch_integrations()` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:427)

That is the cleanest placement because `bot-activity` is the other
history-reading command. It keeps the channel/history inspection handlers
grouped together:

- `fetch_channels()` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:386)
- `fetch_find_channel()` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:393)
- `fetch_read()` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:409)
- new `fetch_bot_activity()`

Reusable code for the handler:

- `combined_channels()` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:246)
  for the scan surface
- `serialize_message()` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:187)
  for `samples`
- `serialize_channel()` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:144)
  as the source of `channel_id` and `channel_name`
- `iso_or_none()` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:104)
  for aggregate and per-channel `last_seen`
- `CLIError` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:25)
  for `--per-channel-limit` validation

Parallel reference code:

- `fetch_read()` is the closest reference for:
  - numeric argument validation
  - `channel.history(...)`
  - message collection
  - response shaping
- `fetch_find_channel()` is the closest reference for:
  - iterating `combined_channels(guild)`
  - matching across channels and threads
  - serializing channel objects in a compact result list
- `fetch_channels()` is the reference for treating channels and threads
  as one inspection domain while still preserving channel/thread identity

What does not exist yet and must be added inside the new handler:

- `args.per_channel_limit` validation
- per-channel history scan loop across `combined_channels(guild)`
- filtering on `message.author.id == args.bot_id`
- aggregate `total_messages_seen`
- aggregate `last_seen`
- compact `per_channel` summary entries
- fixed-cap recent `samples` collection and global sort
- per-channel `discord.Forbidden` skip behavior

Answer to question 1:

- `fetch_bot_activity()` should go after `fetch_read()` and before
  `fetch_integrations()`.

## 2. Helper hookpoint

`is_history_capable_channel()` belongs with the existing helper block,
not inline next to the handler.

Recommended insertion point:

- add `is_history_capable_channel(channel)` between `channel_kind()` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:303)
  and `run_gateway_command()` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:307)

Why this location fits:

- it is a pure channel predicate, like the nearby channel helpers
- it has no async behavior and no handler-specific state
- it is logically part of the same helper cluster as:
  - `combined_channels()`
  - `sort_channel_matches()`
  - `resolve_channel()`
  - `channel_kind()`

Answer to question 2:

- place `is_history_capable_channel()` with the other helpers, not near
  the handler body

## 3. Reusable serializers and helper outputs

Reusable as-is:

- `serialize_message()` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:187)
  for `samples`
- `serialize_channel()` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:144)
  as the source for compact per-channel identity fields

Reusable indirectly through `serialize_message()`:

- `serialize_author()` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:135)
- `serialize_attachment()` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:169)
- `serialize_embed()` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:179)

Reusable helper, not a serializer:

- `iso_or_none()` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:104)
  for both top-level and per-channel timestamps

Not needed for this proposal:

- `serialize_member_identity()`
- `serialize_bot_member()`
- `serialize_integration()`
- `serialize_role()`

Answer to question 3:

- the directly reusable serializers are `serialize_message()` and
  `serialize_channel()`

## 4. `command_specs()` insertion point

The dispatch table is at
[discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:443).

Recommended insertion point:

- add `"bot-activity": fetch_bot_activity,` immediately after
  `"read": fetch_read,` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:449)
  and before `"integrations": fetch_integrations,` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:450)

This keeps command registration aligned with handler locality:

- channel inspection commands first
- then history-reading commands
- then integrations and roles

Answer to question 4:

- put the new entry after `"read": fetch_read`

## 5. `build_parser()` insertion point

`build_parser()` starts at
[discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:468).

The new command does not belong in the simple no-argument parser loop at
[discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:472),
because it has:

- one required positional argument: `bot_id`
- one optional argument: `--per-channel-limit`

Recommended insertion point:

- add a dedicated `bot_activity_parser = subparsers.add_parser(...)`
  block immediately after the existing `read_parser` block at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:486)
  and before `return parser` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:491)

Answer to question 5:

- add the new subparser after the `read` subparser block, not inside the
  no-argument command loop

## 6. Existing patterns to reuse or tighten

There is one duplication pattern worth avoiding while adding this
command.

Current duplication:

- `fetch_find_channel()` manually computes channel kind inline at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:395)
- `fetch_read()` repeats the same inline logic at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:420)

But the file already has:

- `channel_kind()` at
  [discord_cli.py](/home/nes/discord/worktrees/bot-activity/discord_cli.py:303)

Recommendation:

- new `bot-activity` code should call `channel_kind(channel)` and then
  pass that into `serialize_channel(...)` instead of adding a third copy
  of the `"thread" if ... else "channel"` expression

Second duplication to avoid:

- do not add a new compact channel serializer just for `per_channel`
- call `serialize_channel(...)` once, then flatten out the two fields the
  proposal needs: `id` and `name`

Third duplication to avoid:

- do not add a second channel-discovery path
- use `combined_channels(guild)` and filter it with
  `is_history_capable_channel(...)` as proposed

Answer to question 6:

- yes: the inline channel-kind logic should be normalized through
  `channel_kind()`, and the new handler should reuse
  `serialize_channel(...)` instead of inventing a second summary
  serializer

## Conclusion

The clean mapping is:

1. Add `is_history_capable_channel()` in the helper block just before
   `run_gateway_command()`.
2. Add `fetch_bot_activity()` after `fetch_read()`.
3. Reuse `combined_channels()`, `serialize_message()`,
   `serialize_channel()`, `iso_or_none()`, `channel_kind()`, and
   `CLIError`.
4. Register `"bot-activity"` in `command_specs()` after `"read"`.
5. Add a dedicated `bot-activity` parser block after the `read` parser.
