# INIT-110 Handoff: Buildkite Production Wiring

INIT-109 added the local-first CI/CD substrate:

- `.buildkite/pipeline.yml` is the canonical pipeline definition.
- Local development can execute the owned subset with
  `infra/scripts/run-local-buildkite-pipeline.py`.
- Local validation lives at `infra/tests/validate_buildkite_cicd_local.sh`.
- The Buildkite agent token path is Infisical project `platform-cicd`,
  environment `local`, path `/buildkite/local`, key `BUILDKITE_AGENT_TOKEN`.
- Raw local agent manifests live under `gitops/channels/local/cicd`.
- Image build/push continues to use INIT-108's
  `infra/scripts/build-channel-image.sh`.

INIT-110 should own production Buildkite SaaS setup:

- create the Buildkite organization cluster/queue/pipeline;
- connect repository provider/webhooks;
- seed the real agent token into Infisical with
  `infra/scripts/bootstrap-infisical-cicd.sh`;
- decide whether production builds use a custom agent image with Docker tooling
  or a Kubernetes-native build executor;
- keep deployment promotion separate from INIT-109's build/push proof.
