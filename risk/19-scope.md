# Scope Risk: `daemon/__main__.py`

**Overall risk level: LOW**

The proposal is a disciplined direct port of the deleted root `daemon.py`
into `daemon/__main__.py` with exactly three intentional changes — all
mechanically justified by existing code and the new file location. The
anti-scope section is comprehensive and no feature additions are
proposed. Scope proportionality is strong.

## Findings

### 1. All three changes are mechanically required

**Severity: INFO**

The proposal's three deviations from the old `daemon.py` are each driven
by constraints already present in the repo:

- **Path resolution** (`parent.parent` instead of `parent`): required
  because the file moves one directory deeper. Not a design choice.
- **Bot class rename** (`HumilityDaemonBot` → `HumilityBot`): matches
  the existing `TYPE_CHECKING` import in `daemon/applications.py:17-18`.
  The tests do not pin a class name — they only require exactly one
  `commands.Bot` subclass (`tests/test_daemon_entry.py:76-91`). No
  compatibility alias is needed.
- **`setup_applications(self)` wiring**: `daemon/applications.py:381`
  already defines `setup_applications(bot)` expecting to be called from
  the entry point's `setup_hook()`. The proposal places it before
  `tree.sync()` so `/apply` and persistent views are registered before
  the guild command sync. This is the integration the applications
  module was built for.

No speculative additions. No scope creep beyond what the existing module
contracts demand.

### 2. No new runtime behavior beyond applications wiring

**Severity: INFO**

Compared to the deleted `daemon.py`, the only new runtime behavior is
the `await setup_applications(self)` call in `setup_hook()`. The
proposal does not add:

- signal handling
- guild readiness validation
- concurrency policy
- new slash commands
- config hot-reload
- background tasks

This is narrower than the prior P17 entry-point proposal, which included
concurrency policy, signal handling, and guild validation. P19 strips all
of that, keeping scope minimal.

### 3. Anti-scope section is comprehensive

**Severity: INFO**

The anti-scope section (`proposals/19-daemon-main.md:259-271`) explicitly
excludes: new daemon features, ticket wiring, provisioning wiring, new
slash commands beyond `/ping`, compatibility aliases for
`HumilityDaemonBot`, a `daemon.py` shim, and any new startup abstraction
beyond the direct port plus applications wiring. No gaps identified.

### 4. Test impact is acknowledged and appropriately deferred

**Severity: INFO**

The proposal correctly identifies that `tests/test_daemon_entry.py`
currently targets the deleted root `daemon.py` file path
(`tests/test_daemon_entry.py:18-19`) and outlines what the follow-up
test rewrite should verify (`proposals/19-daemon-main.md:240-255`). The
test rewrite is deferred to a separate partition, which is appropriate —
the design proposal should not also carry test implementation.

### 5. Research and needs synthesis are aligned

**Severity: INFO**

Both `research/19-daemon-main.md` and `research/19-daemon-main-needs.md`
converge on the same conclusions as the proposal:

- `HumilityBot` is the correct class name (driven by `applications.py`)
- `BASE_PATH` must be `parent.parent` for the new location
- `setup_applications()` is the only new wiring needed
- the needs synthesis explicitly states "Gaps: None"

No contradictions between research inputs and proposal outputs.

### 6. No backward compatibility burden

**Severity: INFO**

The proposal explicitly rules out a `daemon.py` shim and a
`HumilityDaemonBot` alias. This is appropriate because:

- the old `daemon.py` was already deleted (the root file conflicts with
  the `daemon/` package name at the Python import level)
- `applications.py` already expects `HumilityBot`, not the old name
- the tests are name-agnostic

No orphaned compatibility surface to maintain.
