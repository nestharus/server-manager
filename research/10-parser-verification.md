# Research: Parser Wiring Verification for `bot-activity`

## Scope

This note documents the verification of the `bot-activity` argparse
subparser wiring in `discord_cli.py`. It confirms that the parser
registration implemented in P0040 matches the proposal specification.

This is a verification-only research pass. No new APIs, libraries, or
patterns are investigated because no code changes are needed.

## 1. Subparser registration

The `bot-activity` subparser is registered in `build_parser()` at
[discord_cli.py](/home/nes/discord/discord_cli.py:566):

```python
bot_activity_parser = subparsers.add_parser("bot-activity", help="Scan channels for activity by a bot")
bot_activity_parser.add_argument("bot_id", type=int)
bot_activity_parser.add_argument("--per-channel-limit", type=int, default=100)
bot_activity_parser.set_defaults(func=run_command)
```

### Verification against proposal (proposals/09-bot-activity.md)

| Proposal requirement | Code | Status |
| --- | --- | --- |
| Subcommand name `bot-activity` | `add_parser("bot-activity", ...)` | Matches |
| Positional `bot_id` with `type=int` | `add_argument("bot_id", type=int)` | Matches |
| Optional `--per-channel-limit` with `type=int, default=100` | `add_argument("--per-channel-limit", type=int, default=100)` | Matches |
| `set_defaults(func=run_command)` | `bot_activity_parser.set_defaults(func=run_command)` | Matches |

All four parser elements match the proposal exactly.

## 2. Placement in build_parser()

The `bot-activity` subparser block appears after the `read` subparser
block and before `return parser`, consistent with the hookpoint analysis
in `research/09-hookpoints.md` (section 5).

The `read` subparser block ends at approximately line 565. The
`bot-activity` block starts at line 566. This placement keeps
history-reading commands grouped together.

## 3. Argument behavior

- `bot_id` is positional and required. Argparse will reject invocations
  missing this argument with a usage error before the handler runs.
- `--per-channel-limit` defaults to `100` when omitted, matching the
  proposal's specified default.
- `type=int` on both arguments means argparse rejects non-integer input
  at parse time, before any handler code executes.

## 4. Dispatch wiring

The handler `fetch_bot_activity` is registered in `command_specs()` at
[discord_cli.py](/home/nes/discord/discord_cli.py:524):

```python
"bot-activity": fetch_bot_activity,
```

This is verified separately in P0042, but noted here for completeness:
the parser routes to `run_command` via `set_defaults(func=run_command)`,
and `run_command` looks up the handler via `command_specs()[args.command]`.
The `"bot-activity"` key in `command_specs()` connects the parser to
`fetch_bot_activity`.

## 5. Conclusion

The `bot-activity` argparse subparser is correctly wired. All arguments,
types, defaults, and placement match the proposal. No changes are needed.
