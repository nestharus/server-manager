# Shortcut Risk: Settings Module

**Overall risk level: LOW**

The proposal is well-disciplined. It correctly narrows the settings
module to the environment contract already evidenced in `.env.example`,
avoids copying the reference module's stack-specific fields and
validators, excludes deployment tooling (`RAILWAY_TOKEN`), and
explicitly anti-scopes middleware, nested config, dotenv ownership, and
credential-shape validation. The tradeoffs section justifies each
simplification with evidence. The few findings below are minor
scope-matching and future-friction concerns, none of which will cause
bugs or block progress.

## Findings

### 1. `repr=False` instead of `SecretStr` is a conscious tradeoff, not a shortcut (LOW)

The proposal chooses `repr=False` over `SecretStr` for sensitive fields
and documents the tradeoff: avoids `.get_secret_value()` friction in the
early scaffold. The research confirms both options' protection surfaces.
The synthesis confirms `repr=False` as the minimum bar.

This is a legitimate scaffold-stage simplification. `repr=False` protects
debug output, and the scaffold has no serialization paths that would leak
secrets via `model_dump()`. Upgrading to `SecretStr` later is a
type-level change that won't require architectural rework.

**Severity:** LOW — no serialization surface exists yet that would expose
secrets beyond `repr()`. The shortcut has no consequence at the current
stage.

### 2. No `model_config` definition leaves `extra` behavior implicit (LOW)

The proposal says `model_config` may be omitted entirely. The default
`BaseSettings` behavior for `extra` is `ignore` (not `forbid`), meaning
unrecognized environment variables are silently discarded. This is
actually the correct behavior for this project — the shared `.env`
contains keys like `RAILWAY_TOKEN` that don't belong to the API settings
class, and `extra='forbid'` would reject them if dotenv loading were
ever added.

However, leaving `model_config` implicit means a future developer
could add `model_config = SettingsConfigDict(...)` with `extra='forbid'`
or `env_file='.env'` without understanding why those were intentionally
omitted. The proposal's anti-scope section covers both dotenv and nested
config, which partially mitigates this.

**Severity:** LOW — the anti-scope documentation is clear enough. The
implicit default happens to be the right one for the project's shared-env
structure. No bug results from omitting `model_config`.

### 3. Flat provider keys defer the enablement-check question (LOW)

The proposal lists four optional provider credentials as
`str | None = None`. The research notes that it's unclear "whether every
provider key must exist at process startup or only when a related feature
path is enabled." The proposal sidesteps this by making them all optional.

This is correct at scaffold stage — no feature code consumes these keys
yet, so there is no enablement check to implement. When OCR/LLM features
are built, the service layer that uses a provider will need to validate
that the required key is present at call time (not at startup). This is
a natural consequence of optional fields, not a shortcut.

**Severity:** LOW — the decision to defer is well-matched to the current
evidence. Making them required would be premature since no consumer
exists. The runtime validation belongs in the service/infrastructure
layer, not in settings.

### 4. `supabase_db_url` kept as opaque `str` skips DSN validation (LOW)

The research identifies that `SUPABASE_DB_URL` is "operationally more
sensitive than an ordinary identifier" and that the reference validates
DB URLs by scheme. The proposal keeps it as `str` on the basis that "the
repo only proves that a DB URL is required, not that startup should
reject every non-Postgres variant."

This is appropriate deferral. The database layer doesn't exist yet in
the API service, so the scheme constraint isn't enforceable against a
real consumer. When the database repository module is built, it will
either use SQLAlchemy (which validates DSNs itself) or a Postgres driver
(which rejects non-Postgres URLs at connection time). Adding a
`field_validator` now would be speculative validation without a consumer
to confirm the constraint.

**Severity:** LOW — database connection libraries validate URLs at
connection time. A settings-level validator would be redundant with the
eventual consumer's own validation.

### 5. Hardcoded `app_version` will drift from `pyproject.toml` (LOW)

The proposal defaults `app_version` to `"0.1.0"` and notes this
"matches current package metadata without adding file I/O or packaging
lookups." The tradeoff is that the version string in settings will
silently diverge from `pyproject.toml` when the package version is
bumped.

This is a known limitation, not a shortcut. Dynamic version reading
(via `importlib.metadata` or file parsing) adds startup complexity for
a value that is currently only used as FastAPI metadata. The divergence
is cosmetic — it affects the OpenAPI docs title, not runtime behavior.

**Severity:** LOW — version drift in API metadata is cosmetic. When
versioning matters (e.g., for API clients checking compatibility), the
`api_prefix` path is the real version contract, and that field is
separately configurable.
