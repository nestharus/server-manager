# Task Breakdown: Convert Roadmap into Actionable Task Files

## Your Role

**You are a product owner breaking a prioritized roadmap into individual, actionable task files. Each task file should give a developer everything they need to understand scope, rationale, and dependencies — without re-reading the full roadmap.**

## Provided Files

- **`roadmap.md`** — A value-prioritized product expansion roadmap. This is the authoritative source for what to build and in what order.
- **`proposal.md`** — The system design proposal. Use this to add context, acceptance criteria, and edge cases.
- **`problem.md`** — The problem definition. Use this to ground each task's "why" in real user pain.

## What To Do

### 1. One file per roadmap item

Create a separate markdown file for each item in the roadmap:
- One file for each **prioritized expansion item**
- One file for each **quick win**
- One file for the **de-prioritized items** (all grouped into a single file)

### 2. File naming convention

```
00-deprioritized-items.md
01-<short-slug>.md
02-<short-slug>.md
...
09-quickwin-<short-slug>.md
10-quickwin-<short-slug>.md
...
```

### 3. Task file format

#### For prioritized expansion items:

```markdown
Source: roadmap.md lines <start>-<end>

### <number>) <Title> (<short value statement>)

**Why this is next**

* <1-3 bullets explaining business value and urgency>

**What to build (MVP)**

* <Concrete deliverables, scoped to MVP>
* <UI, data, or workflow changes needed>
* <Keep it specific enough to estimate but not a full spec>

**Dependencies**

* <What must exist first, referencing other task numbers>
* <Or "none" if this is independent>
```

#### For quick wins:

```markdown
Source: roadmap.md lines <start>-<end>

### Quick Win: <Title>

* <1-2 lines on what it does and why it matters>
* <Touchpoints: which areas of the product are affected>
```

#### For de-prioritized items:

```markdown
Source: roadmap.md lines <start>-<end>

## De-prioritized Items

<Brief framing sentence about why these are deferred>

* **<Item name>**
  <1-2 lines on why it's deferred for the current stage>
```

### 4. Enrichment from proposal and problem files

For each task, go beyond what the roadmap states:
- From `problem.md`: identify which problem sections are most relevant. Pull in specific pain points and edge cases.
- From `proposal.md`: check whether the proposal describes additional detail or acceptance criteria. Incorporate anything that sharpens the MVP scope.

Do NOT bloat tasks with proposal content. Only add detail that changes what a developer would build.

### 5. Cross-reference dependencies

Every expansion task should explicitly state its dependencies using task numbering. If a task has no dependencies, say "none."

## Output

Produce all task files as a single output, with clear file name headers separating each one.
