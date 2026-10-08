# Synthesis — Discord service `__main__.py` needs

Source: `research/25-discord-main.md`

## Humility-specific context

The Discord service is one of three services in the monorepo. It runs
as a persistent daemon on Railway, connecting to the Humility guild
(`<guild id>`) and optionally the beta guild. The entry point
must work reliably under Railway's process supervisor which sends
SIGTERM for graceful shutdown.

## Needs mapped from research

### 1. Minimal `__main__.py`

The research confirms Python convention is a thin `__main__.py` that
delegates to imported code. For this service:
- Import `Settings` from `app.core.settings`
- Import `HumilityBot` from `app.core.bot`
- Define an async `main()` coroutine
- Call via `asyncio.run(main())`

### 2. Startup sequence

Based on the research lifecycle analysis:
1. Configure logging first (before any other work)
2. Construct `Settings()` — fails fast on missing env vars
3. Construct `HumilityBot(settings)`
4. Call `bot.start(settings.discord_bot_token)` inside a try/finally
   that guarantees `bot.close()` on exit

### 3. Signal handling

The research confirms:
- `asyncio.run()` handles SIGINT/Ctrl-C via task cancellation
- SIGTERM requires explicit wiring for Railway deployments
- `signal.signal(SIGTERM, ...)` raising `KeyboardInterrupt` or
  cancelling the main task is the simplest cross-platform approach
- Log shutdown reason from coroutine context, not from signal handler

### 4. Logging

Research confirms:
- Configure once at the process boundary
- Use `discord.utils.setup_logging()` or equivalent standard logging
- INFO level for normal daemon operation
- The entry point should log: startup, settings summary (redacted),
  shutdown, and any bootstrap failures

### 5. Error handling at entry point

The research identified 4 error layers:
- **Settings errors**: `pydantic.ValidationError` — log and exit
- **Auth failures**: `discord.LoginFailure` — log and exit
- **Gateway failures**: `GatewayNotFound`, `PrivilegedIntentsRequired`
  — log and exit
- **Clean shutdown**: `KeyboardInterrupt`, `asyncio.CancelledError` —
  log and exit cleanly (exit code 0)

### 6. Gaps

None identified. The research covers all aspects needed for a minimal
entry point. The entry point should NOT contain business logic — that
belongs in `bot.py`'s `setup_hook()` and event handlers.

## Contract summary

- File: `services/discord/app/__main__.py`
- Imports: `logging`, `signal`, `sys`, `asyncio`, `Settings`, `HumilityBot`
- One async `main()` function
- Logging configured at top of `main()`
- Settings loaded, bot constructed, bot started with try/finally close
- SIGTERM handler wired before bot.start()
- Exit codes: 0 for clean shutdown, 1 for configuration/auth errors
- Module docstring: "Discord daemon entry point. Run with: cd services/discord && uv run python -m app"
