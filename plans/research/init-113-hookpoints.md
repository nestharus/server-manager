# INIT-113 Hookpoints

Reusable substrate:

- Image builds: `infra/scripts/build-channel-image.sh`.
- Local CI emulator: `infra/scripts/run-local-buildkite-pipeline.py`.
- CNPG operator and backup style:
  `gitops/channels/local/data-plane/sample-app/cluster.yaml`.
- Atlas operator and AtlasMigration style:
  `gitops/channels/local/data-plane/sample-app/atlas-migration.yaml`.
- InfisicalSecret style:
  `gitops/channels/local/data-plane/sample-app/*infisicalsecret.yaml`.
- Kong ingress style:
  `gitops/channels/local/ingress/default-services/minio/ingress.yaml`.
- Local DNS rewrite style:
  `gitops/channels/local/ingress/default-services/minio/alias-service.yaml`.
- Pod security labels:
  `infra/channels/local.yaml` and `gitops/channels/local/security`.

Application hookpoints:

- API import root: install `services/api`, run from `/app/services/api`.
- API factory: `app.core.factory:create_api_app`.
- API health path: `/api/v1/health`.
- API readiness path: `/api/v1/ready`.
- Discord import root: install `services/discord`, run from
  `/app/services/discord`.
- Discord API base URL: `http://server-manager-api.server-manager.svc.cluster.local:8000`.
- Existing migrations: root `alembic.ini` and `migrations/versions`.

Files added by implementation:

- Containerfiles under `containers/server-manager/`.
- App image wrapper under `infra/scripts/`.
- GitOps subtree under `gitops/channels/local/applications/`.
- Static and runtime harness under `infra/tests/`.
- INIT-114 handoff under `docs/`.
