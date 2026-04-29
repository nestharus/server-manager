# INIT-132 — Scope risk gate

**Verdict:** LOW

## In scope

- New contract `applications_transcript.py` with discriminated
  state-change / message entry types and the
  `ApplicationTranscriptRead` envelope.
- New repository function `list_application_state_changes` that
  reads `activity_state_changes` rows for a given application
  aggregate, joined with the originating `activity_actions` row
  for actor attribution.
- New service `application_transcript.py` with
  `read_application_transcript(...)` that:
  - confirms the application exists
  - delegates message-side authorization to
    `read_application_messages` (INIT-131) — reusing its
    visibility filtering and forbidden-error semantics
  - merges state changes + messages chronologically
- New endpoint
  `GET /api/v1/applications/{id}/transcript` with the standard
  error mapping (404 / 403).
- Router include in
  `endpoints/applications/__init__.py`.

## Out of scope

- Pagination / limit parameters (transcripts are bounded;
  add later if needed).
- Export formats (PDF, JSON download).
- Real-time tail / WebSocket.
- Notification fanout on transcript events.
- SPA UI (INIT-133).
- Edits to message-append logic.
- Edits to state-machine logic.
- Schema changes (none — read-only over existing tables).

## Risk surface

- **HTTP additions:** one new route; no existing route changes.
- **Schema:** none. SELECT-only over existing tables.
- **Authorization:** reuses INIT-131's
  `application.message` permission via
  `read_application_messages`.
- **Behavioral change to existing flows:** none.

## Verdict

LOW — purely additive; no edits to any existing service or
schema; reuses INIT-131's auth surface.
