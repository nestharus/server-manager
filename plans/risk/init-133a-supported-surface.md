# INIT-133A — Supported-surface risk gate

**Verdict:** LOW

## Surfaces touched

### 1. HTTP API

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `GET /api/v1/applications` | n/a (no list route exists) | new (200 / 422 / 403) | additive |
| `GET /api/v1/applications/{id}` | unchanged | unchanged | none — verify FastAPI routes the empty-path GET before the path-param GET |
| `POST /api/v1/applications` | unchanged | unchanged | none |
| `POST /api/v1/applications/{id}/transitions` | unchanged | unchanged | none |
| `POST /api/v1/applications/{id}/messages` (INIT-131) | unchanged | unchanged | none |
| `GET /api/v1/applications/{id}/transcript` (INIT-132) | unchanged | unchanged | none |

FastAPI matches routes in registration order. The new
`@router.get("")` MUST be registered before `@router.get("/{application_id}")`
in `lifecycle.py` to avoid the path-param route swallowing
empty-path requests. The 6c agent must verify this.

### 2. Database schema

No changes. SELECT-only with optional WHERE clauses against the
existing `applications` + `aggregate_heads` join.

### 3. Permission namespace

No new permission. Reuses `application.{claim,review,approve,
deny,waitlist,reactivate,withdraw}` set.

### 4. Python module surface

| Symbol | Pre | Post |
|---|---|---|
| `app.contracts.applications.ApplicationListRead` | n/a | exported |
| `app.repositories.applications.list_applications` | n/a | exported |
| `app.services.applications.list_applications` | n/a | exported |
| `app.services.applications.ApplicationListForbiddenError` | n/a | exported |
| Existing application contracts/repos/services | unchanged | unchanged |

### 5. SPA / Discord / external consumers

- SPA: net-new endpoint to consume; INIT-133B will integrate.
- Discord daemon: not touched.
- Pomerium / Cedar: existing `/api/v1/applications/*` route
  inherits the new sub-resource.

### 6. Authority grants

No changes. The list endpoint requires the same permissions an
officer already needs to operate on individual applications.

## Verdict

LOW — additive across every surface.
