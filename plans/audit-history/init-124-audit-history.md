# Audit history — INIT-124 synthetic member guard

## Purpose
Track the round-2 revise/review cycle after Phase 4 round 1
returned audit=MEDIUM (assumption-register invalidation +
test-intent metadata gaps) with all other gates LOW.

## Artifact lineage
- RCA: `.tmp/rca/synthetic-public-member-pollution-FINDINGS.md`
- Phase 2.5 problem map: `research/08-synthetic-member-guard-problem-map.md`
- Phase 3 proposal (rev0 + rev1): `proposals/05-synthetic-member-guard.md`
- Phase 4 round-1 risk reports:
  - `plans/risk/init-124-audit.md` (MEDIUM)
  - `plans/risk/init-124-scope.md` (LOW)
  - `plans/risk/init-124-shortcut.md` (LOW)
  - `plans/risk/init-124-supported-surface.md` (LOW, term=NONE)
- Phase 3 round-2 revision prompt + note:
  `.tmp/init-124/phase3-revision-prompt.md`,
  `.tmp/init-124/phase3-revision-r2.md`

## Round summaries

### Round 1
- New finding R1-F01: audit MEDIUM — A1/A2 missing invalidation
  source; test-intent track missing fixture/assumption-link/
  residual fields per impl-pipeline.md:91-92.
- Decompose trigger: not fired (single localized non-blocking
  finding).
- Verdict: continue (revise + re-run all four).
- Watch signals: assumption-register completeness, test-intent
  metadata.

### Round 2 — pending re-run
- Artifact: revised proposal (4 lines added per revision note).
- Re-running all 4 risk gates after deleting round-1 reports per
  impl-pipeline.md:108.

## Decision register
- D1 (locked, round 1): Option 1 from RCA (write-boundary guard,
  no schema column).
- D2 (locked, round 1): predicate `is_synthetic_member()` in
  `services/api/app/services/members.py`.

## Final state
Pending round-2 verdicts.
