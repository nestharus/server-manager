# Hookpoint Research: Activity/Audit Model Implementation

## Purpose

Documents every existing code path, contract, test fixture, and
dependency injection seam that the Activity/Audit Model implementation
must modify, replace, or extend. Also documents new code paths that do
not exist yet but are required by the proposal. This file is the map
that implementation agents use to know exactly where to cut.

All file paths are relative to the repository root.

---

## Section 1 — Existing code that will be modified

### Hookpoint 1.1 — VersionedMixin removal from contracts

**File**: `services/api/app/contracts/base.py` (lines 1–10)

**Current state**: `VersionedMixin` is a Pydantic `BaseModel` subclass
that adds a required `version: int = Field(ge=0)` field. It is the sole
content of this module.

**What changes**: The `VersionedMixin` class is removed entirely. The
proposal explicitly states that `version` leaves both `ChapterRead` and
`ChapterUpdate` (proposal §7). The `VersionedMixin` mixin has no other
consumers beyond chapters, so removing the class does not create
orphaned dependencies.

**Downstream dependents**:
- `services/api/app/contracts/__init__.py` — re-exports
  `VersionedMixin` via `__all__`; this re-export must be removed.
- `services/api/app/contracts/chapters.py` — imports `VersionedMixin`
  and uses it as a base class for `ChapterRead` (line 20) and
  `ChapterUpdate` (line 31); both inheritance relationships must be
  removed and the `version` field must not appear on either contract.
- `services/api/tests/test_contracts_base.py` — the entire test file
  exercises `VersionedMixin` schema shape, subclassing behavior, and
  optimistic locking via a minimal in-process FastAPI app. Every test
  in this file must be rewritten or removed.
- `services/api/tests/test_contracts_chapters.py` — multiple tests
  assert `VersionedMixin` inheritance (`test_chapter_read_inherits_from_versioned_mixin`,
  `test_chapter_update_inherits_from_versioned_mixin`), require
  `version` as a field (`_valid_chapter_read_payload`, all optimistic
  locking tests using `_ChapterStore`). These must be rewritten to
  exercise the new ETag/If-Match contract instead.

**Risk if missed**: Any code that still references `VersionedMixin` or
passes `version` in a chapter DTO will fail at import time or raise
`ValidationError` after the removal.

### Hookpoint 1.2 — ChapterRead contract restructure

**File**: `services/api/app/contracts/chapters.py` (lines 20–28)

**Current state**: `ChapterRead` inherits `VersionedMixin` and exposes:
`id`, `name`, `slug`, `status`, `discord_category_id`,
`discord_officer_role_id`, `discord_member_role_id`, `created_at`,
`version`.

**What changes**:
- `VersionedMixin` inheritance is removed.
- `version` field is removed from the response body.
- `created_at` is retained (proposal §5 explicitly keeps it as a
  business field on the projection table).
- `ChapterRead` becomes a plain `BaseModel` subclass with the remaining
  business fields.

**Interaction**: The endpoint layer must set an `ETag` response header
carrying the current aggregate head value instead of including `version`
in the JSON body. The `ChapterRead` contract itself does not carry
concurrency metadata.

### Hookpoint 1.3 — ChapterUpdate contract restructure

**File**: `services/api/app/contracts/chapters.py` (lines 31–41)

**Current state**: `ChapterUpdate` inherits `VersionedMixin`, requiring
a `version` field alongside optional business fields.

**What changes**:
- `VersionedMixin` inheritance is removed.
- `version` field is removed from the request body.
- Concurrency is enforced via the `If-Match` request header, not via
  a body field.
- `ChapterUpdate` becomes a plain `BaseModel` with only optional
  business fields (`name`, `slug`, `status`, Discord IDs).

**Interaction**: The endpoint layer must extract the `If-Match` header
and pass the expected head value to the service layer. The contract
model itself no longer carries concurrency information.

### Hookpoint 1.4 — ChapterRecord dataclass in repository

**File**: `services/api/app/repositories/chapters.py` (lines 27–38)

**Current state**: `ChapterRecord` is a frozen dataclass with `version`
as a field. It is the internal domain record used between the repository
and service layers.

**What changes**:
- `version` field is removed from `ChapterRecord`. The projection row
  no longer carries concurrency metadata.
- `ChapterRecord` retains `created_at` as a business field.
- The record becomes a pure current-state projection: `id`, `name`,
  `slug`, `status`, Discord IDs, `created_at`.

**Downstream dependents**:
- `services/api/app/services/chapters.py` — `_to_read()` (line 37)
  maps `chapter.version` to `ChapterRead.version`; this mapping must
  be removed.
- `services/api/app/services/chapters.py` — `update_chapter()` (line
  25) calls `chapter.model_dump(exclude={"version"}, ...)` and passes
  `expected_version=chapter.version`; both references must change.

### Hookpoint 1.5 — ChapterRepository protocol and InMemoryChapterRepository

**File**: `services/api/app/repositories/chapters.py`

**Current state**:
- `ChapterRepository` protocol (lines 40–55) defines `create`, `list`,
  `get`, `update` (with `expected_version`), and `archive`.
- `InMemoryChapterRepository` (lines 58–121) implements the protocol
  with in-memory dict storage, version-based optimistic locking
  (`_assert_version`), and `replace(current, version=current.version+1)`
  mutations.
- `ChapterVersionConflictError` (lines 16–24) carries `expected_version`
  and `actual_version` for 409 responses.

**What changes**:
- The `update` method signature changes: `expected_version: int` is
  replaced by `expected_head` (or equivalent) carrying the opaque
  aggregate head value.
- `ChapterVersionConflictError` is replaced or renamed to reflect
  ETag/precondition semantics (e.g., `StalePreconditionError`). The
  error should carry enough context for the endpoint layer to return
  412.
- `InMemoryChapterRepository` must be rewritten to implement the new
  write path: append action, append state change, advance aggregate
  head, update projection. The `_assert_version` method is replaced by
  head comparison logic.
- `archive` must also become a preconditioned mutation (proposal §7
  states archive should not remain an unguarded write).

**Interaction with new code**: The repository layer will need to
interact with new in-memory stores for `activity_actions`,
`activity_state_changes`, and `aggregate_heads` (see Section 2).

### Hookpoint 1.6 — ChapterService orchestration

**File**: `services/api/app/services/chapters.py` (lines 1–48)

**Current state**:
- `update_chapter()` (line 24) extracts `version` from the
  `ChapterUpdate` contract via `chapter.version` and passes it as
  `expected_version` to the repository.
- `archive_chapter()` (line 33) delegates to `repository.archive()`
  with no version check.
- `_to_read()` (line 37) maps all `ChapterRecord` fields including
  `version` to `ChapterRead`.

**What changes**:
- `update_chapter()` receives the expected head value (from the
  `If-Match` header, passed by the endpoint) as a separate parameter
  instead of extracting it from the contract body.
- `archive_chapter()` receives the expected head value and passes it
  through to the repository (proposal §7: archive becomes a
  preconditioned mutation).
- `_to_read()` stops mapping `version`.
- The service must return both the `ChapterRead` DTO and the new
  aggregate head value so the endpoint can set the `ETag` header. This
  could be a tuple return, a wrapper dataclass, or the head could be
  attached as context alongside the DTO.
- Per the proposal addendum A1, the service layer should own a single
  `mutate_entity()` primitive that performs the full accepted-write
  sequence in one transaction. For the in-memory implementation this
  means the service coordinates action-insert, state-change-insert,
  head-advance, and projection-update in a single synchronous call.

### Hookpoint 1.7 — Endpoint error handling and HTTP status codes

**File**: `services/api/app/api/v1/endpoints/chapters.py` (lines 1–69)

**Current state**:
- `_raise_for_chapter_error()` (line 17) maps
  `ChapterVersionConflictError` to `409 Conflict`.
- `update_chapter()` (line 49) receives `ChapterUpdate` from the
  request body (which includes `version`).
- `archive_chapter()` (line 60) takes no precondition.

**What changes**:
- Stale-write error mapping changes from `409 Conflict` to
  `412 Precondition Failed` (proposal §4, §7).
- `update_chapter()` must extract the `If-Match` header from the
  request and pass the expected head value to the service.
- `archive_chapter()` must also extract `If-Match` and become a
  preconditioned mutation.
- All read endpoints (`get_chapter`, `list_chapters`) must set an
  `ETag` response header on the returned data. For single-resource
  reads, the ETag is the aggregate head. For list reads, the ETag
  strategy needs definition (per-item headers are not standard; the
  proposal focuses on single-aggregate concurrency).
- `create_chapter()` must return an `ETag` header for the newly created
  aggregate head (seq 1 after the initial state change).
- Missing `If-Match` on mutation endpoints should return
  `428 Precondition Required` (standard HTTP semantics for missing
  precondition headers on endpoints that require them).

### Hookpoint 1.8 — Dependency injection in factory

**File**: `services/api/app/core/factory.py` (lines 17–39)

**Current state**: `create_app()` accepts an optional
`chapter_repository` parameter, defaults to
`InMemoryChapterRepository()`, and wires it into `ChapterService` via
`app.state.chapter_service`.

**What changes**: The factory must wire up the new activity/audit
infrastructure alongside the chapter repository. For the in-memory
implementation, this means creating the in-memory activity stores and
passing them to the repository or service layer. The factory signature
may gain additional parameters for injecting activity stores in tests.

**File**: `services/api/app/core/dependencies.py` (lines 1–9)

**Current state**: `get_chapter_service()` extracts `ChapterService`
from `request.app.state.chapter_service`.

**What changes**: If middleware is used for ETag/If-Match parsing, the
dependency layer may need new extractors. Alternatively, the endpoint
functions themselves can extract headers from the `Request` object
directly (FastAPI supports `Header()` dependencies).

---

## Section 2 — New code paths needed

### Hookpoint 2.1 — activity_actions in-memory store

**New module**: A storage layer for `activity_actions` records.

**Record shape** (from proposal §5 and research §3):
- `id` (auto-incrementing or UUID)
- `action_type` (e.g., `chapter.create`, `chapter.update`,
  `chapter.archive`)
- `aggregate_type` (e.g., `chapter`)
- `aggregate_id` (the chapter ID)
- `actor_kind` (e.g., `user`, `system`)
- `actor_id`
- `request_surface` (e.g., `api:/api/v1/chapters/{id}`)
- `request_json` (redacted logical request payload)
- `status` (`accepted`, `rejected`, `failed`, `noop`)
- `reason_text` (for rejected/failed)
- `recorded_at` (timestamp)

**Behavior**: Append-only. No updates, no deletes. Failed and rejected
actions are recorded but do not advance concurrency. Query patterns
include lookup by aggregate, by actor, and by status.

**Location decision**: Could live in a new
`services/api/app/repositories/activity.py` module or as part of a
broader `services/api/app/repositories/activity/` package. The in-memory
implementation follows the same pattern as
`InMemoryChapterRepository` — a dict-based store with auto-incrementing
IDs.

### Hookpoint 2.2 — activity_state_changes in-memory store

**New module**: A storage layer for `activity_state_changes` records.

**Record shape** (from proposal §5 and research §3):
- `id` (auto-incrementing or UUID)
- `action_id` (FK to `activity_actions.id`)
- `aggregate_type` (e.g., `chapter`)
- `aggregate_id`
- `aggregate_seq` (monotonic per-aggregate sequence number)
- `change_type` (e.g., `chapter.created`, `chapter.updated`,
  `chapter.archived`)
- `payload_json` (the canonical accepted fact — full accepted state)
- `diff_json` (field-level business diff derived from payload_json)
- `recorded_at` (timestamp)

**Behavior**: Append-only. The `aggregate_seq` is the monotonic sequence
number used for Phase 1 concurrency (proposal §4). Each accepted state
change advances the aggregate's sequence. The sequence is scoped to
`(aggregate_type, aggregate_id)`.

### Hookpoint 2.3 — aggregate_heads in-memory store

**New module**: A current-state helper for fast concurrency checks.

**Record shape** (from proposal §3):
- `aggregate_type` (e.g., `chapter`)
- `aggregate_id`
- `current_seq` (latest accepted sequence number)
- `latest_change_id` (FK to the most recent `activity_state_changes.id`)

**Behavior**: Upserted on each accepted state change. Keyed by
`(aggregate_type, aggregate_id)`. This is the lookup target for
ETag generation and If-Match validation. For a new aggregate (e.g.,
newly created chapter), the head is initialized with `current_seq=1`
after the first state change.

**ETag derivation**: The ETag value is derived from `current_seq`. The
proposal states the value is opaque to clients but is sequence-based
in Phase 1 (proposal §4). A simple encoding such as `str(current_seq)`
or a quoted ETag like `'"seq-{current_seq}"'` is sufficient.

### Hookpoint 2.4 — New contracts for activity/audit DTOs

**New file(s)**: Pydantic models for activity and state-change records
if audit/history endpoints are exposed.

**Note**: The proposal states that audit UI is out of scope (§10), but
the contracts are needed at minimum for internal typing between the
repository and service layers. These may be dataclasses rather than
Pydantic models if they are internal-only.

**Minimum new contracts**:
- `ActionRecord` — dataclass for the service/repository boundary
- `StateChangeRecord` — dataclass for the service/repository boundary
- `AggregateHead` — dataclass or named tuple for head lookups

### Hookpoint 2.5 — ETag/If-Match middleware or header handling

**New code**: Logic for setting `ETag` on responses and extracting
`If-Match` from requests.

**Two implementation approaches**:

1. **Per-endpoint handling**: Each endpoint function extracts `If-Match`
   via FastAPI's `Header()` dependency and sets `ETag` on the `Response`
   object. This is simpler and more explicit.

2. **Middleware**: A FastAPI middleware that intercepts responses from
   chapter endpoints and sets `ETag` headers based on aggregate head
   lookups. This centralizes the concern but adds complexity.

**Recommendation from proposal**: The proposal does not prescribe
middleware vs per-endpoint. For the proof-of-concept (chapters only),
per-endpoint handling is sufficient. A middleware pattern can be
introduced when a second aggregate adopts the model.

**Missing-header behavior**: When a mutation endpoint receives no
`If-Match` header, it should return `428 Precondition Required`
(RFC 6585). This is a new HTTP status code not currently used in
the codebase.

### Hookpoint 2.6 — Projection-update function (code-sharing contract)

**New code**: A single function that takes an accepted state change
and applies it to the projection table (proposal §8, addendum A3).

**Contract**: The live write path and rebuild both call this same
function. For the in-memory implementation, this function takes a
state-change record and updates the in-memory chapter dict.

**Location**: Likely in the service or repository layer. The proposal
addendum A1 places the full write sequence in a `mutate_entity()`
service-layer primitive. The projection-update function is one step
within that primitive.

---

## Section 3 — Interaction points with existing chapters CRUD flow

### Hookpoint 3.1 — Create chapter flow

**Current flow**:
1. Endpoint receives `ChapterCreate` body
2. Service calls `repository.create(name=..., slug=...)`
3. Repository creates `ChapterRecord` with `version=0`
4. Service maps to `ChapterRead` (includes `version=0`)
5. Endpoint returns 201 with JSON body

**New flow**:
1. Endpoint receives `ChapterCreate` body (no `If-Match` needed for
   creates — there is no prior state to conflict with)
2. Service calls `mutate_entity()` / write-path primitive:
   a. Append `activity_actions` row (action_type=`chapter.create`,
      status=`accepted`)
   b. Append `activity_state_changes` row (change_type=`chapter.created`,
      aggregate_seq=1, payload_json=full chapter state)
   c. Insert `aggregate_heads` row (current_seq=1)
   d. Insert projection row (chapter record without `version`)
3. Service returns `ChapterRead` + new head value
4. Endpoint returns 201 with JSON body + `ETag` header

**Key difference**: The create flow does not require `If-Match` because
there is no existing aggregate to conflict with. The initial
`aggregate_seq` is 1. The `ETag` on the response allows the client to
immediately perform subsequent mutations.

### Hookpoint 3.2 — Read/Get chapter flow

**Current flow**:
1. Endpoint receives chapter_id path parameter
2. Service calls `repository.get(chapter_id)`
3. Service maps to `ChapterRead` (includes `version`)
4. Endpoint returns 200 with JSON body

**New flow**:
1. Endpoint receives chapter_id path parameter
2. Service calls `repository.get(chapter_id)` for the projection
3. Service looks up `aggregate_heads` for the current head
4. Service returns `ChapterRead` (no `version`) + head value
5. Endpoint returns 200 with JSON body + `ETag` header

**Key difference**: The response body no longer contains `version`. The
concurrency token is in the `ETag` header only.

### Hookpoint 3.3 — List chapters flow

**Current flow**:
1. Endpoint calls `service.list_chapters()`
2. Service returns `list[ChapterRead]` (each with `version`)
3. Endpoint returns 200 with JSON array

**New flow**:
1. Endpoint calls `service.list_chapters()`
2. Service returns `list[ChapterRead]` (no `version` on any item)
3. Endpoint returns 200 with JSON array

**ETag consideration**: The proposal scopes optimistic locking to
single-aggregate operations (proposal §4). For list endpoints, the
ETag is not required for concurrency purposes. Individual item ETags
could be returned as fields in the list items if needed for client
convenience, but the proposal does not require this. Clients that want
to mutate a specific chapter should GET it first to obtain its ETag.

### Hookpoint 3.4 — Update chapter flow

**Current flow**:
1. Endpoint receives `ChapterUpdate` body (includes `version`)
2. Service extracts `version` from body, calls
   `repository.update(chapter_id, expected_version=..., updates=...)`
3. Repository compares `expected_version` to `current.version`
4. On mismatch: `ChapterVersionConflictError` → 409 Conflict
5. On match: `replace(current, **updates, version=current.version+1)`
6. Service maps to `ChapterRead`, endpoint returns 200

**New flow**:
1. Endpoint extracts `If-Match` header (missing → 428)
2. Endpoint receives `ChapterUpdate` body (no `version`)
3. Service calls `mutate_entity()` with expected_head from If-Match:
   a. Read current aggregate head from `aggregate_heads`
   b. Compare If-Match value to current head
   c. On mismatch: raise precondition error → 412
   d. Append `activity_actions` row (action_type=`chapter.update`,
      status=`accepted`)
   e. Compute diff between current projection and new state
   f. Append `activity_state_changes` row (change_type=`chapter.updated`,
      aggregate_seq=current_seq+1, payload_json=new state, diff_json=diff)
   g. Update `aggregate_heads` (current_seq=current_seq+1)
   h. Update projection row
4. Service returns `ChapterRead` + new head value
5. Endpoint returns 200 with JSON body + `ETag` header

**Key differences**:
- Concurrency token moves from body to header
- Error code changes from 409 to 412
- Write path goes from single row mutation to multi-record append
- Diff is computed and stored

### Hookpoint 3.5 — Archive chapter flow

**Current flow**:
1. Endpoint receives chapter_id, no precondition check
2. Service calls `repository.archive(chapter_id)`
3. Repository sets `status=archived`, `version=current.version+1`
4. Service maps to `ChapterRead`, endpoint returns 200

**New flow**:
1. Endpoint extracts `If-Match` header (missing → 428)
2. Service calls `mutate_entity()` with expected_head:
   a–h. Same write-path steps as update (hookpoint 3.4)
   with action_type=`chapter.archive`,
   change_type=`chapter.archived`, status set to `archived`
3. Service returns `ChapterRead` + new head value
4. Endpoint returns 200 with JSON body + `ETag` header

**Key difference**: Archive is no longer an unguarded write. It requires
`If-Match` just like update (proposal §7).

### Hookpoint 3.6 — Error mapping changes

**File**: `services/api/app/api/v1/endpoints/chapters.py`, function
`_raise_for_chapter_error()` (line 17)

**Current mapping**:
- `ChapterNotFoundError` → 404 Not Found
- `ChapterVersionConflictError` → 409 Conflict

**New mapping**:
- `ChapterNotFoundError` → 404 Not Found (unchanged)
- Stale precondition error → 412 Precondition Failed (replaces 409)
- Missing `If-Match` on mutation → 428 Precondition Required (new)

---

## Section 4 — Test infrastructure hookpoints

### Hookpoint 4.1 — test_contracts_base.py rewrite

**File**: `services/api/tests/test_contracts_base.py` (62 lines total)

**Current patterns**:
- Schema/field-shape tests for `VersionedMixin` (lines 1–82)
- A minimal in-process FastAPI app (`_build_versioned_entity_app`)
  with `_ItemCreate`, `_ItemRead`, `_ItemUpdate` contracts using
  `VersionedMixin` (lines 96–139)
- Async `httpx.AsyncClient` tests exercising version-based optimistic
  locking (lines 148–215)

**What changes**: The entire file must be rewritten to test the new
ETag/If-Match concurrency contract instead of body-version locking.
The replacement tests should:
- Verify that the new concurrency primitive works via HTTP headers
- Verify that `ETag` is present on read responses
- Verify that `If-Match` is required on mutations
- Verify that stale `If-Match` returns 412
- Verify that missing `If-Match` returns 428

**Pattern to follow**: The existing async test pattern using
`httpx.AsyncClient` + `httpx.ASGITransport` is the established test
fixture pattern for HTTP-level contract tests.

### Hookpoint 4.2 — test_contracts_chapters.py rewrite

**File**: `services/api/tests/test_contracts_chapters.py` (283 lines)

**Tests that must change**:
- `test_chapter_read_inherits_from_versioned_mixin` (line 97) —
  remove; `ChapterRead` no longer inherits `VersionedMixin`
- `test_chapter_update_inherits_from_versioned_mixin` (line 136) —
  remove
- `_valid_chapter_read_payload()` (line 29) — remove `version` key
- `test_chapter_read_requires_all_fields` parametrize list (line 103)
  — remove `"version"` from the list
- `test_chapter_update_requires_version_and_all_other_fields_are_optional`
  (line 142) — rewrite; `ChapterUpdate` no longer requires `version`,
  and all fields become optional. The test should verify that an empty
  update body is valid (or define what the minimum valid update is).
- `_ChapterStore` class (line 187) — rewrite to use ETag-based locking
  instead of body version
- All `test_optimistic_locking_*` tests (lines 239–283) — rewrite to
  exercise ETag/If-Match semantics

**Tests that remain unchanged**:
- `ChapterStatus` enum tests (lines 43–56)
- `ChapterCreate` validation tests (lines 59–94) — create has no
  version or ETag interaction
- `ChapterUpdate` slug/name validation tests (lines 159–173)

### Hookpoint 4.3 — test_chapters.py (integration tests) rewrite

**File**: `services/api/tests/test_chapters.py` (296 lines)

**Helper functions that change**:
- `_chapter_update_payload(version=0, ...)` (line 19) — remove
  `version` parameter; updates are pure business-field payloads
- `_assert_chapter_read(...)` (line 30) — remove `expected_version`
  parameter and `version` assertion (line 43)

**Tests that must change**:
- `test_create_chapter_returns_created_with_server_managed_fields`
  (line 58) — remove `expected_version=0`; add assertion that
  response has `ETag` header
- `test_list_chapters_returns_created_chapters_with_read_shape`
  (line 96) — remove `expected_version=0`
- `test_update_chapter_with_current_version_succeeds_and_increments_version`
  (line 138) — rewrite to send `If-Match` header instead of body
  version; assert new `ETag` in response instead of `version=1`
- `test_update_chapter_changes_are_visible_on_subsequent_get` (line
  157) — send `If-Match` header; verify `ETag` changes
- `test_update_chapter_can_change_status_and_discord_ids` (line 174) —
  send `If-Match`; remove `version` assertion
- `test_update_chapter_with_stale_version_returns_conflict` (line 196)
  — rewrite to send stale `If-Match`; assert 412 instead of 409
- `test_update_chapter_requires_version_field` (line 211) — rewrite
  to test missing `If-Match` returns 428 instead of testing missing
  body version returns 422
- `test_archive_chapter_marks_chapter_archived_in_response` (line 250)
  — send `If-Match`; remove `expected_version=1`
- `test_archive_chapter_preserves_id_and_created_timestamp` (line 264)
  — send `If-Match`
- `test_archived_chapter_remains_readable_via_get` (line 274) — send
  `If-Match` on archive call
- `test_archived_chapter_remains_listable_and_is_not_hard_deleted`
  (line 284) — send `If-Match` on archive call

**Tests that remain unchanged**:
- `test_create_chapter_assigns_distinct_server_ids` (line 70)
- `test_create_chapter_rejects_empty_name_at_http_boundary` (line 77)
- `test_create_chapter_rejects_invalid_slug_at_http_boundary` (line 83)
- `test_list_chapters_returns_empty_list_when_no_chapters_exist` (line
  89)
- `test_update_chapter_rejects_invalid_slug_at_http_boundary` (line
  221) — still valid, just needs `If-Match` header added
- `test_update_chapter_rejects_empty_name_at_http_boundary` (line 230)
  — still valid, just needs `If-Match` header added
- `test_update_chapter_returns_404_for_unknown_chapter` (line 241) —
  still valid, just needs `If-Match` header added
- `test_get_chapter_by_id_returns_404_for_unknown_chapter` (line 132)
- `test_archive_unknown_chapter_returns_404` (line 295)

**New test patterns needed**:
- Helper to extract `ETag` from response headers
- Helper to send `If-Match` header on requests
- Test that create returns `ETag` header
- Test that get returns `ETag` header
- Test that update with valid `If-Match` returns new `ETag`
- Test that update with stale `If-Match` returns 412
- Test that update without `If-Match` returns 428
- Test that archive requires `If-Match`
- Test that archive with stale `If-Match` returns 412
- Test that sequential mutations advance the ETag monotonically

### Hookpoint 4.4 — test_endpoints_chapters_stubs.py

**File**: `services/api/tests/test_endpoints_chapters_stubs.py`
(106 lines)

**Current state**: Tests that chapter stub routes exist and return
`NOT_IMPLEMENTED`. These tests were relevant during the stub phase and
currently pass with the implemented endpoints returning real responses.

**What changes**: The parametrized test data on line 69 sends
`{"version": 0}` as the PATCH body. This must be updated to omit
`version`. The test may also need to send an `If-Match` header for
mutation routes to avoid getting 428 instead of the expected status.

**Assessment**: This file may be obsoleted by the full integration
tests in `test_chapters.py`. If kept, it needs header adjustments.

### Hookpoint 4.5 — conftest.py fixture patterns

**File**: `services/api/tests/conftest.py` (53 lines)

**Current patterns**:
- `monkeypatch_session` for environment setup (session scope)
- `required_env` / `test_settings` for `Settings` (session scope)
- `app` fixture creates `FastAPI` via `create_app()` (function scope)
- `client` fixture wraps `TestClient` (function scope)
- `async_client` fixture wraps `httpx.AsyncClient` (function scope)

**What changes**: The `app` fixture currently creates a fresh app per
test function, which gives test isolation (each test gets a clean
in-memory repository). This pattern must be preserved. If the factory
gains new parameters for activity stores, the `app` fixture must wire
them up.

**New fixtures potentially needed**:
- A fixture that creates a chapter and returns both the chapter data
  and its `ETag`, to reduce boilerplate in tests that need a
  pre-existing chapter with a known ETag for mutation tests.

### Hookpoint 4.6 — test_conftest.py verification tests

**File**: `services/api/tests/test_conftest.py` (55 lines)

**Current state**: Tests that verify the conftest fixtures work
correctly — that `test_settings` produces valid settings, that the app
fixture returns a FastAPI instance, that endpoints are reachable.

**What changes**: Line 65 sends `{"version": 0}` as the PATCH body for
the chapter endpoint reachability test. This must be updated. The test
currently expects `NOT_IMPLEMENTED` (line 78) which will change once
the endpoints are implemented with the new contract.

### Hookpoint 4.7 — test_factory.py

**File**: `services/api/tests/test_factory.py` (105 lines)

**What changes**: If `create_app()` gains new parameters for activity
stores or the service wiring changes, the factory tests must be updated
to reflect the new signature and behavior. The existing tests verify
settings injection and should remain largely stable.

---

## Summary

The Activity/Audit Model implementation touches every layer of the
chapters slice:

| Layer | Files modified | Nature of change |
|---|---|---|
| Contracts | `base.py`, `chapters.py`, `__init__.py` | Remove `VersionedMixin`, remove `version` from DTOs |
| Repository | `chapters.py` | Remove version from record, rewrite locking to use aggregate heads |
| Service | `chapters.py` | New write-path primitive, ETag return, archive gains precondition |
| Endpoints | `chapters.py` | ETag/If-Match headers, 412/428 status codes, archive precondition |
| Factory | `factory.py`, `dependencies.py` | Wire activity stores |
| Tests | 6 test files | Rewrite version-based assertions to ETag-based |

New code paths:

| Component | Purpose |
|---|---|
| Activity actions store | Append-only attempted-operation records |
| Activity state changes store | Append-only accepted-fact records |
| Aggregate heads store | Current concurrency head per aggregate |
| ETag/If-Match handling | Header extraction and response setting |
| Projection-update function | Shared between live writes and rebuild |
| New error types | `StalePreconditionError`, precondition-required handling |
