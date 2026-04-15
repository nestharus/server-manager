# Risk: Activity/Audit Model — Safety & Data-Integrity Audit

**Rating: LOW** — with conditions listed below.

## Justification

The proposal is architecturally sound across the six focus areas. No
high- or medium-severity gaps were found. The risks that remain are
implementation-time concerns that are solvable with standard PostgreSQL
transactional guarantees, and the proposal explicitly identifies most of
them as failure modes.

### 1. Transactional atomicity across business-row mutation + activity rows

The proposal requires steps 4–7 of the canonical write path (append
action, append state change(s), update aggregate head, update projection)
to execute in **one database transaction** (§4). This is the correct
design. Because the stack is psycopg 3 against a single PostgreSQL
instance with no cross-database or cross-service writes, standard
`BEGIN / COMMIT` guarantees are sufficient. There is no eventual-
consistency gap, no two-phase commit, and no saga requirement for the
single-aggregate scope.

**Residual risk:** Implementation must not break the transaction
boundary (e.g., committing the action row before the state-change row,
or issuing projection updates outside the transaction). This is a
code-review concern, not an architectural one.

### 2. Hash / ETag determinism

Phase 1 uses a **monotonic sequence number**, not a hash. The sequence
is incremented inside the same transaction that appends the state change,
so determinism is guaranteed by PostgreSQL's transactional isolation.
The ETag is derived from this sequence and is opaque to clients.

Hash-chain heads and canonical serialization are explicitly deferred to
Phase 2 (second aggregate). The proposal correctly identifies the
serialization specification (JCS/RFC 8785, key ordering, null handling,
numeric precision, hash algorithm) as prerequisites that must be defined
before hash-chain heads are adopted. Deferral is the right call; adopting
hashes without that specification would be the actual risk.

**Residual risk:** None for Phase 1. Phase 2 will need its own risk
assessment when the serialization spec is proposed.

### 3. Audit-row immutability

Both `activity_actions` and `activity_state_changes` are defined as
**append-only** streams. The proposal never describes an UPDATE or DELETE
path against these tables. The physical enforcement (e.g., triggers
blocking UPDATE/DELETE, or RLS policies) is an implementation detail the
proposal does not specify, but the intent is unambiguous.

**Residual risk:** Without explicit database-level enforcement (a
trigger or policy denying mutations), application bugs or ad-hoc
maintenance queries could violate immutability. This should be addressed
at implementation time with a PostgreSQL trigger or rule. Low severity
because the risk is accidental, not architectural.

### 4. Actor attribution

Attribution is well-structured. Each action captures `actor_kind`,
`actor_id`, request surface, correlation ID, logical request payload
(post-redaction), outcome status, and rejection/failure reason.
State changes link back to the action via `action_id`, producing a
durable chain: actor → action → accepted facts → projection.

The proposal explicitly requires **redaction** of tokens, secrets, and
opaque external credentials from request capture (§5). This is the
correct privacy boundary.

**Residual risk:** Redaction is stated as a requirement but no
mechanism is specified (allowlist vs blocklist, at which layer).
Implementation must define where redaction occurs (service layer, before
the action row is written) and must default to allowlisting safe fields
rather than blocklisting dangerous ones. Low severity because the
proposal raises the requirement; it just does not prescribe the
implementation.

### 5. Backfill and rollback safety

The proposal defines a **replay-from-zero rebuild** strategy (§8):
replay all `activity_state_changes` in order using the same
projection-update function the live write path uses. Divergence detection
compares the final replayed sequence against `aggregate_heads.current_seq`.

For the first aggregate (chapters, small table), manual rebuild is
accepted. Automated tooling is explicitly deferred.

**Backfill safety:** Because the activity streams are append-only and
the projection is derived, a corrupt projection can always be rebuilt
from the authoritative stream. This is strictly safer than the current
mutable-row model, where a bad UPDATE destroys the prior state.

**Rollback safety:** The proposal mandates a single cutover from
row-versioned to activity-derived concurrency (§7). There is no
dual-mode or backward-compatibility path. This is a one-way migration.
If the cutover fails partway, the rollback strategy is to restore from
backup and re-attempt — not to fall back to the old row-version model.

**Residual risk:** The single-cutover strategy is clean but means the
migration itself must be tested end-to-end in staging before production.
A half-applied migration (e.g., activity tables created but projection
not populated) would leave the system in a broken state. Low severity
because the scope is one small aggregate (chapters) and the proposal
explicitly calls this a proof-of-concept.

### 6. Operational failure recovery

The combination of append-only streams + derived projections + rebuild
tooling gives a strong recovery model:

- **Projection corruption:** Rebuild from the activity stream.
- **Head drift:** Rebuild recomputes the head from the stream and
  compares against `aggregate_heads`.
- **Lost action rows:** Not recoverable from the activity stream alone,
  but action rows are written in the same transaction as state changes,
  so partial loss requires a PostgreSQL-level failure (disk corruption,
  incomplete backup restore). Standard database backup/recovery applies.
- **Transaction failure mid-write:** PostgreSQL atomicity guarantees
  mean a crashed transaction leaves no partial state. The next retry
  starts clean.

**Residual risk:** The proposal does not specify monitoring or alerting
for projection drift. For the first aggregate this is acceptable (manual
verification), but for production maturity, automated drift detection
should be added when a second aggregate is onboarded. Low severity.

## Privacy and security notes

- **No PII leakage by design:** The activity model stores actor IDs and
  action metadata, not raw user content beyond the business payload.
  Redaction is mandated for secrets and tokens.
- **No new attack surface:** The proposal does not add external
  endpoints, webhooks, or cross-service calls. All writes are internal
  PostgreSQL transactions.
- **Audit immutability supports compliance:** Append-only streams are
  the correct foundation for audit requirements. Physical enforcement
  should be added at implementation time.

## What LOW requires

For this rating to hold, the implementation must:

1. **Keep steps 4–7 of the write path in a single database
   transaction.** No partial commits, no async projection updates for
   the synchronous API path.
2. **Enforce audit-row immutability at the database level.** Add a
   PostgreSQL trigger or rule that rejects UPDATE and DELETE on
   `activity_actions` and `activity_state_changes`.
3. **Implement request-payload redaction as an allowlist**, not a
   blocklist. Define the safe fields explicitly; reject everything else
   from the persisted `request_json`.
4. **Test the chapters migration as a single atomic cutover in staging**
   before production. Verify that the old row-version path is fully
   removed and the new activity path is fully operational.
5. **Share projection-update code between the live write path and
   rebuild**, as the proposal requires. Do not create a separate rebuild
   implementation.
6. **Validate ETag round-trip determinism in integration tests:**
   read → mutate with If-Match → verify new ETag → stale mutate returns
   412.
