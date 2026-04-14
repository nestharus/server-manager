# Scope Risk: Proposal 27 — Chapter Endpoint Stubs

Date: 2026-04-13

## Findings

### 1. Anti-scope adherence — LOW

The proposal declares nine anti-scope items. The proposed module
imports only `APIRouter`, `HTTPException`, `HTTPStatus`, and the three
chapter contract models. No service, repository, infrastructure,
auth, pagination, or Discord provisioning logic is present.
Every handler body is a single `raise HTTPException(status_code=
HTTPStatus.NOT_IMPLEMENTED)`. The anti-scope boundary holds.

### 2. PR size — LOW

The deliverable is one new file (~30 lines) containing five stub
handlers. This is well within single-PR territory and has no risk
of bundling unrelated concerns.

### 3. Coupling to unbuilt layers — LOW

The only external dependency is `app.contracts.chapters`, which
already exists (merged in P0279). No forward references to service,
repository, or infrastructure modules. The stubs can be written and
tested (via `httpx.AsyncClient` mounting the router directly) without
any layer that doesn't yet exist.

### 4. Route completeness vs contracts — LOW

The five routes cover the full CRUD surface implied by the chapter
contracts:

- `ChapterCreate` → `POST /api/v1/chapters` (201)
- `ChapterRead` → `GET /api/v1/chapters`, `GET /api/v1/chapters/{chapter_id}` (200)
- `ChapterUpdate` → `PATCH /api/v1/chapters/{chapter_id}` (200)
- `ChapterStatus.archived` → `POST /api/v1/chapters/{chapter_id}/archive` (200)

`ChapterStatus.provisioning` has no dedicated endpoint, which is
correct — provisioning is an internal state set during Discord
category/role creation, not a user-facing action. No routes are
missing.

Note: `ChapterUpdate.status` allows setting `archived` via PATCH,
which overlaps semantically with the archive action endpoint. The
proposal addresses this in its tradeoffs section. This is a design
choice, not a scope gap — the dedicated archive endpoint exists to
host future business rules (cascade operations, guard clauses) that
don't belong in a generic partial-update handler.

### 5. Deferred vs included scope — LOW

The proposal defers router wiring (`router.py` inclusion) with "The
central v1 router should later include it." This is a 2-line change
to `services/api/app/api/v1/router.py`. Including it would make the
stubs reachable from a running app instance; excluding it keeps the
PR limited to the endpoint file alone.

Either choice is defensible. Tests can mount the router directly
without the v1 aggregator, and the stubs return 501 regardless. The
wiring is small enough to include if the implementer prefers, but
deferring it does not create a gap — the endpoint contract is fully
defined either way.

### 6. "No Deferred Stubs" rule compatibility — LOW

AGENTS.md states: "Do not create placeholder stubs or TODO comments
unless the implementation plan explicitly indicates the item is
planned for a later task."

The 501 stubs are not deferred implementations — they are the
contract-definition phase artifact described in the implementation
workflow (step 1: "Define contract → Pydantic schemas, endpoint
signatures"). The test agent targets these signatures; the code
agent replaces the 501 bodies. This is the intended pipeline, not
a rule violation.

### 7. Scope creep indicators — LOW

The proposal includes exact code, which could be read as crossing
from "design only" into implementation. However, the code serves as
a precise specification of what the file should look like — it is
not committed to the repo by this proposal. The proposal phase
outputs a design artifact; the implementation phase writes it to
disk. No creep.

## Overall Risk: LOW

The proposal is tightly scoped, correctly bounded by its anti-scope
declarations, and consistent with both the existing codebase patterns
and the project's pipeline rules. No changes are required before
implementation.
