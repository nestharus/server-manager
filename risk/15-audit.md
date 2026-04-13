# Audit Risk Assessment: daemon/db.py

## Overall: LOW

The proposal defines a thin, synchronous SQLite boundary module with
three responsibilities: resolve the database path, open and configure a
connection, and expose plain per-table query helpers. The design is
intentionally conservative — stdlib `sqlite3`, no ORM, no migration
framework, no workflow logic. All identified findings are low severity.
The gaps the proposal carries (no secondary indexes, no migration path,
no FK enforcement) are explicitly acknowledged as anti-scope for v1 and
do not introduce correctness or security risks at the current data
scale.

## Findings

### Finding 1: No secondary indexes for common lookup columns
- Severity: LOW
- Description: The query helper surface includes lookups by `thread_id`
  and `queue_message_id` on both `submissions` and `tickets`. The schema
  defines only primary key indexes. Without secondary indexes, these
  lookups are full table scans. At the current guild scale (85 members,
  low submission/ticket volume), this has no measurable impact.
- Recommendation: No action required for v1. When ticket or submission
  volume grows, add indexes on `thread_id` and `queue_message_id` for
  both tables. The proposal's additive helper design makes this a
  non-breaking change.

### Finding 2: `executescript()` implicitly commits pending transactions
- Severity: LOW
- Description: The research documents that `executescript()` implicitly
  commits any pending transaction before running its script under legacy
  transaction control. The proposal uses `executescript()` (or
  equivalent multi-statement execution) for the bootstrap schema script.
  If `bootstrap_database()` were ever called while a business
  transaction is in-flight on the same connection, that transaction
  would be silently committed. The proposal separates `connect_database`
  from `bootstrap_database` and bootstrap runs at startup before any
  business logic, so this path does not arise in normal operation.
- Recommendation: No action required. The startup-only bootstrap
  sequencing prevents this. Document in a code comment that bootstrap
  must not be called mid-transaction if future callers might attempt it.

### Finding 3: No schema evolution path in v1
- Severity: LOW
- Description: The proposal uses `CREATE TABLE IF NOT EXISTS` for
  idempotent first-boot creation but explicitly defers migration
  infrastructure. If any column is added, renamed, or retyped between
  deployments, the existing database silently retains its old schema
  because `CREATE TABLE IF NOT EXISTS` no-ops on an existing table. The
  proposal acknowledges this in anti-scope and the research documents
  the gap. For v1 with a single Railway deployment and no production
  data yet, this is acceptable.
- Recommendation: No action required for v1. Before the first schema
  change on a database with real data, introduce a versioned migration
  mechanism (e.g., `PRAGMA user_version` with sequential migration
  scripts). The research already identifies this primitive.

### Finding 4: Thread safety left implicit
- Severity: LOW
- Description: The proposal does not specify `check_same_thread`
  behavior. The default (`True`) raises `ProgrammingError` if the
  connection is used from a thread other than the one that created it.
  The needs synthesis recommends `check_same_thread=False`, but the
  proposal itself is silent. discord.py runs event-loop callbacks on the
  main thread, and the proposal's connection model is one long-lived
  connection, so v1 access is effectively single-threaded. The risk is
  that a future background task or signal handler accesses the
  connection from another thread and hits an opaque crash.
- Recommendation: The implementation should make an explicit choice —
  either keep the default and document that all DB access must stay on
  the creating thread, or set `check_same_thread=False` and note the
  single-writer constraint. Either is safe for v1; the important thing
  is that the choice is visible.

### Finding 5: No foreign key enforcement
- Severity: LOW
- Description: The proposal explicitly states no FK enforcement in v1.
  `submissions.chapter_slug` and `tickets.chapter_slug` reference
  `chapters.slug` by convention only. An orphaned submission or ticket
  row referencing a non-existent chapter is possible if chapter deletion
  or archival does not clean up dependent rows. At v1 scale with manual
  chapter provisioning, this is manageable.
- Recommendation: No action required for v1. When chapter lifecycle
  management matures, consider enabling `PRAGMA foreign_keys = ON` and
  adding explicit FK constraints to the schema.

### Finding 6: Caller-owned transaction boundaries
- Severity: LOW
- Description: The proposal mandates that query helpers never call
  `commit()` internally — transaction boundaries belong to the caller.
  This is a clean separation, but it means every daemon flow that writes
  must explicitly commit. A missed `commit()` in the long-running daemon
  means writes accumulate uncommitted and are lost if the process
  crashes or Railway restarts the container. The connection context
  manager (`with conn:`) auto-commits on block exit, which mitigates
  this if callers use it consistently.
- Recommendation: No action required for the db.py design. The daemon
  modules that consume these helpers should use `with conn:` blocks for
  write paths to ensure commits happen even on early returns or
  exceptions.

### Finding 7: TEXT timestamps with no format contract
- Severity: LOW
- Description: All timestamp columns (`created_at`, `submitted_at`,
  `opened_at`, `archived_at`, `decided_at`, `closed_at`, `added_at`)
  are `TEXT` with no format enforcement at the schema or helper level.
  The proposal does not specify ISO 8601 or any canonical format.
  Different callers could write inconsistent formats, making
  chronological queries or comparisons unreliable.
- Recommendation: Establish a convention (ISO 8601 UTC, e.g.,
  `2026-04-13T14:30:00Z`) in the implementation. This can be a module
  constant or a small formatting helper — it does not require schema
  changes.

### Finding 8: SQL injection surface is correctly addressed
- Severity: LOW
- Description: The proposal mandates parameterized SQL for every query
  helper and explicit scalar parameters rather than opaque dict
  payloads. The research confirms that user-provided fields
  (`subject`, `initial_description`, `decision_reason`, `answers_json`)
  flow through these helpers. The parameterization mandate eliminates
  SQL injection as a vector.
- Recommendation: No action required. The design is correct.

### Finding 9: `answers_json` stored as opaque TEXT
- Severity: LOW
- Description: Application answers are stored as a single serialized
  JSON TEXT column with no schema validation. The proposal explicitly
  places JSON validation in anti-scope. For v1, this is acceptable —
  the form rendering module is the sole producer, and the CLI is the
  sole consumer. Corruption or format drift would surface as a display
  bug, not a data integrity issue.
- Recommendation: No action required for v1. If additional consumers
  parse `answers_json`, consider adding a lightweight validation step at
  write time.

### Finding 10: DatabaseConfig path resolution is safe
- Severity: LOW
- Description: The proposal reads `DATABASE_PATH` from the environment
  with a `discord.db` local default, and delegates production path
  configuration to Railway's env var injection rather than hardcoding a
  production branch in code. The `resolve_database_config` function
  accepts an explicit `env` mapping for testability. This is clean and
  consistent with the existing `daemon/config.py` pattern.
- Recommendation: No action required.
