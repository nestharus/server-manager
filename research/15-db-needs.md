# Synthesis: daemon/db.py Needs

Date: 2026-04-13

## Humility-Specific Needs

1. **Schema bootstrap**: Use `CREATE TABLE IF NOT EXISTS` for the 4 tables from DAEMON_DESIGN.md (chapters, submissions, tickets, chapter_blacklist). Simple and sufficient for v1 — no migration framework needed yet.

2. **Connection management**: Single connection for the daemon's lifetime. WAL mode for concurrent reads from CLI. `row_factory = sqlite3.Row` for dict-like access.

3. **Database path**: From environment variable `DATABASE_PATH` (defaults to `discord.db` for local dev, `/data/discord.db` on Railway).

4. **Query helpers**: CRUD operations for each table. Keep them simple — plain functions that take a connection, not an ORM. The daemon modules (applications, tickets, chapters) will call these helpers.

5. **Thread safety**: The daemon is async but sqlite3 is synchronous. Use `check_same_thread=False` since discord.py runs callbacks in the event loop thread. For v1, single-thread access is sufficient.

6. **No interaction logic**: Pure database operations. No Discord API calls, no application flow.

## Gaps
None. The schema is fully defined in DAEMON_DESIGN.md.
