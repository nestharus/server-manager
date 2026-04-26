# INIT-110 Hookpoints

## Existing Surfaces to Reuse

- `infra/scripts/resolve_platform_channel.py`: channel contract resolver.
- `infra/channels/local.yaml` and `infra/channels/dev.yaml`: active channel
  declarations.
- `infra/schemas/platform-channel.schema.json` and
  `infra/schemas/platform-channel-resolved.schema.json`: schema gates.
- `gitops/channels/local/kustomization.yaml`: local GitOps root.
- `gitops/channels/local/tls/local-issuer`: local StepClusterIssuer contract.
- `gitops/channels/local/dns/coredns-configmap.yaml`: local hostname rewrite.
- `gitops/channels/local/object-storage/minio`: MinIO backend service.
- `gitops/channels/local/security`: network policy baseline.

## Implementation Map

- Add optional `ingress` block to both channel schemas.
- Add `ingress` blocks to local and dev channel YAML.
- Add `gitops/channels/local/ingress/kong` with namespace, values, and rendered
  upstream chart output.
- Add `gitops/channels/local/ingress/default-services/minio` with an
  ExternalName alias, Ingress, and network policies.
- Include `ingress` from the local root kustomization.
- Add `infra/tests/validate_kong_ingress_local.sh`.
- Add unit tests for the channel contract and committed manifests.

## Delete Nothing

No INIT-105, INIT-107, INIT-108, or INIT-109 files should be deleted. INIT-110
extends their contracts.
