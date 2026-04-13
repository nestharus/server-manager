# Audit Risk Assessment: Daemon Entry Point

## Overall: LOW

The proposal is thorough, architecturally sound, and makes explicit
decisions on every significant concern: concurrency (WAL + busy_timeout
+ single-writer constraint), lifecycle (try/finally + signal handling),
health (process liveness until background work exists), scope boundaries
(anti-scope section), and operational validation (on_ready guild check).
No security vulnerabilities, data integrity issues, or resource leaks
are present in the proposed design. The findings below are minor design
gaps or coordination risks, all of which are mitigated by explicit
decisions elsewhere in the proposal.

## Findings

### Finding 1: `on_ready` re-entrancy not addressed

- Severity: LOW
- Description: The proposal (section "Guild Readiness Validation")
  specifies that `on_ready` should validate guild reachability and
  members intent. However, discord.py fires `on_ready` on initial
  connect AND on every gateway reconnect. The proposal does not mention
  guarding against re-execution. Without a guard, guild validation and
  `guild.chunk()` would run again on every reconnect, producing
  duplicate log output and redundant chunk requests. The existing
  `discord_cli.py` uses a `has_run` guard for its `on_ready` handler
  (line 446-449), establishing a precedent in the codebase, but the
  proposal does not reference this pattern.
- Recommendation: Specify that `on_ready` should use a `has_run` guard
  (or equivalent) to ensure guild validation executes only once per
  process lifetime, consistent with the CLI pattern.

### Finding 2: Cross-partition dependency for `busy_timeout` in `open_database()`

- Severity: LOW
- Description: The proposal (section "Shared SQLite Concurrency Policy")
  requires `open_database()` to set `PRAGMA busy_timeout = 5000`
  immediately after enabling WAL. This is a change to `daemon/db.py`,
  which was delivered in partition 15. The current `open_database()`
  (db.py:101-104) sets WAL mode but does not set `busy_timeout`. The
  proposal correctly identifies this as a DB-layer concern ("every
  caller that opens through `open_database()` inherits the timeout"),
  but does not state whether the daemon.py partition is responsible for
  modifying db.py or whether this is a prerequisite that must be
  completed first. If the implementer adds `busy_timeout` only in
  daemon.py (as the existing scaffold code does), the CLI and any
  future callers of `open_database()` would not inherit the timeout,
  defeating the stated design goal.
- Recommendation: Clarify that the `busy_timeout` pragma must be added
  to `bootstrap_database()` in `daemon/db.py` as part of this
  partition's implementation scope, since the proposal explicitly
  requires it and no other partition owns the change.

### Finding 3: Single-writer constraint is policy, not enforced

- Severity: LOW
- Description: The proposal (section "Shared SQLite Concurrency Policy")
  establishes a single-writer constraint: only one process may hold an
  open write transaction at a time. This is stated as a design decision
  and deferred to the first partition requiring concurrent writes.
  However, no mechanism prevents an operator from running a CLI write
  command while the daemon is running. The `busy_timeout` provides a
  5-second retry window, after which `SQLITE_BUSY` would surface.
  The proposal's scaffold write posture (schema bootstrap only, before
  gateway connect) makes this unreachable in practice for this
  partition.
- Recommendation: Accept for this partition. The scaffold's write
  posture makes concurrent-write scenarios unreachable. The proposal
  correctly identifies this as a future-partition concern and sets the
  right precondition: "The first partition that requires true
  concurrent writes ... must specify transaction boundaries, commit
  ownership, and retry semantics before implementation."

### Finding 4: Signal handling uses "recommended" language

- Severity: LOW
- Description: The proposal (section "Signal handling") describes
  SIGTERM/SIGINT handling as "Recommended behavior" rather than a hard
  requirement. On Railway, the container runtime sends SIGTERM before
  SIGKILL. Without a SIGTERM handler, the default OS disposition
  terminates the process immediately, bypassing the `finally` block
  that closes the database. While SQLite WAL mode is crash-safe and
  data corruption is not a risk, the distinction between "recommended"
  and "required" could lead an implementer to omit signal handling.
  The proposal's own "Failure behavior" section (under "Startup Order")
  uses stronger language ("should abort", "should still trigger"),
  creating an inconsistency in requirement strength.
- Recommendation: Treat signal handling as a requirement, not a
  recommendation, matching the strength of the lifecycle and failure
  behavior language elsewhere in the proposal. The implementation cost
  is minimal (one `loop.add_signal_handler` call) and the operational
  benefit on Railway is concrete.

### Finding 5: Module-level `load_dotenv` side effect

- Severity: LOW
- Description: The proposal (section "Environment file") specifies
  loading `.env` from `Path(__file__).with_name(".env")`, following the
  same pattern as `discord_cli.py`. This runs at import time, meaning
  importing the daemon module in a test or REPL unconditionally loads
  `.env` into the process environment. The `override=False` default in
  python-dotenv prevents overwriting existing env vars, which mitigates
  production risk on Railway (where env vars are set in the container
  environment). However, tests that import the module will silently
  pick up `.env` values unless they explicitly isolate environment
  state.
- Recommendation: Accept as a known pattern inherited from the CLI.
  If test isolation becomes a problem in a future partition, moving
  `load_dotenv` inside `main()` or `get_runtime_config()` is a
  small, isolated change. Not blocking for this partition.
