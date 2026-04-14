# Scope Risk Assessment: Discord Service Entry Point (`app/__main__.py`)

## Overall: LOW

The proposal defines a thin process-bootstrap module with one async
`main()` coroutine, discord-aware logging setup, fast-fail settings
validation, SIGTERM-driven graceful shutdown, and a simple 0/1 exit
code contract. Every element traces to a documented need from the
research or synthesis. The anti-scope section explicitly fences out
eleven categories of potential expansion. The module owns process
lifecycle only — it does not define what the daemon does once
connected.

## Findings

### Finding 1: Appropriate size for a package entry point
- Severity: LOW
- Description: The proposal delivers exactly what a `__main__.py`
  should own: logging configuration, settings construction, object
  wiring, signal registration, startup, shutdown, and exit codes. The
  research confirms Python convention calls for a thin `__main__.py`
  that delegates to imported code (research lines 29-49). The proposal
  imports two project modules (`Settings`, `HumilityBot`) and three
  stdlib/library modules (`asyncio`, `logging`, `signal`, `discord`,
  `ValidationError`). The only exported symbol is `main()`. Module-level
  code is limited to a logger assignment and the `raise SystemExit`
  entry guard. This is proportionate to the package entry point role.

### Finding 2: No business logic detected
- Severity: LOW
- Description: The proposal contains no event handlers, no command
  registration, no database wiring, no guild inspection, no message
  processing, and no application-domain logic. `main()` constructs
  `Settings()`, constructs `HumilityBot(settings)`, wires a SIGTERM
  handler, calls `bot.start()`, and translates outcomes to exit codes.
  The architecture section (proposal lines 27-41) explicitly delegates
  behavioral ownership: `core.settings` owns config validation,
  `core.bot` owns the bot object and intents, and later modules attach
  handlers via `setup_hook()` or adjacent modules. The entry point
  starts the daemon; it does not define what the daemon does.

### Finding 3: Error handling is proportionate
- Severity: LOW
- Description: The proposal catches eight specific exception types plus
  a catch-all `Exception`. Each maps to a documented failure mode from
  the research: `ValidationError` for settings (research section 5A),
  `LoginFailure` and `HTTPException` for authentication (research
  section 5B), `GatewayNotFound`, `ConnectionClosed`, and
  `PrivilegedIntentsRequired` for gateway failures (research section 5C),
  and `KeyboardInterrupt`/`CancelledError` for clean shutdown (research
  section 5D). The exit code contract is deliberately simple — `0` for
  clean shutdown, `1` for everything else. The proposal explicitly
  states it does not catch per-event handler exceptions (proposal line
  231), correctly deferring those to discord.py's event system. The
  two-boundary structure (settings validation separate from bot
  startup) matches the research's four-layer error model without
  over-engineering it.

### Finding 4: Signal handling is justified with minor over-specification
- Severity: LOW
- Description: SIGTERM wiring is a hard requirement — Railway sends
  SIGTERM for graceful shutdown (synthesis line 10), and the research
  confirms `asyncio.run()` does not provide built-in SIGTERM handling
  (research lines 136-145). The primary path using
  `loop.add_signal_handler()` is the asyncio-native API. The proposal
  includes a fallback registration path for non-Unix platforms (proposal
  lines 173-176). Since the deployment target is Railway on Linux, the
  fallback is not operationally required, but the proposal acknowledges
  this tradeoff explicitly (proposal lines 287-289) and keeps the
  fallback minimal. The idempotency requirement for `request_shutdown()`
  is sound — repeated SIGTERM signals from supervisors are a real
  operational scenario. This is slightly more surface than the bare
  minimum but remains proportionate for a daemon entry point that must
  shut down cleanly under process supervision.

### Finding 5: No unnecessary coupling
- Severity: LOW
- Description: The module couples to exactly two internal modules:
  `app.core.settings.Settings` and `app.core.bot.HumilityBot`. Both are
  already implemented and are the minimum dependencies for a bootstrap
  module. The one field-level coupling is `settings.discord_bot_token`,
  which is unavoidable — the token must be passed to `bot.start()`. The
  choice of `discord.utils.setup_logging()` over raw
  `logging.basicConfig()` couples to discord.py's formatter, but the
  proposal's tradeoffs section (proposal lines 277-280) explicitly
  accepts this as appropriate for a discord.py daemon. No implementation
  details of `HumilityBot` internals are referenced beyond its
  constructor signature and the inherited `start()`/`close()` API.

### Finding 6: Anti-scope is clear and sufficient
- Severity: LOW
- Description: The anti-scope section (proposal lines 259-270)
  enumerates eleven explicit exclusions: business logic, event handlers,
  command registration, `setup_hook()` details, database/repository
  wiring, background tasks, guild inspection, dotenv loading, retry
  orchestration, and compatibility shims. Each exclusion maps to a known
  expansion path: the existing daemon performs `load_dotenv()` at import
  time, registers commands in `setup_hook()`, and stores direct
  database/config attributes. The anti-scope fence prevents migration of
  those patterns into this bootstrap module. The exclusion of retry
  orchestration is particularly well-targeted — the proposal defers to
  discord.py's built-in reconnect behavior inside `bot.start(...,
  reconnect=True)` rather than adding a restart loop.
