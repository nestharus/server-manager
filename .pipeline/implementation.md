# INIT-103 Implementation

## Status

INIT-103 is complete across the runtime-secret slices:

- `SLICE-103.02`: added committed raw Infisical server manifests rendered from
  `infisical-standalone` chart `1.8.0`.
- `SLICE-103.03`: added committed raw Infisical Kubernetes Operator manifests
  rendered from `secrets-operator` chart `0.10.32`, including all Operator
  CRDs.
- `SLICE-103.04`: added bootstrap-only server secret handling and the
  idempotent host-side Universal Auth identity bootstrap.
- `SLICE-103.05`: extended the channel schemas and local channel contract with
  strict Infisical configuration, then added the sample `InfisicalSecret`
  reconciliation proof.
- `SLICE-103.06`: extended the bootstrap harness with local-cluster runtime
  assertions for server readiness, PVC binding, Operator readiness,
  Universal Auth, sample sync, idempotency, and Postgres Pod restart recovery.
- `SLICE-103.07`: consolidated operator documentation and recorded the
  INIT-104 object-storage handoff.

## Done State

The local channel owns a real runtime-secret path:

- Flux reconciles `gitops/channels/local/infisical/server`,
  `gitops/channels/local/infisical/operator`, and
  `gitops/channels/local/infisical/sample`.
- Infisical runs in `infisical-system` with in-cluster PostgreSQL and Redis.
- The Operator runs in `infisical-system` and authenticates through
  `Secret/infisical-operator-auth`.
- The bootstrap-only server config lives in
  `gitops/bootstrap/infisical-server-bootstrap.enc.yaml`.
- `InfisicalSecret/infisical-local-sample` in `infisical-sample` syncs
  `Secret/infisical-local-sample` with
  `INFISICAL_SAMPLE_KEY=infisical-local-ready`.

SOPS+age remains bootstrap-only. Runtime secrets are not committed to SOPS
files; they belong in Infisical and are consumed through `InfisicalSecret`.

## Verification

Canonical no-cluster harness:

```bash
bash infra/tests/validate_platform_bootstrap.sh
```

Canonical local-cluster harness:

```bash
bash infra/tests/validate_platform_bootstrap.sh --cluster
```

Manual runtime proof after bring-up:

```bash
KUBECONFIG=~/.kube/humility-local.yaml \
  kubectl get infisicalsecret,secret -n infisical-sample
```

Expected resources are `InfisicalSecret/infisical-local-sample` and
`Secret/infisical-local-sample`.

## INIT-104 Handoff

INIT-104 consumes the INIT-103 runtime-secret substrate. It should not create a
parallel SOPS path, Helm runtime path, or alternate secret-management system.

Available contract:

- Local Infisical server endpoint:
  `http://infisical.infisical-system.svc.cluster.local:8080`.
- Local channel Infisical project: `platform-local`.
- Local channel environment: `local`.
- Local sample path already proven by INIT-103: `/sample`.
- Operator namespace: `infisical-system`.
- Universal Auth Secret name: `infisical-operator-auth`.
- Universal Auth Secret namespace: `infisical-system`.
- Sample consumer namespace: `infisical-sample`.
- Sample target Secret name: `infisical-local-sample`.
- `resync_interval`: `60s`.

Object-storage credential contract:

- INIT-104 uses the Infisical project bound by D10 for storage credentials:
  `platform-storage`.
- INIT-104 stores object-storage credentials below
  `/object-storage/<channel>/...`, where `<channel>` is the channel id such as
  `local`.
- Local MinIO keys:

  ```text
  /object-storage/<channel>/MINIO_ROOT_USER
  /object-storage/<channel>/MINIO_ROOT_PASSWORD
  ```

- Remote Vultr Object Storage keys:

  ```text
  /object-storage/<channel>/VULTR_OS_ACCESS_KEY
  /object-storage/<channel>/VULTR_OS_SECRET_KEY
  ```

- INIT-104 authors its own `InfisicalSecret` CRs in the object-storage
  namespace it owns. The expected local consumer namespace is `minio-system`.
- INIT-104 chooses whether to reuse the INIT-103 Universal Auth credential or
  create an INIT-104-owned Machine Identity scoped to `platform-storage`.
- MinIO and Vultr Object Storage credentials must not be added to
  `gitops/bootstrap/` or any SOPS-encrypted file.

Open questions for INIT-104:

- Does `platform-storage` get a dedicated INIT-104 Machine Identity, or does
  it temporarily reuse `infisical-operator-auth`?
- Is the local object-storage namespace exactly `minio-system`, and does it
  also own the target Kubernetes Secret names?
- What are the final target Kubernetes Secret names and key casing for MinIO
  and Vultr Object Storage consumers?
- Should `/object-storage/<channel>/...` be recursive in one
  `InfisicalSecret`, or should INIT-104 split MinIO and remote credentials into
  separate CRs?
- What rotation and break-glass expectations are deferred to INIT-115 versus
  owned immediately by INIT-104?
