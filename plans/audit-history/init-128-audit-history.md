# Audit history — INIT-128 receipt-required submit

## Purpose
Track round-2 cycle after Phase 4 round 1 returned shortcut=MEDIUM
(e2e-split contradiction: "remove anon path" + "keep 19-web-ui as
legacy anon spec" can't both be true).

## Round summaries

### Round 1
- Reports: audit=LOW, scope=LOW, surface=LOW, shortcut=MEDIUM
- New finding R1-F01: shortcut MEDIUM Q5 (e2e split contradiction).
- Decompose trigger: not fired.
- Verdict: continue (revise + re-run all four).

### Round 2 — pending
- Revised proposal: 19-web-ui converted in this slice to seed
  receipt + test the new path; no new spec; suite stays at 19.
- Re-running all 4 risk gates.

## Decision register
- D1 (locked, round 1): RCA Option B (receipt-required, anon
  removed)
- D2 (locked, round 1): no member_links table
- D3 (locked, round 1): orphan stance for pre-BL-017 synthetics
- D4 (locked, round 1): notification event emitted; DM
  materialization deferred to BL-020 (depends on BL-019)
- D5 (locked, round 2): 19-web-ui updated in this slice to
  exercise receipt-required path

## Final state
Pending round-2 verdicts.
