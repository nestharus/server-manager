# Research: Discord Daemon Settings Module

Date: 2026-04-13

## Scope

This note documents the problem space for a Discord daemon settings
module at `services/discord/app/core/settings.py`.

It is limited to:

- what configuration the daemon is already evidenced to need
- what `pydantic-settings` documents about field loading, env naming,
  and source priority
- what `discord.py` documents about runtime configuration surfaces,
  especially intents
- what Supabase documents about Postgres connection strings
- how those external facts fit this repository's current service split

It does not propose a final settings class, inheritance structure, or
implementation.

## Local Baseline

- The repo architecture treats the Discord daemon and API as separate
  services:
  [AGENTS.md](/home/nes/discord/AGENTS.md:361).
- The architecture text says the Discord daemon may call the API
  service for mutations, while also handling gateway events itself:
  [AGENTS.md](/home/nes/discord/AGENTS.md:365),
  [AGENTS.md](/home/nes/discord/AGENTS.md:373),
  [AGENTS.md](/home/nes/discord/AGENTS.md:396).
- The API service already has a `BaseSettings` model with direct field
  names for Discord and Supabase configuration:
  [services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:5).
- The API tests encode the current env surface as uppercase,
  unprefixed names such as `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`,
  `SUPABASE_DB_URL`, and `SUPABASE_SERVICE_KEY`:
  [services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:7).
- The repo-wide `.env.example` uses the same unprefixed names and
  already marks `SUPABASE_DB_URL` as PostgreSQL-shaped with the example
  `postgresql://...`:
  [.env.example](/home/nes/discord/.env.example:1).
- The current daemon entry point still reads env vars manually from the
  repo-root `.env`, requires `DISCORD_BOT_TOKEN` and
  `DISCORD_GUILD_ID`, parses the guild ID as `int`, and builds intents
  via `discord.Intents.default()` with `guilds=True`,
  `members=True`, and `message_content=False`:
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:28),
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:42),
  [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:66).
- The daemon entry tests lock in the same requirements:
  [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:96),
  [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:142).
- `services/discord/` already depends on `pydantic-settings`, but does
  not yet contain its own settings module:
  [services/discord/pyproject.toml](/home/nes/discord/services/discord/pyproject.toml:6),
  [services/discord/app/core/__init__.py](/home/nes/discord/services/discord/app/core/__init__.py:1).

## Primary Sources

### Local repo

- [AGENTS.md](/home/nes/discord/AGENTS.md:361)
- [.env.example](/home/nes/discord/.env.example:1)
- [services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:5)
- [services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:7)
- [services/api/pyproject.toml](/home/nes/discord/services/api/pyproject.toml:1)
- [services/discord/pyproject.toml](/home/nes/discord/services/discord/pyproject.toml:1)
- [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:28)
- [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:90)

### External documentation

- Pydantic settings management:
  https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Pydantic URL / DSN types:
  https://docs.pydantic.dev/2.0/usage/types/urls/
- `discord.py` client API:
  https://discordpy.readthedocs.io/en/v2.4.0/api.html
- `discord.py` gateway intents primer:
  https://discordpy.readthedocs.io/en/v2.4.0/intents.html
- `discord.py` interactions API:
  https://discordpy.readthedocs.io/en/v2.4.0/interactions/api.html
- Discord developer API reference:
  https://docs.discord.com/developers/reference
- Supabase Postgres connection docs:
  https://supabase.com/docs/guides/database/connecting-to-postgres

### Local runtime inspection

- On 2026-04-13, `services/api/.venv/bin/python` reported
  `pydantic 2.13.0` and `pydantic-settings 2.13.1`.
- In that environment, a minimal `BaseSettings` model accepted direct
  constructor kwargs in the exact smoke-test shape:
  `discord_bot_token="test"`, `discord_guild_id=1`,
  `supabase_db_url="postgresql://test"`.
- In that same environment, `PostgresDsn` rejected non-Postgres schemes
  and empty-host URLs, but accepted `postgresql://test`.

## 1. `pydantic-settings` for a Discord daemon: fields, types, and validation facts

### What the current repo already evidences

The daemon-side runtime currently proves three required inputs:

- bot token
- guild ID
- database location

Evidence:

- [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:42)
  requires `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID`
- [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:57)
  also resolves a database path
- [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:96)
  and [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:120)
  verify token presence and integer guild ID parsing

Inference from the monorepo architecture: because the daemon may call
the API service, an API base URL is a daemon-adjacent configuration
concern at the architecture level even though no local code or test
currently defines that field yet:
[AGENTS.md](/home/nes/discord/AGENTS.md:365),
[AGENTS.md](/home/nes/discord/AGENTS.md:396).

### What `BaseSettings` guarantees

The Pydantic docs state that if a model inherits from `BaseSettings`,
fields not passed as keyword arguments are loaded from the environment,
while explicitly passed initializer kwargs override env loading. The
documented priority order places initializer arguments above
environment variables and dotenv values.

Evidence:

- Pydantic settings docs: initializer fills fields not passed as kwargs,
  and manual overrides are expected in unit tests:
  https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Field priority order:
  initializer args before env vars before dotenv:
  https://docs.pydantic.dev/latest/concepts/pydantic_settings/

That matches the smoke-test requirement that this construction must
work:

```python
Settings(
    discord_bot_token="test",
    discord_guild_id=1,
    supabase_db_url="postgresql://test",
)
```

and local runtime inspection on 2026-04-13 confirmed that it does.

### Bot token

Discord's API reference describes bot authentication as using "a bot
token found on the Bot page within your app's settings" and sending it
in the `Authorization` header as `Authorization: Bot TOKEN`.

Evidence:

- Discord API reference, Authentication:
  https://docs.discord.com/developers/reference

The documentation characterizes it as an opaque credential, not a
structured identifier. The current API settings module also treats
`discord_bot_token` as a `str` with `repr=False`:
[services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:11).

### Guild ID

Discord's API reference states that Discord IDs are snowflakes, up to
64 bits in size, and are serialized as strings in the HTTP API to avoid
overflow issues in some languages.

Evidence:

- Discord API reference, Snowflakes / ID serialization:
  https://docs.discord.com/developers/reference

Local repo code and tests, however, already normalize `DISCORD_GUILD_ID`
to Python `int`:

- [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:52)
- [services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:12)
- [services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:77)

So the repo's current contract is "Discord snowflake stored as Python
integer", even though Discord's HTTP wire format is string-oriented.

### Database URL / `supabase_db_url`

The repo-wide env contract and API settings already treat
`SUPABASE_DB_URL` as a required setting:

- [.env.example](/home/nes/discord/.env.example:7)
- [services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:15)
- [services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:61)

Supabase's own docs state that Postgres clients connect with a
connection string and show PostgreSQL DSN examples such as:

```text
postgresql://postgres:[YOUR-PASSWORD]@db.<project>.supabase.co:5432/postgres
```

They also document pooler URLs in `postgres://...` form.

Evidence:

- Supabase "Connect to your database":
  https://supabase.com/docs/guides/database/connecting-to-postgres

So the evidence supports "`supabase_db_url` is a PostgreSQL connection
string", not a Supabase REST endpoint and not a service key.

### DSN type and validation facts

Pydantic's URL type docs describe `PostgresDsn` as supporting these
schemes:

- `postgres`
- `postgresql`
- `postgresql+asyncpg`
- `postgresql+pg8000`
- `postgresql+psycopg`
- `postgresql+psycopg2`
- `postgresql+psycopg2cffi`
- `postgresql+py-postgresql`
- `postgresql+pygresql`

The same docs say `PostgresDsn` is intended for Postgres URLs and show
an additional field validator example to enforce that a database name
is present, which means "valid Postgres URL" and "URL includes a DB
name" are not the same validation boundary.

Evidence:

- Pydantic URL docs:
  https://docs.pydantic.dev/2.0/usage/types/urls/

Local runtime inspection on 2026-04-13 adds one important repo-specific
fact: in the installed `pydantic 2.13.0`, `PostgresDsn` accepted
`postgresql://test`, rejected `http://example.com`, and rejected
empty-host forms like `postgresql:///db`.

That matters because the requested smoke-test constructor uses the
minimal value `supabase_db_url="postgresql://test"`.

## 2. Shared vs. separate settings: what the repo currently evidences

The repository currently evidences shared environment names across
services, but not a shared Python settings package.

Evidence:

- The architecture explicitly separates `services/api` and
  `services/discord`:
  [AGENTS.md](/home/nes/discord/AGENTS.md:361).
- The only explicitly shared package named in the architecture is
  `packages/shared-types/`, and it is TypeScript/OpenAPI-oriented, not
  Python runtime configuration:
  [AGENTS.md](/home/nes/discord/AGENTS.md:384).
- The API already owns its own settings class in its own service tree:
  [services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:5).
- `services/discord/` declares its own dependency on
  `pydantic-settings`. Inference from that dependency plus the service
  split: the daemon package is prepared to own a service-local settings
  model rather than depending on the API package's settings module:
  [services/discord/pyproject.toml](/home/nes/discord/services/discord/pyproject.toml:6).
- There is no existing shared Python `settings` module or shared Python
  package surfaced by the repo search; all current `BaseSettings`
  usage is inside the API service.

The current evidence therefore shows:

- shared env var names at the repo level
- separate service packaging
- one existing service-local settings module
- no existing shared Python configuration layer

It does not, by itself, establish a shared-base or duplication policy.

## 3. Environment variable naming in a shared monorepo `.env`

### What the repo uses today

The checked-in `.env.example` uses uppercase, descriptive, unprefixed
names:

- `DISCORD_BOT_TOKEN`
- `DISCORD_GUILD_ID`
- `DISCORD_STAGING_GUILD_ID`
- `SUPABASE_DB_URL`
- `SUPABASE_SERVICE_KEY`

Evidence:

- [.env.example](/home/nes/discord/.env.example:1)
- [services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:7)

### What `pydantic-settings` documents

Pydantic documents three facts that matter here:

1. By default, the environment variable name is the same as the field
   name.
2. The default `env_prefix` is the empty string.
3. Environment variable names are case-insensitive by default.

Evidence:

- Pydantic settings docs, environment variable names and
  case-sensitivity:
  https://docs.pydantic.dev/latest/concepts/pydantic_settings/

For this repo, those facts explain why a field named
`discord_bot_token` can read from `DISCORD_BOT_TOKEN` without extra
aliasing in the current API module.

### What `env_prefix` changes

The Pydantic docs also state that `env_prefix` applies not only to
environment variables but also to dotenv files, secrets, and other
sources.

Evidence:

- Pydantic settings docs:
  https://docs.pydantic.dev/latest/concepts/pydantic_settings/

So a service-specific prefix is not just a naming style choice; it
changes which keys are considered valid across all settings sources.

### Shared `.env` constraint

Pydantic's docs say dotenv values are loaded and passed to the model
regardless of `env_prefix` unless `dotenv_filtering` is used, and with
the default `extra=forbid`, unknown keys in the dotenv file raise
`ValidationError`.

Evidence:

- Pydantic settings docs, dotenv behavior:
  https://docs.pydantic.dev/latest/concepts/pydantic_settings/

That is relevant to this monorepo because the single `.env.example`
already contains keys for Discord, Supabase, Railway, and multiple OCR /
LLM providers:
[.env.example](/home/nes/discord/.env.example:1).

The repo's current API settings model avoids this issue by not
declaring an `env_file` at all; its tests set env vars directly through
`monkeypatch`:
[services/api/tests/test_settings.py](/home/nes/discord/services/api/tests/test_settings.py:29).

## 4. `discord.py` integration facts: config patterns and intents

### Runtime configuration surface

`discord.py` documents that intents are passed to `discord.Client` or
its subclasses via the required `intents` constructor argument. The
client constructor also exposes runtime options such as
`member_cache_flags` and `chunk_guilds_at_startup`.

Evidence:

- `discord.Client(*, intents, **options)`:
  https://discordpy.readthedocs.io/en/v2.4.0/api.html

This is the main `discord.py` configuration pattern evidenced by the
docs: constructor options and an `Intents` object, not a library-owned
settings module.

### Intents

The `discord.py` intents primer states:

- intents are passed to `Client` or subclasses through `intents=...`
- `Intents.default()` is the common baseline in examples
- `Intents.members` is privileged
- `Message Content` is also privileged
- privileged intents must be enabled both in the Developer Portal and
  in code

Evidence:

- `discord.py` intents primer:
  https://discordpy.readthedocs.io/en/v2.4.0/intents.html

The same primer links specific use-cases to specific intents:

- `Intents.members` is tied to join/leave tracking, member updates,
  `Guild.chunk()`, `Guild.fetch_members()`, and high-accuracy member
  cache
- `Intents.message_content` is tied to reading message content,
  attachments, embeds, components, polls, and prefix commands that are
  not mention-only

Evidence:

- `discord.py` intents primer:
  https://discordpy.readthedocs.io/en/v2.4.0/intents.html

That lines up with the current daemon code and tests, which require:

- `guilds=True`
- `members=True`
- `message_content=False`

Evidence:

- [daemon/__main__.py](/home/nes/discord/daemon/__main__.py:66)
- [tests/test_daemon_entry.py](/home/nes/discord/tests/test_daemon_entry.py:142)

### Startup hook and command registration

`discord.py` documents `setup_hook()` as the asynchronous setup point
that runs after login but before the websocket connection, and says it
is only called once. The docs explicitly describe it as a better place
for async setup than `on_ready()`.

Evidence:

- `discord.Client.setup_hook()` docs:
  https://discordpy.readthedocs.io/en/v2.4.0/api.html

For slash commands, the interactions API documents:

- `CommandTree.sync()` must be called for application commands to show up
- passing `guild=` to `sync()` syncs guild commands instead of global
  ones
- `@app_commands.guilds(...)` associates commands with specific guilds
  so they are added as default guild commands rather than global ones

Evidence:

- `CommandTree.sync()` docs:
  https://discordpy.readthedocs.io/en/v2.4.0/interactions/api.html
- `app_commands.guilds()` docs:
  https://discordpy.readthedocs.io/en/v2.4.0/interactions/api.html

The current daemon entry module already follows exactly that pattern:
[daemon/__main__.py](/home/nes/discord/daemon/__main__.py:90).

### Additional client options shaped by intents

The client constructor docs say:

- `member_cache_flags` defaults to caching as much as possible given the
  selected intents
- `chunk_guilds_at_startup` defaults to `True` when
  `Intents.members` is `True`

Evidence:

- `discord.Client` API docs:
  https://discordpy.readthedocs.io/en/v2.4.0/api.html

This means the daemon's intent choice influences more than event
delivery; it also changes startup and member-cache behavior.

## 5. Supabase connection string format

Supabase's Postgres docs distinguish between several connection-string
forms:

- direct connection:
  `postgresql://postgres:[YOUR-PASSWORD]@db.<project>.supabase.co:5432/postgres`
- session pooler:
  `postgres://postgres.<ref>:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres`
- transaction pooler:
  `postgres://postgres:[YOUR-PASSWORD]@db.<project>.supabase.co:6543/postgres`

Evidence:

- Supabase connection docs:
  https://supabase.com/docs/guides/database/connecting-to-postgres

The same docs say:

- Postgres clients use a connection string
- persistent application traffic should use either the direct
  connection string or session-mode pooler, depending on network
  support
- transaction mode is for temporary/serverless clients

Evidence:

- Supabase connection docs:
  https://supabase.com/docs/guides/database/connecting-to-postgres

For this repo, the key fact is narrower: `supabase_db_url` is evidenced
to be a Postgres DSN, and the current placeholder
`SUPABASE_DB_URL=postgresql://...` in `.env.example` matches Supabase's
documented format:
[.env.example](/home/nes/discord/.env.example:7).

## Direct Answers

### 1. What fields does a Discord daemon settings module need, and what types/validation are evidenced?

Currently evidenced fields are:

- `discord_bot_token`: opaque bot credential string
- `discord_guild_id`: Discord snowflake, currently normalized as Python
  `int` in repo code/tests
- `supabase_db_url`: PostgreSQL connection string
- inference from architecture: an API base URL is a daemon-adjacent
  concern because the daemon may call the API, but no current field or
  test names it yet

Validation evidenced by current code/docs:

- token presence is required
- guild ID presence is required and non-integer values are rejected
- Postgres DSN typing can enforce Postgres schemes, but stricter URL
  invariants are a separate question from the repo's smoke-test
  requirement

### 2. What does the repo currently show about shared vs separate settings?

It shows separate services, shared env names, one existing API-local
settings module, and no shared Python settings base.

### 3. What env naming convention is currently evidenced?

Uppercase, descriptive, unprefixed env var names in one shared repo
`.env`, matching lowercase snake_case field names under Pydantic's
default case-insensitive lookup.

### 4. What config pattern does `discord.py` use?

Constructor-based configuration with an explicit `Intents` object,
plus client options such as member cache flags and startup chunking.
`setup_hook()` and `CommandTree.sync()` are the documented startup seams
for command registration.

### 5. What format does `supabase_db_url` take?

A PostgreSQL connection string. Supabase documents both
`postgresql://...` direct URLs and `postgres://...` pooler URLs.
