# BUG-5 — Supported-surface risk gate

**Verdict:** LOW

BUG-5 (local e2e cluster has no `chapter-alpha` row, so Playwright times
out on `selectOption("chapter-alpha")`) is repaired by adding one new
e2e-only seed helper at `infra/tests/e2e/lib/seed-chapter-fixture.mjs`
plus a small invocation block in `infra/tests/e2e/tests/19-web-ui.sh`
(proposal §3, §6). The fix lives entirely under `infra/tests/e2e/**`
and writes only to the existing `chapter_templates`, `chapters`, and
`aggregate_heads` tables already created by migrations
`wu-007a_chapter_templates_foundation.py`,
`wu-018_chapter_templates.py`, and `wu-019_chapter_lifecycle.py`. No
production service code, no public API behavior, no schema, no env
var, no GitOps Job, and no Pomerium/Authentik resource is touched
(proposal §5 anti-scope explicitly forbids each of these).

## Surfaces touched

### 1. Public API surface — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `GET /api/public/chapters` (`services/api/app/repositories/public_chapters.py:12-24`) | returns rows from `chapters WHERE state='active'`, ordered by `name`, limit 200 | unchanged route, query, ordering, and shape; the only delta is that the local e2e database now contains one matching active row — the endpoint reads it the same way it reads any other row | none — proposal §5 anti-scope: "Do not change `/api/public/chapters` behavior or ordering" |
| Chapter management endpoints (`services/api/app/api/v1/endpoints/chapter_templates.py`, `services/api/app/api/v1/endpoints/chapters/base.py`, `services/api/app/api/v1/endpoints/web.py`) | as defined today | unchanged — the e2e seed bypasses these endpoints and writes directly via `psql` through a CNPG primary pod (proposal §3, mirroring `seed-authority-grants.mjs`) | none — proposal §5: "Do not add an admin chapter creation flow" |
| Public submit (`POST /api/public/applications`) | accepts `scope.scope_kind="chapter"` + `scope.scope_id="chapter-alpha"` per `contract.json:143-154` | unchanged endpoint contract; the fixture only makes the row that the SPA dropdown points at exist | none |
| Service layer (`services/api/app/services/chapters.py`, `services/api/app/services/web.py`) | as today | not modified — proposal §3 explicitly limits the change to one `infra/tests/e2e/lib/*.mjs` helper plus a shell-script edit | none |

Risk on §1: **none** — gate criterion 1 (no public API change) holds.
The fix introduces no new endpoint, no new field, no new query, and no
behavior change in any existing endpoint.

### 2. Database tables touched — only existing tables, no schema change

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `chapter_templates` | created by `migrations/versions/wu-007a_chapter_templates_foundation.py:16-48` (`id` UUID PK, `name`, `schema_version`, `channel_structure`/`role_structure`/`default_permission_intents` JSONB, `created_at`); template family columns added by `wu-018_chapter_templates.py:16-41` | one fixture row inserted: `id` = deterministic UUID derived from seed key `e2e-template`, `template_family_id` = same UUID, `version` = 1, `schema_version` = 1, empty `[]::jsonb` for the three structure columns (proposal §2 Q4) — exactly the shape used by `services/api/tests/chapter_selector_fixtures.py:33-48` | none — schema unchanged; row matches the existing migration column types; UUID column accepts deterministic UUID; idempotent guards in proposal §2 Q2 reject any pre-existing row with a different shape rather than overwrite |
| `chapters` | created by `wu-019_chapter_lifecycle.py:17-56` (`id` TEXT PK, `name` TEXT, `template_id` UUID NOT NULL FK→`chapter_templates.id` ON DELETE RESTRICT, `template_snapshot` JSONB NOT NULL, `configuration` JSONB default `'{}'`, `state` TEXT with CHECK `state IN ('proposed','provisioning','active','provisioning_failed')`, `discord_resources` JSONB default `'{}'`, `created_at` default CURRENT_TIMESTAMP); unique LOWER(name) index | one fixture row inserted: `id='chapter-alpha'`, `name='Alpha Chapter'`, `template_id` = the UUID just inserted into `chapter_templates`, `template_snapshot` = JSON object referencing that template id and version, `state='active'`, defaults for `configuration`/`discord_resources`/`created_at` (proposal §2 Q3, Q4, Q6, §3) | none — TEXT id matches contract literal `chapter-alpha` (`contract.json:102-121`); FK satisfied because the template row is inserted first within the same transaction (proposal §3 SQL shape lists `inserted_template` before `inserted_chapter`); `state='active'` satisfies the CHECK; LOWER(name) uniqueness is unaffected because `Alpha Chapter` is the only row in the local cluster |
| `aggregate_heads` | already used by INIT-135 unit fixture (`services/api/tests/chapter_selector_fixtures.py:70-81`); admin chapter listing joins `chapters` to `aggregate_heads` (RCA §6) | one fixture row inserted: `aggregate_type='chapter'`, `aggregate_id='chapter-alpha'`, `current_seq=1`, `latest_change_id=NULL` (proposal §2 Q5) — identical to the unit-test fixture shape | none — no schema change; row references the chapter id inserted in the same transaction |

Risk on §2: **none** — gate criterion 2 (uses only existing tables) and
criterion 6 (foreign-key references valid) both hold. The fixture
inserts in the order `chapter_templates` → `chapters` → `aggregate_heads`
inside one transaction, so the `chapters.template_id` FK to
`chapter_templates.id` is satisfied before the chapter row commits, and
the `aggregate_heads('chapter', 'chapter-alpha')` row references the
chapter id that the same transaction just inserted. The chapter id
literal `chapter-alpha` matches `contract.json:104` and `:120`
(`form.chapters.selected_id` and `form.fields[0].value`), so the row
the helper writes is exactly the row the SPA dropdown and Playwright
expect.

### 3. Database schema / migrations — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Alembic head (`migrations/versions/...`) | current head | unchanged — proposal §5 anti-scope: "Do not add an Alembic migration" | none |
| Column definitions on `chapter_templates`, `chapters`, `aggregate_heads` | as defined by `wu-007a`, `wu-018`, `wu-019` | unchanged — proposal writes data only, no DDL | none |
| Constraints (FK `chapters.template_id → chapter_templates.id`, CHECK `chapters_state_valid`, unique `LOWER(name)`, PK constraints) | as defined | unchanged; satisfied by the seeded row values listed above | none |

Risk on §3: **none** — gate criterion 4 (no DB migrations) holds.

### 4. Environment variables — none added

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `KUBECONFIG_PATH` / `KUBECONFIG` | already required and read by `infra/tests/e2e/lib/seed-authority-grants.mjs:7-18` | reused verbatim by the new helper (proposal §3 "It should follow the execution pattern already used by `seed-authority-grants.mjs`") | none — pre-existing variable, no new env var introduced |
| `E2E_APPLICATION_SCOPE_KIND` / `E2E_APPLICATION_SCOPE_ID` | already provided by `seed-authority-grants.mjs:13-14` | proposal §3 step 4 reuses the existing scope parameters of `seed-authority-grants.mjs` for chapter-scoped officer authority — no new variable name introduced | none — pre-existing variables; the proposal explicitly states "This does not extend the authority helper; it uses the scope parameters it already provides" (proposal §3 step 4) |
| API/web service env (`VITE_API_BASE_URL`, etc.) | as today | unchanged | none |

Risk on §4: **none** — gate criterion 3 (no env vars) holds. The fix
introduces zero new environment variables; it consumes only variables
that already exist on the `seed-authority-grants.mjs` execution surface.

### 5. GitOps surface — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `gitops/channels/local/applications/server-manager/kustomization.yaml` | lists `alembic-migration-job.yaml` and `seed-public-intake-form.yaml` (RCA §2) | unchanged — proposal §2 Q1 explicitly rejects Option b (a new GitOps Job) and proposal §5 anti-scope: "Do not add a GitOps Job or kustomization resource for this e2e-only fixture" | none |
| `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml` | seeds the global public form (RCA §2) | not modified — the chapter fixture is owned by e2e setup, not GitOps bootstrap | none |
| Local cluster bring-up (`infra/scripts/bring-up-local-channel.sh`, etc.) | as today | unchanged — proposal §3 only edits `infra/tests/e2e/tests/19-web-ui.sh` for the seed invocation | none |

Risk on §5: **none** — gate criterion 5 (no GitOps changes) holds.

### 6. Pomerium / Authentik — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `gitops/channels/local/auth/pomerium/**` | as checked in | unchanged | none |
| `gitops/channels/local/auth/authentik/**` | as checked in | unchanged | none |
| OAuth round-trip / route allowlist / claim headers | unchanged | unchanged | none |

Risk on §6: **none** — gate criterion 5 (no Pomerium/Authentik changes)
holds. The fix is entirely below the auth boundary; the seeded officer
identity continues to authenticate exactly as it does today via the
existing `seed-authority-grants.mjs` flow.

### 7. Foreign-key and contract identity verification

| Reference | Source | Target | Verification |
|---|---|---|---|
| `chapters.template_id` (UUID, NOT NULL, ON DELETE RESTRICT) | `wu-019_chapter_lifecycle.py:21,46-50` | `chapter_templates.id` (UUID PK) | satisfied: the seed inserts `chapter_templates(id=<deterministic UUID>)` in the same transaction *before* `chapters(template_id=<same UUID>)` (proposal §3 SQL shape: `inserted_template` precedes `inserted_chapter`) |
| `chapters.id` literal | proposal §2 Q3 | `infra/tests/fixtures/web-ui/contract.json:104` (`selected_id`), `:109` (chapter list response), `:120` (`field.value`), `:150` (`scope.scope_id`) | identical literal `chapter-alpha`; helper asserts exact match against contract on every run (proposal §3 "If the contract changes, this seed should fail instead of silently creating a fixture that no longer matches the browser flow") |
| `chapters.name` literal | proposal §2 Q4 / §3 | `contract.json:105`, `:110` | identical literal `Alpha Chapter` |
| `aggregate_heads(aggregate_type, aggregate_id)` | proposal §2 Q5 | `('chapter', 'chapter-alpha')` matching the chapter row id | satisfied within the same transaction; matches the unit-test fixture shape at `services/api/tests/chapter_selector_fixtures.py:70-81` |
| `chapters.state` | proposal §2 Q6 | CHECK `state IN ('proposed','provisioning','active','provisioning_failed')` (`wu-019_chapter_lifecycle.py:52-55`); public endpoint filters `WHERE state='active'` (`public_chapters.py:18`) | `'active'` satisfies the CHECK and the public list filter |
| `chapter_templates` row identity | proposal §2 Q4 | columns defined in `wu-007a_chapter_templates_foundation.py:16-48` plus family columns from `wu-018` | UUID `id`, UUID `template_family_id` (same value), `version=1`, `schema_version=1`, empty JSONB structure arrays; identical shape used in `services/api/tests/chapter_selector_fixtures.py:33-48` |

Risk on §7: **none** — gate criterion 6 (FK references valid,
`template_id` exists, `chapter id` matches contract) holds. The
fail-closed guard described in proposal §2 Q2 / §3 (`fail_closed_guard`
CTE) explicitly aborts rather than silently overwriting if any
pre-existing row has an incompatible shape, so a partial pre-existing
state cannot produce a dangling FK or a contract mismatch on re-run.

## Supported-surface findings summary

| Gate | Verdict |
|---|---|
| 1. No public API change | PASS |
| 2. Uses existing `chapter_templates` / `chapters` / `aggregate_heads` tables — no schema changes | PASS |
| 3. No env vars | PASS |
| 4. No DB migrations | PASS |
| 5. No GitOps / Pomerium / Authentik changes | PASS |
| 6. Seeded fixture rows have valid foreign-key references (`template_id` exists, `chapter id` matches contract) | PASS |

## Out-of-scope items intentionally not addressed

- Chapter authority/grants beyond the existing `seed-authority-grants.mjs`
  scope (proposal §5 anti-scope).
- Discord roles or channels for the seeded chapter (proposal §5).
- Modifications to `services/api/tests/chapter_selector_fixtures.py`
  (proposal §5).
- Promotion of the e2e fixture into a GitOps Job or kustomization
  resource (proposal §2 Q1 rejected Option b; proposal §5 anti-scope).
- The chapter-scoped officer authority reuse of `seed-authority-grants.mjs`
  (proposal §3 step 4) consumes the helper's pre-existing
  `E2E_APPLICATION_SCOPE_KIND` / `E2E_APPLICATION_SCOPE_ID` parameters
  rather than adding new env vars or extending the helper.

## Verdict

**LOW** — the fix is an e2e-only data seed that writes three rows
(`chapter_templates`, `chapters`, `aggregate_heads`) into the existing
schema using a transaction with FK-ordered inserts and a fail-closed
guard. It changes no public API, no schema, no env var, no GitOps
manifest, and no auth resource, and the seeded identity exactly
matches the values already hardcoded in
`infra/tests/fixtures/web-ui/contract.json`.

SUPPORTED_SURFACE_DONE: plans/risk/bug-5-supported-surface.md
