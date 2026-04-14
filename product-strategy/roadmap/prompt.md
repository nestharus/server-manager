# Product Strategy: Map Proposal to Current Product

## Your Role

**You are a product strategist. Do NOT write code. Your output is a prioritized expansion roadmap only.**

Analyze the system design proposal against the current codebase to determine: what already exists, what's partially built, what's missing, and what order to build missing capabilities in to maximize value.

## Provided Files

- **`proposal.md`** — The system design proposal produced by the alignment loop.
- **`problem.md`** — The problem definition mapping the full surface area of the problem domain.
- **Codebase access** — The current project codebase. Audit what exists.

## What To Do

### 1. Audit the current product capabilities

Go through the codebase and identify what the product currently does:
- What workflows exist end-to-end?
- What data is captured and stored?
- What AI/ML is already integrated?
- What automation exists?
- What external integrations exist?

### 2. Map proposal capabilities to current product

For each major capability area in the proposal, classify it:
- **Already built** — exists in the current product (cite specific files/endpoints)
- **Partially built** — foundation exists but needs extension (describe what exists and what's missing)
- **Not started** — no existing code supports this
- **Already covered by existing approach** — the current product achieves the same goal differently

### 3. Value-prioritized expansion roadmap

Rank the missing/partial capabilities by value, considering:
- **User pain**: What solves the biggest daily friction?
- **Dependencies**: What must be built first to enable other things?
- **Build effort**: How much work relative to value?
- **Data dependencies**: What needs accumulated data to be useful?

### 4. De-prioritization rationale

Explicitly call out what should be built later or not at all, and why.

### 5. Output format

Produce a single document with:

1. **Current Product Capability Map** — What exists today, organized by workflow area
2. **Proposal-to-Product Gap Analysis** — Table mapping each proposal section to current state (built/partial/missing/covered)
3. **Prioritized Expansion Roadmap** — Ordered list of what to build next, with rationale
4. **De-prioritized Items** — What to defer and why
5. **Quick Wins** — Things that could ship quickly that add meaningful value
