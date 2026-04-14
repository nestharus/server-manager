# Roadmap Refinement: Review Engineering and Executive Roadmaps

You are reviewing two roadmap documents — an **engineering roadmap** and an **executive roadmap**. You have access to three governing documents that define the intellectual foundation:

- **philosophy.md** — Design principles that govern how the product thinks about problems. Highest-authority document.
- **problem.md** — Problem definition mapping the full surface area of complexity.
- **proposal.md** — The full system architecture that responds to the problem definition.

## Document hierarchy (review against this)

```
philosophy.md          — HOW we think (governing principles; highest authority)
    |
problem.md             — WHAT we're solving (problem surface; axes of complexity)
    |
proposal.md            — WHAT the target system looks like (architecture under constraints)
    |
engineering roadmap    — HOW we get there from current code
executive roadmap      — WHY this sequence, for whom, at what investment
```

A roadmap that contradicts the philosophy is wrong regardless of how reasonable its business logic sounds.

## How to review

### 1. Philosophy alignment (most important)

For each initiative in both roadmaps, check:
- Does the build scope honor the governing principles?
- Are there philosophy violations disguised as pragmatic staging?
- Does the executive roadmap communicate the philosophy as differentiation?

### 2. Problem coverage and acknowledged deferrals

Cross-reference initiatives against problem.md's axes. For each axis:
- Is it addressed by a specific initiative?
- Is it explicitly deferred with justification?
- Or is it silently omitted?

Silent omissions are the highest-priority finding.

### 3. Proposal fidelity and justified deviation

Where the roadmap deviates from the proposal, is the deviation deliberate, justified, and non-destructive?

### 4. Sequencing and dependency logic

Check that ordering reflects real dependencies: data dependencies, schema dependencies, adoption dependencies, spec-readiness dependencies.

### 5. Engineering roadmap specifics

Build scopes concrete enough to start work. "Leverages existing" claims honest. Acceptance criteria for every initiative.

### 6. Executive roadmap specifics

Audience calibration. Financial framing. Competitive positioning. Risk section.

### 7. Cross-document coherence

Numbering alignment. Scope consistency. Deferral consistency. Timeline consistency.

## Output structure

1. **Overall assessment** — quality and readiness of each document
2. **Philosophy alignment findings** — specific instances of honor or violation
3. **Coverage gaps** — silently omitted problem axes
4. **Sequencing and dependency issues** — ordering corrections
5. **Engineering specifics** — abstract scopes, missing migrations, unrealistic reuse
6. **Executive specifics** — missing financial framing, weak positioning
7. **Cross-document coherence** — mismatches
8. **Recommendations** — prioritized list distinguishing "must fix" from "should improve"
