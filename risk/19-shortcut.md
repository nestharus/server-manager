# Shortcut Risk: daemon/__main__.py

**Overall risk level: LOW**

The proposal is a disciplined direct port of the deleted root `daemon.py`
into the `daemon/__main__.py` package entry point. It makes exactly three
intentional changes (path resolution, class rename, applications wiring)
and explicitly rejects backward-compatibility shims and new features. The
research document thoroughly investigates the double-import hazard, naming
pressure, and package execution semantics. The few gaps identified are
carried-forward divergences from proposal 17's architectural decisions and
one documentation concern — none represent new shortcuts introduced by this
proposal.

## Findings

### 1. `busy_timeout` set in `main()`, not in `open_database()` — carries forward proposal 17 divergence (LOW)

Proposal 17 made a binding architectural decision: "`open_database()` must
also set `PRAGMA busy_timeout = 5000` immediately after enabling WAL"
(`proposals/17-daemon-entry.md`, Shared SQLite Concurrency Policy). The
intent was that every caller of `open_database()` would inherit the timeout
automatically. However, `daemon/db.py:95–104` does not set it — the
current `daemon.py` sets it caller-side in `main()`, and proposal 19's
runtime sequence (step 4) carries forward the same pattern:
`conn.execute("PRAGMA busy_timeout = 5000;")`.

This means any future module that calls `open_database()` directly — such
as `discord_cli.py` if it gains write access — will not get busy_timeout
unless it remembers to set it. The proposal doesn't acknowledge this
divergence from the decided architecture.

**Severity:** LOW — `discord_cli.py` does not currently use the database,
and the single-writer constraint from proposal 17 means concurrent access
is already gated. The risk surfaces only when a second writer is
introduced, at which point the concurrency policy itself must be revisited.

**Recommendation:** Either move `PRAGMA busy_timeout = 5000` into
`open_database()` (or `bootstrap_database()`) per proposal 17's decision,
or document the caller-side pattern as the new decided approach so future
callers know to set it.

### 2. `on_ready` guild validation silently dropped (LOW)

Proposal 17 specified detailed `on_ready` validation: look up the guild via
`bot.get_guild()`, shut down if missing, request chunking if not chunked,
and log a startup-complete message with guild name and member count. This
was designed to catch three operational traps — wrong guild, unapproved
members intent, and gateway not delivering member data.

The deleted `daemon.py` implementation did not include this validation, and
proposal 19 does not mention `on_ready` at all. Since proposal 19 frames
itself as a "direct port with three intentional changes only," the omission
is consistent — it is porting what existed, not what was specified. But
this means the operational trap that proposal 17 identified remains open
across the package migration.

**Severity:** LOW — the `/ping` command provides a basic liveness check,
and the guild readiness gap was already assessed as LOW in risk/17-shortcut.md
finding #3. Future handler partitions that depend on `get_member()` will
fail loud if members data is missing. The gap is not worse than before.

**Recommendation:** Track the `on_ready` guild validation as a known gap
to be addressed in the first partition that adds member-dependent handler
logic, rather than requiring it in the entry-point port.

### 3. `asyncio.to_thread()` not used in `applications.py` interaction handlers (LOW)

Proposal 17 made a binding decision: "All DB calls from interaction
handlers MUST use `asyncio.to_thread()`." The current `applications.py`
calls `db.get_submission_by_id()`, `db.transition_submission_status()`, and
other DB helpers synchronously in `ApplicationReviewView.handle_action()`
(`daemon/applications.py:272–351`). Proposal 19 wires `setup_applications()`
into `setup_hook()`, which activates this code path at runtime.

This is not a shortcut introduced by proposal 19 — the gap exists in
`applications.py` regardless. But by wiring the applications module into
the entry point, proposal 19 makes this code reachable for the first time
in the daemon's live runtime. The proposal does not flag this as a known
divergence.

**Severity:** LOW — SQLite queries on a local database are fast (sub-ms
for the queries in question). Blocking the event loop for a few milliseconds
during button callbacks is unlikely to cause observable latency in a
single-guild bot. The architectural principle matters more for future
queries that may be slower (full-table scans, writes under contention).

**Recommendation:** Note that the `asyncio.to_thread()` wrapping is a
prerequisite for the applications module, not for the entry point. The
applications module should be updated before or alongside the first
deployment that exercises these handlers under real load.

### 4. Test rewrite deferred but breakage is immediate (LOW)

The proposal states that `tests/test_daemon_entry.py` "currently targets
the deleted `daemon.py` file path" and lists what the follow-up test
rewrite should assert. The existing tests use `importlib.util.spec_from_file_location`
pointed at the root `daemon.py` path (`tests/test_daemon_entry.py:18`),
which no longer exists. These tests will fail immediately after the
package migration.

The proposal is design-only, so deferring the test rewrite to the
implementation partition is reasonable. But the implementation must update
the tests atomically — shipping `daemon/__main__.py` without updating
the tests would leave the test suite broken between commits.

**Severity:** LOW — the proposal explicitly describes the test contract
changes needed. The risk is procedural (forgetting to include tests in
the implementation commit), not architectural.

**Recommendation:** Ensure the implementation partition treats the test
rewrite as a blocking prerequisite, not a follow-up task. Both the new
entry point and the updated tests should land in the same commit or PR.

### 5. DAEMON_DESIGN.md and Railway references not updated (LOW)

The design document still describes the entry point as `daemon.py` and
the Railway entrypoint as `uv run python daemon.py`
(`docs/DAEMON_DESIGN.md:10`, `docs/DAEMON_DESIGN.md:169`). The research
document notes these are stale. Proposal 19 does not call for updating
them, though the out-of-scope section doesn't explicitly exclude doc
updates either.

**Severity:** LOW — the stale references are in documentation, not in
code that runs. A developer or operator reading the design doc would be
pointed at a non-existent file, but `python -m daemon` is the standard
Python package execution pattern and is easily discoverable.

**Recommendation:** Include a doc update for DAEMON_DESIGN.md in the
implementation partition, at minimum updating the file references and
the Railway entrypoint command to `python -m daemon`.

### 6. Double-import hazard documented but not guarded against (LOW)

The research document identifies that during `python -m daemon`, a runtime
import of `daemon.__main__` would execute the file a second time under a
different module identity, creating duplicate class objects and re-running
`load_dotenv()`. The proposal correctly notes that `applications.py`'s
back-reference is inside `TYPE_CHECKING` so this doesn't happen today.

The proposal does not add a guard against future developers converting
the `TYPE_CHECKING` import to a runtime import. This is a documentation
gap, not a code gap — the current code is safe.

**Severity:** LOW — the `TYPE_CHECKING` pattern is standard, and the
research document's analysis is thorough enough to serve as documentation
for anyone who encounters the issue. A runtime import of `__main__` from
within the daemon process would be unusual and would likely be caught in
code review.

**Recommendation:** None required. The research document already provides
the necessary context for future developers.
