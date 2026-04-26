# INIT-113 Problem Research: Application Workloads

INIT-113 is the first slice that deploys the existing server-manager
application onto the Phase 5 substrate instead of another sample workload.
The substrate is already present locally: Flux and Kustomize own
`gitops/channels/local`, INIT-108 owns registry naming through
`infra/scripts/build-channel-image.sh`, INIT-109 owns the Buildkite local
runner, INIT-111 owns CNPG and Atlas, INIT-104 owns MinIO, INIT-110 owns Kong,
INIT-105 owns the local Step issuer, INIT-107 owns pod-security conventions,
and INIT-112 owns the CNPG backup shape.

Evidence:

- API runtime entrypoint is `services/api/app/core/factory.py:create_api_app`.
- API health endpoint is `GET /api/v1/health`.
- API readiness endpoint checks database connectivity, `alembic_version`, and
  the scheduler loop at `GET /api/v1/ready`.
- Discord daemon entrypoint is `services/discord/app/__main__.py`.
- Discord daemon probes API health before logging in.
- API settings require `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`,
  `SUPABASE_DB_URL`, and `SUPABASE_SERVICE_KEY`.
- Discord settings require `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, and
  `API_BASE_URL`.
- Existing schema migrations are Alembic Python migrations under
  `migrations/versions`, driven by root `alembic.ini`.
- Existing Atlas operator proof is a SQL-directory `AtlasMigration`; it cannot
  execute the existing Alembic Python migration chain directly.

The hard problem is integration, not application behavior. The deployment must
package the current Python services without rewriting them, create a dedicated
CNPG cluster, run the existing migrations, source runtime secrets through
InfisicalSecret resources, expose the API through Kong and Step-issued TLS, and
prove that the local registry path works for both app images.

Out of scope remains auth, tenant isolation, and observability. Discord gateway
connectivity with a real token is an operator step because it is a visible live
server integration.
