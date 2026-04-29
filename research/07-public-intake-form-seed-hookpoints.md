READ:
- /home/nes/ai/workflows/implementation-pipeline.md
- proposals/04-public-intake-form-seed.md
- research/06-public-intake-form-seed-problem-map.md
- plans/risk/init-122-audit.md
- plans/risk/init-122-scope.md
- plans/risk/init-122-shortcut.md
- plans/risk/init-122-supported-surface.md
- .tmp/rca/public-intake-form-seed-FINDINGS.md
- gitops/channels/local/applications/server-manager/kustomization.yaml
- gitops/channels/local/applications/server-manager/alembic-migration-job.yaml
- gitops/channels/local/applications/server-manager/object-storage-bucket-job.yaml
- gitops/flux/humility-local.yaml
- infra/tests/e2e/lib/bringup.sh
- migrations/versions/wu-002_activity_substrate.py
- migrations/versions/wu-003a_widen_aggregate_id.py
- migrations/versions/wu-003b_audit_context_columns.py
- migrations/versions/wu-018_chapter_templates.py
- migrations/versions/wu-021_forms.py
- migrations/versions/wu-022_applications.py
- migrations/versions/wu-029a_notifications.py
- migrations/versions/wu-031_read_models.py
- services/api/app/repositories/forms.py
- services/api/app/repositories/mutations.py
- services/api/app/services/forms.py
- services/api/app/services/mutations.py
- services/api/app/api/v1/endpoints/applications/forms.py
- services/api/app/api/v1/endpoints/applications/_shared.py
- services/api/tests/conftest.py
- services/api/tests/public_intake_fixtures.py
- services/api/tests/test_forms.py
- services/api/tests/test_public_intake_submit.py
- services/api/tests/test_public_application_route.py
- infra/tests/fixtures/web-ui/contract.json
- infra/tests/fixtures/contracts/application_workloads_contract.yml
- infra/tests/test_application_workloads_contract.py
- infra/tests/validate_application_workloads_local.sh
- infra/tests/e2e/run-fullstack.sh
- infra/tests/e2e/tests/19-web-ui.sh
- infra/tests/e2e/lib/playwright/browser-flow.mjs
- policy/cedar/channels/local/services/server-manager-api/service-identities.json
- policy/cedar/channels/local/services/server-manager-api/policies.json

## Inputs read

- Pipeline rules: `/home/nes/ai/workflows/implementation-pipeline.md`, especially Phase 5's requirement to map the approved proposal onto reusable pieces, extension points, conflicts, and deletion candidates without implementing.
- Approved proposal: `proposals/04-public-intake-form-seed.md`. The design locks the new local manifest, ConfigMap-mounted `seed.sql`, one-shot Job, readiness loop, direct SQL projection plus aggregate rows, deterministic sha256-derived UUID, and idempotent skip/no-op behavior (`proposals/04-public-intake-form-seed.md:68`, `proposals/04-public-intake-form-seed.md:97`, `proposals/04-public-intake-form-seed.md:343`).
- Approved problem map: `research/06-public-intake-form-seed-problem-map.md`. It names the touched local GitOps surface, fresh-bringup failure, aggregate-head consistency risk, and current test fixture gap.
- Risk reports: all four risk reports return LOW / no supported-surface termination. The shortcut report preserves a Step 6 contract obligation: fail closed for "aggregate head exists but no current/seed form" despite the sample CASE's warning-only ELSE.
- RCA: `.tmp/rca/public-intake-form-seed-FINDINGS.md`. It rules out copying the current fixture SQL unchanged because it omits the aggregate head and leaves the canonical current-form API inconsistent.

No approved assumption A1-A5 is contradicted by the current codebase. No `INVALIDATED_ASSUMPTION` signal.

## Job manifest placement hookpoints

Reusable hookpoints:

- The owning directory already contains the local server-manager workload bundle: `gitops/channels/local/applications/server-manager/kustomization.yaml:3`. Existing resources include the namespace and runtime/database secrets before the workload Jobs (`kustomization.yaml:4`, `kustomization.yaml:5`, `kustomization.yaml:7`), the CNPG cluster (`kustomization.yaml:11`), scheduled backup (`kustomization.yaml:12`), Alembic Job (`kustomization.yaml:13`), API/ingress/public-intake resources (`kustomization.yaml:14`, `kustomization.yaml:16`, `kustomization.yaml:17`), Discord deployment (`kustomization.yaml:19`), object-storage bucket Job (`kustomization.yaml:20`), and NetworkPolicies (`kustomization.yaml:21`).
- The new resource should be added immediately after `alembic-migration-job.yaml` in the resources list, matching the approved proposal (`proposals/04-public-intake-form-seed.md:72`). This placement documents the dependency but does not by itself enforce completion.
- The local Flux Kustomization applies one path with `wait: true` and `timeout: 5m`, not a staged dependency chain: `gitops/flux/humility-local.yaml:17`, `gitops/flux/humility-local.yaml:19`, `gitops/flux/humility-local.yaml:21`, `gitops/flux/humility-local.yaml:22`. Because all server-manager sibling resources are rendered together, the seed Job needs its own database/schema readiness loop.
- Existing one-shot Job pattern 1: `server-manager-alembic-migrate` is a `batch/v1` Job in namespace `server-manager`, with `restartPolicy: OnFailure`, `backoffLimit: 6`, `automountServiceAccountToken: false`, non-root pod security, and `DATABASE_URL` from `server-manager-postgres-url` (`alembic-migration-job.yaml:1`, `alembic-migration-job.yaml:4`, `alembic-migration-job.yaml:10`, `alembic-migration-job.yaml:19`, `alembic-migration-job.yaml:20`, `alembic-migration-job.yaml:21`, `alembic-migration-job.yaml:39`).
- Existing one-shot Job pattern 2: `create-server-manager-bucket` uses `/bin/sh -ec`, a bounded readiness loop, `test "$ready" = 1`, idempotent command behavior, secret refs, `/tmp` `emptyDir`, non-root container security, and read-only root FS (`object-storage-bucket-job.yaml:10`, `object-storage-bucket-job.yaml:40`, `object-storage-bucket-job.yaml:44`, `object-storage-bucket-job.yaml:52`, `object-storage-bucket-job.yaml:53`, `object-storage-bucket-job.yaml:54`, `object-storage-bucket-job.yaml:67`, `object-storage-bucket-job.yaml:70`).

New files:

- `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml` containing both ConfigMap and Job, per `proposals/04-public-intake-form-seed.md:38` and `proposals/04-public-intake-form-seed.md:70`.

Conflicting systems:

- There is no existing local form seed Job under `gitops/channels/local/applications/server-manager/`; the current Kustomization has no public-intake seed resource (`kustomization.yaml:3` through `kustomization.yaml:21`).
- There is no Flux-level server-manager sub-Kustomization that can express `dependsOn` only for this Job. Sequencing dependent Jobs in this directory is currently done with resource ordering as documentation plus self-contained readiness loops, not Flux `dependsOn`.

Deletion candidates:

- None in the GitOps placement surface. The Alembic Job and object-storage Job are reusable patterns, not replacements.

## Idempotent SQL hookpoints

Reusable hookpoints:

- `form_definitions` schema: required columns for the seed are `id`, `scope_kind`, `scope_id`, `version`, `name`, `target_type`, `fields`, `routing_rules`, `status`, `published_by_kind`, `published_by_id`, and `published_at` (`migrations/versions/wu-021_forms.py:17`, `migrations/versions/wu-021_forms.py:19`, `migrations/versions/wu-021_forms.py:20`, `migrations/versions/wu-021_forms.py:22`, `migrations/versions/wu-021_forms.py:25`, `migrations/versions/wu-021_forms.py:27`, `migrations/versions/wu-021_forms.py:28`, `migrations/versions/wu-021_forms.py:30`).
- Scope/shape constraints already enforce the global row shape: global scope requires `scope_id IS NULL`, valid targets include `chapter_membership`, statuses are `current|archived`, fields must be a JSON array, and routing rules must be a JSON object (`wu-021_forms.py:43`, `wu-021_forms.py:48`, `wu-021_forms.py:53`, `wu-021_forms.py:59`, `wu-021_forms.py:63`, `wu-021_forms.py:67`).
- Existing uniqueness constraints define idempotency boundaries: one `(scope_kind, scope_id, version)` using `NULLS NOT DISTINCT`, and one current row per `(scope_kind, scope_id)` (`wu-021_forms.py:72`, `wu-021_forms.py:78`).
- The canonical repository current-form lookup joins `form_definitions` to `aggregate_heads` on `aggregate_type='application_form'` and `aggregate_id='application_form|' || f.scope_kind || '|' || COALESCE(f.scope_id, '')` (`services/api/app/repositories/forms.py:10`, `services/api/app/repositories/forms.py:26`, `services/api/app/repositories/forms.py:27`, `services/api/app/repositories/forms.py:28`, `services/api/app/repositories/forms.py:29`). This is the load-bearing reason projection-only SQL is insufficient.
- Existing form publication aggregate id helper returns `application_form|{scope_kind}|{scope_id or ""}` (`services/api/app/services/forms.py:36`). For global scope the exact aggregate id is `application_form|global|`.
- Existing publication flow archives current rows, inserts a new projection row, creates a `StateChangeDraft` with `change_type='form.published'`, then calls `mutate_entity()` with `aggregate_type='application_form'`, `action_type='form.publish'`, request surface `api:/api/v1/application-forms`, and the publish payload allowlist (`services/api/app/services/forms.py:92`, `services/api/app/services/forms.py:99`, `services/api/app/services/forms.py:116`, `services/api/app/services/forms.py:135`, `services/api/app/services/forms.py:137`, `services/api/app/services/forms.py:138`, `services/api/app/services/forms.py:142`, `services/api/app/services/forms.py:144`, `services/api/app/services/forms.py:153`).
- The mutation service's accepted path creates or locks a head, inserts `activity_actions`, inserts `activity_state_changes` at `head.current_seq + 1`, and advances `aggregate_heads` (`services/api/app/services/mutations.py:97`, `services/api/app/services/mutations.py:112`, `services/api/app/services/mutations.py:150`, `services/api/app/services/mutations.py:168`, `services/api/app/services/mutations.py:178`). The seed SQL must produce the same post-state for a fresh aggregate: one accepted action, one state change at seq 1, and head `current_seq=1`.
- Low-level repository row shapes for direct SQL are visible in `insert_action`, `insert_state_change`, and `advance_head` (`services/api/app/repositories/mutations.py:46`, `services/api/app/repositories/mutations.py:66`, `services/api/app/repositories/mutations.py:109`, `services/api/app/repositories/mutations.py:122`, `services/api/app/repositories/mutations.py:151`, `services/api/app/repositories/mutations.py:161`).
- Activity substrate migrations provide the table/FK/unique constraints: `activity_actions` (`wu-002_activity_substrate.py:17`), `activity_state_changes` including unique `(aggregate_type, aggregate_id, aggregate_seq)` (`wu-002_activity_substrate.py:69`, `wu-002_activity_substrate.py:99`), and `aggregate_heads` primary key plus `latest_change_id` FK (`wu-002_activity_substrate.py:113`, `wu-002_activity_substrate.py:124`, `wu-002_activity_substrate.py:130`). `aggregate_id` is text after `wu-003a` (`wu-003a_widen_aggregate_id.py:19`, `wu-003a_widen_aggregate_id.py:34`). Audit context columns are required in `activity_actions` after `wu-003b` (`wu-003b_audit_context_columns.py:17`, `wu-003b_audit_context_columns.py:26`, `wu-003b_audit_context_columns.py:30`).
- `pgcrypto` is already created by an earlier migration, so SQL can use `digest()` and `gen_random_uuid()` after migrations are complete (`migrations/versions/wu-018_chapter_templates.py:16`, `migrations/versions/wu-018_chapter_templates.py:17`).
- Existing idempotent migration-seed style is `INSERT ... SELECT ... WHERE NOT EXISTS (...)`, used for read model and notification service grants (`migrations/versions/wu-031_read_models.py:41`, `migrations/versions/wu-031_read_models.py:49`, `migrations/versions/wu-031_read_models.py:74`; `migrations/versions/wu-029a_notifications.py:229`, `migrations/versions/wu-029a_notifications.py:254`). These are style references only; the proposal forbids an Alembic seed.

Exact INSERT pattern required:

- Use one transaction.
- Build a `seed` CTE with:
  - `form_id` = deterministic UUID from sha256 hex of `init-122:public-intake-global:v1`, truncated to the first 32 hex characters and rendered as UUID.
  - `aggregate_type='application_form'`.
  - `aggregate_id='application_form|global|'`.
  - `scope_kind='global'`, `scope_id=NULL`.
  - `form_version=1`.
  - `name='Public Application'`, `target_type='chapter_membership'`.
  - fields exactly matching the two-field INIT-120 contract.
  - routing rules exactly `{"schema_version":1,"queue":"chapter_officers","review_scope":{"scope_kind":"global","scope_id":null}}`.
  - `actor_kind='service'`, `actor_id='public-intake-seed'`, `request_surface='gitops:local/server-manager/seed-public-intake-form'`.
- Lock `current_global` rows where `scope_kind='global'`, `scope_id IS NULL`, and `status='current'`.
- Lock `existing_seed` row by deterministic `form_id`.
- Insert into `form_definitions` only when no current global form exists and the seed row is absent.
- Insert into `activity_actions` only if `inserted_form` exists, with `action_type='form.publish'`, aggregate `application_form|global|`, service actor `public-intake-seed`, status `accepted`, request JSON limited to the publish allowlist, and reason text naming INIT-122.
- Insert into `activity_state_changes` only if the accepted action exists, with `aggregate_seq=1`, `change_type='form.published'`, payload matching `services/api/app/services/forms.py`'s `StateChangeDraft`, and diff `version null -> 1` / `status null -> current`.
- Insert into `aggregate_heads` only if the state change exists, with `current_seq=1` and `latest_change_id` pointing at the inserted state change.
- Add an explicit dangling-head probe for `aggregate_type='application_form' AND aggregate_id='application_form|global|'` when there is no current global form and no seed row. The approved prose requires this branch to fail closed (`proposals/04-public-intake-form-seed.md:343`); the sample CASE's warning-only ELSE (`proposals/04-public-intake-form-seed.md:337`) should not become the implementation behavior.

New files:

- The SQL lives inline under `data.seed.sql` in `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`.
- For tests, add a helper fixture module that extracts `data["seed.sql"]` from the manifest, instead of duplicating SQL text in tests. Suggested path: `services/api/tests/public_intake_seed_sql_fixtures.py`.

Conflicting systems:

- `services/api/tests/public_intake_fixtures.py::seed_global_public_application_form()` archives any current global form and inserts only `form_definitions` with a random UUID (`services/api/tests/public_intake_fixtures.py:53`, `services/api/tests/public_intake_fixtures.py:76`, `services/api/tests/public_intake_fixtures.py:86`). It is a test-only helper and conflicts with the production seed if copied unchanged.
- Authenticated `POST /api/v1/application-forms` is the domain publish path but requires `application_form.publish` authority (`services/api/app/api/v1/endpoints/applications/forms.py:19`, `services/api/app/api/v1/endpoints/applications/forms.py:23`). No existing service identity or seeded DB grant exists for `public-intake-seed`; Cedar local service identities include only Buildkite and Crossplane (`policy/cedar/channels/local/services/server-manager-api/service-identities.json:5`, `service-identities.json:6`, `service-identities.json:13`), and local public Cedar policy covers only `application:submit_public` (`policy/cedar/channels/local/services/server-manager-api/policies.json:10`). This supports the approved direct-SQL path and does not invalidate A3.

Deletion candidates:

- None during Phase 6 implementation. The existing public-intake fixture can remain for older component tests, but new INIT-122 tests should not use it for seed correctness because it intentionally omits aggregate rows.

## Deterministic seed UUID hookpoints

Reusable hookpoints:

- The approved proposal defines deterministic ID semantics as sha256 of the literal seed key, truncated to 16 bytes / 32 hex characters and rendered as UUID (`proposals/04-public-intake-form-seed.md:65`, `proposals/04-public-intake-form-seed.md:102`, `proposals/04-public-intake-form-seed.md:126`).
- `pgcrypto` is already available after migrations (`migrations/versions/wu-018_chapter_templates.py:17`), so the SQL helper can use `encode(digest('init-122:public-intake-global:v1', 'sha256'), 'hex')`.
- Python has no existing reusable deterministic form-id helper. There are unrelated uses of `uuid5` for public application idempotency and Discord message nonces, but no helper that implements the proposal's sha256-truncated UUID algorithm.

Deterministic value:

- `sha256("init-122:public-intake-global:v1")` = `48b2ddad2c22f2e9f12cfcafd8a0cb0d8351ec354d2b9ccc7c5cd164099c2cc0`.
- Deterministic seed UUID = `48b2ddad-2c22-f2e9-f12c-fcafd8a0cb0d`.

New files:

- If Step 6b needs a Python-side assertion helper, add it to the new test fixture module rather than production code. Suggested function:
  - `deterministic_public_intake_seed_form_id() -> UUID`, implemented with `hashlib.sha256(...).hexdigest()[:32]` and `UUID(hex=...)`.
- Do not add production Python solely for this; the production path is the psql seed.

Conflicting systems:

- The prompt says "UUID5/sha-256 based deterministic ID", but the approved proposal's concrete algorithm is sha256 truncation rendered as UUID, not RFC 4122 UUIDv5. Use the approved proposal unless the orchestrator revises the contract.

Deletion candidates:

- None.

## ConfigMap mount hookpoints

Reusable hookpoints:

- Existing server-manager Jobs do not mount ConfigMaps, but `object-storage-bucket-job.yaml` shows the local Job shell/readiness style and an `emptyDir` for writable temp space under read-only root (`object-storage-bucket-job.yaml:40`, `object-storage-bucket-job.yaml:44`, `object-storage-bucket-job.yaml:67`, `object-storage-bucket-job.yaml:70`).
- Existing local manifests elsewhere show standard ConfigMap volume mounting. For example, local web deployment uses read-only root plus `volumeMounts` and `emptyDir` (`gitops/channels/local/applications/web/deployment.yaml:46`, `gitops/channels/local/applications/web/deployment.yaml:49`, `gitops/channels/local/applications/web/deployment.yaml:58`), and observability deployments mount ConfigMaps by name (`gitops/channels/local/observability/prometheus/deployment.yaml:65`, `gitops/channels/local/observability/prometheus/deployment.yaml:76`).
- The Alembic Job's database secret reference is the exact DB credential hookpoint to reuse: env var `DATABASE_URL` from `secretKeyRef.name=server-manager-postgres-url`, `key=url` (`alembic-migration-job.yaml:39`, `alembic-migration-job.yaml:40`, `alembic-migration-job.yaml:42`, `alembic-migration-job.yaml:43`, `alembic-migration-job.yaml:44`).
- The psql image is already pre-pulled for e2e: `mirror.gcr.io/bitnamilegacy/postgresql:16.2.0-debian-11-r16` appears in `E2E_EXTERNAL_IMAGES` (`infra/tests/e2e/lib/bringup.sh:10`, `infra/tests/e2e/lib/bringup.sh:19`).

Required manifest shape:

- `ConfigMap` named `server-manager-public-intake-form-seed`, namespace `server-manager`, with `data.seed.sql`.
- `Job` named `server-manager-seed-public-intake-form`, namespace `server-manager`.
- Job container image `mirror.gcr.io/bitnamilegacy/postgresql:16.2.0-debian-11-r16`.
- Command `/bin/sh -ec` with readiness loop before `psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f /seed/seed.sql`.
- `volumeMounts` should mount the ConfigMap read-only at `/seed`.
- If `readOnlyRootFilesystem: true` is kept, add a writable `/tmp` `emptyDir` unless runtime validation proves the image does not need it.

New files:

- Same new manifest: `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`.

Conflicting systems:

- None direct. The only caution is security-context compatibility for the Bitnami legacy image; existing Jobs use UID 10001 for API image and UID 1000 for MinIO client, but the Postgres image may prefer UID 1001. Step 6c should verify the rendered Pod starts rather than copying a UID blindly.

Deletion candidates:

- None.

## Test surface hookpoints

Reusable hookpoints:

- Service API tests already have migrated Postgres fixtures: `fresh_migrated_postgres_db` runs Alembic on a clean DB (`services/api/tests/conftest.py:236`), while `governance_dsn` resets state around each test (`services/api/tests/conftest.py:276`, `services/api/tests/conftest.py:286`). SQL idempotency tests should use a clean migrated DB when they need empty-state proof, and `governance_dsn` when they need integration with the shared test app.
- `migrated_async_client` provides the ASGI client after migrations (`services/api/tests/conftest.py:268`). Use it for `GET /api/v1/application-forms/current?scope_kind=global`.
- Existing current-form API expectations are in `services/api/tests/test_forms.py`: publish returns ETag `"1"` and current lookup returns version/ETag for a scope (`test_forms.py:88`, `test_forms.py:99`, `test_forms.py:112`, `test_forms.py:117`, `test_forms.py:119`).
- Risk annotation helper exists in `services/api/tests/public_intake_fixtures.py:228`; new tests should use or mirror this style with sources pointing at `proposals/04-public-intake-form-seed.md#test-intent-track`.
- Existing public-intake route tests seed the old projection-only fixture (`services/api/tests/test_public_application_route.py:57`, `services/api/tests/test_public_intake_submit.py:49`). New INIT-122 tests should seed via extracted ConfigMap SQL, not `seed_global_public_application_form()`.
- Static infra tests already load manifest YAML directly from `APP_DIR` (`infra/tests/test_application_workloads_contract.py:17`, `infra/tests/test_application_workloads_contract.py:20`) and validate migration/bucket/Kong contracts (`infra/tests/test_application_workloads_contract.py:125`). This is the best hookpoint for static manifest assertions.
- The shell validator's static file assertions currently include server-manager Kustomization, Alembic Job, API/Discord, ingress, rate limit, and bucket Job (`infra/tests/validate_application_workloads_local.sh:156`, `validate_application_workloads_local.sh:161`, `validate_application_workloads_local.sh:163`, `validate_application_workloads_local.sh:168`). Add `seed-public-intake-form.yaml` there.
- The shell validator's kustomize render checks already render the server-manager app and local root (`validate_application_workloads_local.sh:187`, `validate_application_workloads_local.sh:190`), then greps for key resources (`validate_application_workloads_local.sh:193`, `validate_application_workloads_local.sh:198`). Add grep checks for the seed ConfigMap, Job, DB secret, mount path, and psql image.
- Runtime validator already waits for the Alembic Job complete (`validate_application_workloads_local.sh:330`) before API health. Add a wait for `job/server-manager-seed-public-intake-form --for=condition=Complete` after Alembic complete.
- Runtime validator already shells into the CNPG primary with `psql "$url"` (`validate_application_workloads_local.sh:336`, `validate_application_workloads_local.sh:337`, `validate_application_workloads_local.sh:338`). Reuse this to assert `form_definitions` plus `aggregate_heads` for `application_form|global|` after seed completion.
- E2E fullstack bringup waits for Flux Kustomization readiness before tests (`infra/tests/e2e/lib/bringup.sh:201`, `bringup.sh:203`, `bringup.sh:204`). No `run-fullstack.sh` ordering change is necessary if the seed Job is included in Flux and `wait: true` sees it complete; if Kubernetes Job readiness is not reflected reliably in Flux wait, extend `e2e_bringup_fullstack()` after `e2e_wait_bringup_ready` to wait for `job/server-manager-seed-public-intake-form` completion.
- `19-web-ui.sh` already verifies browser submit persistence in DB (`infra/tests/e2e/tests/19-web-ui.sh:8`, `19-web-ui.sh:16`, `19-web-ui.sh:19`, `19-web-ui.sh:26`, `19-web-ui.sh:28`). Add a pre-submit or post-submit psql check for current global form plus aggregate head, or add a curl from cluster to `GET /api/v1/application-forms/current?scope_kind=global`.
- Browser flow already waits for the web submit response and asserts status 201 (`infra/tests/e2e/lib/playwright/browser-flow.mjs:46`, `browser-flow.mjs:55`, `browser-flow.mjs:56`). No Playwright change is required for ordering.

New files:

- `services/api/tests/public_intake_seed_sql_fixtures.py`: helper to load `seed.sql` from `seed-public-intake-form.yaml`, compute deterministic seed UUID, execute seed SQL, and fetch seed rows.
- `services/api/tests/test_public_intake_form_seed_sql.py`: component tests for empty DB insert, rerun idempotency, officer-published skip, drift warning, and dangling-head fail-closed.
- Optional if the API lookup is clearer separately: `services/api/tests/test_public_intake_form_seed_api.py`; otherwise include the API current-form lookup in the SQL test file.

Files to extend:

- `gitops/channels/local/applications/server-manager/kustomization.yaml`: add new resource after line 13.
- `infra/tests/test_application_workloads_contract.py`: add static assertions for seed manifest structure.
- `infra/tests/validate_application_workloads_local.sh`: add static file/render checks and runtime wait/query checks.
- `infra/tests/e2e/tests/19-web-ui.sh`: add seeded-form/API current-form probe if Step 6 chooses e2e coverage for T4/T8.
- `infra/tests/e2e/run-fullstack.sh` or `infra/tests/e2e/lib/bringup.sh`: extend only if Flux `wait: true` does not reliably cover the seed Job completion.

Conflicting systems:

- The old `seed_global_public_application_form()` fixture conflicts with INIT-122's aggregate-consistent test intent and should not be used for new seed tests.
- The proposed SQL tests will need to execute SQL extracted from a YAML ConfigMap. Avoid duplicating the seed SQL into Python strings; that would create a parallel source that can drift.

Deletion candidates:

- None required. Later cleanup could migrate public-intake tests from projection-only fixture seeding to the new extracted seed SQL, but that is not necessary for INIT-122 unless Step 6b broadens adjacent regression coverage.

## Conflicting systems / deletion candidates

- Projection-only public-intake fixture: `services/api/tests/public_intake_fixtures.py:53` through `services/api/tests/public_intake_fixtures.py:99`. It is incomplete for runtime bootstrap because it lacks `activity_actions`, `activity_state_changes`, and `aggregate_heads`. Do not copy it into GitOps. Not a deletion candidate now.
- Authenticated form publish API: `services/api/app/api/v1/endpoints/applications/forms.py:19` through `forms.py:38`. It remains the correct officer path, but using it for the bootstrap would require an existing `application_form.publish` authority grant. Hookpoint research found no such service identity or grant. This does not invalidate A3; it supports direct SQL.
- Cedar public-intake policy: local policy grants only `Public::"web-intake.local"` `Action::"application:submit_public"` on public applications (`policy/cedar/channels/local/services/server-manager-api/policies.json:10`). It is unrelated to authenticated form publishing and should not be edited.
- Legacy/root form YAML: RCA ruled out `forms/dark-nemesis.yaml` as runtime source of truth. No INIT-122 deletion.
- Alembic migration seed patterns: existing idempotent service-grant seeds are references for SQL style, but the approved proposal explicitly forbids a migration-based form seed. No migration file should be added or modified for this seed.
- Sample CASE warning-only ELSE in the proposal SQL conflicts with approved fail-closed prose for dangling aggregate head. Treat the prose and A5 as the contract; tests should pin non-zero failure for dangling head rather than allowing `"WARNING: seed made no change and found no current form"` as success.

## New files required

- `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`
- `services/api/tests/public_intake_seed_sql_fixtures.py`
- `services/api/tests/test_public_intake_form_seed_sql.py`

Likely file extensions:

- `gitops/channels/local/applications/server-manager/kustomization.yaml`
- `infra/tests/test_application_workloads_contract.py`
- `infra/tests/validate_application_workloads_local.sh`
- `infra/tests/e2e/tests/19-web-ui.sh`
- `infra/tests/e2e/lib/bringup.sh` only if Flux wait does not prove seed Job completion

## Notable observations

- The approved deterministic ID is sha256-truncated UUID, not UUIDv5. The exact expected UUID is `48b2ddad-2c22-f2e9-f12c-fcafd8a0cb0d`.
- `pgcrypto` is available after migrations because `wu-018` creates it; the seed readiness loop should still check migrated tables/columns, not just extension availability.
- Kustomize resource order is documentation, not completion ordering. The seed Job readiness loop is mandatory even if the resource is listed after Alembic.
- The existing runtime shell validator already has the best DB probe hookpoint and can assert seed Job completion without introducing a new test harness.
- The e2e browser flow does not need a Playwright change; the missing piece is ensuring the cluster has the seed before the browser submits.
- No current source contradicts assumptions A1-A5. A3's invalidation condition was specifically checked: no supported CLI/API bootstrap path with existing authority grants was found.
