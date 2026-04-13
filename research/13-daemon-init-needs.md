# Synthesis: daemon/__init__.py Needs

Date: 2026-04-13

## Context

Research in `research/13-daemon-init.md` established that:
- `daemon/__init__.py` is the standard marker for a regular Python package
- PEP 257 says package docstrings should document the package and its submodules
- Broad re-exports are a library convention (`discord.py`), not needed for an internal application package
- Runtime `__version__` is optional and the distribution name (`discord-server-manager`) differs from the import package name (`daemon`)
- The flat layout in `pyproject.toml` with `pythonpath = ["."]` makes `daemon/` importable from tests and the entry point

## Humility-Specific Needs

1. **Package marker**: `daemon/` must be a regular package so `daemon.py` (the entry point) can `from daemon.config import ...`, `from daemon.db import ...`, etc.

2. **Package docstring**: Should explain this is the long-running Discord daemon for the Humility guild, and that `discord_cli.py` remains the one-shot inspection/admin CLI. Should list the planned submodules per PEP 257.

3. **No re-exports needed**: The daemon submodules (`config`, `db`, `claim`, etc.) are imported directly by the entry point and by each other. There is no external consumer that needs a curated `daemon.SomeClass` API surface. Keeping `__init__.py` minimal avoids import-time coupling.

4. **No `__version__` needed**: The version lives in `pyproject.toml` under a different distribution name. There's no consumer that would read `daemon.__version__`. Adding it would require a version-sync mechanism for no benefit.

5. **No `__all__` needed**: No star-imports from the daemon package are planned or desirable.

## Gaps

None. The file is straightforward: package docstring + empty body. The research is complete for scoping a proposal.
