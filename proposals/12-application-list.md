# Proposal 12 — INIT-133A / BL-019D-α: list-applications endpoint

## Goal

`GET /api/v1/applications` returns a filtered, paged list of
applications. Required for INIT-133B's SPA officer queue page;
no list endpoint exists today (only single-application GET +
public submit + transitions).

## Q1..Q5 — locked

**Q1.** Filters (all optional, all query-string):
- `state` — comma-separated list of `ApplicationState` values
  (`submitted`, `queued`, `claimed`, `in_review`, `interview`,
  `waitlisted`, `approved`, `denied`, `withdrawn`). When omitted,
  returns all states.
- `scope_kind` — `global` | `chapter`. When omitted, returns
  applications across any scope the caller has authority for.
- `scope_id` — chapter id when `scope_kind=chapter`. Required
  if `scope_kind=chapter` is provided.
- `owner_id` — UUID of the assigned reviewer; if provided,
  restricts to applications owned by that member.

**Q2.** Pagination:
- `limit` — default 50, max 200.
- `after_id` — UUID of the last seen application; cursor on
  `(submitted_at DESC, id ASC)`.

**Q3.** Authorization:
- Caller must hold ANY of `application.claim`,
  `application.review`, `application.approve`,
  `application.deny`, `application.waitlist`,
  `application.reactivate`, `application.withdraw` at the
  resolved scope.
- "Resolved scope" = the explicit `scope_kind`+`scope_id` filter
  if provided; else `global`.
- This mirrors `require_application_read_authority` — the
  permission set already used for single-application reads when
  the caller isn't the applicant.

**Q4.** Response shape — new contract `ApplicationListRead`:
```json
{
  "items": [ApplicationRead, ...],
  "next_after_id": "<uuid or null>"
}
```
`next_after_id` is the last item's id when more pages exist,
else null.

**Q5.** No new schema. Pure query against the existing
`applications` table joined with `aggregate_heads` (the existing
`_MEMBER_SELECT` pattern from
`repositories/applications.py:_APPLICATION_SELECT`).

## Scope

- New repository function `list_applications(connection, *,
  states, scope_kind, scope_id, owner_id, limit, after_id) ->
  list[dict]` in
  `services/api/app/repositories/applications.py`.
- New service entry `list_applications(db, *, ...) ->
  ApplicationListRead` in
  `services/api/app/services/applications.py`.
- New endpoint
  `GET /api/v1/applications` in
  `services/api/app/api/v1/endpoints/applications/lifecycle.py`
  (or a new file — pick whichever has the existing
  `POST /api/v1/applications` route to keep the surface
  cohesive).
- New contract `ApplicationListRead` in
  `services/api/app/contracts/applications.py`.
- Tests:
  - filter by state (single + comma list)
  - filter by scope_kind + scope_id
  - filter by owner_id
  - authorization: stranger 403; applicant who is not an officer
    402/403 (only sees own apps via single-app GET, not the
    list); officer with permission 200
  - pagination: limit + after_id round-trip
  - empty result returns `items: []`, `next_after_id: null`

## Anti-scope

- Filtering by applicant_id (the applicant's own apps): the
  caller can fetch their own applications via the existing
  single-app endpoint or a future `/me/applications` route.
  Out of scope here.
- Sorting options other than `submitted_at DESC`: out of scope.
- Free-text search: out of scope.
- Aggregations / counts in the response: out of scope.

## Net value

- Unblocks INIT-133B SPA officer queue.
- Foundation for any future "officer dashboard" features.

## Risk gates (self-review, all LOW)

### Audit
N/A — greenfield read endpoint.

### Scope
Bounded to one repository function, one service entry, one
endpoint, one contract addition, plus tests. No schema change.

### Shortcut
- No filter for applicant_id: deferred per anti-scope; future
  `/me/applications` can serve that need.
- No sort options: applications are naturally chronological;
  reverse-chronological is the only relevant sort for a queue.
- No free-text search: applications don't have a "subject" to
  search.

### Supported-surface
- HTTP: net-new GET on the existing `/api/v1/applications`
  prefix. No conflict with the existing POST.
- DB: SELECT-only, no schema change.
- Permissions: reuses the existing application transition
  permissions; no new permission name.

## Diff budget

~250 lines net add.
