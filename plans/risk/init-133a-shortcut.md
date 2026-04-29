# INIT-133A — Shortcut risk gate

**Verdict:** LOW

## S1 — Keyset pagination on `(submitted_at, id)` only
**Choice:** the cursor is `after_id` resolved server-side via a
subquery to fetch the cursor row's `submitted_at`.

**Risk:** if `submitted_at` is updated post-creation (it should
not be), the cursor could skip or duplicate rows.

**Mitigation:** `submitted_at` is set at row creation and never
updated by any code path (verified by reading the application
service).

Not a shortcut.

## S2 — No filter for applicant_id
**Deferred:** the list endpoint is officer-facing. Applicants
read their own apps via the existing GET-by-id route or a
future `/me/applications` route.

**Risk:** an applicant cannot list "all my pending
applications" through the UI without a per-app fetch.

**Mitigation:** out of scope per proposal Q1; adding it later
is non-breaking (an `applicant_id` filter param is additive).

Not a shortcut.

## S3 — Authorization at the resolved scope only
**Choice:** the request's `scope_kind` + `scope_id` filter
defines the auth scope. If absent → "global". An officer with
chapter-A permissions cannot list across multiple chapters in
one call.

**Risk:** UX limitation (officer must filter to one scope at a
time).

**Mitigation:** correct authorization model. A "list across
multiple scopes" feature would aggregate per-scope queries
client-side; not required for v1.

Not a shortcut — correct security boundary.

## S4 — No total count in the response
**Choice:** response shape has `items` + `next_after_id` only;
no `total: int`.

**Risk:** UI can't show "12 of 327" without an extra count
query.

**Mitigation:** total counts on filtered queries are expensive
in Postgres. The cursor pagination is the primary scaling
mechanism. If a count is needed later, add as a separate
`?with_count=true` flag.

Not a shortcut.

## Verdict

LOW — every deferral is documented and additive.
