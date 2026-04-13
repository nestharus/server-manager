# Scope Risk: Daemon Entry Point

**Overall risk level: LOW**

The proposal is disciplined and well-bounded. `daemon.py` is defined as
a thin orchestration shell that delegates config loading to
`daemon.config`, database management to `daemon.db`, and defers all
feature work (applications, tickets, provisioning) to future partitions.
The anti-scope section is comprehensive. The few scope-adjacent
decisions — concurrency policy, `busy_timeout` placement, guild
readiness validation — are proportionate to the entry-point role and
would be harder to retrofit correctly if deferred.

## Findings

### 1. Concurrency policy binds future partitions without validation

**Severity: LOW**

The "Shared SQLite Concurrency Policy" section
(`proposals/proposals/17-daemon-entry.md`:418-460) makes four binding
architectural decisions: single-writer constraint, `asyncio.to_thread()`
wrapping for all handler DB calls, process-liveness health model, and
`busy_timeout` in the DB layer. These decisions are stated as
"architectural decisions made in this proposal that bind future
partitions" (line 501).

This is scope extension — a scaffold partition is prescribing patterns
for partitions that will contain the actual handlers. The
`asyncio.to_thread()` mandate in particular is decided before any
concrete interaction handler exists to validate the pattern against.
However, the risk is low because (a) the decisions are conventional for
single-file SQLite behind an async event loop, (b) the proposal
explicitly acknowledges the scaffold does not implement them yet
(line 449), and (c) deferring concurrency policy to ad-hoc handler
partitions would be riskier than deciding it at the entry-point
boundary.

### 2. Proposal modifies partition 15's `open_database()`

**Severity: INFO**

The proposal states: "`open_database()` to also set
`PRAGMA busy_timeout = 5000` immediately after enabling WAL"
(line 424). This is a change to `daemon/db.py:95-104`
(`bootstrap_database` / `open_database`), which was partition 15's
scope. The modification is a single PRAGMA addition in a function that
already sets WAL mode, so the blast radius is minimal. The justification
— every caller that opens through `open_database()` inherits the
timeout — is sound and avoids callers needing to remember to set it
themselves. No scope concern.

### 3. Guild readiness validation is proportionate

**Severity: INFO**

The `on_ready` guild validation
(`proposals/proposals/17-daemon-entry.md`:316-341) adds startup logic
beyond the minimum `/ping` scaffold: guild-cache lookup, chunking check,
and a startup-complete log. The proposal explicitly acknowledges this as
a cost (line 369) and justifies it by listing three operational traps it
catches: wrong guild ID, unapproved members intent, and gateway not
delivering member data. These are real failure modes that would produce
silent brokenness in every future handler partition. The added logic is
a handful of lines — proportionate to the risk it mitigates.

### 4. `daemon/claim.py` listed as prerequisite but unused

**Severity: INFO**

The prerequisites section (line 378) lists `daemon/claim.py` (partition
16) as a dependency. However, the proposal never imports, calls, or
references any API from `claim.py`. The entry point only imports from
`daemon.config` and `daemon.db`. The listing appears to reflect a
"package completeness" assumption rather than an actual code dependency.
This is a minor documentation inaccuracy with no implementation impact.

### 5. Signal handling adds modest but justified scope

**Severity: INFO**

The proposal recommends installing `SIGINT` and `SIGTERM` handlers
(lines 263-274). This is beyond the minimum scaffold but is standard
practice for a long-running daemon that holds a SQLite connection and a
gateway websocket. The proposal frames this as "recommended behavior"
and says "this is enough for the scaffold" (line 274), correctly
scoping it as a simple signal-to-shutdown bridge rather than a
supervisor or task registry.

### 6. Anti-scope section is comprehensive

**Severity: INFO**

The anti-scope section (lines 465-481) explicitly excludes: application
submission flow, ticket flow, chapter provisioning, button views, modal
classes, claim orchestration, SQLite workflow queries, config
hot-reload, background tasks, schedulers, polling loops, admin CLI
commands, message-command handlers, and message-content event handlers.
It also clarifies that the database is opened but not used for
workflow reads or writes. No gaps identified.

### 7. Referenced module APIs match existing code

**Severity: INFO**

All referenced APIs exist with matching signatures:

- `daemon.config.load_config(base_path: Path) -> DaemonConfig` —
  `daemon/config.py:117`
- `daemon.db.open_database(path: str | Path) -> sqlite3.Connection` —
  `daemon/db.py:101`
- `daemon.db.close_database(conn: sqlite3.Connection) -> None` —
  `daemon/db.py:107`
- `daemon.db.resolve_database_config()` — `daemon/db.py:79`, correctly
  referenced as the function NOT to call for the unset-DATABASE_PATH
  case (line 403)

The proposal's instruction to bypass `resolve_database_config()` for the
default path and instead anchor to `base_path / "discord.db"` is
correct — `resolve_database_config()` returns a cwd-relative
`Path("discord.db")` which would silently break under Railway or
non-root-cwd launches.

### 8. Needs synthesis conflict on `message_content` is resolved

**Severity: INFO**

The earlier synthesis (`research/research/17-daemon-entry-needs.md`:3)
recommends enabling `message_content`. The proposal explicitly overrides
this (lines 149-163) with reasoning: the scaffold entry point only needs
slash commands, not message-body access, and enabling it later is a
small isolated change. The proposal's reasoning is sound and the
override is deliberate, not an oversight.
