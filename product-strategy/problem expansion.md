# Problem Expansion

## Purpose

Evaluate newly discovered problem surfaces and integrate them into the problem definition. The problem alignment review may uncover problems the proposal addresses that the problem definition doesn't describe, or reveal additional depth within existing axes. This agent determines whether those surfaces are genuine and updates the problem definition accordingly.

---

## Inputs

- **Problem surfaces** (`problem surfaces.md`) — new surfaces discovered by the problem alignment review
- **Problem definition** (`problem.md`) — the current problem definition
- **Problem alignment instructions** (`problem alignment.md`) — the review agent instructions containing the axis reference table

## Outputs

- **Updated problem definition** (`problem.md`) — with new sections or expanded existing sections
- **Updated problem alignment instructions** (`problem alignment.md`) — with new rows in the axis reference table (if new axes were added)

---

## Process

### Step 1: Validate each surface

For each surface in `problem surfaces.md`, determine whether it is genuine:

1. **Is it already covered?** Read the problem definition carefully. The surface may already be described — perhaps under a different name, as a sub-problem of an existing axis, or implicitly within a broader discussion. If it's covered, discard it.

2. **Is it real?** Does this surface describe a genuine difficulty that the target communities face? Or is it an artifact of the proposal's design — a problem that only exists because the proposal chose a particular approach? If it's proposal-specific, discard it.

3. **Is it in scope?** Does this surface belong in the problem definition? Some real problems are outside the scope of what this problem definition covers. If it's out of scope, discard it.

### Step 2: Classify surviving surfaces

For each surface that passes validation:

- **New axis** — the surface describes a problem area the problem definition doesn't cover at all. It needs its own section.
- **Axis expansion** — the surface adds depth to an existing axis. It describes a sub-problem, interaction, or difficulty the existing section doesn't articulate.

### Step 3: Draft expansions

For each new axis:
1. Write a new section for the problem definition following the style and structure of existing sections.
2. The section should describe the core difficulty — why this problem is hard and resists solution — not a feature wish list.
3. Assign it a section number (continuing from the last existing section).

For each axis expansion:
1. Draft additional content for the existing section.
2. The expansion should describe the newly revealed difficulty in the context of the existing section's treatment.
3. Do not rewrite the existing section. Add to it.

### Step 4: Update the axis reference table

If new axes were added to the problem definition, add corresponding rows to the axis reference table at the bottom of `problem alignment.md`. Assign axis numbers continuing from the last existing axis.

---

## What this agent does NOT do

- **Does not modify the proposal.** The proposal may have prompted the discovery, but this agent only updates the problem definition.
- **Does not modify the philosophy.** Philosophical implications of new problem surfaces are a separate concern.
- **Does not evaluate alignment.** Whether the proposal is aligned with the new or expanded axes is for the next review cycle to determine.
- **Does not invent problems.** Every surface must trace back to a finding in `problem surfaces.md`. The agent validates, classifies, and integrates — it does not speculate about additional problems.
- **Does not remove or rewrite existing content.** The problem definition grows; it does not shrink. Existing descriptions may be insufficient, but they are not wrong — add depth, don't replace.

---

## Quality checks

Before writing updates:

- [ ] Every new section describes a core difficulty, not a feature or solution
- [ ] Every expansion adds depth to an existing axis, not a tangent
- [ ] New sections follow the style and structure of existing sections
- [ ] The axis reference table is consistent with the problem definition's sections
- [ ] No surface was added that is already covered elsewhere in the problem definition
- [ ] No surface was added that is proposal-specific rather than domain-general