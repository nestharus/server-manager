# Prototyping Orchestrator

## Purpose

Discover the surface area and complexity of a roadmap slice (or group of slices) to produce refined magnitude estimates. Feeds back into the engineering roadmap as better-informed effort and dependency data. This workflow sits between the strategic roadmap and production implementation.

**Prototyping is NOT production implementation.** The goals are different:
- Implementation cares about correctness, tests, risk elimination, quality, deployability.
- Prototyping cares about discovery: surface area, hidden complexity, API boundary realism, external-dependency behavior, schema shape.

Prototypes are disposable. They answer questions. Their code is not expected to ship.

---

## When to Invoke Prototyping

Prototyping runs:
1. **After a roadmap slice is approved in principle** but before committing to a production plan
2. **When an effort estimate has wide uncertainty** (e.g., a slice estimated at L but could be XL or M depending on unknowns)
3. **When external dependencies are unknown** (e.g., OCR pipeline, Discord rate limits, a new library)
4. **When schema shape depends on operator workflow details** that aren't fully settled

Prototyping does NOT run:
- For slices that follow well-understood existing patterns (no discovery needed)
- For pure refactors or cleanup work
- After production implementation has started (too late; use spikes inside implementation)

---

## Files

### Agent prompts (permanent)

| File | Role |
|---|---|
| `prototyping/orchestrator.md` | This file — orchestrator instructions |
| `prototyping/research agent.md` | Pre-prototype research agent instructions |
| `prototyping/prototype agent.md` | Prototype builder agent instructions |
| `prototyping/findings agent.md` | Prototype findings synthesizer instructions |
| `prototyping/roadmap-update agent.md` | Roadmap update agent (feeds findings back) |

### Output files (per prototype cycle)

| File | Producer |
|---|---|
| `prototyping/<slug>/research.md` | Research agent |
| `prototyping/<slug>/prototype/` | Prototype agent (code, notes, throwaway artifacts) |
| `prototyping/<slug>/findings.md` | Findings agent |
| `prototyping/<slug>/roadmap-update.md` | Roadmap update agent |

`<slug>` is a short identifier for the slice or question being prototyped (e.g., `vs-016-ocr-pipeline`, `vs-005-discord-provisioning`).

---

## Process

### Stage P1: Scope the Prototype

**Gate owner: Human.** The orchestrator (Claude Code) presents the candidate prototype scope to the user for confirmation:
- Which roadmap slice(s) does this prototype inform?
- What specific questions is this prototype answering?
- What is the time budget (rough — e.g., "a few hours of agent time")?
- What exits the prototype early (e.g., "we learn the surface area is 10x what the roadmap estimated")?

The user confirms or adjusts the scope.

### Stage P2: Pre-Prototype Research (gpt-high)

Run the research agent:

```bash
agents -m gpt-high -p <worktree> -f prototyping/research\ agent.md
```

The research agent:
- Reads the roadmap slice description and proposal sections
- Identifies external dependencies (APIs, libraries, Discord features, file formats)
- Reads any existing codebase areas the prototype will touch or interact with
- Documents known unknowns — what the prototype needs to answer
- Identifies "minimum viable prototype" scope — the smallest thing that answers the questions

Output: `prototyping/<slug>/research.md` — a pre-prototype findings document with the focused questions and known constraints.

### Stage P3: Build the Prototype (gpt-high)

Run the prototype agent:

```bash
agents -m gpt-high -p <worktree> -f prototyping/prototype\ agent.md
```

The prototype agent:
- Reads `prototyping/<slug>/research.md`
- Builds a throwaway prototype that answers the research agent's questions
- Writes to `prototyping/<slug>/prototype/` — scripts, throwaway schemas, manual test notes
- Does NOT write production-quality code: no tests, no comprehensive error handling, no documentation beyond what's needed to run the prototype manually
- Does NOT integrate with the main codebase unless strictly necessary
- Documents what worked, what didn't, what surprised the agent

**Key difference from implementation:** The prototype agent is explicitly told NOT to write tests, NOT to follow the full AGENTS.md pipeline, NOT to worry about production quality. It is exploring.

### Stage P4: Findings Synthesis (claude-opus)

Run the findings agent:

```bash
agents -m claude-opus -p <worktree> -f prototyping/findings\ agent.md
```

The findings agent:
- Reads `prototyping/<slug>/research.md` (the questions)
- Reads `prototyping/<slug>/prototype/` (the artifacts)
- Reads the prototype agent's working notes
- Synthesizes: which questions got answered, which didn't, what new questions surfaced
- Produces a refined magnitude estimate for the slice (or slice group)
- Identifies any new risks that the prototype surfaced

Output: `prototyping/<slug>/findings.md` — synthesized conclusions, refined estimates, surfaced risks, remaining unknowns.

### Stage P5: Roadmap Update (gpt-high)

Run the roadmap update agent:

```bash
agents -m gpt-high -p <worktree> -f prototyping/roadmap-update\ agent.md
```

The roadmap update agent:
- Reads `prototyping/<slug>/findings.md`
- Reads the current engineering roadmap
- Proposes specific updates to the engineering roadmap — refined capability descriptions, new risk entries, updated magnitudes if the roadmap uses phase-level magnitude indicators
- Proposes updates to the executive roadmap if the findings change strategic value or ordering

Output: `prototyping/<slug>/roadmap-update.md` — proposed changes with rationale.

### Stage P6: Human Gate

**Gate owner: Human.** The user reviews the findings and proposed roadmap updates:
- Apply the updates to the roadmap(s)?
- Commission follow-up prototypes if new questions surfaced?
- Ready to move to implementation for this slice?

---

## What Gets Prototyped vs What Doesn't

**Prototype when:**
- External API behavior is unknown (e.g., Gemini Vision response format on compliance screenshots, Discord rate limits under sustained provisioning load)
- Schema shape depends on unclear operator workflow details
- A new pattern is being introduced and the surface area isn't clear
- An effort estimate has wide uncertainty (L could be M or XL)

**Don't prototype when:**
- The slice is obvious application of an existing pattern (just ship it through implementation)
- The prototype would be nearly as complex as the production implementation (go directly to implementation with explicit risk assessment)
- External dependencies are well-documented (use the docs, don't build to discover)

---

## Relationship to Other Workflows

- **Upstream**: Engineering roadmap identifies slices that need prototyping (via "high uncertainty" markers)
- **Feeds back into**: Engineering roadmap (refined magnitudes, new risks), sometimes Executive roadmap (if strategic value changes)
- **Downstream**: Production implementation workflow (per `AGENTS.md`) uses prototyping findings as input to the per-slice research → proposal → risk cycle

The prototyping workflow is optional per slice. Slices with obvious implementation patterns skip directly to production implementation.

---

## Risk Assessment in Prototyping

Prototyping has LIGHTER risk assessment than implementation. The prototype agent is explicitly told:
- Do NOT worry about production quality
- Do NOT write comprehensive tests
- Do NOT assess audit/scope/shortcut risks on the prototype code
- The prototype is disposable

The risk assessment happens AFTER prototyping, when the findings feed into the production implementation proposal. That implementation proposal gets the full 3x risk gate from AGENTS.md.

---

## Anti-Patterns

- **Shipping prototype code to production.** If the prototype was useful, its production version is written fresh using its findings as input. Don't let prototype shortcuts leak into production.
- **Prototyping forever.** Prototypes have time budgets. If the time budget is exceeded without answering the questions, the findings agent should surface this and the user decides whether to extend, pivot, or abandon.
- **Skipping prototyping when needed.** If the implementation risk gate is blocking on unknowns, and those unknowns can be answered faster with a prototype than with speculation, do the prototype.
- **Production tests in the prototype.** Tests validate contracts. Prototype contracts are unstable. Don't test the prototype; use manual verification.
