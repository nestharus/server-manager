# Proposal: Initiative — Activity/Audit Model

## 1. Executive summary

The `Activity/Audit Model` initiative establishes one canonical write
model for durable history, actor attribution, and optimistic locking.
The platform should stop treating business rows as the authority for
concurrency and history. Instead, accepted business facts should be
recorded in an append-only state-change stream, with a separate
append-only action stream preserving who attempted what and why.

The proposal adopts a two-stream model:

- `activity_actions` records attempted operations, actor context,
  surface, request intent, and outcome
- `activity_state_changes` records only accepted business facts and is
  the source of truth for audit history and aggregate evolution
- business tables such as `chapters` become current-state projections,
  not the authority for concurrency or historical reconstruction
- optimistic locking moves from row `version` columns to an
  activity-derived opaque head value exposed as an HTTP `ETag` and
  enforced with `If-Match`

This is a clean break. The platform should not keep row-versioning and
activity-derived versioning in production together. The initiative
exists to remove that split authority.

The first aggregate migrated (chapters) is explicitly a proof-of-concept.
Patterns established here will be refined when a second aggregate adopts
the model.

## 2. Scope of Activity/Audit Model

This initiative defines the canonical data model and write/read
boundaries for auditable business state.

In scope:

- define the canonical split between attempted actions and accepted
  state changes
- define append-only records as the durable source of audit history
- define optimistic locking via activity-derived `ETag` values instead
  of row `version` columns
- define how business-entity tables stay free of framework metadata
  (except `created_at`, which is retained as a business field)
- define actor attribution, request capture, and accepted-change
  capture
- define the indexing and query model for normal reads, audit reads, and
  concurrency checks
- define the migration impact on the existing chapters API as a
  proof-of-concept for the model
- define the projection-rebuild contract

This initiative does not implement the model, write migrations, or add
UI surfaces. It defines the canonical architecture that later hookpoint
and implementation work must follow.

Out of scope for the initial aggregate (deferred to second-aggregate
adoption):

- hash-chain head validation (first aggregate uses sequence-number
  concurrency)
- canonical serialization specification
- multi-aggregate transactional patterns

## 3. Canonical model and authority boundaries

### Action vs state change

The proposal adopts a strict semantic split.

An `action` is an attempted operation:

- who initiated it
- from which surface
- against which aggregate or workflow
- with which intended input
- whether it was accepted, rejected, failed, or produced no business
  change

A `state change` is an accepted business fact:

- it mutates one aggregate's durable history
- it advances that aggregate's concurrency head
- it is replayable into current state
- it links back to the action that caused it

One action may emit zero, one, or many state changes. Rejected and
failed actions remain auditable, but they do not advance concurrency and
they do not enter the accepted-state stream.

### Source of truth

The source of truth for historical reconstruction is the ordered
`activity_state_changes` stream per aggregate. The source of truth for
"who attempted what" is `activity_actions`. Business-entity tables are
derived projections for normal reads and business lookup.

That yields a clear authority split:

- audit of attempts starts from `activity_actions`
- audit of accepted facts starts from `activity_state_changes`
- current reads start from projection tables plus an aggregate-head
  helper
- optimistic locking starts from the aggregate head, not from mutable
  business rows

### Recommended physical shape

The proposal recommends three storage layers:

1. `activity_actions`
2. `activity_state_changes`
3. projection/head helpers

The helper layer should include an `aggregate_heads` table keyed by
`(aggregate_type, aggregate_id)` carrying the latest accepted sequence
and latest accepted state-change id. This is infrastructure metadata
and belongs outside business tables.

## 4. Write model and optimistic locking

### Concurrency contract

Optimistic locking should be expressed as an HTTP precondition, not as a
business-body field.

- reads return an opaque `ETag`
- mutating requests must send `If-Match`
- the server compares `If-Match` to the current aggregate head
- mismatch fails before any new accepted state change is appended

Once the API adopts HTTP preconditions, stale writes should return
`412 Precondition Failed`, not `409 Conflict`.

### Phased concurrency validator

The concurrency validator is phased across aggregate adoptions:

**Phase 1 (chapters — this initiative):** The head validator is a
monotonic sequence number stored in `aggregate_heads.current_seq`. The
ETag value is derived from this sequence number (e.g., the sequence
number itself, or a simple encoding of it). Clients treat it as opaque.

This approach is simpler, avoids the canonical-serialization problem
entirely for the first aggregate, and is sufficient to prove the
concurrency model.

**Phase 2 (second aggregate — future initiative):** If the platform
requires corruption-detection or cross-system verification, a
hash-chain head model may be introduced. At that point, the platform
must define a stable canonical serialization specification covering:

- serialization format (e.g., JCS / RFC 8785)
- key ordering rules
- null vs absent-field handling
- numeric representation (integer vs float, precision)
- hash algorithm (e.g., SHA-256)

The sequence-number validator from Phase 1 can coexist or be migrated.
The ETag remains opaque to clients in both phases.

### Canonical write path

For a mutation against one aggregate, the write path should be:

1. validate the request and actor context
2. read the current aggregate head
3. compare `If-Match` to the current head value
4. append an `activity_actions` row
5. if accepted, append one or more `activity_state_changes` rows
6. update `aggregate_heads`
7. update the relevant projection rows
8. return the new projection and `ETag`

Steps 4 through 7 should occur in one database transaction for the
current synchronous APIs. This proposal does not accept an eventually
consistent projection model for ordinary chapter writes because the
chapters API needs immediate read-your-write behavior and a stable new
`ETag`.

### Multi-aggregate actions

The model structurally supports linking many state changes to one
action, which means a single action can touch multiple aggregates.
However, the transactional semantics and failure handling for
multi-aggregate writes are explicitly deferred. No second aggregate
exists yet, and specifying transaction-boundary decisions before the
platform understands its actual cross-aggregate needs risks locking in
premature patterns.

When a second aggregate is proposed, a follow-on initiative must define:

- whether cross-aggregate writes share a transaction or use compensation
- what "fail cleanly" means for partial multi-aggregate failures
- whether a saga or workflow framework is warranted

This initiative scopes concurrency and writes to single-aggregate
operations only.

## 5. Clean business tables, actor attribution, and diff capture

### Business tables stay semantically clean

Business-entity tables should contain business state only.

They should not carry:

- row `version`
- actor ids
- request ids or correlation ids
- framework timestamps used only for audit bookkeeping
- activity hashes or sequence metadata

For chapters, the projection table should hold only the current chapter
fields that matter to business behavior, such as name, slug, status,
Discord bindings, and `created_at`.

`created_at` is retained on the projection table as a business field.
"When was this chapter created?" is a domain question that should be
answerable with a simple projection-table read, not a join against the
activity stream. Concurrency and history metadata (version, actor,
sequence) belong in `aggregate_heads` and the activity streams;
`created_at` does not.

### Actor attribution

Actor attribution belongs first on `activity_actions`.

Each action should capture:

- `actor_kind` such as `user` or `system`
- `actor_id`
- request surface such as API route, slash command, job, or admin task
- correlation/request id
- logical request payload after validation and redaction
- action status: `accepted`, `rejected`, `failed`, or `noop`
- rejection/failure reason when applicable
- recorded timestamp

Accepted state changes then link back to the causing action id. This
gives a durable chain from actor to action to accepted facts.

### Diff capture

The accepted-change stream captures two related artifacts:

- `payload_json`: the canonical accepted fact used to advance the
  aggregate and rebuild projections — this is the source of truth
- `diff_json`: a field-level business diff derived from `payload_json`
  by comparing the new payload against the previous state, used for
  human audit display

**Relationship:** `diff_json` is always derived from `payload_json`.
It is computed at write time by diffing the new accepted state against
the prior projection. `diff_json` is never independently computed or
independently authoritative. If the two were ever to disagree, the
`payload_json` is correct and `diff_json` should be recomputed.

The head value (sequence number in Phase 1, optionally hash in Phase 2)
is computed from `aggregate_heads.current_seq`, not from `payload_json`
or `diff_json` content. This decouples the concurrency primitive from
payload serialization.

The proposal should not rely on diff-only events for rebuild, and it
should not rely on full before/after row snapshots as the default
representation. Full snapshots may still be justified for specific
aggregates later, but they are not the default model.

Request capture must be redacted. Tokens, secrets, and opaque external
credentials do not belong in audit rows.

## 6. Query model and indexing strategy

### Read strategy

The ledger is not the hot read path. Normal list/get endpoints should
read projections plus the current aggregate head. Audit/history views
should read from the action and state-change tables. Rebuild/replay is a
repair and migration capability, not the default GET strategy.

That yields three query classes:

- current business reads from projection tables
- concurrency checks from `aggregate_heads`
- audit/history queries from `activity_actions` and
  `activity_state_changes`

### Core indexes

The proposal requires, at minimum:

On `activity_actions`:

- primary key on `id`
- index on `(aggregate_type, aggregate_id, recorded_at DESC)`
- index on `(actor_kind, actor_id, recorded_at DESC)`
- index on `(status, recorded_at DESC)` for audit and failure review
- optional unique index on idempotency/correlation key when a workflow
  requires deduplication

On `activity_state_changes`:

- primary key on `id`
- unique index on `(aggregate_type, aggregate_id, aggregate_seq)`
- index on `(aggregate_type, aggregate_id, recorded_at DESC)`
- index on `action_id`

On `aggregate_heads`:

- primary key on `(aggregate_type, aggregate_id)`

Projection tables keep business indexes only. For chapters, that
includes the kinds of indexes the business surface already needs, such
as a unique slug and status-oriented lookup paths. Projection indexes
should not become a second audit mechanism.

### Query and storage tradeoffs

Append-only storage improves historical correctness but increases:

- table growth and index growth
- vacuum and backup costs
- write-path complexity
- rebuild tooling requirements

That cost is acceptable only if the platform commits to projections and
repair tooling as first-class concerns. This proposal assumes that
commitment, with rebuild tooling delivered as a follow-on (see §8).

## 7. Migration impact on the existing chapters API

This initiative is a contract break for the current chapter surface.
The chapters migration is explicitly a proof-of-concept for the activity
model. Patterns established here will be refined when a second aggregate
adopts the model.

Today the chapter API is row-versioned:

- `ChapterRead` includes `version`
- `ChapterUpdate` requires `version`
- stale updates return `409 Conflict`
- the repository mutates the chapter row directly
- `created_at` is returned as part of the read DTO

Under this proposal, the chapters API changes as follows:

- `VersionedMixin` leaves `ChapterRead` and `ChapterUpdate`
- `version` is removed from request and response bodies
- chapter reads return an `ETag` header carrying the current aggregate
  head value (sequence-based in Phase 1)
- chapter mutations require `If-Match`
- stale chapter mutations return `412 Precondition Failed`
- `POST /api/v1/chapters/{id}/archive` becomes a preconditioned mutation
  as well; it should not remain an unguarded write while the rest of the
  aggregate is concurrency-protected
- `created_at` remains on the chapter projection table and in the
  business DTO

This must be a single cutover. The platform should not accept both body
`version` and `If-Match`, and it should not preserve both row-version
columns and activity-derived heads in production.

Downstream, tests must move from:

- read version `N`
- update with version `N`
- expect version `N+1`
- stale update returns `409`

to:

- read `ETag`
- update with `If-Match: <etag>`
- expect a new `ETag`
- stale update returns `412`

The current chapter repository pattern of `replace(..., version + 1)`
is superseded by append accepted action, append accepted state change,
advance aggregate head, and refresh the projection.

## 8. Projection rebuild contract and operational tooling

### Rebuild contract

Projection rebuild is a required capability for production safety. The
contract is defined here; implementation is a follow-on deliverable.

**Rebuild strategy:** Replay-from-zero. Rebuild reads the full ordered
`activity_state_changes` stream for an aggregate and recomputes the
projection by applying each accepted payload in sequence. This is
identical to what the live write path does for a single state change,
applied iteratively.

**Code sharing:** The projection-update logic used by the live write
path (step 7 in §4) must be the same code used by rebuild. There must
not be a separate "rebuild projection" implementation. A single
function takes an accepted state change and updates the projection;
the live path calls it once per write, and rebuild calls it in a loop.

**Divergence detection:** After rebuild, the rebuilt projection is
compared to `aggregate_heads.current_seq`. If the final replayed
sequence does not match the current head, the rebuild is marked as
failed and requires investigation. For the first aggregate (chapters),
manual comparison is sufficient.

**When rebuild runs:**

- on-demand for repair after suspected projection corruption
- during schema migrations that change projection shape
- as a verification step in staging before production deployment

### Tooling phasing

For the first aggregate (chapters, small table), rebuild can be a
management command or script. Automated rebuild scheduling, progress
tracking, and production safety interlocks are deferred to the
second-aggregate initiative when table sizes make manual repair
impractical.

## 9. Tradeoffs, failure modes, and downstream implications

### Tradeoffs

- This model is materially more complex than row-versioned CRUD.
- It produces cleaner authority boundaries and stronger auditability.
- It requires projection tables and head helpers; without them, the
  ledger becomes operationally clumsy.
- It favors SQL-first PostgreSQL design and explicit transactional
  writes, which aligns with the database-stack research.

### Failure modes

- If the sequence-based head value is not atomically incremented, clients
  will see false stale-write failures.
- If accepted state changes and projection/head updates are not
  transactionally aligned, reads can drift from the accepted ledger.
- If action request capture is too raw, the audit tables will leak
  secrets or store low-signal noise.
- If rebuild tooling is weak, projection corruption becomes hard to
  repair despite the append-only ledger.

### Downstream implications

- every mutable aggregate will need an explicit projection and aggregate
  head strategy
- API contracts should distinguish business DTOs from concurrency and
  audit metadata
- audit/history endpoints or views become a first-class product surface,
  because business DTOs stop carrying historical framework fields
- operational tooling must include replay/rebuild procedures for
  projections and head repair (follow-on deliverable for first aggregate)

## 10. What is explicitly out of scope

The following are not part of this initiative:

- implementation of migrations, repositories, or projection rebuild jobs
- choosing every event name for every future aggregate
- building audit UI screens or Discord-visible history surfaces
- introducing a second compatibility path that preserves row-versioned
  writes
- adopting a hybrid model where some aggregates use row versions and
  others use activity-derived heads without an explicit later proposal
- using logs as the durable audit source of truth
- replaying the full ledger on ordinary GET/list requests
- introducing framework metadata back into business rows "for
  convenience"
- hash-chain head validation and canonical serialization (deferred to
  second-aggregate adoption)
- multi-aggregate transactional semantics (deferred to when a second
  aggregate exists)
- automated rebuild tooling (manual is sufficient for first aggregate)

## 11. Recommendation

Adopt the split append-only model now as the canonical platform
direction:

- `activity_actions` for attempted operations and actor attribution
- `activity_state_changes` for accepted business facts and audit history
- `aggregate_heads` for current concurrency validation
  (sequence-number-based for Phase 1)
- projection tables for current business reads, including `created_at`
- `ETag`/`If-Match` as the only optimistic-locking contract

That gives Humility one coherent answer to history, attribution, and
concurrency. The cost is real, but the alternative is a mixed authority
model that keeps versioning, audit, and business state coupled in the
same mutable rows.

Chapters is the proof-of-concept. The second aggregate refines the
pattern.
