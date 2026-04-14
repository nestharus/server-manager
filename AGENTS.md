# AGENTS.md — Humility Discord Server Project

Guidance for coding agents working on this project. Modeled on
`~/work/AGENTS.md` and `~/projects/visual-code-editor/AGENTS.md`,
adapted for Discord server management.

---

## Project Context

Long-term goal: a cloud-hosted daemon + CLI stack that handles
applications, tickets, moderation, and sub-community provisioning for
the **Humility** Discord guild (id `900000000000000001`). Replaces an
aging pile of third-party bots, some of which have already shut down
(Gather, ticketsbot.net v1).

The server is a **live production system** with ~84 members, a sole
owner (nestharus), and active silent bots (Captcha.bot, AmariBot, Sx
Bot). There is no staging server yet — every mutation is visible to
real users. See **The Live Server Principle** below.

### Current state

- Humility server structurally encodes a "chapter" system (Chapter*
  roles + GUILD TEMPLATE category), but no chapters are currently
  populated — all scaffolding, no content
- HumilityTicketBot is a dead ghost: the underlying ticketsbot.net v1
  service shut down 2025-03-05; a tickets.bot v2 whitelabel is set up
  but the owner wants to move off third-party bots entirely
- Gather (application forms) is offline and will be replaced
- See `NOTES.md` for the live-server audit

---

## First Principles (hard rules — override everything)

These rules come out of `DECISIONS.md` and the pivot on 2026-04-11.
Violating any of them is a bug.

1. **Research before solutions.** No code is written before a phased
   pipeline has produced a validated proposal. See
   *Implementation & Bug-Fix Workflow* below.
2. **No SQLite.** This project runs in the cloud 24/7. Persistence is
   Supabase (managed Postgres). Local SQLite is not a valid fallback
   "for simplicity." (`DECISIONS.md#D2`)
3. **No compatibility shims.** No feature flags for old behavior. No
   "for now, keep the old path." No transitional code. Ship the change
   cleanly. Rely on thorough testing, not gradual rollout.
4. **No jumping to solutions.** If you find yourself writing code and
   the pipeline (phase 1 → 5) hasn't produced a validated proposal,
   stop and go back.
5. **No bias toward the user's current framing.** The user's
   description of their needs is an input, not ground truth. Research
   may surface problems they haven't named and that change scope.
6. **Live server, real users.** Inspection is free; mutation is not.
   See **The Live Server Principle** below.
7. **Preserve, don't delete.** Pre-research code (`daemon/`, `forms/`,
   `docs/*.md`) stays on disk until the hookpoint phase explicitly
   decides what to keep, rewrite, or drop.
8. **Each phase uses a different model invocation.** The agent that
   does research does not write the proposal. The agent that writes the
   proposal does not assess the risk. Claude Code (this session)
   orchestrates; it does not collapse phases.

---

## The Live Server Principle

Every action this project takes falls into one of three tiers. Each
tier has different safety requirements.

| Tier | Examples | Authorization |
|------|----------|---------------|
| **Read** | `discord_cli.py read`, `channels`, `bots`, `integrations`, `bot-activity`, fetching a message | Always allowed. Free. Do as much as you need. |
| **Write — confined** | Posting a message in a staging/private channel you created; writing to a thread the bot owns; editing a message the bot posted itself | Allowed if scope is clearly bounded. Log in `NOTES.md`. |
| **Write — visible** | Posting in a public channel; creating/deleting channels; creating/editing/deleting roles; kicking/banning members; kicking bots; modifying permission overwrites; sending DMs to users; pinging roles | **Requires explicit user approval** per action, unless the user has pre-authorized a specific runbook in `DECISIONS.md` |

**Hard rules**:
- Never issue tier-3 actions as a side effect of "executing a plan"
  without confirming each one with the user
- Never use destructive actions as shortcuts around obstacles (e.g.,
  "just delete the stale channel" instead of investigating why it exists)
- When in doubt, default to read-only investigation and report findings
- The bot has Administrator permission — the *policy* boundary is this
  AGENTS.md, not the permission system

---

## Workflows

This project does several kinds of work. Each kind has its own
workflow. Pick the right one.

| Cue | Workflow | Gate |
|-----|----------|------|
| "What's going on in the server?" / "Investigate X" | **Server Inspection Workflow** | None — read-only is always safe |
| "Add a new feature" / "Build X" / "Solve Y" | **Implementation & Bug-Fix Workflow** (5 phases) | All phases complete + 3x LOW risk |
| "Why is X broken?" | **Bug Investigation Workflow** | RCA artifact before any fix |
| "Deploy the latest code" | **Deployment Workflow** | Tests + migration dry-run |
| "Fix a broken third-party integration" | **Integration Triage Workflow** | User decides keep-vs-replace |
| "Make a structural change to the server" | **Mutation Safety Workflow** | Per-action user approval |
| "Research what's possible or how things work" | **Research Workflow** | None — it's advisory |

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
| 6. Implementation | `gpt-high` | code | **Only after hookpoints.** Launch implementation. |
| 7. PR review | `claude-opus` | review comments | Multi-concern check + justification check. Split oversized PRs. |

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
| 6. PR review | **`claude-opus`** multi-concern + justification check | Split oversized PRs |

**Rule of thumb**: phases that set scope belong to the user; phases
that validate design or code belong to agents. Do not ask for user
review where a risk gate or PR review is the correct control.

Risk phase specifically:
- All three risks must return **LOW**
- If any is MEDIUM or HIGH, revise proposal and re-run the full risk
  gate — do not cherry-pick which risks to address
- If a risk is LOW but surfaces a concern worth discussing, raise it
  to the user as an observation, not a gate

### Worked example (the current task)

1. Problem research ([research/prompts/01-problem-space.md](research/prompts/01-problem-space.md) → `research/01-problem-space.md`) — **running now**
2. Humility needs synthesis → `research/02-humility-needs.md`
3. v1 proposal → `proposals/01-v1-scope.md`
4. 3x risk → `risk/01-*.md`
5. Hookpoint research → `research/03-hookpoints.md`
6. Implementation → actual daemon code
7. PR review → merge

---

## Bug Investigation Workflow

When something in the live server or our code is broken:

1. **Reproduce** using `discord_cli.py` read commands
2. **RCA agent** (`gpt-high`) writes `research/NN-rca.md`
3. **User reviews RCA** — decides if fix is needed, or if the issue is
   someone else's problem (e.g., a dying third-party bot)
4. If a fix is needed, drop into the normal 5-phase pipeline from
   phase 3 (Proposal)

Do **not** patch bugs by jumping straight to a fix. RCA first.

---

## Integration Triage Workflow

When a third-party bot or integration is broken (it's happened to us
with ticketsbot.net, Gather, and tickets.bot v2 so far):

1. **Determine dead or alive**: firecrawl the service homepage, try
   their docs, try the dashboard, check for sunset notices
2. **Determine data at risk**: can the data be exported? Does it
   matter? (In our history: 3 test tickets + a single form = nothing.)
3. **Present to user** with two options:
   - (a) Push through the third-party path (time investment, future
     lock-in)
   - (b) Replace with a custom implementation (more work up front,
     zero future surprise)
4. **Never** silently move the user toward (b). It must be an informed
   choice — some integrations are genuinely worth keeping.

See `NOTES.md` for the ticketsbot.net and tickets.bot investigations
as worked examples.

---

## Mutation Safety Workflow

For tier-3 (write-visible) actions, follow this checklist **per action**:

1. **State the action** as a one-line intent (e.g., "kick Gather from
   the server", "create category `dark-nemesis`", "remove `Chapter
   Applicant` role from user X")
2. **State the reversal path**: what would it take to undo this? If
   the reversal is impossible or expensive, escalate severity.
3. **Ask the user for explicit confirmation** with the action, the
   blast radius, and the reversal path in one message
4. **Wait for an explicit "yes, do it"** — "OK" in context, but not a
   general "keep going"
5. **Execute** and immediately **verify** the result (next inspection
   commands, log the change in `NOTES.md` D log)
6. **Never batch** multiple tier-3 actions into a single approval
   unless the user has explicitly said "go through the list and do all
   of them"

---

## Server Inspection Workflow

Tier-1 read operations. Always-available. Use liberally.

### Tool: `discord_cli.py`

One-shot CLI. Run via `uv run python discord_cli.py <subcommand>`.
Subcommands return JSON on stdout. Pipe to `jq` for readability.

| Subcommand | Purpose |
|------------|---------|
| `overview` | Guild summary + counts |
| `channels` | Full channel tree (categories → children) |
| `roles` | Role hierarchy, top-down |
| `bots` | Bot members, roles, application info |
| `members [--bots/--humans] [--limit N]` | Member list |
| `integrations` | Server integrations (official path to see app-managed bots) |
| `webhooks` | Webhook inventory |
| `emojis` | Emoji inventory |
| `me` | Bot's own permissions |
| `user <id>` | Fetch user info + member record |
| `channel <id>` | Single channel detail (topic, overwrites, type) |
| `find-channel <query>` | Substring search across channel names |
| `read <channel_id> [--limit N] [--before ID] [--after ID]` | Recent messages in a channel, serialized (content, embeds, components, reactions, pins) |
| `search <query> [--channels id...]` | Substring content search across text channels |
| `bot-activity <bot_id> [--per-channel-limit N]` | Audit a bot's message footprint across text channels |
| `send <channel_id> "msg"` | **Tier 2** — post a message. Use with care. |

### When to add a subcommand

If you find yourself writing the same inline Python twice, turn it into
a `discord_cli.py` subcommand. This CLI is canonical — it survives all
phases.

### What to do with findings

Update `NOTES.md` as you go. Treat it as the living audit of the
Humility server's real state. Don't re-derive things that are already
documented there.

---

## Research Workflow

When phase 1 of the pipeline demands external research (problem space,
existing solutions, API constraints), delegate to `gpt-high` via the
`agents` binary.

### Prompt construction

1. Write the prompt to `research/prompts/NN-<topic>.md`
2. Prompt must include: scope, personas, deliverable shape, sections,
   anti-goals, evidence quality bar, output path
3. Anti-goals matter as much as goals — tell the model what *not* to
   do (no solutions, no design, no recommendations)
4. Pass the project directory with `-p` so the model can write its
   output in-repo

### Dispatch

Run in the background via Claude Code's Bash tool with
`run_in_background: true`. Redirect stdout/stderr to `.tmp/<name>.log`
so you can inspect progress.

```bash
agents -m gpt-high -p /home/nes/discord \
    -f /home/nes/discord/research/prompts/01-problem-space.md \
    > /home/nes/discord/.tmp/research-01-run.log 2>&1
```

### Completion

You'll get a background-task notification when the agent finishes.
Check the log, skim the artifact, update the research index, and move
to the next phase.

---

## Risk Assessment Workflow

Phase 4 of the pipeline. Three parallel `claude-opus` sub-agents.

Each risk sub-agent receives:
- The proposal being assessed
- A narrow prompt defining its risk type (audit / scope / shortcut)
- Instructions to return LOW / MEDIUM / HIGH with justification

### Risk types

| Type | Question |
|------|----------|
| **Audit** | Does the proposal introduce safety, security, privacy, or data-integrity risks? Consider rate limits, token leakage, injection vectors, destructive operations, GDPR. |
| **Scope** | Is the proposed scope reasonable? Is it too ambitious for the problem, or too narrow? Does it create downstream work the team can't afford? Does it block future changes? |
| **Shortcut** | Does the proposal itself introduce shortcuts — hacks, hardcoded values, duplicated logic, source-vs-artifact confusion, symptom-masking workarounds, or "fix one shortcut by adding another"? A proposal that replaces a shortcut with a different shortcut fails this. |

### Dispatch

Three background bash tasks in parallel. Collect outputs when all
three complete. All three must be **LOW**. If any is **MEDIUM** or
**HIGH**, revise the proposal and re-run the whole risk gate — do not
cherry-pick which risks to address.

---

## Deployment Workflow

### Target stack

- **Compute**: Railway (long-running container, `uv run python -m daemon`)
- **Database**: Supabase (managed Postgres, via `postgres://` URL env var)
- **Secrets**: Railway environment variables — `DISCORD_BOT_TOKEN`,
  `DISCORD_GUILD_ID`, `SUPABASE_DB_URL`, `SUPABASE_SERVICE_KEY`
- **Logs**: Railway's built-in log stream; no APM for MVP

### Pre-deploy checklist

1. Smoke-test locally with a `.env` pointing at a **staging**
   Supabase project (TBD — no staging project exists yet; first
   deployment will create it)
2. Run DB migrations in dry-run mode against staging
3. Open a draft PR; risk-assess with the standard 3x process if the
   change hits live-server surface
4. Deploy via Railway auto-deploy on main merge

### Migration strategy

Schema changes go through proper migrations — never hand-edit Supabase.
Migration tool TBD in the proposal phase (likely Alembic or Supabase
CLI). Each migration is a self-contained file in `migrations/`.

**No ad-hoc schema changes.** If the code needs a new column,
the migration comes first, reviewed, then the code change references
the new column.

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

### Agent prompt structure

**Test agent prompt** (step 2):
```
You are a test-writing agent. You ONLY write tests.
Read the contracts at services/api/app/contracts/*.py.
Read the endpoint signatures at services/api/app/api/v1/endpoints/*.py.
Do NOT read services/api/app/services/, repositories/, or infrastructure/.
Write tests to services/api/tests/ that verify the API contract.
Each test encodes INTENT: what should happen when this endpoint is
called with these inputs?
```

**Code agent prompt** (step 3):
```
You are an implementation agent. You write code that makes tests pass.
Read the contracts, the endpoint signatures, AND the test files.
Implement the service, repository, and infrastructure layers.
Follow the ai-workflow layered architecture.
Run pytest to verify. Do not modify tests.
```

### Optimistic locking in tests

Tests MUST verify optimistic locking behavior for versioned entities
(from the java-interview-setup pattern):
- Read entity → get version N
- Update with version N → succeeds, version becomes N+1
- Update with stale version N → returns 409 Conflict
- This is a contract-level behavior, so the test agent writes it.

## Model Roles

| Task | Model | Why |
|------|-------|-----|
| Problem-space research | `gpt-high` | Best at systematic analysis and synthesis over many sources |
| Synthesis of research against user context | `claude-opus` (this session) | Good at carrying conversational context and user-specific nuance |
| Proposal drafting | `gpt-high` | Best at producing structured technical proposals |
| Risk assessment (3x parallel) | `claude-opus` | Conservative, evidence-oriented, good at spotting shortcuts |
| Hookpoint research | `gpt-high` | Best at systematic code analysis |
| Implementation (code) | `gpt-high` | Best at writing production code |
| PR review (multi-concern + justification) | `claude-opus` | Good at "what doesn't belong in this PR" |
| Quick verification / builds / one-offs | `glm` | Fast, cheap |
| Visual design, SVG, diagrams | `gemini-high` | If we ever need this, but unlikely for Discord work |
| Bug RCA | `gpt-high` | Same pattern as `~/work/AGENTS.md` |

### Model boundary: Claude (orchestrator) vs external agents

**Claude Code (this session) orchestrates** the pipeline: writes
prompts, launches agents, collects artifacts, presents to user,
tracks tasks, enforces the gate rules. It does NOT do phase-1
research or phase-6 implementation itself.

**External models do the work inside a phase.** A single phase
invocation is atomic from this session's perspective — it kicks off
an `agents` subprocess with a self-contained prompt and gets back a
written artifact.

The exception: **phase 2 (synthesis)** is done by this session
because it requires carrying conversational context that an external
model doesn't have. Synthesis output still lands as a written
artifact in `research/` and is visible to downstream phases.

---

## Running External Models

Via `~/.local/bin/agents` (the Oulipoly Agent Runner CLI). See
`~/work/AGENTS.md` for full syntax. Quick reference:

```bash
# Foreground, stdout to terminal
agents -m gpt-high -p /home/nes/discord -f research/prompts/01-problem-space.md

# Background (via Claude Code Bash with run_in_background: true)
agents -m gpt-high -p /home/nes/discord -f research/prompts/01-problem-space.md \
    > .tmp/research-01-run.log 2>&1

# Parallel risk assessments
agents -m claude-opus -p /home/nes/discord -f risk/prompts/audit.md    > .tmp/risk-audit.log    2>&1 &
agents -m claude-opus -p /home/nes/discord -f risk/prompts/scope.md    > .tmp/risk-scope.log    2>&1 &
agents -m claude-opus -p /home/nes/discord -f risk/prompts/shortcut.md > .tmp/risk-shortcut.log 2>&1 &
wait
```

Use Claude Code's `run_in_background: true` flag so this session keeps
working while agents execute. You'll get a notification on completion.

**Do not poll.** Don't sleep-and-check in a loop. The runtime will
notify you.

---

## Infrastructure Reference

### Discord

| Thing | Value |
|-------|-------|
| Guild | Humility |
| Guild ID | `900000000000000001` |
| Owner | nestharus (`900000000000000002`) |
| Bot (this project) | `server-manager#1554` (id `1492535248825745558`) |
| Bot permissions | Administrator (everything) |
| Privileged intents enabled | Server Members, Message Content |
| Bot token | `.env` → `DISCORD_BOT_TOKEN` (gitignored) |

### Railway — TBD

Will be set up during proposal/deployment phase. A dedicated Railway
project for this bot (not shared with RFQ). Service name TBD.

### Supabase — TBD

Will be set up during proposal phase. One project, two databases:
- `humility-prod` (live)
- `humility-staging` (future — for testing before prod)

---

## Canonical vs Pre-Research Code

**Canonical** (expected to survive all phases):

- `discord_cli.py` — one-shot inspection CLI. Read-mostly. Non-negotiable.
- `NOTES.md` — live audit of the Humility server state
- `DECISIONS.md` — append-only decision log
- `AGENTS.md` (this file)
- `research/`, `proposals/`, `risk/` — phase artifacts
- `.env`, `.gitignore`, `pyproject.toml`

**Pre-research drafts** (may or may not survive the hookpoint phase):

- `daemon/` — SQLite-based daemon skeleton (wrong DB) + pre-research
  applications subsystem. `daemon/db.py` is definitely going away.
- `chapters.yaml` — pre-research registry
- `forms/dark-nemesis.yaml` — historical reference for a chapter that
  no longer exists
- `docs/APPLICATIONS_SKETCH.md`, `docs/DAEMON_DESIGN.md` — superseded
  design docs from before the pipeline was adopted

Do not delete pre-research code silently. The hookpoint phase
(phase 5) explicitly decides what to keep.

---

## Directory Layout

```
discord/
├── AGENTS.md                    # this file — workflow contract
├── DECISIONS.md                 # append-only decision log
├── NOTES.md                     # live server audit
├── pyproject.toml
├── uv.lock                      # gitignored
├── .env                         # gitignored — bot token + guild id
├── .gitignore
├── .tmp/                        # agent logs, scratch; gitignored
├── discord_cli.py               # canonical inspection CLI
├── chapters.yaml                # pre-research; may be replaced
├── forms/                       # pre-research; may be replaced
│   └── dark-nemesis.yaml
├── daemon/                      # pre-research draft
│   ├── __init__.py
│   ├── __main__.py
│   ├── applications.py
│   ├── claim.py
│   ├── config.py
│   └── db.py                    # WRONG — SQLite; will be replaced
├── docs/                        # superseded pre-research docs
│   ├── APPLICATIONS_SKETCH.md
│   └── DAEMON_DESIGN.md
├── research/                    # phase 1/2/5 outputs
│   ├── 00-INDEX.md
│   ├── prompts/
│   │   └── 01-problem-space.md
│   └── 01-problem-space.md      # to be written by gpt-high
├── proposals/                   # phase 3 outputs
└── risk/                        # phase 4 outputs
    └── prompts/
```

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

## Global Constraints

- **`discord_cli.py` stays canonical.** All inspection subcommands
  evolve there. Don't build parallel inspection tools.
- **Phase gates are non-negotiable.** No "this one is small, let me
  skip the proposal." Small proposals are fine, skipped proposals are
  not.
- **All PRs opened in draft mode** (per `~/work/AGENTS.md`).
- **Cloud stack = Railway + Supabase.** Not AWS, not Fly.io, not
  self-hosted.
- **No secrets in the repo.** `.env` is gitignored. Railway env vars
  are the production source.
- **No local-first design.** If a feature requires something that
  breaks in a Railway container, the feature has to be redesigned.
