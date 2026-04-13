# Hookpoint Research: API Factory Module

## Task
Map the proposal in `proposals/21-factory.md` to existing code.

## Inputs
- `proposals/21-factory.md` — the approved proposal
- `research/21-factory.md` — research findings
- `.refs/ai-workflow/app/core/factory.py` — reference implementation
- `services/api/app/core/settings.py` — settings module (exists)
- `services/api/app/core/__init__.py` — target package
- `services/api/app/__init__.py` — service package

## Deliverable
Write `research/21-hookpoints.md` documenting:
1. What existing code can be reused (settings.py)
2. What files need to be created (factory.py only)
3. What imports are needed
4. What patterns from the reference apply
5. Integration with main.py (which will import create_app)

## Rules
- Do NOT implement. Map the proposal to code only.
- Write findings to `research/21-hookpoints.md`
