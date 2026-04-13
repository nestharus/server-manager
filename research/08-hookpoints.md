# Hookpoint Research: Bots No-Chunking Verification

Date: 2026-04-13

## Status: NO CHANGES — NO NEW HOOKPOINTS NEEDED

This proposal is a verification-only pass. The current `bots` command
already has the hookpoints it needs.

## 1. `fetch_bots()` location and signature

The current handler is:

- `async def fetch_bots(guild: discord.Guild, _: argparse.Namespace) -> dict[str, Any]`
  at [discord_cli.py](/home/nes/discord/discord_cli.py:371)

The implementation reads `guild.members`, filters on `member.bot`, and
returns:

- `{"count": len(bots), "bots": bots}`

It does not add any manual chunking hookpoint.

## 2. Serialization helper

`fetch_bots()` serializes each bot via:

- `serialize_bot_member(member: Any) -> dict[str, Any]` at
  [discord_cli.py](/home/nes/discord/discord_cli.py:122)

That helper already provides the existing output contract for each bot
entry, so no new serializer hookpoint is needed.

## 3. Command registration

The command is already wired into both dispatch and parsing.

Dispatch registration:

- `command_specs()` at [discord_cli.py](/home/nes/discord/discord_cli.py:443)
  includes `"bots": fetch_bots`

Parser registration:

- `build_parser()` at [discord_cli.py](/home/nes/discord/discord_cli.py:468)
  includes `("bots", "List bot members")` in the no-argument command
  loop

So the existing command path is already:

- parser subcommand
- `run_command()`
- `command_specs()["bots"]`
- `fetch_bots()`

## 4. Test coverage

Current coverage in [tests/test_discord_cli.py](/home/nes/discord/tests/test_discord_cli.py:367):

- `test_build_parser_recognizes_all_contract_subcommands`
  ([tests/test_discord_cli.py](/home/nes/discord/tests/test_discord_cli.py:367))
  verifies `"bots"` is a registered subcommand
- `test_bots_handler_filters_members_by_bot_flag`
  ([tests/test_discord_cli.py](/home/nes/discord/tests/test_discord_cli.py:426))
  verifies the public async handler exists and returns only bot members

Current test coverage confirms the command is exposed and that the
handler filters cached members by bot flag. There is not separate test
coverage today for the empty-cache `CLIError` branch.

## 5. Conclusion

No new hookpoints are needed.

This proposal does not require:

- changing `fetch_bots()`
- adding a new serializer
- changing `command_specs()`
- changing `build_parser()`
- adding a new command path

The existing implementation already matches the verification target for
this hookpoint pass.
