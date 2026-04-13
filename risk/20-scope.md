# Scope Risk: `services/api/app/core/settings.py`

**Overall risk level: LOW**

The proposal tightly mirrors the environment contract already declared in
`.env.example`, follows the `ai-workflow` reference pattern without
copying its stack-specific fields or validators, and explicitly excludes
every category of premature complexity identified by the research. The
anti-scope section is comprehensive and well-justified. No scope creep in
either direction.

## Findings

### 1. Field inventory matches the evidenced environment surface exactly

**Severity: INFO**

Every field in the proposal maps to a concrete entry in `.env.example`
or to application metadata already declared in `pyproject.toml`:

- `discord_bot_token`, `discord_guild_id`, `discord_staging_guild_id`
  — `.env.example:2-4`
- `supabase_db_url`, `supabase_service_key` — `.env.example:7-8`
- `google_cloud_vision_key`, `gemini_api_key`, `z_ai_api_key`,
  `minimax_api_key` — `.env.example:14-17`
- `app_name = "server-manager-api"`, `app_version = "0.1.0"`
  — `services/api/pyproject.toml:2-3`
- `debug`, `api_prefix` — minimal scaffold metadata

No invented fields. No fields carried forward from the reference that
don't apply to this stack (SurrealDB, Elasticsearch, middleware toggles,
CSV paths are all absent). `RAILWAY_TOKEN` is correctly excluded as
deployment tooling.

### 2. Required vs. optional field classification is correct

**Severity: INFO**

The proposal makes `discord_bot_token`, `discord_guild_id`,
`supabase_db_url`, and `supabase_service_key` required (no defaults),
matching the behavior already enforced by sibling runtime code in
`discord_cli.py` and `daemon/__main__.py`. Provider credentials are
correctly optional (`str | None = None`) since they are feature-gated,
not startup-critical. `discord_staging_guild_id` is correctly optional
since not all deployments have a staging guild.

### 3. Validation surface is appropriately narrow

**Severity: INFO**

The proposal explicitly limits validation to required-presence and
integer-type coercion for guild IDs. It excludes:

- Token-shape or credential-complexity validation (third-party issued)
- DSN scheme validation for `supabase_db_url`
- Middleware/CORS/HTTP settings
- Cross-setting policy rules

This matches the research conclusion that the current scaffold stage
warrants structural validation only. The reference's URL validators and
credential-complexity regex are correctly not adopted.

### 4. `repr=False` over `SecretStr` is a justified scaffold tradeoff

**Severity: INFO**

The proposal uses `repr=False` for sensitive fields and documents the
tradeoff explicitly: `repr=False` avoids `.get_secret_value()` friction
throughout the early scaffold while still protecting debug
representations. The research confirms that `SecretStr` covers more
surfaces but adds unwrapping friction that is not justified when no
service code consumes these values yet. The tradeoff section correctly
identifies `SecretStr` as a future upgrade path.

### 5. No `env_file` / no dotenv auto-loading is correct

**Severity: INFO**

The proposal explicitly excludes `env_file` from `model_config`. The
research documents two concrete reasons this is right:

- The repo-root `.env` is not in `services/api/`, so
  `env_file='.env'` would be working-directory-dependent
- The repo `.env` contains keys outside the API surface
  (`RAILWAY_TOKEN`), which would cause `ValidationError` with default
  `extra` handling

Dotenv loading is correctly left to the caller or process launcher.

### 6. Anti-scope is comprehensive and matches research gaps

**Severity: INFO**

The anti-scope section excludes six categories, each directly supported
by the research:

- `RAILWAY_TOKEN` — research §1 identifies it as deployment, not runtime
- Middleware/HTTP settings — research §1 confirms the scaffold doesn't
  expose these behaviors
- Nested config objects — research §3 confirms the env surface is flat
- Credential-shape validation — research §5 confirms third-party tokens
  don't warrant format checks
- Dotenv ownership — research §3 documents the working-directory and
  extra-keys hazards
- Runtime behavior beyond configuration — correctly keeps the module as
  pure configuration

No gaps identified. No categories of premature complexity left
unaddressed.

### 7. Architecture placement is correct and non-constraining

**Severity: INFO**

The proposal places `Settings` in `services/api/app/core/`, matching the
`ai-workflow` reference and the architecture described in `AGENTS.md`.
The factory-owns-settings pattern (instantiate once at startup, inject
via `app.state` or dependencies) is described without being implemented,
which is appropriate for a design-only proposal. Services and
repositories receive settings via injection, not by instantiating
`Settings()` themselves. This avoids coupling downstream modules to the
environment.

### 8. No `model_config` overreach

**Severity: INFO**

The proposal states that `model_config`, if defined at all, should
remain minimal and must not include `env_file`,
`env_nested_delimiter`, or secrets-directory configuration. Omitting it
entirely is allowed. This prevents premature configuration of
pydantic-settings behaviors that have documented sharp edges (dotenv
extras, nested delimiter splitting) before the scaffold needs them.
