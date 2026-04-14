# Shortcut Risk Assessment: `services/discord/app/__main__.py`

## Overall: LOW

## Findings

### Finding 1: Signal handler fallback is a compatibility shim
- Severity: LOW
- Description: The proposal specifies a primary path using
  `loop.add_signal_handler(signal.SIGTERM, ...)` and a fallback using
  `signal.signal(signal.SIGTERM, ...)` with thread-safe bounce-back for
  platforms where the asyncio API is unavailable. This is structurally
  a compatibility shim — two code paths that accomplish the same thing
  for different platforms. However, the proposal explicitly justifies
  this in the Tradeoffs section: the deployment target is Railway on
  Linux where `loop.add_signal_handler()` is the operational path, and
  the fallback exists so local development on non-Unix platforms is not
  broken. The primary path is well-defined, the fallback is narrowly
  scoped to signal registration only, and neither path introduces
  behavioral divergence in the shutdown sequence itself. The shim does
  not grow over time or create maintenance burden.
- Recommendation: None. The fallback is justified, narrow, and
  explicitly documented.

### Finding 2: Log level hardcoded to INFO
- Severity: LOW
- Description: The proposal specifies `logging.INFO` as the log level
  with no runtime override mechanism (e.g., a `LOG_LEVEL` setting or
  `--verbose` flag). This could appear to hardcode a value that should
  be configurable. However, for a daemon entry point, INFO is the
  standard production default. The proposal's scope is process
  bootstrap, not configuration surface design. If a configurable log
  level is needed later, it can be added to `Settings` and threaded
  into the `setup_logging()` call without changing the entry point's
  structure. The current choice avoids speculative configurability.
- Recommendation: None. INFO is the correct default for a production
  daemon, and adding configurability later is additive.

### Finding 3: No catch-all error suppression
- Severity: LOW (positive finding)
- Description: The proposal defines specific exception handling for
  each expected failure mode: `ValidationError`, `LoginFailure`,
  `PrivilegedIntentsRequired`, `GatewayNotFound`, `ConnectionClosed`,
  `HTTPException`, `KeyboardInterrupt`, and `CancelledError`. The
  final `Exception` catch is a last-resort handler that logs with full
  traceback and returns exit code 1. The error handling uses two
  distinct boundaries — settings validation around `Settings()` and
  Discord exceptions around `bot.start()` — rather than a single
  catch-all wrapping everything. This is proper structured error
  handling, not a shortcut.
- Recommendation: None. The error strategy is well-structured.

### Finding 4: Exit code simplicity is a deliberate constraint
- Severity: LOW
- Description: The proposal uses only two exit codes: 0 for clean
  shutdown and 1 for all failures. The Tradeoffs section explicitly
  discusses this: "More granular codes are possible, but they add
  operational surface without clear need at this stage." This could
  appear to defer exit-code design. However, for a supervised daemon
  where the supervisor (Railway) only distinguishes success from
  failure, a binary exit contract is the correct level of granularity.
  The log output carries the diagnostic detail. Adding granular exit
  codes later would not require restructuring the error handling.
- Recommendation: None. Binary exit codes match the operational
  environment.

### Finding 5: No backwards-compatibility patterns
- Severity: LOW (positive finding)
- Description: The proposal's anti-scope explicitly excludes
  "compatibility shims for older daemon entrypoints." The module does
  not reference or accommodate the existing `daemon/__main__.py`
  pattern. It defines a clean entry point for `services/discord/app`
  with no migration bridges, re-exports, or dual-path logic. This is
  the correct approach for a new service package.
- Recommendation: None.

### Finding 6: No deferred TODOs
- Severity: LOW (positive finding)
- Description: The proposal contains no TODO markers or "to be
  determined" language. Items outside its scope — event handlers,
  `setup_hook()` implementation, command registration, database
  wiring — are explicitly listed in the anti-scope section rather
  than deferred as inline TODOs. The ownership split between
  `__main__.py`, `core.settings`, and `core.bot` is fully specified.
  The interface contracts (`Settings()`, `HumilityBot(settings)`,
  `bot.start(token)`, `bot.close()`) are resolved, not deferred.
- Recommendation: None.

### Finding 7: `bot.start()` over `bot.run()` is correct
- Severity: LOW (positive finding)
- Description: The proposal explicitly chooses `bot.start()` because
  the daemon needs explicit signal wiring and controlled shutdown.
  The Tradeoffs section documents the reasoning: "`bot.run()` is
  simpler but gives up the lifecycle control this service needs."
  The research confirms that `run()` is the convenience API and
  `start()` is the async API for applications that own process
  lifecycle. This is the correct choice for a supervised daemon
  with SIGTERM requirements.
- Recommendation: None.
