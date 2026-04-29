# INIT-129 — Supported-surface risk gate

**Verdict:** LOW

## Surfaces touched

### 1. HTTP API

| Surface | Pre-INIT-129 | Post-INIT-129 | Risk |
|---|---|---|---|
| POST /api/v1/public/applications | receipt-required (INIT-128) | receipt-required (unchanged) | none |
| POST /api/v1/applications | authenticated user submit | authenticated user submit (unchanged) | none |
| GET/PATCH /api/v1/members/{id} | unchanged | unchanged | none |
| /auth/discord/* | unchanged | unchanged | none |

No HTTP surface changes.

### 2. Python module surface

| Symbol | Pre | Post |
|---|---|---|
| `app.services.applications.submit_application` | exported | unchanged |
| `app.services.applications.submit_public_application_with_receipt` | exported | unchanged |
| `app.services.applications.submit_public_application` | exported | **REMOVED** |
| `app.services.applications.PUBLIC_INTAKE_*` constants | exported | **REMOVED** |
| `app.services.applications._SubmissionAuthority` | private | **REMOVED** |
| `app.services.members.resolve_or_create_real_discord_member` | exported | unchanged |
| `app.services.members.resolve_or_create_public_intake_member` | exported | **REMOVED** |
| `app.services.members.is_synthetic_member` | exported | unchanged |
| `app.services.members.PUBLIC_INTAKE_MEMBER_ACTOR` | exported | **REMOVED** |
| `app.repositories.members._insert_member(_kind=...)` | private kw | **kw removed** |
| `app.core.settings.Settings.public_intake_member_salt` | field | **REMOVED** |

All removed symbols had no callers outside the deleted code. Verified
via grep across `services/api/app/`, `services/api/tests/`,
`services/discord/`, `daemon/`. No external (out-of-API) consumers
exist for these symbols — they were always API-internal.

### 3. Database schema

No changes. `members.kind` column + check constraint from
INIT-125A unchanged. No migrations added.

### 4. Settings / configuration

`public_intake_member_salt` removed. It was never read anywhere in
production code (verified by grep `settings.public_intake_member_salt`,
zero matches). If any downstream env var
`API_PUBLIC_INTAKE_MEMBER_SALT` was being set in deployment
manifests, it becomes a no-op (Pydantic's BaseSettings tolerates
unknown env vars by default).

Verified GitOps manifests:
- `gitops/channels/local/applications/server-manager/runtime-infisicalsecret.yaml`
  — does NOT set `API_PUBLIC_INTAKE_MEMBER_SALT`
- `gitops/channels/local/applications/server-manager/api-deployment.yaml`
  — does NOT reference the removed setting

### 5. Test fixtures shared with downstream tooling

`public_intake_fixtures.PUBLIC_MEMBER_SALT`, `PUBLIC_INTAKE_ACTOR_KIND`,
`PUBLIC_INTAKE_ACTOR_ID` constants removed. These were only used by
the deleted `test_public_intake_synthetic_member.py` (verified via
grep). No other consumers.

### 6. CLI / scripts / e2e

No changes. e2e remains 19/19.

## Verdict

LOW — every removed symbol's call surface is internal and verified
empty before deletion. Schema unchanged. HTTP surface unchanged.
