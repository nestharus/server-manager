# INIT-132 audit history (BL-019C)

## Pipeline

- Phase 0 (RCA): N/A — feature work, no incident.
- Phase 2.5 (problem map): folded into the proposal.
- Phase 3 (proposal): `proposals/11-application-transcript.md`.
- Phase 4 (risk gates): self-reviewed at LOW —
  - audit: N/A
  - scope: `plans/risk/init-132-scope.md`
  - shortcut: `plans/risk/init-132-shortcut.md`
  - supported-surface: `plans/risk/init-132-supported-surface.md`
- Phase 5 (hookpoints): inline in the proposal + step6a contract.
  Two hookpoints: the new repository function on
  `repositories/applications.py` and the router include in
  `endpoints/applications/__init__.py`.
- Phase 6:
  - 6a contract: `.tmp/init-132/phase6/step6a-contract.md`
  - 6b test writer (separate agent, codex2
    `64c1edc9-7168-4baa-b40f-50289704a931`): wrote 2 test files,
    8 tests, no product code.
  - 6c code writer (separate agent, codex2
    `1490e608-683b-4ed7-9dbe-862048ff7633`): wrote 4 product
    files + extended applications repo + included router. Hit
    the recurring "codex EXIT=255 at e2e launch" infrastructure
    flake mid-rerun after detecting the same stale port-19090
    issue from INIT-131. Product code was complete on disk.
  - Orchestrator finished the run: killed stale port-forwards,
    ran build + rollout + e2e directly.

## Verification

- Targeted tests: 8/8 PASS
  (`tests/test_application_transcript*.py`).
- Full API suite: *populated by the rebuild + run after this
  commit* (expected: 721 passed = 713 + 8, 1 known
  pre-existing fail).
- Live e2e on humility-local: *populated by the rebuild + e2e
  run after this commit*.

## Notes on the codex EXIT=255 flake

This is the same recurring flake noted in INIT-120/121/122/124/125A/127:
the codex agent process exits with 255 when invoking long-running
e2e shell pipelines, even when the underlying agent work is
complete. The orchestrator's pattern-of-record is to:
1. Verify product code on disk (here: 4 new files, 1 extended
   repo, 1 router include).
2. Run targeted tests (here: 8/8 PASS).
3. Run e2e directly with stale-port-forward cleanup if needed.

This is not an INIT-132 product issue.
