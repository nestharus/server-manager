# INIT-125A Step 6b Test Residuals

## R1 — Migration Backfill Exhaustiveness

- Residual class: `bounded-model`
- Technique considered: `property-based`
- Scope: TG-1 migration backfill for `members.kind`.
- Budget or bound: Step 6b seeds the contract cases: one `public:%` legacy member and one non-public Discord member.
- Result: The emitted migration test verifies both discriminator branches, NOT NULL, CHECK values, idempotent Alembic re-run, and downgrade removal.
- Remaining residual: The test does not enumerate every production `members.discord_user_id` value. A non-numeric, non-`public:` historical value would be backfilled as `discord`.
- Invalidating inputs: Any production row where `discord_user_id NOT LIKE 'public:%'` and the row is not a Discord-origin member.
- Net-value impact: Does not change the net-value case; this is the proposal's A1 residual and is operator-verifiable with the proposal SQL.

## R2 — INIT-120 Web E2E Regression

- Residual class: `integration-hidden`
- Technique considered: `graph`
- Scope: TG-7 `19-web-ui` end-to-end regression.
- Budget or bound: Step 6b is test-authoring only and does not start the full local cluster or run the web UI E2E harness.
- Result: No new Step 6b test file is emitted for TG-7 by prompt contract. The output index maps TG-7 to the Step 6c obligation to run `19-web-ui`.
- Remaining residual: The browser/API/deployment integration remains unverified until Step 6c reports `SUMMARY: pass=19/19`.
- Invalidating inputs: Any Step 6c run where `19-web-ui` fails, is skipped without documented environment cause, or returns a summary other than `pass=19/19`.
- Net-value impact: Does not change the net-value case; it is a scheduled verification handoff, not a test-design gap.
