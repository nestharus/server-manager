# Proposal Prompt: API Factory Module

## Task
Write a proposal for implementing `services/api/app/core/factory.py`.

## Inputs
- `research/21-factory.md` — problem space research
- `research/21-factory-needs.md` — synthesized needs
- `.refs/ai-workflow/app/core/factory.py` — reference implementation
- `services/api/app/core/settings.py` — settings module (already implemented)
- `AGENTS.md` — project rules

## Deliverable
Write `proposals/21-factory.md` containing:
1. **Goal** — what this module does
2. **Design** — the `create_app` function signature, behavior, and app construction
3. **Architecture** — how it fits in the layered pattern
4. **Tradeoffs** — decisions and alternatives
5. **Anti-scope** — what is explicitly excluded

## Constraints
- Expose `create_app(settings: Settings | None = None) -> FastAPI`
- Instantiate Settings() when settings is None
- Set app title, version, debug from settings
- Store settings on `app.state.settings`
- No routers, middleware, lifespan, or exception handlers
- No load_dotenv() — env preparation is the caller's concern

## Rules
- Do NOT implement. Propose the design only.
- Write the proposal to `proposals/21-factory.md`
