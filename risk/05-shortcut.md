# Shortcut Risk Assessment: discord_cli.py

## Risk Level: LOW

## Re-run Context

This is a re-assessment against the revised proposal. The previous assessment found one MEDIUM-severity shortcut (no gateway connection timeout). The proposal now includes `asyncio.wait_for()` with a 30-second default timeout and a `timeout_error` error category, which resolves that finding.

## Findings

1. **Gateway connection timeout — resolved** (was MEDIUM, now CLOSED)
   The revised proposal wraps the gateway session in `asyncio.wait_for()` with a 30-second default timeout and maps the failure to a `timeout_error` category. This directly addresses the previous finding. The lifecycle section now explicitly lists the timeout alongside `reconnect=False`, the `has_run` guard, and `finally`-based cleanup. No remaining gap.

2. **Member cache completeness is assumed, not verified** (LOW)
   The `bots` command filters `Guild.members` from the gateway cache. For the Humility guild (~85 members), Discord delivers all members in the GUILD_CREATE payload when `Intents.members` is enabled. The proposal doesn't guard against incomplete cache for guilds exceeding the 1000-member chunking threshold. Since the tool reads `DISCORD_GUILD_ID` from `.env`, pointing it at a larger guild is trivial and would produce silently incomplete bot lists. Acceptable for the current single-guild scope but worth noting as a latent assumption.

3. **Snowflake IDs as JSON integers** (LOW)
   The serialization rules specify IDs as integers. Discord snowflakes can exceed `2^53` (JavaScript's `Number.MAX_SAFE_INTEGER`). Since this is a local Python CLI consumed by Python automation, integer IDs are correct and lossless. If the output were ever piped to a JavaScript consumer, IDs would silently lose precision. The proposal's scope makes this acceptable — the fix (string IDs) would be a breaking change to the JSON contract, so flagging it for awareness.

4. **All intents enabled for every subcommand** (LOW)
   Intents are built once with `guilds=True`, `members=True`, `message_content=True` regardless of which subcommand runs. Commands like `overview` and `channels` don't need `members` or `message_content`. Every invocation requests privileged intents even when unnecessary. The practical cost is zero — the bot has these intents enabled — but it means the tool cannot degrade gracefully if a privileged intent were revoked. Acceptable coupling for a single-guild admin tool.

5. **No `--timeout` or `--verbose` escape hatches** (LOW)
   The proposal defines no mechanism to override the 30-second timeout or get diagnostic output. The structured error payloads cover most debugging scenarios, and the timeout default prevents hangs. A `--verbose` flag logging gateway events to stderr or a `--timeout N` override would help edge-case debugging but is not critical for initial delivery.

6. **`read` limit cap at 200 without pagination** (LOW)
   The cap at 200 messages prevents runaway output, which is correct. Since `before`/`after` pagination is not exposed in v1, the cap effectively limits how far back a single invocation can see. This is an acceptable scope limit — the user can inspect recent history and the tool can grow pagination later without breaking the JSON contract.

7. **Thread visibility is permission-filtered without disclosure** (LOW)
   `Guild.threads` only returns threads the bot can view. The output doesn't indicate whether the thread list is complete or permission-filtered. For an admin bot with broad permissions this is fine. If permissions were restricted, threads would be silently omitted. Minor for the current setup.

## Recommendation

**Accept.** The previous MEDIUM finding (no gateway timeout) has been fully addressed. The remaining findings are all LOW severity and appropriate for a local CLI tool of this scope. None require changes before implementation.
