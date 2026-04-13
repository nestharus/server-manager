# Hookpoint Research: `daemon/db.py`

Date: 2026-04-13

## Scope

This note maps [proposals/15-db.md](/home/nes/discord/proposals/15-db.md:1)
onto the current repository.

It is hookpoint-only research for `daemon/db.py`:

- what already exists and is reusable
- where the first real insertion points are
- what can proceed in parallel
- what current boundaries should not be collapsed

This document does not include implementation code.

## 1. What already exists and is reusable

### Existing package slot and naming

The package/layout insertion point already exists:

- [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:7)
  already reserves `daemon/db.py` as the SQLite submodule.
- [daemon/__init__.py](/home/nes/discord/daemon/__init__.py:7)
  already lists `db` as a planned daemon submodule.
- [tests/test_daemon_init.py](/home/nes/discord/tests/test_daemon_init.py:7)
  already treats `"db"` as one of the expected daemon submodule names.

This is reusable directly. `daemon/db.py` does not need a packaging
decision, a new top-level directory, or any renaming work.

### Existing style baseline from `daemon/config.py`

[daemon/config.py](/home/nes/discord/daemon/config.py:1) is the
strongest local style reference for a new daemon support module:

- module docstring first, then `from __future__ import annotations`
  ([daemon/config.py](/home/nes/discord/daemon/config.py:1),
  [daemon/config.py](/home/nes/discord/daemon/config.py:3))
- explicit constants near the top
  ([daemon/config.py](/home/nes/discord/daemon/config.py:15))
- frozen dataclasses for typed return values
  ([daemon/config.py](/home/nes/discord/daemon/config.py:48))
- small dedicated exception hierarchy with operator-facing messages
  ([daemon/config.py](/home/nes/discord/daemon/config.py:96))
- pure function entry points taking explicit inputs instead of relying on
  hidden module globals
  ([daemon/config.py](/home/nes/discord/daemon/config.py:117),
  [daemon/config.py](/home/nes/discord/daemon/config.py:247))

That makes the proposal's `DatabaseConfig` a natural fit. The reusable
part is the shape: `Path`-based inputs, frozen typed config object,
small exceptions, and explicit function boundaries.

### Existing CLI operator UX patterns

[discord_cli.py](/home/nes/discord/discord_cli.py:25) already defines a
small operator-facing error type, and
[discord_cli.py](/home/nes/discord/discord_cli.py:75) plus
[discord_cli.py](/home/nes/discord/discord_cli.py:84) already define the
JSON success/error envelope pattern for CLI commands.

That is reusable for future CLI commands that read from SQLite:

- fail with a narrow exception type
- return structured JSON payloads
- keep argument validation explicit and near the command entry point

The reusable part is the CLI surface behavior, not the gateway runtime.

## 2. Existing boundaries `db.py` must fit

### `chapters.yaml` remains the active chapter registry

The repository already defines a config/database split:

- [chapters.yaml](/home/nes/discord/chapters.yaml:3) says the YAML file
  is the source of truth for which chapters exist.
- [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:69)
  says chapter provisioning both registers the chapter in
  `chapters.yaml` and persists metadata to SQLite.
- [proposals/15-db.md](/home/nes/discord/proposals/15-db.md:35) says
  `daemon/db.py` should treat the four documented tables as the
  canonical persisted model.

So `db.py` is not a replacement for `chapters.yaml`. The current repo
already implies two separate roles:

- repo-managed YAML declares active chapters for config loading
- SQLite stores daemon runtime metadata and workflow state

That means the first `chapters` table helpers should be inserted as part
of chapter provisioning and archive flows, not as a new source of truth
for config loading.

### The schema already overlaps with `ChapterConfig`

There is a clear field-level reuse seam between config and the proposed
`chapters` table:

- [daemon/config.py](/home/nes/discord/daemon/config.py:55) defines
  `ChapterConfig`
- [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:106)
  defines the `chapters` table

These fields already line up closely:

- `slug`
- `display_name`
- `category_id`
- `officer_role_id`
- `member_role_id`
- `applicant_role_id`
- `applications_channel_id`
- `tickets_channel_id`
- `incidents_channel_id`

The main differences are also already explicit:

- config computes `form_path` as a `Path`
  ([daemon/config.py](/home/nes/discord/daemon/config.py:214))
- SQLite stores `form_path` as text plus `created_at` and `archived_at`
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:116),
  [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:117))

This is a strong reuse point because it argues against inventing a
second chapter object model in `db.py`.

### The daemon/CLI split is already documented

The repo already defines the boundary that `db.py` sits behind:

- [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:191)
  says `discord_cli.py` remains the one-shot inspection/admin interface.
- The same section says the daemon and CLI share the SQLite database
  file
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:193)).
- [proposals/15-db.md](/home/nes/discord/proposals/15-db.md:42) turns
  that into the intended runtime model: one long-lived daemon
  connection, one short-lived connection per CLI invocation.

So the architectural hookpoint is already settled. `db.py` is the
shared boundary between future daemon modules and future DB-aware CLI
commands.

## 3. First concrete insertion points

### `daemon/db.py` itself is a new file, but not a new concept

There is no live `daemon/db.py` file yet, and a repo scan found no
existing SQLite access code in the runtime tree outside research/docs.

That means:

- bootstrap SQL will be the first runtime schema representation
- `connect_database(...)` will be the first live database open path
- helper functions will be the first live query surface

Nothing needs to be deleted to make room for it.

### Future daemon consumers are already named

The design doc already names the future callers:

- `chapters.py` for chapter provisioning persistence
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:17),
  [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:61))
- `applications.py` for submission storage and queue/thread lifecycle
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:15),
  [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:43))
- `tickets.py` for ticket storage and lifecycle transitions
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:16),
  [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:41))

Those are not live code hookpoints yet, but they are already the named
consumer boundaries. The reusable insight is that helper families can be
organized by those future callers without putting workflow logic in
`db.py`.

### The current CLI dispatch is the real CLI-side hookpoint

The live CLI is currently hard-wired around Discord gateway work:

- [discord_cli.py](/home/nes/discord/discord_cli.py:629) maps command
  names to async guild handlers
- [discord_cli.py](/home/nes/discord/discord_cli.py:642) runs every
  command through `run_gateway_command(...)`
- [discord_cli.py](/home/nes/discord/discord_cli.py:655) builds only
  gateway-backed subcommands today

This matters because the daemon design explicitly expects DB-backed CLI
work later, including "list submissions" and chapter provisioning
administration
([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:196)).

So the actual CLI insertion point is not inside an existing command
handler. It is at the parser/dispatch layer:

- add new subcommands in `build_parser(...)`
- decide at dispatch time whether a command is gateway-backed or
  database-backed
- keep DB-only commands from opening a Discord client unnecessarily

That is the single most important existing hookpoint in live code.

### Database env resolution should not be folded into `get_config()`

The current CLI env path is narrowly Discord-specific:

- [discord_cli.py](/home/nes/discord/discord_cli.py:17) defines `.env`
  loading
- [discord_cli.py](/home/nes/discord/discord_cli.py:50) reads only
  `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID`

The proposal deliberately wants a separate, testable database config
entry point that reads `DATABASE_PATH` from an injected mapping
([proposals/15-db.md](/home/nes/discord/proposals/15-db.md:169)).

So the clean hookpoint is a new `resolve_database_config(...)`
function in `daemon/db.py`, not expansion of the existing CLI
`get_config()` helper.

## 4. Table-by-table mapping to current code and docs

### `chapters`

This is the most grounded table because the repo already has both a
config schema and a chapter-provisioning story:

- chapter registry shape exists in
  [daemon/config.py](/home/nes/discord/daemon/config.py:19)
- chapter provisioning sequence is documented in
  [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:61)
- `chapters.yaml` already says future `chapters create <slug>` will
  populate it
  ([chapters.yaml](/home/nes/discord/chapters.yaml:6))

So the first real hookpoints for `chapters` helpers are:

- after chapter provisioning succeeds
- after the YAML registry update is known
- before any future archive flow marks a chapter archived

### `submissions`

There is no live submission code yet, but the design already defines the
exact workflow moments that need persistence:

- final application submit
- queue message creation
- private thread creation
- claim/interview/approve/deny transitions
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:43))

So the current mapping is design-to-design only:

- `applications.py` is the future caller
- `db.py` owns storage only
- no current CLI or config code is a direct hookpoint beyond the shared
  chapter slug/form identity data

### `tickets`

This is similar to `submissions`: no live ticket lifecycle code exists,
but the lifecycle is already spelled out in the daemon design
([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:41)).

The future hookpoints are the workflow edges:

- ticket creation
- queue/thread reference attachment
- claim
- close

Again, the current repo has no live runtime implementation to refactor.
The main reusable boundary is the daemon design's lifecycle definition.

### `chapter_blacklist`

The blacklist has the least current runtime coupling:

- it exists only in the schema and workflow docs today
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:77),
  [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:155))
- the first documented consumer is `/apply`
- the first documented mutator is `/chapter-blacklist add @user reason`

So there is no current live hookpoint besides the future daemon command
surface and possible later CLI inspection/admin commands.

## 5. Parallel work boundaries

### Safe to do in parallel

`daemon/db.py` can start before most daemon runtime work exists because
its first responsibilities are local and synchronous:

- `DatabaseConfig`
- connection opening
- WAL/bootstrap
- foundational helper functions

That work does not require:

- a live `daemon.py` entry point
- Discord interaction handlers
- populated `chapters.yaml`
- current CLI command rewrites

### Shared contracts that should be fixed early

Two cross-module contracts matter early:

- the daemon/CLI database path contract:
  `DATABASE_PATH` or default `discord.db`
  ([proposals/15-db.md](/home/nes/discord/proposals/15-db.md:62))
- the chapter metadata contract between config loading and persisted
  `chapters` rows

Once those are fixed, most of `submissions`, `tickets`, and
`chapter_blacklist` helper expansion can proceed in parallel with the
future daemon modules that will call them.

## 6. What not to carry forward from current code

### Do not reuse the CLI gateway path for DB-only work

`run_gateway_command(...)` in
[discord_cli.py](/home/nes/discord/discord_cli.py:436) is the wrong
precedent for DB-only admin or inspection commands. Opening a Discord
client just to query SQLite would couple unrelated concerns and violate
the proposal's thin-boundary goal.

### Do not move config loading into `db.py`

The proposal is explicit that YAML loading remains in `daemon/config.py`
([proposals/15-db.md](/home/nes/discord/proposals/15-db.md:276)). The
current repo already has that module in place
([daemon/config.py](/home/nes/discord/daemon/config.py:117)).

So `db.py` should consume the config boundary where needed, not absorb
it.

### Do not invent a second chapter model

Because `ChapterConfig` and the `chapters` table already overlap so
closely, a new custom model layer inside `db.py` would add drift with no
current need. The proposal's "rows stay rows" rule matches the current
repo better than introducing another abstraction layer.

## Conclusion

`daemon/db.py` is mostly greenfield code with well-defined hookpoints:

- the package slot already exists
- `daemon/config.py` already provides the local style/template
- `docs/DAEMON_DESIGN.md` already defines the schema and future callers
- `discord_cli.py` parser/dispatch is the live CLI seam for future
  DB-backed commands

The most important current boundary is that SQLite should complement,
not replace, the repo-managed YAML config. The most important live
insertion point is the CLI dispatch layer, because the current CLI has
no non-gateway command path yet even though the daemon design already
expects shared DB-backed admin workflows.
