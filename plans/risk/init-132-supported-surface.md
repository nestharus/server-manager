# INIT-132 — Supported-surface risk gate

**Verdict:** LOW

## Surfaces touched

### 1. HTTP API

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `GET /api/v1/applications/{id}/transcript` | n/a | new (200 / 404 / 403) | additive |
| Existing application routes | unchanged | unchanged | none |

### 2. Database schema

No changes. SELECT-only against existing tables:
- `activity_state_changes` (filtered to
  `aggregate_type='application'`)
- `activity_actions` (joined for actor attribution)
- `application_messages` (read via
  `read_application_messages`)
- `applications` (existence check)

### 3. Permissions

No new permission. Reuses `application.message` via
`read_application_messages`.

### 4. Python module surface

Net-new exports:
- `app.contracts.applications_transcript.{ApplicationTranscriptStateChangeEntry, ApplicationTranscriptMessageEntry, ApplicationTranscriptEntry, ApplicationTranscriptRead}`
- `app.services.application_transcript.read_application_transcript`
- `app.repositories.applications.list_application_state_changes`
  (extension)
- `app.api.v1.endpoints.applications.transcript.router`

Existing modules: only the router include line in
`endpoints/applications/__init__.py` is edited.

### 5. SPA / Discord / external consumers

- SPA: net-new endpoint to consume; INIT-133 will integrate.
- Discord: not touched.
- GitOps / Pomerium / Cedar: existing
  `/api/v1/applications/*` route inherits the new sub-resource.
- Authz / authority grants: reuses existing infra.

## Verdict

LOW — additive across every surface.
