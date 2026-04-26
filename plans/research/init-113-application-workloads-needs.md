# INIT-113 Needs Synthesis

Humility needs a local-first application deployment that proves the real
server-manager workloads fit the platform primitives from INIT-101 through
INIT-112. The local environment should answer four operator questions:

1. Can the API and Discord daemon be built as channel-tagged images and pushed
   through the local registry contract?
2. Can the API boot against a dedicated CNPG cluster after the existing Alembic
   migrations run?
3. Can the API be reached through the Kong local hostname with Step-issued TLS?
4. Can the Discord daemon Pod start against the in-cluster API service, while
   leaving real Discord login dependent on operator-seeded Infisical secrets?

Binding needs:

- Keep application code unchanged unless packaging exposes a true runtime bug.
- Use the existing root Alembic migration chain for schema creation.
- Keep all credentials behind InfisicalSecret resources.
- Create a separate CNPG cluster named `server-manager-postgres`.
- Create and use the MinIO bucket `server-manager`.
- Use the INIT-108 image naming convention:
  `localhost:5000/local/<app>:<tag>` for push and
  `k3d-humility-local:5000/local/<app>:<tag>` for pull.
- Deploy under `gitops/channels/local/applications/`.
- Make static validation possible without a live cluster and runtime validation
  meaningful when local k3d is available.

Open operational gap:

- The Infisical paths must be seeded by an operator. The manifests assume
  `platform-databases:/postgres/local/server-manager`,
  `server-manager:/runtime/local`, and
  `platform-storage:/object-storage/local`.
