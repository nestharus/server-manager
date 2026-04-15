# Scope Risk: Activity/Audit Model

**Rating: LOW**

## Justification

The proposed scope is well-matched to the problem. The initiative defines
a canonical architecture for durable history, actor attribution, and
optimistic locking — and it constrains itself to design only, with
chapters as a single proof-of-concept aggregate. That is the right grain
for a first move.

### Not too ambitious

The proposal defers the right things:

- Hash-chain validation is pushed to the second aggregate. Phase 1 uses
  a monotonic sequence number, which avoids the canonical-serialization
  problem entirely.
- Multi-aggregate transactional semantics are deferred until a second
  aggregate exists. Specifying saga/compensation patterns now would be
  premature.
- Automated rebuild tooling is deferred. Manual rebuild for a small
  chapters table is proportionate.
- The initiative is explicitly "define the architecture, not implement
  it." Implementation scope is a separate concern.

The model itself (two append-only tables + aggregate_heads + projection)
is a well-understood event-sourcing-lite pattern, not novel architecture.
Each component — action stream, state-change stream, head helper,
projection — is necessary for the model to function. Nothing is
speculative or optional-looking.

### Not too narrow

Chapters is the only mutable aggregate today. Proving the pattern on the
only thing that exists is the minimum viable scope. Defining less — say,
only the table schemas without the write path, concurrency model, or
query strategy — would leave critical design questions unresolved and
force ad-hoc decisions during implementation.

The proposal also establishes contracts (ETag/If-Match, projection
rebuild, actor attribution) that are general enough to carry forward to
future aggregates without redesign.

### Proportionate downstream work for chapters

The API contract break is real: version leaves the body, ETag/If-Match
replaces it, 409 becomes 412, and the write path grows from a single row
update to an 8-step transactional flow. Tests must change from
version-based to ETag-based assertions.

This is proportionate because:

- Chapters is the only consumer of the current contract.
- The platform has an explicit no-backwards-compatibility rule. No dual
  mode means no maintenance burden from straddling both models.
- The write path complexity increase is inherent to any activity-based
  concurrency model. It cannot be made simpler without abandoning the
  goal.
- The single-cutover approach avoids the worst outcome: two concurrent
  authority models in production where some paths use row version and
  others use activity heads.

### Does not block future work

The proposal is carefully designed to avoid blocking:

- The ETag is opaque to clients. Switching the backing validator from
  sequence number to hash chain is invisible to API consumers.
- The action/state-change split structurally supports multi-aggregate
  actions (one action, many state changes) even though the transactional
  semantics are deferred.
- Projection rebuild is defined as a contract now, so implementation
  work can build toward a known interface.
- Nothing in the Phase 1 design precludes hash-chain adoption, automated
  rebuild, or saga patterns later.

### Residual concerns (not scope risks)

These are implementation-phase concerns, not scope problems:

- The 8-step write path must execute in one transaction for
  read-your-write correctness. Getting the transaction boundary right
  under psycopg 3 is an implementation detail, but it is the most
  likely place for bugs.
- The indexing strategy (6+ indexes across new tables) is defined but
  untested at load. For chapters-scale data this is not a concern; it
  becomes one at a second aggregate with higher write volume.
- Diff capture (`diff_json` derived from `payload_json` at write time)
  adds write-path complexity. The proposal correctly makes it
  subordinate to `payload_json`, but implementers must resist the
  temptation to make diff the source of truth.

## What LOW requires

For scope risk to remain LOW, the following must hold during
implementation:

1. **Chapters stays the only migrated aggregate.** The proposal says
   this; implementation must not scope-creep into migrating a second
   aggregate in the same initiative.
2. **Phase 1 uses sequence-number concurrency only.** No hash-chain
   work, no canonical serialization specification, no corruption
   detection beyond sequence comparison.
3. **Rebuild tooling is a management command, not a framework.** No
   progress tracking, no automated scheduling, no production safety
   interlocks in Phase 1.
4. **The API cutover is atomic.** No transitional period supporting both
   body version and If-Match. One migration, one contract, one test
   update pass.
5. **Implementation is scoped separately.** This initiative defines
   architecture. Implementation effort, migration scripts, and
   repository changes are a follow-on with its own scope review.
