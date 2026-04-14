# Proposal prompt — Discord service `app/__main__.py`

YOU are the proposal writer. YOU write the proposal yourself. Do NOT
delegate to sub-agents or launch subprocesses.

## Task

Write a concrete design proposal for `services/discord/app/__main__.py`
— the Discord daemon package entry point.

## Context

Read these files before writing:
- `research/25-discord-main.md` — research findings
- `research/25-discord-main-needs.md` — synthesis of needs
- `services/discord/app/core/settings.py` — Settings class
- `services/discord/app/core/bot.py` — HumilityBot class

## Proposal requirements

The proposal must specify:

1. **Module structure**: exact imports, function signatures, module
   docstring
2. **`main()` coroutine**: the async entry point
   - Logging setup (use `discord.utils.setup_logging()` or standard
     `logging.basicConfig`)
   - Settings construction with `ValidationError` catch
   - Bot construction
   - SIGTERM handler wiring
   - `bot.start()` with try/finally `bot.close()`
3. **Signal handling**: how SIGTERM triggers graceful shutdown
4. **Error handling**: what exceptions are caught at the top level and
   what exit codes they produce
5. **Entry guard**: `asyncio.run(main())` at module level
6. **Anti-scope**: what does NOT belong in this file (business logic,
   event handlers, command registration)

## Deliverables

Write the proposal to `proposals/25-discord-main.md`. Include:
- Architecture (what the file does, how it fits in the service)
- Exact function signatures
- Error handling strategy
- Exit code table
- Anti-scope list
- Tradeoffs considered

## Rules

- Do NOT write code — describe the design
- Do NOT modify any files other than `proposals/25-discord-main.md`
- Do NOT inspect the live Discord server
- Do NOT implement anything
