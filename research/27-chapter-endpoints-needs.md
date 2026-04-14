# Synthesis: Chapter Endpoint Stubs — Humility Needs

## Purpose

Map the research in `research/27-chapter-endpoints.md` to Humility's
specific requirements for chapter endpoint stubs.

## What Humility needs

This is a **pre-implementation** step. The endpoints exist only to
provide a stable HTTP surface for the test agent to target. The actual
service/repository layers don't exist yet.

### Routes needed

Based on the chapter contracts (P0279) and AGENTS.md contract:

| Route | Method | Request | Response | Status |
|-------|--------|---------|----------|--------|
| `POST /api/v1/chapters` | Create | `ChapterCreate` | `ChapterRead` | 201 Created |
| `GET /api/v1/chapters` | List | — | `list[ChapterRead]` | 200 OK |
| `GET /api/v1/chapters/{chapter_id}` | Get | — | `ChapterRead` | 200 OK |
| `PATCH /api/v1/chapters/{chapter_id}` | Update | `ChapterUpdate` | `ChapterRead` | 200 OK |
| `POST /api/v1/chapters/{chapter_id}/archive` | Archive | — | `ChapterRead` | 200 OK |

### Key design decisions

1. **Archive as POST action, not DELETE** — The research confirms
   archive is a state transition (status → archived), not resource
   removal. Using `POST .../archive` makes this explicit. The chapter
   contracts already have `ChapterStatus.archived`.

2. **Update uses PATCH with optimistic locking** — `ChapterUpdate`
   requires `version` (from `VersionedMixin`). Stale writes return
   409 Conflict. This is the AGENTS.md contract.

3. **Stub behavior: 501 Not Implemented** — All routes currently
   raise `HTTPException(status_code=501)` since no service layer
   exists yet. The test agent will encode the *intended* contract
   behavior, not stub behavior.

4. **Router prefix pattern** — Follow the health endpoint's pattern:
   `APIRouter(prefix="/api/v1/chapters")`.

### What's NOT in scope

- No service layer, repository layer, or database access
- No authentication/authorization
- No pagination on list endpoint
- No filtering/search on list endpoint
- No Discord integration (category/role provisioning)

### Gaps identified

None. The contracts are well-defined, the endpoint signatures follow
directly from them, and the 501 stub approach is straightforward.
