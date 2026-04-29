# INIT-127 Step 6b Test Residuals

## Residual R1 - TG-7 INIT-120 Live E2E Regression

- test_intent_item: TG-7 INIT-120 e2e regression
- named_risk: `init_120_live_e2e_regression`
- residual_class: execution-bound live-cluster residual
- attempted_or_considered_technique: Step 6b added component coverage in `services/web/tests/compat.spec.ts` proving the Login with Discord button can coexist with the anonymous public submit path. The prompt explicitly reserves the live `infra/tests/e2e/tests/19-web-ui.sh` rerun for Step 6c.
- scope: local full-stack browser/Kong/Pomerium/API persistence path for existing INIT-120 behavior after product code lands
- budget_or_bound: no new test file for TG-7; Step 6c must rerun the existing 19-web-ui lane and record `SUMMARY: pass=19/19`
- remaining_risk: a component-level mocked submit can pass while the local cluster browser flow or persistence check regresses after the OAuth UI/API implementation
- invalidating_inputs: Step 6c cannot produce a clean `19-web-ui` summary, or the Login with Discord surface breaks the anonymous submit path in the live lane
- changes_net_value_case: no. This residual is an execution gate already assigned to Step 6c, not a scope/design gap.

## Residual R2 - Live Authentik Blueprint Acceptance

- test_intent_item: TG-1 Authentik blueprint render
- named_risk: `applicant_objects_missing_or_accidentally_mutate_officer_oidc`
- residual_class: static-render-to-live-apply residual
- attempted_or_considered_technique: Step 6b parses committed blueprint YAML and asserts the required Discord Source, applicant Provider, Application, property mapping, and forbidden scope exclusions.
- scope: local Authentik controller applying the blueprint into the running Authentik 2026.2.2 instance
- budget_or_bound: no Tier 3 or live Authentik mutation in Step 6b; live apply belongs to Step 6c verification after product/manifest code lands
- remaining_risk: static YAML may satisfy the contract while a live Authentik model field differs or the blueprint apply fails at runtime
- invalidating_inputs: Authentik rejects the declared `authentik_sources_oauth.oauthsource`, `authentik_providers_oauth2.oauth2provider`, property mapping, or Application model fields during local apply
- changes_net_value_case: no. It remains an A1 runtime validation item for Step 6c/local verification.
