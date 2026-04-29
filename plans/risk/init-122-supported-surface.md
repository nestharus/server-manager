READ:
- proposals/04-public-intake-form-seed.md
- research/06-public-intake-form-seed-problem-map.md
- .tmp/rca/public-intake-form-seed-FINDINGS.md
- ~/ai/workflows/implementation-pipeline.md
- services/api/tests/public_intake_fixtures.py
- infra/tests/fixtures/web-ui/contract.json
- gitops/channels/local/applications/server-manager/kustomization.yaml
- gitops/channels/local/applications/server-manager/alembic-migration-job.yaml
- migrations/versions/wu-022_applications.py
- services/api/app/services/forms.py
- services/api/app/repositories/forms.py

# INIT-122 Phase 4 — Supported-Surface Risk

## Inputs read

- `proposals/04-public-intake-form-seed.md` — full proposal, including the supported-surface track (lines 352-359), net-value statement (lines 32-34), assumption register A1–A5 (lines 361-367), and test-intent track (lines 369-381).
- `research/06-public-intake-form-seed-problem-map.md` — approved Phase 2.5 problem map covering touched surface, current supported paths, brittle behavior already present, blast-radius adjacents, deployment cohort, and open questions for proposal.
- `.tmp/rca/public-intake-form-seed-FINDINGS.md` — Phase 0 RCA establishing the missing-seed root cause and Option A (idempotent local GitOps Job) as the recommended fix shape.
- Phase pipeline conventions: `~/ai/workflows/implementation-pipeline.md`.
- Cited source artifacts for assumption verification: `services/api/tests/public_intake_fixtures.py:53-99`, `infra/tests/fixtures/web-ui/contract.json:36-78`, `gitops/channels/local/applications/server-manager/kustomization.yaml`, `gitops/channels/local/applications/server-manager/alembic-migration-job.yaml`, `services/api/app/services/forms.py:78-166`, `services/api/app/repositories/forms.py:10-30`, `migrations/versions/wu-022_applications.py:51-62`.

## Termination evaluation

Per `implementation-pipeline.md:106`, evaluate orthogonal termination signals before the LOW/MEDIUM/HIGH verdict. Order: invalidated assumption first, then non-positive value.

### Invalidated assumption check

I cross-checked each assumption in the proposal's register against current source. Detail in `## Assumption register cross-check`. Summary: cited evidence resolves at the named locations for A1, A2, A3, A4, and A5; each has an observable invalidation condition. No assumption is contradicted by current source.

**No INVALIDATED_ASSUMPTION signal.**

### Non-positive value check

Existing-state risk on the supported surface is concrete and present today: fresh `humility-local` bringup applies the schema and public-intake deployment surface, but no migration, GitOps Job, or e2e bringup step inserts a current global `form_definitions` row, so `POST /api/v1/public/applications` raises `FormDefinitionNotFoundError` and surfaces as 404 `application_not_found` (`.tmp/rca/public-intake-form-seed-FINDINGS.md:55-56`; `services/api/app/services/applications.py:598-604`; `proposals/02-public-application-intake.md` ratified the public route as a supported surface). This is the BL-002 fresh-bringup failure the slice targets.

Added blast radius is bounded:
- A new local-channel Kubernetes manifest under `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml` (ConfigMap + one-shot Job) inside the touched surface.
- A single new resource entry in `gitops/channels/local/applications/server-manager/kustomization.yaml` after `alembic-migration-job.yaml`.
- Direct SQL writes against four already-migrated tables: `form_definitions`, `activity_actions`, `activity_state_changes`, `aggregate_heads`. No schema changes.
- No edits to API code, Discord code, web code, Authentik, Pomerium, Cedar policy, authority grants, or remote channels.
- The seed is gated by an officer-published-skip rule and a content-hash drift check, so reapplication does not overwrite operator state.

The migration burden is one local-channel manifest plus a Kustomization line; rollback is a GitOps revert plus a manual DB cleanup script that is FK-guarded by `applications.form_definition_id` `ON DELETE RESTRICT` (`migrations/versions/wu-022_applications.py:55-62`). The reduction in concrete current-state risk (a supported public route operationally broken on fresh bringup) clearly outweighs the additive blast radius and the migration cost.

**No NON_POSITIVE_VALUE signal.**

## Existing-state risk reduction

The RCA root cause is structural: INIT-120 made `/api/v1/public/applications` a supported public surface whose day-1 payload targets global scope, but no durable bootstrap step creates the corresponding `form_definitions` current global row, and the only tests that exercise the service satisfy that precondition through `services/api/tests/public_intake_fixtures.py::seed_global_public_application_form`, not through fresh bringup. The proposal addresses this at the structural level rather than relocating the failure:

- The Job seeds both the projection row and the `application_form|global|` aggregate substrate (action, state-change, head). This matches the same shape produced by the canonical authoring path (`services/api/app/services/forms.py:78-166`, `services/api/app/repositories/forms.py:10-30`), so `GET /api/v1/application-forms/current?scope_kind=global` becomes consistent in addition to making public submit work. The RCA's H6 caveat — that the existing test SQL workaround is incomplete because it leaves the aggregate head missing — is resolved.
- The Job is rerunnable with deterministic seed id `sha256("init-122:public-intake-global:v1")` truncated to 16 bytes and a content-hash drift check, so reapply is idempotent in the no-current-form, same-seed-present, and drifted-seed cases without touching officer-published state.
- The "different current global form present" branch logs `officer-published form present; skipping seed` and exits 0, which preserves operator authoring authority. This is the authority-substrate concern the problem map flagged as an open question (`research/06-public-intake-form-seed-problem-map.md:62-71`, `:97-103`); the proposal locks it as fail-soft skip rather than archive-then-replace.
- The "head without form" branch fails closed rather than inventing a version repair. This blocks an entire class of split-state ambiguity.

The fragility shifts from "fresh bringup leaves the public surface broken" to "Job logs a deterministic `seed_outcome`," which is a smaller, observable surface. Concentration of risk on the seed-Job code path is by design.

Residual concern (not a verdict-blocker): the proposal chose direct SQL over API/service publication (Q2) deliberately, to avoid opening a new authority surface (Cedar grant or DB authority grant for `application_form.publish` to a service identity). The problem map noted this tradeoff at `research/06-public-intake-form-seed-problem-map.md:99-100`. The proposal's A3 carries the right invalidation ("hookpoint research finds a supported CLI/API bootstrap path with existing authority grants"). If Phase 5 surfaces such a grant or a clean way to add one, the proposal should be revisited. As of current code (`policy/cedar/channels/local/services/server-manager-api/service-identities.json` has no `public-intake-seed` entry; `application_form.publish` has no DB grant for any service actor), the SQL path is the smaller blast radius.

## Adjacent-path blast-radius bounding

Adjacent paths I checked:

- **INIT-120 public submit (`POST /api/v1/public/applications`, `POST /api/public/applications`)**: this is the supported surface the seed exists to repair. Stamps remain `service`/`public-intake`, Cedar `Public::"web-intake.<channel>"`, surface `api:/api/v1/public/applications`. The seed does not touch the route, the Cedar policy, the synthetic-applicant logic, or the public principal. T8 (public submit fresh-bringup test) is the contractually correct gate.

- **Authenticated `POST /api/v1/applications`**: also reaches `_submit_application_internal()` and `_get_current_form_for_submit()` (`services/api/app/services/applications.py:572-604`, `:723-734`). Adding a current global form makes global-scope authenticated submission *operationally possible* for actors that already hold `application.submit` at global scope. This is an adjacent existing capability rather than a new public route, but the test-intent track does not enumerate a regression check that authenticated chapter-scope submits remain unaffected. The existing chapter-scope tests in `services/api/tests/test_applications.py` should catch any regression. **Notable observation, not blocker.**

- **Discord submission service**: posts to `/api/v1/applications` with command-provided scope and Discord user actor headers (`services/discord/app/handlers/application_submission.py:58-93`). Discord commands target chapter scope, not global, so a global seed does not perturb chapter-scoped form lookup or Discord-visible behavior. Anti-scope respected.

- **`form_definitions` uniqueness constraints**: `ux_form_definitions__current_per_scope` permits one `current` row per `(scope_kind, scope_id)` with `NULLS NOT DISTINCT`, and `ux_form_definitions__scope_version` prevents duplicate `(scope_kind, scope_id, version)` (`migrations/versions/wu-021_forms.py:72-83`, per problem map). The proposal's `INSERT ... WHERE NOT EXISTS (SELECT 1 FROM current_global) AND NOT EXISTS (SELECT 1 FROM existing_seed)` predicate is consistent with both indexes; the `FOR UPDATE` on `current_global` and `existing_seed` blocks concurrent races within the transaction. The "concurrent two Jobs" residual is acknowledged in the test-intent table for the idempotency rerun test.

- **Authenticated form authoring (`POST /api/v1/application-forms`, `GET /api/v1/application-forms/current`)**: still requires `application_form.publish` authority; the seed does not add a grant. After the seed runs, `GET /current?scope_kind=global` returns the seeded form with ETag `"1"` because the aggregate head is present. T4 covers this.

- **Cedar authorization, Pomerium, Authentik**: not touched. Anti-scope.

- **Audit/mutation substrate**: the seed inserts one `accepted` action with `action_type='form.publish'`, one `state_change` with `change_type='form.published'`, and one `aggregate_heads` row with `current_seq=1` for `application_form|global|`. The shape matches what `mutate_entity()` would produce for a fresh aggregate. Subsequent officer publishes go through `mutate_entity()` with `expected_version=1`, which is the correct optimistic-locking handoff. **Verified against `services/api/app/services/forms.py:135-157` and the proposal's CTE SQL at lines 218-307.**

Adjacent-path coverage gap (notable observation): the test-intent table omits a regression check for chapter-scope authenticated submission and a regression check that `POST /api/v1/application-forms` officer publish at global scope still increments `version` correctly after the seed. Step 6a/6b should add or document non-applicability. **Not a proposal-design defect.**

## Migration and rollback realism

Fresh `humility-local` bringup: Flux reconciles the local server-manager Kustomization. Alembic migrates schema, the seed Job's shell loop polls for `form_definitions`, `activity_actions`, `activity_state_changes`, and `aggregate_heads` to exist with the post-`wu-003a_widen_aggregate_id.py` text-shaped `aggregate_id`, then runs the CTE seed SQL once with `ON_ERROR_STOP=1`. The Job logs a single `seed_outcome` line and exits 0 in all four expected branches.

Verified preconditions for the bringup path:
- `gitops/channels/local/applications/server-manager/kustomization.yaml:13` already lists `alembic-migration-job.yaml`. The proposed insertion site after that line is consistent with the locked direction.
- `gitops/channels/local/applications/server-manager/alembic-migration-job.yaml:38-44` exposes `DATABASE_URL` from `secretKeyRef.name=server-manager-postgres-url`. The seed Job will use the same Secret, which avoids introducing a second credential surface.
- The Alembic Job runs as `runAsUser: 10001` with `readOnlyRootFilesystem: true`. The proposal's "where the image supports it" qualifier is honest — the bitnami `psql` image runs as a different default uid (1001) and may need its own securityContext; this is a Step 6c rendering concern, not a proposal-design defect.
- Plain Kustomize sibling resource ordering is not a guarantee; the proposal's shell readiness loop is the correct mitigation. The loop must also cover the post-`wu-003a` `aggregate_id` text shape, which the proposal explicitly states.

Rollback: removing `seed-public-intake-form.yaml` from the Kustomization plus the resource itself prunes the Job/ConfigMap on next reconcile. Database rollback is **not** automatic and the proposal is honest about that. The seed `form_definitions` row may be referenced by `applications.form_definition_id` with `ON DELETE RESTRICT` (`migrations/versions/wu-022_applications.py:55-62`); the proposal's manual cleanup guidance refuses delete when references exist and instead instructs operators to publish a replacement current global form through the authenticated form API. This is the appropriate failure mode for FK-guarded operational state and matches the wu-031/wu-029a/wu-037 migration-seed pattern of avoiding rollback deletion for live operational rows.

The Job remains rerunnable and safe after rollback/reapply: a re-applied Job in a cluster where an officer has published a replacement current global form logs the officer-published skip and exits 0. T6 (officer-published skip) and T9 (rollback guard) are the contractually correct gates.

One non-blocking observation: rollback re-introduces the fresh-bringup failure if the operator has not separately published a current global form. This is acknowledged implicitly in the rollback narrative; the slice intentionally does not provide a "safe undo" because the original state is the broken state. Appropriate for a local-only slice on a known-broken existing state.

## Observability

The proposal's observability story is a single `seed_outcome` line in Job logs with one of:
- `inserted seed public-intake form`
- `seed public-intake form already present; no-op`
- `WARNING: seed public-intake form exists but content has drifted; no-op`
- `WARNING: seed public-intake form exists but content has drifted; officer-published form present; skipping seed`
- `officer-published form present; skipping seed`
- `WARNING: seed made no change and found no current form` (failure-degenerate path)

This is proportional to the slice scope. The Job exits 0 in the success and skip branches and non-zero only when `psql -v ON_ERROR_STOP=1` fails or when the readiness loop times out, so Kubernetes Job/Flux failure semantics surface real configuration or schema problems.

Residual observability concerns (non-blocking):
- WARNING visibility depends on log collection retention — flagged in the test-intent table residual column (T7 drift WARNING). If `humility-local` does not retain Job logs long enough for an operator to notice a drift WARNING, this is a follow-up Prometheus/alerting concern outside this slice. Not a verdict-blocker.
- The proposal does not add a metric or alert for "seeded but not officer-replaced after N days." This is acceptable scope minimalism.
- Restart/reapply durability beyond one Flux reconcile cycle is implicitly covered by idempotency and the deterministic seed id; if Step 6b does not include a Job-rerun-after-reconcile probe in real cluster conditions, a `risk/init-122-test-residuals.md` entry is required per `implementation-pipeline.md:163`.

## Channel-template parity

The proposal stays local-first by design and defers remote to BL-013/INIT-124, matching the `gitops/channels/local/applications/server-manager/` deployment cohort framing in the problem map (`research/06-public-intake-form-seed-problem-map.md:91-95`).

Parity-relevant decisions in the proposal:

- The seed manifest lives at `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`, parallel to the existing local-only `alembic-migration-job.yaml`, `object-storage-bucket-job.yaml`, and `public-intake-rate-limit.yaml`. It is not introduced as a shared template under `gitops/sources/local/` or under a remote-channel path.
- Anti-scope explicitly forbids "remote-channel apply" and "channel-template porting" (`proposals/04-public-intake-form-seed.md:53`). Remote channel application workload bootstrapping remains BL-013's concern.
- The seed content is locked to the INIT-120 two-field global form, matching the visible web contract at `infra/tests/fixtures/web-ui/contract.json:36-78`. No richer chapter selector, no `forms/dark-nemesis.yaml` import, no YAML runtime source of truth — consistent with `proposals/01-v1-scope.md`'s rule that Postgres is the runtime source of truth for forms.
- No channel-conditional logic introduced in renderer scripts or shared paths. When BL-013 materializes remote channels, the equivalent seed (or, more likely, a one-time officer publish) is a separable decision that does not need to be foreshadowed by this slice.

No local-only exception is introduced into a shared surface, and remote contract surface remains preserved (no `dev` channel manifests are touched). This matches the channel-template-pattern memory's expectation that local IS a deployment target with the same component shape, while keeping remote application bootstrapping a deferred backlog item.

## Assumption register cross-check

For each assumption: I check (a) the cited evidence exists at the cited location and supports the claim, and (b) the invalidation condition is observable.

**A1.** "The canonical day-1 public form is the INIT-120 two-field global form."
- Cited at `infra/tests/fixtures/web-ui/contract.json` and `services/api/tests/public_intake_fixtures.py`. Verified `contract.json:36-78`: form has exactly two fields named `character_name` (text, label "Character name") and `application_text` (textarea, label "Application text"). Verified `public_intake_fixtures.py:55-75`: `seed_global_public_application_form` inserts the same two fields with `type=short`/`max_length=64` and `type=long`/`max_length=4000`, and routing rules `{schema_version=1, queue=chapter_officers, review_scope={scope_kind=global, scope_id=null}}`. The proposal's seed payload at `proposals/04-public-intake-form-seed.md:84-95` is byte-equivalent.
- Invalidation condition: a newer approved proposal or contract fixture names a different public form shape. Observable through `infra/tests/fixtures/web-ui/contract.json` diff or `services/api/tests/public_intake_fixtures.py` change. ✓

**A2.** "Local GitOps is the owning deployment surface for this seed."
- Cited at the BL-002/problem map locked direction and `gitops/channels/local/applications/server-manager/`. Verified `kustomization.yaml:1-22` lists 19 sibling resources including Alembic Job, API deployment, public-intake rate limit, Discord deployment, object-storage Job, and network policies. The proposed `seed-public-intake-form.yaml` fits the same Kustomize-resource shape and the same one-shot-Job pattern as `alembic-migration-job.yaml` and `object-storage-bucket-job.yaml`.
- Invalidation condition: BL-013 or another approved channel-template task moves application workload bootstrapping into shared remote/local templates before implementation. Observable through `plans/BACKLOG.md` or a GitOps directory change. ✓

**A3.** "Direct SQL is acceptable only if it writes aggregate rows as well as the projection row."
- Cited at `services/api/app/repositories/forms.py` and `services/api/app/services/forms.py`. Verified `repositories/forms.py:10-30`: `_FORM_SELECT` joins `form_definitions` to `aggregate_heads` on `aggregate_type='application_form'` and `aggregate_id='application_form|' || scope_kind || '|' || COALESCE(scope_id, '')`. Verified `services/forms.py:135-157`: `publish_form()` calls `mutate_entity()` with `aggregate_type='application_form'`, `aggregate_id=application_form_aggregate_id(scope)`, `action_type='form.publish'`, and `payload_allowlist={name, target_type, scope_kind, scope_id, fields, routing_rules}`. The proposal's CTE SQL at lines 218-307 inserts the matching action, state-change, and head with the same aggregate id, action type, payload allowlist, and `change_type='form.published'`.
- Invalidation condition: hookpoint research (Phase 5) finds a supported CLI/API bootstrap path with existing authority grants. Observable through `services/api/app/api/v1/endpoints/applications/forms.py` plus a service-identity grant audit. ✓ (defers a real decision into Phase 5; non-blocking for Phase 4)

**A4.** "A different current global form is operator-owned and must not be replaced."
- Cited at the locked idempotency rule (`proposals/04-public-intake-form-seed.md:63`). The proposal's CTE SQL at lines 308-340 emits `'officer-published form present; skipping seed'` when a `current_global` row exists with id different from the deterministic seed id, and the `INSERT ... WHERE NOT EXISTS (SELECT 1 FROM current_global)` predicate prevents a competing insert. Verified by reading the SQL: the `FOR UPDATE` on `current_global` prevents a concurrent officer publish from racing the skip decision within the same transaction.
- Invalidation condition: a later explicit operator runbook pre-authorizes replacing global form state. Observable through proposal/runbook diff. ✓

**A5.** "The seed's aggregate sequence can start at 1 on the only insertion path."
- Cited at `services/api/app/services/mutations.py` and the locked fail-closed rule. Verified the proposal's CTE inserts `aggregate_seq=1` and `current_seq=1`. The CTE's insert path is gated on `NOT EXISTS (current_global) AND NOT EXISTS (existing_seed)`, so it fires only when no `application_form|global|` aggregate substrate exists (the same precondition `mutate_entity()` would observe with `expected_version=0`). Subsequent officer publishes go through `mutate_entity()` with `expected_version=1`, which matches the head the seed inserts. Verified compatibility against `services/api/app/services/forms.py:78-166` (publish flow uses `expected_version + 1`).
- The proposal also explicitly fails closed if an existing `application_form|global|` head has no corresponding form (rather than inventing a version-repair seed), which is the right answer for a state the seed agent cannot disambiguate.
- Invalidation condition: a database state has an existing `application_form|global|` head but no current form or seed row. Observable through `seed_outcome` line `WARNING: seed made no change and found no current form` plus a non-zero exit if the implementation chooses to fail closed there. ✓

All five assumptions resolve at their cited locations and have observable invalidation conditions. No assumption is contradicted by current source.

## Notable observations

These are observations and watch signals, not verdict-blockers.

1. **Adjacent capability creep — global authenticated submit.** Once a current global `form_definitions` row exists, `POST /api/v1/applications` with `scope.scope_kind='global'` becomes operationally possible for any actor holding `application.submit` at global scope. The test-intent track does not enumerate a regression check that this does not surprise existing chapter-scope submission. Step 6a/6b should add or document non-applicability. Not a proposal-design defect.

2. **psql image security posture.** Existing one-shot Jobs run as `runAsUser: 10001` with `readOnlyRootFilesystem: true`. The bitnami/legacy psql image typically runs as uid 1001 by default. The proposal's "where the image supports it" qualifier is honest but Step 6c must verify the rendered Pod actually starts and that `readOnlyRootFilesystem` does not block psql from creating its tmp/socket files. If it does, an `emptyDir` `volumeMount` is the standard fix and stays inside the slice's blast radius.

3. **Readiness-loop completeness.** The proposal commits to polling `form_definitions`, `activity_actions`, `activity_state_changes`, and `aggregate_heads` for existence before running the SQL. Step 6b (T2 migration readiness/order test) must verify the loop covers all four tables and the post-`wu-003a` text-shaped `aggregate_id` column, not just one table.

4. **Drift WARNING visibility.** T7's residual column flags log retention dependency. If `humility-local` Job logs are not retained beyond one Flux reconcile cycle, an operator may never see a drift WARNING. Not a Phase 4 blocker; a Phase 5/6 follow-up if Step 6b's drift test cannot capture log output deterministically.

5. **Direct-SQL vs. authority-grant tradeoff is a Phase-5 watch signal.** The proposal's A3 invalidation says hookpoint research may find a supported CLI/API bootstrap path with existing authority grants. Current code shows no such grant, so the SQL choice is the smaller blast radius today. If Phase 5 surfaces a clean way to grant a service identity `application_form.publish` (or to expose a one-shot bootstrap CLI that uses the existing authority substrate), the proposal should be revisited — not because the SQL is wrong, but because the service path preserves audit semantics that the SQL re-implements by hand.

6. **No e2e probe for `GET /api/v1/application-forms/current?scope_kind=global` after seed.** T4 covers it at the component level; T8 covers fresh-bringup public submit at e2e level. Adding a single `curl /api/v1/application-forms/current` step inside `infra/tests/e2e/tests/19-web-ui.sh` would close the round-trip cleanly. Step 6b/6c discretion; not a Phase 4 blocker.

7. **Concurrent two-Jobs scenario.** The idempotency test residual column acknowledges it. The CTE's `FOR UPDATE` plus `INSERT ... WHERE NOT EXISTS` shape is correct for transactional concurrency, but Flux/Kubernetes will not apply the same Job manifest concurrently in a steady-state cluster, so this is a low-likelihood residual. If Step 6b cannot exercise it, a `risk/init-122-test-residuals.md` entry under `temporal/concurrency` is appropriate.

## Verdict

The proposal targets the supported local public-intake surface and reduces a concrete current-state risk (fresh `humility-local` bringup leaving `POST /api/v1/public/applications` 404 because no current global `form_definitions` row exists, documented in the RCA). The assumption register is verifiable against current source, the supported-surface track is honest about manual rollback being FK-guarded by `applications.form_definition_id ON DELETE RESTRICT`, the test-intent track binds T1–T9 to assumptions A1–A5 with appropriate level selection (component for SQL/idempotency/officer-skip/drift/API-current-form, particular-integration for rendered GitOps and migration readiness, end-to-end for fresh bringup), and the blast radius is bounded to one local Kustomize entry plus one new manifest plus four already-migrated tables. Net value is positive on the current supported surface. The main residuals (adjacent-capability regression check, psql image rendering, readiness-loop coverage, drift WARNING visibility, Phase-5 hookpoint revisit, e2e current-form probe) are Step 6a/6b/6c obligations rather than proposal defects.

```
SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
```
