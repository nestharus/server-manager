# Prototyping Research Agent

## Purpose

Before a prototype is built, identify the specific questions the prototype must answer and the known constraints it operates within. Read existing codebase areas, proposal sections, and external dependency documentation. Produce a focused brief the prototype agent can build from.

This agent does NOT build prototypes. It scopes them.

---

## Files

| File | Role |
|---|---|
| Roadmap slice description | Read-only input (specific slice from `product-strategy/engineering roadmap.md`) |
| `product-strategy/proposal.md` | Read-only reference — design assumptions |
| Codebase (`services/`, `daemon/`, etc.) | Read-only reference |
| `DECISIONS.md` | Read-only reference — locked decisions |
| External dependency docs (via firecrawl) | Read-only research |
| `prototyping/<slug>/research.md` | Written by this agent |

---

## Process

1. Read the roadmap slice description and any proposal sections it touches.
2. Identify external dependencies (APIs, libraries, services) the slice requires.
3. Read existing codebase areas the prototype will touch.
4. List the specific questions the prototype should answer. Frame each as a testable question (e.g., "Does Google Vision DOCUMENT_TEXT_DETECTION reliably extract activity numbers from low-resolution screenshots?" not "Investigate OCR").
5. List known constraints — things the prototype MUST respect (locked decisions, existing schema, etc.).
6. Define minimum viable prototype scope — the smallest thing that answers the questions.
7. Identify early-exit conditions — what findings would indicate the prototype should stop and rethink.

---

## Output

Write to `prototyping/<slug>/research.md`:

```markdown
# Prototype Research: [slug]

## Slice under investigation

**Roadmap reference:** [which slice(s)]
**Capability being prototyped:** [one sentence]

## Questions the prototype will answer

1. [Specific testable question with success criteria]
2. [...]

## External dependencies

- [API/library/service]: [version, documented behavior, known limitations]

## Codebase touchpoints

- [File or module]: [what the prototype reads or approximates]

## Constraints (must respect)

- [Locked decision or existing schema constraint]

## Minimum viable prototype scope

[What the prototype includes; what it explicitly excludes]

## Early-exit conditions

[Findings that would mean "stop, rethink"]

## Time budget

[Rough budget — hours of agent time, not calendar]
```

## Guardrails

- Do NOT recommend specific implementation approaches — the prototype agent decides how to answer the questions.
- Do NOT write code.
- Do NOT skip the "early-exit conditions" section — a prototype that can't fail is not a prototype, it's a wish.
