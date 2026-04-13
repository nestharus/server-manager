# Research Task: Discord Guild Management Problem Space

## Hard rules

**You are the researcher. Do the research yourself.**
Do not launch, spawn, or delegate to any other agent.

Your deliverable is a single markdown file:
`research/01-problem-space.md`

- **DO** read `AGENTS.md` for project context and workflow rules
- **DO** read `DECISIONS.md` for the locked workflow pivots
- **DO** use web research and current official documentation
- **DO** use dated evidence and note when older community lore is stale
- **DO NOT** inspect the live Humility server in this phase
- **DO NOT** read `NOTES.md` in this phase
- **DO NOT** propose solutions or architecture
- **DO NOT** modify any file other than `research/01-problem-space.md`

## Context

This project is for the Humility Discord guild, but phase 1 is not
server-specific synthesis. The goal here is to map the broader Discord
guild-management problem space before deciding what Humility should
build.

The target slice is not generic chat communities. Focus on the kinds of
servers that look like gaming guilds, alliances, clans, or umbrella
communities with sub-groups, officer structures, applications, tickets,
and long-lived operational workflows.

Prior draft work made premature assumptions about architecture and
feature shape. Ignore those solutions. This phase is about understanding
the actual problem surface.

## What to research

Write a research report that covers all six of these sections.

### 1. Taxonomy of operational problems

Document the main categories of pain that appear in Discord community
management, especially for gaming / multi-sub-community servers:

- onboarding and verification
- applications and structured intake
- tickets / support / incident intake
- moderation accountability and audit trails
- chapter / clan / guild provisioning and lifecycle management
- activity tracking and compliance workflows
- role / permission / category sprawl
- bot overlap, abandonment, and vendor lock-in

For each category, explain the underlying operational problem, not just
the feature request people ask for.

### 2. Existing-solutions map

Map the current solution landscape:

- Discord built-ins
- ticket bots
- application bots / form bots
- modmail and moderation bots
- guild-management tools used by gaming communities

For each category, document:
- what it covers well
- what it consistently fails to cover
- where lock-in or shutdown risk shows up
- where multi-chapter / multi-officer workflows remain unsolved

### 3. Discord platform constraints and moving-target facts

Research the official constraints and capabilities that shape design:

- role, channel, category, and thread limits
- audit log retention
- permission / overwrite behavior
- current modal / component capabilities
- forum / thread behavior where relevant
- any API or product constraints that materially change what is hard

Be explicit about facts that changed over time and would invalidate
stale assumptions.

### 4. Multi-sub-community / chapter-management patterns

Research the problems that appear when one Discord server contains many
sub-groups:

- officer autonomy vs central staff override
- waitlists and chapter-specific intake
- spinning up or archiving sub-communities
- ownership transfer and succession
- member-list privacy / operational secrecy
- permission drift over time

Focus on the structure of the problem, not the implementation.

### 5. Cross-cutting concerns

Document cross-cutting issues that span multiple subsystems:

- volunteer staff burnout
- manual data entry and spreadsheet dependency
- long-term retention / audit requirements
- dependence on third-party bots for critical workflows
- migration pain when a vendor dies or sunsets
- governance / trust / accountability requirements

### 6. Open questions for Humility-specific synthesis

End with the questions that a phase-2 synthesis pass must answer to map
this broad problem space onto the actual Humility server.

These should be scoping questions, not design proposals.

## Evidence requirements

- Prefer official docs, platform docs, vendor docs, and dated public
  announcements where possible
- Supplement with representative community evidence when the problem is
  mostly documented in lived experience rather than formal docs
- Distinguish official claims from community reports
- Use concrete dates whenever a capability or shutdown timing matters

## Output format

Write `research/01-problem-space.md` with this structure:

```markdown
# Discord Guild Management Problem Space

Research date: [date]

## Executive summary
[2-3 paragraphs]

## 1. Taxonomy of operational problems
[findings]

## 2. Existing-solutions map
[findings]

## 3. Discord platform constraints and moving-target facts
[findings]

## 4. Multi-sub-community / chapter-management patterns
[findings]

## 5. Cross-cutting concerns
[findings]

## 6. Open questions for Humility-specific synthesis
[questions only]
```

## Anti-goals

- **Do not propose solutions**
- **Do not write a product roadmap**
- **Do not scope the MVP**
- **Do not assume Humility's server state without evidence**
- **Do not exceed 5000 words**
