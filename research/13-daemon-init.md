# Research: `daemon/__init__.py` Package Marker for the Discord Daemon

Date: 2026-04-13

## Scope

This note documents the problem space for adding `daemon/__init__.py`
to the planned long-running Discord daemon package. It focuses on:

- what `__init__.py` does in a regular Python package
- what package-level docstring conventions apply
- what package-level exports and version metadata are commonly exposed
- when re-exports are used, and what that implies
- how those conventions fit this repository’s current structure

This is a facts-only research pass. It does not propose an
implementation.

## Local Baseline

- The daemon architecture in [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:1)
  defines a top-level `daemon.py` entry point plus a `daemon/` package
  containing `config.py`, `db.py`, `claim.py`, `applications.py`,
  `tickets.py`, `chapters.py`, and `util.py`.
- The design explicitly separates responsibilities:
  - the daemon is the long-running `discord.py` process handling slash
    commands, buttons, and modals
  - `discord_cli.py` remains the one-shot inspection/admin interface and
    shares the SQLite database with the daemon
- [discord_cli.py](/home/nes/discord/discord_cli.py:1) already uses a
  module docstring that describes its one-shot CLI role.
- [pyproject.toml](/home/nes/discord/pyproject.toml:1) declares:
  - distribution name: `discord-server-manager`
  - version: `0.1.0`
  - dependency target: `discord.py>=2.3`
  - flat-layout test import path: `pythonpath = ["."]`
- In this environment, `uv run python` resolves `discord.py` to `2.7.1`.

## Primary Sources

- Python import system reference:
  https://docs.python.org/3.12/reference/import.html
- Python tutorial, packages/import behavior:
  https://docs.python.org/3.12/tutorial/modules.html
- `importlib.metadata` runtime metadata docs:
  https://docs.python.org/3.12/library/importlib.metadata.html
- PyPA discussion: distribution package vs import package:
  https://packaging.python.org/en/latest/discussions/distribution-package-vs-import-package/
- PyPA discussion: single-sourcing the project version:
  https://packaging.python.org/en/latest/discussions/single-source-version/
- PyPA discussion: src layout vs flat layout:
  https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
- PEP 257 docstring conventions:
  https://peps.python.org/pep-0257/
- `discord.py` top-level package source (`v2.7.1`):
  https://raw.githubusercontent.com/Rapptz/discord.py/v2.7.1/discord/__init__.py

## 1. What `__init__.py` means for this package

Python distinguishes between regular packages and namespace packages.
The import-system reference states that a regular package is typically a
directory containing an `__init__.py` file, and that when the package is
imported, `__init__.py` is implicitly executed and the objects it defines
are bound into the package namespace.

Relevant Python reference points:

- A regular package is "typically implemented as a directory containing
  an `__init__.py` file."
- Importing the package implicitly executes that file.
- Namespace packages do not need `__init__.py`, but exist to assemble a
  package from multiple filesystem portions.

Evidence:

- Python import reference, regular packages:
  https://docs.python.org/3.12/reference/import.html
  - lines 73-86 describe regular packages and implicit execution of
    `__init__.py`
  - lines 89-93 describe namespace packages without `__init__.py`

Repo-specific implication:

- The planned `daemon/` directory in `docs/DAEMON_DESIGN.md` is a normal
  single-directory package inside one repository, not a split namespace
  package. In Python’s terminology, this is the ordinary regular-package
  case.

## 2. What a package-level `__init__.py` can contain

Python treats a package’s `__init__.py` as normal module code. The
tutorial states that modules can contain executable statements as well
as definitions, and those statements are executed the first time the
module is imported. The same package tutorial also notes that names
defined in the package are what `from package import item` sees before
Python falls back to loading a submodule.

Evidence:

- Python tutorial:
  https://docs.python.org/3.12/tutorial/modules.html
  - lines 83-85: top-level module statements run on first import
  - lines 306-307: `from package import item` first checks names defined
    in the package namespace

That means `daemon/__init__.py` can legally hold any of the following
categories of content:

- a package docstring
- package-level constants or metadata
- imports that intentionally place names in the package namespace
- `__all__` to define the names imported by `from package import *`

The same tutorial is explicit that `import *` is generally frowned upon
in production code, and that `__all__` exists specifically to control
that star-import surface.

Evidence:

- Python tutorial:
  https://docs.python.org/3.12/tutorial/modules.html
  - lines 99-101: `import *` is generally frowned upon
  - lines 310-325: `__all__` controls `from package import *`

## 3. Package docstring conventions

PEP 257 distinguishes between module, package, and script docstrings.
Its guidance is directly relevant here because the daemon design has
both:

- a package module: `daemon/__init__.py`
- a stand-alone entrypoint script/module: `daemon.py`

PEP 257 states:

- a multi-line docstring uses a summary line, then a blank line, then a
  more detailed description
- a module docstring should generally list exported classes, functions,
  exceptions, and other public objects
- a package docstring, specifically the docstring of `__init__.py`,
  should also list the modules and subpackages exported by the package
- a script docstring is different: it should be usable as the script’s
  usage message

Evidence:

- PEP 257:
  https://peps.python.org/pep-0257/
  - lines 87-91 cover multi-line summary/blank-line structure and
    package-docstring guidance
  - lines 89-90 cover script docstrings as usage text

Repo-specific implication:

- `discord_cli.py` already matches the "script/module describes its own
  role" pattern with the docstring "One-shot Discord inspection CLI for
  the configured guild."
- The planned `daemon/__init__.py` and `daemon.py` have different
  docstring jobs under PEP 257:
  - package docstring: describe the package and its submodules
  - script docstring: describe the entrypoint as an executable module

## 4. Re-export conventions and their tradeoffs

Python’s import rules allow `__init__.py` to re-export names from
submodules by importing them into the package namespace. The import
reference also notes that once a submodule is loaded, a binding is
placed in the parent package namespace for that submodule. This is why
packages can expose either:

- submodules as package attributes, such as `daemon.db`
- objects re-exported by `__init__.py`, such as `daemon.SomeClass`

Evidence:

- Python import reference:
  https://docs.python.org/3.12/reference/import.html
  - lines 202-218 describe parent-package bindings for submodules
- Python tutorial:
  https://docs.python.org/3.12/tutorial/modules.html
  - lines 306-307 describe `from package import item` resolving against
    package-defined names first

The same sources also imply a cost: because `__init__.py` is executed on
import, every top-level import added there increases package import-time
work and couples `import daemon` to the imported submodules.

### `discord.py` as a contrasting example

The installed dependency `discord.py` exposes a broad top-level API. Its
top-level `discord/__init__.py` in `v2.7.1` contains:

- `__version__`
- `version_info`
- many `from .module import *` statements
- selected submodule aliases such as `utils`, `opus`, `abc`, `ui`, and
  `app_commands`

Evidence:

- `discord.py` source:
  https://raw.githubusercontent.com/Rapptz/discord.py/v2.7.1/discord/__init__.py

Inference from the source:

- This is a library-style package surface designed so `import discord`
  exposes a large public API from one namespace.
- That pattern reflects `discord.py`’s role as a reusable library API.
  It is not just a package marker.

This matters as a convention point: broad re-exporting is normal in
library packages that want a curated top-level API, but Python itself
does not require application-internal packages to expose that kind of
surface.

## 5. Version metadata at package level

The packaging sources separate two related concepts:

- the distribution package name recorded in packaging metadata
- the import package name used in Python code

PyPA’s "Distribution package vs. import package" page states that these
names often match, but this is only a convention and is not guaranteed.
The `importlib.metadata` docs make the same distinction and note that
distribution packages do not necessarily correspond 1:1 with top-level
import package names.

Evidence:

- PyPA:
  https://packaging.python.org/en/latest/discussions/distribution-package-vs-import-package/
  - lines 145-165 distinguish install/distribution names from import
    package names
- `importlib.metadata`:
  https://docs.python.org/3.12/library/importlib.metadata.html
  - lines 51-57 explain that metadata is about installed distribution
    packages, not necessarily one-to-one with import packages
  - lines 182-190 define `version(distribution_name)`

Repo-specific fact:

- The distribution name in `pyproject.toml` is
  `discord-server-manager`.
- The planned import package name is `daemon`.

So the project metadata name and the import-package name are different
in this repository.

PyPA’s versioning guidance says runtime `__version__` is commonly used
when an import package is intended to report the same version as the
distribution package. It lists several possible single-source schemes
and recommends an automated test if the runtime import package version
is intended to match `importlib.metadata.version("dist-name")`.

Evidence:

- PyPA single-source version guide:
  https://packaging.python.org/en/latest/discussions/single-source-version/
  - lines 153-165 describe the common desire for a runtime `__version__`
    and the available version-source patterns
  - line 167 recommends an automated test when `import_name.__version__`
    is intended to match `importlib.metadata.version("dist-name")`

Conventional reading of these sources:

- package-level `__version__` is optional, not inherent to `__init__.py`
- when present, it is part of the package’s runtime API surface
- its semantics are clearest when they map intentionally to a known
  distribution version source

## 6. Interaction with the current repo layout

PyPA defines the repository’s current structure as a flat layout: import
packages and configuration files live together at the repository root.
That matches this repo, where `discord_cli.py`, `pyproject.toml`,
`forms/`, `docs/`, and the planned `daemon/` package all live at the
top level.

Evidence:

- PyPA src-vs-flat guide:
  https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
  - lines 145-158 define flat layout vs src layout
  - lines 174-179 describe that flat layout allows running code directly
    from the source tree because the current working directory is on the
    import path

Repo-specific implications:

- `daemon/` at repo root fits the documented flat-layout pattern.
- `pythonpath = ["."]` in `pyproject.toml` means tests already add the
  repository root to the import path, so a top-level `daemon` package
  would be importable in the same way as `discord_cli.py`.

The Python tutorial also states that modules intended for use as the
main module of a Python application must use absolute imports, because
the main module’s name is always `__main__` and relative imports depend
on the current module’s package name.

Evidence:

- Python tutorial:
  https://docs.python.org/3.12/tutorial/modules.html
  - line 343: modules intended for use as the main module must use
    absolute imports

Repo-specific implication:

- If the planned `daemon.py` is run as the top-level entry point from
  the repo root, that entry point is in the `__main__` case described by
  the tutorial, while modules inside `daemon/` remain ordinary package
  modules.

## 7. What the evidence says about this specific problem space

Taken together, the sources establish the following:

- `daemon/__init__.py` is the normal marker for making `daemon/` a
  regular package, and it is executed when the package is imported.
- A package `__init__.py` may expose metadata, imported names, and
  `__all__`, but none of those are required merely to mark the package.
- PEP 257 treats a package docstring differently from a script
  docstring; package docstrings document the package and exported
  modules/subpackages.
- Broad re-export surfaces are a real Python pattern, but the strongest
  example in this dependency stack (`discord.py`) is a library package,
  not an internal application package.
- Runtime `__version__` is a convention, not a language requirement, and
  PyPA treats it as meaningful when it intentionally corresponds to
  distribution metadata.
- This repository’s `pyproject.toml` names the distribution
  `discord-server-manager`, while the planned package name is `daemon`,
  so package-level version exposure and distribution metadata are not
  automatically the same concept here.
- The repo is using flat-layout conventions, so a root-level `daemon/`
  package fits the existing import structure alongside `discord_cli.py`
  and the planned `daemon.py` entrypoint.
