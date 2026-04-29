# INIT-133A — Scope risk gate

**Verdict:** LOW

## In scope

- New endpoint `GET /api/v1/applications` returning a paged
  filtered list of applications.
- Filters: state (comma-sep), scope_kind, scope_id, owner_id.
- Cursor pagination on `(submitted_at DESC, id ASC)`.
- Authorization reuses the `require_application_read_authority`
  permission set (any of claim/review/approve/deny/...).
- `ApplicationListRead` envelope contract.
- Repository/service/endpoint extensions in the existing
  applications modules — no new files required (all extensions
  to `contracts/applications.py`, `repositories/applications.py`,
  `services/applications.py`, `endpoints/applications/lifecycle.py`).

## Out of scope

- Filtering by applicant_id (deferred to a future
  `/me/applications` route).
- Sorting options other than reverse-chronological.
- Free-text search.
- Aggregations/counts in the response.
- SPA UI consumption (INIT-133B).

## Risk surface

- **HTTP additions:** one new GET; no existing route changes.
- **Schema:** none; SELECT-only.
- **Permissions:** reuses existing application-review
  permission set; no new permission name.
- **Behavioral change to existing flows:** none.

## Verdict

LOW — purely additive read endpoint.
