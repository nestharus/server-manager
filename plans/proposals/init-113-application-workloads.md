# INIT-113 Proposal: Application Workloads

Deploy server-manager as a local GitOps application with two Python images,
a dedicated CNPG database, Alembic migration job, Atlas migration guard,
Infisical-managed secrets, MinIO bucket bootstrap, Kong ingress, and a focused
validation harness.

## Architecture

- `containers/server-manager/Containerfile.api` builds the FastAPI service from
  the repo root and starts `uvicorn app.core.factory:create_api_app`.
- `containers/server-manager/Containerfile.discord` builds the Discord daemon
  and starts `python -m app`.
- `infra/scripts/build-server-manager-images.sh` wraps INIT-108's channel image
  builder for `server-manager-api` and `server-manager-discord`.
- `.buildkite/pipeline.yml` gains INIT-113 static validation and app image
  build steps.
- `gitops/channels/local/applications/server-manager` owns the app namespace,
  CNPG cluster, InfisicalSecret resources, Atlas guard migration, Alembic job,
  API deployment, Discord deployment, service, ingress, and policies.
- `infra/tests/validate_application_workloads_local.sh` validates the static
  contract and, when a cluster is present, proves API Pod readiness, database
  migration, Kong curl, and Discord Pod presence.

## Migration Strategy

Atlas remains the platform migration operator. Because the current app schema is
already expressed as Alembic Python migrations, INIT-113 uses an AtlasMigration
guard to prove the target database URL, create Atlas revision state, and provide
operator visibility. The actual application schema is applied by a Kubernetes
Job running the app API image with `alembic -c /app/alembic.ini upgrade heads`.

This is a wrapper around the existing migration system, not a schema rewrite.
Converting Alembic migrations into first-class Atlas SQL migrations is not in
scope for INIT-113.

## Anti-Scope

- No auth or tenant policy.
- No Discord-visible mutation or command execution.
- No observability stack.
- No remote deployment.
- No compatibility shims or alternate service entrypoints.

## Acceptance

- Static kustomize renders the local root with the application subtree.
- App image names resolve through INIT-108's channel builder.
- Local Buildkite dry-run includes the INIT-113 steps.
- Runtime harness can prove API Ready, DB connected and migrated, Kong ingress
  returns 200 for `/api/v1/health`, and the Discord Deployment exists with at
  least one Pod created.
