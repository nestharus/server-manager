# Proposal Prompt: API Settings Module

## Task
Write a proposal for implementing `services/api/app/core/settings.py` for the Humility Discord server manager.

## Inputs
Read these files before writing the proposal:
- `research/20-settings.md` — problem space research
- `research/20-settings-needs.md` — synthesized needs
- `.refs/ai-workflow/app/core/settings.py` — reference implementation
- `.env.example` — current env contract
- `AGENTS.md` — project rules

## Deliverable
Write `proposals/20-settings.md` containing:

1. **Goal** — what this module does and why
2. **Design** — the `Settings` class definition with exact field names, types, defaults, and validators
3. **Architecture** — how it fits in the layered pattern, how the factory will use it
4. **Tradeoffs** — decisions made and alternatives not taken
5. **Anti-scope** — what is explicitly excluded and why

## Constraints
- Follow the ai-workflow `BaseSettings` pattern
- Required fields: `discord_bot_token`, `discord_guild_id`, `supabase_db_url`, `supabase_service_key`
- Optional fields: `discord_staging_guild_id`, provider API keys
- Exclude `RAILWAY_TOKEN` (deployment tooling, not runtime)
- Use `repr=False` on sensitive fields
- No dotenv auto-loading (no `env_file` in model_config)
- No middleware settings, no nested config, no credential complexity regex
- Validation: required presence + integer type for guild IDs only
- App metadata: `app_name`, `app_version`, `debug`, `api_prefix` with defaults

## Rules
- Do NOT implement. Propose the design only.
- Write the proposal to `proposals/20-settings.md`
