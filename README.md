# server-manager

Tooling for running one Discord server. It started as a small command-line tool that reads a server's state (channels, roles, bots, messages) through the Discord API and prints JSON, so people and coding agents can inspect it safely. It has since grown into three services: a FastAPI backend backed by Postgres that holds membership applications, tickets, chapters, roles and permissions, trust, compliance evidence, notifications and an audit log; a Discord bot that turns server interactions into calls to that API; and a small web UI. The repo also holds the infrastructure to run all of it on a local Kubernetes cluster (k3s via k3d). It is built for one specific server and is not a general-purpose product.

## What's in the repo

| Path | Contents |
|------|----------|
| `discord_cli.py` | Read-only inspection CLI for the configured server (prints JSON) |
| `daemon/` | Original minimal bot (SQLite, a `/ping` command) and YAML config loader |
| `services/api/` | FastAPI service (`app/`: endpoints under `/api/v1`, services, repositories, background tasks) |
| `services/discord/` | discord.py bot that forwards interactions to the API |
| `services/web/` | SolidJS + TanStack Router web UI (Vite, Playwright tests) |
| `services/shared/` | Settings contracts shared by the Python services |
| `migrations/`, `alembic.ini` | Alembic migrations for the Postgres schema |
| `chapters.yaml`, `forms/` | YAML chapter registry and application form definitions |
| `policy/cedar/` | Cedar authorization policies per channel (local, dev) for the API |
| `containers/` | Containerfiles for the API, Discord bot and web images |
| `infra/` | OpenTofu modules, channel definitions, operator scripts and infra tests (see `infra/README.md`) |
| `gitops/` | Flux manifests for the cluster: Infisical, Kong, Authentik, Pomerium, OPAL, CloudNativePG, MinIO, cert-manager, observability (see `gitops/README.md`) |
| `.buildkite/` | CI pipelines (unit, service, web and static infra checks; image builds) |
| `tests/` | Root-level tests |
| `docs/`, `plans/`, `proposals/`, `research/`, `risk/`, `product-strategy/`, `prototyping/` | Design notes, plans and review records |
| `AGENTS.md`, `DECISIONS.md`, `NOTES.md` | Working rules for coding agents, recorded decisions, server notes |

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/) (used by the CI pipeline for the services)
- A Discord bot token for the server being managed
- Postgres for the API (the API tests start one with testcontainers, so they need Docker)
- Node.js 22.15 or newer and npm 11.6.2 or newer for the web UI
- For the cluster setup: the pinned tools listed in `infra/README.md` (OpenTofu, kubectl, Docker, k3d, Flux, Helm, SOPS, age and others)

## Install

```bash
git clone https://github.com/nestharus/server-manager.git
cd server-manager
cp .env.example .env          # then fill in values
uv sync                       # root CLI and legacy daemon
(cd services/api && uv sync --dev)
(cd services/discord && uv sync --dev)
(cd services/web && npm ci)
```

The web UI depends on Font Awesome / Web Awesome packages from a private registry; `npm run tokens:npmrc` in `services/web` writes an `.npmrc` from the token variables below.

## Configuration

Settings are read from environment variables (the root CLI and legacy daemon load them from `.env` at the repo root). Names only:

- Root CLI and legacy daemon: `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `DATABASE_PATH` (optional, SQLite file for the daemon)
- API, required: `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `SUPABASE_DB_URL`, `SUPABASE_SERVICE_KEY`
- API, optional: `APP_NAME`, `APP_VERSION`, `PLATFORM_CHANNEL`, `PLATFORM_TENANT`, `DEBUG`, `API_PREFIX`, `DISCORD_STAGING_GUILD_ID`, `PUBLIC_INTAKE_MEMBER_SALT`, `CEDAR_AUTHORIZATION_URL`, `GOOGLE_CLOUD_VISION_KEY`, `GEMINI_API_KEY`, `Z_AI_API_KEY`, `MINIMAX_API_KEY`
- API, applicant sign-in (Discord OAuth through Authentik): `APPLICANT_OIDC_CLIENT_ID`, `APPLICANT_OIDC_CLIENT_SECRET`, `AUTHENTIK_AUTHORIZE_URL`, `AUTHENTIK_TOKEN_URL`, `AUTHENTIK_JWKS_URL`, `AUTHENTIK_ISSUER_URL`, `APPLICANT_DISCORD_REDIRECT_URI`, `APPLICANT_RECEIPT_SIGNING_KEY`, `APPLICANT_RECEIPT_TTL_SECONDS`
- Authentik itself (cluster setup): `DISCORD_APPLICANT_OAUTH_CLIENT_ID`, `DISCORD_APPLICANT_OAUTH_CLIENT_SECRET`
- Migrations: `DATABASE_URL`, falling back to `SUPABASE_DB_URL`
- Discord bot service: `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `API_BASE_URL` (required); `DISCORD_DRY_RUN` (optional: check the API is reachable, then idle without logging in to Discord)
- Web UI package install: `NPM_TOKEN`, `FA_NPM_TOKEN`, `WA_NPM_TOKEN`

In the cluster, secrets are delivered through Infisical, and bootstrap secrets are encrypted with SOPS + age (`.sops.yaml`).

## Usage

Inspect the server (read-only; prints JSON):

```bash
uv run python discord_cli.py overview
uv run python discord_cli.py channels      # also: roles, bots, integrations
uv run python discord_cli.py find-channel <name>
uv run python discord_cli.py read <channel> --limit 50
uv run python discord_cli.py bot-activity <bot_id> --per-channel-limit 100
```

Run the services locally:

```bash
alembic -c alembic.ini upgrade head                         # from repo root, in the API environment
(cd services/api && uv run uvicorn app.main:app --reload)   # API on /api/v1
(cd services/discord && uv run python -m app)               # Discord bot; needs the API reachable
(cd services/web && npm run dev)                            # web UI
uv run python -m daemon                                     # legacy minimal bot
```

Bring up the local cluster and build images (details in `infra/README.md`):

```bash
bash infra/scripts/install-cluster-tools.sh --check
bash infra/scripts/bring-up-local-channel.sh local
bash infra/scripts/delete-local-channel.sh --channel local
```

## Tests

These are the commands the Buildkite pipeline (`.buildkite/pipeline.yml`) runs:

```bash
python -m pytest tests infra/tests                       # root and infra contract tests
(cd services/api && uv sync --dev && uv run pytest -v tests/)       # needs Docker
(cd services/discord && uv sync --dev && uv run pytest -v tests/)
(cd services/web && npm ci && npm test)                  # Playwright
infra/tests/validate_data_plane_local.sh --static-only   # one of several static infra checks
```

## Status

Last activity: 2026-05-21 (the `main` branch was last updated 2026-04-28). Built for managing one Discord server; it is not a general-purpose product, and much of the repo is planning and review material alongside the code. Remote (cloud) deployment is described in `infra/` as plan-only; the local k3d cluster is the working target.

## License

No license has been chosen yet; all rights reserved.
