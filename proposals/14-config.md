# Proposal: `daemon/config.py`

Date: 2026-04-13

## Goal

Define the design for `daemon/config.py` as the YAML config loader for
the Humility Discord daemon.

This proposal is design only. It does not include implementation code.

## Summary

`daemon/config.py` should be a pure file-loading and validation module
with no cached globals and no Discord/runtime side effects.

Its job is:

- load `chapters.yaml` from a supplied base path
- resolve each active chapter to `forms/<slug>.yaml`
- validate both file shapes at load time with clear, path-specific
  errors
- return immutable dataclass objects
- precompute the deterministic per-form interaction plan needed by the
  applications subsystem

The loader should not discover chapters by scanning `forms/`, should not
touch SQLite, and should not contain submission or modal-handling
runtime logic.

## Data Model

All config objects should be regular dataclasses, preferably immutable
(`frozen=True`) so the loaded config is read-only once constructed.

### `DaemonConfig`

Represents one full load of repo-managed daemon config.

Fields:

- `base_path: Path`
- `chapters: tuple[ChapterConfig, ...]`

This wrapper keeps the main API return value explicit and reload-safe.

### `ChapterConfig`

Represents one chapter entry from `chapters.yaml` plus its resolved form.

Fields:

- `slug: str`
- `display_name: str`
- `category_id: int`
- `officer_role_id: int`
- `member_role_id: int`
- `applicant_role_id: int`
- `applications_channel_id: int`
- `tickets_channel_id: int`
- `incidents_channel_id: int`
- `form_path: Path`
- `form: FormConfig`

Design choice:

- `form_path` should be computed, not authored. For chapter `dark-nemesis`,
  the loader resolves `base_path / "forms" / "dark-nemesis.yaml"`.
- `chapters.yaml` remains the source of truth for which chapters are
  active; `forms/` does not imply activation by itself.

### `FormConfig`

Represents one form YAML file and its derived step plan.

Fields:

- `source_path: Path`
- `id: str`
- `title: str`
- `questions: tuple[QuestionConfig, ...]`
- `steps: tuple[FormStepConfig, ...]`

`questions` is the canonical authored order from YAML. `steps` is a
derived execution plan used later by runtime code.

### `QuestionConfig`

Represents one question definition.

Fields:

- `id: str`
- `type: Literal["short", "long", "number", "select", "multi_select"]`
- `label: str`
- `required: bool`
- `max_length: int | None`
- `options: tuple[str, ...]`
- `source_index: int`

Design choice:

- `source_index` preserves authored ordering even when the derived step
  plan groups questions by interaction type.
- `options` should be empty for non-select questions.

### `FormStepConfig`

Represents one deterministic interaction step derived from a form.

Fields:

- `index: int`
- `kind: Literal["modal", "followup_selects"]`
- `questions: tuple[QuestionConfig, ...]`

This object exists so `daemon.applications` can consume a prepared plan
instead of recomputing it at runtime.

## Proposed YAML Shape

`chapters.yaml` should use an explicit closed schema:

```yaml
chapters:
  - slug: dark-nemesis
    display_name: Dark Nemesis
    category_id: 123
    officer_role_id: 456
    member_role_id: 789
    applicant_role_id: 101112
    applications_channel_id: 131415
    tickets_channel_id: 161718
    incidents_channel_id: 192021
```

Notably absent:

- no `form_path` key in YAML
- no implicit discovery by scanning `forms/`

The form file remains `forms/<slug>.yaml`, and that path is derived from
the chapter slug.

## Public API

`daemon/config.py` should expose a small API surface.

### `load_config(base_path: Path) -> DaemonConfig`

Main entry point.

Responsibilities:

- read `base_path / "chapters.yaml"`
- validate the chapter registry
- resolve and load `forms/<slug>.yaml` for each chapter
- validate cross-file consistency
- compute form step plans
- return a fresh `DaemonConfig` object every call

This is the function `daemon.py` should call on startup and on reload.

### `load_form_config(path: Path) -> FormConfig`

Standalone form loader for validation and local tooling.

Responsibilities:

- load one form YAML file directly
- validate the file in isolation
- compute its derived `steps`
- return a fresh `FormConfig`

This supports validating a form before it is referenced from
`chapters.yaml`.

### Error Types

The module should expose a small exception hierarchy so callers can
report configuration failures cleanly.

- `ConfigError`
- `ConfigParseError`
- `ConfigValidationError`

Each raised error should include:

- the file path
- the logical location when known
  - examples: `chapters[0].slug`, `questions[3].options`
- a human-readable message written for operators, not for developers
  only

## Validation Rules

Validation should happen during loading, before any config object is
returned.

### File-level rules

- `chapters.yaml` must exist and be readable.
- Each referenced `forms/<slug>.yaml` must exist and be readable.
- Each file must contain exactly one YAML document.
- Blank or comment-only files are invalid for required config files.
- Malformed YAML is a parse error, not a validation error.

### `chapters.yaml` rules

- The top level must be a mapping.
- The only top-level key is `chapters`.
- `chapters` must be a list.
- An empty list is valid.
- Each chapter entry must be a mapping with the exact keys:
  - `slug`
  - `display_name`
  - `category_id`
  - `officer_role_id`
  - `member_role_id`
  - `applicant_role_id`
  - `applications_channel_id`
  - `tickets_channel_id`
  - `incidents_channel_id`
- Unknown chapter keys are invalid.
- `slug` must match the regex `^[a-z0-9]+(-[a-z0-9]+)*$` (lowercase
  alphanumeric segments separated by hyphens; no path separators, dots,
  or whitespace). This prevents path-traversal when constructing
  `forms/<slug>.yaml`.
- Chapter slugs must be unique.
- `display_name` must be a non-empty string.
- All Discord IDs must be positive integers.

### Form file rules

- The top level must be a mapping.
- Allowed top-level keys are exactly:
  - `id`
  - `title`
  - `questions`
- Unknown top-level form keys are invalid.
- `id` must be a non-empty string.
- `title` must be a non-empty string.
- `questions` must be a non-empty list.
- Each question must be a mapping with a closed schema.
- Question IDs must be unique within the form.
- Supported question types are exactly:
  - `short`
  - `long`
  - `number`
  - `select`
  - `multi_select`
- `label` must be a non-empty string.
- `required` must be a boolean.

For `short`, `long`, and `number`:

- `max_length` is required.
- `max_length` must be a positive integer, at most 4000 (Discord's text
  input component maximum).
- `options` must be absent.

For `select` and `multi_select`:

- `options` is required.
- `options` must be a non-empty list of non-empty strings with at most
  25 entries (Discord's select menu option limit).
- Duplicate option labels are invalid.
- `max_length` must be absent.

### Cross-file rules

- For a chapter slug `X`, the loader must read `forms/X.yaml`.
- The form filename stem must match the chapter slug.
- `form.id` must match the chapter slug.

This removes ambiguity and avoids three separate identifiers drifting
out of sync:

- chapter slug
- form filename
- form `id`

## Multi-step Split Algorithm

The split plan should be computed once, at load time, from the question
types.

### Interaction model

- `short`, `long`, and `number` are modal-backed questions.
- `select` and `multi_select` are follow-up select-menu questions.

### Algorithm

1. Preserve the authored `questions` list exactly as the canonical form
   order.
2. Build `modal_questions` by taking all `short`, `long`, and `number`
   questions in authored order.
3. Build `select_questions` by taking all `select` and `multi_select`
   questions in authored order.
4. Chunk `modal_questions` into groups of at most 5 questions. Each
   chunk becomes one `FormStepConfig(kind="modal", ...)`.
5. Chunk `select_questions` into groups of at most 5 (Discord's
   5-action-row-per-message limit). Each chunk becomes one
   `FormStepConfig(kind="followup_selects", ...)`.
6. The final `steps` tuple is all modal chunks first, then all select
   chunks.

### Why this shape

This matches the current design intent for v1:

- text-compatible fields are gathered through Discord modals
- select-style fields are handled after modal submission
- step planning is deterministic and does not depend on runtime state

It also matches the documented Dark Nemesis example, where authored
question order is:

- `in_game_name` (`short`)
- `timezone` (`select`)
- `daily_events` (`multi_select`)
- `hours_per_day` (`number`)
- `launch_budget_usd` (`number`)
- `monthly_budget_usd` (`number`)
- `pvp_mmorpg_experience` (`long`)

But the derived execution plan is:

- modal step 1:
  - `in_game_name`
  - `hours_per_day`
  - `launch_budget_usd`
  - `monthly_budget_usd`
  - `pvp_mmorpg_experience`
- follow-up selects:
  - `timezone`
  - `daily_events`

That is the right separation for the loader to compute because it is
fully determined by config and platform constraints, while answer
collection and state transitions remain runtime concerns.

## Hot-reload Behavior

The design should be explicitly reload-friendly.

- No module-level caches.
- No singleton config object.
- No file watchers in this module.
- Every call to `load_config()` rereads from disk and rebuilds fresh
  dataclasses.
- Derived fields such as `form_path` and `steps` are recomputed every
  time.

This keeps `/reload` simple and makes unit testing straightforward.

On failure, `load_config()` raises `ConfigError`. The caller
(`daemon.py`) is responsible for catching the error and retaining the
previous good config if one exists. The loader makes no attempt to
partially load or fall back.

## Anti-scope

`daemon/config.py` should not contain:

- Discord API calls
- SQLite reads or writes
- environment variable loading
- slash-command logic
- modal submission handling
- select-menu handling
- numeric answer parsing or coercion
- default answer values
- auto-creation of missing files
- auto-discovery of orphan `forms/*.yaml`
- mutable global registries

In particular, `number` is only a config-time question type. Converting
user input into a numeric value is runtime validation and belongs in
`daemon.applications`, not here.

## Decision

Design `daemon/config.py` as a strict, immutable config loader with two
public load functions, a small error hierarchy, and a derived
`FormStepConfig` plan. `chapters.yaml` should enumerate active chapters;
forms should be resolved as `forms/<slug>.yaml`; and all structural
validation should happen before the daemon starts using the config.
