# Flow and Cohesion Fix Report: Executive Roadmap

## Scope

**Concerns fixed:** E1 (paragraph cohesion), E2 (causality), E3 (cognitive load)
**Sections reviewed:** Strategic Narrative, Phase Structure (risks and narrative borders), Competitive Positioning, Risk Register, Opportunity Cost Summary, Deferred Subsystems, Approval Package
**Sections excluded per prompt:** Executive Summary, Per-Slice Scoring Detail appendix, Value Slice Inventory

**Instances fixed:** 1
**Instances considered and skipped:** several (documented below under "Considered and skipped")

## Per-Concern Findings

### E1 — Paragraph cohesion

Nearly every target-area paragraph already has a clear topic sentence and develops one idea. Known-to-new chains are intact through the Strategic Narrative phase paragraphs, the Competitive Positioning sections, the Risk Register intro, and the Deferred Subsystems entries. No paragraphs needed splitting or refocusing.

### E2 — Causality

Every major claim in the target areas has a concrete "because" in the same paragraph or adjacent prose:

- Strategic Narrative Phase 1: "Building the substrate first is both the competitive bet (differentiated floor no competitor offers) and the risk-containment bet (decisions made in Phase 2 onward are reconstructable…)" — explicit dual because with parenthetical cash-outs.
- Strategic Narrative Phase 2: "Competing on features these markets already serve requires the Phase 1 substrate to distinguish the product" — named mechanism.
- Competitive Positioning "Distinctive advantage": each workflow claim names why the substrate matters.
- Risk Register rows: every mitigation column provides the causal action.

One borderline: Phase 3 risks bullet 1 contains "Managed by dependency discipline" — slightly abstract. The adjacent sentence "No intra-phase dependencies mean slice parallelism is preserved" supplies a concrete supporting fact. Considered a rewrite that specifies what "dependency discipline" means operationally, but concluded that elaboration would add a new operational claim and the existing orientation is adequate for the technical reader. Left as-is.

### E3 — Cognitive load

Strategic Narrative and Phase Structure paragraphs generally move concrete-before-abstract and cash out implications after dense enumerations. One place carried two distinct subjects (tickets and permissions) plus a shared dependency into one sentence, which reads as cognitive overload. Fixed (see below).

## Fix Applied

### Instance 1 (line 298, Competitive Positioning, "Distinctive advantage this sequence creates")

**Before:**
> Tickets inherit typed transitions tied to versioned policy, and permissions become declared intent with drift detection, both requiring the Phase 1 substrate that competitors' action-centric claim flows and role-hierarchy automation lack.

**After:**
> Tickets inherit typed transitions tied to versioned policy, and permissions become declared intent with drift detection. Both require the Phase 1 substrate that competitors' action-centric claim flows and role-hierarchy automation lack.

**Technique:** Period split. Separated the two parallel subject claims (tickets, permissions) from their shared dependency on the Phase 1 substrate. The shared-dependency sentence now stands alone and lands the cash-out directly, reducing cognitive load. No factual change, no new claim, "Both" carries the known referent forward in known-to-new order.

## Considered and Skipped

- **Phase Structure intro, line 59:** Second sentence is long ("naming the business outcome and success condition alongside the investment ask and phase-specific risks so contributors and approvers share a single view…"). Four-element enumeration with clear pairing structure. Skipped — the parallelism is legible and the sentence serves orientation; splitting would not improve clarity.
- **Risk Register intro, line 310:** Second sentence packs LOW rating, monitoring-vs-prediction framing, and a colon elaboration. Skipped — the colon structure is the cash-out for the preceding clause; splitting would flatten the logical relationship.
- **Phase 3 risks, "Managed by dependency discipline":** See E2 note above. Abstract phrase; kept for conservative reasons (concretizing would add a claim).
- **Risk Register row 3 and row 4 trigger indicators:** Somewhat abstract ("publishes declared-intent reconciliation…", "proposed scope item requires moderation-first framing…"). Skipped — the target audience (strategic/technical) can parse these terms, and concretizing would require adding claims about where monitoring signals would appear.
- **Strategic Narrative Phase 1 closing:** "reconstructable, reversible, and auditable" is a three-adjective parallel structure. Skipped as out of scope — this is a Rubric 2 (ban) concern, handled in earlier phases, not a flow/cohesion issue.

## Known Remaining Issues (reviewer flags, not in-scope fixes)

- **Factual inconsistency about VS-005 phase placement.** Line 25 (Exec Summary) and line 108 (Phase 1 risks) treat VS-005 as Phase 1 / Phase 1-eligible. Line 191 lists VS-005 in Phase 2 slices. Line 108 also says "delay here cascades to three later slices" while line 314 (Risk Register) names four downstream slices. This is a factual discrepancy outside the flow/cohesion remit but should be reconciled in a later pass.
- **Broader suites bullet (line 289)** uses a period where other Alternatives bullets use a colon, producing a grammatically detached "Combine multiple surfaces…" fragment. Formatting consistency issue, not flow/cohesion.

## Major Changes Flag

- [ ] Moved a section
- [ ] Rewrote more than 30% of a section
- [ ] Changed the narrative arc
- [ ] Added or removed a section

No restart trigger. Change is a single period split within one paragraph.
