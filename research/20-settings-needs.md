# Synthesis: API Settings Module Needs

Date: 2026-04-13
Based on: research/20-settings.md

## Humility-Specific Context

The API service is the mutation gateway for both the web UI and the
Discord daemon. At this scaffold stage, it needs to encode the
environment contract already declared in `.env.example` without
over-engineering for features that don't exist yet.

## Confirmed Needs

1. **Single `BaseSettings` class** — one settings object that the
   factory can instantiate and inject. Follows the ai-workflow pattern.

2. **Required fields from evidence**:
   - `discord_bot_token: str` — required, secret (repr=False minimum)
   - `discord_guild_id: int` — required, validated as integer
   - `discord_staging_guild_id: int | None` — optional (not all
     deployments have staging)
   - `supabase_db_url: str` — required, secret (contains credentials)
   - `supabase_service_key: str` — required, secret

3. **Optional provider credentials** — these are feature-gated, not
   startup-critical:
   - `google_cloud_vision_key: str | None = None`
   - `gemini_api_key: str | None = None`
   - `z_ai_api_key: str | None = None`
   - `minimax_api_key: str | None = None`

4. **Operator credential excluded** — `RAILWAY_TOKEN` is deployment
   tooling, not API runtime. Exclude from Settings.

5. **App metadata** — `app_name`, `app_version`, `debug` with sensible
   defaults for the scaffold.

6. **Secret treatment** — use `repr=False` on sensitive fields.
   `SecretStr` is stronger but adds unwrapping friction; defer decision
   to when the service actually consumes these values. `repr=False` is
   the minimum bar.

7. **No dotenv auto-loading** — don't set `env_file` on the model.
   The repo-root `.env` is not in `services/api/`, and dotenv with
   `extra=forbid` would reject unknown keys. Let the caller handle
   dotenv loading if needed (or use process env vars directly).

8. **Validation surface** — keep narrow:
   - Required presence for token, guild ID, DB URL, service key
   - Integer type for guild IDs
   - No password-complexity or token-shape validation (third-party issued)
   - No middleware/CORS/HTTP settings (not yet implemented)

## Gaps / Open Questions

- Whether `supabase_db_url` should be validated as a PostgreSQL DSN
  (scheme check) or kept as an opaque string. The reference validates
  DB URLs by scheme, which is reasonable but adds a validator. Keep as
  opaque string for now since the DB layer doesn't exist yet.
- `api_prefix` default: the reference uses `/api/v1`. Reasonable to
  adopt the same convention.

## Anti-Scope

- No middleware settings (CORS, gzip, rate limiting)
- No nested config or env_nested_delimiter
- No secrets-directory support
- No credential complexity regex
- No environment label (staging/production discriminator)
