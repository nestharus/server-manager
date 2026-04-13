# Research: API Settings Module

## Task
Research the problem space for implementing an API settings module for the Humility Discord server manager's FastAPI service.

## Context
- This is the FastAPI API service under `services/api/`
- It follows the ai-workflow layered pattern (api -> services -> repositories -> infrastructure)
- Uses pydantic-settings for configuration
- The `.env.example` defines these environment variables:
  - DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, DISCORD_STAGING_GUILD_ID
  - SUPABASE_DB_URL, SUPABASE_SERVICE_KEY
  - RAILWAY_TOKEN
  - GOOGLE_CLOUD_VISION_KEY, GEMINI_API_KEY, Z_AI_API_KEY, MINIMAX_API_KEY

## Reference
The reference implementation at `/home/nes/discord/.refs/ai-workflow/app/core/settings.py` (on branch `init`) uses:
- `pydantic_settings.BaseSettings`
- Field validators for URL schemes and positive integers
- Custom error classes for validation failures
- Security-sensitive fields marked with `repr=False`

## Deliverable
A research report documenting:
1. What configuration the API service needs at this scaffold stage
2. What patterns from the ai-workflow reference should be adopted vs. adapted
3. How pydantic-settings handles env loading, .env files, and nested config
4. Security considerations for sensitive fields (tokens, keys, DB URLs)
5. What validation is appropriate at this stage

## Rules
- Do NOT design solutions. Document the problem space with evidence.
- Read the reference settings.py at `.refs/ai-workflow/app/core/settings.py`
- Read the `.env.example` to understand what env vars exist
- Write your findings to `research/20-settings.md`
