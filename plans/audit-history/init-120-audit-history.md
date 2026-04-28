# Audit history — INIT-120 public application intake

## Purpose

Track the proposal/risk-gate revise/review loop for INIT-120. Round 1
returned audit=MEDIUM with all other gates LOW; the proposal was
revised narrowly and the gates are re-running in round 2.

## Artifact lineage

- Phase 0 RCA: `.tmp/rca/public-application-intake-FINDINGS.md`
- Phase 2.5 problem map: `research/02-public-application-intake-problem-map.md`
- Phase 3 proposal: `proposals/02-public-application-intake.md`
- Phase 4 round-1 risk reports:
  - `plans/risk/init-120-audit.md` (MEDIUM)
  - `plans/risk/init-120-scope.md` (LOW)
  - `plans/risk/init-120-shortcut.md` (LOW)
  - `plans/risk/init-120-supported-surface.md` (LOW)
- Phase 3 round-2 revision prompt + note:
  `.tmp/init-120/phase3-revision-prompt.md`,
  `.tmp/init-120/phase3-revision-r2.md`

## Round summaries

### Round 1 — Phase 3 proposal reviewed

- Artifact under review: `proposals/02-public-application-intake.md`
- Round artifacts: the four `plans/risk/init-120-*.md` reports above.
- Report artifacts:
  - report index: none
  - PDFs: none
  - uploaded artifact URL: none
  - screenshots: none
  - non-UI evidence: none
- Prior finding counters:
  - closed: 0
  - intact: 0
  - weakened: 0
  - regressed: 0
  - not closed: 0
- New findings:
  - `R1-F01` — non-blocking; audit MEDIUM: proposal does not name the
    Step 6b residual-risk artifact path; ancestor chain: none;
    oscillation: none.
- Oscillation:
  - same-label: 0
  - same-family: 0
  - fix-created: 0
  - two-generation: 0
  - named three-generation: 0
- Decompose trigger: not fired; reason: only one localized non-blocking
  finding.
- Watch signals for next round:
  - audit item 7 — residual-risk artifact path naming.
- Verdict or determination: continue (revise + re-run all four).
- Role outputs:
  - audit (gpt-high): MEDIUM, plans/risk/init-120-audit.md
  - scope (claude-opus): LOW, plans/risk/init-120-scope.md
  - shortcut (claude-opus): LOW, plans/risk/init-120-shortcut.md
  - supported-surface (claude-opus): LOW,
    plans/risk/init-120-supported-surface.md
- Next handoff: Phase 3 proposer reads `plans/risk/init-120-audit.md`
  item 7 and adds the residual-artifact callout.

### Round 2 — revised proposal reviewed

- Artifact under review: `proposals/02-public-application-intake.md`
  (revised; +4 lines, new subsection `### Residual-risk artifact`
  inside `## Test-intent track`).
- Round artifacts:
  - `plans/risk/init-120-audit.md` (LOW)
  - `plans/risk/init-120-scope.md` (LOW)
  - `plans/risk/init-120-shortcut.md` (LOW)
  - `plans/risk/init-120-supported-surface.md` (LOW)
- Report artifacts: none.
- Prior finding counters:
  - closed: 1 (R1-F01 closed by `### Residual-risk artifact`
    subsection)
  - intact: 0
  - weakened: 0
  - regressed: 0
  - not closed: 0
- New findings: none.
- Oscillation:
  - same-label: 0
  - same-family: 0
  - fix-created: 0
  - two-generation: 0
  - named three-generation: 0
- Decompose trigger: not fired.
- Watch signals for next round: none active.
- Verdict or determination: continue (advance to Phase 5).
- Role outputs:
  - audit (gpt-high, invocation `e4b10c29-cf37-44c0-a114-00a9dbdcbe7d`):
    LOW, plans/risk/init-120-audit.md
  - scope (claude-opus, invocation `33423ddb-a5ce-4366-aa22-2466c4d8b6f0`):
    LOW, plans/risk/init-120-scope.md
  - shortcut (claude-opus, invocation `5314475b-ab68-4614-ac50-17de4e2c860c`):
    LOW, plans/risk/init-120-shortcut.md
  - supported-surface (claude-opus, invocation
    `0354f59d-b987-4720-a2a9-b1b4a697166d`): LOW (termination NONE),
    plans/risk/init-120-supported-surface.md
- Process-tree review: parallel risk agents were
  orchestrator-dispatched siblings (no single sub-orchestrator
  subtree). Inline equivalence check: each report named the correct
  model, emitted the required `SUPPORTED_SURFACE_TERMINATION` and
  `VERDICT` lines, and produced its own log under
  `.tmp/init-120/phase4-*-r2.log`. No sibling violated isolation;
  all four reports write to distinct paths.
- Next handoff: Phase 5 hookpoints agent reads
  `proposals/02-public-application-intake.md`,
  `research/02-public-application-intake-problem-map.md`, and
  `plans/risk/init-120-supported-surface.md`.

## Role histories

### Writer (Phase 3 proposer, gpt-high)

- Round 1: produced initial proposal with 4 product calls (Group A)
  and 5 implementation decisions (Group B); user confirmed Group A
  recommendations as-is.
- Round 2: applied 4-line revision to Test-intent track per audit
  item 7; no other sections touched.

### Reviewer (Phase 4 risk gates)

- Audit (gpt-high) — Round 1 MEDIUM (item 7 partial); Round 2 LOW.
- Scope (claude-opus) — Round 1 LOW; Round 2 LOW.
- Shortcut (claude-opus) — Round 1 LOW; Round 2 LOW.
- Supported-surface (claude-opus) — Round 1 LOW (termination NONE);
  Round 2 LOW (termination NONE).

## Decision register

- D1 (round 1, locked): A1=Opt 1 (anonymous Cedar principal on
  `POST /api/v1/public/applications`). Confirmed by user.
- D2 (round 1, locked): A2=Opt 1 (synthetic placeholder member per
  submission). Confirmed by user.
- D3 (round 1, locked): A3=Opt 2 (web first-class for submission;
  Discord first-class for review). Confirmed by user.
- D4 (round 1, locked): A4=Opt 2 (Postgres-via-API Discord submission
  service is the convergence target). Confirmed by user.

## User Q&A Inputs

- 2026-04-28: orchestrator surfaced A1..A4 with proposal recommendations;
  user response: "That is fine." All four locked.

## Watch signals

- Residual-risk artifact path naming (R1-F01 watch).
- No new oscillation chains expected.

## Summarization tail

None yet — round 2 is the second round; below decompose threshold.

## Final state

Phase 4 cleared after round 2: all four risk gates LOW, supported-surface
termination NONE. Phase 5 hookpoint research is the next phase.
