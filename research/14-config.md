# Research: `daemon/config.py` YAML Config Loader

Date: 2026-04-13

## Scope

This note documents the current problem space for the planned
`daemon/config.py` YAML loader.

It is limited to:

- what the repo currently says the loader must read
- what the current YAML files actually contain
- what PyYAML provides in the local environment
- what validation and error cases follow directly from those sources

It does not propose an implementation and does not cover application
submission logic, ticket logic, or Discord-side runtime behavior beyond
what is already stated in the daemon design.

## Local Baseline

- The daemon design defines [daemon/config.py](/home/nes/discord/docs/DAEMON_DESIGN.md:12)
  as the module that loads `chapters.yaml` plus `forms/*.yaml`.
- The same design says YAML config files live in-repo and are part of
  the daemon’s startup/reload path
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:3),
  [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:184)).
- The existing `daemon` package marker already lists `config` as the
  planned submodule for repo-managed configuration
  ([daemon/__init__.py](/home/nes/discord/daemon/__init__.py:7)).
- [pyproject.toml](/home/nes/discord/pyproject.toml:5) sets the Python
  baseline to `>=3.12` and declares `PyYAML` as a dependency
  ([pyproject.toml](/home/nes/discord/pyproject.toml:6)).
- The current chapter registry file is present but empty:
  [chapters.yaml](/home/nes/discord/chapters.yaml:10).
- The only current form definition is
  [forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:7).

## Primary Sources

- Local repo files:
  - [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:1)
  - [chapters.yaml](/home/nes/discord/chapters.yaml:1)
  - [forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:1)
  - [discord_cli.py](/home/nes/discord/discord_cli.py:1)
  - [pyproject.toml](/home/nes/discord/pyproject.toml:1)
- Local runtime inspection:
  - `uv run python` imports `yaml 6.0.3` in this repo
  - local `inspect.getdoc()` / `inspect.getsource()` on `yaml.safe_load`,
    `yaml.safe_load_all`, `yaml.full_load`, and `yaml.unsafe_load`
  - local parse experiments with empty YAML and malformed YAML

## 1. What the loader is expected to read

The daemon design is explicit about the config file set:

- `chapters.yaml` is the registry of active chapters
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:19)).
- `forms/*.yaml` stores one form per chapter
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:20)).
- The chapter provisioning flow says creating a chapter both registers it
  in `chapters.yaml` and associates it with `forms/<slug>.yaml`
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:65)).

`chapters.yaml` adds two more facts:

- it is the "source of truth" for which chapters exist and how they are
  wired up ([chapters.yaml](/home/nes/discord/chapters.yaml:3))
- it is read by the daemon "on startup and on `/reload`"
  ([chapters.yaml](/home/nes/discord/chapters.yaml:4))

Evidence limit in the current repo:

- the file only shows `chapters: []`, so the exact per-chapter mapping
  shape is not yet exemplified in a real chapter entry
  ([chapters.yaml](/home/nes/discord/chapters.yaml:10))

## 2. What PyYAML provides locally for safe loading

The project currently depends on `PyYAML` and no other YAML library
([pyproject.toml](/home/nes/discord/pyproject.toml:6)).

In the local environment, `uv run python` reports `yaml.__version__ ==
6.0.3`.

Observed local docstrings/source:

- `yaml.safe_load(stream)`:
  - "Parse the first YAML document in a stream"
  - "Resolve only basic YAML tags. This is known to be safe for
    untrusted input."
- `yaml.safe_load_all(stream)`:
  - parses all YAML documents
  - the same "basic tags" / "safe for untrusted input" language
- `yaml.full_load(stream)`:
  - resolves all tags except those known to be unsafe on untrusted input
- `yaml.unsafe_load(stream)`:
  - resolves all tags, including ones known to be unsafe on untrusted
    input

Direct consequence for this repo’s files:

- the current config files are single-document YAML examples, so
  `safe_load` matches the current file shape better than
  `safe_load_all`
- `safe_load` returns ordinary Python objects produced from YAML
  mappings/sequences/scalars rather than repo-specific typed objects

Observed local parse behavior:

- `yaml.safe_load("chapters: []\n")` returns `{"chapters": []}`
- `yaml.safe_load("")` returns `None`
- `yaml.safe_load("# only comments\n")` returns `None`

This means "empty file" and "malformed file" are distinct cases in
PyYAML:

- empty/comments-only YAML is not a parser error; it loads as `None`
- syntactically invalid YAML raises a `YAMLError` subclass

Malformed-input experiments in the local environment raised:

- `yaml.parser.ParserError`
- `yaml.scanner.ScannerError`

Both inherit from `yaml.error.MarkedYAMLError`, which inherits from
`yaml.error.YAMLError`.

## 3. What the current chapter registry file actually shows

The current [chapters.yaml](/home/nes/discord/chapters.yaml:1) file
shows only this top-level structure:

```yaml
chapters: []
```

Facts that are explicit today:

- the top-level key is named `chapters`
- its value is intended to be a YAML sequence
- the file is expected to live at repo root
- the daemon reads it at startup and `/reload`

Facts that are not explicit today:

- the exact keys expected inside each chapter entry
- whether the chapter entry stores the form path literally, stores only
  the slug, or stores both
- whether `display_name` lives in `chapters.yaml`, in the form file, or
  elsewhere

The design document does establish two minimum chapter-to-form facts:

- chapter creation is keyed by chapter slug
- the form lives at `forms/<slug>.yaml`

That appears in the provisioning flow
([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:61)).

## 4. What the current form file actually shows

The only concrete form schema in the repo is
[forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:7).

Its top-level keys are:

- `id`
- `title`
- `questions`

Each current question entry contains at least:

- `id`
- `type`
- `label`
- `required`

Some question entries additionally contain:

- `max_length`
- `options`

The sample file contains seven questions:

1. `in_game_name` with type `short`
2. `timezone` with type `select`
3. `daily_events` with type `multi_select`
4. `hours_per_day` with type `number`
5. `launch_budget_usd` with type `number`
6. `monthly_budget_usd` with type `number`
7. `pvp_mmorpg_experience` with type `long`

Evidence from the sample schema:

- `options` appears on `select` and `multi_select`
  ([forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:19),
  [forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:51))
- `max_length` appears on `short`, `number`, and `long`
  ([forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:14),
  [forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:60),
  [forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:75))
- `required` can be both `true` and `false`
  ([forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:13),
  [forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:74))

Evidence limit in the current repo:

- there is only one form file
- there is no second example showing optional top-level fields,
  alternate question shapes, or chapter-specific metadata

## 5. Supported question types and multi-step splitting

The daemon design defines the supported form question types for v1:

- `short`
- `long`
- `select`
- `multi_select`
- `number`

Source:
[docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:84).

The same section ties those types to Discord UI constraints:

- Discord modals support at most 5 components per modal
- modal component types are limited to `short` and `paragraph` text
  inputs
- `short` and `long` map to native modal text inputs
- `select` and `multi_select` are not modal-native and instead require
  follow-up ephemeral select menus
- `number` is collected as text input with server-side numeric
  validation

Source:
[docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:86).

The design also includes one concrete split example for the Dark Nemesis
form:

- total question count: 7
- first modal step:
  - `ign`
  - `hours`
  - `budget_launch`
  - `budget_monthly`
  - `experience`
- follow-up ephemeral step:
  - `timezone` select
  - `daily_events` multi-select
- final submit occurs after the last menu answer

Source:
[docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:94).

Important boundary for the loader:

- the YAML file itself does not contain explicit "step" metadata in the
  current sample
- the split behavior is described as runtime behavior derived from
  question count and question types

## 6. Evidence relevant to structured config types

The repo’s current Python style is stdlib-leaning:

- `discord_cli.py` uses `pathlib.Path`, builtin exceptions, a custom
  `CLIError`, and `typing` annotations such as `dict[str, Any]`,
  `tuple[str, int]`, and `Callable`
  ([discord_cli.py](/home/nes/discord/discord_cli.py:11),
  [discord_cli.py](/home/nes/discord/discord_cli.py:25),
  [discord_cli.py](/home/nes/discord/discord_cli.py:50),
  [discord_cli.py](/home/nes/discord/discord_cli.py:75)).
- A repo-wide search for `dataclass`, `TypedDict`, `BaseModel`, and
  `pydantic` returned no matches in the current codebase.
- `pyproject.toml` does not declare `pydantic`, `attrs`, or another
  schema/validation dependency
  ([pyproject.toml](/home/nes/discord/pyproject.toml:6)).

Concrete facts that follow from the environment:

- plain Python `dict` / `list` shapes are what `yaml.safe_load`
  naturally returns
- `dataclasses` and `typing.TypedDict` are available in Python `>=3.12`
  without adding a new dependency
- `Pydantic` is not currently part of the declared dependency set

This is the current evidence base for any later type-shape decision. The
repo does not yet establish a project-local convention for config models.

## 7. Validation that is directly implied by current sources

The current sources imply several load-time invariants, even though they
do not yet specify a full validation policy.

### 7.1 File-level invariants

- `chapters.yaml` must exist at repo root if the daemon is expected to
  read it on startup or `/reload`
  ([chapters.yaml](/home/nes/discord/chapters.yaml:4)).
- The form file for a chapter must exist under `forms/<slug>.yaml`
  because that path convention is stated in the design
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:69)).
- Each file must parse as YAML rather than raising `YAMLError`.

### 7.2 Shape invariants from current YAML examples

- `chapters.yaml` currently expects a top-level mapping with a
  `chapters` key whose value is a sequence
  ([chapters.yaml](/home/nes/discord/chapters.yaml:10)).
- A form file currently expects top-level `id`, `title`, and
  `questions`
  ([forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:7)).
- Each question in the sample form has `id`, `type`, `label`, and
  `required`
  ([forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:10)).

### 7.3 Semantic invariants from the daemon design

- question `type` must be one of the v1-supported types listed in the
  design
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:84)).
- `select` and `multi_select` questions need choice data, because the
  design says they are rendered as follow-up select menus; the current
  sample expresses that via `options`
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:90),
  [forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:19)).
- `number` questions are expected to undergo numeric validation
  server-side, so the loader at minimum needs to preserve that a
  question’s declared type is `number`
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:92)).

Validation boundaries that are not established by the current evidence:

- whether form `id` must equal the chapter slug
- whether question IDs must be unique
- whether `max_length` is required, optional, or forbidden for any given
  question type
- whether select-option lists have minimum or maximum lengths
- whether unknown extra keys should be accepted or rejected

## 8. Missing-file and malformed-YAML handling cases evidenced today

The current sources establish the existence of these distinct failure
classes:

### 8.1 Missing file

- missing `chapters.yaml`
- missing `forms/<slug>.yaml` for a referenced chapter

These are filesystem/config-consistency failures, not YAML parser
failures.

### 8.2 Malformed YAML

- invalid indentation
- invalid flow syntax
- other parser/scanner failures

In the local PyYAML environment, malformed samples raised
`ParserError`, a `YAMLError` subclass.

### 8.3 Empty YAML document

- empty file contents
- comments-only file contents

In the local PyYAML environment, these load as `None`, not as a mapping
and not as a parser error.

### 8.4 Well-formed YAML with the wrong shape

Examples directly relevant to the current config surface:

- `chapters.yaml` parses but is not a mapping
- `chapters.yaml` has no `chapters` key
- `chapters` exists but is not a sequence
- a form file parses but has no `questions`
- a question uses an unsupported `type`
- a chapter references a form file that does not exist

These are schema/consistency failures rather than YAML-syntax failures.

## 9. Gaps in the current evidence

The current repo leaves several loader-relevant details unspecified:

- `chapters.yaml` is empty, so the exact chapter-entry schema is still
  undocumented by example
- only one form exists, so optional vs required form fields are not yet
  established by multiple examples
- the sources do not say whether one bad form should fail the entire
  config load or whether partial success is acceptable
- the sources do not define whether reload-time behavior should preserve
  the last good config after a parse/validation failure

Those are open policy questions. They are not answered by the current
design doc or YAML files.
