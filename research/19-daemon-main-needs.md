# Needs Synthesis: daemon/__main__.py

Date: 2026-04-13

## Context

The old `daemon.py` entry point was deleted because it conflicts with the
`daemon/` package name. `daemon/__main__.py` replaces it, enabling
`python -m daemon` execution.

## Key Decisions

### Bot class name
The applications.py TYPE_CHECKING import uses `HumilityBot`, not
`HumilityDaemonBot`. The class in __main__.py should be named `HumilityBot`
to match. This is a deliberate rename from the old `HumilityDaemonBot`.

### Applications wiring
`setup_hook()` must call `await setup_applications(self)` from
`daemon.applications` before `self.tree.sync(guild=guild)`. This registers
the `/apply` command and persistent review views.

### Import compatibility
`from daemon.__main__ import HumilityBot` must work for TYPE_CHECKING in
`daemon/applications.py`. The `if __name__ == "__main__"` guard must not
prevent imports.

### ENV_PATH and BASE_PATH
With the file now at `daemon/__main__.py`, `Path(__file__).resolve().parent`
points to `daemon/`, not the repo root. `BASE_PATH` should be the repo root
(parent of the daemon package), so it should be
`Path(__file__).resolve().parent.parent`.

## Minimum Surface

- `HumilityBot` (class, commands.Bot subclass)
- `RuntimeConfig` (dataclass)
- `get_runtime_config()` → RuntimeConfig
- `build_intents()` → discord.Intents
- `main()` → async entry point
- `if __name__ == "__main__"` guard calling `asyncio.run(main())`

## Gaps

None — this is a straightforward port with the name change and applications
wiring addition.
