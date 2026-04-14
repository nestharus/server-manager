# Philosophy Alignment Review

## Purpose

For problems the proposal is correctly aimed at (passed Stage 1), determine whether the proposal solves them in a way that embodies the product philosophy. The reference document is the product philosophy. The output is a list of violations — places where the proposal's design contradicts or fails to embody a principle.

This is Stage 2. It only applies to axes that passed Stage 1 (problem alignment). A proposal that is aimed at the wrong problem doesn't need philosophy review — it needs to be re-aimed first.

---

## Inputs

- **Product philosophy** (`philosophy.md`) — the principles that govern how we think and design
- **Proposal** (`proposal.md`) — the system design being reviewed
- **Problem review** (`problem review.md`) — Stage 1 output containing the list of aligned axes to review

## Outputs

- **Philosophy review** (`philosophy review.md`) — alignment findings for the proposer
- **Philosophy surfaces** (`philosophy surfaces.md`) — new philosophical concerns discovered during review (only written if surfaces are found)

---

## What this review does

For each axis that passed Stage 1:

1. Read the proposal's design decisions for that axis — schema objects, workflows, governance mechanisms, AI/ML approaches, constraints, and how it handles edge cases.

2. For each design decision, ask:
   - Is this decision traceable to a principle? Which one?
   - Does this decision contradict a principle? Which one, and how?
   - When the proposal encounters a difficulty on this axis, does it respond the way the philosophy would predict? Or does it take a shortcut that undermines a principle?

3. Classify the result:
   - **Embodied** — the design decisions on this axis are consistent with the philosophy. No output needed.
   - **Violation** — a specific design decision contradicts a specific principle. Describe both.
   - **Ungrounded** — a design decision exists that isn't traceable to any principle and isn't obviously wrong, but has no philosophical basis. This is a flag, not necessarily a problem — it may indicate a missing principle or a design decision that needs justification.

4. For ungrounded decisions, go one step further in two ways:

   a. **Check the implementation against existing principles.** An ungrounded decision may have a defensible intent that doesn't trace to a principle, but its *implementation mechanism* may violate existing principles. Examine not just what the decision is trying to achieve, but how the proposal achieves it. If the implementation contradicts a principle, that is a **violation**, not just an ungrounded finding.

   b. **Articulate the implicit principle.** If the decision is coherent and the reasoning is identifiable, describe the implicit principle the decision appears to embody — the philosophy expansion agent needs this to evaluate whether the philosophy should grow.

### Surface discovery

While performing the per-axis review, watch for philosophical concerns that the current philosophy does not address. These take three forms:

**Implicit principles.** An ungrounded design decision embodies a coherent philosophy that isn't articulated in any existing principle. The decision makes sense, but the principle behind it is missing from the philosophy.

**Principle tensions.** The proposal's approach to an axis reveals a tension between two existing principles that the philosophy doesn't acknowledge or resolve. The principles may coexist in general but conflict in this specific context.

**New philosophical axes.** The proposal introduces a concern — a way of thinking about design — that is entirely absent from the philosophy. Not a missing principle within an existing concern, but a concern the philosophy doesn't address at all.

If any philosophical surfaces are found, write them to `philosophy surfaces.md`. If none are found, do not create the file.

---

## What this review does NOT do

- **Does not re-check problem alignment.** That was Stage 1. If an axis is on the aligned list, accept it.
- **Does not evaluate implementation quality.** Whether a mechanism is well-engineered is not the question. Whether it embodies the principles is.
- **Does not prescribe solutions.** If a violation is found, the output is the violation — not a redesign.
- **Does not update the philosophy.** New philosophical concerns are captured in `philosophy surfaces.md` for the expansion agent. This review does not modify `philosophy.md`.
- **Does not address roadmap concerns.**

---

## How to read the philosophy

The philosophy contains:
- **Principles** (numbered) — each describes how we think about a specific aspect of design
- **Principle interactions** — how principles reinforce each other
- **Expansion guidance** — how principles apply when encountering new problem surfaces

When checking a design decision:
- First check against the specific principle most relevant to the decision
- Then check against principle interactions — a decision can satisfy one principle while violating another
- For new capabilities the proposal introduces, check against the expansion guidance

---

## Output format

### Violations

For each violation:
- **Axis:** which problem surface
- **Design decision:** what the proposal does
- **Principle violated:** which principle (by number and name)
- **How it's violated:** specific description of the contradiction
- **Why this matters:** what goes wrong if the violation persists

### Ungrounded decisions

For each ungrounded decision:
- **Axis:** which problem surface
- **Design decision:** what the proposal does
- **Observation:** why it's not traceable to a principle
- **Question:** what should the proposer consider — is this a missing principle, or a decision that needs justification?

### Structural concerns

Design-level issues that aren't about individual principle violations but about how the system's internal mechanisms interact:
- Are there places where mechanisms will conflict as the system grows?
- Are there governance gaps in the proposal's own internal design?

These must be system design concerns, not roadmap concerns.

---

## Philosophy surfaces output format (`philosophy surfaces.md`)

Only written if new philosophical concerns are found. Omit entirely if there are none.

### Implicit principles

For each ungrounded decision that embodies a coherent but unarticulated philosophy:
- **Axis:** which problem surface
- **Design decision:** what the proposal does
- **Implicit principle:** the principle the decision appears to embody (articulated by the reviewer)
- **Relationship to existing principles:** does it extend an existing principle, or is it independent?
- **Strength of evidence:** how many decisions in the proposal appear to follow this same implicit principle?

### Principle tensions

For each tension between existing principles revealed by the proposal:
- **Axis:** which problem surface
- **Principles in tension:** which principles (by number and name) and how they conflict in this context
- **How the proposal resolves it:** what the proposal does when the principles pull in different directions
- **What the philosophy doesn't say:** the guidance the philosophy is missing for resolving this tension

### New philosophical axes

For each concern the philosophy doesn't address at all:
- **Concern:** what the proposal is reasoning about that has no philosophical grounding
- **Evidence from proposal:** which design decisions reveal this concern
- **Why it's not covered:** why no existing principle addresses this — it's not a gap in an existing principle, it's an entirely absent concern
- **Questions for the user:** what direction should this axis point? What is the user's stance on this concern? (The expansion agent cannot resolve this without user input.)
