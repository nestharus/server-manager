# Research: Dispatch Wiring Verification for `bot-activity`

## Scope

This note documents the verification of the `bot-activity` command
dispatch wiring in `discord_cli.py`. It confirms that the dispatch
registration implemented in P0040 correctly connects the parsed
`bot-activity` subcommand to the `fetch_bot_activity` handler.

This is a verification-only research pass. No new APIs, libraries, or
patterns are investigated because no code changes are needed.

## 1. command_specs() registration

The `bot-activity` handler is registered in `command_specs()` at
[discord_cli.py](/home/nes/discord/discord_cli.py:524):

```python
"bot-activity": fetch_bot_activity,
```

The full `command_specs()` dictionary (lines 517-527) maps subcommand
names to their async handler functions:

```python
def command_specs() -> dict[str, Callable[[discord.Guild, argparse.Namespace], Awaitable[dict[str, Any]]]]:
    return {
        "overview": fetch_overview,
        "bots": fetch_bots,
        "channels": fetch_channels,
        "find-channel": fetch_find_channel,
        "read": fetch_read,
        "bot-activity": fetch_bot_activity,
        "integrations": fetch_integrations,
        "roles": fetch_roles,
    }
```

### Verification against proposal (proposals/09-bot-activity.md)

| Proposal requirement | Code | Status |
| --- | --- | --- |
| Key `"bot-activity"` in `command_specs()` | `"bot-activity": fetch_bot_activity` | Matches |
| Value is `fetch_bot_activity` function | `fetch_bot_activity` at line 446 | Matches |
| Handler signature `(guild, args) -> dict` | `async def fetch_bot_activity(guild: discord.Guild, args: argparse.Namespace) -> dict[str, Any]` | Matches |

All dispatch elements match the proposal exactly.

## 2. run_command() dispatch flow

The `run_command()` function at [discord_cli.py](/home/nes/discord/discord_cli.py:530-539)
performs the dispatch:

```python
async def run_command(args: argparse.Namespace) -> int:
    command = args.command
    handler = command_specs()[command]
    _, guild_id = get_config()

    async def gateway_handler(_: discord.Client, guild: discord.Guild) -> dict[str, Any]:
        return await handler(guild, args)

    data = await run_gateway_command(gateway_handler)
    print_json(success_payload(command, guild_id, data))
```

The dispatch chain is:

1. `args.command` is set to `"bot-activity"` by argparse (from the
   subparser name)
2. `command_specs()["bot-activity"]` resolves to `fetch_bot_activity`
3. `gateway_handler` wraps the call with guild context
4. `run_gateway_command` establishes the Discord gateway connection
5. `fetch_bot_activity(guild, args)` executes and returns the result
6. `success_payload` wraps the result for JSON output

## 3. Parser-to-dispatch connection

The parser wiring (verified in P0041) sets `func=run_command` via
`set_defaults`. When argparse parses `bot-activity`, it:

1. Sets `args.command = "bot-activity"` (from the subparser name)
2. Sets `args.func = run_command` (from `set_defaults`)
3. The main function calls `args.func(args)` which invokes `run_command`
4. `run_command` uses `args.command` to look up the handler in
   `command_specs()`

This two-step dispatch (parser → `run_command` → `command_specs()`) is
the standard pattern used by all subcommands in `discord_cli.py`.

## 4. Handler function exists and is callable

`fetch_bot_activity` is defined at [discord_cli.py](/home/nes/discord/discord_cli.py:446):

```python
async def fetch_bot_activity(guild: discord.Guild, args: argparse.Namespace) -> dict[str, Any]:
```

The function is an async coroutine that accepts `(guild, args)` and
returns `dict[str, Any]`, matching the type signature expected by
`command_specs()` and `run_command()`.

## 5. Conclusion

The `bot-activity` dispatch wiring is correctly implemented. The
`command_specs()` dictionary maps `"bot-activity"` to `fetch_bot_activity`,
and `run_command()` correctly resolves and invokes the handler through
the gateway. No changes are needed.
