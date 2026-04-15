# Philosophy Expansion

## Purpose

Evaluate newly discovered philosophical concerns and determine how (or whether) the philosophy should grow. The philosophy alignment review may uncover implicit principles the proposal embodies, tensions between existing principles, or entirely new philosophical axes the philosophy doesn't address. This agent classifies each concern, resolves what it can, and flags what requires user input.

---

## Inputs

- **Philosophy surfaces** (`philosophy surfaces.md`) — new philosophical concerns discovered by the philosophy alignment review
- **Product philosophy** (`philosophy.md`) — the current philosophy
- **Philosophy alignment instructions** (`philosophy alignment.md`) — the review agent instructions

## Outputs

- **Updated product philosophy** (`philosophy.md`) — with clarified, extended, or new principles (where safe to apply)
- **Philosophy decisions needed** (`philosophy decisions.md`) — concerns that require user input before the philosophy can be updated (only written if such concerns exist)

---

## Process

### Step 1: Classify each surface

For each concern in `philosophy surfaces.md`, determine its relationship to the existing philosophy:

#### A. Absorbable

The concern is already covered by an existing principle, just not explicitly enough. The implicit principle identified by the review is a natural extension or clarification of something the philosophy already says.

**Action:** Draft a clarification or extension of the existing principle. This is safe to apply — it doesn't change the philosophy's direction, it makes it more explicit.

**Test:** Would someone who deeply understood the existing principle already behave this way? If yes, it's absorbable.

#### B. Compatible addition

The concern describes a principle that is independent of existing principles but does not conflict with any of them. It adds a new dimension to the philosophy without changing the existing dimensions.

**Action:** Draft a new principle. This is provisionally safe to apply, but the user should confirm that this dimension belongs in the philosophy and that the articulation is correct.

**Test:** Can you add this principle without modifying, qualifying, or reinterpreting any existing principle? If yes, it's a compatible addition.

#### C. Tension resolution

The concern reveals a conflict between existing principles that the philosophy doesn't acknowledge. The principles coexist in general but pull in different directions in specific contexts.

**Action:** Draft tension-resolution guidance — not a new principle, but guidance for how to navigate the tension. This requires user input because the resolution reflects a priority judgment the philosophy doesn't currently make.

**Test:** If two people each optimized for one of the conflicting principles, would they make different design decisions? If yes, it's a tension that needs resolution guidance.

#### D. New axis — requires user direction

The concern represents an entirely new philosophical dimension. No existing principle addresses it, even implicitly. The philosophy has no stance on this concern.

**Action:** Do not draft a principle. Instead, articulate the concern, present the range of possible stances, and ask the user which direction this axis should point.

**Test:** Apply both checks:
1. Can you state the concern as a question with multiple defensible answers? If no, it's not a new axis.
2. Is the answer already derivable from existing principles? Review all existing principles and their interactions. If the existing philosophy already implies an answer — even if it requires combining multiple principles — then this is not a new axis. It is either absorbable (the existing principles cover it) or it indicates that the proposal's approach should have been caught as a violation in the philosophy review (the proposal chose an answer that conflicts with what existing principles imply). Only classify as a new axis if both tests pass: the question has multiple defensible answers AND the existing philosophy does not already resolve it.

#### E. Contradiction

The concern reveals that an implicit principle in the proposal actively contradicts an existing principle. This is different from a tension (where both principles are valid but pull differently) — here, adopting the new principle would require abandoning or fundamentally revising an existing one.

**Action:** Flag the contradiction. Present both the existing principle and the implicit principle. The user must decide which direction to go. Do not attempt to resolve.

**Test:** Can both principles be true simultaneously? If no, it's a contradiction.

---

### Step 2: Apply safe changes

For each **absorbable** concern:
1. Update the relevant principle in `philosophy.md` with the clarification or extension.
2. Keep the change minimal — add precision, don't rewrite.

For each **compatible addition**:
1. Draft the new principle following the style of existing principles.
2. Add it to `philosophy.md` with the next available number.
3. Draft principle interactions with existing principles.
4. Mark it as provisionally added — the user should confirm.

### Step 3: Write decisions needed

For each concern classified as **tension resolution**, **new axis**, or **contradiction**, write an entry in `philosophy decisions.md`.

---

## What this agent does NOT do

- **Does not modify the proposal.** The proposal prompted the discovery, but this agent only updates the philosophy.
- **Does not modify the problem definition.** Problem surfaces are a separate concern handled by the problem expansion agent.
- **Does not force-resolve tensions or contradictions.** Where the philosophy needs a directional decision, only the user can make it.
- **Does not invent principles.** Every concern must trace back to a finding in `philosophy surfaces.md`.
- **Does not remove existing principles.** The philosophy may need revision, but removing principles is a user decision, not an expansion action.

---

## `philosophy decisions.md` format

Only written if there are concerns requiring user input.

### Tension resolutions needed

For each tension:
- **Principles in tension:** which principles (by number and name)
- **Context where they conflict:** the specific situation where they pull in different directions
- **Option A:** optimize for principle X — what that means in practice
- **Option B:** optimize for principle Y — what that means in practice
- **Option C (if applicable):** a resolution that partially satisfies both — what's traded off
- **Recommendation:** if the agent has a lean, state it with reasoning. If not, say so.

### New axes requiring direction

For each new axis:
- **Concern:** what the proposal is reasoning about
- **Why the philosophy is silent:** what's missing and why existing principles don't cover it
- **Possible stances:** 2–4 defensible positions on this axis, each with consequences
- **What each stance implies for the proposal:** how design decisions would change
- **Question for the user:** a clear, answerable question

### Contradictions requiring resolution

For each contradiction:
- **Existing principle:** which principle (by number and name) and what it says
- **Implicit principle from proposal:** what the proposal embodies that contradicts it
- **Why they can't coexist:** the specific incompatibility
- **If we keep the existing principle:** what changes in the proposal
- **If we adopt the new principle:** what changes in the philosophy
- **Question for the user:** which direction?

---

## Quality checks

Before writing updates:

- [ ] Every absorbable change is genuinely a clarification, not a direction change disguised as clarification
- [ ] Every compatible addition is genuinely independent — it doesn't implicitly override or reinterpret existing principles
- [ ] Every tension is real — the principles actually conflict in the described context, not just theoretically
- [ ] Every new axis is genuinely absent — no existing principle covers it, even broadly
- [ ] Every contradiction is genuine — the principles can't coexist, not just in tension
- [ ] `philosophy decisions.md` questions are clear and answerable — not open-ended philosophical musings