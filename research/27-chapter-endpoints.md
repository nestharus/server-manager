# Research: FastAPI Chapter Endpoint Stubs

Date: 2026-04-13

## Scope

This note documents the problem space for adding chapter CRUD endpoint
stubs to the FastAPI API service.

It is limited to:

- FastAPI router and path operation patterns relevant to chapter CRUD
- how stubbed endpoints can expose a stable HTTP surface while still
  returning "not implemented" responses
- standard CRUD HTTP shapes for a versioned entity
- optimistic locking semantics at the HTTP boundary
- archive versus delete semantics for a resource that already has an
  `archived` lifecycle state

It does not propose a final endpoint design or write implementation
code.

## Local baseline

- Chapter contracts already exist at
  [services/api/app/contracts/chapters.py](/home/nes/discord/services/api/app/contracts/chapters.py:1):
  - `ChapterCreate`
  - `ChapterRead`
  - `ChapterUpdate`
  - `ChapterStatus`
- The base optimistic-locking contract is
  [VersionedMixin](/home/nes/discord/services/api/app/contracts/base.py:1),
  which requires `version: int` with `ge=0`.
- The only current v1 endpoint is
  [health.py](/home/nes/discord/services/api/app/api/v1/endpoints/health.py:1),
  using `router = APIRouter(prefix="/api/v1/health")`.
- The v1 aggregator is
  [services/api/app/api/v1/router.py](/home/nes/discord/services/api/app/api/v1/router.py:1),
  which uses `router.include_router(health.router, tags=["health"])`.
- `AGENTS.md` defines optimistic-locking expectations at the HTTP level:
  read version `N`, update with `N`, success yields `N+1`, stale update
  returns `409 Conflict`
  ([AGENTS.md](/home/nes/discord/AGENTS.md:146)).

## Primary sources

- Local repo:
  - [services/api/app/contracts/chapters.py](/home/nes/discord/services/api/app/contracts/chapters.py:1)
  - [services/api/app/contracts/base.py](/home/nes/discord/services/api/app/contracts/base.py:1)
  - [services/api/app/api/v1/endpoints/health.py](/home/nes/discord/services/api/app/api/v1/endpoints/health.py:1)
  - [services/api/app/api/v1/router.py](/home/nes/discord/services/api/app/api/v1/router.py:1)
  - [AGENTS.md](/home/nes/discord/AGENTS.md:146)
- Official FastAPI docs:
  - APIRouter reference: https://fastapi.tiangolo.com/reference/apirouter/
  - Bigger Applications: https://fastapi.tiangolo.com/tutorial/bigger-applications/
  - Response model / return type: https://fastapi.tiangolo.com/tutorial/response-model/
  - Response status code: https://fastapi.tiangolo.com/tutorial/response-status-code/
  - Handling errors: https://fastapi.tiangolo.com/tutorial/handling-errors/
  - Body updates: https://fastapi.tiangolo.com/tutorial/body-updates/
  - Return a response directly: https://fastapi.tiangolo.com/advanced/response-directly/
  - Additional responses in OpenAPI: https://fastapi.tiangolo.com/advanced/additional-responses/
- HTTP specifications:
  - RFC 9110 HTTP Semantics: https://www.rfc-editor.org/rfc/rfc9110
  - RFC 5789 PATCH Method for HTTP: https://www.rfc-editor.org/rfc/rfc5789

## 1. FastAPI router patterns

### `APIRouter` is the normal unit for grouped endpoints

FastAPI documents `APIRouter` as the object used to group path
operations, especially for "bigger applications" split across multiple
files. The router itself can carry:

- a `prefix`
- default `tags`
- shared `dependencies`
- shared `responses`

The official "Bigger Applications" example shows exactly that shape:

```python
router = APIRouter(
    prefix="/items",
    tags=["items"],
    dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Not found"}},
)
```

Source: FastAPI "Bigger Applications"
https://fastapi.tiangolo.com/tutorial/bigger-applications/

That matches the current local pattern, where the project already has:

- endpoint-local router prefixes, e.g. `"/api/v1/health"`
- central inclusion through `app/api/v1/router.py`

### Path operation decorators carry response shape and default status

FastAPI’s path decorators (`@router.get`, `@router.post`, `@router.put`,
`@router.delete`, etc.) take metadata such as:

- `response_model`
- `status_code`
- `responses`
- `tags`

FastAPI’s APIRouter reference and response-model docs make two
important points:

- the response type can be declared either as the Python return type or
  via `response_model`
- `status_code` is declared on the decorator, not in the function body

FastAPI doc example:

```python
@app.post("/items/", status_code=201)
async def create_item(name: str):
    return {"name": name}
```

Source: FastAPI "Response Status Code"
https://fastapi.tiangolo.com/tutorial/response-status-code/

FastAPI doc example:

```python
@app.post("/items/")
async def create_item(item: Item) -> Item:
    return item

@app.get("/items/")
async def read_items() -> list[Item]:
    return [...]
```

Source: FastAPI "Response Model - Return Type"
https://fastapi.tiangolo.com/tutorial/response-model/

### Return type vs `response_model`

FastAPI supports two closely related patterns:

1. Annotate the function return type directly.
2. Declare `response_model=...` in the decorator.

The docs state that `response_model` takes priority if both are
present. This matters for stubs because a handler can keep a stable
documented success shape even if the temporary implementation does not
yet return that shape.

FastAPI doc example:

```python
@app.get("/items/", response_model=list[Item])
async def read_items() -> Any:
    return [
        {"name": "Portal Gun", "price": 42.0},
        {"name": "Plumbus", "price": 32.0},
    ]
```

Source: FastAPI "Response Model - Return Type"
https://fastapi.tiangolo.com/tutorial/response-model/

### Router-level and route-level responses compose

The "Bigger Applications" docs show router-level `responses={404: ...}`
plus route-level `responses={403: ...}` on a specific path operation.
That is relevant because a chapter router can document defaults at the
router and add per-endpoint details where needed.

## 2. Stub patterns for "not implemented" endpoints

### FastAPI uses `HTTPException` to abort a request with an HTTP error

FastAPI’s documented pattern for error responses is to `raise
HTTPException(status_code=..., detail=...)`.

Doc example:

```python
@app.get("/items/{item_id}")
async def read_item(item_id: str):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"item": items[item_id]}
```

Source: FastAPI "Handling Errors"
https://fastapi.tiangolo.com/tutorial/handling-errors/

That mechanism is the simplest documented way to keep a route in place
while returning an error response instead of successful data.

### `responses=...` is how additional non-default responses enter OpenAPI

FastAPI’s "Additional Responses in OpenAPI" docs state that extra
status codes must be declared with the decorator `responses` parameter
if they should appear in generated docs. The same doc also states that
for those additional responses, the handler must actually return a
`Response` such as `JSONResponse` at runtime.

Doc example:

```python
@app.get(
    "/items/{item_id}",
    response_model=Item,
    responses={404: {"model": Message}},
)
async def read_item(item_id: str):
    ...
    return JSONResponse(status_code=404, content={"message": "Item not found"})
```

Source: FastAPI "Additional Responses in OpenAPI"
https://fastapi.tiangolo.com/advanced/additional-responses/

Research implication:

- a stub route can preserve the success contract using return typing or
  `response_model`
- but if the docs should explicitly show `501`, that status must be
  added through `responses={501: ...}`

This second point is an inference from the docs above plus FastAPI’s
general exception behavior.

### Returning a `Response` directly bypasses normal response-model handling

FastAPI’s "Return a Response Directly" docs say that when a handler
returns `Response`/`JSONResponse` directly, FastAPI does not validate,
serialize, or document that response automatically.

That matters for stubs:

- returning `JSONResponse(status_code=501, ...)` gives full control
- but it shifts documentation burden to `responses=...`

### `501 Not Implemented` has a narrower HTTP meaning than "TODO stub"

RFC 9110 defines `501 Not Implemented` as the server not supporting the
functionality needed to fulfill the request, and says it is the right
response when the server does not recognize the request method and
cannot support it for any resource.

Source: RFC 9110 section 15.6.2
https://www.rfc-editor.org/rfc/rfc9110

Research implication:

- using `501` for an application-level stubbed endpoint is common in
  practice
- but it is somewhat broader than the RFC’s narrow framing

That distinction is important evidence, because the prompt explicitly
asks about `501` stubs.

## 3. CRUD endpoint signatures for a versioned entity

### Standard collection/item split

The common REST shape for CRUD is:

- collection endpoint for create/list
- item endpoint for get/update/delete-like operations

At the FastAPI level, that typically means:

- `POST /resources` for create
- `GET /resources` for list
- `GET /resources/{id}` for fetch-one
- `PATCH /resources/{id}` or `PUT /resources/{id}` for update
- `DELETE /resources/{id}` for removal

This is not a FastAPI-specific rule, but it aligns with the framework’s
path operation decorators and the HTTP semantics in RFC 9110 / RFC 5789.

### `POST` create normally returns `201 Created`

FastAPI’s status-code docs use `status_code=201` on `POST` as the
canonical "created a new record" example.

For a versioned entity like chapter contracts, the common request and
response surface is:

- request body: `ChapterCreate`
- response body: `ChapterRead`
- default status: `201 Created`

This mapping is an inference from the existing local chapter contracts
plus the FastAPI status/response-model docs.

### List/read endpoints usually return read models

FastAPI’s response-model docs explicitly show list responses as
`list[Item]`. Applied to a versioned entity, the common read surface is:

- list endpoint returns `list[ChapterRead]`
- fetch-one endpoint returns `ChapterRead`

This follows directly from FastAPI’s response typing patterns and the
local distinction between create/update schemas and read schema.

### `PUT` and `PATCH` mean different things

FastAPI’s "Body - Updates" guide makes the distinction explicit:

- `PUT` replaces existing data
- `PATCH` partially updates existing data

Doc example:

```python
@app.put("/items/{item_id}", response_model=Item)
async def update_item(item_id: str, item: Item):
    ...

@app.patch("/items/{item_id}")
async def update_item(item_id: str, item: Item) -> Item:
    ...
```

Source: FastAPI "Body - Updates"
https://fastapi.tiangolo.com/tutorial/body-updates/

For the chapter contracts already present locally, `ChapterUpdate`
contains optional mutable fields plus required `version`. That contract
shape aligns more naturally with partial-update semantics than full
replacement semantics. This is an inference from the contract shape and
the FastAPI update guidance.

### Common success codes for update endpoints

The problem space for update success responses is:

- `200 OK` when the server returns a representation after the update
- `204 No Content` when the update succeeded and no body is returned

RFC 9110 says successful `PUT` can return either `200` or `204`.
RFC 5789 shows a successful `PATCH` example returning `204 No Content`,
while noting that other success codes could also be used.

Sources:

- RFC 9110 section 9.3.4: https://www.rfc-editor.org/rfc/rfc9110
- RFC 5789 section 2.1: https://www.rfc-editor.org/rfc/rfc5789

### Archive belongs in the CRUD problem space because the entity is versioned and stateful

The existing chapter model already includes `ChapterStatus.archived`.
That means the entity surface is not a pure create/read/update/delete
problem; lifecycle state change is already part of the contract space.

Research implication:

- there is a normal CRUD question (`DELETE` vs no `DELETE`)
- and a separate lifecycle question (`archive` as a status transition)

## 4. Optimistic locking at the HTTP layer

### The repo’s current concurrency contract is body-version based

Local evidence already fixes the core concurrency rule:

- read returns `version`
- update submits `version`
- stale update maps to `409 Conflict`

That is established by:

- `VersionedMixin`
- `ChapterRead`
- `ChapterUpdate`
- `AGENTS.md`

### HTTP has two related concurrency patterns: conditional requests and application-level version fields

RFC 5789 recommends conditional requests for PATCH collisions, using a
strong ETag in `If-Match` so the request fails if the resource changed
since the client last saw it.

Source: RFC 5789 section 2
https://www.rfc-editor.org/rfc/rfc5789

That is the protocol-native HTTP mechanism. The project’s existing
contracts instead use an application-level version integer in the body.

Research implication:

- HTTP-native optimistic locking commonly uses validators / `If-Match`
- this repo’s current contract surface uses body-carried version data

### `409 Conflict` is well aligned with stale-version failures

RFC 9110 defines `409 Conflict` as a request that could not be
completed because of a conflict with the current state of the target
resource, and explicitly says versioning conflicts are a likely case.

RFC 5789 also gives `409 Conflict` as the useful response for
conflicting state, conflicting modification without a precondition, and
some concurrent-modification cases.

Sources:

- RFC 9110 section 15.5.10: https://www.rfc-editor.org/rfc/rfc9110
- RFC 5789 section 2.2: https://www.rfc-editor.org/rfc/rfc5789

This lines up directly with the repo’s `VersionedMixin` rule.

### `412 Precondition Failed` is the neighboring status when headers are used

RFC 5789 distinguishes two concurrency cases:

- if the client sent a precondition such as `If-Match` and it fails,
  `412 Precondition Failed` is most helpful
- if there was no precondition and the server detects a conflicting
  modification, `409 Conflict` can be returned

Research implication:

- body-version concurrency naturally points to `409`
- header-precondition concurrency naturally points to `412`

That distinction matters because the prompt asked specifically about the
meaning of `409 Conflict`.

## 5. Archive versus delete semantics

### `DELETE` is about removing the URI/resource association

RFC 9110 defines `DELETE` as a request to remove the association between
the target resource and its current functionality. The spec explicitly
notes that the underlying representation might or might not be destroyed
and that related implementation state might instead be deactivated or
archived.

It also says successful `DELETE` commonly returns:

- `202 Accepted` if not yet enacted
- `204 No Content` if enacted with no body
- `200 OK` if enacted with a representation describing status

Source: RFC 9110 section 9.3.5
https://www.rfc-editor.org/rfc/rfc9110

### Archive is not an HTTP verb; it is a state transition

HTTP does not define an "archive" method. In a resource model where
`archived` is an explicit lifecycle state, archive is therefore a
domain-level state change rather than a protocol-level deletion
primitive.

Because RFC 5789 defines PATCH as applying partial modifications to an
existing resource, and because the local chapter contracts already
include `status`, archive naturally sits in the problem space of:

- partial update to an existing resource, or
- action endpoint if the operation is modeled as a command rather than a
  generic field patch

The second bullet is supported by RFC 5789’s guidance that if an
operation does not modify the resource in a predictable way, `POST`
should be considered instead of `PATCH` or `PUT`.

Source: RFC 5789 section 2
https://www.rfc-editor.org/rfc/rfc5789

This is not a design recommendation; it is the boundary of the problem
space created by the existing `ChapterStatus` contract.

### Archive and hard delete communicate different client expectations

From the existing local contracts alone:

- `archived` implies the chapter still exists as a readable entity
- hard delete implies the client should stop expecting the entity to
  remain addressable

That difference affects:

- whether `GET /chapters/{id}` can still succeed after archival
- whether list endpoints include archived chapters
- whether clients treat the action as reversible state change or as
  resource disappearance

Those are behavior questions that sit downstream from the HTTP semantics
documented here.

## Problem-space summary

- FastAPI’s standard router pattern is `APIRouter` with shared `prefix`,
  `tags`, and optional shared `responses`, then path decorators with
  `response_model` and `status_code`.
- The simplest stable stub surface is a declared route plus
  `HTTPException` or direct `Response`/`JSONResponse`; explicit OpenAPI
  documentation for `501` requires `responses=...`.
- `501 Not Implemented` is usable as a stub status in application code,
  but RFC 9110 gives it a narrower semantics than generic "not built
  yet".
- The existing chapter contracts already imply a standard create/list/
  get/update surface, with `ChapterUpdate` looking PATCH-shaped because
  its mutable fields are optional but `version` is required.
- `409 Conflict` is a strong semantic match for stale-version updates in
  a body-version optimistic-locking scheme; `412` is the sibling status
  when header preconditions are used instead.
- Archive is a resource state transition, not an HTTP method. `DELETE`
  and archive are therefore semantically different even if both may
  affect visibility.
