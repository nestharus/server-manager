# INIT-109 Hookpoints

## Existing Surfaces to Reuse

- `infra/scripts/build-channel-image.sh`: single image build/push entrypoint.
- `infra/tests/validate_container_delivery_local.sh`: cluster pull proof model.
- `infra/scripts/resolve_platform_channel.py`: source of channel runtime config.
- `infra/channels/local.yaml` and `infra/channels/dev.yaml`: active channel
  declarations.
- `infra/schemas/platform-channel.schema.json` and
  `infra/schemas/platform-channel-resolved.schema.json`: schema gate.
- `gitops/channels/local/kustomization.yaml`: local GitOps root.
- `gitops/channels/local/infisical/*`: InfisicalSecret pattern.

## Reusable Patterns

- Shell harnesses report `PASS:` and fail fast for runtime proof.
- Infisical bootstrap scripts resolve channel metadata rather than duplicating
  constants.
- Runtime secrets are not committed; Infisical CRs describe the sync target.
- Local proof scripts accept `--kubeconfig` and default to
  `~/.kube/humility-local.yaml`.

## Implementation Map

- Channel schema: add optional `cicd` alongside `image_registry`.
- Pipeline: add `.buildkite/pipeline.yml`.
- Local runner: add `infra/scripts/run-local-buildkite-pipeline.py`.
- Token bootstrap: add `infra/scripts/bootstrap-infisical-cicd.sh`.
- Agent manifests: add `gitops/channels/local/cicd` and include it from the
  local root kustomization.
- Harness: add `infra/tests/validate_buildkite_cicd_local.sh`.

## Delete Nothing

No INIT-108 files should be deleted. The new code calls the existing image
builder and consumes the existing channel resolver.
