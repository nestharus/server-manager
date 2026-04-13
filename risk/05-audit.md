# Audit Risk Assessment: discord_cli.py

## Risk Level: LOW

*Re-run after proposal revision (gateway timeout added).*

## Findings

1. **Token never echoed in output (severity: low, mitigated by design)**
   The proposal loads `DISCORD_BOT_TOKEN` from `.env` and passes it to `Client.start()`. The structured error categories (`config_error`, `login_error`, `timeout_error`) describe failure *types* without echoing the credential value into the JSON payload. The error mapping implies this but does not state it explicitly. **Implementation note**: error messages must not echo the raw `DISCORD_BOT_TOKEN` value in `message` or `details` fields.

2. **Intents are slightly broader than minimum (severity: informational)**
   The proposal enables `message_content=True` even though the research establishes that `history()` does not require it. The proposal documents this tradeoff explicitly and justifies it: the user already enabled the intent in the Developer Portal, and it avoids future surprises. For a single-guild admin CLI this is a reasonable pragmatic choice, not a vulnerability.

3. **No sensitive data in stdout beyond what the operator requested (severity: informational)**
   Message content, member names, and integration account details all appear in stdout by design — the operator is explicitly requesting this data via the subcommand. The tool does not log to files, persist data locally, or transmit over a network. Stdout exposure is equivalent to any CLI that reads from an API the operator has access to.

4. **Input validation is adequate (severity: none)**
   All user-controlled inputs are validated:
   - `DISCORD_GUILD_ID` must be a valid integer; missing or non-integer values produce `config_error`.
   - `DISCORD_BOT_TOKEN` must be present; missing value produces `config_error`.
   - `--limit N` rejects values ≤ 0 and caps at 200.
   - Channel selectors go through a defined resolution chain (ID → exact name → substring → error) with explicit ambiguity rejection.
   - argparse handles subcommand routing, so invalid commands are rejected before reaching Discord.

5. **Error handling avoids information leakage (severity: none)**
   The error strategy emits one JSON envelope per exit path with a constrained schema (`type`, `message`, `details`). Documented `details` values are Discord HTTP status codes, resource codes, channel selectors, and candidate matches — none of which are secrets. The principle "do not print mixed human logs alongside JSON" prevents accidental leakage through unstructured stderr/stdout mixing.

6. **Rate limiting is a non-issue for one-shot design (severity: informational)**
   Each invocation opens one gateway connection, runs one subcommand (at most a few HTTP calls), and exits. Discord's 50 req/s global limit and 10,000 invalid-request limit per 10 minutes are orders of magnitude above a single CLI invocation. The tool itself cannot cause rate-limit problems in normal use.

7. **No write operations in scope (severity: none)**
   The entire subcommand set is read-only: `overview`, `bots`, `channels`, `find-channel`, `read`, `integrations`. No mutation endpoints exist. The tool cannot alter guild state even if misused.

8. **Gateway timeout does not introduce audit concerns (severity: none)**
   The revised proposal wraps the gateway session in `asyncio.wait_for()` with a 30-second default timeout. On timeout, the client is closed and a `timeout_error` is returned via the standard JSON envelope. This change:
   - Does not expose new data (the error payload contains no credentials or sensitive state).
   - Does not open new network surface (the timeout shortens the connection window, it does not extend it).
   - Closes the client in `finally`, preventing resource leaks that could hold an authenticated session open longer than necessary.
   - Uses the same error envelope as all other failure paths, so no information leakage through a different output format.

   From an audit perspective the timeout is strictly positive: it reduces the window during which an authenticated gateway connection is held open, and it ensures the process exits cleanly on infrastructure failures.

## Recommendation

**Accept.** The proposal has a fundamentally small attack surface: a local CLI that reads a token from `.env`, makes read-only Discord API calls, prints JSON to stdout, and exits. The gateway timeout revision addresses the only operational gap from the prior assessment round without introducing new security concerns. No findings rise above informational severity. One implementation note carries forward:

- Error messages (particularly `login_error`, `config_error`, and `timeout_error`) must not echo the raw `DISCORD_BOT_TOKEN` value in the `message` or `details` fields.
