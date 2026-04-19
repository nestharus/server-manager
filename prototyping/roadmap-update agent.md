# Roadmap Update Agent

## Purpose

Take the prototype's findings and propose specific updates to the engineering roadmap (and executive roadmap if strategically relevant). The agent proposes — the user decides whether to apply.

---

## Files

| File | Role |
|---|---|
| `prototyping/<slug>/findings.md` | Read-only input — the synthesis |
| `product-strategy/engineering roadmap.md` | Read-only reference — current roadmap |
| `product-strategy/executive roadmap.md` | Read-only reference |
| `prototyping/<slug>/roadmap-update.md` | Written by this agent |

---

## Process

1. Read `prototyping/<slug>/findings.md`.
2. Identify roadmap claims that need updating:
   - Refined magnitudes that differ from current roadmap
   - New risks that should appear in risk sections
   - New dependency acknowledgments
   - Scope clarifications (e.g., "the prototype revealed this slice should be split in two")
3. Check whether findings affect the executive roadmap:
   - Does the refined magnitude change the value/cost tradeoff?
   - Does a new risk change strategic priority?
4. Draft specific updates — not vague guidance. Every proposed update should be a concrete edit (add this paragraph, revise this risk entry, split this slice into two).
5. Do NOT apply the updates directly. The user decides what to apply.

---

## Guardrails

- Do NOT modify any roadmap. The output is a proposal.
- Do NOT invent findings not in the source. Trace every proposed update to a specific finding.
- Distinguish engineering roadmap updates (most changes) from executive roadmap updates (rare — only when strategic value/cost changes).
- If no updates are needed (prototype confirmed existing roadmap), say so explicitly.

---

## Output

Write to `prototyping/<slug>/roadmap-update.md`:

```markdown
# Proposed Roadmap Updates: [slug]

## Engineering roadmap updates

### Update E-1: [brief name]
**Section affected:** [path to section in engineering roadmap]
**Current text:** [excerpt]
**Proposed text:** [excerpt]
**Source finding:** [reference to findings.md]
**Rationale:** [one sentence]

[Repeat for each]

## Executive roadmap updates

[Either "No updates needed — findings do not change strategic value or ordering" OR specific updates with the same structure]

## Summary

- Total engineering updates: N
- Total executive updates: N
- Recommendation: [apply all / apply engineering only / discuss with user before applying]
```
