# INIT-109 Research: Buildkite CI/CD

## Scope

INIT-109 needs a local-first CI/CD path that adds Buildkite without weakening
the INIT-108 image registry contract. The questions are whether Buildkite can
run locally from YAML, how the Kubernetes agent is installed, how tokens are
provided, and how a development proof can run before production Buildkite SaaS
setup exists.

## Buildkite Agent Install

Buildkite offers a general self-hosted agent and an Agent Stack for Kubernetes.
The core agent is a runner that polls Buildkite for work over HTTPS, accepts a
job, runs the command, streams logs, reports status, and uploads artifacts. The
Agent Stack for Kubernetes is a controller that watches scheduled jobs assigned
to its queue and creates Kubernetes Jobs to execute them.

The Kubernetes stack has a Helm path upstream, but this repository's local
platform is already represented as raw GitOps manifests under
`gitops/channels/local`. INIT-109 therefore uses raw manifests for a minimal
single-agent Deployment rather than introducing Helm release orchestration in
this slice. That keeps the blast radius aligned with the existing local channel
contracts.

Agent token requirements are strict. Current Buildkite Kubernetes stack docs say
v0.28.0 and later use the Agent REST API and require only a cluster agent token;
the organization slug and cluster UUID can be inferred from the token. Older
GraphQL-token flows are not a good baseline for INIT-109.

## Pipeline Definition Format

Buildkite pipeline steps are YAML. A repository-local `pipeline.yml` lets the
pipeline be versioned, audited, and reviewed with the code. The conventional
location is `.buildkite/pipeline.yml`; `buildkite-agent pipeline upload` looks
there by default if no path is supplied.

The file supports top-level `agents`, `env`, and `steps`. Command steps carry
the shell command. Wait steps sequence groups of command steps. The upload
command can dry-run and render the pipeline, but that is validation, not job
execution.

## Local Buildkite Mode

The researched answer is no: Buildkite's real agent does not run arbitrary local
pipeline YAML offline. It polls the Buildkite Agent API for assigned work. The
`buildkite-agent pipeline upload --dry-run` command can validate/render pipeline
YAML without uploading, but it does not execute jobs.

INIT-109 therefore needs an explicit local CI emulator. The emulator should:

- read `.buildkite/pipeline.yml`;
- support the subset this project owns now: top-level env, command steps, wait
  steps, labels, and keys;
- execute selected command steps in order;
- reject unsupported step types instead of silently pretending they ran;
- leave the real Buildkite agent and token flow intact for SaaS execution.

This is a local development tool, not a compatibility shim for old behavior.

## Toolchain

The Buildkite-side toolchain is `buildkite-agent`. INIT-109 pins the agent image
to `buildkite/agent:3.104.0` because Buildkite's CLI docs call out newer
multi-pipeline behavior starting in that series. The local image build toolchain
continues to use INIT-108's `infra/scripts/build-channel-image.sh`, Docker, and
the channel resolver.

## Source Links

- Buildkite agent overview: https://buildkite.com/docs/agent
- Buildkite Agent Stack for Kubernetes: https://buildkite.com/docs/agent/self-hosted/agent-stack-k8s
- Defining pipeline steps: https://buildkite.com/docs/pipelines/configure/defining-steps
- `buildkite-agent pipeline`: https://buildkite.com/docs/agent/cli/reference/pipeline
