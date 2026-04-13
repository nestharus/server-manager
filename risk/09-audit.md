# Audit Risk Assessment: bot-activity

## Overall: LOW

No finding reaches MEDIUM or HIGH. The command can proceed to
implementation as proposed.

## Findings

### Finding 1: Unbounded per-channel-limit allows large API request volume
- Risk level: LOW
- Description: The proposal explicitly recommends *not* clamping
  `--per-channel-limit` to `MAX_READ_LIMIT` (200). A caller can pass
  values like `2000`, which at `ceil(N/100)` pages per channel across
  the full guild surface could produce hundreds of Discord REST
  requests in a single invocation. For a guild with 42 scannable
  channels and `--per-channel-limit 2000`, the worst case is ~840
  `/messages` requests. Discord's per-route rate limits (typically
  5 req/5s per channel) and global rate limits could cause significant
  back-pressure and extend execution time well past
  `GATEWAY_TIMEOUT_SECONDS` (30s).
- Recommendation: The risk is LOW because `discord.py` already handles
  rate-limit 429 responses with automatic retry and backoff, so the
  command will slow down rather than fail or get the bot banned. The
  30-second gateway timeout provides a natural ceiling — scans that
  exceed it will abort cleanly via `asyncio.TimeoutError`. No change
  is required before implementation. If operational experience shows
  abuse, a reasonable upper bound (e.g. 2000) can be added later as a
  backward-compatible constraint.

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
  change is required. If content sensitivity becomes a concern, a
  future `--no-samples` flag or a content-truncation option would be
  a clean extension point.

### Finding 3: Silent Forbidden skipping hides partial coverage
- Risk level: LOW
- Description: The proposal silently skips channels where
  `discord.Forbidden` is raised. A caller has no way to know which
  channels were excluded from the scan, which could produce misleading
  zero-activity results for a bot that is actually active in
  permission-restricted channels.
- Recommendation: The risk is LOW because the proposal explicitly
  identifies this as a known tradeoff and names `skipped` as a future
  extension point. For an audit tool, silent gaps could matter, but
  the v1 scope is reasonable — the bot typically has
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
- Recommendation: No change required. The typing is correct as
  proposed.

### Finding 5: Strictly read-only — no data integrity risk
- Risk level: LOW
- Description: The command performs only `channel.history()` reads and
  in-memory filtering. It does not call any Discord mutation endpoint
  (send, edit, delete, ban, kick, role change, etc.). It does not
  write to local disk, databases, or caches. The anti-scope section
  explicitly excludes all mutation behavior.
- Recommendation: No change required. The read-only constraint is
  well-enforced by the design.

### Finding 6: Command fits the existing permission model
- Risk level: LOW
- Description: The CLI has no tiered access control — all commands are
  available to anyone with the `DISCORD_BOT_TOKEN` and
  `DISCORD_GUILD_ID` environment variables. `bot-activity` follows
  the same pattern as every other command: authenticate via the bot
  token, operate within the bot's Discord permissions. The bot's
  Discord-side permissions (specifically `read_message_history`)
  govern what channels can be scanned, enforced by the API itself.
- Recommendation: No change required. The command does not bypass or
  weaken the existing permission model.
