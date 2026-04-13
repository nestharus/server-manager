# Research: Bots Command Without Explicit Chunking

## Scope

This note checks whether the current `bots` implementation in
`discord_cli.py` still depends on guild member chunking.

Evidence below comes from the repo source and the installed
`discord.py` in this repo's `.venv` (`2.7.1`).

Primary sources consulted:

- [discord_cli.py](/home/nes/discord/discord_cli.py:307)
- [client.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/client.py:216)
- [state.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/state.py:240)
- [guild.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/guild.py:997)

## Findings

### Current implementation analysis

`fetch_bots()` is currently:

- reading `guild.members` into a local list
  ([discord_cli.py](/home/nes/discord/discord_cli.py:371))
- raising `CLIError("intent_error", ...)` when that cache is empty but
  `guild.member_count` is truthy
  ([discord_cli.py](/home/nes/discord/discord_cli.py:373))
- filtering cached members by `member.bot`
  ([discord_cli.py](/home/nes/discord/discord_cli.py:379))
- returning `{"count": len(bots), "bots": bots}`
  ([discord_cli.py](/home/nes/discord/discord_cli.py:380))

This means the function itself does not fetch members and does not call
`guild.chunk()`. It is strictly a cache read over `guild.members`.

`Guild.members` in `discord.py` is just a proxy over the internal member
cache (`self._members.values()`), not an API fetch
([guild.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/guild.py:997)).

### `guild.chunk()` usage in `discord_cli.py`

There are no explicit `guild.chunk()` calls anywhere in
`discord_cli.py`.

There are also no explicit calls to:

- `guild.fetch_members()`
- `guild.query_members()`
- websocket `request_chunks()`

So at the repo code level, the file no longer performs manual chunking.

### Empty-cache behavior

When `guild.members` is empty and `guild.member_count` is non-zero,
`fetch_bots()` raises:

`CLIError("intent_error", "Guild member cache is empty; enable the members intent for this bot")`

That is a clear failure path for the fully-empty-cache case.

If both `guild.members` and `guild.member_count` are empty/falsey, the
handler returns zero bots instead of failing.

If the member cache is partially populated, the handler does not detect
that. Any non-empty `guild.members` list is accepted and filtered.

### Hidden startup chunking dependency

The important nuance is outside `fetch_bots()` itself.

`run_gateway_command()` constructs the client as:

- `discord.Client(intents=build_intents())`
  ([discord_cli.py](/home/nes/discord/discord_cli.py:311))

`build_intents()` enables `Intents.members`
([discord_cli.py](/home/nes/discord/discord_cli.py:67)).

In installed `discord.py` `2.7.1`, `Client` defaults
`chunk_guilds_at_startup` to `True` when `Intents.members` is `True`
([client.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/client.py:222)).
The state layer sets:

- `self._chunk_guilds = options.get('chunk_guilds_at_startup', intents.members)`
  ([state.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/state.py:240))

Before firing `ready`, discord.py checks whether each guild needs
chunking and, if so, starts chunk requests and waits for them in the
ready delay path
([state.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/state.py:532),
 [state.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/state.py:606)).

So while `discord_cli.py` does not explicitly call `guild.chunk()`, the
current runner still appears to rely on discord.py's automatic startup
chunking unless `chunk_guilds_at_startup=False` is passed.

## Conclusion

The current `fetch_bots()` implementation already satisfies part of the
goal:

- no explicit `guild.chunk()` call
- cache-based enumeration via `guild.members`
- clear error when the cache is fully empty

However, the command path does not fully satisfy the stronger
"no-chunking bot enumeration" goal yet, because
`run_gateway_command()` still creates a default `discord.Client` with
`Intents.members=True`, which in `discord.py 2.7.1` implies automatic
startup chunking unless explicitly disabled.

## Remaining concerns

- The repo no longer has a manual chunk call, but it still likely pays
  for implicit startup chunking before `on_ready()` runs.
- The empty-cache check only catches a totally empty cache. A partial
  cache would produce a partial bot list with no error.
- The current error message says to "enable the members intent", but in
  this codebase the intent is already enabled in `build_intents()`.
  An empty cache under a future no-startup-chunk design would more
  likely mean "member cache was not populated" rather than "intent is
  disabled".
