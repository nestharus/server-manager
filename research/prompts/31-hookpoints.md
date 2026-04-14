# Hookpoint Research: Phase 1 Foundation — Terraform Infrastructure

## Context

You are performing hookpoint research for the Phase 1 Foundation
Terraform infrastructure implementation. This phase maps the validated
proposal to existing code to find what's reusable, what's parallel,
and what to delete.

Read these files:
- `proposals/31-phase1-terraform.md` — the validated proposal
- `plans/proposals/phase1-foundation.md` — overarching Phase 1 context
- `research/31-phase1-terraform.md` — problem research
- `research/31-phase1-terraform-needs.md` — synthesized needs

## Scope

Examine the existing codebase to identify:

1. **What already exists** in `infra/` — are there any existing
   Terraform files, modules, or configurations?
2. **What's in `plans/`** — the platform planning artifacts contain
   infrastructure research. Which research findings are directly
   applicable to the Terraform files being created?
3. **Pre-existing code to preserve** — `daemon/`, `discord_cli.py`,
   `forms/`, `docs/` — none of these should be affected by Terraform
   infrastructure work, but confirm no conflicts.
4. **Directory structure** — confirm `infra/environments/{staging,production}`
   and `infra/modules/` directories exist and are ready.
5. **Git branch state** — confirm we're on `feat/phase1-foundation`.

## Deliverable

Write your findings to `research/31-hookpoints.md`.

Include:
- List of existing files that interact with the new Terraform files
- List of files that should NOT be touched
- Any naming or convention patterns to follow
- Recommendations for file placement

## Anti-goals

- Do NOT implement any code
- Do NOT modify existing files
- Do NOT propose architectural changes

## Output path

`research/31-hookpoints.md`
