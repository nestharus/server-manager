# INIT-122 Step 6b Test Residuals

## R1 — Full Flux/Alembic Scheduling Race

- Residual class: `temporal/concurrency`
- Technique considered: `chaos`
- Scope: static manifest/order tests verify resource order, `pg_isready`, and `psql -v ON_ERROR_STOP=1`; they do not model all Flux sibling-resource scheduling paths.
- Budget or bound: Step 6b is test authoring only; no fresh cluster is created in this phase.
- Result: TG-3 and TG-4 encode the static and validator checks. Step 6c must prove the Job completes in cluster.
- Remaining residual: a cluster could schedule the seed Job while schema migrations are incomplete if Step 6c omits a sufficient readiness loop.
- Invalidating inputs: seed Job reaches `psql -f /seed/seed.sql` before migrated tables exist and fails permanently.
- Net-value impact: does not change the net-value case because TG-4 and TG-5 are explicit follow-on gates.

## R2 — Simultaneous Seed Job Executions

- Residual class: `temporal/concurrency`
- Technique considered: `model-checking`
- Scope: TG-1 verifies sequential idempotency, not two simultaneous Kubernetes Job pods executing the seed SQL.
- Budget or bound: no concurrent database scheduler or duplicate Job injection is run in Step 6b.
- Result: tests assert rerun row counts and version remain unchanged.
- Remaining residual: two concurrent seed executions could expose a race if Step 6c omits transactional locking.
- Invalidating inputs: two seed executions create duplicate actions/state changes or fail with a uniqueness violation instead of leaving one accepted aggregate sequence.
- Net-value impact: low; Flux normally reconciles one Job resource, but the SQL must still be transactionally guarded.

## R3 — Drift Warning Visibility

- Residual class: `integration-hidden`
- Technique considered: `mutation`
- Scope: proposal test intent includes drift warning observability, but the Step 6a/user TG list does not require a drift fixture.
- Budget or bound: no retained Kubernetes Job logs are available in Step 6b.
- Result: no drift-warning test was emitted.
- Remaining residual: a drifted deterministic seed row may warn only in ephemeral Job logs.
- Invalidating inputs: deterministic seed row content is changed and operators cannot observe the warning outcome.
- Net-value impact: does not change the net-value case; it is an observability follow-up, not a supported-surface blocker.

## R4 — Operator Rollback Guard

- Residual class: `integration-hidden`
- Technique considered: `graph`
- Scope: proposal test intent names a rollback guard, but Step 6a does not define a cleanup script or operator runbook artifact for Step 6b to test.
- Budget or bound: no rollback artifact exists in the contract.
- Result: no rollback-guard test was emitted.
- Remaining residual: a future manual cleanup command could try to delete a referenced seed form.
- Invalidating inputs: cleanup deletes or attempts to delete a `form_definitions` row referenced by `applications.form_definition_id`.
- Net-value impact: low for this slice because rollback remains manual and FK-guarded by the database.

## R5 — Fresh Bringup E2E

- Residual class: `emergent-interaction`
- Technique considered: `chaos`
- Scope: TG-5 is a required rerun of `infra/tests/e2e/tests/19-web-ui.sh` on fresh bringup, but Step 6b only records the expectation.
- Budget or bound: Step 6c owns the product code and fresh-bringup run.
- Result: no new e2e test file was emitted.
- Remaining residual: fresh local GitOps may still require manual SQL if the Job does not complete before the browser flow.
- Invalidating inputs: `19-web-ui.sh` fails on a fresh cluster unless an orchestrator-applied SQL workaround is used.
- Net-value impact: unchanged until Step 6c verification; TG-5 is the final supported-surface proof.
