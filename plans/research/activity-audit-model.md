# Activity/Audit Data Model Research

## Bottom line

If the goal is to remove `version`, timestamps, actor metadata, and
activity hashes from business rows while still keeping optimistic
locking, auditability, and history, the strongest model is:

- an append-only `activity_actions` stream for user/system actions
- an append-only `activity_state_changes` stream for accepted business
  facts emitted by those actions
- thin current-state projection tables for normal reads
- optimistic locking derived from the aggregate's current activity head,
  exposed as an HTTP `ETag` and checked with `If-Match`

That split matters. Actions and state changes are not the same thing.
An action is who tried to do what and why. A state change is the durable
fact that actually changed business state. Failed or rejected actions
should remain auditable, but they must not advance the concurrency
validator because they did not change state.

For this project, activity-derived versioning is a better conceptual fit
than entity-row `version` fields because the user explicitly wants one
append-only mechanism to provide history, actor attribution, and
optimistic locking. The cost is higher write-path complexity and a hard
requirement for projection/read-model tables. The design should not
pretend replaying the full ledger on every GET is acceptable.

## 1. Problem framing: actions vs state changes

The user's distinction is structurally correct and should be preserved.

`Action` means an attempted business operation:

- who initiated it
- from which surface
- against which aggregate
- with which intended payload
- whether it was accepted, rejected, failed, or produced no change

`State change` means the accepted business fact(s) caused by that
action:

- chapter renamed
- chapter archived
- officer role linked
- activity row corrected
- member/day score superseded

One action can produce zero, one, or many state changes. Examples:

- `PATCH /chapters/{id}` with invalid preconditions produces one audited
  action and zero state changes.
- `archive chapter` produces one action and one state change for the
  chapter aggregate.
- `approve application` could produce one action and multiple accepted
  state changes across application, roster, and role-assignment
  aggregates.

This split avoids a common failure mode in mixed audit/event tables:
failed writes and accepted writes get co-mingled in one stream, which
makes the stream poor at both audit and locking. Audit wants to record
attempts. Optimistic locking wants to advance only on accepted state
transitions.

The practical implication is:

- audit history should start from actions
- business reconstruction and optimistic locking should start from state
  changes

## 2. Entity-row versioning vs activity-derived versioning

The current chapter API is conventional row-level optimistic locking:

- `ChapterRead` returns `version`
- `ChapterUpdate` requires `version`
- the repository compares `expected_version`
- accepted updates increment the row's `version`
- stale updates return `409 Conflict`

That model is simple, but it couples three concerns to the entity row:

- current business state
- concurrency control
- mutation history hints

That is exactly what the user wants to avoid.

Activity-derived versioning changes the authority boundary:

- business rows become projections of current state, not the source of
  write authority
- the append-only activity stream becomes the source of truth
- the current concurrency validator comes from the aggregate's stream
  head, not from a mutable entity column

Benefits over row-level `version`:

- one source for history, actor attribution, and locking
- correction flows become natural append operations instead of "update +
  remember what changed"
- business rows stay semantically clean
- projections can be rebuilt if needed

Costs relative to row-level `version`:

- writes need a serialization point per aggregate
- read paths need projections or materialized heads
- debugging requires understanding action streams and projections
- backfills and migrations become more operationally significant

This trade is justified only if durable history and audit are
first-class requirements. In this project they are.

## 3. Activity-table schema options

There are three realistic schema shapes.

### Option A: single append-only table for everything

One table stores actor, target, request payload, before/after snapshots,
event type, and status.

Strengths:

- simplest schema
- easy to start
- one place to inspect

Weaknesses:

- actions and accepted state changes are conflated
- stale-write attempts and accepted writes live in the same stream
- multi-aggregate actions become awkward
- concurrency validators become harder to define cleanly

This is acceptable for a pure audit table. It is weak as the single
mechanism for both audit and optimistic locking.

### Option B: split `activity_actions` and `activity_state_changes`

`activity_actions` records the attempted operation and actor context.
`activity_state_changes` records only accepted domain facts and links
back to the action that caused them.

Typical columns for `activity_actions`:

- `id`
- `action_type`
- `aggregate_type`
- `aggregate_id`
- `actor_kind`
- `actor_id`
- `request_json`
- `status` (`accepted`, `rejected`, `failed`, `noop`)
- `reason_text`
- `recorded_at`
- optional idempotency/correlation keys

Typical columns for `activity_state_changes`:

- `id`
- `action_id`
- `aggregate_type`
- `aggregate_id`
- `aggregate_seq`
- `change_type`
- `payload_json`
- `previous_head_hash`
- `head_hash`
- `recorded_at`
- optional business-effective timestamp when needed

Strengths:

- clean semantic separation
- failed actions remain auditable without affecting locking
- one action can emit many accepted changes
- per-aggregate sequences and hashes live in the right place

Weaknesses:

- more moving parts than a single table
- transaction boundaries must be carefully designed

This is the strongest fit for the user's framing.

### Option C: split ledger plus projection/head helpers

This extends Option B with explicit infrastructure tables:

- current projection tables such as `chapters`
- an `aggregate_heads` helper keyed by `(aggregate_type, aggregate_id)`
  with latest `aggregate_seq`, `head_hash`, and latest change ID

Strengths:

- cheap GET/list reads
- cheap concurrency validation
- no need to scan the full change stream for ordinary requests

Weaknesses:

- another consistency surface to maintain
- projection rebuild tooling becomes mandatory, not optional

For this project, Option C is the practical end state even if the
conceptual model is Option B. Without projections or a head helper, the
append-only design will be operationally clumsy.

## 4. Optimistic locking via activity hash / ETag

The cleanest migration path is to stop treating optimistic locking as an
entity-body field and treat it as an HTTP validator.

Two candidate validators exist:

### Sequence-only validator

Use the aggregate's current accepted sequence number as the validator.

Pros:

- cheap
- easy to reason about
- no hash computation

Cons:

- leaks ordering directly unless wrapped opaquely
- does not help detect projection corruption on its own

### State-hash validator

Use an opaque hash as the validator.

There are two variants:

- hash of canonical projected state
- hash-chain head derived from prior head hash plus the accepted change

Pros:

- opaque to clients
- naturally fits `ETag`
- can unify concurrency validation with append-only history

Cons:

- requires canonical serialization rules
- recomputing from projected state can be expensive if done naively

The strongest option here is a per-aggregate head hash carried by the
accepted state-change stream, with the API exposing only the opaque head
value as the `ETag`. That keeps hashes out of business rows while still
letting the activity mechanism own concurrency.

Operationally:

- GET returns the current projection plus `ETag`
- mutation requests send `If-Match`
- the server compares `If-Match` with the current aggregate head
- mismatch means the mutation is stale and must fail before a new state
  change is appended

If the API adopts `If-Match`, the most standards-aligned stale-write
status is `412 Precondition Failed`, not `409 Conflict`. `409` is still
common in body-version APIs, but once the contract becomes HTTP
preconditions, `412` is the cleaner fit.

One important semantic rule follows from the action/state-change split:

- rejected or failed actions do not advance the `ETag`
- only accepted state changes do

That preserves the meaning of "the resource changed" instead of "someone
tried to change it."

## 5. Audit trail, actor attribution, and reconstruction

This model can satisfy auditability without polluting business rows.

Actor attribution belongs first on the action record:

- user vs system actor kind
- Discord user ID or service identity
- request surface such as API route, slash command, or background job
- safe logical request parameters
- correlation/request IDs

The resulting state changes link back to that action ID. That gives a
clean chain:

`actor -> action -> accepted state changes -> current projection`

For reconstruction:

- the canonical historical record is the ordered
  `activity_state_changes` stream for an aggregate
- projections are derived artifacts
- full rebuild is possible by replaying accepted state changes in order

This is stronger than treating logs as history. Logs are operational
telemetry. They are lossy, retention-bound, formatter-dependent, and not
a reliable source of business truth. Durable application audit history
must remain in database rows designed for that purpose.

The main design choice still open at proposal time is reconstruction
granularity:

- coarse change events such as `chapter_updated` with a field diff
- fine-grained events such as `chapter_name_changed`,
  `chapter_status_changed`, `chapter_discord_role_linked`

That is a proposal-phase scope decision, not a research blocker. The
important research conclusion is that the stream should reconstruct
state from accepted facts, not from mutable business rows plus logs.

## 6. Query, indexing, and operational tradeoffs

An append-only model changes the hot queries.

You will need efficient access to:

- latest head for one aggregate
- full accepted history for one aggregate
- actions by actor and time range
- accepted changes caused by one action
- current lists of chapters or activity rows without replaying history

That implies at least:

- an index on `(aggregate_type, aggregate_id, aggregate_seq DESC)` for
  state changes
- an index on `action_id` in the state-change table
- an index on `(aggregate_type, aggregate_id, recorded_at DESC)` for
  action lookups
- actor/time indexes for audit queries

PostgreSQL partial and expression indexes are relevant if the proposal
uses helper projections such as "current unsuperseded activity rows" or
canonicalized lookup keys. The earlier `activity_log ... WHERE
superseded_at IS NULL` pattern is the right kind of shape for a
projection or current-view helper even if the source of truth moves to
append-only state changes.

Operationally, the biggest tradeoffs are:

- append-only tables grow forever, so retention assumptions affect
  vacuum, index size, and backup cost
- per-aggregate ordering needs a serialization point
- projections must update transactionally with accepted state changes or
  be asynchronously repairable with a deterministic rebuild path
- investigation gets better historically but more complex mechanically

For Humility's likely scale, this is still reasonable. The main mistake
would be adopting the ledger without adopting projections and rebuild
tooling.

## 7. Migration impact on the existing chapters API

The current chapters slice is explicitly row-versioned. Moving it to an
activity-derived model is a contract break, not an internal refactor.

The impact is:

1. `version` leaves `ChapterRead` and `ChapterUpdate`.
2. Chapter mutations stop taking a body `version`.
3. Chapter reads return an `ETag` derived from the chapter aggregate
   head.
4. Chapter mutations require `If-Match`.
5. Stale updates likely move from `409 Conflict` to `412 Precondition
   Failed` if the API fully adopts HTTP preconditions.

There is a second likely impact if the user's cleanliness rule applies
to API contracts as well as storage rows:

- `created_at` may also leave the canonical business DTO and become
  derived history metadata rather than part of the chapter row itself

That needs an explicit proposal decision. The current repo treats
`created_at` as a server-managed read field, but the prompt groups
timestamps with the metadata that should not live on business rows.

From a migration strategy perspective:

- this should be a clean break
- do not support both `version` and `If-Match`
- update contracts, endpoints, tests, and clients in one pass

That matches the repo's no-backwards-compatibility rule.

The existing chapter repository also shows an important architectural
shift. Today it mutates the canonical row directly. Under the
activity-derived design, the write path becomes:

1. validate `If-Match` against the aggregate head
2. append an accepted action
3. append one or more accepted state changes
4. update the chapter projection
5. return the projection plus the new `ETag`

That is materially more complex than the in-memory `replace(...,
version=current.version + 1)` model now in `services/api/app/repositories/chapters.py`,
but it is aligned with the user's stated goal of one append-only
mechanism for locking, history, and audit.

## Sources

- Local code and planning artifacts:
  - `services/api/app/contracts/base.py`
  - `services/api/app/contracts/chapters.py`
  - `services/api/app/services/chapters.py`
  - `services/api/app/repositories/chapters.py`
  - `services/api/tests/test_chapters.py`
  - `proposals/01-v1-scope.rev1.md`
  - `proposals/01-v1-scope.md`
  - `plans/research/database-stack.md`
- HTTP semantics for validators and preconditions:
  - RFC 9110, HTTP Semantics: https://www.rfc-editor.org/rfc/rfc9110.html
- PostgreSQL indexing references relevant to current/projection and
  derived-key query patterns:
  - Partial indexes: https://www.postgresql.org/docs/current/indexes-partial.html
  - Indexes on expressions: https://www.postgresql.org/docs/current/indexes-expressional.html
