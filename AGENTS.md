# AGENTS.md — Humility Discord Server Project

Guidance for coding agents working on this project. Modeled on
`~/work/AGENTS.md` and `~/projects/visual-code-editor/AGENTS.md`,
adapted for Discord server management.

---

## Project

Discord server management for the "Humility" guild (id `<guild id>`).
Long-term goal: a cloud-hosted daemon that handles applications,
tickets, moderation, role management, and server organization — with
Claude Code as the orchestrating interface.

---

## The Live Server Principle

This project operates on a live Discord server with real users.
Every action falls into one of three tiers:

| Tier | Examples | Authorization |
|------|----------|---------------|
| 1 — Read | List channels, read messages, fetch member list, inspect roles | Always allowed |
| 2 — Confined write | Create/edit files locally, commit to git, run tests | Always allowed |
| 3 — Visible write | Send messages, create channels, modify roles, kick/ban, change permissions | **Requires explicit per-action user approval** unless a runbook has been pre-authorized in `DECISIONS.md` |

**Tier 3 rule**: Before executing any action visible to Discord users,
describe exactly what will happen and wait for explicit confirmation.
No batching — each visible action is approved individually.

---

## Workflows

Pick the workflow that matches the situation. If unclear, ask the user.

| Cue | Workflow |
|-----|----------|
| "What does the server look like?" / audit / inspect | Server Inspection |
| New feature, enhancement, refactor | Implementation & Bug-Fix |
| Something is broken, errors in logs | Bug Investigation (RCA-first) |
| External service is down / bot not responding | Integration Triage |
| Need to change something users can see | Mutation Safety |
| "Research X" / "What are the options for Y" | Research |
| Deploying, updating infra, changing hosting | Deployment |

---

## Implementation & Bug-Fix Workflow

The 5-phase pipeline. Features skip RCA; bugs start with it. Nothing
is skipped except by explicit decision recorded in `DECISIONS.md`.

| Phase | Model | Artifact | Role |
|-------|-------|----------|------|
| 0. RCA (bugs only) | `gpt-high` | `research/NN-rca.md` | Investigate root cause. Read code, trace failure, produce report. **Do NOT propose fixes.** |
| 1. Problem research | `gpt-high` | `research/NN-*.md` | Document problem space with evidence. **Do NOT design solutions.** |
| 2. Synthesize user needs | `claude-opus` (this session, orchestrator) | `research/NN-*-needs.md` | Map research to Humility's specific context. Flag gaps. |
| 3. Proposal | `gpt-high` | `proposals/NN-*.md` | Propose a design/scope. Include architecture, tradeoffs, anti-scope. **Do NOT implement.** |
| 4. Risk assessment | 3x `claude-opus` in parallel | `risk/NN-{audit,scope,shortcut}.md` | Three sub-agents: audit risk + scope risk + shortcut risk. **All must return LOW.** If MEDIUM/HIGH, revise proposal and re-run. |
| 5. Hookpoint research | `gpt-high` | `research/NN-hookpoints.md` | **Only after risk LOW.** Map proposal to existing code. Find what's reusable, what's parallel, what to delete. |
| 6. Implementation | `gpt-high` | code | **Only after hookpoints.** Launch implementation using test/code separation. |
| 7. CodeRabbit review | CLI | review comments | Rerun until clean. Amend same commit. |
| 8. PR review | `claude-opus` | review comments | Multi-concern check + justification check. Split oversized PRs. |

### Principles

- **Separate agents for separate concerns.** RCA agents don't propose;
  proposal agents don't implement. This is how you avoid the
  solution-fixation trap.
- **Zero-risk gate.** All three risk assessments must return LOW before
  implementation starts. Shortcut risk flags proposals that introduce
  their own shortcuts.
- **No compatibility shims** anywhere in the pipeline.
- **Research before implementation.** Hookpoints (phase 5) finds what
  exists so the implementation doesn't build parallel systems.
- **Iterate until it passes.** Don't implement a proposal that hasn't
  cleared risk.

### Gate ownership per phase

Different phases have different gates. Some are model-gated, some are
human-gated. Getting this wrong burns cycles and erodes trust.

| Phase | Gate owner | What the gate does |
|---|---|---|
| 0. RCA (bugs) | **Human** | User decides if the bug is worth fixing at all |
| 1. Problem research | **Human** | User confirms scope framing — did the research find the right problems? |
| 2. Synthesis | **Human** | User confirms the mapping to their actual needs and answers any open questions |
| 3. Proposal | **3x `claude-opus` parallel** — audit + scope + shortcut risk | The risk assessment IS the review. No human gate here. |
| 4. Hookpoint research | **Human** | User confirms which pre-existing code survives |
| 5. Implementation | (continuous) | Test suite + CI + daemon smoke |
| 6. CodeRabbit | **Model** | Rerun until clean |
| 7. PR review | **`claude-opus`** multi-concern + justification check | Split oversized PRs |

**Rule of thumb**: phases that set scope belong to the user; phases
that validate design or code belong to agents. Do not ask for user
review where a risk gate or PR review is the correct control.

Risk phase specifically:
- All three risks must return **LOW**
- If any is MEDIUM or HIGH, revise proposal and re-run the full risk
  gate — do not cherry-pick which risks to address
- If a risk is LOW but surfaces a concern worth discussing, raise it
  to the user as an observation, not a gate

---

## Implementation Workflow — Test/Code Agent Separation

**CRITICAL**: The test writer MUST be a different agent invocation
from the code writer. This ensures tests encode intent from the
contract, not from the implementation. If the same agent writes both,
tests tend to mirror the implementation instead of validating the
contract.

### Per-feature PR workflow

Each feature PR goes through this sequence:

| Step | Agent | Input | Output |
|------|-------|-------|--------|
| 1. Define contract | Orchestrator (this session) | Proposal subsystem design | Pydantic schemas, endpoint signatures, command definitions |
| 2. Write tests | `gpt-high` (test agent) | Contracts ONLY — no implementation code | `tests/` files that encode expected behavior |
| 3. Write code | `gpt-high` (code agent, separate invocation) | Contracts + test files | Implementation that makes tests pass |
| 4. Verify | CI (local pytest run) | Tests + code | Green/red |
| 5. Review | CodeRabbit | PR diff | Review comments |

**Key rules**:
- The test agent ONLY sees the contracts (Pydantic models, endpoint
  signatures, CLI command definitions). It does NOT see the service/
  repository/infrastructure implementation.
- The code agent sees both the contracts AND the tests. Its job is
  to make the tests pass while following the layered architecture.
- If tests fail after step 3, the code agent is re-invoked with the
  test output. The test agent is NOT re-invoked (tests encode intent,
  not implementation — if a test is wrong, it's the contract's fault,
  not the test's).
- Tests use `pytest` with `httpx.AsyncClient` for API endpoints and
  mock/fixture patterns for Discord interactions.

### Optimistic locking in tests

Tests MUST verify optimistic locking behavior for versioned entities
(from the java-interview-setup pattern):
- Read entity -> get version N
- Update with version N -> succeeds, version becomes N+1
- Update with stale version N -> returns 409 Conflict
- This is a contract-level behavior, so the test agent writes it.

---

## CodeRabbit Review Loop

CodeRabbit CLI is a formal stage in the per-feature PR workflow.
One pass is NOT enough — keep rerunning until the review is clean.

```bash
coderabbit review --plain --base main --cwd <project-dir>

# Iterate until clean:
# 1. Fix findings
# 2. Run tests
git commit --amend --no-edit
git push --force-with-lease
coderabbit review --plain --base main --cwd <project-dir>
```

Keep amending the same commit so CodeRabbit always reviews a single
clean diff against main.

---

## PR Review Workflow

After implementation and CodeRabbit, before merging, all PRs go through
decomposition review.

| Step | Model | Role |
|------|-------|------|
| 1. Multi-concern check | `claude-opus` | Can this PR be decomposed into smaller PRs with single concerns? Identify each concern, the lines/functions involved, and dependency order. |
| 2. Justification check | `claude-opus` | What deserves to be in this PR? What does not? Anything separable goes to its own PR. |

**Rules:**
- Run on the actual diff, not the proposal — proposals can look
  reasonable while the diff bundles too much
- A PR that touches N independent concerns should be split into N PRs
- Dependency order matters — if PR B depends on PR A, A merges first
- A large deletion is its own PR, separate from the addition that replaces it
- Additive changes go before behavioral changes
- If multi-concern check says "cannot decompose further", PR is ready for merge

---

## Bug Investigation Workflow (RCA-First)

1. **RCA agent** (`gpt-high`) — investigate root cause. Read code, trace
   the failure path, produce a report. Do NOT propose fixes.
2. Feed RCA report into the Implementation & Bug-Fix pipeline at phase 3
   (Proposal).

---

## Server Inspection Workflow

Read-only audit of the Discord server state. Tier 1 only.

1. Fetch current state (channels, roles, members, permissions)
2. Produce a structured report
3. Compare against expected state if a reference exists

---

## Integration Triage Workflow

When an external service or bot is unresponsive:

1. **Check status** — is the service actually down? Check endpoints,
   status pages, logs.
2. **Identify impact** — what functionality is lost?
3. **Document** — log the outage, affected features, and workaround
   if any.
4. **Mitigate** — if a workaround exists, propose it (follows Mutation
   Safety if it changes anything visible).
5. **Recover** — when service returns, verify functionality is restored.
6. **Post-mortem** — update docs with lessons learned.

---

## Mutation Safety Workflow

For any Tier 3 action (visible to Discord users):

1. **State** — describe the current state of what will change
2. **Reversal path** — describe how to undo the change if it goes wrong
3. **Ask user** — present the action, current state, and reversal path
4. **Wait for explicit yes** — do not proceed on ambiguous responses
5. **Execute + verify** — perform the action, then verify the result
6. **No batching** — each visible action is its own cycle

---

## Research Workflow

For open-ended investigation:

1. **Scope** — define what question needs answering
2. **Research agent** (`gpt-high` or `gpt-xhigh` for deep research) —
   investigate, produce a report
3. **Synthesis** (this session) — integrate findings into project context
4. **Decision** — user decides next steps based on findings

---

## Deployment Workflow

For infrastructure changes:

1. **Proposal** — describe what changes and why
2. **Risk assessment** — 3x risk (same as implementation)
3. **Dry run** — test in staging/preview if possible
4. **Execute** — apply changes
5. **Verify** — confirm everything works
6. **Document** — update infrastructure reference

---

## Prototyping Workflow

Runs between strategic roadmap approval and production implementation when
a slice has wide magnitude uncertainty or unknown external dependencies.
See `prototyping/orchestrator.md` for the full process.

**Prototyping is NOT implementation.** It cares about discovery, not
correctness. Prototype code is disposable. Production code is written
fresh using prototype findings as input.

Five stages:

1. Scope the prototype (human gate — user approves the questions and budget)
2. Pre-prototype research (`gpt-high`, `prototyping/research agent.md`)
3. Build the prototype (`gpt-high`, `prototyping/prototype agent.md`)
4. Synthesize findings (`claude-opus`, `prototyping/findings agent.md`)
5. Propose roadmap updates (`gpt-high`, `prototyping/roadmap-update agent.md`)
6. Human gate — user applies updates, commissions follow-ups, or moves to implementation

No 3x risk gate. Prototype artifacts live in `prototyping/<slug>/prototype/`
and are not shipped.

---

## Writing Pipeline

Multi-agent writing quality system for public-facing documents. See
`product-strategy/writing pipeline orchestrator.md` for the full process
and `product-strategy/WRITING_SKILL_MASTER.md` for the craft reference.

Applies to: executive roadmap, pitch deck, and any future public documents.

**Phase A: Content Revision**
1. Content revision (`claude-opus`, `writing content agent.md`)
   — adds missing sections from communication research
2. Human gate — user approves content additions

**Phase B: Writing Quality (sequential, per rubric)**
3. Skeleton extraction (`gpt-high`) — structural analysis
4. Non-negotiable scan (`gpt-high`) — hard ban violations
5. Rubric 1: Story beats (`claude-opus`, `writing rubric agent.md`)
6. Rubric 2: AI tell filter (`claude-opus`, `writing rubric agent.md`)
7. Rubric 3: Flow and cohesion (`claude-opus`, `writing rubric agent.md`)
8. Rubric 4: Adversarial robustness (`claude-opus`, `writing rubric agent.md`)
9. Tempo and editorial (`claude-opus`, `writing editorial agent.md`)
10. Restart check — if major edits, re-run from step 4. Max 3 cycles.

**Phase C: Quality Gate**
11. Quality gate (`claude-opus`, `writing quality gate agent.md`)
    — PASS/FAIL with specific findings. Separate reviewer.
12. PDF rendering — `python scripts/render-pitch-deck.py`

**Gate: Human** — user reviews the PDF before distribution.

Communication research per document type:
- Executive roadmap: `research/exec-roadmap-communication.md`
- Pitch deck: `research/pitch-deck-communication.md`

---

## Product Strategy Workflow

For strategic product decisions, use the alignment loop in
`product-strategy/`. See `product-strategy/orchestrator.md` for the
full process.

**CRITICAL**: Each stage is a SEPARATE sub-agent invocation. Claude Code
acts as the orchestrator, NOT a single mega-agent. Do not collapse the
multi-stage workflow into a single agent.

Pipeline after alignment converges — see
`product-strategy/roadmap orchestrator.md` for the full process:

**Layer 0: Market Research**
1. Research planning (orchestrator — identifies research questions)
2. Web research execution (`gpt-high` × N parallel, via Firecrawl MCP)
3. Market research synthesis (`gpt-high`, `market research agent.md`)
4. Surface check → product strategy re-entry if surfaces found

**Layer 1: Executive Roadmap**
5. Executive roadmap proposal (`gpt-high`, `executive roadmap proposer.md`)
6. 3x executive risk assessment (`claude-opus`, parallel):
   market misread, dependency trap, completeness
7. Human gate — user approves strategic ordering

**Layer 2: Engineering Roadmap**
8. Engineering codebase research (`gpt-high`, `engineering research agent.md`)
9. Engineering roadmap proposal (`gpt-high`, `engineering roadmap proposer.md`)
10. 3x engineering risk assessment (`claude-opus`, parallel):
    feasibility, integration, drift
11. Human gate — user resolves ordering disagreements

**Layer 3: AI-Optimized Roadmap**
12. AI roadmap proposal (`gpt-high`, `ai roadmap proposer.md`)
13. 3x AI risk assessment (`claude-opus`, parallel):
    decomposition, coverage, dependency
14. Model gate — orchestrator validates completeness

**Layer 4: Ticket Generation**
15. Ticket generation (`gpt-high`, `ticket generation agent.md`)
16. Human gate — user reviews tickets

Risk types per layer are defined in `product-strategy/roadmap risk types.md`.
All risk assessments must return LOW. If any returns MEDIUM/HIGH, the
proposer revises and the full risk gate re-runs. See the roadmap
orchestrator for resolution paths per risk type.

---

## Model Roles

| Model | Use for |
|-------|---------|
| `gpt-high` | RCA, proposals, research, hookpoint analysis, implementation |
| `gpt-xhigh` | Coordination and deep reasoning (see below) |
| `claude-opus` | Risk assessments, PR reviews, alignment reviews, synthesis |
| `claude-sonnet` | Quick checks, summaries |

### No Super Agents

**CRITICAL**: No single agent should both research AND synthesize for
large tasks. Large tasks use a coordinator/researcher split:

- `gpt-xhigh` acts as **coordinator** — identifies what questions need
  answering, writes research prompts, launches `gpt-high` agents,
  synthesizes their findings into the deliverable.
- `gpt-high` acts as **researcher** — receives a focused question,
  investigates, returns findings.

The coordinator does NOT do deep research itself. It delegates research
to `gpt-high` agents via the `agents` CLI:

```bash
# Coordinator writes a prompt, launches a researcher:
~/.local/bin/agents -m gpt-high -p <project> -f .tmp/<research-prompt>.md
```

This applies to:
- Proposal writing (coordinator patches proposal, researchers answer gaps)
- Problem space investigation (coordinator identifies axes, researchers
  gather evidence)
- Any task that requires both broad reasoning and detailed research

A single agent trying to do both produces shallow work. Split the roles.

---

## Running Sub-Agents

The `agents` CLI (`~/.local/bin/agents`) runs external models.

```bash
# Run a model with a prompt:
agents -m gpt-high -p <worktree-path> "your prompt"

# Run from a prompt file:
agents -m gpt-high -p <worktree-path> -f prompt.md

# Available models: gpt-high, gpt-medium, gpt-low, gpt-xhigh,
#   claude-opus, claude-sonnet, claude-haiku,
#   gemini-high, gemini-pro-high, gemini-flash-high
```

**CRITICAL — Worktree Isolation**: When running multiple agents in
parallel, each agent MUST operate on its own git worktree. The `-p`
flag must point to a worktree directory, NOT the shared project root.

```bash
# Create a worktree for an agent:
git worktree add worktrees/<branch> -b <branch>

# Point the agent at the worktree:
agents -m gpt-high -p worktrees/<branch> -f prompt.md

# After agent completes, merge the worktree branch and clean up:
git worktree remove worktrees/<branch>
```

Never run parallel agents writing to the same directory.

---

## Architecture (Three Services)

```
services/
  api/          # FastAPI — the mutation gateway. Both UI and Discord daemon call it.
    api/        # endpoints (versioned: v1/)
    contracts/  # Pydantic schemas / DTOs
    core/       # factory, settings, dependencies, middleware
    services/   # business logic
    repositories/  # database access
    infrastructure/  # external clients (Google Vision, Gemini, etc.)

  discord/      # discord.py daemon — gateway adapter
    # Translates Discord interactions (slash commands, buttons, modals, threads)
    # into API calls or direct DB writes. Posts embeds, manages threads.

apps/
  web/          # TanStack Start/Router frontend
    # Application forms (richer than Discord modals)
    # Officer review dashboards
    # Activity tracking views + correction UI
    # Chapter management admin panels

packages/
  shared-types/ # TypeScript contracts (generated from OpenAPI)

migrations/     # Alembic for Postgres schema
docs/           # planning docs
plans/          # plans and research
```

### API-First Design Rule

- Human UI and agent API are BOTH first-class surfaces
- The UI is a client of the API, not the only way to operate the system
- Every UI action has a corresponding structured API endpoint
- OpenAPI/Pydantic contracts make the surface agent-friendly

### Key Patterns from References

From `ai-workflow/app`:
- Layered: api -> services -> repositories, with contracts and core as cross-cutting
- Factory pattern for app creation
- Settings via Pydantic
- Dependency injection via FastAPI Depends

From `java-interview-setup`:
- VersionedEntity base class -> optimistic locking via version column
- AuditInfo / AuditorContextHolder -> audit trail with actor context
- EntityValidator -> validation at the domain layer
- Mapper pattern -> entity <-> DTO conversion
- Projections -> query-specific read models

From `ui-designer`:
- Bun + Turborepo for TypeScript workspace management
- Changesets for versioning
- Lefthook for git hooks
- Vitest + Playwright for testing
- Soft assertions convention
- TanStack Query 5

---

## Infrastructure Reference

### Discord

| Item | Value |
|------|-------|
| Guild ID | `<guild id>` |
| Guild name | Humility |

### Hosting

Platform decisions will be recorded in `DECISIONS.md` as they are made.

---

## When to Ask the User

Not in the middle of a phase. Phases are self-contained — you give
the external model a complete prompt and get back a complete artifact.
**Not at every phase boundary either** — only at phase boundaries
where the user is the gate owner (see Gate ownership per phase above).

Ask the user:

- **At human-gated phase boundaries** — research, synthesis,
  hookpoint findings. They confirm scope and framing before the
  pipeline advances. This is NOT every phase; proposal phase is
  model-gated.
- **Before tier-3 destructive actions** — per-action, with action +
  blast radius + reversal path in one message.
- **When blocked on credentials or external action** — things only the
  user can physically do (log into a website, click a Discord dialog,
  pay a bill, create a staging Discord guild).
- **When two clearly-defined paths have different irreversible
  consequences** — present both, let them choose. Don't flood with
  six variants.

Do **not** ask the user:

- To review a proposal — that's what the 3x risk gate is for
- Things you can verify with `discord_cli.py`
- Things that are already in `NOTES.md` or `DECISIONS.md`
- Minor design decisions that fit within a phase's scope — make a call,
  document in `DECISIONS.md`, keep moving
- "Is this OK?" checks on every action. Overasking erodes trust faster
  than occasional mistakes

---

## No Backwards Compatibility

**CRITICAL**: Never introduce backward-compatibility shims, feature
flags for old behavior, transitional code paths, deprecated aliases,
re-exports, or dual support. Ship changes cleanly.

When updating code:
1. Find all usages
2. Update all call sites
3. Delete old code
4. Run tests
5. No fallbacks

---

## No Deferred Stubs

Do not create placeholder stubs or TODO comments unless the
implementation plan explicitly indicates the item is planned for a
later task. Implement fully or document what's blocking.

---

## Git Conventions

- All work in worktrees — main checkout stays clean
- All PRs opened in draft mode
- GPG-signed commits (key `2AAAEEBD97F32BFE`)
- No Co-Authored-By lines — agents do not add themselves as authors
- Branch naming: `feat/<description>` or `<TICKET-ID>-<description>`
