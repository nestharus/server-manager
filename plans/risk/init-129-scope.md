# INIT-129 — Scope risk gate

**Verdict:** LOW

## Diff scope (vs HEAD@98bfa77 INIT-128)

```
services/api/app/core/settings.py                  |   1 -
services/api/app/repositories/members.py           |   8 +-
services/api/app/services/applications.py          |  74 +-------
services/api/app/services/members.py               |  84 -----
services/api/tests/public_intake_fixtures.py       |   3 -
services/api/tests/test_public_intake_submit.py    |  18 +-
services/api/tests/test_public_intake_synthetic_member.py | 183 ----
research/17-init-129-dead-synthetic-path-scope.md  | (new)
plans/risk/init-129-{scope,shortcut,supported-surface}.md | (new)
plans/audit-history/init-129-audit-history.md      | (new)
plans/BACKLOG.md                                   |  (close BL-018)
7 files changed, 15 insertions(+), 356 deletions(-)
```

Net deletion of 341 lines.

## In scope

- Delete `submit_public_application` (legacy anonymous-flow service entry).
- Delete `_SubmissionAuthority` enum + `submission_authority` parameter
  on `_submit_application_internal`. Only USER remained after the
  receipt-required path took over; the conditional was a no-op shell.
- Delete `resolve_or_create_public_intake_member` helper +
  `PUBLIC_INTAKE_MEMBER_ACTOR` constant.
- Delete `PUBLIC_INTAKE_ACTOR`, `PUBLIC_INTAKE_MEMBER_SALT`,
  `PUBLIC_INTAKE_NAMESPACE` constants in applications.py.
- Drop `_kind` parameter from `_insert_member` /
  `_insert_member_on_discord_conflict_do_nothing` — only callers ever
  passed `'discord'` (default) post-INIT-128.
- Drop `public_intake_member_salt` setting (orphaned: never read).
- Delete `tests/test_public_intake_synthetic_member.py` (only tested
  the dead helper).
- Drop fixture `public_intake_member_guard` from
  `test_public_intake_submit.py` (defended against a now-impossible
  call path).

## Out of scope (preserved)

- `is_synthetic_member()` + every caller in
  `services/{applications,trust,roster,authority,members}.py` —
  defense-in-depth against the 18 historical synthetic rows in
  humility-local + any historical production data.
- `MemberKind = Literal["discord", "public_intake"]` — historical
  rows use `"public_intake"`; type must accept it.
- `SyntheticMemberGuardMemberFactory` test fixture — used by
  `test_applications.py` / `test_members.py` / `test_trust.py` to
  verify write-boundary guards.
- `authorize_public_intake` — Cedar policy gate, orthogonal.
- `PUBLIC_SUBMIT_SURFACE` constant — still referenced by
  `submit_public_application_with_receipt`.
- `members.kind` schema column + check constraint — INIT-125A
  delivered; no migration changes.

## Risk surface

- **Behavioral change:** the synthetic-member rejection in
  `_submit_application_internal` previously gated on
  `submission_authority != PUBLIC_INTAKE`. Now it always rejects.
  Equivalent because the only PUBLIC_INTAKE caller
  (`submit_public_application`) is deleted in this slice.
- **Schema change:** none. Migrations untouched.
- **API surface change:** none. The endpoint
  `POST /api/v1/public/applications` keeps its receipt-required
  contract from INIT-128.
- **Test coverage:** removed tests (TG-2 from INIT-120's synthetic
  helper) target dead code; equivalent coverage exists in
  `test_applications.py::test_authenticated_submit_rejects_synthetic_applicant`
  + `test_synthetic_member_helper.py`.

## Verdict

LOW — deletion is bounded to dead code reachable only from the
removed entry points; defense-in-depth guards remain.
