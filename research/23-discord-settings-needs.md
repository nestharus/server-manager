# Synthesis: Discord Settings Needs for Humility

## Context Mapping

### 1. Required fields for the daemon

The daemon needs:
- `discord_bot_token: str` — required, sensitive (repr=False)
- `discord_guild_id: int` — required, the primary guild
- `supabase_db_url: str` — required, PostgreSQL connection string, sensitive

These match the smoke-test pattern:
```python
Settings(discord_bot_token="test", discord_guild_id=1, supabase_db_url="postgresql://test")
```

### 2. Independent settings from API

The daemon settings should be an independent `BaseSettings` subclass,
NOT importing from the API service. Both services share env var names
(no prefix) but are separate packages with separate deployments.

### 3. No dotenv auto-loading

Following the API settings pattern, the daemon settings should NOT
auto-load `.env` files. The entry point handles dotenv loading.

### 4. Secrets hidden from repr

`discord_bot_token` and `supabase_db_url` must use `repr=False` to
prevent token leakage in logs/tracebacks.

### 5. Construction must expose discord_guild_id

The smoke test pattern requires `settings.discord_guild_id` to be
accessible as an attribute on the constructed object.

## Gaps

None. The research covers field requirements, env naming, and the
relationship to the API settings module.
