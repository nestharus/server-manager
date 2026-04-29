# Proposal 11 — INIT-132 / BL-019C: application transcript endpoint

## Goal

Read-only endpoint `GET /api/v1/applications/{id}/transcript`
that returns a chronological merge of:
- application state changes (claim/transition events from
  `activity_state_changes` filtered to
  `aggregate_type='application'`, `aggregate_id=<id>`)
- application messages (from the new `application_messages`
  table — INIT-131)

with per-viewer visibility filtering. The applicant sees their
own state-change events + `applicant_visible` messages. An
officer with `application.message` permission at the
application's target_scope sees state changes + both visibilities
of messages.

## Q1..Q5 — locked

**Q1.** Single chronological list, sorted by occurrence time
(state changes use `recorded_at`; messages use `created_at`).
Type-discriminated entries:
```json
{
  "type": "state_change",
  "occurred_at": "...",
  "from_state": "queued",
  "to_state": "claimed",
  "actor_kind": "user",
  "actor_id": "<member uuid>",
  "change_type": "application.transitioned"
}
```
or:
```json
{
  "type": "message",
  "occurred_at": "...",
  "message_seq": 3,
  "author_actor_kind": "user",
  "author_actor_id": "<member uuid>",
  "visibility": "applicant_visible",
  "body_markdown": "..."
}
```

**Q2.** Authorization:
- Applicant identity (member referenced by
  `applications.applicant_id`): allowed; messages filtered to
  `applicant_visible`.
- Actor with `application.message` permission at the
  application's target_scope: allowed; messages include both
  visibilities.
- Else: 403 `application_transcript_forbidden`.

This mirrors `read_application_messages` exactly and reuses
the same authorization shape.

**Q3.** Endpoint mounted at the same applications router:
- `GET /api/v1/applications/{application_id}/transcript`
- 200 with `ApplicationTranscriptRead`
- 404 `application_not_found` if no such application
- 403 `application_transcript_forbidden` if viewer has no
  applicant identity AND no permission

**Q4.** No new schema. Uses existing
`activity_state_changes` + `application_messages` tables.

**Q5.** Pagination/limit: out of scope for v1. Applications are
short-lived (submitted → decided in days/weeks); transcript
volume is bounded. Add limits later if needed. The query joins
+ ORDER BY in SQL with no LIMIT.

## Scope

- new contract `ApplicationTranscriptEntry` (discriminated
  union: `state_change` | `message`) and
  `ApplicationTranscriptRead` (list of entries) in
  `services/api/app/contracts/applications_transcript.py`.
- new service
  `services/api/app/services/application_transcript.py`:
  - `read_application_transcript(db, *, application_id,
    viewer_actor_kind, viewer_actor_id)` returns
    `ApplicationTranscriptRead`.
  - reuses
    `services/application_messages.read_application_messages` for
    the message side (which already enforces visibility/auth);
    fetches state changes via a new repository read function;
    interleaves by occurred-at; builds the discriminated entry
    list.
- new repository read in
  `services/api/app/repositories/applications.py` (or a new
  module): function to list activity_state_changes rows for a
  given application aggregate, ordered by recorded_at ASC.
- endpoint in
  `services/api/app/api/v1/endpoints/applications/transcript.py`
  with the GET route.
- router include in
  `services/api/app/api/v1/endpoints/applications/__init__.py`.
- tests covering: applicant-view filters messages; officer-view
  includes both visibilities; stranger 403; correct chronological
  ordering when state changes and messages interleave; 404 on
  missing application.

## Anti-scope

- Pagination / limits — future.
- Notification fanout — orthogonal to transcript reads.
- Export formats (PDF, JSON download) — future.
- Real-time tail / WebSocket — future.
- SPA UI — INIT-133.
- Edits to message-append logic — none.
- Edits to state-machine logic — none.

## Net value

- BL-019D's SPA review page consumes this endpoint to render the
  full conversation+lifecycle history.
- Officer can audit decisions with a single GET; applicant gets
  a self-service record of their interaction.
- Foundation for the transcript export when/if needed.

## Risk gates (self-review, all LOW)

### Audit (LOW)
No incident; greenfield read-only endpoint.

### Scope (LOW)
Bounded to one new contract module, one new service, one new
repository function, one new endpoint, one router include. No
edits to existing application service logic, message logic,
state-change writers, or schema.

### Shortcut (LOW)
- Pagination omitted: applications are bounded; transcripts are
  small. Add later under load.
- `limit` parameter omitted: same reason.
- Reuses `read_application_messages` for message authorization
  rather than duplicating: deliberate; ensures consistency.

### Supported-surface (LOW)
- HTTP: net-new route; no existing route changes.
- DB: net-new SQL query; no schema change.
- Permissions: reuses `application.message` permission. No new
  permission name.

## Diff budget

~350 lines net add. No deletions.
