# Proposal: Dispatch Wiring Verification for `bot-activity`

Date: 2026-04-13

## Goal

Verify that the `bot-activity` command dispatch wiring in
`discord_cli.py` matches the specification in `proposals/09-bot-activity.md`.

This proposal is verification only. It does not include implementation
code because no code changes are needed.

## Summary

The research and synthesis phases confirm that all dispatch elements are
correctly implemented:

- `command_specs()` entry: `"bot-activity": fetch_bot_activity`
- Handler function: `fetch_bot_activity(guild, args) -> dict`
- Dispatch flow: `run_command()` → `command_specs()[args.command]` → handler
- Handler signature matches `command_specs()` type annotation

## Verification Result

| Element | Expected (proposal) | Actual (code) | Match |
| --- | --- | --- | --- |
| `command_specs()` key | `"bot-activity"` | `"bot-activity"` | Yes |
| `command_specs()` value | `fetch_bot_activity` | `fetch_bot_activity` | Yes |
| Handler signature | `(guild, args) -> dict` | `(guild: Guild, args: Namespace) -> dict[str, Any]` | Yes |
| Dispatch via `run_command` | `command_specs()[command]` | `handler = command_specs()[command]` | Yes |

## Architecture

No changes to the existing architecture. The dispatch wiring follows the
same `command_specs()` pattern used by every other subcommand.

## Data Flow

No changes to data flow. The existing path is:

1. `build_parser()` creates `bot-activity` subparser with `set_defaults(func=run_command)`
2. Argparse parses user input, sets `args.command = "bot-activity"`
3. `run_command(args)` is invoked via `args.func`
4. `command_specs()["bot-activity"]` resolves to `fetch_bot_activity`
5. `fetch_bot_activity(guild, args)` executes within the gateway context
6. Result is wrapped by `success_payload()` and printed as JSON

This path is already implemented and verified.

## Decision

No code changes needed. The dispatch wiring is correct as implemented in
P0040. This verification pass confirms the implementation matches the
proposal specification.

## Anti-scope

This proposal explicitly does not include:

- any code changes
- any new command_specs entries
- any modifications to run_command() or the dispatch flow
- any changes to the handler function signature or behavior
