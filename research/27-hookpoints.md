# Hookpoint Research — Chapter endpoint stubs

## Existing code that can be reused as-is

### `services/api/app/api/v1/endpoints/health.py`

- `health.py` is the correct local pattern template for the proposed
  endpoint module.
- It already establishes the baseline shape the proposal wants:
  module docstring, `from __future__ import annotations`, local
  `APIRouter(prefix=...)`, and sync `def` handlers with `@router.get("")`
  style decorators ([services/api/app/api/v1/endpoints/health.py](/home/nes/discord/services/api/app/api/v1/endpoints/health.py:1)).
- The chapter stub module can reuse that construction style directly
  while swapping in `HTTPException`, `HTTPStatus`, and chapter contract
  imports.

### `services/api/app/contracts/chapters.py`

- The chapter contract models already exist and match the proposal's
  intended handler signatures:
  - `ChapterCreate` for `POST /api/v1/chapters`
  - `ChapterRead` for all success responses
  - `ChapterUpdate` for `PATCH /api/v1/chapters/{chapter_id}`
  - `ChapterStatus` for lifecycle state shape
  ([services/api/app/contracts/chapters.py](/home/nes/discord/services/api/app/contracts/chapters.py:9)).
- `ChapterRead` and `ChapterUpdate` already inherit `VersionedMixin`,
  so the update route's optimistic-lock request shape is already present
  via the required `version` field ([services/api/app/contracts/chapters.py](/home/nes/discord/services/api/app/contracts/chapters.py:20), [services/api/app/contracts/base.py](/home/nes/discord/services/api/app/contracts/base.py:4)).
- No contract changes are required for the stub endpoint phase.

### `services/api/app/api/v1/router.py`

- This file is already the intended aggregation point for v1 endpoints.
- Its current structure is minimal and reusable: import endpoint module,
  create a shared `APIRouter()`, then `include_router(...)`
  ([services/api/app/api/v1/router.py](/home/nes/discord/services/api/app/api/v1/router.py:1)).

## What needs to be created

### New endpoint module

- Create `services/api/app/api/v1/endpoints/chapters.py`.
- This is the only new file required by the proposal itself.
- Its responsibility is limited to declaring the five route stubs and
  binding them to the existing contract types described in
  `proposals/27-chapter-endpoints.md`
  ([proposals/27-chapter-endpoints.md](/home/nes/discord/proposals/27-chapter-endpoints.md:17)).

## What needs to be modified

### `services/api/app/api/v1/router.py`

- Yes, this file needs modification.
- It currently imports only `health` and mounts only `health.router`
  ([services/api/app/api/v1/router.py](/home/nes/discord/services/api/app/api/v1/router.py:11)).
- To expose the new chapter endpoints through the existing v1
  aggregation point, it needs:
  - an import for `chapters`
  - `router.include_router(chapters.router, tags=["chapters"])`

### `services/api/app/core/factory.py`

- Yes, this file also needs modification if the goal is for the stub
  endpoints to be reachable at runtime.
- `create_app()` currently creates the `FastAPI` instance, stores
  settings on `app.state`, and returns immediately. It does not include
  the v1 router at all
  ([services/api/app/core/factory.py](/home/nes/discord/services/api/app/core/factory.py:6)).
- `services/api/app/main.py` does nothing beyond `app = create_app()`,
  so there is no alternate mount point elsewhere in the app bootstrap
  path ([services/api/app/main.py](/home/nes/discord/services/api/app/main.py:6)).
- Result: today, even the existing `health` router is defined but not
  attached to the application instance. Chapter routes would inherit the
  same problem unless `create_app()` includes the shared v1 router.
- This is a pre-existing integration seam, not a chapters-specific
  design change.

### `services/api/app/api/v1/endpoints/__init__.py`

- No update is required for proposal compliance.
- The file is currently only a package docstring
  ([services/api/app/api/v1/endpoints/__init__.py](/home/nes/discord/services/api/app/api/v1/endpoints/__init__.py:1)).
- The current import style in `router.py` is `from app.api.v1.endpoints import health`,
  which works because Python can resolve submodules from the package
  without explicit re-exports in `__init__.py`.
- The same pattern can be used for `chapters`, so adding package-level
  exports would be optional convention work, not a hookpoint requirement.

## What should be deleted

- Nothing.
- This change is additive. No existing endpoint, router, or contract
  module needs removal to make room for `chapters.py`.

## Parallelization opportunities

- The new endpoint file and the integration wiring are separable work.
- One worker can create `services/api/app/api/v1/endpoints/chapters.py`
  while another updates router registration in:
  - `services/api/app/api/v1/router.py`
  - `services/api/app/core/factory.py`
- These touch disjoint files and only converge at final verification.

## Direct answers

1. What existing code can be reused as-is?
   - `health.py` for router/module layout.
   - `contracts/chapters.py` for request/response type signatures.
   - `api/v1/router.py` as the central mount point pattern.
2. What needs to be created?
   - `services/api/app/api/v1/endpoints/chapters.py`.
3. What needs to be modified?
   - `services/api/app/api/v1/router.py`: yes, to mount `chapters.router`.
   - `services/api/app/core/factory.py`: yes, to include the v1 router on
     the FastAPI app.
   - `services/api/app/api/v1/endpoints/__init__.py`: no, not required.
4. What should be deleted?
   - Nothing.
5. Can any work be parallelized?
   - Yes. Endpoint-file creation is independent from router/app mounting.
