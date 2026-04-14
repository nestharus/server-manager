# PR Review: Chapter Endpoint Stubs

Date: 2026-04-13

Proposal: `proposals/27-chapter-endpoints.md`

## Verdict: Single PR — no decomposition required

The PR contains one concern: establish the chapter HTTP surface as
501 stubs. The three file changes are co-dependent and cannot ship
independently in a useful state.

## Multi-Concern Analysis

### Concern 1: Endpoint stub module

Files: `services/api/app/api/v1/endpoints/chapters.py` (lines 1–37)

Five route handlers, each a single `raise HTTPException(501)`. The
module imports only `APIRouter`, `HTTPException`, `HTTPStatus`, and the
three contract models. No business logic, no service dependencies.

### Concern 2: Router mount

Files: `services/api/app/api/v1/router.py` (lines 11, 14)

Two-line change: add `chapters` to the import and call
`router.include_router(chapters.router, tags=["chapters"])`.

### Concern 3: Stub tests

Files: `services/api/tests/test_endpoints_chapters_stubs.py` (lines 1–106)

Seven tests: one parametrized test covering all five routes return 501,
one verifying the module is importable, one verifying the expected route
set is registered.

### Dependency graph

```
router mount ← endpoint stubs ← tests
```

All three are tightly coupled:

- The router mount is meaningless without the endpoint module.
- The tests import and exercise the endpoint module and the router.
- The endpoint module serves no purpose if not mounted.

Splitting any of these into a separate PR would create a PR that either
(a) adds dead code or (b) breaks the build.

### Could the tests be a follow-up PR?

No. The stubs are trivial enough that shipping them without tests
provides no incremental value. The tests are what prove the stubs
exist and behave as specified. Separating them would create a first PR
whose only reviewable claim — "these five routes exist and return 501" —
is unverified.

## Justification Check

### Belongs in this PR

| Item | Justification |
|------|---------------|
| `chapters.py` — 5 stub handlers | Core deliverable: establish HTTP surface |
| `router.py` — mount chapters router | Required for stubs to be reachable |
| `test_endpoints_chapters_stubs.py` — 7 tests | Verify the contract this PR claims to deliver |

### Does not belong in this PR (none found)

The PR adds no unrelated changes. No formatting fixes, no refactors,
no dependency bumps, no changes to unrelated modules.

## Implementation vs Proposal Deviation

One deviation from the proposal's design section:

The implementation adds explicit `response_model=ChapterRead` (and
`response_model=list[ChapterRead]`) arguments to every route decorator.
The proposal's "Return annotations vs explicit `response_model`"
tradeoff section explicitly chose to rely on return type annotations
alone and called `response_model=` redundant.

```python
# Proposal (§ Exact Module Structure):
@router.post("", status_code=HTTPStatus.CREATED)
def create_chapter(payload: ChapterCreate) -> ChapterRead:

# Implementation:
@router.post("", response_model=ChapterRead, status_code=HTTPStatus.CREATED)
def create_chapter(chapter: ChapterCreate) -> ChapterRead:
```

This deviation is harmless — `response_model` and the return annotation
produce the same OpenAPI output when they agree — but it contradicts a
deliberate proposal decision. The implementation should either drop the
`response_model` arguments to match the proposal or the proposal should
be amended to justify the addition.

Additionally, the parameter name differs: the proposal uses `payload`
while the implementation uses `chapter`. This is cosmetic and does not
affect behavior, but is noted for consistency tracking.

## Conclusion

This PR is a single atomic concern: define the chapter endpoint HTTP
surface as 501 stubs, mount it, and test it. It cannot be meaningfully
decomposed further. The one actionable finding is the `response_model`
deviation from the proposal, which should be resolved in one direction
or the other before merge.
