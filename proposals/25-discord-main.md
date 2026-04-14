# Proposal: `services/discord/app/__main__.py`

Date: 2026-04-13

## Goal

Define `services/discord/app/__main__.py` as the Discord service's
package entry point for:

`cd services/discord && uv run python -m app`

Its job is to own process bootstrap only:

- configure process-wide logging
- construct validated runtime settings
- construct the Discord bot
- wire supervisor-driven graceful shutdown
- start the bot and translate top-level failures into process exit
  codes

This proposal is design only. It does not include implementation code.

## Architecture

`app.__main__` is the daemon boundary for the Discord service. It
belongs above `core.settings` and `core.bot` and should stay thinner
than either of them.

Recommended ownership split:

- `core.settings` owns environment-backed configuration validation.
- `core.bot` owns the configured `HumilityBot` object and its intents.
- `app.__main__` owns process lifecycle: logging, signal wiring,
  startup, shutdown, and exit codes.
- Later handlers, commands, and background tasks attach to the bot from
  bot-owned startup hooks or adjacent modules, not from the package
  entry point.

This keeps the entry point operational rather than behavioral. The file
starts the daemon; it does not define what the daemon does once
connected.

## Module Structure

The module should use this docstring:

```python
"""Discord daemon entry point. Run with: cd services/discord && uv run python -m app."""
```

The module should import exactly the process-bootstrap dependencies it
uses:

```python
import asyncio
import logging
import signal

import discord
from pydantic import ValidationError

from app.core.bot import HumilityBot
from app.core.settings import Settings
```

The module should expose one importable coroutine and no public helper
API:

```python
async def main() -> int:
    """Run the Discord daemon and return a process exit code."""
```

Module-level structure should otherwise be limited to:

- `logger = logging.getLogger(__name__)`
- a module-level `raise SystemExit(asyncio.run(main()))`

No extra exported functions are needed. The SIGTERM callback can stay a
small nested function inside `main()` so `__main__.py` remains thin.

## `main()` Coroutine Design

`main()` should execute in this order:

1. Configure logging before any other work.
2. Construct `Settings()` and fail fast on invalid runtime config.
3. Construct `HumilityBot(settings)`.
4. Register a SIGTERM callback against the running loop.
5. Await `bot.start(settings.discord_bot_token)`.
6. In `finally`, ensure `bot.close()` is awaited if shutdown has not
   already closed the client.
7. Return a numeric exit code instead of calling `sys.exit()` from
   inside the coroutine.

### Logging setup

Use `discord.utils.setup_logging()` rather than raw
`logging.basicConfig()`.

Recommended shape:

- configure once at the top of `main()`
- level: `logging.INFO`
- configure the root logger so both this module and discord.py emit to
  the same handler stack

This matches discord.py's documented logging path when the application
uses `bot.start()` instead of `bot.run()`.

### Settings construction

`Settings()` should be instantiated inside `main()` under a dedicated
`ValidationError` catch.

Required behavior:

- log configuration failure at error or critical level
- do not attempt bot construction if settings validation fails
- return exit code `1`

The log record should identify the failure as bootstrap/configuration
error. It should not echo sensitive values such as the bot token or
database URL.

### Bot construction

After settings load succeeds, `main()` should construct:

```python
bot = HumilityBot(settings)
```

Construction remains side-effect-free. No Discord connection should be
attempted until `await bot.start(...)`.

### Startup and shutdown shape

`bot.start(settings.discord_bot_token)` should run under a `try/finally`
that guarantees `bot.close()` is called during teardown.

The intent is:

- `bot.start(...)` owns login plus gateway connection
- signal-triggered shutdown asks the bot to close gracefully
- `finally` is the last safety net if startup partially succeeds or
  shutdown unwinds through cancellation

The `finally` block should guard against duplicate close calls by
checking whether the client is already closed before awaiting
`bot.close()`.

## Signal Handling

`SIGINT` does not need custom wiring in this module. `asyncio.run()`
already provides the structured Ctrl-C path.

`SIGTERM` does need explicit wiring because Railway and other process
supervisors terminate daemons with `SIGTERM`.

Design the shutdown path like this:

- inside `main()`, capture the running loop with
  `asyncio.get_running_loop()`
- define a small nested `request_shutdown() -> None`
- make `request_shutdown()` idempotent so repeated signals do not
  schedule multiple shutdowns
- have `request_shutdown()` schedule bot shutdown onto the event loop;
  it should not perform logging directly from the raw signal path

Recommended registration policy:

- primary path: `loop.add_signal_handler(signal.SIGTERM, request_shutdown)`
- fallback path: if signal-handler registration is unavailable,
  register `signal.signal(signal.SIGTERM, ...)` and bounce back into the
  loop thread-safely to call `request_shutdown()`

The shutdown effect should be:

1. supervisor sends `SIGTERM`
2. handler schedules `bot.close()`
3. `bot.start(...)` unwinds and returns or raises through normal client
   shutdown behavior
4. `finally` performs last-resort close if needed
5. `main()` returns exit code `0`

Logging for the shutdown reason should happen after control returns to
normal coroutine context, not from the raw signal handler itself.

## Error Handling Strategy

`main()` is the top-level async boundary. It should translate expected
bootstrap and shutdown exceptions into explicit exit codes and log
levels.

Catch and handle these cases:

- `ValidationError`
  Configuration is invalid or incomplete. Log the validation failure and
  return `1`.
- `discord.LoginFailure`
  Authentication failed because the bot token is rejected. Log and
  return `1`.
- `discord.PrivilegedIntentsRequired`
  The configured privileged intents are not enabled in the Discord
  application settings. Log and return `1`.
- `discord.GatewayNotFound`
  Discord gateway discovery failed. Log and return `1`.
- `discord.ConnectionClosed`
  The websocket closed in a way the library did not recover from. Log
  and return `1`.
- `discord.HTTPException`
  A Discord HTTP-layer startup failure occurred. Log and return `1`.
- `KeyboardInterrupt`
  Treat as normal operator shutdown and return `0`.
- `asyncio.CancelledError`
  Treat as normal graceful shutdown when cancellation is part of the
  stop path and return `0`.
- `Exception`
  Log with traceback as unexpected top-level daemon failure and return
  `1`.

Two boundaries matter here:

- settings validation should be caught around `Settings()` specifically
  so config errors are reported cleanly before the bot exists
- Discord startup/runtime exceptions should be caught around
  `await bot.start(...)`

This file should not try to catch per-event handler exceptions. Those
belong to discord.py's event system and are logged there.

## Exit Code Table

| Exit code | Meaning | Triggers |
|---|---|---|
| `0` | Clean shutdown | SIGTERM-triggered graceful close, Ctrl-C / `KeyboardInterrupt`, cancellation during normal shutdown, or a normal return after `bot.close()` |
| `1` | Daemon failed to start or terminated abnormally | `ValidationError`, `discord.LoginFailure`, `discord.PrivilegedIntentsRequired`, `discord.GatewayNotFound`, `discord.ConnectionClosed`, `discord.HTTPException`, or any other uncaught top-level exception |

This proposal keeps the exit-code contract intentionally simple for
supervisors: success is `0`, anything operationally failed is `1`.

## Entry Guard

The module footer should be:

```python
raise SystemExit(asyncio.run(main()))
```

That preserves Python's standard async-program entry pattern while also
making the returned exit code the process exit status.

Because this file is package `__main__.py`, it does not need an
additional `if __name__ == "__main__"` block.

## Anti-scope

This file should explicitly exclude:

- business logic for applications, tickets, moderation, or role flows
- event handlers such as `on_ready`, `on_message`, or error callbacks
- slash-command or command-tree registration
- `setup_hook()` implementation details
- repository construction, database access, or Supabase wiring
- background task definitions or scheduling
- guild inspection or any live Discord read/write behavior beyond
  starting the bot connection
- dotenv loading, env-file discovery, or config mutation
- retry orchestration beyond what discord.py already does inside
  `bot.start(..., reconnect=True)`
- compatibility shims for older daemon entrypoints

## Tradeoffs Considered

- `discord.utils.setup_logging()` vs `logging.basicConfig()`
  Choose `discord.utils.setup_logging()` because it is the library's
  documented path when the application does not use `bot.run()`. The
  tradeoff is tighter coupling to discord.py's formatter choices, which
  is acceptable for this daemon entrypoint.
- `bot.run()` vs `bot.start()`
  Choose `bot.start()` because the daemon needs explicit signal wiring
  and controlled shutdown. `bot.run()` is simpler but gives up the
  lifecycle control this service needs.
- `loop.add_signal_handler()` only vs hybrid registration
  Prefer `loop.add_signal_handler()` because it is asyncio-native, but
  include a fallback registration path so local development is not tied
  to Unix-only behavior. The deployment target is Railway on Linux, so
  the primary path remains the operational one.
- `main() -> None` with `sys.exit()` side effects vs `main() -> int`
  Return an integer from `main()` and convert it to a process exit code
  at module level. This keeps the coroutine easier to test and keeps
  process termination in one obvious place.
- Multiple non-zero exit codes vs one failure code
  Use a single failure exit code `1`. More granular codes are possible,
  but they add operational surface without clear need at this stage.

## Decision

Keep `services/discord/app/__main__.py` as a thin operational
bootstrapper: one `main()` coroutine, discord-aware logging setup,
fast-fail settings validation, explicit SIGTERM-driven graceful
shutdown, `bot.start()` under `try/finally`, and a simple `0`/`1`
process exit contract.
