# Hookpoint Research: `daemon/config.py`

Date: 2026-04-13

## Scope

This note maps [proposals/14-config.md](/home/nes/discord/proposals/14-config.md:1)
onto the current repository.

It is hookpoint-only research for `daemon/config.py`:

- what already exists and is reusable
- what can proceed in parallel
- what, if anything, should be deleted or explicitly not carried forward

This document does not include implementation code.

## 1. What already exists and is reusable

### Existing package slot and file layout

The insertion point already exists at the architecture level:

- [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:7)
  already reserves `daemon/config.py` as the module that loads
  `chapters.yaml` plus `forms/*.yaml`.
- [daemon/__init__.py](/home/nes/discord/daemon/__init__.py:1) already
  marks `daemon/` as the package and names `config` as a planned
  submodule.
- [tests/test_daemon_init.py](/home/nes/discord/tests/test_daemon_init.py:7)
  already treats `"config"` as one of the expected daemon submodules.

This is reusable directly. `daemon/config.py` does not need a packaging
change, a new top-level directory, or a new naming decision.

### Existing config files

The proposal's file inputs already exist in the tree:

- [chapters.yaml](/home/nes/discord/chapters.yaml:1) is already the
  daemon's "source of truth" registry and is already described as being
  read on startup and `/reload`.
- [forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:7)
  already provides one concrete form file with the exact top-level keys
  the proposal expects today: `id`, `title`, and `questions`.

The Dark Nemesis sample is especially reusable because it already
matches the proposal's supported question-type set:

- `short` at [forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:10)
- `select` at [forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:15)
- `multi_select` at [forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:45)
- `number` at [forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:54)
- `long` at [forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:69)

### Existing dependency baseline

- [pyproject.toml](/home/nes/discord/pyproject.toml:5) already targets
  Python `>=3.12`.
- [pyproject.toml](/home/nes/discord/pyproject.toml:6) already declares
  `PyYAML`.
- [pyproject.toml](/home/nes/discord/pyproject.toml:18) sets
  `pythonpath = ["."]`, which matches the flat repo-root import layout.

So the proposal's use of `Path`, dataclasses, tuple-based immutable
shapes, and a small `yaml.safe_load`-style loader can fit the current
environment without dependency or layout churn.

### Existing error-handling style to borrow from

[discord_cli.py](/home/nes/discord/discord_cli.py:25) already uses a
small custom exception type with operator-facing messages and optional
structured details. It also uses direct guard-clause validation before
doing work, for example at
[discord_cli.py](/home/nes/discord/discord_cli.py:538) and
[discord_cli.py](/home/nes/discord/discord_cli.py:556).

That is the closest reusable validation style:

- explicit checks
- fail early
- small exception hierarchy
- human-readable messages

The proposal should borrow that style, not the CLI's Discord/runtime
behavior.

## 2. What does not already exist

### No live YAML loader today

A repo-wide search of the main tree found no live `import yaml`,
`yaml.safe_load`, or other YAML-loading code outside docs/research
artifacts. In current code, YAML is a declared dependency and a file
format already present in the repo, but not yet a runtime behavior.

That means `daemon/config.py` is a new module, not a refactor of an
older config layer.

### No existing dataclass pattern today

A repo-wide search of the main tree found no existing `@dataclass`
usage. The live code is currently plain functions, plain exceptions, and
plain dict/list payload shaping, especially in
[discord_cli.py](/home/nes/discord/discord_cli.py:1).

So the proposal's immutable dataclasses are compatible with the repo,
but they are not reusing an established local pattern. `daemon/config.py`
would introduce the first dataclass-based model in the main tree.

### No current chapter-entry schema in real data

[chapters.yaml](/home/nes/discord/chapters.yaml:10) is still
`chapters: []`.

That means these proposed `ChapterConfig` fields are new schema surface,
not existing data being typed:

- `display_name`
- the chapter/category/role/channel snowflake fields

The hookpoint implication is simple: form loading can be grounded in a
real example today, but chapter-registry loading is still being defined
from proposal/design docs rather than from populated repository data.

## 3. Import path and package shape

The correct import shape is already visible from the package tests:

- [tests/test_daemon_init.py](/home/nes/discord/tests/test_daemon_init.py:18)
  imports `daemon` as a package.
- [tests/test_daemon_init.py](/home/nes/discord/tests/test_daemon_init.py:52)
  asserts that the package must not define `__all__`.
- [tests/test_daemon_init.py](/home/nes/discord/tests/test_daemon_init.py:59)
  asserts that the package has no public names at all.

So the correct consumer path for the new module is:

- `from daemon.config import load_config, load_form_config`
- `from daemon.config import ConfigError, ConfigParseError, ConfigValidationError`
- not `from daemon import load_config`

The package root is intentionally empty. `daemon/__init__.py` is not a
hookpoint for re-exports.

## 4. Validation patterns to follow

The existing codebase does not have a generic validation framework. The
closest pattern is the CLI's simple, explicit input validation.

Good patterns to follow from current code:

- use a small dedicated exception type rather than returning sentinel
  values ([discord_cli.py](/home/nes/discord/discord_cli.py:25))
- validate inputs before constructing downstream objects
  ([discord_cli.py](/home/nes/discord/discord_cli.py:538))
- keep messages written for the operator, not just the implementer

Patterns not to reuse from current code:

- top-level env loading via `load_dotenv(...)` at
  [discord_cli.py](/home/nes/discord/discord_cli.py:17)
- `.env`-driven config lookup in `get_config()` at
  [discord_cli.py](/home/nes/discord/discord_cli.py:50)
- JSON payload formatting helpers, which are CLI-specific

That split matches the proposal's anti-scope at
[proposals/14-config.md](/home/nes/discord/proposals/14-config.md:363).

## 5. Parallel work boundaries

### Safe to build in parallel

`daemon/config.py` is mostly parallel-friendly because its inputs are
repo files and its output is pure Python objects:

- it does not need Discord connectivity
- it does not need SQLite
- it does not need `.env`
- it does not need the rest of the daemon runtime to exist first

That follows both the proposal's purity requirement at
[proposals/14-config.md](/home/nes/discord/proposals/14-config.md:14)
and the current daemon package constraint that the package root exports
nothing ([tests/test_daemon_init.py](/home/nes/discord/tests/test_daemon_init.py:59)).

Practical parallel tracks:

- `daemon/config.py` implementation
- unit tests for loader/validation behavior
- population of future `chapters.yaml` entries
- authoring of additional `forms/*.yaml`

### Shared contract with later daemon code

The one important parallel boundary is the derived step-plan shape:

- the proposal wants `FormStepConfig` so `daemon.applications` can
  consume a precomputed plan
  ([proposals/14-config.md](/home/nes/discord/proposals/14-config.md:107),
  [proposals/14-config.md](/home/nes/discord/proposals/14-config.md:117))
- the daemon design already says application forms are split according
  to Discord modal/select constraints
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:84))

So `daemon/config.py` and `daemon.applications` can proceed in parallel
only if they agree on the step-plan contract early.

## 6. Existing design tensions to call out

### Step-order wording is not fully aligned

The daemon design says multi-step forms are split as:

- `modal -> select menus -> modal -> etc.`
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:94))

The proposal is stricter:

- collect all modal-compatible questions first
- then all select questions
- final `steps` is all modal chunks first, then all select chunks
  ([proposals/14-config.md](/home/nes/discord/proposals/14-config.md:293))

These are consistent for the current Dark Nemesis example, but they are
not the same general rule for larger future forms. If the proposal is
implemented as written, the broader wording in
[docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:94)
should be tightened later.

### The older applications sketch is broader than the new config schema

[docs/APPLICATIONS_SKETCH.md](/home/nes/discord/docs/APPLICATIONS_SKETCH.md:23)
describes forms as containing not just questions, but also review
destination, reviewer roles, and approval/rejection actions.

The proposal narrows `daemon/config.py` to a closed form schema with:

- `id`
- `title`
- `questions`
  ([proposals/14-config.md](/home/nes/discord/proposals/14-config.md:235))

That means the applications sketch is not a direct schema hookpoint for
this proposal. Those broader form fields are either deferred or belong
in a later config revision, not in the first `daemon/config.py`
contract.

## 7. What to delete, and what not to carry forward

### Delete from current code: nothing

There is no existing config module, YAML loader, or dataclass model to
remove. Nothing in the live codebase has to be deleted to make room for
`daemon/config.py`.

### Do not carry these ideas forward into the loader

The proposal is explicit here, and the current codebase gives no reason
to violate it:

- do not reuse the CLI's env-loading path
- do not put Discord API access in the loader
- do not put SQLite access in the loader
- do not scan `forms/` to auto-discover active chapters
- do not add authored `form_path` to `chapters.yaml`

That last point matters because the daemon design's SQLite schema still
stores `form_path` as persisted metadata at
[docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:106),
but the proposal clearly treats `form_path` as a computed field in
memory rather than a YAML-authored field
([proposals/14-config.md](/home/nes/discord/proposals/14-config.md:67),
[proposals/14-config.md](/home/nes/discord/proposals/14-config.md:139)).

## Conclusion

`daemon/config.py` is mostly a greenfield module with strong non-code
reuse:

- the package slot already exists
- the YAML files already exist
- the dependency baseline already exists
- the import path is already implied as `from daemon.config import ...`

What does not exist yet is exactly the loader itself: no current YAML
parsing code, no current dataclass model, and no current populated
chapter registry. Nothing needs deletion in live code. The main caution
is to keep the module pure and to treat the proposal's stricter
step-planning rule as superseding the looser wording in the daemon
design if both remain in the repo.
