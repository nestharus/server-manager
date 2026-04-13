# Hookpoint Research: API Settings Module

## Task
Map the proposal in `proposals/20-settings.md` to existing code. Find
what's reusable, what's parallel, and what needs to be created new.

## Inputs
- `proposals/20-settings.md` — the approved proposal
- `research/20-settings.md` — research findings
- `.refs/ai-workflow/app/core/settings.py` — reference implementation
- `services/api/app/core/__init__.py` — target package
- `services/api/pyproject.toml` — dependencies
- `discord_cli.py` — existing env loading pattern
- `daemon/__main__.py` — existing env loading pattern

## Deliverable
Write `research/20-hookpoints.md` documenting:
1. What existing code can be reused or referenced
2. What files need to be created
3. What imports/dependencies are needed
4. What patterns from the reference should be followed exactly
5. What parallel/duplicate code would this create (should be none)

## Rules
- Do NOT implement. Map the proposal to code only.
- Write findings to `research/20-hookpoints.md`
