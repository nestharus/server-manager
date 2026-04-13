# Hookpoint Research: `daemon/__init__.py`

Date: 2026-04-13

## Scope

This note maps [proposals/13-daemon-init.md](/home/nes/discord/proposals/13-daemon-init.md:1)
onto the current repository. It is hookpoint-only research for
`daemon/__init__.py`: what already exists, what would conflict, where
the file should land, and which code-style conventions it should follow.

This document does not include implementation code.

## 1. What already exists and can be reused

### Existing architectural boundary

- The daemon architecture is already defined in
  [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:3).
- That design explicitly reserves a top-level `daemon.py` entry point and
  a sibling `daemon/` directory for the daemon submodules at
  [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:10).
- The same design also states that
  [discord_cli.py](/home/nes/discord/discord_cli.py:2) remains the
  separate one-shot inspection/admin CLI, while the daemon handles the
  long-running interaction flow at
  [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:191).

This is reusable as the package-level framing for `daemon/__init__.py`:
the proposal does not need to invent package purpose or boundaries from
scratch because the repo already has them documented.

### Existing flat-layout import model

- [pyproject.toml](/home/nes/discord/pyproject.toml:18) sets
  `pythonpath = ["."]` for tests.
- The project is currently a flat top-level layout with modules such as
  [discord_cli.py](/home/nes/discord/discord_cli.py:1) living directly
  at repo root, not under `src/`.
- A repo scan found no existing `__init__.py` files in the main tree, so
  adding `daemon/__init__.py` would be the first explicit package marker
  in the repository.

This is reusable because it means the proposal fits the current import
shape directly. No packaging rework is needed just to make `daemon/` an
importable regular package.

### Existing style reference

[discord_cli.py](/home/nes/discord/discord_cli.py:1) provides the best
local style reference for daemon modules:

- module-level docstring first
- `from __future__ import annotations` immediately after the docstring at
  [discord_cli.py](/home/nes/discord/discord_cli.py:4)
- standard-library imports first, third-party imports second at
  [discord_cli.py](/home/nes/discord/discord_cli.py:6)
- module-level constants in uppercase at
  [discord_cli.py](/home/nes/discord/discord_cli.py:17)
- modern Python 3.12 typing syntax throughout, including built-in
  generics and `|` unions

For `daemon/__init__.py` specifically, only the docstring pattern is
directly reusable. The proposal explicitly rejects the CLI's top-level
environment-loading behavior.

## 2. Existing `daemon` definitions and conflicts

### Current tree: no live `daemon` module or package

There is no current `daemon.py` file and no current `daemon/` directory
in the main repository tree. References to `daemon.py` and `daemon/`
exist only in design/proposal documents:

- [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:10)
- [proposals/13-daemon-init.md](/home/nes/discord/proposals/13-daemon-init.md:14)

So the answer to "does any existing code already define a `daemon`
package or module?" is no.

### Current conflict surface: none

Because neither `daemon.py` nor `daemon/` exists yet, adding
`daemon/__init__.py` does not currently collide with any live file,
package marker, import path, or test path.

Nothing needs to be deleted to make room for `daemon/__init__.py`.

### Future name overlap to be aware of

The design expects both:

- `daemon.py` as the executable entry point
- `daemon/` as the internal package

That creates a same-name module/package pair at repo root. I verified
the import behavior locally with `uv run python`: when both exist in the
same directory, `import daemon` resolves to the package
`daemon/__init__.py`, not the sibling `daemon.py`. I also verified that
running `python daemon.py` can still import `from daemon.config import`
from the package.

So this is not a blocker for the proposal, but it is an insertion-point
constraint:

- package imports should stay explicit, e.g. `from daemon.config import ...`
- `daemon/__init__.py` should remain minimal and not try to mirror the
  entrypoint
- contributors should expect `daemon` to mean the package in import
  contexts, even after `daemon.py` exists

## 3. Import patterns the daemon modules should follow

The proposal says future callers should import concrete submodules such
as `daemon.config` and `daemon.db` at
[proposals/13-daemon-init.md](/home/nes/discord/proposals/13-daemon-init.md:70).
That matches the current local import style better than re-exporting.

Patterns visible in [discord_cli.py](/home/nes/discord/discord_cli.py:4):

- prefer module-level imports over deep symbol fan-out
- use a small number of direct `from ... import ...` imports only when
  they are stable and obvious, such as
  `from pathlib import Path` or `from dotenv import load_dotenv`
- keep third-party modules namespace-qualified where that improves
  readability, as with `import discord`

Mapped onto the daemon package, the safest fit is:

- direct submodule imports by callers: `from daemon.config import ...`
- no package-root re-exports
- no package-root convenience aliases

That also matches the proposal's anti-scope at
[proposals/13-daemon-init.md](/home/nes/discord/proposals/13-daemon-init.md:113).

## 4. Insertion points

### Filesystem insertion point

The package should land as a new top-level directory:

- `daemon/`
- `daemon/__init__.py`

This should sit alongside:

- [discord_cli.py](/home/nes/discord/discord_cli.py:1)
- [chapters.yaml](/home/nes/discord/chapters.yaml)
- [forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:1)

This placement is already implied by the architecture diagram in
[docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:9).

### Parallel work boundary

`daemon/__init__.py` is unusually parallel-friendly because the proposal
keeps it docstring-only:

- it does not need `daemon.config`, `daemon.db`, or other submodules to
  exist first
- it does not need `daemon.py` to exist first
- it does not require `pyproject.toml` changes
- it does not require `discord_cli.py` changes

That means `daemon/__init__.py` can land independently of the rest of
the daemon implementation. Future work on `daemon.py`, `daemon/config.py`,
`daemon/db.py`, and the other submodules can proceed in parallel because
the package marker does not import or re-export them.

### What should not be touched for this proposal

No insertion point exists in:

- [discord_cli.py](/home/nes/discord/discord_cli.py:655)
- [pyproject.toml](/home/nes/discord/pyproject.toml:1)

Those files are reference material for style and layout, not hookpoints
that need modification for this proposal.

## 5. Code-style conventions to follow

### Docstring conventions

The proposal requires a PEP 257 multi-line package docstring at
[proposals/13-daemon-init.md](/home/nes/discord/proposals/13-daemon-init.md:35).
That fits the current repo style:

- [discord_cli.py](/home/nes/discord/discord_cli.py:2) already opens
  with a concise module docstring
- [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:191)
  already defines the daemon/CLI split the docstring should summarize

The package docstring should therefore be:

- concise on the first line
- explicit about the daemon/CLI boundary
- inventory-oriented rather than API-oriented

### Minimal top-level surface

The local codebase does use top-level executable setup in the CLI, such
as `load_dotenv(ENV_PATH)` at
[discord_cli.py](/home/nes/discord/discord_cli.py:22). For
`daemon/__init__.py`, that is the wrong precedent.

The proposal is explicit that `daemon/__init__.py` should contain no:

- env loading
- logging setup
- database setup
- Discord client setup
- helper functions
- constants
- re-exports

So the style convention to reuse is "keep top-level files easy to scan,"
not "repeat the CLI's runtime setup."

### Python version assumptions

[pyproject.toml](/home/nes/discord/pyproject.toml:5) targets Python
`>=3.12`. That means the daemon package can follow the same modern
syntax conventions already present in [discord_cli.py](/home/nes/discord/discord_cli.py:4)
without back-compat shims.

For `daemon/__init__.py`, this mainly matters as a negative constraint:
there is no need to add compatibility helpers or packaging metadata just
to support older Python versions.

## 6. What to reuse, what conflicts, what to delete

### Reuse

- Reuse the daemon/CLI separation already documented in
  [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:191).
- Reuse the flat repo-root placement implied by
  [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:10)
  and supported by [pyproject.toml](/home/nes/discord/pyproject.toml:18).
- Reuse the local module style from
  [discord_cli.py](/home/nes/discord/discord_cli.py:2): clear docstring,
  modern typing, simple top-level layout.

### Conflicts

- No current code defines a live `daemon` package or module.
- No current file conflicts with `daemon/__init__.py`.
- The only future overlap is the planned `daemon.py` plus `daemon/`
  package name reuse, which is workable as long as imports stay
  submodule-directed.

### Delete

- Nothing in the current codebase needs to be deleted for this proposal.
- No existing import, package marker, or config entry needs removal.

## Conclusion

`daemon/__init__.py` has a clean insertion point in the current repo.
There is no existing `daemon` implementation to unwind, no current file
conflict, and no required edits outside the new package directory. The
main constraint is to keep the file strictly docstring-only so it stays
independent of the future `daemon.py` entry point and the planned daemon
submodules.
