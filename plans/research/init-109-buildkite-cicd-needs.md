# INIT-109 Synthesis: User Needs and Decisions

## Decisions

- D-AGENT-INSTALL: use raw manifests under `gitops/channels/local/cicd`.
- D-AGENT-TOKEN-FLOW: source the agent token from Infisical, project
  `platform-cicd`, environment `local`, path `/buildkite/local`, managed into
  `Secret/buildkite-agent-token` in namespace `buildkite-agent`.
- D-PIPELINE-LOCATION: store the project pipeline at `.buildkite/pipeline.yml`.
- D-LOCAL-CI-MODE: implement local emulation over the same YAML because the real
  Buildkite agent always polls the Buildkite API for jobs.
- D-CHANNEL-SCHEMA-EXT: add optional channel `cicd` block for queue, namespace,
  agent image, Infisical token path, and local pipeline file.
- D-LOCAL-CONTRACT: the harness asserts schema resolution, raw manifest shape,
  local runner execution, echo proof, image build/push, and optional cluster Pod
  pull/run proof.
- D-VERSION-PINS: `buildkite/agent:3.104.0`, Docker CLI `27.5.1`,
  namespace `buildkite-agent`, queue `cicd-local`.

## Humility Context

The project should get CI/CD execution without moving registry concerns out of
INIT-108. The pipeline invokes the existing image builder and uses the channel
resolver for image names. The Buildkite token is runtime-only material and lives
in Infisical, not SOPS or Git.

The local proof needs to be usable before production Buildkite workspace setup.
The local runner is therefore a first-class development harness. Real SaaS
execution remains ready once the token and pipeline exist in Buildkite.

## Gaps

Production Buildkite organization, cluster, queue, repository provider, and
pipeline creation are intentionally out of scope. The raw manifests and
Infisical path define the runtime contract for when that setup exists.
