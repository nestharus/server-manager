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
  activity-derived opaque head hash exposed as an HTTP `ETag` and
  enforced with `If-Match`

This is a clean break. The platform should not keep row-versioning and
activity-derived versioning in production together. The initiative
exists to remove that split authority.

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
- define actor attribution, request capture, and accepted-change diff
  capture
- define the indexing and query model for normal reads, audit reads, and
  concurrency checks
- define the migration impact on the existing chapters API

This initiative does not implement the model, write migrations, or add
UI surfaces. It defines the canonical architecture that later hookpoint
and implementation work must follow.

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
`(aggregate_type, aggregate_id)` carrying the latest accepted sequence,
latest accepted state-change id, and current opaque head hash. This is
infrastructure metadata and belongs outside business tables.

## 4. Write model and optimistic locking

### Concurrency contract

Optimistic locking should be expressed as an HTTP precondition, not as a
business-body field.

- reads return an opaque `ETag`
- mutating requests must send `If-Match`
- the server compares `If-Match` to the current aggregate head
- mismatch fails before any new accepted state change is appended

The canonical validator is the aggregate's current head hash derived
from accepted state changes. It is not a row version and it is not a
timestamp. Clients treat it as opaque.

Once the API adopts HTTP preconditions, stale writes should return
`412 Precondition Failed`, not `409 Conflict`.

### Head-hash model

The head validator should be a hash-chain head carried by accepted state
changes and surfaced through `aggregate_heads`.

Each accepted state change stores:

- `aggregate_seq`
- `previous_head_hash`
- `head_hash`

The new `head_hash` is computed from the prior head plus a canonical
representation of the accepted state change. The platform must define a
stable canonical serialization for this computation before
implementation; without that, the validator is not trustworthy.

### Canonical write path

For a mutation against one aggregate, the write path should be:

1. validate the request and actor context
2. read the current aggregate head
3. compare `If-Match` to the current head hash
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

Some actions will legitimately emit changes to more than one aggregate.
The model supports that by linking many state changes to one action.
However, concurrency remains aggregate-scoped. A request touching
multiple aggregates must validate and append changes in one database
transaction or fail cleanly. This initiative does not introduce a
general workflow-orchestration or saga framework.

## 5. Clean business tables, actor attribution, and diff capture

### Business tables stay semantically clean

Business-entity tables should contain business state only.

They should not carry:

- row `version`
- actor ids
- request ids or correlation ids
- framework timestamps used only for audit bookkeeping
- activity hashes
- append-only sequence metadata

For chapters, the projection table should hold only the current chapter
fields that matter to business behavior, such as name, slug, status,
and Discord bindings. Concurrency and history metadata belong in
`aggregate_heads` and the activity streams.

This proposal also treats `created_at` as history metadata unless a
domain explicitly requires it as a business field. For the existing
chapters API, creation time should come from activity history rather
than from the canonical business projection.

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

The accepted-change stream should capture two distinct artifacts:

- `payload_json`: the canonical accepted fact used to advance the
  aggregate and rebuild projections
- `diff_json`: a field-level business diff used for human audit display

The payload is the reconstruction primitive. The diff is the audit
readability primitive. The proposal should not rely on diff-only events
for rebuild, and it should not rely on full before/after row snapshots
as the default representation. Full snapshots may still be justified for
specific aggregates later, but they are not the default model.

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
- unique index on `(aggregate_type, aggregate_id, head_hash)`
- index on `action_id`

On `aggregate_heads`:

- primary key on `(aggregate_type, aggregate_id)`
- unique or otherwise strictly controlled storage of the current
  `head_hash`

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
commitment.

## 7. Migration impact on the existing chapters API

This initiative is a contract break for the current chapter surface.

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
  head hash
- chapter mutations require `If-Match`
- stale chapter mutations return `412 Precondition Failed`
- `POST /api/v1/chapters/{id}/archive` becomes a preconditioned mutation
  as well; it should not remain an unguarded write while the rest of the
  aggregate is concurrency-protected
- `created_at` leaves the canonical chapter business DTO and becomes
  historical metadata derived from the activity stream

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

## 8. Tradeoffs, failure modes, and downstream implications

### Tradeoffs

- This model is materially more complex than row-versioned CRUD.
- It produces cleaner authority boundaries and stronger auditability.
- It requires projection tables and head helpers; without them, the
  ledger becomes operationally clumsy.
- It favors SQL-first PostgreSQL design and explicit transactional
  writes, which aligns with the database-stack research.

### Failure modes

- If canonical serialization for the head hash is unstable, clients will
  see false stale-write failures or incorrect validator reuse.
- If accepted state changes and projection/head updates are not
  transactionally aligned, reads can drift from the accepted ledger.
- If action request capture is too raw, the audit tables will leak
  secrets or store low-signal noise.
- If multi-aggregate writes are partially committed, the audit chain may
  show an accepted action without a coherent set of accepted facts.
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
  projections and head repair

## 9. What is explicitly out of scope

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

## 10. Recommendation

Adopt the split append-only model now as the canonical platform
direction:

- `activity_actions` for attempted operations and actor attribution
- `activity_state_changes` for accepted business facts and audit history
- `aggregate_heads` for current concurrency validation
- projection tables for current business reads
- `ETag`/`If-Match` as the only optimistic-locking contract

That gives Humility one coherent answer to history, attribution, and
concurrency. The cost is real, but the alternative is a mixed authority
model that keeps versioning, audit, and business state coupled in the
same mutable rows.
