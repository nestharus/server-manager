# INIT-124 Step 6b Test Residuals

## R-1: INIT-120 Web E2E Runtime Proof

- Test-intent item: TG-9 — INIT-120 e2e regression.
- Residual class: integration-hidden.
- Technique considered: chaos.
- Scope: `infra/tests/e2e/tests/19-web-ui.sh` runtime proof that Step 6c will execute and report `pass=19/19`.
- Budget or bound: Step 6b does not start the full local cluster or mutate product code; it only maps the existing e2e artifact into the output index.
- Result: existing e2e artifact identified; no new test file emitted by contract.
- Remaining residual: Step 6b cannot prove the live `19-web-ui` pass count in this invocation.
- Invalidating inputs: Step 6c cannot run `infra/tests/e2e/tests/19-web-ui.sh`, or it runs with a result other than `pass=19/19`.
- Net-value effect: unchanged; this is a runtime proof handoff, not a missing product-guard test.

## R-2: Pre-Existing Synthetic Pollution Reads

- Test-intent item: supported-surface residual from approved proposal and risk.
- Residual class: combinatorial/path-state.
- Technique considered: graph.
- Scope: already-polluted owner workload rows, trust profile reads, roster reads, compliance enumeration, archive counts, and silent succession omit behavior.
- Budget or bound: INIT-124 Step 6b covers new write-boundary rejection and real-member positive paths only.
- Result: no read-side hardening tests emitted because read-side cleanup is anti-scope for INIT-124 and deferred to BL-008.
- Remaining residual: pre-existing synthetic rows may still surface through read paths until a cleanup/read-hardening slice lands.
- Invalidating inputs: production data contains synthetic UUIDs in `roster_entries.member_id`, `applications.owner_id`, or trust rows and operators expect INIT-124 to hide or repair them.
- Net-value effect: unchanged; the approved slice is explicitly guard-only.
