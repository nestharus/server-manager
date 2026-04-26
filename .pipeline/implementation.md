# INIT-104 Implementation

## Status

INIT-104 is implemented across seven slices:

- `SLICE-104.01`: strict `object_storage` channel schema, local MinIO block,
  optional Vultr block, inheritance, and Vultr endpoint derivation.
- `SLICE-104.02`: pinned host `mc` installer support at
  `RELEASE.2025-08-13T08-35-41Z`.
- `SLICE-104.03`: Infisical `platform-storage` bootstrap and
  `InfisicalSecret/minio-root`.
- `SLICE-104.04`: raw single-node MinIO manifests for the local channel.
- `SLICE-104.05`: idempotent bucket creation Job for `humility-local-sample`.
- `SLICE-104.06`: provider-neutral S3 round-trip script.
- `SLICE-104.07`: local cluster object-storage harness and documentation.

## Pins

- MinIO server:
  `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z@sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e`
- MinIO Client image:
  `quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z@sha256:a7fe349ef4bd8521fb8497f55c6042871b2ae640607cf99d9bede5e9bdf11727`
- Host `mc` binary:
  `mc.RELEASE.2025-08-13T08-35-41Z`,
  SHA256 `01f866e9c5f9b87c2b09116fa5d7c06695b106242d829a8bb32990c00312e891`

## Verification

Static harness:

```bash
bash infra/tests/validate_platform_bootstrap.sh
```

Cluster harness:

```bash
bash infra/tests/validate_platform_bootstrap.sh --cluster
```

Focused object-storage proof after a local channel is up:

```bash
KUBECONFIG=~/.kube/humility-local.yaml \
  bash infra/tests/validate_object_storage_local.sh
```

Standalone S3-compatible round trip:

```bash
bash infra/scripts/test-s3-roundtrip.sh
```

The round-trip script reads only `S3_ENDPOINT`, `S3_ACCESS_KEY_ID`,
`S3_SECRET_ACCESS_KEY`, `S3_REGION`, and `S3_BUCKET`.

## Handoff To INIT-105

- INIT-105 can treat `minio.minio-system.svc.cluster.local:9000` as the local
  internal S3 endpoint; INIT-104 does not expose MinIO through ingress or TLS.
- DNS/TLS work should not modify the MinIO root credential flow. Credentials
  remain in Infisical project `platform-storage`, path `/object-storage/local/`.
- If INIT-105 adds local DNS names or TLS termination for storage, it should
  add a new Service/Ingress layer without changing the internal ClusterIP
  Service contract used by the bucket Job and harness.
- Remote Vultr Object Storage remains a contract only. INIT-104 did not create
  Vultr buckets, remote Flux resources, or remote `InfisicalSecret` manifests.

## Residual Risks

- MinIO is intentionally single-node local storage. It proves S3 semantics and
  credential flow, not HA object durability.
- Root credentials are used for local MinIO bootstrap only. App-scoped storage
  credentials and rotation are deferred to later storage/application work.
