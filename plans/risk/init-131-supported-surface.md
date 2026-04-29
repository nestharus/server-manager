# INIT-131 — Supported-surface risk gate

**Verdict:** LOW

## Surfaces touched

### 1. HTTP API

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `POST /api/v1/applications/{id}/messages` | n/a | new (201 / 404 / 422 / 403) | additive |
| `GET /api/v1/applications/{id}/messages` | n/a | new (200 / 404 / 403) | additive |
| Existing application routes (lifecycle, transitions, forms, public submit, etc.) | unchanged | unchanged | none |
| Existing authority-grant endpoint | unchanged | unchanged | none — chapter admins use it as-is to grant `application.message` |

### 2. Database schema

| Object | Change |
|---|---|
| `application_messages` (table) | new |
| `applications.id` FK target | new (ON DELETE RESTRICT) |
| Existing tables | unchanged |
| Migration head | `wu_043_members_kind` → `wu_044_application_messages` |

Migration is a clean append on the linear chain. No table
alterations, no backfills. Downgrade drops the table cleanly.

### 3. Permission namespace

New canonical permission `application.message`. Sibling of the
existing `application.review`, `application.claim`, etc. Granted
the same way as those (`POST /api/v1/authority-grants`).

### 4. Python module surface

| Symbol | Pre | Post |
|---|---|---|
| `app.contracts.application_messages.*` | n/a | exported |
| `app.repositories.application_messages.*` | n/a | private repo functions |
| `app.services.application_messages.*` | n/a | exported |
| `app.api.v1.endpoints.applications.messages.router` | n/a | exported, mounted |
| Existing `app.services.applications.*` | unchanged | unchanged |
| Existing `app.contracts.applications.*` | unchanged | unchanged |

No breaking changes to internal Python surface.

### 5. SPA / Discord / external consumers

- SPA: not touched. INIT-133 will consume the new endpoints.
- Discord daemon: not touched. The legacy `interview_thread_id`
  field remains for any code path that still sets/reads it.
- Pomerium / Authentik / Cedar: not touched. Existing route
  matches `/api/v1/applications/*` and the new sub-resource
  inherits the same auth boundary.
- GitOps manifests: not touched.

### 6. Test surface

Four new test files under `services/api/tests/`:
- `test_application_messages_service.py`
- `test_application_messages_endpoint.py`
- `test_application_messages_repository.py`
- `test_application_messages_migration.py`

All pass on the INIT-131 baseline (21 tests). No edits to
existing tests.

## Verdict

LOW — purely additive across HTTP, schema, permissions, Python
modules, and external surfaces. No deprecations, no behavioral
shifts.
