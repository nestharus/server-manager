# Audit Risk Assessment: `daemon/__main__.py`

## Overall: LOW

The proposal is a controlled, mechanical port of the deleted root
`daemon.py` into the package entry point `daemon/__main__.py`, with
exactly three intentional changes: path resolution adjustment
(`parent.parent`), bot class rename (`HumilityBot`), and applications
wiring (`setup_applications`). The research backing is thorough —
particularly the dual-module-identity analysis and the constraint
derivation from `applications.py`'s TYPE_CHECKING import. No security
vulnerabilities, data integrity issues, or resource leaks are
introduced. All findings below are minor design gaps or inherited
concerns, none of which block implementation.

## Findings

### Finding 1: Double-import hazard is documented but not guarded

- Severity: LOW
- Description: The research (section 2) correctly identifies that
  `python -m daemon` executes `daemon/__main__.py` under the module
  name `__main__`, while a later `import daemon.__main__` would
  re-execute the file under the name `daemon.__main__`, creating two
  distinct module objects. This means `load_dotenv()` would run a second
  time (harmless due to `override=False`) and, more importantly, class
  identity checks (`isinstance`, `is`) between the two module loads
  would fail. The proposal relies on the current `TYPE_CHECKING` guard
  in `daemon/applications.py:17-18` to prevent this at runtime, which
  is correct. However, the proposal does not specify any documentation
  or code-level guard (e.g., a comment, a `sys.modules` check, or a
  note in `__init__.py`) to warn future developers against adding an
  unconditional runtime import of `daemon.__main__`.
- Recommendation: Add a module-level comment in `daemon/__main__.py`
  noting the dual-identity hazard and that runtime imports of this
  module must use `TYPE_CHECKING` guards. This costs nothing and
  prevents a subtle future regression.

### Finding 2: Signal handling remains absent

- Severity: LOW
- Description: The prior audit (17-audit.md, Finding 4) identified that
  signal handling was described as "recommended" in that proposal. This
  proposal does not mention signal handling at all, inheriting the
  deleted `daemon.py` behavior of no explicit SIGTERM handler. The
  proposal uses `asyncio.run(main())` as the process entry point.
  `asyncio.run()` installs a SIGINT handler (raising
  `KeyboardInterrupt`), but the default SIGTERM disposition on Linux
  terminates the process without running `finally` blocks. On Railway,
  container shutdown sends SIGTERM before SIGKILL. Without a handler,
  `close_database(conn)` in the `finally` block would be skipped on
  graceful container shutdown. SQLite WAL mode is crash-safe, so no
  data corruption would occur, but the connection would not be cleanly
  closed.
- Recommendation: Accept for this partition since it is a direct port
  and the prior audit already flagged this. When signal handling is
  added (per the prior audit's recommendation), it belongs in this
  module's `main()` function.

### Finding 3: `PRAGMA busy_timeout` placement inconsistency persists

- Severity: LOW
- Description: The proposal specifies
  `conn.execute("PRAGMA busy_timeout = 5000;")` in `main()` after
  `open_database()`. The prior audit (17-audit.md, Finding 2) already
  identified that this pragma should be set inside
  `bootstrap_database()` in `daemon/db.py:95-98` so that all callers
  (daemon and CLI) inherit the timeout. This proposal perpetuates the
  `main()`-level placement from the deleted `daemon.py`. The pragma is
  idempotent, so setting it in both locations would not cause harm, but
  setting it only in `main()` means CLI operations that use
  `open_database()` would not get the busy timeout.
- Recommendation: Accept for this partition since the test contract
  (`test_daemon_entry.py:226-229`) explicitly asserts the pragma is
  called on the connection, and the proposal is a faithful port.
  Moving the pragma into `bootstrap_database()` is a `daemon/db.py`
  change that should be tracked separately.

### Finding 4: `setup_applications` failure mode not specified

- Severity: LOW
- Description: The proposal specifies that `setup_hook()` must call
  `await setup_applications(self)` before `tree.sync(guild=guild)`.
  The `setup_applications` function (`daemon/applications.py:381-458`)
  reads active submission IDs from the database
  (`db.load_active_submission_ids(bot.conn)` at line 457) and registers
  persistent views. If this DB read fails (e.g., schema not yet
  migrated, disk error), the exception would propagate through
  `setup_hook()` → `bot.start()` → `main()`, and the `finally` block
  would close the database. This fail-fast behavior is correct, but the
  proposal does not explicitly state whether `setup_applications`
  failures should be fatal or recoverable. The implicit answer (let it
  propagate) is the right one — a bot that starts without persistent
  review views would silently lose button functionality on all active
  applications.
- Recommendation: Accept the implicit fail-fast behavior. No code
  change needed. If the proposal is revised, a brief note confirming
  that `setup_applications` failures are intentionally fatal would
  remove ambiguity.

### Finding 5: Test file targets deleted path — window of broken imports

- Severity: LOW
- Description: `tests/test_daemon_entry.py:18` sets
  `DAEMON_ENTRY_PATH = Path(__file__).resolve().parents[1] / "daemon.py"`,
  which no longer exists. The tests are already non-functional because
  `daemon.py` was deleted. The proposal acknowledges this (section
  "Test Impact") and specifies what the rewrite should assert, including
  the new import path (`daemon.__main__`), updated `BASE_PATH`
  derivation, and the `HumilityBot` class name. However, the proposal
  does not specify the sequencing: whether the test rewrite is part of
  this partition or a follow-up. If the implementation ships without the
  test rewrite, the test suite would still contain a test file that
  fails at import time.
- Recommendation: Clarify that the test rewrite is either included in
  this partition's implementation scope or is a named follow-up. The
  tests are already broken, so this is not a regression, but explicit
  sequencing avoids confusion.
