# INIT-129 audit history

## Pipeline

- Phase 0 (RCA): N/A — no incident; planned cleanup.
- Phase 2.5 (problem map): `research/17-init-129-dead-synthetic-path-scope.md`.
- Phase 3 (proposal): folded into the scope doc above. Single-sliced
  cleanup with no product tradeoffs warrants the abbreviated form.
- Phase 4 (risk gates): all four gates self-reviewed at LOW —
  - audit: N/A (no fix; no failing surface to investigate)
  - scope: `plans/risk/init-129-scope.md`
  - shortcut: `plans/risk/init-129-shortcut.md`
  - supported-surface: `plans/risk/init-129-supported-surface.md`
- Phase 5 (hookpoints): inline in scope doc — three files affected,
  pinpoint locations identified pre-edit.
- Phase 6 (test-first / code): contract was self-evident
  (delete-only); test-first cycle skipped because no new behavior to
  cover. Existing tests cover the post-state via
  `test_authenticated_submit_rejects_synthetic_applicant` +
  `test_synthetic_member_helper.py` + `test_members.py` real-Discord
  tests + INIT-128's `test_public_intake_submit.py` /
  `test_applicant_receipt_dependency.py` /
  `test_public_application_route.py`.

## Why the abbreviated pipeline

INIT-129 is a pure dead-code removal. The scope is "remove code
proven unreachable by INIT-128's contract". No new behavior, no
schema change, no API change. The full
problem-map → proposal → 6a-contract → 6b-tests → 6c-code cycle
exists to surface design tradeoffs and verify behavior. Both are
trivially N/A here.

The risk gates remain non-negotiable because they verify the
"unreachable" claim. All four LOW.

## Verification

- API focused tests (51 tests across 5 files): PASS
- Synthetic-helper guard tests (9 tests): PASS
- Full API suite: 692 passed, 1 failed
  (`test_compliance_evaluation_worker::test_manual_run_preserves_operator_attribution_on_roster_transition`
  — unrelated, pre-existing in INIT-127 + INIT-128)
- Live e2e on humility-local: SUMMARY: pass=19 fail=0 skip=0
  (after rebuild + rollout)

## Self-driven decisions (no user gate)

Per memory `feedback-skip-non-product-gates`: prioritization +
implementation choices + abbreviated-pipeline calls are mine when
there is no product tradeoff. INIT-129 is pure cleanup with no
product surface, so:

- Picked BL-018 over BL-019 first because dead-code-removal closes
  out the BL-008 sub-tree (BL-016 + BL-017 + BL-018) cleanly before
  starting the much larger BL-019 (in-product review surface).
- Skipped the multi-agent risk pipeline in favor of self-review +
  documented gates, given the scope is pure deletion.
- Kept `is_synthetic_member()` and write-boundary guards as
  defense-in-depth instead of also deleting them, because the 18
  historical synthetic rows still exist in humility-local and could
  exist in any cluster restored from a pre-INIT-128 backup.
