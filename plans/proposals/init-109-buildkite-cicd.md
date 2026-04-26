# INIT-109 Proposal: CI/CD via Buildkite

## 1. Summary

INIT-109 adds CI/CD execution without changing the INIT-108 image registry
contract. The implementation has six slices: pipeline artifacts, channel
contract, local Buildkite runner, Infisical token bootstrap, raw Kubernetes
agent manifests, and validation/docs.

The design separates two modes.

Real mode runs a self-hosted Buildkite agent in the local k3d cluster. The agent
uses an Infisical-managed Kubernetes Secret for `BUILDKITE_AGENT_TOKEN` and
polls Buildkite SaaS for jobs.

Local mode executes the repository's `.buildkite/pipeline.yml` through a narrow
emulator. This exists because Buildkite's agent is not an offline YAML runner.
The emulator supports the subset needed by this repo and rejects unsupported
steps.

## 2. Slices

### Slice 1: Pipeline Artifacts

Artifacts:

- `plans/research/init-109-buildkite-cicd.md`
- `plans/research/init-109-buildkite-cicd-needs.md`
- `plans/proposals/init-109-buildkite-cicd.md`
- `plans/risk/init-109-{audit,scope,shortcut}.md`
- `plans/research/init-109-hookpoints.md`

Acceptance:

- decisions D-AGENT-INSTALL through D-VERSION-PINS exist;
- risk gate files say LOW;
- hookpoints map INIT-109 to INIT-108 surfaces.

### Slice 2: Channel Contract

Add optional `cicd` block to both source and resolved schemas. Add the block to
`infra/channels/local.yaml` and `infra/channels/dev.yaml`.

Fields:

- `provider`
- `agent_namespace`
- `agent_image`
- `agent_queue`
- `agent_token_secret_name`
- `agent_token_secret_key`
- `infisical_project`
- `infisical_environment`
- `infisical_path`
- `local_pipeline_file`
- `local_mode`

Acceptance:

- local and dev channels resolve;
- additional properties remain disallowed;
- no old schema version or fallback path is introduced.

### Slice 3: Pipeline and Local Runner

Add `.buildkite/pipeline.yml` with test, echo, and registry build/push steps.
Add `infra/scripts/run-local-buildkite-pipeline.py`.

Runner behavior:

- parse YAML with PyYAML;
- merge top-level and step-level env;
- run command steps in declared order;
- treat wait steps as sequencing markers;
- select steps with repeated `--step-key`;
- dry-run without executing commands;
- reject unsupported steps.

Acceptance:

- unit tests cover selection, env merge, wait handling, and unsupported step
  rejection;
- the runner can execute the echo and image build/push steps for local proof.

### Slice 4: Infisical Token Flow

Add `infra/scripts/bootstrap-infisical-cicd.sh`.

Behavior:

- resolve channel `cicd` fields;
- verify existing operator Universal Auth Secret;
- create/find Infisical project `platform-cicd`;
- create/find environment `local`;
- create/find path `/buildkite/local`;
- write `BUILDKITE_AGENT_TOKEN` only when supplied by environment and absent in
  Infisical;
- grant the existing `local-operator` identity access to the project;
- never write token material to Git or SOPS.

Acceptance:

- help text documents idempotency;
- static harness confirms no token literal exists in committed files.

### Slice 5: Raw Agent Manifests

Add `gitops/channels/local/cicd`.

Objects:

- namespace `buildkite-agent`;
- service account;
- Role/RoleBinding for local job operations;
- InfisicalSecret that syncs `buildkite-agent-token`;
- Deployment using `buildkite/agent:3.104.0`;
- ConfigMap documenting the queue and local pipeline path.

Acceptance:

- root local kustomization includes `cicd`;
- manifests are raw YAML;
- token arrives from Infisical, not SOPS.

### Slice 6: Harness and Handoff

Add `infra/tests/validate_buildkite_cicd_local.sh` and documentation.

Harness behavior:

- verify required files;
- resolve channel and assert `cicd` fields;
- dry-run local pipeline;
- run echo step;
- run registry build/push step when Docker is available;
- if kubeconfig and kubectl are available, run a Pod that pulls the image and
  verifies the INIT-108 log marker;
- report PASS/SKIP counts.

Acceptance:

- static checks pass without a cluster;
- full local proof passes when the INIT-108 local registry/cluster are present.

## 3. Anti-Scope

Production Buildkite organization setup is out of scope. Production repository
provider setup is out of scope. Production deployment automation is out of
scope. Buildkite agent UI ingress is out of scope.

## 4. Risk Notes

The largest risk is pretending Buildkite has an offline local runner. It does
not. The explicit emulator avoids that ambiguity and keeps local iteration
honest.

The second risk is bypassing INIT-108. The container build command is reused
directly so registry naming, push endpoint, and pull endpoint remain centralized.

The third risk is token leakage. The implementation uses Infisical CRs and a
bootstrap script that accepts the token from the caller environment only.

## 5. Line-Item Implementation Plan

001. Preserve INIT-108 image builder as the only image push entrypoint.
002. Preserve INIT-108 local pull proof shape.
003. Add `.buildkite/pipeline.yml`.
004. Add command step key `init-109-smoke`.
005. Add command step key `unit-tests`.
006. Add command step key `registry-build-push`.
007. Add wait step between smoke/test and image build.
008. Add top-level queue `cicd-local`.
009. Add top-level `CHANNEL_ID`.
010. Add top-level `IMAGE_APP`.
011. Add top-level `IMAGE_TAG`.
012. Add top-level `IMAGE_CONTEXT`.
013. Add top-level `IMAGE_FILE`.
014. Add local runner parser.
015. Add local runner step model.
016. Add local runner command execution.
017. Add local runner dry-run output.
018. Add local runner step filtering.
019. Add local runner unsupported-step error.
020. Add local runner wait-step no-op.
021. Add local runner env merge.
022. Add local runner repo-root cwd.
023. Add local runner tests.
024. Add source schema `cicd` property.
025. Add resolved schema `cicd` property.
026. Add `cicd` definition.
027. Add channel local cicd block.
028. Add channel dev cicd block.
029. Keep schema version at 1.
030. Keep `cicd` optional.
031. Add Buildkite namespace manifest.
032. Add service account manifest.
033. Add Role manifest.
034. Add RoleBinding manifest.
035. Add InfisicalSecret manifest.
036. Add Deployment manifest.
037. Add ConfigMap manifest.
038. Add cicd kustomization.
039. Include cicd in local root.
040. Add bootstrap script.
041. Resolve channel in bootstrap script.
042. Verify Infisical server readiness in bootstrap script.
043. Port-forward Infisical in bootstrap script.
044. Login/bootstrap admin token in bootstrap script.
045. Create/find project in bootstrap script.
046. Create/find environment in bootstrap script.
047. Create/find identity access in bootstrap script.
048. Put token only from env in bootstrap script.
049. Leave existing token unchanged.
050. Add harness file checks.
051. Add harness schema checks.
052. Add harness local runner dry-run.
053. Add harness echo execution.
054. Add harness image build/push execution.
055. Add harness optional cluster Pod proof.
056. Add harness PASS/SKIP output.
057. Add docs handoff.
058. Run schema resolution.
059. Run unit tests.
060. Run harness static checks.
061. Run full harness when cluster exists.
062. Commit each slice independently.
063. Record commit SHAs.
064. Record harness counts.
065. Record INIT-110 handoff.

## 6. Detailed Contract Lines

The following numbered contract lines intentionally make the proposal reviewable
at slice granularity.

L001. INIT-109 owns CI/CD execution only.
L002. INIT-109 does not change the registry image naming convention.
L003. INIT-109 does not move registry credentials.
L004. INIT-109 does not introduce production deployment automation.
L005. INIT-109 stores pipeline definition at `.buildkite/pipeline.yml`.
L006. INIT-109 real agent uses `buildkite/agent:3.104.0`.
L007. INIT-109 local queue is `cicd-local`.
L008. INIT-109 local namespace is `buildkite-agent`.
L009. INIT-109 token Secret is `buildkite-agent-token`.
L010. INIT-109 token key is `BUILDKITE_AGENT_TOKEN`.
L011. INIT-109 Infisical project is `platform-cicd`.
L012. INIT-109 Infisical environment is `local`.
L013. INIT-109 Infisical path is `/buildkite/local`.
L014. INIT-109 local runner is explicitly not Buildkite SaaS.
L015. INIT-109 local runner executes command steps.
L016. INIT-109 local runner treats wait steps as sequencing markers.
L017. INIT-109 local runner rejects block steps.
L018. INIT-109 local runner rejects trigger steps.
L019. INIT-109 local runner rejects input steps.
L020. INIT-109 local runner rejects group steps unless later scoped.
L021. INIT-109 local runner merges top-level env.
L022. INIT-109 local runner merges step env.
L023. INIT-109 local runner step env overrides top-level env.
L024. INIT-109 local runner preserves current process env.
L025. INIT-109 local runner sets `BUILDKITE_LOCAL=true`.
L026. INIT-109 local runner sets `BUILDKITE=true`.
L027. INIT-109 local runner exits nonzero on first command failure.
L028. INIT-109 local runner prints selected step labels.
L029. INIT-109 local runner supports repeated `--step-key`.
L030. INIT-109 local runner runs all command steps when no keys are provided.
L031. INIT-109 local runner has dry-run mode.
L032. INIT-109 local runner dry-run does not execute commands.
L033. INIT-109 pipeline has smoke step.
L034. INIT-109 smoke step echoes a deterministic marker.
L035. INIT-109 pipeline has unit test step.
L036. INIT-109 pipeline has registry build step.
L037. INIT-109 registry build step calls `infra/scripts/build-channel-image.sh`.
L038. INIT-109 registry build step uses channel resolver indirectly.
L039. INIT-109 registry build step defaults channel to local.
L040. INIT-109 registry build step defaults app to registry-smoke.
L041. INIT-109 registry build step defaults tag to init-109-local.
L042. INIT-109 registry build step points at `containers/samples/registry-smoke`.
L043. INIT-109 channel schema accepts `cicd`.
L044. INIT-109 channel schema disallows unknown `cicd` fields.
L045. INIT-109 resolved schema accepts inherited `cicd`.
L046. INIT-109 does not add schema version 2.
L047. INIT-109 local channel declares `cicd`.
L048. INIT-109 dev channel declares `cicd`.
L049. INIT-109 dev channel remains contract-only for real remote use.
L050. INIT-109 raw manifests are under local channel GitOps root.
L051. INIT-109 raw manifests do not require Helm.
L052. INIT-109 namespace is labeled restricted.
L053. INIT-109 Deployment reads token through env var from Secret.
L054. INIT-109 Deployment uses non-root security context.
L055. INIT-109 Deployment has no committed token.
L056. INIT-109 Deployment uses queue tag.
L057. INIT-109 Deployment uses agent name from Pod metadata.
L058. INIT-109 Deployment has resource requests.
L059. INIT-109 Deployment has resource limits.
L060. INIT-109 Deployment uses rollout strategy defaults.
L061. INIT-109 InfisicalSecret points at local Infisical service.
L062. INIT-109 InfisicalSecret uses existing Universal Auth Secret.
L063. INIT-109 InfisicalSecret uses projectSlug `platform-cicd`.
L064. INIT-109 InfisicalSecret uses envSlug `local`.
L065. INIT-109 InfisicalSecret uses secretsPath `/buildkite/local`.
L066. INIT-109 bootstrap creates project if absent.
L067. INIT-109 bootstrap creates environment if absent.
L068. INIT-109 bootstrap writes token only from caller environment.
L069. INIT-109 bootstrap leaves existing token unchanged.
L070. INIT-109 bootstrap prints no token.
L071. INIT-109 bootstrap grants local operator access.
L072. INIT-109 harness checks source files.
L073. INIT-109 harness checks schema resolution.
L074. INIT-109 harness checks kustomization inclusion.
L075. INIT-109 harness checks token is not in Git.
L076. INIT-109 harness dry-runs the pipeline.
L077. INIT-109 harness runs smoke step.
L078. INIT-109 harness builds and pushes sample image when Docker is present.
L079. INIT-109 harness verifies Pod pull when kubeconfig exists.
L080. INIT-109 harness skips cluster proof when cluster prerequisites are absent.
L081. INIT-109 full local proof requires Docker.
L082. INIT-109 full local proof requires kubectl.
L083. INIT-109 full local proof requires the local registry.
L084. INIT-109 full local proof requires k3d kubeconfig.
L085. INIT-109 full local proof uses INIT-108 sample marker.
L086. INIT-109 docs hand off production Buildkite setup to INIT-110.
L087. INIT-109 docs identify token path.
L088. INIT-109 docs identify local runner.
L089. INIT-109 docs identify harness command.
L090. INIT-109 docs identify cluster proof command.
L091. INIT-109 keeps production deploy out of scope.
L092. INIT-109 keeps Buildkite UI ingress out of scope.
L093. INIT-109 keeps repository provider setup out of scope.
L094. INIT-109 keeps SaaS workspace setup out of scope.
L095. INIT-109 avoids compatibility shims.
L096. INIT-109 avoids feature flags for old behavior.
L097. INIT-109 deletes no INIT-108 surfaces.
L098. INIT-109 relies on existing local channel bring-up.
L099. INIT-109 relies on existing Infisical operator.
L100. INIT-109 relies on existing registry smoke sample.
