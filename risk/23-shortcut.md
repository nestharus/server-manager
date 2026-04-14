# Shortcut Risk Assessment: Discord Settings

## Overall: LOW

## Findings

### Finding 1: `str` instead of `PostgresDsn` is a documented tradeoff, not deferred validation
- Severity: LOW
- Description: The proposal types `supabase_db_url` as `str` rather than
  Pydantic's `PostgresDsn`, which means malformed or non-Postgres URLs
  are not rejected at settings construction time. This could appear to
  be a shortcut that defers URL validation to the database driver at
  connection time. However, the proposal documents this explicitly in
  the Tradeoffs section and explains the rationale: it matches the
  synthesized requirement directly and avoids adding stricter URL-policy
  validation into an early settings module. The research confirms that
  `PostgresDsn` accepts the smoke-test value `postgresql://test`, so
  the stricter type would not break the test contract — but adopting it
  would also introduce rejection behavior (e.g., for `postgresql:///db`
  empty-host forms) that the proposal deliberately excludes from scope.
  The API service uses the identical `str` typing for the same field:
  `services/api/app/core/settings.py:15`.
- Recommendation: None. The tradeoff is documented, consistent with
  the API precedent, and the anti-scope explicitly excludes DB URL
  format validation.

### Finding 2: `repr=False` instead of `SecretStr` leaves secrets as plain strings at runtime
- Severity: LOW
- Description: The proposal uses `Field(..., repr=False)` for
  `discord_bot_token` and `supabase_db_url` instead of Pydantic's
  `SecretStr` type. `repr=False` prevents secrets from appearing in
  `repr()` output (logs, tracebacks), but the values remain plain `str`
  at runtime and could leak through other serialization paths (e.g.,
  `model_dump()`, `json()`, or accidental f-string interpolation). This
  could appear to be a shortcut that defers proper secret handling.
  However, the proposal acknowledges this explicitly in the Tradeoffs
  section: "`repr=False` satisfies the immediate leak-prevention
  requirement without adding secret-wrapper ergonomics to every
  consumer." The API settings module uses the same `repr=False` pattern
  for all its sensitive fields: `services/api/app/core/settings.py:11`,
  `services/api/app/core/settings.py:15`,
  `services/api/app/core/settings.py:16`. Adopting `SecretStr` would
  require every consumer to call `.get_secret_value()`, which is an
  ergonomic cost the proposal is not prepared to impose at this stage.
- Recommendation: None. The decision is documented, matches the
  existing API convention, and the test contract correctly encodes the
  repr-hiding behavior.

### Finding 3: Three-field surface omits API base URL that architecture evidences
- Severity: LOW
- Description: The research identifies that an API base URL is a
  "daemon-adjacent configuration concern" because the architecture says
  the daemon may call the API service for mutations
  (`AGENTS.md:365`, `AGENTS.md:396`). The proposal omits this field,
  which could appear to be deferring a known requirement. However, the
  proposal's Tradeoffs section explains the choice: "This keeps the
  daemon contract anchored to what the research actually proves today."
  No current daemon code, test, or env var references an API base URL.
  The anti-scope section explicitly excludes "API base URLs or other
  cross-service transport settings not yet used by the daemon." Adding
  a speculative field would violate the proposal's own design principle
  of anchoring to evidenced requirements. When the daemon-to-API call
  path is implemented, adding the field is an additive, non-breaking
  change.
- Recommendation: None. The omission is deliberate, documented, and
  the future addition path is straightforward.

### Finding 4: No `model_config` specification for `extra` field handling
- Severity: LOW
- Description: The proposal does not specify whether the Settings class
  should set `model_config` with an `extra` policy (e.g.,
  `extra="forbid"` or `extra="ignore"`). In a monorepo with a shared
  `.env` containing keys from multiple services, this could matter: if
  `extra="forbid"` were set alongside dotenv loading, unrelated env
  keys would cause `ValidationError`. However, this is a non-issue
  because the proposal explicitly prohibits dotenv auto-loading ("Do
  not set `env_file` in `model_config`, and do not call `load_dotenv()`
  inside `settings.py`"). Without dotenv loading, `BaseSettings` only
  reads env vars matching declared field names, so extra keys in the
  environment are silently ignored regardless of the `extra` setting.
  The API settings module also does not set `model_config`:
  `services/api/app/core/settings.py:5`. The proposal's instruction to
  not set `env_file` in `model_config` demonstrates awareness of this
  configuration surface without over-specifying it.
- Recommendation: None. The no-dotenv decision neutralizes any risk
  from the unspecified `extra` policy, and the approach is consistent
  with the API precedent.
