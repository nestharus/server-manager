# Audit Risk Assessment: Discord Settings

## Overall: LOW

The proposal is well-scoped, consistent with the existing API settings
pattern, and backed by thorough research. No blocking issues were
identified. Implementation can proceed as designed.

## Findings

### Finding 1: `repr=False` prevents repr leakage but not direct-access leakage
- Severity: LOW
- Description: The proposal uses `repr=False` on `discord_bot_token` and
  `supabase_db_url` to prevent credential exposure in `repr()`, logging
  frameworks that call `repr()`, and tracebacks. This matches the API
  settings module exactly
  ([services/api/app/core/settings.py:11](/home/nes/discord/services/api/app/core/settings.py:11)).
  However, the values remain plain strings at runtime, so code that logs
  `settings.discord_bot_token` directly (not via repr) would still leak
  the credential. The alternative, `SecretStr`, forces callers to use
  `.get_secret_value()`, which adds friction to every consumer. The
  proposal explicitly acknowledges this tradeoff and chooses consistency
  with the API module over wrapper ergonomics, which is the right call
  at this stage.
- Recommendation: None. If the project later adopts structured logging
  that serializes settings objects by field access rather than repr,
  revisit the `SecretStr` upgrade. This is not a current concern.

### Finding 2: `supabase_db_url: str` admits non-Postgres connection strings
- Severity: LOW
- Description: The proposal types `supabase_db_url` as `str` rather than
  `PostgresDsn`. This means a value like `http://example.com` would pass
  settings validation and only fail later when the database driver
  attempts to connect. The research confirmed that `PostgresDsn` rejects
  non-Postgres schemes at validation time
  ([research/23-discord-settings.md](/home/nes/discord/research/23-discord-settings.md:247)).
  However, the API settings module also uses `str` for the same field
  ([services/api/app/core/settings.py:15](/home/nes/discord/services/api/app/core/settings.py:15)),
  and the proposal's smoke-test value `postgresql://test` is accepted by
  both `str` and `PostgresDsn`. The tradeoff is explicitly documented:
  avoiding stricter URL-policy validation in an early settings module.
- Recommendation: None. The fail-fast benefit of `PostgresDsn` is real
  but marginal — a misconfigured DB URL will fail within seconds at
  connection time regardless. If both services later tighten their DB URL
  validation, they can adopt `PostgresDsn` in lockstep.

### Finding 3: Field inventory matches evidenced daemon requirements
- Severity: LOW
- Description: The three fields (`discord_bot_token`, `discord_guild_id`,
  `supabase_db_url`) are directly evidenced by the current daemon entry
  point
  ([daemon/__main__.py:42](/home/nes/discord/daemon/__main__.py:42)),
  the repo's `.env.example`
  ([.env.example:1](/home/nes/discord/.env.example:1)),
  and the API settings module
  ([services/api/app/core/settings.py:11](/home/nes/discord/services/api/app/core/settings.py:11)).
  The proposal correctly excludes `discord_staging_guild_id` (the daemon
  currently operates against a single primary guild),
  `supabase_service_key` (the daemon connects via Postgres DSN, not the
  Supabase REST API), and all OCR/LLM provider keys (daemon-side
  concerns only if the architecture evolves). The research notes that an
  API base URL is "daemon-adjacent" because the daemon may call the API
  service
  ([research/23-discord-settings.md:124](/home/nes/discord/research/23-discord-settings.md:124)),
  but the proposal correctly defers this to anti-scope since no current
  code or test evidences it.
- Recommendation: None. The minimal surface is appropriate. Future fields
  should be added when evidenced by actual daemon code, not speculatively.

### Finding 4: No dotenv auto-loading is the correct default
- Severity: LOW
- Description: The proposal explicitly prohibits `env_file` in
  `model_config` and `load_dotenv()` inside `settings.py`. This matches
  the API settings pattern
  ([services/api/tests/test_settings.py:29](/home/nes/discord/services/api/tests/test_settings.py:29))
  and avoids the monorepo `.env` pitfall documented in the research:
  with `extra=forbid` (Pydantic's default for `BaseSettings`), dotenv
  loading would inject all `.env` keys and raise `ValidationError` for
  unrecognized fields like `RAILWAY_TOKEN` or `GOOGLE_CLOUD_VISION_KEY`
  ([research/23-discord-settings.md:346](/home/nes/discord/research/23-discord-settings.md:346)).
  The current daemon entry point calls `load_dotenv()` at the module
  level
  ([daemon/__main__.py:31](/home/nes/discord/daemon/__main__.py:31)),
  so that responsibility stays with the entry point, not the settings
  class.
- Recommendation: None. The test contract correctly encodes the
  expectation that `.env` file presence alone must not make `Settings()`
  succeed, which guards against accidental dotenv regression.

### Finding 5: Test contract covers the right boundaries
- Severity: LOW
- Description: The proposal's test contract encodes seven verification
  points: constructor success, attribute access, env resolution, kwarg
  override, missing-field rejection, integer coercion, and repr
  suppression, plus two negative constraints (no implicit dotenv, no
  DSN-specific rejection). These boundaries are well-drawn. The
  constructor smoke test matches the exact shape verified by the
  research's local runtime inspection against `pydantic 2.13.0` and
  `pydantic-settings 2.13.1`
  ([research/23-discord-settings.md:96](/home/nes/discord/research/23-discord-settings.md:96)).
  The env override test ensures the `BaseSettings` priority order
  (init args > env vars) is locked in, which is critical for test
  isolation.
- Recommendation: None. The test boundaries are comprehensive for the
  module's scope.
