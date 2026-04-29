# INIT-131 audit history (BL-019B)

## Pipeline

- Phase 0 (RCA): N/A — feature work, no incident.
- Phase 2.5 (problem map): folded into the substrate audit in
  `research/18-bl-019-substrate-audit.md` (committed earlier
  with the BL-019 decomposition) plus the proposal itself.
- Phase 3 (proposal): `proposals/10-application-messages.md`
  (Q1..Q7 locked).
- Phase 4 (risk gates): self-reviewed at LOW —
  - audit: N/A (greenfield substrate; no failing surface)
  - scope: `plans/risk/init-131-scope.md`
  - shortcut: `plans/risk/init-131-shortcut.md`
  - supported-surface: `plans/risk/init-131-supported-surface.md`
- Phase 5 (hookpoints): inline in the proposal + step6a contract.
  The new substrate is purely additive; hookpoints reduce to
  "where does the new router get mounted" (`endpoints/applications/__init__.py`)
  and "where is the new permission named" (the permission
  constant).
- Phase 6:
  - 6a contract: `.tmp/init-131/phase6/step6a-contract.md`
  - 6b test writer (separate agent, codex
    `5050dca6-ad80-49e6-9835-87ac33664629`): wrote 4 test files,
    21 tests, no product code.
  - 6c code writer (separate agent, codex2
    `0918c151-d1de-46e9-bd12-ac326f079979`): wrote 6 files
    (migration, contracts, repo, service, endpoint, router
    include) per the contract; flagged
    `CONTRACT_REVISION_NEEDED` for a 6b fixture bug in TG-2 that
    granted the same active grant twice.
  - 6b fixture patch (orchestrator): made `_grant` helper
    idempotent on `DuplicateActiveGrantError` so the
    chapter-isolation test could publish two forms with the
    same operator at global scope. No assertion weakened.

## Verification

- Targeted tests: 21/21 PASS
  (`tests/test_application_messages_*.py -v`).
- Full API suite: 713 passed, 1 failed (the same pre-existing
  `test_compliance_evaluation_worker::test_manual_run_preserves_operator_attribution_on_roster_transition`
  that has been failing since INIT-127; unrelated). Up from 692
  in the INIT-129 baseline due to the +21 new tests.
- Live e2e on humility-local after API rebuild + rollout:
  *populated by the rebuild + e2e run after this commit*.

## Why the orchestrator stepped in for the 6b fixture fix

The original 6b test writer's `_grant` helper called
`grant_authority` unconditionally. The TG-2 chapter-isolation
test creates two applications, each requiring a published form,
each requiring `application_form.publish` granted to `operator`
at global scope. The second grant raises
`DuplicateActiveGrantError` before the message-substrate
authorization is even exercised.

This is a 6b test-author bug, not a contract or product-code
bug. The fix swallows the duplicate-grant error in the helper
with an explicit `pass` and a load-bearing comment about
fixture-reuse idempotency. No assertion is weakened, no
visibility check is bypassed, no intent is shifted.

The pattern matches INIT-127's "6b-patch" round (deterministic
timestamp fixture for HTTP-real-time test path) where the test
intent was sound but the setup mechanics were buggy. Same shape
of fix, smaller scope, applied directly here rather than via a
separate dispatched agent.

## Self-driven decisions (no user gate)

- Scope decisions (separate substrate vs reuse tickets, deferred
  fanout vs included, no real-time delivery) are documented in
  the proposal's Q1..Q7 + shortcut gate; all are implementation
  tradeoffs, not product positioning.
- BL-019B picked as the first BL-019 sub-slice over BL-019A
  because the substrate audit found BL-019A reduces to a
  permission-bundle constant + integration test — folded into
  the new permission constant introduced here.
