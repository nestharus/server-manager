# Risk Assessment: Shortcut Risk — `daemon.py`

Date: 2026-04-13

Overall risk: **LOW**

## Summary

The proposal makes explicit architectural decisions across every area
that typically generates deferred shortcuts: SQLite concurrency,
health monitoring, async DB access, and guild readiness validation.
Forward-looking statements are framed as binding constraints with
blocking prerequisites, not as open questions to revisit later. The
few gaps identified are minor — they concern the precision of a
heuristic check and a small divergence in database path resolution —
and none represent deferred decisions that will become hard blockers.

## Findings

### 1. SQLite Concurrency Policy makes binding decisions

The "Shared SQLite Concurrency Policy" section contains three explicit
architectural decisions, not deferrals:

- **WAL + busy_timeout in the DB layer**: requires `open_database()` to
  set `PRAGMA busy_timeout = 5000` (`proposals/proposals/17-daemon-entry.md:420–426`).
  Every caller inherits the timeout. Concrete change to `daemon/db.py:95–98`.
- **Single-writer constraint**: "only one process may hold an open write
  transaction at a time" (`proposals/proposals/17-daemon-entry.md:429–442`). The first
  partition requiring concurrent writes must design a multi-writer policy
  as a **blocking prerequisite**, not a follow-up.
- **Async DB wrapping**: "All DB calls from interaction handlers MUST use
  `asyncio.to_thread()`" (`proposals/proposals/17-daemon-entry.md:446–452`). This is
  decided architecture — the pattern is set even though no handler
  invokes it yet.

All three are decided constraints. No deferral.

**Risk: LOW**

### 2. Production health signal is a decided constraint with an upgrade trigger

The proposal declares process liveness as the health model for all
scaffold-era partitions (`proposals/proposals/17-daemon-entry.md:291–313`). This is not
"we'll figure out health later" — it is an explicit decision that process
liveness IS sufficient while the daemon has no background work that can
fail silently. The upgrade trigger is stated as a blocking prerequisite:
"The first partition that adds background work which can fail without
crashing the process must add an HTTP health endpoint" before
implementation, not after.

The reasoning is sound: Railway restarts exited containers, and
`reconnect=True` handles transient gateway disconnections. The gateway
connection itself is the liveness probe.

**Risk: LOW**

### 3. Guild readiness validation closes the members-intent trap with a heuristic

The validation behavior is concrete (`proposals/proposals/17-daemon-entry.md:326–338`):
look up the guild, shut down if missing, request chunking if not chunked,
log guild name and member count. The proposal explicitly identifies three
operational traps this catches: wrong guild, unapproved members intent,
and gateway not delivering member data.

There is one minor gap: the validation logs member count but does not
assert that the count is plausibly non-trivial (e.g., `> 1`). If the
members intent is not approved at the Discord developer portal,
`guild.chunk()` may succeed silently with a nearly empty member list, and
the daemon would log "startup complete" with a suspiciously low count
rather than shutting down. An operator watching logs would notice, but
the daemon wouldn't catch it automatically.

This is a heuristic gap, not a deferral. The validation behavior is
decided and concrete — it just relies on operator observation for one
edge case rather than automated detection. Future handler partitions
will fail loud on `get_member()` returning `None`, providing a second
detection layer.

**Risk: LOW**

### 4. Database path resolution bypasses `resolve_database_config()` correctly but creates a minor divergence

The proposal correctly identifies that `daemon.db.resolve_database_config()`
returns a cwd-relative `Path("discord.db")` when `DATABASE_PATH` is unset
(`daemon/db.py:80–84`), and decides that `daemon.py` must bypass it,
reading the env var directly and falling back to `base_path / "discord.db"`
(`proposals/proposals/17-daemon-entry.md:395–411`).

This is the right decision for the daemon. The minor divergence: the
helper function `resolve_database_config()` still exists with its
cwd-relative default, but no current caller outside tests uses it. If a
future module calls `resolve_database_config()` without reading this
proposal, it would get the cwd-relative behavior. The risk is minimal
because the proposal makes the daemon's path resolution explicit, and
the CLI (`discord_cli.py`) does not currently use the database at all.

**Risk: LOW**

### 5. `on_ready` idempotency not explicitly addressed

In discord.py, `on_ready` can fire multiple times — once on initial
connection and again after each reconnection. The CLI guards against
this with a `has_run` flag (`discord_cli.py:446–449`). The proposal
places guild validation in `on_ready` but does not mention whether the
handler should be guarded against repeated invocation.

For the scaffold, this is not a real risk: the validation check (look up
guild, log member count) is naturally idempotent. Re-running it after a
reconnection is harmless or even useful. But the proposal should note
the pattern for future partitions that add `on_ready` work that is not
idempotent (e.g., posting a "bot online" message).

**Risk: LOW**

## Bottom Line

The proposal is unusually disciplined about converting potential deferrals
into decided constraints. The SQLite concurrency policy, health model,
async DB pattern, and guild validation all make binding architectural
decisions with clear upgrade triggers stated as blocking prerequisites.
The gaps found — members-intent heuristic precision, database path helper
divergence, `on_ready` idempotency — are minor and none represent
deferred decisions that will become hard blockers. This is a low-risk
proposal.
