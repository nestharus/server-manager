# Proposal: `daemon/__init__.py`

Date: 2026-04-13

## Goal

Define the design for `daemon/__init__.py` as the package marker for
the Humility Discord daemon.

This proposal is design only. It does not include implementation code.

## Summary

`daemon/__init__.py` should be intentionally minimal:

- make `daemon/` a regular Python package
- contain a PEP 257 multi-line package docstring
- describe the package as the long-running Discord daemon for the
  Humility guild
- note that `discord_cli.py` remains the separate one-shot
  inspection/admin CLI
- list the planned daemon submodules: `config`, `db`, `claim`,
  `applications`, `tickets`, `chapters`, and `util`
- contain no executable setup logic and no package-level API surface

The file should function as documentation plus package marker, not as a
convenience import layer.

## Exact Scope

The file should contain exactly two things:

1. The existence of `daemon/__init__.py` so Python treats `daemon/` as a
   regular package.
2. A package docstring that follows PEP 257:
   - first line: concise summary of the package purpose
   - blank line
   - short descriptive paragraph explaining that this package holds the
     long-running daemon implementation for the Humility guild
   - a note that `discord_cli.py` is the separate one-shot CLI for
     inspection and administrative tasks
   - a short module inventory listing the planned submodules and their
     roles at a high level

There should be no additional statements after the docstring.

## Architecture

### Regular package marker

`daemon/` should be an explicit regular package, not a namespace
package. This repo is a single-directory application package inside one
repository, and the daemon design expects direct imports such as
`from daemon.config import ...` and `from daemon.db import ...`.

Using `__init__.py` makes that package boundary explicit and matches the
rest of the project’s flat-layout import model.

### Package-level documentation only

The package docstring should do the orientation work:

- define the daemon package’s purpose
- distinguish it from `discord_cli.py`
- document the expected submodule layout

That keeps the package root useful for readers and future contributors
without turning it into a runtime coordination point.

### Direct submodule imports

Submodules should be imported directly by callers:

- `daemon.config`
- `daemon.db`
- `daemon.claim`
- `daemon.applications`
- `daemon.tickets`
- `daemon.chapters`
- `daemon.util`

`daemon/__init__.py` should not re-export objects from those modules.
This keeps package imports cheap, avoids hidden import-time coupling, and
prevents the package root from becoming an unstable public API surface.

## Tradeoffs

### Benefits

- Explicit package marker removes ambiguity about package type.
- A package docstring gives one canonical description of the daemon
  package and its module layout.
- Keeping the file docstring-only avoids side effects during
  `import daemon`.
- No re-exports means less import-time coupling between submodules.
- No package version metadata avoids duplicating version information that
  already lives in `pyproject.toml`.

### Costs

- `import daemon` will not expose convenience names such as
  `daemon.Database` or `daemon.load_config`.
- Callers must continue to import from concrete submodules.
- The package root will remain intentionally sparse, which is slightly
  less convenient for interactive discovery than a curated top-level API.

For this repo, those costs are acceptable because `daemon/` is an
internal application package, not a reusable library intended to present
one consolidated import surface.

## Anti-scope

`daemon/__init__.py` should not contain:

- re-exports from submodules
- package-level imports solely to populate the root namespace
- `__version__`, `version_info`, or any other version constant
- `__all__`
- config loading, environment reads, logging setup, database setup, or
  Discord client setup
- helper functions, constants, registries, or compatibility shims
- any runtime behavior beyond the normal execution of the docstring as
  module metadata

## Decision

Treat `daemon/__init__.py` as a package marker and package docstring
only. The correct design is a minimal file that documents the daemon
package, points readers to the separate CLI boundary, and leaves all
runtime behavior in `daemon.py` and the daemon submodules.
