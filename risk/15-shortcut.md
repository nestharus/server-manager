# Shortcut Risk: `daemon/db.py`

**Overall risk level: LOW**

The proposal is closely aligned with the research and explicitly
acknowledges the boundaries it draws. Anti-scope items (ORM, migration
framework, workflow logic, hidden globals) are listed with rationale
rather than silently omitted. The design is intentionally thin and the
tradeoffs are honest. The findings below are underspecifications — places
where the research raised a concern that the proposal does not address —
rather than corners cut for expedience.

## Findings

### 1. Thread-safety policy unspecified (MEDIUM)

The research (§5) documents that `check_same_thread=True` is the
`sqlite3` default, that cross-thread use raises `ProgrammingError`, and
that the daemon may eventually invoke callbacks from background tasks or
worker threads. The needs synthesis recommends
`check_same_thread=False`. The proposal's `connect_database` section
says only "configure the connection for daemon use" and
"set `row_factory = sqlite3.Row`" — it does not mention
`check_same_thread`, does not state the threading policy, and does not
address the research's warning that disabling the check requires
application-side serialization to avoid corruption.

**Severity:** MEDIUM — the practical risk in v1 is low because
discord.py's event loop is single-threaded, but the research
specifically flagged this as an open question and the proposal is silent
on it. An implementer following only the proposal has no guidance, while
an implementer following the needs doc gets a recommendation
(`check_same_thread=False`) without the serialization caveat the
research attached to it.

**Recommendation:** Add one sentence to the Connection Rules section
stating which `check_same_thread` value to use and why (e.g., "keep the
default `check_same_thread=True` since v1 database access stays on the
event loop thread" or "set `check_same_thread=False` since discord.py
callbacks are all dispatched on the main thread").

### 2. WAL mode failure undetected (LOW)

The research (§2) notes that `PRAGMA journal_mode=WAL` returns `wal` on
success or the prior mode unchanged on failure. The proposal says
bootstrap should execute the pragma but does not specify checking the
return value. If WAL mode fails silently (e.g., read-only filesystem,
NFS path), the daemon falls back to rollback-journal mode without
knowing, degrading the concurrent daemon/CLI access the design depends
on.

**Severity:** LOW — Railway's persistent volume is local and writable,
so WAL activation is almost certain to succeed. The failure scenario is
plausible only on an unexpected hosting misconfiguration.

**Recommendation:** Add a note that the bootstrap function should verify
the pragma's return value equals `wal` and raise on mismatch.

### 3. `busy_timeout` not addressed (LOW)

The research (§4) identifies `timeout` and `busy_timeout` as the
built-in mechanism for write-lock contention when multiple connections
share a database file. The proposal enables that exact scenario (daemon
+ CLI on the same file) but does not mention busy_timeout or state
whether the 5-second default is appropriate.

**Severity:** LOW — the default 5-second timeout is reasonable for v1
volumes. A CLI write blocked for 5 seconds during a daemon write is
unlikely and would resolve normally.

**Recommendation:** Consider a one-line note in Connection Rules
acknowledging the default timeout as acceptable for v1.

### 4. `executescript()` implicit commit not acknowledged (LOW)

The research (§3) explicitly flags that `executescript()` implicitly
commits any pending transaction under legacy transaction control. The
proposal's bootstrap calls for running a multi-statement schema script
(consistent with `executescript()`) but does not acknowledge this side
effect.

**Severity:** LOW — bootstrap runs at process startup before any
application transactions exist, so the implicit commit has no practical
consequence. The concern would only matter if bootstrap were ever called
mid-flight with an open transaction.

**Recommendation:** None required. The startup-only usage makes this
safe. A comment in the bootstrap function noting the implicit commit
behavior would be sufficient if the implementation uses `executescript()`.

### 5. Timestamp format unspecified (LOW)

The research (§7) notes all timestamps are stored as `TEXT`. The
proposal defines helpers that write and read timestamp columns
(`created_at`, `submitted_at`, `opened_at`, `archived_at`, etc.) but
does not specify the format. ISO 8601 is the natural choice and
SQLite's built-in datetime functions work with it, but leaving the
format implicit means different callers could produce inconsistent
strings.

**Severity:** LOW — an implementer will almost certainly pick ISO 8601,
and any inconsistency would be caught in early testing.

**Recommendation:** Add one sentence stating the timestamp format (e.g.,
"all TEXT timestamps use ISO 8601 UTC").

### 6. No secondary indexes discussed (LOW)

The research (§7) notes the schema has no indexes beyond primary keys.
The proposal defines helpers for lookup by `thread_id`,
`queue_message_id`, `chapter_slug`, and `status` — access patterns that
would benefit from indexes — but does not mention indexing at all.

**Severity:** LOW — at v1 table sizes (tens to low hundreds of rows),
full table scans are imperceptible. The gap is silent rather than
acknowledged, but has zero practical impact.

**Recommendation:** None required. Indexes can be added when query
volume warrants them, without changing the helper API.
