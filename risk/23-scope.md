# Scope Risk Assessment: Discord Settings

## Overall: LOW

The proposal defines one `BaseSettings` subclass with exactly three
fields, all directly evidenced by research as current daemon
requirements. It introduces no new dependencies, no cross-service
coupling, and explicitly fences out twelve categories of potential
scope expansion. The design mirrors the existing API settings pattern
without importing it.

## Findings

### Finding 1: No scope creep detected
- Severity: LOW
- Description: The research identified three required daemon inputs:
  bot token, guild ID, and database URL. The synthesis confirmed these
  three with no gaps. The proposal delivers exactly those three fields
  with types and sensitivity annotations matching both the research
  evidence and the existing API settings module
  (`services/api/app/core/settings.py:11-15`). The research noted that
  an API base URL is architecturally adjacent but not yet evidenced by
  code or tests — the proposal correctly excludes it via anti-scope
  (proposal lines 113-129). Nothing in the proposal extends beyond what
  the research surfaced.

### Finding 2: Complexity is proportional
- Severity: LOW
- Description: The implementation surface is one class inheriting
  `BaseSettings` with three fields and no `model_config`. Validation
  stays at Pydantic defaults: required presence and integer coercion.
  The proposal explicitly rejects custom token validators, DB URL
  scheme validators, nested models, env prefixes, and singleton
  accessors (proposal lines 113-129). The test contract (proposal
  lines 135-149) enumerates seven verifiable properties but requires no
  test infrastructure beyond standard Pydantic assertions and
  `monkeypatch` for env vars — the same pattern already used in
  `services/api/tests/test_settings.py`. Document length is in
  reasoning and guardrails, not code surface.

### Finding 3: No new dependency surface
- Severity: LOW
- Description: The proposal depends on `pydantic.Field` and
  `pydantic_settings.BaseSettings`, both already declared in
  `services/discord/pyproject.toml:7-9` (`pydantic>=2.9.0`,
  `pydantic-settings>=2.5.0`). No new packages are introduced. The
  module is explicitly independent from the API settings class —
  shared env var names are a repo convention, not a Python import
  dependency. The decision to use `str` over `PostgresDsn` avoids
  pulling in Pydantic URL-type validation semantics that would widen
  the contract beyond the evidenced smoke-test requirement.

### Finding 4: Anti-scope coverage is thorough
- Severity: LOW
- Description: The anti-scope section (proposal lines 113-129)
  enumerates twelve explicit exclusions spanning API metadata fields,
  staging guild ID, service keys, OCR/LLM keys, cross-service URLs,
  client constructor options, nested models, env prefixes, dotenv
  ownership, custom validators, and singleton helpers. Each exclusion
  maps to a real expansion path: for example, the API settings module
  already carries `discord_staging_guild_id`, `supabase_service_key`,
  and four provider API keys (`services/api/app/core/settings.py:13-22`)
  that could have migrated into the daemon settings by analogy. The
  anti-scope fence prevents that analogy-driven expansion.

### Finding 5: Minimal future burden
- Severity: LOW
- Description: The module is new with no migration path to manage.
  Future daemon configuration needs are additive — new fields can be
  appended without modifying the existing three-field contract. The
  explicit no-dotenv-loading decision aligns with the API settings
  pattern and avoids the monorepo `.env` pitfall documented in the
  research (research lines 339-359), where `extra=forbid` combined
  with dotenv auto-loading would reject unrelated keys. The only
  ongoing obligation is that the daemon entry point must instantiate
  `Settings()` and pass dotenv loading responsibility upstream, which
  is the same pattern the codebase already follows.
