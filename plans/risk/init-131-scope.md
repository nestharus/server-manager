# INIT-131 — Scope risk gate

**Verdict:** LOW

## Diff scope

```
migrations/versions/wu-044_application_messages.py            (new)
services/api/app/contracts/application_messages.py            (new)
services/api/app/repositories/application_messages.py         (new)
services/api/app/services/application_messages.py             (new)
services/api/app/api/v1/endpoints/applications/messages.py    (new)
services/api/app/api/v1/endpoints/applications/__init__.py   (router include)
services/api/tests/test_application_messages_*.py             (new, 4 files)
proposals/10-application-messages.md                          (new)
plans/risk/init-131-{scope,shortcut,supported-surface}.md     (new)
plans/audit-history/init-131-audit-history.md                 (new)
research/18-bl-019-substrate-audit.md                         (existing — committed earlier)
```

Plus a one-line fixture-idempotency fix in
`services/api/tests/test_application_messages_service.py`'s
`_grant` helper to swallow `DuplicateActiveGrantError` so the
TG-2 chapter-isolation test can publish two forms with the same
operator at global scope. The fix preserves test intent (no
weakening of any assertion).

## In scope

- New `application_messages` table mirror of `ticket_messages`
  shape with applicant_visible / officer_only visibility.
- Service-layer authorization split: applicant authors via
  applicant_id match; everyone else needs the new
  `application.message` permission at the application's
  target_scope.
- POST + GET endpoints under
  `/api/v1/applications/{id}/messages`.
- Idempotency on `client_message_id`.
- Read-side visibility filtering.

## Out of scope

- SPA UI (BL-019D / INIT-133).
- Transcript merging with state changes (BL-019C / INIT-132).
- Notification fanout on message append (future).
- Retention/redaction policy (future).
- Real-time delivery (future).
- File attachments (future).
- Migration of existing `interview_thread_id` → application_messages
  for historical applications (future, if ever).

## Risk surface

- **Schema additions:** one new table, no edits to existing tables.
  Migration is a clean alembic upgrade from `wu_043_members_kind`.
- **Authorization additions:** one new permission name
  `application.message`. Granted via the existing
  `POST /api/v1/authority-grants` endpoint by chapter admins.
- **HTTP additions:** two new routes; no existing route changes.
- **Behavioral change to existing flows:** none. Application
  lifecycle, claim/transition, and `interview_thread_id` are
  untouched.

## Verdict

LOW — purely additive surface; no edits to existing application
service or endpoint code beyond the router include line; clean
migration chain; tests cover happy path + visibility + scope
isolation + idempotency.
