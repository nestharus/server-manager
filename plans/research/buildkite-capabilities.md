# Buildkite Capabilities vs Legacy CI Platform

## 1. Executive summary

Buildkite can replace most of the legacy **CI/CD control-plane** assumptions described in the merged corpus: GitLab-runner style private execution, generic YAML CI placeholders, manual approval gates, build artifact handoff, and much of the bespoke scheduler/orchestration logic wrapped around Dagger or custom pipeline glue. Its best fit is a hybrid model where Buildkite provides the control plane and your own infrastructure provides the execution plane through self-hosted agents, including Kubernetes.

Buildkite does **not** replace every category in the old stack. It is a CI/CD scheduler and governance surface, not a general event bus, not CDC, and not a deployment reconciler. Flux covers the reconciliation side well: Git remains the source of truth, Flux updates or reacts to image/tag changes, and receivers make pull-based GitOps responsive enough for normal deployment automation. That means **Buildkite + Flux can eliminate the Kafka/Debezium/Redis layer if that layer exists mainly to move CI/CD state, approvals, image promotions, and environment sync**. If Kafka, Debezium, or Redis are carrying runtime-domain events or database change capture for applications, they remain.

Recommendation: adopt **Buildkite for CI** and **Flux for CD/GitOps**. Delete the bespoke orchestration layer unless it serves a real non-CI/CD runtime need. Do not keep Dagger, GitLab-runner assumptions, or a Kafka-style deployment bus as canonical by default.

## 2. Capability comparison table

| Legacy assumption / need | Buildkite coverage | Assessment |
| --- | --- | --- |
| GitLab-runner style private execution | Self-hosted agents, queues, clusters, scoped agent tokens | Direct replacement |
| Pipelines as code | Repo-managed pipeline YAML plus dynamic pipeline upload | Direct replacement |
| Manual approvals / deploy gates | `block` steps, team-scoped unblock permissions, trigger steps | Direct replacement |
| Artifact handoff between jobs | Native artifact upload/download and API access | Direct replacement for build-scoped handoff |
| Artifact or package promotion | Package Registries plus downstream triggers | Partial replacement; use registries, not ephemeral artifacts, for releases |
| Dagger-centered orchestration | Buildkite replaces scheduling and pipeline control | Partial replacement; Dagger's execution abstraction is not replaced one-for-one |
| Secrets | Buildkite Secrets, access policies, OIDC to cloud IAM | Strong replacement, but external secret managers may still be better for strict threat models |
| Enterprise governance | SSO, audit log, templates, Terraform management, EventBridge/webhooks | Strong replacement, though some features are plan-gated |
| Kubernetes-native execution | Agent Stack for Kubernetes creates one Kubernetes Job/Pod per scheduled job | Direct replacement for Kubernetes executor assumptions |
| Kafka/Debezium/Redis orchestration for CI/CD | Webhooks, metadata, triggers, package registries, Flux reconciliation | Replaceable only if that layer exists for CI/CD choreography rather than app/runtime concerns |

## 3. What Buildkite replaces vs what remains

### What Buildkite replaces directly

- Private runner pools and queueing assumptions from GitLab-runner style designs.
- Static or placeholder CI YAML with repo-defined pipelines and dynamic step generation.
- Manual approval checkpoints with first-class `block` and `trigger` steps.
- Basic artifact passing between jobs and across pipelines.
- Most custom CI scheduler glue for fan-out, fan-in, conditional execution, metadata passing, and chained pipelines.

### What Buildkite replaces only partially

- **Dagger**: Buildkite replaces the control-plane reason teams often adopt Dagger, but not Dagger's programmable build engine. If some Dagger modules encode real build logic, they can run inside Buildkite jobs during migration, but they should be treated as transitional unless they still buy something concrete.
- **Artifact promotion**: Buildkite artifacts are build-oriented. Long-lived promotion should use OCI/packages plus Git or GitOps state. Buildkite Package Registries help here, but an external registry may still be the better system of record.
- **Secrets**: Buildkite covers many cases, but OIDC plus cloud-native secret retrieval is cleaner where secrets must stay out of the CI vendor's control plane.

### What remains outside Buildkite

- GitOps reconciliation and drift correction: **Flux**
- Database change capture: **Debezium**
- General event streaming: **Kafka**
- Any broader coordination/cache role unrelated to CI/CD: **Redis**
- Thin platform glue around publishing images/packages, policy checks, and release metadata

### Likely remaining bespoke glue

- Registry publish conventions and release metadata mapping
- GitOps repo write policy if you do not rely solely on Flux image automation
- Organization-specific policy checks or approval policy not expressible in Buildkite/Flux primitives
- Any genuine runtime eventing that is not part of CI/CD

## 4. Kubernetes/self-hosting fit

This is a strong fit, not a workaround. Buildkite is designed to separate control plane from execution plane, and its self-hosted agent model maps cleanly onto private infrastructure. The Kubernetes path is especially credible because Buildkite's Agent Stack for Kubernetes schedules each job as a Kubernetes Job with a single Pod, which is close to the mental model teams already have from GitLab's Kubernetes executor but without carrying GitLab-specific runner assumptions forward.

For this platform, that means Buildkite can support:

- private execution inside your own cluster
- per-queue or per-cluster isolation
- custom pod specs, images, sidecars, and resource controls
- container build strategies such as BuildKit, Kaniko, or other preferred builders
- stricter hardening than fully hosted CI agents

The main caveat is that you still own cluster operations: capacity, base images, network policy, caching strategy, and container-build security. Also note the current Buildkite Kubernetes stack requires Kubernetes `1.29+` for newer controller versions that use native sidecars.

## 5. Risks and caveats

- **Category mismatch**: Buildkite is not a replacement for a general event platform or CDC stack.
- **Secrets tradeoff**: Buildkite Secrets are decrypted on Buildkite application servers before delivery to agents. For stricter environments, prefer OIDC-federated runtime retrieval from your cloud secret manager.
- **Enterprise concentration**: Some of the strongest governance features sit behind higher Buildkite plans, so plan fit matters if auditability and centralized controls are hard requirements.
- **Artifacts are not releases**: Do not model long-lived promotion on Buildkite artifacts alone.
- **Cross-cluster rules are not a stable baseline yet**: Buildkite's rules system for cross-cluster triggering and artifact reads is currently opt-in early access. Do not make that the foundation of the design if simpler same-cluster or registry/GitOps flows work.
- **Migration risk is mostly simplification risk**: the main failure mode is dragging old abstractions forward and rebuilding the bespoke orchestration layer on top of Buildkite instead of deleting it.

## 6. Recommendation for this platform

Use **Buildkite as the CI control plane** and **Flux as the CD/GitOps reconciler**.

That implies:

1. Replace GitLab-runner and generic CI placeholders with Buildkite clusters, queues, and repo-managed pipelines.
2. Standardize execution on self-hosted agents, preferably Kubernetes-backed for Linux/container workloads.
3. Use Buildkite approvals, triggers, artifacts, package registries, metadata, webhooks, and OIDC instead of custom CI event plumbing.
4. Use Flux receivers and image automation to remove bespoke deployment-choreography logic.
5. Delete Kafka/Debezium/Redis orchestration that exists only to coordinate CI/CD state transitions, image promotion, deploy approvals, or environment sync.
6. Keep Kafka, Debezium, or Redis only where they serve a real runtime/application role outside CI/CD.

Bottom line: **yes, Buildkite can replace the legacy platform assumptions for the CI/CD portion of the corpus.** Buildkite plus Flux should remove most of the custom orchestration layer. What remains should be thin, explicit glue, not a second homegrown control plane.

## Sources

- Buildkite architecture: https://buildkite.com/docs/pipelines/architecture
- Buildkite self-hosted agents: https://buildkite.com/docs/agent/self-hosted
- Buildkite Agent Stack for Kubernetes: https://buildkite.com/docs/agent/self-hosted/agent-stack-k8s
- Buildkite dynamic pipelines: https://buildkite.com/docs/pipelines/configure/dynamic-pipelines
- Buildkite block steps: https://buildkite.com/docs/pipelines/configure/step-types/block-step
- Buildkite artifacts: https://buildkite.com/docs/pipelines/configure/artifacts
- Buildkite Package Registries: https://buildkite.com/docs/package-registries
- Buildkite Secrets: https://buildkite.com/docs/pipelines/security/secrets/buildkite-secrets
- Buildkite clusters and rules: https://buildkite.com/docs/pipelines/security/clusters and https://buildkite.com/docs/pipelines/security/clusters/rules
- Buildkite OIDC: https://buildkite.com/docs/pipelines/security/oidc
- Buildkite audit log: https://buildkite.com/docs/platform/audit-log
- Buildkite IaC/Terraform management: https://buildkite.com/docs/pipelines/best-practices/iac
- Flux webhook receivers: https://fluxcd.io/flux/guides/webhook-receivers/
- Flux image update automation: https://fluxcd.io/flux/components/image/imageupdateautomations/
- Dagger CI overview: https://docs.dagger.io/quickstart/ci/
