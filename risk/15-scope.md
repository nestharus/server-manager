# Scope Risk: `daemon/db.py`

**Overall risk level: LOW**

The proposal defines a thin, synchronous SQLite boundary module with
three clear responsibilities: resolve the database path, open/configure
a connection, and expose per-table query helpers. The anti-scope section
is comprehensive (10 explicit exclusions) and well-calibrated to the
architecture in DAEMON_DESIGN.md. The module does not absorb workflow
logic, Discord API calls, migration orchestration, or ORM abstractions.
The public API surface — three bootstrap functions plus table-oriented
helpers — is proportionate to the four-table schema. Transaction
boundaries are explicitly delegated to callers, which prevents the db
layer from accumulating policy decisions.

## Findings

### 1. Full helper list could tempt premature implementation

**Severity: LOW**

The proposal enumerates ~22 helpers across all four table families with
named signatures. It correctly adds a design note that "v1
implementation should prioritize connection/bootstrap plus the minimum
helpers actually needed by the first daemon flows," but the full
inventory is prominent and detailed. An implementer could reasonably
interpret the list as the v1 deliverable rather than a planned surface.

**Recommendation:** No proposal change needed. At implementation time,
gate each helper on an actual caller in `applications.py`, `tickets.py`,
`chapters.py`, or the CLI. Helpers without a caller stay unwritten.

### 2. `check_same_thread` not addressed

**Severity: INFO**

The research (section 5) identifies thread safety as a relevant concern
and the needs synthesis recommends `check_same_thread=False`. The
proposal's connection rules section specifies `row_factory` and
parameterized SQL but does not state a position on `check_same_thread`.
This is an implementation detail rather than a scope issue — the
proposal is not accidentally pulling threading policy into scope, it
simply leaves the parameter unspecified.

**Recommendation:** The implementation should document the
`check_same_thread` choice in a code comment at connect time.

### 3. Migration deferral is correctly scoped

**Severity: INFO**

DAEMON_DESIGN.md names `db.py` as responsible for "migrations," yet the
proposal explicitly defers migration machinery to post-v1. The research
confirms that `CREATE TABLE IF NOT EXISTS` is sufficient for first-boot
but does not reconcile column changes on existing databases. This
deferral is appropriate: the schema is new, there are no existing
databases to migrate, and adding migration scaffolding now would be
speculative. No scope risk — the deferral is deliberate and justified.

### 4. DatabaseConfig is minimal and proportionate

**Severity: INFO**

`DatabaseConfig` has one field (`path`). The needs synthesis and research
both confirm this is the only configuration axis. No risk of the config
object becoming an accidental extension point for unrelated settings.

### 5. Anti-scope covers the right exclusions

**Severity: INFO**

The 10 anti-scope bullets map directly to foreseeable scope-creep
vectors: ORM drift, Discord API leakage, workflow logic absorption,
migration framework, connection pooling, global state, and ad-hoc SQL.
Each exclusion corresponds to something another module in the
architecture already owns. No gaps detected — the anti-scope is
complete relative to the current design surface.

### 6. Transaction policy delegation is a clean boundary

**Severity: INFO**

The rule "no implicit `commit()` inside helpers; transaction boundaries
belong to the caller" prevents the db layer from silently absorbing
commit policy. This is the correct cut for a shared module consumed by
both long-running daemon handlers and one-shot CLI commands, which have
different transaction lifetimes. No scope leakage risk here.
