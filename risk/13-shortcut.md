# Shortcut Risk: `daemon/__init__.py`

**Overall risk level: LOW**

The proposal is a docstring-only package marker with no executable code,
no re-exports, and no runtime API surface. The design is deliberately
minimal, and every omission (no `__version__`, no `__all__`, no
re-exports, no setup logic) is explicitly called out in the anti-scope
section with clear reasoning rather than silently deferred. There are no
compatibility shims, no workarounds, and no patterns that would require
cleanup. The two findings below are minor documentation-maintenance
observations, not structural shortcuts.

## Findings

### 1. Submodule inventory in the docstring may drift (LOW)

The proposal specifies that the package docstring should list the planned
submodules (`config`, `db`, `claim`, `applications`, `tickets`,
`chapters`, `util`). These modules do not exist yet. If the module set
changes during development — modules renamed, split, merged, or new ones
added — the docstring becomes stale. A stale inventory in `__init__.py`
is mildly misleading to readers but has no runtime consequence.

**Severity:** LOW — the docstring is documentation, not code. Staleness
is a maintenance chore, not a structural debt. The submodule list is
already defined in `DAEMON_DESIGN.md`, so the docstring is a secondary
source that can be updated whenever modules change.

**Recommendation:** None required. Normal code-review discipline is
sufficient to keep the docstring current as submodules are added.

### 2. Proposal does not address `daemon.py` / `daemon/` name collision (LOW)

The daemon architecture places both `daemon.py` (entry point) and
`daemon/` (package) at the repo root. Python resolves this correctly —
the directory package takes precedence for imports, and the entry point
runs as `__main__` — but the proposal does not mention the coexistence
or confirm it was considered. The research document (section 6) does
address this, noting the `__main__` distinction, so the omission from
the proposal appears to be a scoping choice rather than an oversight.

**Severity:** LOW — the coexistence is a pre-existing architectural
decision from `DAEMON_DESIGN.md`, not something this proposal
introduces. The `__init__.py` file itself neither creates nor worsens
the situation. Python's resolution rules handle it correctly for the
planned usage pattern (entry point run directly, submodules imported from
the package).

**Recommendation:** None required. If the coexistence ever causes
confusion, the fix is an entry-point rename (e.g., `run_daemon.py` or a
`__main__.py` inside the package), but that is an architecture-level
decision outside this proposal's scope.
