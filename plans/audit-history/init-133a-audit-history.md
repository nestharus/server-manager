# INIT-133A audit history (BL-019D-α)

## Pipeline

- Phase 0 (RCA): N/A — feature work, no incident.
- Phase 2.5 (problem map): the substrate audit
  `research/18-bl-019-substrate-audit.md` (BL-019 root) plus
  the proposal itself.
- Phase 3 (proposal): `proposals/12-application-list.md`.
- Phase 4 (risk gates): self-reviewed at LOW —
  - audit: N/A
  - scope: `plans/risk/init-133a-scope.md`
  - shortcut: `plans/risk/init-133a-shortcut.md`
  - supported-surface: `plans/risk/init-133a-supported-surface.md`
- Phase 5 (hookpoints): inline; pure extension of existing
  application modules. No new files for repo/service/contract;
  only the test file is new.
- Phase 6:
  - 6a contract: `.tmp/init-133a/phase6/step6a-contract.md`
  - 6b test writer (codex2 75b958d5-c6c3-4c74-8a09-373db158dd95):
    1 test file, 6 tests, no product code.
  - 6c code writer (codex2 c50bbed7-cf08-4843-8810-1f13ac9dc03e):
    extended contracts/applications.py, repositories/applications.py,
    services/applications.py, endpoints/applications/lifecycle.py.
    Hit the recurring "codex EXIT=255 at e2e launch" flake
    mid-rerun (same as INIT-132); product code complete on disk.
  - Orchestrator finished the run: killed stale port-forwards,
    ran build + rollout + e2e directly.

## Verification

- Targeted tests: 6/6 PASS
  (`tests/test_applications_list.py`).
- Full API suite: *populated by the rebuild + run after this
  commit* (expected: 727 passed = 721 + 6, 1 known
  pre-existing fail).
- Live e2e on humility-local: *populated by the rebuild + e2e
  run after this commit*.

## Decomposition note

BL-019D split into:
- BL-019D-α (this slice, INIT-133A): backend list endpoint
- BL-019D-β (next, INIT-133B): SPA officer review surface

The split was driven by the discovery that no list-applications
endpoint exists in the API. INIT-133B's queue page needs one.
Splitting keeps slices small and the dependency clear.
