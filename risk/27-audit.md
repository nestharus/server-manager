# Risk Assessment: Audit Risk — Chapter Endpoint Stubs

Date: 2026-04-13

Proposal: `proposals/27-chapter-endpoints.md`

## Verdict: LOW

The proposal is narrow, internally consistent, and safe. All five
evaluation criteria pass. Two informational findings are recorded
below; neither requires proposal revision before implementation.

## Findings

### F1. Archive endpoint omits version input for optimistic locking — Severity: LOW

`POST /api/v1/chapters/{chapter_id}/archive` accepts no request body.
When implemented, archiving will mutate entity state (status → archived)
and increment the version. Without a submitted version, the service
layer cannot enforce optimistic locking on this transition.

This is explicitly anti-scoped: the proposal states "optimistic-lock
conflict handling beyond the ChapterUpdate request shape" is out of
scope. The deferral is reasonable because:

- The stub does nothing — no data mutation occurs.
- Archive is closer to an idempotent command than a general mutation.
- The service layer can decide whether archive requires a version
  check (via query parameter, request body, or business-rule choice
  that archiving an already-archived chapter is a no-op).

This finding is informational. When the service layer is implemented,
the archive endpoint's concurrency semantics should be decided
explicitly rather than left as an implicit gap.

### F2. 501 Not Implemented is semantically broader than "stub" — Severity: LOW

RFC 9110 §15.6.2 defines 501 as the server not supporting the
functionality required to fulfill the request, specifically when the
server does not recognize the request method. Using 501 for
application-level "not yet built" stubs is common practice but
stretches the RFC's narrow definition.

The research acknowledges this tension. The risk is negligible because:

- The 501 status is temporary and will be replaced by real
  implementations.
- No clients depend on the stubs in production.
- The proposal's purpose is to establish the OpenAPI surface, not to
  serve traffic.
- Alternative stub statuses (503, custom 5xx) would introduce their
  own semantic mismatches without meaningful benefit.

No action required. The 501 approach is the pragmatic choice for this
phase.

## Criteria Assessment

### 1. Endpoint signatures vs contract models

All five route signatures correctly bind to the existing contract
models:

| Route | Request body | Response | Contract match |
|-------|-------------|----------|----------------|
| `POST /api/v1/chapters` | `ChapterCreate` | `ChapterRead` | `ChapterCreate` has `name` + `slug`, no `version` (correct per `VersionedMixin` docstring: "Exclude from create contracts") |
| `GET /api/v1/chapters` | — | `list[ChapterRead]` | Correct collection response |
| `GET /api/v1/chapters/{chapter_id}` | — | `ChapterRead` | Correct single-entity response |
| `PATCH /api/v1/chapters/{chapter_id}` | `ChapterUpdate` | `ChapterRead` | `ChapterUpdate` carries optional mutable fields + required `version` from `VersionedMixin` |
| `POST /api/v1/chapters/{chapter_id}/archive` | — | `ChapterRead` | Archive is a command returning the resulting state |

- `chapter_id` is typed `int`, matching `ChapterRead.id: int`.
- Return type annotations are used directly in function signatures,
  consistent with the `health.py` pattern and sufficient for OpenAPI
  generation.
- No contract model is misused or mismatched. **Pass.**

### 2. Status codes per HTTP semantics

- `POST` create → `201 Created`: correct per RFC 9110 §9.3.3 and
  FastAPI convention for resource creation.
- `GET` list → `200 OK`: correct.
- `GET` single → `200 OK`: correct.
- `PATCH` update → `200 OK`: correct for an update that returns a
  representation (RFC 5789 §2.1 allows 200 or 204; 200 is appropriate
  since the response includes the updated `ChapterRead`).
- `POST` archive → `200 OK`: correct for an action endpoint returning
  the resulting resource state.
- Stub `501`: see F2; acceptable for this phase. **Pass.**

### 3. 501 stub safety (no data leakage, no side effects)

Each stub handler consists of a single statement:
`raise HTTPException(status_code=HTTPStatus.NOT_IMPLEMENTED)`.

- **No side effects**: no database access, no service calls, no state
  mutation, no Discord API interaction, no file I/O.
- **No data leakage**: FastAPI's default error response is
  `{"detail": "Not Implemented"}`. No custom detail strings, no
  internal state, no stack traces.
- **No imports beyond contracts**: the module imports only `APIRouter`,
  `HTTPException`, `HTTPStatus`, and the three contract models. No
  service, repository, or infrastructure modules are pulled in.
- **Pydantic validation runs before the handler**: `POST` and `PATCH`
  routes will validate request bodies and return 422 on malformed
  input, which is standard FastAPI behavior and does not leak data.

**Pass.**

### 4. Archive route avoids destructive semantics

- Modeled as `POST /api/v1/chapters/{chapter_id}/archive`, not
  `DELETE`. The HTTP method and path clearly communicate a state
  transition, not resource removal.
- Returns `ChapterRead`, confirming the resource remains accessible
  after archival.
- No `DELETE` route is defined anywhere in the proposal, correctly
  avoiding hard-delete semantics.
- `ChapterStatus.archived` already exists in the contract enum,
  establishing that archive is a lifecycle state, not destruction.
- The action is implicitly reversible: status could be changed back
  to `active` via `PATCH` if future business rules permit.

**Pass.**

### 5. Security concerns with the stub approach

- **No auth enforcement**: authentication and authorization are
  explicitly anti-scoped. This is correct for stubs — enforcing auth
  on endpoints that always return 501 would add complexity without
  value. Auth will be added when real handlers are implemented.
- **No injection vectors**: `chapter_id` is typed `int` (FastAPI
  rejects non-integer path values with 422). Request bodies are
  validated by Pydantic models with explicit constraints (slug regex,
  name length bounds, version non-negative).
- **OpenAPI surface exposure**: the stubs advertise the intended API
  shape in generated docs. This is the explicit purpose of the
  proposal and is not a security concern — the API surface will be
  public when implemented.
- **No CORS, rate limiting, or middleware concerns**: these are
  cross-cutting concerns handled at the application level, not per
  endpoint module.
- **Router pattern matches existing baseline**: follows `health.py`
  conventions exactly, inheriting whatever security middleware the
  application factory applies.

**Pass.**

## Recommendations

None required. Both findings are informational and correctly deferred
to later implementation phases. The proposal may proceed as designed.
