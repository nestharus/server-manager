# Risk: Activity/Audit Model — Safety & Data-Integrity Audit (Re-assessment)

**Rating: LOW** — all four prior MEDIUM findings resolved by addenda A1–A4.

## Prior MEDIUM findings: disposition

### 1. Transactional atomicity / four-write invariant → LOW

**Prior concern:** The proposal body (§4) used "should" language for the
four-write transaction (action insert, state-change insert, head update,
projection update). Without a harder contract, implementation could split
the transaction boundary accidentally.

**What A1 adds:** Mandates a single `mutate_entity()` service-layer
primitive that owns all four writes in one PostgreSQL transaction. Direct
write paths outside this primitive are forbidden and treated as CI/review
violations.

**Why resolved:** "Should execute in one transaction" is now "MUST go
through a single primitive." The primitive is named, its scope is
defined, and bypass is explicitly a violation. This converts an
architectural recommendation into an enforceable contract. Combined with
psycopg 3 against a single PostgreSQL instance (no cross-service writes),
standard `BEGIN / COMMIT` guarantees are sufficient.

**Residual risk:** Implementation must enforce the single-primitive rule
through code review and, ideally, a linting or architectural test that
detects direct writes to activity tables outside `mutate_entity()`.
This is a code-quality concern, not an architectural gap.

### 2. Hash / ETag determinism → LOW

**Prior concern:** Hash-based ETags require canonical serialization
(key ordering, null handling, numeric precision, hash algorithm). Without
a serialization spec, hash determinism is fragile.

**What A2 adds:** Explicitly states that Phase 1 does not depend on
hash-chain correctness. The concurrency head is a monotonic sequence
number. Hash-chain heads and canonical serialization are deferred to the
second-aggregate initiative. Phase 1 does not rely on timestamp precision
or JSONB serialization determinism.

**Why resolved:** The risk was never about sequence numbers — it was
about premature adoption of hash-chain heads without a serialization
spec. A2 codifies the deferral as a formal commitment, removing any
ambiguity about Phase 1 dependencies. Sequence-number determinism is
guaranteed by PostgreSQL's transactional isolation (the increment happens
inside the same transaction as the state-change append).

**Residual risk:** None for Phase 1. Phase 2 will require its own risk
assessment when the serialization specification is proposed.

### 3. Backfill correctness → LOW

**Prior concern:** Rebuild could silently produce a divergent projection
if the replay logic differs from the live write path, or if a partial
rebuild is accepted as valid.

**What A3 adds:** Mandates that backfill replays `activity_state_changes`
through the same projection-update function used by the live write path.
Backfills must fail closed on divergence, verify the final
`aggregate_heads.current_seq`, and must not leave a partially rebuilt
projection silently accepted as valid state.

**Why resolved:** A3 closes the two gaps that mattered. First, code
sharing between live and rebuild paths is now a MUST, not a
recommendation. Second, the fail-closed requirement prevents silent
corruption — a partial or divergent rebuild is treated as a failure
requiring investigation, not quietly promoted to current state. For the
first aggregate (chapters, small table), manual verification is
sufficient.

**Residual risk:** Automated divergence alerting is deferred to the
second aggregate. Acceptable at current scale.

### 4. Rollback path → LOW

**Prior concern:** A single cutover with no dual-write path means a
failed migration could leave the system in a broken state with no
defined recovery mechanism.

**What A4 adds:** Requires staging rehearsal before production cutover.
Mandates a backup immediately before production cutover. If the cutover
fails, the rollback is restore-from-backup — not reintroduction of the
old row-version path. No compatibility shim, dual-write mode, or mixed
authority rollback path is allowed.

**Why resolved:** A4 provides a concrete, tested rollback mechanism
(backup restore) instead of leaving rollback undefined. The staging
rehearsal requirement means the cutover is validated before it runs
against production. The explicit prohibition on mixed-authority fallback
prevents the most dangerous failure mode (two competing concurrency
authorities). For one small aggregate (chapters), backup/restore is a
proportionate and reliable recovery strategy.

**Residual risk:** The backup must be taken immediately before cutover,
not hours earlier. This is an operational discipline requirement, not an
architectural gap.

## Privacy and security notes

- **No PII leakage by design.** Activity rows store actor IDs and
  business payload metadata, not raw user content beyond the business
  fields. Redaction of secrets and tokens is mandated (§5).
- **No new attack surface.** The proposal adds no external endpoints,
  webhooks, or cross-service calls. All writes are internal PostgreSQL
  transactions.
- **Audit immutability supports compliance.** Append-only streams are
  the correct foundation. Physical enforcement (trigger/rule rejecting
  UPDATE/DELETE) should be added at implementation time.

## What LOW requires

For this rating to hold, the implementation must:

1. **Route all mutations through `mutate_entity()`** with the four
   writes (action, state change(s), head update, projection) in a
   single database transaction. No partial commits.
2. **Enforce audit-row immutability at the database level.** Add a
   PostgreSQL trigger or rule rejecting UPDATE and DELETE on
   `activity_actions` and `activity_state_changes`.
3. **Implement request-payload redaction as an allowlist.** Define safe
   fields explicitly; reject everything else from persisted
   `request_json`.
4. **Rehearse the chapters migration in staging** as a single atomic
   cutover. Take a backup immediately before production cutover.
   Verify old row-version path is fully removed and new activity path
   is fully operational.
5. **Share projection-update code** between the live write path and
   rebuild. No separate rebuild implementation.
6. **Fail closed on rebuild divergence.** If replayed sequence does not
   match `aggregate_heads.current_seq`, treat the rebuild as failed.
7. **Validate ETag round-trip determinism in integration tests:**
   read → mutate with If-Match → verify new ETag → stale mutate
   returns 412.
