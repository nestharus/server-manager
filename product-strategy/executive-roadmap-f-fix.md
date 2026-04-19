# Adversarial Robustness Fix Report: Executive Roadmap

## Scope

**Concern fixed:** Rubric 4 (Adversarial Robustness) — F1 Intent alignment, F2 Pushback pass, F3 Worst case reader test, F4 Quote test, F5 Evidence toggle.
**Instances revised:** 2
**Instances skipped:** 0

Revisions were limited to surgical sentence-level fixes surfaced by the quote test. Executive Summary and other heavily-worked sections were not reopened per guardrails.

---

## Per-check findings

### F1 Intent alignment (private sentences not shown)

Private alignment check performed. The intended reader takeaway is that the ordering is structurally required and risk-contained; what the reader should not conclude is that gap claims are durable facts or that calendar dates are committed. This discipline informed the F4 revision on the "documented, not speculative" sentence, which drifted toward an overclaim the private-intent check flagged.

### F2 Pushback pass

**Strongest objection named in the prompt:** "Your gap classifications are 'no one ships X' claims that could be wrong because your market research is a point-in-time scan."

**Existing coverage:** Risk #3 (Market misread) in the Risk Register, `plans/risk/executive-market-misread.md` F-8, and the "re-run the market misread risk gate at each phase boundary" review cadence in the Approval Package.

**Stronger form surfaced:** The research snapshot concern applies not only at Phase 0 but compounds with every month of Phase 1→4 execution. A competitor shipping mid-execution reclassifies `gap` slices as `parity` or `table-stakes`, degrading the differentiation story. The document does handle this via phase-boundary refresh, but the Competitive Positioning section itself framed gaps as "documented, not speculative" — a framing that quietly fights the risk-gate mitigation by implying the claims are durable.

**Resolution:** The revised bullet (see F4 Instance 1) surfaces the time-bounded framing inside Competitive Positioning itself and cross-references Risk Register #3, so the time-boundedness is integrated rather than siloed in the risk section.

### F3 Worst case reader test

**Accusation 1:** "This is just a wish list dressed up as a roadmap."
**Preemption status:** Adequate. The scoring methodology (Appendix A), the composite formula with explicit inputs, the opportunity cost table, the dependency analysis, and the Risk Register with LOW ratings and trigger indicators collectively distinguish this from a wish list. The reader can audit the priority of every slice.

**Accusation 2:** "This is consultant-speak hiding the fact that nothing has been built."
**Preemption status:** Adequate. The document is explicit throughout: "contributor time," "Approval ask. Commit contributor effort," "No calendar dates are committed," "Value realization is expressed by phase completion, not by date." The memo is framed as a pre-build plan, not a post-build summary, and nowhere claims shipped capability.

No revisions required for F3.

### F4 Quote test

Three sentences pulled from different sections and read as hostile quotes:

**Sentence 1 (Competitive Positioning, line 304):** "Market gaps are documented, not speculative."
**Hostile read:** "They claim the gaps are 'documented' as if that makes them permanent. 'Documented' just means they wrote them down — the market moves every day."
**Verdict:** FAIL. "Documented, not speculative" sets up a false binary. The hostile reader extracts "documented" as a durability claim the research snapshot cannot support.
**Action:** Revised to sharpen the time-bounded framing and cross-reference the refresh mechanism. See Instance 1 below.

**Sentence 2 (Competitive Positioning, line 298):** "The Phase 1 governance substrate (trust, authority, audit, policy versioning) is the floor no competitor offers."
**Hostile read:** "'No competitor offers' — one counterexample ships tomorrow and this claim dies."
**Verdict:** SUSPECT. The document uses "no reviewed competitor" elsewhere to bound the claim to the research scope. This sentence drops the qualifier. In context, the "reviewed market" frame is established in the section, but extracted hostilely the sentence reads as a universal claim.
**Action:** Added the "reviewed" qualifier to match the document's consistent phrasing elsewhere. See Instance 2 below.

**Sentence 3 (Strategic Narrative, line 47):** "Every capability is a deliberate subsystem, not a toolkit primitive."
**Hostile read:** "This is marketing language dressed as discipline. What's the test for 'deliberate'?"
**Verdict:** PASS. The Non-goals enumeration immediately below (no scripting or arbitrary-automation surface, no AI-driven decisions, no real-time game integration, etc.) provides the concrete test. The sentence is grounded by the adjacent scope exclusions.
**Action:** None.

### F5 Evidence toggle

Scanned for empirical claims asserting facts without citation, hypothesis labels, or anecdote labels. Findings:

- Market-structure claims consistently cite `market research.md` with section numbers (e.g., §1, §2, §6, §7, Cross-cutting Findings).
- Operator-harm claims consistently cite `problem.md` with section numbers.
- Risk and dependency claims consistently cite the three `plans/risk/executive-*.md` documents with finding labels (F-1, F-3, F-4, etc.).
- Capability claims (what the system will do) are design commitments, not empirical claims, and are appropriately unlabeled.
- Non-goals and Deferred Subsystems are structural commitments, not empirical claims.

No uncited empirical claims surfaced that required labeling as hypothesis or anecdote. No revisions required for F5.

---

## Sample Fixes

### Instance 1 (line 304 bullet in Competitive Positioning → Why timing matters now)

**Before:**
- **Market gaps are documented, not speculative.** Every `gap` classification in the scoring traces to an explicit "Gap Analysis" section in the source research (`plans/risk/executive-market-misread.md` F-3).

**After:**
- **Gap claims trace to explicit research and are time-bounded to that snapshot.** Every `gap` classification in the scoring traces to a "Gap Analysis" section in the source research; the phase-boundary risk gate (Risk Register #3) refreshes these claims against fresh market data at each phase transition (`plans/risk/executive-market-misread.md` F-3).

**Technique:** Replaced the "documented, not speculative" binary with an explicit time-bounded framing. Cross-referenced Risk Register #3 so the refresh mechanism is co-located with the claim. This survives the hostile quote test because the sentence itself admits the scope and points at the mitigation.

### Instance 2 (line 298 in Competitive Positioning → Distinctive advantage)

**Before:**
**Distinctive advantage this sequence creates.** The Phase 1 governance substrate (trust, authority, audit, policy versioning) is the floor no competitor offers.

**After:**
**Distinctive advantage this sequence creates.** The Phase 1 governance substrate (trust, authority, audit, policy versioning) is the floor no reviewed competitor offers.

**Technique:** Added "reviewed" to bound the claim to the research scope, matching the document's consistent phrasing elsewhere (e.g., line 12, line 89, line 241). The hostile "one counterexample kills the claim" attack no longer lands because the claim is scoped to the reviewed field.

---

## Major Changes Flag

- [ ] Moved a section
- [ ] Rewrote more than 30% of a section
- [ ] Changed the narrative arc
- [ ] Added or removed a section

No boxes checked. The two revisions are surgical sentence-level edits within existing structure. No restart from Rubric 1 required.

---

## Guardrail Compliance

- No em dashes introduced.
- No sentences opening with banned words (But, And, So, Or, Still, Yet, However, Therefore).
- No new triads or banned structures introduced.
- No factual content changed. Both revisions sharpen existing claims rather than adding or removing claims.
- All citations preserved. Instance 1 adds a cross-reference to Risk Register #3 (internal) alongside the existing external citation.
- Executive Summary was not reopened.

---

## Known Remaining Issues

- The phrase "competitive bet" / "risk-containment bet" on line 37 uses "bet" twice in one sentence. Strategy-speak convention treats "bet" as a deliberate strategic commitment, and the parentheticals provide the rationale, so this survives the quote test. A reviewer with a strict view of hedging language may still flag it.
- The word "defensible" appears several times in Phase 1 framing ("defensible governance substrate," "defensible differentiation"). This is accurate given the cited gaps but could read as assertive if extracted. Current phrasing is consistent with the scope of the claim and cited.
- The "Not yet built" lists at the end of each phase description enumerate three-plus items in parallel form. These are inventory lists rather than prose triads and therefore do not trigger the Rubric 1 banned-list-shaped-prose rule, but a strict reviewer could flag the parallel structure.
