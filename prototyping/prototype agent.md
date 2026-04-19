# Prototype Agent

## Purpose

Build a throwaway prototype that answers the research agent's questions. The goal is discovery, not production code. This agent is explicitly freed from production quality concerns.

---

## What This Agent Does Differently From Implementation Agents

Compared to the AGENTS.md implementation pipeline:

| Concern | Implementation pipeline | Prototype agent |
|---|---|---|
| Tests | Required (test/code agent separation) | Not required. Manual verification is fine. |
| Documentation | Required (docstrings, ADRs) | Only what's needed to run the prototype |
| Error handling | Comprehensive | Only for paths the prototype exercises |
| Code style | Follows project conventions | Follows conventions only where it matters for running the prototype |
| Schema stability | Contracts are frozen before tests | Schemas are throwaway and can change between runs |
| Risk gate | 3x LOW required | None |
| PR review | CodeRabbit + multi-concern + justification | None |
| Destination | Production codebase | `prototyping/<slug>/prototype/` only |

**The prototype is disposable.** If the prototype is useful, its production version is written fresh using this prototype's findings as input.

---

## Files

| File | Role |
|---|---|
| `prototyping/<slug>/research.md` | Read-only input — the questions to answer |
| Codebase | Read-only reference (do NOT modify production code) |
| `prototyping/<slug>/prototype/` | Written by this agent — prototype artifacts |
| `prototyping/<slug>/prototype-notes.md` | Written by this agent — agent's running notes |

---

## Process

1. Read `prototyping/<slug>/research.md`.
2. For each question, design the minimal artifact that answers it. Often this is a script, a small module, a schema sketch, or a manual test driver.
3. Build the artifacts in `prototyping/<slug>/prototype/`. Organize however makes sense — this directory is disposable.
4. Run the prototype manually. Capture what happens: outputs, errors, surprises, unanticipated behaviors.
5. Keep running notes in `prototyping/<slug>/prototype-notes.md` as you go. Document what worked, what didn't, what was harder or easier than expected.
6. Answer each research question in the notes. If a question couldn't be answered, say why and what would be needed.
7. Identify new questions that surfaced during the prototype — things the research agent didn't anticipate.

---

## Guardrails

- Do NOT modify production code. The prototype lives entirely in `prototyping/<slug>/prototype/`.
- Do NOT write tests. Manual verification + notes are the validation.
- Do NOT implement production-quality error handling. Let errors crash; that's useful signal.
- Do NOT worry about style consistency beyond what's needed to run.
- Do NOT hide surprising results. Document everything, even (especially) the embarrassing things.
- Do NOT exceed the time budget from research.md. If the budget is exhausted, stop and write notes.
- Do NOT skip documentation of why the prototype was abandoned if it was abandoned — "this approach doesn't work because X" is a valuable finding.

---

## Output

1. **Prototype artifacts** in `prototyping/<slug>/prototype/` — however organized.
2. **Running notes** in `prototyping/<slug>/prototype-notes.md`:

```markdown
# Prototype Notes: [slug]

## Questions and answers

### Q1: [question from research.md]
**Answer:** [what the prototype showed]
**Evidence:** [what files or outputs back this up]
**Caveats:** [what the answer is conditional on]

[Repeat for each question]

## Surprises

- [Things that were harder or easier than expected]

## New questions surfaced

- [Things to investigate in a future prototype]

## Artifacts built

- [List of files in prototyping/<slug>/prototype/ and what each does]

## Time spent

- [Rough time budget consumed; whether exits were taken]
```

The findings agent reads these notes next and synthesizes.
