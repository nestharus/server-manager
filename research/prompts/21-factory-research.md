# Research: API Factory Module

## Task
Research the problem space for implementing an API application factory
for the Humility Discord server manager's FastAPI service.

## Context
- This is the FastAPI API service under `services/api/`
- It follows the ai-workflow layered pattern (api -> services -> repositories -> infrastructure)
- `services/api/app/core/settings.py` already exists with a `Settings` class
- The reference implementation at `.refs/ai-workflow/app/core/factory.py` shows the pattern
- The factory will be used by `app/main.py` as: `from app.core.factory import create_app; app = create_app()`

## Reference
Read the reference factory at `.refs/ai-workflow/app/core/factory.py`.

## Deliverable
A research report documenting:
1. What the factory module needs to do at this scaffold stage
2. What patterns from the ai-workflow reference should be adopted vs. adapted
3. How FastAPI app construction works (metadata, state, lifespan)
4. What the factory should expose (function signature, return type)
5. What the factory should NOT do yet (routers, middleware, etc.)

## Rules
- Do NOT design solutions. Document the problem space with evidence.
- Read the reference factory.py, the settings module, and AGENTS.md
- Write your findings to `research/21-factory.md`
