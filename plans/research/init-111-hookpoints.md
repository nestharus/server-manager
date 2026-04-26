# INIT-111 Hookpoints

## Existing Surfaces to Reuse

- `infra/scripts/resolve_platform_channel.py`: channel contract resolver.
- `infra/channels/local.yaml` and `infra/channels/dev.yaml`: active channel
  declarations.
- `infra/schemas/platform-channel.schema.json` and
  `infra/schemas/platform-channel-resolved.schema.json`: schema gates.
- `gitops/channels/local/kustomization.yaml`: local GitOps root.
- `gitops/channels/local/infisical/operator`: Infisical Operator CRD and sync
  behavior.
- `gitops/channels/local/object-storage`: MinIO service, bucket, and credentials
  Secret.
- `infra/scripts/install-flux-for-channel.sh`: post-reconcile local bootstrap
  path for Infisical-backed runtime credentials.
- `.buildkite/pipeline.yml`: local CI entrypoint.

## Implementation Map

- Add optional `data_plane` block to both channel schemas.
- Add `data_plane` blocks to local and dev channel YAML.
- Add `gitops/channels/local/data-plane/cnpg` with namespace and upstream raw
  manifest.
- Add `gitops/channels/local/data-plane/sample-app` with namespace,
  InfisicalSecret resources, CNPG Cluster, Atlas migration ConfigMap, and
  AtlasMigration.
- Add `gitops/channels/local/data-plane/atlas` with namespace, values, and
  rendered chart output.
- Include `data-plane` from the local root kustomization.
- Add `infra/scripts/bootstrap-infisical-databases.sh`.
- Add `infra/tests/validate_data_plane_local.sh`.

## Delete Nothing

No INIT-103, INIT-104, INIT-107, INIT-108, INIT-109, or INIT-110 files should
be deleted. INIT-111 extends their contracts.
