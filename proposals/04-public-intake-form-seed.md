READ:
- /home/nes/ai/workflows/implementation-pipeline.md
- .tmp/rca/public-intake-form-seed-FINDINGS.md
- research/06-public-intake-form-seed-problem-map.md
- proposals/02-public-application-intake.md
- services/api/app/services/forms.py
- services/api/app/repositories/forms.py
- services/api/app/api/v1/endpoints/applications/forms.py
- services/api/app/contracts/applications.py
- services/api/app/services/applications.py
- services/api/app/services/mutations.py
- services/api/app/repositories/mutations.py
- migrations/versions/wu-002_activity_substrate.py
- migrations/versions/wu-003a_widen_aggregate_id.py
- migrations/versions/wu-003b_audit_context_columns.py
- migrations/versions/wu-021_forms.py
- migrations/versions/wu-022_applications.py
- migrations/versions/wu-031_read_models.py
- migrations/versions/wu-029a_notifications.py
- migrations/versions/wu-037_ticket_sla_triggers.py
- services/api/tests/public_intake_fixtures.py
- infra/tests/fixtures/web-ui/contract.json
- gitops/channels/local/applications/server-manager/alembic-migration-job.yaml
- gitops/channels/local/applications/server-manager/object-storage-bucket-job.yaml
- gitops/channels/local/applications/server-manager/kustomization.yaml
- infra/tests/e2e/lib/bringup.sh

## Summary

Add a local-channel, idempotent, one-shot GitOps Job that seeds the canonical two-field public-intake application form into Postgres after Alembic has created the form and mutation substrate. The Job writes the `form_definitions` current global row and the matching `application_form|global|` aggregate action, state-change, and head rows, so both the public submit path and the authenticated current-form lookup see the same seeded form. It skips without replacement when an officer-published current global form already exists, preserving operator ownership of live form content.

## Net-value statement

This proposal reduces the current supported-surface risk that fresh `humility-local` bringup exposes the INIT-120 public web/API intake path but has no current global form, causing `/api/v1/public/applications` to fail at form lookup instead of creating an application (`.tmp/rca/public-intake-form-seed-FINDINGS.md`; `services/api/app/services/applications.py`; `proposals/02-public-application-intake.md`). The added blast radius is a local GitOps Job with direct database write authority over `form_definitions`, `activity_actions`, `activity_state_changes`, and `aggregate_heads`, plus operational rollback decisions for seeded state that may later be referenced by applications (`migrations/versions/wu-022_applications.py`). The value is positive because the write is local-only, deterministic, no-op safe, does not replace officer-published content, and closes a real fresh-bringup failure on a supported public surface.

## Scope

- Add `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml` containing a ConfigMap-mounted seed payload and a one-shot Job.
- Add that manifest to `gitops/channels/local/applications/server-manager/kustomization.yaml`.
- Use a tiny image with `psql`, preferably the already mirrored local e2e Postgres image `mirror.gcr.io/bitnamilegacy/postgresql:16.2.0-debian-11-r16` (`infra/tests/e2e/lib/bringup.sh`).
- Read `DATABASE_URL` from the existing `server-manager-postgres-url` Secret, matching the Alembic Job (`gitops/channels/local/applications/server-manager/alembic-migration-job.yaml`).
- Seed the canonical INIT-120 global form with fields `character_name` short required and `application_text` long required, using the fixture-visible labels and max lengths from `services/api/tests/public_intake_fixtures.py` and `infra/tests/fixtures/web-ui/contract.json`.
- Insert the corresponding accepted mutation rows for aggregate type `application_form`, aggregate id `application_form|global|`, aggregate sequence `1`, and `form.published` state.
- Add implementation tests later for rendered GitOps, SQL idempotency, API current-form lookup, public submit recovery, and operator-published skip behavior.

## Anti-scope

- No change to Discord application form flows or Discord-visible behavior.
- No Authentik or Pomerium change.
- No INIT-120 public route or public request/response contract change.
- No change to authenticated `/api/v1/application-forms/*` endpoint behavior.
- No form-authoring UI or officer workflow change.
- No remote-channel apply; remote remains deferred to BL-013.
- No YAML `forms/` runtime source of truth. Postgres remains the runtime form source.
- No migration-based seed and no Alembic downgrade hook for this form.
- No replacement, archiving, or mutation of a different current global form.

## Implementation decisions taken in proposal

- Q1, ownership: seed as a separate local GitOps one-shot Job, not an Alembic migration. This matches the locked RCA direction and keeps local operational content independently rerunnable from schema lifecycle.
- Q2, write path: use direct SQL, not the authenticated form API. Direct SQL avoids adding a temporary service authority path solely for bootstrap, but must write the projection and mutation substrate together because `get_current_form_for_scope()` joins `form_definitions` to `aggregate_heads` (`services/api/app/repositories/forms.py`).
- Q3, content source: keep form content inline in the Job's ConfigMap-mounted payload. This makes the local bootstrap self-contained while Postgres remains the runtime source of truth.
- Q4, conflict behavior: insert only when no current global form exists; no-op when the deterministic seed row already exists; skip when any different current global form exists. This prevents a seed rerun from overwriting officer-published state.
- Job image: use a tiny `psql` image, preferably `mirror.gcr.io/bitnamilegacy/postgresql:16.2.0-debian-11-r16`, because it is already mirrored by local e2e bringup.
- Idempotency: derive the seed id from `sha256("init-122:public-intake-global:v1")` truncated to 16 bytes and rendered as a UUID; compare a deterministic content hash of the expected form fields, routing rules, and publisher metadata when that row already exists.
- Aggregate head: insert both `form_definitions` and the accepted `application_form` action/state/head rows. The shape follows the idempotent seed style in `migrations/versions/wu-031_read_models.py` and `migrations/versions/wu-029a_notifications.py`, while using the mutation row contract implemented by `services/api/app/services/forms.py` and `services/api/app/services/mutations.py`.

## Design

The implementation adds `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`. The file contains a `ConfigMap` named `server-manager-public-intake-form-seed` with `seed.sql`, and a `batch/v1` Job named `server-manager-seed-public-intake-form`. The Job mounts the ConfigMap read-only, reads `DATABASE_URL` from `server-manager-postgres-url`, runs `/bin/sh -ec`, waits for the required migrated tables/columns to exist, then executes `psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f /seed/seed.sql`. It uses the same non-root, read-only-root-filesystem posture as the existing Alembic and bucket Jobs where the image supports it (`gitops/channels/local/applications/server-manager/alembic-migration-job.yaml`; `gitops/channels/local/applications/server-manager/object-storage-bucket-job.yaml`).

Kustomization integration is a single new resource entry after `alembic-migration-job.yaml`:

```yaml
resources:
  - alembic-migration-job.yaml
  - seed-public-intake-form.yaml
```

File order is not treated as the only ordering control. The seed Job must have its own readiness gate because the current local Flux Kustomization applies sibling resources together and waits after apply (`gitops/flux/humility-local.yaml`). The Job's shell loop should poll Postgres until `form_definitions`, `activity_actions`, `activity_state_changes`, and `aggregate_heads` exist with the post-migration text `aggregate_id` shape (`migrations/versions/wu-003a_widen_aggregate_id.py`; `migrations/versions/wu-021_forms.py`). If those relations never appear, the Job fails and Kubernetes retry/backoff handles the same way the existing one-shot Jobs do.

The ConfigMap keeps the seed payload inline. The expected fields are:

```json
[
  {"id": "character_name", "type": "short", "label": "Character name", "required": true, "max_length": 64},
  {"id": "application_text", "type": "long", "label": "Application text", "required": true, "max_length": 4000}
]
```

The expected routing rules are:

```json
{"schema_version": 1, "queue": "chapter_officers", "review_scope": {"scope_kind": "global", "scope_id": null}}
```

The SQL shape is a single transaction with CTEs:

```sql
BEGIN;

WITH seed AS (
  SELECT
    (
      substr(seed_hex, 1, 8) || '-' ||
      substr(seed_hex, 9, 4) || '-' ||
      substr(seed_hex, 13, 4) || '-' ||
      substr(seed_hex, 17, 4) || '-' ||
      substr(seed_hex, 21, 12)
    )::uuid AS form_id,
    'application_form'::text AS aggregate_type,
    'application_form|global|'::text AS aggregate_id,
    'global'::text AS scope_kind,
    NULL::text AS scope_id,
    1::bigint AS form_version,
    'Public Application'::text AS name,
    'chapter_membership'::text AS target_type,
    '[{"id":"character_name","type":"short","label":"Character name","required":true,"max_length":64},{"id":"application_text","type":"long","label":"Application text","required":true,"max_length":4000}]'::jsonb AS fields,
    '{"schema_version":1,"queue":"chapter_officers","review_scope":{"scope_kind":"global","scope_id":null}}'::jsonb AS routing_rules,
    'service'::text AS actor_kind,
    'public-intake-seed'::text AS actor_id,
    'gitops:local/server-manager/seed-public-intake-form'::text AS request_surface,
    gen_random_uuid() AS correlation_id,
    CURRENT_TIMESTAMP AS published_at
  FROM (
    SELECT encode(digest('init-122:public-intake-global:v1', 'sha256'), 'hex') AS seed_hex
  ) h
),
seed_with_hash AS (
  SELECT
    seed.*,
    encode(
      digest(
        jsonb_build_object(
          'name', name,
          'target_type', target_type,
          'scope_kind', scope_kind,
          'scope_id', scope_id,
          'version', form_version,
          'fields', fields,
          'routing_rules', routing_rules,
          'published_by_kind', actor_kind,
          'published_by_id', actor_id
        )::text,
        'sha256'
      ),
      'hex'
    ) AS expected_content_hash
  FROM seed
),
current_global AS (
  SELECT id
  FROM form_definitions
  WHERE scope_kind = 'global'
    AND scope_id IS NULL
    AND status = 'current'
  FOR UPDATE
),
existing_seed AS (
  SELECT
    f.id,
    f.status,
    encode(
      digest(
        jsonb_build_object(
          'name', f.name,
          'target_type', f.target_type,
          'scope_kind', f.scope_kind,
          'scope_id', f.scope_id,
          'version', f.version,
          'fields', f.fields,
          'routing_rules', f.routing_rules,
          'published_by_kind', f.published_by_kind,
          'published_by_id', f.published_by_id
        )::text,
        'sha256'
      ),
      'hex'
    ) AS actual_content_hash
  FROM form_definitions f
  JOIN seed_with_hash s ON f.id = s.form_id
  FOR UPDATE
),
inserted_form AS (
  INSERT INTO form_definitions (
    id,
    scope_kind,
    scope_id,
    version,
    name,
    target_type,
    fields,
    routing_rules,
    status,
    published_by_kind,
    published_by_id,
    published_at
  )
  SELECT
    form_id,
    scope_kind,
    scope_id,
    form_version,
    name,
    target_type,
    fields,
    routing_rules,
    'current',
    actor_kind,
    actor_id,
    published_at
  FROM seed_with_hash
  WHERE NOT EXISTS (SELECT 1 FROM current_global)
    AND NOT EXISTS (SELECT 1 FROM existing_seed)
  RETURNING id
),
inserted_action AS (
  INSERT INTO activity_actions (
    action_type,
    aggregate_type,
    aggregate_id,
    actor_kind,
    actor_id,
    correlation_id,
    causation_id,
    scope_kind,
    scope_id,
    request_surface,
    request_json,
    status,
    reason_text,
    error_metadata
  )
  SELECT
    'form.publish',
    aggregate_type,
    aggregate_id,
    actor_kind,
    actor_id,
    correlation_id,
    NULL,
    scope_kind,
    scope_id,
    request_surface,
    jsonb_build_object(
      'name', name,
      'target_type', target_type,
      'scope_kind', scope_kind,
      'scope_id', scope_id,
      'fields', fields,
      'routing_rules', routing_rules
    ),
    'accepted',
    'init-122 public-intake form seed',
    NULL
  FROM seed_with_hash
  WHERE EXISTS (SELECT 1 FROM inserted_form)
  RETURNING id
),
inserted_change AS (
  INSERT INTO activity_state_changes (
    action_id,
    aggregate_type,
    aggregate_id,
    aggregate_seq,
    change_type,
    payload_json,
    diff_json
  )
  SELECT
    inserted_action.id,
    seed_with_hash.aggregate_type,
    seed_with_hash.aggregate_id,
    1,
    'form.published',
    jsonb_build_object(
      'form_definition_id', seed_with_hash.form_id::text,
      'name', seed_with_hash.name,
      'target_type', seed_with_hash.target_type,
      'scope_kind', seed_with_hash.scope_kind,
      'scope_id', seed_with_hash.scope_id,
      'version', seed_with_hash.form_version,
      'fields', seed_with_hash.fields,
      'routing_rules', seed_with_hash.routing_rules,
      'status', 'current'
    ),
    '{"version":{"old":null,"new":1},"status":{"old":null,"new":"current"}}'::jsonb
  FROM inserted_action
  CROSS JOIN seed_with_hash
  RETURNING id
),
inserted_head AS (
  INSERT INTO aggregate_heads (
    aggregate_type,
    aggregate_id,
    current_seq,
    latest_change_id
  )
  SELECT
    seed_with_hash.aggregate_type,
    seed_with_hash.aggregate_id,
    1,
    inserted_change.id
  FROM inserted_change
  CROSS JOIN seed_with_hash
  RETURNING aggregate_type, aggregate_id
)
SELECT
  CASE
    WHEN EXISTS (SELECT 1 FROM inserted_form)
      THEN 'inserted seed public-intake form'
    WHEN EXISTS (
      SELECT 1
      FROM current_global, seed_with_hash
      WHERE current_global.id <> seed_with_hash.form_id
    )
    AND EXISTS (
      SELECT 1
      FROM existing_seed, seed_with_hash
      WHERE existing_seed.actual_content_hash <> seed_with_hash.expected_content_hash
    )
      THEN 'WARNING: seed public-intake form exists but content has drifted; officer-published form present; skipping seed'
    WHEN EXISTS (
      SELECT 1
      FROM current_global, seed_with_hash
      WHERE current_global.id <> seed_with_hash.form_id
    )
      THEN 'officer-published form present; skipping seed'
    WHEN EXISTS (
      SELECT 1
      FROM existing_seed, seed_with_hash
      WHERE existing_seed.actual_content_hash <> seed_with_hash.expected_content_hash
    )
      THEN 'WARNING: seed public-intake form exists but content has drifted; no-op'
    WHEN EXISTS (SELECT 1 FROM existing_seed)
      THEN 'seed public-intake form already present; no-op'
    ELSE 'WARNING: seed made no change and found no current form'
  END AS seed_outcome;

COMMIT;
```

The implementation may factor the SQL for maintainability, but the observable behavior must stay this shape: no current global form inserts one seed form and its accepted aggregate rows; existing seed row emits a no-op outcome and verifies content hash; different current global row emits `officer-published form present; skipping seed` and exits 0. If the implementation detects an existing aggregate head without a current global form and without the seed row, it should fail closed rather than invent a version rewrite in this seed slice.

The aggregate rows needed for the API to find the form are concrete:

- `form_definitions`: `id=<deterministic seed UUID>`, `scope_kind='global'`, `scope_id=NULL`, `version=1`, `name='Public Application'`, `target_type='chapter_membership'`, `fields=<two-field jsonb>`, `routing_rules=<global review jsonb>`, `status='current'`, `published_by_kind='service'`, `published_by_id='public-intake-seed'`, `published_at=CURRENT_TIMESTAMP`.
- `activity_actions`: `action_type='form.publish'`, `aggregate_type='application_form'`, `aggregate_id='application_form|global|'`, `actor_kind='service'`, `actor_id='public-intake-seed'`, `scope_kind='global'`, `scope_id=NULL`, `request_surface='gitops:local/server-manager/seed-public-intake-form'`, `request_json=<publish payload allowlist>`, `status='accepted'`.
- `activity_state_changes`: `action_id=<inserted action id>`, `aggregate_type='application_form'`, `aggregate_id='application_form|global|'`, `aggregate_seq=1`, `change_type='form.published'`, `payload_json` matching `services/api/app/services/forms.py` publish payload, and `diff_json` with version `null -> 1` and status `null -> current`.
- `aggregate_heads`: `aggregate_type='application_form'`, `aggregate_id='application_form|global|'`, `current_seq=1`, `latest_change_id=<inserted state change id>`.

## Supported-surface track

- Deployment mode: local first. Remote channel apply is deferred to BL-013 and must not be introduced by this slice.
- Customer cohort: cluster operators and CI. The direct user-visible effect is only that the already-supported public intake path works after fresh local bringup.
- Adjacent paths: INIT-120 public submit becomes operationally functional because the global form exists before submission. `GET /api/v1/application-forms/current?scope_kind=global` also becomes consistent because the aggregate head exists.
- Blast-radius: `services/api/app/services/forms.py` current-form semantics, `services/api/app/repositories/forms.py` aggregate join, Discord submission service form lookups for global scope, public submit fallback behavior in `services/api/app/services/applications.py`, and the audit/mutation substrate.
- Migration / rollback: deployment is a GitOps resource add/remove, not Alembic. Rollback removes the Job resource from GitOps; database cleanup is manual and guarded because applications may reference `form_definitions.id` through a restrictive FK.
- Observability: the Job logs a single `seed_outcome` line, and idempotency outcomes are visible as `inserted seed public-intake form`, `seed public-intake form already present; no-op`, `WARNING: seed public-intake form exists but content has drifted; no-op`, or `officer-published form present; skipping seed`.

## Assumption register

- A1: The canonical day-1 public form is the INIT-120 two-field global form. Evidence: `infra/tests/fixtures/web-ui/contract.json` and `services/api/tests/public_intake_fixtures.py` use `character_name` and `application_text`. Invalidation: a newer approved proposal or contract fixture names a different public form shape.
- A2: Local GitOps is the owning deployment surface for this seed. Evidence: BL-002/problem map and the locked direction place the resource under `gitops/channels/local/applications/server-manager/`. Invalidation: BL-013 or another approved channel-template task moves application workload bootstrapping into shared remote/local templates before implementation.
- A3: Direct SQL is acceptable only if it writes aggregate rows as well as the projection row. Evidence: `services/api/app/repositories/forms.py` joins `form_definitions` to `aggregate_heads`, and `services/api/app/services/forms.py` publishes through `mutate_entity()`. Invalidation: hookpoint research finds a supported CLI/API bootstrap path with existing authority grants that can publish the seed without new auth surface.
- A4: A different current global form is operator-owned and must not be replaced. Evidence: the locked idempotency rule says to log `officer-published form present; skipping seed` and exit 0. Invalidation: a later explicit operator runbook pre-authorizes replacing global form state.
- A5: The seed's aggregate sequence can start at 1 on the only insertion path. Evidence: fresh bringup has no current global form or `application_form|global|` head; service publication with expected version 0 creates a head and first state change (`services/api/app/services/mutations.py`). Invalidation: a database state has an existing `application_form|global|` head but no current form or seed row, which should fail closed and return to research rather than guessing a repair.

## Test-intent track

| Test / group | Change risk | Intended behavior | Level | Fixture source | Assumption link | Observable signal | Residual risk |
|---|---|---|---|---|---|---|---|
| Rendered GitOps resource test | Seed manifest omitted or wired without DB secret / ConfigMap | `kustomization.yaml` includes `seed-public-intake-form.yaml`; rendered Job mounts inline seed SQL and reads `server-manager-postgres-url` | particular-integration | local kustomize render | A2 | Rendered YAML has ConfigMap, Job, psql image, DB URL secret, non-root security context | Does not prove Job completes in cluster |
| Migration readiness/order test | Seed runs before Alembic and fails permanently | Job command includes schema readiness loop for `form_definitions`, `activity_actions`, `activity_state_changes`, and `aggregate_heads` before running seed SQL | particular-integration | rendered Job command/static shell check | A2, A5 | Test finds readiness probe SQL before `psql -f /seed/seed.sql` | Static proof cannot model all Flux scheduling races |
| Fresh database seed SQL test | Direct SQL creates projection-only form | On empty migrated DB, seed inserts one current global form, one accepted action, one state change, and one head for `application_form|global|` | component | migrated Postgres test DB plus ConfigMap SQL | A3, A5 | Counts and selected columns match expected values; head `current_seq=1`; latest change FK resolves | Does not prove Kubernetes Job image runtime |
| API current-form lookup test | Public submit works via fallback while current-form API still 404s | After seed, `GET /api/v1/application-forms/current?scope_kind=global` returns the seeded form with ETag `"1"` | component | API test DB seeded by seed SQL | A3 | Response 200, two fields, global scope, version 1 | Does not test auth publish endpoint |
| Idempotency rerun test | Reapplying seed duplicates current forms or extra aggregate changes | Running seed twice returns no-op on second run and leaves exactly one seed form, one accepted action, one state change, and one head | component | same seed SQL against migrated DB | A3, A5 | Second outcome is `seed public-intake form already present; no-op`; row counts unchanged | Does not cover simultaneous concurrent Jobs |
| Officer-published skip test | Seed overwrites operator form | If a different current global form exists, seed exits 0, logs skip, and does not archive or replace it | component | API-published or SQL fixture for non-seed current global form | A4 | Outcome contains `officer-published form present; skipping seed`; current form id unchanged | Does not prove every possible officer content shape |
| Drift warning test | Seed row content drift is silently accepted as healthy | If deterministic seed id exists with changed content, seed emits warning and makes no mutation | component | SQL fixture that mutates seed row fields | A3, A4 | Outcome contains `WARNING`; row content unchanged; no new action/state rows | Warning visibility depends on log collection retention |
| Public submit fresh-bringup test | Original BL-002 failure remains | Fresh local bringup succeeds through public web/API submission without manual SQL | end-to-end | `infra/tests/e2e/tests/19-web-ui.sh` after local GitOps reconcile | A1, A2, A3 | Browser submit receives 201; persisted application is queued with `public:` synthetic applicant identity | E2E covers local only, not remote BL-013 |
| Rollback guard test | Cleanup guidance deletes referenced form state | Manual cleanup script/runbook refuses to delete seed form when any application references it | particular-integration | SQL rollback check fixture | A2, A4 | Cleanup preflight reports references and exits non-zero | Actual rollback remains operator-run, not automated |

### Residual-risk artifact

`plans/risk/init-122-test-residuals.md`

## Migration / rollback

Migration is a GitOps resource addition: add `seed-public-intake-form.yaml` and include it in the local server-manager Kustomization after the Alembic Job. No Alembic revision is added, and no application code migration is required.

Rollback removes `seed-public-intake-form.yaml` from the local Kustomization and deletes the completed Kubernetes Job/ConfigMap on reconcile. Database rollback is not automatic. If the seed form has never been referenced by `applications.form_definition_id`, an operator can manually delete the seed `form_definitions` row, its `application_form|global|` aggregate head, and its seed action/state rows by exact deterministic id and aggregate id. If any application references the seed form, the form row must remain because `applications.form_definition_id` is `ON DELETE RESTRICT` (`migrations/versions/wu-022_applications.py`); the reversible action is to publish a new current global form through the authenticated form API, leaving the seed archived or superseded.

The Job itself must remain rerunnable and safe after rollback/reapply. Reapplying it after an officer has published a replacement current global form logs the officer-published skip and exits 0.

## Out of scope for follow-up

- Extending the seed to chapter scope or chapter-specific application forms; that belongs to BL-010 territory.
- Remote channel apply or channel-template porting; that remains BL-013.
- Officer-driven form authoring UI.
- Importing or reconciling `forms/dark-nemesis.yaml` into the runtime database.
- Reworking the authenticated application form publish API, optimistic-locking behavior, or authority model.
