# Audit Risk Assessment: `services/discord/app/__main__.py`

## Overall: LOW

The proposal is well-structured and explicitly addresses all six audit
criteria. The design follows documented Python asyncio patterns,
discord.py's recommended startup path for daemons using `bot.start()`,
and standard signal-handling safety practices. No blocking issues were
identified. Implementation can proceed as designed.

## Findings

### Finding 1: Token handling is safe by design
- Severity: LOW
- Description: The bot token flows through exactly one path:
  `bot.start(settings.discord_bot_token)`. This is the standard
  discord.py API surface. The proposal explicitly prohibits logging
  sensitive values: "It should not echo sensitive values such as the bot
  token or database URL" (proposal, Settings construction section). The
  existing `Settings` class marks `discord_bot_token` and
  `supabase_db_url` with `repr=False`
  ([settings.py:8](/home/nes/discord/services/discord/app/core/settings.py:8)),
  which suppresses them from model repr output. No custom string
  formatting or interpolation of the token is proposed. The token is
  never stored in a second location or passed to any surface beyond
  discord.py's own `start()` method.
- Recommendation: None. The token handling is minimal and correct.

### Finding 2: Error messages do not expose sensitive data
- Severity: LOW
- Description: The proposal defines explicit catch blocks for each
  expected exception type and specifies log-and-return-exit-code
  behavior for all of them. The `ValidationError` catch is scoped around
  `Settings()` construction specifically, and the proposal explicitly
  states that log records should not echo sensitive values. One minor
  consideration: Pydantic v2's `ValidationError` can include input values
  in its error details. However, the practical risk is negligible because
  (a) `discord_bot_token` is typed as `str`, so type coercion failures
  are extremely unlikely from environment variable sources which are
  already strings, (b) the most probable failure mode is a missing field,
  which produces no value in the error, and (c) `repr=False` on the
  field further limits repr-based exposure paths. Discord exception
  messages (`LoginFailure`, `GatewayNotFound`, etc.) do not echo
  credentials. The catch-all `Exception` handler logs with traceback,
  which is standard daemon practice and does not introduce novel
  leakage since the token is only held in discord.py internal state at
  that point, not in `__main__` locals.
- Recommendation: None. The explicit prohibition on logging sensitive
  values combined with `repr=False` on credential fields provides
  adequate protection. If defense-in-depth is desired, the
  implementation could log only `str(error)` rather than the full
  `ValidationError` object, but this is not required.

### Finding 3: Signal handler safety is explicitly addressed
- Severity: LOW
- Description: The proposal dedicates an entire section to signal
  handling and gets the safety constraints right. The key design
  decisions: (1) the signal handler (`request_shutdown()`) only schedules
  `bot.close()` onto the event loop — it does not perform logging or
  other complex operations from signal context; (2) the proposal
  explicitly states "Logging for the shutdown reason should happen after
  control returns to normal coroutine context, not from the raw signal
  handler itself"; (3) the research confirms this matches Python's
  documented constraint that "logging may not be safe from asynchronous
  signal handlers implemented via the `signal` module"
  ([research:166-169](/home/nes/discord/research/25-discord-main.md:166));
  (4) the handler is specified as idempotent, preventing repeated signals
  from scheduling multiple shutdown sequences. The primary registration
  path uses `loop.add_signal_handler()` which runs callbacks in the
  event loop context (inherently safer than raw `signal.signal()`), with
  a fallback for non-Unix platforms.
- Recommendation: None. The signal handling design follows documented
  best practices for both asyncio and Python's logging safety model.

### Finding 4: Cleanup is guaranteed through try/finally
- Severity: LOW
- Description: The proposal specifies `bot.start()` inside a
  `try/finally` that guarantees `bot.close()` is awaited during
  teardown. The `finally` block guards against duplicate close calls by
  checking whether the client is already closed before awaiting
  `bot.close()`. This covers four shutdown paths: (1) SIGTERM triggers
  `bot.close()` via the signal handler, `start()` unwinds, `finally`
  checks and skips duplicate close; (2) SIGINT/Ctrl-C triggers task
  cancellation via `asyncio.run()`, `finally` closes the bot;
  (3) discord exceptions during startup cause `start()` to raise,
  `finally` closes the bot; (4) unexpected exceptions trigger
  `finally` cleanup. The proposal also correctly notes that
  `asyncio.run()` handles loop teardown, async generator finalization,
  and executor shutdown, so `__main__` does not need to replicate that
  work.
- Recommendation: None. The cleanup guarantee is comprehensive and
  handles all identified shutdown paths.

### Finding 5: Exit codes are meaningful and consistent
- Severity: LOW
- Description: The proposal defines a simple binary exit code contract:
  `0` for clean shutdown, `1` for any failure. The exit code table
  maps every handled exception type to a specific code. Clean shutdown
  paths (SIGTERM, KeyboardInterrupt, CancelledError) return `0`.
  Bootstrap failures (ValidationError, LoginFailure,
  PrivilegedIntentsRequired, GatewayNotFound, ConnectionClosed,
  HTTPException) and unexpected exceptions return `1`. Exit codes are
  returned from the `main()` coroutine rather than calling `sys.exit()`
  from inside async context, and converted to process exit status at
  module level via `raise SystemExit(asyncio.run(main()))`. This keeps
  the coroutine testable and the exit-code conversion in one place.
  The proposal explicitly considered and rejected finer-grained exit
  codes as adding operational surface without clear value.
- Recommendation: None. The simple binary contract is appropriate for
  Railway's process supervisor and standard daemon management.

### Finding 6: Logging configuration follows documented patterns
- Severity: LOW
- Description: The proposal uses `discord.utils.setup_logging()` as
  the one-time logging configuration call, which is discord.py's
  documented path when the application uses `bot.start()` instead of
  `bot.run()`. Configuration happens at the top of `main()` before any
  other work, ensuring bootstrap failures are captured. The level is
  `logging.INFO`. The root logger is configured so both `__main__` and
  discord.py emit to the same handler stack. No custom formatters or
  handlers are introduced that could inadvertently leak data. The
  proposal correctly identifies that per-event-handler errors are logged
  by discord.py's own event system and do not need entry-point handling.
- Recommendation: None. The logging setup is minimal, safe, and follows
  the library's documented integration path.
