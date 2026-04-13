# Audit Risk Assessment: bot-activity

## Overall: LOW

No finding reaches MEDIUM or HIGH. The revised proposal's 10000 upper
bound on `--per-channel-limit` addresses the prior shortcut MEDIUM
finding. The command can proceed to implementation as proposed.

## Findings

### Finding 1: Per-channel-limit bounded at 10000 — prior MEDIUM resolved
- Risk level: LOW
- Description: The prior shortcut assessment rated the unbounded
  `--per-channel-limit` as MEDIUM because values like `100000` could
  produce thousands of paginated REST requests with no practical benefit.
  The revised proposal adds a hard upper bound of 10000 with explicit
  validation (`args.per_channel_limit <= 10000`), raising `CLIError`
  on violation. At the worst case of 10000 per channel across ~42
  scannable channels, this means ~4200 paginated `/messages` requests
  (ceil(10000/100) × 42). That is a large but finite scan.
  `discord.py`'s built-in rate-limit backoff prevents 429 bans, and the
  30-second `GATEWAY_TIMEOUT_SECONDS` provides a natural execution
  ceiling — scans exceeding it abort cleanly via `asyncio.TimeoutError`.
  The 10000 cap eliminates the effectively-unbounded scenario while
  preserving the audit-depth flexibility the command is designed for.
- Recommendation: No change required. The upper bound adequately
  addresses the prior MEDIUM finding. Note: the current implementation
  at `discord_cli.py:447-448` validates `> 0` but does not yet enforce
  the `<= 10000` check specified in the proposal. The implementation
  should add this validation to match the proposal.

### Finding 2: Message content exposure in samples
- Risk level: LOW
- Description: The `samples` field uses `serialize_message()`, which
  includes full `content`, `attachments` (with URLs), and `embeds`.
  If the CLI output is piped into logs, shared files, or AI context
  windows, message content from restricted channels could leak beyond
  its intended audience.
- Recommendation: The risk is LOW because the exposure surface is
  identical to the existing `read` command, which already returns full
  message content. The CLI is a local tool authenticated with the same
  bot token, so anyone running `bot-activity` already has the same
  access as someone running `read` on each channel individually. No
  change is required.

### Finding 3: Silent Forbidden skipping hides partial coverage
- Risk level: LOW
- Description: The proposal silently skips channels where
  `discord.Forbidden` is raised. A caller has no way to know which
  channels were excluded from the scan, which could produce misleading
  zero-activity results for a bot that is actually active in
  permission-restricted channels.
- Recommendation: The risk is LOW because the proposal explicitly
  identifies this as a known tradeoff and names `skipped` as a future
  extension point. The v1 scope is reasonable — the bot typically has
  `read_message_history` on most channels it's deployed to inspect.
  No change is required before implementation.

### Finding 4: No injection vectors in bot_id argument
- Risk level: LOW
- Description: `bot_id` is declared as `type=int` in argparse, which
  rejects non-integer input at parse time before it reaches any
  Discord API call. The value is compared via `message.author.id ==
  args.bot_id` (integer equality), not interpolated into strings or
  queries. There is no path from this argument to command injection,
  SQL injection, or API parameter manipulation.
- Recommendation: No change required.

### Finding 5: Strictly read-only — no data integrity risk
- Risk level: LOW
- Description: The command performs only `channel.history()` reads and
  in-memory filtering. It does not call any Discord mutation endpoint
  (send, edit, delete, ban, kick, role change, etc.). It does not
  write to local disk, databases, or caches. The anti-scope section
  explicitly excludes all mutation behavior.
- Recommendation: No change required.

### Finding 6: Command fits the existing permission model
- Risk level: LOW
- Description: The CLI has no tiered access control — all commands are
  available to anyone with the `DISCORD_BOT_TOKEN` and
  `DISCORD_GUILD_ID` environment variables. `bot-activity` follows
  the same pattern as every other command: authenticate via the bot
  token, operate within the bot's Discord permissions. The bot's
  Discord-side permissions (specifically `read_message_history`)
  govern what channels can be scanned, enforced by the API itself.
- Recommendation: No change required.
