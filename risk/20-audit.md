# Audit Risk Assessment: `services/api/app/core/settings.py`

## Overall: LOW

The proposal defines a straightforward `BaseSettings`-derived
configuration class for the API service. It correctly identifies all
sensitive fields from `.env.example`, marks them with `repr=False`,
excludes deployment-only credentials (`RAILWAY_TOKEN`), avoids dotenv
auto-loading, and keeps validation narrow and evidence-based. The
security posture is appropriate for the scaffold stage. No finding
rises above LOW.

## Findings

### Finding 1: `repr=False` rather than `SecretStr` for sensitive fields

- Severity: LOW
- Description: The proposal uses `repr=False` on all secret fields
  (`discord_bot_token`, `supabase_db_url`, `supabase_service_key`, and
  the four optional provider keys). The research (section 4) documents
  that `repr=False` suppresses secrets in `repr()` output but does not
  mask them in `model_dump()` or `model_dump_json()`. This means that
  any code path that serializes the settings object (logging, debug
  endpoints, error handlers that dump state) would expose raw secrets.
  `SecretStr` would mask across `repr()`, `str()`, and JSON
  serialization. However, the proposal explicitly acknowledges this
  tradeoff and defers `SecretStr` adoption to when the service actually
  consumes these values and serialization paths exist. At the current
  scaffold stage, no serialization code exists in the API service, so
  the exposure surface is theoretical.
- Recommendation: Accept for this phase. When the factory or dependency
  layer is implemented, re-evaluate whether any code path calls
  `model_dump()` on the settings object. If so, upgrade to `SecretStr`
  at that point.

### Finding 2: No `model_config` constraint on `extra` fields

- Severity: LOW
- Description: The proposal does not specify whether `model_config`
  includes `extra = "forbid"`, `extra = "ignore"`, or is omitted
  entirely. The default for `BaseSettings` is `extra = "ignore"`. This
  means that if a process environment contains typos
  (e.g., `DISCORD_BOT_TOLEN` instead of `DISCORD_BOT_TOKEN`), the
  misspelled variable would be silently ignored and the required field
  would raise a validation error with no hint about the near-miss. This
  is a usability concern, not a security vulnerability — the startup
  would still fail, just with a less helpful error message. Setting
  `extra = "forbid"` is not viable because the process environment
  typically contains many unrelated variables (`PATH`, `HOME`, etc.).
- Recommendation: Accept the implicit default. The correct mitigation
  is clear startup error messages from Pydantic's required-field
  validation, which already happens by default.

### Finding 3: `supabase_db_url` stored as opaque `str`

- Severity: LOW
- Description: The proposal types `supabase_db_url` as `str` with
  `repr=False` and no format validation. The research (section 4) notes
  that database DSNs often embed usernames, passwords, hostnames, and
  database names in a single string, making them more sensitive than a
  single-purpose API key. If this string were logged or serialized, it
  would reveal multiple infrastructure details at once. However, the
  proposal already marks the field `repr=False`, the research
  explicitly recommends keeping it as an opaque string at this stage
  (since the DB layer doesn't exist yet), and no code in the current
  scaffold serializes settings. Adding a DSN validator (e.g., requiring
  `postgresql://` scheme) would be premature given the anti-scope.
- Recommendation: Accept. When the database layer is implemented
  (proposal 15), the connection setup code will parse this URL anyway,
  providing implicit format validation at use-time.

### Finding 4: No runtime guard against guild ID confusion

- Severity: LOW
- Description: The proposal defines `discord_guild_id: int` (required)
  and `discord_staging_guild_id: int | None = None` (optional). The
  research (section 4) notes that guild IDs "affect blast radius
  because they select which guild a deployment can act on." If a
  staging deployment accidentally sets `DISCORD_GUILD_ID` to the
  production guild ID, the API would operate on the wrong guild. The
  proposal provides no cross-validation between the two fields (e.g.,
  ensuring they differ when both are present). However, such
  cross-validation is a deployment policy concern, not a settings
  module responsibility. The Tier 3 rule in AGENTS.md already requires
  explicit per-action user approval for visible Discord writes, which
  is the correct control layer for blast-radius protection.
- Recommendation: Accept. Guild targeting safety is enforced at the
  mutation layer (Tier 3 approval), not the configuration layer. A
  validator that rejects identical guild IDs would be a useful
  defensive measure when the staging deployment pattern is established,
  but is premature now.

### Finding 5: `debug: bool = False` has no defined behavior boundary

- Severity: LOW
- Description: The proposal includes `debug: bool = False` as a
  "minimal scaffold flag for local development vs normal runtime" but
  does not specify what `debug=True` enables or constrains. In
  production FastAPI applications, debug mode typically controls
  exception detail in responses, auto-reload, and middleware behavior.
  If a future consumer of this flag inadvertently uses it to enable
  verbose error responses that include stack traces or settings state,
  it could lead to information disclosure. However, at this scaffold
  stage, no consumer of the flag exists, and the proposal explicitly
  excludes middleware and HTTP server settings from scope.
- Recommendation: Accept. When the factory is implemented, ensure that
  `debug=True` does not enable settings serialization in error
  responses or expose stack traces to unauthenticated clients.

### Finding 6: No dotenv auto-loading is a positive security decision

- Severity: LOW (positive finding)
- Description: The proposal explicitly excludes `env_file` from
  `model_config` and states that "environment preparation belongs to
  the caller or process launcher." The research (section 3)
  demonstrates that dotenv loading with the repo-root `.env` would
  either require `extra = "ignore"` (hiding typos) or fail on
  `RAILWAY_TOKEN` and other non-API keys. By delegating dotenv handling
  to the caller, the settings module avoids both issues and remains
  testable without filesystem dependencies. This is the correct
  security posture: the settings module validates its own contract
  without assuming how secrets are delivered.
- Recommendation: None. This is the right design.
