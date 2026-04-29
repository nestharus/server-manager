# INIT-129 — BL-018 scope: remove dead synthetic-creation path

## Background

INIT-128 (BL-017) replaced the anonymous public submit path with a
receipt-required path. The endpoint
`POST /api/v1/public/applications` now requires a valid
`applicant_receipt` cookie and dispatches to
`submit_public_application_with_receipt` which resolves or creates
a real `kind='discord'` member from the receipt's snowflake.

The pre-INIT-128 anonymous flow (`submit_public_application` →
`resolve_or_create_public_intake_member` → synthetic
`kind='public_intake'` member) is now unreachable from the request
path. Tests for the dead helper still exist.

## Live state on humility-local (post-INIT-128)

```
SELECT kind, COUNT(*) FROM members GROUP BY kind;
discord        1   -- the receipt-backed e2e submission from INIT-128
public_intake 18   -- pre-INIT-128 historical e2e fixture artifacts
```

The 18 historical synthetic rows are e2e test artifacts from
prior init runs. They are not user data. Production has not
shipped yet.

## What is dead vs alive

### Dead (no callers from request path)

- `services/api/app/services/applications.py`
  - `submit_public_application` (function, lines ~828-860)
  - `PUBLIC_INTAKE_ACTOR` constant (only used by dead function)
  - `PUBLIC_INTAKE_MEMBER_SALT` constant (only used by dead helper)
  - `PUBLIC_INTAKE_NAMESPACE` constant (only used by dead function)
  - `_SubmissionAuthority.PUBLIC_INTAKE` enum value + the branch
    in `_submit_application_internal` that handles it
- `services/api/app/services/members.py`
  - `resolve_or_create_public_intake_member` async helper
  - The `public:<digest>` discord_user_id formula it uses
- `services/api/app/core/settings.py`
  - `public_intake_member_salt` setting field
- `services/api/tests/test_public_intake_synthetic_member.py`
  (entire file — direct tests for the dead helper)
- `services/api/tests/conftest.py` synthetic-member fixture
  (need to check usage; INIT-128's test_public_intake_submit.py
  still references it but only via `public_intake_fixtures.py`)

### Alive (kept as defense-in-depth)

- `services/api/app/contracts/members.py:MemberKind` literal
  including `"public_intake"` — historical rows in DB still have
  this value; the type must accept it.
- `services/api/app/services/members.py:is_synthetic_member()` —
  write-boundary guard. Even though no new synthetic rows can be
  created via the request path, the helper is the canonical way
  to check for historical-or-injected synthetic rows.
- All `is_synthetic_member()` callers in
  `services/{applications,trust,roster,authority}.py` — guards
  remain valuable for the 18 historical rows already in
  humility-local + any other historical production data.
- `services/api/app/services/authorization.py:authorize_public_intake`
  — Cedar policy check for whether public intake is allowed in
  this channel; orthogonal to receipt mechanism.
- `PUBLIC_SUBMIT_SURFACE` constant in applications.py — still
  used by `submit_public_application_with_receipt` for the
  request_surface field.

## What about the 18 historical rows?

Options considered:

1. **Delete them (and cascading audit/state-change/aggregate-head
   rows)** — destructive; breaks the audit trail; not safe in
   production. Rejected.
2. **Annotate them (e.g., add a `superseded_at` timestamp)** —
   adds schema complexity for a problem that doesn't exist yet
   (no consumer is reading these rows).
3. **Leave them as-is.** Read-side guards already filter them
   correctly. They are e2e test artifacts in humility-local;
   they are not in production.

Picking option 3. The "cleanup Job" originally proposed in
BL-018's plan section assumed a "linked → keep, unlinked
synthetic → drop" rule that came from the abandoned
member_links/conversion design. Post-INIT-128 there is no
linking — synthetic rows are simply historical and inert.

## Scope

INIT-129 = code-only dead-path removal:

- Delete `submit_public_application` and its constants
  (PUBLIC_INTAKE_ACTOR, PUBLIC_INTAKE_MEMBER_SALT,
  PUBLIC_INTAKE_NAMESPACE).
- Delete `_SubmissionAuthority.PUBLIC_INTAKE` enum value + its
  branch in `_submit_application_internal`. The remaining enum
  member is the receipt-backed path.
- Delete `resolve_or_create_public_intake_member` helper.
- Delete `public_intake_member_salt` setting field.
- Delete `services/api/tests/test_public_intake_synthetic_member.py`.
- Update `services/api/tests/conftest.py` and any other test
  fixtures that depend on the deleted helpers.
- Keep `is_synthetic_member()` and all its callers as
  defense-in-depth.
- Keep `MemberKind` literal accepting `"public_intake"` so
  the type-checker accepts historical rows.

## Out of scope

- Schema migration (`kind` column already exists from INIT-125A;
  no change needed).
- Cleanup of historical synthetic rows in any DB.
- Removing `is_synthetic_member()` or its callers — they remain
  defense-in-depth.
- Removing the `MemberKind` literal's `"public_intake"` member.

## Net value

- Eliminates the only code path that creates synthetic members.
- Reduces surface area for future bugs ("why did this
  request-path helper return a synthetic?").
- Closes BL-005's read-side residual: there's no longer any
  request path that would expose newly-created synthetics.

## Diff budget

Net deletion. Estimate -300 lines, +20 lines (test adjustments).
