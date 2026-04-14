# Research: Discord Service Package Entry Point (`app/__main__.py`)

Date: 2026-04-13

## Scope

This report covers the design space for a package entry point that allows
running the Discord service with:

`cd services/discord && uv run python -m app`

It focuses on Python package entry-point behavior, the `discord.py`
startup/shutdown lifecycle, signal handling, logging, and bootstrap-time
error handling. It does not propose an implementation.

## 1. Standard `__main__.py` Pattern for Python Package Entry Points

Python treats `__main__` in two related ways:

- The top-level executed module gets `__name__ == "__main__"`.
- A package-level `__main__.py` is what runs when the package is invoked with
  `python -m <package>`.

For this case, `python -m app` runs `app/__main__.py`. Since the command is
being run from `services/discord`, `app` is import-resolved from that working
directory. This last point is an inference from normal Python import-path
behavior.

The Python docs describe the idiomatic package pattern as:

- Keep `__main__.py` short.
- Import a callable from elsewhere rather than putting a lot of logic directly
  in `__main__.py`.
- Prefer a `main()`-style function as the process entry point.
- For package `__main__.py`, an `if __name__ == "__main__"` guard is usually
  unnecessary; the docs explicitly note that minimal `__main__.py` files are
  preferred.

For async daemons specifically, the relevant Python guidance is that
`asyncio.run()` is the standard high-level entry point for an asyncio program.
It owns loop creation and teardown, finalizes async generators, and shuts down
the default executor.

Implications for research:

- `app/__main__.py` is the package-level process entry point, not a general
  module initializer.
- A thin file that delegates to importable code matches Python’s documented
  packaging conventions.
- If the process wants explicit lifecycle control, that control belongs in the
  async entry coroutine and its caller, not in ad hoc top-level code.

## 2. `discord.py` Startup and Shutdown Lifecycle

`discord.ext.commands.Bot` is a subclass of `discord.Client`, so the client
lifecycle APIs apply directly to `HumilityBot`.

### Lifecycle primitives

`discord.py` exposes four relevant lifecycle layers:

- `login(token)`
  - Authenticates using the token.
  - Calls `setup_hook()`.
  - Raises `LoginFailure` for bad credentials and `HTTPException` for other
    HTTP-layer failures.
- `connect(reconnect=True)`
  - Opens the gateway websocket and runs the event system until the websocket
    terminates.
  - Contains the library’s reconnect loop when reconnects are enabled.
  - Raises `GatewayNotFound` and `ConnectionClosed`.
- `start(token, reconnect=True)`
  - Documented as shorthand for `login()` + `connect()`.
  - This is the async lifecycle surface.
- `run(token, ...)`
  - Documented as a blocking convenience wrapper that abstracts event-loop
    initialization.
  - The upstream implementation wraps an async runner in `asyncio.run(...)`.
  - It also configures logging unless `log_handler=None` is passed.
  - It catches `KeyboardInterrupt` and relies on `asyncio.run()` for loop
    cleanup.

### `start()` vs `run()`

The important split is control ownership:

- `run()` is the convenience API. The docs explicitly say not to use it if you
  want more control over the event loop.
- `start()` is the async API surface to use when the application itself owns
  process lifecycle, loop policy, or shutdown choreography.

That distinction matters here because the research target includes explicit
SIGINT/SIGTERM shutdown behavior. `run()` is designed for simple blocking
startup, while `start()` is the controllable layer.

### `setup_hook()` timing

`login()` calls `setup_hook()`. The upstream docs/source are explicit that
`setup_hook()` runs:

- after login,
- before the websocket connects,
- before any events are dispatched,
- only once.

They also warn that anything waiting on the websocket in `setup_hook()` will
deadlock, including `wait_for()` and `wait_until_ready()`.

This is relevant to entry-point research because startup work can happen in
three different phases:

- pre-bot construction and settings/bootstrap work,
- post-login / pre-websocket async setup in `setup_hook()`,
- post-gateway event handling after connection is live.

## 3. Signal Handling Best Practices

### Python / asyncio behavior

Python’s current asyncio guidance is:

- application code should usually prefer `asyncio.run()` over manual loop
  management;
- `asyncio.Runner.run()` installs special handling for `SIGINT` only.

The Python docs describe `SIGINT` handling under `asyncio.Runner.run()` this
way:

- a custom `SIGINT` handler is installed before user code runs;
- the main task is cancelled;
- cleanup can happen through `try/finally` and normal cancellation unwinding;
- after cancellation, `KeyboardInterrupt` is raised.

This means `asyncio.run()` already gives a disciplined Ctrl-C path for the main
task.

### `SIGTERM`

The Python runner docs only document special handling for `SIGINT`, not
`SIGTERM`. From that, the correct inference is:

- graceful `SIGTERM` handling is not something `asyncio.run()` gives you by
  default in the same documented way;
- if the daemon needs graceful termination under supervisors that send
  `SIGTERM`, the application must arrange that explicitly.

### `loop.add_signal_handler`

For explicit signal wiring, asyncio documents `loop.add_signal_handler()` as
the proper event-loop-integrated API:

- the callback runs in the event loop, alongside other queued callbacks and
  coroutines;
- unlike a plain `signal.signal()` handler, that callback is allowed to
  interact with the event loop;
- it must be invoked in the main thread;
- availability is Unix-only.

The docs also provide a dedicated example for registering `SIGINT` and
`SIGTERM` with `loop.add_signal_handler()`.

### Logging inside signal paths

The Python logging docs add an important constraint:

- the logging module is thread-safe for normal use,
- but logging may not be safe from asynchronous signal handlers implemented via
  the `signal` module.

For research purposes, that means the safe pattern is:

- use the signal handler to trigger shutdown into the event loop,
- do actual shutdown logging from normal task/coroutine context rather than
  directly from a raw signal handler.

### Cross-platform constraint

Because `loop.add_signal_handler()` is Unix-only, the design space splits:

- Unix: explicit `SIGINT`/`SIGTERM` registration can be done through asyncio’s
  native signal API.
- Non-Unix: that exact API is unavailable, so graceful signal integration
  cannot rely on `loop.add_signal_handler()`.

## 4. Logging Configuration at Entry Point Level

`discord.py` uses the standard Python `logging` module for diagnostics and
errors. Its documentation explicitly says that if logging is not configured,
those logs do not go anywhere.

### What `discord.py` already provides

When using `Client.run()`:

- the library can configure logging automatically;
- the default output is to `stderr`;
- the default formatter is colorized when supported;
- `root_logger=True` extends that setup to the root logger;
- `log_handler=None` disables the automatic logging setup.

When not using `Client.run()`:

- the library docs explicitly direct users to `discord.utils.setup_logging()`.
- upstream `setup_logging()` defaults to:
  - `logging.INFO`,
  - `logging.StreamHandler`,
  - a color formatter when supported,
  - otherwise a formatter of the form:
    `[{asctime}] [{levelname:<8}] {name}: {message}`

### Entry-point-level conclusions

For daemon research, the entry point is the correct place to do one-time
process logging setup because:

- it defines process-wide behavior;
- it captures both bootstrap failures and runtime library logs;
- it avoids per-module ad hoc configuration.

For structured output specifically, Python logging supports contextual fields
via:

- the `extra=` argument on log calls, which adds user-defined attributes to the
  `LogRecord`;
- `logging.LoggerAdapter`, which is the standard mechanism for attaching
  contextual information repeatedly.

So the research-supported logging design space is:

- use standard `logging` as the system of record,
- configure it once at the process boundary,
- choose whether only the `discord` logger or the root logger is configured,
- attach daemon-specific context through `extra` or `LoggerAdapter` if more
  structure is needed.

## 5. Error Handling Requirements at the Entry Point

Bootstrap error handling divides into four layers.

### A. Settings loading errors

`BaseSettings` reads missing field values from environment variables. Pydantic
settings documentation states that invalid settings construction raises
`ValidationError` in cases such as missing or invalid values.

For this service, that means settings bootstrap can fail before the bot exists,
for example if:

- `discord_bot_token` is missing or invalid for the declared type,
- `discord_guild_id` is missing or invalid for the declared type,
- `supabase_db_url` is missing or invalid for the declared type.

This is entry-point scope, not bot-runtime scope.

### B. Authentication failures

`discord.Client.login()` documents:

- `LoginFailure` for wrong credentials,
- `HTTPException` for other HTTP-related login failures.

The source also strips surrounding whitespace from the token and raises
`TypeError` if the token is not a string.

### C. Gateway connection failures

`discord.Client.connect()` documents:

- `GatewayNotFound` when Discord’s gateway cannot be found, typically implying
  outage conditions,
- `ConnectionClosed` when the websocket terminates in a way the library cannot
  handle internally.

Also relevant at startup is `PrivilegedIntentsRequired`, which the library
documents as the exception raised when the gateway requests privileged intents
that are not enabled in the Discord developer configuration. This is a real
bootstrap concern here because the stated bot configuration uses
`members=True` and `message_content=True`, both privileged intents.

### D. Controlled shutdown vs real failure

Shutdown-triggered exceptions should not be treated as startup failures:

- `KeyboardInterrupt` is part of the documented `asyncio.run()` / runner
  shutdown path for `SIGINT`.
- task cancellation during graceful stop is part of normal unwinding.

So the top-level error surface should distinguish:

- expected termination paths,
- misconfiguration,
- authentication failures,
- gateway/network/API failures,
- unexpected uncaught exceptions.

### Event-handler errors are a separate concern

`discord.Client.on_error()` logs uncaught event-handler exceptions by default.
That means the package entry point does not need to be the primary handler for
individual Discord event callback failures; those are handled inside the
client/event system and emitted through logging.

## 6. Design-Space Summary

The documented design space looks like this:

- Package invocation:
  - `python -m app` runs `app/__main__.py`.
  - Minimal `__main__.py` is the standard package pattern.
- Async ownership:
  - `asyncio.run()` is Python’s preferred top-level async program runner.
  - `discord.Client.run()` is the library convenience wrapper built around that
    idea.
- Bot lifecycle:
  - `login()` authenticates and calls `setup_hook()`.
  - `connect()` owns the gateway loop.
  - `start()` is `login() + connect()`.
  - `run()` is the blocking convenience API.
- Shutdown:
  - `asyncio.run()` already handles `SIGINT`/Ctrl-C in a structured way.
  - explicit `SIGTERM` handling requires application wiring if graceful
    termination is required.
  - `loop.add_signal_handler()` is the asyncio-native API, but only on Unix.
- Logging:
  - configure once at process entry;
  - `discord.py` logging is standard Python logging;
  - `discord.utils.setup_logging()` is the documented helper when not using
    `Client.run()`.
- Errors:
  - settings construction errors happen before bot startup;
  - login and gateway failures are the main daemon bootstrap failure classes;
  - privileged intents are a startup-time risk for this bot’s stated intents.

## Relevant API References

- Python `__main__` docs:
  - https://docs.python.org/3/library/__main__.html
- Python asyncio runners:
  - https://docs.python.org/3/library/asyncio-runner.html
- Python asyncio event loop and Unix signals:
  - https://docs.python.org/3/library/asyncio-eventloop.html
- Python logging:
  - https://docs.python.org/3/library/logging.html
- `discord.py` client API:
  - https://discordpy.readthedocs.io/en/stable/api.html#discord.Client
  - https://discordpy.readthedocs.io/en/stable/api.html#discord.Client.login
  - https://discordpy.readthedocs.io/en/stable/api.html#discord.Client.connect
  - https://discordpy.readthedocs.io/en/stable/api.html#discord.Client.start
  - https://discordpy.readthedocs.io/en/stable/api.html#discord.Client.run
  - https://discordpy.readthedocs.io/en/stable/api.html#discord.Client.close
- `discord.py` logging setup:
  - https://discordpy.readthedocs.io/en/stable/logging.html
  - https://discordpy.readthedocs.io/en/stable/api.html#discord.utils.setup_logging
- `discord.ext.commands.Bot` inheritance from `Client`:
  - https://discordpy.readthedocs.io/en/stable/ext/commands/api.html#discord.ext.commands.Bot
- Pydantic settings:
  - https://docs.pydantic.dev/2.4/concepts/pydantic_settings/
  - https://docs.pydantic.dev/latest/api/pydantic_settings/

## Source Notes

Two small conclusions above are inferences rather than explicit statements in a
single source:

- running from `services/discord` makes `app` import-resolvable from that
  directory for `python -m app`;
- `SIGTERM` requires explicit application handling because Python’s runner docs
  explicitly document special behavior for `SIGINT` and do not document an
  equivalent built-in `SIGTERM` path.
