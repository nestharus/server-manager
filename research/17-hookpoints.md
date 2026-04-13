# Hookpoint Research: `daemon.py`

Date: 2026-04-13

## Scope

This note maps
[proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:1)
onto the current repository.

It is hookpoint-only research for `daemon.py`:

- what already exists and is reusable
- where the first real insertion points are
- what can proceed in parallel
- what current boundaries should not be collapsed

This document does not include implementation code.

## 1. What already exists and is reusable

### `daemon/config.py` already owns repo-managed config loading

The proposal says `daemon.py` should resolve the repo base path and then
delegate YAML loading to `daemon.config.load_config(...)`
([proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:68),
[proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:175)).

That hookpoint already exists directly:

- [daemon/config.py](/home/nes/discord/daemon/config.py:48) defines the
  immutable daemon config dataclasses.
- [daemon/config.py](/home/nes/discord/daemon/config.py:117) already
  accepts a `base_path` and loads `chapters.yaml`.
- [daemon/config.py](/home/nes/discord/daemon/config.py:214) already
  resolves `forms/<slug>.yaml` relative to that base path.

This is the cleanest existing reuse seam. `daemon.py` does not need to
know chapter/file layout details beyond computing the repo root once.

### `daemon/db.py` already owns SQLite open/bootstrap/close

The proposal says the entry point should resolve a database path, open
SQLite before connecting to Discord, and always close it on shutdown
([proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:176),
[proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:179),
[proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:254)).

Those runtime primitives already exist:

- [daemon/db.py](/home/nes/discord/daemon/db.py:87) opens a SQLite
  connection and creates parent directories.
- [daemon/db.py](/home/nes/discord/daemon/db.py:95) bootstraps the
  schema and enables WAL mode.
- [daemon/db.py](/home/nes/discord/daemon/db.py:101) combines those
  steps in `open_database(...)`.
- [daemon/db.py](/home/nes/discord/daemon/db.py:107) exposes
  `close_database(...)`.

This means the entry-point work is orchestration, not schema or
connection implementation.

### `discord_cli.py` already defines the local `.env` convention

The proposal explicitly says `daemon.py` should follow the same local
environment convention as `discord_cli.py`
([proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:49)).

That convention already exists in live code:

- [discord_cli.py](/home/nes/discord/discord_cli.py:17) defines the
  repo-local `.env` path as `Path(__file__).with_name(".env")`.
- [discord_cli.py](/home/nes/discord/discord_cli.py:22) loads that file
  with `load_dotenv(...)`.
- [discord_cli.py](/home/nes/discord/discord_cli.py:50) validates
  `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID`.

This is reusable as behavior and operator UX. It is not a strong direct
import hookpoint, because `get_config()` is CLI-shaped and only returns
token plus guild ID.

### The repo already favors explicit startup-owned state over globals

The proposal wants a small `commands.Bot` subclass that carries
`guild_id`, loaded config, and the opened DB connection
([proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:104),
[proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:118)).

That matches the current module style:

- [daemon/config.py](/home/nes/discord/daemon/config.py:48) and
  [daemon/db.py](/home/nes/discord/daemon/db.py:74) use frozen
  dataclasses for explicit typed state.
- [daemon/config.py](/home/nes/discord/daemon/config.py:117),
  [daemon/db.py](/home/nes/discord/daemon/db.py:79), and
  [daemon/claim.py](/home/nes/discord/daemon/claim.py:40) all take
  explicit inputs rather than relying on module-level runtime
  singletons.

So a startup-owned bot object with injected dependencies is aligned with
the codebase that already exists.

### `daemon/claim.py` already makes the member-intent requirement real

The scaffold proposal says the daemon should enable `members` even
before application and ticket flows are implemented
([proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:137)).

That is not abstract anymore. Current code already has member-sensitive
logic in:

- [daemon/claim.py](/home/nes/discord/daemon/claim.py:74), which
  resolves existing thread members and narrows membership on claim.
- [daemon/claim.py](/home/nes/discord/daemon/claim.py:161), which uses
  `guild.get_member(...)` and `guild.fetch_member(...)` during that
  reconciliation.

`daemon.py` does not need to call those helpers in this scaffold, but it
does need to start with an intent set that is compatible with them.

## 2. Existing boundaries `daemon.py` must fit

### The CLI is a reference point, not a runtime dependency

`discord_cli.py` is the closest existing startup analogue, but it is
still a one-shot inspection program:

- [discord_cli.py](/home/nes/discord/discord_cli.py:440) constructs a
  raw `discord.Client`.
- [discord_cli.py](/home/nes/discord/discord_cli.py:445) does all work
  inside `on_ready()`.
- [discord_cli.py](/home/nes/discord/discord_cli.py:461) closes the
  client immediately after one handler run.
- [discord_cli.py](/home/nes/discord/discord_cli.py:642) dispatches a
  single CLI command per process.

So `discord_cli.py` is a reuse source for env parsing and explicit loop
ownership, not something `daemon.py` should import into its runtime
path.

### `discord_cli.build_intents()` is intentionally not reusable as-is

The proposal requires `guilds = True` and `members = True`, but says the
scaffold must not enable `message_content`
([proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:123),
[proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:149)).

The current CLI helper differs on exactly that point:

- [discord_cli.py](/home/nes/discord/discord_cli.py:67) builds intents
  from `discord.Intents.default()`.
- [discord_cli.py](/home/nes/discord/discord_cli.py:71) enables
  `message_content = True`.

That makes `build_intents()` a pattern reference, not a safe shared
helper for the daemon scaffold.

### `resolve_database_config()` is also not a safe direct fit

This is the main existing helper that the proposal explicitly narrows
away from.

- [daemon/db.py](/home/nes/discord/daemon/db.py:11) defines the default
  path as `Path("discord.db")`.
- [daemon/db.py](/home/nes/discord/daemon/db.py:79) returns that
  cwd-relative path when `DATABASE_PATH` is unset.

The proposal says `daemon.py` must not use that unset-path behavior and
must instead anchor the default DB path to
`Path(__file__).resolve().parent`
([proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:331),
[proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:339)).

So the reusable DB hookpoint is `open_database(...)` and
`close_database(...)`, not `resolve_database_config(...)`.

### `daemon.py` should not absorb workflow logic from `claim.py`

The proposal's anti-scope excludes application flow, ticket flow, and
claim orchestration beyond future imports
([proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:392),
[proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:398)).

That fits the current `claim.py` boundary exactly:

- [daemon/claim.py](/home/nes/discord/daemon/claim.py:1) says the
  module only reconciles explicit private-thread membership.
- [daemon/claim.py](/home/nes/discord/daemon/claim.py:4) says it does
  not manage workflow state or DB updates.

This boundary should stay intact. `daemon.py` should create runtime
state that later workflow modules can use; it should not start
coordinating claims itself.

## 3. First concrete insertion points

### The new top-level file is the main hookpoint

There is no live `daemon.py` entry point in the current tree, so the
primary insertion point is a new top-level file at the repo root.

That file should stay thin and use existing modules in the proposal's
startup order
([proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:169)).

### Env parsing should start from the CLI's local pattern

The first concrete startup steps should mirror the existing CLI
behavior:

1. define the repo-local `.env` path the same way as
   [discord_cli.py](/home/nes/discord/discord_cli.py:17)
2. load it the same way as
   [discord_cli.py](/home/nes/discord/discord_cli.py:22)
3. validate token and guild ID with the same guard-clause shape used in
   [discord_cli.py](/home/nes/discord/discord_cli.py:50)

This is the most direct mapping for
[proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:54)
through
[proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:64).

### Config loading should happen immediately after base-path resolution

Once `daemon.py` has computed `base_path =
Path(__file__).resolve().parent`, the next real hookpoint is:

- call [daemon/config.py](/home/nes/discord/daemon/config.py:117)
  `load_config(base_path)`

That is the concrete implementation seam for
[proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:174)
and
[proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:175).

### Database resolution splits into two parts

The first real DB startup hookpoint is deliberately split:

1. resolve `db_path` in `daemon.py` itself from `os.environ`
2. pass the resolved path to
   [daemon/db.py](/home/nes/discord/daemon/db.py:101)
   `open_database(...)`
3. ensure
   [daemon/db.py](/home/nes/discord/daemon/db.py:107)
   `close_database(...)` runs in `finally`

That is the correct mapping for
[proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:176)
through
[proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:179),
plus the path-resolution exception at
[proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:339).

The proposal's recommended `PRAGMA busy_timeout = 5000` also belongs in
this same startup slot, immediately after `open_database(...)` and
before the gateway connection starts
([proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:374)).

### Bot construction is a new runtime seam, not a refactor of CLI code

There is no existing bot subclass or slash-command registration surface
in the files reviewed here. So the next insertion point is entirely new:

- construct a small `commands.Bot` subclass carrying `guild_id`,
  config, DB connection, and optionally `base_path`
- keep those as startup-owned runtime state rather than globals

That structure is justified by the proposal
([proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:102))
and is consistent with the explicit-state patterns already present in
`daemon/config.py`, `daemon/db.py`, and `daemon/claim.py`.

### `setup_hook()` is the first real slash-command hookpoint

The proposal says the minimal command should be registered and
guild-synced from `setup_hook()`
([proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:114),
[proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:222)).

There is no current slash-command scaffolding in `discord_cli.py`,
`daemon/config.py`, `daemon/db.py`, or `daemon/claim.py`, so this is a
net-new insertion point inside the new bot subclass rather than a patch
to an existing module.

### Process lifetime should reuse the CLI's explicit loop ownership, not its one-shot flow

The local repo already uses explicit `asyncio.run(...)` ownership in the
CLI:

- [discord_cli.py](/home/nes/discord/discord_cli.py:686) defines a
  synchronous `main(...)`
- [discord_cli.py](/home/nes/discord/discord_cli.py:692) calls
  `asyncio.run(...)`

That is the closest existing hookpoint for the proposal's requirement to
manage lifecycle explicitly rather than leaning on `bot.run(...)`
([proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:232),
[proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:252)).

But the daemon runtime itself should diverge from the CLI's one-shot
shape:

- not `discord.Client`
- not work-in-`on_ready()`
- not immediate close after first action

Instead, the new `daemon.py` main path is where `async with bot:`,
`await bot.start(token)`, signal handling, and DB cleanup belong.

## 4. Parallel work boundaries

### `daemon.py` can be built now without waiting on new support modules

The proposal's prerequisites named in the design already exist in the
working tree, and the concrete runtime dependencies for the scaffold are
already present in code:

- config loading in [daemon/config.py](/home/nes/discord/daemon/config.py:117)
- DB open/close in
  [daemon/db.py](/home/nes/discord/daemon/db.py:101) and
  [daemon/db.py](/home/nes/discord/daemon/db.py:107)
- future claim helpers in
  [daemon/claim.py](/home/nes/discord/daemon/claim.py:40) and
  [daemon/claim.py](/home/nes/discord/daemon/claim.py:74)

So the entry-point scaffold is not blocked on new lower-level modules.

### `/ping` scaffolding is independent of application and ticket flows

Because the proposal keeps the scaffold intentionally narrow
([proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:196)),
the first slash-command path can proceed without:

- queue-message logic
- claim orchestration
- workflow DB writes
- chapter provisioning logic

That lets the daemon boot boundary land before later interaction
partitions exist.

### Future workflow modules can target bot-owned state once this lands

The proposal's bot subclass state is the forward hookpoint for later
partitions:

- config loaded once at startup
- DB connection opened once at startup
- guild ID stored once at startup

That gives later modules a stable runtime boundary without forcing
`daemon.py` itself to absorb workflow code.

## 5. Current gaps and tensions to keep visible

### The strongest existing code is support code, not entry-point code

The repo already has the reusable support modules the proposal depends
on, but none of the actual daemon entry-point wiring exists yet. So the
hookpoints identified here are mostly module boundaries, not existing
call sites waiting for a one-line patch.

### The CLI is close enough to copy patterns from, but not close enough to share directly

`discord_cli.py` is intentionally wrong for the daemon scaffold in three
important ways:

- it uses `discord.Client`, not `commands.Bot`
- it enables `message_content`
- it exits after a single `on_ready()` action

That makes it a behavioral reference, not shared startup infrastructure.

### The DB path helper mismatch is the one concrete trap already in tree

The proposal's warning about cwd-relative default DB paths is grounded
in a real current helper:
[daemon/db.py](/home/nes/discord/daemon/db.py:79).

If `daemon.py` reuses that helper blindly, it violates the proposal's
repo-root anchoring rule
([proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:326)).
This is the clearest existing hookpoint where "reuse existing code" is
the wrong move unless the call site is narrowed carefully.

### `daemon/claim.py` is a prerequisite, but not a direct startup consumer yet

The proposal lists `daemon/claim.py` as a prerequisite
([proposals/17-daemon-entry.md](/home/nes/discord/proposals/17-daemon-entry.md:318)),
but the scaffold entry point does not need to call it. Its practical
impact on `daemon.py` today is indirect:

- justify keeping `members` intent enabled
- justify storing shared runtime state on the bot for later modules
- avoid pulling claim or workflow logic into the entry-point scaffold
