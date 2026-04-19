# Structural Fix Report: Pitch Deck (Phase D)

## Scope

**Concern fixed:** Structural issues identified in `pitch-deck-skeleton.md` — visible templates, missing narrative steps (delayed hypothesis, late lens shift, absent "why this team" beat), weak borders, container headings without prose, repeated subsection template inside Risks and Mitigation.

**Categories addressed:**

- Heading rename: 1 (Solution)
- Border bridges added: 5 (Why Now → Market Opportunity, Adjacent Expansion → Solution, Competitive Positioning → Business Model, Phase 4 → Team, and the Roadmap intro which also answers Risk 4 → Roadmap)
- Container framing added: 3 (How It Works, Roadmap, The Ask)
- Template variation: 1 (Risk 4 rewritten as prose)
- Hypothesis acceleration: 1 (new closing paragraph in Problem section)

**Not fixed (pitch-deck conventions kept per prompt):** The Ask, Competitive Positioning, Why Now, Market Opportunity, Appendix / Q&A Preparation headings — all acceptable conventions the reader expects.

**Not fixed (preserved placeholders):** Team / Why Us bracketed placeholders, Cost Structure figures, Burn/Runway figures, Ask amounts. These remain bracketed per guardrail.

---

## Sample Fixes

### Instance 1: Hypothesis acceleration (end of Problem section)

**Before:** The Problem section ended at "officers burn out and leave." The reader then had to wait until the Solution section (after Current Landscape, Why Now, Market Opportunity) to hear the confident thesis.

**After:** Added a new closing paragraph:

> The shared failure across all of these patterns is that no tool owns the operational record. Operational state lives as vendor-held fragments scattered across ticket bots, application bots, spreadsheets, and DMs, and none of them can reconstruct what actually happened across the whole lifecycle of a member or a case. Operator-owned durable state is the structural answer, and the rest of this deck is about why that answer is buildable now and what it costs to build.

**Technique:** Plant the hypothesis at the earliest point where the reader has felt the pain. The rest of the deck now reads as elaboration of a claim already on the table, not as deferred reveal.

### Instance 2: Heading rename — Solution

**Before:**

```
## Solution

**Operator-owned durable state replaces vendor lock-in. Every operational decision is recorded once, and every subsystem consumes from the same causal chain.**

Humility replaces the fragmented bot stack with a single system where intake, cases, compliance, permissions, chapters, and governance share a unified audit chain.
```

**After:**

```
## Operator-Owned Durable State Replaces Vendor Lock-In

Every operational decision is recorded once, and every subsystem consumes from the same causal chain. Humility replaces the fragmented bot stack with a single system where intake, cases, compliance, permissions, chapters, and governance share a unified audit chain.
```

**Technique:** Heading now names the claim, not the rhetorical function. The redundant bold restatement was collapsed into the opening sentence so the value-prop is not duplicated.

### Instance 3: Adjacent Expansion → Solution border bridge

**Before:** Adjacent Expansion ended with the "Scope" paragraph about top-down TAM framing. Solution then opened with the bold thesis.

**After:** Added a bridge paragraph at the end of Market Opportunity:

> Across the wedge and the adjacent segments, the operational profile resolves to a single architectural requirement: one audit chain that spans every subsystem. The next section describes the system that makes that possible.

**Technique:** Sentence-level bridge that links buyer pain (operational profile) to the proposed architectural answer, so the move into Solution is earned in prose rather than by heading slot.

### Instance 4: Risk 4 template variation

**Before:** Four bold labels ("**The scenario.** ... **Why it matters.** ... **Mitigation.** ... **Milestone that proves the risk is contained.**") matched Risks 1, 2, and 3 exactly, making the repeated template conspicuous.

**After:** Risk 4 rewritten as three flowing paragraphs that still cover scenario, stakes, mitigation, and milestone, but without the visible bold scaffolding. The shift happens on the risk that pairs most naturally with prose (contributor sustainability is a narrative failure mode, not a point-in-time event).

**Technique:** Break cadence by varying the format of the last instance in a repeated pattern. Three instances establish the template; one departure signals the pattern was a tool, not a frame.

### Instance 5: The Ask container framing

**Before:** `## The Ask` went directly into `### For Investors / Financial Backers` with no framing prose.

**After:** Added intro:

> Three audiences have different-shaped commitments to make, and the ask below is broken out accordingly. Investors fund infrastructure and engineering runway. Community sponsors fund operational continuity for a codebase vendors cannot deprecate. Contributors and design partners trade time and feedback for early influence on Phase 1 and Phase 2 design. All three paths converge on the same near-term milestone: Phase 2 completion at the reference community and initial design partners.

**Technique:** Tell the reader what the section contains, why it is split three ways, and what the three audiences have in common before showing the three subsection asks.

---

## Full Change Inventory

| Location | Fix type | What changed |
|---|---|---|
| End of `## The Problem` | Hypothesis acceleration | Added closing paragraph stating "operator-owned durable state is the structural answer" before Current Landscape |
| `## Market Opportunity` intro | Border bridge (Why Now → Market Opportunity) | Added sentence linking window-timing to buyer-readiness |
| End of `### Adjacent Expansion` | Border bridge (Adjacent Expansion → Solution) | Added paragraph linking shared operational profile to single architectural requirement |
| `## Solution` heading | Heading rename | "Solution" → "Operator-Owned Durable State Replaces Vendor Lock-In"; collapsed bold restatement into body |
| `## How It Works` | Container framing | Added intro naming the three workflows and the shared audit chain |
| `## Business / Funding Model` intro | Border bridge (Competitive Positioning → Business Model) | Added two sentences linking architectural moat to community-owned funding posture |
| `## Roadmap` | Container framing + Risk 4 → Roadmap bridge | Added intro reframing the phase sequence as the risk-containment mechanism and noting coherent stopping points |
| `## Team / Why Us` | Border bridge (Phase 4 → Team) | Added intro paragraph explaining why operator-seat experience is load-bearing for the architecture |
| `## The Ask` | Container framing + Team → Ask bridge | Added intro naming the three audiences and the shared milestone |
| `### Risk 4: Volunteer contributor sustainability` | Template variation | Rewrote from four-bold-label template into three prose paragraphs |

---

## Major Changes Flag

Did this pass make any changes that could trigger the restart-from-earlier-phase rule?

- [ ] Moved a section
- [ ] Rewrote more than 30% of a section
- [ ] Changed the narrative arc
- [ ] Added or removed a section

**Assessment:** No major restructuring. One section heading was renamed, one subsection (Risk 4) was reformatted but retains all original claims and citations, and several bridge/intro paragraphs were added. No sections moved, no claims added or removed, no financial/team placeholders filled. Restart not triggered.

---

## Known Remaining Issues

1. **Team / Why Us still has bracketed placeholders.** The section now has a framing paragraph, but the credentialing content remains user-supplied. The Phase 4 → Team border is bridged by the new intro, but the true "why this team" beat cannot land until placeholders resolve. This was explicitly preserved per guardrail.

2. **Financial ask remains incomplete.** The Ask section has an audience-level intro, but commitment amounts, runway, burn, and target design-partner count are still bracketed. Preserved per guardrail.

3. **Risks and Mitigation template still visible on Risks 1–3.** Variation was applied only to Risk 4 to break cadence without rewriting every risk (which would change the factual content reviewers expect). A stricter reviewer might argue for varying Risk 3 as well; this was a judgment call to keep the fix minimal.

4. **Current Landscape still functions as a pitch-deck convention section.** No rename applied. The section carries its weight via content (five competitor categories with specific products and gaps), so the heading being functional rather than content-bearing is defensible as convention.

5. **Appendix / Q&A Preparation heading kept as convention.** Readers of pitch decks expect this label.

6. **Hypothesis sentence is now placed in Problem.** A reviewer focused on "hook and hypothesis point at the same object" might still prefer a version where the opening subtitle itself names operator-owned durable state. The subtitle currently says "unified guild-management system"; the hypothesis now lands two screens later. Kept the subtitle unchanged because restating it inside Problem preserves the deck's current opening scene while accelerating the thesis.

---

## Guardrail Compliance

- No em dashes introduced (grep clean).
- No banned openers in added sentences (But, And, So, Or, Still, Yet, However, Therefore).
- No team credentials fabricated.
- No financial numbers fabricated.
- All `[BRACKETED: ...]` placeholders preserved.
- All citations preserved.
- Sections working well (Problem body, How It Works workflow walkthroughs, Roadmap phase content, Competitive Positioning table) were not touched.
