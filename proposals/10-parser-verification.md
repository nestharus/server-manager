# Proposal: Parser Wiring Verification for `bot-activity`

Date: 2026-04-13

## Goal

Verify that the `bot-activity` argparse subparser wiring in
`discord_cli.py` matches the specification in `proposals/09-bot-activity.md`.

This proposal is verification only. It does not include implementation
code because no code changes are needed.

## Summary

The research and synthesis phases confirm that all parser elements are
correctly implemented:

- Subcommand name: `bot-activity`
- Positional argument: `bot_id` with `type=int`
- Optional argument: `--per-channel-limit` with `type=int, default=100`
- Default handler routing: `set_defaults(func=run_command)`
- Placement: after `read` subparser, before `return parser`

## Verification Result

| Element | Expected (proposal) | Actual (code) | Match |
| --- | --- | --- | --- |
| Subcommand name | `"bot-activity"` | `"bot-activity"` | Yes |
| `bot_id` type | `int` | `int` | Yes |
| `--per-channel-limit` type | `int` | `int` | Yes |
| `--per-channel-limit` default | `100` | `100` | Yes |
| `set_defaults` | `func=run_command` | `func=run_command` | Yes |

## Architecture

No changes to the existing architecture. The parser wiring follows the
same pattern as every other subcommand in `build_parser()`.

## Data Flow

No changes to data flow. The existing path is:

1. `build_parser()` creates `bot-activity` subparser
2. Argparse parses user input, coerces types, applies defaults
3. `set_defaults(func=run_command)` routes to `run_command()`
4. `run_command()` looks up `command_specs()["bot-activity"]`
5. `fetch_bot_activity(guild, args)` executes

This path is already implemented and verified.

## Decision

No code changes needed. The parser wiring is correct as implemented in
P0040. This verification pass confirms the implementation matches the
proposal specification.

## Anti-scope

This proposal explicitly does not include:

- any code changes
- any new arguments or flags
- any modifications to existing parser behavior
- any changes to the handler or dispatch wiring
