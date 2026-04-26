# INIT-114 Handoff: Auth After Application Workloads

INIT-113 deploys server-manager API and Discord workloads locally without
adding auth. The API exposes the existing unauthenticated service surface
behind Kong at `https://api.local.humility.local`.

INIT-114 should start from these deployed resources:

- Namespace: `server-manager`
- API Service: `server-manager-api.server-manager.svc.cluster.local:8000`
- Local host: `api.local.humility.local`
- Runtime secret: `Secret/server-manager-runtime`, synced from
  Infisical project `server-manager`, env `local`, path `/runtime/local`
- Database: `Cluster/server-manager-postgres`, database `server_manager`
- Database URL secret: `Secret/server-manager-postgres-url`

Required auth decisions:

- Which API endpoints remain unauthenticated health/readiness probes.
- Kong edge policy versus in-app auth enforcement.
- Service-to-service identity for the Discord daemon.
- Operator and future web UI identity model.

Do not move the runtime secrets out of Infisical, change the image naming
contract, or add tenant-isolation policy in INIT-114. Tenant isolation remains
INIT-116.

