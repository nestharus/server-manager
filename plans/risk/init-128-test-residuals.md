# INIT-128 Step 6b Test Residuals

## Residual R1 - Concurrent real-member resolver interleavings

- Residual class: bounded concurrency coverage.
- Named risk: `real_discord_member_race_duplicate_insert`.
- Technique attempted or considered: TG-4 adds concurrent same-snowflake resolver calls with `asyncio.gather` and asserts both calls return one `members.kind='discord'` row. Exhaustive scheduler control or database lock-step fault injection was considered, but it would require implementation-specific hooks not present in the Step 6a contract.
- Scope: `resolve_or_create_real_discord_member(db, discord_user_id)`.
- Budget or bound: one concurrent pair against the real migrated database and the unique `members.discord_user_id` boundary.
- Result: test coverage verifies the externally observable convergence contract, not every possible internal interleaving.
- Remaining residual: an implementation could still contain a rare race outside the exercised pair timing if it does not rely on the locked `ON CONFLICT DO NOTHING + SELECT` posture.
- Invalidating inputs: implementation that exposes deterministic race hooks, or a repository helper whose conflict behavior can be instrumented without coupling tests to product internals.
- Net-value impact: does not change the net-value case; the bounded test still fails the known duplicate-insert class and the database unique constraint remains the contract boundary.

## Residual R2 - E2E receipt secret provisioning

- Residual class: environment fixture dependency.
- Named risk: `e2e_receipt_required_submit_false_green`.
- Technique attempted or considered: TG-8 updates `19-web-ui.sh` to require `server-manager-e2e-fixtures` keys and updates `browser-flow.mjs` to compute and inject a test-mode HMAC receipt before `/applications`.
- Scope: local e2e environment only.
- Budget or bound: e2e fails closed when the fixture-only secret is absent or empty.
- Result: the test harness verifies the browser submit contract once the fixture-only secret exists, but Step 6b cannot create or apply Kubernetes secrets as test-writing scope.
- Remaining residual: 6c or deployment setup must provide the fixture-only secret with the same signing key as the local API.
- Invalidating inputs: a committed fixture manifest or runbook that provisions `server-manager-e2e-fixtures` before `19-web-ui.sh` runs.
- Net-value impact: does not change the net-value case; failure is explicit and prevents an anonymous-submit false green.
