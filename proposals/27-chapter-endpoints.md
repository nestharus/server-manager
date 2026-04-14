# Proposal: `services/api/app/api/v1/endpoints/chapters.py`

Date: 2026-04-13

## Goal

Define `services/api/app/api/v1/endpoints/chapters.py` as the v1 HTTP
surface for chapter CRUD and archive operations.

This proposal is design only. It does not include implementation code.

The module should expose the chapter endpoint contract early, using
stubbed handlers that always raise `HTTPException` with `501 Not
Implemented`, while still advertising the intended success request and
response shapes in OpenAPI.

## Architecture

`chapters.py` belongs in the API layer at
`services/api/app/api/v1/endpoints/`. Its responsibility is limited to
declaring FastAPI routes and binding them to the existing chapter
contract models in `services/api/app/contracts/chapters.py`.

Layer boundaries:

- `services/api/app/contracts/chapters.py` owns the request and response
  schemas: `ChapterCreate`, `ChapterRead`, and `ChapterUpdate`.
- `services/api/app/api/v1/endpoints/chapters.py` owns the HTTP method,
  path, status code, and path/body signatures for chapter operations.
- Future service, repository, and infrastructure modules will own
  actual business logic, persistence, optimistic-lock conflict handling,
  and Discord-side provisioning effects.

Integration point:

- The module should follow the existing `health.py` endpoint pattern:
  declare `router = APIRouter(prefix="/api/v1/chapters")` locally.
- The central v1 router should later include it with
  `router.include_router(chapters.router, tags=["chapters"])`, matching
  the current `health` inclusion style.

This keeps the endpoint module narrow: it defines the public HTTP
surface without pulling service dependencies into the file before those
layers exist.

## Route Table

| Method | Path | Request body | Success response | Success status | Current stub behavior |
|---|---|---|---|---|---|
| `POST` | `/api/v1/chapters` | `ChapterCreate` | `ChapterRead` | `201 Created` | raises `501 Not Implemented` |
| `GET` | `/api/v1/chapters` | — | `list[ChapterRead]` | `200 OK` | raises `501 Not Implemented` |
| `GET` | `/api/v1/chapters/{chapter_id}` | — | `ChapterRead` | `200 OK` | raises `501 Not Implemented` |
| `PATCH` | `/api/v1/chapters/{chapter_id}` | `ChapterUpdate` | `ChapterRead` | `200 OK` | raises `501 Not Implemented` |
| `POST` | `/api/v1/chapters/{chapter_id}/archive` | — | `ChapterRead` | `200 OK` | raises `501 Not Implemented` |

Notes:

- `chapter_id` should be typed as `int`.
- `PATCH` uses `ChapterUpdate`, which already carries the required
  `version` field through `VersionedMixin`.
- `archive` is modeled as an action endpoint, not a delete endpoint,
  because the chapter contract already has an `archived` lifecycle
  state.

## Exact Module Structure

The module should follow the same construction style as
`services/api/app/api/v1/endpoints/health.py`: module docstring,
`from __future__ import annotations`, imports, router declaration, then
path operation functions.

```python
"""Chapter endpoint stubs."""

from __future__ import annotations

from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from app.contracts.chapters import ChapterCreate, ChapterRead, ChapterUpdate

router = APIRouter(prefix="/api/v1/chapters")


@router.post("", status_code=HTTPStatus.CREATED)
def create_chapter(payload: ChapterCreate) -> ChapterRead:
    raise HTTPException(status_code=HTTPStatus.NOT_IMPLEMENTED)


@router.get("")
def list_chapters() -> list[ChapterRead]:
    raise HTTPException(status_code=HTTPStatus.NOT_IMPLEMENTED)


@router.get("/{chapter_id}")
def get_chapter(chapter_id: int) -> ChapterRead:
    raise HTTPException(status_code=HTTPStatus.NOT_IMPLEMENTED)


@router.patch("/{chapter_id}")
def update_chapter(chapter_id: int, payload: ChapterUpdate) -> ChapterRead:
    raise HTTPException(status_code=HTTPStatus.NOT_IMPLEMENTED)


@router.post("/{chapter_id}/archive")
def archive_chapter(chapter_id: int) -> ChapterRead:
    raise HTTPException(status_code=HTTPStatus.NOT_IMPLEMENTED)
```

Module decisions:

- Use `from http import HTTPStatus` for decorator and exception status
  constants.
- Use contract models directly in function signatures so generated
  OpenAPI reflects the intended request and response shapes.
- Keep the collection-root decorators on `""`, not `"/"`, to match the
  existing `health.py` style and avoid introducing trailing-slash
  behavior that differs from the local baseline.
- Use plain synchronous `def` handlers for now, matching `health.py`
  and avoiding premature async structure before service calls exist.
- Raise `HTTPException` directly in each handler; no shared helper is
  needed for five small stubs.

## Tradeoffs Considered

### Root path as `""` vs `"/"`

Using `""` in the decorators keeps the external route at
`/api/v1/chapters` while matching the existing `health.py` pattern.
Using `"/"` would introduce a trailing-slash collection route and drift
from the current endpoint style.

### `POST /{chapter_id}/archive` vs `PATCH` status mutation

Both shapes could represent archiving, but `POST /{chapter_id}/archive`
is the better fit for this project’s current contract stage:

- it makes the archive action explicit
- it avoids overloading general update semantics before business rules
  exist
- it aligns with the fact that chapter lifecycle already includes an
  `archived` state rather than resource deletion

### Return annotations vs explicit `response_model`

The simplest shape is to rely on typed function signatures:

- request bodies use `ChapterCreate` and `ChapterUpdate`
- return types use `ChapterRead` and `list[ChapterRead]`

That is sufficient for OpenAPI generation and keeps the module minimal.
Adding explicit `response_model=` arguments would be redundant unless a
future implementation needs response filtering or a different internal
return type.

### Documenting only the intended success contract vs modeling 501 in OpenAPI

The proposal keeps the route declarations centered on the intended
steady-state contract while the implementation temporarily raises `501`.
This is the right tradeoff for the current phase because the purpose of
these stubs is to establish the long-term HTTP surface that later layers
will satisfy, not to encode temporary stub-only docs complexity.

### No extra path/body validation beyond the contracts

The path parameter remains `chapter_id: int` without additional
constraints such as `Path(gt=0)`. That keeps the module aligned with the
requested scope and avoids sneaking in validation policy that belongs in
later implementation or broader API conventions.

## Anti-Scope

The following do not belong in
`services/api/app/api/v1/endpoints/chapters.py` for this proposal:

- service-layer calls or dependency injection
- repository or infrastructure imports
- authentication or authorization requirements
- pagination, filtering, or search on the list route
- optimistic-lock conflict handling beyond the `ChapterUpdate` request
  shape
- `404`, `409`, or other detailed error responses
- database models, migrations, or persistence behavior
- Discord category or role provisioning logic
- router-level shared dependencies, tags, or response metadata beyond
  what is needed for these five stubs
